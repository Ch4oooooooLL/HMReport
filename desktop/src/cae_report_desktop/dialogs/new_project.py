from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from cae_report_server.schemas import TASK_TYPES


class NewProjectWizard(QWizard):
    def __init__(self, default_workspace: Path, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建 CAE 分析项目")
        self.setMinimumSize(720, 520)
        self.default_workspace = default_workspace
        self.name_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.workspace_edit = QLineEdit(str(default_workspace))
        self.fem_edit = QLineEdit()
        self.h3d_edit = QLineEdit()
        self.solver_combo = QComboBox()
        self.solver_combo.addItems(["optistruct", "nastran"])
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["mm-N-MPa", "m-N-Pa", "inch-lbf-psi"])
        self.task_checks: dict[str, QCheckBox] = {}
        self.addPage(self._basic_page())
        self.addPage(self._source_page())
        self.addPage(self._task_page())
        self.addPage(self._summary_page())

    def _basic_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("基本信息")
        layout = QFormLayout(page)
        layout.addRow("项目名称 *", self.name_edit)
        layout.addRow("项目编号", self.code_edit)
        layout.addRow("求解器", self.solver_combo)
        layout.addRow("单位制", self.unit_combo)
        layout.addRow("项目根目录 *", self._path_row(self.workspace_edit, True, "选择项目根目录"))
        page.registerField("project_name*", self.name_edit)
        page.registerField("workspace*", self.workspace_edit)
        return page

    def _source_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("外部输入文件")
        page.setSubTitle("只保存绝对路径和指纹，不复制或修改 FEM/H3D。")
        layout = QFormLayout(page)
        layout.addRow("FEM *", self._path_row(self.fem_edit, False, "选择 FEM", "FEM (*.fem *.bdf *.dat *.nas)"))
        layout.addRow("H3D *", self._path_row(self.h3d_edit, False, "选择 H3D", "H3D (*.h3d)"))
        page.registerField("fem*", self.fem_edit)
        page.registerField("h3d*", self.h3d_edit)
        return page

    def _task_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("任务类型")
        page.setSubTitle("选择高层工程任务，依赖项将自动补齐。")
        layout = QVBoxLayout(page)
        labels = {
            "fem.model_summary": "模型信息",
            "fem.mesh_summary": "网格统计",
            "fem.material_property": "材料与属性",
            "fem.boundary_conditions": "边界条件",
            "fem.subcases": "子工况",
            "h3d.result_index": "H3D 结果索引",
            "result.stress_hotspots": "应力热点",
            "result.displacement_hotspots": "位移热点",
            "capture.standard_views": "标准视图",
            "report.prepare": "报告数据",
        }
        for task_type in TASK_TYPES:
            check = QCheckBox(f"{labels[task_type]}  ·  {task_type}")
            check.setChecked(True)
            self.task_checks[task_type] = check
            layout.addWidget(check)
        layout.addStretch()
        return page

    def _summary_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("创建")
        layout = QVBoxLayout(page)
        label = QLabel("完成后将创建项目目录和 Draft Run。原始 FEM/H3D 保持在原位置。")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label)
        return page

    def _path_row(self, edit: QLineEdit, directory: bool, title: str, file_filter: str = "") -> Any:
        widget = QHBoxLayout()
        button = QPushButton("浏览…")

        def choose() -> None:
            if directory:
                value = QFileDialog.getExistingDirectory(self, title, edit.text())
            else:
                value, _ = QFileDialog.getOpenFileName(self, title, edit.text(), file_filter)
            if value:
                edit.setText(value)

        button.clicked.connect(choose)
        widget.addWidget(edit)
        widget.addWidget(button)
        return widget

    def accept(self) -> None:
        if not Path(self.fem_edit.text()).is_file() or not Path(self.h3d_edit.text()).is_file():
            QMessageBox.warning(self, "文件无效", "请选择存在且可读的 FEM 和 H3D 文件。")
            return
        if not any(check.isChecked() for check in self.task_checks.values()):
            QMessageBox.warning(self, "未选择任务", "请至少选择一个任务。")
            return
        super().accept()

    def payload(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "code": self.code_edit.text().strip(),
            "workspace_path": str(Path(self.workspace_edit.text()).resolve()),
            "solver": self.solver_combo.currentText(),
            "unit_system": self.unit_combo.currentText(),
            "fem_path": str(Path(self.fem_edit.text()).resolve()),
            "h3d_path": str(Path(self.h3d_edit.text()).resolve()),
            "task_types": [name for name, check in self.task_checks.items() if check.isChecked()],
        }

