"""Where each depth chart slot sits on the field. Pure Python, no GUI.

Spots use fractions of the drawing area: x runs 0 (left sideline) to 1 (right
sideline) and y runs 0 (top) to 1 (bottom). The UI multiplies by its own size.

Offense is drawn with the line of scrimmage near the top and the backfield below
it. Defense is drawn with the line of scrimmage near the bottom and the safeties
deep at the top, so both read as "facing the ball".

Labels are matched in three steps:
1. Exact named spots such as QB, LT, LCB, or WLB.
2. Group labels with an optional number, such as WR2, CB1, DT, or OLB2. The
   number picks the spot within the group; with no number the next free one is used.
3. Anything else (custom labels like "JOKER") goes in an overflow row along the
   bottom, in the order given, so every slot is always shown somewhere.

Special teams is drawn like a field goal or punt: snapper on the line, holder
and kicker behind, punter to the side, and returners deep. Its overflow row runs
along the top, since the returners use the bottom.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from rostermanager.models import DepthChart, Unit


@dataclass(frozen=True)
class FieldSpot:
    """A point on the field as fractions of the drawing area (0-1 on each axis)."""

    x: float
    y: float


OFFENSE_LINE = 0.30
DEFENSE_LINE = 0.72
OVERFLOW_Y = 0.92
SPECIAL_TEAMS_LINE = OFFENSE_LINE
SPECIAL_TEAMS_OVERFLOW_Y = 0.10

_OFFENSE_NAMED: dict[str, FieldSpot] = {
    "LT": FieldSpot(0.28, OFFENSE_LINE),
    "LG": FieldSpot(0.39, OFFENSE_LINE),
    "C": FieldSpot(0.50, OFFENSE_LINE),
    "RG": FieldSpot(0.61, OFFENSE_LINE),
    "RT": FieldSpot(0.72, OFFENSE_LINE),
    "QB": FieldSpot(0.50, 0.50),
    "FB": FieldSpot(0.50, 0.62),
    "RB": FieldSpot(0.50, 0.75),
    "HB": FieldSpot(0.50, 0.75),
    "LWR": FieldSpot(0.05, OFFENSE_LINE),
    "RWR": FieldSpot(0.95, OFFENSE_LINE),
    "SWR": FieldSpot(0.86, 0.52),
    "SLOT": FieldSpot(0.86, 0.52),
}

_OFFENSE_GROUPS: dict[str, tuple[FieldSpot, ...]] = {
    "WR": (
        FieldSpot(0.05, OFFENSE_LINE),
        FieldSpot(0.95, OFFENSE_LINE),
        FieldSpot(0.86, 0.52),
        FieldSpot(0.14, 0.52),
    ),
    "TE": (FieldSpot(0.83, 0.33), FieldSpot(0.17, 0.33)),
    "RB": (FieldSpot(0.50, 0.75), FieldSpot(0.64, 0.75)),
    "HB": (FieldSpot(0.50, 0.75), FieldSpot(0.64, 0.75)),
    "QB": (FieldSpot(0.50, 0.50),),
    "FB": (FieldSpot(0.50, 0.62),),
    "C": (FieldSpot(0.50, OFFENSE_LINE),),
    "T": (FieldSpot(0.28, OFFENSE_LINE), FieldSpot(0.72, OFFENSE_LINE)),
    "OT": (FieldSpot(0.28, OFFENSE_LINE), FieldSpot(0.72, OFFENSE_LINE)),
    "G": (FieldSpot(0.39, OFFENSE_LINE), FieldSpot(0.61, OFFENSE_LINE)),
    "OG": (FieldSpot(0.39, OFFENSE_LINE), FieldSpot(0.61, OFFENSE_LINE)),
    "OL": tuple(FieldSpot(x, OFFENSE_LINE) for x in (0.28, 0.39, 0.50, 0.61, 0.72)),
}

_DEFENSE_NAMED: dict[str, FieldSpot] = {
    "LDE": FieldSpot(0.30, DEFENSE_LINE),
    "LDT": FieldSpot(0.43, DEFENSE_LINE),
    "NT": FieldSpot(0.50, DEFENSE_LINE),
    "RDT": FieldSpot(0.57, DEFENSE_LINE),
    "RDE": FieldSpot(0.70, DEFENSE_LINE),
    "LOLB": FieldSpot(0.18, 0.62),
    "ROLB": FieldSpot(0.82, 0.62),
    "WLB": FieldSpot(0.30, 0.48),
    "MLB": FieldSpot(0.50, 0.48),
    "SLB": FieldSpot(0.70, 0.48),
    "LILB": FieldSpot(0.40, 0.48),
    "RILB": FieldSpot(0.60, 0.48),
    "LCB": FieldSpot(0.06, 0.66),
    "RCB": FieldSpot(0.94, 0.66),
    "NB": FieldSpot(0.84, 0.40),
    "NCB": FieldSpot(0.84, 0.40),
    "SCB": FieldSpot(0.84, 0.40),
    "FS": FieldSpot(0.38, 0.18),
    "SS": FieldSpot(0.62, 0.26),
}

_DEFENSE_GROUPS: dict[str, tuple[FieldSpot, ...]] = {
    "DE": (_DEFENSE_NAMED["LDE"], _DEFENSE_NAMED["RDE"]),
    "EDGE": (_DEFENSE_NAMED["LDE"], _DEFENSE_NAMED["RDE"]),
    "DT": (_DEFENSE_NAMED["LDT"], _DEFENSE_NAMED["RDT"]),
    "NT": (_DEFENSE_NAMED["NT"],),
    "DL": tuple(_DEFENSE_NAMED[k] for k in ("LDE", "LDT", "RDT", "RDE")),
    "LB": tuple(_DEFENSE_NAMED[k] for k in ("MLB", "WLB", "SLB")),
    "OLB": (_DEFENSE_NAMED["LOLB"], _DEFENSE_NAMED["ROLB"]),
    "ILB": (_DEFENSE_NAMED["LILB"], _DEFENSE_NAMED["RILB"]),
    "CB": tuple(_DEFENSE_NAMED[k] for k in ("LCB", "RCB", "NB")),
    "S": (_DEFENSE_NAMED["FS"], _DEFENSE_NAMED["SS"]),
    "SAF": (_DEFENSE_NAMED["FS"], _DEFENSE_NAMED["SS"]),
    "DB": tuple(_DEFENSE_NAMED[k] for k in ("LCB", "RCB", "FS", "SS", "NB")),
}

_SPECIAL_NAMED: dict[str, FieldSpot] = {
    "LS": FieldSpot(0.50, SPECIAL_TEAMS_LINE),
    "H": FieldSpot(0.50, 0.48),
    "K": FieldSpot(0.50, 0.64),
    "PK": FieldSpot(0.50, 0.64),
    "KOS": FieldSpot(0.32, 0.64),  # kickoff specialist
    "P": FieldSpot(0.70, 0.56),
    "KR": FieldSpot(0.35, 0.82),
    "PR": FieldSpot(0.65, 0.82),
}

_SPECIAL_GROUPS: dict[str, tuple[FieldSpot, ...]] = {
    "KR": (FieldSpot(0.35, 0.82), FieldSpot(0.15, 0.82)),
    "PR": (FieldSpot(0.65, 0.82), FieldSpot(0.85, 0.82)),
    "K": (FieldSpot(0.50, 0.64), FieldSpot(0.32, 0.64)),
    "PK": (FieldSpot(0.50, 0.64), FieldSpot(0.32, 0.64)),
    "P": (FieldSpot(0.70, 0.56),),
    "LS": (FieldSpot(0.50, SPECIAL_TEAMS_LINE),),
    "H": (FieldSpot(0.50, 0.48),),
}

_LABEL = re.compile(r"^([A-Z]+?)(\d*)$")


def layout_slots(unit: Unit, labels: Sequence[str]) -> dict[str, FieldSpot]:
    """A spot for every label, in the order given. No two labels share a spot."""
    named, groups, overflow_y = {
        Unit.OFFENSE: (_OFFENSE_NAMED, _OFFENSE_GROUPS, OVERFLOW_Y),
        Unit.DEFENSE: (_DEFENSE_NAMED, _DEFENSE_GROUPS, OVERFLOW_Y),
        Unit.SPECIAL_TEAMS: (_SPECIAL_NAMED, _SPECIAL_GROUPS, SPECIAL_TEAMS_OVERFLOW_Y),
    }[unit]

    spots: dict[str, FieldSpot] = {}
    taken: set[FieldSpot] = set()
    leftovers: list[str] = []

    def claim(label: str, spot: FieldSpot) -> bool:
        if spot in taken:
            return False
        spots[label] = spot
        taken.add(spot)
        return True

    # Exact names first, so "LCB" keeps its spot even if "CB1" comes earlier.
    pending = []
    for label in labels:
        key = label.upper()
        if key in named and claim(label, named[key]):
            continue
        pending.append(label)

    # Numbered group labels next (WR2 wants the second WR spot), then unnumbered.
    def group_parts(label: str) -> tuple[str, int | None] | None:
        match = _LABEL.match(label.upper())
        if match is None or match.group(1) not in groups:
            return None
        return match.group(1), int(match.group(2)) if match.group(2) else None

    for label in pending:
        parts = group_parts(label)
        if parts is None or parts[1] is None:
            continue
        group = groups[parts[0]]
        index = parts[1] - 1
        if 0 <= index < len(group):
            claim(label, group[index])

    for label in pending:
        if label in spots:
            continue
        parts = group_parts(label)
        if parts is not None and any(claim(label, spot) for spot in groups[parts[0]]):
            continue
        leftovers.append(label)

    spots.update(_overflow_row(leftovers, overflow_y))
    return {label: spots[label] for label in labels}


def layout_depth_chart(chart: DepthChart) -> dict[str, FieldSpot]:
    """A spot for every slot in a depth chart."""
    return layout_slots(chart.unit, list(chart.slots))


def _overflow_row(labels: Sequence[str], y: float) -> dict[str, FieldSpot]:
    count = len(labels)
    return {label: FieldSpot((index + 1) / (count + 1), y) for index, label in enumerate(labels)}
