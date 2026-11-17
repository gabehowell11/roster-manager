"""Tests for clicking a card and editing a player, run offscreen."""

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services import PlayerKey, RosterService
from rostermanager.services.depth_editing import find_player
from rostermanager.ui.player_card import PlayerCard
from rostermanager.ui.player_dialog import PlayerDialog, depth_text
from rostermanager.ui.team_view import TeamView

pytestmark = pytest.mark.usefixtures("qapp")

TEAM = Team(abbreviation="XYZ", name="Example City", primary_color="#E31837")
QB1 = PlayerKey(Unit.OFFENSE, "QB", 1)
QB2 = PlayerKey(Unit.OFFENSE, "QB", 2)


@pytest.fixture
def service(tmp_path: Path) -> RosterService:
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    service.repo.save_roster(
        Roster(
            team=TEAM,
            players=[
                Player(
                    name="Quinn Starter",
                    position="QB",
                    unit="offense",
                    jersey_number=12,
                    height=76,
                    weight=225,
                    college="Somewhere State",
                    years_experience=5,
                    rating=88,
                    depth_order=1,
                ),
                Player(name="Quincy Backup", position="QB", unit="offense", depth_order=2),
            ],
        )
    )
    return service


def dialog_for(service: RosterService, key: PlayerKey) -> PlayerDialog:
    return PlayerDialog(service, TEAM, find_player(service.load_roster("XYZ"), key))


def test_dialog_shows_every_field(service: RosterService) -> None:
    dialog = dialog_for(service, QB1)
    assert dialog.heading.text() == "Quinn Starter"
    assert dialog.depth_label.text() == "Starter at QB"
    assert dialog.position.text() == "QB"
    assert dialog.unit.currentData() == Unit.OFFENSE.value
    assert dialog.jersey.value() == 12
    assert dialog.height_input.text() == "6-4"
    assert dialog.weight.value() == 225
    assert dialog.college.text() == "Somewhere State"
    assert dialog.experience.value() == 5
    assert dialog.rating.value() == 88
    assert dialog.changes() == {}


def test_unset_fields_show_as_not_set(service: RosterService) -> None:
    dialog = dialog_for(service, QB2)
    assert dialog.rating.text() == "No rating"
    assert dialog.jersey.text() == "-"
    assert dialog.height_input.text() == ""
    assert dialog.changes() == {}
    assert depth_text(dialog.player) == "Backup #1 at QB (depth 2)"


def test_save_rating_and_details(service: RosterService) -> None:
    dialog = dialog_for(service, QB1)
    dialog.rating.setValue(91)
    dialog.height_input.setText("6-3")
    dialog.college.setText("")
    dialog.save()

    assert dialog.result() == PlayerDialog.DialogCode.Accepted
    player = find_player(service.load_roster("XYZ"), QB1)
    assert (player.rating, player.height, player.college) == (91, 75, None)
    assert dialog.roster is not None


def test_clear_rating(service: RosterService) -> None:
    dialog = dialog_for(service, QB1)
    dialog.rating.setValue(dialog.rating.minimum())
    assert dialog.changes() == {"rating": None}
    dialog.save()
    assert find_player(service.load_roster("XYZ"), QB1).rating is None


def test_invalid_input_shows_error_and_saves_nothing(service: RosterService) -> None:
    before = service.load_roster("XYZ")
    dialog = dialog_for(service, QB1)
    dialog.height_input.setText("tall")
    dialog.save()
    assert not dialog.error_label.isHidden()
    assert "height" in dialog.error_label.text()
    assert dialog.roster is None
    assert service.load_roster("XYZ") == before


def test_delete_player_after_confirming(service: RosterService) -> None:
    dialog = dialog_for(service, QB1)
    dialog.confirm = lambda text: False  # type: ignore[method-assign]
    dialog.delete_player()
    assert len(service.load_roster("XYZ").players) == 2

    dialog.confirm = lambda text: True  # type: ignore[method-assign]
    dialog.delete_player()
    roster = service.load_roster("XYZ")
    assert [p.name for p in roster.players] == ["Quincy Backup"]
    assert find_player(roster, QB1).name == "Quincy Backup"


def test_clicking_a_card_emits_its_player() -> None:
    player = Player(name="Q", position="QB", unit="offense", depth_order=1)
    card = PlayerCard(player, TEAM, starter=True)
    seen: list[object] = []
    card.clicked.connect(seen.append)
    for kind in (QMouseEvent.Type.MouseButtonPress, QMouseEvent.Type.MouseButtonRelease):
        event = QMouseEvent(
            kind,
            QPointF(10, 10),
            QPointF(10, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(card, event)
    assert seen == [player]


def test_team_view_redraws_after_an_edit(service: RosterService) -> None:
    view = TeamView(service)
    view.set_roster(service.load_roster("XYZ"))

    def edit(player: Player) -> Roster:
        return service.update_player("XYZ", PlayerKey.of(player), {"rating": 42})

    view.run_player_dialog = edit  # type: ignore[method-assign]
    starter = view.field.slot_cards["QB"][0]
    starter.clicked.emit(starter.player)

    assert view.field.slot_cards["QB"][0].rating_label.text() == "Rating 42"
