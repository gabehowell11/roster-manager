"""Start the app: python -m rostermanager (or RosterManager.exe in the Windows build).

--self-test starts everything offscreen against a throwaway database, checks the
bundled templates and NFL download code are present, and exits 0 on success. CI
runs it against the built exe to prove the bundle is complete.
"""

import os
import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        return self_test()

    # Imported here so `import rostermanager` never pulls in PySide6.
    from PySide6.QtWidgets import QApplication

    from rostermanager.services import RosterService
    from rostermanager.ui.main_window import MainWindow
    from rostermanager.ui.theme import apply_theme

    app = QApplication([sys.argv[0], *args])
    app.setApplicationName("Roster Manager")
    apply_theme(app)
    window = MainWindow(RosterService())
    window.show()
    return app.exec()


def self_test() -> int:
    """Build the whole UI offscreen and check bundled pieces. 0 means everything loaded."""
    import tempfile
    import traceback
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from rostermanager.data import RosterRepository
        from rostermanager.services import RosterService, template_path
        from rostermanager.ui.main_window import MainWindow
        from rostermanager.ui.theme import apply_theme

        app = QApplication.instance() or QApplication([sys.argv[0]])
        assert isinstance(app, QApplication)
        apply_theme(app)
        for kind in ("csv", "json"):
            if not template_path(kind).is_file():
                raise FileNotFoundError(f"missing template {template_path(kind)}")
        with tempfile.TemporaryDirectory() as folder:
            service = RosterService(RosterRepository(Path(folder) / "self_test.db"))
            roster = service.import_custom_file(template_path("json"))
            window = MainWindow(service)
            window.show()
            window.open_team(roster.team.abbreviation)
            app.processEvents()
            window.close()
            del window, service

        import rostermanager.data.nflverse  # noqa: F401 - proves polars and nflreadpy are bundled
    except Exception:  # noqa: BLE001 - any failure becomes a non-zero exit code
        traceback.print_exc()
        return 1
    print("self-test ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
