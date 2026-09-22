"""Phase 1 (journal-upgrade): stage-by-stage profiling of the dynamic-link
incremental rebuild at a given model size, isolating the copy-of-cached-DLLs
loop (currently un-instrumented inside c_build.incremental_rebuild_dynamic)
from DLL recompilation and driver relink -- built to diagnose the
N=5,000/14,999-equation speedup anomaly in results/measurements_validate_scale.csv
(3.33x, far below the trend the smaller sizes establish).

Does not modify c_build.py: reimplements the copy loop standalone here,
timed in isolation, and cross-checks its sum against a real
incremental_rebuild_dynamic() call so nothing is double-counted or missed.

Writes results/journal_upgrade_phase1_profile.csv -- a NEW file, does not
touch any existing results/*.csv.
"""
from __future__ import annotations

import shutil
import statistics
import time
from pathlib import Path

from c_build import (
    BuildSources, compile_c, full_rebuild_dynamic, incremental_rebuild_dynamic,
    link_driver_only, build_dlls_many, write_sources,
)
from compile import compile_model
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from model_layout import build_layout
from resolver import resolve_impact
from unit_codegen import generate_all_unit_sources, generate_unit_driver_dynamic, unit_function_suffix
from codegen_units import generate_header
from scaled_models import generate_thermal_chain, swap_room_conductance

MODELS_ROOT = Path("models") / "scaled_profile"
BUILD_ROOT = Path("build_cache_profile")


def _as_build_sources(model_name: str, ir: dict, layout) -> BuildSources:
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


def time_copy_only(unit_files: dict, cached_objects: dict, affected: set, build_dir: Path) -> float:
    """Times ONLY the shutil.copyfile loop over unaffected units -- the
    exact loop body inside c_build.incremental_rebuild_dynamic(), extracted
    standalone so its own wall time is visible, not folded into the total."""
    build_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    n_copied = 0
    for c_filename in unit_files:
        if c_filename in affected:
            continue
        dll_path = build_dir / (Path(c_filename).stem + ".dll")
        shutil.copyfile(cached_objects[c_filename], dll_path)
        n_copied += 1
    elapsed = time.perf_counter() - t0
    return elapsed, n_copied


