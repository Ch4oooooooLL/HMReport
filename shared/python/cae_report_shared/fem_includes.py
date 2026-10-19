from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_INCLUDE = re.compile(
    r"^\s*INCLUDE(?:\s*=|\s+)\s*(?:'([^']+)'|\"([^\"]+)\"|([^\s,$]+))",
    re.IGNORECASE,
)


def include_target(line: str) -> str | None:
    """Return the path referenced by an OptiStruct/Nastran INCLUDE line."""
    content = line.split("$", 1)[0]
    match = _INCLUDE.match(content)
    if match is None:
        return None
    return next(value.strip() for value in match.groups() if value is not None)


@dataclass(slots=True)
class FemSourceTree:
    files: list[Path] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)

    @property
    def includes(self) -> list[Path]:
        return self.files[1:]


def resolve_fem_source_tree(head: Path) -> FemSourceTree:
    """Resolve the unique, recursive INCLUDE closure rooted at ``head``."""
    result = FemSourceTree()
    visited: set[Path] = set()

    def visit(path: Path) -> None:
        resolved = path.expanduser().resolve()
        if resolved in visited:
            return
        visited.add(resolved)
        if not resolved.is_file():
            result.missing.append(resolved)
            return
        result.files.append(resolved)
        try:
            stream = resolved.open("r", encoding="utf-8-sig", errors="replace")
        except OSError:
            result.missing.append(resolved)
            return
        with stream:
            for raw in stream:
                target = include_target(raw)
                if target is not None:
                    visit(resolved.parent / target)

    visit(head)
    return result
