"""Tests for the nflverse import. All offline: a fake source stands in for nflreadpy."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from rostermanager.data import RosterRepository
from rostermanager.data.nflverse import build_roster, build_team, import_team, main
from rostermanager.models import Roster, Unit

OLD = "2026-11-01T07:00:00Z"
NEW = "2026-11-11T07:00:00Z"

TEAMS = pl.DataFrame(
    {
        "team_abbr": ["XYZ", "ABC"],
        "team_name": ["Example City Testers", "Other Town"],
        "team_color": ["#a1b2c3", None],
        "team_color2": ["#000000", None],
        "team_logo_espn": ["https://example.invalid/logo.png", None],
    }
)


def depth_row(
    name: str,
    gsis: str | None,
    group: str,
    abb: str,
    slot: int,
    rank: int,
    dt: str = NEW,
    team: str = "XYZ",
) -> dict[str, Any]:
    return {
        "dt": dt,
        "team": team,
        "player_name": name,
        "gsis_id": gsis,
        "pos_grp": group,
        "pos_abb": abb,
        "pos_slot": slot,
        "pos_rank": rank,
    }


def roster_row(gsis: str, name: str, jersey: int, week: int = 10, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "team": "XYZ",
        "week": week,
        "gsis_id": gsis,
        "full_name": name,
        "jersey_number": jersey,
        "height": 74,
        "weight": 210,
        "college": "Somewhere State",
        "years_exp": 3,
    }
    row.update(extra)
    return row


OFF = "3WR 1TE"
DEF = "Base 4-3 D"
ST = "Special Teams"

DEPTH = pl.DataFrame(
    [
        depth_row("Q. Starter", "q1", OFF, "QB", 1, 1),
        depth_row("Q. Backup", "q2", OFF, "QB", 1, 3),  # rank gap: 1 then 3
        depth_row("W. One", "w1", OFF, "WR", 2, 1),
        depth_row("W. Two", "w2", OFF, "WR", 3, 1),
        depth_row("W. Three", "w3", OFF, "WR", 4, 1),
        depth_row("Corner", "c1", DEF, "LCB", 1, 1),
        depth_row("Returner", "w1", ST, "KR", 1, 1),  # same person as W. One
        depth_row("Unlisted Kicker", None, ST, "PK", 2, 1),  # not in roster data
        depth_row("Stale Player", "s1", OFF, "QB", 1, 1, dt=OLD),  # older snapshot
        depth_row("Other Team QB", "o1", OFF, "QB", 1, 1, team="ABC"),
    ]
)

ROSTERS = pl.DataFrame(
    [
        roster_row("q1", "Quinn Starter", 12, week=9, college="Old College"),
        roster_row("q1", "Quinn Starter", 12, week=10),
        roster_row("q2", "Quincy Backup", 7, height=None, college=None, years_exp=0),
        roster_row("w1", "Wes One", 11),
        roster_row("w2", "Will Two", 13),
        roster_row("w3", "Walt Three", 14),
        roster_row("c1", "Cory Corner", 24),
    ]
)


def build() -> Roster:
    return build_roster("XYZ", ROSTERS, DEPTH, TEAMS)


def by_name(roster: Roster, name: str, unit: Unit) -> Any:
    return next(p for p in roster.players if p.name == name and p.unit is unit)


def test_team_uses_names_and_colors_only() -> None:
    team = build_team("XYZ", TEAMS)

    assert team.name == "Example City Testers"
    assert team.primary_color == "#A1B2C3"
    assert team.secondary_color == "#000000"


def test_missing_team_colors_fall_back_to_defaults() -> None:
    team = build_team("ABC", TEAMS)

    assert (team.primary_color, team.secondary_color) == ("#444444", "#FFFFFF")


def test_unknown_team_is_an_error() -> None:
    with pytest.raises(ValueError, match="unknown team"):
        build_roster("NOPE", ROSTERS, DEPTH, TEAMS)


def test_team_without_depth_chart_is_an_error() -> None:
    with pytest.raises(ValueError, match="no depth chart"):
        build_roster("ABC", ROSTERS, DEPTH.filter(pl.col("team") != "ABC"), TEAMS)


def test_only_the_latest_snapshot_and_requested_team_are_used() -> None:
    names = {p.name for p in build().players}

    assert "Stale Player" not in names
    assert "Other Team QB" not in names


def test_roster_details_are_joined_from_latest_week() -> None:
    qb = by_name(build(), "Quinn Starter", Unit.OFFENSE)

    assert qb.jersey_number == 12
    assert qb.height == 74
    assert qb.college == "Somewhere State"
    assert qb.years_experience == 3


def test_players_missing_from_roster_data_keep_depth_chart_name() -> None:
    kicker = by_name(build(), "Unlisted Kicker", Unit.SPECIAL_TEAMS)

    assert kicker.position == "PK"
    assert kicker.jersey_number is None
    assert kicker.years_experience == 0


def test_rank_gaps_are_renumbered() -> None:
    chart = build().depth_chart(Unit.OFFENSE)

    assert [(p.name, p.depth_order) for p in chart.slots["QB"]] == [
        ("Quinn Starter", 1),
        ("Quincy Backup", 2),
    ]


def test_repeated_position_labels_get_numbers() -> None:
    chart = build().depth_chart(Unit.OFFENSE)

    assert {pos: [p.name for p in group] for pos, group in chart.slots.items() if "WR" in pos} == {
        "WR1": ["Wes One"],
        "WR2": ["Will Two"],
        "WR3": ["Walt Three"],
    }


def test_groups_map_to_units() -> None:
    roster = build()

    assert [p.position for p in roster.depth_chart(Unit.DEFENSE).players] == ["LCB"]
    assert {p.position for p in roster.depth_chart(Unit.SPECIAL_TEAMS).players} == {"KR", "PK"}


def test_player_in_two_units_appears_in_each() -> None:
    roster = build()

    assert by_name(roster, "Wes One", Unit.OFFENSE).position == "WR1"
    assert by_name(roster, "Wes One", Unit.SPECIAL_TEAMS).position == "KR"


def test_duplicate_listing_in_one_slot_is_dropped() -> None:
    depth = pl.concat([DEPTH, DEPTH.filter(pl.col("gsis_id") == "c1")])

    roster = build_roster("XYZ", ROSTERS, depth, TEAMS)

    assert [p.name for p in roster.depth_chart(Unit.DEFENSE).players] == ["Cory Corner"]


def test_only_the_larger_defensive_front_is_kept() -> None:
    three_four = pl.DataFrame(
        [
            depth_row("Edge One", None, "Base 3-4 D", "LOLB", 1, 1),
            depth_row("Edge Two", None, "Base 3-4 D", "ROLB", 2, 1),
        ]
    )

    roster = build_roster("XYZ", ROSTERS, pl.concat([DEPTH, three_four]), TEAMS)

    # Base 3-4 D has two entries and Base 4-3 D has one, so only the 3-4 survives.
    assert [p.name for p in roster.depth_chart(Unit.DEFENSE).players] == ["Edge One", "Edge Two"]


@dataclass
class FakeSource:
    seasons: list[int] = field(default_factory=list)

    def load_rosters(self, seasons: int) -> pl.DataFrame:
        self.seasons.append(seasons)
        return ROSTERS

    def load_depth_charts(self, seasons: int) -> pl.DataFrame:
        self.seasons.append(seasons)
        return DEPTH

    def load_teams(self) -> pl.DataFrame:
        return TEAMS


def test_import_team_saves_to_repository(tmp_path: Path) -> None:
    repo = RosterRepository(tmp_path / "rosters.db")
    source = FakeSource()

    roster = import_team(" xyz ", repo, season=2026, source=source)

    assert source.seasons == [2026, 2026]
    assert repo.load_roster("XYZ") == roster


def test_main_reports_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = RosterRepository(tmp_path / "rosters.db")

    code = main(["XYZ", "--season", "2026"], repo=repo, source=FakeSource())

    assert code == 0
    assert "Example City Testers" in capsys.readouterr().out
    assert repo.load_roster("XYZ") is not None


def test_main_reports_unknown_team(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = RosterRepository(tmp_path / "rosters.db")

    code = main(["NOPE", "--season", "2026"], repo=repo, source=FakeSource())

    assert code == 1
    assert "unknown team" in capsys.readouterr().err
    assert repo.list_teams() == []
