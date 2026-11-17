"""Tests for the home screen: downloads in the background and custom imports."""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from rostermanager.data import RosterRepository
from rostermanager.models import Roster, Team
from rostermanager.services import RosterService, TeamDownloadError
from rostermanager.ui.background import BackgroundRunner
from rostermanager.ui.home_screen import HomeScreen
from rostermanager.ui.team_dialog import TeamDialog
from tests.test_nflverse import FakeSource

pytestmark = pytest.mark.usefixtures("qapp")


def wait_for(runner: BackgroundRunner) -> None:
    """Let the thread pool finish, then deliver its queued signals on this thread."""
    for _ in range(200):
        QThreadPool.globalInstance().waitForDone(50)
        QApplication.processEvents()
        if not runner.busy:
            return
    raise AssertionError("background task did not finish")


class OfflineService(RosterService):
    """Downloads use the fake nflverse source; records which thread ran them."""

    def __init__(self, repo: RosterRepository, fail: bool = False) -> None:
        super().__init__(repo)
        self.fail = fail
        self.threads: list[threading.Thread] = []

    def download_nfl_team(
        self, abbreviation: str, season: int | None = None, source: Any = None
    ) -> Roster:
        self.threads.append(threading.current_thread())
        if self.fail:
            raise TeamDownloadError(f"could not download {abbreviation}: no internet")
        return super().download_nfl_team("XYZ", season=2026, source=FakeSource())


@pytest.fixture
def repo(db_path: Path) -> RosterRepository:
    return RosterRepository(db_path)


def make_home(service: RosterService, errors: list[tuple[str, str]]) -> HomeScreen:
    home = HomeScreen(service)

    def record(title: str, details: str) -> None:
        errors.append((title, details))

    home.show_error = record  # type: ignore[method-assign]
    return home


def test_download_runs_in_background_and_adds_team(repo: RosterRepository) -> None:
    service = OfflineService(repo)
    errors: list[tuple[str, str]] = []
    home = make_home(service, errors)

    home.start_download()
    assert not home.download_button.isEnabled()
    assert "Downloading" in home.status_label.text()
    wait_for(home.runner)

    assert service.threads and service.threads[0] is not threading.main_thread()
    assert errors == []
    assert home.download_button.isEnabled()
    assert home.team_list.count() == 1
    assert home.team_list.currentItem().text().splitlines()[0] == "Example City Testers (XYZ)"


def test_download_failure_shows_error(repo: RosterRepository) -> None:
    errors: list[tuple[str, str]] = []
    home = make_home(OfflineService(repo, fail=True), errors)

    home.start_download()
    wait_for(home.runner)

    assert errors and "no internet" in errors[0][1]
    assert home.download_button.isEnabled()
    assert home.team_list.count() == 0


def patch_dialogs(home: HomeScreen, path: Path | None, team: Team | None) -> list[int]:
    asked: list[int] = []
    home.choose_file = lambda: path  # type: ignore[method-assign]

    def ask() -> Team | None:
        asked.append(1)
        return team

    home.ask_team = ask  # type: ignore[method-assign]
    return asked


def test_csv_import_asks_for_team_and_saves(repo: RosterRepository, tmp_path: Path) -> None:
    path = tmp_path / "team.csv"
    path.write_text("name,position,unit,depth_order\nSam,QB,offense,1\n", encoding="utf-8")
    errors: list[tuple[str, str]] = []
    home = make_home(RosterService(repo), errors)
    asked = patch_dialogs(home, path, Team(abbreviation="CUS", name="Custom"))

    home.start_import()

    assert asked == [1]
    assert errors == []
    assert home.team_list.currentItem().text().splitlines()[0] == "Custom (CUS)"


def test_json_import_uses_team_in_file(repo: RosterRepository, tmp_path: Path) -> None:
    path = tmp_path / "team.json"
    path.write_text(
        '{"team": {"abbreviation": "JSN", "name": "Json Town"},'
        ' "players": [{"name": "Sam", "position": "QB", "unit": "offense", "depth_order": 1}]}',
        encoding="utf-8",
    )
    errors: list[tuple[str, str]] = []
    home = make_home(RosterService(repo), errors)
    asked = patch_dialogs(home, path, None)

    home.start_import()

    assert asked == []
    assert home.team_list.count() == 1


def test_import_errors_are_shown_in_full(repo: RosterRepository, tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "name,position,unit,depth_order\nSam,QB,offense,0\nAl,QB,nowhere,1\n", encoding="utf-8"
    )
    errors: list[tuple[str, str]] = []
    home = make_home(RosterService(repo), errors)
    patch_dialogs(home, path, Team(abbreviation="CUS", name="Custom"))

    home.start_import()

    assert len(errors) == 1
    title, details = errors[0]
    assert "bad.csv" in title
    assert "row 2" in details and "row 3" in details
    assert home.team_list.count() == 0


def test_cancelling_dialogs_does_nothing(repo: RosterRepository, tmp_path: Path) -> None:
    errors: list[tuple[str, str]] = []
    home = make_home(RosterService(repo), errors)
    patch_dialogs(home, None, None)
    home.start_import()

    patch_dialogs(home, tmp_path / "team.csv", None)
    home.start_import()

    assert errors == []
    assert home.team_list.count() == 0


def test_team_dialog_validates() -> None:
    dialog = TeamDialog()
    dialog.abbreviation.setText("1")
    dialog.accept()
    assert dialog.team is None
    assert "abbreviation" in dialog.error_label.text()

    dialog.abbreviation.setText("exc")
    dialog.name.setText("Example City")
    dialog.accept()
    assert dialog.team == Team(abbreviation="EXC", name="Example City")


def test_background_runner_reports_errors_on_ui_thread() -> None:
    runner = BackgroundRunner()
    seen: list[tuple[str, threading.Thread]] = []

    def boom() -> None:
        raise ValueError("bad")

    on_error: Callable[[Exception], None] = lambda e: seen.append(
        (str(e), threading.current_thread())
    )
    runner.run(boom, on_done=lambda _r: None, on_error=on_error)
    wait_for(runner)

    assert seen == [("bad", threading.main_thread())]
