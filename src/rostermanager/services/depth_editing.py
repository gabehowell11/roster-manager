"""Depth chart and player edits. Pure functions: each takes a Roster and returns a new one.

A player is identified by a PlayerKey: unit, position label, and depth order. That
trio is unique within a valid roster. Every edit renumbers the affected slots to
1, 2, 3... and builds a new Roster, so the depth order rules are re-checked.
RosterService wraps these to load, edit, and save in one call.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import ValidationError

from rostermanager.models import Player, Roster, Unit


class EditError(ValueError):
    """An edit could not be applied. The message is meant for the user."""


@dataclass(frozen=True)
class PlayerKey:
    """Which player: their unit, position label, and depth order."""

    unit: Unit
    position: str
    depth_order: int

    @classmethod
    def of(cls, player: Player) -> "PlayerKey":
        return cls(player.unit, player.position, player.depth_order)

    def slot(self) -> tuple[Unit, str]:
        return (self.unit, self.position)


# Fields the player editor may change. depth_order changes go through move_player.
EDITABLE_FIELDS: tuple[str, ...] = tuple(
    name for name in Player.model_fields if name != "depth_order"
)


def find_player(roster: Roster, key: PlayerKey) -> Player:
    for player in roster.players:
        if PlayerKey.of(player) == key:
            return player
    raise EditError(f"no {key.unit.value} {key.position} at depth {key.depth_order}")


def slot_players(roster: Roster, unit: Unit, position: str) -> list[Player]:
    """The players in one slot, starter first."""
    found = [p for p in roster.players if p.unit is unit and p.position == position]
    return sorted(found, key=lambda p: p.depth_order)


def move_player(roster: Roster, key: PlayerKey, to_depth: int) -> Roster:
    """Move a player to a new depth within their slot; others shift to make room."""
    player = find_player(roster, key)
    slot = slot_players(roster, key.unit, key.position)
    if not 1 <= to_depth <= len(slot):
        raise EditError(f"{key.position} depth must be 1 to {len(slot)}, not {to_depth}")
    order = [p for p in slot if p is not player]
    order.insert(to_depth - 1, player)
    return _renumbered(roster, {id(p): depth for depth, p in enumerate(order, start=1)})


def promote(roster: Roster, key: PlayerKey) -> Roster:
    """Move a backup up one spot (2 becomes 1 and the old starter becomes 2)."""
    if key.depth_order == 1:
        raise EditError(f"{find_player(roster, key).name} is already the starter")
    return move_player(roster, key, key.depth_order - 1)


def demote(roster: Roster, key: PlayerKey) -> Roster:
    """Move a player down one spot."""
    if key.depth_order == len(slot_players(roster, key.unit, key.position)):
        raise EditError(f"{find_player(roster, key).name} is already last at {key.position}")
    return move_player(roster, key, key.depth_order + 1)


def make_starter(roster: Roster, key: PlayerKey) -> Roster:
    """Move a player to depth 1; everyone ahead of them shifts down one."""
    return move_player(roster, key, 1)


def swap_players(roster: Roster, a: PlayerKey, b: PlayerKey) -> Roster:
    """Exchange two players' places. They may be in different slots of the same unit."""
    if a.unit is not b.unit:
        raise EditError("players can only swap within the same unit")
    first, second = find_player(roster, a), find_player(roster, b)
    swapped = {
        id(first): first.model_copy(update={"position": b.position, "depth_order": b.depth_order}),
        id(second): second.model_copy(
            update={"position": a.position, "depth_order": a.depth_order}
        ),
    }
    return _rebuild(roster, [swapped.get(id(p), p) for p in roster.players])


def update_player(roster: Roster, key: PlayerKey, changes: Mapping[str, object]) -> Roster:
    """Change a player's details. A new unit or position moves them to the end of that slot."""
    unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
    if unknown:
        raise EditError(f"cannot edit {', '.join(unknown)}")
    old = find_player(roster, key)
    data = {**old.model_dump(), **changes}
    try:
        new = Player.model_validate(data)
    except ValidationError as error:
        raise EditError(describe(error)) from None

    if (new.unit, new.position) == key.slot():
        return _rebuild(roster, [new if p is old else p for p in roster.players])
    # Leaving the slot: append to the new slot, then close the gap in the old one.
    new = new.model_copy(
        update={"depth_order": len(slot_players(roster, new.unit, new.position)) + 1}
    )
    moved = [new if p is old else p for p in roster.players]
    return _close_gaps(_rebuild(roster, moved, check=False), key.unit, key.position)


def remove_player(roster: Roster, key: PlayerKey) -> Roster:
    """Take a player off the roster; backups behind them move up."""
    old = find_player(roster, key)
    remaining = [p for p in roster.players if p is not old]
    return _close_gaps(_rebuild(roster, remaining, check=False), key.unit, key.position)


def add_player(roster: Roster, data: Mapping[str, object]) -> Roster:
    """Add a player at the end of their slot (depth_order is assigned)."""
    fields = {k: v for k, v in data.items() if k != "depth_order"}
    try:
        probe = Player.model_validate({**fields, "depth_order": 1})
    except ValidationError as error:
        raise EditError(describe(error)) from None
    depth = len(slot_players(roster, probe.unit, probe.position)) + 1
    return _rebuild(roster, [*roster.players, probe.model_copy(update={"depth_order": depth})])


def describe(error: ValidationError) -> str:
    """Pydantic errors as short lines like 'rating: must be 99 or less'."""
    lines = []
    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"]) or "player"
        message = item["msg"].removeprefix("Value error, ")
        lines.append(f"{field}: {message}")
    return "\n".join(lines)


def _renumbered(roster: Roster, depths: dict[int, int]) -> Roster:
    players = [
        p.model_copy(update={"depth_order": depths[id(p)]}) if id(p) in depths else p
        for p in roster.players
    ]
    return _rebuild(roster, players)


def _close_gaps(roster: Roster, unit: Unit, position: str) -> Roster:
    slot = slot_players(roster, unit, position)
    return _renumbered(roster, {id(p): depth for depth, p in enumerate(slot, start=1)})


def _rebuild(roster: Roster, players: list[Player], check: bool = True) -> Roster:
    """A new Roster. check=False skips validation for an intermediate step only."""
    if not check:
        return Roster.model_construct(team=roster.team, players=players)
    try:
        return Roster(team=roster.team, players=players)
    except ValidationError as error:
        raise EditError(describe(error)) from None
