"""Feature 13: real incremental-versus-full-rebuild speedup measured
across a range of model sizes. The automated test here uses a small
size range (kept fast for the regression suite); the real Feature 13
evidence at the sizes reported in the paper is logged separately (see
docs/progress.md) and not re-run on every test invocation.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from measure_scale import log_scale_sweep

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models" / "scaled"


@pytest.fixture(autouse=True)
def _clean():
    yield
    if MODELS_ROOT.exists():
        shutil.rmtree(MODELS_ROOT, ignore_errors=True)


def test_logs_one_complete_record_per_size_with_real_measured_speedup(tmp_path):
    df = log_scale_sweep(sizes=[20, 40], repeats=2, out_dir=tmp_path)

    assert len(df) == 2
    assert df.isnull().values.any() == False  # noqa: E712

    for _, row in df.iterrows():
        assert row["n_equations"] == 3 * row["n_rooms"] - 1
        assert row["total_units"] == row["n_equations"]
        assert row["full_rebuild_mean_s"] > 0
        assert row["incremental_mean_s"] > 0
        assert row["measured_speedup"] > 0
        assert row["outputs_identical"] == True  # noqa: E712
        assert row["reused_objects_byte_identical_to_cache"] == True  # noqa: E712

    assert (tmp_path / "measurements_scale.parquet").exists()
    assert (tmp_path / "measurements_scale.csv").exists()
