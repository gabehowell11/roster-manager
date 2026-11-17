"""The team view: one team's roster. The field drawing is added in a later issue."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from rostermanager.models import Roster


class TeamView(QWidget):
    """Shows one roster. Emits back_requested when the user wants the home screen."""

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.roster: Roster | None = None

        self.back_button = QPushButton("< Teams")
        self.back_button.clicked.connect(self.back_requested.emit)

        self.title = QLabel()
        self.title.setStyleSheet("font-size: 20px; font-weight: bold;")

        header = QHBoxLayout()
        header.addWidget(self.back_button)
        header.addWidget(self.title, stretch=1)

        self.body = QVBoxLayout()

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addLayout(self.body, stretch=1)

    def set_roster(self, roster: Roster) -> None:
        """Show this roster."""
        self.roster = roster
        self.title.setText(f"{roster.team.name} ({roster.team.abbreviation})")
