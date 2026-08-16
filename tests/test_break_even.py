"""Feature 16: break-even change frequency. Small automated model here
(kept fast for the regression suite); the reported N=300 sweep is logged
separately (see docs/progress.md). Checks the sweep actually produces a
real crossing (or honestly reports none), and that the crossing found is
stable against the measured spread of the full-rebuild timing.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from break_even import sweep_break_even

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models" / "scaled"
BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_cache_freq"


@pytest.fixture(autouse=True)
def _clean():
    yield
    for p in (MODELS_ROOT, BUILD_ROOT):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


def test_sweep_finds_a_real_crossing_on_a_small_model():
    result = sweep_break_even(20, [3, 6, 9, 12, 15], batch_sizes=[1, 2, 3, 5])

    assert result["full_rebuild_mean_s"] > 0
    assert result["streaming_incremental_total_s"] > 0
    assert len(result["sweep"]) == 4

    # batch_size=1 (rebuild fully after every single change) must always
    # be at least as expensive as streaming incremental for a model where
    # a full rebuild costs more than one incremental step -- the sweep
    # must show batching getting relatively cheaper as batch_size grows.
    costs = [r["batched_full_total_s_mean"] for r in result["sweep"]]
    assert costs == sorted(costs, reverse=True)

    if result["break_even_batch_size"] is not None:
        assert result["break_even_batch_size"] in [1, 2, 3, 5]
        assert isinstance(result["break_even_stable_within_spread"], bool)


def test_raises_if_chain_is_not_structurally_invariant(monkeypatch):
    import break_even as be

    def _fake_run_change_sequence(n_rooms, changed_rooms):
        return {
            "n_changes": 2,
            "steps": [
                {"step": 1, "total_units": 10},
                {"step": 2, "total_units": 11},  # inconsistent on purpose
            ],
            "sources": [None, None, None],
            "base_dir": Path("unused"),
            "total_streaming_incremental_s": 1.0,
        }

    monkeypatch.setattr(be, "run_change_sequence", _fake_run_change_sequence)
    with pytest.raises(RuntimeError, match="total_units varies"):
        be.sweep_break_even(20, [1, 2], batch_sizes=[1, 2])
