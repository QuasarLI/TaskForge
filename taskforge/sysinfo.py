"""Real hardware and memory telemetry (registry, WMI/CIM, PDH counters, GetPerformanceInfo)."""
import ctypes
import json
import winreg
from ctypes import wintypes

import psutil

from .util import run_powershell


# ---------------------------------------------------------------- CPU identity
def cpu_identity() -> dict:
    info = {"name": "Unknown processor", "vendor": "", "base_mhz": 0,
            "cores": psutil.cpu_count(logical=False) or 0,
            "threads": psutil.cpu_count(logical=True) or 0}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            info["name"] = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            info["vendor"] = winreg.QueryValueEx(k, "VendorIdentifier")[0].strip()
            info["base_mhz"] = int(winreg.QueryValueEx(k, "~MHz")[0])
    except OSError:
        pass
    return info


def cpu_vendor_family(name: str, vendor: str) -> str:
    text = f"{name} {vendor}".lower()
    if "intel" in text:
        return "intel"
    if "amd" in text or "authenticamd" in text:
        return "amd"
    return "other"


def is_unlocked_cpu(name: str) -> bool:
    """Best-effort guess from the model string (Intel 'K'/'X' SKUs, AMD Ryzen)."""
    import re
    n = name.upper()
    if "RYZEN" in n or "THREADRIPPER" in n:
        return True
    return bool(re.search(r"I[3579]-\d{4,5}K|\d{3,5}KF?S?\b|-\d{4,5}X|ULTRA \d \d{3}K", n))


INVENTORY_PS = r"""
$ErrorActionPreference='SilentlyContinue'
$o=[ordered]@{}
$o.cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,Manufacturer,MaxClockSpeed,CurrentClockSpeed,ExtClock,L2CacheSize,L3CacheSize,NumberOfCores,NumberOfLogicalProcessors,VirtualizationFirmwareEnabled,SocketDesignation,Caption
$o.board = Get-CimInstance Win32_BaseBoard | Select-Object -First 1 Manufacturer,Product
$o.bios = Get-CimInstance Win32_BIOS | Select-Object -First 1 Manufacturer,SMBIOSBIOSVersion,ReleaseDate
$o.system = Get-CimInstance Win32_ComputerSystem | Select-Object -First 1 Manufacturer,Model,PCSystemType,AutomaticManagedPagefile,TotalPhysicalMemory
$o.dimms = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer,PartNumber,Capacity,Speed,ConfiguredClockSpeed,DeviceLocator)
$o.pagefiles = @(Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage)
$o.disks = @(Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,Size)
$o | ConvertTo-Json -Depth 4 -Compress
"""


def hardware_inventory() -> dict:
    """Slow (1-3 s) WMI inventory. Call from a worker thread."""
    rc, out, _ = run_powershell(INVENTORY_PS, timeout=60)
    if rc != 0 or not out.strip():
        return {}
    try:
        data = json.loads(out)
    except ValueError:
        return {}
    for key in ("dimms", "pagefiles", "disks"):
        val = data.get(key)
        if isinstance(val, dict):
            data[key] = [val]
        elif val is None:
            data[key] = []
    return data


# ------------------------------------------------------- Live effective clock
class LiveClock:
    """Effective CPU clock from the PDH '% Processor Performance' counter (same source Task Manager uses)."""

    def __init__(self, base_mhz: int):
        self.base = base_mhz
        self.query = None
        self.counter = None
        try:
            import win32pdh
            self._pdh = win32pdh
            self.query = win32pdh.OpenQuery()
            path = r"\Processor Information(_Total)\% Processor Performance"
            try:
                self.counter = win32pdh.AddEnglishCounter(self.query, path)
            except Exception:
                self.counter = win32pdh.AddCounter(self.query, path)
            win32pdh.CollectQueryData(self.query)
        except Exception:
            self.query = None

    def mhz(self) -> int:
        if self.query and self.base:
            try:
                self._pdh.CollectQueryData(self.query)
                _, val = self._pdh.GetFormattedCounterValue(self.counter, self._pdh.PDH_FMT_DOUBLE)
                return int(self.base * val / 100.0)
            except Exception:
                pass
        try:
            f = psutil.cpu_freq()
            return int(f.current) if f else 0
        except Exception:
            return 0


# ---------------------------------------------------------- Memory internals
class PERFORMANCE_INFORMATION(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD),
                ("CommitTotal", ctypes.c_size_t), ("CommitLimit", ctypes.c_size_t),
                ("CommitPeak", ctypes.c_size_t), ("PhysicalTotal", ctypes.c_size_t),
                ("PhysicalAvailable", ctypes.c_size_t), ("SystemCache", ctypes.c_size_t),
                ("KernelTotal", ctypes.c_size_t), ("KernelPaged", ctypes.c_size_t),
                ("KernelNonpaged", ctypes.c_size_t), ("PageSize", ctypes.c_size_t),
                ("HandleCount", wintypes.DWORD), ("ProcessCount", wintypes.DWORD),
                ("ThreadCount", wintypes.DWORD)]


def performance_info() -> dict:
    pi = PERFORMANCE_INFORMATION()
    pi.cb = ctypes.sizeof(pi)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb):
        return {}
    ps = pi.PageSize
    return {
        "commit_total": pi.CommitTotal * ps, "commit_limit": pi.CommitLimit * ps,
        "commit_peak": pi.CommitPeak * ps, "phys_total": pi.PhysicalTotal * ps,
        "phys_avail": pi.PhysicalAvailable * ps, "system_cache": pi.SystemCache * ps,
        "kernel_paged": pi.KernelPaged * ps, "kernel_nonpaged": pi.KernelNonpaged * ps,
        "handles": pi.HandleCount, "processes": pi.ProcessCount, "threads": pi.ThreadCount,
    }
