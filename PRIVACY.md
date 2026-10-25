# Privacy and advertising

TaskForge collects no analytics or telemetry and includes no tracking SDK. Settings, change backups, diagnostics,
and paid activation state stay under the current Windows user's `%APPDATA%\TaskForge` directory.

Supporter and Pro contact Gumroad only when the user explicitly clicks **Activate**. The customer-entered key is
posted over HTTPS to Gumroad's license verification endpoint, never printed or logged, and the local record is
encrypted with Windows DPAPI for the current user. Deactivation deletes the local record.

Free with Ads displays clearly labeled affiliate cards only in **Edition & Resources**. Links open in the default
browser only after an explicit click. TaskForge has no embedded browser, auto-download, popup, countdown, impression
tracking, or click tracking of its own. The destination may apply its own privacy policy.

## Optional VirusTotal hash lookup

TaskForge computes SHA-256 locally. It does not contact VirusTotal automatically. If the user explicitly adds an
API key, the key is protected for the current Windows user using DPAPI and is sent only to VirusTotal v3 when the
user requests a hash report or verifies the key. TaskForge sends the file hash and normal HTTPS request metadata;
it does not upload the executable or its contents. The API key is not placed in a URL, logs, diagnostics, or exports.
Non-secret report counts and a timestamp are cached in memory for the current app session only. The user may remove
the saved key at any time. VirusTotal's own privacy and retention terms apply to data it receives.
