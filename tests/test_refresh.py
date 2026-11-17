"""Tests for safe refreshes: import dates, schema upgrade, rating carry-over, overwrite warnings."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, RosterSource, Team, Unit
from rostermanager.services import PlayerKey, RosterService
from rostermanager.services.roster_service import carry_over_ratings
from rostermanager.ui.home_screen import HomeScreen, describe_saved, format_date, replace_warning
from tests.test_home_screen import wait_for
from tests.test_nflverse import FakeSource

WHEN = datetime(2026, 11, 16, 18, 30, tzinfo=UTC)


def roster(
    abbreviation: str = "XYZ", name: str = "Example City", rating: int | None = None
) -> Roster:
    return Roster(
        team=Team(abbreviation=abbreviation, name=name),
        players=[
            Player(
                name="Quinn Starter", position="QB", unit="offense", rating=rating, depth_order=1
            ),
            Player(name="Wes One", position="KR", unit="special_teams", depth_order=1),
        ],
    )


@pytest.fixture
def repo(tmp_path: Path) -> RosterRepository:
    return RosterRepository(tmp_path / "r.db")


@pytest.fixture
def service(repo: RosterRepository) -> RosterService:
    return RosterService(repo)


# Repository


def test_saved_teams_record_source_time_and_count(repo: RosterRepository) -> None:
    repo.save_roster(roster(), source=RosterSource.NFLVERSE, imported_at=WHEN)
    repo.save_roster(roster("ABC", "Alpha"))
    saved = repo.list_saved_teams()
    assert [s.team.abbreviation for s in saved] == ["ABC", "XYZ"]
    alpha, example = saved
    assert (alpha.source, alpha.imported_at, alpha.player_count) == (RosterSource.CUSTOM, None, 2)
    assert (example.source, example.imported_at) == (RosterSource.NFLVERSE, WHEN)
    assert repo.saved_team("xyz") == example
    assert repo.saved_team("NOPE") is None


def test_edits_keep_source_and_import_time(repo: RosterRepository) -> None:
    repo.save_roster(roster(), source=RosterSource.NFLVERSE, imported_at=WHEN)
    repo.save_roster(roster(rating=80))  # an edit saves without source or time
    saved = repo.saved_team("XYZ")
    assert saved is not None
    assert (saved.source, saved.imported_at) == (RosterSource.NFLVERSE, WHEN)


def test_version_1_database_is_upgraded_in_place(tmp_path: Path) -> None:
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE teams (id INTEGER PRIMARY KEY, abbreviation TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, primary_color TEXT NOT NULL, secondary_color TEXT NOT NULL);
            CREATE TABLE players (id INTEGER PRIMARY KEY,
                team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                sort_index INTEGER NOT NULL, name TEXT NOT NULL, position TEXT NOT NULL,
                jersey_number INTEGER, unit TEXT NOT NULL, height INTEGER, weight INTEGER,
                college TEXT, years_experience INTEGER NOT NULL, rating INTEGER,
                depth_order INTEGER NOT NULL);
            INSERT INTO teams VALUES (1, 'OLD', 'Old Town', '#111111', '#FFFFFF');
            INSERT INTO players VALUES (1, 1, 0, 'Al', 'QB', 7, 'offense', NULL, NULL, NULL, 2, 70, 1);
            PRAGMA user_version = 1;
            """
        )
    conn.close()

    repo = RosterRepository(db)

    saved = repo.saved_team("OLD")
    assert saved is not None
    assert (saved.source, saved.imported_at, saved.player_count) == (RosterSource.CUSTOM, None, 1)
    loaded = repo.load_roster("OLD")
    assert loaded is not None and loaded.players[0].rating == 70
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    conn.close()


# Service


def test_carry_over_ratings_matches_name_and_unit_then_name() -> None:
    old = Roster(
        team=Team(abbreviation="XYZ", name="X"),
        players=[
            Player(name="Quinn", position="QB", unit="offense", rating=90, depth_order=1),
            Player(name="Wes", position="KR", unit="special_teams", rating=60, depth_order=1),
            Player(name="Wes", position="WR1", unit="offense", rating=75, depth_order=1),
            Player(name="Gone", position="RB", unit="offense", rating=50, depth_order=1),
        ],
    )
    new = Roster(
        team=old.team,
        players=[
            Player(name="Quinn", position="QB", unit="offense", depth_order=1),
            Player(name="Wes", position="KR", unit="special_teams", depth_order=1),
            Player(name="Wes", position="WR2", unit="offense", depth_order=1),
            Player(name="Rookie", position="RB", unit="offense", depth_order=1),
            Player(name="Quinn", position="H", unit="special_teams", depth_order=1),
        ],
    )
    ratings = {(p.name, p.unit): p.rating for p in carry_over_ratings(old, new).players}
    assert ratings[("Quinn", Unit.OFFENSE)] == 90
    assert ratings[("Wes", Unit.SPECIAL_TEAMS)] == 60
    assert ratings[("Wes", Unit.OFFENSE)] == 75  # position changed, still matched
    assert ratings[("Rookie", Unit.OFFENSE)] is None
    assert ratings[("Quinn", Unit.SPECIAL_TEAMS)] == 90  # matched by name alone


