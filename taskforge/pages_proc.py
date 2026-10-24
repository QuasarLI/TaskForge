"""Dashboard and Processes pages."""
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QGuiApplication
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import editions, procman
from .procman import OpError
from .util import fmt_bytes
from .widgets import MetricCard, NumItem, bar, confirm, explain, page_header


class DashboardPage(QWidget):
    def __init__(self, monitor, palette):
        super().__init__()
        self.monitor = monitor
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 12)
        ident = monitor.ident
        lay.addWidget(page_header("Dashboard", f"{ident['name']}  •  {ident['cores']} cores / "
                                               f"{ident['threads']} threads  •  base {ident['base_mhz']} MHz"))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cpu = MetricCard("CPU load", palette["accent"])
        self.clk = MetricCard("Effective clock", palette["accent2"])
        self.ram = MetricCard("Physical memory in use", palette["accent"])
        self.com = MetricCard("Commit charge (RAM + pagefile)", palette["warn"])
        for i, c in enumerate((self.cpu, self.clk, self.ram, self.com)):
            grid.addWidget(c, i // 2, i % 2)
        lay.addLayout(grid)

        row = QHBoxLayout()
        cores = QGroupBox("Per-core load")
        self.core_lay = QGridLayout(cores)
        self.core_bars = []
        for i in range(ident["threads"] or 1):
            self.core_lay.addWidget(QLabel(f"CPU {i}"), i // 2, (i % 2) * 2)
            b = bar()
            self.core_bars.append(b)
            self.core_lay.addWidget(b, i // 2, (i % 2) * 2 + 1)
        row.addWidget(cores, 1)

        top = QGroupBox("Top consumers")
        tl = QVBoxLayout(top)
        self.top_cpu = QLabel()
        self.top_mem = QLabel()
        for l in (self.top_cpu, self.top_mem):
            l.setTextFormat(Qt.TextFormat.RichText)
            tl.addWidget(l)
        row.addWidget(top, 1)
        lay.addLayout(row)

        self.sysline = explain("")
        lay.addWidget(self.sysline)
        lay.addStretch()
        monitor.updated.connect(self.refresh)

    def apply_palette(self, pal):
        self.cpu.spark.set_color(pal["accent"])
        self.clk.spark.set_color(pal["accent2"])
        self.ram.spark.set_color(pal["accent"])
        self.com.spark.set_color(pal["warn"])

    def refresh(self, s):
        if not self.isVisible():
            return
        h = s["history"]
        self.cpu.value.setText(f"{s['cpu']:.0f}%")
        self.cpu.sub.setText(f"{len(s['procs'])} processes")
        self.cpu.spark.set_data(h["cpu"], 100)
        base = self.monitor.ident["base_mhz"] or 1
        self.clk.value.setText(f"{s['mhz']/1000:.2f} GHz")
        self.clk.sub.setText(f"{100*s['mhz']/base:.0f}% of base ({base} MHz) — above 100% = turbo active")
        self.clk.spark.set_data(h["mhz"], base * 1.5)
        vm = s["vm"]
        self.ram.value.setText(f"{fmt_bytes(vm.used)} / {fmt_bytes(vm.total)}")
        self.ram.sub.setText(f"{fmt_bytes(vm.available)} available  •  {vm.percent:.0f}% used")
        self.ram.spark.set_data(h["ram"], 100)
        p = s["perf"]
        if p:
            self.com.value.setText(f"{fmt_bytes(p['commit_total'])} / {fmt_bytes(p['commit_limit'])}")
            self.com.sub.setText(f"peak {fmt_bytes(p['commit_peak'])}  •  pagefile backs anything above RAM")
            self.com.spark.set_data(h["commit"], 100)
            self.sysline.setText(f"Handles {p['handles']:,}   •   Threads {p['threads']:,}   •   "
                                 f"File cache {fmt_bytes(p['system_cache'])}   •   Kernel paged "
                                 f"{fmt_bytes(p['kernel_paged'])} / non-paged {fmt_bytes(p['kernel_nonpaged'])}")
        for b, v in zip(self.core_bars, s["percore"]):
            b.setValue(int(v))
        procs = [x for x in s["procs"] if x["pid"] not in (0,)]
        tc = sorted(procs, key=lambda x: -x["cpu"])[:5]
        tm = sorted(procs, key=lambda x: -x["ws"])[:5]
        self.top_cpu.setText("<b>CPU</b><br>" + "<br>".join(f"{x['name']} — {x['cpu']:.1f}%" for x in tc))
        self.top_mem.setText("<b>Memory</b><br>" + "<br>".join(f"{x['name']} — {fmt_bytes(x['ws'])}" for x in tm))


COLS = ["Name", "PID", "CPU %", "Working set", "Private", "Threads", "Priority", "User", "Path"]


class AffinityDialog(QDialog):
    def __init__(self, parent, n, current):
        super().__init__(parent)
        self.setWindowTitle("CPU affinity")
        lay = QVBoxLayout(self)
        lay.addWidget(explain("Choose which logical CPUs this process may run on. Pinning can isolate a game or "
                              "background job, but restricting too far slows the process. Resets when it restarts."))
        grid = QGridLayout()
        self.boxes = []
        for i in range(n):
            cb = QCheckBox(f"CPU {i}")
            cb.setChecked(i in current)
            self.boxes.append(cb)
            grid.addWidget(cb, i // 4, i % 4)
        lay.addLayout(grid)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def selected(self):
        return [i for i, b in enumerate(self.boxes) if b.isChecked()]


class ProcessesPage(QWidget):
    def __init__(self, monitor, status):
        super().__init__()
        self.monitor, self.status = monitor, status
        self.rows = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 12)
        lay.addWidget(page_header("Processes", "Live process list with enhanced control. Right-click a row for "
                                               "every action. Core Windows processes are protected from kill/suspend."))
        tb = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by name, PID, user or path…")
        self.filter.textChanged.connect(self.render)
        tb.addWidget(self.filter, 1)
        self.hide_sys = QCheckBox("Hide system / other users")
        self.hide_sys.toggled.connect(self.render)
        tb.addWidget(self.hide_sys)
        self.pause = QCheckBox("Pause updates")
        tb.addWidget(self.pause)
        lay.addLayout(tb)

        actions = QHBoxLayout()
        for text, obj, fn, tip in (
            ("End task", "DangerBtn", self.kill, "TerminateProcess: immediate, unsaved data is lost."),
            ("End tree", "DangerBtn", self.kill_tree, "Kill the process and every child it started."),
            ("Suspend", "", self.suspend, "Freeze all threads (process stays in memory)."),
            ("Resume", "", self.resume, "Unfreeze a suspended process."),
            ("Trim RAM", "", self.trim, "Page out the working set. It refills as the app touches memory again."),
            ("Efficiency mode", "", self.eco, "Windows 11 EcoQoS + idle priority: runs the process on efficient "
                                              "clocks/cores to save power for background apps."),
            ("Affinity…", "", self.affinity, "Choose the CPUs this process may use."),
            ("Open location", "", self.open_loc, "Show the executable in Explorer."),
        ):
            b = QPushButton(text)
            if obj:
                b.setObjectName(obj)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            actions.addWidget(b)
        actions.addStretch()
        lay.addLayout(actions)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        for i, w in enumerate((200, 70, 70, 100, 100, 70, 100, 160)):
            self.table.setColumnWidth(i, w)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.menu)
        lay.addWidget(self.table, 1)
        monitor.updated.connect(self.on_snapshot)
        self.me = os.environ.get("USERNAME", "").lower()

    def on_snapshot(self, s):
        if self.pause.isChecked():
            return
        self.rows = s["procs"]
        if self.isVisible():
            self.render()

    def render(self):
        q = self.filter.text().lower().strip()
        rows = self.rows
        if self.hide_sys.isChecked():
            rows = [r for r in rows if r.get("user") and r["user"].lower().endswith("\\" + self.me)]
        if q:
            rows = [r for r in rows if q in r["name"].lower() or q == str(r["pid"]) or
                    q in (r.get("user") or "").lower() or q in (r.get("exe") or "").lower()]
        sel = self.selected_pid()
        t = self.table
        t.setUpdatesEnabled(False)
        t.setSortingEnabled(False)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            name = QTableWidgetItem(r["name"])
            name.setData(Qt.ItemDataRole.UserRole, r["pid"])
            name.setToolTip(r.get("exe") or "")
            t.setItem(i, 0, name)
            t.setItem(i, 1, NumItem(str(r["pid"]), r["pid"]))
            t.setItem(i, 2, NumItem(f"{r['cpu']:.1f}", r["cpu"]))
            t.setItem(i, 3, NumItem(fmt_bytes(r["ws"]), r["ws"]))
            t.setItem(i, 4, NumItem(fmt_bytes(r["private"]), r["private"]))
            t.setItem(i, 5, NumItem(str(r.get("threads") or 0), r.get("threads") or 0))
            t.setItem(i, 6, QTableWidgetItem(procman.PRIORITY_NAMES.get(r.get("nice"), "—")))
            t.setItem(i, 7, QTableWidgetItem(r.get("user") or "—"))
            t.setItem(i, 8, QTableWidgetItem(r.get("exe") or ""))
        t.setSortingEnabled(True)
        if sel is not None:
            for i in range(t.rowCount()):
                if t.item(i, 0).data(Qt.ItemDataRole.UserRole) == sel:
                    t.selectRow(i)
                    break
        t.setUpdatesEnabled(True)

    # ---------------------------------------------------------- actions
    def selected_pid(self):
        items = self.table.selectedItems()
        if not items:
            return None
        return self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _target(self):
        pid = self.selected_pid()
        if pid is None:
            QMessageBox.information(self, "TaskForge", "Select a process first.")
            return None, None
        r = next((x for x in self.rows if x["pid"] == pid), {"name": str(pid)})
        return pid, r["name"]

    def _do(self, fn, ok_msg):
        try:
            res = fn()
            self.status(ok_msg if res is None or res is True else f"{ok_msg} ({res})")
        except OpError as e:
            QMessageBox.warning(self, "TaskForge", str(e))

    def _guard(self, pid, name, action):
        reason = procman.protection_reason(pid, name)
        if reason:
            QMessageBox.warning(self, "Protected process", f"Refusing to {action} {name} (PID {pid}).\n\n{reason}.")
            return False
        return True

    def kill(self):
        pid, name = self._target()
        if pid is None or not self._guard(pid, name, "end"):
            return
        if confirm(self, "End task", f"End {name} (PID {pid}) immediately?\nUnsaved work in it will be lost.", True):
            self._do(lambda: procman.terminate(pid), f"Ended {name} ({pid})")

    def kill_tree(self):
        pid, name = self._target()
        if pid is None or not self._guard(pid, name, "end"):
            return
        if confirm(self, "End process tree", f"End {name} (PID {pid}) and ALL of its child processes?", True):
            self._do(lambda: f"{procman.terminate_tree(pid)} processes", f"Ended tree of {name}")

    def suspend(self):
        pid, name = self._target()
        if pid is None or not self._guard(pid, name, "suspend"):
            return
        if confirm(self, "Suspend", f"Freeze {name} (PID {pid})? It will look hung until resumed."):
            self._do(lambda: procman.suspend(pid), f"Suspended {name}")

    def resume(self):
        pid, name = self._target()
        if pid is not None:
            self._do(lambda: procman.resume(pid), f"Resumed {name}")

    def trim(self):
        pid, name = self._target()
        if pid is None:
            return
        ok = procman.trim_working_set(pid)
        if ok:
            self.status(f"Trimmed working set of {name}")
        else:
            QMessageBox.warning(self, "TaskForge", f"Could not trim {name}: access denied (try running as admin).")

    def eco(self):
        pid, name = self._target()
        if pid is None or not self._guard(pid, name, "throttle"):
            return
        box = QMessageBox(self)
        box.setWindowTitle("Efficiency mode")
        box.setText(f"Efficiency mode for {name}:\nOn = EcoQoS + idle priority (saves power, runs slower).\n"
                    "Off = normal scheduling.")
        on = box.addButton("Turn on", QMessageBox.ButtonRole.AcceptRole)
        off = box.addButton("Turn off", QMessageBox.ButtonRole.RejectRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() in (on, off):
            en = box.clickedButton() is on
            self._do(lambda: procman.set_efficiency_mode(pid, en), f"Efficiency mode {'on' if en else 'off'}: {name}")

    def set_priority(self, cls, label):
        if not editions.can("pro"):
            QMessageBox.information(self, "Pro feature",
                                    "Priority controls are a Pro feature. Efficiency mode and core process safety "
                                    "remain available in every edition.")
            return
        pid, name = self._target()
        if pid is None:
            return
        if label in ("Realtime", "High") and not confirm(
                self, "Priority", f"{label} priority can starve input, audio and drivers if {name} spins the CPU. "
                                  "Continue?", True):
            return
        self._do(lambda: procman.set_priority(pid, cls), f"{name} priority → {label}")

    def affinity(self):
        pid, name = self._target()
        if pid is None:
            return
        try:
            cur = procman.get_affinity(pid)
        except OpError as e:
            QMessageBox.warning(self, "TaskForge", str(e))
            return
        dlg = AffinityDialog(self, self.monitor.ident["threads"], cur)
        if dlg.exec() and dlg.selected():
            self._do(lambda: procman.set_affinity(pid, dlg.selected()), f"{name} affinity → {dlg.selected()}")

    def open_loc(self):
        pid = self.selected_pid()
        r = next((x for x in self.rows if x["pid"] == pid), None)
        if r and r.get("exe"):
            subprocess.Popen(["explorer", "/select,", r["exe"]])
        else:
            QMessageBox.information(self, "TaskForge", "Path unavailable (protected or system process).")

    def menu(self, pos):
        if self.selected_pid() is None:
            return
        m = QMenu(self)
        for text, fn in (("End task", self.kill), ("End process tree", self.kill_tree), (None, None),
                         ("Suspend", self.suspend), ("Resume", self.resume), ("Trim working set", self.trim),
                         ("Efficiency mode…", self.eco), ("Affinity…", self.affinity), (None, None),
                         ("Open file location", self.open_loc), ("Copy path", self.copy_path),
                         ("Search online", self.search)):
            if text is None:
                m.addSeparator()
            else:
                m.addAction(text, fn)
        pm = m.addMenu("Set priority")
        for label, cls in procman.PRIORITIES:
            act = QAction(label, pm)
            act.triggered.connect(lambda _c=False, c=cls, l=label: self.set_priority(c, l))
            pm.addAction(act)
        m.exec(self.table.viewport().mapToGlobal(pos))

    def copy_path(self):
        pid = self.selected_pid()
        r = next((x for x in self.rows if x["pid"] == pid), None)
        if r:
            QGuiApplication.clipboard().setText(r.get("exe") or r["name"])

    def search(self):
        import webbrowser
        _, name = self._target()
        if name:
            webbrowser.open(f"https://www.bing.com/search?q={name}+process")
