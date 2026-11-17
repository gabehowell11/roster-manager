"""Tests for FieldView and the team view's offense/defense toggle, run offscreen."""

import pytest

from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.ui.field_view import MAX_BACKUPS_SHOWN, FieldView
from rostermanager.ui.player_card import PlayerCard
from rostermanager.ui.team_view import TeamView

pytestmark = pytest.mark.usefixtures("qapp")

TEAM = Team(abbreviation="XYZ", name="Example City", primary_color="#112266")


def players(unit: str, position: str, count: int) -> list[Player]:
    return [
        Player(name=f"{position} {i}", position=position, unit=unit, depth_order=i)
        for i in range(1, count + 1)
    ]


ROSTER = Roster(
    team=TEAM,
    players=[
        *players("offense", "QB", 2),
        *players("offense", "LT", 1),
        *players("offense", "WR1", 6),
        *players("offense", "JOKER", 1),
        *players("defense", "LCB", 3),
        *players("defense", "FS", 1),
    ],
)


def field_for(unit: Unit) -> FieldView:
    field = FieldView()
    field.resize(1000, 620)
    field.set_depth_chart(ROSTER.depth_chart(unit), TEAM)
    return field


def test_each_slot_gets_starter_and_backup_cards() -> None:
    field = field_for(Unit.OFFENSE)
    assert set(field.slot_cards) == {"QB", "LT", "WR1", "JOKER"}
    qb = field.slot_cards["QB"]
    assert [card.player.name for card in qb] == ["QB 1", "QB 2"]
    assert qb[0].is_starter and not qb[1].is_starter


def test_backups_are_capped() -> None:
    field = field_for(Unit.OFFENSE)
    assert len(field.slot_cards["WR1"]) == MAX_BACKUPS_SHOWN + 1


def test_starter_is_drawn_in_front_of_backups() -> None:
    field = field_for(Unit.OFFENSE)
    order = [child for child in field.children() if isinstance(child, PlayerCard)]
    starter, backup = field.slot_cards["QB"]
    assert order.index(starter) > order.index(backup)  # later sibling = on top


def test_backups_fan_away_from_line_of_scrimmage() -> None:
    offense = field_for(Unit.OFFENSE)
    starter, backup = offense.slot_cards["QB"]
    assert backup.y() > starter.y()

    defense = field_for(Unit.DEFENSE)
    starter, backup, _ = defense.slot_cards["LCB"]
    assert backup.y() < starter.y()


def test_cards_stay_inside_the_field() -> None:
    field = field_for(Unit.OFFENSE)
    for cards in field.slot_cards.values():
        for card in cards:
            assert field.rect().contains(card.geometry())


def test_line_of_scrimmage_sits_between_offense_and_defense_sides() -> None:
    offense = field_for(Unit.OFFENSE)
    defense = field_for(Unit.DEFENSE)
    off_line, def_line = offense.line_of_scrimmage_y(), defense.line_of_scrimmage_y()
    assert off_line is not None and def_line is not None
    assert off_line < offense.slot_cards["LT"][0].y()
    assert def_line > defense.slot_cards["LCB"][0].geometry().bottom() - 40


def test_empty_unit_shows_message() -> None:
    roster = Roster(team=TEAM, players=players("offense", "QB", 1))
    field = FieldView()
    field.set_depth_chart(roster.depth_chart(Unit.DEFENSE), TEAM)
    assert field.slot_cards == {}
    assert field.empty_label.text() == "No defense players."


def test_paint_does_not_crash() -> None:
    field = field_for(Unit.DEFENSE)
    assert not field.grab().isNull()


def shown_unit(view: TeamView) -> Unit:
    assert view.field.chart is not None
    assert view.field.chart.unit is view.unit
    return view.unit


def test_team_view_toggles_between_offense_and_defense() -> None:
    view = TeamView()
    view.set_roster(ROSTER)
    assert view.unit is Unit.OFFENSE
    assert "QB" in view.field.slot_cards

    view.unit_buttons[Unit.DEFENSE].click()
    assert shown_unit(view) is Unit.DEFENSE
    assert set(view.field.slot_cards) == {"LCB", "FS"}
    assert view.unit_buttons[Unit.DEFENSE].isChecked()
    assert not view.unit_buttons[Unit.OFFENSE].isChecked()

    view.set_roster(ROSTER)  # opening a team starts back on offense
    assert shown_unit(view) is Unit.OFFENSE


def test_backups_peek_out_from_behind_the_starter() -> None:
    for unit, label in ((Unit.OFFENSE, "WR1"), (Unit.DEFENSE, "LCB")):
        field = field_for(unit)
        starter, *backups = field.slot_cards[label]
        for backup in backups:
            assert not starter.geometry().contains(backup.geometry()), (unit, backup.player.name)


def test_switching_units_removes_old_cards_immediately() -> None:
    field = field_for(Unit.OFFENSE)
    old = field.slot_cards["QB"][0]
    field.set_depth_chart(ROSTER.depth_chart(Unit.DEFENSE), TEAM)
    cards = [child for child in field.children() if isinstance(child, PlayerCard)]
    assert old not in cards
    assert {card.player.position for card in cards} == {"LCB", "FS"}


def test_stacks_at_the_sideline_stay_inside_the_field() -> None:
    roster = Roster(team=TEAM, players=players("offense", "WR2", 4))  # far right sideline
    field = FieldView()
    field.resize(1000, 620)
    field.set_depth_chart(roster.depth_chart(Unit.OFFENSE), TEAM)
    for card in field.slot_cards["WR2"]:
        assert field.rect().contains(card.geometry())
