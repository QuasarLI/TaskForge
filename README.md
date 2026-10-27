# TaskForge 2.4.0 Beta 1

**Real beta release:** [Download v2.4.0-beta.1](https://github.com/QuasarLI/TaskForge/releases/tag/v2.4.0-beta.1) |
[Source repository](https://github.com/QuasarLI/TaskForge) | [Changelog](CHANGELOG.md)

TaskForge is a Windows system control center and advanced process manager for live CPU/RAM monitoring, safe process
inspection and controls, documented processor power diagnostics, and reversible paging-file guidance. It uses
supported Windows APIs and commands, explains tradeoffs in plain language, and never applies tuning automatically.

## What changed in 2.4

- **A more cohesive visual system:** shared spacing, surface, border, typography, and control tokens give the
  dashboard, health, process, memory, CPU, startup, settings, and resources pages a consistent hierarchy. Theme
  character remains intact across all ten palettes, including Matrix Green.
- **Refined application shell:** clearer page context, tactile theme-aware navigation, saved compact navigation,
  visible keyboard focus, accessible page names, and a smaller minimum window size for common laptop and scaled
  displays.
- **Calmer, clearer data views:** metric cards, process rows, tables, dialogs, status chips, and explanatory text
  now share consistent spacing and selection states. Process updates still preserve the user's row order, scroll,
  and selection instead of jumping around.
- **A brief startup splash:** the familiar TaskForge icon is drawn from the same vector geometry as the executable
  and tray icon. A single restrained bolt ignition and chrome light sweep stop after one pass; reduced-motion,
  high-contrast, battery-saver, self-test, and tray-first launches use a static or suppressed path. Startup is never
  held open to finish an animation.
- **Accessibility and responsiveness:** keyboard focus is visible, accessible names identify navigation and status,
  text uses DPI-aware point sizing, and compact navigation is available for narrower windows. Motion is bounded and
  disabled when Windows accessibility or power preferences request it.

This is a visual and interaction polish beta, not a feature rewrite. Existing monitoring, edition gates, licensing,
process safeguards, VirusTotal privacy, settings backups, and restore behavior are retained.

## Editions

| Capability | Free | Free with Ads | Supporter | Pro |
|---|:---:|:---:|:---:|:---:|
| Monitoring, explanations, critical safety | Yes | Yes | Yes | Yes |
| Protected process controls | Yes | Yes | Yes | Yes |
| Process inspector, history, signature/hash check | Yes | Yes | Yes | Yes |
| VirusTotal hash lookup (user key required) | Yes | Yes | Yes | Yes |
| Single-process trim and measured result | Yes | Yes | Yes | Yes |
| Multi-process trim | - | Yes | Yes | Yes |
| Backups and restore | Yes | Yes | Yes | Yes |
| Advanced RAM/pagefile and CPU tools | - | Yes | Yes | Yes |
| Affiliate resource cards | No | Yes | No | No |
| Gumroad activation | No | No | `ncbdzb` | `uojwbi` |
| Priority controls and redacted export | - | - | - | Yes |

Supporter and Pro are build-time-distinct binaries and remain locked until a matching customer-entered Gumroad
license verifies. Keys are never logged and local activation is protected with Windows DPAPI. Network failure
fails closed for a new activation; an already protected local activation remains usable offline. No seller secret
is needed or supported.

- [TaskForge Supporter](https://quasarlabs3.gumroad.com/l/ncbdzb)
- [TaskForge Pro](https://quasarlabs3.gumroad.com/l/uojwbi)

## Tools and beginner guidance

- **RAM:** shows working set, private commit, cache, commit limit, kernel pools, and top consumers. Cached RAM is
  explained as reusable rather than “wasted.” Working-set trim is temporary and never advertised as a speed boost.
- **Paging:** reads the same registry value as Windows, recommends a conservative size from RAM and observed peak
  commit, backs up before writes, requires admin, and states when reboot is required. Windows-managed is the sensible
  default; Windows has no pagefile priority or speed-class setting.
- **CPU:** reads live effective clock and per-core load; exposes documented `powercfg` settings for boost mode,
  min/max state, EPP, parking, cooling, and C-states. Each setting explains likely benefit, risk, default,
  reversibility, and admin implications.
- **Processes:** sortable name/PID/parent/CPU/memory/thread/handle/user/path columns; selected-process details include
  status, architecture where Windows reports it, start time, parent, command line, and memory. Right-click for
  terminate/tree terminate, suspend/resume, working-set trim, efficiency mode, affinity, priority, path, copy, and
  process search actions. Snapshot updates refresh values in place and do not continuously re-sort rows; click a
  column header to sort deliberately. New processes append, and exits preserve the scroll offset and other selected
  rows.
- **Executable risk context:** local SHA-256 and Authenticode status/publisher plus explainable path/signature
  signals. These are context only—not malware detection. VirusTotal v3 is hash-only and opt-in; TaskForge never
  uploads a process executable.
- **Dashboard and tray:** live resource cards, process context, uptime, drive capacity, and an optional rotating
  tray tooltip. The tray icon stays static to avoid constant redraw and distraction.
- **Themes:** Midnight Violet, OLED Black, Nord Frost, Ember Red, Matrix Green, Arctic Light, Cyber Ocean,
  Solarized Dusk, Royal Amethyst, and Slate Professional.

## Advertising and privacy

Only **Free with Ads** shows sponsored cards, and only on **Edition & Resources**, away from operational tabs.
They are clearly labeled affiliate links, open in the system browser only after a click, and use only approved
AdGuard destinations. There are no tracking SDKs, embedded browsers, popups, timers, auto-downloads, or deceptive
controls. See [PRIVACY.md](PRIVACY.md).

VirusTotal is a separate user-initiated feature. If the user adds a key, TaskForge stores it with Windows DPAPI.
Choosing a lookup sends the SHA-256 hash and ordinary request metadata to VirusTotal; the file itself is never
uploaded. Results are cached only in memory for the current run. See [PRIVACY.md](PRIVACY.md).

## Run, test, and build

```powershell
python -m pip install -r requirements.txt
python run.py
python -m unittest discover -s tests -v
python run.py --selftest
powershell -ExecutionPolicy Bypass -File build.ps1
```

`--selftest` opens every page, waits for real telemetry, and exits without changing the machine or showing the
splash. The build creates four production editions and a separate, unmistakably watermarked owner-only Pro test
build. The test binary and ZIP are local evaluation files only and must never be distributed.

```text
dist\TaskForge-2.4.0-beta.1\TaskForge-2.4.0-beta.1-Free.exe
dist\TaskForge-2.4.0-beta.1\TaskForge-2.4.0-beta.1-Free-with-Ads.exe
dist\TaskForge-2.4.0-beta.1\TaskForge-2.4.0-beta.1-Supporter.exe
dist\TaskForge-2.4.0-beta.1\TaskForge-2.4.0-beta.1-Pro.exe
dist\TaskForge-2.4.0-beta.1\TaskForge-2.4.0-beta.1-UNLOCKED-BETA-TEST-NOT-FOR-DISTRIBUTION.exe
dist\TaskForge-2.4.0-beta.1-Packages\
dist\TaskForge-2.4.0-beta.1-Packages\TaskForge-2.4.0-beta.1-UNLOCKED-BETA-TEST-NOT-FOR-DISTRIBUTION.zip
dist\TaskForge-2.4.0-beta.1-Packages\SHA256SUMS.txt
```

Upload only the production Supporter and Pro packages to their matching Gumroad products. Do not upload or enter
seller credentials into TaskForge. The production paid binaries contain the configured product IDs but remain
locked until a customer enters a matching valid license.

## Releases and Sigstore

Pushing a `v*` tag runs `.github/workflows/release.yml`. GitHub Actions builds on Windows, runs tests and the safe
self-test, produces Free and Free-with-Ads ZIPs, generates SHA-256 checksums, creates keyless Sigstore bundles with
GitHub OIDC, attests build provenance, and publishes those ZIPs as a prerelease. Supporter/Pro packages are built
and keylessly signed by the separate private [TaskForge-Distribution](https://github.com/QuasarLI/TaskForge-Distribution)
workflow, verified against its exact GitHub Actions identity, and retained as a private Actions artifact for seven
days. They are not attached to the public release.

Verify a downloaded file after installing `cosign`:

```powershell
cosign verify-blob TaskForge-2.4.0-beta.1-Free.zip `
  --bundle TaskForge-2.4.0-beta.1-Free.zip.sigstore.json `
  --certificate-identity-regexp "https://github.com/QuasarLI/TaskForge/.github/workflows/release.yml@refs/tags/v.*" `
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
Get-FileHash TaskForge-2.4.0-beta.1-Free.zip -Algorithm SHA256
```

## Safety and source licensing

No MSR, chipset, voltage, multiplier, or BCLK writes are performed. Every power/pagefile change is confirmed,
backed up under `%APPDATA%\TaskForge\backups`, and restorable. TaskForge is not kernel-level Process Explorer:
it does not yet provide DLL/handle-object trees, reliable service mapping, GPU/network per-process graphs, process
dumps, or a Windows service manager. The configured Sysinternals Process Explorer launch remains available for
those specialist workflows. See [SECURITY.md](SECURITY.md).

This repository did not contain an open-source license before this release. No open-source grant is inferred or
invented; see [LICENSING.md](LICENSING.md) before redistributing source or binaries.
