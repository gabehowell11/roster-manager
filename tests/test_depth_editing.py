"""Tests for depth chart and player edits."""

from pathlib import Path

import pytest

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services import EditError, PlayerKey, RosterService
from rostermanager.services import depth_editing as edit

TEAM = Team(abbreviation="XYZ", name="Example City")


def roster() -> Roster:
    return Roster(
        team=TEAM,
        players=[
            Player(name="QB A", position="QB", unit="offense", depth_order=1),
            Player(name="QB B", position="QB", unit="offense", depth_order=2),
            Player(name="QB C", position="QB", unit="offense", depth_order=3),
            Player(name="Left Corner", position="LCB", unit="defense", depth_order=1),
            Player(name="Left Backup", position="LCB", unit="defense", depth_order=2),
            Player(name="Right Corner", position="RCB", unit="defense", depth_order=1),
        ],
    )


def names(r: Roster, unit: Unit, position: str) -> list[str]:
    return [p.name for p in edit.slot_players(r, unit, position)]


QB1 = PlayerKey(Unit.OFFENSE, "QB", 1)
QB2 = PlayerKey(Unit.OFFENSE, "QB", 2)
QB3 = PlayerKey(Unit.OFFENSE, "QB", 3)
LCB1 = PlayerKey(Unit.DEFENSE, "LCB", 1)
LCB2 = PlayerKey(Unit.DEFENSE, "LCB", 2)
RCB1 = PlayerKey(Unit.DEFENSE, "RCB", 1)


def test_promote_swaps_with_player_ahead() -> None:
    assert names(edit.promote(roster(), QB2), Unit.OFFENSE, "QB") == ["QB B", "QB A", "QB C"]


def test_demote_swaps_with_player_behind() -> None:
    assert names(edit.demote(roster(), QB1), Unit.OFFENSE, "QB") == ["QB B", "QB A", "QB C"]


def test_make_starter_shifts_everyone_ahead_down() -> None:
    assert names(edit.make_starter(roster(), QB3), Unit.OFFENSE, "QB") == ["QB C", "QB A", "QB B"]


def test_move_player_renumbers_without_gaps() -> None:
    result = edit.move_player(roster(), QB1, 3)
    slot = edit.slot_players(result, Unit.OFFENSE, "QB")
    assert [p.name for p in slot] == ["QB B", "QB C", "QB A"]
    assert [p.depth_order for p in slot] == [1, 2, 3]


def test_edges_raise_edit_error() -> None:
    with pytest.raises(EditError, match="already the starter"):
        edit.promote(roster(), QB1)
    with pytest.raises(EditError, match="already last"):
        edit.demote(roster(), QB3)
    with pytest.raises(EditError, match="1 to 3"):
        edit.move_player(roster(), QB1, 4)
    with pytest.raises(EditError, match="no offense QB at depth 9"):
        edit.promote(roster(), PlayerKey(Unit.OFFENSE, "QB", 9))


def test_swap_across_slots() -> None:
    result = edit.swap_players(roster(), LCB2, RCB1)
    assert names(result, Unit.DEFENSE, "LCB") == ["Left Corner", "Right Corner"]
    assert names(result, Unit.DEFENSE, "RCB") == ["Left Backup"]


def test_swap_across_units_is_rejected() -> None:
    with pytest.raises(EditError, match="same unit"):
        edit.swap_players(roster(), QB1, LCB1)


def test_update_player_details_and_rating() -> None:
    result = edit.update_player(roster(), QB2, {"rating": 77, "jersey_number": 8, "college": "X U"})
    player = edit.find_player(result, QB2)
    assert (player.rating, player.jersey_number, player.college) == (77, 8, "X U")
    cleared = edit.update_player(result, QB2, {"rating": None})
    assert edit.find_player(cleared, QB2).rating is None


def test_update_player_rejects_bad_values() -> None:
    with pytest.raises(EditError, match="rating"):
        edit.update_player(roster(), QB1, {"rating": 120})
    with pytest.raises(EditError, match="cannot edit depth_order"):
        edit.update_player(roster(), QB1, {"depth_order": 2})


def test_changing_position_moves_player_to_end_of_new_slot() -> None:
    result = edit.update_player(roster(), LCB1, {"position": "RCB"})
    assert names(result, Unit.DEFENSE, "RCB") == ["Right Corner", "Left Corner"]
    assert names(result, Unit.DEFENSE, "LCB") == ["Left Backup"]
    assert edit.find_player(result, LCB1).name == "Left Backup"  # promoted to fill the gap


def test_changing_unit_moves_player() -> None:
    result = edit.update_player(roster(), QB3, {"unit": "special_teams", "position": "H"})
    assert names(result, Unit.SPECIAL_TEAMS, "H") == ["QB C"]
    assert names(result, Unit.OFFENSE, "QB") == ["QB A", "QB B"]


def test_remove_player_moves_backups_up() -> None:
    result = edit.remove_player(roster(), QB1)
    slot = edit.slot_players(result, Unit.OFFENSE, "QB")
    assert [(p.name, p.depth_order) for p in slot] == [("QB B", 1), ("QB C", 2)]


def test_add_player_goes_to_end_of_slot() -> None:
    result = edit.add_player(
        roster(), {"name": "New Guy", "position": "qb", "unit": "offense", "depth_order": 1}
    )
    assert names(result, Unit.OFFENSE, "QB")[-1] == "New Guy"
    assert edit.find_player(result, PlayerKey(Unit.OFFENSE, "QB", 4)).name == "New Guy"
    with pytest.raises(EditError, match="name"):
        edit.add_player(roster(), {"position": "QB", "unit": "offense"})


def test_edits_never_mutate_the_original() -> None:
    original = roster()
    before = original.model_dump()
    edit.promote(original, QB2)
    edit.update_player(original, QB1, {"rating": 50, "position": "WR"})
    assert original.model_dump() == before


def test_service_edits_save_and_failures_save_nothing(tmp_path: Path) -> None:
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    service.repo.save_roster(roster())

    service.promote("XYZ", QB2)
    service.update_player("xyz", QB1, {"rating": 90})
    saved = service.load_roster("XYZ")
    assert names(saved, Unit.OFFENSE, "QB") == ["QB B", "QB A", "QB C"]
    assert edit.find_player(saved, QB1).rating == 90

    with pytest.raises(EditError):
        service.update_player("XYZ", QB1, {"rating": -1})
    assert service.load_roster("XYZ") == saved

    service.swap_players("XYZ", LCB2, RCB1)
    service.remove_player("XYZ", QB3)
    service.add_player("XYZ", {"name": "K", "position": "K", "unit": "special_teams"})
    service.make_starter("XYZ", QB2)
    service.demote("XYZ", QB1)
    service.move_player("XYZ", QB1, 2)
    assert len(service.load_roster("XYZ").players) == 6
