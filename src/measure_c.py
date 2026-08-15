"""End-to-end measured incremental-vs-full compile+link experiment
(Section 5, Features M1-M5; Section 7, Feature C1's correctness check
reuses this module's output). Real gcc calls throughout -- no timing is
derived from another timing by arithmetic.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from c_build import (
    fingerprint_objects, full_rebuild, generate_sources, incremental_rebuild,
    repeated_full_rebuild_time, repeated_incremental_rebuild_time, run_sim, write_sources,
)
from causal_graph import build_causalized_graph
from compile import compile_model
from model_layout import build_layout
from resolver import resolve_impact

BUILD_ROOT = Path("build_cache")
REPEATS = 5


def _unit_c_filename(model_name: str, equation_name: str) -> str:
    return f"{model_name}_unit_{equation_name}.c"


def run_cell(baseline_path: str, changed_path: str, model_name: str, seed: list[str], t_end: float, dt: float) -> dict:
    baseline = compile_model(baseline_path, model_name)
    changed = compile_model(changed_path, model_name)

    layout = build_layout(baseline.ir, changed.ir)
    baseline_sources = generate_sources(model_name, baseline.ir, layout)
    changed_sources = generate_sources(model_name, changed.ir, layout)

    cell_dir = BUILD_ROOT / model_name
    baseline_src_dir = cell_dir / "baseline_src"
    changed_src_dir = cell_dir / "changed_src"
    write_sources(baseline_sources, baseline_src_dir)
    write_sources(changed_sources, changed_src_dir)

    # "Cold cache": the pre-existing compiled artifacts for the baseline
    # model, built once, standing in for what a real incremental compiler
    # would already have on disk before the change happens.
    cache_build = full_rebuild(baseline_sources, baseline_src_dir, cell_dir / "cache")

    impact = resolve_impact(changed.ir, seed, graph_builder=build_causalized_graph)
    affected_equations = {eq for unit_id in impact["affected_units"] for eq in impact["units"][unit_id]}
    affected_c_filenames = {_unit_c_filename(model_name, eq) for eq in affected_equations}

    full_times = repeated_full_rebuild_time(changed_sources, changed_src_dir, cell_dir / "full_repeats", REPEATS)
    full_result = full_rebuild(changed_sources, changed_src_dir, cell_dir / "full_reference")

    cached_objects = cache_build.object_paths
    incr_times = repeated_incremental_rebuild_time(
        changed_sources, changed_src_dir, cell_dir / "incr_repeats",
        affected_c_filenames, cached_objects, REPEATS,
    )
    incr_result = incremental_rebuild(
        changed_sources, changed_src_dir, cell_dir / "incr_reference",
        affected_c_filenames, cached_objects,
    )

    # Fingerprint proof: unaffected units' objects in the incremental
    # build must be byte-identical to the cached baseline objects (true
    # reuse, not a recompile that happened to match); affected units'
    # objects must differ from what the baseline had cached.
    cache_fp = fingerprint_objects(cache_build)
    incr_fp = fingerprint_objects(incr_result)
    full_fp = fingerprint_objects(full_result)

    reused_correctly = all(
        incr_fp[c] == cache_fp[c]
        for c in incr_fp if c not in affected_c_filenames and c in cache_fp
    )
    # NOTE: a recompiled unit's object is NOT guaranteed to differ from its
    # cached version -- a unit that references another unit's output only
    # by memory slot (not by inlined value) can recompile to byte-identical
    # machine code even when the thing it depends on changed (e.g.
    # ThermalNetwork's T1 unit: its own C source is unchanged by the Q1
    # swap, so it recompiles identically). The resolver recompiling it
    # anyway is the conservative-and-safe behavior, not a bug -- so this is
    # reported per-file rather than collapsed into one pass/fail boolean.
    affected_object_diff_from_cache = {
        c: incr_fp[c] != cache_fp.get(c) for c in affected_c_filenames if c in cache_fp
    }
    at_least_one_affected_object_differs = any(affected_object_diff_from_cache.values())
    incremental_matches_full_for_unaffected = all(
        incr_fp[c] == full_fp[c] for c in incr_fp if c not in affected_c_filenames
    )

    full_output = run_sim(full_result.exe_path, t_end, dt)
    incr_output = run_sim(incr_result.exe_path, t_end, dt)

    return {
        "model_name": model_name,
        "total_units": impact["total_units"],
        "affected_units": sorted(impact["affected_units"]),
        "affected_c_filenames": sorted(affected_c_filenames),
        "n_units_total": len(changed_sources.unit_files),
        "n_units_recompiled": len(affected_c_filenames),
        "full_rebuild_times_s": full_times,
        "full_rebuild_mean_s": statistics.mean(full_times),
        "full_rebuild_stdev_s": statistics.stdev(full_times) if len(full_times) > 1 else 0.0,
        "incremental_times_s": incr_times,
        "incremental_mean_s": statistics.mean(incr_times),
        "incremental_stdev_s": statistics.stdev(incr_times) if len(incr_times) > 1 else 0.0,
        "measured_speedup": statistics.mean(full_times) / statistics.mean(incr_times),
        "reused_objects_byte_identical_to_cache": reused_correctly,
        "affected_object_diff_from_cache": affected_object_diff_from_cache,
        "at_least_one_affected_object_differs": at_least_one_affected_object_differs,
        "incremental_matches_full_for_unaffected_objects": incremental_matches_full_for_unaffected,
        "full_output": full_output,
        "incremental_output": incr_output,
        "outputs_identical": full_output == incr_output,
    }


if __name__ == "__main__":
    for baseline_path, changed_path, model_name, seed in [
        ("models/rlc_circuit/RLCCircuit.mo", "models/rlc_circuit_swapped/RLCCircuit.mo", "RLCCircuit", ["i"]),
        ("models/thermal_network/ThermalNetwork.mo", "models/thermal_network_swapped/ThermalNetwork.mo",
         "ThermalNetwork", ["Q1"]),
    ]:
        result = run_cell(baseline_path, changed_path, model_name, seed, t_end=5.0, dt=0.5)
        print(f"{model_name}:")
        print(f"  units: {result['n_units_recompiled']}/{result['n_units_total']} recompiled "
              f"({result['affected_c_filenames']})")
        print(f"  full_rebuild: mean={result['full_rebuild_mean_s']*1000:.3f}ms "
              f"stdev={result['full_rebuild_stdev_s']*1000:.3f}ms")
        print(f"  incremental:  mean={result['incremental_mean_s']*1000:.3f}ms "
              f"stdev={result['incremental_stdev_s']*1000:.3f}ms")
        print(f"  measured_speedup={result['measured_speedup']:.2f}x")
        print(f"  reused_byte_identical={result['reused_objects_byte_identical_to_cache']} "
              f"affected_object_diff_from_cache={result['affected_object_diff_from_cache']} "
              f"incremental_matches_full={result['incremental_matches_full_for_unaffected_objects']}")
        print(f"  outputs_identical={result['outputs_identical']}")
