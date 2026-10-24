"""TaskForge main window, tray integration and entry point."""
import ctypes
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
                             QPushButton, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

from . import __app_name__, __version__, editions, icon, sysinfo
from .page_resources import ResourcesPage
from .page_health import HealthPage
from .pages_mem import MemoryPage
from .pages_proc import DashboardPage, ProcessesPage
from .pages_sys import CpuPage, SettingsPage, StartupPage, build_oc_guide
from .themes import palette, stylesheet
from .util import Settings, is_admin, relaunch_as_admin
from .widgets import Monitor, run_async, shutdown_workers

NAV = ["Dashboard", "System Health", "Processes", "Memory", "CPU & Turbo", "Overclocking Guide", "Startup",
       "Settings", "Edition & Resources"]


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.really_quit = False
        self.setWindowTitle(f"{__app_name__} {editions.info()['name']} — System Control Center")
        self.resize(1320, 860)
        self.setMinimumSize(1050, 680)

        self.monitor = Monitor(settings.get("refresh_ms"))
        pal = palette(settings.get("theme"))

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._header())

        body = QHBoxLayout()
        body.setSpacing(0)
        v.addLayout(body, 1)

        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(210)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 14, 0, 12)
        self.nav = []
        for i, name in enumerate(NAV):
            b = QPushButton(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, i=i: self.go(i))
            sl.addWidget(b)
            self.nav.append(b)
        sl.addStretch()
        foot = QLabel(f"{editions.info()['name']} • v{__version__}\nNo telemetry")
        foot.setObjectName("SidebarFoot")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(foot)
        body.addWidget(side)

        self.stack = QStackedWidget()
        st = self.status
        self.dashboard = DashboardPage(self.monitor, pal)
        self.health = HealthPage(self.monitor, st)
        self.processes = ProcessesPage(self.monitor, st)
        self.memory = MemoryPage(self.monitor, st)
        self.cpu = CpuPage(self.monitor, st)
        self.guide = build_oc_guide(self.monitor, settings.get)
        self.startup = StartupPage(settings)
        self.settings_page = SettingsPage(settings)
        self.resources = ResourcesPage()
        for p in (self.dashboard, self.health, self.processes, self.memory, self.cpu, self.guide, self.startup,
                  self.settings_page, self.resources):
            self.stack.addWidget(p)
        body.addWidget(self.stack, 1)

        self.settings_page.theme_changed.connect(self.apply_theme)
        self.settings_page.interval_changed.connect(self.monitor.set_interval)
        self.monitor.updated.connect(self._header_update)

        self._tray()
        self.apply_theme(settings.get("theme"))
        self.go(0)
        self.statusBar().showMessage("Ready" + ("" if is_admin() else " — running as standard user; some actions "
                                                                       "need “Restart as admin”."))
        run_async(self, sysinfo.hardware_inventory, on_done=self._inventory, on_fail=lambda _m: None)
        QTimer.singleShot(50, self.monitor.tick)

    # ---------------------------------------------------------------- UI
    def _header(self):
        h = QFrame()
        h.setObjectName("Header")
        h.setFixedHeight(64)
        lay = QHBoxLayout(h)
        lay.setContentsMargins(16, 8, 16, 8)
        self.logo = QLabel()
        lay.addWidget(self.logo)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        t = QLabel("TASKFORGE")
        t.setObjectName("HeaderTitle")
        s = QLabel("System Control Center")
        s.setObjectName("HeaderSub")
        tv.addWidget(t)
        tv.addWidget(s)
        lay.addLayout(tv)
        lay.addStretch()
        self.chip_cpu, self.chip_clk, self.chip_ram = QLabel("CPU –"), QLabel("– GHz"), QLabel("RAM –")
        for c in (self.chip_cpu, self.chip_clk, self.chip_ram):
            c.setObjectName("Chip")
            lay.addWidget(c)
        admin = QLabel("ADMIN" if is_admin() else "STANDARD USER")
        admin.setObjectName("ChipAdmin" if is_admin() else "ChipUser")
        lay.addSpacing(10)
        lay.addWidget(admin)
        if not is_admin():
            b = QPushButton("Restart as admin")
            b.setObjectName("AccentBtn")
            b.clicked.connect(self.elevate)
            lay.addWidget(b)
        return h

    def _header_update(self, s):
        self.chip_cpu.setText(f"CPU {s['cpu']:.0f}%")
        self.chip_clk.setText(f"{s['mhz']/1000:.2f} GHz")
        self.chip_ram.setText(f"RAM {s['vm'].percent:.0f}%")
        if hasattr(self, "tray"):
            self.tray.setToolTip(f"TaskForge — CPU {s['cpu']:.0f}% • RAM {s['vm'].percent:.0f}% • "
                                 f"{s['mhz']/1000:.2f} GHz")

    def _inventory(self, inv):
        if not inv:
            return
        for p in (self.cpu, self.memory, self.guide):
            p.set_inventory(inv)

    def go(self, i):
        self.stack.setCurrentIndex(i)
        for j, b in enumerate(self.nav):
            b.setChecked(i == j)
        if self.monitor.last:
            self.monitor.updated.emit(self.monitor.last)

    def apply_theme(self, name):
        pal = palette(name)
        QApplication.instance().setStyleSheet(stylesheet(name))
        ic = icon.app_icon(pal["accent"], pal["accent2"])
        self.setWindowIcon(ic)
        QApplication.instance().setWindowIcon(ic)
        self.logo.setPixmap(icon.render(44, pal["accent"], pal["accent2"]))
        self.dashboard.apply_palette(pal)
        if hasattr(self, "tray"):
            self.tray.setIcon(ic)

    def status(self, msg):
        self.statusBar().showMessage(msg, 10000)

    def elevate(self):
        if relaunch_as_admin():
            self.really_quit = True
            QApplication.quit()
        else:
            QMessageBox.warning(self, "TaskForge", "Elevation was cancelled or failed.")

    # ---------------------------------------------------------------- tray
    def _tray(self):
        self.tray = QSystemTrayIcon(icon.app_icon(), self)
        m = QMenu()
        m.addAction("Show TaskForge", self.restore)
        for i, name in ((0, "Dashboard"), (1, "System Health"), (2, "Processes"), (3, "Memory"),
                        (4, "CPU & Turbo")):
            m.addAction(name, lambda i=i: (self.restore(), self.go(i)))
        m.addSeparator()
        quit_act = QAction("Exit", m)
        quit_act.triggered.connect(self.quit)
        m.addAction(quit_act)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: self.restore() if r in (QSystemTrayIcon.ActivationReason.Trigger,
                                                                       QSystemTrayIcon.ActivationReason.DoubleClick)
                                    else None)
        self.tray.show()

    def restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit(self):
        self.really_quit = True
        self.monitor.timer.stop()
        self.tray.hide()
        QApplication.quit()

    def _hint_tray(self):
        if not self.settings.get("tray_notice_shown"):
            self.tray.showMessage("TaskForge is still running", "Click the tray icon to reopen; right-click → Exit to quit.",
                                  QSystemTrayIcon.MessageIcon.Information, 4000)
            self.settings.set("tray_notice_shown", True)

    def changeEvent(self, e):
        if e.type() == e.Type.WindowStateChange and self.isMinimized() and self.settings.get("minimize_to_tray") \
                and QSystemTrayIcon.isSystemTrayAvailable():
            QTimer.singleShot(0, self.hide)
            self._hint_tray()
        super().changeEvent(e)

    def closeEvent(self, e):
        if not self.really_quit and self.settings.get("close_to_tray") and QSystemTrayIcon.isSystemTrayAvailable():
            e.ignore()
            self.hide()
            self._hint_tray()
            return
        self.tray.hide()
        e.accept()
        QApplication.quit()


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TaskForge.SystemControlCenter")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    settings = Settings()
    win = MainWindow(settings)
    app.aboutToQuit.connect(lambda: (win.monitor.timer.stop(), shutdown_workers(20000)))
    if "--selftest" in sys.argv:
        return _selftest(app, win)
    if "--icon-out" in sys.argv:
        icon.render(256).save(sys.argv[sys.argv.index("--icon-out") + 1], "PNG")
        return 0

    if settings.get("start_minimized") and QSystemTrayIcon.isSystemTrayAvailable():
        win.hide()
    else:
        win.show()
    return app.exec()


def _selftest(app, win):
    """Open every page, wait for real telemetry, then exit. Changes no system settings."""
    result = {"ok": False}
    win.show()

    def visit(i=0):
        if i < len(NAV):
            win.go(i)
            QTimer.singleShot(400, lambda: visit(i + 1))
        else:
            s = win.monitor.last
            result["ok"] = bool(s and s["procs"] and s["vm"].total)
            print(f"SELFTEST pages={len(NAV)} procs={len(s.get('procs', []))} cpu={s.get('cpu', 0):.0f}% "
                  f"mhz={s.get('mhz')} ok={result['ok']}", flush=True)
            win.quit()

    QTimer.singleShot(3500, visit)
    app.exec()
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
