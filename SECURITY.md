# Security

## Safety model

- Critical Windows processes are protected from kill and suspend operations.
- Destructive actions require confirmation; pagefile and power changes are backed up before writes.
- Elevated rights are requested through normal Windows UAC only when needed.
- TaskForge uses documented Windows APIs, registry values, and `powercfg`; it does not write MSRs or firmware.
- Builds contain no seller secrets, API tokens, or customer keys.
- Paid unlocks fail closed on verification errors and enforce the build's product permalink.
- Activation data is protected by Windows DPAPI and diagnostics redact license values.
- VirusTotal keys are optional, stored with Windows DPAPI, and used only for an explicit v3 hash lookup. Executables
  are never uploaded; request failures are surfaced without exposing the key.
- Process context signals (path, signature state, publisher and hash) are not malware verdicts. Never rely on them
  instead of a trusted endpoint security product.
- Working-set trimming and paging-file changes are opt-in; trimming may hurt responsiveness, while pagefile changes
  require administrator rights, backup, and reboot. Tests use mocks and do not tune the host.

## Reporting

Report vulnerabilities privately through GitHub's security advisory feature for `QuasarLI/TaskForge`. Do not include
real customer license keys, access tokens, or personal data in a report.

## Release verification

Official public artifacts have SHA-256 checksums, Sigstore keyless bundles, and GitHub build provenance. Verify the
certificate identity and OIDC issuer shown in README before running a download.

## Feature boundaries

TaskForge uses documented Windows user-mode interfaces. It does not install a kernel driver, inspect arbitrary
kernel objects, write hardware registers, upload process files, or claim full parity with Task Manager/Process
Explorer. VirusTotal queries disclose a hash and request metadata to VirusTotal only after explicit user action.
