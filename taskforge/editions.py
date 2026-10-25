"""Build-time edition policy loaded from the manifest embedded by build.ps1."""
import json

from .util import resource_path

FREE = "free"
FREE_ADS = "free-ads"
SUPPORTER = "supporter"
PRO = "pro"
PRO_TEST = "pro-test"
TEST_BUILD_NAME = "UNLOCKED TEST BUILD — NOT FOR DISTRIBUTION OR GUMROAD UPLOAD"

CATALOG = {
    FREE: {"name": "Free", "advanced": False, "ads": False, "paid": False, "product": None},
    FREE_ADS: {"name": "Free with Ads", "advanced": True, "ads": True, "paid": False, "product": None},
    SUPPORTER: {"name": "Supporter", "advanced": True, "ads": False, "paid": True, "product": "ncbdzb"},
    PRO: {"name": "Pro", "advanced": True, "ads": False, "paid": True, "product": "uojwbi"},
    PRO_TEST: {"name": TEST_BUILD_NAME, "advanced": True, "ads": False, "paid": False, "product": None},
}


def _load():
    try:
        with open(resource_path("edition.json"), "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        manifest = {"edition": FREE}
    return normalize_manifest(manifest)


def normalize_manifest(manifest):
    manifest = dict(manifest)
    value = manifest.get("edition", FREE)
    test_build = value == PRO_TEST and manifest.get("test_build") is True
    manifest["edition"] = PRO_TEST if test_build else (value if value in CATALOG and value != PRO_TEST else FREE)
    manifest["test_build"] = test_build
    if test_build:
        manifest["product_id"] = None
    return manifest


MANIFEST = _load()
EDITION = MANIFEST["edition"]


def info():
    return dict(CATALOG[EDITION], id=EDITION, product_id=MANIFEST.get("product_id") or None)


def entitled(feature: str, activated=False):
    policy = info()
    unlocked = EDITION == PRO_TEST or not policy["paid"] or activated
    if feature == "core":
        return True
    if feature == "advanced":
        return policy["advanced"] and unlocked
    if feature == "pro":
        return EDITION in (PRO, PRO_TEST) and unlocked
    return False


def activated():
    if EDITION == PRO_TEST:
        return True
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


def is_test_build():
    return bool(MANIFEST.get("test_build"))
