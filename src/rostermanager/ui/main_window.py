"""The main window. Switches between the home screen and the team view."""

from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QWidget

from rostermanager.services import RosterNotFoundError, RosterService
from rostermanager.ui.home_screen import HomeScreen
from rostermanager.ui.team_view import TeamView


class MainWindow(QMainWindow):
    """Holds one page at a time: the home screen or a team's view."""

    def __init__(self, service: RosterService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Roster Manager")
        self.resize(1100, 750)

        self.home = HomeScreen(service)
        self.team_view = TeamView()
        self.home.team_selected.connect(self.open_team)
        self.team_view.back_requested.connect(self.show_home)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.home)
        self.pages.addWidget(self.team_view)
        self.setCentralWidget(self.pages)

    def show_home(self) -> None:
        """Go back to the home screen with an up-to-date team list."""
        self.home.refresh()
        self.pages.setCurrentWidget(self.home)
        self.setWindowTitle("Roster Manager")

    def open_team(self, abbreviation: str) -> None:
        """Load a saved team and show it. Stays on the home screen if it is gone."""
        try:
            roster = self.service.load_roster(abbreviation)
        except RosterNotFoundError as error:
            QMessageBox.warning(self, "Team not found", str(error))
            self.home.refresh()
            return
        self.team_view.set_roster(roster)
        self.pages.setCurrentWidget(self.team_view)
        self.setWindowTitle(f"{roster.team.name} - Roster Manager")
