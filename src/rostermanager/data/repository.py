"""SQLite storage for rosters.

One file holds every team and its players. Saving a roster replaces that team's
players in a single transaction, so a crash mid-save never leaves half a roster.

Schema history (PRAGMA user_version):
1. teams and players.
2. teams.source ("nflverse" or "custom") and teams.imported_at (ISO time, UTC).
   Older files are upgraded in place; their teams are marked custom with no date.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

from rostermanager.data.paths import default_db_path
from rostermanager.models import Player, Roster, RosterSource, SavedTeam, Team

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    abbreviation TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    primary_color TEXT NOT NULL,
    secondary_color TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'custom',
    imported_at TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    sort_index INTEGER NOT NULL,
    name TEXT NOT NULL,
    position TEXT NOT NULL,
    jersey_number INTEGER,
    unit TEXT NOT NULL,
    height INTEGER,
    weight INTEGER,
    college TEXT,
    years_experience INTEGER NOT NULL,
    rating INTEGER,
    depth_order INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS players_team ON players(team_id, sort_index);
"""

_PLAYER_COLUMNS = (
    "name",
    "position",
    "jersey_number",
    "unit",
    "height",
    "weight",
    "college",
    "years_experience",
    "rating",
    "depth_order",
)


class RosterRepository:
    """Saves and loads rosters in one SQLite file."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path if db_path is not None else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"{self.db_path} was made by a newer Roster Manager "
                    f"(schema {version}, this version supports {SCHEMA_VERSION})"
                )
            if version == 1:
                conn.execute("ALTER TABLE teams ADD COLUMN source TEXT NOT NULL DEFAULT 'custom'")
                conn.execute("ALTER TABLE teams ADD COLUMN imported_at TEXT")
            conn.executescript(_SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection that commits on success, rolls back on error, and always closes."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                yield conn

    def save_roster(
        self,
        roster: Roster,
        source: RosterSource | None = None,
        imported_at: datetime | None = None,
    ) -> None:
        """Insert or replace the roster for roster.team.abbreviation.

        Pass source and imported_at when the roster was just downloaded or imported.
        Leave them out for edits, which keep the team's existing values.
        """
        team = roster.team
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO teams
                    (abbreviation, name, primary_color, secondary_color, source, imported_at)
                VALUES (:abbreviation, :name, :primary, :secondary,
                        COALESCE(:source, 'custom'), :imported_at)
                ON CONFLICT(abbreviation) DO UPDATE SET
                    name = excluded.name,
                    primary_color = excluded.primary_color,
                    secondary_color = excluded.secondary_color,
                    source = COALESCE(:source, teams.source),
                    imported_at = COALESCE(:imported_at, teams.imported_at)
                """,
                {
                    "abbreviation": team.abbreviation,
                    "name": team.name,
                    "primary": team.primary_color,
                    "secondary": team.secondary_color,
                    "source": source.value if source is not None else None,
                    "imported_at": imported_at.isoformat() if imported_at is not None else None,
                },
            )
            team_id = conn.execute(
                "SELECT id FROM teams WHERE abbreviation = ?", (team.abbreviation,)
            ).fetchone()["id"]
            conn.execute("DELETE FROM players WHERE team_id = ?", (team_id,))
            conn.executemany(
                f"""
                INSERT INTO players (team_id, sort_index, {", ".join(_PLAYER_COLUMNS)})
                VALUES (?, ?, {", ".join("?" for _ in _PLAYER_COLUMNS)})
                """,
                [
                    (team_id, index, *(_player_value(p, col) for col in _PLAYER_COLUMNS))
                    for index, p in enumerate(roster.players)
                ],
            )

    def load_roster(self, abbreviation: str) -> Roster | None:
        """The saved roster for a team, or None if there isn't one."""
        with self._connect() as conn:
            team_row = conn.execute(
                "SELECT * FROM teams WHERE abbreviation = ?", (abbreviation.strip().upper(),)
            ).fetchone()
            if team_row is None:
                return None
            player_rows = conn.execute(
                "SELECT * FROM players WHERE team_id = ? ORDER BY sort_index",
                (team_row["id"],),
            ).fetchall()
        return Roster(
            team=_team_from_row(team_row),
            players=[Player(**{col: row[col] for col in _PLAYER_COLUMNS}) for row in player_rows],
        )

    def list_teams(self) -> list[Team]:
        """Every saved team, sorted by name."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM teams ORDER BY name, abbreviation").fetchall()
        return [_team_from_row(row) for row in rows]

    def list_saved_teams(self) -> list[SavedTeam]:
        """Every saved team with its source, import time, and player count, by name."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT teams.*, COUNT(players.id) AS player_count
                FROM teams LEFT JOIN players ON players.team_id = teams.id
                GROUP BY teams.id
                ORDER BY teams.name, teams.abbreviation
                """
            ).fetchall()
        return [_saved_team_from_row(row) for row in rows]

    def saved_team(self, abbreviation: str) -> SavedTeam | None:
        """One saved team's summary, or None if it isn't saved."""
        wanted = abbreviation.strip().upper()
        return next((t for t in self.list_saved_teams() if t.team.abbreviation == wanted), None)

    def delete_roster(self, abbreviation: str) -> bool:
        """Remove a team and its players. Returns False if it wasn't saved."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM teams WHERE abbreviation = ?", (abbreviation.strip().upper(),)
            )
        return cursor.rowcount > 0


def _player_value(player: Player, column: str) -> object:
    value = getattr(player, column)
    return value.value if column == "unit" else value


def _team_from_row(row: sqlite3.Row) -> Team:
    return Team(
        abbreviation=row["abbreviation"],
        name=row["name"],
        primary_color=row["primary_color"],
        secondary_color=row["secondary_color"],
    )


def _saved_team_from_row(row: sqlite3.Row) -> SavedTeam:
    imported = row["imported_at"]
    return SavedTeam(
        team=_team_from_row(row),
        source=RosterSource(row["source"]),
        imported_at=datetime.fromisoformat(imported) if imported else None,
        player_count=row["player_count"],
    )
