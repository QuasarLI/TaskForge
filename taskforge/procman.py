"""Process control: protected-process checks, kill/tree-kill, suspend, trim, priority, affinity, EcoQoS."""
import ctypes
import base64
import hashlib
import json
import os
import time
from collections import deque
from ctypes import wintypes

import psutil

from .util import run_powershell

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
        raise OpError(f"Access denied opening PID {pid} to trim its working set (try administrator mode).")
    try:
        minus1 = ctypes.c_size_t(-1).value
        if not kernel32.SetProcessWorkingSetSize(h, minus1, minus1):
            raise OpError(f"Windows rejected working-set trim for PID {pid} (error {ctypes.get_last_error()}).")
        return True
    finally:
        kernel32.CloseHandle(h)


def trim_working_set_measured(pid: int) -> dict:
    """Trim one working set and return measured before/after resident bytes."""
    try:
        process = psutil.Process(pid)
        before = process.memory_info().rss
    except psutil.NoSuchProcess as exc:
        raise OpError(f"PID {pid} has already exited.") from exc
    except (psutil.AccessDenied, OSError) as exc:
        raise OpError(f"Cannot read memory use for PID {pid}; try administrator mode.") from exc
    trim_working_set(pid)
    try:
        after = psutil.Process(pid).memory_info().rss
    except psutil.NoSuchProcess:
        after = 0
    except (psutil.AccessDenied, OSError) as exc:
        raise OpError(f"Trim requested for PID {pid}, but Windows would not allow the after-measurement.") from exc
    return {"before": before, "after": after, "reclaimed": max(0, before - after)}


def trim_process_batch(pids):
    """Trim an explicitly selected set; return a visible result for every PID."""
    results = []
    for pid in pids:
        try:
            name = psutil.Process(pid).name()
            reason = protection_reason(pid, name)
            if reason:
                results.append({"pid": pid, "name": name, "error": f"Protected: {reason}"})
                continue
            results.append({"pid": pid, "name": name, **trim_working_set_measured(pid)})
        except OpError as exc:
            results.append({"pid": pid, "name": str(pid), "error": str(exc)})
        except psutil.Error as exc:
            results.append({"pid": pid, "name": str(pid), "error": f"Windows process access failed: {exc}"})
    return results


PLACEHOLDER_PATH_PARTS = (
    "\\appdata\\local\\temp\\", "\\windows\\temp\\", "\\downloads\\",
)


def process_risk_signals(path: str, signature_status: str, windows_dir=None) -> list:
    """Return explainable context signals; these are not a malware verdict."""
    if not path:
        return ["Executable path is unavailable; this is common for protected/system processes."]
    normalized = os.path.normcase(os.path.abspath(path))
    signals = []
    if not os.path.isfile(path):
        signals.append("The executable file is missing or no longer accessible.")
    win = os.path.normcase(windows_dir or os.environ.get("WINDIR", r"C:\Windows"))
    if normalized.startswith(win + os.sep):
        signals.append("The file is under the Windows directory; location alone does not prove it is safe.")
    elif any(part in normalized.lower() for part in PLACEHOLDER_PATH_PARTS):
        signals.append("The file is in a user-writable or temporary location; verify whether you expected it there.")
    if signature_status and signature_status.lower() not in ("valid", "not checked"):
        signals.append(f"Authenticode status is {signature_status}; an unsigned or invalid signature is not proof of malware.")
    if not signals:
        signals.append("No unusual path/signature signal was reported. This is not a malware verdict.")
    return signals


