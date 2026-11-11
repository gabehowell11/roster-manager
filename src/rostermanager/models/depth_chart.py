"""DepthChart and Roster models, plus the depth_order rules they enforce.

A slot is one position label within one unit, such as offense "QB" or defense "LCB".
Each slot has exactly one starter (depth_order 1), and its backups count up from 2
with no gaps or repeats. Positions that field two starters use separate labels
(LT and RT, LCB and RCB) so each starter owns its own slot.
"""

from collections import defaultdict
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, model_validator

from rostermanager.models.player import Player, Unit
from rostermanager.models.team import Team


def _check_depth_orders(players: Iterable[Player]) -> None:
    """Raise ValueError unless every slot's depth orders are exactly 1..n."""
    orders: dict[tuple[Unit, str], list[int]] = defaultdict(list)
    for player in players:
        orders[(player.unit, player.position)].append(player.depth_order)

    problems = []
    for (unit, position), found in orders.items():
        found.sort()
        if found != list(range(1, len(found) + 1)):
            problems.append(f"{unit.value} {position} has depth orders {found}")
    if problems:
        raise ValueError(
            "each slot needs one starter (1) and backups numbered 2, 3, ... with no gaps "
            "or repeats: " + "; ".join(sorted(problems))
        )


class DepthChart(BaseModel):
    """The players of one unit, grouped into slots and ordered starter first."""

    model_config = ConfigDict(extra="forbid")

    unit: Unit
    players: list[Player]

    @model_validator(mode="after")
    def _check_players(self) -> "DepthChart":
        wrong_unit = [p.name for p in self.players if p.unit is not self.unit]
        if wrong_unit:
            raise ValueError(f"players not on {self.unit.value}: {', '.join(wrong_unit)}")
        _check_depth_orders(self.players)
        return self

    @property
    def slots(self) -> dict[str, list[Player]]:
        """Position label to players, starter first. Slots keep first-seen order."""
        grouped: dict[str, list[Player]] = {}
        for player in self.players:
            grouped.setdefault(player.position, []).append(player)
        return {
            position: sorted(group, key=lambda p: p.depth_order)
            for position, group in grouped.items()
        }

    @property
    def starters(self) -> list[Player]:
        return [group[0] for group in self.slots.values()]

    @property
    def backups(self) -> list[Player]:
        return [player for group in self.slots.values() for player in group[1:]]


class Roster(BaseModel):
    """A team and all of its players across offense, defense, and special teams."""

    model_config = ConfigDict(extra="forbid")

    team: Team
    players: list[Player]

    @model_validator(mode="after")
    def _check_players(self) -> "Roster":
        _check_depth_orders(self.players)
        return self

    def depth_chart(self, unit: Unit) -> DepthChart:
        """The depth chart for one unit of this roster."""
        return DepthChart(unit=unit, players=[p for p in self.players if p.unit is unit])
