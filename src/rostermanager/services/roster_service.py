"""The one place the UI goes for rosters: list, load, and import teams.

The UI never touches SQLite or the importers directly. It calls RosterService,
which wraps the data layer and turns its failures into a few clear error types.
"""

import shutil
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rostermanager.data import RosterRepository
from rostermanager.data.custom_import import RosterImportError, import_roster
from rostermanager.data.custom_import import template_path as _data_template_path
from rostermanager.models import DepthChart, Roster, RosterSource, SavedTeam, Team, Unit
from rostermanager.services import depth_editing
from rostermanager.services.depth_editing import EditError, PlayerKey

if TYPE_CHECKING:
    from rostermanager.data.nflverse import NflverseSource

# nflverse abbreviations for the 32 teams, used to offer real teams to download.
NFL_TEAM_ABBREVIATIONS: tuple[str, ...] = (
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
)  # fmt: skip

__all__ = [
    "NFL_TEAM_ABBREVIATIONS",
    "EditError",
    "PlayerKey",
    "RosterImportError",
    "RosterNotFoundError",
    "RosterService",
    "TeamDownloadError",
    "copy_template",
    "template_path",
]


def template_path(kind: str) -> Path:
    """The blank roster template shipped with the app ("csv" or "json")."""
    if kind not in ("csv", "json"):
        raise ValueError(f"no {kind!r} template; use csv or json")
    return _data_template_path("csv" if kind == "csv" else "json")


def copy_template(kind: str, destination: Path) -> Path:
    """Copy a roster template where the user can fill it in. Returns the new file."""
    return Path(shutil.copyfile(template_path(kind), destination))


class RosterNotFoundError(LookupError):
    """No roster is saved for the requested team."""

    def __init__(self, abbreviation: str) -> None:
        self.abbreviation = abbreviation
        super().__init__(f"no saved roster for {abbreviation!r}")


class TeamDownloadError(RuntimeError):
    """A real NFL team could not be downloaded from nflverse."""


class RosterService:
    """Roster operations for the UI. Pass a repository to use a different database."""

    def __init__(self, repo: RosterRepository | None = None) -> None:
        self.repo = repo if repo is not None else RosterRepository()

    def list_teams(self) -> list[Team]:
        """Every saved team, sorted by name."""
        return self.repo.list_teams()

    def load_roster(self, abbreviation: str) -> Roster:
        """The saved roster for a team. Raises RosterNotFoundError if there isn't one."""
        roster = self.repo.load_roster(abbreviation)
        if roster is None:
            raise RosterNotFoundError(abbreviation.strip().upper())
        return roster

    def depth_chart(self, abbreviation: str, unit: Unit) -> DepthChart:
        """One unit's depth chart for a saved team."""
        return self.load_roster(abbreviation).depth_chart(unit)

    def delete_team(self, abbreviation: str) -> bool:
        """Remove a saved team. Returns False if it wasn't saved."""
        return self.repo.delete_roster(abbreviation)

    def list_saved_teams(self) -> list[SavedTeam]:
        """Every saved team with where it came from and when, sorted by name."""
        return self.repo.list_saved_teams()

    def saved_team(self, abbreviation: str) -> SavedTeam | None:
        """A saved team's summary, or None. Use it to warn before overwriting."""
        return self.repo.saved_team(abbreviation)

    def read_custom_file(self, path: Path, team: Team | None = None) -> Roster:
        """Read a .csv or .json roster without saving it.

        Raises RosterImportError listing every problem in the file.
        """
        return import_roster(path, team)

    def save_custom_roster(self, roster: Roster) -> None:
        """Save a roster read by read_custom_file, replacing any team with its abbreviation."""
        self.repo.save_roster(roster, source=RosterSource.CUSTOM, imported_at=datetime.now(UTC))

    def import_custom_file(self, path: Path, team: Team | None = None) -> Roster:
        """Read and save a custom roster in one step."""
        roster = self.read_custom_file(path, team)
        self.save_custom_roster(roster)
        return roster

    def download_nfl_team(
        self,
        abbreviation: str,
        season: int | None = None,
        source: "NflverseSource | None" = None,
    ) -> Roster:
        """Download a real team from nflverse and save it. Needs internet.

        Refreshing a team that was downloaded before keeps the user's ratings for
        players still on the roster. Raises TeamDownloadError on any failure.
        """
        try:
            # Imported here so the app still starts without the optional data extras.
            from rostermanager.data.nflverse import fetch_team
        except ImportError as error:
            raise TeamDownloadError(
                'NFL downloads need the data extras: python -m pip install -e ".[data]"'
            ) from error
        try:
            roster = fetch_team(abbreviation, season=season, source=source)
        except Exception as error:  # network, parsing, or validation: all shown to the user
            raise TeamDownloadError(
                f"could not download {abbreviation.strip().upper()}: {error}"
            ) from error
        existing = self.saved_team(roster.team.abbreviation)
        if existing is not None and existing.source is RosterSource.NFLVERSE:
            roster = carry_over_ratings(self.load_roster(roster.team.abbreviation), roster)
        self.repo.save_roster(roster, source=RosterSource.NFLVERSE, imported_at=datetime.now(UTC))
        return roster

    # Editing. Each loads the saved roster, applies one change, validates, saves,
    # and returns the updated roster. Failures raise EditError and save nothing.

    def _edit(self, abbreviation: str, change: Callable[[Roster], Roster]) -> Roster:
        roster = change(self.load_roster(abbreviation))
        self.repo.save_roster(roster)
        return roster

    def move_player(self, abbreviation: str, key: PlayerKey, to_depth: int) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.move_player(r, key, to_depth))

    def promote(self, abbreviation: str, key: PlayerKey) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.promote(r, key))

    def demote(self, abbreviation: str, key: PlayerKey) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.demote(r, key))

    def make_starter(self, abbreviation: str, key: PlayerKey) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.make_starter(r, key))

    def swap_players(self, abbreviation: str, a: PlayerKey, b: PlayerKey) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.swap_players(r, a, b))

    def update_player(
        self, abbreviation: str, key: PlayerKey, changes: Mapping[str, object]
    ) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.update_player(r, key, changes))

    def remove_player(self, abbreviation: str, key: PlayerKey) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.remove_player(r, key))

    def add_player(self, abbreviation: str, data: Mapping[str, object]) -> Roster:
        return self._edit(abbreviation, lambda r: depth_editing.add_player(r, data))


def carry_over_ratings(old: Roster, new: Roster) -> Roster:
    """new, with ratings copied from old for the same player.

    A player matches by name and unit first (the same person can have separate
    offense and special teams entries), then by name alone. Ratings already set in
    new are left alone.
    """
    by_name_unit = {(p.name, p.unit): p.rating for p in old.players if p.rating is not None}
    by_name = {p.name: p.rating for p in old.players if p.rating is not None}
    players = []
    for player in new.players:
        rating = by_name_unit.get((player.name, player.unit), by_name.get(player.name))
        if player.rating is None and rating is not None:
            player = player.model_copy(update={"rating": rating})
        players.append(player)
    return Roster(team=new.team, players=players)
