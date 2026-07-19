from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


class ProcessSupervisor(QObject):
    server_ready = Signal(str)
    status_changed = Signal(str, str)
    output = Signal(str)

    def __init__(self, workspace: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.server = QProcess(self)
        self.worker = QProcess(self)
        self.server.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.worker.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.server.readyReadStandardOutput.connect(self._server_output)
        self.worker.readyReadStandardOutput.connect(self._worker_output)
        self.server.finished.connect(lambda: self.status_changed.emit("Server", "stopped"))
        self.worker.finished.connect(lambda: self.status_changed.emit("Worker", "stopped"))
        self.server_url = ""

    def start(self) -> None:
        if self.server.state() != QProcess.ProcessState.NotRunning:
            return
        self.workspace.mkdir(parents=True, exist_ok=True)
        if getattr(sys, "frozen", False):
            package_root = Path(sys.executable).resolve().parent
            server_program = package_root / "CAEReportServer" / "CAEReportServer.exe"
            self.server.setProgram(str(server_program))
            self.server.setArguments(["--workspace", str(self.workspace), "--dynamic-port"])
        else:
            self.server.setProgram(sys.executable)
            self.server.setArguments(["-m", "cae_report_server.main", "--workspace", str(self.workspace), "--dynamic-port"])
        self.server.start()
        self.status_changed.emit("Server", "starting")

    def _server_output(self) -> None:
        text = bytes(self.server.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.output.emit(text)
        match = re.search(r"CAE_REPORT_SERVER_URL=(http://[^\s]+)", text)
        if match and not self.server_url:
            self.server_url = match.group(1)
            self.status_changed.emit("Server", "ready")
            self.server_ready.emit(self.server_url)
            self._start_worker()

    def _start_worker(self) -> None:
        environment = self.worker.processEnvironment()
        environment.insert("CAE_REPORT_SERVER_URL", self.server_url)
        environment.insert("CAE_REPORT_FAKE_HV", os.environ.get("CAE_REPORT_FAKE_HV", "1"))
        self.worker.setProcessEnvironment(environment)
        if getattr(sys, "frozen", False):
            package_root = Path(sys.executable).resolve().parent
            worker_program = package_root / "CAEReportWorker" / "CAEReportWorker.exe"
            self.worker.setProgram(str(worker_program))
            self.worker.setArguments(["--server", self.server_url])
        else:
            self.worker.setProgram(sys.executable)
            self.worker.setArguments(["-m", "cae_report_worker.main", "--server", self.server_url])
        self.worker.start()
        self.status_changed.emit("Worker", "starting")

    def _worker_output(self) -> None:
        text = bytes(self.worker.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.output.emit(text)
        self.status_changed.emit("Worker", "ready" if self.worker.state() == QProcess.ProcessState.Running else "stopped")

    def stop(self) -> None:
        for process in (self.worker, self.server):
            if process.state() != QProcess.ProcessState.NotRunning:
                process.terminate()
                if not process.waitForFinished(5000):
                    process.kill()
