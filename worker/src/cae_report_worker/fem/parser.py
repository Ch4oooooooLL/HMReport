from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ELEMENT_CARDS: dict[str, int] = {
    "CBAR": 1,
    "CBEAM": 1,
    "CBUSH": 1,
    "CTRIA3": 2,
    "CQUAD4": 2,
    "CTETRA": 3,
    "CPENTA": 3,
    "CHEXA": 3,
}
PROPERTY_CARDS = {"PSHELL", "PCOMP", "PSOLID", "PBAR", "PBEAM", "PBUSH"}
MATERIAL_CARDS = {"MAT1", "MAT8"}
LOAD_CARDS = {"FORCE", "MOMENT", "GRAV", "LOAD", "DLOAD"}
CONSTRAINT_CARDS = {"SPC", "SPC1", "SPCADD", "MPC", "MPCADD"}
CONNECTION_CARDS = {"RBE2", "RBE3", "CONM2"}


def _number(value: str, default: float = 0.0) -> float:
    text = value.strip()
    if not text:
        return default
    normalized = re.sub(r"(?<=\d)([+-]\d+)$", r"E\1", text.replace("D", "E").replace("d", "e"))
    try:
        return float(normalized)
    except ValueError:
        return default


def _integer(value: str, default: int = 0) -> int:
    try:
        return int(float(value.strip()))
    except ValueError:
        return default


@dataclass(slots=True)
class SourceCard:
    name: str
    fields: list[str]
    source_file: str
    line_no: int


@dataclass(slots=True)
class FemModel:
    source: str
    nodes: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    element_counts: Counter[str] = field(default_factory=Counter)
    element_dimensions: Counter[int] = field(default_factory=Counter)
    element_property_counts: Counter[int] = field(default_factory=Counter)
    element_node_refs: Counter[int] = field(default_factory=Counter)
    edge_lengths: list[float] = field(default_factory=list)
    properties: dict[int, dict[str, Any]] = field(default_factory=dict)
    materials: dict[int, dict[str, Any]] = field(default_factory=dict)
    loads: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    connections: list[dict[str, Any]] = field(default_factory=list)
    subcases: list[dict[str, Any]] = field(default_factory=list)
    include_files: list[str] = field(default_factory=list)
    component_names: dict[int, str] = field(default_factory=dict)
    unknown_cards: Counter[str] = field(default_factory=Counter)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def element_count(self) -> int:
        return sum(self.element_counts.values())

    def model_summary(self) -> dict[str, Any]:
        coordinates = list(self.nodes.values())
        if coordinates:
            bounds = {
                "min": [min(point[i] for point in coordinates) for i in range(3)],
                "max": [max(point[i] for point in coordinates) for i in range(3)],
            }
        else:
            bounds = None
        referenced_materials = {mat_id for prop in self.properties.values() for mat_id in prop.get("material_ids", []) if mat_id}
        referenced_properties = set(self.element_property_counts)
        component_ids = sorted(self.component_names) or sorted(referenced_properties)
        components = [
            {
                "id": component_id,
                "name": self.component_names.get(component_id, f"Component {component_id}"),
                "property_id": component_id if component_id in self.properties else None,
                "element_count": self.element_property_counts.get(component_id, 0),
            }
            for component_id in component_ids
        ]
        return {
            "node_count": len(self.nodes),
            "element_count": self.element_count,
            "component_count": len(components),
            "property_count": len(self.properties),
            "material_count": len(self.materials),
            "subcase_count": len(self.subcases),
            "include_count": len(self.include_files),
            "element_dimensions": {str(key): value for key, value in sorted(self.element_dimensions.items())},
            "bounding_box": bounds,
            "total_mass": None,
            "unreferenced": {
                "materials": sorted(set(self.materials) - referenced_materials),
                "properties": sorted(set(self.properties) - referenced_properties),
            },
            "components": components,
            "include_graph": [{"path": value} for value in self.include_files],
            "unknown_cards": dict(self.unknown_cards.most_common()),
            "warnings": self.warnings,
        }

    def mesh_summary(self) -> dict[str, Any]:
        lengths = sorted(self.edge_lengths)
        average = sum(lengths) / len(lengths) if lengths else None
        distribution: list[dict[str, Any]] = []
        if lengths:
            buckets = 10
            low, high = lengths[0], lengths[-1]
            width = (high - low) / buckets if high > low else 1.0
            counts = [0] * buckets
            for value in lengths:
                index = min(buckets - 1, int((value - low) / width)) if high > low else 0
                counts[index] += 1
            distribution = [
                {"min": low + index * width, "max": low + (index + 1) * width, "count": count}
                for index, count in enumerate(counts)
            ]
        used_nodes = set(self.element_node_refs)
        return {
            "element_types": dict(self.element_counts),
            "dimensions": {str(key): value for key, value in sorted(self.element_dimensions.items())},
            "average_edge_length": average,
            "edge_length_distribution": distribution,
            "shell_ratio": (sum(count for card, count in self.element_counts.items() if ELEMENT_CARDS.get(card) == 2) / self.element_count) if self.element_count else 0,
            "triangle_count": self.element_counts["CTRIA3"],
            "quad_count": self.element_counts["CQUAD4"],
            "solid_types": {card: self.element_counts[card] for card in ("CTETRA", "CPENTA", "CHEXA") if self.element_counts[card]},
            "rbe2_count": sum(1 for item in self.connections if item["type"] == "RBE2"),
            "rbe3_count": sum(1 for item in self.connections if item["type"] == "RBE3"),
            "orphan_node_count": len(set(self.nodes) - used_nodes),
            "unused_node_count": len(set(self.nodes) - used_nodes),
        }

    def material_property_summary(self) -> dict[str, Any]:
        referenced_materials = {mat_id for prop in self.properties.values() for mat_id in prop.get("material_ids", []) if mat_id}
        referenced_properties = set(self.element_property_counts)
        return {
            "materials": list(self.materials.values()),
            "properties": list(self.properties.values()),
            "links": [
                {"property_id": prop["id"], "material_id": material_id}
                for prop in self.properties.values()
                for material_id in prop.get("material_ids", [])
                if material_id
            ],
            "unreferenced_materials": sorted(set(self.materials) - referenced_materials),
            "unreferenced_properties": sorted(set(self.properties) - referenced_properties),
            "missing_material_properties": [prop["id"] for prop in self.properties.values() if any(mid not in self.materials for mid in prop.get("material_ids", []))],
        }

    def boundary_summary(self) -> dict[str, Any]:
        return {"loads": self.loads, "constraints": self.constraints, "connections": self.connections}

    def subcase_summary(self) -> dict[str, Any]:
        return {"subcases": self.subcases}


