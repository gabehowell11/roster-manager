"""A saved team's summary: where its roster came from and when."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from rostermanager.models.team import Team


class RosterSource(StrEnum):
    """How a saved roster got into the app."""

    NFLVERSE = "nflverse"
    CUSTOM = "custom"


class SavedTeam(BaseModel):
    """One saved team for listing: no players, just facts about the roster."""

    model_config = ConfigDict(extra="forbid")

    team: Team
    source: RosterSource
    imported_at: datetime | None  # when it was downloaded or imported (UTC)
    player_count: int
