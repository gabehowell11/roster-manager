# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Early scaffold. `rostermanager` is a PySide6 desktop app; right now `src/rostermanager/__main__.py`
only opens a placeholder `QLabel` window (smoke test). There is no real architecture yet, so
update this file as modules are added.

Declared dependencies hint at the intended design: `pydantic` for data models, `platformdirs` for
per-user config/data storage locations, and an optional `data` extra (`pandas`, `nflreadpy`) for
importing NFL roster data. `pyinstaller` is in the dev extra for packaging a desktop executable.

## Commands

Requires Python >= 3.12. Uses a `src/` layout, so install the package (editable) before running
or testing.

```bash
pip install -e ".[dev]"          # add ,data for pandas/nflreadpy: ".[dev,data]"
python -m rostermanager          # run the app (no console-script entry point is defined)
pytest                           # run tests (tests/ currently has no test modules)
pytest tests/test_x.py::test_name  # run a single test
ruff check .                     # lint
ruff format .                    # format (line length 100, set in pyproject.toml)
mypy src                         # type-check
```

`pre-commit` is a dev dependency but there is no `.pre-commit-config.yaml` yet.

## Conventions

- Keep the `data` extra optional: code that imports `pandas` or `nflreadpy` should not be on the
  app's core import path, so the GUI still runs with only the base dependencies installed.
- The app is developed on Windows; tests that create Qt widgets need a `QApplication` instance
  (and `QT_QPA_PLATFORM=offscreen` in headless CI).
