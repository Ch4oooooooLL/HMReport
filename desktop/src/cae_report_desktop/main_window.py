from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .dialogs.new_project import NewProjectWizard
from .process_supervisor import ProcessSupervisor
from .server_client import ServerClient
from .style import CAE_DESKTOP_QSS
from .title_bar import CustomTitleBar


class MainWindow(QMainWindow):
    def __init__(self, workspace: Path) -> None:
        super().__init__()
        self.workspace = workspace
        self.setWindowTitle("CAE 结果分析与报告工作台 (HMReport)")
        self.resize(1280, 820)
        
        # Enable Frameless Window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self._resize_margin = 6
        self._is_resizing = False
        self._resize_drag_pos: QPoint | None = None
        self._resize_direction: str | None = None

        self.client: ServerClient | None = None
        self.projects: list[dict[str, Any]] = []
        self.current_project: dict[str, Any] | None = None
        self.current_run: dict[str, Any] | None = None
        self.supervisor = ProcessSupervisor(workspace, self)
        self.supervisor.server_ready.connect(self._connected)
        self.supervisor.status_changed.connect(self._process_status)
        self.supervisor.output.connect(self._log)
        self.setStyleSheet(CAE_DESKTOP_QSS)
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self.supervisor.start()

    def _build_ui(self) -> None:
        # Root container with custom border
        self.container = QWidget(self)
        self.container.setObjectName("FramelessContainer")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBar(self.container)
        container_layout.addWidget(self.title_bar)

        # ToolBar Panel
        toolbar_wrapper = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_wrapper)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        toolbar = self.addToolBar("项目操作")
        toolbar.setMovable(False)
        for text, slot in (
            ("新建项目", self.new_project),
            ("重新运行", self.rerun_project),
            ("刷新", self.refresh),
            ("打开 Web 结果", self.open_web),
            ("打开项目文件夹", self.open_folder),
        ):
            action = QAction(text, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

        diagnostics_action = QAction("导出诊断包", self)
        diagnostics_action.triggered.connect(self.export_diagnostics)
        toolbar.addAction(diagnostics_action)

        delete_action = QAction("删除项目", self)
        delete_action.triggered.connect(self.delete_project)
        toolbar.addAction(delete_action)

        container_layout.addWidget(toolbar)

        # Main Content Splitter
        self.project_list = QListWidget()
        self.project_list.setMinimumWidth(280)
        self.project_list.currentItemChanged.connect(self._project_selected)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_header = QLabel("工程项目列表")
        left_header.setStyleSheet("font-weight: 600; color: #424242; font-size: 12px; margin-bottom: 2px;")
        left_layout.addWidget(left_header)
        left_layout.addWidget(self.project_list)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(12, 8, 12, 8)

        self.title = QLabel("等待本地服务连接…")
        self.title.setObjectName("ProjectTitle")
        detail_layout.addWidget(self.title)

        form = QFormLayout()
        form.setSpacing(6)
        self.code_label = QLabel("—")
        self.fem_label = QLabel("—")
        self.h3d_label = QLabel("—")
        self.run_label = QLabel("—")
        for widget in (self.fem_label, self.h3d_label):
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            widget.setWordWrap(True)

        form.addRow("项目编号:", self.code_label)
        form.addRow("FEM 文件:", self.fem_label)
        form.addRow("H3D 文件:", self.h3d_label)
        form.addRow("当前 Run:", self.run_label)
        detail_layout.addLayout(form)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        for text, action in (
            ("启动 Run", "start"),
            ("暂停", "pause"),
            ("恢复", "resume"),
            ("取消", "cancel"),
            ("重试失败项", "retry-failed")
        ):
            button = QPushButton(text)
            if action in ("start", "retry-failed"):
                button.setProperty("primary", True)
            elif action == "cancel":
                button.setProperty("danger", True)
            button.clicked.connect(lambda _checked=False, value=action: self.control_run(value))
            controls.addWidget(button)
        controls.addStretch()
        detail_layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setFormat("总体进度: %p%")
        detail_layout.addWidget(self.progress)

        self.tasks = QTableWidget(0, 4)
        self.tasks.setHorizontalHeaderLabels(["任务类型", "状态", "阶段进度", "当前执行信息"])
        self.tasks.horizontalHeader().setStretchLastSection(True)
        self.tasks.setAlternatingRowColors(True)
        detail_layout.addWidget(self.tasks, 1)

        # Log Console Header & TextEdit
        console_box = QWidget()
        console_layout = QVBoxLayout(console_box)
        console_layout.setContentsMargins(0, 2, 0, 0)
        console_layout.setSpacing(4)
        
        console_header = QHBoxLayout()
        log_title = QLabel("系统运行日志 (Console Log)")
        log_title.setStyleSheet("font-weight: 600; color: #424242; font-size: 12px;")
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setFixedSize(68, 22)
        clear_log_btn.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        clear_log_btn.clicked.connect(lambda: self.log.clear())
        
        console_header.addWidget(log_title)
        console_header.addStretch()
        console_header.addWidget(clear_log_btn)
        console_layout.addLayout(console_header)

        self.log = QTextEdit()
        self.log.setObjectName("ConsoleLog")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        console_layout.addWidget(self.log)

        detail_layout.addWidget(console_box)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(detail)
        splitter.setStretchFactor(1, 1)
        container_layout.addWidget(splitter, 1)

        # Status Bar
        container_layout.addWidget(self.statusBar())
        self.setCentralWidget(self.container)

        self.server_status = QLabel("Server: starting")
        self.worker_status = QLabel("Worker: waiting")
        self.hyperview_status = QLabel("HyperView: idle")
        self.statusBar().addPermanentWidget(self.server_status)
        self.statusBar().addPermanentWidget(self.worker_status)
        self.statusBar().addPermanentWidget(self.hyperview_status)

    # Mouse Events for Window Border Resizing
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._resize_direction:
            self._is_resizing = True
            self._resize_drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        rect = self.rect()
        margin = self._resize_margin

        if not self._is_resizing:
            left_edge = pos.x() <= margin
            right_edge = pos.x() >= rect.width() - margin
            top_edge = pos.y() <= margin
            bottom_edge = pos.y() >= rect.height() - margin

            if top_edge and left_edge:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                self._resize_direction = "top_left"
            elif top_edge and right_edge:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                self._resize_direction = "top_right"
            elif bottom_edge and left_edge:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                self._resize_direction = "bottom_left"
            elif bottom_edge and right_edge:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                self._resize_direction = "bottom_right"
            elif left_edge:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self._resize_direction = "left"
            elif right_edge:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self._resize_direction = "right"
            elif top_edge:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
                self._resize_direction = "top"
            elif bottom_edge:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
                self._resize_direction = "bottom"
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self._resize_direction = None
        else:
            global_pos = event.globalPosition().toPoint()
            diff = global_pos - (self._resize_drag_pos or global_pos)
            geo = self.geometry()

            if "right" in (self._resize_direction or ""):
                geo.setWidth(max(800, geo.width() + diff.x()))
            if "bottom" in (self._resize_direction or ""):
                geo.setHeight(max(600, geo.height() + diff.y()))

            self.setGeometry(geo)
            self._resize_drag_pos = global_pos
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._is_resizing = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def _connected(self, url: str) -> None:
        self.client = ServerClient(url)
        self.timer.start()
        self.refresh()

    def _process_status(self, process: str, status: str) -> None:
        label = self.server_status if process == "Server" else self.worker_status
        label.setText(f"{process}: {status}")

    def _log(self, text: str) -> None:
        self.log.append(text.rstrip())

    def refresh(self) -> None:
        if self.client is None:
            return
        try:
            current_id = self.current_project["id"] if self.current_project else None
            self.projects = self.client.get("/api/v1/projects")
            self._fill_projects(current_id)
            if current_id:
                self._load_project(current_id)
            health = self.client.get("/health")
            worker_state = health.get('worker', 'unknown')
            self.worker_status.setText(f"Worker: {worker_state}")
        except Exception as exc:
            self.statusBar().showMessage(f"刷新失败：{exc}", 4000)

    def _fill_projects(self, selected_id: str | None) -> None:
        if self.project_list.count() == len(self.projects) and all(self.project_list.item(i).data(Qt.ItemDataRole.UserRole) == project["id"] for i, project in enumerate(self.projects)):
            return
        self.project_list.blockSignals(True)
        self.project_list.clear()
        selected_row = 0
        for index, project in enumerate(self.projects):
            item = QListWidgetItem(f"{project['name']}\n{project.get('code') or 'PRJ-UNASSIGNED'}  ·  {project['status']}")
            item.setData(Qt.ItemDataRole.UserRole, project["id"])
            self.project_list.addItem(item)
            if project["id"] == selected_id:
                selected_row = index
        self.project_list.blockSignals(False)
        if self.projects:
            self.project_list.setCurrentRow(selected_row)

    def _project_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current:
            self._load_project(current.data(Qt.ItemDataRole.UserRole))

    def _load_project(self, project_id: str) -> None:
        if self.client is None:
            return
        project = self.client.get(f"/api/v1/projects/{project_id}")
        self.current_project = project
        self.title.setText(project["name"])
        self.code_label.setText(project.get("code") or "—")
        sources = {source["source_type"]: source for source in project["sources"]}
        self.fem_label.setText(sources.get("fem", {}).get("absolute_path", "—"))
        self.h3d_label.setText(sources.get("h3d", {}).get("absolute_path", "—"))
        runs = project.get("runs", [])
        if runs:
            self.current_run = self.client.get(f"/api/v1/runs/{runs[0]['id']}")
            self._fill_run(self.current_run)
        else:
            self.current_run = None
            self._fill_run(None)

    def _fill_run(self, run: dict[str, Any] | None) -> None:
        self.tasks.setRowCount(0)
        if run is None:
            self.run_label.setText("—")
            self.progress.setValue(0)
            return
        self.run_label.setText(f"{run['name']}  ·  {run['status']}")
        self.progress.setValue(run["progress"])
        self.tasks.setRowCount(len(run["tasks"]))
        for row, task in enumerate(run["tasks"]):
            status_text = "已完成" if task["status"] == "completed" else "运行中" if task["status"] == "running" else "失败" if task["status"] == "failed" else "等待中"
            values = [task["task_type"], status_text, f"{task['progress_current']}/{task['progress_total']}", task["progress_message"]]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 1:
                    if task["status"] == "completed":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    elif task["status"] == "running":
                        item.setForeground(Qt.GlobalColor.darkBlue)
                    elif task["status"] == "failed":
                        item.setForeground(Qt.GlobalColor.red)
                self.tasks.setItem(row, column, item)

        active_hv = any(task["status"] == "running" and not task["task_type"].startswith("fem.") for task in run["tasks"])
        self.hyperview_status.setText(f"HyperView: {'busy' if active_hv else 'idle'}")

    def new_project(self) -> None:
        if self.client is None:
            return
        wizard = NewProjectWizard(self.workspace / "projects", self)
        if wizard.exec():
            try:
                project = self.client.post("/api/v1/projects", wizard.payload())
                self.current_project = project
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "创建失败", str(exc))

    def control_run(self, action: str) -> None:
        if self.client is None or self.current_run is None:
            return
        try:
            self.current_run = self.client.post(f"/api/v1/runs/{self.current_run['id']}/{action}")
            self._fill_run(self.current_run)
        except Exception as exc:
            err_text = str(exc)
            if any(k in err_text for k in ("运行中", "排队", "已完成")):
                QMessageBox.information(self, "运行提示", err_text)
            else:
                QMessageBox.warning(self, "操作提示", err_text)

    def rerun_project(self) -> None:
        if self.client is None or self.current_project is None:
            return
        answer = QMessageBox.question(
            self,
            "重新运行分析",
            "将重新读取当前 FEM/H3D、接受最新文件指纹并创建一个新 Run。"
            "上一次 Run 的结果、截图和报告会继续保留。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.current_run = self.client.post(
                f"/api/v1/projects/{self.current_project['id']}/rerun"
            )
            self._fill_run(self.current_run)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "重新运行失败", str(exc))

    def open_web(self) -> None:
        if self.client and self.current_project:
            webbrowser.open(f"{self.client.base_url}/projects/{self.current_project['id']}")

    def open_folder(self) -> None:
        if self.client and self.current_project:
            self.client.post(f"/api/v1/projects/{self.current_project['id']}/reveal-folder")

    def delete_project(self) -> None:
        if self.client is None or self.current_project is None:
            return
        answer = QMessageBox.warning(self, "删除项目数据", "将删除工作台生成的项目目录、截图和报告。外部 FEM/H3D 不会删除。是否继续？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.client.delete(f"/api/v1/projects/{self.current_project['id']}")
            self.current_project = None
            self.current_run = None
            self.refresh()

    def export_diagnostics(self) -> None:
        if self.client is None:
            return
        try:
            result = self.client.post("/api/v1/diagnostics/export")
            webbrowser.open(f"{self.client.base_url}{result['download_url']}")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.timer.stop()
        if self.client:
            self.client.close()
        self.supervisor.stop()
        event.accept()
