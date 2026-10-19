from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from .process_job import ProcessJob


def use_fake_hyperview(*, frozen: bool) -> bool:
    default = "0" if frozen else "1"
    return os.environ.get("CAE_REPORT_FAKE_HV", default) == "1"


def worker_environment_values(
    *,
    server_url: str,
    fake_hyperview: bool,
    hyperview_executable: Path | None,
    worker_log_path: Path | None = None,
) -> dict[str, str]:
    values = {
        "CAE_REPORT_SERVER_URL": server_url,
        "CAE_REPORT_FAKE_HV": "1" if fake_hyperview else "0",
    }
    if hyperview_executable is not None:
        values["CAE_REPORT_HYPERVIEW_EXE"] = str(hyperview_executable.resolve())
    if worker_log_path is not None:
        values["CAE_REPORT_WORKER_LOG"] = str(worker_log_path.resolve())
    return values


def worker_restart_delay(*, attempt: int, stopping: bool) -> int | None:
    if stopping or attempt >= 5:
        return None
    return min(30_000, 1000 * (2**attempt))


class ProcessSupervisor(QObject):
    server_ready = Signal(str)
    status_changed = Signal(str, str)
    output = Signal(str)

    def __init__(
        self,
        workspace: Path,
        parent: QObject | None = None,
        *,
        hyperview_executable: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.hyperview_executable = hyperview_executable
        self._stopping = False
        self._worker_restart_attempts = 0
        self.server = QProcess(self)
        self.worker = QProcess(self)
        self.server.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.worker.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.server.readyReadStandardOutput.connect(self._server_output)
        self.worker.readyReadStandardOutput.connect(self._worker_output)
        self.server.finished.connect(lambda: self.status_changed.emit("Server", "stopped"))
        self.worker.finished.connect(self._worker_finished)
        self.server.started.connect(lambda: self._assign_to_job("Server", self.server))
        self.worker.started.connect(self._worker_started)
        self.process_job = ProcessJob()
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
        if (
            self._stopping
            or self.worker.state() != QProcess.ProcessState.NotRunning
            or self.server.state() != QProcess.ProcessState.Running
        ):
            return
        frozen = bool(getattr(sys, "frozen", False))
        fake_hyperview = use_fake_hyperview(frozen=frozen)
        environment = QProcessEnvironment.systemEnvironment()
        for name, value in worker_environment_values(
            server_url=self.server_url,
            fake_hyperview=fake_hyperview,
            hyperview_executable=self.hyperview_executable,
            worker_log_path=self.workspace / "app" / "logs" / "worker.jsonl",
        ).items():
            environment.insert(name, value)
        self.worker.setProcessEnvironment(environment)
        mode_argument = "--fake-hyperview" if fake_hyperview else "--real-hyperview"
        if frozen:
            package_root = Path(sys.executable).resolve().parent
            worker_program = package_root / "CAEReportWorker" / "CAEReportWorker.exe"
            self.worker.setProgram(str(worker_program))
            self.worker.setArguments(["--server", self.server_url, mode_argument])
        else:
            self.worker.setProgram(sys.executable)
            self.worker.setArguments(
                ["-m", "cae_report_worker.main", "--server", self.server_url, mode_argument]
            )
        self.worker.start()
        self.status_changed.emit("Worker", "starting")

    def _worker_started(self) -> None:
        self._assign_to_job("Worker", self.worker)
        QTimer.singleShot(60_000, self._reset_worker_restart_attempts)

    def _reset_worker_restart_attempts(self) -> None:
        if self.worker.state() == QProcess.ProcessState.Running:
            self._worker_restart_attempts = 0

    def _worker_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self.status_changed.emit("Worker", "stopped")
        delay = worker_restart_delay(
            attempt=self._worker_restart_attempts,
            stopping=self._stopping,
        )
        if delay is None:
            if not self._stopping:
                self.output.emit(f"Worker 异常退出（代码 {exit_code}），自动重启次数已用尽。")
            return
        self._worker_restart_attempts += 1
        self.output.emit(
            f"Worker 异常退出（代码 {exit_code}），将在 {delay / 1000:g} 秒后自动重启。"
        )
        self.status_changed.emit("Worker", "restarting")
        QTimer.singleShot(delay, self._start_worker)

    def _worker_output(self) -> None:
        text = bytes(self.worker.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.output.emit(text)
        self.status_changed.emit("Worker", "ready" if self.worker.state() == QProcess.ProcessState.Running else "stopped")

    def _assign_to_job(self, name: str, process: QProcess) -> None:
        try:
            self.process_job.assign(process.processId())
        except OSError as exc:
            self.output.emit(f"{name} 进程树托管失败：{exc}")
            process.kill()

    def stop(self) -> None:
        self._stopping = True
        try:
            for process in (self.worker, self.server):
                if process.state() != QProcess.ProcessState.NotRunning:
                    process.terminate()
                    if not process.waitForFinished(5000):
                        process.kill()
        finally:
            self.process_job.close()
