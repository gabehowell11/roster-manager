"""Guards for the layering rules in CLAUDE.md."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Modules that must import without pulling in PySide6.
GUI_FREE_MODULES = [
    "rostermanager",
    "rostermanager.models",
    "rostermanager.data",
    "rostermanager.services",
]


@pytest.mark.parametrize("module", GUI_FREE_MODULES)
def test_module_does_not_import_pyside6(module: str) -> None:
    # A fresh interpreter, so modules imported by other tests can't hide a leak.
    code = f"import sys, {module}; print('PySide6' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False", f"{module} imports PySide6"


def test_entry_point_exposes_main() -> None:
    from rostermanager.__main__ import main

    assert callable(main)


def test_ui_never_imports_the_data_layer() -> None:
    # CLAUDE.md: the UI calls services and never touches SQLite or importers directly.
    ui_dir = Path(__file__).parent.parent / "src" / "rostermanager" / "ui"
    banned = re.compile(r"^\s*(from|import)\s+(rostermanager\.data|sqlite3)\b", re.MULTILINE)
    offenders = [p.name for p in ui_dir.glob("*.py") if banned.search(p.read_text("utf-8"))]
    assert offenders == []
