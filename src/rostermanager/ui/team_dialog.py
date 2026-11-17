"""A small dialog asking for a custom team's abbreviation and name."""

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from rostermanager.models import Team


class TeamDialog(QDialog):
    """Asks for a team. After exec() is accepted, team holds a valid Team."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom team")
        self.team: Team | None = None

        self.abbreviation = QLineEdit()
        self.abbreviation.setPlaceholderText("2-4 letters, e.g. EXC")
        self.abbreviation.setMaxLength(4)
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Example City")
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #B00020;")
        self.error_label.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow("Abbreviation", self.abbreviation)
        form.addRow("Team name", self.name)
        form.addRow(self.error_label)
        form.addRow(buttons)

    def accept(self) -> None:
        try:
            self.team = Team(abbreviation=self.abbreviation.text(), name=self.name.text())
        except ValidationError as error:
            fields = sorted({str(item["loc"][0]) for item in error.errors()})
            self.error_label.setText("Please fix: " + ", ".join(fields))
            return
        super().accept()
