from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
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


class MainWindow(QMainWindow):
    def __init__(self, workspace: Path) -> None:
        super().__init__()
        self.workspace = workspace
        self.setWindowTitle("CAE 结果分析与报告工作台")
        self.resize(1280, 820)
        self.client: ServerClient | None = None
        self.projects: list[dict[str, Any]] = []
        self.current_project: dict[str, Any] | None = None
        self.current_run: dict[str, Any] | None = None
        self.supervisor = ProcessSupervisor(workspace, self)
        self.supervisor.server_ready.connect(self._connected)
        self.supervisor.status_changed.connect(self._process_status)
        self.supervisor.output.connect(self._log)
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self.supervisor.start()

    def _build_ui(self) -> None:
        toolbar = self.addToolBar("项目")
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

        self.project_list = QListWidget()
        self.project_list.setMinimumWidth(280)
        self.project_list.currentItemChanged.connect(self._project_selected)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("项目列表"))
        left_layout.addWidget(self.project_list)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.title = QLabel("等待本地服务…")
        self.title.setStyleSheet("font-size: 24px; font-weight: 600; color: #18324a")
        detail_layout.addWidget(self.title)
        form = QFormLayout()
        self.code_label = QLabel("—")
        self.fem_label = QLabel("—")
        self.h3d_label = QLabel("—")
        self.run_label = QLabel("—")
        for widget in (self.fem_label, self.h3d_label):
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            widget.setWordWrap(True)
        form.addRow("项目编号", self.code_label)
        form.addRow("FEM", self.fem_label)
        form.addRow("H3D", self.h3d_label)
        form.addRow("当前 Run", self.run_label)
        detail_layout.addLayout(form)

        controls = QHBoxLayout()
        for text, action in (("启动", "start"), ("暂停", "pause"), ("恢复", "resume"), ("取消", "cancel"), ("重试失败项", "retry-failed")):
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, value=action: self.control_run(value))
            controls.addWidget(button)
        controls.addStretch()
        detail_layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setFormat("总体进度 %p%")
        detail_layout.addWidget(self.progress)
        self.tasks = QTableWidget(0, 4)
        self.tasks.setHorizontalHeaderLabels(["任务", "状态", "阶段进度", "当前信息"])
        self.tasks.horizontalHeader().setStretchLastSection(True)
        self.tasks.setAlternatingRowColors(True)
        detail_layout.addWidget(self.tasks, 1)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        detail_layout.addWidget(self.log)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(detail)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.server_status = QLabel("Server: starting")
        self.worker_status = QLabel("Worker: waiting")
        self.hyperview_status = QLabel("HyperView: idle")
        self.statusBar().addPermanentWidget(self.server_status)
        self.statusBar().addPermanentWidget(self.worker_status)
        self.statusBar().addPermanentWidget(self.hyperview_status)

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
            self.worker_status.setText(f"Worker: {health['worker']}")
        except Exception as exc:
            self.statusBar().showMessage(f"刷新失败：{exc}", 4000)

    def _fill_projects(self, selected_id: str | None) -> None:
        if self.project_list.count() == len(self.projects) and all(self.project_list.item(i).data(Qt.ItemDataRole.UserRole) == project["id"] for i, project in enumerate(self.projects)):
            return
        self.project_list.blockSignals(True)
        self.project_list.clear()
        selected_row = 0
        for index, project in enumerate(self.projects):
            item = QListWidgetItem(f"{project['name']}\n{project.get('code') or '未编号'}  ·  {project['status']}")
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
            values = [task["task_type"], task["status"], f"{task['progress_current']}/{task['progress_total']}", task["progress_message"]]
            for column, value in enumerate(values):
                self.tasks.setItem(row, column, QTableWidgetItem(str(value)))
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
            QMessageBox.warning(self, "操作失败", str(exc))

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
