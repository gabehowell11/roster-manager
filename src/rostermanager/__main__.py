import sys


def main() -> None:
    # Imported here so `import rostermanager` never pulls in PySide6.
    from PySide6.QtWidgets import QApplication

    from rostermanager.services import RosterService
    from rostermanager.ui.main_window import MainWindow
    from rostermanager.ui.theme import apply_theme

    app = QApplication(sys.argv)
    app.setApplicationName("Roster Manager")
    apply_theme(app)
    window = MainWindow(RosterService())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
