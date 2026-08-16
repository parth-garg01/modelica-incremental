"""Feature 11: end-to-end correctness and soundness at scale. Runs the
full detect-resolve-recompile-relink-bit-diff pipeline on a generated
large model for a single local change. The automated test here uses a
size that keeps the test suite fast (N=100, ~299 equations); a much
larger one-off run (N=500, ~1499 equations) was used to validate the
pipeline at real scale and is documented in the commit history and
docs/findings/scaling-bottlenecks.md rather than re-run on every test
invocation (it alone takes ~4.7 minutes for one cell, 5 repeats).
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from measure_msl import run_cell
from scaled_models import generate_thermal_chain, swap_room_conductance

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models" / "scaled"
BUILD_CACHE = Path(__file__).resolve().parent.parent / "build_cache_msl"


@pytest.fixture(autouse=True)
def _clean():
    yield
    for p in (MODELS_ROOT, BUILD_CACHE):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


def test_local_change_stays_local_and_correct_at_scale():
    """A change to ONE room, in a 100-room chain (299 equations), must
    affect only a small, bounded number of units (not scale with N),
    and the incremental build must still be bit-identical to a full
    rebuild -- the real correctness bar, not a tolerance, even at scale."""
    n = 100
    mid = n // 2
    base_path = generate_thermal_chain(n, MODELS_ROOT / f"ThermalChainScale{n}" / f"ThermalChainScale{n}.mo")
    chg_path = swap_room_conductance(base_path, mid, MODELS_ROOT / f"ThermalChainScale{n}_swapped" / f"ThermalChainScale{n}.mo")

    result = run_cell(str(base_path), str(chg_path), f"ThermalChain{n}", [f"Q{mid}env"], 2.0, 1.0)

    assert result["total_units"] == 3 * n - 1
    assert result["affected_units"] <= 4  # bounded, not proportional to N
    assert result["affected_fraction"] < 0.02  # locality holds at scale
    assert result["outputs_identical"] is True
    assert result["reused_objects_byte_identical_to_cache"] is True
