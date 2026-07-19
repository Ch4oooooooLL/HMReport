from __future__ import annotations

import argparse
import json
import socketserver
import threading
from pathlib import Path
from typing import Any

from cae_report_worker.hyperview.fake_adapter import FakeHyperViewAdapter
from cae_report_worker.hyperview.protocol import ALLOWED_COMMANDS


class FakeState:
    def __init__(self, token: str) -> None:
        self.token = token
        self.adapter = FakeHyperViewAdapter()
        self.shutdown = threading.Event()


class Handler(socketserver.StreamRequestHandler):
    server: FakeServer

    def handle(self) -> None:
        while not self.server.state.shutdown.is_set():
            raw = self.rfile.readline(1024 * 1024 + 1)
            if not raw:
                break
            if len(raw) > 1024 * 1024:
                break
            try:
                request = json.loads(raw.decode("utf-8"))
                response = self.dispatch(request)
            except Exception as exc:
                response = {"id": None, "success": False, "error": {"code": "HV_COMMAND_FAILED", "message": str(exc), "details": {}}}
            self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))
            self.wfile.flush()

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        command = request.get("command")
        payload = request.get("payload", {})
        if command not in ALLOWED_COMMANDS:
            return {"id": request_id, "success": False, "error": {"code": "COMMAND_NOT_ALLOWED", "message": str(command), "details": {}}}
        if command == "session.ping":
            if payload.get("token") != self.server.state.token:
                return {"id": request_id, "success": False, "error": {"code": "AUTH_FAILED", "message": "invalid token", "details": {}}}
            result: dict[str, Any] = {"status": "ready", "version": "FakeHyperView/1.0"}
        elif command == "session.capabilities":
            result = {"protocol_version": "1.0", "capabilities": sorted(ALLOWED_COMMANDS), "partial": False}
        elif command == "source.open":
            result = self.server.state.adapter.open_source(Path(payload["path"]), str(payload.get("fingerprint", "")))
        elif command == "source.status":
            result = {"status": "ready" if self.server.state.adapter.source else "empty"}
        elif command == "source.index":
            result = self.server.state.adapter.index()
        elif command in {"view.apply", "view.restore"}:
            result = self.server.state.adapter.apply_view(payload["view_state"])
        elif command == "view.read":
            result = self.server.state.adapter.read_view()
        elif command == "capture.execute":
            result = {"status": "captured", "path": payload.get("path"), "view_state": self.server.state.adapter.read_view()}
        elif command == "session.shutdown":
            result = {"status": "stopping"}
            self.server.state.shutdown.set()
        else:
            result = {}
        return {"id": request_id, "success": True, "result": result}


class FakeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: FakeState) -> None:
        super().__init__(address, Handler)
        self.state = state


def main() -> None:
    parser = argparse.ArgumentParser(description="Fake HyperView JSONL protocol server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", default="development-token")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("Fake HyperView only listens on loopback")
    state = FakeState(args.token)
    with FakeServer((args.host, args.port), state) as server:
        print(f"FAKE_HYPERVIEW_ADDRESS={server.server_address[0]}:{server.server_address[1]}", flush=True)
        while not state.shutdown.is_set():
            server.handle_request()


if __name__ == "__main__":
    main()

