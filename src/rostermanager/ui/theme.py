"""The app's look: a dull dark blue theme with flat, rounded buttons.

Colors live here so every widget shares them. apply_theme() is called once at
startup; widgets only set object names (like "Title") to pick up styles.
"""

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from rostermanager.models import Team
from rostermanager.ui.player_card import contrast_ratio

BACKGROUND = "#1C2635"  # dull dark blue behind everything
SURFACE = "#253247"  # buttons, lists, inputs, group boxes
SURFACE_HOVER = "#2E3D55"
BORDER = "#36465E"
TEXT = "#E4E9F0"
MUTED_TEXT = "#8F9CB0"
ACCENT = "#4F7CC2"  # selected items and checked buttons
ACCENT_HOVER = "#5C89CF"

FONT_FAMILY = "Segoe UI"

STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-family: "{FONT_FAMILY}";
    font-size: 13px;
}}
QMainWindow, QDialog, QMessageBox {{
    background-color: {BACKGROUND};
}}
QLabel {{
    background: transparent;
}}
QLabel#Title {{
    font-size: 28px;
    font-weight: 700;
}}
QLabel#TeamTitle {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel#Muted {{
    color: {MUTED_TEXT};
    font-size: 12px;
}}
QLabel#Status {{
    color: {MUTED_TEXT};
}}
QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 22px;
    padding: 14px 10px 10px 10px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 6px;
    font-size: 14px;
}}
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
}}
QGroupBox QPushButton {{
    background-color: {BACKGROUND};
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
    border-color: {ACCENT};
}}
QPushButton:pressed, QPushButton:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #FFFFFF;
}}
QPushButton:checked:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton:disabled {{
    color: {MUTED_TEXT};
    border-color: {SURFACE};
}}
QListWidget, QLineEdit, QComboBox {{
    background-color: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QListWidget {{
    outline: 0;  /* no dotted focus box inside the selected row */
}}
QListWidget::item {{
    padding: 8px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background-color: {SURFACE_HOVER};
}}
QListWidget::item:selected {{
    background-color: {ACCENT};
    color: #FFFFFF;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QToolTip {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Give the whole app the dark blue look. Safe to call more than once."""
    app.setStyle("Fusion")  # draws consistently with style sheets on every Windows version
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BACKGROUND),
        (QPalette.ColorRole.Base, BACKGROUND),
        (QPalette.ColorRole.AlternateBase, SURFACE),
        (QPalette.ColorRole.Button, SURFACE),
        (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.Text, TEXT),
        (QPalette.ColorRole.ButtonText, TEXT),
        (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, "#FFFFFF"),
        (QPalette.ColorRole.ToolTipBase, SURFACE),
        (QPalette.ColorRole.ToolTipText, TEXT),
        (QPalette.ColorRole.PlaceholderText, MUTED_TEXT),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(STYLESHEET)


def team_title_color(team: Team) -> str:
    """The team's primary color if it reads well on the background, else its
    secondary color, else plain text color.

    2.5:1 is a little under the usual 3:1 for large text; the title is big and bold,
    and this lets warm team colors like burnt orange show instead of plain white.
    """
    for color in (team.primary_color, team.secondary_color):
        if contrast_ratio(color, BACKGROUND) >= 2.5:
            return color
    return TEXT
