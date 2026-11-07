"""Small line icons painted with QPainter: identical on every machine, no image files."""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

SIZE = 18


def icon(kind: str, colour: str, size: int = SIZE) -> QIcon:
    pixmap = QPixmap(size * 2, size * 2)  # 2x for crisp rendering on HiDPI
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2.0)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(colour), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.scale(size / 18, size / 18)
    _DRAW[kind](p, QColor(colour))
    p.end()
    return QIcon(pixmap)


def _calendar(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(3, 4, 12, 11), 2.5, 2.5)
    p.drawLine(QPointF(3, 7.5), QPointF(15, 7.5))
    p.drawLine(QPointF(6.5, 2.5), QPointF(6.5, 5))
    p.drawLine(QPointF(11.5, 2.5), QPointF(11.5, 5))


def _user(p: QPainter, c: QColor) -> None:
    p.drawEllipse(QRectF(6, 2.5, 6, 6))
    path = QPainterPath()
    path.moveTo(3, 15.5)
    path.cubicTo(3, 11, 15, 11, 15, 15.5)
    p.drawPath(path)


def _settings(p: QPainter, c: QColor) -> None:
    p.drawEllipse(QRectF(6.5, 6.5, 5, 5))
    for i in range(8):
        a = i * math.pi / 4
        p.drawLine(QPointF(9 + 4.6 * math.cos(a), 9 + 4.6 * math.sin(a)),
                   QPointF(9 + 6.6 * math.cos(a), 9 + 6.6 * math.sin(a)))


def _refresh(p: QPainter, c: QColor) -> None:
    p.drawArc(QRectF(3.5, 3.5, 11, 11), 30 * 16, 290 * 16)
    p.drawLine(QPointF(14.2, 3.2), QPointF(14.2, 6.6))
    p.drawLine(QPointF(14.2, 6.6), QPointF(10.8, 6.6))


def _chevron_left(p: QPainter, c: QColor) -> None:
    p.drawPolyline([QPointF(11, 4), QPointF(6, 9), QPointF(11, 14)])


def _chevron_right(p: QPainter, c: QColor) -> None:
    p.drawPolyline([QPointF(7, 4), QPointF(12, 9), QPointF(7, 14)])


def _chevron_down(p: QPainter, c: QColor) -> None:
    p.drawPolyline([QPointF(5, 7), QPointF(9, 11), QPointF(13, 7)])


def _download(p: QPainter, c: QColor) -> None:
    p.drawLine(QPointF(9, 3), QPointF(9, 11.5))
    p.drawPolyline([QPointF(5.5, 8), QPointF(9, 11.5), QPointF(12.5, 8)])
    p.drawLine(QPointF(3.5, 15), QPointF(14.5, 15))


def _search(p: QPainter, c: QColor) -> None:
    p.drawEllipse(QRectF(3, 3, 9, 9))
    p.drawLine(QPointF(10.8, 10.8), QPointF(15, 15))


def _sheet(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(3, 3, 12, 12), 2, 2)
    p.drawLine(QPointF(3, 7), QPointF(15, 7))
    p.drawLine(QPointF(7.5, 7), QPointF(7.5, 15))


def _file(p: QPainter, c: QColor) -> None:
    path = QPainterPath()
    path.moveTo(5, 2.5)
    path.lineTo(10.5, 2.5)
    path.lineTo(14, 6)
    path.lineTo(14, 15.5)
    path.lineTo(5, 15.5)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(7, 10), QPointF(12, 10))
    p.drawLine(QPointF(7, 12.5), QPointF(11, 12.5))


def _printer(p: QPainter, c: QColor) -> None:
    p.drawRect(QRectF(5.5, 2.5, 7, 4))
    p.drawRoundedRect(QRectF(2.5, 6.5, 13, 6), 1.5, 1.5)
    p.drawRect(QRectF(5.5, 10.5, 7, 5))


_DRAW = {
    "calendar": _calendar, "user": _user, "settings": _settings, "refresh": _refresh,
    "chevron-left": _chevron_left, "chevron-right": _chevron_right,
    "chevron-down": _chevron_down, "download": _download, "search": _search,
    "sheet": _sheet, "file": _file, "printer": _printer,
}
