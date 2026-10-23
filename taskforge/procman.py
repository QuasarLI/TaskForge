"""Process control: protected-process checks, kill/tree-kill, suspend, trim, priority, affinity, EcoQoS."""
import ctypes
import os
from ctypes import wintypes

import psutil

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_SET_QUOTA = 0x0100
PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t]
kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
kernel32.IsProcessCritical.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
kernel32.IsProcessCritical.restype = wintypes.BOOL
kernel32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel32.SetProcessInformation.restype = wintypes.BOOL

# Killing any of these crashes or destabilises Windows (or logs the user out).
PROTECTED_NAMES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe",
    "winlogon.exe", "services.exe", "lsass.exe", "lsaiso.exe", "svchost.exe", "fontdrvhost.exe",
    "dwm.exe", "memory compression", "secure system", "lsm.exe", "sihost.exe",
    "msmpeng.exe", "audiodg.exe", "spoolsv.exe", "wudfhost.exe",
}

PRIORITIES = [
    ("Idle", psutil.IDLE_PRIORITY_CLASS),
    ("Below normal", psutil.BELOW_NORMAL_PRIORITY_CLASS),
    ("Normal", psutil.NORMAL_PRIORITY_CLASS),
    ("Above normal", psutil.ABOVE_NORMAL_PRIORITY_CLASS),
    ("High", psutil.HIGH_PRIORITY_CLASS),
    ("Realtime", psutil.REALTIME_PRIORITY_CLASS),
]
PRIORITY_NAMES = {v: k for k, v in PRIORITIES}


class OpError(Exception):
    pass


def _is_critical_flag(pid: int) -> bool:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        flag = wintypes.BOOL(False)
        if kernel32.IsProcessCritical(h, ctypes.byref(flag)):
            return bool(flag.value)
        return False
    finally:
        kernel32.CloseHandle(h)


def protection_reason(pid: int, name: str = "") -> str:
    """Return a human reason if the process must not be killed/suspended, else ''."""
    if pid in (0, 4):
        return "Windows kernel / idle process"
    if pid == os.getpid():
        return "TaskForge itself"
    if not name:
        try:
            name = psutil.Process(pid).name()
        except psutil.Error:
            name = ""
    if name.lower() in PROTECTED_NAMES:
        return f"{name} is a core Windows process"
    try:
        if _is_critical_flag(pid):
            return f"{name or pid} is flagged critical by Windows (killing it bug-checks the system)"
    except Exception:
        pass
    return ""


def _wrap(fn, pid, action):
    try:
        return fn()
    except psutil.NoSuchProcess:
        raise OpError(f"PID {pid} has already exited.")
    except psutil.AccessDenied:
        raise OpError(f"Access denied while trying to {action} PID {pid}. "
                      "Restart TaskForge as administrator, or the process may be protected (PPL/anti-cheat/AV).")


def terminate(pid: int):
    _wrap(lambda: psutil.Process(pid).kill(), pid, "terminate")


def terminate_tree(pid: int) -> int:
    def go():
        root = psutil.Process(pid)
        kids = root.children(recursive=True)
        for k in kids:
            if protection_reason(k.pid, k.name()):
                raise OpError(f"Tree contains protected process {k.name()} (PID {k.pid}); aborted.")
        count = 0
        for k in reversed(kids):
            try:
                k.kill()
                count += 1
            except psutil.NoSuchProcess:
                pass
        root.kill()
        return count + 1
    return _wrap(go, pid, "terminate the tree of")


def suspend(pid: int):
    _wrap(lambda: psutil.Process(pid).suspend(), pid, "suspend")


def resume(pid: int):
    _wrap(lambda: psutil.Process(pid).resume(), pid, "resume")


def set_priority(pid: int, cls: int):
    _wrap(lambda: psutil.Process(pid).nice(cls), pid, "change priority of")


def get_affinity(pid: int):
    return _wrap(lambda: psutil.Process(pid).cpu_affinity(), pid, "read affinity of")


def set_affinity(pid: int, cpus):
    _wrap(lambda: psutil.Process(pid).cpu_affinity(list(cpus)), pid, "change affinity of")


def trim_working_set(pid: int) -> bool:
    """Ask Windows to page out a process working set. Pages return on demand (soft faults)."""
    h = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        minus1 = ctypes.c_size_t(-1).value
        return bool(kernel32.SetProcessWorkingSetSize(h, minus1, minus1))
    finally:
        kernel32.CloseHandle(h)


# EcoQoS / "Efficiency mode" (documented SetProcessInformation, Windows 10 1709+/11)
class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]


