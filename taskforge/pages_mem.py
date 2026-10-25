"""Memory page: RAM breakdown, per-app consumers, working-set trimming and paging-file helper."""
import os
import string
import subprocess
from collections import defaultdict

import psutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSpinBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import editions, pagefile, procman
from .procman import OpError
from .util import fmt_bytes, is_admin
from .widgets import NumItem, bar, confirm, explain, page_header, run_async


class MemoryPage(QWidget):
    def __init__(self, monitor, status):
        super().__init__()
        self.monitor, self.status = monitor, status
        self.groups = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(22, 18, 22, 12)
        lay.addWidget(page_header("Memory", "Where your RAM is going, who is using it, and how the paging file "
                                            "backs it up. All numbers are live from Windows."))

        # -------- breakdown
        bd = QGroupBox("Physical memory")
        g = QGridLayout(bd)
        self.lbl = {}
        fields = [("used", "In use"), ("avail", "Available"), ("cache", "File cache (standby/modified)"),
                  ("commit", "Committed"), ("paged", "Paged pool"), ("nonpaged", "Non-paged pool")]
        for i, (k, t) in enumerate(fields):
            cap = QLabel(t)
            cap.setObjectName("Muted")
            v = QLabel("-")
            v.setObjectName("Value")
            self.lbl[k] = v
            g.addWidget(cap, i // 3 * 2, i % 3)
            g.addWidget(v, i // 3 * 2 + 1, i % 3)
        self.ram_bar = bar()
        g.addWidget(self.ram_bar, 4, 0, 1, 3)
        g.addWidget(explain("“Available” already includes cached memory that Windows hands back instantly, so "
                            "a large cache is healthy, not wasted RAM. Committed memory is what programs have "
                            "reserved; it must fit in RAM + pagefile (the commit limit) or apps fail to allocate."),
                    5, 0, 1, 3)
        lay.addWidget(bd)

        # -------- consumers
        cg = QGroupBox("What's using RAM (grouped by application)")
        cl = QVBoxLayout(cg)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Application", "Instances", "Working set", "Private (commit)", "% of RAM"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(260)
        cl.addWidget(self.table)
        btns = QHBoxLayout()
        b_kill = QPushButton("End all instances")
        b_kill.setObjectName("DangerBtn")
        b_kill.clicked.connect(self.kill_group)
        b_trim = QPushButton("Trim selected app")
        b_trim.clicked.connect(self.trim_group)
        b_all = QPushButton("Trim all background apps…")
        b_all.clicked.connect(self.trim_all)
        for b in (b_kill, b_trim, b_all):
            btns.addWidget(b)
        btns.addStretch()
        cl.addLayout(btns)
        cl.addWidget(explain("Trimming asks Windows to move a process's pages to the standby list. It instantly "
                             "raises “free” RAM, but the app faults the pages back when it next needs them, so it "
                             "is NOT a guaranteed speed-up. It is most useful to reclaim memory from idle "
                             "background apps before launching something big. Ending an app frees its memory for "
                             "real but loses unsaved work."))
        lay.addWidget(cg)

        # -------- pagefile
        pg = QGroupBox("Paging file (virtual memory) helper")
        pl = QVBoxLayout(pg)
        self.pf_current = QLabel("-")
        self.pf_current.setTextFormat(Qt.TextFormat.RichText)
        self.pf_current.setWordWrap(True)
        pl.addWidget(self.pf_current)
        self.pf_reco = QLabel("-")
        self.pf_reco.setObjectName("Value")
        self.pf_reco.setWordWrap(True)
        pl.addWidget(self.pf_reco)

        modes = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.r_auto = QRadioButton("Windows managed (all drives)")
        self.r_sys = QRadioButton("System managed on drive")
        self.r_custom = QRadioButton("Custom size")
        for i, r in enumerate((self.r_auto, self.r_sys, self.r_custom)):
            self.mode_group.addButton(r, i)
            modes.addWidget(r)
        modes.addStretch()
        pl.addLayout(modes)

        form = QHBoxLayout()
        form.addWidget(QLabel("Drive"))
        self.drive = QComboBox()
        for d in string.ascii_uppercase:
            if os.path.exists(f"{d}:\\"):
                try:
                    free = psutil.disk_usage(f"{d}:\\").free
                    self.drive.addItem(f"{d}:  ({fmt_bytes(free)} free)", d)
                except OSError:
                    pass
        form.addWidget(self.drive)
        form.addWidget(QLabel("Initial MB"))
        self.init_mb = QSpinBox()
        self.init_mb.setRange(16, 262144)
        self.init_mb.setSingleStep(256)
        form.addWidget(self.init_mb)
        form.addWidget(QLabel("Maximum MB"))
        self.max_mb = QSpinBox()
        self.max_mb.setRange(16, 524288)
        self.max_mb.setSingleStep(256)
        form.addWidget(self.max_mb)
        use_reco = QPushButton("Use recommendation")
        use_reco.clicked.connect(self.use_reco)
        form.addWidget(use_reco)
        form.addStretch()
        pl.addLayout(form)

        act = QHBoxLayout()
        self.apply_btn = QPushButton("Apply pagefile settings (admin, reboot)")
        self.apply_btn.setObjectName("AccentBtn")
        self.apply_btn.clicked.connect(self.apply_pagefile)
        restore = QPushButton("Restore previous pagefile")
        restore.clicked.connect(self.restore_pagefile)
        native = QPushButton("Open Windows Virtual Memory dialog")
        native.clicked.connect(lambda: subprocess.Popen(["SystemPropertiesPerformance.exe"]))
        for b in (self.apply_btn, restore, native):
            act.addWidget(b)
        act.addStretch()
        pl.addLayout(act)
        pl.addWidget(explain(
            "Tips: keep a pagefile even with lots of RAM — Windows and many apps expect one, and crash dumps need it. "
            "Put it on your fastest SSD/NVMe drive (not a USB or spinning disk). A fixed size (initial = maximum) "
            "avoids growth fragmentation but can cause out-of-memory errors if set too small; “System managed” is the "
            "safest choice for most people. The recommendation is based on this session's peak commit. "
            "Changes are written to HKLM\\…\\Memory Management\\PagingFiles exactly like the Windows dialog, the old "
            "value is backed up first, and they take effect after a restart. Windows does not expose "
            "a pagefile priority or speed setting; it chooses paging behavior. Multiple pagefiles "
            "do not guarantee faster paging. Faster paging ultimately means a faster drive or more "
            "RAM — software cannot make the disk itself quicker. Keep enough free space for crash "
            "dump requirements if you rely on kernel or complete dumps."))
        lay.addWidget(pg)
        lay.addStretch()

        self.load_pagefile()
        monitor.updated.connect(self.refresh)

    # ------------------------------------------------------------- live data
    def refresh(self, s):
        if not self.isVisible():
            return
        vm, p = s["vm"], s["perf"]
        self.lbl["used"].setText(f"{fmt_bytes(vm.used)}  ({vm.percent:.0f}%)")
        self.lbl["avail"].setText(fmt_bytes(vm.available))
        self.ram_bar.setValue(int(vm.percent))
        if p:
            self.lbl["cache"].setText(fmt_bytes(p["system_cache"]))
            self.lbl["commit"].setText(f"{fmt_bytes(p['commit_total'])} / {fmt_bytes(p['commit_limit'])}")
            self.lbl["paged"].setText(fmt_bytes(p["kernel_paged"]))
            self.lbl["nonpaged"].setText(fmt_bytes(p["kernel_nonpaged"]))
            if not getattr(self, "_reco", None):
                self._reco = pagefile.recommend(p["phys_total"], p["commit_peak"])
                self.pf_reco.setText(f"Recommendation for this PC: initial {self._reco[0]:,} MB, maximum "
                                     f"{self._reco[1]:,} MB (peak commit {fmt_bytes(p['commit_peak'])}, RAM "
                                     f"{fmt_bytes(p['phys_total'])}).")
        groups = defaultdict(lambda: {"pids": [], "ws": 0, "private": 0})
        for r in s["procs"]:
            if r["pid"] in (0, 4):
                continue
            g = groups[r["name"]]
            g["pids"].append(r["pid"])
            g["ws"] += r["ws"]
            g["private"] += r["private"]
        self.groups = groups
        top = sorted(groups.items(), key=lambda kv: -kv[1]["ws"])[:40]
        sel = self.selected_name()
        t = self.table
        t.setUpdatesEnabled(False)
        t.setSortingEnabled(False)
        t.setRowCount(len(top))
        for i, (name, g) in enumerate(top):
            t.setItem(i, 0, QTableWidgetItem(name))
            t.setItem(i, 1, NumItem(str(len(g["pids"])), len(g["pids"])))
            t.setItem(i, 2, NumItem(fmt_bytes(g["ws"]), g["ws"]))
            t.setItem(i, 3, NumItem(fmt_bytes(g["private"]), g["private"]))
            pct = 100 * g["ws"] / vm.total
            t.setItem(i, 4, NumItem(f"{pct:.1f}%", pct))
            if name == sel:
                t.selectRow(i)
        t.setSortingEnabled(True)
        t.setUpdatesEnabled(True)

    def set_inventory(self, inv):
        self.inventory = inv
        self.load_pagefile()

    def selected_name(self):
        items = self.table.selectedItems()
        return self.table.item(items[0].row(), 0).text() if items else None

    # ------------------------------------------------------------- actions
    def kill_group(self):
        name = self.selected_name()
        if not name:
            return
        pids = list(self.groups.get(name, {}).get("pids", []))
        reason = next((procman.protection_reason(p, name) for p in pids if procman.protection_reason(p, name)), "")
        if reason:
            QMessageBox.warning(self, "Protected", f"Refusing to end {name}: {reason}.")
            return
        if not confirm(self, "End all instances", f"End all {len(pids)} instance(s) of {name}? Unsaved work is lost.",
                       True):
            return
        errors = []
        for pid in pids:
            try:
                procman.terminate(pid)
            except OpError as e:
                errors.append(str(e))
        self.status(f"Ended {len(pids) - len(errors)}/{len(pids)} instances of {name}")
        if errors:
            QMessageBox.warning(self, "Some processes could not be ended", "\n".join(errors[:8]))

    def trim_group(self):
        name = self.selected_name()
        if not name:
            return
        pids = self.groups.get(name, {}).get("pids", [])
        if len(pids) > 1 and not editions.can("advanced"):
            QMessageBox.information(self, "Advanced feature",
                                    "Trimming multiple app instances requires Free with Ads, Supporter, or Pro.")
            return
        if not confirm(self, "Trim app working sets",
                       f"Ask Windows to trim {len(pids)} instance(s) of {name}? Data may be paged back in "
                       "when those apps are used, which can temporarily slow them down."):
            return
        run_async(self, procman.trim_process_batch, pids,
                  on_done=lambda results: self._trim_results(results, name))

    def trim_all(self):
        if not editions.can("advanced"):
            QMessageBox.information(self, "Edition feature",
                                    "Bulk background trimming requires Free with Ads or Supporter/Pro.")
            return
        if not confirm(self, "Trim background apps",
                       "Request a working-set trim for every accessible process except TaskForge? Windows-critical "
                       "processes are explicitly excluded.\n\nThis can reclaim resident memory temporarily, but "
                       "applications may page data back in when used and run slower. It is not a permanent speed boost."):
            return
        before = psutil.virtual_memory().available
        pids = [p.pid for p in psutil.process_iter(["pid"]) if p.pid not in (0, 4, os.getpid())]
        self.status(f"Requesting working-set trims for {len(pids)} processes…")
        run_async(self, procman.trim_process_batch, pids,
                  on_done=lambda results: self._trim_results(results, "background processes", before))

    def _trim_results(self, results, label, available_before=None):
        succeeded = [r for r in results if "error" not in r]
        failures = [r for r in results if "error" in r]
        reclaimed = sum(r["reclaimed"] for r in succeeded)
        detail = (f"Trimmed {len(succeeded)}/{len(results)} {label}; measured decrease in resident "
                  f"working sets: {fmt_bytes(reclaimed)}.")
        if available_before is not None:
            detail += (f"\nAvailable physical memory: {fmt_bytes(available_before)} → "
                       f"{fmt_bytes(psutil.virtual_memory().available)}. This system-wide change is not "
                       "necessarily attributable only to these trim requests.")
        if failures:
            detail += "\n\nSome processes were protected or inaccessible:\n" + "\n".join(
                f"PID {r['pid']} {r['name']}: {r['error']}" for r in failures[:20])
            if len(failures) > 20:
                detail += f"\n…and {len(failures) - 20} additional process(es) could not be trimmed."
        self.status(detail.splitlines()[0])
        QMessageBox.information(self, "Working-set trim results", detail)

    # ------------------------------------------------------------- pagefile
    def load_pagefile(self):
        try:
            entries = pagefile.read_config()
        except OSError as e:
            self.pf_current.setText(f"Could not read pagefile config: {e}")
            return
        usage = {(u.get("Name") or "").lower(): u for u in getattr(self, "inventory", {}).get("pagefiles", [])}
        volumes = {str(v.get("Drive") or "").upper(): v
                   for v in getattr(self, "inventory", {}).get("volumes", [])}
        parts = []
        for e in entries:
            u = usage.get(e["path"].lower())
            use = f" — in use {u['CurrentUsage']} MB of {u['AllocatedBaseSize']} MB (peak {u['PeakUsage']} MB)" if u else ""
            volume = volumes.get(e["path"][:1].upper(), {})
            media = ", ".join(f"{label}: {volume[field]}" for field, label in (
                ("MediaType", "media"), ("BusType", "bus"), ("HealthStatus", "health")
            ) if volume.get(field))
            media_text = f" — volume {media}" if media else ""
            desc = {"auto": "Windows managed (automatic)", "system": "system managed size",
                    "custom": f"custom {e['initial_mb']:,}–{e['max_mb']:,} MB"}[e["mode"]]
            parts.append(f"<b>{e['path']}</b>: {desc}{use}{media_text}")
        self.pf_current.setText("Current configuration: " + ("<br>".join(parts) if parts else "<b>No pagefile</b> "
                                "(not recommended)") + ("<br>Clear pagefile at shutdown: <b>on</b> (secure but slows "
                                "shutdown)" if pagefile.read_clear_at_shutdown() else ""))
        if entries:
            e = entries[0]
            {"auto": self.r_auto, "system": self.r_sys, "custom": self.r_custom}[e["mode"]].setChecked(True)
            d = e["path"][0].upper()
            idx = self.drive.findData(d)
            if idx >= 0:
                self.drive.setCurrentIndex(idx)
            if e["mode"] == "custom":
                self.init_mb.setValue(e["initial_mb"])
                self.max_mb.setValue(e["max_mb"])
        else:
            self.r_auto.setChecked(True)

    def use_reco(self):
        reco = getattr(self, "_reco", None)
        if reco:
            self.r_custom.setChecked(True)
            self.init_mb.setValue(reco[0])
            self.max_mb.setValue(reco[1])

    def apply_pagefile(self):
        if not editions.can("advanced"):
            QMessageBox.information(self, "Edition feature",
                                    "Custom pagefile changes require Free with Ads or Supporter/Pro. "
                                    "Monitoring, recommendations, Windows' dialog, backups, and restore remain free.")
            return
        if not is_admin():
            QMessageBox.warning(self, "Administrator required",
                                "Changing the pagefile requires administrator rights. Use “Restart as admin” in the header.")
            return
        mode = ("auto", "system", "custom")[self.mode_group.checkedId()]
        drive = self.drive.currentData()
        if mode == "custom" and self.max_mb.value() < self.init_mb.value():
            QMessageBox.warning(self, "TaskForge", "Maximum size must be ≥ initial size.")
            return
        try:
            if mode != "auto":
                pagefile.validate_fixed_local_drive(drive)
            line = pagefile.build_line(mode, drive, self.init_mb.value(), self.max_mb.value())
        except ValueError as e:
            QMessageBox.warning(self, "Unsupported pagefile target", str(e))
            return
        if not confirm(self, "Apply pagefile", f"Set PagingFiles to:\n\n    {line}\n\nThe current value is backed up "
                                               "first. Takes effect after you restart Windows. Continue?"):
            return
        try:
            bpath = pagefile.apply([line])
        except OSError as e:
            QMessageBox.critical(self, "TaskForge", f"Failed to write pagefile config: {e}")
            return
        self.load_pagefile()
        QMessageBox.information(self, "Pagefile updated", f"Saved. Restart Windows to apply.\nBackup: {bpath}")

    def restore_pagefile(self):
        path = pagefile.latest_backup()
        if not path:
            QMessageBox.information(self, "TaskForge", "No pagefile backup found (none has been changed by TaskForge).")
            return
        if not is_admin():
            QMessageBox.warning(self, "Administrator required", "Restoring requires administrator rights.")
            return
        if confirm(self, "Restore pagefile", f"Restore pagefile settings from\n{path}?"):
            try:
                lines = pagefile.restore(path)
                self.load_pagefile()
                QMessageBox.information(self, "Restored", f"Restored: {lines}\nRestart Windows to apply.")
            except OSError as e:
                QMessageBox.critical(self, "TaskForge", str(e))
