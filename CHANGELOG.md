# Changelog

## 2.4.0-beta.1 - 2026-10-24

- Established shared theme-aware spacing, typography, surface, control, table, selection, and keyboard-focus tokens
  for consistent hierarchy across all application pages and all ten themes.
- Refined the application shell with page context, compact persistent navigation, keyboard shortcuts, accessible
  names, tactile sidebar states, and a smaller minimum window size for scaled and compact displays.
- Improved dashboard cards, process-table readability, status states, and consistent page spacing while preserving
  stable process selection and scroll behavior.
- Added a short, non-modal startup splash that reuses the official icon's vector geometry. Its one-shot bolt
  ignition and polished chrome light sweep stop after one pass and never delay main-window display.
- Added static splash behavior for reduced-motion, Windows high-contrast, battery-saver, self-test, and tray-first
  startup, plus a clear owner-test watermark and startup failure escape.
- Deferred startup-entry enumeration until after the main window can render and showed an explicit loading state.
- Added theme-token, splash-stage, motion-policy, reduced-motion, test-watermark, startup suppression, and failure
  message coverage without changing host settings or requiring live services.
- Preserved existing edition gates, licensing, privacy, process safety, VirusTotal boundaries, backups, and restore.

`v2.4.0-beta.1` is a real prerelease for early evaluation. Public packages are Free and Free with Ads; paid upload
packages and the unlocked owner test build remain separate from the public release.

## 2.3.0-beta.1 - 2026-10-24

- Reworked Processes into a sortable, filterable advanced process list with parent PID, CPU, memory, handles, user,
  path, a selected-process inspector, and 60-sample CPU/working-set sparklines.
- Added on-demand command line, architecture, status, start time, parent, thread/handle and memory details, plus
  measured working-set trim results with protected-process exclusions and visible per-process failures.
- Added local SHA-256, Authenticode publisher/status and explainable path signals; none is presented as a malware
  verdict.
- Added opt-in VirusTotal v3 hash reports with a DPAPI-protected local key, explicit disclosure/confirmation,
  session-only result cache and no binary upload.
- Improved pagefile target checks, drive media/bus/health context when Windows reports it, and plain-language notes
  that Windows has no pagefile priority or speed-class setting.
- Sanitized common empty/default SMBIOS values and added system/board fallback labels.
- Enriched dashboard uptime/system-drive summary and added optional 15-second rotating tray hover text.
- Preserved all ten themes, edition gates, safety protections and Windows-native reversible settings; documented
  current gaps versus kernel-level Process Explorer and Task Manager.
- Added mocked VirusTotal, process-history/risk, firmware-sanitization and pagefile-validation tests.

`v2.3.0-beta.1` is a real prerelease for early evaluation. Public packages are Free and Free with Ads; paid upload
packages and the unlocked owner test build are kept separate from the public release.

## 2.2.0-beta.1 - 2026-10-24

- Added a crisp, beginner-friendly System Health page with live CPU, RAM, commit, and top-process insights.
- Added actionable pressure explanations that recommend observation before tuning and reject RAM-cleaner myths.
- Added safe Windows battery and 60-second energy report generation with explicit no-change guidance.
- Added redacted Pro snapshot export for before/after comparisons.
- Improved navigation and preserved all ten themes, critical-process protections, confirmations, and restore paths.
- Configured production paid builds for the current Gumroad product IDs while retaining customer-key verification,
  DPAPI storage, product mismatch protection, redaction, deactivation, and fail-closed behavior.
- Updated beta packaging, tests, checksums, Sigstore ZIP signing, attestations, and prerelease automation.

`v2.2.0-beta.1` is a real prerelease for early evaluation. Report issues at
https://github.com/QuasarLI/TaskForge/issues. The public beta offers Free and Free with Ads; Supporter/Pro ZIPs are
local seller upload candidates. Never distribute the separately watermarked unlocked Pro beta test build.

## 2.1.0 - 2026-10-24

- Added build-time Free, Free with Ads, Supporter, and Pro editions with explicit gates.
- Added Gumroad customer activation for Supporter/Pro with product-ID matching, DPAPI storage, redaction, deactivation,
  offline local activation, and fail-closed network/error behavior.
- Added a dedicated edition/resources page with a no-dark-pattern edition matrix and restrained affiliate cards.
- Added Cyber Ocean, Solarized Dusk, Royal Amethyst, and Slate Professional themes.
- Added Pro redacted diagnostics export and gated priority controls.
- Expanded beginner explanations for CPU, RAM, paging, risk, defaults, admin, reboot, and reversibility.
- Added a Gumroad-ready 1200x675 Matrix Green cover derived from TaskForge's programmatic icon.
- Added a four-edition build matrix, checksums, tests, and a least-privilege Sigstore/OIDC release workflow.
