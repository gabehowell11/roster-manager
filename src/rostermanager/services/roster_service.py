"""The one place the UI goes for rosters: list, load, and import teams.

The UI never touches SQLite or the importers directly. It calls RosterService,
which wraps the data layer and turns its failures into a few clear error types.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from rostermanager.data import RosterRepository
from rostermanager.data.custom_import import RosterImportError, import_roster
from rostermanager.models import DepthChart, Roster, Team, Unit

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
    "RosterImportError",
    "RosterNotFoundError",
    "RosterService",
    "TeamDownloadError",
]


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

    def import_custom_file(self, path: Path, team: Team | None = None) -> Roster:
        """Import a .csv or .json roster and save it.

        Raises RosterImportError listing every problem in the file.
        """
        roster = import_roster(path, team)
        self.repo.save_roster(roster)
        return roster

    def download_nfl_team(
        self,
        abbreviation: str,
        season: int | None = None,
        source: "NflverseSource | None" = None,
    ) -> Roster:
        """Download a real team from nflverse and save it. Needs internet.

        Raises TeamDownloadError with a readable message on any failure.
        """
        try:
            # Imported here so the app still starts without the optional data extras.
            from rostermanager.data.nflverse import import_team
        except ImportError as error:
            raise TeamDownloadError(
                'NFL downloads need the data extras: python -m pip install -e ".[data]"'
            ) from error
        try:
            return import_team(abbreviation, self.repo, season=season, source=source)
        except Exception as error:  # network, parsing, or validation: all shown to the user
            raise TeamDownloadError(
                f"could not download {abbreviation.strip().upper()}: {error}"
            ) from error
