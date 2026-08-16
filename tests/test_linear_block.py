import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from linear_block import build_linear_system
from model_layout import build_layout

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


def _solve_numeric(ir: dict, equations, unknown_names):
    layout = build_layout(ir)
    A_c, b_c = build_linear_system(equations, unknown_names, layout.name_to_c())
    # These fixtures have no parameters/states referenced by the coupled
    # block's coefficients, so every A/b entry is a literal C expression
    # (e.g. "(-(((1.0) * (2.0))))") that also happens to be valid Python.
    A = [[eval(c) for c in row] for row in A_c]
    b = [eval(c) for c in b_c]
    return np.linalg.solve(A, b)


def test_coupled_algebraic_matches_hand_solved_system():
    """y1 = 2*y2 + 1, y2 = 3*y1 - 2  =>  y1 = 0.6, y2 = -0.2 (hand-solved:
    substitute y1 = 2*(3*y1-2)+1 = 6*y1-3 => -5*y1 = -3 => y1 = 0.6)."""
    ir = load_ir("CoupledAlgebraic")
    equations = [(0, ir["f_x"][0]), (1, ir["f_x"][1])]
    x = _solve_numeric(ir, equations, ["y1", "y2"])
    assert np.allclose(x, [0.6, -0.2])


def test_affine_extraction_teeth_a_dropped_negation_gives_a_wrong_answer():
    """Teeth check (required by prd-combined.md Feature 4: 'teeth-test by
    perturbing the assembled system and confirming correctness fails'):
    monkeypatch _merge_add to simulate a dropped negation in Sub handling
    (the exact bug manually introduced and reverted during development,
    verified end-to-end through a real gcc build at the time -- this is
    the permanent, automated version of that check) and confirm the
    solved system is WRONG, not silently still correct."""
    import linear_block

    ir = load_ir("CoupledAlgebraic")
    equations = [(0, ir["f_x"][0]), (1, ir["f_x"][1])]

    original_negate = linear_block._negate
    linear_block._negate = lambda a: a  # drop the negation entirely
    try:
        x_broken = _solve_numeric(ir, equations, ["y1", "y2"])
    finally:
        linear_block._negate = original_negate

    assert not np.allclose(x_broken, [0.6, -0.2]), (
        "perturbing the assembled system should have produced a wrong answer, "
        "but the result still matched the correct solution"
    )
