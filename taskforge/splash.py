"""Short, accessible startup splash with a single lightweight brand animation."""
import ctypes
import sys

from PyQt6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath, QRadialGradient)
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from . import __version__, editions, icon
from .themes import palette

STAGES = (
    "Loading settings and theme",
    "Initializing system monitors",
    "Preparing dashboard and process data",
    "Restoring tray and preferences",
    "Ready",
)
ANIMATION_DURATION_MS = 850


def should_show_splash(settings, args, tray_available=True):
    """Keep automated and tray-first launches quiet; never delay startup for the splash."""
    args = set(args)
    if {"--selftest", "--background", "--icon-out"} & args:
        return False
    return not (settings.get("start_minimized") and tray_available)


def animation_enabled(reduced_motion=False, high_contrast=False, battery_saver=False):
    return not (reduced_motion or high_contrast or battery_saver)


def startup_failure_message(stage, error):
    return (
        "TaskForge could not finish initializing. Check that Windows and the application files are available, "
        "then try again.\n\n"
        f"Startup stage: {stage}\nDetails: {error}"
    )


def system_prefers_reduced_motion():
    """Read Windows accessibility/power preferences; failed probes safely disable motion."""
    if sys.platform != "win32":
        return True
    try:
        user32 = ctypes.windll.user32
        enabled = ctypes.c_int()
        if not user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return True
        if not enabled.value:
            return True
        class HighContrast(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint),
                        ("lpszDefaultScheme", ctypes.c_wchar_p)]

        contrast = HighContrast(ctypes.sizeof(HighContrast), 0, None)
        if user32.SystemParametersInfoW(0x0042, ctypes.sizeof(contrast), ctypes.byref(contrast), 0) \
                and contrast.dwFlags & 1:
            return True
        class PowerStatus(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_uint32), ("BatteryFullLifeTime", ctypes.c_uint32)]

        power = PowerStatus()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)) and power.SystemStatusFlag == 1:
            return True
        return False
    except (AttributeError, OSError, TypeError, ValueError):
        return True


