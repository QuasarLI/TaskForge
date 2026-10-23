"""Paging-file configuration (registry PagingFiles, same value the System Properties dialog writes)."""
import json
import os
import winreg

from .util import backup_dir, timestamp

MM_KEY = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"


def read_config():
    """Return list of entries: dict(path, initial_mb, max_mb, mode) where mode is auto|system|custom."""
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MM_KEY) as k:
        try:
            raw = winreg.QueryValueEx(k, "PagingFiles")[0]
        except OSError:
            raw = []
    entries = []
    for line in raw or []:
        parts = line.split()
        if not parts:
            continue
        path = parts[0]
        init = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        mx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        if path.startswith("?"):
            mode = "auto"
        elif init == 0 and mx == 0:
            mode = "system"
        else:
            mode = "custom"
        entries.append({"path": path, "initial_mb": init, "max_mb": mx, "mode": mode, "raw": line})
    return entries


def read_clear_at_shutdown() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MM_KEY) as k:
            return bool(winreg.QueryValueEx(k, "ClearPageFileAtShutdown")[0])
    except OSError:
        return False


def recommend(phys_total: int, commit_peak: int):
    """Sizing heuristic (MB) based on observed peak commit, per Microsoft guidance."""
    ram_mb = phys_total // (1024 * 1024)
    peak_mb = commit_peak // (1024 * 1024)
    initial = max(2048, peak_mb - ram_mb + 1024)
    initial = int((initial + 255) // 256 * 256)
    maximum = max(initial * 2, ram_mb, 4096)
    maximum = int((maximum + 255) // 256 * 256)
    return initial, maximum


def _backup(raw_lines) -> str:
    path = os.path.join(backup_dir(), f"pagefile-{timestamp()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"PagingFiles": raw_lines}, f, indent=2)
    return path


def apply(lines):
    """Write new PagingFiles value (requires admin, effective after reboot). Returns backup path."""
    current = [e["raw"] for e in read_config()]
    bpath = _backup(current)
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MM_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "PagingFiles", 0, winreg.REG_MULTI_SZ, list(lines))
    return bpath


def build_line(mode: str, drive: str, initial=0, maximum=0) -> str:
    drive = drive.rstrip(":\\").upper()
    if mode == "auto":
        return "?:\\pagefile.sys"
    if mode == "system":
        return f"{drive}:\\pagefile.sys 0 0"
    return f"{drive}:\\pagefile.sys {int(initial)} {int(maximum)}"


def latest_backup():
    import glob
    files = sorted(glob.glob(os.path.join(backup_dir(), "pagefile-*.json")), reverse=True)
    return files[0] if files else None


def restore(path: str):
    with open(path, "r", encoding="utf-8") as f:
        lines = json.load(f)["PagingFiles"]
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MM_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "PagingFiles", 0, winreg.REG_MULTI_SZ, lines)
    return lines
