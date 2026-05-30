"""
NetTool - Network Toolbox
Version: V100R008C00SPC700
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Qt-painted vector icon system shared by macOS and Windows.
"""

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


def _color(value):
    return QColor(value)


@lru_cache(maxsize=512)
def pixmap(name, size=24, fg="#0f172a", accent="#10a37f", bg="transparent", dpr=3):
    physical_size = int(size * dpr)
    pm = QPixmap(physical_size, physical_size)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = float(physical_size)
    c = _color(fg)
    a = _color(accent)

    def pen(color=c, width=2.0, cap=Qt.PenCapStyle.RoundCap):
        qpen = QPen(color, max(1.0, width * s / 24.0))
        qpen.setCapStyle(cap)
        qpen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return qpen

    def rounded(rect, radius, fill, outline=None, width=1.4):
        p.setBrush(QBrush(fill))
        p.setPen(Qt.PenStyle.NoPen if outline is None else pen(outline, width))
        p.drawRoundedRect(rect, radius, radius)

    if bg != "transparent":
        g = QLinearGradient(0, 0, s, s)
        g.setColorAt(0, QColor(bg).lighter(122))
        g.setColorAt(1, QColor(bg).darker(108))
        rounded(QRectF(1, 1, s - 2, s - 2), s * 0.28, QBrush(g), QColor(bg).lighter(130), 0.8)

    if name == "app":
        rounded(QRectF(s * 0.16, s * 0.18, s * 0.68, s * 0.64), s * 0.18, QColor("#172033"), a, 1.6)
        p.setPen(pen(QColor("#5eead4"), 3.0))
        p.drawLine(QPointF(s * 0.34, s * 0.34), QPointF(s * 0.52, s * 0.50))
        p.drawLine(QPointF(s * 0.52, s * 0.50), QPointF(s * 0.34, s * 0.66))
        p.setPen(pen(QColor("#d7dde7"), 2.4))
        p.drawLine(QPointF(s * 0.58, s * 0.66), QPointF(s * 0.74, s * 0.66))

    elif name == "ntp":
        p.setPen(pen(c, 1.7))
        p.setBrush(QBrush(QColor(255, 255, 255, 35)))
        p.drawEllipse(QRectF(s * 0.17, s * 0.17, s * 0.66, s * 0.66))
        p.setPen(pen(a, 2.0))
        p.drawLine(QPointF(s * 0.50, s * 0.50), QPointF(s * 0.50, s * 0.28))
        p.drawLine(QPointF(s * 0.50, s * 0.50), QPointF(s * 0.66, s * 0.58))
        p.setPen(pen(c, 1.2))
        for x, y in ((0.50, 0.22), (0.78, 0.50), (0.50, 0.78), (0.22, 0.50)):
            p.drawPoint(QPointF(s * x, s * y))

    elif name == "ftp":
        rounded(QRectF(s * 0.12, s * 0.27, s * 0.76, s * 0.52), s * 0.10, QColor(255, 255, 255, 42), c, 1.5)
        tab = QPainterPath()
        tab.moveTo(s * 0.16, s * 0.31)
        tab.lineTo(s * 0.34, s * 0.31)
        tab.lineTo(s * 0.42, s * 0.40)
        tab.lineTo(s * 0.18, s * 0.40)
        tab.closeSubpath()
        p.fillPath(tab, QBrush(a))
        p.setPen(pen(a, 1.8))
        p.drawLine(QPointF(s * 0.29, s * 0.57), QPointF(s * 0.71, s * 0.57))

    elif name == "ping":
        p.setPen(pen(c, 1.7))
        p.drawEllipse(QRectF(s * 0.38, s * 0.38, s * 0.24, s * 0.24))
        p.setPen(pen(a, 1.8))
        p.drawArc(QRectF(s * 0.25, s * 0.25, s * 0.50, s * 0.50), 30 * 16, 120 * 16)
        p.drawArc(QRectF(s * 0.10, s * 0.10, s * 0.80, s * 0.80), 30 * 16, 120 * 16)
        p.drawArc(QRectF(s * 0.25, s * 0.25, s * 0.50, s * 0.50), 210 * 16, 120 * 16)
        p.drawArc(QRectF(s * 0.10, s * 0.10, s * 0.80, s * 0.80), 210 * 16, 120 * 16)

    elif name == "subnet":
        p.setPen(pen(c, 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * 0.14, s * 0.20, s * 0.72, s * 0.60))
        p.drawLine(QPointF(s * 0.15, s * 0.50), QPointF(s * 0.85, s * 0.50))
        p.drawArc(QRectF(s * 0.30, s * 0.20, s * 0.40, s * 0.60), 90 * 16, 180 * 16)
        p.drawArc(QRectF(s * 0.30, s * 0.20, s * 0.40, s * 0.60), -90 * 16, 180 * 16)
        p.setPen(pen(a, 1.5))
        p.drawLine(QPointF(s * 0.30, s * 0.27), QPointF(s * 0.70, s * 0.73))

    elif name == "cmd":
        rounded(QRectF(s * 0.14, s * 0.20, s * 0.72, s * 0.60), s * 0.12, QColor(255, 255, 255, 40), c, 1.6)
        p.setPen(pen(a, 2.4))
        p.drawLine(QPointF(s * 0.30, s * 0.39), QPointF(s * 0.44, s * 0.50))
        p.drawLine(QPointF(s * 0.44, s * 0.50), QPointF(s * 0.30, s * 0.61))
        p.setPen(pen(c, 1.9))
        p.drawLine(QPointF(s * 0.54, s * 0.62), QPointF(s * 0.72, s * 0.62))

    elif name == "iperf":
        p.setPen(pen(c, 1.5))
        for i, h in enumerate((0.28, 0.42, 0.58, 0.74)):
            x = s * (0.20 + i * 0.17)
            p.drawLine(QPointF(x, s * 0.78), QPointF(x, s * h))
        p.setPen(pen(a, 2.0))
        p.drawLine(QPointF(s * 0.17, s * 0.80), QPointF(s * 0.84, s * 0.80))

    elif name == "mac":
        rounded(QRectF(s * 0.14, s * 0.23, s * 0.72, s * 0.54), s * 0.08, QColor(255, 255, 255, 36), c, 1.5)
        p.setPen(pen(a, 1.7))
        p.drawLine(QPointF(s * 0.28, s * 0.39), QPointF(s * 0.72, s * 0.39))
        p.drawLine(QPointF(s * 0.28, s * 0.52), QPointF(s * 0.72, s * 0.52))
        p.drawLine(QPointF(s * 0.28, s * 0.65), QPointF(s * 0.52, s * 0.65))

    elif name == "route":
        p.setPen(pen(c, 1.7))
        p.drawLine(QPointF(s * 0.22, s * 0.72), QPointF(s * 0.22, s * 0.36))
        p.drawLine(QPointF(s * 0.22, s * 0.36), QPointF(s * 0.52, s * 0.36))
        p.drawLine(QPointF(s * 0.52, s * 0.36), QPointF(s * 0.52, s * 0.22))
        p.drawLine(QPointF(s * 0.22, s * 0.55), QPointF(s * 0.70, s * 0.55))
        p.setPen(pen(a, 2.0))
        p.drawLine(QPointF(s * 0.62, s * 0.45), QPointF(s * 0.76, s * 0.55))
        p.drawLine(QPointF(s * 0.76, s * 0.55), QPointF(s * 0.62, s * 0.65))

    elif name == "log":
        rounded(QRectF(s * 0.20, s * 0.14, s * 0.60, s * 0.72), s * 0.08, QColor(255, 255, 255, 38), c, 1.4)
        p.setPen(pen(a, 1.5))
        for y in (0.34, 0.50, 0.66):
            p.drawLine(QPointF(s * 0.32, s * y), QPointF(s * 0.68, s * y))

    elif name in ("upload", "download"):
        p.setPen(pen(c, 1.6))
        rounded(QRectF(s * 0.20, s * 0.58, s * 0.60, s * 0.22), s * 0.06, QColor(255, 255, 255, 30), c, 1.3)
        p.setPen(pen(a, 2.2))
        if name == "upload":
            p.drawLine(QPointF(s * 0.50, s * 0.22), QPointF(s * 0.50, s * 0.58))
            p.drawLine(QPointF(s * 0.36, s * 0.36), QPointF(s * 0.50, s * 0.22))
            p.drawLine(QPointF(s * 0.64, s * 0.36), QPointF(s * 0.50, s * 0.22))
        else:
            p.drawLine(QPointF(s * 0.50, s * 0.22), QPointF(s * 0.50, s * 0.58))
            p.drawLine(QPointF(s * 0.36, s * 0.44), QPointF(s * 0.50, s * 0.58))
            p.drawLine(QPointF(s * 0.64, s * 0.44), QPointF(s * 0.50, s * 0.58))

    elif name == "delete":
        p.setPen(pen(c, 1.5))
        p.drawLine(QPointF(s * 0.28, s * 0.32), QPointF(s * 0.72, s * 0.32))
        rounded(QRectF(s * 0.32, s * 0.36, s * 0.36, s * 0.42), s * 0.05, QColor(255, 255, 255, 30), c, 1.3)
        p.setPen(pen(a, 1.4))
        p.drawLine(QPointF(s * 0.43, s * 0.46), QPointF(s * 0.43, s * 0.68))
        p.drawLine(QPointF(s * 0.57, s * 0.46), QPointF(s * 0.57, s * 0.68))

    elif name == "refresh":
        p.setPen(pen(a, 2.0))
        p.drawArc(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), 40 * 16, 255 * 16)
        p.drawLine(QPointF(s * 0.74, s * 0.26), QPointF(s * 0.80, s * 0.45))
        p.drawLine(QPointF(s * 0.74, s * 0.26), QPointF(s * 0.55, s * 0.29))

    elif name == "up":
        p.setPen(pen(a, 2.2))
        p.drawLine(QPointF(s * 0.50, s * 0.24), QPointF(s * 0.50, s * 0.74))
        p.drawLine(QPointF(s * 0.32, s * 0.42), QPointF(s * 0.50, s * 0.24))
        p.drawLine(QPointF(s * 0.68, s * 0.42), QPointF(s * 0.50, s * 0.24))

    elif name == "add":
        p.setPen(pen(a, 2.3))
        p.drawLine(QPointF(s * 0.50, s * 0.25), QPointF(s * 0.50, s * 0.75))
        p.drawLine(QPointF(s * 0.25, s * 0.50), QPointF(s * 0.75, s * 0.50))

    else:
        p.setPen(pen(a, 2.0))
        p.drawEllipse(QRectF(s * 0.24, s * 0.24, s * 0.52, s * 0.52))

    p.end()
    return pm


def icon(name, size=24, fg="#0f172a", accent="#10a37f", bg="transparent"):
    return QIcon(pixmap(name, size, fg, accent, bg))


def decorate_button(button, name, size=16, fg="#ffffff", accent="#ffffff"):
    button.setIcon(icon(name, size, fg=fg, accent=accent))
    button.setIconSize(QSize(size, size))
    return button
