# Phase 0: execution checklist

Inspection-only, no changes made in this phase. Builds on the deep repo
audit already performed for `docs/journal-plan.md` (paper, `docs/results.md`,
`docs/progress.md`, all `docs/findings/*.md`, `src/`, `tests/`, `git log`).

## Confirmed current paper claims (paper/main.tex, as of commit b4b7e08)

- Bit-identical correctness on every measured cell (Table II caption,
  reiterated throughout).
- Real MSL speedup: 1.09x-2.27x across 4 cells (electrical + thermal
  domains), ripple 4%-61% (Table III / §MSL results).
- A genuine O(n^2) codegen bug found and fixed, ~8.5x-49x speedup on that
  stage alone (Table on codegen before/after).
- Speedup-vs-size (dynamic-link build): grows 5.66x -> 27.01x across
  149 -> 2,999 equations (Table "scale"), reversing an earlier flat
  1.8x-2.3x plateau attributed to always-relink-everything under the
  original static-link design.
- One-time setup overhead stays 1.3%-1.7%/2.9%-5.2% of full-rebuild time
  (two slightly different framings appear: abstract says 1.3%/1.7%, Table
  in `docs/results.md` §4 says 2.9%-5.2% -- **discrepancy noted, not yet
  resolved, out of scope for Phase 1, flagged for Phase 9 paper-plan
  review**).
- Break-even change frequency: batching wins at B>=2 (dynamic-link,
  N=300/899-equation model, 10-change cumulative sequence).
- States-as-knowns dependency-graph correction: described in Methodology
  §"Recompilation unit definition" as a correctness fix (ThermalNetwork
  raw ripple 100% -> true ripple 22%), not elevated to a separate
  contribution bullet.
- Dynamic linking: described as fixing the relink ceiling, Methodology
  §"Code generation and incremental build".
- Scaling limitations (paper's own Limitations §1): pipeline verified
  bit-identical to 14,999 eq (one-off); repeated speedup/overhead reaches
  2,999; codegen profiled to 14,999; compile-only to 29,999. Paper
  explicitly flags the N=5,999/14,999 one-off cells as "30.5x" (clean,
  continues trend) and "3.3x" (noisy, unexplained) -- **this IS already in
  the paper's Limitations prose**, just not in a results table. The
  N=5,000/14,999-equation number the task names is this same "3.3x" point,
  sourced from `results/measurements_validate_scale.csv`
  (`docs/results.md` §2.1).

## Confirmed evidence-ledger detail behind the N=5,000 anomaly (docs/results.md §2.1)

- Script: `src/validate_scale.py`, command
  `python src/validate_scale.py 2000 5000`.
- N=5,000 rooms -> 14,999 equations. Full rebuild: 675.5s. Incremental:
  203.1s. Speedup: 3.33x (one-off, `repeats=1`, not a properly repeated
  measurement). Bit-identical: **Yes** (correctness held; only the speed
  number is anomalous relative to the trend).
- N=2,000 rooms -> 5,999 equations, same run: 229.4s full, 7.5s
  incremental, 30.53x, bit-identical -- continues the Table-IV trend
  cleanly.
- Existing hypothesis in the ledger (not confirmed): the dynamic-link
  design's still-present O(N) per-rebuild copy step (every unaffected
  unit's cached `.dll` is copied into a fresh build directory on every
  incremental rebuild -- `docs/findings/scaling-bottlenecks.md`
  "Bottleneck 4 fix", never removed) becomes dominant again at large
  enough N. A `du -sh` scan over the N=5,000 cell's build directories did
  not complete within 2 minutes on this machine -- direct evidence
  filesystem operations at ~15,000-file counts are themselves slow here,
  independent of any single build step, but not a stage-by-stage
  breakdown.
- No cached build artifacts from that original run survive on disk
  (`build_cache_msl/`, `models/scaled/` are both empty at the start of
  this session) -- Phase 1 must rebuild the cache from scratch to profile
  it; cannot resume from a prior cache.

## Architecture map used for Phase 1 profiling (from src/c_build.py, src/validate_scale.py, src/measure_msl.py)

`validate_one_size(n_rooms)` calls `run_cell(..., repeats=1)`
(`measure_msl.py`), which for ONE size does, in order:
1. `compile_model()` x2 (Rumoca parse/flatten/DAE-export, baseline +
   changed) -- Bottleneck 1's ~O(n^1.7) cost, ~21s each at N=5,000 per
   `docs/findings/scaling-bottlenecks.md`.
2. `build_layout`, matching/partition/graph construction (near-linear,
   already profiled elsewhere, not the suspect here).
3. `full_rebuild_dynamic()` on the BASELINE model -> the cache.
4. `resolve_impact()` (reachability, cheap).
5. `repeated_full_rebuild_time_dynamic(..., repeats=1)` -- 1 untimed
   warm-up full rebuild + 1 timed full rebuild of the CHANGED model (2
   full rebuilds).
6. ONE MORE full rebuild as the `full_reference` build (for fingerprint
   comparison) -- a 3rd full rebuild of the changed model.
7. `repeated_incremental_rebuild_time_dynamic(..., repeats=1)` -- 1
   untimed warm-up incremental rebuild + 1 timed incremental rebuild (2
   incremental rebuilds).
8. ONE MORE incremental rebuild as the `incr_reference` build -- a 3rd
   incremental rebuild.
9. SHA-256 fingerprinting + 2 simulation runs (full_result.exe,
   incr_result.exe).

**This means the reported "203.1s incremental" at N=5,000 is a SINGLE
incremental_rebuild_dynamic() call's wall time** (the one timed repeat,
after one discarded warm-up) -- not an average, and the warm-up/timed pair
are the 2nd/3rd incremental builds this process has done back-to-back at
that point (the 1st being the `incr_reference` build that actually runs
after the timed pair in source order -- re-check exact call order below).

Each `incremental_rebuild_dynamic()` call, per unit in `sources.unit_files`
(14,999 of them at N=5,000): if affected (2 units), submit to
`build_dlls_many` (parallel gcc -shared); else, `shutil.copyfile()` one
cached `.dll` (~14,997 sequential copies, single-threaded, no
parallelization in this loop today) into the fresh `build_dir`. Then
compile+link the driver once. **The per-unit copy loop is single-threaded
and un-instrumented for its own wall time separately from the DLL
build/driver steps** -- this is exactly the stage Phase 1 needs to isolate.

## Phase 1 plan (next)

1. Smoke test: confirm `generate_thermal_chain`/`swap_room_conductance`/
   `compile_model`/`full_rebuild_dynamic` still work end-to-end at a small
   size (N=50, already-known-good) before spending time at N=5,000.
2. Build the N=5,000 baseline cache once (`full_rebuild_dynamic`),
   timed, kept on disk (not deleted) so it can be profiled repeatedly
   without rebuilding it each time.
3. Instrument and directly time, in isolation, against that persistent
   cache: (a) the copy-only loop (shutil.copyfile x ~14,997, single
   invocation), (b) the 2-unit DLL recompile step, (c) driver
   compile+link. Compare their sum against a full
   `incremental_rebuild_dynamic()` call's total wall time to confirm
   nothing unaccounted-for is happening.
4. Repeat the copy-only measurement 2-3x (cheap once the cache exists) to
   get a real stdev on that specific stage, rather than trusting a single
   204s number.
5. Write `docs/journal_upgrade/phase1_scaling_diagnosis.md` with the
   verdict (A/B/C/D per the task's classification) and confidence level.

Committing this checklist now, before Phase 1 experimentation begins.
