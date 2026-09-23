# Phase 6: link-strategy ablation

Question: how much of the paper's growing-speedup result comes from dynamic linking,
how much from DLL stripping, and does static linking impose a scaling ceiling? All
configurations measured in one session (2026-09-23, 12:37-15:56 IST), same machine,
same model family (ThermalChain N, room-loss edit at N/2, 2 units affected), on AC power.

Scripts: `src/journal_link_ablation.py` (driver), `src/journal_parallel_timing.py`
(harness: 1 first pair + 5 timed pairs, full and incremental interleaved, raw times
stored), `src/journal_link_rerun.py` (single-cell reruns), `src/journal_suspend_check.py`,
`src/journal_parallel_analysis.py`. Data: `results/journal_upgrade/link_ablation_parallel/
link_ablation.csv` (12 rows incl. 3 reruns), `link_ablation_suspend_check.csv`. Tables:
`docs/journal_upgrade/parallel_analysis/tables.md`.

Configurations:
- static: per-unit .o, every rebuild relinks all objects into one .exe (c_build, unchanged);
- dynamic_unstripped: per-unit .dll with plain `gcc -shared`. A RECONSTRUCTION: this
  variant was never committed; it is the current dynamic path with strip/gc-sections/
  no-timestamp flags removed;
- dynamic_stripped: the current design (c_build.full_rebuild_dynamic/incremental_rebuild_dynamic).

Warm-up handled as a statistic, not a separate run ("disc" = first pair discarded, n=5;
"all" = n=6). Correctness on every row: bit-identical simulation output, every reused
artifact byte-identical to its cache, and the changed-source set contained in the
recompiled set.

## 1. Contamination and reruns (pre-registered policy)

The Windows System log shows power-button Modern Standby events inside three cells
(12:40:49 2 s; 12:49:51 standby that became a timed hibernate from 13:05 to 13:49;
14:11:10 3 s). Those three rows are excluded from the tables and each was rerun once
with the identical protocol; both rows are kept in the CSV (reruns marked `rerun=True`).
No suspend event overlaps any rerun or any other cell.

- N=100 dynamic_stripped: original 9.43x, rerun 9.79x [8.55, 11.37] (consistent).
- N=500 dynamic_unstripped: original contained the hibernate (one full rebuild 3,623 s);
  rerun below.
- N=1000 dynamic_stripped: the original's last two incremental repeats took 373.5 s and
  212.1 s, far beyond what a 3-second standby explains; the rerun, with no suspend event,
  was steady (5.6-7.6 s). The original outliers remain UNEXPLAINED; they are excluded
  only because the cell overlapped a suspend event, per the policy fixed in advance.

## 2. Results (clean rows; means with 95% CI; speedup with Fieller interval)

| N (eqs) | Config | Full rebuild s | Incremental s (median) | Link step in incr, median s | Speedup vs own full |
|---|---|---|---|---|---|
| 100 (299) | static | 5.10 [4.80, 5.41] | 1.64 (1.65) | 0.99 | 3.10 [2.91, 3.30] |
| 100 | dynamic_unstripped | 11.42 [10.87, 11.97] | 1.32 (1.26) | 0.09 | 8.63 [7.61, 9.93] |
| 100 | dynamic_stripped | 12.85 [12.08, 13.62] | 1.31 (1.28) | 0.09 | 9.79 [8.55, 11.37] |
| 500 (1,499) | static | 28.29 [26.11, 30.46] | 12.30 | 9.76 | 2.30 [2.04, 2.59] |
| 500 | dynamic_unstripped | 73.89 [70.94, 76.83] | 9.08, CV 123% (4.56) | 0.11 | 8.13 [unbounded] |
| 500 | dynamic_stripped | 54.54 [51.32, 57.76] | 3.00 [2.94, 3.07] | 0.09 | 18.15 [17.02, 19.31] |
| 1000 (2,999) | static | 67.59 [62.01, 73.17] | 34.22 (34.23) | 22.73 | 1.98 [1.57, 2.61] |
| 1000 | dynamic_unstripped | 136.40 [124.47, 148.33] | 45.57, CV 99% (21.27) | 0.11 | 2.99 [unbounded] |
| 1000 | dynamic_stripped | 136.49 [132.98, 139.99] | 6.14 [5.12, 7.16] (5.73) | 0.09 | 22.23 [19.01, 26.71] |

