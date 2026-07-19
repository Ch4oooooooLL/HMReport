from __future__ import annotations

import threading

import pytest

from cae_report_worker.hyperview.protocol import JsonLineClient, ProtocolError
from fake_hyperview.main import FakeServer, FakeState


def test_fake_hyperview_handshake_and_whitelist(source_files: tuple[object, object]) -> None:
    _, h3d = source_files
    state = FakeState("secret")
    server = FakeServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = JsonLineClient("127.0.0.1", server.server_address[1], "secret")
    try:
        assert client.connect()["status"] == "ready"
        assert "source.open" in client.request("session.capabilities")["capabilities"]
        client.request("source.open", {"path": str(h3d), "fingerprint": "fixture"})
        index = client.request("source.index")
        assert len(index["subcases"]) == 2
        with pytest.raises(ProtocolError, match="not allowed"):
            client.request("tcl.eval", {})
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

