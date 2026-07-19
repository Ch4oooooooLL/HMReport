from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_ELEMENT_CARDS = {
    "CBAR",
    "CBEAM",
    "CBUSH",
    "CHEXA",
    "CPENTA",
    "CQUAD4",
    "CTETRA",
    "CTRIA3",
}
REQUIRED_PROPERTY_CARDS = {"PBAR", "PBEAM", "PBUSH", "PCOMP", "PSHELL", "PSOLID"}
REQUIRED_MATERIAL_CARDS = {"MAT1", "MAT8"}
REQUIRED_LOAD_CARDS = {"DLOAD", "FORCE", "GRAV", "LOAD", "MOMENT"}
REQUIRED_CONSTRAINT_CARDS = {"MPC", "MPCADD", "SPC", "SPC1", "SPCADD"}
REQUIRED_CONNECTION_CARDS = {"CONM2", "RBE2", "RBE3"}


def _text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        text = f"{value:.12g}"
        if "." not in text and "e" not in text.lower():
            text += "."
        return text
    return str(value)


def free_card(name: str, *values: object | None) -> list[str]:
    """Format an OptiStruct free-field card with legal eight-data-field lines."""
    fields = [_text(value) for value in values]
    while fields and fields[-1] == "":
        fields.pop()
    if not fields:
        return [name]
    lines = [",".join([name, *fields[:8]])]
    for index in range(8, len(fields), 8):
        lines.append(",".join(["+", *fields[index : index + 8]]))
    return lines


def fixed_card(name: str, *values: object | None) -> list[str]:
    """Format one small fixed-field card; used to exercise the FEM parser."""
    fields = [_text(value) for value in values]
    while fields and fields[-1] == "":
        fields.pop()
    if len(fields) > 8:
        raise ValueError(f"fixed-field card {name} needs continuation")
    if len(name) > 8 or any(len(value) > 8 for value in fields):
        raise ValueError(f"fixed-field value does not fit card {name}")
    return [f"{name:<8}{''.join(f'{value:>8}' for value in fields)}"]


def large_card(name: str, *values: object | None) -> list[str]:
    """Format a large fixed-field card using four data fields per half-line."""
    fields = [_text(value) for value in values]
    while fields and fields[-1] == "":
        fields.pop()
    if len(name) > 7 or any(len(value) > 16 for value in fields):
        raise ValueError(f"large-field value does not fit card {name}")
    lines: list[str] = []
    for index in range(0, len(fields), 4):
        prefix = f"{name + '*':<8}" if index == 0 else f"{'*':<8}"
        lines.append(prefix + "".join(f"{value:>16}" for value in fields[index : index + 4]))
    return lines or [f"{name + '*':<8}"]


@dataclass(frozen=True, slots=True)
class Element:
    card: str
    property_id: int
    node_ids: tuple[int, ...]


