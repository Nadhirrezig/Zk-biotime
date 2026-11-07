"""Dashboard for the chosen date: a presence hero card plus anomaly cards.

Every card and legend chip is a filter for the table below (mouse, Enter or Space); the
active filter is shown as a selected card. Colour is reserved for counts above zero.
"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, QLocale, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from zkreport.engine import Summary

from . import labels_fr as fr
from . import theme as t

FRENCH = QLocale(QLocale.Language.French, QLocale.Country.Tunisia)


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)} %" if whole else "—"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _label(text: str, size: int, colour: str, weight: int = 400, caps: bool = False) -> QLabel:
    label = QLabel(text)
    spacing = "letter-spacing: 0.6px;" if caps else ""
    label.setStyleSheet(f"font-size: {size}px; font-weight: {weight}; color: {colour};"
                        f" background: transparent; {spacing}")
    return label


class _Clickable(QFrame):
    """Card/chip base: hover, keyboard focus, selected state, emits its filter."""

    activated = pyqtSignal(str)

    def __init__(self, filter_key: str, tone: t.Tone, radius: int, parent=None):
        super().__init__(parent)
        self.filter_key = filter_key
        self._tone = tone
        self._radius = radius
        self._selected = False
        self.setObjectName("clickable")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._restyle()

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self._restyle()

    def is_selected(self) -> bool:
        return self._selected

    def _restyle(self) -> None:
        border = self._tone.solid if self._selected else t.BORDER
        background = self._tone.tint if self._selected else t.SURFACE
        hover = self._tone.solid if self._selected else t.BORDER_HOVER
        self.setStyleSheet(
            f"#clickable {{ background: {background}; border: 1px solid {border};"
            f" border-radius: {self._radius}px; }}"
            f"#clickable:hover {{ border-color: {hover}; }}"
            f"#clickable:focus {{ border: 1px solid {t.FOCUS}; }}"
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.activated.emit(self.filter_key)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit(self.filter_key)
            return
        super().keyPressEvent(event)


class SegmentBar(QWidget):
    """Rounded stacked bar: [(value, colour), ...] over a grey track."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[tuple[int, str]] = []
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_segments(self, segments: list[tuple[int, str]]) -> None:
        self._segments = [(v, c) for v, c in segments if v > 0]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setClipPath(clip)
        painter.fillRect(rect, QColor(t.TRACK))
        total = sum(v for v, _ in self._segments)
        x = rect.left()
        gap = 2.0
        for i, (value, colour) in enumerate(self._segments):
            width = rect.width() * value / total if total else 0
            last = i == len(self._segments) - 1
            painter.fillRect(QRectF(x, rect.top(), max(width - (0 if last else gap), 0),
                                    rect.height()), QColor(colour))
            x += width


