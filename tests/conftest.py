"""Shared fixtures. Qt runs offscreen so UI tests never open real windows."""

import gc
import os
import sys
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


@pytest.fixture(autouse=True)
def _delete_leftover_widgets() -> Iterator[None]:
    """After each test, close and really delete every top-level widget.

    The app frees detached widgets (deleteLater) from its event loop, which tests
    never run. Without this they pile up until Python exits, some are destroyed
    after the QApplication, and Qt aborts the process even though every test passed.
    """
    yield
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        return
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "rosters.db"
