"""Regression coverage for four status GUI controls (offline, no Camfrog needed)."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["status_random_gui.py", "status_marquee_gui.py"])
def test_four_button_handlers_are_present_and_ordered(name):
    source = (ROOT / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    buttons = next(node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == "_build_actions")
    rendered = ast.get_source_segment(source, buttons)
    assert rendered.index("1. Discovery") < rendered.index("2. Apply")
    assert rendered.index("2. Apply") < rendered.index("3. Start")
    assert rendered.index("3. Start") < rendered.index("4. Stop")
    for handler in ("self.discover", "self.apply_now", "self.set_enabled"):
        assert handler in rendered


@pytest.mark.parametrize("name", ["status_random_gui.py", "status_marquee_gui.py"])
def test_stop_is_not_blocked_by_unsaved_invalid_form_data(name):
    source = (ROOT / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == "set_enabled")
    assert any(isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp)
               and isinstance(node.test.op, ast.Not)
               for node in function.body)
    # STOP branch occurs before form validation/save and immediately returns.
    first_stop = next(node for node in function.body
                      if isinstance(node, ast.If)
                      and isinstance(node.test, ast.UnaryOp)
                      and isinstance(node.test.op, ast.Not)
                      and isinstance(node.test.operand, ast.Name)
                      and node.test.operand.id == "enabled")
    assert isinstance(first_stop.body[-1], ast.Return)
    assert "save_settings" not in ast.get_source_segment(source, first_stop)
    assert "cmd_stop" in source


@pytest.mark.parametrize("name", ["status_random_gui.py", "status_marquee_gui.py"])
def test_action_handlers_guard_busy_state(name):
    source = (ROOT / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for handler in ("apply_now", "discover", "set_enabled"):
        f = next(node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == handler)
        assert any(isinstance(node, ast.If)
                   and isinstance(node.test, ast.Attribute)
                   and node.test.attr == "busy"
                   for node in f.body[:3]), handler
