"""Programmatic TaskForge icon (anvil-shaped chip with a lightning bolt) - no external art needed."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def paint_icon(p: QPainter, rect: QRectF, accent="#8b5cf6", accent2="#22d3ee"):
    """Paint the canonical icon geometry into any square or rectangular target."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    size = min(rect.width(), rect.height())
    s = size / 256.0
    p.translate(rect.x() + (rect.width() - size) / 2, rect.y() + (rect.height() - size) / 2)

    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(accent))
    grad.setColorAt(1, QColor(accent2))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 56 * s, 56 * s)

    # chip pins
    p.setBrush(QColor(255, 255, 255, 120))
    for i in range(4):
        off = (70 + i * 34) * s
        for x, y, w, h in ((off, 34 * s, 14 * s, 22 * s), (off, 200 * s, 14 * s, 22 * s),
                           (34 * s, off, 22 * s, 14 * s), (200 * s, off, 22 * s, 14 * s)):
            p.drawRoundedRect(QRectF(x, y, w, h), 4 * s, 4 * s)

    # chip body
    p.setBrush(QColor(12, 14, 22, 235))
    p.drawRoundedRect(QRectF(56 * s, 56 * s, 144 * s, 144 * s), 22 * s, 22 * s)

    # lightning bolt
    bolt = QPolygonF([QPointF(x * s, y * s) for x, y in
                      ((140, 68), (90, 136), (124, 136), (110, 188), (166, 116), (130, 116), (148, 68))])
    path = QPainterPath()
    path.addPolygon(bolt)
    bgrad = QLinearGradient(0, 68 * s, 0, 188 * s)
    bgrad.setColorAt(0, QColor("#fde047"))
    bgrad.setColorAt(1, QColor("#f97316"))
    p.setBrush(QBrush(bgrad))
    p.setPen(QPen(QColor(255, 255, 255, 200), 3 * s))
    p.drawPath(path)

    p.restore()


def render(size: int = 256, accent="#8b5cf6", accent2="#22d3ee") -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    paint_icon(p, QRectF(0, 0, size, size), accent, accent2)
    p.end()
    return pm


def app_icon(accent="#8b5cf6", accent2="#22d3ee") -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(render(sz, accent, accent2))
    return icon
