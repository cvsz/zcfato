"""Ensure process-tree shutdown cannot resolve taskkill from a writable PATH entry."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIRS = {".git", ".venv", "build", "dist", "__pycache__"}


def test_taskkill_invocations_use_windows_system_directory_helper():
    taskkill_calls = []
    bare_calls = []
    for source_path in ROOT.rglob("*.py"):
        if any(part in GENERATED_DIRS for part in source_path.relative_to(ROOT).parts):
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "run" or not node.args or not isinstance(node.args[0], ast.List):
                continue
            argv = node.args[0].elts
            if not argv:
                continue
            first = argv[0]
            if isinstance(first, ast.Constant) and first.value in {"taskkill", "taskkill.exe"}:
                bare_calls.append(f"{source_path.relative_to(ROOT)}:{node.lineno}")
            elif (
                isinstance(first, ast.Call)
                and isinstance(first.func, ast.Name)
                and first.func.id == "system_taskkill_path"
            ):
                taskkill_calls.append(source_path)

    assert not bare_calls, f"taskkill must use its absolute Windows system path: {bare_calls}"
    assert len(taskkill_calls) >= 12
