"""Feature 14: one-time graph/partition setup overhead versus model
size, expressed relative to a full rebuild. Small automated sizes here;
the reported paper numbers are logged separately (see docs/progress.md).
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from measure_overhead import log_overhead_sweep

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models" / "scaled"


@pytest.fixture(autouse=True)
def _clean():
    yield
    if MODELS_ROOT.exists():
        shutil.rmtree(MODELS_ROOT, ignore_errors=True)


def test_logs_setup_overhead_per_size(tmp_path):
    df = log_overhead_sweep(sizes=[20, 40], out_dir=tmp_path)

    assert len(df) == 2
    for _, row in df.iterrows():
        assert row["rumoca_compile_s"] > 0
        assert row["match_s"] >= 0
        assert row["partition_s"] >= 0
        assert row["graph_s"] >= 0
        assert row["graph_and_partition_s"] == pytest.approx(
            row["match_s"] + row["partition_s"] + row["graph_s"]
        )
        assert row["total_setup_s"] == pytest.approx(row["rumoca_compile_s"] + row["graph_and_partition_s"])

    assert (tmp_path / "measurements_overhead.parquet").exists()
    assert (tmp_path / "measurements_overhead.csv").exists()


def test_ratio_to_full_rebuild_computed_when_scale_log_present(tmp_path):
    import pandas as pd

    scale_df = pd.DataFrame.from_records([
        {"n_rooms": 20, "full_rebuild_mean_s": 2.0},
        {"n_rooms": 40, "full_rebuild_mean_s": 4.0},
    ])
    scale_df.to_csv(tmp_path / "measurements_scale.csv", index=False)

    df = log_overhead_sweep(sizes=[20, 40], out_dir=tmp_path)

    assert "graph_and_partition_over_full_rebuild" in df.columns
    assert "total_setup_over_full_rebuild" in df.columns
    for _, row in df.iterrows():
        assert row["graph_and_partition_over_full_rebuild"] > 0
        assert row["total_setup_over_full_rebuild"] > 0
