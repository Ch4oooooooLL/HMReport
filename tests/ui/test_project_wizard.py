from __future__ import annotations

from pathlib import Path

from cae_report_desktop.dialogs.new_project import NewProjectWizard


def test_project_wizard_builds_server_payload(qtbot: object, source_files: tuple[Path, Path], tmp_path: Path) -> None:
    fem, h3d = source_files
    wizard = NewProjectWizard(tmp_path / "projects")
    # pytest-qt owns the widget for deterministic cleanup.
    qtbot.addWidget(wizard)  # type: ignore[attr-defined]
    wizard.name_edit.setText("UI 创建项目")
    wizard.code_edit.setText("UI-001")
    wizard.fem_edit.setText(str(fem))
    wizard.h3d_edit.setText(str(h3d))
    payload = wizard.payload()
    assert payload["name"] == "UI 创建项目"
    assert payload["fem_path"] == str(fem.resolve())
    assert payload["h3d_path"] == str(h3d.resolve())
    assert "result.stress_hotspots" in payload["task_types"]

