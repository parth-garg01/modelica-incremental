# Phase 5: states-as-knowns dependency ablation

Graph level and code-generation level only (no C builds needed; see Section 4 for
why a build is impossible under the naive variant). Script
`src/journal_state_ablation.py` (drafted by the stopped parallel worker, reviewed,
probe output persistence added, rerun 2026-09-23). Outputs in
`results/journal_upgrade/states_ablation_parallel/`: `state_ablation_units.csv`,
`state_ablation_ripple.csv`, `state_ablation_probes.json`. The rerun reproduced
the worker's draft CSVs byte-for-byte, as expected for a deterministic metric
(the drafts were then removed as redundant copies).

## 1. Question and design

Does the single design choice "a state is not an edge source" (a state is a known
at each step; its derivative row writes der(x), not x) materially change the
dependency analysis, the partition, the recompilation scope, and whether code can
be generated?

`build_ablation_graph(ir, states_as_edge_sources)` toggles only that choice. The
matching, the unit definition (SCCs), the resolver and the soundness check are
unchanged. Toggle False reproduces `matched_graph.build_matched_graph()` and
`compute_matched_units()` exactly (asserted on every model). Toggle True: the
derivative row writes the state itself and every equation reading the state gets a
read edge from it. The phase-1 raw graph is reported alongside where it can parse
the model (it cannot parse connect-generated residuals).

Corpus: 7 hand-written fixtures, 3 real MSL models, ThermalChain N=10/50/250/1000,
RcLadder N=10/50/250; change cells from Phase 2 plus thermal-chain swaps.

## 2. Partition

- State-aware (False): unit count equals Rumoca's own independent block count
  (`Model.structure().n_blocks`) on all 16 models where Rumoca reported one
  (ThermalChain1000 skipped: `structure()` too slow at that size).
- Naive (True): disagrees with Rumoca on 10 of those 16. Every thermal chain
  collapses into ONE unit containing the whole model (29/29 ... 2,999/2,999
  equations). MslThermalChain: 20 units to 5 (one 16-equation block). MslRcCircuit:
  23 to 16 (one 8-equation block). RcLadder: N pairs of 2-equation blocks. RLCCircuit:
  3 to 2. ThermalNetwork: 9 to 2 (one 8-equation block).
- Unaffected: models where no state feeds back into the algebraic system (OneLine,
  DecoupledPair, Chain, CoupledAlgebraic, CoupledDynamic, MslResistorNetwork, which
  has no states).
- The phase-1 raw graph behaves exactly like the naive toggle wherever it parses.

## 3. Recompilation scope (ripple)

Both variants are sound on every cell (every actually changed unit is selected).
The difference is scope:

| Cell | State-aware: affected / total units (equations recompiled) | Naive |
|---|---|---|
| ThermalChain N=10/50/250/1000 room swap | 2 / 29, 149, 749, 2999 (2 eqs) | 1 / 1 (all 29 ... 2,999 eqs, ripple 100%) |
| ThermalNetwork swap | 2 / 9 (2) | 1 / 1 (9, 100%) |
| MslThermalChain swap | 7 / 20 (7) | 3 / 5 (18 of 22 eqs) |
| MslRcCircuit swap | 13 / 23 (13) | 9 / 16 (16) |
| RLCCircuit swap | 1 / 3 (1) | 1 / 2 (2) |
| MslResistorNetwork removal | 11 / 18 (19) | identical |

Under the naive treatment the incremental build degenerates to a full rebuild on
every generated chain, at every size: the growing-speedup result could not exist.

## 4. Code generation and correctness

- On every model whose partition the toggle changes (RLCCircuit, ThermalNetwork,
  MslRcCircuit, MslThermalChain, ThermalChain10/50, RcLadder10/50), the repo's own
  unit code generator fails on the naive partition: `NotImplementedError: an
  unknown appears inside an unsupported node for affine extraction: ['BuiltinCall']`.
  A merged unit contains a derivative equation, and the explicit-step emitter
  (which solves algebraic blocks and then updates states) has no meaning for a
  block that mixes der(x) with algebraic unknowns. So the naive variant is not
  buildable here, and no build/correctness comparison is possible. On models the
  toggle does not change, codegen succeeds identically.
- A pure-Python semantic probe (solve one step with x and der(x) identified as the
  same unknown) gives wrong derivatives on the state-bearing fixtures (max abs
  error 1.2 to 10.6). This is WEAK evidence: it tests a literal reading of "the
  derivative row writes x" that the graph toggle does not implement (it also
  reports an error on OneLine, whose partition is identical under both variants),
  and that reading is trivially wrong. It is recorded, not relied on.

## 5. Interpretation

The state-aware treatment is required for the semantics this project supports
(index-1 models integrated with an explicit per-step update: at each step, states
are known inputs, the algebraic system is solved, then derivatives are evaluated).
Treating states as edge sources creates cycles that do not exist in that
computation: it merges state equations with the algebraic blocks that read them,
disagrees with the compiler's own block structure, turns every thermal-chain edit
into a full rebuild, and produces units the code generator cannot emit.

This is standard practice, not a new idea: Modelica causalization and BLT
sorting (e.g. OpenModelica's backend, and Rumoca's own `structure()`, which agrees
with the state-aware partition on every model) treat states as known at each step.

**Recommendation for the paper:** present it as a methodological requirement with
ablation evidence (one short paragraph plus the collapse-to-one-unit numbers), not
as a separate technical contribution. The earlier project history (phase-1 graph
collapsing ThermalNetwork to one unit) is an implementation correction that brought
the pipeline in line with standard causalization; the ablation now quantifies why it
matters for incremental builds specifically (100% ripple on every chain otherwise).
