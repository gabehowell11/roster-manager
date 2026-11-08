# Roster Manager

[![CI](https://github.com/gabehowell11/roster-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/gabehowell11/roster-manager/actions/workflows/ci.yml)

A Windows desktop app for managing football rosters. Pick a real NFL team or import your own
roster, then see the offense or defense laid out on a football field, with each player shown as
a card and starters in front of their backups.

> **Status:** early development. The project setup is done; the roster features below are planned
> and not built yet. See the [issues](https://github.com/gabehowell11/roster-manager/issues) for
> the roadmap.

## Planned features

- Browse any NFL team's current roster, downloaded once and stored locally so the app works offline
- Import a custom roster from CSV or JSON
- Field view for offense and defense, with starters and backups by position
- Reorder the depth chart (swap starters and backups)
- Give players your own 0-99 rating

## Screenshots

_Coming soon._

## Requirements

- Windows 10 or 11
- Python 3.12

## Setup

In PowerShell, from the folder where you want the project:

```powershell
git clone https://github.com/gabehowell11/roster-manager.git
cd roster-manager
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,data]"
python -m pre_commit install
```

If PowerShell refuses to run `Activate.ps1`, allow local scripts for your user once with
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again.

## Running the app

```powershell
python -m rostermanager
```

## Development

| Task       | Command                                |
| ---------- | -------------------------------------- |
| Tests      | `python -m pytest`                     |
| Lint       | `python -m ruff check .`               |
| Format     | `python -m ruff format .`              |
| Type check | `python -m mypy`                       |
| All hooks  | `python -m pre_commit run --all-files` |

Every pull request runs lint, type checks, and tests on Windows through GitHub Actions.

## Disclaimer

Roster Manager is an independent project. It is not affiliated with, endorsed by, or sponsored by
the National Football League (NFL) or any of its teams. Team names are used only to identify
rosters; the app does not use NFL or team logos or other official branding.

## License

[MIT](LICENSE)
