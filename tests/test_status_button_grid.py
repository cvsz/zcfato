"""Tk-free tests for the shared 2x2 status action panel."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename", ["status_random_gui.py", "status_marquee_gui.py"])
def test_action_grid_is_two_columns_and_four_working_callbacks(filename):
    source = (ROOT / filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == "_build_actions")
    block = ast.get_source_segment(source, method)
    assert 'actions.columnconfigure(0, weight=1' in block
    assert 'actions.columnconfigure(1, weight=1' in block
    assert 'row=index // 2, column=index % 2' in block
    for name in ("1. Discovery", "2. Apply", "3. Start", "4. Stop"):
        assert name in block
    assert "self.discover" in block
    assert "self.apply_now" in block
    assert "self.set_enabled(self.mode, True)" in block
    assert "self.set_enabled(self.mode, False)" in block
    assert 'command=self.check_update' in block
