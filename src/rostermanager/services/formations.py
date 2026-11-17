"""Offensive and defensive formations. Pure Python, no GUI.

A formation is a list of roles. Each role has a spot on the field and an ordered
list of depth chart slots it can draw a player from. Filling a formation walks the
roles and gives each one the best player not already on the field, in two passes:

* first every role takes its own first source (RB gets the starting RB before the
  fullback role, which falls back to RBs, gets a look);
* then roles still open try their remaining sources in order; "TE" matches slots TE, TE1, TE2, ... in chart order,
  while a direction-specific source such as "LDE" matches only LDE;
* within a slot the highest player on the depth chart goes first.

So Goal Line's TE2 is the TE2 starter on a roster that has a TE2 slot, or the TE
slot's first backup on one that doesn't. That lets formations work with nflverse
4-3 and 3-4 depth charts and with custom rosters using generic labels (DE, LB, CB).
A role nobody can fill is returned empty so the UI can show an open spot.

The "Depth chart" view (DEPTH_CHART) is not a formation: it shows every slot as
the roster lists it, using field_layout.
"""

import re
from dataclasses import dataclass, field

from rostermanager.models import DepthChart, Player, Unit
from rostermanager.services.field_layout import DEFENSE_LINE, OFFENSE_LINE, FieldSpot

DEPTH_CHART = "Depth chart"

_BASE = re.compile(r"^(.*?)(\d*)$")


@dataclass(frozen=True)
class Role:
    """One spot in a formation and the slots that can fill it, best first."""

    label: str
    spot: FieldSpot
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Formation:
    name: str
    unit: Unit
    roles: tuple[Role, ...]


@dataclass
class FilledRole:
    """A role and who plays it. players[0] is on the field; the rest are that
    player's slot-mates not used elsewhere in the formation (shown behind)."""

    role: Role
    players: list[Player] = field(default_factory=list)


def _role(label: str, x: float, y: float, *sources: str) -> Role:
    return Role(label, FieldSpot(x, y), sources or (label,))


# Shared source lists.
_LT = ("LT", "T", "OT", "OL")
_LG = ("LG", "G", "OG", "OL")
_C = ("C", "OL")
_RG = ("RG", "G", "OG", "OL")
_RT = ("RT", "T", "OT", "OL")
_QB = ("QB",)
_RB = ("RB", "HB")
_FB = ("FB", "RB", "HB")
_WR1 = ("WR1", "LWR", "WR")
_WR2 = ("WR2", "RWR", "WR")
_WR3 = ("WR3", "SWR", "SLOT", "WR")
_WR4 = ("WR4", "WR")
_TE1 = ("TE1", "TE")
_TE2 = ("TE2", "TE")
_TE3 = ("TE3", "TE")


def _line(y: float = OFFENSE_LINE) -> tuple[Role, ...]:
    return (
        _role("LT", 0.28, y, *_LT),
        _role("LG", 0.39, y, *_LG),
        _role("C", 0.50, y, *_C),
        _role("RG", 0.61, y, *_RG),
        _role("RT", 0.72, y, *_RT),
    )