class FemParser:
    def __init__(self, *, max_include_depth: int = 20) -> None:
        self.max_include_depth = max_include_depth

    def parse(self, path: Path) -> FemModel:
        source = path.expanduser().resolve()
        model = FemModel(source=str(source))
        self._parse_file(source, model, set(), 0, assume_bulk=False)
        return model

    def _parse_file(
        self,
        path: Path,
        model: FemModel,
        visited: set[Path],
        depth: int,
        *,
        assume_bulk: bool,
    ) -> None:
        if depth > self.max_include_depth:
            model.warnings.append({"code": "FEM_INCLUDE_DEPTH", "path": str(path)})
            return
        resolved = path.resolve()
        if resolved in visited:
            model.warnings.append({"code": "FEM_INCLUDE_CYCLE", "path": str(resolved)})
            return
        visited.add(resolved)
        try:
            lines = resolved.open("r", encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            model.warnings.append({"code": "FEM_INCLUDE_MISSING", "path": str(resolved), "message": str(exc)})
            return
        bulk = assume_bulk
        current_subcase: dict[str, Any] | None = None
        pending: SourceCard | None = None
        with lines:
            for line_no, raw in enumerate(lines, start=1):
                line = raw.rstrip("\r\n")
                self._capture_comment(line, model)
                content = line.split("$", 1)[0].rstrip()
                if not content.strip():
                    continue
                upper = content.strip().upper()
                include_match = re.match(r"^INCLUDE\s*[= ]\s*['\"]?([^'\"]+)['\"]?", content.strip(), re.I)
                if include_match:
                    include_path = (resolved.parent / include_match.group(1).strip()).resolve()
                    model.include_files.append(str(include_path))
                    self._parse_file(include_path, model, visited, depth + 1, assume_bulk=bulk)
                    continue
                if upper.startswith("BEGIN BULK"):
                    bulk = True
                    continue
                if upper.startswith("ENDDATA"):
                    break
                if not bulk:
                    if upper.startswith("SUBCASE"):
                        if current_subcase:
                            model.subcases.append(current_subcase)
                        fields = upper.replace("=", " ").split()
                        subcase_id = _integer(fields[-1], len(model.subcases) + 1)
                        current_subcase = {"id": subcase_id, "name": f"SUBCASE {subcase_id}", "references": {}, "source_file": str(resolved), "line_no": line_no}
                    elif current_subcase and "=" in content:
                        key, value = content.split("=", 1)
                        key = key.strip().upper()
                        current_subcase["references"][key] = value.strip()
                        if key == "LABEL":
                            current_subcase["name"] = value.strip()
                    continue
                fields = self._fields(content)
                if not fields:
                    continue
                first = fields[0].strip().upper().rstrip("*")
                continuation = not first or first in {"+", "*"} or content[0].isspace()
                if continuation and pending is not None:
                    pending.fields.extend(fields[1:] if first in {"+", "*"} else fields)
                    continue
                if pending is not None:
                    self._consume(pending, model)
                pending = SourceCard(first, fields, str(resolved), line_no)
            if pending is not None:
                self._consume(pending, model)
        if current_subcase:
            model.subcases.append(current_subcase)

    @staticmethod
    def _capture_comment(line: str, model: FemModel) -> None:
        match = re.search(r"\$HMNAME\s+COMP\s+(\d+)\s*\"([^\"]+)\"", line, re.I)
        if match:
            model.component_names[int(match.group(1))] = match.group(2)

    @staticmethod
    def _fields(line: str) -> list[str]:
        if "," in line:
            return [part.strip() for part in line.split(",")]
        large = line[:8].strip().endswith("*")
        width = 16 if large else 8
        first = line[:8].strip()
        return [first, *[line[index : index + width].strip() for index in range(8, len(line), width)]]

    def _consume(self, card: SourceCard, model: FemModel) -> None:
        name, fields = card.name, card.fields
        if name == "GRID":
            node_id = _integer(_at(fields, 1))
            if node_id:
                model.nodes[node_id] = (_number(_at(fields, 3)), _number(_at(fields, 4)), _number(_at(fields, 5)))
            return
        if name in ELEMENT_CARDS:
            model.element_counts[name] += 1
            model.element_dimensions[ELEMENT_CARDS[name]] += 1
            prop_id = _integer(_at(fields, 2))
            if prop_id:
                model.element_property_counts[prop_id] += 1
            node_ids = [_integer(value) for value in fields[3:] if _integer(value)]
            model.element_node_refs.update(node_ids)
            self._sample_lengths(node_ids, model)
            return
        if name in PROPERTY_CARDS:
            property_id = _integer(_at(fields, 1))
            material_ids: list[int] = []
            thickness: float | None = None
            if name == "PSHELL":
                material_ids = [_integer(_at(fields, index)) for index in (2, 4, 6, 8) if _integer(_at(fields, index))]
                thickness = _number(_at(fields, 3)) or None
            elif name in {"PSOLID", "PBAR", "PBEAM"}:
                material_ids = [_integer(_at(fields, 2))] if _integer(_at(fields, 2)) else []
            elif name == "PCOMP":
                material_ids = sorted({_integer(_at(fields, index)) for index in range(9, len(fields), 4) if _integer(_at(fields, index))})
                thickness = sum(_number(_at(fields, index)) for index in range(10, len(fields), 4)) or None
            model.properties[property_id] = {"id": property_id, "type": name, "material_ids": material_ids, "thickness": thickness, "source_file": card.source_file, "line_no": card.line_no}
            return
        if name in MATERIAL_CARDS:
            material_id = _integer(_at(fields, 1))
            if name == "MAT1":
                data = {"E": _number(_at(fields, 2)), "G": _number(_at(fields, 3)), "nu": _number(_at(fields, 4)), "rho": _number(_at(fields, 5))}
            else:
                data = {"E1": _number(_at(fields, 2)), "E2": _number(_at(fields, 3)), "nu12": _number(_at(fields, 4)), "G12": _number(_at(fields, 5)), "rho": _number(_at(fields, 8))}
            model.materials[material_id] = {"id": material_id, "type": name, **data, "source_file": card.source_file, "line_no": card.line_no}
            return
        base = {"id": _integer(_at(fields, 1)), "type": name, "source_file": card.source_file, "line_no": card.line_no, "raw_fields": fields[2:]}
        if name in LOAD_CARDS:
            model.loads.append(base)
        elif name in CONSTRAINT_CARDS:
            model.constraints.append(base)
        elif name in CONNECTION_CARDS:
            model.connections.append(base)
        elif name not in {"BEGIN", "PARAM", "ECHO", "TITLE", "SUBTITLE", "LABEL"}:
            model.unknown_cards[name] += 1

    @staticmethod
    def _sample_lengths(node_ids: list[int], model: FemModel) -> None:
        if len(model.edge_lengths) >= 200_000:
            return
        for first, second in zip(node_ids, node_ids[1:] + node_ids[:1], strict=False):
            a, b = model.nodes.get(first), model.nodes.get(second)
            if a and b:
                model.edge_lengths.append(math.dist(a, b))


def _at(fields: list[str], index: int) -> str:
    return fields[index] if index < len(fields) else ""
