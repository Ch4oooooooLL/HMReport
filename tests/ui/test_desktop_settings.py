from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from cae_report_desktop.settings import DesktopSettings


def test_hyperview_path_is_persisted(tmp_path: Path) -> None:
    store_path = tmp_path / "desktop.ini"
    first_store = QSettings(str(store_path), QSettings.Format.IniFormat)
    first = DesktopSettings(first_store)
    executable = tmp_path / "Altair" / "hw.exe"

    first.hyperview_executable = executable
    first_store.sync()

    second = DesktopSettings(QSettings(str(store_path), QSettings.Format.IniFormat))
    assert second.hyperview_executable == executable.resolve()


def test_empty_hyperview_path_uses_application_default(tmp_path: Path) -> None:
    settings = DesktopSettings(QSettings(str(tmp_path / "desktop.ini"), QSettings.Format.IniFormat))

    assert settings.hyperview_executable is None
