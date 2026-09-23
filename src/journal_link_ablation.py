"""Controlled link-strategy ablation (journal upgrade, parallel worker).

The paper tells the scaling story as a before/after fix: static linking
plateaued at 1.8x-2.3x, then dynamic linking + DLL stripping + a discarded
warm-up rebuild gave 5.66x-27.01x. Those numbers came from different runs
on different days. This script re-measures the build configurations in one
session, same machine, same models, same change:

  static            : per-unit .o, relink every object into one .exe
                      (c_build.full_rebuild / c_build.incremental_rebuild, unchanged)
  dynamic_unstripped: per-unit .dll built with plain `gcc -shared`. RECONSTRUCTION:
                      this variant was never committed; it is c_build's dynamic path
                      with the strip/gc-sections/no-timestamp flags removed.
  dynamic_stripped  : the current design (c_build.full_rebuild_dynamic /
                      incremental_rebuild_dynamic, unchanged)

Warm-up is a measurement policy, not a build change: every config runs
1 + REPEATS interleaved full/incremental pairs (src/journal_parallel_timing.py)
and both "first discarded" and "all" statistics are stored.

Configs run in a rotated order per size to spread slow drift across configs.
Output: results/journal_upgrade/link_ablation_parallel/link_ablation.csv
Usage: python -u src/journal_link_ablation.py [sizes...]   (default 100 500 1000)
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import c_build
from c_build import (
    BuildResult, BuildSources, GCC, _run_timed, compile_c, full_rebuild, full_rebuild_dynamic,
    incremental_rebuild, incremental_rebuild_dynamic, link_driver_only, write_sources,
)
from codegen_units import generate_header
from compile import compile_model
from journal_parallel_timing import timed_pairs, wait_until_idle
from matched_graph import build_matched_graph
from measure_msl import _affected_c_filenames
from model_layout import build_layout
from resolver import resolve_impact
from scaled_models import generate_thermal_chain, swap_room_conductance
from unit_codegen import generate_all_unit_sources, generate_unit_driver, generate_unit_driver_dynamic

MODELS_ROOT = Path("models") / "journal_link_parallel"
BUILD_ROOT = Path("build_cache_journal_link_parallel")
OUT_CSV = Path("results") / "journal_upgrade" / "link_ablation_parallel" / "link_ablation.csv"
CONFIGS = ["static", "dynamic_unstripped", "dynamic_stripped"]


def _build_dll_unstripped(c_path: Path, dll_path: Path) -> float:
    c_path, dll_path = c_path.resolve(), dll_path.resolve()
    return _run_timed([GCC, "-shared", str(c_path), "-o", str(dll_path)], cwd=c_path.parent)


def _dlls_many(jobs):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=c_build._MAX_WORKERS) as pool:
        for f in [pool.submit(_build_dll_unstripped, c, d) for c, d in jobs]:
            f.result()


def _unstripped(sources: BuildSources, src_dir: Path, build_dir: Path, affected=None, cached=None) -> BuildResult:
    """Mirror of c_build.full_rebuild_dynamic (affected=None) / incremental_rebuild_dynamic."""
    build_dir.mkdir(parents=True, exist_ok=True)
    paths, jobs = {}, []
    for c in sources.unit_files:
        p = build_dir / (Path(c).stem + ".dll")
        paths[c] = p
        if affected is None or c in affected:
            jobs.append((src_dir / c, p))
        else:
            shutil.copyfile(cached[c], p)
    _dlls_many(jobs)
    driver_o = build_dir / (Path(sources.driver_file[0]).stem + ".o")
    compile_c(src_dir / sources.driver_file[0], driver_o)
    exe = build_dir / f"{sources.model_name}_{'full' if affected is None else 'incremental'}.exe"
    return BuildResult(exe, paths, {}, link_driver_only(driver_o, exe))


def ops(config: str):
    """(full, incr, dynamic_driver?) for a config."""
    if config == "static":
        return full_rebuild, incremental_rebuild, False
    if config == "dynamic_stripped":
        return full_rebuild_dynamic, incremental_rebuild_dynamic, True
    return _unstripped, _unstripped, True


def build_sources(model_name, ir, layout, dynamic: bool) -> BuildSources:
    driver = generate_unit_driver_dynamic(model_name, ir, layout) if dynamic else generate_unit_driver(model_name, ir, layout)
    return BuildSources(model_name, layout, generate_all_unit_sources(model_name, ir, layout),
                        (f"{model_name}_driver.c", driver), (f"{model_name}.h", generate_header(model_name, layout)))


def run_config(config, cell: Path, baseline_ir, changed_ir, layout, seed, model_name,
               t_end=2.0, dt=1.0) -> dict:
    """Cache build of the baseline, then the timed interleaved pairs on the changed model."""
    full, incr, dynamic = ops(config)
    shutil.rmtree(cell, ignore_errors=True)
    bsrc, csrc = build_sources(model_name, baseline_ir, layout, dynamic), build_sources(model_name, changed_ir, layout, dynamic)
    bdir, cdir = cell / "baseline_src", cell / "changed_src"
    write_sources(bsrc, bdir)
    write_sources(csrc, cdir)
    t0 = time.perf_counter()
    cache = full(bsrc, bdir, cell / "cache")
    cache_build_s = time.perf_counter() - t0
    impact = resolve_impact(changed_ir, seed, graph_builder=build_matched_graph)
    affected = _affected_c_filenames(model_name, changed_ir, impact)
    cache_bytes = sum(p.stat().st_size for p in (cell / "cache").iterdir() if p.is_file())
    rec = {"config": config, "model_name": model_name, "seed": ",".join(seed),
           "total_units": impact["total_units"], "affected_units": len(impact["affected_units"]),
           "cache_build_s": cache_build_s, "cache_bytes": cache_bytes}
    rec.update(timed_pairs(full, incr, csrc, cdir, cell, affected, cache, bsrc, t_end, dt))
    shutil.rmtree(cell, ignore_errors=True)  # keep disk bounded; raw numbers are in the CSV
    return rec


def append_row(rec: dict, out_csv: Path) -> None:
    import pandas as pd
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([rec])
    if out_csv.exists():
        df = pd.concat([pd.read_csv(out_csv), df], ignore_index=True)
    df.to_csv(out_csv, index=False)  # append per cell: partial results survive a crash


def run_size(n_rooms: int, rotation: int, out_csv: Path) -> None:
    model_name = f"ThermalChain{n_rooms}"
    mid = n_rooms // 2
    base = generate_thermal_chain(n_rooms, MODELS_ROOT / f"N{n_rooms}_base" / f"{model_name}.mo")
    chg = swap_room_conductance(base, mid, MODELS_ROOT / f"N{n_rooms}_chg" / f"{model_name}.mo")
    b_ir, c_ir = compile_model(str(base), model_name).ir, compile_model(str(chg), model_name).ir
    layout = build_layout(b_ir, c_ir)
    order = CONFIGS[rotation % 3:] + CONFIGS[:rotation % 3]
    for k, config in enumerate(order):
        wait_until_idle()
        t0 = time.time()
        print(f"[N={n_rooms}] {config} start {time.strftime('%H:%M:%S')}", flush=True)
        rec = run_config(config, BUILD_ROOT / f"N{n_rooms}" / config, b_ir, c_ir, layout, [f"Q{mid}env"], model_name)
        rec.update(n_rooms=n_rooms, n_equations=3 * n_rooms - 1, run_order_index=k, wall_clock_s=time.time() - t0)
        print(f"  speedup disc={rec['speedup_disc']:.2f}x [{rec['speedup_disc_fieller_low']:.2f},"
              f"{rec['speedup_disc_fieller_high']:.2f}] all={rec['speedup_all']:.2f}x "
              f"full={rec['full_disc_mean_s']:.1f}s incr={rec['incr_disc_mean_s']:.2f}s "
              f"identical={rec['outputs_identical']} reuse_ok={rec['reused_byte_identical']} "
              f"wall={rec['wall_clock_s']:.0f}s", flush=True)
        append_row(rec, out_csv)


if __name__ == "__main__":
    sizes = [int(a) for a in sys.argv[1:] if a.isdigit()] or [100, 500, 1000]
    out = OUT_CSV.with_name("link_ablation_smoke.csv") if "--smoke" in sys.argv else OUT_CSV
    for k, n in enumerate(sizes):
        run_size(n, k, out)
    print(f"wrote {out}")
