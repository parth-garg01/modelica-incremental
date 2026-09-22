# Phase 2 draft: a fair simpler baseline, and a content-hash oracle

Status: graph-level results measured (no gcc). Build-timing driver written,
not yet run. Everything below the "Prediction" heading is a prediction.

Files:
- `src/journal_naive_resolver.py`: baseline resolver (`resolve_impact_naive`),
  content-hash oracle (`content_hash_oracle`), the cell list, and the
  graph-level comparison (`python src/journal_naive_resolver.py`).
- `tests/test_journal_naive_resolver.py`: 42 graph-level tests, all passing
  (Rumoca compiles and pure-Python codegen only).
- `results/journal_upgrade_phase2_ripple.csv`: graph-level results, 11 cells.
- `src/journal_baseline_compare.py`: build-timing driver (not run).

## 1. What a simpler strategy may know

The paper's method needs one thing a simpler tool does not have: the
matching, i.e. which unknown each algebraic equation is solved for. That is
what turns the equation-variable incidence into a *directed* data-flow
graph. The baseline is therefore allowed exactly this:

| Information | Baseline may use? | Why |
|---|---|---|
| Incidence: which non-state unknowns each residual in `f_x` mentions | yes | read directly off the IR |
| Which rows are state rows (contain `der(x)`) | yes | syntactic; `matching.compute_matching` classifies these before running any matching |
| States are knowns within a step; a state row writes only `der(x)`, which no per-step equation reads | yes | the same assumption the paper's graph makes (state rows have no out-edges); giving it to both methods isolates the one real difference |
| Seed equations (what the injector edited) | yes | same seeds as the paper's method |
| Matching of algebraic rows (data-flow direction) | **no** | this is the proposed method's contribution |
| Unit partition and code generator | only as bookkeeping | the decision is mapped onto the same units so builds are comparable |

## 2. Candidates considered, and the one chosen

**Chosen (primary): undirected incidence closure, states as knowns.**
Starting from the seed equations, follow shared unknowns in both
directions, transitively; state rows can be reached but never propagate.
Affected units are all units containing a reached equation. Without
direction, an equation that shares an unknown with a changed equation may be
the producer or the consumer of that unknown, so following both directions
is the least a sound strategy can do. Treating states as knowns is the
strongest version of this baseline that is still fully matching-free, so it
is the fair choice rather than a strawman.

**Rejected: undirected closure without state knowledge**
(`states_as_knowns=False`). States propagate like any other shared variable.
Measured: 100% ripple on all 11 cells (column
`naive_no_state_knowledge_ripple`). It degenerates to a full rebuild
everywhere, so comparing against it would be a strawman.

**Considered, not adopted: component-level granularity** (recompile every
unit whose matched variable shares an instance prefix such as `R.` with a
seed). Probed on the 4 MSL cells: 9/23, 6/20, 1/24 and 14/18 units. It is
meaningless on the flat thermal fixtures and chains (no prefixes). Its seed
prefixes also have to be derived from the paper's seed names, and in these
cells it only covers what changed because of the runtime-struct property
described in Section 4 (the same property that makes the oracle small). It
is not a dependency analysis, so it is not an alternative impact-analysis
strategy.

**Considered, not adopted: syntactic direction** (use the written
`lhs = rhs` form as the direction where one exists). On the assignment-form
fixtures this reduces exactly to the paper's method
(`agrees_with_natural_targets()` holds on them). On acausal MSL models it
can be wrong: the matcher solves Ohm's law for `R.i` rather than its
syntactic target `R.v` (`docs/results.md` 1.1 step 4). Following a wrong
direction can drop affected units, so this strategy is not sound in general.

## 3. Graph-level results

Source: `results/journal_upgrade_phase2_ripple.csv`. Affected units / total,
with ripple = affected / total. Soundness is `soundness.check_soundness`
with the matched graph.

