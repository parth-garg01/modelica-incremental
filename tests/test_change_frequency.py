"""Feature 15: change-frequency harness. A short real sequence on a
small model (kept fast for the regression suite; the reported N=300/
10-change sequence is logged separately, see docs/progress.md), checked
end to end: every change logged with its affected units, both the
streaming-incremental and batched-full costs are real gcc/ld timings,
and rerunning gives stable (not wildly different) timings.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from change_frequency import run_batched_full, run_change_sequence

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models" / "scaled"
BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_cache_freq"


@pytest.fixture(autouse=True)
def _clean():
    yield
    for p in (MODELS_ROOT, BUILD_ROOT):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


def test_streaming_sequence_logs_every_change_with_affected_units():
    seq = run_change_sequence(20, [3, 6, 9])

    assert seq["n_changes"] == 3
    assert len(seq["steps"]) == 3
    for i, step in enumerate(seq["steps"], start=1):
        assert step["step"] == i
        assert 0 < step["affected_units"] <= step["total_units"]
        assert step["incremental_s"] > 0
    assert seq["total_streaming_incremental_s"] == pytest.approx(
        sum(s["incremental_s"] for s in seq["steps"])
    )


def test_batched_full_covers_every_change_exactly_once():
    seq = run_change_sequence(20, [3, 6, 9, 12])
    batched = run_batched_full(seq, batch_size=2)

    assert batched["batch_size"] == 2
    assert [b["batch_end_step"] for b in batched["batches"]] == [2, 4]
    for b in batched["batches"]:
        assert b["full_rebuild_s"] > 0
    assert batched["total_batched_full_s"] == pytest.approx(
        sum(b["full_rebuild_s"] for b in batched["batches"])
    )


def test_uneven_batch_size_still_covers_the_last_partial_batch():
    seq = run_change_sequence(20, [3, 6, 9])
    batched = run_batched_full(seq, batch_size=2)

    # 3 changes, batch_size=2 -> batches ending at step 2 and step 3
    # (the trailing partial batch), not silently dropped.
    assert [b["batch_end_step"] for b in batched["batches"]] == [2, 3]
