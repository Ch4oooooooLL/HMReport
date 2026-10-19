from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings


class DesktopSettings:
    HYPERVIEW_EXECUTABLE_KEY = "hyperview/executable"

    def __init__(self, store: QSettings | None = None) -> None:
        self.store = store or QSettings()

    @property
    def hyperview_executable(self) -> Path | None:
        value = str(self.store.value(self.HYPERVIEW_EXECUTABLE_KEY, "")).strip()
        return Path(value).expanduser().resolve() if value else None

    @hyperview_executable.setter
    def hyperview_executable(self, value: Path | None) -> None:
        if value is None:
            self.store.remove(self.HYPERVIEW_EXECUTABLE_KEY)
        else:
            self.store.setValue(self.HYPERVIEW_EXECUTABLE_KEY, str(value.expanduser().resolve()))
        self.store.sync()
