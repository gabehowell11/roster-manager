"""Write packaging/icon.ico from the icon drawn in rostermanager.ui.app_icon.

    python packaging/make_icon.py

Run it again after changing the drawing, and commit the new icon.ico. The build
uses the committed file, so CI never needs a display to draw it.
"""

import os
import sys
from pathlib import Path

ICON = Path(__file__).resolve().parent / "icon.ico"


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from rostermanager.ui.app_icon import ico_bytes

    _app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    ICON.write_bytes(ico_bytes())
    print(f"wrote {ICON}")


if __name__ == "__main__":
    main()
