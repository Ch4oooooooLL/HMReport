from __future__ import annotations

from pathlib import Path

from cae_report_worker.fem import FemParser


def test_parser_builds_v1_summaries(source_files: tuple[Path, Path]) -> None:
    fem, _ = source_files
    model = FemParser().parse(fem)
    summary = model.model_summary()
    mesh = model.mesh_summary()
    material = model.material_property_summary()
    boundary = model.boundary_summary()
    assert summary["node_count"] == 4
    assert summary["element_count"] == 1
    assert summary["bounding_box"] == {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 0.0]}
    assert summary["components"][0]["name"] == "FRAME_LEFT"
    assert mesh["element_types"] == {"CQUAD4": 1}
    assert mesh["average_edge_length"] == 10.0
    assert material["properties"][0]["thickness"] == 1.2
    assert material["materials"][0]["E"] == 210000.0
    assert len(boundary["constraints"]) == 1
    assert len(boundary["loads"]) == 1
    assert len(boundary["connections"]) == 1
    assert model.subcases[0]["references"]["SPC"] == "100"


def test_parser_follows_include(tmp_path: Path) -> None:
    include = tmp_path / "part.inc"
    include.write_text("GRID,9,,1.,2.,3.\n", encoding="utf-8")
    root = tmp_path / "root.fem"
    root.write_text("BEGIN BULK\nINCLUDE 'part.inc'\nENDDATA\n", encoding="utf-8")
    model = FemParser().parse(root)
    assert model.nodes[9] == (1.0, 2.0, 3.0)
    assert model.include_files == [str(include.resolve())]


def test_parser_follows_nested_includes_from_head_file(tmp_path: Path) -> None:
    parts = tmp_path / "parts"
    parts.mkdir()
    nodes = parts / "nodes.fem"
    nodes.write_text("GRID,9,,1.,2.,3.\n", encoding="utf-8")
    assembly = tmp_path / "assembly.inc"
    assembly.write_text('INCLUDE = "parts/nodes.fem"\n', encoding="utf-8")
    head = tmp_path / "head.fem"
    head.write_text("BEGIN BULK\nINCLUDE 'assembly.inc'\nENDDATA\n", encoding="utf-8")

    model = FemParser().parse(head)

    assert model.nodes[9] == (1.0, 2.0, 3.0)
    assert model.include_files == [str(assembly.resolve()), str(nodes.resolve())]


def test_boundary_summary_accepts_inertia_relief_without_constraints(tmp_path: Path) -> None:
    fem = tmp_path / "inertia_relief.fem"
    fem.write_text(
        "SOL 101\nCEND\nBEGIN BULK\nPARAM,INREL,-2\nGRAV,10,0,9810.,0.,0.,-1.\nENDDATA\n",
        encoding="utf-8",
    )

    boundary = FemParser().parse(fem).boundary_summary()

    assert boundary["constraints"] == []
    assert boundary["inertia_relief"] == {"enabled": True, "value": "-2"}

