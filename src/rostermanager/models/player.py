"""The Player model shared by real NFL rosters and custom imports."""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Accepts "6-2", "6'2", 6' 2", 6'2" and similar feet-inches spellings.
_FEET_INCHES = re.compile(r"""^\s*(\d)\s*['\-]\s*(\d{1,2})\s*"?\s*$""")


class Unit(StrEnum):
    """Which side of the ball a player lines up on."""

    OFFENSE = "offense"
    DEFENSE = "defense"
    SPECIAL_TEAMS = "special_teams"


class Player(BaseModel):
    """One player on a roster.

    height is stored in inches and weight in pounds. depth_order 1 is the starter,
    2 the first backup, and so on. rating is user-assigned and may be edited later;
    assignments are validated too.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(min_length=1)
    position: str = Field(min_length=1, max_length=5)
    jersey_number: int | None = Field(default=None, ge=0, le=99)
    unit: Unit
    height: int | None = Field(default=None, ge=48, le=96)
    weight: int | None = Field(default=None, ge=100, le=450)
    college: str | None = None
    years_experience: int = Field(default=0, ge=0, le=30)
    rating: int | None = Field(default=None, ge=0, le=99)
    depth_order: int = Field(ge=1)

    @field_validator("position")
    @classmethod
    def _uppercase_position(cls, value: str) -> str:
        return value.upper()

    @field_validator("unit", mode="before")
    @classmethod
    def _normalize_unit(cls, value: object) -> object:
        # Lets imports write "Offense" or "special teams".
        if isinstance(value, str):
            return value.strip().lower().replace(" ", "_")
        return value

    @field_validator("college", mode="before")
    @classmethod
    def _blank_college_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("height", mode="before")
    @classmethod
    def _parse_height(cls, value: object) -> object:
        """Convert feet-inches text like "6-2" to inches; leave numbers alone."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return None
        match = _FEET_INCHES.match(text)
        if match:
            feet, inches = int(match.group(1)), int(match.group(2))
            if inches > 11:
                raise ValueError(f"inches must be 0-11 in {value!r}")
            return feet * 12 + inches
        return text  # Let pydantic parse plain numbers like "74" or reject junk.
