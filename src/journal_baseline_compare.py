"""Journal upgrade, phase 2: build-timing driver comparing incremental
strategies that differ ONLY in which unit C files they recompile:

  matching : the paper's method (resolver.resolve_impact over
             matched_graph.build_matched_graph), exactly as run_cell uses it
  naive    : undirected incidence closure, states as knowns
             (journal_naive_resolver.resolve_impact_naive)
  oracle   : content-hash reference point, units whose generated C text
             differs from the baseline's (journal_naive_resolver.content_hash_oracle)

Flow is measure_msl.run_cell's, step for step (same compile, shared
layout, source writing, cached baseline build, repeated_*_dynamic timing
wrappers with their untimed warm-up, fingerprint checks, and full-stdout
outputs_identical check). One deliberate difference: per cell, the
compile, cache build and full-rebuild timing are done ONCE and shared by
all strategies (full rebuild does not depend on the strategy); each
strategy then gets its own incremental timing, reference build,
fingerprint and output checks in its own build directory.

This invokes gcc. Run it serially, alone on the machine:
  cd <repo>; $env:PYTHONPATH="src"; .\\.venv\\Scripts\\python.exe src\\journal_baseline_compare.py
  ... --smoke                     tiny ThermalNetwork swap cell only, 1 repeat
  ... --only MslRcCircuit/swap    run cells whose label contains the given text
Writes results/journal_upgrade_phase2_timing.csv (rewritten after every
cell, so a partial run keeps what finished). Builds go to
build_cache_journal_baseline/, never to measure_msl's build_cache_msl/.
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from c_build import (
    fingerprint_objects, full_rebuild_dynamic, incremental_rebuild_dynamic,
    repeated_full_rebuild_time_dynamic, repeated_incremental_rebuild_time_dynamic, run_sim, write_sources,
)
from compile import compile_model
from journal_naive_resolver import FIXTURE_CELLS, comparison_cells, content_hash_oracle, resolve_impact_naive
from matched_graph import build_matched_graph
from measure_msl import REPEATS, _affected_c_filenames, _as_build_sources
from model_layout import build_layout
from resolver import resolve_impact

BUILD_ROOT = Path("build_cache_journal_baseline")
OUT_CSV = Path("results/journal_upgrade_phase2_timing.csv")
STRATEGIES = ("matching", "naive", "oracle")


def affected_c_filenames(strategy: str, model_name: str, baseline_ir: dict, changed_ir: dict, seed: list[str]) -> set[str]:
    if strategy == "matching":
        return _affected_c_filenames(model_name, changed_ir, resolve_impact(changed_ir, seed, graph_builder=build_matched_graph))
    if strategy == "naive":
        return _affected_c_filenames(model_name, changed_ir, resolve_impact_naive(changed_ir, seed))
    if strategy == "oracle":
        return set(content_hash_oracle(model_name, baseline_ir, changed_ir)["affected_c_filenames"])
    raise ValueError(f"unknown strategy {strategy!r}")


def run_cell_strategies(
    label: str, baseline_path: str, changed_path: str, model_name: str, seed: list[str],
    t_end: float, dt: float, baseline_roots: list[str] | None = None,
    changed_roots: list[str] | None = None, repeats: int = REPEATS, strategies=STRATEGIES,
) -> list[dict]:
    baseline = compile_model(baseline_path, model_name, roots=baseline_roots)
    changed = compile_model(changed_path, model_name, roots=changed_roots)

    layout = build_layout(baseline.ir, changed.ir)
    baseline_sources = _as_build_sources(model_name, baseline.ir, layout)
    changed_sources = _as_build_sources(model_name, changed.ir, layout)

    cell_dir = BUILD_ROOT / label.replace("/", "_")
    baseline_src_dir = cell_dir / "baseline_src"
    changed_src_dir = cell_dir / "changed_src"
    write_sources(baseline_sources, baseline_src_dir)
    write_sources(changed_sources, changed_src_dir)

    cache_build = full_rebuild_dynamic(baseline_sources, baseline_src_dir, cell_dir / "cache")

    affected = {s: affected_c_filenames(s, model_name, baseline.ir, changed.ir, seed) for s in strategies}
    if "oracle" in affected:
        # guard: the oracle recompiled here must equal the independently computed source diff
        # (src/journal_phase2_verify_oracle.py logic: changed-or-new unit files, compared directly)
        independent = {f for f, t in changed_sources.unit_files.items() if baseline_sources.unit_files.get(f) != t}
        if affected["oracle"] != independent:
            raise RuntimeError(f"oracle set disagrees with independent source diff: {affected['oracle'] ^ independent}")

    full_times = repeated_full_rebuild_time_dynamic(changed_sources, changed_src_dir, cell_dir / "full_repeats", repeats)
    full_result = full_rebuild_dynamic(changed_sources, changed_src_dir, cell_dir / "full_reference")
    full_fp = fingerprint_objects(full_result)
    full_output = run_sim(full_result.exe_path, t_end, dt)
    cache_fp = fingerprint_objects(cache_build)
    cached_objects = cache_build.object_paths
    total_units = len(changed_sources.unit_files)

    rows = []
    for order, strategy in enumerate(strategies):
        files = affected[strategy]
        s_dir = cell_dir / strategy
        incr_times = repeated_incremental_rebuild_time_dynamic(
            changed_sources, changed_src_dir, s_dir / "incr_repeats", files, cached_objects, repeats,
        )
        incr_result = incremental_rebuild_dynamic(
            changed_sources, changed_src_dir, s_dir / "incr_reference", files, cached_objects,
        )
        incr_fp = fingerprint_objects(incr_result)
        rows.append({
            "cell": label,
            "model_name": model_name,
            "seed": ",".join(seed),
            "strategy": strategy,
            "strategy_order": order,
            "total_units": total_units,
            "n_units_recompiled": len(files),
            "recompiled_fraction": len(files) / total_units,
            "repeats": repeats,
            "full_rebuild_mean_s": statistics.mean(full_times),
            "full_rebuild_stdev_s": statistics.stdev(full_times) if len(full_times) > 1 else 0.0,
            "incremental_mean_s": statistics.mean(incr_times),
            "incremental_stdev_s": statistics.stdev(incr_times) if len(incr_times) > 1 else 0.0,
            "measured_speedup": statistics.mean(full_times) / statistics.mean(incr_times),
            "full_rebuild_times_s": ";".join(f"{t:.6f}" for t in full_times),
            "incremental_times_s": ";".join(f"{t:.6f}" for t in incr_times),
            "reused_objects_byte_identical_to_cache": all(
                incr_fp[c] == cache_fp[c] for c in incr_fp if c not in files and c in cache_fp
            ),
            "incremental_matches_full_for_unaffected_objects": all(
                incr_fp[c] == full_fp[c] for c in incr_fp if c not in files
            ),
            "outputs_identical": full_output == run_sim(incr_result.exe_path, t_end, dt),
        })
    return rows


def _write(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke", action="store_true", help="ThermalNetwork/swap only, 1 repeat, output under build dir")
    ap.add_argument("--only", nargs="*", default=None, help="keep cells whose label contains any of these")
    ap.add_argument("--repeats", type=int, default=REPEATS)
    ap.add_argument("--sizes", type=int, nargs="*", default=None, help="ThermalChain sizes (default 50 250 1000)")
    ap.add_argument("--strategies", nargs="*", default=list(STRATEGIES), choices=STRATEGIES)
    args = ap.parse_args(argv)

    if args.smoke:
        cells, repeats, out = [FIXTURE_CELLS[0]], 1, BUILD_ROOT / "smoke_timing.csv"
    else:
        cells = comparison_cells() if args.sizes is None else comparison_cells(args.sizes)
        repeats, out = args.repeats, OUT_CSV
    if args.only:
        cells = [c for c in cells if any(s in c["label"] for s in args.only)]

    rows: list[dict] = []
    for k, c in enumerate(cells):
        # rotate strategy order per cell so slow drift does not always land on the same strategy
        strategies = args.strategies[k % len(args.strategies):] + args.strategies[:k % len(args.strategies)]
        print(f"[{c['label']}] building (order {strategies}) ...", flush=True)
        rows += run_cell_strategies(
            c["label"], c["baseline_path"], c["changed_path"], c["model_name"], c["seed"], c["t_end"], c["dt"],
            baseline_roots=c.get("baseline_roots"), changed_roots=c.get("changed_roots"),
            repeats=repeats, strategies=strategies,
        )
        _write(rows, out)
        for r in rows[-len(args.strategies):]:
            print(f"  {r['strategy']:>8}: recompiled {r['n_units_recompiled']}/{r['total_units']} "
                  f"incr={r['incremental_mean_s']:.3f}s full={r['full_rebuild_mean_s']:.3f}s "
                  f"speedup={r['measured_speedup']:.2f} identical={r['outputs_identical']}", flush=True)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
