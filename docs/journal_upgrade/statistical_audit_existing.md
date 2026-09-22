# Statistical and provenance audit of the existing results

Scope: every timing and correctness file under `results/` that backs `paper/main.tex` (state at commit `b4b7e08` for the paper, `2741414` for the newest committed results). Nothing was re-run for this audit: no build, no measurement script, no pytest. All numbers below come from the committed CSV/parquet files, their git history, or the producing scripts' source.

Machine-readable per-cell table: `results/journal_upgrade_stats_existing.csv`, produced by

```
cd C:\Users\parth\Desktop\Papers\compiler_digital_twin; $env:PYTHONPATH="src"
.\.venv\Scripts\python.exe src\journal_stats_audit.py results\measurements.csv results\measurements_c_stage0_rerun.txt results\measurements_msl.parquet results\measurements_scale.parquet results\measurements_overhead.parquet results\measurements_break_even.parquet results\measurements_validate_scale.parquet --out results\journal_upgrade_stats_existing.csv
.\.venv\Scripts\python.exe src\journal_stats_audit.py --selftest
```

CSV and parquet copies of each file were checked against each other: identical shapes, maximum numeric difference 5.7e-14 (float formatting only).

## 1. Method

**Interval for a mean.** 95% CI = mean ± t(0.975, n-1) · sd/√n. A t critical value is used rather than z = 1.96 because sd is itself estimated from the same n = 3 to 7 samples; the t distribution accounts for that extra uncertainty, and at these n the difference is large (t = 4.303 at n = 3, 2.776 at n = 5, 2.447 at n = 7). scipy is not installed and was not added; `src/journal_stats_audit.py` hard-codes a standard two-sided t-table for df 1..30.

**Caveat on n = 3.** With df = 2 the multiplier is 4.303/√3 = 2.48 standard deviations, so a cell with a 3% CV gets a ±7.4% CI. These CIs are honest but wide, and they rest on an approximate normality assumption that n = 3 cannot check. A single outlier (such as the documented 80 s cold-start repeat, Section 5) would dominate any n = 3 cell.

**Interval for a speedup ratio S = mean_full / mean_incr.** Two methods are reported; neither is presented as exact.
1. *Endpoint interval* (primary, simplest): [ (mf - hf)/(mi + hi), (mf + hf)/(mi - hi) ], built from the two means' 95% CI half-widths hf, hi. It is always very wide. Its guaranteed coverage under independence is only 0.95² = 90.25% (both component intervals must cover), although in practice it is much wider than an exact 95% interval.
2. *Fieller interval* (secondary): solves (mf - θ·mi)² = t²(sef² + θ²·sei²) for θ, treating the full and incremental samples as independent (they are separate builds in separate directories) with t at df = min(nf, ni) - 1. Unbounded if the denominator mean is not significantly non-zero; that never happens here.

**No CI is produced when n = 1** or when n cannot be established from the file or the producing script. A stored `*_stdev_s = 0.0` at n = 1 is treated as a placeholder, not as a measured zero spread.

**Where n comes from.** Only `measurements.csv` (`compile_repeats`) and `measurements_scale.csv` (`repeats`) store n. For MSL (5), break-even full rebuild (3), validate_scale (1) and Stage 0 (5), n was taken from the producing script's constant (`src/measure_msl.py:43`, `src/break_even.py:29`, `src/validate_scale.py:37`, `src/measure_c.py:21`), assuming the run used the defaults. **No existing result file stores raw per-repeat times**, so min/max are available only for `measurements.csv`.

## 2. Metric classification

| Class | Columns | Treatment |
|---|---|---|
| Deterministic | `total_units`, `affected_units`, `affected_fraction` (ripple ρ), `n_equations`, `n_rooms`, `n_batches`, `projected_speedup_ceiling`, `outputs_identical`, `reused_objects_byte_identical_to_cache`, `incremental_matches_full_for_unaffected_objects` | Exact; no interval. Git history confirms ρ was identical across all seven committed MSL runs (for example 13/23, 1/24, 11/18 in every version). |
| Noisy, repeated | `full_rebuild_mean_s/stdev_s`, `incremental_mean_s/stdev_s`, `compile_time_*` | t-CI (Section 3). |
| Noisy, single sample (n = 1) | all of `measurements_overhead` timings (`rumoca_compile_s`, `match_s`, `partition_s`, `graph_s`, `total_setup_s`), `streaming_incremental_total_s`, all of `measurements_validate_scale` timings | No variance estimate exists. |
| Derived | `measured_speedup`, `*_over_full_rebuild`, `batched_full_total_s_*`, `break_even_batch_size`, `batched_cheaper_*` | Inherit the uncertainty of their inputs (Sections 3 and 4). |

