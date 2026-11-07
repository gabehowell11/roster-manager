"""Guards for the layering rules in CLAUDE.md."""

import subprocess
import sys

import pytest

# Modules that must import without pulling in PySide6.
# Add rostermanager.models, .services and .data here as those packages are created.
GUI_FREE_MODULES = ["rostermanager"]


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
