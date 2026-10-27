import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime
from unittest import mock

from taskforge import __version__, editions, licensing, pagefile, procman, sysinfo, virustotal
from taskforge.page_resources import ADS
from taskforge.themes import THEMES, TOKENS, contrast_foreground, design_tokens, stylesheet
from taskforge.widgets import PAGE_MARGINS, PAGE_SPACING
from taskforge.splash import (ANIMATION_DURATION_MS, STAGES, StartupSplash, animation_enabled,
                              should_show_splash, startup_failure_message)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class VirusTotalTests(unittest.TestCase):
    def test_explicit_hash_only_lookup_and_session_cache(self):
        sha256 = "a" * 64
        requests = []

        def opener(request, timeout):
            requests.append(request)
            if request.full_url.endswith("/users/me"):
                return Response({"data": {"id": "mock-user"}})
            return Response({"data": {"attributes": {"last_analysis_stats": {
                "malicious": 1, "suspicious": 2, "undetected": 40, "harmless": 5}}}})

        with tempfile.TemporaryDirectory() as folder:
            store = virustotal.SecretStore(
                os.path.join(folder, "vt.key"), protector=lambda value: value[::-1],
                unprotector=lambda value: value[::-1])
            client = virustotal.VirusTotalClient(store, opener)
            client.verify_key("unit-test-key")
            with open(store.path, "rb") as handle:
                self.assertNotIn(b"unit-test-key", handle.read())
            result = client.lookup_hash(sha256)
            cached = client.lookup_hash(sha256)
            self.assertEqual(result["malicious"], 1)
            self.assertEqual(datetime.fromisoformat(result["checked_at"]).tzinfo is not None, True)
            self.assertTrue(cached["cached"])
            self.assertEqual(len(requests), 2)
            self.assertTrue(requests[1].full_url.endswith("/files/" + sha256))
            self.assertIsNone(requests[1].data)
            self.assertEqual(requests[1].get_header("X-apikey"), "unit-test-key")
            store.clear()
            with self.assertRaises(virustotal.VirusTotalError):
                client.lookup_hash("b" * 64)

    def test_rate_limit_and_bad_hash_are_sanitized(self):
        def limited(_request, timeout):
            raise urllib.error.HTTPError("https://www.virustotal.com/api/v3/files", 429, "limited", {}, None)

        with tempfile.TemporaryDirectory() as folder:
            store = virustotal.SecretStore(os.path.join(folder, "vt.key"),
                                           protector=lambda value: value, unprotector=lambda value: value)
            store.save("unit-test-key")
            client = virustotal.VirusTotalClient(store, limited)
            with self.assertRaisesRegex(virustotal.VirusTotalError, "rate limit"):
                client.lookup_hash("a" * 64)
            with self.assertRaisesRegex(virustotal.VirusTotalError, "SHA-256"):
                client.lookup_hash("not-a-hash")