_OFFENSE = (
    Formation(
        "Shotgun (11)",
        Unit.OFFENSE,
        (
            *_line(),
            _role("QB", 0.50, 0.54, *_QB),
            _role("RB", 0.62, 0.54, *_RB),
            _role("TE", 0.17, 0.33, *_TE1),
            _role("WR1", 0.05, OFFENSE_LINE, *_WR1),
            _role("WR2", 0.95, OFFENSE_LINE, *_WR2),
            _role("WR3", 0.84, 0.45, *_WR3),
        ),
    ),
    Formation(
        "Singleback (11)",
        Unit.OFFENSE,
        (
            *_line(),
            _role("QB", 0.50, 0.47, *_QB),
            _role("RB", 0.50, 0.72, *_RB),
            _role("TE", 0.83, 0.33, *_TE1),
            _role("WR1", 0.05, OFFENSE_LINE, *_WR1),
            _role("WR2", 0.95, OFFENSE_LINE, *_WR2),
            _role("WR3", 0.14, 0.45, *_WR3),
        ),
    ),
    Formation(
        "I-Form (21)",
        Unit.OFFENSE,
        (
            *_line(),
            _role("QB", 0.50, 0.47, *_QB),
            _role("FB", 0.50, 0.62, *_FB),
            _role("RB", 0.50, 0.78, *_RB),
            _role("TE", 0.83, 0.33, *_TE1),
            _role("WR1", 0.05, OFFENSE_LINE, *_WR1),
            _role("WR2", 0.95, OFFENSE_LINE, *_WR2),
        ),
    ),
    Formation(
        "Pistol (11)",
        Unit.OFFENSE,
        (
            *_line(),
            _role("QB", 0.50, 0.50, *_QB),
            _role("RB", 0.50, 0.70, *_RB),
            _role("TE", 0.83, 0.33, *_TE1),
            _role("WR1", 0.05, OFFENSE_LINE, *_WR1),
            _role("WR2", 0.95, OFFENSE_LINE, *_WR2),
            _role("WR3", 0.14, 0.45, *_WR3),
        ),
    ),
    Formation(
        "Empty (10)",
        Unit.OFFENSE,
        (
            *_line(),
            _role("QB", 0.50, 0.52, *_QB),
            _role("WR1", 0.05, OFFENSE_LINE, *_WR1),
            _role("WR2", 0.95, OFFENSE_LINE, *_WR2),
            _role("WR3", 0.16, 0.46, *_WR3),
            _role("WR4", 0.84, 0.46, *_WR4),
            _role("RB", 0.32, 0.52, *_RB),
        ),
    ),
    Formation(
        "Goal Line (23)",
        Unit.OFFENSE,
        (
            *_line(),
            _role("QB", 0.50, 0.47, *_QB),
            _role("FB", 0.50, 0.62, *_FB),
            _role("RB", 0.50, 0.78, *_RB),
            _role("TE1", 0.83, 0.33, *_TE1),
            _role("TE2", 0.17, 0.33, *_TE2),
            _role("TE3", 0.94, 0.42, *_TE3),
        ),
    ),
)

_D = DEFENSE_LINE
_LDE = ("LDE", "DE", "EDGE", "DL", "LOLB", "OLB")
_RDE = ("RDE", "DE", "EDGE", "DL", "ROLB", "OLB")
_LDT = ("LDT", "DT", "NT", "DL")
_RDT = ("RDT", "DT", "NT", "DL")
_NT = ("NT", "DT", "LDT", "RDT", "DL")
_WLB = ("WLB", "LB", "OLB", "LOLB", "LILB", "ILB")
_MLB = ("MLB", "LB", "ILB", "LILB", "RILB")
_SLB = ("SLB", "LB", "OLB", "ROLB", "RILB", "ILB")
_LOLB = ("LOLB", "OLB", "WLB", "LDE", "DE", "EDGE", "LB")
_ROLB = ("ROLB", "OLB", "SLB", "RDE", "DE", "EDGE", "LB")
_LILB = ("LILB", "ILB", "MLB", "WLB", "LB")
_RILB = ("RILB", "ILB", "MLB", "SLB", "LB")
_LCB = ("LCB", "CB", "DB")
_RCB = ("RCB", "CB", "DB")
_NB = ("NB", "NCB", "SCB", "CB", "DB", "LCB", "RCB")
_DIME = ("DB", "CB", "NB", "NCB", "LCB", "RCB", "S", "SAF", "FS", "SS")
_FS = ("FS", "S", "SAF", "DB")
_SS = ("SS", "S", "SAF", "DB")


def _corners_and_safeties() -> tuple[Role, ...]:
    return (
        _role("LCB", 0.06, 0.66, *_LCB),
        _role("RCB", 0.94, 0.66, *_RCB),
        _role("FS", 0.38, 0.18, *_FS),
        _role("SS", 0.62, 0.26, *_SS),
    )


def _four_man_line() -> tuple[Role, ...]:
    return (
        _role("LDE", 0.30, _D, *_LDE),
        _role("LDT", 0.43, _D, *_LDT),
        _role("RDT", 0.57, _D, *_RDT),
        _role("RDE", 0.70, _D, *_RDE),
    )


def _three_man_line() -> tuple[Role, ...]:
    return (
        _role("LDE", 0.35, _D, *_LDE),
        _role("NT", 0.50, _D, *_NT),
        _role("RDE", 0.65, _D, *_RDE),
    )


