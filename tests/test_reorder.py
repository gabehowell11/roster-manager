"""Tests for reordering the depth chart from the field view, run offscreen."""

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt
from PySide6.QtGui import QDropEvent

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services import PlayerKey, RosterService
from rostermanager.services.depth_editing import find_player
from rostermanager.ui.player_card import PLAYER_MIME, PlayerCard, decode_key, encode_key
from rostermanager.ui.player_dialog import PlayerDialog
from rostermanager.ui.team_view import TeamView

pytestmark = pytest.mark.usefixtures("qapp")

TEAM = Team(abbreviation="XYZ", name="Example City")
QB1 = PlayerKey(Unit.OFFENSE, "QB", 1)
QB2 = PlayerKey(Unit.OFFENSE, "QB", 2)
QB3 = PlayerKey(Unit.OFFENSE, "QB", 3)
RB1 = PlayerKey(Unit.OFFENSE, "RB", 1)


@pytest.fixture
def service(tmp_path: Path) -> RosterService:
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    service.repo.save_roster(
        Roster(
            team=TEAM,
            players=[
                Player(name="QB A", position="QB", unit="offense", depth_order=1),
                Player(name="QB B", position="QB", unit="offense", depth_order=2),
                Player(name="QB C", position="QB", unit="offense", depth_order=3),
                Player(name="Runner", position="RB", unit="offense", depth_order=1),
                Player(name="Corner", position="LCB", unit="defense", depth_order=1),
            ],
        )
    )
    return service


@pytest.fixture
def view(service: RosterService) -> TeamView:
    view = TeamView(service)
    view.set_roster(service.load_roster("XYZ"))
    return view


def qb_names(view: TeamView) -> list[str]:
    return [card.player.name for card in view.field.slot_cards["QB"]]


def test_key_round_trips_through_drag_data() -> None:
    assert decode_key(encode_key(QB2)) == QB2
    assert decode_key(b"junk") is None


def test_menu_enables_only_possible_moves(view: TeamView) -> None:
    starter, middle, last = view.field.slot_cards["QB"]
    enabled = {
        card.player.name: {n: e for n, _l, e in card.menu_actions()}
        for card in (starter, middle, last)
    }
    always = {"edit": True, "delete": True}
    assert enabled["QB A"] == {**always, "starter": False, "up": False, "down": True}
    assert enabled["QB B"] == {**always, "starter": True, "up": True, "down": True}
    assert enabled["QB C"] == {**always, "starter": True, "up": True, "down": False}


@pytest.mark.parametrize(
    ("action", "key", "expected"),
    [
        ("starter", QB3, ["QB C", "QB A", "QB B"]),
        ("up", QB2, ["QB B", "QB A", "QB C"]),
        ("down", QB1, ["QB B", "QB A", "QB C"]),
    ],
)
def test_menu_actions_save_and_redraw(
    view: TeamView, service: RosterService, action: str, key: PlayerKey, expected: list[str]
) -> None:
    card = next(c for c in view.field.slot_cards["QB"] if c.key == key)
    card.action_requested.emit(card.player, action)
    assert qb_names(view) == expected
    assert [
        p.name
        for p in sorted(
            (p for p in service.load_roster("XYZ").players if p.position == "QB"),
            key=lambda p: p.depth_order,
        )
    ] == expected


def test_impossible_action_shows_error(view: TeamView) -> None:
    errors: list[str] = []

    def record(text: str) -> None:
        errors.append(text)

    view.show_error = record  # type: ignore[method-assign]
    starter = view.field.slot_cards["QB"][0]
    view.run_action(starter.player, "up")
    assert errors and "already the starter" in errors[0]


def drop(target: PlayerCard, key: PlayerKey) -> bool:
    mime = QMimeData()
    mime.setData(PLAYER_MIME, encode_key(key))
    event = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    target.dropEvent(event)
    return event.isAccepted()


def test_dropping_a_backup_on_another_slot_swaps_them(
    view: TeamView, service: RosterService
) -> None:
    runner = view.field.slot_cards["RB"][0]
    assert drop(runner, QB2)
    roster = service.load_roster("XYZ")
    assert find_player(roster, RB1).name == "QB B"
    assert find_player(roster, QB2).name == "Runner"
    assert view.field.slot_cards["RB"][0].player.name == "QB B"


def test_drop_on_itself_or_other_unit_is_ignored(view: TeamView) -> None:
    qb = view.field.slot_cards["QB"][0]
    assert not drop(qb, QB1)
    assert not drop(qb, PlayerKey(Unit.DEFENSE, "LCB", 1))
    assert qb_names(view) == ["QB A", "QB B", "QB C"]


def test_dialog_depth_buttons_save_immediately(service: RosterService) -> None:
    player = find_player(service.load_roster("XYZ"), QB3)
    dialog = PlayerDialog(service, TEAM, player)
    assert not dialog.down_button.isEnabled()

    dialog.up_button.click()
    assert dialog.depth_label.text() == "Backup #1 at QB (depth 2)"
    assert dialog.down_button.isEnabled()
    dialog.starter_button.click()
    assert dialog.depth_label.text() == "Starter at QB"
    assert not dialog.up_button.isEnabled()
    assert find_player(service.load_roster("XYZ"), QB1).name == "QB C"

    dialog.rating.setValue(70)  # a later Save edits the player at their new depth
    dialog.save()
    assert find_player(service.load_roster("XYZ"), QB1).rating == 70


def test_click_still_opens_editor_after_drag_support(view: TeamView) -> None:
    opened: list[str] = []

    def fake_dialog(player: Player) -> Roster | None:
        opened.append(player.name)
        return None

    view.run_player_dialog = fake_dialog  # type: ignore[method-assign]
    card = view.field.slot_cards["QB"][1]
    card.clicked.emit(card.player)
    assert opened == ["QB B"]
    assert card.slot_size == 3
