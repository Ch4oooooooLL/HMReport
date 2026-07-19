from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app, find_free_port
from .settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="CAE Report local application server")
    parser.add_argument("--workspace", type=Path, default=Path(os.environ.get("CAE_REPORT_WORKSPACE", "C:/CAEReportWorkbench")))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CAE_REPORT_PORT", "8765")))
    parser.add_argument("--dynamic-port", action="store_true")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("server may only listen on loopback")
    port = find_free_port() if args.dynamic_port else args.port
    settings = Settings(args.workspace.resolve(), args.host, port)
    app = create_app(settings)
    print(f"CAE_REPORT_SERVER_URL=http://{args.host}:{port}", flush=True)
    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()

