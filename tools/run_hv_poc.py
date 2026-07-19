from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from cae_report_worker.hyperview.session_manager import HyperViewSessionManager

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HyperView 2019 protocol POC")
    parser.add_argument("--hyperview", type=Path, default=Path("C:/Program Files/Altair/2019/hw/bin/win64/hw.exe"))
    parser.add_argument("--h3d", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime" / "poc" / "result.json")
    args = parser.parse_args()
    manager = HyperViewSessionManager(ROOT / "runtime" / "hyperview", args.hyperview, ROOT / "hyperview" / "bootstrap.tcl")
    started = time.monotonic()
    session = manager.start("poc", args.h3d)
    result: dict[str, object] = {
        "session_id": session.session_id,
        "startup_seconds": round(time.monotonic() - started, 3),
        "capabilities": session.capabilities,
        "ping": session.request("session.ping", {"token": session.token}),
    }
    if args.h3d:
        result["open"] = session.request("source.open", {"path": str(args.h3d.resolve())})
        index = session.request("source.index")
        result["index"] = index
        for result_type in index.get("result_types", []):
            name = str(result_type.get("name", ""))
            if "stress" in name.lower():
                result["stress_max"] = session.request(
                    "result.query_max",
                    {
                        "subcase_id": "1",
                        "simulation_index": "0",
                        "data_type": name,
                        "component": "vonMises",
                        "count": "3",
                    },
                )
                break
        captures: dict[str, object] = {}
        view_apply: dict[str, object] = {}
        for view in ("isometric", "front", "right", "top"):
            view_apply[view] = session.request("view.apply", {"camera_preset": view})
            capture = args.output.parent / f"hyperview-poc-{view}.png"
            captures[view] = session.request(
                "capture.execute",
                {"path": str(capture.resolve()), "width": "1920", "height": "1080"},
            )
        result["captures"] = captures
        result["view_apply"] = view_apply
        result["view_state"] = session.request("view.read")
    session.stop()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

