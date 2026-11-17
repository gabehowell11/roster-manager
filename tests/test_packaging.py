"""Tests for what the Windows build relies on: the self-test and the templates."""

from pathlib import Path

import pytest

from rostermanager.__main__ import main
from rostermanager.data import RosterRepository
from rostermanager.services import RosterService, copy_template, template_path
from rostermanager.ui.home_screen import HomeScreen


@pytest.mark.usefixtures("qapp")
def test_self_test_passes_from_source() -> None:
    assert main(["--self-test"]) == 0


def test_templates_are_found_and_copied(tmp_path: Path) -> None:
    for kind in ("csv", "json"):
        assert template_path(kind).is_file()
        copied = copy_template(kind, tmp_path / f"mine.{kind}")
        assert copied.read_bytes() == template_path(kind).read_bytes()
    with pytest.raises(ValueError, match="csv or json"):
        template_path("xlsx")


def test_copied_csv_template_imports(tmp_path: Path) -> None:
    from rostermanager.models import Team

    path = copy_template("csv", tmp_path / "t.csv")
    service = RosterService(RosterRepository(tmp_path / "r.db"))
    roster = service.import_custom_file(path, Team(abbreviation="EXC", name="Example City"))
    assert roster.players


@pytest.mark.usefixtures("qapp")
@pytest.mark.parametrize(
    ("chosen", "expected"), [("a.json", "a.json"), ("b.csv", "b.csv"), ("c", "c.csv")]
)
def test_home_saves_a_template(tmp_path: Path, chosen: str, expected: str) -> None:
    home = HomeScreen(RosterService(RosterRepository(tmp_path / "r.db")))
    home.choose_save_path = lambda: tmp_path / chosen  # type: ignore[method-assign]
    home.save_template()
    assert (tmp_path / expected).is_file()
    assert "Template saved" in home.status_label.text()
