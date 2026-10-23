"""Shared helpers: subprocess wrapper, admin detection, settings and app-data paths."""
import ctypes
import json
import os
import subprocess
import sys
import time

CREATE_NO_WINDOW = 0x08000000


def app_data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "TaskForge")
    os.makedirs(path, exist_ok=True)
    return path


def backup_dir() -> str:
    path = os.path.join(app_data_dir(), "backups")
    os.makedirs(path, exist_ok=True)
    return path


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def run(cmd, timeout=30):
    """Run a command without flashing a console window. Returns (returncode, stdout, stderr)."""
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace",
        )
        return res.returncode, res.stdout or "", res.stderr or ""
    except FileNotFoundError as e:
        return 127, "", str(e)
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {timeout}s"


def run_powershell(script: str, timeout=60):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-Command", script], timeout=timeout)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Start an elevated copy of TaskForge through the UAC prompt."""
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe = sys.executable
        params = f'"{os.path.abspath(sys.argv[0])}"'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


def open_path(path: str):
    try:
        os.startfile(path)
        return True
    except OSError:
        return False


def resource_path(*parts) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def fmt_bytes(n: float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


DEFAULT_SETTINGS = {
    "theme": "Midnight Violet",
    "refresh_ms": 2000,
    "minimize_to_tray": True,
    "close_to_tray": True,
    "start_minimized": False,
    "tray_notice_shown": False,
    "procexp_path": r"C:\Users\Inv11\Downloads\ProcessExplorer\procexp64.exe",
    "autoruns_path": r"C:\Users\Inv11\Downloads\Autoruns\Autoruns64.exe",
}


class Settings:
    def __init__(self):
        self.path = os.path.join(app_data_dir(), "settings.json")
        self.data = dict(DEFAULT_SETTINGS)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass
