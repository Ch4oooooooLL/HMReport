from __future__ import annotations

import json
from pathlib import Path

from cae_report_worker.fem import FemParser
from generate_optistruct_feature_model import (
    REQUIRED_CONNECTION_CARDS,
    REQUIRED_CONSTRAINT_CARDS,
    REQUIRED_ELEMENT_CARDS,
    REQUIRED_LOAD_CARDS,
    REQUIRED_MATERIAL_CARDS,
    REQUIRED_PROPERTY_CARDS,
    generate_model,
)


def test_generated_model_covers_parser_and_report_features(tmp_path: Path) -> None:
    fem = tmp_path / "feature_model.fem"
    generated_manifest = generate_model(fem)
    stored_manifest = json.loads(fem.with_name("feature_model.manifest.json").read_text("utf-8"))
    model = FemParser().parse(fem)

    assert stored_manifest == generated_manifest
    assert set(model.element_counts) == REQUIRED_ELEMENT_CARDS
    assert {item["type"] for item in model.properties.values()} == REQUIRED_PROPERTY_CARDS
    assert {item["type"] for item in model.materials.values()} == REQUIRED_MATERIAL_CARDS
    assert {item["type"] for item in model.loads} == REQUIRED_LOAD_CARDS
    assert {item["type"] for item in model.constraints} == REQUIRED_CONSTRAINT_CARDS
    assert {item["type"] for item in model.connections} == REQUIRED_CONNECTION_CARDS

    expected = generated_manifest["expected_counts"]
    assert isinstance(expected, dict)
    assert len(model.nodes) == expected["nodes"]
    assert model.element_count == expected["elements"]
    assert len(model.properties) == expected["properties"]
    assert len(model.materials) == expected["materials"]
    assert len(model.subcases) == expected["subcases"] == 6

    summary = model.model_summary()
    material_summary = model.material_property_summary()
    assert summary["component_count"] == expected["components"]
    assert summary["element_dimensions"] == {"1": 3, "2": 19, "3": 3}
    assert summary["unreferenced"] == {"materials": [99], "properties": [199]}
    assert material_summary["missing_material_properties"] == []
    assert {item["name"] for item in summary["components"]} >= {
        "STEEL_SHELL_MIXED_MESH",
        "CARBON_COMPOSITE_PANEL",
        "RBE2_LOAD_PATCH",
        "RBE3_LOAD_PATCH",
    }

    subcases = {item["name"]: item["references"] for item in model.subcases}
    assert subcases["FULL_LOAD_STATIC"]["LOAD"] == "9101"
    assert subcases["NORMAL_MODES"]["METHOD"] == "9301"
    assert subcases["NONLINEAR_STATIC"]["NLPARM"] == "9601"
    assert subcases["HARMONIC_SWEEP"]["DLOAD"] == "9503"
    assert subcases["HARMONIC_SWEEP"]["FREQUENCY"] == "9401"


def test_generated_split_model_exercises_include_parser(tmp_path: Path) -> None:
    fem = tmp_path / "feature_model_split.fem"
    manifest = generate_model(fem, split_includes=True)
    model = FemParser().parse(fem)

    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, dict)
    include_names = artifacts["includes"]
    assert isinstance(include_names, list)
    include_path = tmp_path / str(include_names[0])
    assert include_path.is_file()
    assert model.include_files == [str(include_path.resolve())]
    assert set(model.element_counts) == REQUIRED_ELEMENT_CARDS
    assert len(model.subcases) == 6
