from __future__ import annotations

import argparse
import os
from collections.abc import Mapping

from .worker_app import WorkerApp


def resolve_fake_hyperview(
    *,
    real_requested: bool,
    fake_requested: bool,
    environment: Mapping[str, str],
) -> bool:
    if real_requested:
        return False
    if fake_requested:
        return True
    return environment.get("CAE_REPORT_FAKE_HV", "0") == "1"


def main() -> None:
    parser = argparse.ArgumentParser(description="CAE Report worker")
    parser.add_argument("--server", default=os.environ.get("CAE_REPORT_SERVER_URL", "http://127.0.0.1:8765"))
    hyperview_mode = parser.add_mutually_exclusive_group()
    hyperview_mode.add_argument("--real-hyperview", action="store_true")
    hyperview_mode.add_argument("--fake-hyperview", action="store_true")
    args = parser.parse_args()
    fake_hyperview = resolve_fake_hyperview(
        real_requested=args.real_hyperview,
        fake_requested=args.fake_hyperview,
        environment=os.environ,
    )
    worker = WorkerApp(args.server, fake_hyperview=fake_hyperview)
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        worker.close()


if __name__ == "__main__":
    main()

