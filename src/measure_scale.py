"""Feature 13 (Stage B): real incremental-versus-full-rebuild wall-clock
speedup measured ACROSS A RANGE OF MODEL SIZES, not just the fixed-size
real-MSL cells src/measure_msl.py's CELLS covers. Reuses run_cell()
unchanged (it is already model-agnostic); the only new thing here is the
sweep over src/scaled_models.py's generated ThermalChain{N}.

Size range and repeat count are deliberately scoped, not maximal: per
docs/findings/scaling-bottlenecks.md's own guidance, a repeated-
measurement cell (multiple full AND incremental rebuilds each) needs to
complete in tens of seconds to a few minutes to be affordable across
several sizes in one run. Calibrated directly before picking the range:
one N=1000 cell (2,999 equations) at 3 repeats took 470.9s wall-clock
end to end. REPEATS=3 (not measure_msl.py's REPEATS=5) is the deliberate
trade against total sweep time; still real repetition with a real
(if smaller) spread, not a single sample dressed up as a mean.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from measure_msl import run_cell
from scaled_models import generate_thermal_chain, swap_room_conductance

MODELS_ROOT = Path("models") / "scaled"
SCALE_SIZES = [50, 100, 250, 500, 1000]  # rooms; equations = 3*n - 1
SCALE_REPEATS = 3


def run_scale_cell(n_rooms: int, repeats: int = SCALE_REPEATS) -> dict:
    model_name = f"ThermalChain{n_rooms}"
    mid = n_rooms // 2
    base_path = generate_thermal_chain(
        n_rooms, MODELS_ROOT / f"{model_name}_scale" / f"{model_name}.mo"
    )
    chg_path = swap_room_conductance(
        base_path, mid, MODELS_ROOT / f"{model_name}_scale_swapped" / f"{model_name}.mo"
    )
    result = run_cell(str(base_path), str(chg_path), model_name, [f"Q{mid}env"], 2.0, 1.0, repeats=repeats)
    result["n_rooms"] = n_rooms
    result["n_equations"] = 3 * n_rooms - 1
    result["repeats"] = repeats
    return result


def log_scale_sweep(sizes: list[int] = SCALE_SIZES, repeats: int = SCALE_REPEATS, out_dir: str | Path = "results") -> "pd.DataFrame":
    import pandas as pd

    records = []
    for n in sizes:
        result = run_scale_cell(n, repeats=repeats)
        records.append({
            "model_name": result["model_name"],
            "n_rooms": result["n_rooms"],
            "n_equations": result["n_equations"],
            "total_units": result["total_units"],
            "affected_units": result["affected_units"],
            "affected_fraction": result["affected_fraction"],
            "repeats": result["repeats"],
            "full_rebuild_mean_s": result["full_rebuild_mean_s"],
            "full_rebuild_stdev_s": result["full_rebuild_stdev_s"],
            "incremental_mean_s": result["incremental_mean_s"],
            "incremental_stdev_s": result["incremental_stdev_s"],
            "measured_speedup": result["measured_speedup"],
            "reused_objects_byte_identical_to_cache": result["reused_objects_byte_identical_to_cache"],
            "incremental_matches_full_for_unaffected_objects": result["incremental_matches_full_for_unaffected_objects"],
            "outputs_identical": result["outputs_identical"],
        })

    df = pd.DataFrame.from_records(records)
    required = list(records[0].keys())
    if df[required].isnull().any().any():
        raise RuntimeError("a required metric is missing for at least one size; refusing to log an incomplete record")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "measurements_scale.parquet", index=False)
    df.to_csv(out_dir / "measurements_scale.csv", index=False)
    return df


if __name__ == "__main__":
    df = log_scale_sweep()
    pd_options_set = False
    try:
        import pandas as pd
        pd.set_option("display.width", 200)
        pd.set_option("display.max_columns", 20)
        pd_options_set = True
    except ImportError:
        pass
    print(df.to_string(index=False) if pd_options_set else df)
    print(f"\nWrote {len(df)} records to results/measurements_scale.parquet and results/measurements_scale.csv")
