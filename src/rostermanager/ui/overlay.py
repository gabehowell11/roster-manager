"""Show a dialog inside the main window, centered over a lightly blurred background."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsBlurEffect,
    QGraphicsDropShadowEffect,
    QLabel,
    QMessageBox,
    QWidget,
)

BLUR_RADIUS = 4.0  # very slight: the field stays recognizable behind the editor
DIM = "rgba(0, 0, 0, 70)"  # slight darkening so the editor stands out


class BlurOverlay(QWidget):
    """Covers host with a blurred, dimmed snapshot of it and keeps dialog centered.

    The overlay swallows clicks, so nothing behind it can be used while it is open.
    """

    def __init__(self, host: QWidget, dialog: QDialog) -> None:
        snapshot = host.grab()  # taken before the overlay exists, so it isn't in the shot
        super().__init__(host)
        self.host = host
        self.dialog = dialog

        self.backdrop = QLabel(self)
        self.backdrop.setPixmap(snapshot)
        self.backdrop.setScaledContents(True)  # a resize stretches it instead of leaving gaps
        blur = QGraphicsBlurEffect(self.backdrop)
        blur.setBlurRadius(BLUR_RADIUS)
        blur.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
        self.backdrop.setGraphicsEffect(blur)

        self.tint = QWidget(self)
        self.tint.setStyleSheet(f"background-color: {DIM};")
        self.tint.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        # Embed the dialog: no title bar, so it can't be dragged off center.
        dialog.setParent(self, Qt.WindowType.Widget)
        dialog.setObjectName("Sheet")
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = dialog.layout()
        if layout is not None:
            layout.setContentsMargins(24, 18, 24, 18)  # room inside the rounded border
        shadow = QGraphicsDropShadowEffect(dialog)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 150))
        dialog.setGraphicsEffect(shadow)

        host.installEventFilter(self)
        self._fit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.host and event.type() == QEvent.Type.Resize:
            self._fit()
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        event.accept()  # clicks on the blurred background do nothing

    def _fit(self) -> None:
        rect = self.host.rect()
        self.setGeometry(rect)
        self.backdrop.setGeometry(rect)
        self.tint.setGeometry(rect)
        self.dialog.adjustSize()
        size = self.dialog.size()
        self.dialog.move((rect.width() - size.width()) // 2, (rect.height() - size.height()) // 2)

    def close_overlay(self) -> None:
        self.host.removeEventFilter(self)
        self.hide()
        self.deleteLater()


def exec_over(dialog: QDialog, host: QWidget) -> int:
    """Run dialog modally inside host, centered on a blurred copy of host.

    Returns exec()'s result, like QDialog.exec().
    """
    overlay = BlurOverlay(host, dialog)
    overlay.show()
    overlay.raise_()
    dialog.setFocus()
    try:
        return dialog.exec()
    finally:
        overlay.close_overlay()


def confirm_over(host: QWidget, title: str, text: str, yes_text: str = "Yes") -> bool:
    """Ask a yes/no question in the middle of host, over the blur. No is the default."""
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(f"<b>{title}</b>")
    box.setInformativeText(text)
    # Wide enough that a one-line question doesn't wrap into a narrow column.
    box.setStyleSheet("QLabel#qt_msgbox_informativelabel { min-width: 300px; }")
    yes = box.addButton(yes_text, QMessageBox.ButtonRole.YesRole)
    if yes_text == "Delete":
        yes.setObjectName("Danger")
    no = box.addButton("Cancel", QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no)
    box.setEscapeButton(no)
    exec_over(box, host)
    return box.clickedButton() is yes
