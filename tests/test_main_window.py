"""Smoke tests for the main window, run offscreen."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team
from rostermanager.services import RosterService
from rostermanager.ui.main_window import MainWindow

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture
def service(db_path: Path) -> RosterService:
    service = RosterService(RosterRepository(db_path))
    service.repo.save_roster(
        Roster(
            team=Team(abbreviation="XYZ", name="Example City"),
            players=[Player(name="QB One", position="QB", unit="offense", depth_order=1)],
        )
    )
    return service


def test_window_opens_on_home_screen(service: RosterService) -> None:
    window = MainWindow(service)
    window.show()
    assert window.isVisible()
    assert window.pages.currentWidget() is window.home
    assert window.home.team_list.count() == 1
    window.close()


def test_selecting_a_team_opens_team_view_and_back_returns(service: RosterService) -> None:
    window = MainWindow(service)
    window.home.team_list.setCurrentRow(0)
    window.home.open_button.click()

    assert window.pages.currentWidget() is window.team_view
    assert window.team_view.title.text() == "Example City (XYZ)"
    assert "Example City" in window.windowTitle()

    window.team_view.back_button.click()
    assert window.pages.currentWidget() is window.home


def test_missing_team_warns_and_stays_home(
    service: RosterService, monkeypatch: pytest.MonkeyPatch
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    window = MainWindow(service)
    service.delete_team("XYZ")

    window.open_team("XYZ")

    assert window.pages.currentWidget() is window.home
    assert warnings and "XYZ" in warnings[0]
    assert window.home.team_list.count() == 0


def test_home_shows_empty_message_without_teams(db_path: Path) -> None:
    window = MainWindow(RosterService(RosterRepository(db_path)))
    window.show()
    assert window.home.empty_label.isVisible()
    assert not window.home.open_button.isEnabled()
    window.close()
