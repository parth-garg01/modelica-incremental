"""Feature 8: measured ripple and real incremental-vs-full-rebuild
wall-clock speedup, generalized to work on ANY model (real MSL or
hand-written) via src/unit_codegen.py's per-UNIT (not per-equation)
codegen and src/matched_graph.py's matching-based resolver -- the
combination Feature 7 validated soundness on. src/measure_c.py (Stage 0)
is narrower: it predates Feature 2's coupled-block units and Feature 1's
real-model matching, so it only ever worked on singleton-only,
fully-assignment-form models. This module supersedes it for anything
past Feature 4.

Real gcc calls throughout, repeated with the spread reported -- no
timing derived from another timing by arithmetic.

Relink-ceiling fix: run_cell() builds via the DYNAMIC-LINK path
(src/c_build.py's full_rebuild_dynamic()/incremental_rebuild_dynamic(),
src/unit_codegen.py's generate_unit_driver_dynamic()) -- every unit is
its own .dll, loaded at runtime, so an incremental rebuild's link cost
no longer scales with the total unit count. The old static-link path
(full_rebuild()/incremental_rebuild(), one flat .exe, always relinked)
is kept in src/c_build.py unchanged, still used by src/measure_c.py's
Stage-0 regression path -- see that module and docs/findings/
scaling-bottlenecks.md Bottleneck 4 for the "before" measurements this
fix responds to.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from c_build import (
    BuildSources, fingerprint_objects, full_rebuild_dynamic, incremental_rebuild_dynamic,
    repeated_full_rebuild_time_dynamic, repeated_incremental_rebuild_time_dynamic, run_sim, write_sources,
)
from compile import compile_model
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from matching import compute_matching
from model_layout import build_layout
from resolver import resolve_impact
from unit_codegen import generate_all_unit_sources, generate_unit_driver_dynamic, unit_function_suffix

BUILD_ROOT = Path("build_cache_msl")
REPEATS = 5


def _as_build_sources(model_name: str, ir: dict, layout) -> BuildSources:
    from codegen_units import generate_header

    return BuildSources(
        model_name=model_name,
        layout=layout,
        unit_files=generate_all_unit_sources(model_name, ir, layout),
        driver_file=(f"{model_name}_driver.c", generate_unit_driver_dynamic(model_name, ir, layout)),
        header_file=(f"{model_name}.h", generate_header(model_name, layout)),
    )


def _affected_c_filenames(model_name: str, changed_ir: dict, impact: dict) -> set[str]:
    units = compute_matched_units(changed_ir)
    filenames = set()
    for unit_id in impact["affected_units"]:
        members = units[unit_id]
        suffix = unit_function_suffix(unit_id, members)
        filenames.add(f"{model_name}_unit_{suffix}.c")
    return filenames


def run_cell(
    baseline_path: str, changed_path: str, model_name: str, seed: list[str],
    t_end: float, dt: float, baseline_roots: list[str] | None = None,
    changed_roots: list[str] | None = None, repeats: int = REPEATS,
) -> dict:
    # Separate roots per compile: a root pointing at the OTHER variant's
    # directory would make the session see two files both defining class
    # `model_name` (a real "duplicate class" compile error, hit during
    # development when both baseline and changed shared one roots list).
    baseline = compile_model(baseline_path, model_name, roots=baseline_roots)
    changed = compile_model(changed_path, model_name, roots=changed_roots)

    layout = build_layout(baseline.ir, changed.ir)
    baseline_sources = _as_build_sources(model_name, baseline.ir, layout)
    changed_sources = _as_build_sources(model_name, changed.ir, layout)

    cell_dir = BUILD_ROOT / model_name
    baseline_src_dir = cell_dir / "baseline_src"
    changed_src_dir = cell_dir / "changed_src"
    write_sources(baseline_sources, baseline_src_dir)
    write_sources(changed_sources, changed_src_dir)

    cache_build = full_rebuild_dynamic(baseline_sources, baseline_src_dir, cell_dir / "cache")

    impact = resolve_impact(changed.ir, seed, graph_builder=build_matched_graph)
    affected_c_filenames = _affected_c_filenames(model_name, changed.ir, impact)

    full_times = repeated_full_rebuild_time_dynamic(changed_sources, changed_src_dir, cell_dir / "full_repeats", repeats)
    full_result = full_rebuild_dynamic(changed_sources, changed_src_dir, cell_dir / "full_reference")

    cached_objects = cache_build.object_paths
    incr_times = repeated_incremental_rebuild_time_dynamic(
        changed_sources, changed_src_dir, cell_dir / "incr_repeats",
        affected_c_filenames, cached_objects, repeats,
    )
    incr_result = incremental_rebuild_dynamic(
        changed_sources, changed_src_dir, cell_dir / "incr_reference",
        affected_c_filenames, cached_objects,
    )

    cache_fp = fingerprint_objects(cache_build)
    incr_fp = fingerprint_objects(incr_result)
    full_fp = fingerprint_objects(full_result)

    reused_correctly = all(
        incr_fp[c] == cache_fp[c]
        for c in incr_fp if c not in affected_c_filenames and c in cache_fp
    )
    incremental_matches_full_for_unaffected = all(
        incr_fp[c] == full_fp[c] for c in incr_fp if c not in affected_c_filenames
    )

    full_output = run_sim(full_result.exe_path, t_end, dt)
    incr_output = run_sim(incr_result.exe_path, t_end, dt)

    total_units = impact["total_units"]
    n_affected = len(impact["affected_units"])

    return {
        "model_name": model_name,
        "total_units": total_units,
        "affected_units": n_affected,
        "affected_fraction": n_affected / total_units,
        "n_units_recompiled": len(affected_c_filenames),
        "full_rebuild_times_s": full_times,
        "full_rebuild_mean_s": statistics.mean(full_times),
        "full_rebuild_stdev_s": statistics.stdev(full_times) if len(full_times) > 1 else 0.0,
        "incremental_times_s": incr_times,
        "incremental_mean_s": statistics.mean(incr_times),
        "incremental_stdev_s": statistics.stdev(incr_times) if len(incr_times) > 1 else 0.0,
        "measured_speedup": statistics.mean(full_times) / statistics.mean(incr_times),
        "reused_objects_byte_identical_to_cache": reused_correctly,
        "incremental_matches_full_for_unaffected_objects": incremental_matches_full_for_unaffected,
        "outputs_identical": full_output == incr_output,
    }


CELLS = [
    dict(
        baseline_path="models/msl_rc_circuit/MslRcCircuit.mo",
        changed_path="models/msl_rc_circuit_swapped/MslRcCircuit.mo",
        model_name="MslRcCircuit", seed=["R.G_actual", "R.i"],
        baseline_roots=["msl_src", "models/msl_rc_circuit"],
        changed_roots=["msl_src", "models/msl_rc_circuit_swapped"], t_end=3.0, dt=0.5,
    ),
    dict(
        # Priority 3: broadening the real-model corpus beyond the
        # electrical domain -- Modelica.Thermal.HeatTransfer, the same
        # component-swap change type (ThermalConductor -> ThermalResistor
        # is the thermal-domain dual of Resistor -> Conductor above),
        # same connect()-wired-component generality claim, a different
        # physical domain entirely.
        baseline_path="models/msl_thermal_chain/MslThermalChain.mo",
        changed_path="models/msl_thermal_chain_swapped/MslThermalChain.mo",
        model_name="MslThermalChain", seed=["G1.Q_flow", "G1.dT"],
        baseline_roots=["msl_src", "models/msl_thermal_chain"],
        changed_roots=["msl_src", "models/msl_thermal_chain_swapped"], t_end=3.0, dt=0.5,
    ),
    dict(
        baseline_path="models/msl_rc_circuit/MslRcCircuit.mo",
        changed_path="models/msl_rc_circuit_sensor/MslRcCircuit.mo",
        model_name="MslRcCircuit", seed=["P_R"],
        baseline_roots=["msl_src", "models/msl_rc_circuit"],
        changed_roots=["msl_src", "models/msl_rc_circuit_sensor"], t_end=3.0, dt=0.5,
    ),
    dict(
        baseline_path="models/msl_resistor_network/MslResistorNetwork.mo",
        changed_path="models/msl_resistor_network_removed/MslResistorNetwork.mo",
        model_name="MslResistorNetwork", seed=["G.p.i", "R1.p.i", "V.n.v"],
        baseline_roots=["msl_src", "models/msl_resistor_network"],
        changed_roots=["msl_src", "models/msl_resistor_network_removed"], t_end=1.0, dt=1.0,
    ),
]


def log_all_cells(out_dir: str | Path = "results") -> "pd.DataFrame":
    import pandas as pd

    records = []
    for cell in CELLS:
        result = run_cell(
            cell["baseline_path"], cell["changed_path"], cell["model_name"], cell["seed"],
            cell["t_end"], cell["dt"], baseline_roots=cell["baseline_roots"], changed_roots=cell["changed_roots"],
        )
        records.append({
            "model_name": result["model_name"],
            "seed": ",".join(cell["seed"]),
            "total_units": result["total_units"],
            "affected_units": result["affected_units"],
            "affected_fraction": result["affected_fraction"],
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
        raise RuntimeError("a required metric is missing for at least one cell; refusing to log an incomplete record")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "measurements_msl.parquet", index=False)
    df.to_csv(out_dir / "measurements_msl.csv", index=False)
    return df


if __name__ == "__main__":
    df = log_all_cells()
    pd_options_set = False
    try:
        import pandas as pd
        pd.set_option("display.width", 200)
        pd.set_option("display.max_columns", 20)
        pd_options_set = True
    except ImportError:
        pass
    print(df.to_string(index=False) if pd_options_set else df)
    print(f"\nWrote {len(df)} records to results/measurements_msl.parquet and results/measurements_msl.csv")
