from __future__ import annotations

import math
from typing import Any


def deduplicate_hotspots(
    candidates: list[dict[str, Any]],
    *,
    minimum_distance: float,
    top_n: int,
) -> list[dict[str, Any]]:
    """Keep the highest value within each component/distance neighborhood.

    Ranking is per-subcase: candidates are grouped by their ``subcase`` field,
    and each group keeps its own top-N ranked 1..N so a single subcase can never
    crowd out hotspots from other subcases.
    """
    by_subcase: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = str(candidate.get("subcase", ""))
        by_subcase.setdefault(key, []).append(candidate)

    ranked: list[dict[str, Any]] = []
    for items in by_subcase.values():
        kept: list[dict[str, Any]] = []
        for candidate in sorted(items, key=lambda item: abs(float(item.get("value", 0))), reverse=True):
            coordinate = candidate.get("coordinate")
            duplicate = False
            if isinstance(coordinate, list) and len(coordinate) == 3:
                for existing in kept:
                    other = existing.get("coordinate")
                    if (
                        existing.get("component_id") == candidate.get("component_id")
                        and isinstance(other, list)
                        and len(other) == 3
                        and math.dist(coordinate, other) < minimum_distance
                    ):
                        duplicate = True
                        break
            if not duplicate:
                kept.append(candidate)
            if len(kept) >= top_n:
                break
        for rank, item in enumerate(kept, start=1):
            item["rank"] = rank
        ranked.extend(kept)
    return ranked

