from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, hyperview_executable: Path | None, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(620)
        self.hyperview_edit = QLineEdit(str(hyperview_executable or ""))
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse_hyperview)
        path_row = QHBoxLayout()
        path_row.addWidget(self.hyperview_edit)
        path_row.addWidget(browse)
        form = QFormLayout()
        form.addRow("HyperView 可执行文件", path_row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def hyperview_executable(self) -> Path | None:
        value = self.hyperview_edit.text().strip()
        return Path(value).expanduser().resolve() if value else None

    def _browse_hyperview(self) -> None:
        value, _ = QFileDialog.getOpenFileName(
            self,
            "选择 HyperView 可执行文件",
            self.hyperview_edit.text(),
            "HyperView (hw.exe);;可执行文件 (*.exe);;所有文件 (*)",
        )
        if value:
            self.hyperview_edit.setText(value)

    def accept(self) -> None:
        executable = self.hyperview_executable
        if executable is not None and not executable.is_file():
            QMessageBox.warning(self, "路径无效", "请选择存在的 HyperView 可执行文件（hw.exe）。")
            return
        super().accept()
