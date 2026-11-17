"""Build the Windows app folder with PyInstaller.

    python packaging/build.py

Produces dist/RosterManager/RosterManager.exe plus its supporting files. The whole
dist/RosterManager folder is the app: zip it or copy it anywhere; no Python needed.
Then check it starts with:

    dist/RosterManager/RosterManager.exe --self-test

A one-folder build (not one-file) starts faster and is less often flagged by
antivirus tools than a self-extracting single exe.
"""

import os
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "src" / "rostermanager" / "data" / "templates"
WORK = ROOT / "build" / "pyinstaller"


def build() -> None:
    PyInstaller.__main__.run(
        [
            str(ROOT / "packaging" / "launcher.py"),
            "--name=RosterManager",
            "--windowed",  # no console window behind the app
            "--noconfirm",
            "--clean",
            f"--distpath={ROOT / 'dist'}",
            f"--workpath={WORK}",
            f"--specpath={WORK}",
            f"--paths={ROOT / 'src'}",
            # Roster templates, read with importlib.resources at runtime.
            f"--add-data={TEMPLATES}{os.pathsep}rostermanager/data/templates",
            # Imported lazily (only when downloading), so PyInstaller can't see it.
            "--hidden-import=rostermanager.data.nflverse",
            "--collect-submodules=nflreadpy",
            "--collect-data=nflreadpy",
            # Not used by the app; leaving them out keeps the build smaller.
            "--exclude-module=tkinter",
            "--exclude-module=pytest",
            "--exclude-module=mypy",
        ]
    )


if __name__ == "__main__":
    build()
