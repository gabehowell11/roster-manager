"""FieldView: one unit drawn on a football field, each slot as a stack of cards."""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget

from rostermanager.models import DepthChart, Player, Team, Unit
from rostermanager.services import FieldSpot, layout_depth_chart
from rostermanager.services.field_layout import (
    DEFENSE_LINE,
    OFFENSE_LINE,
    SPECIAL_TEAMS_LINE,
)
from rostermanager.services.formations import Formation, fill_formation
from rostermanager.ui.player_card import STARTER_SIZE, PlayerCard
from rostermanager.ui.theme import MUTED_TEXT

MAX_BACKUPS_SHOWN = 3
BACKUP_PEEK = 16  # pixels of each backup showing past the card in front of it
MIN_FIELD_SIZE = (1000, 600)

# Muted greens so the field sits calmly on the dark blue theme.
_GRASS = QColor("#2D5E3A")
_GRASS_STRIPE = QColor("#316640")
_LINE = QColor(255, 255, 255, 110)


class FieldView(QWidget):
    """Draws a depth chart on a field.

    The starter card sits in front at the slot's spot. Up to MAX_BACKUPS_SHOWN
    backups sit straight behind it, peeking out away from the line of scrimmage:
    downward on offense, upward on defense. Hovering a backup lifts it in front of
    the stack so its whole card shows; moving off it puts the stack back. Hover a
    card for full details; click it to emit player_clicked with the Player.
    """

    player_clicked = Signal(object)
    action_requested = Signal(object, str)  # (Player, "edit" | "starter" | "up" | "down")
    swap_requested = Signal(object, object)  # (dragged PlayerKey, target PlayerKey)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(*MIN_FIELD_SIZE)
        self.chart: DepthChart | None = None
        self.spots: dict[str, FieldSpot] = {}
        self.slot_cards: dict[str, list[PlayerCard]] = {}  # starter first
        self.open_cards: dict[str, QLabel] = {}  # formation roles nobody can fill
        self.formation: Formation | None = None
        self.lifted: tuple[str, PlayerCard] | None = None  # (slot, backup) lifted by hover

        self.empty_label = QLabel(self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: white; font-size: 16px;")
        self.empty_label.hide()

    def set_depth_chart(
        self, chart: DepthChart, team: Team, formation: Formation | None = None
    ) -> None:
        """Replace the cards with this depth chart's players.

        With no formation every slot is shown where field_layout puts it. With a
        formation, each role shows the player filling it, and roles nobody can fill
        show an open placeholder.
        """
        for widget in [
            *(c for cards in self.slot_cards.values() for c in cards),
            *self.open_cards.values(),
        ]:
            # Detach now so old cards vanish immediately; Qt frees them later.
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self.slot_cards = {}
        self.open_cards = {}
        self.lifted = None
        self.chart = chart
        self.formation = formation

        groups: list[tuple[str, list[Player]]]
        if formation is None:
            self.spots = layout_depth_chart(chart)
            groups = list(chart.slots.items())
        else:
            filled = fill_formation(chart, formation)
            self.spots = {entry.role.label: entry.role.spot for entry in filled}
            groups = [(entry.role.label, entry.players) for entry in filled]

        slot_sizes = {label: len(players) for label, players in chart.slots.items()}
        for label, players in groups:
            if not players:
                self.open_cards[label] = _open_card(label, self)
                continue
            shown = players[: MAX_BACKUPS_SHOWN + 1]
            cards = [PlayerCard(p, team, starter=i == 0, parent=self) for i, p in enumerate(shown)]
            for card in cards:
                card.slot_size = slot_sizes[card.player.position]
                card.clicked.connect(self.player_clicked.emit)
                card.action_requested.connect(self.action_requested.emit)
                card.swap_requested.connect(self.swap_requested.emit)
                card.hover_changed.connect(
                    lambda entered, label=label, card=card: self._hover_changed(
                        label, card, entered
                    )
                )
            self.slot_cards[label] = cards
            self._restack(label)
            for card in cards:
                card.show()

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

    def _restack(self, label: str) -> None:
        """Default order: later-raised widgets draw on top, so deepest backup first."""
        for card in reversed(self.slot_cards[label]):
            card.raise_()

    def _hover_changed(self, label: str, card: PlayerCard, entered: bool) -> None:
        if entered:
            self._drop_lifted()
            if not card.is_starter:
                card.raise_()
                self.lifted = (label, card)
        elif self.lifted is not None and self.lifted[1] is card:
            # Only the lifted card's own leave restores the stack, so a late leave
            # from a neighbour can't hide a card that was just lifted.
            self._drop_lifted()

    def _drop_lifted(self) -> None:
        if self.lifted is not None:
            label, _ = self.lifted
            self.lifted = None
            if label in self.slot_cards:
                self._restack(label)

    def _backup_direction(self) -> int:
        return -1 if self.chart is not None and self.chart.unit is Unit.DEFENSE else 1

    def _position_cards(self) -> None:
        width, height = self.width(), self.height()
        downward = self._backup_direction() > 0
        starter_w, starter_h = STARTER_SIZE
        for label, placeholder in self.open_cards.items():
            spot = self.spots[label]
            left = _clamp(round(spot.x * width) - starter_w // 2, 0, width - starter_w)
            top = _clamp(round(spot.y * height) - starter_h // 2, 0, height - starter_h)
            placeholder.move(left, top)
        for label, cards in self.slot_cards.items():
            spot = self.spots[label]
            # Clamp the starter so the whole stack stays inside the field.
            spread = BACKUP_PEEK * (len(cards) - 1)
            min_top, max_top = (
                (0, height - starter_h - spread) if downward else (spread, height - starter_h)
            )
            left = _clamp(round(spot.x * width) - starter_w // 2, 0, width - starter_w)
            top = _clamp(round(spot.y * height) - starter_h // 2, min_top, max_top)
            for depth, card in enumerate(cards):
                # Backups are smaller: center them under the starter, and line up their
                # far edge with the starter's before stepping them straight outward.
                x = left + (starter_w - card.width()) // 2
                if downward:
                    y = top + starter_h - card.height() + BACKUP_PEEK * depth
                else:
                    y = top - BACKUP_PEEK * depth
                card.move(x, y)

    def line_of_scrimmage_y(self) -> int | None:
        """Pixel row of the line of scrimmage, or None before a chart is set."""
        if self.chart is None:
            return None
        gap = STARTER_SIZE[1] // 2 + 6
        if self.chart.unit is Unit.DEFENSE:
            return round(DEFENSE_LINE * self.height()) + gap
        line = OFFENSE_LINE if self.chart.unit is Unit.OFFENSE else SPECIAL_TEAMS_LINE
        return round(line * self.height()) - gap

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


def _open_card(label: str, parent: QWidget) -> QLabel:
    """A dashed placeholder for a formation role with no player to fill it."""
    card = QLabel(f"{label}\nopen", parent)
    card.setAlignment(Qt.AlignmentFlag.AlignCenter)
    card.setFixedSize(*STARTER_SIZE)
    card.setToolTip(f"No player on the roster can fill {label} in this formation.")
    card.setStyleSheet(
        f"border: 2px dashed {MUTED_TEXT}; border-radius: 8px;"
        f" color: {MUTED_TEXT}; background: rgba(0, 0, 0, 40); font-weight: 600;"
    )
    card.show()
    return card
