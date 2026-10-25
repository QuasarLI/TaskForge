"""Edition, activation, privacy, export and curated resources UI."""
import json
import os
import webbrowser

from PyQt6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from . import __version__, editions, licensing
from .util import app_data_dir
from .widgets import explain, page_header

ADS = [
    ("AdGuard", "Block intrusive ads and trackers", "https://adguard.com/?aid=138471"),
    ("AdGuard VPN", "Optional encrypted VPN service", "https://adguard-vpn.com/?aid=138471"),
    ("AdGuard DNS", "DNS-level filtering for your devices", "https://adguard-dns.io/?aid=138471"),
]
GUMROAD = {
    editions.SUPPORTER: "https://quasarlabs3.gumroad.com/l/ncbdzb",
    editions.PRO: "https://quasarlabs3.gumroad.com/l/uojwbi",
}


class ResourcesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.policy = editions.info()
        self.store = licensing.ActivationStore()
        self.activation = self._load()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(22, 18, 22, 12)
        lay.addWidget(page_header("Edition & Resources",
                                  f"TaskForge {self.policy['name']} {__version__} - clear choices, no dark patterns."))
        self.state = QLabel()
        self.state.setWordWrap(True)
        self.state.setObjectName("Value")
        lay.addWidget(self.state)
        self._update_state()
        if editions.is_test_build():
            lay.addWidget(explain(
                "UNLOCKED TEST BUILD — NOT FOR DISTRIBUTION OR GUMROAD UPLOAD. This local owner-only build unlocks "
                "features for evaluation, does not verify or accept production license keys, and must never be "
                "uploaded to Gumroad or distributed."))

        matrix = QGroupBox("What each edition includes")
        ml = QVBoxLayout(matrix)
        ml.addWidget(explain(
            "Free: monitoring, process safety, explanations, backups, restore, and basic controls.\n"
            "Free with Ads: advanced RAM/pagefile and CPU tuning, funded by optional affiliate cards on this page.\n"
            "Supporter: all advanced tools with no ads after Gumroad activation.\n"
            "Pro: Supporter features plus automation, reusable presets, export, and priority features.\n\n"
            "Core safety, monitoring, explanations, backups, and restore are never paywalled."))
        lay.addWidget(matrix)

        if self.policy["paid"]:
            self._activation_box(lay)
        elif not editions.is_test_build():
            upgrades = QGroupBox("Optional upgrades")
            ul = QHBoxLayout(upgrades)
            for label, edition in (("TaskForge Supporter", editions.SUPPORTER), ("TaskForge Pro", editions.PRO)):
                button = QPushButton(label)
                button.clicked.connect(lambda _c=False, u=GUMROAD[edition]: webbrowser.open(u))
                ul.addWidget(button)
            ul.addStretch()
            lay.addWidget(upgrades)

        if self.policy["ads"]:
            sponsored = QGroupBox("Sponsored resources")
            sl = QVBoxLayout(sponsored)
            sl.addWidget(explain("Affiliate disclosure: these optional links may earn Quasar Labs a commission. "
                                 "They never open unless clicked; there is no tracking SDK or embedded browser."))
            for title, description, url in ADS:
                row = QHBoxLayout()
                row.addWidget(QLabel(f"<b>{title}</b> - {description}"), 1)
                button = QPushButton("Open website")
                button.clicked.connect(lambda _c=False, u=url: webbrowser.open(u))
                row.addWidget(button)
                sl.addLayout(row)
            lay.addWidget(sponsored)

        learning = QGroupBox("Beginner checklist")
        ll = QVBoxLayout(learning)
        ll.addWidget(explain(
            "RAM: high 'cached' memory is healthy. Prefer Windows-managed paging. Trimming is temporary, not a speed hack.\n"
            "CPU: Balanced is the sensible default. More turbo means more heat, fan noise, and battery use.\n"
            "Admin: only needed when Windows protects a setting. Reboot is required only where the UI says so.\n"
            "Undo: power and pagefile settings are backed up before changes; Restore uses those backups."))
        lay.addWidget(learning)

        if editions.entitled("pro", bool(self.activation)):
            export = QPushButton("Export redacted diagnostics (Pro)")
            export.clicked.connect(self.export_diagnostics)
            lay.addWidget(export)
        lay.addStretch()

    def _load(self):
        try:
            record = self.store.load()
            return record if record and record.get("product") == editions.info()["product"] else None
        except licensing.LicenseError:
            return None

    def _update_state(self):
        if not self.policy["paid"]:
            self.state.setText(f"Running {self.policy['name']}. No activation required.")
        elif self.activation:
            self.state.setText(f"{self.policy['name']} is activated for this Windows user.")
        else:
            self.state.setText(f"{self.policy['name']} is locked. Core features remain available.")

    def _activation_box(self, lay):
        box = QGroupBox("Gumroad activation")
        bl = QVBoxLayout(box)
        bl.addWidget(explain("Enter the license key from your Gumroad receipt. It is sent only to Gumroad's "
                             "verification endpoint and stored locally with Windows DPAPI. It is never logged. "
                             "Paid features fail closed while unverified; a local activation works offline."))
        row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Gumroad license key")
        row.addWidget(self.key, 1)
        activate = QPushButton("Activate")
        activate.setObjectName("AccentBtn")
        activate.clicked.connect(self.activate)
        row.addWidget(activate)
        deactivate = QPushButton("Deactivate this PC")
        deactivate.clicked.connect(self.deactivate)
        row.addWidget(deactivate)
        bl.addLayout(row)
        lay.addWidget(box)

    def activate(self):
        try:
            record = licensing.verify_license(self.policy["product"], self.key.text(), self.policy["product_id"])
            self.store.save(record)
            self.activation = record
            self.key.clear()
            self._update_state()
            QMessageBox.information(self, "TaskForge", "Activation verified and protected. Restart TaskForge "
                                                        "to refresh all edition gates.")
        except licensing.LicenseError as exc:
            QMessageBox.warning(self, "Activation failed", str(exc))

    def deactivate(self):
        self.store.clear()
        self.activation = None
        self.key.clear()
        self._update_state()

    def export_diagnostics(self):
        path = os.path.join(app_data_dir(), "taskforge-diagnostics.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"version": __version__, "edition": self.policy["id"], "activated": bool(self.activation),
                       "activation_key": licensing.redact(self.activation.get("license_key")
                                                         if self.activation else None)}, handle, indent=2)
        QMessageBox.information(self, "TaskForge", f"Redacted diagnostics exported to:\n{path}")
