"""Build dist/RosterManagerSetup.exe with Inno Setup.

    python packaging/build_installer.py

Builds the app folder first (packaging/build.py) unless it already exists, then
compiles packaging/installer.iss with the version from pyproject.toml. Needs Inno
Setup 6 (https://jrsoftware.org/isinfo.php); GitHub's Windows runners have it.
"""

import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "packaging" / "installer.iss"
APP_EXE = ROOT / "dist" / "RosterManager" / "RosterManager.exe"
SETUP_EXE = ROOT / "dist" / "RosterManagerSetup.exe"


def app_version(pyproject: Path = ROOT / "pyproject.toml") -> str:
    """The version in pyproject.toml, e.g. "0.1.0"."""
    with pyproject.open("rb") as file:
        version: str = tomllib.load(file)["project"]["version"]
    return version


def find_iscc(
    on_path: str | None = None, folders: Iterable[str | None] | None = None
) -> Path | None:
    """ISCC.exe from PATH or a standard Inno Setup 6 install folder, else None."""
    found = on_path if on_path is not None else shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return Path(found)
    if folders is None:
        folders = (
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramFiles"),
            os.environ.get("LOCALAPPDATA") and str(Path(os.environ["LOCALAPPDATA"]) / "Programs"),
        )
    for folder in folders:
        if folder:
            candidate = Path(folder) / "Inno Setup 6" / "ISCC.exe"
            if candidate.is_file():
                return candidate
    return None


def iscc_command(iscc: Path, version: str) -> list[str]:
    return [str(iscc), f"/DAppVersion={version}", str(SCRIPT)]


def main() -> int:
    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup 6 not found. Install it from https://jrsoftware.org/isinfo.php")
        return 1
    if not APP_EXE.is_file():
        subprocess.run([sys.executable, str(ROOT / "packaging" / "build.py")], check=True)
    subprocess.run(iscc_command(iscc, app_version()), check=True)
    print(f"built {SETUP_EXE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
