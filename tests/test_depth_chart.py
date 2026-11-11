"""Tests for the DepthChart and Roster models and their depth_order rules."""

import pytest
from pydantic import ValidationError

from rostermanager.models import DepthChart, Player, Roster, Team, Unit


def player(name: str, position: str, depth: int, unit: str = "offense") -> Player:
    return Player(name=name, position=position, unit=unit, depth_order=depth)


TEAM = Team(abbreviation="XYZ", name="Example City")


def test_depth_chart_groups_slots_starter_first() -> None:
    chart = DepthChart(
        unit=Unit.OFFENSE,
        players=[
            player("QB Two", "QB", 2),
            player("Left Tackle", "LT", 1),
            player("QB One", "QB", 1),
            player("QB Three", "QB", 3),
        ],
    )

    assert {pos: [p.name for p in group] for pos, group in chart.slots.items()} == {
        "QB": ["QB One", "QB Two", "QB Three"],
        "LT": ["Left Tackle"],
    }
    assert [p.name for p in chart.starters] == ["QB One", "Left Tackle"]
    assert [p.name for p in chart.backups] == ["QB Two", "QB Three"]


def test_empty_depth_chart_is_allowed() -> None:
    chart = DepthChart(unit=Unit.DEFENSE, players=[])

    assert chart.slots == {}
    assert chart.starters == []


@pytest.mark.parametrize(
    "depths",
    [
        [2],  # no starter
        [1, 1],  # two starters in one slot
        [1, 3],  # gap in backups
        [1, 2, 2],  # repeated backup
    ],
)
def test_depth_chart_rejects_bad_depth_orders(depths: list[int]) -> None:
    players = [player(f"QB {i}", "QB", depth) for i, depth in enumerate(depths)]

    with pytest.raises(ValidationError, match="offense QB"):
        DepthChart(unit=Unit.OFFENSE, players=players)


def test_depth_chart_rejects_players_from_another_unit() -> None:
    with pytest.raises(ValidationError, match="Corner"):
        DepthChart(
            unit=Unit.OFFENSE,
            players=[player("QB", "QB", 1), player("Corner", "LCB", 1, "defense")],
        )


def test_same_position_label_in_two_units_are_separate_slots() -> None:
    roster = Roster(
        team=TEAM,
        players=[player("Off One", "X", 1), player("Def One", "X", 1, "defense")],
    )

    assert len(roster.players) == 2


def test_roster_rejects_bad_depth_orders() -> None:
    with pytest.raises(ValidationError, match="defense LCB"):
        Roster(
            team=TEAM,
            players=[player("A", "LCB", 1, "defense"), player("B", "LCB", 1, "defense")],
        )


def test_roster_builds_a_depth_chart_per_unit() -> None:
    roster = Roster(
        team=TEAM,
        players=[
            player("QB One", "QB", 1),
            player("QB Two", "QB", 2),
            player("Corner", "LCB", 1, "defense"),
            player("Kicker", "K", 1, "special_teams"),
        ],
    )

    offense = roster.depth_chart(Unit.OFFENSE)
    assert offense.unit is Unit.OFFENSE
    assert [p.name for p in offense.starters] == ["QB One"]
    assert [p.name for p in roster.depth_chart(Unit.DEFENSE).starters] == ["Corner"]
    assert [p.name for p in roster.depth_chart(Unit.SPECIAL_TEAMS).starters] == ["Kicker"]
