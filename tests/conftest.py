"""Shared fixtures. Qt runs offscreen so UI tests never open real windows."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp() -> Iterator[object]:
    """The one QApplication for the test run. Imported lazily to keep non-UI tests GUI-free."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "rosters.db"
