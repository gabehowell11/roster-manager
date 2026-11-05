import sys

from PySide6.QtWidgets import QApplication, QLabel


def main() -> None:
    app = QApplication(sys.argv)
    label = QLabel("Roster Manager")
    label.resize(400, 200)
    label.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