## 3. Per-cell statistics (timings in seconds)

### 3.1 Real MSL models (`measurements_msl.csv`, n = 5, dynamic-link build)

| Cell | Full mean ± sd (CV) | Full 95% CI | Incr mean ± sd (CV) | Incr 95% CI | S | S endpoint CI | S Fieller CI |
|---|---|---|---|---|---|---|---|
| MslRcCircuit swap | 1.4534 ± 0.0280 (1.9%) | [1.419, 1.488] | 1.2175 ± 0.0518 (4.3%) | [1.153, 1.282] | 1.194 | [1.107, 1.290] | [1.128, 1.266] |
| MslThermalChain swap | 1.4358 ± 0.1421 (9.9%) | [1.259, 1.612] | 0.9528 ± 0.0334 (3.5%) | [0.911, 0.994] | 1.507 | [1.267, 1.769] | [1.313, 1.706] |
| MslRcCircuit sensor | 1.5298 ± 0.0273 (1.8%) | [1.496, 1.564] | 0.8442 ± 0.0218 (2.6%) | [0.817, 0.871] | 1.812 | [1.717, 1.914] | [1.743, 1.885] |
| MslResistorNetwork removal | 1.3019 ± 0.0474 (3.6%) | [1.243, 1.361] | 1.0759 ± 0.0224 (2.1%) | [1.048, 1.104] | 1.210 | [1.126, 1.298] | [1.148, 1.274] |

Within-run intervals exclude 1.0 for all four cells. **But within-run intervals understate the real uncertainty here**: the git history shows the *between-run* spread is larger than the within-run CI. For example, MslRcCircuit swap measured 1.142, 1.186 and 1.092 in three runs of the same static-link code (`410c852`, `c51af07`, `d2a6ee6`), and 1.219 then 1.194 in two dynamic-link runs (`94d0037`, `2741414`). A run-level (not repeat-level) replication is what these cells need.

### 3.2 Size sweep (`measurements_scale.csv`, n = 3, dynamic-link build)

| Eq. | Full mean ± sd (CV) | Full 95% CI | Incr mean ± sd (CV) | Incr 95% CI | S | S endpoint CI | S Fieller CI |
|---|---|---|---|---|---|---|---|
| 149 | 5.932 ± 0.078 (1.3%) | [5.74, 6.13] | 1.048 ± 0.089 (8.5%) | [0.83, 1.27] | 5.66 | [4.52, 7.42] | [4.66, 7.20] |
| 299 | 11.221 ± 0.178 (1.6%) | [10.78, 11.66] | 1.123 ± 0.031 (2.8%) | [1.05, 1.20] | 9.99 | [8.98, 11.16] | [9.24, 10.84] |
| 749 | 27.556 ± 0.826 (3.0%) | [25.50, 29.61] | 1.778 ± 0.184 (**10.4%**) | [1.32, 2.24] | 15.50 | [11.41, 22.44] | [12.16, 21.05] |
| 1,499 | 51.609 ± 0.301 (0.6%) | [50.86, 52.36] | 2.487 ± 0.038 (1.5%) | [2.39, 2.58] | 20.75 | [19.70, 21.89] | [19.93, 21.63] |
| 2,999 | 109.484 ± 4.368 (4.0%) | [98.63, 120.34] | 4.053 ± 0.121 (3.0%) | [3.75, 4.35] | 27.01 | [22.66, 32.06] | [23.81, 30.51] |

The monotone growth of S survives the intervals for every adjacent pair except one: 749 vs 1,499 overlap (Fieller [12.2, 21.0] vs [19.9, 21.6]; endpoint [11.4, 22.4] vs [19.7, 21.9]), driven by the N = 250 incremental CV of 10.4%. All other adjacent pairs are separated under both methods. The trend claim is supported across 149 to 2,999 as a whole; the 749-to-1,499 step on its own is not resolved at n = 3.

