"""Tests for formations: role filling and non-overlapping spots."""

import pytest

from rostermanager.models import DepthChart, Player, Unit
from rostermanager.services.formations import (
    DEPTH_CHART,
    FORMATIONS,
    Formation,
    fill_formation,
    formation_names,
    get_formation,
)


def chart(unit: str, slots: dict[str, int]) -> DepthChart:
    return DepthChart(
        unit=Unit(unit),
        players=[
            Player(name=f"{label} {d}", position=label, unit=unit, depth_order=d)
            for label, count in slots.items()
            for d in range(1, count + 1)
        ],
    )


NFL_OFFENSE = chart(
    "offense",
    {
        "QB": 2,
        "RB": 2,
        "WR1": 2,
        "WR2": 2,
        "WR3": 2,
        "TE": 3,
        "LT": 1,
        "LG": 1,
        "C": 1,
        "RG": 1,
        "RT": 1,
    },
)
NFL_43 = chart(
    "defense",
    {
        "LDE": 2,
        "LDT": 2,
        "RDT": 1,
        "RDE": 2,
        "WLB": 1,
        "MLB": 2,
        "SLB": 1,
        "LCB": 2,
        "RCB": 2,
        "NB": 1,
        "FS": 1,
        "SS": 2,
    },
)
NFL_34 = chart(
    "defense",
    {
        "LDE": 1,
        "NT": 2,
        "RDE": 1,
        "LOLB": 2,
        "LILB": 1,
        "RILB": 1,
        "ROLB": 2,
        "LCB": 2,
        "RCB": 1,
        "FS": 1,
        "SS": 1,
    },
)
GENERIC_DEFENSE = chart("defense", {"DE": 3, "DT": 3, "LB": 4, "CB": 4, "S": 3})


def on_field(filled: list) -> dict[str, str | None]:  # type: ignore[type-arg]
    return {f.role.label: (f.players[0].name if f.players else None) for f in filled}


ALL = [f for unit in (Unit.OFFENSE, Unit.DEFENSE) for f in FORMATIONS[unit]]


@pytest.mark.parametrize("formation", ALL, ids=lambda f: f.name)
def test_every_formation_has_eleven_unique_roles_that_never_overlap(formation: Formation) -> None:
    assert len(formation.roles) == 11
    assert len({r.label for r in formation.roles}) == 11
    width, height, card_w, card_h = 1000, 600, 100, 80
    spots = [r.spot for r in formation.roles]
    for i, a in enumerate(spots):
        assert 0 <= a.x <= 1 and 0 <= a.y <= 1
        for b in spots[i + 1 :]:
            apart = abs(a.x - b.x) * width >= card_w or abs(a.y - b.y) * height >= card_h
            assert apart, (formation.name, a, b)


@pytest.mark.parametrize("formation", FORMATIONS[Unit.OFFENSE], ids=lambda f: f.name)
def test_full_nfl_offense_fills_every_role(formation: Formation) -> None:
    filled = fill_formation(NFL_OFFENSE, formation)
    assert all(f.players for f in filled), on_field(filled)
    names = [f.players[0].name for f in filled]
    assert len(names) == len(set(names))  # nobody plays two spots


def test_goal_line_uses_te_backups_for_extra_tight_ends() -> None:
    goal_line = get_formation(Unit.OFFENSE, "Goal Line (23)")
    assert goal_line is not None
    field = on_field(fill_formation(NFL_OFFENSE, goal_line))
    assert (field["TE1"], field["TE2"], field["TE3"]) == ("TE 1", "TE 2", "TE 3")
    assert field["FB"] == "RB 2"  # no FB slot: the backup RB lines up at fullback


def test_empty_takes_four_receivers_and_backs_up_with_wr_backups() -> None:
    empty = get_formation(Unit.OFFENSE, "Empty (10)")
    assert empty is not None
    field = on_field(fill_formation(NFL_OFFENSE, empty))
    assert (field["WR1"], field["WR2"], field["WR3"]) == ("WR1 1", "WR2 1", "WR3 1")
    assert field["WR4"] == "WR1 2"  # no WR4 slot: next best receiver


@pytest.mark.parametrize(
    "roster_chart", [NFL_43, NFL_34, GENERIC_DEFENSE], ids=["4-3", "3-4", "generic"]
)
@pytest.mark.parametrize("formation", FORMATIONS[Unit.DEFENSE], ids=lambda f: f.name)
def test_defensive_formations_fill_from_any_front(
    roster_chart: DepthChart, formation: Formation
) -> None:
    filled = fill_formation(roster_chart, formation)
    names = [f.players[0].name for f in filled if f.players]
    assert len(names) == len(set(names))
    assert sum(1 for f in filled if f.players) >= 9  # at most a couple open spots


def test_three_four_roster_in_four_three_uses_nose_tackle_inside() -> None:
    four_three = get_formation(Unit.DEFENSE, "4-3")
    assert four_three is not None
    field = on_field(fill_formation(NFL_34, four_three))
    assert field["LDT"] == "NT 1"
    assert field["RDT"] == "NT 2"
    assert field["WLB"] == "LOLB 1"


def test_nickel_puts_the_nickel_back_in() -> None:
    nickel = get_formation(Unit.DEFENSE, "Nickel (4-2-5)")
    assert nickel is not None
    assert on_field(fill_formation(NFL_43, nickel))["NB"] == "NB 1"
    assert on_field(fill_formation(NFL_34, nickel))["NB"] == "LCB 2"


def test_missing_players_leave_open_roles() -> None:
    tiny = chart("offense", {"QB": 1, "WR": 1})
    shotgun = get_formation(Unit.OFFENSE, "Shotgun (11)")
    assert shotgun is not None
    field = on_field(fill_formation(tiny, shotgun))
    assert field["QB"] == "QB 1"
    assert field["WR1"] == "WR 1"
    assert field["WR2"] is None
    assert field["LT"] is None


def test_backups_behind_a_card_exclude_players_on_the_field() -> None:
    goal_line = get_formation(Unit.OFFENSE, "Goal Line (23)")
    assert goal_line is not None
    filled = {f.role.label: f for f in fill_formation(NFL_OFFENSE, goal_line)}
    assert [p.name for p in filled["TE1"].players] == ["TE 1"]  # TE 2 and 3 are on the field
    assert [p.name for p in filled["QB"].players] == ["QB 1", "QB 2"]


def test_names_and_lookup() -> None:
    assert formation_names(Unit.OFFENSE)[0] == DEPTH_CHART
    assert "Goal Line (23)" in formation_names(Unit.OFFENSE)
    assert {"4-3", "3-4", "Nickel (4-2-5)", "Dime (4-1-6)"} <= set(formation_names(Unit.DEFENSE))
    assert formation_names(Unit.SPECIAL_TEAMS) == [DEPTH_CHART]
    assert get_formation(Unit.OFFENSE, DEPTH_CHART) is None
    with pytest.raises(ValueError, match="defense formation"):
        four_three = get_formation(Unit.DEFENSE, "4-3")
        assert four_three is not None
        fill_formation(NFL_OFFENSE, four_three)
