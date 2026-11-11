"""Where the app keeps its files on disk."""

from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "RosterManager"
DB_FILENAME = "rosters.db"


def default_db_path() -> Path:
    """The SQLite file in the user's app data folder, e.g. %LOCALAPPDATA%\\RosterManager."""
    return Path(user_data_dir(APP_NAME, appauthor=False)) / DB_FILENAME
