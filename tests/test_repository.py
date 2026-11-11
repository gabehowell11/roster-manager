"""Tests for the SQLite roster repository."""

import sqlite3
from pathlib import Path

import pytest

from rostermanager.data import RosterRepository, default_db_path
from rostermanager.data.repository import SCHEMA_VERSION
from rostermanager.models import Player, Roster, Team, Unit


def make_roster(abbreviation: str = "XYZ", name: str = "Example City") -> Roster:
    return Roster(
        team=Team(abbreviation=abbreviation, name=name, primary_color="#112233"),
        players=[
            Player(
                name="QB One",
                position="QB",
                jersey_number=12,
                unit="offense",
                height=76,
                weight=225,
                college="Somewhere State",
                years_experience=5,
                rating=88,
                depth_order=1,
            ),
            Player(name="QB Two", position="QB", unit="offense", depth_order=2),
            Player(name="Corner", position="LCB", unit="defense", depth_order=1),
            Player(name="Kicker", position="K", unit="special_teams", depth_order=1),
        ],
    )


@pytest.fixture
def repo(tmp_path: Path) -> RosterRepository:
    return RosterRepository(tmp_path / "rosters.db")


def test_save_then_load_round_trips_every_field(repo: RosterRepository) -> None:
    roster = make_roster()

    repo.save_roster(roster)

    assert repo.load_roster("XYZ") == roster


def test_load_keeps_player_order(repo: RosterRepository) -> None:
    roster = make_roster()
    repo.save_roster(roster)

    loaded = repo.load_roster("XYZ")

    assert loaded is not None
    assert [p.name for p in loaded.players] == [p.name for p in roster.players]


def test_load_is_case_insensitive(repo: RosterRepository) -> None:
    repo.save_roster(make_roster())

    assert repo.load_roster(" xyz ") is not None


def test_load_missing_team_returns_none(repo: RosterRepository) -> None:
    assert repo.load_roster("NOPE") is None


def test_saving_again_replaces_team_and_players(repo: RosterRepository) -> None:
    repo.save_roster(make_roster())
    updated = Roster(
        team=Team(abbreviation="XYZ", name="Renamed City"),
        players=[Player(name="New QB", position="QB", unit=Unit.OFFENSE, depth_order=1)],
    )

    repo.save_roster(updated)

    assert repo.load_roster("XYZ") == updated
    assert len(repo.list_teams()) == 1


def test_saving_one_team_leaves_others_alone(repo: RosterRepository) -> None:
    first, second = make_roster("AAA", "Alpha"), make_roster("BBB", "Bravo")
    repo.save_roster(first)
    repo.save_roster(second)

    repo.save_roster(Roster(team=first.team, players=[]))

    assert repo.load_roster("BBB") == second


def test_list_teams_is_sorted_by_name(repo: RosterRepository) -> None:
    repo.save_roster(make_roster("ZZZ", "Bravo"))
    repo.save_roster(make_roster("AAA", "Charlie"))
    repo.save_roster(make_roster("MMM", "Alpha"))

    assert [t.name for t in repo.list_teams()] == ["Alpha", "Bravo", "Charlie"]


def test_delete_removes_team_and_players(repo: RosterRepository) -> None:
    repo.save_roster(make_roster())

    assert repo.delete_roster("XYZ") is True
    assert repo.load_roster("XYZ") is None
    assert repo.delete_roster("XYZ") is False
    with sqlite3.connect(repo.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0


def test_data_survives_reopening(tmp_path: Path) -> None:
    db = tmp_path / "rosters.db"
    RosterRepository(db).save_roster(make_roster())

    assert RosterRepository(db).load_roster("XYZ") == make_roster()


def test_creates_missing_folders_and_sets_schema_version(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "folder" / "rosters.db"

    RosterRepository(db)

    assert db.exists()
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_refuses_database_from_newer_version(tmp_path: Path) -> None:
    db = tmp_path / "rosters.db"
    with sqlite3.connect(db) as conn:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")

    with pytest.raises(RuntimeError, match="newer"):
        RosterRepository(db)


def test_failed_save_keeps_the_old_roster(repo: RosterRepository) -> None:
    original = make_roster()
    repo.save_roster(original)
    broken = make_roster()
    # Bypass validation to force a NOT NULL failure partway through the save.
    object.__setattr__(broken.players[1], "name", None)

    with pytest.raises(sqlite3.IntegrityError):
        repo.save_roster(broken)

    assert repo.load_roster("XYZ") == original


def test_default_db_path_is_in_user_data_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rostermanager.data.paths.user_data_dir", lambda app, appauthor: f"C:/data/{app}"
    )

    assert default_db_path() == Path("C:/data/RosterManager/rosters.db")
