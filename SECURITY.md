# Security

## Safety model

- Critical Windows processes are protected from kill and suspend operations.
- Destructive actions require confirmation; pagefile and power changes are backed up before writes.
- Elevated rights are requested through normal Windows UAC only when needed.
- TaskForge uses documented Windows APIs, registry values, and `powercfg`; it does not write MSRs or firmware.
- Builds contain no seller secrets, API tokens, or customer keys.
- Paid unlocks fail closed on verification errors and enforce the build's product permalink.
- Activation data is protected by Windows DPAPI and diagnostics redact license values.

## Reporting

Report vulnerabilities privately through GitHub's security advisory feature for `QuasarLI/TaskForge`. Do not include
real customer license keys, access tokens, or personal data in a report.

## Release verification

Official public artifacts have SHA-256 checksums, Sigstore keyless bundles, and GitHub build provenance. Verify the
certificate identity and OIDC issuer shown in README before running a download.
