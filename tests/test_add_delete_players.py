"""Tests for adding players and deleting them from anywhere, run offscreen."""

from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services import PlayerKey, RosterService
from rostermanager.services.depth_editing import find_player, slot_players
from rostermanager.ui.overlay import BlurOverlay, confirm_over
from rostermanager.ui.player_dialog import AddPlayerDialog, PlayerDialog, delete_question
from rostermanager.ui.team_view import TeamView

pytestmark = pytest.mark.usefixtures("qapp")

TEAM = Team(abbreviation="XYZ", name="Example City", primary_color="#E31837")


@pytest.fixture
def service(tmp_path: Path) -> RosterService:
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    service.repo.save_roster(
        Roster(
            team=TEAM,
            players=[
                Player(name="Starter QB", position="QB", unit="offense", depth_order=1),
                Player(name="Backup QB", position="QB", unit="offense", depth_order=2),
                Player(name="Corner", position="LCB", unit="defense", depth_order=1),
            ],
        )
    )
    return service


@pytest.fixture
def view(service: RosterService) -> TeamView:
    view = TeamView(service)
    view.resize(1200, 800)
    view.show()
    view.set_roster(service.load_roster("XYZ"))
    return view


def player_names(service: RosterService) -> list[str]:
    return [p.name for p in service.load_roster("XYZ").players]


# Adding


def test_add_dialog_starts_blank_on_the_current_unit(service: RosterService) -> None:
    dialog = AddPlayerDialog(service, TEAM, Unit.DEFENSE)
    assert dialog.heading.text() == "Add player"
    assert dialog.name.text() == ""
    assert dialog.position.text() == ""
    assert dialog.unit.currentData() == Unit.DEFENSE.value
    assert dialog.save_button.text() == "Add player"
    assert dialog.delete_button.isHidden()
    assert dialog.starter_button.isHidden()


def test_add_dialog_requires_name_and_position(service: RosterService) -> None:
    dialog = AddPlayerDialog(service, TEAM)
    dialog.save()
    assert "name" in dialog.error_label.text()
    dialog.name.setText("New Guy")
    dialog.save()
    assert "position" in dialog.error_label.text()
    assert dialog.roster is None
    assert len(player_names(service)) == 3


def test_add_dialog_adds_as_last_backup_by_default(service: RosterService) -> None:
    dialog = AddPlayerDialog(service, TEAM)
    dialog.name.setText("New Guy")
    dialog.position.setText("qb")
    dialog.jersey.setValue(7)
    dialog.rating.setValue(70)
    dialog.save()
    assert dialog.result() == PlayerDialog.DialogCode.Accepted
    added = find_player(service.load_roster("XYZ"), PlayerKey(Unit.OFFENSE, "QB", 3))
    assert (added.name, added.jersey_number, added.rating) == ("New Guy", 7, 70)


def test_add_dialog_can_add_a_starter(service: RosterService) -> None:
    dialog = AddPlayerDialog(service, TEAM)
    dialog.name.setText("New Guy")
    dialog.position.setText("QB")
    dialog.starter_check.setChecked(True)
    dialog.save()
    qbs = slot_players(service.load_roster("XYZ"), Unit.OFFENSE, "QB")
    assert [p.name for p in qbs] == ["New Guy", "Starter QB", "Backup QB"]


def test_add_dialog_shows_bad_values_and_saves_nothing(service: RosterService) -> None:
    dialog = AddPlayerDialog(service, TEAM)
    dialog.name.setText("New Guy")
    dialog.position.setText("QB")
    dialog.height_input.setText("12 feet")
    dialog.save()
    assert "height" in dialog.error_label.text()
    assert dialog.roster is None
    assert "New Guy" not in player_names(service)


def test_add_button_opens_editor_over_the_window(view: TeamView) -> None:
    view.show_unit(Unit.DEFENSE)
    seen: dict[str, object] = {}

    def fill_and_add() -> None:
        dialog = view.window().findChild(AddPlayerDialog)
        assert dialog is not None
        seen["overlay"] = isinstance(dialog.parent(), BlurOverlay)
        seen["unit"] = dialog.unit.currentData()
        dialog.name.setText("Safety Sam")
        dialog.position.setText("FS")
        dialog.save()

    QTimer.singleShot(0, fill_and_add)
    view.add_button.click()
    assert seen == {"overlay": True, "unit": Unit.DEFENSE.value}
    assert "FS" in view.field.slot_cards  # redrawn with the new player
    assert "Safety Sam" in [p.name for p in view.roster_panel.listed_players()]


def test_cancelled_add_changes_nothing(view: TeamView, service: RosterService) -> None:
    def cancel() -> None:
        dialog = view.window().findChild(AddPlayerDialog)
        assert dialog is not None
        dialog.reject()

    QTimer.singleShot(0, cancel)
    view.add_button.click()
    assert len(player_names(service)) == 3


# Deleting


def test_delete_question_asks_are_you_sure() -> None:
    player = Player(name="Starter QB", position="QB", unit="offense", depth_order=1)
    assert delete_question(player).startswith("Are you sure you want to delete Starter QB")


@pytest.mark.parametrize("answer", [True, False])
def test_card_menu_delete_asks_first(view: TeamView, service: RosterService, answer: bool) -> None:
    asked: list[str] = []

    def confirm(text: str) -> bool:
        asked.append(text)
        return answer

    view.confirm = confirm  # type: ignore[method-assign]
    starter = view.field.slot_cards["QB"][0]
    starter.action_requested.emit(starter.player, "delete")
    assert len(asked) == 1
    assert "Starter QB" in asked[0]
    qbs = [p.name for p in slot_players(service.load_roster("XYZ"), Unit.OFFENSE, "QB")]
    assert qbs == (["Backup QB"] if answer else ["Starter QB", "Backup QB"])
    if answer:  # the backup moved up and the field shows it
        assert view.field.slot_cards["QB"][0].player.name == "Backup QB"


def test_roster_list_menu_can_edit_and_delete(view: TeamView, service: RosterService) -> None:
    view.confirm = lambda text: True  # type: ignore[method-assign]
    opened: list[Player] = []

    def fake_editor(player: Player) -> Roster | None:
        opened.append(player)
        return None

    view.run_player_dialog = fake_editor  # type: ignore[method-assign]
    panel = view.roster_panel
    corner = next(row for row in panel.player_rows if row[0].name == "Corner")
    corner[1].action_requested.emit("edit")
    assert [p.name for p in opened] == ["Corner"]
    corner[1].action_requested.emit("delete")
    assert "Corner" not in player_names(service)
    assert "Corner" not in [p.name for p in panel.listed_players()]


def test_confirm_over_opens_in_app_and_defaults_to_cancel(view: TeamView) -> None:
    seen: dict[str, object] = {}

    def check_and_answer() -> None:
        box = view.window().findChild(QMessageBox)
        assert box is not None
        seen["overlay"] = isinstance(box.parent(), BlurOverlay)
        default = box.defaultButton()
        assert default is not None
        seen["default"] = default.text()
        default.click()

    QTimer.singleShot(0, check_and_answer)
    assert confirm_over(view.window(), "Delete player?", "Sure?", yes_text="Delete") is False
    assert seen == {"overlay": True, "default": "Cancel"}


def test_confirm_over_delete_returns_true(view: TeamView) -> None:
    def press_delete() -> None:
        box = view.window().findChild(QMessageBox)
        assert box is not None
        next(b for b in box.buttons() if b.text() == "Delete").click()

    QTimer.singleShot(0, press_delete)
    assert confirm_over(view.window(), "Delete player?", "Sure?", yes_text="Delete") is True
