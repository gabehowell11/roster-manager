"""Tests for the dark blue theme and centered, team-colored titles."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team
from rostermanager.services import RosterService
from rostermanager.ui.home_screen import HomeScreen
from rostermanager.ui.player_card import contrast_ratio
from rostermanager.ui.team_view import TeamView
from rostermanager.ui.theme import BACKGROUND, TEXT, apply_theme, team_title_color

pytestmark = pytest.mark.usefixtures("qapp")


def test_apply_theme_sets_dark_blue_background(qapp: QApplication) -> None:
    apply_theme(qapp)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().upper() == BACKGROUND
    assert BACKGROUND in qapp.styleSheet()


def test_theme_text_is_readable_on_background() -> None:
    assert contrast_ratio(TEXT, BACKGROUND) >= 7


@pytest.mark.parametrize(
    ("primary", "secondary", "expected"),
    [
        ("#E31837", "#FFB81C", "#E31837"),  # bright primary reads well: use it
        ("#0B162A", "#C83803", "#C83803"),  # navy on dark blue: fall back to secondary
        ("#101820", "#1A2230", TEXT),  # neither readable: plain text color
    ],
)
def test_team_title_color(primary: str, secondary: str, expected: str) -> None:
    team = Team(abbreviation="XYZ", name="X", primary_color=primary, secondary_color=secondary)
    assert team_title_color(team) == expected


def test_home_title_is_centered(tmp_path: Path) -> None:
    home = HomeScreen(RosterService(RosterRepository(tmp_path / "r.db")))
    title = home.findChild(QLabel, "Title")
    assert title is not None
    assert title.text() == "Roster Manager"
    assert title.alignment() & Qt.AlignmentFlag.AlignHCenter


def test_team_title_is_centered_in_team_color(tmp_path: Path) -> None:
    team = Team(abbreviation="XYZ", name="Example City", primary_color="#E31837")
    view = TeamView(RosterService(RosterRepository(tmp_path / "r.db")))
    view.set_roster(
        Roster(team=team, players=[Player(name="Q", position="QB", unit="offense", depth_order=1)])
    )
    assert view.title.text() == "Example City"
    assert view.title.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert "#E31837" in view.title.styleSheet()
