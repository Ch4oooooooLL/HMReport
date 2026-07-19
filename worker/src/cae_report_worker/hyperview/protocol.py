from __future__ import annotations

import json
import socket
import uuid
from dataclasses import dataclass
from typing import Any


class ProtocolError(RuntimeError):
    pass


ALLOWED_COMMANDS = {
    "session.ping",
    "session.capabilities",
    "source.open",
    "source.status",
    "source.index",
    "view.apply",
    "view.read",
    "capture.execute",
    "view.restore",
    "session.shutdown",
}


@dataclass(slots=True)
class JsonLineClient:
    host: str
    port: int
    token: str
    timeout: float = 15.0
    _socket: socket.socket | None = None
    _reader: Any = None

    def connect(self) -> dict[str, Any]:
        self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._reader = self._socket.makefile("r", encoding="utf-8", newline="\n")
        response = self.request("session.ping", {"token": self.token})
        return response

    def request(self, command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if command not in ALLOWED_COMMANDS:
            raise ProtocolError(f"command not allowed: {command}")
        if self._socket is None or self._reader is None:
            raise ProtocolError("not connected")
        request_id = uuid.uuid4().hex
        message = {"id": request_id, "command": command, "payload": payload or {}}
        encoded = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(encoded) > 1024 * 1024:
            raise ProtocolError("message too large")
        self._socket.sendall(encoded)
        self._socket.settimeout(self.timeout)
        line = self._reader.readline()
        if not line:
            raise ProtocolError("peer closed connection")
        response = json.loads(line)
        if response.get("id") != request_id:
            raise ProtocolError("response id mismatch")
        if not response.get("success"):
            error = response.get("error", {})
            raise ProtocolError(f"{error.get('code', 'HV_COMMAND_FAILED')}: {error.get('message', '')}")
        return dict(response.get("result", {}))

    def close(self) -> None:
        if self._reader:
            self._reader.close()
        if self._socket:
            self._socket.close()
        self._reader = None
        self._socket = None

