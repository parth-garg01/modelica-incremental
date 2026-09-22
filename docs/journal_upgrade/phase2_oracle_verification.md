# Phase 2 verification: paper method vs matching-free baseline vs source-diff oracle

Run 2026-09-22 23:57 to 2026-09-23 00:44 IST, serially, alone on the machine
(the three analysis agents were stopped first and no other Python process was
running). Paper (`paper/main.tex`) not modified.

## 1. Objective

Phase 2's graph-level comparison found that the paper's reachability set can be
much larger than the set of units whose generated C source actually changes
(MslRcCircuit swap: 13 vs 2 of 23). This phase establishes, by independent
recomputation and real builds, (a) whether that source-diff set is reproducible,
(b) whether building with only that set is bit-identical to a full rebuild,
(c) what each strategy actually costs in wall-clock time, and (d) what this means
for the paper's central claim.

## 2. Methodology

Three incremental strategies that differ ONLY in which unit C files they
recompile. All share the unit partition (matching + SCC/BLT, states as knowns),
the C generator, the shared variable layout, the dynamic-link build, and the
correctness checks:

| Strategy | Recompiles | Uses the matching? |
|---|---|---|
| paper (`matching`) | units reachable from the seed equations on the post-change matched graph (`resolver.resolve_impact`) | yes, for impact direction |
| baseline (`naive`) | units in the undirected equation-variable incidence closure from the seeds, states as knowns | no (for impact analysis) |
| oracle | units whose generated C source text differs from the baseline model's, plus new units | no (compares generated text) |

Important scope note: all three strategies, including the baseline and the
oracle, depend on the matching-derived unit partition and code generator. Without
a matching there are no per-unit C files to build at all for acausal
(connect-generated) equations. The comparison therefore isolates impact analysis
only, not the value of matching as a whole.

Driver: `src/journal_baseline_compare.py` (flow copied from `measure_msl.run_cell`:
compile, shared layout, cached baseline build, `repeated_*_dynamic` wrappers with
one untimed warm-up, 5 timed repeats, fingerprint and full-stdout checks). Two
changes made before the full run, neither depending on any result: strategy
order rotates per cell (recorded as `strategy_order`), and a guard asserts that
the oracle set used for the build equals the independently computed source diff.
Per cell, compile, cache build and full-rebuild timing are shared by the three
strategies; each strategy has its own incremental timing, reference build,
fingerprints and output check in its own directory.

Pre-registered decision rule (fixed before the last cell finished, in
`src/journal_phase2_analyze.py`): A beats B on a cell only if the 95% Welch CI
of mean(incremental_A) minus mean(incremental_B) excludes 0; otherwise tie.
Calibration: pairs that recompile the identical unit set do identical work, so
any "win" among them measures the rule's false-positive rate here. No outlier
removal anywhere; all raw repeat times are in the CSV.

Corpus: 11 cells (4 real MSL, 4 hand-written fixtures, ThermalChain N=50/250/1000,
mid-room conductance swap).

## 3. Independent source-diff verification (Task 1)

`src/journal_phase2_verify_oracle.py` takes only cell definitions (paths, names,
seeds) and recomputes everything itself: regenerates both models' unit sources
with the production pipeline and compares file contents directly, without calling
the agent's `content_hash_oracle`. Result: identical counts to the agent's CSV on
all 11 cells for all three strategies, and equal to the ground-truth count of
actually changed units (`ALL AGREE: True`). On every cell, oracle is a subset of
paper, which is a subset of baseline.

It also checked what lies outside the unit files. The shared header is identical
by construction (one layout built from both models). The driver differs on every
MSL and fixture cell (unit call list and evaluation order change) and is identical
on the thermal chains. Every strategy always rebuilds the driver, which is a
precondition of the oracle's safety (Section 13).

## 4. Recompilation sets (units recompiled / total)

