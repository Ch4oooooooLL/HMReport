from cae_report_worker.hotspots import deduplicate_hotspots


def test_hotspot_dedup_keeps_highest_in_component_neighborhood() -> None:
    candidates = [
        {"component_id": 10, "coordinate": [0.0, 0.0, 0.0], "value": 100.0},
        {"component_id": 10, "coordinate": [0.5, 0.0, 0.0], "value": 90.0},
        {"component_id": 11, "coordinate": [0.5, 0.0, 0.0], "value": 80.0},
    ]
    kept = deduplicate_hotspots(candidates, minimum_distance=1.0, top_n=10)
    assert [item["value"] for item in kept] == [100.0, 80.0]
    assert [item["rank"] for item in kept] == [1, 2]

