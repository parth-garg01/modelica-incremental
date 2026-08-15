"""Measure ripple and compute the projected speedup ceiling for each
model-and-change cell. Full compile time is repeated and its spread
reported, not a single sample. The speedup ceiling is a projection --
1 / affected_fraction -- not a measured incremental runtime; there is no
working incremental compiler in this study (see prd.md Section 2).
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import pandas as pd

from compile import compile_model, provenance
from resolver import resolve_impact

REPEATS = 7

# Each cell: (baseline model, changed model, model class, change type, seed equations)
CELLS = [
    (
        "models/rlc_circuit/RLCCircuit.mo",
        "models/rlc_circuit_swapped/RLCCircuit.mo",
        "RLCCircuit",
        "component_swap",
        ["i"],
    ),
    (
        "models/thermal_network/ThermalNetwork.mo",
        "models/thermal_network_swapped/ThermalNetwork.mo",
        "ThermalNetwork",
        "component_swap",
        ["Q1"],
    ),
]


def measure_cell(baseline_path: str, changed_path: str, model_name: str, change_type: str, seed: list[str]) -> dict:
    compile_times = []
    changed_result = None
    for _ in range(REPEATS):
        changed_result = compile_model(changed_path, model_name)
        compile_times.append(changed_result.compile_seconds)

    impact = resolve_impact(changed_result.ir, seed)
    total_units = impact["total_units"]
    affected_units = len(impact["affected_units"])
    affected_fraction = affected_units / total_units

    return {
        "model_name": model_name,
        "change_type": change_type,
        "seed_equations": ",".join(seed),
        "total_units": total_units,
        "affected_units": affected_units,
        "affected_fraction": affected_fraction,
        "projected_speedup_ceiling": 1.0 / affected_fraction,
        "compile_time_mean_s": statistics.mean(compile_times),
        "compile_time_stdev_s": statistics.stdev(compile_times) if len(compile_times) > 1 else 0.0,
        "compile_time_min_s": min(compile_times),
        "compile_time_max_s": max(compile_times),
        "compile_repeats": REPEATS,
        "baseline_path": baseline_path,
        "changed_path": changed_path,
    }


def main() -> None:
    records = [measure_cell(*cell) for cell in CELLS]
    df = pd.DataFrame.from_records(records)

    required_cols = [
        "model_name", "change_type", "total_units", "affected_units",
        "affected_fraction", "projected_speedup_ceiling",
        "compile_time_mean_s", "compile_time_stdev_s",
    ]
    if df[required_cols].isnull().any().any():
        raise RuntimeError("a required metric is missing for at least one cell; refusing to log an incomplete record")

    out_dir = Path("results")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "measurements.parquet", index=False)
    df.to_csv(out_dir / "measurements.csv", index=False)

    (out_dir / "measurements_provenance.json").write_text(
        json.dumps(provenance(), indent=2), encoding="utf-8"
    )

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    print(df[required_cols].to_string(index=False))
    print(f"\nWrote {len(df)} records to results/measurements.parquet and results/measurements.csv")


if __name__ == "__main__":
    main()
