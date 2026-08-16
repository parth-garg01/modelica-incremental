"""Feature 10: parameterized model generators emit valid models at
several sizes, equation counts match the requested sizes, and the
largest target compiles under Rumoca. Generated models are NOT
committed (models/scaled/ is gitignored) -- they are cheap and
deterministic to regenerate from src/scaled_models.py.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from compile import compile_model
from matching import compute_matching
from scaled_models import generate_rc_ladder, generate_thermal_chain

BUILD_ROOT = Path(__file__).resolve().parent.parent / "models" / "scaled"


@pytest.fixture(autouse=True)
def _clean():
    yield
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)


@pytest.mark.parametrize("n_rooms,expected_eq", [(3, 8), (10, 29), (100, 299)])
def test_thermal_chain_equation_count_matches_request(n_rooms, expected_eq):
    path = generate_thermal_chain(n_rooms, BUILD_ROOT / f"ThermalChain{n_rooms}" / f"ThermalChain{n_rooms}.mo")
    result = compile_model(str(path), f"ThermalChain{n_rooms}")
    n_eq = len(result.ir["x"]) + len(result.ir["y"])
    # der(Ti) for each of N rooms + Qi_env for each of N rooms + Qi,i+1
    # for N-1 adjacent pairs = 3N - 1 (cross-checked against real
    # measurements during development: N=5 -> 14, N=100 -> 299, N=1000
    # -> 2999, N=5000 -> 14999, all exactly 3N-1).
    assert n_eq == expected_eq == 3 * n_rooms - 1


@pytest.mark.parametrize("n_segments,expected_eq", [(3, 7), (10, 21), (100, 201)])
def test_rc_ladder_equation_count_matches_request(n_segments, expected_eq):
    path = generate_rc_ladder(n_segments, BUILD_ROOT / f"RcLadder{n_segments}" / f"RcLadder{n_segments}.mo")
    result = compile_model(str(path), f"RcLadder{n_segments}")
    n_eq = len(result.ir["x"]) + len(result.ir["y"])
    assert n_eq == expected_eq  # 1 source + 2 per segment


@pytest.mark.parametrize("n_rooms", [3, 100, 1000])
def test_thermal_chain_is_fully_matched_and_index_1(n_rooms):
    """Every generated size must stay index-1 (matched=True, no
    unmatched equations) -- the generator's chain topology never
    introduces a reactive-only loop by construction."""
    path = generate_thermal_chain(n_rooms, BUILD_ROOT / f"ThermalChain{n_rooms}" / f"ThermalChain{n_rooms}.mo")
    result = compile_model(str(path), f"ThermalChain{n_rooms}")
    m = compute_matching(result.ir)
    assert m.is_matched is True
    assert m.unmatched_equations == []
