"""CPU & Turbo, Overclocking guide, Startup and Settings pages."""
import os
import subprocess
import webbrowser
import winreg

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
                             QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import __version__, power, sysinfo
from .themes import THEMES
from .util import app_data_dir, backup_dir, fmt_bytes, is_admin, open_path
from .widgets import bar, confirm, explain, page_header, run_async


def scrolled(widget_builder):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    body = QWidget()
    sc.setWidget(body)
    outer.addWidget(sc)
    lay = QVBoxLayout(body)
    lay.setContentsMargins(22, 18, 22, 12)
    widget_builder(lay)
    lay.addStretch()
    return page


# ======================================================================= CPU
class CpuPage(QWidget):
    def __init__(self, monitor, status):
        super().__init__()
        self.monitor, self.status = monitor, status
        self.controls = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        outer.addWidget(sc)
        body = QWidget()
        sc.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(22, 18, 22, 12)
        lay.addWidget(page_header("CPU & Turbo", "Processor details and every turbo/power-management knob Windows "
                                                 "exposes through documented power-plan settings. Hover any control "
                                                 "for details; every change is backed up and reversible."))
        # identity
        idg = QGroupBox("Processor")
        self.id_grid = QGridLayout(idg)
        self.id_vals = {}
        for i, k in enumerate(("Model", "Cores / threads", "Base clock", "Live effective clock", "Bus clock (BCLK)",
                               "L2 / L3 cache", "Virtualization", "Multiplier")):
            cap = QLabel(k)
            cap.setObjectName("Muted")
            v = QLabel("…")
            v.setObjectName("Value")
            v.setWordWrap(True)
            self.id_vals[k] = v
            self.id_grid.addWidget(cap, i // 2, (i % 2) * 2)
            self.id_grid.addWidget(v, i // 2, (i % 2) * 2 + 1)
        ident = monitor.ident
        self.id_vals["Model"].setText(ident["name"])
        self.id_vals["Cores / threads"].setText(f"{ident['cores']} / {ident['threads']}")
        self.id_vals["Base clock"].setText(f"{ident['base_mhz']} MHz")
        unlocked = sysinfo.is_unlocked_cpu(ident["name"])
        self.id_vals["Multiplier"].setText("Likely unlocked — tune in BIOS / vendor tool (see Overclocking Guide)"
                                           if unlocked else "Locked by Intel/AMD for this model (no ratio overclock)")
        lay.addWidget(idg)

        # power plans
        pp = QGroupBox("Windows power plan")
        pl = QVBoxLayout(pp)
        row = QHBoxLayout()
        self.scheme_combo = QComboBox()
        row.addWidget(self.scheme_combo, 1)
        act = QPushButton("Activate plan")
        act.setObjectName("AccentBtn")
        act.clicked.connect(self.activate_scheme)
        ult = QPushButton("Add Ultimate Performance plan")
        ult.clicked.connect(self.add_ultimate)
        ctl = QPushButton("Open Power Options")
        ctl.clicked.connect(lambda: subprocess.Popen(["control", "powercfg.cpl"]))
        for b in (act, ult, ctl):
            row.addWidget(b)
        pl.addLayout(row)
        pl.addWidget(explain("Balanced lets the CPU sleep and boost on demand (recommended for most). High / "
                             "Ultimate Performance keep clocks and devices at full readiness for lower latency at the "
                             "cost of idle power and heat. Ultimate is a hidden Microsoft plan for workstations; adding "
                             "it only creates the plan, it doesn't activate it."))
        lay.addWidget(pp)

        # presets
        pr = QGroupBox("Turbo presets (apply to the active plan)")
        prl = QGridLayout(pr)
        for i, (name, p) in enumerate(power.PRESETS.items()):
            b = QPushButton(name)
            b.setObjectName("AccentBtn" if name == "Max Turbo" else "")
            b.setMinimumWidth(170)
            b.clicked.connect(lambda _c=False, n=name: self.apply_preset(n))
            prl.addWidget(b, i, 0)
            prl.addWidget(explain(p["desc"]), i, 1)
        lay.addWidget(pr)

        # advanced
        adv = QGroupBox("Advanced processor power management")
        al = QGridLayout(adv)
        al.setColumnStretch(3, 1)
        hdr = [QLabel("Setting"), QLabel("Plugged in"), QLabel("On battery"), QLabel("What it does")]
        for i, h in enumerate(hdr):
            h.setObjectName("Muted")
            al.addWidget(h, 0, i)
        for r, (key, guid, label, kind, options, desc) in enumerate(power.PROCESSOR_SETTINGS, start=1):
            al.addWidget(QLabel(f"<b>{label}</b>"), r, 0)
            pair = []
            for c in (1, 2):
                if kind == "enum":
                    w = QComboBox()
                    for v, n in options:
                        w.addItem(n, v)
                else:
                    w = QSpinBox()
                    w.setRange(0, 100)
                    w.setSuffix(" %")
                w.setToolTip(desc)
                w.setMinimumWidth(150)
                al.addWidget(w, r, c)
                pair.append(w)
            self.controls[key] = (kind, pair)
            al.addWidget(explain(desc), r, 3)
        btns = QHBoxLayout()
        apply_b = QPushButton("Apply changes")
        apply_b.setObjectName("AccentBtn")
        apply_b.clicked.connect(self.apply_manual)
        reload_b = QPushButton("Reload from Windows")
        reload_b.clicked.connect(self.reload)
        restore_b = QPushButton("Restore a backup…")
        restore_b.clicked.connect(self.restore)
        for b in (apply_b, reload_b, restore_b):
            btns.addWidget(b)
        btns.addStretch()
        al.addLayout(btns, len(power.PROCESSOR_SETTINGS) + 1, 0, 1, 4)
        self.adv_state = explain("")
        al.addWidget(self.adv_state, len(power.PROCESSOR_SETTINGS) + 2, 0, 1, 4)
        lay.addWidget(adv)

        # per-core
        cg = QGroupBox("Per-core load")
        cgl = QGridLayout(cg)
        self.core_bars = []
        for i in range(ident["threads"] or 1):
            cgl.addWidget(QLabel(f"CPU {i}"), i // 4, (i % 4) * 2)
            b = bar()
            self.core_bars.append(b)
            cgl.addWidget(b, i // 4, (i % 4) * 2 + 1)
        lay.addWidget(cg)
        lay.addStretch()

        monitor.updated.connect(self.refresh)
        self.reload()

    # ------------------------------------------------------------- data
    def set_inventory(self, inv):
        c = inv.get("cpu") or {}
        ext = c.get("ExtClock")
        self.id_vals["Bus clock (BCLK)"].setText(f"{ext} MHz (firmware-reported)" if ext else "n/a")
        l2, l3 = c.get("L2CacheSize"), c.get("L3CacheSize")
        self.id_vals["L2 / L3 cache"].setText(f"{fmt_bytes((l2 or 0) * 1024)} / {fmt_bytes((l3 or 0) * 1024)}")
        v = c.get("VirtualizationFirmwareEnabled")
        self.id_vals["Virtualization"].setText("Enabled in firmware" if v else ("Disabled / in use by Hyper-V"
                                                                                if v is not None else "n/a"))

    def refresh(self, s):
        if not self.isVisible():
            return
        base = self.monitor.ident["base_mhz"] or 1
        self.id_vals["Live effective clock"].setText(f"{s['mhz']} MHz ({100*s['mhz']/base:.0f}% of base)")
        for b, v in zip(self.core_bars, s["percore"]):
            b.setValue(int(v))

    def reload(self):
        self.adv_state.setText("Reading current plan…")
        run_async(self, lambda: (power.list_schemes(), power.read_all()), on_done=self._loaded,
                  on_fail=lambda m: self.adv_state.setText(f"Could not read power settings: {m}"))

    def _loaded(self, res):
        schemes, values = res
        self.scheme_combo.clear()
        for guid, name, active in schemes:
            self.scheme_combo.addItem(f"{name}{'   (active)' if active else ''}", guid)
            if active:
                self.scheme_combo.setCurrentIndex(self.scheme_combo.count() - 1)
        missing = []
        for key, (kind, pair) in self.controls.items():
            v = values.get(key)
            for w, val in zip(pair, v or (None, None)):
                w.setEnabled(v is not None)
                if val is None:
                    continue
                if kind == "enum":
                    i = w.findData(val)
                    if i < 0:
                        w.addItem(f"Value {val}", val)
                        i = w.count() - 1
                    w.setCurrentIndex(i)
                else:
                    w.setValue(val)
            if v is None:
                missing.append(key)
        self.loaded = values
        self.adv_state.setText("Values loaded from the active plan." + (
            f" Not supported on this system: {', '.join(missing)}." if missing else ""))

    def _current_values(self):
        ac, dc = {}, {}
        for key, (kind, pair) in self.controls.items():
            if not pair[0].isEnabled():
                continue
            get = (lambda w: w.currentData()) if kind == "enum" else (lambda w: w.value())
            ac[key], dc[key] = get(pair[0]), get(pair[1])
        return ac, dc

    # ------------------------------------------------------------- actions
    def _apply(self, ac_vals, dc_vals, note):
        try:
            bpath = power.backup(note)
        except (power.PowerError, OSError) as e:
            QMessageBox.critical(self, "TaskForge", f"Backup failed, nothing changed: {e}")
            return
        errors = []
        try:
            errors += power.apply_values(ac_vals, ac=True, dc=False)
            errors += power.apply_values(dc_vals, ac=False, dc=True)
        except power.PowerError as e:
            errors.append(str(e))
        self.reload()
        if errors:
            QMessageBox.warning(self, "Some settings were rejected", "\n".join(errors[:10]) +
                                ("\n\nTry running as administrator." if not is_admin() else ""))
        self.status(f"Power settings applied ({note}). Backup: {os.path.basename(bpath)}")

    def apply_preset(self, name):
        p = power.PRESETS[name]
        vals = {k: v for k, v in p["values"].items() if self.controls[k][1][0].isEnabled()}
        lines = "\n".join(f"  • {power.SETTING_BY_KEY[k][2]}: {self._fmt(k, v)}" for k, v in vals.items())
        if confirm(self, f"Apply preset: {name}", f"{p['desc']}\n\nChanges (plugged in AND battery):\n{lines}\n\n"
                                                  "Current values are backed up first. Continue?"):
            self._apply(vals, vals, f"preset {name}")

    def apply_manual(self):
        ac, dc = self._current_values()
        old = getattr(self, "loaded", {})
        diff = [f"  • {power.SETTING_BY_KEY[k][2]}: {self._fmt(k, old[k][0])}/{self._fmt(k, old[k][1])} → "
                f"{self._fmt(k, ac[k])}/{self._fmt(k, dc[k])}" for k in ac if old.get(k) and (ac[k], dc[k]) != old[k]]
        if not diff:
            self.status("No changes to apply.")
            return
        if confirm(self, "Apply processor settings", "Changes (plugged in / battery):\n" + "\n".join(diff) +
                   "\n\nCurrent values are backed up first. Continue?"):
            self._apply(ac, dc, "manual")

    def _fmt(self, key, v):
        _, _, _, kind, options, _ = power.SETTING_BY_KEY[key]
        if kind == "enum":
            return dict(options).get(v, str(v))
        return f"{v}%"

    def restore(self):
        files = power.list_backups()
        if not files:
            QMessageBox.information(self, "TaskForge", "No power backups yet. One is created automatically before "
                                                       "every change.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose a power backup", backup_dir(), "Power backup (power-*.json)")
        if path and confirm(self, "Restore", f"Restore power plan and processor settings from\n{os.path.basename(path)}?"):
            try:
                data, errors = power.restore_backup(path)
            except (OSError, ValueError, power.PowerError) as e:
                QMessageBox.critical(self, "TaskForge", str(e))
                return
            self.reload()
            self.status(f"Restored power settings from {data.get('created')}")
            if errors:
                QMessageBox.warning(self, "Partially restored", "\n".join(errors[:10]))

    def activate_scheme(self):
        guid = self.scheme_combo.currentData()
        if guid and confirm(self, "Activate plan", f"Switch Windows to “{self.scheme_combo.currentText()}”?\n"
                                                   "(Previous plan is recorded in a backup.)"):
            try:
                power.backup("before plan switch")
                power.set_active(guid)
                self.status(f"Activated {self.scheme_combo.currentText()}")
            except power.PowerError as e:
                QMessageBox.warning(self, "TaskForge", str(e))
            self.reload()

    def add_ultimate(self):
        if any("ultimate" in self.scheme_combo.itemText(i).lower() for i in range(self.scheme_combo.count())):
            QMessageBox.information(self, "TaskForge", "An Ultimate Performance plan already exists.")
            return
        if confirm(self, "Add Ultimate Performance", "Create the hidden Ultimate Performance plan? It will appear in "
                                                     "the list; it is not activated automatically."):
            try:
                power.create_ultimate()
                self.status("Ultimate Performance plan created")
            except power.PowerError as e:
                QMessageBox.warning(self, "TaskForge", f"{e}\n(Some Modern-Standby laptops block this plan.)")
            self.reload()


# ============================================================= OC guide
VENDOR_LINKS = {
    "intel": [("Intel Extreme Tuning Utility (XTU)", "https://www.intel.com/content/www/us/en/download/17881/",
               "Multiplier, voltage offset, power limits (PL1/PL2), Turbo Boost Max. Only supports unlocked "
               "or selected CPUs/platforms; many laptops lock it.")],
    "amd": [("AMD Ryzen Master", "https://www.amd.com/en/technologies/ryzen-master",
             "Per-CCX/core ratios, Precision Boost Overdrive, Curve Optimizer, memory timings on Ryzen desktop CPUs.")],
    "common": [
        ("HWiNFO (sensors)", "https://www.hwinfo.com/", "Free deep sensor monitor: temps, voltages, power, throttling "
                                                        "reasons. Use alongside any tuning."),
        ("ThrottleStop (3rd-party)", "https://www.techpowerup.com/download/techpowerup-throttlestop/",
         "Intel power limits, turbo ratios and undervolting where the firmware allows it. Advanced users only."),
        ("ASUS Armoury Crate / AI Suite", "https://www.asus.com/supportonly/armoury%20crate/", "ASUS board tuning."),
        ("MSI Center", "https://www.msi.com/Landing/MSI-Center", "MSI board tuning & profiles."),
        ("GIGABYTE Control Center", "https://www.gigabyte.com/Support/Utility", "GIGABYTE board tools."),
        ("ASRock A-Tuning", "https://www.asrock.com/", "ASRock board tuning."),
    ],
}


def build_oc_guide(monitor, settings_get):
    ident = monitor.ident
    fam = sysinfo.cpu_vendor_family(ident["name"], ident["vendor"])
    unlocked = sysinfo.is_unlocked_cpu(ident["name"])
    holder = {}

    def build(lay):
        lay.addWidget(page_header("Overclocking Guide", "What can (and can't) be tuned on this machine, and the "
                                                        "right tool for each control."))
        sumg = QGroupBox("Your hardware")
        sl = QVBoxLayout(sumg)
        holder["hw"] = QLabel("Loading inventory…")
        holder["hw"].setTextFormat(Qt.TextFormat.RichText)
        holder["hw"].setWordWrap(True)
        sl.addWidget(holder["hw"])
        verdict = (f"<b>{ident['name']}</b> appears <b>{'UNLOCKED' if unlocked else 'LOCKED'}</b>. " +
                   ("Ratio, voltage and BCLK overclocking are possible from BIOS or the vendor utility below."
                    if unlocked else
                    "Intel/AMD fuse the multiplier on this model, and BCLK/voltage are not exposed by consumer "
                    "firmware. The useful levers are turbo behaviour, power limits (if the BIOS exposes them), "
                    "cooling and RAM — the CPU & Turbo page covers everything Windows can change safely."))
        v = QLabel(verdict)
        v.setWordWrap(True)
        v.setTextFormat(Qt.TextFormat.RichText)
        sl.addWidget(v)
        lay.addWidget(sumg)

        tbl = QGroupBox("Control-by-control")
        tl = QGridLayout(tbl)
        rows = [
            ("Turbo eagerness / max state / EPP / core parking", "TaskForge → CPU & Turbo", "Available now"),
            ("Power plan (Balanced / High / Ultimate)", "TaskForge → CPU & Turbo", "Available now"),
            ("CPU multiplier (ratio) overclock", "BIOS, Intel XTU, AMD Ryzen Master", "Unlocked CPUs only"),
            ("BCLK / bus speed (FSB)", "BIOS (some boards' utilities)", "Board-dependent; affects PCIe/RAM too"),
            ("Core voltage / undervolt / Curve Optimizer", "BIOS, XTU, Ryzen Master, ThrottleStop",
             "Often locked on laptops (Plundervolt mitigation)"),
            ("Power limits PL1/PL2 / PPT, TDC, EDC", "BIOS, XTU, Ryzen Master (PBO)", "Platform-dependent"),
            ("RAM XMP / EXPO profile, timings", "BIOS", "Desktop boards; laptops usually fixed"),
            ("Fan curves", "BIOS or board utility", "Board-dependent"),
        ]
        for i, h in enumerate(("Control", "Where to change it", "Availability")):
            lab = QLabel(h)
            lab.setObjectName("Muted")
            tl.addWidget(lab, 0, i)
        for r, row in enumerate(rows, 1):
            for c, text in enumerate(row):
                l = QLabel(text)
                l.setWordWrap(True)
                tl.addWidget(l, r, c)
        tl.addWidget(explain("Why TaskForge doesn't write voltages/ratios directly: those live in model-specific "
                             "registers (MSRs) and chipset registers that need a signed kernel driver, differ per "
                             "CPU generation, and can corrupt data or damage hardware if wrong. Vendor tools validate "
                             "against your exact silicon; TaskForge sticks to documented Windows interfaces."),
                     len(rows) + 1, 0, 1, 3)
        lay.addWidget(tbl)

        tools = QGroupBox("Vendor & specialist tools")
        gl = QGridLayout(tools)
        links = VENDOR_LINKS.get(fam, []) + VENDOR_LINKS["common"]
        for r, (name, url, desc) in enumerate(links):
            b = QPushButton(name)
            b.clicked.connect(lambda _c=False, u=url: webbrowser.open(u))
            gl.addWidget(b, r, 0)
            gl.addWidget(explain(desc), r, 1)
        r = len(links)
        pe = QPushButton("Launch Process Explorer")
        pe.clicked.connect(lambda: _launch(settings_get("procexp_path")))
        gl.addWidget(pe, r, 0)
        gl.addWidget(explain("Sysinternals Process Explorer (path set in Settings) for handle/DLL-level inspection."), r, 1)
        bios = QPushButton("Restart into BIOS/UEFI…")
        bios.clicked.connect(lambda: _uefi(bios))
        gl.addWidget(bios, r + 1, 0)
        gl.addWidget(explain("Reboots straight to firmware setup (shutdown /r /fw). Save your work first."), r + 1, 1)
        lay.addWidget(tools)

    page = scrolled(build)

    def set_inventory(inv):
        b, bios, sysd = inv.get("board") or {}, inv.get("bios") or {}, inv.get("system") or {}
        dimms = inv.get("dimms") or []
        mem = ", ".join(f"{fmt_bytes(int(d.get('Capacity') or 0))} @ {d.get('ConfiguredClockSpeed') or d.get('Speed')} "
                        f"MT/s ({(d.get('Manufacturer') or '').strip()})" for d in dimms) or "n/a"
        kind = {1: "Desktop", 2: "Laptop / mobile", 3: "Workstation"}.get(sysd.get("PCSystemType"), "Unknown")
        holder["hw"].setText(
            f"<b>System:</b> {sysd.get('Manufacturer', '')} {sysd.get('Model', '')} ({kind})<br>"
            f"<b>Motherboard:</b> {b.get('Manufacturer', 'n/a')} {b.get('Product', '')}<br>"
            f"<b>BIOS:</b> {bios.get('Manufacturer', '')} {bios.get('SMBIOSBIOSVersion', '')}<br>"
            f"<b>Memory modules:</b> {mem}")

    page.set_inventory = set_inventory
    return page


def _launch(path):
    if path and os.path.exists(path):
        open_path(path)
    else:
        QMessageBox.information(None, "TaskForge", f"Tool not found:\n{path}\nSet the path in Settings.")


def _uefi(parent):
    if not is_admin():
        QMessageBox.warning(parent, "TaskForge", "Requires administrator rights.")
        return
    if confirm(parent, "Restart to firmware", "Restart NOW into BIOS/UEFI setup? Unsaved work will be lost.", True):
        subprocess.Popen(["shutdown", "/r", "/fw", "/t", "5"])


# ============================================================== startup
RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU Run",
     r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM Run",
     r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM Run (32-bit)",
     r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32"),
]


def _approved(hive, key, name):
    try:
        with winreg.OpenKey(hive, key) as k:
            data = winreg.QueryValueEx(k, name)[0]
            return "Disabled" if data and data[0] in (1, 3) else "Enabled"
    except OSError:
        return "Enabled"


def read_startup():
    items = []
    for hive, key, loc, appr in RUN_KEYS:
        try:
            with winreg.OpenKey(hive, key) as k:
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    items.append((name, str(val), loc, _approved(hive, appr, name)))
                    i += 1
        except OSError:
            pass
    folders = [(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"), "User Startup folder"),
               (os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\StartUp"), "All-users Startup folder")]
    for folder, loc in folders:
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.lower() != "desktop.ini":
                    hive = winreg.HKEY_CURRENT_USER if loc.startswith("User") else winreg.HKEY_LOCAL_MACHINE
                    st = _approved(hive, r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder", f)
                    items.append((f, os.path.join(folder, f), loc, st))
    return items


class StartupPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 12)
        lay.addWidget(page_header("Startup", "Programs that launch when you sign in. Fewer startup apps = faster boot "
                                             "and more free RAM. Read-only here; use the buttons to change them safely."))
        row = QHBoxLayout()
        for text, fn in (("Refresh", self.load),
                         ("Open Task Manager → Startup", lambda: subprocess.Popen(["taskmgr", "/0", "/startup"])),
                         ("Open Settings → Startup apps", lambda: os.startfile("ms-settings:startupapps")),
                         ("Launch Autoruns (full view)", lambda: _launch(self.settings.get("autoruns_path"))),
                         ("Open Startup folder", lambda: open_path(os.path.expandvars(
                             r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Status", "Location", "Command"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        lay.addWidget(explain("Autoruns (Sysinternals) additionally shows services, scheduled tasks, drivers, shell "
                              "extensions and more. Disable rather than delete entries so you can undo."))
        self.load()

    def load(self):
        items = read_startup()
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            for c, v in enumerate((it[0], it[3], it[2], it[1])):
                self.table.setItem(r, c, QTableWidgetItem(v))


# ============================================================== settings
class SettingsPage(QWidget):
    theme_changed = pyqtSignal(str)
    interval_changed = pyqtSignal(int)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        def build(lay):
            lay.addWidget(page_header("Settings", f"TaskForge {__version__}"))
            tg = QGroupBox("Appearance")
            tl = QHBoxLayout(tg)
            tl.addWidget(QLabel("Theme"))
            self.theme = QComboBox()
            self.theme.addItems(list(THEMES))
            self.theme.setCurrentText(settings.get("theme"))
            self.theme.currentTextChanged.connect(self._theme)
            tl.addWidget(self.theme)
            tl.addStretch()
            lay.addWidget(tg)

            bg = QGroupBox("Behaviour")
            bl = QVBoxLayout(bg)
            row = QHBoxLayout()
            row.addWidget(QLabel("Refresh interval"))
            self.interval = QSpinBox()
            self.interval.setRange(750, 10000)
            self.interval.setSingleStep(250)
            self.interval.setSuffix(" ms")
            self.interval.setValue(int(settings.get("refresh_ms")))
            self.interval.valueChanged.connect(self._interval)
            row.addWidget(self.interval)
            row.addWidget(explain("Lower = smoother graphs, slightly more CPU used by TaskForge itself."))
            row.addStretch()
            bl.addLayout(row)
            for key, text in (("minimize_to_tray", "Minimize to system tray"),
                              ("close_to_tray", "Close button hides to tray (exit from the tray menu)"),
                              ("start_minimized", "Start minimized to tray")):
                cb = QCheckBox(text)
                cb.setChecked(bool(settings.get(key)))
                cb.toggled.connect(lambda v, k=key: settings.set(k, v))
                bl.addWidget(cb)
            lay.addWidget(bg)

            pg = QGroupBox("External tools")
            pl = QGridLayout(pg)
            for r, (key, label) in enumerate((("procexp_path", "Process Explorer"), ("autoruns_path", "Autoruns"))):
                pl.addWidget(QLabel(label), r, 0)
                e = QLineEdit(settings.get(key))
                e.editingFinished.connect(lambda k=key, w=e: settings.set(k, w.text().strip()))
                pl.addWidget(e, r, 1)
                b = QPushButton("Browse…")
                b.clicked.connect(lambda _c=False, k=key, w=e: self._browse(k, w))
                pl.addWidget(b, r, 2)
            lay.addWidget(pg)

            dg = QGroupBox("Data & privacy")
            dl = QVBoxLayout(dg)
            dl.addWidget(explain(f"Settings and change backups are stored locally in {app_data_dir()}. TaskForge makes "
                                 "no network requests, needs no API keys and sends no telemetry."))
            ob = QPushButton("Open backups folder")
            ob.clicked.connect(lambda: open_path(backup_dir()))
            dl.addWidget(ob, 0, Qt.AlignmentFlag.AlignLeft)
            lay.addWidget(dg)

        page = scrolled(build)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(page)

    def _theme(self, name):
        self.settings.set("theme", name)
        self.theme_changed.emit(name)

    def _interval(self, v):
        self.settings.set("refresh_ms", v)
        self.interval_changed.emit(v)

    def _browse(self, key, edit):
        path, _ = QFileDialog.getOpenFileName(self, "Locate tool", os.path.dirname(edit.text() or "C:\\"),
                                              "Programs (*.exe)")
        if path:
            edit.setText(os.path.normpath(path))
            self.settings.set(key, edit.text())
