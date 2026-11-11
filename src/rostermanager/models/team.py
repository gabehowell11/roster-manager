"""The Team model. Names and colors only, no logos or official branding."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


class Team(BaseModel):
    """A real NFL team or a user-made custom team."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    abbreviation: str = Field(min_length=2, max_length=4, pattern=r"^[A-Za-z]+$")
    name: str = Field(min_length=1)
    primary_color: str = Field(default="#444444", pattern=_HEX_COLOR)
    secondary_color: str = Field(default="#FFFFFF", pattern=_HEX_COLOR)

    @field_validator("abbreviation", "primary_color", "secondary_color")
    @classmethod
    def _uppercase(cls, value: str) -> str:
        return value.upper()
