"""Beginner-friendly system health snapshot and safe Windows reports."""
import json
import os
import time

from PyQt6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from . import editions, pagefile
from .util import app_data_dir, fmt_bytes, open_path, run
from .widgets import explain, page_header, page_layout, run_async


class HealthPage(QWidget):
    def __init__(self, monitor, status):
        super().__init__()
        self.monitor, self.status = monitor, status
        self.snapshot = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        page_layout(lay)
        lay.addWidget(page_header("System Health", "A plain-language snapshot of current pressure and safe next steps. "
                                                  "TaskForge observes only; it never tunes automatically."))

        summary = QGroupBox("Live health snapshot")
        grid = QGridLayout(summary)
        self.values = {}
        for i, title in enumerate(("CPU load", "CPU clock", "RAM pressure", "Commit pressure", "Top CPU app",
                                   "Top memory app")):
            label = QLabel(title)
            label.setObjectName("Muted")
            value = QLabel("Waiting for telemetry...")
            value.setObjectName("Value")
            value.setWordWrap(True)
            self.values[title] = value
            grid.addWidget(label, i // 2 * 2, i % 2)
            grid.addWidget(value, i // 2 * 2 + 1, i % 2)
        lay.addWidget(summary)

        advice = QGroupBox("What needs attention")
        al = QVBoxLayout(advice)
        self.advice = QLabel("Collecting enough information to explain this PC...")
        self.advice.setWordWrap(True)
        self.advice.setObjectName("Explain")
        al.addWidget(self.advice)
        lay.addWidget(advice)

        reports = QGroupBox("Safe Windows reports")
        rl = QVBoxLayout(reports)
        rl.addWidget(explain("These tools only ask Windows to create a report; they do not change power, CPU, memory, "
                             "or paging settings. Energy diagnostics take 60 seconds and may need administrator rights."))
        row = QHBoxLayout()
        battery = QPushButton("Create battery report")
        battery.clicked.connect(lambda: self.make_report("battery"))
        energy = QPushButton("Create 60-second energy report")
        energy.clicked.connect(lambda: self.make_report("energy"))
        folder = QPushButton("Open reports folder")
        folder.clicked.connect(lambda: open_path(self._reports_dir()))
        export = QPushButton("Export snapshot (Pro)")
        export.clicked.connect(self.export_snapshot)
        for button in (battery, energy, folder, export):
            row.addWidget(button)
        row.addStretch()
        rl.addLayout(row)
        lay.addWidget(reports)

        defaults = QGroupBox("Sensible defaults")
        dl = QVBoxLayout(defaults)
        dl.addWidget(explain(
            "CPU: Balanced plan and normal boost behavior are best for most people. More performance means more heat.\n"
            "Memory: cached RAM is useful and reclaimed automatically. Do not trim routinely.\n"
            "Paging: Windows-managed is safest. Custom sizing needs admin, a backup, and a reboot to take effect.\n"
            "Undo: use TaskForge Restore for settings it changed; generated reports require no undo."))
        lay.addWidget(defaults)
        lay.addStretch()
        monitor.updated.connect(self.refresh)

    def refresh(self, snap):
        if not self.isVisible():
            return
        self.snapshot = snap
        vm, perf = snap["vm"], snap["perf"]
        commit_pct = 100 * perf.get("commit_total", 0) / max(1, perf.get("commit_limit", 1))
        procs = [p for p in snap["procs"] if p["pid"] not in (0, 4)]
        top_cpu = max(procs, key=lambda p: p["cpu"], default=None)
        top_mem = max(procs, key=lambda p: p["ws"], default=None)
        self.values["CPU load"].setText(f"{snap['cpu']:.0f}% - {'busy' if snap['cpu'] >= 85 else 'normal'}")
        self.values["CPU clock"].setText(f"{snap['mhz']/1000:.2f} GHz effective")
        self.values["RAM pressure"].setText(f"{vm.percent:.0f}% used, {fmt_bytes(vm.available)} available")
        self.values["Commit pressure"].setText(f"{commit_pct:.0f}% of RAM + pagefile limit")
        self.values["Top CPU app"].setText(f"{top_cpu['name']} ({top_cpu['cpu']:.1f}%)" if top_cpu else "None")
        self.values["Top memory app"].setText(f"{top_mem['name']} ({fmt_bytes(top_mem['ws'])})" if top_mem else "None")
        notes = []
        if snap["cpu"] >= 90:
            notes.append("CPU is heavily loaded now. Check the top CPU app before changing power settings.")
        if vm.percent >= 90:
            notes.append("RAM pressure is high. Close an unused large app; trimming is only temporary.")
        if commit_pct >= 85:
            initial, maximum = pagefile.recommend(perf.get("phys_total", vm.total), perf.get("commit_peak", 0))
            notes.append(f"Commit is near its limit. Keep a pagefile; a workload-based starting point is "
                         f"{initial:,}-{maximum:,} MB, but Windows-managed remains the safest default.")
        if not notes:
            notes.append("No immediate pressure detected. Changing settings without a measured problem is unlikely "
                         "to help and can increase heat, power use, or instability.")
        self.advice.setText("\n\n".join(notes))

    def _reports_dir(self):
        path = os.path.join(app_data_dir(), "reports")
        os.makedirs(path, exist_ok=True)
        return path

    def make_report(self, kind):
        name = f"{kind}-{time.strftime('%Y%m%d-%H%M%S')}.html"
        path = os.path.join(self._reports_dir(), name)
        args = ["powercfg", f"/{kind}", "/output", path]
        if kind == "energy":
            args.extend(["/duration", "60"])
        self.status(f"Generating Windows {kind} report...")
        run_async(self, run, args, 90, on_done=lambda result: self._report_done(path, result),
                  on_fail=lambda message: QMessageBox.warning(self, "Report failed", message))

    def _report_done(self, path, result):
        code, _out, error = result
        if code or not os.path.exists(path):
            QMessageBox.warning(self, "Report failed", error.strip() or f"Windows returned error {code}.")
            return
        self.status(f"Created {path}")
        open_path(path)

    def export_snapshot(self):
        if not editions.can("pro"):
            QMessageBox.information(self, "Pro feature", "Redacted snapshot export requires activated Pro.")
            return
        if not self.snapshot:
            QMessageBox.information(self, "TaskForge", "Wait for the first telemetry update.")
            return
        snap, perf = self.snapshot, self.snapshot["perf"]
        data = {
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "edition": editions.info()["id"],
            "cpu_percent": round(snap["cpu"], 1),
            "effective_mhz": snap["mhz"],
            "memory_percent": snap["vm"].percent,
            "memory_available_bytes": snap["vm"].available,
            "commit_total_bytes": perf.get("commit_total"),
            "commit_limit_bytes": perf.get("commit_limit"),
            "process_count": len(snap["procs"]),
        }
        path = os.path.join(self._reports_dir(), f"snapshot-{time.strftime('%Y%m%d-%H%M%S')}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        self.status(f"Exported redacted snapshot: {path}")
