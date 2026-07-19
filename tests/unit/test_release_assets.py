from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_script_keeps_desktop_entry_at_archive_root() -> None:
    script = (REPO_ROOT / "tools" / "package.ps1").read_text(encoding="utf-8")

    desktop_command = script.split("--name CAEReportDesktop", maxsplit=1)[0].rsplit("PyInstaller", maxsplit=1)[1]
    assert "--onefile" in desktop_command
    assert "--onedir" not in desktop_command
    assert '--icon "resources/app-icon.ico"' in script
    assert "CAE_Result_Analysis_Report_Workbench_SPEC.md" not in script


def test_application_icon_assets_are_valid() -> None:
    png_path = REPO_ROOT / "resources" / "app-icon.png"
    ico_path = REPO_ROOT / "resources" / "app-icon.ico"

    with Image.open(png_path) as png:
        assert png.mode == "RGBA"
        assert png.size[0] == png.size[1]
        assert png.getpixel((0, 0))[3] == 0

    with Image.open(ico_path) as ico:
        assert ico.format == "ICO"
        assert (256, 256) in ico.info["sizes"]
        assert (16, 16) in ico.info["sizes"]
