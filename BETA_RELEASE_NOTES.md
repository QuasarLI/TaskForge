# TaskForge 2.4.0 Beta 1

TaskForge v2.4.0-beta.1 is a real prerelease focused on a substantial GUI polish pass while preserving the ten-theme
identity, edition model, v2.3 process tooling, privacy boundaries, and safe Windows controls.

## What changed

- Unified page spacing, type hierarchy, cards, buttons, tables, dialogs, status chips, focus states, and selected-row
  contrast through shared theme-aware design tokens.
- Refined the shell with page context, compact persistent navigation, keyboard shortcuts, accessible names, clearer
  focus and hover states, and a smaller minimum window size for common scaled displays.
- Improved dashboard metric cards and table readability without changing process sampling order, selection, or
  scroll behavior.
- Added a brief startup splash drawn from the existing TaskForge icon geometry. The bolt ignition and neutral
  chrome reflection run once, then settle; reduced-motion, high-contrast, battery-saver, self-test, and tray-first
  startup paths avoid motion or suppress the splash. Startup is never delayed for the animation.
- Deferred startup-list enumeration until after the main window can render, and added a visible loading state.
- Kept monitoring, process safeguards, DPAPI-protected license and VirusTotal secrets, Gumroad product matching,
  edition gates, and reversible power/pagefile behavior intact.

This is a user-interface and interaction polish beta, not a feature rewrite or a claim of full Task Manager /
Process Explorer parity. Known feature gaps remain listed in README.

## Editions and verification

The GitHub prerelease contains Free and Free with Ads ZIP packages, their SHA-256 manifest, Sigstore keyless bundles,
and GitHub build provenance. Supporter and Pro packages are built and signed by the separate private
TaskForge-Distribution workflow, verified against its exact GitHub Actions identity, and retained as a private
Actions artifact. They are not attached to the public release.

The separate `UNLOCKED-BETA-TEST-NOT-FOR-DISTRIBUTION` Pro test build and ZIP are owner-only evaluation files.
Never upload them to Gumroad or distribute them.

For issues and beta feedback, visit https://github.com/QuasarLI/TaskForge/issues.
