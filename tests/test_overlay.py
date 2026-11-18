"""Tests for showing the player editor inside the window over a blurred background."""

from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QGraphicsBlurEffect, QLabel, QWidget

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, Team
from rostermanager.services import RosterService
from rostermanager.ui.main_window import MainWindow
from rostermanager.ui.overlay import BlurOverlay, exec_over
from rostermanager.ui.player_dialog import PlayerDialog

pytestmark = pytest.mark.usefixtures("qapp")

TEAM = Team(abbreviation="XYZ", name="Example City", primary_color="#E31837")


def host_and_dialog() -> tuple[QWidget, QDialog]:
    host = QWidget()
    host.resize(900, 700)
    host.show()
    dialog = QDialog()
    dialog.setFixedSize(300, 200)
    return host, dialog


def test_overlay_covers_the_host_with_a_blurred_snapshot() -> None:
    host, dialog = host_and_dialog()
    overlay = BlurOverlay(host, dialog)
    assert overlay.geometry() == host.rect()
    assert isinstance(overlay.backdrop, QLabel)
    assert not overlay.backdrop.pixmap().isNull()
    assert isinstance(overlay.backdrop.graphicsEffect(), QGraphicsBlurEffect)


def test_dialog_is_embedded_and_centered() -> None:
    host, dialog = host_and_dialog()
    BlurOverlay(host, dialog)
    assert not dialog.isWindow()  # inside the app, no title bar to drag it away
    assert (dialog.x(), dialog.y()) == ((900 - 300) // 2, (700 - 200) // 2)


def test_dialog_stays_centered_when_the_window_resizes() -> None:
    host, dialog = host_and_dialog()
    overlay = BlurOverlay(host, dialog)
    host.resize(1300, 900)
    assert overlay.geometry() == host.rect()
    assert dialog.x() == (1300 - 300) // 2
    assert dialog.y() == (900 - 200) // 2


def test_exec_over_returns_the_result_and_removes_the_overlay() -> None:
    host, dialog = host_and_dialog()
    QTimer.singleShot(0, dialog.accept)
    assert exec_over(dialog, host) == QDialog.DialogCode.Accepted
    QApplication.processEvents()
    overlays = [child for child in host.findChildren(BlurOverlay) if child.isVisible()]
    assert overlays == []


def test_clicking_a_card_opens_the_editor_over_the_window(tmp_path: Path) -> None:
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    service.repo.save_roster(
        Roster(team=TEAM, players=[Player(name="Q", position="QB", unit="offense", depth_order=1)])
    )
    window = MainWindow(service)
    window.show()
    window.open_team("XYZ")
    seen: dict[str, object] = {}

    def check_and_close() -> None:
        dialog = window.findChild(PlayerDialog)
        assert dialog is not None
        seen["embedded"] = not dialog.isWindow()
        seen["overlay"] = isinstance(dialog.parent(), BlurOverlay)
        dialog.reject()

    QTimer.singleShot(0, check_and_close)
    card = window.team_view.field.slot_cards["QB"][0]
    card.clicked.emit(card.player)
    assert seen == {"embedded": True, "overlay": True}


def test_number_boxes_show_their_value_when_themed(tmp_path: Path) -> None:
    """Hiding the arrows must not squeeze the text area to nothing."""
    from rostermanager.ui.theme import apply_theme

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_theme(app)
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    player = Player(name="Q", position="QB", unit="offense", depth_order=1, jersey_number=12)
    service.repo.save_roster(Roster(team=TEAM, players=[player]))
    dialog = PlayerDialog(service, TEAM, player)
    dialog.resize(400, 600)
    dialog.show()
    QApplication.processEvents()
    for spin in (dialog.jersey, dialog.weight, dialog.experience, dialog.rating):
        assert spin.lineEdit().width() > spin.width() // 2
