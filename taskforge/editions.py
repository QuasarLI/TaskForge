"""Build-time edition policy loaded from the manifest embedded by build.ps1."""
import json

from .util import resource_path

FREE = "free"
FREE_ADS = "free-ads"
SUPPORTER = "supporter"
PRO = "pro"

CATALOG = {
    FREE: {"name": "Free", "advanced": False, "ads": False, "paid": False, "product": None},
    FREE_ADS: {"name": "Free with Ads", "advanced": True, "ads": True, "paid": False, "product": None},
    SUPPORTER: {"name": "Supporter", "advanced": True, "ads": False, "paid": True, "product": "ncbdzb"},
    PRO: {"name": "Pro", "advanced": True, "ads": False, "paid": True, "product": "uojwbi"},
}


def _load():
    try:
        with open(resource_path("edition.json"), "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        manifest = {"edition": FREE}
    value = manifest.get("edition", FREE)
    manifest["edition"] = value if value in CATALOG else FREE
    return manifest


MANIFEST = _load()
EDITION = MANIFEST["edition"]


def info():
    return dict(CATALOG[EDITION], id=EDITION, product_id=MANIFEST.get("product_id") or None)


def entitled(feature: str, activated=False):
    policy = info()
    unlocked = not policy["paid"] or activated
    if feature == "core":
        return True
    if feature == "advanced":
        return policy["advanced"] and unlocked
    if feature == "pro":
        return EDITION == PRO and unlocked
    return False


def activated():
    if not info()["paid"]:
        return True
    try:
        from .licensing import ActivationStore, LicenseError
        record = ActivationStore().load()
        return bool(record and record.get("verified") and record.get("product") == info()["product"])
    except (LicenseError, OSError):
        return False


def can(feature: str):
    return entitled(feature, activated())
