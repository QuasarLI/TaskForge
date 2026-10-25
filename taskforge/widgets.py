"""Reusable widgets, background workers and the shared telemetry monitor."""
from collections import deque

import psutil
import os
import time
from PyQt6.QtCore import QObject, QRectF, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QSizePolicy,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from . import procman, sysinfo
from .procman import ProcessSampler


class Worker(QThread):
    """Run a callable off the UI thread."""
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self.fn, self.args = fn, args

    def run(self):
        try:
            self.done.emit(self.fn(*self.args))
        except Exception as e:  # surfaced to the user by the caller
            self.failed.emit(str(e))


_LIVE_WORKERS = set()


def workers_running():
    for worker in list(_LIVE_WORKERS):
        try:
            if worker.isRunning():
                return True
        except RuntimeError:
            continue
    return False


def shutdown_workers(timeout_ms=5000):
    for w in list(_LIVE_WORKERS):
        try:
            w.wait(timeout_ms)
        except RuntimeError:
            pass


def run_async(owner, fn, *args, on_done=None, on_fail=None):
    w = Worker(fn, *args, parent=owner)
    if on_done:
        w.done.connect(on_done)
    w.failed.connect(on_fail or (lambda msg: QMessageBox.warning(owner, "TaskForge", msg)))
    _LIVE_WORKERS.add(w)
    w.finished.connect(lambda: _LIVE_WORKERS.discard(w))
    w.finished.connect(w.deleteLater)
    w.start()
    return w


class Monitor(QObject):
    """Samples system + process telemetry on a worker thread and broadcasts snapshots."""
    updated = pyqtSignal(dict)

    def __init__(self, interval_ms=2000):
        super().__init__()
        self.ident = sysinfo.cpu_identity()
        self.clock = sysinfo.LiveClock(self.ident["base_mhz"])
        self.sampler = ProcessSampler()
        self.history = {k: deque([0.0] * 90, maxlen=90) for k in ("cpu", "ram", "commit", "mhz")}
        self.last = {}
        self.process_history = procman.ProcessHistory()
        self._busy = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.set_interval(interval_ms)

    def set_interval(self, ms):
        self.timer.start(max(750, int(ms)))

    def tick(self):
        if self._busy:
            return
        self._busy = True
        run_async(self, self._collect, on_done=self._publish, on_fail=lambda _m: setattr(self, "_busy", False))

    def _collect(self):
        times = psutil.cpu_times(percpu=True)
        prev, self._prev_times = getattr(self, "_prev_times", None), times
        per = []
        for i, t in enumerate(times):
            if prev and i < len(prev):
                busy = (t.user + t.system + t.interrupt + t.dpc) - (prev[i].user + prev[i].system +
                                                                    prev[i].interrupt + prev[i].dpc)
                total = busy + (t.idle - prev[i].idle)
                per.append(max(0.0, min(100.0, 100.0 * busy / total)) if total > 0 else 0.0)
            else:
                per.append(0.0)
        vm = psutil.virtual_memory()
        perf = sysinfo.performance_info()
        procs = self.sampler.sample()
        system_disk = psutil.disk_usage(os.path.abspath(os.sep))
        return {"cpu": sum(per) / max(1, len(per)), "percore": per, "vm": vm, "perf": perf,
                "mhz": self.clock.mhz(), "procs": procs, "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
                "system_disk": system_disk}

    def _publish(self, snap):
        self._busy = False
        self.history["cpu"].append(snap["cpu"])
        self.history["ram"].append(snap["vm"].percent)
        perf = snap["perf"]
        if perf.get("commit_limit"):
            self.history["commit"].append(100.0 * perf["commit_total"] / perf["commit_limit"])
        self.history["mhz"].append(snap["mhz"])
        self.process_history.update(snap["procs"])
        snap["history"] = self.history
        self.last = snap
        self.updated.emit(snap)


class Sparkline(QWidget):
    def __init__(self, color="#8b5cf6", maximum=100.0, parent=None):
        super().__init__(parent)
        self.data = []
        self.color = QColor(color)
        self.maximum = maximum
        self.setMinimumHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_color(self, c):
        self.color = QColor(c)
        self.update()

    def set_data(self, data, maximum=None):
        self.data = list(data)
        if maximum:
            self.maximum = maximum
        self.update()

    def paintEvent(self, _e):
        if len(self.data) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height() - 2
        mx = max(self.maximum, max(self.data) or 1)
        step = w / (len(self.data) - 1)
        path = QPainterPath()
        for i, v in enumerate(self.data):
            x, y = i * step, h - (v / mx) * (h - 4) + 1
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        fill = QPainterPath(path)
        fill.lineTo(w, h + 2)
        fill.lineTo(0, h + 2)
        fill.closeSubpath()
        g = QLinearGradient(0, 0, 0, h)
        c1, c2 = QColor(self.color), QColor(self.color)
        c1.setAlpha(110)
        c2.setAlpha(5)
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        p.fillPath(fill, g)
        p.setPen(QPen(self.color, 2))
        p.drawPath(path)
        p.end()


class MetricCard(QFrame):
    def __init__(self, title, color="#8b5cf6"):
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.title = QLabel(title)
        self.title.setObjectName("Muted")
        self.value = QLabel("-")
        self.value.setObjectName("BigValue")
        self.sub = QLabel("")
        self.sub.setObjectName("Explain")
        self.spark = Sparkline(color)
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        lay.addWidget(self.sub)
        lay.addWidget(self.spark)


def page_header(title, subtitle):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    s = QLabel(subtitle)
    s.setObjectName("PageSub")
    s.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(s)
    return w


def explain(text):
    lbl = QLabel(text)
    lbl.setObjectName("Explain")
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


def bar(value=0):
    b = QProgressBar()
    b.setRange(0, 100)
    b.setValue(int(value))
    b.setFixedHeight(14)
    return b


class NumItem(QTableWidgetItem):
    """Table item that sorts by a numeric key."""

    def __init__(self, text, key):
        super().__init__(text)
        self.key = key
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        try:
            return self.key < other.key
        except (AttributeError, TypeError):
            return super().__lt__(other)


def hrow(*widgets, stretch_last=False):
    lay = QHBoxLayout()
    for w in widgets:
        if w == "stretch":
            lay.addStretch()
        else:
            lay.addWidget(w)
    if stretch_last:
        lay.addStretch()
    return lay


def confirm(parent, title, text, danger=False) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    return box.exec() == QMessageBox.StandardButton.Yes
