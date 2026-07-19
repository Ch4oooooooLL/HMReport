from __future__ import annotations

import ctypes
import json
import os
import secrets
import socket
import subprocess
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .protocol import ALLOWED_COMMANDS, ProtocolError


@dataclass(slots=True)
class HyperViewSession:
    session_id: str
    token: str
    process: subprocess.Popen[str]
    connection: socket.socket
    reader: Any
    capabilities: list[str]
    context_path: Path

    def request(self, command: str, payload: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
        if command not in ALLOWED_COMMANDS:
            raise ProtocolError(f"command not allowed: {command}")
        request_id = uuid.uuid4().hex
        message = {"id": request_id, "command": command, "payload": payload or {}}
        self.connection.sendall((json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        self.connection.settimeout(timeout)
        raw = self.reader.readline()
        if not raw:
            raise ProtocolError("HyperView Tcl disconnected")
        try:
            response = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"HV_PROTOCOL_INVALID_JSON: {raw!r}") from exc
        if response.get("id") != request_id:
            raise ProtocolError("response id mismatch")
        if not response.get("success"):
            error = response.get("error", {})
            raise ProtocolError(f"{error.get('code')}: {error.get('message')}")
        return dict(response.get("result", {}))

    def stop(self) -> None:
        with suppress(Exception):
            self.request("session.shutdown", timeout=5)
        try:
            self.connection.close()
        finally:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()

    def bring_to_front(self) -> bool:
        if os.name != "nt" or self.process.poll() is not None:
            return False

        user32 = ctypes.windll.user32
        target_pid = self.process.pid
        found: list[int] = []
        enum_callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def collect_window(window: int, _: int) -> bool:
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
            if process_id.value == target_pid and user32.IsWindowVisible(window):
                found.append(window)
                return False
            return True

        callback = enum_callback(collect_window)
        user32.EnumWindows(callback, 0)
        if not found:
            return False
        window = found[0]
        user32.ShowWindow(window, 9)  # SW_RESTORE
        return bool(user32.SetForegroundWindow(window))


class HyperViewSessionManager:
    def __init__(
        self,
        runtime_dir: Path,
        hyperview_exe: Path,
        bootstrap_tcl: Path,
        *,
        background: bool = True,
    ) -> None:
        self.runtime_dir = runtime_dir
        self.hyperview_exe = hyperview_exe
        self.bootstrap_tcl = bootstrap_tcl
        self.background = background

    def start(self, run_id: str, h3d_path: Path | None = None, timeout: float = 45.0) -> HyperViewSession:
        if not self.hyperview_exe.is_file():
            raise FileNotFoundError(f"HV_START_FAILED: {self.hyperview_exe}")
        session_id = f"hvs_{uuid.uuid4().hex}"
        token = secrets.token_urlsafe(32)
        session_dir = self.runtime_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=False)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(timeout)
            port = int(listener.getsockname()[1])
            context_path = session_dir / "context.json"
            context = {
                "session_id": session_id,
                "run_id": run_id,
                "h3d_path": str(h3d_path.resolve()) if h3d_path else "",
                "worker_host": "127.0.0.1",
                "worker_port": port,
                "auth_token": token,
                "protocol_version": "1.0",
            }
            context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
            environment = os.environ.copy()
            # HyperView 2019/Tcl decodes Windows environment-variable values
            # with the legacy system code page. Passing an absolute path that
            # contains a Chinese project name therefore produces mojibake.
            # The process already starts in session_dir, so an ASCII relative
            # filename is both sufficient and encoding-safe.
            environment["CAE_REPORT_HV_CONTEXT"] = context_path.name
            command = [str(self.hyperview_exe)]
            if self.background:
                command.append("-b")
            command.extend(
                ["/clientconfig", "hwpost.dat", "-tcl", str(self.bootstrap_tcl)]
            )
            process = subprocess.Popen(command, env=environment, cwd=session_dir, text=True)
            try:
                connection, _ = listener.accept()
            except Exception:
                process.terminate()
                raise
        reader = connection.makefile("r", encoding="utf-8", newline="\n")
        connection.settimeout(timeout)
        raw = reader.readline()
        if not raw:
            process.terminate()
            raise ProtocolError("HV_CONNECT_TIMEOUT: no handshake")
        hello = json.loads(raw)
        if hello.get("type") != "handshake" or hello.get("token") != token or hello.get("session_id") != session_id:
            process.terminate()
            raise ProtocolError("HV_HANDSHAKE_FAILED")
        session = HyperViewSession(session_id, token, process, connection, reader, list(hello.get("capabilities", [])), context_path)
        pong = session.request("session.ping", {"token": token})
        if pong.get("status") != "ready":
            session.stop()
            raise ProtocolError("HV_START_FAILED: ping")
        return session
