"""The player editor: every field of one player, editable, saved through the service."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rostermanager.models import Player, Roster, Team, Unit
from rostermanager.services import EditError, PlayerKey, RosterService
from rostermanager.services.depth_editing import find_player
from rostermanager.ui.theme import team_title_color

NONE = -1  # spin box value meaning "not set"; shown as a dash
UNIT_NAMES = {Unit.OFFENSE: "Offense", Unit.DEFENSE: "Defense", Unit.SPECIAL_TEAMS: "Special teams"}


def depth_text(player: Player) -> str:
    if player.depth_order == 1:
        return f"Starter at {player.position}"
    return f"Backup #{player.depth_order - 1} at {player.position} (depth {player.depth_order})"


def _optional_spin(minimum: int, maximum: int, none_text: str) -> QSpinBox:
    """A spin box whose lowest value (one below minimum) means "not set"."""
    spin = QSpinBox()
    spin.setRange(minimum - 1, maximum)
    spin.setSpecialValueText(none_text)
    return spin


class PlayerDialog(QDialog):
    """Shows and edits one player. After an accepted exec(), roster holds the saved roster."""

    def __init__(
        self,
        service: RosterService,
        team: Team,
        player: Player,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.team = team
        self.player = player
        self.key = PlayerKey.of(player)
        self.roster: Roster | None = None
        self.setWindowTitle(player.name)
        self.setMinimumWidth(380)

        self.heading = QLabel(player.name)
        self.heading.setObjectName("TeamTitle")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heading.setStyleSheet(f"color: {team_title_color(team)};")
        self.depth_label = QLabel(depth_text(player))
        self.depth_label.setObjectName("Muted")
        self.depth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name = QLineEdit(player.name)
        self.position = QLineEdit(player.position)
        self.position.setMaxLength(5)
        self.unit = QComboBox()
        for unit, label in UNIT_NAMES.items():
            self.unit.addItem(label, unit.value)
        self.unit.setCurrentIndex(list(UNIT_NAMES).index(player.unit))
        self.jersey = _optional_spin(0, 99, "-")
        self.height_input = QLineEdit(_height_text(player.height))
        self.height_input.setPlaceholderText("e.g. 6-2, or blank")
        self.weight = _optional_spin(100, 450, "-")
        self.weight.setSuffix(" lb")
        self.college = QLineEdit(player.college or "")
        self.experience = QSpinBox()
        self.experience.setRange(0, 30)
        self.experience.setSuffix(" yr")
        self.rating = _optional_spin(0, 99, "No rating")

        self.jersey.setValue(_or_none(player.jersey_number))
        self.weight.setValue(player.weight if player.weight is not None else 99)
        self.experience.setValue(player.years_experience)
        self.rating.setValue(_or_none(player.rating))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Name", self.name)
        form.addRow("Position", self.position)
        form.addRow("Unit", self.unit)
        form.addRow("Jersey", self.jersey)
        form.addRow("Height", self.height_input)
        form.addRow("Weight", self.weight)
        form.addRow("College", self.college)
        form.addRow("Experience", self.experience)
        form.addRow("Rating (0-99)", self.rating)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #FF8A80;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.delete_button = QPushButton("Delete player")
        self.delete_button.clicked.connect(self.delete_player)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save)
        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)

        # Depth buttons save right away, so the field updates even if the dialog is cancelled.
        self.starter_button = QPushButton("Make starter")
        self.up_button = QPushButton("Move up")
        self.down_button = QPushButton("Move down")
        self.starter_button.clicked.connect(lambda: self.change_depth("starter"))
        self.up_button.clicked.connect(lambda: self.change_depth("up"))
        self.down_button.clicked.connect(lambda: self.change_depth("down"))
        depth_row = QHBoxLayout()
        depth_row.addStretch()
        for button in (self.starter_button, self.up_button, self.down_button):
            depth_row.addWidget(button)
        depth_row.addStretch()
        depth_note = QLabel("Depth chart changes save right away")
        depth_note.setObjectName("Muted")
        depth_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extra = QVBoxLayout()
        self.extra.addLayout(depth_row)
        self.extra.addWidget(depth_note)
        self._update_depth_buttons()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(self.heading)
        layout.addWidget(self.depth_label)
        layout.addLayout(form)
        layout.addLayout(self.extra)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

    def changes(self) -> dict[str, object]:
        """Only the fields the user changed, ready for update_player."""
        values: dict[str, object] = {
            "name": self.name.text(),
            "position": self.position.text(),
            "unit": Unit(self.unit.currentData()),
            "jersey_number": _from_spin(self.jersey),
            "height": self.height_input.text().strip() or None,
            "weight": _from_spin(self.weight),
            "college": self.college.text(),
            "years_experience": self.experience.value(),
            "rating": _from_spin(self.rating),
        }
        current = self.player.model_dump()
        current["height"] = _height_text(self.player.height) or None
        current["college"] = self.player.college or ""
        return {k: v for k, v in values.items() if v != current[k]}

    def save(self) -> None:
        changes = self.changes()
        if not changes:
            self.accept()
            return
        try:
            self.roster = self.service.update_player(self.team.abbreviation, self.key, changes)
        except EditError as error:
            self.show_error(str(error))
            return
        self.accept()

    def change_depth(self, action: str) -> None:
        """Make starter / move up / move down, saved immediately."""
        edits = {
            "starter": self.service.make_starter,
            "up": self.service.promote,
            "down": self.service.demote,
        }
        try:
            self.roster = edits[action](self.team.abbreviation, self.key)
        except EditError as error:
            self.show_error(str(error))
            return
        depth = self.key.depth_order
        new_depth = {"starter": 1, "up": depth - 1, "down": depth + 1}[action]
        self.key = PlayerKey(self.key.unit, self.key.position, new_depth)
        self.player = find_player(self.roster, self.key)
        self.depth_label.setText(depth_text(self.player))
        self.error_label.hide()
        self._update_depth_buttons()

    def _slot_size(self) -> int:
        roster = self.roster or self.service.load_roster(self.team.abbreviation)
        return sum(1 for p in roster.players if (p.unit, p.position) == self.key.slot())

    def _update_depth_buttons(self) -> None:
        first = self.key.depth_order == 1
        self.starter_button.setEnabled(not first)
        self.up_button.setEnabled(not first)
        self.down_button.setEnabled(self.key.depth_order < self._slot_size())

    def delete_player(self) -> None:
        if not self.confirm(f"Delete {self.player.name} from the roster? This cannot be undone."):
            return
        try:
            self.roster = self.service.remove_player(self.team.abbreviation, self.key)
        except EditError as error:
            self.show_error(str(error))
            return
        self.accept()

    def show_error(self, text: str) -> None:
        self.error_label.setText(text)
        self.error_label.show()

    def confirm(self, text: str) -> bool:
        """Ask a yes/no question. Separate so tests can answer it."""
        answer = QMessageBox.question(self, "Please confirm", text)
        return answer == QMessageBox.StandardButton.Yes


def _or_none(value: int | None) -> int:
    return value if value is not None else NONE


def _from_spin(spin: QSpinBox) -> int | None:
    return None if spin.value() == spin.minimum() else spin.value()


def _height_text(inches: int | None) -> str:
    return f"{inches // 12}-{inches % 12}" if inches is not None else ""
