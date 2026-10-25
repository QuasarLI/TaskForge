"""Explicit, hash-only VirusTotal v3 lookups with a DPAPI-protected API key."""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .licensing import LicenseError, protect, unprotect
from .util import app_data_dir

API_ROOT = "https://www.virustotal.com/api/v3"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class VirusTotalError(Exception):
    pass


class SecretStore:
    def __init__(self, path=None, protector=protect, unprotector=unprotect):
        self.path = path or os.path.join(app_data_dir(), "virustotal.key")
        self.protector, self.unprotector = protector, unprotector

    def save(self, key):
        temporary = self.path + ".tmp"
        try:
            protected = self.protector(key.strip().encode("utf-8"))
            with open(temporary, "wb") as handle:
                handle.write(protected)
            os.replace(temporary, self.path)
        except LicenseError as exc:
            raise VirusTotalError("Windows DPAPI could not protect the VirusTotal key.") from exc
        except OSError as exc:
            raise VirusTotalError("The protected VirusTotal key could not be saved.") from exc

    def load(self):
        try:
            with open(self.path, "rb") as handle:
                return self.unprotector(handle.read()).decode("utf-8")
        except FileNotFoundError:
            return None
        except (LicenseError, OSError, UnicodeError) as exc:
            raise VirusTotalError("The protected VirusTotal key could not be read.") from exc

    def clear(self):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


class VirusTotalClient:
    def __init__(self, store=None, opener=urllib.request.urlopen):
        self.store = store or SecretStore()
        self.opener = opener
        self.cache = {}

    def _get(self, path, key):
        request = urllib.request.Request(
            f"{API_ROOT}{path}", headers={"x-apikey": key, "Accept": "application/json",
                                          "User-Agent": "TaskForge/2.3"})
        try:
            with self.opener(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise VirusTotalError("VirusTotal rate limit reached; wait before retrying.") from None
            if exc.code in (401, 403):
                raise VirusTotalError("VirusTotal rejected the API key or this account's access.") from None
            raise VirusTotalError(f"VirusTotal returned HTTP {exc.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise VirusTotalError("VirusTotal could not be reached or returned an unreadable response.") from None

    def verify_key(self, key):
        if not key or not key.strip():
            raise VirusTotalError("Enter a VirusTotal API key.")
        self._get("/users/me", key.strip())
        self.store.save(key.strip())
        return True

    def lookup_hash(self, sha256):
        if not SHA256_RE.fullmatch(sha256 or ""):
            raise VirusTotalError("A valid SHA-256 hash is required.")
        cached = self.cache.get(sha256.lower())
        if cached:
            return dict(cached, cached=True)
        key = self.store.load()
        if not key:
            raise VirusTotalError("No VirusTotal API key is configured.")
        result = self._get(f"/files/{sha256.lower()}", key)
        attrs = result.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats")
        if not isinstance(stats, dict):
            raise VirusTotalError("VirusTotal returned no file analysis summary.")
        summary = {
            "sha256": sha256.lower(),
            "malicious": int(stats.get("malicious", 0)),
            "suspicious": int(stats.get("suspicious", 0)),
            "undetected": int(stats.get("undetected", 0)),
            "harmless": int(stats.get("harmless", 0)),
            "link": f"https://www.virustotal.com/gui/file/{sha256.lower()}",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }
        self.cache[sha256.lower()] = summary
        return dict(summary)
