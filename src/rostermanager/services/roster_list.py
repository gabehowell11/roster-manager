"""The roster as one ordered list, grouped by position. Pure Python, no GUI.

Offense runs QB, RB, TE, WR, OL. Defense runs front to back: defensive line,
linebackers, cornerbacks, safeties. Special teams comes last. Inside each group
every starter is listed first, then every first backup, and so on, with
positions in field order (LT, LG, C, RG, RT). Labels the app does not know go
in an "Other" group at the end of their unit, so nobody is left out.
"""

import re
from dataclasses import dataclass

from rostermanager.models import Player, Roster, Unit

UNIT_ORDER = (Unit.OFFENSE, Unit.DEFENSE, Unit.SPECIAL_TEAMS)

# (group name, position labels in the order they are listed). Trailing numbers
# are ignored when matching, so WR1, WR2, and WR all land in Wide receivers.
_GROUPS: dict[Unit, tuple[tuple[str, tuple[str, ...]], ...]] = {
    Unit.OFFENSE: (
        ("Quarterbacks", ("QB",)),
        ("Running backs", ("RB", "HB", "FB")),
        ("Tight ends", ("TE",)),
        ("Wide receivers", ("WR", "LWR", "RWR", "SWR", "SLOT")),
        ("Offensive line", ("LT", "LG", "C", "RG", "RT", "T", "OT", "G", "OG", "OL")),
    ),
    Unit.DEFENSE: (
        (
            "Defensive line",
            ("LDE", "DE", "EDGE", "LDT", "DT", "NT", "RDT", "RDE", "DL"),
        ),
        (
            "Linebackers",
            ("LOLB", "WLB", "LILB", "MLB", "ILB", "RILB", "SLB", "ROLB", "OLB", "LB"),
        ),
        ("Cornerbacks", ("LCB", "RCB", "CB", "NB", "NCB", "SCB", "DB")),
        ("Safeties", ("FS", "SS", "S", "SAF")),
    ),
    Unit.SPECIAL_TEAMS: (
        ("Kickers", ("K", "PK", "KOS")),
        ("Punters", ("P",)),
        ("Long snappers", ("LS",)),
        ("Holders", ("H",)),
        ("Returners", ("KR", "PR")),
    ),
}

OTHER = "Other"
_NUMBER = re.compile(r"\d+$")


@dataclass(frozen=True)
class RosterGroup:
    """One position group in the list, e.g. Wide receivers on offense."""

    unit: Unit
    name: str
    players: tuple[Player, ...]


def _place(unit: Unit, position: str) -> tuple[int, int]:
    """(group index, label index) for a position label; unknown labels go last."""
    label = position.upper()
    groups = _GROUPS[unit]
    for exact in (label, _NUMBER.sub("", label)):
        for group_index, (_, labels) in enumerate(groups):
            if exact in labels:
                return group_index, labels.index(exact)
    return len(groups), 0


def roster_groups(roster: Roster) -> list[RosterGroup]:
    """Every player, grouped and ordered for the roster list. Empty groups are skipped."""
    groups: list[RosterGroup] = []
    for unit in UNIT_ORDER:
        names = [name for name, _ in _GROUPS[unit]] + [OTHER]
        buckets: list[list[Player]] = [[] for _ in names]
        for player in roster.players:
            if player.unit is unit:
                buckets[_place(unit, player.position)[0]].append(player)
        for name, players in zip(names, buckets, strict=True):
            if not players:
                continue
            ordered = sorted(
                players,
                key=lambda p: (
                    p.depth_order,  # all starters first, then first backups, ...
                    _place(unit, p.position)[1],
                    _number(p.position),  # WR1 before WR2
                    p.position,
                    p.name,
                ),
            )
            groups.append(RosterGroup(unit, name, tuple(ordered)))
    return groups


def _number(position: str) -> int:
    match = _NUMBER.search(position)
    return int(match.group()) if match else 0
