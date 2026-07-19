from __future__ import annotations

from pathlib import Path

from cae_report_server.services import expand_tasks, file_fingerprint


def test_full_fingerprint_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "model.fem"
    path.write_bytes(b"GRID,1,,0.,0.,0.\n")
    first = file_fingerprint(path)
    second = file_fingerprint(path)
    assert first == second
    assert first[0] == "sha256"


def test_dag_adds_dependencies() -> None:
    expanded = expand_tasks(["result.stress_hotspots"])
    assert expanded == ["h3d.result_index", "result.stress_hotspots"]