| Cell | Units | Paper (matching) | Baseline (naive) | Oracle | Actually changed | Sound (P/N/O) |
|---|---:|---:|---:|---:|---:|---|
| MslRcCircuit/swap | 23 | 13 (56.5%) | 23 (100%) | 2 (8.7%) | 2 | Y/Y/Y |
| MslThermalChain/swap | 20 | 7 (35.0%) | 20 (100%) | 1 (5.0%) | 1 | Y/Y/Y |
| MslRcCircuit/sensor-add | 24 | 1 (4.2%) | 24 (100%) | 1 (4.2%) | 1 | Y/Y/Y |
| MslResistorNetwork/removal | 18 | 11 (61.1%) | 18 (100%) | 3 (16.7%) | 3 | Y/Y/Y |
| ThermalNetwork/swap | 9 | 2 (22.2%) | 2 (22.2%) | 1 (11.1%) | 1 | Y/Y/Y |
| RLCCircuit/swap | 3 | 1 (33.3%) | 1 (33.3%) | 1 (33.3%) | 1 | Y/Y/Y |
| ThermalNetwork/sensor-add | 10 | 1 (10.0%) | 7 (70.0%) | 1 (10.0%) | 1 | Y/Y/Y |
| ThermalNetwork/removal | 6 | 1 (16.7%) | 1 (16.7%) | 1 (16.7%) | 1 | Y/Y/Y |
| ThermalChain50/swap | 149 | 2 (1.3%) | 2 (1.3%) | 1 (0.7%) | 1 | Y/Y/Y |
| ThermalChain250/swap | 749 | 2 (0.27%) | 2 (0.27%) | 1 (0.13%) | 1 | Y/Y/Y |
| ThermalChain1000/swap | 2999 | 2 (0.07%) | 2 (0.07%) | 1 (0.03%) | 1 | Y/Y/Y |

Also, on every cell: paper set is a subset of the baseline set; oracle set
is a subset of the paper set; oracle set equals the ground-truth
"actually changed" unit set exactly (`oracle_equals_actually_changed`).

**Reading the baseline result.**
- On acausal MSL models (connect-generated KCL/KVL residuals), missing
  direction costs everything: the algebraic incidence graph is one
  connected piece, so the baseline recompiles 100% of units in all 4 cells.
  The paper's method recompiles 4% to 61%. This is where the matching earns
  its keep.
- On assignment-form models, the matching adds little: the baseline equals
  the paper's method on 6 of 7 non-MSL cells, including every thermal-chain
  size. A changed row that only feeds a state row is stopped by the state
  cut in both methods. The one fixture where direction matters is the
  sensor-add (`Qtotal = Q1env + Q2env + Q3env`: 7/10 vs 1/10), because
  without direction the new sensor row might be producing any of the
  variables it reads.
- The paper's scaling headline (ThermalChain, ripple of 2 units at every N)
  is therefore **not** evidence for matching over this baseline: the
  simpler strategy reaches the same 2 units. The MSL cells are the evidence.

**Resolver wall time** (pure Python, `perf_counter`, 5 repeats, mean; the
machine was running a separate long timing experiment at the same time, so
treat these as indicative; two runs differed by up to ~40%):

| Cell | Paper | Baseline (full, incl. unit mapping) | Baseline closure only | Oracle (codegen both models + diff) |
|---|---:|---:|---:|---:|
| MslRcCircuit/swap | 5.8 ms | 10.2 ms | 5.9 ms | 28.1 ms |
| MslResistorNetwork/removal | 3.6 ms | 8.0 ms | 1.7 ms | 32.1 ms |
| ThermalChain250/swap | 135 ms | 321 ms | 91 ms | 675 ms |
| ThermalChain1000/swap | 588 ms | 1360 ms | 382 ms | 3029 ms |

The baseline's own closure is cheaper than the paper's resolver, but
expressing it on the shared unit partition requires the matching anyway, so
the fair end-to-end number is the "full" column. All three are well under
one second below N=1000 and small next to gcc time.

## 4. Oracle findings and what they imply for the paper's claims

The oracle regenerates every unit's C source for the baseline and changed
models (`unit_codegen.generate_all_unit_sources`, shared
`model_layout.build_layout(baseline_ir, changed_ir)`, exactly as
`measure_msl.run_cell` does) and counts units whose text is new or
different.

