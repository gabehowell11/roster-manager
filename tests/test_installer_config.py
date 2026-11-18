"""Tests for the installer setup: icon, Inno Setup script, and the build helper.

Inno Setup itself only runs in CI (packaging/test_installer.ps1 installs, self-tests,
and uninstalls the real installer there); these check what can be checked anywhere.
"""

import importlib.util
import struct
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, PACKAGING / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def iss() -> str:
    return (PACKAGING / "installer.iss").read_text(encoding="utf-8")


def ico_sizes(data: bytes) -> list[int]:
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 1)
    sizes = []
    for i in range(count):
        width, *_rest, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        assert data[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
        assert offset + length <= len(data)
        sizes.append(width or 256)
    return sizes


# Icon


@pytest.mark.usefixtures("qapp")
def test_ico_holds_every_size_as_png() -> None:
    from rostermanager.ui.app_icon import ICO_SIZES, ico_bytes

    assert ico_sizes(ico_bytes()) == list(ICO_SIZES)


@pytest.mark.usefixtures("qapp")
def test_committed_icon_matches_the_drawing() -> None:
    """Run python packaging/make_icon.py after changing app_icon.py."""
    from rostermanager.ui.app_icon import ICO_SIZES

    committed = (PACKAGING / "icon.ico").read_bytes()
    assert ico_sizes(committed) == list(ICO_SIZES)


@pytest.mark.usefixtures("qapp")
def test_icon_is_drawn_with_transparent_corners() -> None:
    from rostermanager.ui.app_icon import app_icon, render

    image = render(64)
    assert image.pixelColor(0, 0).alpha() == 0  # rounded corner
    assert image.pixelColor(32, 32).alpha() == 255
    assert not app_icon().isNull()


# Inno Setup script


def test_installer_is_per_user_with_desktop_and_start_menu_icons() -> None:
    script = iss()
    assert "PrivilegesRequired=lowest" in script  # no admin prompt
    assert r"DefaultDirName={autopf}\{#AppName}" in script
    assert r"{autodesktop}\{#AppName}" in script
    assert r"{autoprograms}\{#AppName}" in script
    assert "OutputBaseFilename=RosterManagerSetup" in script
    assert "SetupIconFile=icon.ico" in script


def test_desktop_icon_is_offered_and_ticked() -> None:
    task = next(line for line in iss().splitlines() if line.startswith('Name: "desktopicon"'))
    assert "unchecked" not in task


def test_app_id_never_changes() -> None:
    """Changing it would make Windows treat an upgrade as a second app."""
    assert "AppId={{6D99A611-9021-4CB2-93E9-0CD60968A896}" in iss()


def test_shortcuts_share_the_apps_taskbar_id() -> None:
    from rostermanager.__main__ import APP_USER_MODEL_ID

    assert f'#define AppUserModelID "{APP_USER_MODEL_ID}"' in iss()


def test_installer_packs_the_pyinstaller_folder() -> None:
    script = iss()
    assert r'Source: "..\dist\RosterManager\*"' in script
    assert '#define AppExe "RosterManager.exe"' in script


# build_installer.py


def test_version_comes_from_pyproject(tmp_path: Path) -> None:
    build = load("build_installer")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8")
    assert build.app_version(pyproject) == "1.2.3"
    assert build.app_version() == build.app_version(ROOT / "pyproject.toml")


def test_iscc_command_passes_the_version() -> None:
    build = load("build_installer")
    command = build.iscc_command(Path("ISCC.exe"), "1.2.3")
    assert command[:2] == ["ISCC.exe", "/DAppVersion=1.2.3"]
    assert command[2].endswith("installer.iss")


def test_find_iscc_checks_path_then_install_folders(tmp_path: Path) -> None:
    build = load("build_installer")
    assert build.find_iscc(on_path=r"C:\tools\ISCC.exe") == Path(r"C:\tools\ISCC.exe")
    assert build.find_iscc(on_path="", folders=[str(tmp_path), None]) is None
    installed = tmp_path / "Inno Setup 6" / "ISCC.exe"
    installed.parent.mkdir()
    installed.write_bytes(b"")
    assert build.find_iscc(on_path="", folders=[None, str(tmp_path)]) == installed


def test_exe_build_uses_the_icon() -> None:
    text = (PACKAGING / "build.py").read_text(encoding="utf-8")
    assert "--icon=" in text
    assert (PACKAGING / "icon.ico").is_file()
