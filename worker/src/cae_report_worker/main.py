from __future__ import annotations

import argparse
import os

from .worker_app import WorkerApp


def main() -> None:
    parser = argparse.ArgumentParser(description="CAE Report worker")
    parser.add_argument("--server", default=os.environ.get("CAE_REPORT_SERVER_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--real-hyperview", action="store_true")
    args = parser.parse_args()
    worker = WorkerApp(args.server, fake_hyperview=not args.real_hyperview)
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        worker.close()


if __name__ == "__main__":
    main()

