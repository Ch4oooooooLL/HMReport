from pathlib import Path


def test_tcl_protocol_has_no_arbitrary_execution_surface() -> None:
    root = Path(__file__).resolve().parents[2] / "hyperview"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.tcl"))
    for forbidden in ("tcl.eval", "shell.exec", "file.delete"):
        assert forbidden not in text

