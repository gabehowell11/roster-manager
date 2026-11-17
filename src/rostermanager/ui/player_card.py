"""PlayerCard: one player drawn as a card in team colors. No logos."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from rostermanager.models import Player, Team

STARTER_SIZE = (100, 80)
BACKUP_SIZE = (92, 60)


def _luminance(hex_color: str) -> float:
    """Relative luminance (WCAG) of a #RRGGBB color, 0 (black) to 1 (white)."""

    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colors, 1 to 21."""
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def text_color(background: str, preferred: str) -> str:
    """preferred if it is readable on background, otherwise black or white."""
    if contrast_ratio(background, preferred) >= 3:
        return preferred
    return "#000000" if _luminance(background) > 0.18 else "#FFFFFF"


def format_height(inches: int | None) -> str:
    return f"{inches // 12}'{inches % 12}\"" if inches is not None else "-"


class PlayerCard(QFrame):
    """A card with jersey number, name, position, and rating.

    Starters are larger and solid in the team's primary color. Backups are smaller
    and lighter so they read as sitting behind the starter. Clicking a card emits
    clicked with its Player.
    """

    clicked = Signal(object)

    def __init__(
        self, player: Player, team: Team, starter: bool, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.player = player
        self.is_starter = starter
        self.setObjectName("PlayerCard")

        jersey = f"#{player.jersey_number}" if player.jersey_number is not None else "#--"
        rating = str(player.rating) if player.rating is not None else "--"
        self.top_label = QLabel(f"{jersey}  {player.position}")
        self.name_label = QLabel(player.name)
        self.name_label.setWordWrap(True)
        self.rating_label = QLabel(f"Rating {rating}")

        for label in (self.top_label, self.name_label, self.rating_label):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(0)
        layout.addWidget(self.top_label)
        layout.addWidget(self.name_label, stretch=1)
        layout.addWidget(self.rating_label)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(*(STARTER_SIZE if starter else BACKUP_SIZE))
        self.setToolTip(self._details())
        self._apply_style(team)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit(self.player)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _details(self) -> str:
        p = self.player
        weight = f"{p.weight} lb" if p.weight is not None else "-"
        role = "Starter" if self.is_starter else f"Backup (depth {p.depth_order})"
        return (
            f"{p.name}\n{p.position}, {role}\n"
            f"Height {format_height(p.height)}, weight {weight}\n"
            f"College: {p.college or '-'}\nExperience: {p.years_experience} yr"
        )

    def _apply_style(self, team: Team) -> None:
        if self.is_starter:
            background, border, width = team.primary_color, team.secondary_color, 2
            self.foreground = text_color(background, team.secondary_color)
            name_size, small_size = 13, 10
        else:
            # Dark slate to match the app theme; the team color stays on the border.
            background, border, width = "#2B3A4F", team.primary_color, 1
            self.foreground = "#D5DCE6"
            name_size, small_size = 11, 9
        self.background = background
        self.setStyleSheet(
            f"""
            QFrame#PlayerCard {{
                background-color: {background};
                border: {width}px solid {border};
                border-radius: 8px;
            }}
            QFrame#PlayerCard QLabel {{
                color: {self.foreground};
                background: transparent;
                font-size: {small_size}px;
            }}
            """
        )
        self.name_label.setStyleSheet(f"font-size: {name_size}px; font-weight: bold;")
