"""Tests for the Team model."""

import pytest
from pydantic import ValidationError

from rostermanager.models import Team


def test_team_normalizes_abbreviation_and_colors() -> None:
    team = Team(abbreviation=" xyz ", name="Example City", primary_color="#a1b2c3")

    assert team.abbreviation == "XYZ"
    assert team.name == "Example City"
    assert team.primary_color == "#A1B2C3"
    assert team.secondary_color == "#FFFFFF"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("abbreviation", "X"),
        ("abbreviation", "TOOLONG"),
        ("abbreviation", "X1"),
        ("name", "  "),
        ("primary_color", "red"),
        ("primary_color", "#12345"),
        ("secondary_color", "123456"),
    ],
)
def test_invalid_team_values_are_rejected(field: str, value: str) -> None:
    fields = {"abbreviation": "XYZ", "name": "Example City", field: value}
    with pytest.raises(ValidationError):
        Team(**fields)
