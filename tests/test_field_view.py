"""Tests for FieldView and the team view's offense/defense toggle, run offscreen."""

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services import RosterService
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


def test_team_view_toggles_between_offense_and_defense(tmp_path: Path) -> None:
    view = TeamView(RosterService(RosterRepository(tmp_path / "r.db")))
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


def test_team_view_shows_special_teams(tmp_path: Path) -> None:
    roster = Roster(
        team=TEAM,
        players=[
            *players("special_teams", "PK", 1),
            *players("special_teams", "P", 1),
            *players("special_teams", "KR", 2),
        ],
    )
    view = TeamView(RosterService(RosterRepository(tmp_path / "r.db")))
    view.set_roster(roster)
    view.unit_buttons[Unit.SPECIAL_TEAMS].click()
    assert view.unit is Unit.SPECIAL_TEAMS
    assert view.unit_buttons[Unit.SPECIAL_TEAMS].text() == "Special Teams"
    assert set(view.field.slot_cards) == {"PK", "P", "KR"}
    assert view.field.line_of_scrimmage_y() is not None


FULL = Roster(
    team=TEAM,
    players=[
        *players("offense", "QB", 2),
        *players("offense", "RB", 2),
        *players("offense", "TE", 3),
        *players("offense", "WR1", 1),
        *players("offense", "WR2", 1),
        *[p for label in ("LT", "LG", "C", "RG", "RT") for p in players("offense", label, 1)],
        *players("defense", "LCB", 2),
    ],
)


def test_formation_picker_redraws_field_and_remembers_per_unit(tmp_path: Path) -> None:
    view = TeamView(RosterService(RosterRepository(tmp_path / "r.db")))
    view.set_roster(FULL)
    assert view.formation_picker.currentText() == "Depth chart"
    assert set(view.field.slot_cards) == {
        "QB",
        "RB",
        "TE",
        "WR1",
        "WR2",
        "LT",
        "LG",
        "C",
        "RG",
        "RT",
    }

    view.formation_picker.setCurrentText("Goal Line (23)")
    assert view.field.formation is not None
    assert view.field.slot_cards["TE2"][0].player.name == "TE 2"
    assert view.field.slot_cards["FB"][0].player.name == "RB 2"
    assert view.field.open_cards == {}

    view.unit_buttons[Unit.DEFENSE].click()
    assert view.formation_picker.currentText() == "Depth chart"
    view.formation_picker.setCurrentText("4-3")
    assert "LDE" in view.field.open_cards  # a corners-only defense leaves the front open
    assert view.field.slot_cards["LCB"][0].player.name == "LCB 1"

    view.unit_buttons[Unit.OFFENSE].click()
    assert view.formation_picker.currentText() == "Goal Line (23)"

    view.unit_buttons[Unit.SPECIAL_TEAMS].click()
    assert view.formation_picker.isHidden()


def test_formation_cards_still_edit_the_real_slot(tmp_path: Path) -> None:
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    service.repo.save_roster(FULL)
    view = TeamView(service)
    view.set_roster(service.load_roster("XYZ"))
    view.formation_picker.setCurrentText("Goal Line (23)")

    te3 = view.field.slot_cards["TE3"][0]
    assert te3.slot_size == 3
    te3.action_requested.emit(te3.player, "starter")  # TE 3 becomes the TE starter

    assert view.formation_picker.currentText() == "Goal Line (23)"
    assert view.field.slot_cards["TE1"][0].player.name == "TE 3"


def test_backups_stack_straight_down_under_the_starter() -> None:
    for unit, label in ((Unit.OFFENSE, "WR1"), (Unit.DEFENSE, "LCB")):
        field = field_for(unit)
        starter, *backups = field.slot_cards[label]
        for backup in backups:
            assert abs(backup.geometry().center().x() - starter.geometry().center().x()) <= 1


def stacking(field: FieldView) -> list[PlayerCard]:
    """Cards from bottom to top (later siblings draw on top)."""
    return [child for child in field.children() if isinstance(child, PlayerCard)]


def test_hovering_a_backup_brings_it_in_front_of_the_starter() -> None:
    field = field_for(Unit.OFFENSE)
    starter, first, second, third = field.slot_cards["WR1"]

    QApplication.sendEvent(second, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    assert stacking(field)[-1] is second

    # Sliding onto the next backup: the old one's leave restores, then the new one lifts.
    QApplication.sendEvent(second, QEvent(QEvent.Type.Leave))
    QApplication.sendEvent(third, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    assert stacking(field)[-1] is third

    QApplication.sendEvent(third, QEvent(QEvent.Type.Leave))
    order = stacking(field)
    assert order.index(starter) > order.index(first) > order.index(second) > order.index(third)


def test_a_late_leave_does_not_drop_the_newly_lifted_backup() -> None:
    field = field_for(Unit.OFFENSE)
    _, first, second, _ = field.slot_cards["WR1"]
    QApplication.sendEvent(second, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    QApplication.sendEvent(first, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    QApplication.sendEvent(second, QEvent(QEvent.Type.Leave))
    assert stacking(field)[-1] is first


def test_hovering_the_starter_keeps_it_in_front() -> None:
    field = field_for(Unit.OFFENSE)
    starter, backup = field.slot_cards["QB"]
    QApplication.sendEvent(backup, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    QApplication.sendEvent(starter, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    order = stacking(field)
    assert order.index(starter) > order.index(backup)