def set_efficiency_mode(pid: int, enable: bool):
    h = kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
    if not h:
        raise OpError(f"Access denied opening PID {pid} (try running as administrator).")
    try:
        st = PROCESS_POWER_THROTTLING_STATE(1, 0x1, 0x1 if enable else 0x0)
        ok = kernel32.SetProcessInformation(h, 4, ctypes.byref(st), ctypes.sizeof(st))
        if not ok:
            raise OpError(f"Windows rejected EcoQoS change (error {ctypes.get_last_error()}).")
    finally:
        kernel32.CloseHandle(h)
    try:
        psutil.Process(pid).nice(psutil.IDLE_PRIORITY_CLASS if enable else psutil.NORMAL_PRIORITY_CLASS)
    except psutil.Error:
        pass


# ----------------------------------------------------------------- Sampling
class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", ctypes.c_void_p)]


class SYSTEM_PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("NextEntryOffset", wintypes.ULONG), ("NumberOfThreads", wintypes.ULONG),
                ("WorkingSetPrivateSize", ctypes.c_int64), ("HardFaultCount", wintypes.ULONG),
                ("NumberOfThreadsHighWatermark", wintypes.ULONG), ("CycleTime", ctypes.c_uint64),
                ("CreateTime", ctypes.c_int64), ("UserTime", ctypes.c_int64), ("KernelTime", ctypes.c_int64),
                ("ImageName", UNICODE_STRING), ("BasePriority", ctypes.c_long),
                ("UniqueProcessId", ctypes.c_void_p), ("InheritedFromUniqueProcessId", ctypes.c_void_p),
                ("HandleCount", wintypes.ULONG), ("SessionId", wintypes.ULONG),
                ("UniqueProcessKey", ctypes.c_void_p), ("PeakVirtualSize", ctypes.c_size_t),
                ("VirtualSize", ctypes.c_size_t), ("PageFaultCount", wintypes.ULONG),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivatePageCount", ctypes.c_size_t)]


_ntdll = ctypes.WinDLL("ntdll")
_ntdll.NtQuerySystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.ULONG,
                                            ctypes.POINTER(wintypes.ULONG)]
_ntdll.NtQuerySystemInformation.restype = ctypes.c_long
STATUS_INFO_LENGTH_MISMATCH = ctypes.c_long(0xC0000004).value


def snapshot_processes():
    """One read-only kernel query returning every process (same source Task Manager / Process Explorer use)."""
    size = 1 << 20
    while True:
        buf = ctypes.create_string_buffer(size)
        need = wintypes.ULONG(0)
        st = _ntdll.NtQuerySystemInformation(5, buf, size, ctypes.byref(need))
        if st == STATUS_INFO_LENGTH_MISMATCH:
            size = max(size * 2, need.value + 65536)
            continue
        if st != 0:
            raise OSError(f"NtQuerySystemInformation failed: 0x{st & 0xFFFFFFFF:08X}")
        break
    base = ctypes.addressof(buf)
    off = 0
    out = []
    while True:
        spi = SYSTEM_PROCESS_INFORMATION.from_address(base + off)
        pid = spi.UniqueProcessId or 0
        if spi.ImageName.Buffer and spi.ImageName.Length:
            name = ctypes.wstring_at(spi.ImageName.Buffer, spi.ImageName.Length // 2)
        else:
            name = "System Idle Process" if pid == 0 else "?"
        out.append({"pid": pid, "ppid": spi.InheritedFromUniqueProcessId or 0, "name": name,
                    "threads": spi.NumberOfThreads, "handles": spi.HandleCount,
                    "ws": spi.WorkingSetSize, "private": spi.PrivatePageCount,
                    "cputime": spi.UserTime + spi.KernelTime, "create": spi.CreateTime})
        if not spi.NextEntryOffset:
            break
        off += spi.NextEntryOffset
    return out


class ProcessSampler:
    """Fast sampler: one kernel snapshot per tick; exe/user cached per process instance."""

    def __init__(self):
        self.ncpu = psutil.cpu_count() or 1
        self.prev = {}
        self.meta = {}
        self.last_t = None

    def sample(self):
        import time
        now = time.perf_counter()
        rows = snapshot_processes()
        dt = (now - self.last_t) if self.last_t else None
        cur, meta = {}, {}
        for r in rows:
            key = (r["pid"], r["create"])
            cur[key] = r["cputime"]
            prev = self.prev.get(key)
            r["cpu"] = (100.0 * (r["cputime"] - prev) / (dt * 1e7 * self.ncpu)) if (dt and prev is not None) else 0.0
            m = self.meta.get(key)
            if m is None:
                m = {"exe": None, "user": None}
                try:
                    p = psutil.Process(r["pid"])
                    for attr in ("exe", "username"):
                        try:
                            m["exe" if attr == "exe" else "user"] = getattr(p, attr)()
                        except (psutil.Error, OSError):
                            pass
                except psutil.Error:
                    pass
            meta[key] = m
            r.update(m)
            try:
                r["nice"] = psutil.Process(r["pid"]).nice() if r["pid"] > 4 else None
            except (psutil.Error, OSError):
                r["nice"] = None
        self.prev, self.meta, self.last_t = cur, meta, now
        return rows
