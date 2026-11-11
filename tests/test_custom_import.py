"""Tests for the custom CSV/JSON roster importer."""

import json
from pathlib import Path
from typing import Any

import pytest

from rostermanager.data import RosterRepository
from rostermanager.data.custom_import import (
    COLUMNS,
    RosterImportError,
    import_roster,
    main,
    template_path,
)
from rostermanager.models import Team, Unit

TEAM = Team(abbreviation="EXC", name="Example City")
HEADER = ",".join(COLUMNS)


def write(tmp_path: Path, name: str, text: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


def csv_file(tmp_path: Path, *rows: str, header: str = HEADER) -> Path:
    return write(tmp_path, "roster.csv", "\n".join([header, *rows]) + "\n")


def problems(path: Path, team: Team | None = TEAM) -> list[str]:
    with pytest.raises(RosterImportError) as caught:
        import_roster(path, team)
    return caught.value.problems


# --- templates -------------------------------------------------------------


@pytest.mark.parametrize("kind", ["csv", "json"])
def test_templates_ship_and_import_cleanly(kind: Any) -> None:
    path = template_path(kind)

    roster = import_roster(path, TEAM if kind == "csv" else None)

    assert path.exists()
    assert len(roster.players) == 6
    assert roster.depth_chart(Unit.OFFENSE).slots["QB"][1].name == "Riley Backup"


def test_template_csv_header_matches_player_fields() -> None:
    header = template_path("csv").read_text(encoding="utf-8").splitlines()[0]

    assert tuple(header.split(",")) == COLUMNS


def test_template_json_has_its_own_team() -> None:
    assert import_roster(template_path("json")).team.abbreviation == "EXC"


# --- CSV -------------------------------------------------------------------


def test_csv_reads_every_field(tmp_path: Path) -> None:
    path = csv_file(tmp_path, "Sam Example,qb,7,Offense,6-3,220,Example State,4,85,1")

    player = import_roster(path, TEAM).players[0]

    assert player.model_dump() == {
        "name": "Sam Example",
        "position": "QB",
        "jersey_number": 7,
        "unit": Unit.OFFENSE,
        "height": 75,
        "weight": 220,
        "college": "Example State",
        "years_experience": 4,
        "rating": 85,
        "depth_order": 1,
    }


def test_csv_blank_cells_and_short_rows_mean_not_set(tmp_path: Path) -> None:
    path = csv_file(
        tmp_path,
        "Sam Example,QB,offense,1,,",
        "",  # blank line in the middle
        "Kick Er,K,special_teams,1",  # short row: trailing optional cells left off
        ",,,,,",  # Excel-style empty row at the end
        header="name,position,unit,depth_order,jersey_number,college",
    )

    roster = import_roster(path, TEAM)

    assert [p.name for p in roster.players] == ["Sam Example", "Kick Er"]
    assert roster.players[0].jersey_number is None
    assert roster.players[0].college is None
    assert roster.players[1].years_experience == 0


def test_csv_columns_can_be_in_any_order_and_case(tmp_path: Path) -> None:
    path = csv_file(tmp_path, "1,offense,QB,Sam Example", header=" Depth_Order ,UNIT,position,name")

    assert import_roster(path, TEAM).players[0].name == "Sam Example"


def test_csv_accepts_excel_byte_order_mark(tmp_path: Path) -> None:
    path = write(tmp_path, "r.csv", f"{HEADER}\nSam Example,QB,7,offense,,,,,,1\n", "utf-8-sig")

    assert import_roster(path, TEAM).players[0].name == "Sam Example"


def test_csv_needs_a_team(tmp_path: Path) -> None:
    path = csv_file(tmp_path, "Sam Example,QB,7,offense,,,,,,1")

    assert problems(path, team=None) == ["a CSV file needs a team abbreviation and name"]


def test_every_bad_row_is_reported_with_row_number_and_name(tmp_path: Path) -> None:
    path = csv_file(
        tmp_path,
        "Sam Example,QB,7,offense,,,,,,1",
        "Bad Jersey,WR1,123,offense,,,,,,1",
        "Bad Unit,LCB,24,goalie,,,,,,1",
        ",RB,22,offense,,,,,,1",
    )

    found = problems(path)

    assert len(found) == 3
    assert found[0].startswith("row 3 (Bad Jersey): jersey_number '123'")
    assert found[1].startswith("row 4 (Bad Unit): unit 'goalie'")
    assert found[2] == "row 5: name is required"


def test_misspelled_column_suggests_the_right_one(tmp_path: Path) -> None:
    path = csv_file(tmp_path, header=HEADER.replace("jersey_number", "jersy_number"))

    assert problems(path) == [
        "header: unknown column 'jersy_number' (did you mean 'jersey_number'?)"
    ]


def test_missing_required_and_duplicate_columns_are_reported(tmp_path: Path) -> None:
    path = csv_file(tmp_path, header="name,name,position")

    assert problems(path) == [
        "header: column 'name' appears twice",
        "header: missing required columns unit, depth_order",
    ]


def test_row_with_too_many_cells_is_reported(tmp_path: Path) -> None:
    path = csv_file(tmp_path, "Sam Example,QB,7,offense,,,,,,1,extra")

    assert problems(path) == ["row 2: has 11 cells but the header has 10"]


def test_depth_order_problems_are_reported(tmp_path: Path) -> None:
    path = csv_file(
        tmp_path, "Sam Example,QB,7,offense,,,,,,1", "Other Starter,QB,8,offense,,,,,,1"
    )

    [problem] = problems(path)

    assert problem.startswith("depth order:")
    assert "offense QB has depth orders [1, 1]" in problem


def test_empty_and_header_only_files_are_reported(tmp_path: Path) -> None:
    assert problems(write(tmp_path, "empty.csv", "")) == ["file is empty"]
    assert problems(csv_file(tmp_path)) == ["no players found"]


def test_non_utf8_file_explains_how_to_fix(tmp_path: Path) -> None:
    path = write(tmp_path, "r.csv", f"{HEADER}\nJosé Ñame,QB,7,offense,,,,,,1\n", "cp1252")

    assert "CSV UTF-8" in problems(path)[0]


def test_missing_file_and_wrong_type_are_reported(tmp_path: Path) -> None:
    assert problems(tmp_path / "nope.csv") == ["file not found"]
    assert "use .csv or .json" in problems(write(tmp_path, "r.txt", "x"))[0]


def test_error_message_lists_every_problem(tmp_path: Path) -> None:
    path = csv_file(tmp_path, "A,QB,7,offense,,,,,,0", "B,QB,8,offense,,,,,,-1")

    with pytest.raises(RosterImportError) as caught:
        import_roster(path, TEAM)

    message = str(caught.value)
    assert message.startswith("Could not import roster.csv:")
    assert "row 2 (A)" in message and "row 3 (B)" in message


# --- JSON ------------------------------------------------------------------


def json_file(tmp_path: Path, data: object) -> Path:
    return write(tmp_path, "roster.json", json.dumps(data))


PLAYER = {"name": "Sam Example", "position": "QB", "unit": "offense", "depth_order": 1}


def test_json_with_team_object(tmp_path: Path) -> None:
    path = json_file(tmp_path, {"team": {"abbreviation": "abc", "name": "A"}, "players": [PLAYER]})

    roster = import_roster(path)

    assert roster.team.abbreviation == "ABC"
    assert roster.players[0].name == "Sam Example"


def test_json_list_uses_given_team_and_team_argument_overrides_file(tmp_path: Path) -> None:
    assert import_roster(json_file(tmp_path, [PLAYER]), TEAM).team == TEAM

    with_team = json_file(
        tmp_path, {"team": {"abbreviation": "ABC", "name": "A"}, "players": [PLAYER]}
    )
    assert import_roster(with_team, TEAM).team == TEAM


def test_json_without_any_team_is_reported(tmp_path: Path) -> None:
    assert "team" in problems(json_file(tmp_path, [PLAYER]), team=None)[0]


def test_json_bad_team_is_reported(tmp_path: Path) -> None:
    path = json_file(tmp_path, {"team": {"abbreviation": "A", "name": "A"}, "players": [PLAYER]})

    assert problems(path, team=None)[0].startswith("team: abbreviation 'A'")


def test_json_bad_players_are_numbered(tmp_path: Path) -> None:
    path = json_file(tmp_path, [PLAYER, {**PLAYER, "name": "Too Old", "rating": 120}])

    [problem] = problems(path)

    assert problem.startswith("player 2 (Too Old): rating 120")


def test_json_unknown_key_is_reported(tmp_path: Path) -> None:
    path = json_file(tmp_path, [{**PLAYER, "speed": 4.4}])

    assert problems(path) == ["player 1: unknown column 'speed'"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("{not json", "not valid JSON (line 1, column 2)"),
        ('{"players": 3}', 'expected a list of players or an object with a "players" list'),
        ("[1]", "player 1: expected an object"),
    ],
)
def test_json_shape_problems_are_reported(tmp_path: Path, text: str, expected: str) -> None:
    assert problems(write(tmp_path, "r.json", text))[0].startswith(expected)


# --- command line ----------------------------------------------------------


def test_main_imports_and_saves(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = RosterRepository(tmp_path / "rosters.db")

    code = main([str(template_path("csv")), "--team", "exc", "--name", "Example City"], repo)

    assert code == 0
    assert "Saved 6 players for Example City" in capsys.readouterr().out
    assert repo.load_roster("EXC") is not None


def test_main_reports_problems_and_saves_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = RosterRepository(tmp_path / "rosters.db")
    path = csv_file(tmp_path, "Sam Example,QB,7,offense,,,,,,0")

    code = main([str(path), "--team", "EXC", "--name", "Example City"], repo)

    assert code == 1
    assert "row 2 (Sam Example): depth_order" in capsys.readouterr().err
    assert repo.list_teams() == []


def test_main_rejects_bad_team(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = RosterRepository(tmp_path / "rosters.db")

    code = main([str(template_path("csv")), "--team", "X", "--name", "Example City"], repo)

    assert code == 1
    assert "team: abbreviation 'X'" in capsys.readouterr().err
