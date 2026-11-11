"""Import a custom roster from a CSV or JSON file.

Both formats use the Player field names as columns or keys, so custom and real
rosters share one code path. Blank cells mean "not set" for optional fields.

CSV holds players only; the team comes from the caller. JSON may hold both:

    {"team": {"abbreviation": "EXC", "name": "Example City"}, "players": [{...}, ...]}

Every problem in the file is collected and reported together, with the row or
player number, so a user can fix them all in one pass.

Templates ship with the app; see template_path(). From the command line:

    python -m rostermanager.data.custom_import my_team.csv --team EXC --name "Example City"
"""

import argparse
import csv
import difflib
import json
import sys
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from rostermanager.data.repository import RosterRepository
from rostermanager.models import Player, Roster, Team

COLUMNS: tuple[str, ...] = tuple(Player.model_fields)
REQUIRED_COLUMNS: tuple[str, ...] = tuple(
    name for name, info in Player.model_fields.items() if info.is_required()
)


class RosterImportError(ValueError):
    """A custom roster file could not be imported. problems lists every issue found."""

    def __init__(self, path: Path, problems: list[str]) -> None:
        self.path = path
        self.problems = problems
        lines = "\n".join(f"  - {problem}" for problem in problems)
        super().__init__(f"Could not import {path.name}:\n{lines}")


def template_path(kind: Literal["csv", "json"]) -> Path:
    """The template file shipped with the app, for users to copy and fill in."""
    return Path(
        str(resources.files("rostermanager.data") / "templates" / f"roster_template.{kind}")
    )


def import_roster(path: Path, team: Team | None = None) -> Roster:
    """Read a .csv or .json roster. team overrides any team given inside a JSON file."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        if team is None:
            raise RosterImportError(path, ["a CSV file needs a team abbreviation and name"])
        return _roster(path, team, _read_csv(path))
    if suffix == ".json":
        file_team, labeled_rows = _read_json(path)
        chosen = team if team is not None else file_team
        if chosen is None:
            raise RosterImportError(path, ['add a "team" object to the file or give a team'])
        return _roster(path, chosen, labeled_rows)
    raise RosterImportError(path, [f"unsupported file type {path.suffix!r}; use .csv or .json"])


def _read_text(path: Path) -> str:
    try:
        # utf-8-sig also accepts the byte order mark Excel adds to "CSV UTF-8" files.
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise RosterImportError(path, ["file not found"]) from None
    except UnicodeDecodeError:
        raise RosterImportError(
            path, ["file is not UTF-8 text; in Excel use Save As > CSV UTF-8"]
        ) from None


def _read_csv(path: Path) -> list[tuple[str, dict[str, Any]]]:
    reader = csv.reader(_read_text(path).splitlines())
    header = next(reader, None)
    if header is None:
        raise RosterImportError(path, ["file is empty"])
    header = [column.strip().lower() for column in header]
    _check_columns(path, header)

    rows = []
    problems = []
    for line_number, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue  # skip blank lines, including trailing ones Excel writes
        if len(cells) > len(header):
            problems.append(
                f"row {line_number}: has {len(cells)} cells but the header has {len(header)}"
            )
            continue
        # Short rows are fine: missing trailing cells count as blank.
        rows.append((f"row {line_number}", dict(zip(header, cells, strict=False))))
    if problems:
        raise RosterImportError(path, problems)
    return rows


def _read_json(path: Path) -> tuple[Team | None, list[tuple[str, dict[str, Any]]]]:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as error:
        raise RosterImportError(
            path, [f"not valid JSON (line {error.lineno}, column {error.colno}): {error.msg}"]
        ) from None

    if isinstance(data, list):
        team_data, players = None, data
    elif isinstance(data, dict) and isinstance(data.get("players"), list):
        team_data, players = data.get("team"), data["players"]
    else:
        raise RosterImportError(
            path, ['expected a list of players or an object with a "players" list']
        )

    team = None
    if team_data is not None:
        try:
            team = Team.model_validate(team_data)
        except ValidationError as error:
            raise RosterImportError(path, _describe(error, "team")) from None

    rows = []
    for number, player in enumerate(players, start=1):
        if not isinstance(player, dict):
            raise RosterImportError(path, [f"player {number}: expected an object"])
        keys = [str(key).strip().lower() for key in player]
        _check_columns(path, keys, label=f"player {number}")
        rows.append((f"player {number}", dict(zip(keys, player.values(), strict=True))))
    return team, rows


def _check_columns(path: Path, columns: list[str], label: str = "header") -> None:
    problems = []
    seen: set[str] = set()
    for column in columns:
        if column in seen:
            problems.append(f"{label}: column {column!r} appears twice")
        seen.add(column)
        if column not in COLUMNS:
            guess = difflib.get_close_matches(column, COLUMNS, n=1)
            hint = f" (did you mean {guess[0]!r}?)" if guess else ""
            problems.append(f"{label}: unknown column {column!r}{hint}")
    missing = [column for column in REQUIRED_COLUMNS if column not in seen]
    if missing and label == "header":
        problems.append(f"header: missing required columns {', '.join(missing)}")
    if problems:
        raise RosterImportError(path, problems)


def _roster(path: Path, team: Team, labeled_rows: list[tuple[str, dict[str, Any]]]) -> Roster:
    players: list[Player] = []
    problems: list[str] = []
    for label, row in labeled_rows:
        # Drop blank cells and nulls so each field falls back to its default
        # (None, or 0 for years_experience) and blank required fields read as missing.
        cleaned = {key: value for key, value in row.items() if not _is_blank(value)}
        try:
            players.append(Player.model_validate(cleaned))
        except ValidationError as error:
            name = cleaned.get("name")
            problems.extend(_describe(error, f"{label} ({name})" if name else label))
    if problems:
        raise RosterImportError(path, problems)
    if not players:
        raise RosterImportError(path, ["no players found"])
    try:
        return Roster(team=team, players=players)
    except ValidationError as error:
        raise RosterImportError(path, _describe(error, "depth order")) from None


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _describe(error: ValidationError, label: str) -> list[str]:
    """Turn pydantic's errors into short, readable lines."""
    lines = []
    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"])
        message = item["msg"].removeprefix("Value error, ")
        if item["type"] == "missing":
            lines.append(f"{label}: {field} is required")
        elif field:
            lines.append(f"{label}: {field} {item['input']!r} - {message}")
        else:
            lines.append(f"{label}: {message}")
    return lines


def main(argv: Sequence[str] | None = None, repo: RosterRepository | None = None) -> int:
    """Command-line entry point. repo exists so tests never touch real user data."""
    parser = argparse.ArgumentParser(description="Import a custom roster from CSV or JSON.")
    parser.add_argument("file", type=Path, help="path to a .csv or .json roster")
    parser.add_argument("--team", help="team abbreviation (required for CSV)")
    parser.add_argument("--name", help="team name (required with --team)")
    args: Any = parser.parse_args(argv)

    team = None
    if args.team or args.name:
        if not (args.team and args.name):
            parser.error("--team and --name must be given together")
        try:
            team = Team(abbreviation=args.team, name=args.name)
        except ValidationError as error:
            print("\n".join(_describe(error, "team")), file=sys.stderr)
            return 1

    try:
        roster = import_roster(args.file, team)
    except RosterImportError as error:
        print(error, file=sys.stderr)
        return 1
    repo = repo if repo is not None else RosterRepository()
    repo.save_roster(roster)
    print(f"Saved {len(roster.players)} players for {roster.team.name} to {repo.db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
