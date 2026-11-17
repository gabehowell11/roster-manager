"""Tests for RosterService. All offline, each test with its own database."""

from pathlib import Path

import polars as pl
import pytest

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services import (
    NFL_TEAM_ABBREVIATIONS,
    RosterImportError,
    RosterNotFoundError,
    RosterService,
    TeamDownloadError,
)
from tests.test_nflverse import FakeSource


@pytest.fixture
def service(tmp_path: Path) -> RosterService:
    return RosterService(RosterRepository(tmp_path / "rosters.db"))


def make_roster(abbreviation: str = "XYZ", name: str = "Example City") -> Roster:
    return Roster(
        team=Team(abbreviation=abbreviation, name=name),
        players=[
            Player(name="QB One", position="QB", unit="offense", depth_order=1),
            Player(name="QB Two", position="QB", unit="offense", depth_order=2),
            Player(name="Corner", position="LCB", unit="defense", depth_order=1),
        ],
    )


def test_list_teams_starts_empty_then_shows_saved(service: RosterService) -> None:
    assert service.list_teams() == []
    service.repo.save_roster(make_roster("BBB", "Bravo"))
    service.repo.save_roster(make_roster("AAA", "Alpha"))
    assert [team.name for team in service.list_teams()] == ["Alpha", "Bravo"]


def test_load_roster_returns_saved_roster(service: RosterService) -> None:
    roster = make_roster()
    service.repo.save_roster(roster)
    assert service.load_roster(" xyz ") == roster


def test_load_missing_roster_raises(service: RosterService) -> None:
    with pytest.raises(RosterNotFoundError, match="'NOPE'"):
        service.load_roster("nope")


def test_depth_chart_returns_one_unit(service: RosterService) -> None:
    service.repo.save_roster(make_roster())
    chart = service.depth_chart("XYZ", Unit.OFFENSE)
    assert chart.unit is Unit.OFFENSE
    assert [p.name for p in chart.slots["QB"]] == ["QB One", "QB Two"]


def test_delete_team(service: RosterService) -> None:
    service.repo.save_roster(make_roster())
    assert service.delete_team("XYZ") is True
    assert service.delete_team("XYZ") is False
    assert service.list_teams() == []


def test_import_custom_file_saves_roster(service: RosterService, tmp_path: Path) -> None:
    path = tmp_path / "team.csv"
    path.write_text("name,position,unit,depth_order\nSam Starter,QB,offense,1\n", encoding="utf-8")
    roster = service.import_custom_file(path, Team(abbreviation="CUS", name="Custom"))
    assert service.load_roster("CUS") == roster


def test_import_custom_file_errors_pass_through(service: RosterService, tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("name,position,unit,depth_order\nSam,QB,offense,0\n", encoding="utf-8")
    with pytest.raises(RosterImportError) as caught:
        service.import_custom_file(path, Team(abbreviation="CUS", name="Custom"))
    assert caught.value.problems
    assert service.list_teams() == []


def test_download_nfl_team_saves_roster(service: RosterService) -> None:
    roster = service.download_nfl_team("xyz", season=2026, source=FakeSource())
    assert service.load_roster("XYZ") == roster


def test_download_failure_becomes_team_download_error(service: RosterService) -> None:
    with pytest.raises(TeamDownloadError, match="could not download ZZZ"):
        service.download_nfl_team("zzz", season=2026, source=FakeSource())


def test_network_failure_becomes_team_download_error(service: RosterService) -> None:
    class OfflineSource(FakeSource):
        def load_rosters(self, seasons: int) -> pl.DataFrame:
            raise ConnectionError("no internet")

    with pytest.raises(TeamDownloadError, match="no internet"):
        service.download_nfl_team("XYZ", season=2026, source=OfflineSource())


def test_nfl_team_list_has_32_unique_teams() -> None:
    assert len(set(NFL_TEAM_ABBREVIATIONS)) == 32