@dataclass(slots=True)
class DeckBuilder:
    nodes: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    elements: dict[int, Element] = field(default_factory=dict)
    properties: dict[int, tuple[str, tuple[int, ...]]] = field(default_factory=dict)
    materials: dict[int, str] = field(default_factory=dict)
    components: dict[int, str] = field(default_factory=dict)
    sections: dict[str, list[str]] = field(
        default_factory=lambda: {
            "parameters": [],
            "materials": [],
            "properties": [],
            "nodes": [],
            "elements": [],
            "connections": [],
            "constraints": [],
            "loads": [],
            "dynamics": [],
        }
    )
    element_counts: Counter[str] = field(default_factory=Counter)
    connection_counts: Counter[str] = field(default_factory=Counter)
    constraint_counts: Counter[str] = field(default_factory=Counter)
    load_counts: Counter[str] = field(default_factory=Counter)
    referenced_load_nodes: set[int] = field(default_factory=set)
    referenced_constraint_nodes: set[int] = field(default_factory=set)
    next_node_id: int = 1
    next_element_id: int = 1001

    def add_lines(self, section: str, lines: Iterable[str]) -> None:
        self.sections[section].extend(lines)

    def add_node(
        self,
        xyz: tuple[float, float, float],
        *,
        card_format: str = "free",
    ) -> int:
        node_id = self.next_node_id
        self.next_node_id += 1
        self.nodes[node_id] = xyz
        values: tuple[object | None, ...] = (node_id, None, *xyz)
        if card_format == "fixed":
            lines = fixed_card("GRID", *values)
        elif card_format == "large":
            lines = large_card("GRID", *values)
        else:
            lines = free_card("GRID", *values)
        self.add_lines("nodes", lines)
        return node_id

    def reserve_element_id(self) -> int:
        element_id = self.next_element_id
        self.next_element_id += 1
        return element_id

    def add_element(
        self,
        card: str,
        property_id: int,
        node_ids: Sequence[int],
        *extra_fields: object | None,
    ) -> int:
        element_id = self.reserve_element_id()
        self.elements[element_id] = Element(card, property_id, tuple(node_ids))
        self.element_counts[card] += 1
        self.add_lines(
            "elements",
            free_card(card, element_id, property_id, *node_ids, *extra_fields),
        )
        return element_id

    def add_connection(self, card: str, *values: object | None) -> int:
        element_id = self.reserve_element_id()
        self.connection_counts[card] += 1
        self.add_lines("connections", free_card(card, element_id, *values))
        return element_id

    def add_material(self, material_id: int, card: str, *values: object | None) -> None:
        if material_id in self.materials:
            raise ValueError(f"duplicate material {material_id}")
        self.materials[material_id] = card
        self.add_lines("materials", free_card(card, material_id, *values))

    def add_property(
        self,
        property_id: int,
        component_name: str,
        card: str,
        material_ids: Sequence[int],
        *values: object | None,
    ) -> None:
        if property_id in self.properties:
            raise ValueError(f"duplicate property {property_id}")
        self.properties[property_id] = (card, tuple(material_ids))
        self.components[property_id] = component_name
        self.add_lines("properties", free_card(card, property_id, *values))

    def add_constraint(
        self,
        card: str,
        *values: object | None,
        node_ids: Iterable[int] = (),
    ) -> None:
        self.constraint_counts[card] += 1
        self.referenced_constraint_nodes.update(node_ids)
        self.add_lines("constraints", free_card(card, *values))

    def add_load(
        self,
        card: str,
        *values: object | None,
        node_ids: Iterable[int] = (),
    ) -> None:
        self.load_counts[card] += 1
        self.referenced_load_nodes.update(node_ids)
        self.add_lines("loads", free_card(card, *values))

    def validate(self) -> None:
        missing_nodes = {
            node_id
            for element in self.elements.values()
            for node_id in element.node_ids
            if node_id not in self.nodes
        }
        missing_nodes.update((self.referenced_load_nodes | self.referenced_constraint_nodes) - self.nodes.keys())
        if missing_nodes:
            raise ValueError(f"cards reference missing GRID IDs: {sorted(missing_nodes)}")

        missing_properties = {
            element.property_id
            for element in self.elements.values()
            if element.property_id not in self.properties
        }
        if missing_properties:
            raise ValueError(f"elements reference missing properties: {sorted(missing_properties)}")

        missing_materials = {
            material_id
            for _, material_ids in self.properties.values()
            for material_id in material_ids
            if material_id not in self.materials
        }
        if missing_materials:
            raise ValueError(f"properties reference missing materials: {sorted(missing_materials)}")

        coverage = {
            "elements": set(self.element_counts),
            "properties": {card for card, _ in self.properties.values()},
            "materials": set(self.materials.values()),
            "loads": set(self.load_counts),
            "constraints": set(self.constraint_counts),
            "connections": set(self.connection_counts),
        }
        required = {
            "elements": REQUIRED_ELEMENT_CARDS,
            "properties": REQUIRED_PROPERTY_CARDS,
            "materials": REQUIRED_MATERIAL_CARDS,
            "loads": REQUIRED_LOAD_CARDS,
            "constraints": REQUIRED_CONSTRAINT_CARDS,
            "connections": REQUIRED_CONNECTION_CARDS,
        }
        gaps = {name: sorted(cards - coverage[name]) for name, cards in required.items() if cards - coverage[name]}
        if gaps:
            raise ValueError(f"feature coverage is incomplete: {gaps}")


def _add_plate(
    deck: DeckBuilder,
    property_id: int,
    x_values: Sequence[float],
    y_values: Sequence[float],
    *,
    z: float = 0.0,
    split_cell: tuple[int, int] | None = None,
) -> list[list[int]]:
    grid: list[list[int]] = []
    for y_index, y_value in enumerate(y_values):
        row: list[int] = []
        for x_index, x_value in enumerate(x_values):
            card_format = "free"
            if not deck.nodes and x_index == 0 and y_index == 0:
                card_format = "fixed"
            elif len(deck.nodes) == 1:
                card_format = "large"
            row.append(deck.add_node((x_value, y_value, z), card_format=card_format))
        grid.append(row)

    for y_index in range(len(y_values) - 1):
        for x_index in range(len(x_values) - 1):
            n1 = grid[y_index][x_index]
            n2 = grid[y_index][x_index + 1]
            n3 = grid[y_index + 1][x_index + 1]
            n4 = grid[y_index + 1][x_index]
            if split_cell == (x_index, y_index):
                deck.add_element("CTRIA3", property_id, (n1, n2, n3))
                deck.add_element("CTRIA3", property_id, (n1, n3, n4))
            else:
                deck.add_element("CQUAD4", property_id, (n1, n2, n3, n4))
    return grid