class StatusIcon(QWidget):
    """Small painted glyph on a tinted rounded square (no font/emoji dependency)."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._tone = t.NEUTRAL
        self.setFixedSize(30, 30)

    def set_tone(self, tone: t.Tone) -> None:
        self._tone = tone
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._tone.tint))
        p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        colour = QColor(self._tone.solid)
        pen = QPen(colour, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        circle = QRectF(8, 8, 14, 14)
        p.drawEllipse(circle)
        cx, cy = circle.center().x(), circle.center().y()
        if self._kind == "single":      # half-filled circle: one of two punches
            p.setBrush(colour)
            p.drawPie(circle, 90 * 16, 180 * 16)
        elif self._kind == "late":      # clock
            p.drawLine(int(cx), int(cy), int(cx), int(cy - 4.5))
            p.drawLine(int(cx), int(cy), int(cx + 3.5), int(cy + 1))
        elif self._kind == "absent":    # crossed circle
            d = 3.2
            p.drawLine(int(cx - d), int(cy - d), int(cx + d), int(cy + d))
            p.drawLine(int(cx + d), int(cy - d), int(cx - d), int(cy + d))


class LegendChip(_Clickable):
    HEIGHT = 26  # Qt ignores a border radius above half the height: keep radius < 13

    def __init__(self, filter_key: str, tone: t.Tone, parent=None):
        super().__init__(filter_key, tone, radius=12, parent=parent)
        self._chip_tone = tone
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 12, 0)
        layout.setSpacing(6)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.text = _label("", 12, t.TEXT)
        layout.addWidget(self.dot)
        layout.addWidget(self.text)
        self.set_count_text(0, "")

    def set_count_text(self, count: int, text: str) -> None:
        """Zero counts are muted so they do not compete with real figures."""
        colour = self._chip_tone.solid if count else t.BORDER_HOVER
        self.dot.setStyleSheet(f"background: {colour}; border-radius: 4px;")
        self.text.setStyleSheet(f"font-size: 12px; background: transparent;"
                                f" color: {t.TEXT if count else t.TEXT_MUTED};")
        self.text.setText(text)


class PresenceCard(_Clickable):
    """Hero: present / expected, rate, segmented composition, legend chips."""

    def __init__(self, parent=None):
        super().__init__(fr.FILTER_PRESENT, t.PRESENT, radius=12, parent=parent)
        self.setToolTip("Cliquez pour n'afficher que les présents")
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(_label("PRÉSENTS", 11, t.TEXT_MUTED, 600, caps=True))
        header.addStretch(1)
        self.day_label = _label("", 12, t.TEXT_MUTED)
        header.addWidget(self.day_label)
        root.addLayout(header)

        figures = QHBoxLayout()
        figures.setSpacing(6)
        self.present = _label("–", 34, t.TEXT, 600)
        self.expected = _label("", 15, t.TEXT_MUTED)
        figures.addWidget(self.present, 0, Qt.AlignmentFlag.AlignBottom)
        figures.addWidget(self.expected, 0, Qt.AlignmentFlag.AlignBottom)
        figures.addStretch(1)
        rate_box = QVBoxLayout()
        rate_box.setSpacing(0)
        self.rate = _label("—", 22, t.PRESENT.text, 600)
        self.rate.setAlignment(Qt.AlignmentFlag.AlignRight)
        rate_caption = _label("taux de présence", 11, t.TEXT_MUTED)
        rate_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        rate_box.addWidget(self.rate)
        rate_box.addWidget(rate_caption)
        figures.addLayout(rate_box)
        root.addLayout(figures)

        self.bar = SegmentBar()
        root.addWidget(self.bar)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chips = {
            fr.FILTER_TWICE: LegendChip(fr.FILTER_TWICE, t.COMPLETE),
            fr.FILTER_ONCE: LegendChip(fr.FILTER_ONCE, t.SINGLE),
            fr.FILTER_ABSENT: LegendChip(fr.FILTER_ABSENT, t.ABSENT),
        }
        for chip in self.chips.values():
            chips.addWidget(chip)
        chips.addStretch(1)
        root.addLayout(chips)

    def update_from(self, s: Summary | None, day: date | None, holiday: str | None) -> None:
        day_text = FRENCH.toString(QDate(day.year, day.month, day.day), "dddd d MMMM yyyy") \
            if day else ""
        self.day_label.setText(f"{day_text} · {holiday}" if holiday else day_text)
        if s is None:
            self.present.setText("–")
            self.expected.setText("")
            self.rate.setText("—")
            self.bar.set_segments([])
            for chip in self.chips.values():
                chip.set_count_text(0, "")
            return
        expected = s.present + s.absent
        self.present.setText(str(s.present))
        self.expected.setText(f"/ {expected} attendus" if expected else "aucun employé attendu")
        self.rate.setText(_pct(s.present, expected))
        others = s.employees - s.present - s.absent
        self.bar.set_segments([(s.complete, t.COMPLETE.solid), (s.single_punch, t.SINGLE.solid),
                               (s.absent, t.ABSENT.solid), (others, t.OTHER.solid)])
        self.chips[fr.FILTER_TWICE].set_count_text(
            s.complete, _plural(s.complete, "complet", "complets"))
        self.chips[fr.FILTER_ONCE].set_count_text(
            s.single_punch, _plural(s.single_punch, "pointage unique", "pointages uniques"))
        self.chips[fr.FILTER_ABSENT].set_count_text(
            s.absent, _plural(s.absent, "absent", "absents"))


class AnomalyCard(_Clickable):
    def __init__(self, filter_key: str, title: str, icon: str, tone: t.Tone, tip: str,
                 parent=None):
        super().__init__(filter_key, tone, radius=12, parent=parent)
        self.tone = tone
        self.setToolTip(tip)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(4)
        header = QHBoxLayout()
        self.icon = StatusIcon(icon)
        header.addWidget(_label(title.upper(), 11, t.TEXT_MUTED, 600, caps=True))
        header.addStretch(1)
        header.addWidget(self.icon)
        root.addLayout(header)
        self.value = _label("–", 30, t.TEXT, 600)
        self.caption = _label("", 12, t.TEXT_MUTED)
        root.addWidget(self.value)
        root.addWidget(self.caption)
        root.addStretch(1)

    def update_value(self, value: int | None, caption: str) -> None:
        if value is None:
            self.value.setText("–")
            self.caption.setText("")
            self.icon.set_tone(t.NEUTRAL)
            return
        active = value > 0
        self.value.setText(str(value))
        self.value.setStyleSheet(
            f"font-size: 30px; font-weight: 600; background: transparent;"
            f" color: {self.tone.text if active else t.TEXT_MUTED};")
        self.caption.setText(caption if active else "Aucun")
        self.icon.set_tone(self.tone if active else t.NEUTRAL)


class Dashboard(QWidget):
    filter_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hero = PresenceCard()
        self.cards = {
            fr.FILTER_ONCE: AnomalyCard(
                fr.FILTER_ONCE, "Un seul pointage", "single", t.SINGLE,
                "Employés avec une seule pointe : arrivée ou départ manquant"),
            fr.FILTER_LATE: AnomalyCard(
                fr.FILTER_LATE, "En retard", "late", t.LATE,
                "Arrivées après l'heure de début + tolérance"),
            fr.FILTER_ABSENT: AnomalyCard(
                fr.FILTER_ABSENT, "Absents", "absent", t.ABSENT,
                "Jour travaillé sans aucun pointage (hors congé et férié)"),
        }
        self.context = _label("", 12, t.TEXT_MUTED)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.hero, 5)
        for card in self.cards.values():
            row.addWidget(card, 2)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(row)
        layout.addWidget(self.context)

        for widget in self._clickables():
            widget.activated.connect(self._on_activated)
        self._values: dict[str, str] = {}
        self._active = fr.FILTER_ALL
        self.set_summary(None)

    def _clickables(self) -> list[_Clickable]:
        return [self.hero, *self.hero.chips.values(), *self.cards.values()]

    def _on_activated(self, key: str) -> None:
        # Clicking the active filter again clears it.
        self.filter_requested.emit(fr.FILTER_ALL if key == self._active else key)

    def set_active_filter(self, key: str) -> None:
        self._active = key
        for widget in self._clickables():
            widget.set_selected(widget.filter_key == key)

    def set_summary(self, s: Summary | None, day: date | None = None,
                    holiday: str | None = None) -> None:
        self.hero.update_from(s, day, holiday)
        if s is None:
            for card in self.cards.values():
                card.update_value(None, "")
            self.context.setText("")
            self._values = {}
            return
        expected = s.present + s.absent
        self.cards[fr.FILTER_ONCE].update_value(
            s.single_punch, f"{_pct(s.single_punch, s.present)} des présents")
        self.cards[fr.FILTER_LATE].update_value(s.late, f"{_pct(s.late, s.present)} des présents")
        self.cards[fr.FILTER_ABSENT].update_value(s.absent, f"{_pct(s.absent, expected)} des attendus")
        self.context.setText(
            f"Effectif : {s.employees}   ·   Congé : {s.leave}   ·   Férié : {s.holiday}"
            f"   ·   Repos : {s.rest}   ·   Cliquez sur une carte pour filtrer le tableau")
        self._values = {k: str(getattr(s, k)) for k in (
            "employees", "present", "complete", "single_punch", "late", "absent",
            "leave", "holiday", "rest")}

    def value(self, key: str) -> str:
        return self._values.get(key, "–")