### 3.3 Other files

| File / cell | n | Mean ± sd (CV) | 95% CI | Notes |
|---|---|---|---|---|
| `measurements.csv` RLCCircuit compile | 7 | 3.83 ms ± 0.99 ms (25.9%) | [2.91, 4.75] ms | min 2.73, max 5.01 ms; Rumoca compile only, phase 1 |
| `measurements.csv` ThermalNetwork compile | 7 | 5.20 ms ± 1.14 ms (21.9%) | [4.14, 6.25] ms | min 3.87, max 6.80 ms |
| Stage 0 RLCCircuit full / incr (static link) | 5 | 313.5 ± 41.9 ms (13.4%) / 311.7 ± 20.0 ms (6.4%) | S = 1.006, endpoint [0.78, 1.28] | **S not distinguishable from 1** |
| Stage 0 ThermalNetwork full / incr | 5 | 371.6 ± 11.8 ms / 319.8 ± 29.0 ms | S = 1.162, endpoint [1.00, 1.36], Fieller [1.04, 1.32] | lower endpoint touches 1.0 |
| Break-even T_full (N = 300) | 3 | 35.52 ± 2.30 s (6.5%) | [29.80, 41.24] | CI half-width 16% of mean |
| Break-even T_stream | 1 | 291.20 s | none | sum of 10 single-sample steps |
| Overhead, all timings | 1 | see CSV | none | denominator copied from scale sweep |
| validate_scale N = 2,000 | 1 | full 229.45, incr 7.52, S = 30.53 | none | |
| validate_scale N = 5,000 | 1 | full 675.46, incr 203.13, S = 3.33 | none | |

### 3.4 High-variance and no-variance cells (flags)

