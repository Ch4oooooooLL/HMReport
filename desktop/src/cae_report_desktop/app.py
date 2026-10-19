from __future__ import annotations

import os
import sys
from pathlib import Path

from cae_report_shared.json_logging import configure_json_logger
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .settings import DesktopSettings


def _application_icon_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources" / "app-icon.png"
    return Path(__file__).resolve().parents[3] / "resources" / "app-icon.png"


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CAE Result Analysis & Report Workbench")
    app.setOrganizationName("CAEReportWorkbench")
    icon = QIcon(str(_application_icon_path()))
    app.setWindowIcon(icon)
    workspace = Path(os.environ.get("CAE_REPORT_WORKSPACE", "C:/CAEReportWorkbench")).resolve()
    logger = configure_json_logger("cae_report.desktop", "desktop", workspace / "app" / "logs" / "desktop.jsonl")
    logger.info("Desktop starting", extra={"event": "desktop.start"})
    window = MainWindow(workspace, DesktopSettings())
    window.setWindowIcon(icon)
    window.show()
    return app.exec()