def process_details(pid: int) -> dict:
    """Read selected-process details on demand; access failures are returned explicitly."""
    try:
        process = psutil.Process(pid)
        with process.oneshot():
            try:
                name = process.name()
            except psutil.Error:
                name = str(pid)
            try:
                path = process.exe()
            except psutil.AccessDenied:
                path = "Access denied"
            except psutil.Error:
                path = "Unavailable"
            try:
                parent = process.parent()
                parent_info = {"pid": parent.pid, "name": parent.name()} if parent else None
            except psutil.Error:
                parent_info = None
            try:
                command_line = " ".join(process.cmdline())
            except psutil.AccessDenied:
                command_line = "Access denied (try administrator mode)"
            except psutil.Error:
                command_line = "Unavailable"
            try:
                create_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(process.create_time()))
            except psutil.Error:
                create_time = "Unavailable"
            try:
                status = process.status()
            except psutil.Error:
                status = "Unavailable"
            try:
                user = process.username()
            except psutil.AccessDenied:
                user = "Access denied"
            except psutil.Error:
                user = "Unavailable"
            try:
                threads = process.num_threads()
            except psutil.Error:
                threads = None
            try:
                handles = process.num_handles() if hasattr(process, "num_handles") else None
            except psutil.AccessDenied:
                handles = None
            except psutil.Error:
                handles = None
            try:
                memory = process.memory_info()
            except psutil.AccessDenied as exc:
                raise OpError(f"Access denied reading PID {pid}; try administrator mode.") from exc
            try:
                architecture = "64-bit" if process.is_64bit() else "32-bit"
            except (AttributeError, psutil.Error):
                architecture = "Unavailable"
        return {
            "pid": pid, "name": name, "path": path, "parent": parent_info, "architecture": architecture,
            "command_line": command_line, "started": create_time, "status": status, "user": user,
            "threads": threads, "handles": handles, "working_set": memory.rss,
            "private": getattr(memory, "private", None),
        }
    except psutil.NoSuchProcess as exc:
        raise OpError(f"PID {pid} has already exited.") from exc
    except psutil.AccessDenied as exc:
        raise OpError(f"Access denied inspecting PID {pid}; try administrator mode.") from exc


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze_executable(path: str) -> dict:
    """Hash a local executable and read its Authenticode status without uploading it."""
    if not path or not os.path.isfile(path):
        raise OpError("The selected executable is not available as a local file.")
    digest = sha256_file(path)
    encoded_path = base64.b64encode(path.encode("utf-8")).decode("ascii")
    script = (
        "$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded_path + "'));"
        "$s=Get-AuthenticodeSignature -LiteralPath $p;"
        "[ordered]@{status=[string]$s.Status; signer=[string]$s.SignerCertificate.Subject} | "
        "ConvertTo-Json -Compress"
    )
    rc, output, _error = run_powershell(script, timeout=30)
    if rc != 0 or not output.strip():
        raise OpError("Windows could not read the executable's Authenticode signature status.")
    try:
        signature = json.loads(output)
    except ValueError as exc:
        raise OpError("Windows returned an unreadable signature result.") from exc
    return {
        "sha256": digest,
        "signature_status": signature.get("status") or "Unknown",
        "publisher": signature.get("signer") or "No signer reported",
        "signals": process_risk_signals(path, signature.get("status") or "Unknown"),
    }


class ProcessHistory:
    """Bounded CPU/working-set history keyed by PID and process creation time."""
    def __init__(self, capacity=60):
        self.capacity = capacity
        self.samples = {}

    def update(self, rows):
        active = set()
        for row in rows:
            key = (row["pid"], row["create"])
            active.add(key)
            history = self.samples.setdefault(key, {
                "cpu": deque(maxlen=self.capacity), "memory": deque(maxlen=self.capacity)})
            history["cpu"].append(row["cpu"])
            history["memory"].append(row["ws"])
            row["history"] = {name: list(values) for name, values in history.items()}
        for key in set(self.samples) - active:
            del self.samples[key]
        return rows


def preserve_process_order(existing_pids, rows_by_pid, sort_key, reverse=False):
    """Keep visible rows fixed across telemetry ticks; sort only newly observed processes."""
    order = [pid for pid in existing_pids if pid in rows_by_pid]
    present = set(order)
    added = [pid for pid in rows_by_pid if pid not in present]
    added.sort(key=lambda pid: sort_key(rows_by_pid[pid]), reverse=reverse)
    return order + added


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