- **CV above 10%**: scale N = 250 incremental (10.4%); Stage 0 RLCCircuit full (13.4%); phase 1 compile times (22 to 26%). MslThermalChain full is 9.9%.
- **No variance estimate at all (n = 1)**: both `validate_scale` rows (including the 30.5x and 3.3x quoted in the paper's limitations), every overhead timing (the 1.3% and 1.7% claims), and T_stream (the break-even numerator).
- **Superseded static-link N = 1,000** (`git show 9fb61d9:results/measurements_scale.csv`): incremental 39.29 ± 11.95 s (CV 30.4%), and the static N = 500 incremental was 16.02 ± 9.04 s (CV 56%; `docs/results.md:611` says about 75%, which is not what the committed file holds). These are cited in the paper only as the diagnosed "before" state, which is appropriate, but at n = 3 with CV 30 to 56% they cannot support any quantitative claim beyond "large and noisy".
- **Single-sample instability demonstrated by the history**: the overhead stages' code (`compile.py`, `matching.py`, `matched_units.py`, `matched_graph.py`, `scaled_models.py`, `measure_overhead.py`) did not change between `29d9ac6` and `94d0037` (checked with `git log`), yet the N = 1,000 single-sample numbers moved from rumoca 2.704 s to 1.490 s and match+partition+graph from 1.020 s to 0.330 s. Single-sample setup timings vary by 2 to 3x between runs, so the overhead fractions need repeats.

## 4. Paper-vs-data consistency (`paper/main.tex` at `b4b7e08`)

Checked and **consistent** with the current CSVs: MSL table (main.tex:172-175, all eight times match `measurements_msl.csv` to 0.1 ms); scale table (234-238, all 15 numbers); "5.66x to 27.01x, roughly 4.8-fold" (250); abstract "5.7x to 27.0x"; 1.3% and 1.7% overhead (254) match `total_setup_over_full_rebuild` 0.01324 and 0.01662; break-even T_stream = 291.2 s and T_full = 35.5 s (270) and table rows (281-286); 899 equations = 3·300 - 1; validate_scale 30.5x and 3.3x and "bit-identical up to 14,999" (304); static-link "30% vs 4%" RSD at N = 1,000 (221) matches the superseded `9fb61d9` CSV (30.4%, 3.9%); the static "1.8x to 2.3x" band matches `9fb61d9` (1.84 to 2.27).

**Mismatches and unsupported statements:**

1. **Abstract speedup range (main.tex:42).** Says "On real Modelica-Standard-Library circuits we measure real speedups of 1.09x--2.27x". Current data (`measurements_msl.csv`) and the results section (main.tex:194) give **1.19x to 1.81x**. Origin traced: the abstract sentence was written at `d37239d` and never updated at `94d0037`. 1.09 is the static-link MslRcCircuit swap from `d2a6ee6`, and **2.27 is not an MSL number at all**; it is the static-link generated ThermalChain50 cell (`9fb61d9`, 2.2746). Fix: "1.19x--1.81x".
2. **"standard deviation now under about 9% of the mean at every size" (main.tex:250; also `docs/results.md:609-610`).** Scale N = 250 incremental has CV 10.4% (0.1845/1.7778). Say "at most about 10%" or name the exception.
3. **"a flat, roughly threefold-higher plateau" (main.tex:298).** The only documented per-step streaming data (`docs/results.md:817-819`) is step 1 = 1.93 s, then 31.15 to 33.91 s, about **16x** higher, not threefold. Those per-step values also sum to 288.1 s, not the 291.2 s in `measurements_break_even.csv`, so they come from a different execution of `run_change_sequence` (the `change_frequency.py` main block) than the one that produced the table (`break_even.py` main block reruns the sequence). Per-step data is stored in no results file.
4. **"independent re-runs ... vary by up to roughly 30--40%" (main.tex:194, `docs/results.md:515`).** The committed CSV history does not reproduce this. Across the three committed static-link runs of the same code, the largest relative spread in S is 17% (MslResistorNetwork 1.150 to 1.347); full-rebuild means vary by at most 15%. The 30 to 40% may come from uncommitted runs; either cite the source or restate from the committed data.
5. **Overhead "non-trending fraction" (main.tex:254).** The current series is 1.32%, 1.42%, 1.43%, 1.66%, 1.66%, which is monotone non-decreasing. The *values* 1.3% and 1.7% are correct; the adjective is not. Also, "shrank further as a fraction once full-rebuild time itself grew" is correct only because (a) the denominator rose (static 72.2 s to dynamic 109.5 s at N = 1,000) and (b) the single-sample numerator fell by half with no code change (Section 3.4). The comparison against `docs/results.md` Section 4's 2.9%-5.2% is internally consistent (those are the `29d9ac6` static-link values), but `docs/results.md:654-662` was never updated or marked superseded, unlike Sections 3.1, 3.2, 6.1 and 6.2.
6. **Real-model corpus size (main.tex:318).** Limitation 8 says "two real circuits plus the Cauer filter"; main.tex:146 and 194 describe three real models (MslRcCircuit, MslResistorNetwork, MslThermalChain) plus Cauer.
7. **Break-even table (281-286)** silently omits the B = 7 row present in the CSV (71.0 s, 2 rebuilds, cheaper). Not a numeric error.
8. **Break-even "stable even under ... worst-case measured spread" (298).** The code's "worst case" is mean + 1 sd (`src/break_even.py:66-67`), not a confidence bound. Rechecked with the t-based 95% CI on T_full [29.80, 41.24] s: B = 1 batched total [298.0, 412.4] s is never cheaper than 291.2 s; B = 2 [149.0, 206.2] s is always cheaper. **The crossing at B = 2 survives the 95% CI**, but only for T_full; T_stream is n = 1 with no variance estimate. B = 1 misses by 6.8 s at the lower CI bound, so a T_stream about 2.3% higher would already make B = 1 ambiguous (this affects only the B = 1 row, not the crossing).
9. **Values not traceable to any results file** (docs-only provenance): codegen table 3.13/0.37/88.86/1.81 s (main.tex:210-211); "1,499 equations, 11.3 s vs 29.8 s" (221); "roughly twentyfold" warm-up spike and "86%" DLL size reduction (223, sourced only from comments in `src/c_build.py:280-286, 414-415`). The 4.85x ratio (216) cannot be recomputed exactly from the rounded 0.37/1.81 (gives 4.89).
10. **`docs/results.md:483-487` misattributes a commit.** It says the CSV committed at `410c852` held 1.186/1.612/1.191; `git show 410c852:results/measurements_msl.csv` holds 1.142/1.721/1.150 (matching that commit's message), and 1.186/1.612/1.191 first appears at `c51af07`.

**Validity threat not stated in the paper (important for reviewers).** The dynamic-link full rebuild, the denominator of every current speedup, is much slower than the static-link full rebuild it replaced: N = 50, 3.04 s to 5.93 s; N = 1,000, 72.2 s to 109.5 s; N = 300, 18.9 s to 35.5 s; MSL cells, about 0.55-0.60 s to 1.30-1.53 s. Part of the speedup growth therefore comes from a slower baseline. Against the older static full rebuild, N = 1,000 would be 72.2/4.05 = 17.8x rather than 27.0x (different sessions, indicative only), and on the MSL cells the current dynamic *incremental* times (0.84 to 1.22 s) are slower than the old static *full* rebuilds (0.55 to 0.60 s). A journal version should report both baselines, or justify the dynamic full rebuild as the fair comparison (same artifact format), and say so explicitly.

## 5. Provenance

| File | Last written (git) | Producer | n | Warm-up |
|---|---|---|---|---|
| `measurements.csv`/`.parquet`, `measurements_provenance.json`, `summary.md` | `4090086` (2026-08-15); summary `f7ab9d8` | `src/measure.py` (Rumoca compile timing) | 7 (`compile_repeats`) | none |
| `measurements_c_stage0_rerun.txt` | `2819e84` (2026-08-17) | `src/measure_c.py` stdout, static link | 5 (script constant) | none |
| `measurements_msl.*` | `2741414` (2026-08-18 09:40); 7 versions since `06e5504` | `src/measure_msl.py log_all_cells()`, **invoked from `tests/test_measure_msl.py:31`, which writes into the real `results/` directory** (`docs/results.md:522-524`) | 5 (not stored) | 1 untimed full + 1 untimed incremental (`c_build.py:398, 427`) |
| `measurements_scale.*` | `94d0037` (file mtime 05:51, commit 06:54) | `src/measure_scale.py` | 3 (stored) | as MSL |
| `measurements_overhead.*` | `94d0037` (mtime 06:08) | `src/measure_overhead.py`; ratio denominator read from whatever `measurements_scale.csv` existed at run time | 1 | none |
| `measurements_break_even.*` | `94d0037` (mtime 06:17) | `src/break_even.py` main (reruns the change sequence) | full 3 (not stored), stream 1 | **none** for the full repeats (`break_even.py:32-40`) or for streaming steps |
| `measurements_validate_scale.*` | `2741414` (mtime 08:36) | `src/validate_scale.py 2000 5000` | 1 | as MSL (1 untimed warm-up each, even at repeats = 1) |
| superseded static scale/overhead/break-even | `9fb61d9`, `29d9ac6`, `80407d1` | same scripts, static link | 3 / 1 / 3 | none |

**Tool versions.** Paper (main.tex:146): Rumoca 0.9.20, Python 3.11.9, MinGW-w64 GCC 15.2, "one Windows machine". Recorded: `measurements_provenance.json` only (Rumoca 0.9.20, Python 3.11.9, Windows-10-10.0.**26100**, AMD64), written once by `src/measure.py` on 2026-08-15 and never by any later script. `docs/results.md:15-16` states later sessions ran on build **26200**. Today (read-only check): `gcc (Rev13, Built by MSYS2 project) 15.2.0`, Python 3.11.9, Windows 10.0.26200, rumoca 0.9.20, pandas 2.2.3, numpy 2.4.6, networkx 3.4.2, AMD Ryzen 5 7535HS (6 cores / 12 threads, 3.3 GHz base), power plan "Balanced". `requirements.txt` pins rumoca/networkx/pandas/matplotlib/pytest/pyarrow but not numpy.

**Gaps.**
- No per-run record of GCC version, OS build, CPU, git SHA, dirty-tree flag, timestamp, or thread count for any file after 2026-08-15. The GCC 15.2 in the paper matches today's toolchain but was not recorded at measurement time.
- The results were written before their commits (mtimes precede commit times), so the exact code state at run time is the uncommitted tree before `94d0037`/`2741414`.
- Repeat counts are not stored for MSL, break-even, or validate_scale.
- No raw per-repeat times are stored anywhere, even though `run_cell()` returns `full_rebuild_times_s` and `incremental_times_s`; `log_all_cells`/`log_scale_sweep` drop them.
- Model-generation parameters are fixed in code and not logged: scale/validate use `generate_thermal_chain(N)` with the swap at room N//2, seed `Q{N//2}env`, t_end 2.0, dt 1.0; break-even N = 300, rooms [30, 60, ..., 270, 295], batch sizes [1, 2, 3, 4, 5, 7, 10]; MSL cells in `measure_msl.py:145-180`.
- **Clobber risk**: any `pytest` run overwrites `results/measurements_msl.*` (the paper's Table), and re-running `measure_scale.py` silently invalidates the ratios in `measurements_overhead.csv` until that is rerun too.

## 6. Execution order and environment threats

- **No randomization or interleaving.** In `run_cell()` all full-rebuild repeats run as one block, then all incremental repeats (`measure_msl.py:95-102`); sizes run in ascending order in one session; MSL cells in fixed order. Slow drift (thermal throttling, background activity, Defender state) is therefore confounded with condition and with size.
- **Warm-up policy is inconsistent across experiments.** The dynamic-link `run_cell()` discards one warm-up for each condition; the break-even full-rebuild repeats and the streaming chain have none; Stage 0, phase 1 and all superseded static-link runs have none. The paper (main.tex:223) describes the warm-up for the size sweep only, and main.tex:298 explains why none was applied to streaming. `src/c_build.py:415` records raw N = 1,000 incremental times [80.48, 4.18, 4.08, 4.01, 11.21] s: discarding the first still leaves an 11.21 s outlier (2.7x), so one warm-up does not remove all Defender-related spikes.
- **Windows Defender real-time protection** is enabled (`c_build.py:283-285, 417-418`; `docs/findings/scaling-bottlenecks.md:241, 282`) and is the leading explanation for the N = 5,000 3.3x result and the streaming plateau, but it was never toggled or excluded experimentally.
- **CPU frequency scaling**: laptop CPU on the "Balanced" power plan; AC or battery state and boost behavior were not recorded.
- **Parallelism**: gcc runs through a `ThreadPoolExecutor` with `os.cpu_count()` = 12 workers (`c_build.py:39`). The paper does not state this. It helps full rebuilds (many files) far more than incremental ones, so S depends on core count; it must be reported.
- **Shared machine**: runs were not isolated from other work; the current journal work also runs long experiments on this machine in parallel.

## 7. Recommended pre-registered policy for the new experiments

Fix these before running anything, write them into the experiment scripts, and do not change them after seeing results.

1. **Repeats**: n = 10 timed repeats per condition per cell (n = 5 minimum for cells over 10 minutes, stated in advance per cell), plus **exactly one discarded warm-up per condition**, applied identically to every experiment (MSL, size sweep, break-even full rebuilds, streaming chain, validation cells).
2. **Order**: interleave conditions (full, incremental, full, ...) with a seeded random order per cell; log the seed and the order. Randomize cell order within a session where feasible.
3. **Reporting**: for every timing, report n, mean, sd, median, min, max, 95% t-CI, and store **all raw per-repeat values** (list column) in the parquet. For speedups, report the ratio of means with the Fieller interval (df = min(n) - 1) and the endpoint interval, and say which is which. Report medians alongside means because of the known heavy right tail.
4. **No adaptive re-running**: no re-running a cell because the number looks wrong, no dropping outliers beyond the one pre-declared warm-up. If a run is invalid for a stated external reason (crash, machine sleep), log it and rerun the *whole* cell; keep the invalid run's raw data.
5. **Provenance per results file**: git SHA plus dirty flag, UTC timestamp, `gcc --version`, Python, Rumoca, numpy, OS build, CPU model, `os.cpu_count()` and the worker count actually used, power plan and AC state, Defender real-time state (on/off, exclusions), and the script's full parameter set (sizes, seeds, repeats, warm-ups, t_end, dt).
6. **Environment**: AC power, "High performance" or "Best performance" plan, no other heavy jobs, and either a Defender exclusion on the build directories or both states measured as a named factor. Report the thread count and, ideally, one sweep at 1 worker.
7. **Baselines**: report speedups against both the dynamic-link full rebuild and the static-link full rebuild in the same session.
8. **Replication**: repeat the whole MSL block in at least 3 independent sessions and report between-session spread, since between-run variance already exceeds within-run variance there.
9. **Tests must not write into `results/`**: point `tests/test_measure_msl.py` at `tmp_path`, as the scale and overhead tests already do.
10. Re-run `src/journal_stats_audit.py` on every new file, and check every paper number against its output before submission.