def build_deck() -> tuple[list[str], DeckBuilder, dict[str, object]]:
    deck = DeckBuilder()

    deck.add_lines("parameters", free_card("PARAM", "AUTOSPC", "YES"))
    deck.add_lines("parameters", free_card("PARAM", "G", 0.04))

    deck.add_material(1, "MAT1", 210000.0, 80769.2308, 0.3, 7.85e-9, None, None, None, 450.0, 350.0, 260.0)
    deck.add_material(2, "MAT1", 70000.0, 26923.0769, 0.3, 2.70e-9, None, None, None, 310.0, 250.0, 180.0)
    deck.add_material(
        3,
        "MAT8",
        135000.0,
        9000.0,
        0.3,
        5000.0,
        3500.0,
        3500.0,
        1.60e-9,
        0.0,
        0.0,
        20.0,
        1500.0,
        1200.0,
        50.0,
        200.0,
        70.0,
    )
    deck.add_material(99, "MAT1", 1000.0, 384.6154, 0.3, 1.0e-9)

    deck.add_property(101, "STEEL_SHELL_MIXED_MESH", "PSHELL", (1,), 1, 1.5, 1)
    deck.add_property(
        102,
        "CARBON_COMPOSITE_PANEL",
        "PCOMP",
        (3,),
        None,
        0.0,
        70.0,
        None,
        None,
        None,
        None,
        3,
        0.25,
        0.0,
        "YES",
        3,
        0.25,
        45.0,
        "YES",
        3,
        0.25,
        -45.0,
        "YES",
        3,
        0.25,
        90.0,
        "YES",
    )
    deck.add_property(103, "ALUMINUM_HEXA_BLOCK", "PSOLID", (2,), 2)
    deck.add_property(104, "STEEL_TETRA_BRACKET", "PSOLID", (1,), 1)
    deck.add_property(105, "ALUMINUM_PENTA_WEDGE", "PSOLID", (2,), 2)
    deck.add_property(106, "STEEL_BAR", "PBAR", (1,), 1, 100.0, 833.333, 833.333, 1406.0)
    deck.add_property(107, "ALUMINUM_BEAM", "PBEAM", (2,), 2, 120.0, 1600.0, 900.0, 0.0, 300.0, 0.0)
    deck.add_property(108, "ELASTIC_BUSH_MOUNT", "PBUSH", (), "K", 1500.0, 1200.0, 1000.0, 120.0, 100.0, 80.0)
    deck.add_property(109, "RBE2_LOAD_PATCH", "PSHELL", (1,), 1, 1.2, 1)
    deck.add_property(110, "RBE3_LOAD_PATCH", "PSHELL", (2,), 2, 1.2, 2)
    deck.add_property(199, "UNUSED_DIAGNOSTIC_PROPERTY", "PSHELL", (1,), 1, 0.8, 1)

    steel = _add_plate(deck, 101, (0.0, 25.0, 60.0, 100.0), (0.0, 20.0, 60.0), split_cell=(2, 1))
    composite = _add_plate(deck, 102, (0.0, 50.0, 100.0), (100.0, 130.0, 160.0))
    rbe2_patch = _add_plate(deck, 109, (160.0, 200.0, 240.0), (0.0, 30.0, 60.0))
    rbe3_patch = _add_plate(deck, 110, (160.0, 200.0, 240.0), (100.0, 130.0, 160.0))

    hexa = [
        deck.add_node((x, y, z))
        for x, y, z in (
            (0.0, 220.0, 0.0),
            (40.0, 220.0, 0.0),
            (40.0, 260.0, 0.0),
            (0.0, 260.0, 0.0),
            (0.0, 220.0, 20.0),
            (40.0, 220.0, 20.0),
            (40.0, 260.0, 20.0),
            (0.0, 260.0, 20.0),
        )
    ]
    deck.add_element("CHEXA", 103, hexa)

    tetra = [
        deck.add_node(point)
        for point in (
            (140.0, 220.0, 0.0),
            (180.0, 220.0, 0.0),
            (140.0, 260.0, 0.0),
            (140.0, 220.0, 35.0),
        )
    ]
    deck.add_element("CTETRA", 104, tetra)

    penta = [
        deck.add_node(point)
        for point in (
            (70.0, 220.0, 0.0),
            (110.0, 220.0, 0.0),
            (70.0, 260.0, 0.0),
            (70.0, 220.0, 25.0),
            (110.0, 220.0, 25.0),
            (70.0, 260.0, 25.0),
        )
    ]
    deck.add_element("CPENTA", 105, penta)

    bar_root = deck.add_node((0.0, 330.0, 0.0))
    bar_tip = deck.add_node((100.0, 330.0, 0.0))
    deck.add_element("CBAR", 106, (bar_root, bar_tip), 0.0, 0.0, 1.0)

    beam_root = deck.add_node((0.0, 360.0, 0.0))
    beam_tip = deck.add_node((100.0, 360.0, 0.0))
    deck.add_element("CBEAM", 107, (beam_root, beam_tip), 0.0, 0.0, 1.0)

    bush_root = deck.add_node((0.0, 390.0, 0.0))
    bush_tip = deck.add_node((50.0, 390.0, 0.0))
    bush_orientation = deck.add_node((0.0, 390.0, 20.0))
    deck.add_element("CBUSH", 108, (bush_root, bush_tip), bush_orientation)
    deck.add_connection("CONM2", bush_tip, 0, 2.5e-3)

    rbe2_reference = deck.add_node((255.0, 30.0, 0.0))
    rbe2_dependents = [row[-1] for row in rbe2_patch]
    deck.add_connection("RBE2", rbe2_reference, 123456, *rbe2_dependents)

    rbe3_reference = deck.add_node((255.0, 130.0, 0.0))
    rbe3_independent = [node_id for row in rbe3_patch for node_id in row[1:]]
    deck.add_connection("RBE3", None, rbe3_reference, 123, 1.0, 123, *rbe3_independent)

    shell_supports = [row[0] for row in steel + composite + rbe2_patch + rbe3_patch]
    one_d_supports = [bar_root, beam_root, bush_root]
    solid_supports = [*hexa[:4], *tetra[:3], *penta[:3]]
    primary_support = shell_supports.pop(0)
    deck.add_constraint("SPC", 9000, primary_support, 123456, 0.0, node_ids=[primary_support])
    deck.add_constraint("SPC1", 9001, 123456, *shell_supports, *one_d_supports, node_ids=[*shell_supports, *one_d_supports])
    deck.add_constraint("SPC1", 9001, 123, *solid_supports, node_ids=solid_supports)
    deck.add_constraint("SPCADD", 9002, 9000, 9001)

    steel_right_bottom = steel[0][-1]
    steel_right_top = steel[-1][-1]
    deck.add_constraint("MPC", 9010, steel_right_bottom, 2, 1.0, steel_right_top, 2, -1.0, node_ids=[steel_right_bottom, steel_right_top])
    deck.add_constraint("MPC", 9011, steel_right_bottom, 3, 1.0, steel_right_top, 3, -1.0, node_ids=[steel_right_bottom, steel_right_top])
    deck.add_constraint("MPCADD", 9012, 9010, 9011)

    primary_force_nodes = [
        steel_right_top,
        composite[1][-1],
        hexa[6],
        tetra[3],
        penta[4],
        bar_tip,
        beam_tip,
        bush_tip,
        rbe2_reference,
        rbe3_reference,
    ]
    for index, node_id in enumerate(primary_force_nodes):
        magnitude = 120.0 + index * 35.0
        direction = (1.0, 0.25, -0.15) if index % 2 == 0 else (0.2, -0.3, -1.0)
        deck.add_load("FORCE", 9201, node_id, 0, magnitude, *direction, node_ids=[node_id])
    deck.add_load("MOMENT", 9202, beam_tip, 0, 25000.0, 0.0, 1.0, 0.0, node_ids=[beam_tip])
    deck.add_load("MOMENT", 9202, rbe2_reference, 0, 12000.0, 0.0, 0.0, 1.0, node_ids=[rbe2_reference])
    deck.add_load("GRAV", 9203, 0, 9810.0, 0.0, 0.0, -1.0)
    deck.add_load("LOAD", 9101, 1.0, 1.0, 9201, 1.0, 9202, 1.0, 9203)

    reverse_nodes = [steel[1][-1], composite[-1][-1], rbe3_reference]
    for node_id in reverse_nodes:
        deck.add_load("FORCE", 9204, node_id, 0, 300.0, -1.0, 0.35, 0.2, node_ids=[node_id])
    deck.add_load("MOMENT", 9205, bar_tip, 0, 8000.0, 0.0, 0.0, -1.0, node_ids=[bar_tip])
    deck.add_load("LOAD", 9102, 1.0, 1.0, 9204, 1.0, 9205)

    deck.add_lines("dynamics", free_card("EIGRL", 9301, 0.0, 1000.0, 12))
    deck.add_lines("dynamics", free_card("FREQ1", 9401, 5.0, 5.0, 20))
    deck.add_lines("dynamics", free_card("DAREA", 9500, bush_tip, 1, 1.0))
    deck.add_lines("dynamics", free_card("TABLED1", 9502))
    deck.add_lines("dynamics", free_card("+", 0.0, 0.0, 1.0, 1.0, "ENDT"))
    deck.add_lines("dynamics", free_card("RLOAD1", 9501, 9500, None, None, 9502, None, "LOAD"))
    deck.add_load("DLOAD", 9503, 1.0, 1.0, 9501)
    deck.add_lines("dynamics", free_card("NLPARM", 9601, 10))

    deck.validate()

    case_control = [
        "$ Generated by tools/generate_optistruct_feature_model.py",
        "$ Units: mm, N, MPa, tonne, second",
        "TITLE = HMREPORT OPTISTRUCT FEATURE COVERAGE MODEL",
        "ECHO = NONE",
        "FORMAT,H3D",
        "DISPLACEMENT(H3D) = ALL",
        "VELOCITY(H3D) = ALL",
        "ACCELERATION(H3D) = ALL",
        "STRESS(H3D,CORNER) = ALL",
        "SUBCASE 1",
        "  LABEL = FULL_LOAD_STATIC",
        "  ANALYSIS = STATICS",
        "  SPC = 9002",
        "  MPC = 9012",
        "  LOAD = 9101",
        "SUBCASE 2",
        "  LABEL = REVERSE_LOAD_STATIC",
        "  ANALYSIS = STATICS",
        "  SPC = 9002",
        "  MPC = 9012",
        "  LOAD = 9102",
        "SUBCASE 3",
        "  LABEL = GRAVITY_ONLY_STATIC",
        "  ANALYSIS = STATICS",
        "  SPC = 9002",
        "  MPC = 9012",
        "  LOAD = 9203",
        "SUBCASE 4",
        "  LABEL = NORMAL_MODES",
        "  ANALYSIS = MODES",
        "  SPC = 9002",
        "  MPC = 9012",
        "  METHOD = 9301",
        "SUBCASE 5",
        "  LABEL = NONLINEAR_STATIC",
        "  ANALYSIS = NLSTAT",
        "  SPC = 9002",
        "  MPC = 9012",
        "  LOAD = 9101",
        "  NLPARM = 9601",
        "SUBCASE 6",
        "  LABEL = HARMONIC_SWEEP",
        "  ANALYSIS = MFREQ",
        "  SPC = 9002",
        "  MPC = 9012",
        "  METHOD = 9301",
        "  FREQUENCY = 9401",
        "  DLOAD = 9503",
        "BEGIN BULK",
    ]

    component_comments = [
        f'{"$HMNAME":<8}{"COMP":<16}{property_id:>8}"{name}"'
        for property_id, name in sorted(deck.components.items())
    ]
    bulk_lines = [
        *component_comments,
        "$ --- PARAMETERS ---",
        *deck.sections["parameters"],
        "$ --- MATERIALS ---",
        *deck.sections["materials"],
        "$ --- PROPERTIES ---",
        *deck.sections["properties"],
        "$ --- NODES ---",
        *deck.sections["nodes"],
        "$ --- STRUCTURAL ELEMENTS ---",
        *deck.sections["elements"],
        "$ --- CONNECTIONS AND MASS ---",
        *deck.sections["connections"],
        "$ --- CONSTRAINTS ---",
        *deck.sections["constraints"],
        "$ --- STATIC LOADS ---",
        *deck.sections["loads"],
        "$ --- MODAL, FREQUENCY, AND NONLINEAR CONTROLS ---",
        *deck.sections["dynamics"],
    ]

    used_properties = {element.property_id for element in deck.elements.values()}
    referenced_materials = {
        material_id
        for property_id in used_properties
        for material_id in deck.properties[property_id][1]
    }
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": "tools/generate_optistruct_feature_model.py",
        "solver": {
            "name": "OptiStruct",
            "compatibility_target": "2019+",
            "validated_with": "OptiStruct 2019 build 0960190med33190",
            "unit_system": "mm-N-MPa-tonne-s",
            "expected_result": "H3D plus standard OUT/STAT files",
        },
        "subcases": [
            {"id": 1, "label": "FULL_LOAD_STATIC", "analysis": "STATICS"},
            {"id": 2, "label": "REVERSE_LOAD_STATIC", "analysis": "STATICS"},
            {"id": 3, "label": "GRAVITY_ONLY_STATIC", "analysis": "STATICS"},
            {"id": 4, "label": "NORMAL_MODES", "analysis": "MODES"},
            {"id": 5, "label": "NONLINEAR_STATIC", "analysis": "NLSTAT"},
            {"id": 6, "label": "HARMONIC_SWEEP", "analysis": "MFREQ"},
        ],
        "coverage": {
            "element_cards": sorted(deck.element_counts),
            "property_cards": sorted({card for card, _ in deck.properties.values()}),
            "material_cards": sorted(set(deck.materials.values())),
            "load_cards": sorted(deck.load_counts),
            "constraint_cards": sorted(deck.constraint_counts),
            "connection_cards": sorted(deck.connection_counts),
            "input_formats": ["free-field", "small-fixed-field", "large-fixed-field", "continuation"],
            "workbench_features": [
                "model/component/property/material summaries",
                "1D/2D/3D mesh and mixed element statistics",
                "loads, constraints, rigid connections, and concentrated mass",
                "multiple static, modal, nonlinear, and frequency subcases",
                "stress, displacement, velocity, acceleration, modal, and frequency H3D results",
                "global/local/component hotspot and multi-view capture geometry",
            ],
        },
        "expected_counts": {
            "nodes": len(deck.nodes),
            "elements": sum(deck.element_counts.values()),
            "elements_by_card": dict(sorted(deck.element_counts.items())),
            "components": len(deck.components),
            "properties": len(deck.properties),
            "materials": len(deck.materials),
            "connections_by_card": dict(sorted(deck.connection_counts.items())),
            "constraints_by_card": dict(sorted(deck.constraint_counts.items())),
            "loads_by_card": dict(sorted(deck.load_counts.items())),
            "subcases": 6,
        },
        "components": [
            {"id": property_id, "name": name, "property_type": deck.properties[property_id][0]}
            for property_id, name in sorted(deck.components.items())
        ],
        "intentional_diagnostics": {
            "unreferenced_properties": sorted(set(deck.properties) - used_properties),
            "unreferenced_materials": sorted(set(deck.materials) - referenced_materials),
            "purpose": "Exercise workbench unreferenced-definition reporting without solver errors.",
        },
    }
    return [*case_control, *bulk_lines, "ENDDATA"], deck, manifest