| Cell | Paper | Baseline | Oracle | Paper units with unchanged source |
|---|---|---|---|---|
| MslRcCircuit swap | 13/23 | 23/23 | 2/23 | 11 (C_i, C_n_i, C_p_i, C_v, G_p_i, R_LossPower, R_n_i, R_p_i, V_i, V_n_i, V_p_i) |
| MslThermalChain swap | 7/20 | 20/20 | 1/20 | 6 (incl. seed G1_dT, whose equation text did not change) |
| MslRcCircuit sensor-add | 1/24 | 24/24 | 1/24 | 0 |
| MslResistorNetwork removal | 11/18 | 18/18 | 3/18 | 8 |
| ThermalNetwork swap | 2/9 | 2/9 | 1/9 | 1 |
| RLCCircuit swap | 1/3 | 1/3 | 1/3 | 0 |
| ThermalNetwork sensor-add | 1/10 | 7/10 | 1/10 | 0 |
| ThermalNetwork removal | 1/6 | 1/6 | 1/6 | 0 |
| ThermalChain50/250/1000 swap | 2 | 2 | 1 | 1 (the downstream state unit T{i}) |

Named sets for every cell: `results/journal_upgrade_phase2_oracle_independent.json`.

Why the paper's set is larger: units read other units' outputs from the shared
struct at run time, and the shared layout keeps slot indices fixed. A downstream
unit's generated code therefore does not change when an upstream equation
changes; only its runtime inputs do. Reachability identifies units whose VALUES
change (semantic impact); the source diff identifies units whose CODE changes.

## 5. Oracle-driven build results (Task 3)

Smoke test (ThermalNetwork swap, 1 repeat): all three strategies bit-identical.
Full run: 33 strategy-cell builds, all completed, none failed.

## 6. Bit-identical correctness

| Check | Result |
|---|---|
| `outputs_identical` (full simulation stdout of incremental reference build == full rebuild) | True on 33/33, including all 11 oracle builds |
| `reused_objects_byte_identical_to_cache` | True on 33/33 |
| oracle build set == independent source diff (guard) | held on all 11 cells |

`incremental_matches_full_for_unaffected_objects` is not a correctness criterion
under the dynamic-link path (two independent `gcc -shared` builds of identical
source differ by a few bytes on this toolchain, documented in
`docs/findings/scaling-bottlenecks.md`).

## 7. Timing results (Task 4)

n = 5 timed repeats per strategy after one untimed warm-up. Speedup = mean full /
mean incremental, 95% Fieller interval. Full per-row statistics (mean, median,
sd, CV, CI, min, max): `results/journal_upgrade_phase2_timing_stats.csv`; raw
repeats: `results/journal_upgrade_phase2_timing.csv`.

| Cell | Full (s) | Paper incr (s) / speedup | Baseline incr (s) / speedup | Oracle incr (s) / speedup |
|---|---|---|---|---|
| MslRcCircuit swap | 1.462 | 1.150 / 1.27 [1.22, 1.33] | 1.401 / 1.04 [0.99, 1.10] | 0.841 / 1.74 [1.65, 1.83] |
| MslThermalChain swap | 1.482 | 0.996 / 1.49 [1.33, 1.67] | 1.285 / 1.15 [1.07, 1.24] | 0.824 / 1.80 [1.68, 1.92] |
| MslRcCircuit sensor-add | 1.580 | 0.820 / 1.93 [1.77, 2.08] | 1.423 / 1.11 [1.01, 1.21] | 0.830 / 1.90 [1.74, 2.07] |
| MslResistorNetwork removal | 1.279 | 1.093 / 1.17 [1.06, 1.30] | 1.328 / 0.96 [0.90, 1.03] | 0.858 / 1.49 [1.41, 1.58] |
| ThermalNetwork swap | 0.946 | 0.824 / 1.15 | 0.830 / 1.14 | 0.814 / 1.16 |
| RLCCircuit swap | 0.815 | 0.819 / 0.99 | 0.813 / 1.00 | 0.822 / 0.99 |
| ThermalNetwork sensor-add | 0.973 | 0.803 / 1.21 | 0.933 / 1.04 | 0.842 / 1.15 |
| ThermalNetwork removal | 0.891 | 0.825 / 1.08 | 0.834 / 1.07 | 0.844 / 1.06 |
| ThermalChain50 | 6.03 | 1.149 / 5.25 [4.55, 6.18] | 1.026 / 5.88 [5.59, 6.17] | 1.003 / 6.01 [5.74, 6.29] |
| ThermalChain250 | 28.72 | 2.381 / 12.07 [9.00, 18.25] | 1.989 / 14.44 [13.35, 15.70] | 1.818 / 15.80 [15.28, 16.33] |
| ThermalChain1000 | 128.83 | 5.111 / 25.21 [23.72, 26.73] | 7.653 / 16.83 [11.38, 31.95] | 5.387 / 23.91 [22.36, 25.53] |

