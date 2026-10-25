"""Dashboard and Processes pages."""
import html
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QGuiApplication
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
                             QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import editions, procman
from .procman import OpError
from .util import fmt_bytes
from .virustotal import VirusTotalClient, VirusTotalError
from .widgets import MetricCard, NumItem, Sparkline, bar, confirm, explain, page_header, run_async


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
        self.summary = explain("")
        lay.addWidget(self.summary)
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
        uptime = s["uptime_seconds"]
        days, hours = divmod(uptime // 3600, 24)
        minutes = (uptime // 60) % 60
        disk = s["system_disk"]
        self.summary.setText(
            f"Uptime {days}d {hours}h {minutes}m  •  System drive free "
            f"{fmt_bytes(disk.free)} of {fmt_bytes(disk.total)}  •  {len(s['procs'])} live processes")
        for b, v in zip(self.core_bars, s["percore"]):
            b.setValue(int(v))
        procs = [x for x in s["procs"] if x["pid"] not in (0,)]
        tc = sorted(procs, key=lambda x: -x["cpu"])[:5]
        tm = sorted(procs, key=lambda x: -x["ws"])[:5]
        self.top_cpu.setText("<b>CPU</b><br>" + "<br>".join(f"{x['name']} — {x['cpu']:.1f}%" for x in tc))
        self.top_mem.setText("<b>Memory</b><br>" + "<br>".join(f"{x['name']} — {fmt_bytes(x['ws'])}" for x in tm))


COLS = ["Name", "PID", "Parent", "CPU %", "Working set", "Private commit",
        "Threads", "Handles", "User", "Path"]


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
        self._rendering = False
        self._details_pid = None
        self._visible_order = []
        self._sort_col = 4
        self._sort_descending = True
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 12)
        self.vt = VirusTotalClient()
        lay.addWidget(page_header("Processes", "Inspect live CPU and memory use, select a process for details, or "
                                               "right-click for controls. System-process protections remain active."))
        tb = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by name, PID, user or path…")
        self.filter.textChanged.connect(lambda: self.render(preserve_order=False))
        tb.addWidget(self.filter, 1)
        self.hide_sys = QCheckBox("Hide system / other users")
        self.hide_sys.toggled.connect(lambda: self.render(preserve_order=False))
        tb.addWidget(self.hide_sys)
        self.pause = QCheckBox("Pause updates")
        tb.addWidget(self.pause)
        lay.addLayout(tb)

        actions = QHBoxLayout()
        for text, obj, fn, tip in (
            ("End task", "DangerBtn", self.kill, "Ends immediately; unsaved work may be lost."),
            ("Trim selected", "", self.trim, "Requests Windows to trim selected working sets; memory may refill."),
            ("Open location", "", self.open_loc, "Show the selected executable in Explorer."),
        ):
            b = QPushButton(text)
            if obj:
                b.setObjectName(obj)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            actions.addWidget(b)
        actions.addStretch()
        lay.addLayout(actions)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        hh.setSortIndicatorShown(True)
        hh.setSortIndicator(self._sort_col, Qt.SortOrder.DescendingOrder)
        hh.sectionClicked.connect(self._sort_by_column)
        for i, w in enumerate((175, 60, 65, 65, 100, 105, 65, 70, 135, 130)):
            self.table.setColumnWidth(i, w)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.menu)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        split.addWidget(self.table)
        inspect = QGroupBox("Process inspector")
        il = QVBoxLayout(inspect)
        self.inspector = QLabel("Select a process to inspect its metadata and recent resource history.")
        self.inspector.setWordWrap(True)
        self.inspector.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        il.addWidget(self.inspector)
        self.cpu_graph = Sparkline()
        self.mem_graph = Sparkline()
        self.cpu_graph.setMinimumHeight(36)
        self.mem_graph.setMinimumHeight(36)
        il.addWidget(QLabel("CPU history (last 60 samples)"))
        il.addWidget(self.cpu_graph)
        il.addWidget(QLabel("Working-set history (last 60 samples)"))
        il.addWidget(self.mem_graph)
        self.details_button = QPushButton("Refresh process details")
        self.details_button.clicked.connect(lambda: self.selection_changed(force=True))
        il.addWidget(self.details_button)
        self.copy_details_button = QPushButton("Copy process details")
        self.copy_details_button.clicked.connect(self.copy_details)
        il.addWidget(self.copy_details_button)
        self.analyze_button = QPushButton("Analyze executable / VirusTotal")
        self.analyze_button.setToolTip("Computes a local SHA-256 and signature status. VirusTotal lookup is an "
                                       "explicit hash-only request; the executable is never uploaded.")
        self.analyze_button.clicked.connect(self.analyze_selected)
        il.addWidget(self.analyze_button)
        self.vt_key_button = QPushButton("Set VirusTotal API key…")
        self.vt_key_button.clicked.connect(self.set_vt_key)
        il.addWidget(self.vt_key_button)
        self.vt_remove_button = QPushButton("Remove saved VirusTotal key")
        self.vt_remove_button.clicked.connect(self.remove_vt_key)
        il.addWidget(self.vt_remove_button)
        il.addStretch()
        split.addWidget(inspect)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        lay.addWidget(split, 1)
        monitor.updated.connect(self.on_snapshot)
        self.me = os.environ.get("USERNAME", "").lower()

    def on_snapshot(self, s):
        if self.pause.isChecked():
            return
        self.rows = s["procs"]
        if self.isVisible():
            self.render(preserve_order=True)

    def _sort_key(self, row, column):
        return {
            0: lambda: row["name"].casefold(),
            1: lambda: row["pid"],
            2: lambda: row.get("ppid", 0),
            3: lambda: row["cpu"],
            4: lambda: row["ws"],
            5: lambda: row["private"],
            6: lambda: row.get("threads") or 0,
            7: lambda: row.get("handles") or 0,
            8: lambda: (row.get("user") or "").casefold(),
            9: lambda: (row.get("exe") or "").casefold(),
        }[column]()

    def _sort_by_column(self, column):
        if column == self._sort_col:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_col = column
            self._sort_descending = column in (3, 4, 5, 6, 7)
        order = Qt.SortOrder.DescendingOrder if self._sort_descending else Qt.SortOrder.AscendingOrder
        self.table.horizontalHeader().setSortIndicator(column, order)
        self.render(preserve_order=False)

    def render(self, preserve_order=False):
        q = self.filter.text().lower().strip()
        rows = self.rows
        if self.hide_sys.isChecked():
            rows = [r for r in rows if r.get("user") and r["user"].lower().endswith("\\" + self.me)]
        if q:
            rows = [r for r in rows if q in r["name"].lower() or q == str(r["pid"]) or
                    q == str(r.get("ppid", "")) or q in (r.get("user") or "").lower() or
                    q in (r.get("exe") or "").lower()]
        by_pid = {r["pid"]: r for r in rows}
        if preserve_order:
            ordered_pids = procman.preserve_process_order(
                self._visible_order, by_pid, lambda row: self._sort_key(row, self._sort_col),
                reverse=self._sort_descending)
        else:
            ordered_pids = sorted(by_pid, key=lambda pid: self._sort_key(by_pid[pid], self._sort_col),
                                  reverse=self._sort_descending)
        rows = [by_pid[pid] for pid in ordered_pids]
        selected = set(self.selected_pids())
        t = self.table
        self._rendering = True
        t.setUpdatesEnabled(False)
        old_order = [t.item(i, 0).data(Qt.ItemDataRole.UserRole) for i in range(t.rowCount())]
        scroll_value = t.verticalScrollBar().value()
        if old_order == ordered_pids:
            for i, r in enumerate(rows):
                cells = (
                    r["name"], str(r["pid"]), str(r.get("ppid", 0)), f"{r['cpu']:.1f}",
                    fmt_bytes(r["ws"]), fmt_bytes(r["private"]), str(r.get("threads") or 0),
                    str(r.get("handles") or 0), r.get("user") or "—", r.get("exe") or "",
                )
                keys = (None, r["pid"], r.get("ppid", 0), r["cpu"], r["ws"], r["private"],
                        r.get("threads") or 0, r.get("handles") or 0, None, None)
                for col, (text, key) in enumerate(zip(cells, keys)):
                    item = t.item(i, col)
                    item.setText(text)
                    if key is not None:
                        item.key = key
                t.item(i, 0).setToolTip(r.get("exe") or "")
        else:
            t.setRowCount(len(rows))
            for i, r in enumerate(rows):
                name = QTableWidgetItem(r["name"])
                name.setData(Qt.ItemDataRole.UserRole, r["pid"])
                name.setToolTip(r.get("exe") or "")
                t.setItem(i, 0, name)
                t.setItem(i, 1, NumItem(str(r["pid"]), r["pid"]))
                t.setItem(i, 2, NumItem(str(r.get("ppid", 0)), r.get("ppid", 0)))
                t.setItem(i, 3, NumItem(f"{r['cpu']:.1f}", r["cpu"]))
                t.setItem(i, 4, NumItem(fmt_bytes(r["ws"]), r["ws"]))
                t.setItem(i, 5, NumItem(fmt_bytes(r["private"]), r["private"]))
                t.setItem(i, 6, NumItem(str(r.get("threads") or 0), r.get("threads") or 0))
                t.setItem(i, 7, NumItem(str(r.get("handles") or 0), r.get("handles") or 0))
                t.setItem(i, 8, QTableWidgetItem(r.get("user") or "—"))
                t.setItem(i, 9, QTableWidgetItem(r.get("exe") or ""))
            t.verticalScrollBar().setValue(scroll_value)
        self._visible_order = ordered_pids
        for i in range(t.rowCount()):
            if t.item(i, 0).data(Qt.ItemDataRole.UserRole) in selected:
                t.selectRow(i)
        t.setUpdatesEnabled(True)
        self._rendering = False
        self.selection_changed()

    # ---------------------------------------------------------- actions
    def selected_pid(self):
        items = self.table.selectedItems()
        if not items:
            return None
        return self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def selected_pids(self):
        return list(dict.fromkeys(
            self.table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
            for index in self.table.selectionModel().selectedRows()))

    def selection_changed(self, *_args, force=False):
        if self._rendering:
            return
        pids = self.selected_pids()
        pid = pids[0] if pids else None
        if pid is None:
            self._details_pid = None
            self.inspector.setText("Select a process to inspect its metadata and recent resource history.")
            self.cpu_graph.set_data([], 100)
            self.mem_graph.set_data([], 1)
            return
        row = next((item for item in self.rows if item["pid"] == pid), None)
        if row:
            history = row.get("history", {})
            self.cpu_graph.set_data(history.get("cpu", []), 100)
            mem = history.get("memory", [])
            self.mem_graph.set_data(mem, max(mem, default=1))
            compare_rows = [item for item in self.rows if item["pid"] in pids]
            total_cpu = sum(item["cpu"] for item in compare_rows)
            total_memory = sum(item["ws"] for item in compare_rows)
            self.inspector.setText(
                f"<b>{html.escape(row['name'])} (PID {pid})</b><br>"
                f"CPU {row['cpu']:.1f}% &nbsp; Working set {fmt_bytes(row['ws'])}<br>"
                f"Private memory {fmt_bytes(row['private'])} &nbsp; Threads {row.get('threads') or 0}<br>"
                f"Selected total: {total_cpu:.1f}% CPU &nbsp; {fmt_bytes(total_memory)} working set "
                f"across {len(compare_rows)} process(es).")
        if self._details_pid == pid and not force:
            return
        self._details_pid = pid
        run_async(self, procman.process_details, pid,
                  on_done=lambda result, selected=pid: self._details_ready(selected, result))

    def _details_ready(self, pid, details):
        if pid != self.selected_pid():
            return
        self._process_details = details
        row = next((item for item in self.rows if item["pid"] == pid), {})
        history = row.get("history", {})
        memory = history.get("memory", [])
        self.cpu_graph.set_data(history.get("cpu", []), 100)
        self.mem_graph.set_data(memory, max(memory, default=1))
        parent = details.get("parent")
        parent_text = (f"{html.escape(parent['name'])} (PID {parent['pid']})"
                       if parent else "Unavailable or no parent")
        handles = details.get("handles")
        self.inspector.setText(
            f"<b>{html.escape(details['name'])} (PID {pid})</b><br>"
            f"Status: {html.escape(details['status'])} &nbsp; "
            f"Architecture: {html.escape(details.get('architecture', 'Unavailable'))}<br>"
            f"User: {html.escape(details['user'])}<br>Started: {html.escape(details['started'])}<br>"
            f"Parent: {parent_text}<br>Threads: {details['threads'] or 'Unavailable'} &nbsp; "
            f"Handles: {handles if handles is not None else 'Unavailable'}<br>"
            f"Working set: {fmt_bytes(details['working_set'])} &nbsp; "
            f"Private: {fmt_bytes(details['private']) if details['private'] is not None else 'Unavailable'}<br>"
            f"Path: {html.escape(details['path'] or 'Unavailable')}<br>"
            f"Command line: {html.escape(details['command_line'])}")

    def copy_details(self):
        details = getattr(self, "_process_details", None)
        if details and details.get("pid") == self.selected_pid():
            QGuiApplication.clipboard().setText("\n".join(
                f"{key}: {value}" for key, value in details.items()))
            self.status("Process details copied to clipboard.")
        else:
            QMessageBox.information(self, "TaskForge", "Select a process and wait for its details to load.")

    def set_vt_key(self):
        from PyQt6.QtWidgets import QInputDialog
        key, accepted = QInputDialog.getText(
            self, "VirusTotal API key", "TaskForge stores this key using Windows DPAPI. It is never logged. "
                                       "The key is sent only to VirusTotal when you explicitly request a lookup.",
            QLineEdit.EchoMode.Password)
        if accepted and key.strip():
            run_async(self, self.vt.verify_key, key,
                      on_done=lambda _result: QMessageBox.information(
                          self, "VirusTotal", "API key verified and saved with Windows DPAPI."))

    def remove_vt_key(self):
        self.vt.store.clear()
        self.vt.cache.clear()
        self.status("Saved VirusTotal key removed.")

    def analyze_selected(self):
        details = getattr(self, "_process_details", None)
        if not details or details.get("pid") != self.selected_pid():
            QMessageBox.information(self, "TaskForge", "Select a process and wait for its details to load.")
            return
        path = details.get("path")
        if not path:
            QMessageBox.warning(self, "TaskForge", "Windows did not provide an executable path for this process.")
            return
        self.analyze_button.setEnabled(False)
        run_async(self, procman.analyze_executable, path,
                  on_done=lambda result: self._analysis_ready(result),
                  on_fail=lambda message: self._analysis_failed(message))

    def _analysis_failed(self, message):
        self.analyze_button.setEnabled(True)
        QMessageBox.warning(self, "TaskForge", message)

    def _analysis_ready(self, result):
        self.analyze_button.setEnabled(True)
        signals = "\n".join(f"• {signal}" for signal in result["signals"])
        answer = QMessageBox(self)
        answer.setWindowTitle("Local executable analysis")
        answer.setTextFormat(Qt.TextFormat.PlainText)
        answer.setText(f"SHA-256: {result['sha256']}\nSignature: {result['signature_status']}\n"
                       f"Publisher: {result['publisher']}\n\nContext signals (not a malware verdict):\n{signals}")
        lookup = answer.addButton("Look up hash on VirusTotal…", QMessageBox.ButtonRole.AcceptRole)
        browser = answer.addButton("Search hash in browser…", QMessageBox.ButtonRole.ActionRole)
        copy = answer.addButton("Copy SHA-256", QMessageBox.ButtonRole.ActionRole)
        answer.addButton(QMessageBox.StandardButton.Close)
        answer.exec()
        if answer.clickedButton() is copy:
            QGuiApplication.clipboard().setText(result["sha256"])
            return
        if answer.clickedButton() is browser:
            import webbrowser
            webbrowser.open("https://www.virustotal.com/gui/search?query=" + result["sha256"])
            return
        if answer.clickedButton() is not lookup:
            return
        try:
            key = self.vt.store.load()
        except VirusTotalError as exc:
            QMessageBox.warning(self, "VirusTotal", str(exc))
            return
        if not key:
            QMessageBox.information(
                self, "VirusTotal",
                "No key is configured. You can copy the hash or set a key to request a report. "
                "A public browser search is also available from the process context menu.")
            return
        if not confirm(self, "VirusTotal privacy notice",
                       "Send this SHA-256 hash to VirusTotal for a report lookup? The executable itself "
                       "and its contents will not be uploaded. VirusTotal receives the hash and request metadata."):
            return
        run_async(self, self.vt.lookup_hash, result["sha256"], on_done=self._vt_result,
                  on_fail=lambda message: QMessageBox.warning(self, "VirusTotal", message))

    def _vt_result(self, result):
        QMessageBox.information(
            self, "VirusTotal hash report",
            f"Latest analysis: {result['malicious']} malicious, {result['suspicious']} suspicious, "
            f"{result['undetected']} undetected.\nChecked: {result['checked_at']}"
            f"{' (session cache)' if result.get('cached') else ''}.\n\nThese are third-party engine results, not a definitive "
            "malware verdict. Choose 'Open report' only if you want to contact VirusTotal in your browser.")
        import webbrowser
        if confirm(self, "Open VirusTotal report", "Open the hash report in your default browser?"):
            webbrowser.open(result["link"])

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
        pids = self.selected_pids()
        if not pids:
            self._target()
            return
        if len(pids) > 1 and not editions.can("advanced"):
            QMessageBox.information(self, "Advanced feature",
                                    "Bulk process trimming is available in Free with Ads, Supporter, and Pro. "
                                    "Select one process to use the core trim tool.")
            return
        names = [r["name"] for r in self.rows if r["pid"] in pids]
        if not confirm(self, "Trim working sets",
                       f"Ask Windows to trim {len(pids)} selected process working set(s)? "
                       "This does not free memory permanently; applications may page data back in, "
                       "which can temporarily slow them down. Protected processes are skipped."):
            return
        run_async(self, procman.trim_process_batch, pids, on_done=self._trim_done)

    def _trim_done(self, results):
        lines = []
        total = 0
        for result in results:
            if "error" in result:
                lines.append(f"PID {result['pid']} {result['name']}: {result['error']}")
            else:
                total += result["reclaimed"]
                lines.append(f"PID {result['pid']} {result['name']}: {fmt_bytes(result['before'])} → "
                             f"{fmt_bytes(result['after'])}, measured decrease {fmt_bytes(result['reclaimed'])}")
        self.status(f"Trim requests finished; measured working-set decrease {fmt_bytes(total)}.")
        QMessageBox.information(self, "Trim results", "\n".join(lines) +
                                "\n\nWorking-set changes are temporary and are not guaranteed performance gains.")

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
                         ("Copy process details", self.copy_details), ("Analyze executable / VirusTotal…",
                                                                       self.analyze_selected),
                         ("Search process online", self.search)):
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
