import json
import os
import tempfile
import unittest

from taskforge import editions, licensing, pagefile
from taskforge.page_resources import ADS
from taskforge.themes import THEMES


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class ReleaseTests(unittest.TestCase):
    def test_edition_matrix(self):
        self.assertFalse(editions.CATALOG["free"]["advanced"])
        self.assertTrue(editions.CATALOG["free-ads"]["ads"])
        self.assertEqual(editions.CATALOG["supporter"]["product"], "ncbdzb")
        self.assertEqual(editions.CATALOG["pro"]["product"], "uojwbi")
        self.assertFalse(editions.entitled("pro", activated=True))

    def test_license_verification_and_mismatch(self):
        opener = lambda _request, timeout: Response({"success": True, "purchase": {
            "product_id": "supporter-product-id", "refunded": False}})
        record = licensing.verify_license("ncbdzb", "test-key-not-real", "supporter-product-id", opener)
        self.assertEqual(record["product"], "ncbdzb")
        self.assertEqual(licensing.redact(record["license_key"]), "<redacted>")
        with self.assertRaises(licensing.LicenseError):
            licensing.verify_license("uojwbi", "test-key-not-real", "pro-product-id", opener)
        with self.assertRaises(licensing.LicenseError):
            licensing.verify_license("ncbdzb", "test-key-not-real")

    def test_activation_storage_seam(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "activation.dat")
            store = licensing.ActivationStore(path, protector=lambda b: b[::-1], unprotector=lambda b: b[::-1])
            store.save({"license_key": "secret", "product": "ncbdzb"})
            with open(path, "rb") as handle:
                self.assertNotIn(b"secret", handle.read())
            self.assertEqual(store.load()["product"], "ncbdzb")
            store.clear()
            self.assertIsNone(store.load())

    def test_links_and_themes(self):
        approved = {
            "https://adguard.com/?aid=138471",
            "https://adguard-vpn.com/?aid=138471",
            "https://adguard-dns.io/?aid=138471",
        }
        self.assertEqual({url for _, _, url in ADS}, approved)
        self.assertEqual(len(THEMES), 10)
        self.assertIn("Matrix Green", THEMES)

    def test_pagefile_dry_run(self):
        self.assertEqual(pagefile.build_line("system", "C"), r"C:\pagefile.sys 0 0")
        initial, maximum = pagefile.recommend(16 * 1024**3, 20 * 1024**3)
        self.assertGreaterEqual(initial, 2048)
        self.assertGreaterEqual(maximum, initial)


if __name__ == "__main__":
    unittest.main()
