"""FieldView: one unit drawn on a football field, each slot as a stack of cards."""

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget

from rostermanager.models import DepthChart, Team, Unit
from rostermanager.services import FieldSpot, layout_depth_chart
from rostermanager.services.field_layout import DEFENSE_LINE, OFFENSE_LINE
from rostermanager.ui.player_card import STARTER_SIZE, PlayerCard

MAX_BACKUPS_SHOWN = 3
BACKUP_OFFSET = QPoint(8, 12)  # each backup peeks out this far from the one in front
MIN_FIELD_SIZE = (1000, 620)

_GRASS = QColor("#2E7D32")
_GRASS_STRIPE = QColor("#388E3C")
_LINE = QColor(255, 255, 255, 170)


class FieldView(QWidget):
    """Draws a depth chart on a field.

    The starter card sits in front at the slot's spot. Up to MAX_BACKUPS_SHOWN
    backups sit behind it, fanned away from the line of scrimmage: downward on
    offense, upward on defense. Hover a card for full details.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(*MIN_FIELD_SIZE)
        self.chart: DepthChart | None = None
        self.spots: dict[str, FieldSpot] = {}
        self.slot_cards: dict[str, list[PlayerCard]] = {}  # starter first

        self.empty_label = QLabel(self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: white; font-size: 16px;")
        self.empty_label.hide()

    def set_depth_chart(self, chart: DepthChart, team: Team) -> None:
        """Replace the cards with this depth chart's players."""
        for cards in self.slot_cards.values():
            for card in cards:
                # Detach now so old cards vanish immediately; Qt frees them later.
                card.hide()
                card.setParent(None)
                card.deleteLater()
        self.slot_cards = {}
        self.chart = chart
        self.spots = layout_depth_chart(chart)

        for label, players in chart.slots.items():
            shown = players[: MAX_BACKUPS_SHOWN + 1]
            cards = [PlayerCard(p, team, starter=i == 0, parent=self) for i, p in enumerate(shown)]
            # Later-raised widgets draw on top: deepest backup first, starter last.
            for card in reversed(cards):
                card.raise_()
                card.show()
            self.slot_cards[label] = cards

        if chart.players:
            self.empty_label.hide()
        else:
            self.empty_label.setText(f"No {chart.unit.value.replace('_', ' ')} players.")
            self.empty_label.show()
        self._position_cards()
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.empty_label.setGeometry(self.rect())
        self._position_cards()

    def _backup_direction(self) -> int:
        return -1 if self.chart is not None and self.chart.unit is Unit.DEFENSE else 1

    def _position_cards(self) -> None:
        width, height = self.width(), self.height()
        downward = self._backup_direction() > 0
        starter_w, starter_h = STARTER_SIZE
        for label, cards in self.slot_cards.items():
            spot = self.spots[label]
            # Clamp the starter so the whole fanned stack stays inside the field.
            spread_x = BACKUP_OFFSET.x() * (len(cards) - 1)
            spread_y = BACKUP_OFFSET.y() * (len(cards) - 1)
            min_top, max_top = (
                (0, height - starter_h - spread_y) if downward else (spread_y, height - starter_h)
            )
            left = _clamp(round(spot.x * width) - starter_w // 2, 0, width - starter_w - spread_x)
            top = _clamp(round(spot.y * height) - starter_h // 2, min_top, max_top)
            for depth, card in enumerate(cards):
                # Backups are smaller, so line up their far edge with the starter's and
                # step them outward; otherwise they hide completely behind it.
                x = left + starter_w - card.width() + BACKUP_OFFSET.x() * depth
                if downward:
                    y = top + starter_h - card.height() + BACKUP_OFFSET.y() * depth
                else:
                    y = top - BACKUP_OFFSET.y() * depth
                card.move(x, y)

    def line_of_scrimmage_y(self) -> int | None:
        """Pixel row of the line of scrimmage, or None for special teams."""
        if self.chart is None or self.chart.unit is Unit.SPECIAL_TEAMS:
            return None
        gap = STARTER_SIZE[1] // 2 + 6
        if self.chart.unit is Unit.OFFENSE:
            return round(OFFENSE_LINE * self.height()) - gap
        return round(DEFENSE_LINE * self.height()) + gap

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        width, height = self.width(), self.height()
        stripes = 10
        for i in range(stripes):
            top = round(i * height / stripes)
            bottom = round((i + 1) * height / stripes)
            color = _GRASS if i % 2 == 0 else _GRASS_STRIPE
            painter.fillRect(QRect(0, top, width, bottom - top), color)

        painter.setPen(QPen(_LINE, 1))
        for i in range(1, stripes):
            y = round(i * height / stripes)
            painter.drawLine(0, y, width, y)
            # hash marks a third of the way in from each sideline
            for x in (width // 3, 2 * width // 3):
                painter.drawLine(x - 6, y, x + 6, y)

        scrimmage = self.line_of_scrimmage_y()
        if scrimmage is not None:
            painter.setPen(QPen(QColor("#FFEB3B"), 3))
            painter.drawLine(0, scrimmage, width, scrimmage)
        painter.end()


def _clamp(value: int, low: int, high: int) -> int:
    """value limited to low..high; low wins if the field is too small for both."""
    return max(low, min(value, high))
