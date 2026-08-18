"""Priority 2 (relink-ceiling follow-up): push the FULL detect-resolve-
recompile-relink-bit-diff pipeline's correctness verification to larger
model sizes than Feature 11's automated N=100 / one-off N=500 reached,
now that the dynamic-link build (src/c_build.py's full_rebuild_dynamic()/
incremental_rebuild_dynamic()) has removed relinking as the dominant
incremental cost -- making a correctness-only run (no repeats needed,
one full + one incremental build, bit-diffed) at a given size cheaper
than it was under the old always-relink-everything design.

Reuses src/measure_msl.py's run_cell() with repeats=1 unchanged -- the
SAME bit-identical and byte-identical-object-reuse checks every other
measurement in this project is held to, not a new or weaker check
invented for this script. Only reports sizes actually run to completion;
never guesses or extrapolates a result for a size not reached.
"""
from __future__ import annotations

import time
from pathlib import Path

from measure_msl import run_cell
from scaled_models import generate_thermal_chain, swap_room_conductance

MODELS_ROOT = Path("models") / "scaled"
DEFAULT_SIZES = [2000, 5000, 10000]


def validate_one_size(n_rooms: int) -> dict:
    model_name = f"ThermalChain{n_rooms}"
    mid = n_rooms // 2
    base_path = generate_thermal_chain(n_rooms, MODELS_ROOT / f"{model_name}_validate" / f"{model_name}.mo")
    chg_path = swap_room_conductance(
        base_path, mid, MODELS_ROOT / f"{model_name}_validate_swapped" / f"{model_name}.mo"
    )

    t0 = time.perf_counter()
    result = run_cell(str(base_path), str(chg_path), model_name, [f"Q{mid}env"], 2.0, 1.0, repeats=1)
    elapsed = time.perf_counter() - t0

    return {
        "n_rooms": n_rooms,
        "n_equations": 3 * n_rooms - 1,
        "total_units": result["total_units"],
        "affected_units": result["affected_units"],
        "affected_fraction": result["affected_fraction"],
        "full_rebuild_s": result["full_rebuild_mean_s"],
        "incremental_s": result["incremental_mean_s"],
        "measured_speedup": result["measured_speedup"],
        "outputs_identical": result["outputs_identical"],
        "reused_objects_byte_identical_to_cache": result["reused_objects_byte_identical_to_cache"],
        "incremental_matches_full_for_unaffected_objects": result["incremental_matches_full_for_unaffected_objects"],
        "wall_clock_s": elapsed,
    }


def validate_sizes(sizes: list[int] = DEFAULT_SIZES, out_dir: str | Path = "results") -> "pd.DataFrame":
    """Runs sizes in ASCENDING order and stops at the first one that
    fails to complete or fails bit-identical, reporting everything
    reached so far rather than raising and losing prior results --
    the honest largest-size-that-runs-cleanly report the project's own
    standing rule calls for."""
    import pandas as pd

    records = []
    for n in sizes:
        print(f"validating N={n} ({3*n-1} equations)...", flush=True)
        try:
            record = validate_one_size(n)
        except Exception as e:
            print(f"  N={n} did not complete: {e}")
            break
        records.append(record)
        status = "OK" if record["outputs_identical"] and record["reused_objects_byte_identical_to_cache"] else "FAILED"
        print(f"  N={n}: {status}, wall_clock={record['wall_clock_s']:.1f}s, speedup={record['measured_speedup']:.2f}x")
        if status == "FAILED":
            break

    if not records:
        raise RuntimeError("no size completed even the smallest requested validation cell")

    df = pd.DataFrame.from_records(records)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "measurements_validate_scale.csv", index=False)
    df.to_parquet(out_dir / "measurements_validate_scale.parquet", index=False)
    return df


if __name__ == "__main__":
    import sys

    sizes = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_SIZES
    df = validate_sizes(sizes)
    print(f"\nLargest size verified bit-identical: N={int(df['n_rooms'].max())} "
          f"({int(df['n_equations'].max())} equations)")
    print(f"Wrote {len(df)} records to results/measurements_validate_scale.csv")