(Fixture full-rebuild values are the shared per-cell means; fixture CIs are in the stats CSV.)

Incremental floor: about 0.8 s even when one unit is recompiled (driver compile,
driver link, process spawn). On the small models this floor bounds every
strategy's speedup, which is why all fixture cells sit near 1.0x to 1.2x.

Anomaly, preserved: on the thermal chains, the large within-cell outliers fall
on whichever strategy ran first in the cell, not on a particular strategy:
N=250 first strategy (paper) repeat 4 = 3.49 s vs about 2.0 s otherwise; N=1000
first strategy (baseline) repeat 4 = 12.74 s vs about 6 s otherwise. This is
consistent with the Phase 1 finding that freshly written DLL caches incur a
first-read cost (Windows Defender real-time on-access scanning is enabled) that
one warm-up rebuild does not fully absorb. These points are not removed.

## 8. Full rebuild comparison

Every strategy beats a full rebuild on every MSL cell except the baseline, whose
interval includes 1.0 on MslRcCircuit swap and MslResistorNetwork removal. The
paper method's MSL speedups (1.17x to 1.93x) are consistent with the paper's
Table III band (1.19x to 1.81x, a different session). ThermalChain1000 paper
method 25.21x vs the paper's 27.01x, also consistent given run-to-run spread.

## 9. Matching (paper) vs baseline

Pairwise verdicts (`results/journal_upgrade_phase2_pairwise.csv`):

- Real MSL models: paper faster on 4/4 cells, by 0.24 to 0.60 s (18% to 42% less
  incremental time), all CIs excluding 0. The baseline recompiles every unit on
  all four (the acausal connect-generated equations make the undirected closure
  cover the whole model).
- Hand-written fixtures: paper faster on ThermalNetwork sensor-add (1 vs 7
  units, 0.13 s); tie on the other three, where the two sets are identical.
- Thermal chains: the two sets are identical (2 units) at every size, so the
  strategies do identical work. Measured differences are ties and track run
  position (Section 7), not strategy.

## 10. Matching (paper) vs oracle

- MSL: oracle faster on 3/4 cells (by 0.17 to 0.31 s, 17% to 27% less
  incremental time); tie on sensor-add, where both recompile the same single new
  unit. Oracle recompiles 7 units in total across the four cells vs 32 for the
  paper method (78% fewer).
- Fixtures: ties, except ThermalNetwork sensor-add where the rule flagged the
  paper method as 0.04 s faster although both build the identical set. This is
  the calibration false positive (1 of 12 identical-work pairs flagged), so
  differences of a few tens of milliseconds on small models are not meaningful.
- Thermal chains: oracle recompiles 1 unit instead of 2, but the saving (one
  parallel `gcc -shared` of a one-line unit, about 0.1 s) is below the noise;
  verdicts are ties at N=50 and N=250, and "paper faster" at N=1000 by 0.28 s,
  which runs opposite to the work done and coincides with run position (paper
  ran last). Treated as a tie.

## 11. Thermal-chain interpretation

The thermal-chain scaling cells are evidence for the incremental build system
(per-unit partition, cached per-unit DLLs, runtime loading), not for
matching-based impact analysis specifically: the matching-free baseline selects
the identical 2-unit set on every chain, and the oracle's 1-unit set is not
measurably cheaper. The speedup growth with N comes from the full rebuild growing
linearly while the incremental rebuild stays small, whatever the selection
strategy.

## 12. MSL interpretation

The real, acausal MSL models are where impact-analysis strategy matters. There,
the matching gives the dependency direction that lets reachability avoid
recompiling the whole model (the direction-agnostic baseline recompiles all
units on every MSL cell and is at or near 1.0x). But the generated-source diff
selects far fewer units again, and building with only those units was
bit-identical to a full rebuild on every cell, and faster than the paper method
on 3 of 4 MSL cells.

## 13. Failures and anomalies

- No build or correctness failure in any of the 33 strategy-cell builds.
- Run-position outliers on the thermal chains (Section 7), preserved.
- One false-positive "win" among 12 identical-work pairs (Section 10), consistent
  with a 5% two-sided rule plus drift.
