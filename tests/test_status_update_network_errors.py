"""Guard against update-check failures leaking from Windows GUI threads."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["status_random_gui.py", "status_marquee_gui.py"])
def test_auto_update_worker_handles_network_error(name):
    source = (ROOT / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == "_auto_update_check")
    worker = next(node for node in ast.walk(method)
                  if isinstance(node, ast.FunctionDef) and node.name == "work")
    assert any(isinstance(node, ast.Try) and any(
        isinstance(handler.type, ast.Tuple) and any(
            isinstance(item, ast.Name) and item.id == "OSError"
            for item in handler.type.elts)
        for handler in node.handlers) for node in worker.body), (
        "Background update check must catch HTTPError (an OSError subclass)")