**Finding.** A downstream unit's C source does **not** change when an
upstream unit's equation changes. Each unit reads other variables from the
shared struct (`v->y[k]`) at runtime, and the shared union layout keeps
every slot index fixed, so a unit's text depends only on its own
equation(s) and the layout. The header is identical for both builds (same
layout), and the driver is always rebuilt. The oracle set therefore equals
the set of units whose own equations changed. It matched the independent
ground truth exactly in all 11 cells, and is 2/23, 1/20, 1/24 and 3/18 on
the MSL cells where the paper's method recompiles 13, 7, 1 and 11.

**Implication (stated plainly).** Under this code generator, graph
reachability is a sound but conservative **over-approximation** of what
must be recompiled to reproduce a full rebuild bit for bit. Rebuilding the
directly edited units, plus any unit whose matching changed (which content
hashing detects automatically), is sufficient. The paper should not claim
that the downstream units in the reachability set *need* recompilation.
Honest framings that remain true:
1. Reachability computes *semantic* impact: the set of units whose runtime
   values may change. That is the right set for re-validation, test or
   re-simulation selection, and invalidating cached results, but it is not
   the minimal build set.
2. Reachability becomes necessary for the build only if code generation
   crosses unit boundaries (inlining, constant folding, or fusing an
   upstream expression into a downstream unit) or if slot layout is not
   kept stable. The current generator does neither, by design.
3. `soundness.check_soundness` checks coverage of *directly* changed
   equations only. Any strategy that contains the seeds passes it, so the
   check does not separate the three strategies. The build-level checks
   (fingerprints, `outputs_identical`) are the ones that matter for the
   timing comparison.
4. The existing pipeline already regenerates every changed-model unit
   source (`run_cell` writes all of them), so a content-hash comparison
   against the cached sources costs almost nothing extra. A reviewer will
   ask why the build does not simply do that. The paper needs an answer:
   for example, reachability works *before* codegen and needs no cached
   sources, it provides the semantic-impact set, and a content hash needs
   the baseline sources or hashes to be stored.

Where matching still clearly beats the fair simpler baseline: on acausal
models, *for semantic impact*, 4% to 61% versus 100%. Where it does not:
assignment-form models, including the generated scaling family.

## 5. Prediction for the timing run (PREDICTION, not measured)

Command (run alone, serially):
`$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe src\journal_baseline_compare.py`
(`--smoke` for a 1-repeat ThermalNetwork check; `--only <label>` to select
cells). Output: `results/journal_upgrade_phase2_timing.csv`.

Anchors from existing measurements (`results/measurements_msl.csv`,
`measurements_scale.csv`, same dynamic-link build, 12 logical cores):
incremental MSL builds took 0.84 s (1 unit), 0.95 s (7), 1.08 s (11) and
1.22 s (13); full MSL rebuilds took 1.3 s to 1.5 s.

Predicted:
- **MSL, naive:** it recompiles every unit, so incremental time is about
  the same as a full rebuild. Speedup is roughly 1.0 (maybe slightly above,
  since nothing is copied).
- **MSL, oracle:** it recompiles 1 to 3 units, so incremental time should
  be about 0.85 s to 0.9 s on all four cells. Speedup should be roughly
  1.5x to 1.8x, versus the paper's 1.2x to 1.8x. The largest gap should be
  on MslRcCircuit/swap and MslResistorNetwork/removal. With 12 parallel
  workers, the gap in wall time is smaller than the gap in unit count.
- **ThermalNetwork sensor-add:** naive recompiles 7 of 10 units and the
  other two recompile 1. The difference is probably within noise at this
  size.
- **ThermalChain N = 50/250/1000:** the three strategies should be within
  noise of each other (2, 2 and 1 units). Incremental time there is
  dominated by copying N cached DLLs and rebuilding the driver, not by the
  one or two unit compiles. Speedups should stay near the existing 5.7x,
  15.5x and 27x.
- **Correctness:** `outputs_identical`, `reused_objects_byte_identical_to_cache`
  and `incremental_matches_full_for_unaffected_objects` are expected to be
  True for all three strategies. This is expected for the oracle as well,
  because of Section 4. A False result for the oracle would contradict the
  finding and must be investigated, not dropped.