_DEFENSE = (
    Formation(
        "4-3",
        Unit.DEFENSE,
        (
            *_four_man_line(),
            _role("WLB", 0.30, 0.48, *_WLB),
            _role("MLB", 0.50, 0.48, *_MLB),
            _role("SLB", 0.70, 0.48, *_SLB),
            *_corners_and_safeties(),
        ),
    ),
    Formation(
        "3-4",
        Unit.DEFENSE,
        (
            *_three_man_line(),
            _role("LOLB", 0.18, 0.62, *_LOLB),
            _role("LILB", 0.40, 0.48, *_LILB),
            _role("RILB", 0.60, 0.48, *_RILB),
            _role("ROLB", 0.82, 0.62, *_ROLB),
            *_corners_and_safeties(),
        ),
    ),
    Formation(
        "Nickel (4-2-5)",
        Unit.DEFENSE,
        (
            *_four_man_line(),
            _role("LB1", 0.38, 0.48, *_WLB),
            _role("LB2", 0.62, 0.48, *_MLB),
            _role("NB", 0.84, 0.40, *_NB),
            *_corners_and_safeties(),
        ),
    ),
    Formation(
        "Dime (4-1-6)",
        Unit.DEFENSE,
        (
            *_four_man_line(),
            _role("MLB", 0.50, 0.48, *_MLB),
            _role("NB", 0.84, 0.40, *_NB),
            _role("DIME", 0.16, 0.40, *_DIME),
            *_corners_and_safeties(),
        ),
    ),
    Formation(
        "3-3-5",
        Unit.DEFENSE,
        (
            *_three_man_line(),
            _role("WLB", 0.30, 0.48, *_WLB),
            _role("MLB", 0.50, 0.48, *_MLB),
            _role("SLB", 0.70, 0.48, *_SLB),
            _role("NB", 0.84, 0.36, *_NB),
            *_corners_and_safeties(),
        ),
    ),
    Formation(
        "Goal Line (6-2)",
        Unit.DEFENSE,
        (
            _role("LEDGE", 0.20, _D, *_LOLB),
            _role("LDE", 0.32, _D, *_LDE),
            _role("LDT", 0.44, _D, *_LDT),
            _role("RDT", 0.56, _D, *_RDT),
            _role("RDE", 0.68, _D, *_RDE),
            _role("REDGE", 0.80, _D, *_ROLB),
            _role("LB1", 0.38, 0.50, *_WLB),
            _role("LB2", 0.62, 0.50, *_MLB),
            _role("LCB", 0.06, 0.66, *_LCB),
            _role("RCB", 0.94, 0.66, *_RCB),
            _role("S", 0.50, 0.26, "SS", "FS", "S", "SAF", "DB"),
        ),
    ),
)

FORMATIONS: dict[Unit, tuple[Formation, ...]] = {
    Unit.OFFENSE: _OFFENSE,
    Unit.DEFENSE: _DEFENSE,
    Unit.SPECIAL_TEAMS: (),
}


def formation_names(unit: Unit) -> list[str]:
    """Choices for a unit, with the plain depth chart view first."""
    return [DEPTH_CHART, *(f.name for f in FORMATIONS[unit])]


def get_formation(unit: Unit, name: str) -> Formation | None:
    """The named formation, or None for the depth chart view or an unknown name."""
    return next((f for f in FORMATIONS[unit] if f.name == name), None)


def _matches(source: str, label: str) -> bool:
    match = _BASE.match(label)
    base = match.group(1) if match else label
    return label == source or base == source


def fill_formation(chart: DepthChart, formation: Formation) -> list[FilledRole]:
    """Assign the chart's players to the formation's roles (see module docstring)."""
    if chart.unit is not formation.unit:
        raise ValueError(f"{formation.name} is a {formation.unit.value} formation")
    slots = chart.slots
    used: set[int] = set()
    filled = [FilledRole(role) for role in formation.roles]
    for first_pass in (True, False):
        for entry in filled:
            if entry.players:
                continue
            sources = entry.role.sources[:1] if first_pass else entry.role.sources[1:]
            choice = _pick(slots, sources, used)
            if choice is not None:
                used.add(id(choice))
                entry.players.append(choice)

    # Backups behind each card: the rest of that player's slot not used on the field.
    for entry in filled:
        if entry.players:
            front = entry.players[0]
            entry.players.extend(
                p for p in slots[front.position] if p is not front and id(p) not in used
            )
    return filled


def _pick(
    slots: dict[str, list[Player]], sources: tuple[str, ...], used: set[int]
) -> Player | None:
    for source in sources:
        for label, players in slots.items():
            if not _matches(source, label):
                continue
            for player in players:
                if id(player) not in used:
                    return player
    return None