def test_refreshing_a_downloaded_team_keeps_ratings(service: RosterService) -> None:
    first = service.download_nfl_team("XYZ", season=2026, source=FakeSource())
    starter = next(p for p in first.players if p.unit is Unit.OFFENSE and p.position == "QB")
    service.update_player("XYZ", PlayerKey.of(starter), {"rating": 93})

    refreshed = service.download_nfl_team("XYZ", season=2026, source=FakeSource())

    again = next(p for p in refreshed.players if p.name == starter.name and p.unit is Unit.OFFENSE)
    assert again.rating == 93
    saved = service.saved_team("XYZ")
    assert saved is not None and saved.source is RosterSource.NFLVERSE
    assert saved.imported_at is not None


def test_downloading_over_a_custom_team_does_not_borrow_its_ratings(service: RosterService) -> None:
    service.repo.save_roster(
        Roster(
            team=Team(abbreviation="XYZ", name="Custom"),
            players=[
                Player(
                    name="Quinn Starter", position="QB", unit="offense", rating=11, depth_order=1
                )
            ],
        ),
        source=RosterSource.CUSTOM,
    )
    roster = service.download_nfl_team("XYZ", season=2026, source=FakeSource())
    assert all(p.rating is None for p in roster.players)


def test_read_custom_file_does_not_save(service: RosterService, tmp_path: Path) -> None:
    path = tmp_path / "t.csv"
    path.write_text("name,position,unit,depth_order\nSam,QB,offense,1\n", encoding="utf-8")
    roster = service.read_custom_file(path, Team(abbreviation="CUS", name="Custom"))
    assert service.saved_team("CUS") is None
    service.save_custom_roster(roster)
    saved = service.saved_team("CUS")
    assert saved is not None and saved.source is RosterSource.CUSTOM and saved.imported_at


# Home screen


def test_list_shows_source_and_date(repo: RosterRepository) -> None:
    repo.save_roster(roster(), source=RosterSource.NFLVERSE, imported_at=WHEN)
    saved = repo.saved_team("XYZ")
    assert saved is not None
    assert describe_saved(saved) == f"NFL data, downloaded {format_date(WHEN)}, 2 players"
    assert format_date(None) == "date unknown"
    assert "ratings are kept" in replace_warning(saved)
    assert "replaces it completely" in replace_warning(saved, custom=True)


def make_home(service: RosterService, answers: list[bool]) -> tuple[HomeScreen, list[str]]:
    home = HomeScreen(service)
    asked: list[str] = []

    def confirm(title: str, text: str) -> bool:
        asked.append(title)
        return answers.pop(0)

    def no_error(title: str, details: str) -> None:
        raise AssertionError(f"{title}: {details}")

    home.confirm = confirm  # type: ignore[method-assign]
    home.show_error = no_error  # type: ignore[method-assign]
    return home, asked


class OfflineService(RosterService):
    def download_nfl_team(
        self, abbreviation: str, season: int | None = None, source: object = None
    ) -> Roster:
        return super().download_nfl_team("XYZ", season=2026, source=FakeSource())


@pytest.mark.usefixtures("qapp")
def test_refresh_button_only_for_downloaded_teams_and_asks_first(repo: RosterRepository) -> None:
    service = OfflineService(repo)
    service.download_nfl_team("XYZ")
    repo.save_roster(roster("CUS", "Custom"), source=RosterSource.CUSTOM)
    home, asked = make_home(service, [False, True])

    home._select("CUS")
    assert not home.refresh_button.isEnabled()
    assert home.delete_button.isEnabled()

    home._select("XYZ")
    assert home.refresh_button.isEnabled()
    home.start_refresh()  # answered no
    assert not home.runner.busy
    home.start_refresh()  # answered yes
    wait_for(home.runner)
    assert asked == ["Replace Example City Testers?", "Replace Example City Testers?"]
    assert "Saved" in home.status_label.text()


@pytest.mark.usefixtures("qapp")
def test_download_over_custom_team_with_same_abbreviation_warns(repo: RosterRepository) -> None:
    repo.save_roster(roster("XYZ", "My Custom XYZ"), source=RosterSource.CUSTOM)
    home, asked = make_home(OfflineService(repo), [False])
    home.team_picker.setCurrentText("KC")
    home._download("XYZ")
    assert asked == ["Replace My Custom XYZ?"]
    saved = repo.saved_team("XYZ")
    assert saved is not None and saved.team.name == "My Custom XYZ"  # declined: untouched


@pytest.mark.usefixtures("qapp")
def test_import_over_existing_team_warns(repo: RosterRepository, tmp_path: Path) -> None:
    repo.save_roster(roster("CUS", "Old Custom"), source=RosterSource.CUSTOM)
    path = tmp_path / "t.csv"
    path.write_text("name,position,unit,depth_order\nSam,QB,offense,1\n", encoding="utf-8")
    home, asked = make_home(RosterService(repo), [False, True])
    home.choose_file = lambda: path  # type: ignore[method-assign]
    home.ask_team = lambda: Team(abbreviation="CUS", name="New Custom")  # type: ignore[method-assign]

    home.start_import()
    saved = repo.saved_team("CUS")
    assert saved is not None and saved.team.name == "Old Custom"

    home.start_import()
    saved = repo.saved_team("CUS")
    assert saved is not None and saved.team.name == "New Custom"
    assert asked == ["Replace Old Custom?", "Replace Old Custom?"]


@pytest.mark.usefixtures("qapp")
def test_delete_team_after_confirming(repo: RosterRepository) -> None:
    repo.save_roster(roster())
    home, asked = make_home(RosterService(repo), [False, True])
    home._select("XYZ")
    home.delete_selected()
    assert repo.saved_team("XYZ") is not None
    home.delete_selected()
    assert repo.saved_team("XYZ") is None
    assert home.team_list.count() == 0
    assert asked == ["Delete Example City?", "Delete Example City?"]