class ReleaseTests(unittest.TestCase):
    def test_edition_matrix(self):
        self.assertFalse(editions.CATALOG["free"]["advanced"])
        self.assertTrue(editions.CATALOG["free-ads"]["ads"])
        self.assertEqual(editions.CATALOG["supporter"]["product"], "ncbdzb")
        self.assertEqual(editions.CATALOG["pro"]["product"], "uojwbi")
        self.assertFalse(editions.entitled("pro", activated=True))

    def test_unlocked_test_manifest_is_explicit_and_never_verifies_licenses(self):
        self.assertEqual(editions.normalize_manifest({"edition": "pro-test"})["edition"], "free")
        test_manifest = editions.normalize_manifest({"edition": "pro-test", "test_build": True})
        self.assertEqual(test_manifest["edition"], "pro-test")
        with mock.patch.object(editions, "MANIFEST", test_manifest), \
                mock.patch.object(editions, "EDITION", editions.PRO_TEST):
            self.assertTrue(editions.is_test_build())
            self.assertTrue(editions.can("pro"))
            with self.assertRaisesRegex(licensing.LicenseError, "does not accept"):
                licensing.verify_license("uojwbi", "", "mock-product", opener=lambda *_args: self.fail())

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

    def test_configured_beta_product_ids(self):
        supporter = "qIWfZBJk_q_bpjPcghP3wA=="
        pro = "aBykQcqc7WgISimkDyJnXw=="
        for permalink, product_id in (("ncbdzb", supporter), ("uojwbi", pro)):
            opener = lambda _request, timeout, pid=product_id: Response({
                "success": True, "purchase": {"product_id": pid, "refunded": False}})
            record = licensing.verify_license(permalink, "mock-license-key", product_id, opener)
            self.assertEqual(record["product_id"], product_id)

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

    def test_theme_system_has_shared_layout_and_accessible_states(self):
        self.assertEqual(PAGE_MARGINS, (24, 20, 24, 16))
        self.assertEqual(PAGE_SPACING, 14)
        self.assertEqual(TOKENS["control_height"], 34)
        self.assertEqual(contrast_foreground("#ffffff"), "#111827")
        self.assertEqual(contrast_foreground("#000000"), "#ffffff")
        for name, colors in THEMES.items():
            with self.subTest(theme=name):
                tokens = design_tokens(name)
                self.assertEqual(tokens["accent"], colors["accent"])
                self.assertIn(tokens["accent_text"], ("#111827", "#ffffff"))
                css = stylesheet(name)
                for selector in ("#PageHeader", "#MetricCard", "QPushButton:focus",
                                 "QLineEdit:focus", "QTableWidget::item:selected",
                                 "#Sidebar[compact=\"true\"]"):
                    self.assertIn(selector, css)
                self.assertNotIn("{accent}", css)

    def test_splash_stages_motion_startup_policy_and_failure_escape(self):
        self.assertEqual(STAGES, (
            "Loading settings and theme",
            "Initializing system monitors",
            "Preparing dashboard and process data",
            "Restoring tray and preferences",
            "Ready",
        ))
        self.assertLessEqual(ANIMATION_DURATION_MS, 900)
        settings = {"start_minimized": True}
        self.assertFalse(should_show_splash(settings, [], tray_available=True))
        self.assertTrue(should_show_splash(settings, [], tray_available=False))
        self.assertFalse(should_show_splash({}, ["--background"], tray_available=True))
        self.assertFalse(should_show_splash({}, ["--selftest"], tray_available=True))
        self.assertTrue(animation_enabled())
        self.assertFalse(animation_enabled(reduced_motion=True))
        self.assertFalse(animation_enabled(high_contrast=True))
        self.assertFalse(animation_enabled(battery_saver=True))
        message = startup_failure_message(STAGES[2], RuntimeError("view initialization"))
        self.assertIn("try again", message)
        self.assertIn(STAGES[2], message)
        self.assertIn("view initialization", message)

        app = QApplication.instance() or QApplication([])
        splash = StartupSplash("Matrix Green", test_build=True, reduced_motion=True)
        try:
            self.assertFalse(splash.animate)
            self.assertFalse(splash._animation_timer.isActive())
            self.assertIn("NOT FOR DISTRIBUTION", splash.watermark.text())
            self.assertEqual(splash.progress.maximum(), len(STAGES) - 1)
            for stage in STAGES:
                splash.set_stage(stage)
                self.assertEqual(splash.status.text(), stage)
            self.assertFalse(splash._long_startup_timer.isActive())
            self.assertFalse(splash._animation_timer.isActive())
        finally:
            splash.stop_animation()
            splash.close()
            app.processEvents()
        animated = StartupSplash("Matrix Green", reduced_motion=False)
        try:
            animated._motion.start()
            image = QImage(animated.size(), QImage.Format.Format_ARGB32)
            animated.render(image)
            self.assertTrue(animated.animate)
            self.assertFalse(animated._animation_timer.isActive())
        finally:
            animated.stop_animation()
            animated.close()

    def test_beta_version_and_owner_test_packaging_are_explicit(self):
        root = os.path.dirname(os.path.dirname(__file__))
        self.assertEqual(__version__, "2.4.0-beta.1")
        with open(os.path.join(root, "build.ps1"), encoding="utf-8") as handle:
            build_script = handle.read()
        self.assertIn("$version = '2.4.0-beta.1'", build_script)
        self.assertIn("UNLOCKED-BETA-TEST-NOT-FOR-DISTRIBUTION", build_script)
        self.assertIn("test_build=$true", build_script)
        with open(os.path.join(root, ".github", "workflows", "release.yml"), encoding="utf-8") as handle:
            release_workflow = handle.read()
        self.assertIn('$version = "2.4.0-beta.1"', release_workflow)
        self.assertIn('"Free", "Free-with-Ads"', release_workflow)

    def test_pagefile_dry_run(self):
        self.assertEqual(pagefile.build_line("system", "C"), r"C:\pagefile.sys 0 0")
        initial, maximum = pagefile.recommend(16 * 1024**3, 20 * 1024**3)
        self.assertGreaterEqual(initial, 2048)
        self.assertGreaterEqual(maximum, initial)
        self.assertEqual(pagefile.validate_fixed_local_drive("D", lambda _root: 3), "D:\\")
        with self.assertRaises(ValueError):
            pagefile.validate_fixed_local_drive("E", lambda _root: 2)
        with self.assertRaises(ValueError):
            pagefile.build_line("custom", "C", 2048, 1024)

    def test_firmware_placeholder_sanitization(self):
        for value in ("Default string", "To Be Filled By O.E.M.", "System Product Name",
                      "Unknown", "Not Specified", "00000000", "   "):
            self.assertIsNone(sysinfo.sanitize_firmware_value(value), value)
        self.assertEqual(sysinfo.sanitize_firmware_value("Example Board"), "Example Board")
        result = sysinfo.sanitize_hardware_inventory({
            "system": {"Manufacturer": "Default string", "Model": "Model X"},
            "board": {"Manufacturer": "Maker", "Product": "System Product Name"},
        })
        self.assertIsNone(result["system"]["Manufacturer"])
        self.assertIsNone(result["board"]["Product"])

    def test_process_history_and_non_verdict_risk_signals(self):
        history = procman.ProcessHistory(capacity=2)
        for sample in (1, 2, 3):
            history.update([{"pid": 10, "create": 100, "cpu": sample, "ws": sample * 100}])
        self.assertEqual(len(history.samples[(10, 100)]["cpu"]), 2)
        row = {"pid": 10, "create": 200, "cpu": 1, "ws": 100}
        history.update([row])
        self.assertNotIn((10, 100), history.samples)
        self.assertEqual(len(row["history"]["memory"]), 1)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sample.exe")
            with open(path, "wb") as handle:
                handle.write(b"not executed")
            signals = procman.process_risk_signals(path, "NotSigned", windows_dir=r"Z:\Windows")
        self.assertTrue(any("Authenticode" in signal for signal in signals))
        self.assertFalse(any("malware detected" in signal.lower() for signal in signals))
        self.assertTrue(procman.protection_reason(4))

    def test_process_list_order_is_stable_between_samples(self):
        previous = [8, 3, 5]
        rows = {3: {"cpu": 100}, 5: {"cpu": 1}, 8: {"cpu": 25}, 11: {"cpu": 50}}
        result = procman.preserve_process_order(previous, rows, lambda row: row["cpu"], reverse=True)
        self.assertEqual(result, [8, 3, 5, 11])
        self.assertEqual(procman.preserve_process_order(result, {3: rows[3], 11: rows[11]},
                                                        lambda row: row["cpu"]), [3, 11])


if __name__ == "__main__":
    unittest.main()
