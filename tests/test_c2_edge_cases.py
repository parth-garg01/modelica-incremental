"""Feature C2: edge cases for the incremental recompile+relink pipeline.

1. A change that ripples to most of the model even after the granularity
   fix (models/chain: a forward-dependency chain, no feedback, no
   genuine algebraic loop -- the causalized-graph fix doesn't help here
   because there's nothing to fix; forward-reachability from the root
   equation legitimately reaches everything downstream).
2. The empty change (recompile the SAME model as its own "changed"
   variant -- zero affected units, full object reuse).

"Change inside a genuine algebraic loop" is not exercised: Feature D2's
diagnosis found no genuine algebraic loop in any fixture (see
src/diagnostic.py; all verdicts are "integration-artifact" or
"no-coupling"), so this case does not currently exist to test. Recorded
here rather than silently skipped.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from correctness_c import diff_outputs
from measure_c import run_cell

BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_cache"


@pytest.fixture(autouse=True)
def _clean_build_cache():
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    yield
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)


def test_near_full_ripple_change_still_produces_correct_output():
    """The Chain model's root equation change ripples to every downstream
    equation under forward-reachability. Even at high ripple, the
    incremental build must still match the full rebuild exactly."""
    result = run_cell(
        "models/chain/Chain.mo", "models/chain_swapped/Chain.mo", "Chain",
        seed=["y1"], t_end=2.0, dt=0.5,
    )
    # y1 (root) -> y2 (reads y1) -> x (state eq reads y2): full chain reached.
    assert result["n_units_recompiled"] == result["n_units_total"] == 3

    diff = diff_outputs(result["full_output"], result["incremental_output"])
    assert diff["pass"] is True
    assert diff["max_abs_error"] == 0.0


def test_empty_change_recompiles_nothing_and_still_matches():
    """Recompiling the SAME model as its own 'changed' variant: nothing
    was actually edited, so the resolver, seeded with an empty change,
    should mark zero units affected, reuse every cached object, and the
    incremental build should still match the full rebuild exactly."""
    result = run_cell(
        "models/rlc_circuit/RLCCircuit.mo", "models/rlc_circuit/RLCCircuit.mo", "RLCCircuit",
        seed=[], t_end=2.0, dt=0.5,
    )
    assert result["n_units_recompiled"] == 0
    assert result["reused_objects_byte_identical_to_cache"] is True

    diff = diff_outputs(result["full_output"], result["incremental_output"])
    assert diff["pass"] is True
    assert diff["max_abs_error"] == 0.0
