"""The home screen: saved teams, downloading a real NFL team, importing a custom file."""

from datetime import datetime
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

from rostermanager.models import Roster, RosterSource, SavedTeam, Team
from rostermanager.services import (
    NFL_TEAM_ABBREVIATIONS,
    RosterImportError,
    RosterService,
    copy_template,
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
        self.refresh_button = QPushButton("Refresh from NFL data")
        self.refresh_button.setToolTip("Download this team again to get the latest roster.")
        self.refresh_button.clicked.connect(self.start_refresh)
        self.delete_button = QPushButton("Delete team")
        self.delete_button.clicked.connect(self.delete_selected)
        open_row = _centered(self.open_button, self.refresh_button, self.delete_button)

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
        self.template_button = QPushButton("Save a template...")
        self.template_button.setToolTip("Save a blank CSV or JSON roster to fill in.")
        self.template_button.clicked.connect(self.save_template)
        custom.setLayout(_centered(self.import_button, self.template_button))

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
        self.saved: dict[str, SavedTeam] = {}
        for saved in self.service.list_saved_teams():
            team = saved.team
            self.saved[team.abbreviation] = saved
            item = QListWidgetItem(f"{team.name} ({team.abbreviation})\n{describe_saved(saved)}")
            item.setData(Qt.ItemDataRole.UserRole, team.abbreviation)
            self.team_list.addItem(item)
        has_teams = self.team_list.count() > 0
        self.team_list.setVisible(has_teams)
        self.empty_label.setVisible(not has_teams)
        self._update_buttons()

    # Download

    def start_download(self) -> None:
        """Download the picked team in the background, after asking if it replaces one."""
        self._download(self.team_picker.currentText())

    def start_refresh(self) -> None:
        """Re-download the selected real team."""
        abbreviation = self._selected_abbreviation()
        if abbreviation is not None:
            self._download(abbreviation)

    def _download(self, abbreviation: str) -> None:
        existing = self.service.saved_team(abbreviation)
        if existing is not None and not self.confirm(
            f"Replace {existing.team.name}?", replace_warning(existing)
        ):
            return
        self.download_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.status_label.setText(f"Downloading {abbreviation}...")
        self.runner.run(
            lambda: self.service.download_nfl_team(abbreviation),
            on_done=self._download_done,
            on_error=self._download_failed,
        )

    def _download_done(self, roster: Roster) -> None:
        self.download_button.setEnabled(True)
        self._update_buttons()
        self.status_label.setText(f"Saved {roster.team.name} ({len(roster.players)} players).")
        self.refresh()
        self._select(roster.team.abbreviation)

    def _download_failed(self, error: Exception) -> None:
        self.download_button.setEnabled(True)
        self._update_buttons()
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
            roster = self.service.read_custom_file(path, team)
        except RosterImportError as error:
            self.status_label.setText("Import failed.")
            self.show_error(f"Could not import {path.name}", "\n".join(error.problems))
            return
        existing = self.service.saved_team(roster.team.abbreviation)
        if existing is not None and not self.confirm(
            f"Replace {existing.team.name}?", replace_warning(existing, custom=True)
        ):
            return
        self.service.save_custom_roster(roster)
        self.status_label.setText(f"Imported {roster.team.name} ({len(roster.players)} players).")
        self.refresh()
        self._select(roster.team.abbreviation)

    def save_template(self) -> None:
        """Save a roster template where the user picks, to fill in and import."""
        target = self.choose_save_path()
        if target is None:
            return
        kind = "json" if target.suffix.lower() == ".json" else "csv"
        if target.suffix.lower() not in (".csv", ".json"):
            target = target.with_suffix(".csv")
        try:
            saved = copy_template(kind, target)
        except OSError as error:
            self.show_error("Could not save the template", str(error))
            return
        self.status_label.setText(f"Template saved to {saved}")

    # Delete

    def delete_selected(self) -> None:
        abbreviation = self._selected_abbreviation()
        if abbreviation is None:
            return
        name = self.saved[abbreviation].team.name
        if not self.confirm(
            f"Delete {name}?",
            f"{name} and all its players, ratings, and depth chart changes will be removed. "
            "This cannot be undone.",
        ):
            return
        self.service.delete_team(abbreviation)
        self.status_label.setText(f"Deleted {name}.")
        self.refresh()

    # Dialogs, separate so tests can replace them

    def confirm(self, title: str, text: str) -> bool:
        """Ask a yes/no question."""
        answer = QMessageBox.question(self, title, text)
        return answer == QMessageBox.StandardButton.Yes

    def choose_file(self) -> Path | None:
        name, _ = QFileDialog.getOpenFileName(
            self, "Import roster", "", "Roster files (*.csv *.json);;All files (*)"
        )
        return Path(name) if name else None

    def choose_save_path(self) -> Path | None:
        name, _ = QFileDialog.getSaveFileName(
            self,
            "Save roster template",
            str(Path.home() / "roster_template.csv"),
            "CSV (*.csv);;JSON (*.json)",
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

    def _selected_abbreviation(self) -> str | None:
        items = self.team_list.selectedItems()
        return str(items[0].data(Qt.ItemDataRole.UserRole)) if items else None

    def _update_buttons(self) -> None:
        abbreviation = self._selected_abbreviation()
        saved = self.saved.get(abbreviation) if abbreviation is not None else None
        self.open_button.setEnabled(saved is not None)
        self.delete_button.setEnabled(saved is not None and not self.runner.busy)
        self.refresh_button.setEnabled(
            saved is not None and saved.source is RosterSource.NFLVERSE and not self.runner.busy
        )

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


def format_date(moment: datetime | None) -> str:
    """Like "Nov 16, 2026" in local time, or "date unknown"."""
    if moment is None:
        return "date unknown"
    local = moment.astimezone()
    return f"{local:%b} {local.day}, {local.year}"


def describe_saved(saved: SavedTeam) -> str:
    """Second line of a team in the list, e.g. "NFL data, downloaded Nov 16, 2026, 61 players"."""
    plural = "" if saved.player_count == 1 else "s"
    count = f"{saved.player_count} player{plural}"
    if saved.source is RosterSource.NFLVERSE:
        return f"NFL data, downloaded {format_date(saved.imported_at)}, {count}"
    return f"Custom roster, imported {format_date(saved.imported_at)}, {count}"


def replace_warning(existing: SavedTeam, custom: bool = False) -> str:
    """What will be lost if this saved team is replaced."""
    name = existing.team.name
    if not custom and existing.source is RosterSource.NFLVERSE:
        return (
            f"{name} was downloaded {format_date(existing.imported_at)}. Refreshing replaces its "
            "depth chart and player details with the latest NFL data, so your reordering and "
            "edits are lost. Your ratings are kept for players still on the team."
        )
    kind = "custom roster" if existing.source is RosterSource.CUSTOM else "downloaded NFL team"
    return (
        f"A {kind} with the abbreviation {existing.team.abbreviation} is already saved "
        f"({name}, {existing.player_count} players). Continuing replaces it completely, "
        "including its ratings and depth chart changes."
    )
