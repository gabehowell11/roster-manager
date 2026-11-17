"""The team view: one team's roster on a football field, offense or defense."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rostermanager.models import Roster, Unit
from rostermanager.ui.field_view import FieldView
from rostermanager.ui.theme import team_title_color

SHOWN_UNITS = (Unit.OFFENSE, Unit.DEFENSE)


class TeamView(QWidget):
    """Shows one roster. Emits back_requested when the user wants the home screen."""

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.roster: Roster | None = None
        self.unit = Unit.OFFENSE

        self.back_button = QPushButton("< Teams")
        self.back_button.clicked.connect(self.back_requested.emit)

        self.title = QLabel()
        self.title.setObjectName("TeamTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.unit_buttons: dict[Unit, QPushButton] = {}
        self.unit_group = QButtonGroup(self)
        self.unit_group.setExclusive(True)
        toggles = QHBoxLayout()
        toggles.setSpacing(6)
        toggles.addStretch()
        for unit in SHOWN_UNITS:
            button = QPushButton(unit.value.replace("_", " ").title())
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, u=unit: self.show_unit(u))
            self.unit_group.addButton(button)
            self.unit_buttons[unit] = button
            toggles.addWidget(button)
        self.unit_buttons[self.unit].setChecked(True)

        # Three equal columns keep the title centered on the window, not between buttons.
        header = QGridLayout()
        header.addWidget(self.back_button, 0, 0, Qt.AlignmentFlag.AlignLeft)
        header.addWidget(self.title, 0, 1)
        header.addLayout(toggles, 0, 2)
        for column in range(3):
            header.setColumnStretch(column, 1)

        self.field = FieldView()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.field)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(scroll, stretch=1)

    def set_roster(self, roster: Roster) -> None:
        """Show this roster, starting on offense."""
        self.roster = roster
        self.title.setText(roster.team.name)
        self.title.setStyleSheet(f"color: {team_title_color(roster.team)};")
        self.show_unit(Unit.OFFENSE)

    def show_unit(self, unit: Unit) -> None:
        """Switch the field between offense and defense."""
        self.unit = unit
        self.unit_buttons[unit].setChecked(True)
        if self.roster is not None:
            self.field.set_depth_chart(self.roster.depth_chart(unit), self.roster.team)
