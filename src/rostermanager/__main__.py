import sys


def main() -> None:
    # Imported here so `import rostermanager` never pulls in PySide6.
    from PySide6.QtWidgets import QApplication

    from rostermanager.services import RosterService
    from rostermanager.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Roster Manager")
    window = MainWindow(RosterService())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
