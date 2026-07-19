from __future__ import annotations

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
        response = json.loads(raw)
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


class HyperViewSessionManager:
    def __init__(self, runtime_dir: Path, hyperview_exe: Path, bootstrap_tcl: Path) -> None:
        self.runtime_dir = runtime_dir
        self.hyperview_exe = hyperview_exe
        self.bootstrap_tcl = bootstrap_tcl

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
            environment["CAE_REPORT_HV_CONTEXT"] = str(context_path)
            command = [str(self.hyperview_exe), "/clientconfig", "hwpost.dat", "-tcl", str(self.bootstrap_tcl)]
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
