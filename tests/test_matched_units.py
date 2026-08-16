import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from causal_graph import build_causalized_graph
from matched_units import compute_matched_units
from units import compute_units

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"

ALL_EQUATION_FORM_MODELS = ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork", "Chain"]


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


@pytest.mark.parametrize("model_name", ALL_EQUATION_FORM_MODELS)
def test_units_cover_every_equation_with_no_overlap(model_name):
    ir = load_ir(model_name)
    units = compute_matched_units(ir)
    covered = [name for members in units.values() for name in members]
    n_equations = len(ir["f_x"])
    assert len(covered) == n_equations
    assert len(covered) == len(set(covered))


@pytest.mark.parametrize("model_name", ["RLCCircuit", "ThermalNetwork"])
def test_matches_phase_2_causalized_scc_partition_exactly(model_name):
    """No-regression check: BLT-block units (Feature 2's new definition)
    must produce the IDENTICAL unit dict as the causalized-SCC definition
    (phase 2, src/causal_graph.py + src/units.py) on the two models phase
    2 validated that definition against."""
    ir = load_ir(model_name)
    matched = compute_matched_units(ir)
    causalized = compute_units(build_causalized_graph(ir))
    assert matched == causalized


def test_known_coupled_block_yields_one_coupled_unit_not_singletons():
    """CoupledAlgebraic (y1 = 2*y2+1, y2 = 3*y1-2) is a hand-verified
    genuine 2-equation algebraic loop (Model.structure() independently
    confirms algebraic_loops=1). This is the case the causalized-SCC
    definition was never actually tested against, because no fixture
    with a genuine (non-integration-artifact) coupled block existed
    until this feature needed one."""
    ir = load_ir("CoupledAlgebraic")
    units = compute_matched_units(ir)
    assert units == {"y1+y2": ["y1", "y2"]}


def test_coupled_block_teeth_a_broken_matcher_would_show_singletons():
    """Teeth check: if blt_blocks failed to find the y1<->y2 coupling (the
    exact failure mode this test guards against), CoupledAlgebraic would
    incorrectly show 2 singleton units instead of 1 coupled one. Confirm
    the two representations are actually distinguishable, i.e. this test
    is not vacuous."""
    ir = load_ir("CoupledAlgebraic")
    units = compute_matched_units(ir)
    broken_looking_result = {"y1": ["y1"], "y2": ["y2"]}
    assert units != broken_looking_result