class BoltMark(QWidget):
    def __init__(self, accent, accent2, parent=None):
        super().__init__(parent)
        self.accent, self.accent2 = QColor(accent), QColor(accent2)
        self.progress = 1.0
        self.setFixedSize(64, 64)
        self.setAccessibleName("TaskForge lightning bolt")

    def set_progress(self, progress):
        self.progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon.paint_icon(p, QRectF(1, 1, self.width() - 2, self.height() - 2),
                        self.accent.name(), self.accent2.name())
        scale = min(self.width(), self.height()) / 256
        offset_x = (self.width() - 256 * scale) / 2
        offset_y = (self.height() - 256 * scale) / 2
        bolt = QPainterPath()
        points = ((140, 68), (90, 136), (124, 136), (110, 188), (166, 116), (130, 116), (148, 68))
        bolt.moveTo(offset_x + points[0][0] * scale, offset_y + points[0][1] * scale)
        for x, y in points[1:]:
            bolt.lineTo(offset_x + x * scale, offset_y + y * scale)
        bolt.closeSubpath()
        glow = max(0.0, 1.0 - abs(self.progress - 0.48) / 0.3)
        if glow:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 224, 112, int(34 * glow)))
            p.drawPath(bolt)
            p.setPen(QColor(255, 248, 201, int(115 * glow)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(bolt)
        p.end()


class StartupSplash(QWidget):
    """Non-modal splash; animation is bounded and does not control window lifetime."""

    def __init__(self, theme_name="Midnight Violet", test_build=False, reduced_motion=None):
        super().__init__()
        self.colors = palette(theme_name)
        if reduced_motion is None:
            reduced_motion = system_prefers_reduced_motion()
        self.animate = animation_enabled(reduced_motion)
        self.test_build = bool(test_build)
        self.stage_index = -1
        self._motion = QElapsedTimer()
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(33)
        self._animation_timer.timeout.connect(self._tick_animation)
        self.setObjectName("StartupSplash")
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(468, 278)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(25, 21, 25, 17)
        outer.setSpacing(11)
        heading = QHBoxLayout()
        heading.setSpacing(13)
        self.bolt = BoltMark(self.colors["accent"], self.colors["accent2"])
        heading.addWidget(self.bolt)
        brand = QVBoxLayout()
        brand.setSpacing(1)
        title = QLabel("TASKFORGE")
        title.setStyleSheet("font-size: 17pt; font-weight: 800;")
        sub = QLabel("System Control Center")
        sub.setStyleSheet(f"color: {self.colors['muted']}; font-size: 9pt;")
        brand.addWidget(title)
        brand.addWidget(sub)
        heading.addLayout(brand)
        heading.addStretch()
        self.version = QLabel(f"v{__version__}")
        self.version.setStyleSheet(f"color: {self.colors['muted']}; font-size: 9pt;")
        heading.addWidget(self.version, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(heading)

        self.edition = QLabel(editions.info()["name"])
        self.edition.setStyleSheet(
            f"background: {self.colors['card']}; border: 1px solid {self.colors['border']}; "
            f"border-radius: 9px; padding: 3px 9px; font-size: 8.5pt;")
        self.edition.setAccessibleName(f"TaskForge edition: {editions.info()['name']}")
        outer.addWidget(self.edition, 0, Qt.AlignmentFlag.AlignLeft)
        self.watermark = None
        if self.test_build:
            self.watermark = QLabel("UNLOCKED TEST BUILD — NOT FOR DISTRIBUTION")
            self.watermark.setStyleSheet("color: #fbbf24; font-weight: 800; font-size: 8.5pt;")
            self.watermark.setAccessibleName("Unlocked owner test build. Not for distribution.")
            outer.addWidget(self.watermark)

        outer.addStretch(1)
        self.status = QLabel(STAGES[0])
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Startup progress status")
        self.status.setAccessibleDescription("Current TaskForge startup stage")
        self.status.setStyleSheet("font-weight: 650;")
        outer.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, len(STAGES) - 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setAccessibleName("Startup stage progress")
        outer.addWidget(self.progress)
        foot = QHBoxLayout()
        self.hint = QLabel("Starting quickly · no settings are changed")
        self.hint.setStyleSheet(f"color: {self.colors['muted']}; font-size: 8pt;")
        foot.addWidget(self.hint, 1)
        self.hide_button = QPushButton("Hide")
        self.hide_button.setObjectName("SplashHide")
        self.hide_button.setFixedHeight(28)
        self.hide_button.setAccessibleName("Hide startup splash without cancelling startup")
        self.hide_button.clicked.connect(self.dismiss)
        foot.addWidget(self.hide_button)
        outer.addLayout(foot)
        self._long_startup_timer = QTimer(self)
        self._long_startup_timer.setSingleShot(True)
        self._long_startup_timer.setInterval(12000)
        self._long_startup_timer.timeout.connect(self._show_long_startup_hint)

    def showEvent(self, event):
        super().showEvent(event)
        if self.animate:
            self._motion.start()
            self._animation_timer.start()
        self._long_startup_timer.start()
        screen = self.screen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())

    def set_theme(self, theme_name):
        self.colors = palette(theme_name)
        self.bolt.accent = QColor(self.colors["accent"])
        self.bolt.accent2 = QColor(self.colors["accent2"])
        self.bolt.update()
        self.update()

    def set_stage(self, stage):
        if isinstance(stage, str):
            if stage not in STAGES:
                raise ValueError(f"Unknown startup stage: {stage}")
            index = STAGES.index(stage)
        else:
            index = int(stage)
            if not 0 <= index < len(STAGES):
                raise ValueError(f"Startup stage index out of range: {index}")
            stage = STAGES[index]
        self.stage_index = max(self.stage_index, index)
        self.status.setText(stage)
        self.status.setAccessibleDescription(f"Current TaskForge startup stage: {stage}")
        self.progress.setValue(self.stage_index)
        self.update()
        QApplication.processEvents()

    def _show_long_startup_hint(self):
        self.hint.setText("Still preparing; startup continues. Hide this panel if you prefer.")

    def _tick_animation(self):
        elapsed = self._motion.elapsed()
        self.bolt.set_progress(min(1.0, elapsed / ANIMATION_DURATION_MS))
        self.update()
        if elapsed >= ANIMATION_DURATION_MS:
            self._animation_timer.stop()

    def stop_animation(self):
        self._animation_timer.stop()
        self._long_startup_timer.stop()

    def dismiss(self):
        self.stop_animation()
        self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        radius = 17
        shell = QPainterPath()
        shell.addRoundedRect(outer, radius, radius)
        fill = QLinearGradient(0, outer.top(), 0, outer.bottom())
        fill.setColorAt(0, QColor(self.colors["panel"]))
        fill.setColorAt(1, QColor(self.colors["bg"]))
        p.fillPath(shell, fill)

        inset = 2.4
        inner = outer.adjusted(inset, inset, -inset, -inset)
        border_path = QPainterPath()
        border_path.addRoundedRect(outer, radius, radius)
        cutout = QPainterPath()
        cutout.addRoundedRect(inner, radius - inset, radius - inset)
        ring = border_path.subtracted(cutout)
        chrome = QLinearGradient(0, outer.top(), 0, outer.bottom())
        for position, color in ((0.0, "#eef3f8"), (0.12, "#8793a1"), (0.3, "#ffffff"),
                                (0.48, "#687483"), (0.68, "#e2e8ef"), (0.86, "#7b8795"),
                                (1.0, "#f5f7fa")):
            chrome.setColorAt(position, QColor(color))
        p.fillPath(ring, chrome)
        accent = QColor(self.colors["accent"])
        accent.setAlpha(96)
        p.setPen(accent)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(inner.adjusted(0.6, 0.6, -0.6, -0.6), radius - inset, radius - inset)

        if self.animate and self._motion.isValid():
            elapsed = self._motion.elapsed()
            progress = min(1.0, elapsed / ANIMATION_DURATION_MS)
            if progress < 1:
                p.save()
                p.setClipPath(ring)
                sweep_x = -100 + (self.width() + 200) * progress
                sweep = QLinearGradient(sweep_x, 0, sweep_x + 86, self.height())
                clear = QColor("#ffffff")
                clear.setAlpha(0)
                tint = QColor(self.colors["accent"])
                tint.setAlpha(28)
                shine = QColor("#ffffff")
                shine.setAlpha(185)
                sweep.setColorAt(0, clear)
                sweep.setColorAt(0.34, tint)
                sweep.setColorAt(0.5, shine)
                sweep.setColorAt(0.66, tint)
                sweep.setColorAt(1, clear)
                p.fillRect(self.rect(), sweep)
                bloom_strength = max(0.0, 1.0 - abs(progress - 0.56) / 0.22)
                if bloom_strength:
                    center = QPointF(self.width() - 8, 8)
                    bloom = QRadialGradient(center, 43)
                    glow = QColor("#fff2b0")
                    glow.setAlpha(int(70 * bloom_strength))
                    transparent = QColor("#fff2b0")
                    transparent.setAlpha(0)
                    bloom.setColorAt(0, glow)
                    bloom.setColorAt(1, transparent)
                    p.setBrush(bloom)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(center, 43, 43)
                p.restore()
        p.end()
