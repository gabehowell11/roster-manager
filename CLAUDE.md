# Roster Manager

Windows desktop app (Python + PySide6) that manages NFL/football rosters. Users pick a real NFL team or import a custom roster, then view offense or defense laid out like a football field. Each player is a card, with starters in front of backups.

## Commands (Windows PowerShell, venv active)

Always run tools as modules. Application Control blocks the .exe launchers in .venv.

- Run app: `python -m rostermanager`
- Tests: `python -m pytest`
- Lint: `python -m ruff check .`
- Format: `python -m ruff format .`
- Types: `python -m mypy` (checks `src` and `tests`, configured in pyproject.toml)
- Single test: `python -m pytest tests/test_architecture.py::test_entry_point_exposes_main`
- Install: `python -m pip install -e ".[dev,data]"`

## Architecture (src/rostermanager/)

Keep these layers separate. Dependencies point downward only.

1. `ui/` - PySide6 widgets only (home screen, team view, field view, PlayerCard).
2. `services/` - roster logic (depth ordering, swapping starters/backups, validation).
3. `data/` - SQLite repository, nflverse import, CSV/JSON importers.
4. `models/` - pydantic models: Player, Team, Roster, DepthChart.

Rules:
- No PySide6 imports outside `ui/`. Models, services, and data must run and be testable without a GUI.
- UI never touches SQLite directly. It calls services.
- Real NFL data is downloaded once into the local SQLite database so the app works offline.

## Player fields

name, position, jersey_number, unit (offense/defense/special_teams), height, weight, college, years_experience, rating (user-assigned 0-99, optional, editable), depth_order (1 = starter, 2 = first backup, ...).

Custom roster imports use the same columns, so real and custom rosters share one code path.

## Conventions

- Python 3.12, type hints on all functions, ruff-clean, mypy-clean.
- Every new service or data function gets pytest tests.
- Save user data under the platformdirs app data folder, never next to the app.
- Create files as UTF-8 without BOM. Never write files with PowerShell `Set-Content -Encoding utf8`.
- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- One branch per GitHub issue (`feature/<name>`), small PRs into `main`. Never commit directly to `main`.
- Do not add dependencies without saying why.

## Legal

Do not use NFL logos or official branding. Team names and colors only. README states the project is unaffiliated with the NFL.

## Current status

Phase 1 (setup and tooling) in progress. See GitHub issues and the Project board for the roadmap.