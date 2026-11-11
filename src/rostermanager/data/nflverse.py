"""Import a real NFL team's roster from nflverse and save it to SQLite.

Run once per team while online; afterwards the app reads the saved copy offline:

    python -m rostermanager.data.nflverse KC

The depth chart decides who is imported and in what order. Each depth chart entry
becomes one Player, so a receiver who also returns kicks appears on offense and on
special teams. Roster data fills in jersey number, size, college and experience.
Players who are not on the depth chart (deep reserves, practice squad) are skipped.

Only names and colors are taken from nflverse team data, never logos.
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import polars as pl

from rostermanager.data.repository import RosterRepository
from rostermanager.models import Player, Roster, Team, Unit


class NflverseSource(Protocol):
    """The nflreadpy functions this module uses. Tests pass a fake."""

    def load_rosters(self, seasons: int) -> pl.DataFrame: ...
    def load_depth_charts(self, seasons: int) -> pl.DataFrame: ...
    def load_teams(self) -> pl.DataFrame: ...


@dataclass(frozen=True)
class _Nflreadpy:
    """The real source, downloading through nflreadpy."""

    def load_rosters(self, seasons: int) -> pl.DataFrame:
        import nflreadpy

        result: pl.DataFrame = nflreadpy.load_rosters(seasons)
        return result

    def load_depth_charts(self, seasons: int) -> pl.DataFrame:
        import nflreadpy

        result: pl.DataFrame = nflreadpy.load_depth_charts(seasons)
        return result

    def load_teams(self) -> pl.DataFrame:
        import nflreadpy

        result: pl.DataFrame = nflreadpy.load_teams()
        return result


def current_season() -> int:
    """The most recent season nflverse has rosters for."""
    import nflreadpy

    season: int = nflreadpy.get_current_season(roster=True)
    return season


def _unit_for_group(group: str) -> Unit:
    """Map an nflverse depth chart group such as "Base 4-3 D" to a unit."""
    if group == "Special Teams":
        return Unit.SPECIAL_TEAMS
    if group.endswith(" D"):
        return Unit.DEFENSE
    return Unit.OFFENSE


def build_team(abbreviation: str, teams: pl.DataFrame) -> Team:
    """The Team for one abbreviation from nflverse team data (no logos)."""
    rows = teams.filter(pl.col("team_abbr") == abbreviation).to_dicts()
    if not rows:
        raise ValueError(f"unknown team {abbreviation!r}")
    row = rows[0]
    return Team(
        abbreviation=abbreviation,
        name=row["team_name"],
        primary_color=row["team_color"] or "#444444",
        secondary_color=row["team_color2"] or "#FFFFFF",
    )


def build_roster(
    abbreviation: str, rosters: pl.DataFrame, depth_charts: pl.DataFrame, teams: pl.DataFrame
) -> Roster:
    """Combine nflverse tables into one team's Roster. Pure, so it is easy to test."""
    team = build_team(abbreviation, teams)

    depth = depth_charts.filter(pl.col("team") == abbreviation)
    if depth.is_empty():
        raise ValueError(f"no depth chart for {abbreviation!r}")
    depth = depth.filter(pl.col("dt") == pl.col("dt").max())  # latest snapshot only
    depth = _keep_one_defense(depth)

    details = (
        rosters.filter(pl.col("team") == abbreviation)
        .sort("week")
        .unique(subset="gsis_id", keep="last")  # latest week's details per player
        .select("gsis_id", "full_name", "jersey_number", "height", "weight", "college", "years_exp")
    )
    joined = depth.join(details, on="gsis_id", how="left").sort("pos_grp", "pos_slot", "pos_rank")

    labels = _slot_labels(joined)
    players: list[Player] = []
    next_depth: dict[tuple[str, int], int] = {}
    seen: set[tuple[str, int, str]] = set()
    for row in joined.iter_rows(named=True):
        slot = (row["pos_grp"], row["pos_slot"])
        key = (*slot, row["gsis_id"] or row["player_name"])
        if key in seen:  # same player listed twice in one slot
            continue
        seen.add(key)
        # Renumber 1, 2, 3... so gaps in nflverse ranks never break validation.
        next_depth[slot] = next_depth.get(slot, 0) + 1
        players.append(
            Player(
                name=row["full_name"] or row["player_name"],
                position=labels[slot],
                jersey_number=row["jersey_number"],
                unit=_unit_for_group(row["pos_grp"]),
                height=row["height"],
                weight=row["weight"],
                college=row["college"],
                years_experience=row["years_exp"] or 0,
                depth_order=next_depth[slot],
            )
        )
    return Roster(team=team, players=players)


def _keep_one_defense(depth: pl.DataFrame) -> pl.DataFrame:
    """If a snapshot lists both a 4-3 and a 3-4 defense, keep the larger one."""
    defenses = (
        depth.filter(pl.col("pos_grp").str.ends_with(" D"))
        .group_by("pos_grp")
        .len()
        .sort(["len", "pos_grp"], descending=[True, False])
    )
    if defenses.height <= 1:
        return depth
    keep = defenses["pos_grp"][0]
    return depth.filter(~pl.col("pos_grp").str.ends_with(" D") | (pl.col("pos_grp") == keep))


def _slot_labels(depth: pl.DataFrame) -> dict[tuple[str, int], str]:
    """Position label per (group, slot). Repeated labels get numbers: WR1, WR2, WR3."""
    slots = depth.select("pos_grp", "pos_slot", "pos_abb").unique().sort("pos_grp", "pos_slot")
    counts: dict[tuple[str, str], int] = {}
    for row in slots.iter_rows(named=True):
        key = (row["pos_grp"], row["pos_abb"])
        counts[key] = counts.get(key, 0) + 1

    labels: dict[tuple[str, int], str] = {}
    numbered: dict[tuple[str, str], int] = {}
    for row in slots.iter_rows(named=True):
        key = (row["pos_grp"], row["pos_abb"])
        label: str = row["pos_abb"]
        if counts[key] > 1:
            numbered[key] = numbered.get(key, 0) + 1
            label = f"{label}{numbered[key]}"
        labels[(row["pos_grp"], row["pos_slot"])] = label
    return labels


def import_team(
    abbreviation: str,
    repo: RosterRepository,
    season: int | None = None,
    source: NflverseSource | None = None,
) -> Roster:
    """Download one team's roster from nflverse, save it, and return it."""
    abbreviation = abbreviation.strip().upper()
    source = source if source is not None else _Nflreadpy()
    season = season if season is not None else current_season()
    roster = build_roster(
        abbreviation,
        rosters=source.load_rosters(season),
        depth_charts=source.load_depth_charts(season),
        teams=source.load_teams(),
    )
    repo.save_roster(roster)
    return roster


def main(
    argv: Sequence[str] | None = None,
    repo: RosterRepository | None = None,
    source: NflverseSource | None = None,
) -> int:
    """Command-line entry point. repo and source exist so tests can stay offline."""
    parser = argparse.ArgumentParser(description="Import a real NFL roster from nflverse.")
    parser.add_argument("team", help="team abbreviation, e.g. KC")
    parser.add_argument("--season", type=int, help="season year (default: latest)")
    args: Any = parser.parse_args(argv)

    repo = repo if repo is not None else RosterRepository()
    try:
        roster = import_team(args.team, repo, season=args.season, source=source)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        f"Saved {len(roster.players)} depth chart entries for {roster.team.name} to {repo.db_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
