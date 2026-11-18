"""RosterPanel: the whole roster as a scrolling list, shown over the right side of a team."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rostermanager.models import Player, Roster, Unit
from rostermanager.services.roster_list import roster_groups
from rostermanager.ui.theme import team_title_color

UNIT_TITLES = {
    Unit.OFFENSE: "Offense",
    Unit.DEFENSE: "Defense",
    Unit.SPECIAL_TEAMS: "Special teams",
}
WIDTH_SHARE = 0.27  # of the window: "roughly a quarter"
MIN_WIDTH = 260


class RosterPanel(QFrame):
    """Name, position, and rating for every player, grouped by position.

    Starters are bold at the top of each group. Emits close_requested when its
    close button is clicked; the team view decides what to do.
    """

    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RosterPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(-4, 0)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)

        self.title = QLabel("Roster")
        self.title.setObjectName("PanelTitle")
        self.count_label = QLabel()
        self.count_label.setObjectName("Muted")
        self.close_button = QPushButton("✕")  # a plain X
        self.close_button.setObjectName("PanelClose")
        self.close_button.setToolTip("Close the roster (Esc)")
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(self.close_requested.emit)
        top = QHBoxLayout()
        top.addWidget(self.title)
        top.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignBottom)
        top.addStretch()
        top.addWidget(self.close_button)

        self.rows = QWidget()
        self.rows.setObjectName("RosterRows")
        self.grid = QGridLayout(self.rows)
        self.grid.setContentsMargins(0, 0, 4, 12)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(2)
        self.grid.setColumnStretch(0, 1)
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_scroll.setWidget(self.rows)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 8, 0)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self.list_scroll, stretch=1)

        self.player_rows: list[tuple[Player, QLabel, QLabel, QLabel]] = []

    def set_roster(self, roster: Roster) -> None:
        """Rebuild the list for this roster."""
        while (item := self.grid.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.player_rows = []
        accent = team_title_color(roster.team)
        plural = "" if len(roster.players) == 1 else "s"
        self.count_label.setText(f"{len(roster.players)} player{plural}")

        row = 0
        for column, text in enumerate(("Name", "Pos", "Rating")):
            header = QLabel(text)
            header.setObjectName("ColumnHeader")
            if column:
                header.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.grid.addWidget(header, row, column)
        row += 1

        unit: Unit | None = None
        for group in roster_groups(roster):
            if group.unit is not unit:
                unit = group.unit
                heading = QLabel(UNIT_TITLES[unit].upper())
                heading.setObjectName("UnitHeading")
                heading.setStyleSheet(f"color: {accent};")
                self.grid.addWidget(heading, row, 0, 1, 3)
                row += 1
            group_label = QLabel(group.name)
            group_label.setObjectName("GroupHeading")
            self.grid.addWidget(group_label, row, 0, 1, 3)
            row += 1
            for player in group.players:
                self._add_player(player, row)
                row += 1

        if not roster.players:
            empty = QLabel("No players on this roster.")
            empty.setObjectName("Muted")
            self.grid.addWidget(empty, row, 0, 1, 3)
            row += 1
        self.grid.setRowStretch(row, 1)  # keep rows packed at the top

    def _add_player(self, player: Player, row: int) -> None:
        rating = str(player.rating) if player.rating is not None else "--"
        name = QLabel(player.name)
        position = QLabel(player.position)
        score = QLabel(rating)
        role = "Starter" if player.depth_order == 1 else "Backup"
        for label in (name, position, score):
            label.setObjectName(role)  # theme.py: starters bold, backups muted
        name.setToolTip(f"{player.name}, {player.position} ({role.lower()})")
        position.setAlignment(Qt.AlignmentFlag.AlignRight)
        score.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.grid.addWidget(name, row, 0)
        self.grid.addWidget(position, row, 1)
        self.grid.addWidget(score, row, 2)
        self.player_rows.append((player, name, position, score))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        super().keyPressEvent(event)

    def listed_players(self) -> list[Player]:
        """Players in the order shown."""
        return [player for player, *_ in self.player_rows]


def panel_width(window_width: int) -> int:
    """About a quarter of the window, never too narrow to read."""
    return max(MIN_WIDTH, round(window_width * WIDTH_SHARE))
