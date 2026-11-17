"""The home screen: saved teams, downloading a real NFL team, importing a custom file."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rostermanager.models import Roster, Team
from rostermanager.services import (
    NFL_TEAM_ABBREVIATIONS,
    RosterImportError,
    RosterService,
)
from rostermanager.ui.background import BackgroundRunner
from rostermanager.ui.team_dialog import TeamDialog


class HomeScreen(QWidget):
    """Lists saved teams. Emits team_selected with the team abbreviation."""

    team_selected = Signal(str)

    def __init__(
        self,
        service: RosterService,
        runner: BackgroundRunner | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.runner = runner if runner is not None else BackgroundRunner()

        title = QLabel("Roster Manager")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        disclaimer = QLabel("Not affiliated with or endorsed by the NFL.")
        disclaimer.setObjectName("Muted")
        disclaimer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Saved teams
        self.team_list = QListWidget()
        self.team_list.itemActivated.connect(self._open_item)
        self.team_list.itemSelectionChanged.connect(self._update_buttons)
        self.empty_label = QLabel("No saved teams yet. Download one or import a file below.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.open_button = QPushButton("Open team")
        self.open_button.clicked.connect(self._open_selected)
        open_row = _centered(self.open_button)

        self.empty_label.setObjectName("Muted")
        saved = QGroupBox("Saved teams")
        saved_layout = QVBoxLayout(saved)
        saved_layout.addWidget(self.team_list)
        saved_layout.addWidget(self.empty_label)
        saved_layout.addLayout(open_row)

        # Download a real team
        self.team_picker = QComboBox()
        self.team_picker.addItems(NFL_TEAM_ABBREVIATIONS)
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        download = QGroupBox("Real NFL team (needs internet once)")
        download.setLayout(_centered(self.team_picker, self.download_button))

        # Import a custom roster
        self.import_button = QPushButton("Import CSV or JSON...")
        self.import_button.clicked.connect(self.start_import)
        custom = QGroupBox("Custom roster")
        custom.setLayout(_centered(self.import_button))

        self.status_label = QLabel()
        self.status_label.setObjectName("Status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.team_picker.setMinimumWidth(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(disclaimer)
        layout.addWidget(saved, stretch=1)
        layout.addWidget(download)
        layout.addWidget(custom)
        layout.addWidget(self.status_label)

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

    # Download

    def start_download(self) -> None:
        """Download the picked team in the background."""
        abbreviation = self.team_picker.currentText()
        self.download_button.setEnabled(False)
        self.status_label.setText(f"Downloading {abbreviation}...")
        self.runner.run(
            lambda: self.service.download_nfl_team(abbreviation),
            on_done=self._download_done,
            on_error=self._download_failed,
        )

    def _download_done(self, roster: Roster) -> None:
        self.download_button.setEnabled(True)
        self.status_label.setText(f"Saved {roster.team.name} ({len(roster.players)} players).")
        self.refresh()
        self._select(roster.team.abbreviation)

    def _download_failed(self, error: Exception) -> None:
        self.download_button.setEnabled(True)
        self.status_label.setText("Download failed.")
        self.show_error("Download failed", str(error))

    # Import

    def start_import(self) -> None:
        """Pick a file, ask for a team if it is a CSV, then import it."""
        path = self.choose_file()
        if path is None:
            return
        team = None
        if path.suffix.lower() == ".csv":
            team = self.ask_team()
            if team is None:
                return
        try:
            roster = self.service.import_custom_file(path, team)
        except RosterImportError as error:
            self.status_label.setText("Import failed.")
            self.show_error(f"Could not import {path.name}", "\n".join(error.problems))
            return
        self.status_label.setText(f"Imported {roster.team.name} ({len(roster.players)} players).")
        self.refresh()
        self._select(roster.team.abbreviation)

    # Dialogs, separate so tests can replace them

    def choose_file(self) -> Path | None:
        name, _ = QFileDialog.getOpenFileName(
            self, "Import roster", "", "Roster files (*.csv *.json);;All files (*)"
        )
        return Path(name) if name else None

    def ask_team(self) -> Team | None:
        dialog = TeamDialog(self)
        return dialog.team if dialog.exec() == QDialog.DialogCode.Accepted else None

    def show_error(self, title: str, details: str) -> None:
        """Every problem is listed in the message itself, not hidden behind a button."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(details)
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.exec()

    # Selection

    def _select(self, abbreviation: str) -> None:
        for row in range(self.team_list.count()):
            item = self.team_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == abbreviation:
                self.team_list.setCurrentItem(item)
                return

    def _update_buttons(self) -> None:
        self.open_button.setEnabled(bool(self.team_list.selectedItems()))

    def _open_selected(self) -> None:
        items = self.team_list.selectedItems()
        if items:
            self._open_item(items[0])

    def _open_item(self, item: QListWidgetItem) -> None:
        self.team_selected.emit(item.data(Qt.ItemDataRole.UserRole))


def _centered(*widgets: QWidget) -> QHBoxLayout:
    """A row with the widgets in the middle."""
    row = QHBoxLayout()
    row.addStretch()
    for widget in widgets:
        row.addWidget(widget)
    row.addStretch()
    return row
