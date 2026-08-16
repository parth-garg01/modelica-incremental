"""Feature 14 (Stage B): one-time setup overhead versus model size --
the cost of building the graph and partition (matching + recompilation-
unit partitioning + matched-graph construction for the resolver), paid
ONCE per model regardless of how many changes follow, expressed relative
to a full rebuild so the paper can state whether it stays acceptable at
scale.

Reuses the SAME sizes and generated models as src/measure_scale.py
(Feature 13) so this can be joined against results/measurements_scale.csv
on n_rooms without paying for a second set of expensive full/incremental
rebuild repeats -- this measurement itself is cheap (sub-2s even at
15,000 equations, per docs/findings/scaling-bottlenecks.md), so it is
measured directly rather than reusing old profiling numbers.
"""
from __future__ import annotations

import time
from pathlib import Path

from compile import compile_model
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from matching import compute_matching
from scaled_models import generate_thermal_chain

MODELS_ROOT = Path("models") / "scaled"
OVERHEAD_SIZES = [50, 100, 250, 500, 1000]


def measure_overhead_cell(n_rooms: int) -> dict:
    model_name = f"ThermalChain{n_rooms}"
    path = generate_thermal_chain(n_rooms, MODELS_ROOT / f"{model_name}_overhead" / f"{model_name}.mo")

    t0 = time.perf_counter()
    result = compile_model(str(path), model_name)
    rumoca_compile_s = time.perf_counter() - t0
    ir = result.ir

    t0 = time.perf_counter()
    compute_matching(ir)
    match_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    compute_matched_units(ir)
    partition_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    build_matched_graph(ir)
    graph_s = time.perf_counter() - t0

    graph_and_partition_s = match_s + partition_s + graph_s
    return {
        "model_name": model_name,
        "n_rooms": n_rooms,
        "n_equations": 3 * n_rooms - 1,
        "rumoca_compile_s": rumoca_compile_s,
        "match_s": match_s,
        "partition_s": partition_s,
        "graph_s": graph_s,
        "graph_and_partition_s": graph_and_partition_s,
        "total_setup_s": rumoca_compile_s + graph_and_partition_s,
    }


def log_overhead_sweep(sizes: list[int] = OVERHEAD_SIZES, out_dir: str | Path = "results") -> "pd.DataFrame":
    import pandas as pd

    records = [measure_overhead_cell(n) for n in sizes]
    df = pd.DataFrame.from_records(records)

    scale_path = Path(out_dir) / "measurements_scale.csv"
    if scale_path.exists():
        scale_df = pd.read_csv(scale_path)[["n_rooms", "full_rebuild_mean_s"]]
        df = df.merge(scale_df, on="n_rooms", how="left")
        df["graph_and_partition_over_full_rebuild"] = df["graph_and_partition_s"] / df["full_rebuild_mean_s"]
        df["total_setup_over_full_rebuild"] = df["total_setup_s"] / df["full_rebuild_mean_s"]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "measurements_overhead.parquet", index=False)
    df.to_csv(out_dir / "measurements_overhead.csv", index=False)
    return df


if __name__ == "__main__":
    df = log_overhead_sweep()
    pd_options_set = False
    try:
        import pandas as pd
        pd.set_option("display.width", 200)
        pd.set_option("display.max_columns", 20)
        pd_options_set = True
    except ImportError:
        pass
    print(df.to_string(index=False) if pd_options_set else df)
    print(f"\nWrote {len(df)} records to results/measurements_overhead.parquet and results/measurements_overhead.csv")
