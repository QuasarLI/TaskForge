# TaskForge 2.0 — System Control Center (Windows)

PyQt6 task manager focused on CPU turbo/power tuning, RAM and process control, and pagefile help.

**Canonical source:** `D:\TaskForgeGitSources` (this folder). `D:\TaskForge` holds the original prototype and is kept for reference only.

## Run / build
```powershell
pip install -r requirements.txt
python run.py                 # run from source
python run.py --selftest      # opens every page, checks live telemetry, exits 0 on success (changes nothing)
powershell -ExecutionPolicy Bypass -File build.ps1   # -> dist\TaskForge.exe
```
Bump the version in `taskforge/__init__.py` and `tools/version_info.txt`.

## Layout
| File | Purpose |
|---|---|
| `taskforge/app.py` | Main window, header/icon, sidebar, tray, admin relaunch, `--selftest` |
| `taskforge/widgets.py` | `Monitor` (background telemetry), sparkline, workers, helpers |
| `taskforge/procman.py` | Fast process snapshot (NtQuerySystemInformation), kill/tree/suspend/trim/priority/affinity/EcoQoS, protected-process rules |
| `taskforge/power.py` | `powercfg` plans, processor settings, turbo presets, JSON backup/restore |
| `taskforge/pagefile.py` | Read/write `PagingFiles` registry value with backups, sizing recommendation |
| `taskforge/sysinfo.py` | CPU identity, PDH effective clock, WMI inventory, GetPerformanceInfo |
| `taskforge/pages_*.py` | UI pages |
| `taskforge/themes.py`, `icon.py` | 6 themes, programmatic icon |

## Safety rules (keep these)
- Only documented Windows interfaces. No MSR/chipset writes: multiplier, BCLK and voltage are **not** changed by TaskForge; the Overclocking Guide routes users to BIOS / Intel XTU / AMD Ryzen Master.
- Every power/pagefile change is confirmed, backed up to `%APPDATA%\TaskForge\backups`, and restorable. Pagefile changes need admin + reboot.
- Core Windows / critical-flagged processes cannot be killed or suspended. Destructive actions always confirm.
- Memory trimming is presented honestly (not a guaranteed speed-up).

## Secrets
The app needs **no API keys** and makes no network requests. Never commit keys: use environment variables or a local `.env` (git-ignored). The old `D:\TaskForge\generate.py` only used a local Ollama server (no key).
