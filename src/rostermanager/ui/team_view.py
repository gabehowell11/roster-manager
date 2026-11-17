"""The team view: one team's roster on a football field, offense or defense."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rostermanager.models import Roster, Unit
from rostermanager.ui.field_view import FieldView

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
        self.title.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.unit_buttons: dict[Unit, QPushButton] = {}
        self.unit_group = QButtonGroup(self)
        self.unit_group.setExclusive(True)
        header = QHBoxLayout()
        header.addWidget(self.back_button)
        header.addWidget(self.title, stretch=1)
        for unit in SHOWN_UNITS:
            button = QPushButton(unit.value.replace("_", " ").title())
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, u=unit: self.show_unit(u))
            self.unit_group.addButton(button)
            self.unit_buttons[unit] = button
            header.addWidget(button)
        self.unit_buttons[self.unit].setChecked(True)

        self.field = FieldView()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.field)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(scroll, stretch=1)

    def set_roster(self, roster: Roster) -> None:
        """Show this roster, starting on offense."""
        self.roster = roster
        self.title.setText(f"{roster.team.name} ({roster.team.abbreviation})")
        self.show_unit(Unit.OFFENSE)

    def show_unit(self, unit: Unit) -> None:
        """Switch the field between offense and defense."""
        self.unit = unit
        self.unit_buttons[unit].setChecked(True)
        if self.roster is not None:
            self.field.set_depth_chart(self.roster.depth_chart(unit), self.roster.team)
