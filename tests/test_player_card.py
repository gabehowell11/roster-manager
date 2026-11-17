"""Tests for PlayerCard and its color helpers, run offscreen."""

import pytest

from rostermanager.models import Player, Team
from rostermanager.ui.player_card import (
    PlayerCard,
    contrast_ratio,
    format_height,
    text_color,
)

pytestmark = pytest.mark.usefixtures("qapp")

TEAM = Team(
    abbreviation="XYZ", name="Example City", primary_color="#112266", secondary_color="#FFCC00"
)


def make_player(**overrides: object) -> Player:
    data: dict[str, object] = {
        "name": "Quinn Starter",
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
    data.update(overrides)
    return Player.model_validate(data)


def test_starter_card_shows_player_info_in_team_colors() -> None:
    card = PlayerCard(make_player(), TEAM, starter=True)
    assert card.top_label.text() == "#12  QB"
    assert card.name_label.text() == "Quinn Starter"
    assert card.rating_label.text() == "Rating 88"
    assert card.background == "#112266"
    assert card.foreground == "#FFCC00"
    assert "Somewhere State" in card.toolTip()
    assert "6'4\"" in card.toolTip()


def test_backup_card_is_smaller_and_muted() -> None:
    starter = PlayerCard(make_player(), TEAM, starter=True)
    backup = PlayerCard(make_player(depth_order=2), TEAM, starter=False)
    assert backup.width() < starter.width()
    assert backup.height() < starter.height()
    assert backup.background != TEAM.primary_color
    assert "Backup (depth 2)" in backup.toolTip()


def test_missing_optional_fields_show_placeholders() -> None:
    player = make_player(jersey_number=None, rating=None, height=None, weight=None, college=None)
    card = PlayerCard(player, TEAM, starter=True)
    assert card.top_label.text() == "#--  QB"
    assert card.rating_label.text() == "Rating --"
    assert "College: -" in card.toolTip()


def test_unreadable_secondary_color_falls_back_to_black_or_white() -> None:
    dark = Team(abbreviation="DRK", name="Dark", primary_color="#101010", secondary_color="#202020")
    light = Team(
        abbreviation="LGT", name="Light", primary_color="#F0F0F0", secondary_color="#FFFFFF"
    )
    assert PlayerCard(make_player(), dark, starter=True).foreground == "#FFFFFF"
    assert PlayerCard(make_player(), light, starter=True).foreground == "#000000"


def test_contrast_ratio_bounds() -> None:
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21)
    assert contrast_ratio("#777777", "#777777") == pytest.approx(1)
    assert text_color("#000000", "#FFFFFF") == "#FFFFFF"


def test_format_height() -> None:
    assert format_height(74) == "6'2\""
    assert format_height(None) == "-"
