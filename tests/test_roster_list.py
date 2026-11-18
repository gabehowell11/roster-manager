"""Tests for ordering the roster into the grouped list."""

from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services.roster_list import OTHER, roster_groups

TEAM = Team(abbreviation="XYZ", name="Example City", primary_color="#112266")


def p(position: str, unit: str, depth: int, name: str | None = None) -> Player:
    return Player(
        name=name or f"{position}-{depth}", position=position, unit=unit, depth_order=depth
    )


def names(roster: Roster) -> list[tuple[str, str]]:
    return [(g.unit.value, g.name) for g in roster_groups(roster)]


def test_offense_groups_run_qb_rb_te_wr_ol_then_defense_then_special_teams() -> None:
    roster = Roster(
        team=TEAM,
        players=[
            p("K", "special_teams", 1),
            p("FS", "defense", 1),
            p("LT", "offense", 1),
            p("WR1", "offense", 1),
            p("TE", "offense", 1),
            p("RB", "offense", 1),
            p("QB", "offense", 1),
            p("MLB", "defense", 1),
            p("LCB", "defense", 1),
            p("DT", "defense", 1),
        ],
    )
    assert names(roster) == [
        ("offense", "Quarterbacks"),
        ("offense", "Running backs"),
        ("offense", "Tight ends"),
        ("offense", "Wide receivers"),
        ("offense", "Offensive line"),
        ("defense", "Defensive line"),
        ("defense", "Linebackers"),
        ("defense", "Cornerbacks"),
        ("defense", "Safeties"),
        ("special_teams", "Kickers"),
    ]


def test_starters_come_first_in_each_group() -> None:
    roster = Roster(
        team=TEAM,
        players=[
            p("WR1", "offense", 2),
            p("WR2", "offense", 1),
            p("WR1", "offense", 1),
            p("WR3", "offense", 1),
            p("WR2", "offense", 2),
            p("WR1", "offense", 3),
        ],
    )
    (group,) = roster_groups(roster)
    assert [x.name for x in group.players] == [
        "WR1-1",
        "WR2-1",
        "WR3-1",
        "WR1-2",
        "WR2-2",
        "WR1-3",
    ]


def test_offensive_line_is_in_field_order() -> None:
    labels = ["RT", "C", "LG", "RG", "LT"]
    roster = Roster(team=TEAM, players=[p(label, "offense", 1) for label in labels])
    (group,) = roster_groups(roster)
    assert [x.position for x in group.players] == ["LT", "LG", "C", "RG", "RT"]


def test_unknown_labels_go_in_other_at_the_end_of_their_unit() -> None:
    roster = Roster(
        team=TEAM,
        players=[
            p("JOKER", "offense", 1),
            p("QB", "offense", 1),
            p("ROVER", "defense", 1),
            p("SS", "defense", 1),
        ],
    )
    assert names(roster) == [
        ("offense", "Quarterbacks"),
        ("offense", OTHER),
        ("defense", "Safeties"),
        ("defense", OTHER),
    ]


def test_every_player_is_listed_once() -> None:
    players = [
        p("QB", "offense", 1),
        p("QB", "offense", 2),
        p("HB", "offense", 1),
        p("FB", "offense", 1),
        p("OLB2", "defense", 1),
        p("NB", "defense", 1),
        p("PR", "special_teams", 1),
        p("ZZZ", "special_teams", 1),
    ]
    roster = Roster(team=TEAM, players=players)
    listed = [x for g in roster_groups(roster) for x in g.players]
    assert sorted(x.name for x in listed) == sorted(x.name for x in players)


def test_empty_roster_has_no_groups() -> None:
    assert roster_groups(Roster(team=TEAM, players=[])) == []


def test_groups_know_their_unit() -> None:
    roster = Roster(team=TEAM, players=[p("QB", "offense", 1), p("FS", "defense", 1)])
    assert [g.unit for g in roster_groups(roster)] == [Unit.OFFENSE, Unit.DEFENSE]
