# TaskForge 2.3.0 Beta 1

**Real beta release:** [Download v2.3.0-beta.1](https://github.com/QuasarLI/TaskForge/releases/tag/v2.3.0-beta.1) |
[Source repository](https://github.com/QuasarLI/TaskForge) | [Changelog](CHANGELOG.md)

TaskForge is a Windows system control center and advanced process manager for live CPU/RAM monitoring, safe process
inspection and controls, documented processor power diagnostics, and reversible paging-file guidance. It uses
supported Windows APIs and commands, explains tradeoffs in plain language, and never applies tuning automatically.

**Beta highlight:** the Processes page adds sortable process-tree context, a selected-process inspector, bounded
CPU/working-set graphs, measured trim results, executable signature context, and explicit VirusTotal hash lookup.
The dashboard now includes uptime and system-drive capacity; tray hover text rotates a short summary every 15 seconds
and can be disabled in Settings.
The tray icon itself stays static; Windows hover text is not a scrolling/animation surface, and TaskForge avoids
constantly rewriting icons to conserve CPU and avoid distraction.

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

## Safe tools and beginner guidance

- **RAM:** shows working set, private commit, cache, commit limit, kernel pools, and top consumers. Cached RAM is
  explained as reusable rather than “wasted.” Working-set trim is explicitly temporary and never advertised as a
  speed boost.
- **Paging:** reads the same registry value as Windows, recommends a conservative size from RAM and observed peak
  commit, backs up before writes, requires admin, and states when reboot is required. Windows-managed is the
  sensible default.
- **CPU:** reads live effective clock and per-core load; exposes documented `powercfg` settings for boost mode,
  min/max state, EPP, parking, cooling, and C-states. Each setting states likely benefit, heat/battery risk,
  sensible default, reversibility, and admin implications.
- **Processes:** sortable name/PID/parent/CPU/memory/thread/handle/user/path columns; selected-process details include
  status, architecture where Windows reports it, start time, parent, command line, and memory. Right-click for
  terminate/tree terminate, suspend/resume, working-set trim, efficiency mode, affinity, priority, path, copy, and
  process search actions. Snapshot updates refresh values in place and do not continuously re-sort rows, so a
  selection stays under the pointer; click a column header to sort deliberately. New processes append, and if a
  process exits TaskForge preserves the scroll offset and other selected rows. Core Windows processes are guarded.
  Each selected process gets a bounded 60-sample CPU and working-set history; graphs are in the inspector rather than
  one chart per process.
- **Executable risk context:** local SHA-256 and Authenticode status/publisher plus explainable path/signature signals.
  These are context only—not malware detection. VirusTotal v3 is hash-only and opt-in; TaskForge never uploads a
  process executable.
- **Pagefile:** Windows has no pagefile priority or speed-class setting. TaskForge reports Windows usage/peak and
  available volume media/bus/health metadata, offers a measured-workload recommendation, rejects removable/network
  targets, backs up before changing Windows settings, and clearly explains reboot and crash-dump implications.
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

`--selftest` opens every page, waits for real telemetry, and exits without changing the machine. The build produces
four visibly named executables, checksums, a Windows zip, the app icon, and a 1200x675 Gumroad cover:

```text
dist\TaskForge-2.3.0-beta.1\TaskForge-2.3.0-beta.1-Free.exe
dist\TaskForge-2.3.0-beta.1\TaskForge-2.3.0-beta.1-Free-with-Ads.exe
dist\TaskForge-2.3.0-beta.1\TaskForge-2.3.0-beta.1-Supporter.exe
dist\TaskForge-2.3.0-beta.1\TaskForge-2.3.0-beta.1-Pro.exe
assets\taskforge-gumroad-matrix-cover.png
```

Upload the local Supporter and Pro executables to their matching Gumroad products. Do not upload or enter seller
credentials into TaskForge. Before publishing paid files, confirm Gumroad still accepts the documented
`POST https://api.gumroad.com/v2/licenses/verify` fields `product_permalink`, `license_key`, and
`increment_uses_count`. Current Gumroad products require their product IDs rather than permalinks. The production
build requires `TASKFORGE_GUMROAD_SUPPORTER_PRODUCT_ID` and `TASKFORGE_GUMROAD_PRO_PRODUCT_ID` to be present in the
build environment (the release workflow reads the matching non-secret GitHub Actions repository variables). If
either is missing, `build.ps1` stops before producing binaries rather than creating paid packages that cannot
activate. The binaries still remain locked until a customer enters a matching valid key.

## Releases and Sigstore

Pushing a `v*` tag runs `.github/workflows/release.yml`. GitHub Actions builds on Windows, runs tests and the safe
self-test, produces Free and Free-with-Ads ZIPs, generates SHA-256 checksums, creates keyless Sigstore bundles with
GitHub OIDC, attests build provenance, and publishes those ZIPs as a prerelease. Paid ZIPs remain private local
Gumroad upload files. They are checksummed but not Sigstore-signed: this workflow cannot use GitHub OIDC to sign
private local files without uploading them.

Verify a downloaded file after installing `cosign`:

```powershell
cosign verify-blob TaskForge-2.3.0-beta.1-Free.zip `
  --bundle TaskForge-2.3.0-beta.1-Free.zip.sigstore.json `
  --certificate-identity-regexp "https://github.com/QuasarLI/TaskForge/.github/workflows/release.yml@refs/tags/v.*" `
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
Get-FileHash TaskForge-2.3.0-beta.1-Free.zip -Algorithm SHA256
```

## Safety and source licensing

No MSR, chipset, voltage, multiplier, or BCLK writes are performed. Every power/pagefile change is confirmed,
backed up under `%APPDATA%\TaskForge\backups`, and restorable. TaskForge is not kernel-level Process Explorer:
it does not yet provide DLL/handle-object trees, reliable service mapping, GPU/network per-process graphs, process
dumps, or a Windows service manager. The configured Sysinternals Process Explorer launch remains available for
those specialist workflows. See [SECURITY.md](SECURITY.md).

This repository did not contain an open-source license before this release. No open-source grant is inferred or
invented; see [LICENSING.md](LICENSING.md) before redistributing source or binaries.
