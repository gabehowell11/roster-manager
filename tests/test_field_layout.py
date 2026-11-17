"""Tests for the field layout service."""

import pytest

from rostermanager.models import DepthChart, Player, Unit
from rostermanager.services import FieldSpot, layout_depth_chart, layout_slots
from rostermanager.services.field_layout import OVERFLOW_Y

OFFENSE = ["QB", "RB", "WR1", "WR2", "WR3", "TE", "LT", "LG", "C", "RG", "RT"]
DEFENSE_43 = ["LDE", "LDT", "RDT", "RDE", "WLB", "MLB", "SLB", "LCB", "RCB", "FS", "SS"]
DEFENSE_34 = ["LDE", "NT", "RDE", "LOLB", "LILB", "RILB", "ROLB", "LCB", "RCB", "FS", "SS"]


def in_bounds(spot: FieldSpot) -> bool:
    return 0 <= spot.x <= 1 and 0 <= spot.y <= 1


@pytest.mark.parametrize(
    ("unit", "labels"),
    [(Unit.OFFENSE, OFFENSE), (Unit.DEFENSE, DEFENSE_43), (Unit.DEFENSE, DEFENSE_34)],
)
def test_standard_formations_fit_without_overflow(unit: Unit, labels: list[str]) -> None:
    spots = layout_slots(unit, labels)
    assert list(spots) == labels
    assert len(set(spots.values())) == len(labels)
    assert all(in_bounds(spot) and spot.y != OVERFLOW_Y for spot in spots.values())


def test_offense_line_is_left_to_right_and_qb_behind_center() -> None:
    spots = layout_slots(Unit.OFFENSE, OFFENSE)
    xs = [spots[label].x for label in ("LT", "LG", "C", "RG", "RT")]
    assert xs == sorted(xs)
    assert spots["QB"].x == spots["C"].x
    assert spots["C"].y < spots["QB"].y < spots["RB"].y


def test_defense_safeties_are_deeper_than_the_line() -> None:
    spots = layout_slots(Unit.DEFENSE, DEFENSE_43)
    assert spots["FS"].y < spots["MLB"].y < spots["LDT"].y
    assert spots["LCB"].x < spots["RCB"].x


def test_numbered_group_labels_pick_their_spot() -> None:
    forward = layout_slots(Unit.OFFENSE, ["WR1", "WR2"])
    backward = layout_slots(Unit.OFFENSE, ["WR2", "WR1"])
    assert forward == backward


def test_unnumbered_group_labels_take_free_spots() -> None:
    spots = layout_slots(Unit.DEFENSE, ["CB", "LCB", "S", "DE"])
    assert spots["LCB"] != spots["CB"]
    assert len(set(spots.values())) == 4
    assert all(spot.y != OVERFLOW_Y for spot in spots.values())


def test_unknown_labels_go_to_overflow_row_in_order() -> None:
    spots = layout_slots(Unit.OFFENSE, ["QB", "JOKER", "X9"])
    assert spots["QB"].y != OVERFLOW_Y
    assert spots["JOKER"].y == spots["X9"].y == OVERFLOW_Y
    assert spots["JOKER"].x < spots["X9"].x


def test_too_many_of_a_group_overflow_instead_of_overlapping() -> None:
    labels = ["QB1", "QB2", "WR1", "WR2", "WR3", "WR4", "WR5"]
    spots = layout_slots(Unit.OFFENSE, labels)
    assert spots["QB2"].y == OVERFLOW_Y
    assert spots["WR5"].y == OVERFLOW_Y
    assert len(set(spots.values())) == len(labels)


def test_out_of_range_number_still_uses_a_free_group_spot() -> None:
    spots = layout_slots(Unit.OFFENSE, ["WR5"])
    assert spots["WR5"].y != OVERFLOW_Y


def test_offense_labels_on_defense_are_unknown() -> None:
    spots = layout_slots(Unit.DEFENSE, ["QB"])
    assert spots["QB"].y == OVERFLOW_Y


def test_special_teams_uses_a_grid() -> None:
    labels = ["K", "P", "LS", "H", "KR", "PR", "GUN1"]
    spots = layout_slots(Unit.SPECIAL_TEAMS, labels)
    assert len(set(spots.values())) == len(labels)
    assert all(in_bounds(spot) for spot in spots.values())
    assert spots["GUN1"].y > spots["K"].y  # seventh label starts a second row


def test_empty_labels() -> None:
    assert layout_slots(Unit.OFFENSE, []) == {}
    assert layout_slots(Unit.SPECIAL_TEAMS, []) == {}


def test_layout_depth_chart_uses_slots() -> None:
    chart = DepthChart(
        unit=Unit.DEFENSE,
        players=[
            Player(name="A", position="LCB", unit="defense", depth_order=1),
            Player(name="B", position="LCB", unit="defense", depth_order=2),
            Player(name="C", position="FS", unit="defense", depth_order=1),
        ],
    )
    assert list(layout_depth_chart(chart)) == ["LCB", "FS"]
