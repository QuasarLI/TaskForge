# TaskForge 2.3.0 Beta 1

TaskForge v2.3.0-beta.1 is a real prerelease for early evaluation as an Advanced Task Manager / process explorer.

## Highlights

- Processes adds sortable/filterable parent/process context, inspector details, bounded CPU/working-set history,
  process comparison and measured trim results. Critical process safeguards and explicit confirmations remain.
- Local SHA-256, Authenticode publisher/status and location context help users investigate without pretending to
  detect malware.
- VirusTotal reports are optional, hash-only, and require explicit user action. The executable is never uploaded;
  API keys are stored with Windows DPAPI.
- Pagefile tools reject removable/network destinations, display volume metadata when Windows provides it, and
  explain that Windows offers no user-settable pagefile priority or speed class.
- Firmware placeholders are replaced with clear "Not reported by firmware" labels; dashboard and tray summaries
  provide uptime, storage and process context.
- Existing System Health, battery/energy reporting, Pro redacted snapshots, all ten themes, edition safeguards and
  reversible settings remain in place.

TaskForge is still not kernel-level Process Explorer parity: DLL/handle-object trees, reliable service mapping,
GPU/network per-process graphs, process dumps and service management are not included in this beta.

## Editions and verification

The GitHub prerelease contains Free and Free with Ads ZIP packages, their SHA-256 manifest, Sigstore keyless bundles,
and GitHub build provenance. Supporter and Pro ZIPs are private local Gumroad upload candidates; they have SHA-256
checksums but no claimed Sigstore signature because they were not uploaded to the signing workflow.

The separate `UNLOCKED-BETA-TEST-NOT-FOR-DISTRIBUTION` Pro test build and ZIP are owner-only evaluation files.
Never upload them to Gumroad or distribute them.

For issues and beta feedback, visit https://github.com/QuasarLI/TaskForge/issues.
