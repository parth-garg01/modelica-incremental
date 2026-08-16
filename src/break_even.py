"""Feature 16 (Stage B): break-even change frequency. Sweeps batch size
(the natural unit here: "changes accumulated before a rebuild" -- see
src/change_frequency.py's docstring for why frequency and batch size are
the same knob under a fixed-rate arrival model) and finds the crossing
point where periodic full rebuilds (Feature 15's BATCHED strategy) stop
costing more than always incrementally recompiling after every change
(STREAMING).

Real measurements only: the streaming total (src/change_frequency.py's
run_change_sequence) is one real, fixed number that does not depend on
batch size at all -- every one of its K steps is an independently timed
gcc/ld run. The full-rebuild cost used across the batch-size sweep is
measured directly, REPEATED for spread, at one representative point in
the chain -- justified, not assumed, by confirming `total_units` (hence
equation/codegen/compile cost) is IDENTICAL at every step of the chain
(the edits only change a numeric coefficient inside an existing
equation's RHS, never add or remove an equation or variable), which
run_change_sequence's own per-step records already show directly.
"""
from __future__ import annotations

import statistics
import time
from pathlib import Path

from c_build import full_rebuild
from change_frequency import run_change_sequence

FULL_REBUILD_REPEATS = 3


def _repeated_full_rebuild_at_end(seq: dict, repeats: int = FULL_REBUILD_REPEATS) -> list[float]:
    sources = seq["sources"][-1]
    src_dir = seq["base_dir"] / f"step_{seq['n_changes']:02d}" / "src"
    times = []
    for i in range(repeats):
        t0 = time.perf_counter()
        full_rebuild(sources, src_dir, seq["base_dir"] / f"full_repeat_{i}")
        times.append(time.perf_counter() - t0)
    return times


def sweep_break_even(n_rooms: int, changed_rooms: list[int], batch_sizes: list[int]) -> dict:
    seq = run_change_sequence(n_rooms, changed_rooms)
    n_changes = seq["n_changes"]

    total_units_by_step = {s["step"]: s["total_units"] for s in seq["steps"]}
    structurally_invariant = len(set(total_units_by_step.values())) == 1
    if not structurally_invariant:
        raise RuntimeError(
            f"total_units varies across the chain {total_units_by_step}; the "
            "single-full-rebuild-cost assumption behind this sweep does not hold"
        )

    full_times = _repeated_full_rebuild_at_end(seq)
    full_mean = statistics.mean(full_times)
    full_stdev = statistics.stdev(full_times) if len(full_times) > 1 else 0.0

    streaming_total = seq["total_streaming_incremental_s"]

    rows = []
    for b in batch_sizes:
        n_batches = -(-n_changes // b)  # ceil
        batched_mean = n_batches * full_mean
        batched_low = n_batches * max(full_mean - full_stdev, 0.0)
        batched_high = n_batches * (full_mean + full_stdev)
        rows.append({
            "batch_size": b,
            "n_batches": n_batches,
            "batched_full_total_s_mean": batched_mean,
            "batched_full_total_s_low": batched_low,
            "batched_full_total_s_high": batched_high,
            "streaming_incremental_total_s": streaming_total,
            "batched_cheaper_mean": batched_mean < streaming_total,
            "batched_cheaper_worst_case": batched_high < streaming_total,
        })

    crossing = next((r["batch_size"] for r in rows if r["batched_cheaper_mean"]), None)
    crossing_stable = None
    if crossing is not None:
        crossing_stable = next((r["batch_size"] for r in rows if r["batched_cheaper_worst_case"]), None) == crossing

    return {
        "n_rooms": n_rooms,
        "n_changes": n_changes,
        "full_rebuild_mean_s": full_mean,
        "full_rebuild_stdev_s": full_stdev,
        "full_rebuild_repeats": FULL_REBUILD_REPEATS,
        "streaming_incremental_total_s": streaming_total,
        "sweep": rows,
        "break_even_batch_size": crossing,
        "break_even_stable_within_spread": crossing_stable,
    }


def log_break_even_sweep(
    n_rooms: int | None = None, changed_rooms: list[int] | None = None, batch_sizes: list[int] | None = None,
    out_dir: str | Path = "results", result: dict | None = None,
) -> "pd.DataFrame":
    """One row per swept batch size, columns repeated from the top-level
    summary so the figure (Feature 17) can load a single flat table
    without re-deriving the crossing point itself. Pass a precomputed
    `result` (from sweep_break_even) to log without re-running the real
    gcc/ld sweep a second time; otherwise n_rooms/changed_rooms/batch_sizes
    are required and the sweep runs here."""
    import pandas as pd

    if result is None:
        result = sweep_break_even(n_rooms, changed_rooms, batch_sizes)
    records = []
    for r in result["sweep"]:
        records.append({
            "n_rooms": result["n_rooms"],
            "n_changes": result["n_changes"],
            "full_rebuild_mean_s": result["full_rebuild_mean_s"],
            "full_rebuild_stdev_s": result["full_rebuild_stdev_s"],
            "streaming_incremental_total_s": result["streaming_incremental_total_s"],
            "break_even_batch_size": result["break_even_batch_size"],
            "break_even_stable_within_spread": result["break_even_stable_within_spread"],
            **r,
        })

    df = pd.DataFrame.from_records(records)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "measurements_break_even.parquet", index=False)
    df.to_csv(out_dir / "measurements_break_even.csv", index=False)
    return df


if __name__ == "__main__":
    _n_rooms, _changed_rooms, _batch_sizes = 300, [30, 60, 90, 120, 150, 180, 210, 240, 270, 295], [1, 2, 3, 4, 5, 7, 10]
    result = sweep_break_even(_n_rooms, _changed_rooms, batch_sizes=_batch_sizes)
    print(f"n_rooms={result['n_rooms']} n_changes={result['n_changes']}")
    print(f"full_rebuild: {result['full_rebuild_mean_s']:.3f}s +/- {result['full_rebuild_stdev_s']:.3f}s "
          f"({result['full_rebuild_repeats']} repeats)")
    print(f"streaming_incremental_total_s={result['streaming_incremental_total_s']:.3f}s")
    for r in result["sweep"]:
        print(f"  batch_size={r['batch_size']:>2} n_batches={r['n_batches']:>2} "
              f"batched_total_mean={r['batched_full_total_s_mean']:.3f}s "
              f"[{r['batched_full_total_s_low']:.3f}, {r['batched_full_total_s_high']:.3f}] "
              f"cheaper_than_streaming={r['batched_cheaper_mean']}")
    if result["break_even_batch_size"] is not None:
        print(f"\nBREAK-EVEN: batching wins once >= {result['break_even_batch_size']} changes "
              f"accumulate per rebuild (stable within measured spread: {result['break_even_stable_within_spread']})")
    else:
        print(f"\nNo crossing in the tested batch-size range {[r['batch_size'] for r in result['sweep']]} "
              "-- streaming incremental wins throughout; reported honestly, not a fabricated crossing.")

    df = log_break_even_sweep(result=result)
    print(f"\nWrote {len(df)} records to results/measurements_break_even.parquet and results/measurements_break_even.csv")