Cross-configuration ratios, same session (Fieller):
- dynamic_stripped full / static full: 2.52 (N=100), 1.93 (N=500), 2.02 (N=1000). The
  dynamic build makes a full rebuild about twice as expensive.
- static full / dynamic_stripped incremental ("speedup against the fastest full rebuild
  available"): 3.89 [3.40, 4.52], 9.42 [8.67, 10.17], 11.01 [9.23, 13.42].

## 3. Findings

1. **Static linking creates a scaling ceiling.** Its incremental link step grows linearly
   with N (median 0.99 s, 9.76 s, 22.73 s) and dominates the incremental rebuild at N=1000
   (22.7 of 34.2 s); speedup falls 3.10x, 2.30x, 1.98x. This reproduces, in a controlled
   same-session comparison, the paper's superseded 1.8x-2.3x static plateau.
2. **Dynamic linking removes it.** The incremental link step is constant (about 0.09 s at
   every N), incremental time grows slowly (1.31, 3.00, 6.14 s, dominated by copying
   cached DLLs, as profiled in Phase 1), and speedup grows (9.79x, 18.15x, 22.23x).
3. **Part of the headline speedup is the slower full rebuild.** The dynamic full rebuild
   costs about 2x the static one (per-unit DLL linking). Measured against the static full
   rebuild, the gain from incremental rebuilding is 3.9x, 9.4x and 11.0x: real and growing
   with N, but about half the same-config ratio. The paper must report both.
4. **Stripping matters at scale, mainly for stability.** At N=100 unstripped and stripped
   are indistinguishable. At N=500 and N=1000 the unstripped incremental rebuild is
   erratic without any suspend event (CV 123% and 99%; repeats spanning 3.3-29.0 s and
   9.8-110.8 s), and slower even by median (4.56 vs about 3.0 s; 21.3 vs 5.7 s). The
   unstripped DLLs are about 7x larger (cache 26.3 MB vs 3.6 MB at N=100), so every
   incremental rebuild copies about 7x more bytes of freshly written executables, which is
   exactly the per-file first-touch/I/O exposure diagnosed in Phase 1. Consistent with the
   project's original motivation for stripping; the mechanism is likely, not proven.
5. **Reproduction of the paper's Table IV.** This session's dynamic_stripped speedups are
   lower than the paper's at N=500 (18.15 [17.02, 19.31] vs 20.75) and N=1000 (22.23
   [19.01, 26.71] vs 27.01), and match at N=100 (9.79 vs 9.99). Both rebuild kinds were slower this
   session at N=1000 (full 136.5 s vs 109.5 s; incremental 6.14 s vs 4.05 s); the slower
   incremental rebuild is what lowers the ratio (a slower full rebuild alone would raise it). The growing trend reproduces; the exact values vary
   by about 10-20% between sessions, so the paper should report intervals and treat single
   session values as one sample.

## 4. Anomalies preserved

- Two cells (N=500 unstripped rerun, N=1000 unstripped) have unbounded speedup
  intervals because of incremental outliers; reported, not trimmed.
- The original N=1000 dynamic_stripped cell's 373.5 s and 212.1 s repeats (Section 1).
- Power-button standby events during the run (user interaction with the laptop), detected
  only by checking the Windows event log; every row now carries its suspend check.

## 5. Implications for the paper

- Keep the dynamic-link result as the scaling mechanism, now supported by a controlled
  same-session ablation instead of a before/after narrative.
- Report absolute times and both baselines; state the about 2x full-rebuild cost of the
  dynamic design as a trade-off: at N=1000, compared with static-link incremental
  rebuilding, it saves 28.1 s per edit (34.22 vs 6.14 s) but costs 68.9 s more per full
  rebuild (136.49 vs 67.59 s), so it pays off once more than about 2.5 edits occur per
  full rebuild.
- Present stripping as a variance and I/O-volume measure, with the unstripped instability
  as evidence, not only as a size reduction.
- The remaining incremental cost at large N is the per-rebuild copy of cached DLLs
  (Phase 1); removing that O(N) file materialization is the natural next step.
