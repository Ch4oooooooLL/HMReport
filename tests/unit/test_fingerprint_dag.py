from __future__ import annotations

from pathlib import Path

from cae_report_server.services import expand_tasks, file_fingerprint, verify_source


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


def test_fem_fingerprint_covers_nested_include_files(tmp_path: Path) -> None:
    parts = tmp_path / "parts"
    parts.mkdir()
    nested = parts / "nodes.inc"
    nested.write_text("GRID,1,,0.,0.,0.\n", encoding="utf-8")
    assembly = tmp_path / "assembly.inc"
    assembly.write_text("INCLUDE 'parts/nodes.inc'\n", encoding="utf-8")
    head = tmp_path / "model.fem"
    head.write_text("BEGIN BULK\nINCLUDE 'assembly.inc'\nENDDATA\n", encoding="utf-8")

    first = verify_source(head, "fem")
    nested.write_text("GRID,1,,1.,0.,0.\n", encoding="utf-8")
    second = verify_source(head, "fem")

    assert first["availability"] == "available"
    assert first["fingerprint_type"] == "fem-tree-sha256"
    assert first["include_files"] == [str(assembly.resolve()), str(nested.resolve())]
    assert first["fingerprint"] != second["fingerprint"]


def test_fem_source_is_missing_when_an_include_is_missing(tmp_path: Path) -> None:
    head = tmp_path / "model.fem"
    head.write_text("INCLUDE 'missing.inc'\n", encoding="utf-8")

    check = verify_source(head, "fem")

    assert check["availability"] == "missing"
    assert check["error"] == "FEM_INCLUDE_MISSING"
    assert check["missing_includes"] == [str((tmp_path / "missing.inc").resolve())]

