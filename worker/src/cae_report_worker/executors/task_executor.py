from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from cae_report_worker.fem import FemParser
from cae_report_worker.hotspots import deduplicate_hotspots
from cae_report_worker.hyperview import FakeHyperViewAdapter, RealHyperViewAdapter
from cae_report_worker.imaging import create_capture

Progress = Callable[[int, int, str], None]


class TaskExecutor:
    def __init__(self, *, fake_hyperview: bool = True) -> None:
        self.parser = FemParser()
        self.fake_hyperview = fake_hyperview
        self._models: dict[str, Any] = {}
        self._hv: dict[str, FakeHyperViewAdapter | RealHyperViewAdapter] = {}

    def close(self) -> None:
        for run_id in list(self._hv):
            self.release_run(run_id)
        self._models.clear()

    def release_run(self, run_id: str) -> None:
        adapter = self._hv.pop(run_id, None)
        if isinstance(adapter, RealHyperViewAdapter):
            adapter.close()
        self._models.pop(run_id, None)

    def release_action_session(self, run_id: str) -> None:
        adapter = self._hv.get(run_id)
        if (
            isinstance(adapter, RealHyperViewAdapter)
            and not adapter.background
            and adapter.is_alive
        ):
            return
        self.release_run(run_id)

    def execute(self, task: dict[str, Any], progress: Progress) -> dict[str, Any]:
        task_type = task["task_type"]
        run_id = task["run_id"]
        snapshot = task["run"]["input_snapshot"]
        project_path = Path(task["project"]["workspace_path"])
        progress(5, 100, "准备输入")
        if task_type.startswith("fem."):
            model = self._models.get(run_id)
            if model is None:
                model = self.parser.parse(Path(snapshot["fem"]["path"]))
                self._models[run_id] = model
            progress(80, 100, "整理 FEM 数据")
            result = {
                "fem.model_summary": model.model_summary,
                "fem.mesh_summary": model.mesh_summary,
                "fem.material_property": model.material_property_summary,
                "fem.boundary_conditions": model.boundary_summary,
                "fem.subcases": model.subcase_summary,
            }[task_type]()
            progress(100, 100, "FEM 任务完成")
            return result
        hv = self._adapter(run_id, project_path, snapshot)
        if task_type == "h3d.result_index":
            progress(60, 100, "索引 H3D 结果")
            result = hv.index()
        elif task_type in {"result.stress_hotspots", "result.displacement_hotspots"}:
            kind = "stress" if "stress" in task_type else "displacement"
            configuration = task.get("configuration", {})
            top_n = int(configuration.get("top_n", 3))
            candidates = hv.hotspots(kind, max(top_n * 2, top_n))
            hotspots = deduplicate_hotspots(
                candidates,
                minimum_distance=float(configuration.get("minimum_distance", 0.0)),
                top_n=top_n,
            )
            views = ["global", "local_isometric", "front", "right", "top", "component_isolate", "component_context"]
            for hotspot_index, hotspot in enumerate(hotspots):
                capture_name = f"{kind.title()} hotspot [{hotspot.get('subcase', '')}] #{hotspot['rank']}"
                hotspot["captures"] = [
                    (
                        create_capture(
                            project_path,
                            run_id,
                            capture_name,
                            view,
                            hotspot=hotspot,
                            source_fingerprint=snapshot["h3d"]["fingerprint"],
                        )
                        if isinstance(hv, FakeHyperViewAdapter)
                        else hv.capture(
                            project_path,
                            run_id,
                            capture_name,
                            view,
                            hotspot=hotspot,
                        )
                    )
                    for view in views
                ]
                progress(20 + int(70 * (hotspot_index + 1) / len(hotspots)), 100, f"生成热点 {hotspot_index + 1}/{len(hotspots)}")
            result = {"hotspots": hotspots}
        elif task_type == "capture.standard_views":
            views = ["global_model", "mesh", "constraints", "loads", "global_stress", "global_displacement", "front", "rear", "left", "right", "top"]
            captures = [
                (
                    create_capture(
                        project_path,
                        run_id,
                        f"Standard / {view}",
                        view,
                        source_fingerprint=snapshot["h3d"]["fingerprint"],
                    )
                    if isinstance(hv, FakeHyperViewAdapter)
                    else hv.capture(project_path, run_id, f"Standard / {view}", view)
                )
                for view in views
            ]
            result = {"captures": captures}
        elif task_type == "report.prepare":
            result = {"document": self._report_document(run_id, task["project"])}
        else:
            raise RuntimeError(f"unknown task type: {task_type}")
        progress(100, 100, "任务完成")
        return result

    def execute_action(self, action: dict[str, Any]) -> dict[str, Any]:
        kind = action["kind"]
        run_id = str(action["run_id"])
        project_path = Path(action["project"]["workspace_path"])
        snapshot = action["run"]["input_snapshot"]
        bring_to_front = bool(action.get("payload", {}).get("bring_to_front", False))
        adapter = self._adapter(
            run_id,
            project_path,
            snapshot,
            background=not (kind == "view.restore" and bring_to_front),
        )
        if kind == "capture.recapture":
            capture = action["capture"]
            view_state = action["view_state"]
            generated = (
                create_capture(
                    project_path,
                    run_id,
                    capture["name"],
                    capture["view_name"],
                    source_fingerprint=str(view_state.get("source_fingerprint", "")),
                    logical_capture_id=capture["id"],
                )
                if isinstance(adapter, FakeHyperViewAdapter)
                else adapter.capture(
                    project_path,
                    run_id,
                    capture["name"],
                    capture["view_name"],
                    logical_capture_id=capture["id"],
                    view_state=view_state,
                )
            )
            if isinstance(adapter, FakeHyperViewAdapter):
                generated["view_state"] = view_state
            return {"capture": generated}
        if kind == "view.restore":
            if isinstance(adapter, RealHyperViewAdapter):
                return adapter.apply_view(
                    action["view_state"],
                    bring_to_front=bring_to_front,
                )
            return adapter.apply_view(action["view_state"])
        raise RuntimeError(f"unknown action kind: {kind}")

    def _adapter(
        self,
        run_id: str,
        project_path: Path,
        snapshot: dict[str, Any],
        *,
        background: bool | None = None,
    ) -> FakeHyperViewAdapter | RealHyperViewAdapter:
        adapter = self._hv.get(run_id)
        if (
            isinstance(adapter, RealHyperViewAdapter)
            and not adapter.is_alive
        ):
            adapter.close()
            self._hv.pop(run_id, None)
            adapter = None
        if adapter is not None:
            if (
                not isinstance(adapter, RealHyperViewAdapter)
                or background is None
                or adapter.background == background
            ):
                return adapter
            adapter.close()
            self._hv.pop(run_id, None)
        if self.fake_hyperview:
            adapter = FakeHyperViewAdapter()
        else:
            adapter = RealHyperViewAdapter(
                run_id,
                project_path / "runtime" / "hyperview",
                background=background,
            )
        h3d = snapshot["h3d"]
        adapter.open_source(Path(h3d["path"]), str(h3d["fingerprint"]))
        self._hv[run_id] = adapter
        return adapter

    @staticmethod
    def _report_document(run_id: str, project: dict[str, Any]) -> dict[str, Any]:
        titles = ["封面", "项目说明", "计算模型", "网格信息", "材料与属性", "边界条件", "工况说明", "应力结果", "位移结果", "热点详情", "结论", "附录"]
        return {
            "id": "",
            "run_id": run_id,
            "template_id": "default-v1",
            "page_size": "LAYOUT_WIDE",
            "theme": {"primary": "#176B87", "font": "Microsoft YaHei"},
            "sections": [],
            "slides": [
                {"id": f"slide-{index}", "title": title, "layout": "cover" if index == 0 else "title-content", "elements": [{"type": "text", "x": 0.8, "y": 1.4, "w": 11.7, "h": 4.8, "text": project["name"] if index == 0 else f"{title}（待工程师审核）"}], "notes": ""}
                for index, title in enumerate(titles)
            ],
        }