def profile_one_size(n_rooms: int, repeats_copy: int = 3) -> dict:
    model_name = f"ThermalChainProfile{n_rooms}"
    mid = n_rooms // 2
    base_path = generate_thermal_chain(n_rooms, MODELS_ROOT / f"{model_name}_base" / f"{model_name}.mo")
    chg_path = swap_room_conductance(base_path, mid, MODELS_ROOT / f"{model_name}_chg" / f"{model_name}.mo")

    print(f"[{model_name}] compiling baseline+changed via Rumoca...", flush=True)
    t0 = time.perf_counter()
    baseline = compile_model(str(base_path), model_name)
    t_compile_baseline = time.perf_counter() - t0
    t0 = time.perf_counter()
    changed = compile_model(str(chg_path), model_name)
    t_compile_changed = time.perf_counter() - t0
    print(f"  rumoca compile: baseline={t_compile_baseline:.2f}s changed={t_compile_changed:.2f}s", flush=True)

    t0 = time.perf_counter()
    layout = build_layout(baseline.ir, changed.ir)
    baseline_sources = _as_build_sources(model_name, baseline.ir, layout)
    changed_sources = _as_build_sources(model_name, changed.ir, layout)
    t_graph = time.perf_counter() - t0
    print(f"  layout+codegen-source-build: {t_graph:.2f}s", flush=True)

    cell_dir = BUILD_ROOT / model_name
    baseline_src_dir = cell_dir / "baseline_src"
    changed_src_dir = cell_dir / "changed_src"
    write_sources(baseline_sources, baseline_src_dir)
    write_sources(changed_sources, changed_src_dir)

    print(f"  building baseline cache (full_rebuild_dynamic, {len(baseline_sources.unit_files)} units)...", flush=True)
    t0 = time.perf_counter()
    cache_build = full_rebuild_dynamic(baseline_sources, baseline_src_dir, cell_dir / "cache")
    t_cache_build = time.perf_counter() - t0
    print(f"  cache build: {t_cache_build:.2f}s", flush=True)

    impact = resolve_impact(changed.ir, [f"Q{mid}env"], graph_builder=build_matched_graph)
    affected_c_filenames = _affected_c_filenames(model_name, changed.ir, impact)
    total_units = impact["total_units"]
    n_affected = len(impact["affected_units"])
    print(f"  impact: {n_affected}/{total_units} units affected", flush=True)

    cached_objects = cache_build.object_paths

    # --- Stage 1: full end-to-end incremental_rebuild_dynamic(), as the
    # existing harness measures it, for a ground-truth total. ---
    print("  timing one full incremental_rebuild_dynamic() call (end-to-end, ground truth)...", flush=True)
    t0 = time.perf_counter()
    incr_result = incremental_rebuild_dynamic(
        changed_sources, changed_src_dir, cell_dir / "incr_e2e", affected_c_filenames, cached_objects,
    )
    t_incr_e2e = time.perf_counter() - t0
    print(f"  end-to-end incremental_rebuild_dynamic: {t_incr_e2e:.2f}s", flush=True)

    # --- Stage 2: decompose the SAME operation into its parts, each timed
    # separately, in a fresh build dir, to attribute the total. ---
    print("  decomposing: DLL recompile of affected units only...", flush=True)
    decomp_dir = cell_dir / "incr_decomp"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for c_filename in changed_sources.unit_files:
        if c_filename in affected_c_filenames:
            dll_path = decomp_dir / (Path(c_filename).stem + ".dll")
            jobs.append((changed_src_dir / c_filename, dll_path))
    t0 = time.perf_counter()
    build_dlls_many(jobs)
    t_recompile_affected = time.perf_counter() - t0
    print(f"    recompile affected DLLs ({len(jobs)}): {t_recompile_affected:.2f}s", flush=True)

    copy_times = []
    for i in range(repeats_copy):
        rep_dir = cell_dir / f"incr_decomp_copy_{i}"
        t_copy, n_copied = time_copy_only(changed_sources.unit_files, cached_objects, affected_c_filenames, rep_dir)
        copy_times.append(t_copy)
        print(f"    copy-only pass {i}: {t_copy:.2f}s ({n_copied} files)", flush=True)
        shutil.rmtree(rep_dir, ignore_errors=True)

    print("  decomposing: driver compile + link...", flush=True)
    driver_name, _ = changed_sources.driver_file
    driver_o = decomp_dir / (Path(driver_name).stem + ".o")
    t0 = time.perf_counter()
    compile_c(changed_src_dir / driver_name, driver_o)
    t_driver_compile = time.perf_counter() - t0
    exe_path = decomp_dir / f"{model_name}_incr_decomp.exe"
    t0 = time.perf_counter()
    link_driver_only(driver_o, exe_path)
    t_driver_link = time.perf_counter() - t0
    print(f"    driver compile={t_driver_compile:.2f}s link={t_driver_link:.2f}s", flush=True)

    copy_mean = statistics.mean(copy_times)
    copy_stdev = statistics.stdev(copy_times) if len(copy_times) > 1 else 0.0
    decomposed_sum = t_recompile_affected + copy_mean + t_driver_compile + t_driver_link

    return {
        "n_rooms": n_rooms,
        "n_equations": 3 * n_rooms - 1,
        "total_units": total_units,
        "affected_units": n_affected,
        "rumoca_compile_baseline_s": t_compile_baseline,
        "rumoca_compile_changed_s": t_compile_changed,
        "layout_codegen_build_s": t_graph,
        "cache_build_full_rebuild_s": t_cache_build,
        "incr_end_to_end_s": t_incr_e2e,
        "incr_recompile_affected_s": t_recompile_affected,
        "incr_copy_cached_mean_s": copy_mean,
        "incr_copy_cached_stdev_s": copy_stdev,
        "incr_copy_cached_all_s": copy_times,
        "incr_driver_compile_s": t_driver_compile,
        "incr_driver_link_s": t_driver_link,
        "decomposed_sum_s": decomposed_sum,
        "unaccounted_s": t_incr_e2e - decomposed_sum,
        "copy_fraction_of_e2e": copy_mean / t_incr_e2e if t_incr_e2e else float("nan"),
    }


if __name__ == "__main__":
    import sys
    import json

    sizes = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [50]
    records = []
    for n in sizes:
        print(f"=== profiling N={n} rooms ({3*n-1} equations) ===", flush=True)
        rec = profile_one_size(n)
        records.append(rec)
        print(json.dumps(rec, indent=2, default=str), flush=True)

    import pandas as pd
    df = pd.DataFrame.from_records(records)
    out = Path("results") / "journal_upgrade_phase1_profile.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    # append if file exists (allows running different sizes in separate invocations)
    if out.exists():
        old = pd.read_csv(out)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(out, index=False)
    print(f"\nWrote {len(records)} record(s) to {out}")