def generate_model(output: Path, *, split_includes: bool = False) -> dict[str, object]:
    lines, _, manifest = build_deck()
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    include_paths: list[str] = []
    if split_includes:
        begin_index = lines.index("BEGIN BULK")
        bulk_lines = lines[begin_index + 1 : -1]
        include_path = output.with_name(f"{output.stem}_bulk.inc")
        include_path.write_text("\n".join([*bulk_lines, ""]), encoding="utf-8", newline="\n")
        root_lines = [*lines[: begin_index + 1], f"INCLUDE '{include_path.name}'", "ENDDATA"]
        output.write_text("\n".join([*root_lines, ""]), encoding="utf-8", newline="\n")
        include_paths.append(include_path.name)
    else:
        output.write_text("\n".join([*lines, ""]), encoding="utf-8", newline="\n")

    manifest["artifacts"] = {
        "fem": output.name,
        "includes": include_paths,
        "manifest": f"{output.stem}.manifest.json",
    }
    manifest_path = output.with_name(f"{output.stem}.manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic OptiStruct model covering HMReport FEM/H3D features."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("examples/optistruct_feature_model/optistruct_feature_model.fem"),
        help="Root FEM path (default: examples/optistruct_feature_model/optistruct_feature_model.fem)",
    )
    parser.add_argument(
        "--split-includes",
        action="store_true",
        help="Move Bulk Data into a sibling .inc file to test recursive INCLUDE parsing.",
    )
    args = parser.parse_args()
    manifest = generate_model(args.output, split_includes=args.split_includes)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, dict)
    print(f"Generated {args.output.resolve()}")
    print(f"Manifest {args.output.resolve().with_name(str(artifacts['manifest']))}")
    expected_counts = manifest["expected_counts"]
    assert isinstance(expected_counts, dict)
    print(f"Subcases {expected_counts['subcases']}")


if __name__ == "__main__":
    main()
