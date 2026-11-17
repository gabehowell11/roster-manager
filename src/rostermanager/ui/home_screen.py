"""The home screen: the list of saved teams."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rostermanager.services import RosterService


class HomeScreen(QWidget):
    """Lists saved teams. Emits team_selected with the team abbreviation."""

    team_selected = Signal(str)

    def __init__(self, service: RosterService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service

        title = QLabel("Roster Manager")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        self.team_list = QListWidget()
        self.team_list.itemActivated.connect(self._open_item)
        self.team_list.itemSelectionChanged.connect(self._update_buttons)

        self.empty_label = QLabel("No saved teams yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.open_button = QPushButton("Open team")
        self.open_button.clicked.connect(self._open_selected)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.open_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(QLabel("Saved teams"))
        layout.addWidget(self.team_list)
        layout.addWidget(self.empty_label)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Reload the saved teams from the service."""
        self.team_list.clear()
        for team in self.service.list_teams():
            item = QListWidgetItem(f"{team.name} ({team.abbreviation})")
            item.setData(Qt.ItemDataRole.UserRole, team.abbreviation)
            self.team_list.addItem(item)
        has_teams = self.team_list.count() > 0
        self.team_list.setVisible(has_teams)
        self.empty_label.setVisible(not has_teams)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.open_button.setEnabled(bool(self.team_list.selectedItems()))

    def _open_selected(self) -> None:
        items = self.team_list.selectedItems()
        if items:
            self._open_item(items[0])

    def _open_item(self, item: QListWidgetItem) -> None:
        self.team_selected.emit(item.data(Qt.ItemDataRole.UserRole))
