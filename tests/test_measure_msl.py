"""Feature 8: ripple and measured (real, repeated) incremental-vs-full
wall-clock speedup on real implicit-equation models, logged to
parquet/CSV with one complete record per model-and-change cell.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from measure_msl import CELLS, log_all_cells

MSL_SRC = Path(__file__).resolve().parent.parent / "msl_src"
pytestmark = pytest.mark.skipif(not MSL_SRC.exists(), reason="msl_src/ not present")

BUILD_CACHE = Path(__file__).resolve().parent.parent / "build_cache_msl"


@pytest.fixture(autouse=True)
def _clean_build_cache():
    if BUILD_CACHE.exists():
        shutil.rmtree(BUILD_CACHE, ignore_errors=True)
    yield
    if BUILD_CACHE.exists():
        shutil.rmtree(BUILD_CACHE, ignore_errors=True)


def test_logs_one_complete_record_per_cell_with_real_measured_speedup():
    df = log_all_cells(out_dir=Path(__file__).resolve().parent.parent / "results")

    assert len(df) == len(CELLS)
    assert df.isnull().values.any() == False  # noqa: E712 -- explicit for clarity

    for _, row in df.iterrows():
        assert row["total_units"] > 0
        assert 0 < row["affected_units"] <= row["total_units"]
        assert row["full_rebuild_mean_s"] > 0
        assert row["incremental_mean_s"] > 0
        assert row["measured_speedup"] > 0
        # This is the real correctness bar: incremental and full outputs
        # from the SAME changed model must be bit-identical.
        assert row["outputs_identical"] == True  # noqa: E712
        assert row["reused_objects_byte_identical_to_cache"] == True  # noqa: E712