- Scope limits of the oracle's demonstrated safety (not failures, but conditions
  under which it was tested): (1) the header is shared and identical by
  construction, because the layout is built from both models; a per-model layout
  would shift slot indices and change many unit sources (the oracle would then
  select more units, which is still safe), but a header change that the oracle
  did not hash would NOT be caught; a production content hash must cover the full
  preprocessed compilation input (unit source, included header, compiler flags),
  not only the unit file text. (2) The driver is always rebuilt. (3) Tested on 11
  cells and one simulation trace each; this is evidence, not a proof.

## 14. What this means scientifically

- The matching-based unit partition is what makes incremental rebuilding possible
  at all for acausal models: every strategy tested, including the baseline and
  the oracle, builds on it.
- Graph reachability over the matched graph is a sound but conservative
  selector of what to recompile. On the MSL cells it recompiled 3.2x to 13x more
  units than necessary (per the source diff), costing 17% to 27% of incremental
  time on 3 of 4 cells.
- What reachability does compute correctly is semantic impact: which units'
  runtime values change. That is the right set for re-simulation, re-validation,
  or telling a digital-twin operator which outputs an edit can affect; it is not
  the right set for deciding what to recompile.
- Content-based selection (the source diff) is standard build-system practice
  (Make/Bazel-style hashing of generated sources). It is not a novel algorithm;
  what is established here is that, on top of the matching-based partition and a
  fixed shared layout, it is sound on every tested cell and cheaper than
  reachability on the real MSL cells.

## 15. Claims that remain supported

- Incremental rebuilding with per-unit caching is bit-identical to a full rebuild
  (now 33 more strategy-cell builds, all identical).
- Incremental rebuilding is faster than a full rebuild, with speedup growing with
  model size on the thermal chains (5.25x, 12.07x, 25.21x at N=50/250/1000 for
  the paper method; consistent with the paper's Table IV).
- Matching-derived dependency direction materially narrows impact relative to a
  direction-agnostic closure on real acausal MSL models (4/4 cells, faster in all).
- Soundness of reachability (every changed unit is in its set).

## 16. Claims that need narrowing or reframing

- "Resolve a change's impact by graph reachability, then recompile the predicted
  units" as the recompilation mechanism: reachability over-approximates the
  recompile set; on 3 of 4 MSL cells a source-diff selection was bit-identical
  and faster. The paper should present reachability as semantic impact analysis
  and either adopt content-based selection for recompilation or justify
  reachability explicitly (e.g. it needs no second code generation of the whole
  model; note that the current pipeline regenerates all unit sources anyway).
- The thermal-chain scaling results should be attributed to the build system
  (partition + per-unit caching + dynamic loading), not to matching-based impact
  analysis; a matching-free closure selects the same units there.
- "Every simulation compiler rebuilds from scratch" style framing should not
  imply the contribution is a better recompile-set selector than content hashing.
- The comparison says nothing about matching being unnecessary: the partition
  itself requires it.

## 17. Should the Phase 3+ plan continue unchanged?

Not unchanged. Decision (Section 18): outcome B with elements of C.
- Link ablation: still high value, arguably higher. The scaling claim now rests on
  the build system, so whether linking/copy/first-read costs create a ceiling is
  the central open question.
- Locality: still useful, but reframe: ripple measures semantic impact scope, not
  build cost. Measure both the reachability set and the source-diff set per edit
  position.
- States-as-knowns ablation: still relevant (it shapes the partition every
  strategy depends on).
- RC ladder: lower value; only as topology generality of the build system.
- New targeted experiment worth adding: none that needs a large build; the oracle
  question for the paper's scope is answered on this corpus.

## 18. Decision gate

**Outcome B (narrow the original story), with a C element.** The evidence
supports reframing the contribution as three separable pieces: (1) a
matching-derived unit partition that makes equation-based models compatible with
per-unit incremental builds (necessary for every strategy tested); (2) a
per-unit dynamic-link build that makes incremental cost nearly independent of
model size (the thermal-chain scaling result); (3) reachability over the matched
graph as a semantic change-impact analysis for the twin (which values an edit can
affect), with recompilation driven by generated-source content rather than by
reachability. Outcome D is ruled out on this corpus: the oracle built
bit-identically on 11/11 cells. Outcome A is not supported as stated, because the
paper's recompile-set mechanism is not the best-performing one tested.

Next actions: update the journal plan to this narrower framing (done in
`docs/journal_upgrade/STATUS.md` after this commit), keep the parallel link,
locality, states and RC experiments running with the reframing in mind, then
Phase 1's diagnosis write-up, then synthesis.
