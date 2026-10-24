"""Gumroad customer-license verification and DPAPI-protected local activation."""
import base64
import ctypes
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes

from .util import app_data_dir

VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"


class LicenseError(Exception):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def redact(value):
    return "<redacted>" if value else "<empty>"


def _blob(data):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(source), "TaskForge activation", None, None, None, 0, ctypes.byref(output)):
        raise LicenseError("Windows could not protect the activation record.")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def unprotect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)):
        raise LicenseError("This activation record cannot be opened by the current Windows user.")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


class ActivationStore:
    def __init__(self, path=None, protector=protect, unprotector=unprotect):
        self.path = path or os.path.join(app_data_dir(), "activation.dat")
        self.protector, self.unprotector = protector, unprotector

    def save(self, record):
        payload = json.dumps(record, sort_keys=True).encode("utf-8")
        encoded = base64.b64encode(self.protector(payload))
        temp = self.path + ".tmp"
        with open(temp, "wb") as handle:
            handle.write(encoded)
        os.replace(temp, self.path)

    def load(self):
        try:
            with open(self.path, "rb") as handle:
                return json.loads(self.unprotector(base64.b64decode(handle.read())).decode("utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError) as exc:
            raise LicenseError(f"Stored activation is unreadable: {type(exc).__name__}") from exc

    def clear(self):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


def verify_license(product_permalink, license_key, product_id=None, opener=urllib.request.urlopen):
    if product_permalink not in ("ncbdzb", "uojwbi"):
        raise LicenseError("Unknown TaskForge product.")
    if not license_key or len(license_key.strip()) < 8:
        raise LicenseError("Enter the complete Gumroad license key.")
    if not product_id:
        raise LicenseError("This paid build has no Gumroad product ID configured. The seller must rebuild it with "
                           "the product ID from Gumroad; permalinks alone are not accepted for newer products.")
    body = urllib.parse.urlencode({
        "product_id": product_id,
        "license_key": license_key.strip(),
        "increment_uses_count": "false",
    }).encode("ascii")
    request = urllib.request.Request(
        VERIFY_URL, data=body, method="POST",
        headers={"User-Agent": "TaskForge/2.1", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise LicenseError("Gumroad verification could not be completed. Check the connection and try again.") from exc
    if not result.get("success"):
        raise LicenseError("Gumroad did not accept this key for this edition.")
    purchase = result.get("purchase") or {}
    if purchase.get("refunded") or purchase.get("chargebacked") or purchase.get("subscription_ended_at"):
        raise LicenseError("This purchase is no longer active.")
    returned = purchase.get("product_id")
    if returned and returned != product_id:
        raise LicenseError("The key belongs to a different TaskForge edition.")
    return {"product": product_permalink, "product_id": product_id, "license_key": license_key.strip(),
            "verified": True}
