"""Regenerate the README screenshots in docs/screenshots/.

    python docs/make_screenshots.py

Renders offscreen (no windows appear) with a made-up team, so the images never
show real players or NFL branding. On Windows it reads fonts from C:/Windows/Fonts.
"""

import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PySide6.QtWidgets import QApplication

from rostermanager.data import RosterRepository
from rostermanager.models import Player, Roster, RosterSource, Team, Unit
from rostermanager.services import RosterService
from rostermanager.services.depth_editing import PlayerKey, find_player
from rostermanager.ui.main_window import MainWindow
from rostermanager.ui.player_dialog import PlayerDialog
from rostermanager.ui.theme import apply_theme

OUT = Path(__file__).resolve().parent / "screenshots"

FIRST = [
    "Avery", "Blake", "Cam", "Dante", "Eli", "Finn", "Gabe", "Hayes", "Isaiah", "Jalen",
    "Kai", "Logan", "Malik", "Nico", "Owen", "Parker", "Quinn", "Reed", "Silas", "Tate",
    "Uriah", "Vance", "Wes", "Xavier", "Yusuf", "Zane",
]  # fmt: skip
LAST = [
    "Adler", "Brooks", "Carver", "Dalton", "Ellis", "Foster", "Grady", "Holt", "Ingram",
    "Jensen", "Keller", "Lowe", "Mercer", "Nash", "Ortega", "Pryor", "Quill", "Ramsey",
    "Sutton", "Tillman", "Underwood", "Vale", "Whitaker", "Young",
]  # fmt: skip

OFFENSE = {
    "QB": 2,
    "RB": 2,
    "WR1": 2,
    "WR2": 2,
    "WR3": 2,
    "TE": 3,
    "LT": 2,
    "LG": 1,
    "C": 2,
    "RG": 1,
    "RT": 2,
}
DEFENSE = {
    "LDE": 2,
    "LDT": 2,
    "RDT": 1,
    "RDE": 2,
    "WLB": 1,
    "MLB": 2,
    "SLB": 1,
    "LCB": 2,
    "RCB": 2,
    "NB": 1,
    "FS": 1,
    "SS": 2,
}
SPECIAL = {"PK": 1, "P": 1, "LS": 1, "H": 1, "KR": 2, "PR": 1}


def build_roster() -> Roster:
    players: list[Player] = []
    n = 0
    for unit, slots in (("offense", OFFENSE), ("defense", DEFENSE), ("special_teams", SPECIAL)):
        for position, count in slots.items():
            for depth in range(1, count + 1):
                name = f"{FIRST[n % len(FIRST)]} {LAST[(n * 7) % len(LAST)]}"
                players.append(
                    Player(
                        name=name,
                        position=position,
                        unit=unit,
                        jersey_number=(n * 13) % 99 + 1,
                        height=70 + n % 8,
                        weight=190 + (n * 11) % 120,
                        college="Example State" if n % 3 else "Sample Tech",
                        years_experience=n % 9,
                        rating=95 - (depth - 1) * 12 - n % 7,
                        depth_order=depth,
                    )
                )
                n += 1
    team = Team(
        abbreviation="EXC", name="Example City", primary_color="#1F4E79", secondary_color="#F2C14E"
    )
    return Roster(team=team, players=players)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    app = QApplication([sys.argv[0]])
    apply_theme(app)
    with tempfile.TemporaryDirectory() as folder:
        service = RosterService(RosterRepository(Path(folder) / "shots.db"))
        roster = build_roster()
        now = datetime.now(UTC)
        service.repo.save_roster(roster, source=RosterSource.CUSTOM, imported_at=now)
        other = Roster(
            team=Team(abbreviation="SMP", name="Sampleton", primary_color="#2E7D32"),
            players=roster.players[:3],
        )
        service.repo.save_roster(other, source=RosterSource.CUSTOM, imported_at=now)

        window = MainWindow(service)
        window.resize(1200, 820)
        window.show()
        window.home.team_list.setCurrentRow(0)
        app.processEvents()
        window.grab().save(str(OUT / "home.png"))

        window.open_team("EXC")
        view = window.team_view
        shots = [
            (Unit.OFFENSE, "Depth chart", "offense.png"),
            (Unit.OFFENSE, "Shotgun (11)", "shotgun.png"),
            (Unit.DEFENSE, "Nickel (4-2-5)", "nickel.png"),
            (Unit.SPECIAL_TEAMS, "Depth chart", "special_teams.png"),
        ]
        for unit, formation, file in shots:
            view.show_unit(unit)
            view.formation_picker.setCurrentText(formation)
            app.processEvents()
            window.grab().save(str(OUT / file))

        player = find_player(service.load_roster("EXC"), PlayerKey(Unit.OFFENSE, "QB", 1))
        dialog = PlayerDialog(service, roster.team, player)
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(OUT / "player_editor.png"))
        dialog.close()
        window.close()
    print(f"saved screenshots to {OUT}")


if __name__ == "__main__":
    main()
