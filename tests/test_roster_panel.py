"""Tests for the View roster side panel, run offscreen."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team
from rostermanager.services import PlayerKey, RosterService
from rostermanager.services.roster_list import roster_groups
from rostermanager.ui.main_window import MainWindow
from rostermanager.ui.roster_panel import MIN_WIDTH, RosterPanel, panel_width

pytestmark = pytest.mark.usefixtures("qapp")

TEAM = Team(abbreviation="XYZ", name="Example City", primary_color="#E31837")
ROSTER = Roster(
    team=TEAM,
    players=[
        Player(name="Backup QB", position="QB", unit="offense", depth_order=2),
        Player(name="Starter QB", position="QB", unit="offense", depth_order=1, rating=91),
        Player(name="Lefty", position="LT", unit="offense", depth_order=1),
        Player(name="Corner", position="LCB", unit="defense", depth_order=1, rating=80),
    ],
)


@pytest.fixture
def window(tmp_path: Path) -> MainWindow:
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    service.repo.save_roster(ROSTER)
    window = MainWindow(service)
    window.resize(1200, 800)
    window.show()
    window.open_team("XYZ")
    return window


def test_panel_lists_name_position_and_rating_in_roster_order() -> None:
    panel = RosterPanel()
    panel.set_roster(ROSTER)
    expected = [p for group in roster_groups(ROSTER) for p in group.players]
    assert panel.listed_players() == expected
    rows = {p.name: (n.text(), pos.text(), r.text()) for p, n, pos, r in panel.player_rows}
    assert rows["Starter QB"] == ("Starter QB", "QB", "91")
    assert rows["Lefty"] == ("Lefty", "LT", "--")
    assert panel.count_label.text() == "4 players"


def test_starters_and_backups_are_styled_apart() -> None:
    panel = RosterPanel()
    panel.set_roster(ROSTER)
    names = {p.name: n.objectName() for p, n, _, _ in panel.player_rows}
    assert names["Starter QB"] == "Starter"
    assert names["Backup QB"] == "Backup"


def test_view_roster_button_opens_panel_over_the_right_side(window: MainWindow) -> None:
    view = window.team_view
    assert not view.roster_panel.isVisible()
    view.roster_button.click()
    panel = view.roster_panel
    assert panel.isVisible()
    assert panel.geometry().right() == view.rect().right()  # flush with the right edge
    assert panel.width() == panel_width(window.width())
    assert panel.geometry().top() == view.field_scroll.geometry().top()  # header stays usable
    assert panel.geometry().bottom() == view.rect().bottom()
    # Floats over the field instead of shrinking it.
    assert view.field_scroll.geometry().right() > panel.geometry().left()


def test_button_close_button_and_escape_all_close_it(window: MainWindow) -> None:
    view = window.team_view
    view.roster_button.click()
    view.roster_button.click()
    assert not view.roster_panel.isVisible()

    view.roster_button.click()
    view.roster_panel.close_button.click()
    assert not view.roster_panel.isVisible()
    assert not view.roster_button.isChecked()

    view.roster_button.click()
    view.roster_panel.list_scroll.setFocus()
    QTest.keyClick(view.roster_panel.list_scroll, Qt.Key.Key_Escape)
    assert not view.roster_panel.isVisible()


def test_panel_follows_window_resizes(window: MainWindow) -> None:
    view = window.team_view
    view.roster_button.click()
    window.resize(1600, 900)
    assert view.roster_panel.width() == panel_width(1600)
    assert view.roster_panel.geometry().right() == view.rect().right()


def test_panel_updates_after_an_edit(window: MainWindow) -> None:
    view = window.team_view
    roster = window.service.update_player("XYZ", PlayerKey.of(ROSTER.players[1]), {"rating": 55})
    view.update_roster(roster)
    rows = {p.name: r.text() for p, _, _, r in view.roster_panel.player_rows}
    assert rows["Starter QB"] == "55"


def test_opening_another_team_starts_with_the_panel_closed(window: MainWindow) -> None:
    view = window.team_view
    view.roster_button.click()
    window.show_home()
    window.open_team("XYZ")
    assert not view.roster_panel.isVisible()
    assert not view.roster_button.isChecked()


def test_panel_never_narrower_than_readable() -> None:
    assert panel_width(400) == MIN_WIDTH
    assert panel_width(2000) == 540
