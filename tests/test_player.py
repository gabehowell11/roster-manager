"""Tests for the Player model."""

from typing import Any

import pytest
from pydantic import ValidationError

from rostermanager.models import Player, Unit


def make_player(**overrides: Any) -> Player:
    fields: dict[str, Any] = {
        "name": "Test Player",
        "position": "QB",
        "jersey_number": 12,
        "unit": "offense",
        "height": 76,
        "weight": 225,
        "college": "Somewhere State",
        "years_experience": 5,
        "rating": 88,
        "depth_order": 1,
    }
    fields.update(overrides)
    return Player(**fields)


def test_valid_player_keeps_all_fields() -> None:
    player = make_player()

    assert player.name == "Test Player"
    assert player.position == "QB"
    assert player.jersey_number == 12
    assert player.unit is Unit.OFFENSE
    assert player.height == 76
    assert player.weight == 225
    assert player.college == "Somewhere State"
    assert player.years_experience == 5
    assert player.rating == 88
    assert player.depth_order == 1


def test_optional_fields_default_sensibly() -> None:
    player = Player(name="Minimal", position="K", unit="special_teams", depth_order=2)

    assert player.jersey_number is None
    assert player.height is None
    assert player.weight is None
    assert player.college is None
    assert player.years_experience == 0
    assert player.rating is None


def test_text_is_trimmed_and_position_uppercased() -> None:
    player = make_player(name="  Sam Example ", position=" wr ")

    assert player.name == "Sam Example"
    assert player.position == "WR"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Offense", Unit.OFFENSE), ("DEFENSE", Unit.DEFENSE), ("special teams", Unit.SPECIAL_TEAMS)],
)
def test_unit_accepts_loose_spellings(raw: str, expected: Unit) -> None:
    assert make_player(unit=raw).unit is expected


def test_blank_college_becomes_none() -> None:
    assert make_player(college="   ").college is None


@pytest.mark.parametrize(
    ("raw", "inches"),
    [(74, 74), ("74", 74), ("6-2", 74), ("6'2", 74), ("6' 2\"", 74), ("5-11", 71), ("", None)],
)
def test_height_parses_inches_and_feet_inches(raw: object, inches: int | None) -> None:
    assert make_player(height=raw).height == inches


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "   "),
        ("position", ""),
        ("position", "TOOLONG"),
        ("jersey_number", -1),
        ("jersey_number", 100),
        ("unit", "goalie"),
        ("height", 30),
        ("height", "6-13"),
        ("height", "tall"),
        ("weight", 50),
        ("weight", 600),
        ("years_experience", -1),
        ("rating", -1),
        ("rating", 100),
        ("depth_order", 0),
    ],
)
def test_invalid_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        make_player(**{field: value})


def test_depth_order_is_required() -> None:
    with pytest.raises(ValidationError):
        Player(name="No Depth", position="QB", unit="offense")  # type: ignore[call-arg]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_player(team="XYZ")


def test_rating_edits_are_validated() -> None:
    player = make_player(rating=None)

    player.rating = 75
    assert player.rating == 75

    with pytest.raises(ValidationError):
        player.rating = 150
    assert player.rating == 75
