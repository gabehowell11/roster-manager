"""Roster logic between the UI and data layers. No GUI imports allowed here."""

from rostermanager.services.depth_editing import EDITABLE_FIELDS, EditError, PlayerKey
from rostermanager.services.field_layout import FieldSpot, layout_depth_chart, layout_slots
from rostermanager.services.roster_service import (
    NFL_TEAM_ABBREVIATIONS,
    RosterImportError,
    RosterNotFoundError,
    RosterService,
    TeamDownloadError,
    copy_template,
    template_path,
)

__all__ = [
    "EDITABLE_FIELDS",
    "NFL_TEAM_ABBREVIATIONS",
    "EditError",
    "FieldSpot",
    "PlayerKey",
    "RosterImportError",
    "RosterNotFoundError",
    "RosterService",
    "TeamDownloadError",
    "copy_template",
    "layout_depth_chart",
    "layout_slots",
    "template_path",
]
