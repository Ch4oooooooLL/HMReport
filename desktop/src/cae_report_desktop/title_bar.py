"""Custom Title Bar widget for CAE Report Desktop application."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class CustomTitleBar(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(36)
        self._drag_pos: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(8)

        # Brand Icon & Title
        self.icon_label = QLabel("CR")
        self.icon_label.setObjectName("TitleBarIcon")
        self.icon_label.setFixedSize(22, 22)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("CAE 结果分析与报告工作台 (HMReport)")
        self.title_label.setObjectName("TitleBarTitle")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch()

        # Window Control Buttons
        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("TitleMinBtn")
        self.min_btn.setFixedSize(42, 36)
        self.min_btn.setToolTip("最小化")
        self.min_btn.clicked.connect(self._minimize)

        self.max_btn = QPushButton("□")
        self.max_btn.setObjectName("TitleMaxBtn")
        self.max_btn.setFixedSize(42, 36)
        self.max_btn.setToolTip("最大化")
        self.max_btn.clicked.connect(self._toggle_maximize)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("TitleCloseBtn")
        self.close_btn.setFixedSize(42, 36)
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self._close_window)

        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)

    def _minimize(self) -> None:
        window = self.window()
        if window:
            window.showMinimized()

    def _toggle_maximize(self) -> None:
        window = self.window()
        if window:
            if window.isMaximized():
                window.showNormal()
                self.max_btn.setText("□")
            else:
                window.showMaximized()
                self.max_btn.setText("❐")

    def _close_window(self) -> None:
        window = self.window()
        if window:
            window.close()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            event.buttons() == Qt.MouseButton.LeftButton
            and self._drag_pos is not None
            and not self.window().isMaximized()
        ):
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
