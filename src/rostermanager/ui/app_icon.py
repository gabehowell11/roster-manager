"""The app icon, drawn in code: a rounded green field with yard lines and a football.

No logos or official branding. app_icon() is the window/taskbar icon at runtime;
ico_bytes() writes the same drawing as a Windows .ico for the exe, shortcuts, and
installer (packaging/make_icon.py saves it to packaging/icon.ico).
"""

import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

_GRASS_TOP = QColor("#3B7A4B")
_GRASS_BOTTOM = QColor("#245236")
_LINE = QColor(255, 255, 255, 150)
_BALL = QColor("#8B4A22")
_BALL_EDGE = QColor("#5A2E14")
_LACES = QColor("#FFFFFF")


def render(size: int) -> QImage:
    """The icon at size x size pixels, transparent outside the rounded square."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 256, size / 256)  # draw on a 256-unit canvas at any size

    field = QPainterPath()
    field.addRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    grass = QLinearGradient(0, 8, 0, 248)
    grass.setColorAt(0, _GRASS_TOP)
    grass.setColorAt(1, _GRASS_BOTTOM)
    p.fillPath(field, grass)

    # Yard lines; small icons get fewer, thicker ones so they don't turn to mush.
    p.save()
    p.setClipPath(field)
    lines = (64, 128, 192) if size >= 32 else (128,)
    p.setPen(QPen(_LINE, 6 if size >= 32 else 14))
    for x in lines:
        p.drawLine(QPointF(x, 8), QPointF(x, 248))
    p.restore()

    # The football, tilted like it's mid-spiral.
    p.save()
    p.translate(128, 128)
    p.rotate(-35)
    ball = QPainterPath()
    ball.moveTo(-92, 0)
    ball.cubicTo(-52, -62, 52, -62, 92, 0)
    ball.cubicTo(52, 62, -52, 62, -92, 0)
    p.setPen(QPen(_BALL_EDGE, 6))
    p.setBrush(_BALL)
    p.drawPath(ball)
    if size >= 24:  # laces vanish into noise below this
        p.setPen(QPen(_LACES, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-34, 0), QPointF(34, 0))
        for x in (-22, -7, 8, 23):
            p.drawLine(QPointF(x, -12), QPointF(x, 12))
    p.restore()

    p.end()
    return image


def app_icon() -> QIcon:
    """The window and taskbar icon."""
    icon = QIcon()
    for size in ICO_SIZES:
        icon.addPixmap(QPixmap.fromImage(render(size)))
    return icon


def _png(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # The stubs say bytes, but PySide6 only accepts a str here at runtime.
    image.save(buffer, "PNG")  # type: ignore[call-overload]
    buffer.close()
    return bytes(data.data())


def ico_bytes(sizes: tuple[int, ...] = ICO_SIZES) -> bytes:
    """A .ico file holding the icon at every size, each stored as PNG.

    Windows Vista and later read PNG entries; Qt's own ICO writer only stores one
    size, which looks blurry on the desktop.
    """
    images = [_png(render(size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))  # reserved, type 1 = icon, count
    offset = len(header) + 16 * len(images)
    entries = b""
    for size, png in zip(sizes, images, strict=True):
        side = 0 if size >= 256 else size  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    return header + entries + b"".join(images)
