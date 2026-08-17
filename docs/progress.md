# Progress log

Living document. Update this after every commit so a fresh session (or a
fresh agent with no memory of this conversation) can pick up work without
re-deriving context. Newest entries at the top of each phase's log. Do
not delete history -- this is a log, not a status snapshot.

**How to use this file if you are picking up cold:**
1. Read this file top to bottom.
2. Read `prd.md` (phase 1 spec, done), `prd-phase2.md` (phase 2 spec,
   superseded -- see below), and `prd-combined.md` (the CURRENT spec,
   covers all remaining work as one phase with three ordered stages: A
   generality, B scale+break-even, C publication) for the full execution
   rules and feature definitions.
3. Run `python -m pytest tests/ -v` from the repo root (after activating
   `.venv`) to confirm the standing regression suite still passes before
   touching anything.
4. Check the "Next up" line at the top of the Combined-PRD log (below)
   for where to resume -- that log is now the active one.

---

## Combined-PRD status: IN PROGRESS (supersedes the "what's left" list at
## the bottom of the Phase 2 section below -- prd-combined.md subsumes
## everything phase 2 hadn't finished, plus a large amount of new scope)

**Next up: STAGE A IS COMPLETE (Features 1-9, commit `fb977fa`). STAGE B
IS NOW COMPLETE (Features 10-17, commits `410c852` through `194f35e`).
`docs/results.md` (see the entry below) now gathers every Stage A/B
result in one evidence-backed document -- read it, not just this log,
before starting any Stage C writing work. Stage C (Features 18-23:
target venue, full-length restructure, related work, reproducibility
package, threats to validity, final review) is IN PROGRESS: Feature 18
is partially done (`docs/venue.md` -- real venue researched, ACM
template port deferred), and Feature 19 (full-length restructure) is
done, but in IEEE format rather than the ACM template, per explicit user
instruction ("start writing in ieee format... we will change it later
after i have finalised the journal") -- see the dedicated entry below.
Features 20-23 (related work as its own section, reproducibility
package, threats-to-validity as its own section, final review) have not
started; Feature 19's draft already folds a related-work subsection and
a limitations/threats section into itself, so 20/22 are partially
subsumed, not starting from zero.**

**Feature 19 (full-length restructure, IEEE format): DONE.**
`paper/main.tex` + `paper/refs.bib`, `\documentclass[journal]{IEEEtran}`,
compiles clean (three `pdflatex` passes + `bibtex`, zero warnings, every
page rendered to PNG and visually checked, not just a clean compile log
trusted blind) to an 8-page PDF. Every section prd-combined.md's Feature
19 check calls for is present: introduction, background/related work
(with six real, verified citations -- Grieves 2014 on digital twins,
Fritzson et al. 2005 on OpenModelica, Agosta et al. 2023 on MARCO, the
Modelica Language Specification, Condie et al. 2026 on Rumoca itself,
Feldman 1979 on Make, Abbasi et al. 2024 on digital-twin semantic drift
-- each looked up via WebSearch/WebFetch before citing, not recalled
from memory), method, experimental setup, results (four tables, six
figures, all traced directly to `docs/results.md`'s numbers -- MSL
speedup, the O(n^2) codegen bug, speedup vs. size, one-time overhead vs.
size, the break-even sweep), limitations/threats to validity, future
work, and conclusion. Title and prose written in plain, human academic
register per explicit instruction, not AI-slop phrasing. New: PDF export
added alongside the existing deterministic-SVG export in
`src/figures.py`/`src/figures_msl.py`/`src/figures_scale.py` (a shared
`_savefig()` helper writing both formats from the same figure object),
since `pdflatex` has no native SVG support -- SVGs re-confirmed
byte-identical after the change (only new `.pdf` files appeared in `git
status`, no existing file changed). `docs/venue.md` updated to record
this as a deliberate, disclosed pivot, not a replacement for the earlier
EOOLT/ACM research, which remains the concrete next step once an actual
target venue is finalized.

**Results-gathering session (commit `d2a6ee6` and the `docs/results.md`
commit that follows it) -- NOT a Stage C feature, a dedicated pass
requested to assemble everything already measured into one citable
document before any paper writing begins.** Re-ran the full test suite
clean (152 passed, 1 xfailed, unchanged from Stage B's close). Found and
fixed a real reproducibility gap while cross-checking old evidence: the
committed `results/measurements_msl.csv` (from commit `410c852`) did not
match either that commit's own message or `docs/paper.md`'s table --
re-ran `src/measure_msl.py` fresh and got a **fourth** distinct value
for the same experiment, all with identical ripple but timing swinging
up to ~30-40% relative between runs (commit `d2a6ee6` has the full
diagnosis). Traced this to `gcc`/`ld` process-spawn noise dominating on
very small (23-24 total unit) builds -- also independently re-confirmed
on the even-smaller Stage-0 `measure_c.py` cells (RLCCircuit/
ThermalNetwork, 3/9 units: historical 1.54x/2.23x, this session's fresh
rerun 1.01x/1.16x, still bit-identical both times). This is now recorded
as an explicit, documented finding (`docs/results.md` Sections 3.3-3.4,
7.8) rather than a silently "corrected" number. All 6 figures NOT
affected by that rerun were regenerated and confirmed byte-identical to
their previously-committed versions (direct file diff, not visual
inspection). `docs/results.md` also states plainly, for the first time
in one place, that the original ">=100,000 equations" success criterion
was never reached -- largest full-pipeline-verified size is N=500 rooms
/ 1,499 equations; largest Rumoca has ever compiled in this project is
N=10,000 rooms / 29,999 equations (compile-only). See `docs/results.md`
Section 7 for the complete, itemized limitations list (12 items) and
Section 11 for the standing-rules self-check.

**Stage B summary (full detail in the dated entries below).** All 8
features done, real measurements throughout, no projections. Headline
results: codegen's confirmed O(n^2) bottleneck fixed (Feature 12,
~49x faster at 15,000 equations); incremental-vs-full speedup measured
across a 20x size range (149 to 2,999 equations), staying in a 1.8x-2.3x
band rather than growing with size (Feature 13); one-time setup
overhead (Rumoca compile + matching/partition/graph-build) stays under
~5.2% of full-rebuild time at every tested size (Feature 14); a real
change-frequency harness (Feature 15) driving a genuine cumulative
10-change sequence through both a streaming-incremental and a
batched-full-rebuild path; a measured break-even crossing at batch
size 4 -- batching wins once 4+ changes accumulate before a rebuild,
confirmed stable both within measured spread and across an independent
rerun of the same sequence (Feature 16); three figures regenerated
byte-identically across two independent runs (Feature 17). 152 passed,
1 xfailed (up from 144 -- 8 new tests for Features 13-16, all on small
automated sizes; the reported numbers above come from dedicated larger
one-off runs, documented in the feature-by-feature entries below, not
re-run on every test invocation).

**Feature 12 (O(n^2) codegen fix, commit `b0e7ec9`) -- see the dedicated
entry below and `docs/findings/scaling-bottlenecks.md`'s Bottleneck 5
for full detail.** Headline: codegen at 15,000 equations dropped from
88.86s to 1.81s (~49x) by replacing per-unit O(N) list scans/dict
rebuilds with O(1) dict lookups built once per model.

**Environment gotcha found while triaging Feature 12: use PowerShell,
not the Bash tool, for anything that shells out to gcc in this repo.**
Git Bash's PATH puts Git for Windows' own bundled MinGW runtime ahead of
`C:\msys64\mingw64\bin`; `gcc.exe` itself is invoked by absolute path
so it's unaffected, but its internal `cc1.exe` subprocess resolves ITS
OWN runtime DLLs via standard Windows DLL search order (falls through
to PATH), silently loading Git's mismatched DLLs and crashing with exit
code 1 and completely empty stdout/stderr -- indistinguishable from a
real code regression at a glance. Confirmed directly: identical `gcc -c`
invocation failed under Bash, succeeded under PowerShell, on the exact
same file. PowerShell's PATH has only the MSYS2 mingw64 directory, no
conflict.

**Stage A summary (full detail in the dated entries below).** All 9
features done. Headline results: a real per-unit C compile-and-relink
pipeline (not projected) with MEASURED speedup on real
`connect()`-wired MSL components (1.66x, 5.75x, 1.50x across swap/
sensor-add/removal, all bit-identical output); the phase-1 "100% ripple"
negative result was diagnosed and fixed (was an integration-graph
artifact, true ripple 22%); Rumoca's own matching isn't exposed via its
API, so a from-scratch bipartite matcher was built and validated
(catching a real `networkx` non-determinism bug along the way); the
Cauer filter needs genuine index reduction and is out of scope,
documented precisely rather than forced or hidden; Feature 6 (nonlinear
blocks) skipped, no tested model needs one; getting real MSL models
working surfaced and fixed 6 more real latent bugs (Unary node key,
state-equation der-on-either-side, Boolean/expression parameter
defaults, dotted C identifiers, the serious "matched != natural target"
singleton codegen bug, `ir["w"]` never getting a layout slot, and
uninitialized driver memory corrupting output comparisons on removal
changes) -- NONE of which any hand-written fixture had ever exercised.
One real generality wall hit and scoped around rather than solved
under budget: MSL's standard signal-source blocks (Ramp, Sine, ...)
need discrete/event "If"-expression codegen this project doesn't have;
worked around by picking a different swap target (documented in
src/msl_change.py, not silently substituted). 134 tests passing, 1
xfailed (a documented third-party Rumoca bug, not this project's).

**Known environment gotcha found in Stage B prep, read before scaling
scripts:** `nx.strongly_connected_components`/Tarjan-based code is safe
under hash randomization (see the Feature 1-era determinism audit
below), but ANYTHING using bipartite matching (src/matching.py) MUST use
the hand-rolled `_kuhn_max_bipartite_matching`, never
`networkx.bipartite.hopcroft_karp_matching` -- re-confirm this wasn't
reintroduced if matching.py is ever touched again at scale (a natural
temptation when optimizing for 100k+ equations, since a real
Hopcroft-Karp is asymptotically faster than the current O(V*E) Kuhn's
implementation -- if replaced for performance, the replacement MUST
independently be re-verified deterministic across hash seeds via
tests/test_determinism_audit.py's pattern, not assumed safe).

**Stage A Feature 5 is DONE**, pivoted to an index-1 MSL flagship as
planned: `models/msl_rc_circuit/MslRcCircuit.mo` (real
Resistor+Capacitor+Ground+ConstantVoltage, `connect()`-wired,
`structure()` confirms `blocks=23, algebraic_loops=0, matched=true`,
this project's own matcher achieves 23/23). Getting a REAL MSL model
through the pipeline for the first time surfaced and fixed 4 real bugs
no hand-written fixture had ever exercised: (1) MSL's Capacitor writes
`i = C*der(v)` (der on the RHS, opposite of every hand-written fixture)
-- `extract_state_equation` only checked the LHS, fixed to check both;
(2) a real MSL parameter can default to an expression referencing
ANOTHER parameter (`Resistor.T` defaults to `T_ref`) -- driver init
generalized with topological param ordering; (3) real MSL names contain
dots (`R.p.i`), invalid in C identifiers -- new
`model_layout.sanitize_c_ident()` applied everywhere; (4) **the serious
one**: singleton codegen naively assumed "matched variable = natural
syntactic target" and just grabbed "the other side" of the residual --
silently wrong (`R.i = R.R_actual * R.i`, self-referential) whenever the
bipartite matcher assigns an equation to a DIFFERENT variable than its
natural one (confirmed: Ohm's law naturally targets `R.v`, matched to
solve for `R.i` since `R.v` was already claimed). Fixed by routing
singleton codegen through the SAME affine-form extraction Feature 4
built for coupled blocks (`linear_block.affine_form`) -- singleton and
coupled codegen now share one provably-correct foundation instead of two
paths that could silently diverge. Correctness checked against an
independent RC-circuit-theory discrete recursion (exact %g-precision
match) plus a sanity cross-check against Rumoca's own (trustworthy here)
simulation. 113 tests passing, 1 xfailed.

`msl_src/` (gitignored MSL sparse clone) has Electrical.Analog.{Basic,
Sources,Interfaces,Icons} and ModelicaServices checked out; extend the
sparse-checkout set if a different component is needed. Tests needing it
skip gracefully (not error) if it's absent.

**Stage A Feature 6 (nonlinear block solve): SKIPPED, recorded why per
the PRD's own instruction ("only if a real target model needs it...
record that no tested model required it").** Every coupled block built
or found so far (CoupledAlgebraic, CoupledDynamic's y1/y2 pair) is
exactly linear; MslRcCircuit has zero coupled blocks at all (23/23
singleton). No tested model has a genuine nonlinear algebraic loop.

**Honest scope assessment, read this before continuing or reporting
status to the user.** prd-combined.md Section 1 defines "done" as: the
pipeline running on real implicit-equation models, measured speedup up
to >=100,000 equations, a measured break-even change frequency, and a
submitted full-length paper. That is Stage A (9 features) + Stage B (8
features, including scaling to 100k+ equations and a change-frequency
sweep) + Stage C (6 features, including picking a venue and a full
writeup). This is realistically weeks of further work, not something
that completes inside a handful of agent turns -- say so plainly if
asked for a status update rather than implying more is done than is.
As of this entry, Stage A Features 1-4 (of 23 total features across all
three stages) are complete.

**Stage A Feature 1 is DONE.** `feat: source equation-variable matching
and block structure from the compiler`. The literal plan (extract
matching/blocks from Rumoca's own BLT output) hit a real API wall:
`Model.to_dict()`/`to_json()` only expose "dae"/"flat" stages; the
"solve" (matched) stage is explicitly rejected with "use
codegen()/render() for solve-stage targets", and that codegen text is
one flattened function with unmarked SSA temporaries -- no per-equation
block boundaries recoverable from it either. Documented, not forced
through (prd-combined.md Section 7.5 itself anticipates this exact
scenario). Built `src/matching.py` instead: our own bipartite
equation-to-unknown maximum matching + Tarjan SCC for BLT blocks, the
documented fallback from the ORIGINAL year-long prd.md's Feature D1.

Two real bugs found and fixed along the way (both now teeth-tested):
1. A greedy "assign obvious targets first" pre-pass can strand a later
   equation that needed one of the "obvious" targets, even when a valid
   perfect matching exists overall. Fixed: one single full bipartite
   matching pass, not two passes.
2. `networkx.bipartite.hopcroft_karp_matching` was **non-deterministic
   across process runs** on the one real-world graph tested (the MSL
   Cauer filter) -- different runs of the IDENTICAL input JSON produced
   different matching sizes and different unmatched equations. Root
   cause: Python's per-process string hash randomization
   (`PYTHONHASHSEED`) leaking into networkx's internal traversal order,
   even after every input list/set was sorted before being handed to it.
   This is a serious finding for anyone else using networkx's bipartite
   matching in a context requiring reproducibility. Fixed by replacing
   it entirely with a ~15-line hand-rolled deterministic Kuhn's
   algorithm (`_kuhn_max_bipartite_matching` in `src/matching.py`),
   verified stable across 20 repeated calls on the exact scenario that
   used to vary.

Results: **100% match + 100% agreement with known-correct targets** on
every fully-assignment-form fixture (OneLine, DecoupledPair, RLCCircuit,
ThermalNetwork, Chain) -- block counts agree exactly with
`Model.structure().n_blocks` on every one. On the one real MSL model
tested (`Modelica.Electrical.Analog.Examples.CauerLowPassAnalog`, 7
states, 69 equations, saved as `results/fixtures/CauerLowPassAnalog.json`
for the first time): **67/69 (97%) matched**, not the full 69/69 Rumoca
confirms is achievable (`structure().is_matched=True`). Root-caused (not
just observed) to a genuine local structural gap in how this module
extracts "which unknowns does an equation structurally involve" for
`connect()`-derived potential-equality equations specifically -- verified
NOT to be an algorithm bug (the same Kuhn's implementation finds a
provably-complete matching on every smaller isolated subgraph pulled
from this same model). Documented as a known limitation in the module's
own docstring rather than chased to 100% given the scope of everything
else in this PRD.

msl_src/ (gitignored MSL sparse clone) is still present locally from
the phase-2 B1 investigation; re-clone if missing (see the Phase 2
section's B1 note below for the exact clone/sparse-checkout commands).

83 tests passing (71 from before + 12 new in `tests/test_matching.py`).

**User-directed determinism audit (between Feature 1 and Feature 2).**
Requested: check whether the hash-randomization bug class found in
matching.py exists ANYWHERE ELSE networkx sits under this codebase
(dependency graph, SCC partitioning), not just the new matcher. Manual
audit: 20 fresh subprocesses, `PYTHONHASHSEED` unset (freely
randomized), fingerprinting raw units + causalized units + matching +
BLT blocks for all 6 fixtures -- all 20 byte-identical. Theoretical
grounding: SCC decomposition is a mathematically unique partition
regardless of traversal order (unlike bipartite MAXIMUM matching, where
multiple valid maximum matchings can exist -- exactly what made
matching.py vulnerable), and `src/units.py` already sorts before
building ids. Made permanent: `tests/test_determinism_audit.py` spawns
`src/determinism_probe.py` under 5 explicit varied seeds and requires
identical output. Attempted pinning `PYTHONHASHSEED` for the whole test
session via a `conftest.py` `os.execv` re-exec (belt-and-suspenders, as
requested) -- **dropped it**, it silently hung/broke pytest collection
on this Windows/PowerShell setup; the actual protection was always the
explicit multi-seed subprocess test, which doesn't depend on the outer
process's own hash seed. 84 tests passing after this.

**Stage A Feature 2 is DONE.** `feat: define recompilation units over
matched blt blocks`. `src/matched_units.py` redefines a recompilation
unit as a BLT block. New fixture, `models/coupled_algebraic/
CoupledAlgebraic.mo` (y1=2*y2+1, y2=3*y1-2, hand-solvable y1=0.6,
y2=-0.2, `structure()` confirms `algebraic_loops=1`) -- built because
NONE of the 5 assignment-form fixtures have a genuine coupled block
after causalization, so phase 2's SCC-over-causalized-graph definition
had literally never been tested against one before. Result: CoupledAlgebraic
correctly yields ONE unit `{'y1+y2': ['y1','y2']}`, not two singletons.
**No-regression check exceeds the PRD's literal ask** (block COUNT
matching Rumoca's `structure().n_blocks` alone is not sufficient
evidence of a correct partition -- different partitions can share a
count): added `test_matches_phase_2_causalized_scc_partition_exactly`,
asserting the BLT-block unit dict is byte-for-byte IDENTICAL to phase
2's causalized-SCC unit dict on RLCCircuit and ThermalNetwork, plus a
combined test asserting singleton-block-count + per-equation natural-
target agreement together constitute full partition agreement (not a
count coincidence) on all 5 clean fixtures. 99 tests passing.

**Stage A Feature 3 is DONE.** `feat: generate singleton-unit code from
the matching`. `src/matched_codegen.py` generates each singleton unit's
C from `matching.eq_to_var`/`eq_kind` directly, not by re-deriving the
target independently via `ir_equations.equation_target()` (phase 2's
`codegen_units.py`, which happens to agree only because every fixture so
far is fully assignment-form). Bit-identical regression check run on ALL
5 clean fixtures (PRD names only RLC/Thermal explicitly) -- all
identical. **Real pre-existing bug caught**: running the check against
OneLine/DecoupledPair (never run through C codegen before -- only
RLC/ThermalNetwork had been) crashed BOTH the old and new codegen paths
with `KeyError('arg')` in `src/expr_c.py`'s Unary handling -- Rumoca's IR
uses key `"rhs"` for a Unary node's operand (mirroring Binary's lhs/rhs),
not `"arg"`. Fixed, verified with a real gcc build+run of OneLine
(`der(x)=-x`): forward-Euler correctly halves x each step. 106 tests
passing.

**Stage A Feature 4 is DONE.** `feat: emit linear block solves for
coupled units`. `src/linear_block.py` extracts an affine form of each
coupled equation's residual over the block's own unknowns (raises on any
genuine nonlinear term -- product/quotient of two unknowns -- correctly
deferring to Feature 6); `src/block_codegen.py` assembles A/b and emits
a shared C99-VLA Gaussian-elimination-with-partial-pivoting solver;
`src/unit_codegen.py` combines singleton (Feature 3) and coupled
(Feature 4) codegen into one driver, using a new unit-level topological
eval order (`eval_order.unit_eval_order`).

New fixture, `models/coupled_dynamic/CoupledDynamic.mo`: needed because
CoupledAlgebraic (Feature 2's fixture) has zero states/zero time-
dependence, which **Rumoca's own `Model.simulate()` cannot even run**
("did not converge at t=0"). CoupledDynamic adds `der(x)=-x` feeding the
coupled pair (`y1=2*y2+x, y2=3*y1-2*x`, hand-solvable `y1=0.6*x,
y2=-0.2*x`).

**Real finding, not this project's bug** (`docs/findings/
rumoca-algebraic-loop-bug.md`): Rumoca's own `Model.simulate()` gets
CoupledDynamic's t=0 right (0.6, -0.2) but is WRONG from the second
timestep onward on ALL 5 available solvers -- `y2` comes out exactly
equal to `x` (should be `-0.2*x`), `y1` wildly wrong. Consistent with
the CoupledAlgebraic convergence failure -- both symptomatic of Rumoca's
algebraic-loop runtime using an iterative/relaxation scheme (glimpsed
earlier in generated `embedded-c`: a capped 100-iteration fixed-point
loop) that doesn't reliably converge, even on small exactly-linear
systems. This project's own generated C, checked against the
independently-hand-derived formula, matches with **max_abs_error ==
0.0** at every timestep -- so Feature 4's "bit-identical to a full
Rumoca compile" check is satisfied against that analytical ground truth
instead, since matching Rumoca's buggy runtime would validate a wrong
answer. Recorded as an `xfail` test so a future Rumoca fix is caught
automatically.

Teeth (PRD's explicit ask, "perturb the assembled system and confirm
correctness fails"): manually dropped the Sub-handling negation in
`linear_block.py`, rebuilt and ran the real C binary -- y1 came out -0.6
instead of 0.6. Reverted, codified as a permanent monkeypatch-based test.
110 tests passing, 1 xfailed (the documented Rumoca bug).

**Stage A Feature 5 (`de4f1e5`): Cauer filter end to end, pivoted to an
index-1 MSL flagship** (`models/msl_rc_circuit/MslRcCircuit.mo`, real
Resistor+Capacitor+Ground+ConstantVoltage). Confirmed index-1
(`structure()`: blocks=23, algebraic_loops=0; own matcher 23/23).
Surfaced and fixed 4 real bugs no hand-written fixture ever exercised:
(1) MSL's Capacitor writes `i = C*der(v)` (der on the RHS) --
`extract_state_equation` only checked the LHS; (2) a real parameter can
default to an expression referencing another parameter; (3) real MSL
names contain dots, invalid in C identifiers -- new
`sanitize_c_ident()`; (4) **the serious one**: singleton codegen
assumed "matched var = natural target" and grabbed "the other side" of
the residual -- silently wrong (`R.i = R.R_actual * R.i`) whenever the
matcher assigns an equation to a DIFFERENT variable than its natural
one. Fixed by routing singleton codegen through the same affine-form
extraction Feature 4 built for coupled blocks -- singleton and coupled
codegen now share one foundation. Checked against an independent RC-
circuit-theory discrete recursion (exact match) plus a Rumoca sanity
cross-check. 113 tests passing.

**Stage A Feature 6 (`07068a8`): nonlinear block solve -- SKIPPED**, no
tested model (real or hand-written) has a genuine nonlinear coupled
block. Recorded why per the PRD's own instruction.

**Stage A Feature 7 (`6d3ecfc`): full change-type suite on real
models.** New bridge `src/matched_graph.py` (matching-based graph
compatible with `resolver.py`/`soundness.py`'s existing `graph_builder`
interface -- verified SCC-over-this-graph reproduces `matched_units.py`
exactly on all 8 fixtures). Second real model,
`models/msl_resistor_network/MslResistorNetwork.mo`, surfaced a REAL
14-equation LINEAR coupled block (a resistive KCL loop) -- a real-world
stress test for Feature 4's solver well beyond the 2-equation fixtures.
`soundness.py` generalized to use `matching.py` instead of
`ir_equations.equation_targets()` (proven behavior-preserving on every
prior fixture). All 3 change types (component swap, sensor add,
component removal) sound and teeth-tested on the 2 real models; real
finding: the swap's seed needed BOTH the edited equation AND a
genuinely NEW one the swap introduced -- codified as a permanent
regression test. 133 tests passing.

**Stage A Feature 8 (`06e5504`): measured ripple and real speedup on
real models.** New `src/measure_msl.py` (generalizes Stage-0's
`measure_c.py` to per-UNIT not per-equation codegen + matching-based
resolver). Fixed 3 more real bugs: `ir["w"]` ("output"-declared
variables, e.g. a Ramp block's internal signal) never got a layout
slot; the ORIGINALLY-PLANNED swap (ConstantVoltage->RampVoltage) hit a
genuine wall -- every MSL signal-source block compiles its
`startTime`-conditional to an "If" expression over a synthetic
Rumoca-generated condition variable this project's C emitter can't
translate (real discrete/event-signal support, out of scope, documented
in `msl_change.py`, swapped to Resistor->Conductor instead); the
driver's struct was left uninitialized, harmless for swap/sensor-add but
NOT for removal (an orphaned slot's uninitialized garbage differed
between separately-built full/incremental binaries) -- fixed with
`memset`. **Real measured speedups: 1.66x (swap, 56.5% ripple), 5.75x
(sensor-add, 4.2% ripple), 1.50x (removal, 61.1% ripple)**, all
bit-identical output, logged to `results/measurements_msl.{parquet,csv}`.
134 tests passing, 1 xfailed.

**Stage A Feature 9 (`fb977fa`): figures + paper draft updated, STAGE A
COMPLETE.** 3 new deterministic figures (`src/figures_msl.py`).
`docs/paper.md` Section 4.5 added (Stage A addendum with the measured-
speedup table); limitations section rewritten, explicitly marking the
phase-1 "speedup is projected"/"no incremental compiler" limitations as
SUPERSEDED rather than left stale. 134 tests passing, 1 xfailed
(unchanged, docs/figures-only feature).

**Stage B Feature 10 (`410c852`): parameterized model generators for
scale.** `src/scaled_models.py` -- `generate_thermal_chain(n)` (3N-1
equations, same topology as `models/thermal_network`, index-1 by
construction) and `generate_rc_ladder(n)` (2N+1 equations, same coupling
flavor as `models/rlc_circuit`), plus `swap_room_conductance()` (Feature
11's change injector). Hand-written flat equations, not real MSL
component instantiations, deliberately: a real MSL Resistor alone drags
in ~9 equations unrelated to what Stage B tests (pipeline scaling
behavior); Stage A's real-MSL generality claim already stands on its
own. While validating this, found and documented (not "fixed", since
they're third-party/OS limits, not this project's bugs)
`docs/findings/scaling-bottlenecks.md` Bottlenecks 1-4: Rumoca's own
O(n^1.7) compile time, gcc's ~85ms/file subprocess overhead (fixed via
`ThreadPoolExecutor`-based parallel compilation, `src/c_build.py`'s
`compile_many()`, ~4x speedup), Windows' ~32KB command-line length limit
at link time (fixed with gcc/ld response files, `@file` syntax, forward
slashes to dodge gcc's own backslash-escaping in response files), and
relinking a large object count dominating incremental time at scale (a
real design tradeoff, not fixed -- recorded as the honest reason speedup
should plateau, not grow without bound, as N grows).

**Stage B Feature 11 (`c51af07`): correctness and soundness at scale.**
`tests/test_scale_correctness.py` runs the full detect-resolve-
recompile-relink-bit-diff pipeline on a generated 100-room thermal chain
(299 equations) for a local change, asserting: affected units stay
bounded (<=4, not proportional to N), affected fraction stays small
(<2%), and incremental output is BIT-IDENTICAL to a full rebuild -- the
real correctness bar, still met at scale. A larger one-off N=500 run
(1499 equations) validated the same pipeline at real scale outside the
fast automated test (documented in `docs/findings/scaling-
bottlenecks.md`, not re-run every invocation). Found and fixed along the
way: uninitialized driver struct memory on orphaned variable slots
(removal changes leave a shared-layout slot with no writer) made full
vs. incremental builds read different garbage, producing false
correctness failures -- fixed with `memset(&v, 0, sizeof(v))` at driver
start.

**Stage B Feature 12 (O(n^2) codegen fix): DONE.** Per prd-combined.md's
explicit instruction ("Profile and harden the scaling path... If
anything is superlinear, fix it with sparse structures or incremental
construction"), profiled every pipeline stage stage-by-stage on
`ThermalChain{N}` and found codegen genuinely quadratic: 3.13s at 2,999
equations -> 88.86s at 14,999 equations, a 28.4x increase for a 5x size
increase (matching, block-partitioning, and graph-building stages were
all confirmed roughly linear, not superlinear -- codegen was the one
real offender). Root cause: `src/codegen_units.py`'s `generate_unit_c()`
called `layout.name_to_c()` (rebuilds an O(N) dict) and
`layout.y.index(name)` / `layout.x.index(name)` (O(N) list scans)
INSIDE the function body, called once per recompilation unit in a loop
over all N units -- O(N) work done N times, O(N^2) total.
`src/block_codegen.py`'s `generate_block_unit_c()` had the identical
pattern; `src/unit_codegen.py`'s `generate_unit_driver()` had a
smaller-magnitude version over parameters/states. Fixed with two new
O(1) lookup methods on `Layout` (`y_index_map()`, `x_index_map()`,
`src/model_layout.py`), built ONCE per model in the hot-path callers
(`generate_all_unit_sources()`, `generate_unit_driver()`) and threaded
through as optional parameters (falling back to computing them inline
for single-unit callers, e.g. `block_codegen.py`'s own `__main__` demo,
so no call site broke). After the fix: codegen at 14,999 equations
dropped from 88.86s to 1.81s (~49x speedup on that stage), and the
5x-size growth from N=1,000 to N=5,000 now costs 4.85x time --
log(4.85)/log(5) ~= 0.99, linear, not quadratic. Full detail and the
before/after table: `docs/findings/scaling-bottlenecks.md`'s
Bottleneck 5. Teeth: full pytest suite re-run clean after the fix, 144
passed 1 xfailed, identical to before -- confirms the lookup-mechanism
change (list scan -> dict lookup for the same keys) altered no output,
only performance. Also surfaced and documented (not a code bug, an
environment gotcha) that the Bash tool's PATH breaks gcc's internal
`cc1.exe` DLL resolution on this machine -- see the "Next up" note
above; cost real time mid-session before being traced to a PATH
conflict rather than a real regression.

**Stage B Feature 13 (`9fb61d9`): incremental speedup measured across
model sizes.** `src/measure_scale.py` sweeps `ThermalChain{N}` for N in
{50, 100, 250, 500, 1000} rooms (149-2,999 equations), reusing
`measure_msl.run_cell()` unchanged (already model-agnostic) with a new
optional `repeats` parameter (default unchanged at 5, used here at 3 to
keep the whole 5-size sweep affordable -- calibrated directly first: one
N=1000 cell at 3 repeats took 470.9s end to end). Logged to
`results/measurements_scale.{csv,parquet}`. Real measured speedups:
2.27x (N=50), 1.88x (N=100), 2.05x (N=250), 2.13x (N=500), 1.84x
(N=1000) -- all outputs bit-identical, all reused objects
byte-identical to cache. Honest trend: speedup stays in a ~1.8x-2.3x
band across the whole 20x size range instead of growing with size,
consistent with `docs/findings/scaling-bottlenecks.md`'s Bottleneck 4
(relinking the full object set, not recompiling, dominates incremental
cost at this file count -- confirmed again here, not merely
theorized: at N=1000, incremental_stdev_s=11.9s on a 39.3s mean, a
large relative spread consistent with relink-dominated timing being
noisier than compile-dominated timing).

**Stage B Feature 14 (`29d9ac6`): one-time setup overhead measured
across model sizes.** `src/measure_overhead.py` reuses the exact same
sizes as Feature 13 (joins on `n_rooms` against
`results/measurements_scale.csv` for the ratio, no need to re-run
expensive full rebuilds) and measures, per size: Rumoca's own compile
time, plus matching/partition/graph-build time (the "one-time setup"
Feature 12 already profiled and confirmed near-linear). This
measurement itself is cheap (sub-4s even at the largest size tested
here), so it's measured directly rather than reusing old profiling
numbers. Real result at N=1000 (2,999 equations): rumoca_compile=2.70s,
graph_and_partition=1.02s, total_setup=3.72s against a 72.18s full
rebuild -- **5.16% of full-rebuild time.** Across the whole range the
ratio stays in 2.9%-5.2%, never trending sharply upward -- setup cost
stays acceptable at scale over this range, reported at the sizes
actually run, not extrapolated to 100,000 equations.

**Stage B Feature 15 (`f6a120b`): change-frequency harness.**
`src/change_frequency.py` builds a real, CUMULATIVE sequence of K
structural changes (each edit written on top of the previous step's
already-edited `.mo` source, via `swap_room_conductance`, the way a
real codebase actually accumulates edits over time -- not K independent
edits to one original), then drives it through two independently timed
strategies: STREAMING (recompile+relink after every single change,
chained so each step's object cache is the PREVIOUS step's own
incremental build output, never a fresh full rebuild) and BATCHED
(accumulate changes, one real full rebuild per batch). Both are real
gcc/ld wall-clock measurements end to end, nothing arithmetic-derived.
Real sample sequence: N=300 rooms (899 equations), 10 changes (one
every 30 rooms) -- every step affects exactly 2/899 units; streaming
totals 65.522s across 10 steps (5.2s-15.5s per step); batched at
batch_size=5 (2 full rebuilds) totals 44.498s, already cheaper than
streaming at that batch size.

**Stage B Feature 16 (`80407d1`): break-even change frequency
measured.** `src/break_even.py` sweeps batch size (frequency and batch
size are the same knob under a fixed-rate change-arrival model, see
`change_frequency.py`'s docstring) using the real streaming total from
Feature 15's harness (fixed, doesn't depend on batch size) against a
REPEATED (3x), directly measured full-rebuild cost at one representative
point in the chain -- justified, not assumed, by confirming
`total_units` is identical at every step of the chain first (the
harness raises if it isn't). Real crossing found on the same N=300,
10-change sequence: full_rebuild=18.932s +/- 0.332s; streaming_total=
63.009s; **BREAK-EVEN at batch_size=4** (batching wins once 4+ changes
accumulate per rebuild), stable within measured spread (even
batch_size=4's worst-case-slow batched estimate beats streaming's
mean). Rerun-stability check: this run's streaming total (63.009s) was
an INDEPENDENT re-measurement of the identical 10-change sequence
Feature 15 already measured at 65.522s -- within ~4% of each other,
real evidence of stable timings across reruns, not a cherry-picked
number.

**Stage B Feature 17 (`194f35e`): scaling and break-even figures,
STAGE B COMPLETE.** `src/figures_scale.py` -- three new figures
(`speedup_vs_size.svg`, `overhead_vs_size.svg`,
`break_even_crossing.svg`), regenerated from Features 13/14/16's logs
and verified BYTE-IDENTICAL across two independent regenerations
(diffed directly, not just visually inspected). 152 passed, 1 xfailed
(full suite, including all Stage B tests) -- up from 144 at Stage A's
close.

---

## Phase 2 status: IN PROGRESS (superseded by the Combined-PRD section
## above for what to work on next -- kept for history)

**Next up:** Section 9 (characterization), Section 11 (figures), Section
16 (paper upgrade) all remain undone -- see the honest status note below
before starting any of them, since Section 8's MSL attempt (B1) hit a
real architectural blocker that affects what "characterization" can mean
right now.

**Feature B1 (real MSL models) hit a genuine blocker -- read before
retrying.** Cloned `ModelicaStandardLibrary` (sparse checkout into
`msl_src/`, gitignored -- NOT committed, re-clone if needed:
`git clone --depth 1 --filter=blob:none --sparse
https://github.com/modelica/ModelicaStandardLibrary.git msl_src` then
`git sparse-checkout set <paths>` inside it). A single unconnected
component (`Modelica.Electrical.Analog.Basic.Resistor`) compiles but
is `matched=false` (needs a real circuit context). A real circuit,
`Modelica.Electrical.Analog.Examples.CauerLowPassAnalog` (a 7th-order
Cauer filter), DOES compile and simulate correctly through Rumoca after
sparse-checking out its transitive dependencies (Interfaces, Sources,
Icons, ModelicaServices, Math.Random) -- 7 states, 69 equations,
`Model.structure()` reports `algebraic_loops=1`, a genuine one this
time (not diagnosed as an artifact).

**The blocker:** `src/ir_equations.py`'s `equation_target()` assumes
every `f_x[i]` residual has a clean single-variable target (either
`var = expr` or `coef*der(state) = expr`). Real MSL circuits built from
`connect()` statements generate Kirchhoff-law balance equations in the
form `0 = i1 + i2 + ...` (e.g. KCL at a node), which constrain MULTIPLE
variables simultaneously and have no single "target" -- this is
precisely the multi-equation genuine-algebraic-loop case Feature G2
anticipated ("if tearing is not exposed, fall back to residual-function-
level units"). Properly supporting it needs: (1) generalizing
`ir_equations.py` to represent an anonymous residual constraint (no
single target) as its own graph node type, and (2) extending the C
codegen (`src/codegen_units.py`/`src/expr_c.py`) to emit a simultaneous
linear/nonlinear solve for a torn block instead of one function with one
output per equation -- a substantial engineering task, not a quick fix.
**Did not attempt this fix** -- it's a real scoping decision, not
something to force through under time pressure per the PRD's own rule 6
("stop and report when blocked rather than inventing a workaround").
CauerLowPassAnalog's `.mo` file was NOT added as a fixture (its IR
export was generated once to confirm the blocker, then deleted -- it's
not committed and not used anywhere in the pipeline). Options for
whoever picks this up: (a) do the tearing/residual-unit engineering
above, (b) find/construct MSL-derived models that avoid `connect()`-
generated balance equations (rare in real MSL, defeats much of the
realism benefit), or (c) scope Section 9's characterization to the
current fixture set (OneLine, DecoupledPair, RLCCircuit, ThermalNetwork,
Chain) and report the MSL blocker itself as a finding -- honestly
representative of the "these operators aren't supported yet" limitation
Section 15 already anticipates.

**Section 8 (Features B2-B3) is DONE, B1 is a documented blocker (see
above), not silently skipped.**

**Section 7 (Features C1-C2) is DONE.** `src/correctness_c.py` formalizes
the correctness check into a real numeric diff (atol=rtol=1e-9); both
real change cells show EXACTLY zero error (bit-identical binaries).
Teeth proven by corrupting a value and confirming the diff reports it.
Edge cases (`tests/test_c2_edge_cases.py`): a new synthetic `models/chain`
fixture (pure forward chain, no feedback) shows 100% predicted ripple
still produces a byte-identical incremental build; an empty change
(same model as its own "changed" variant) recompiles 0/N units and still
matches. "Change inside a genuine algebraic loop" is NOT exercised --
none exists in any fixture per D2's diagnosis -- and this is recorded
explicitly in the test module rather than silently skipped.

**Section 5 (Features M1-M5) is DONE, and landed on Rung 1 of the
fallback ladder (Section 6) -- the best case: a real per-unit C compile
and relink with measured, not projected, speedup.** Rumoca's
`embedded-c` codegen target turned out to emit one monolithic `.c` file
per model, not one file per recompilation unit, so a bespoke C emitter
was written instead (tractable, since fixture equations are simple
Binary/BuiltinCall/VarRef/Literal trees) rather than post-processing
Rumoca's monolithic output. gcc is available on this machine
(`C:\msys64\mingw64\bin\gcc.exe`) and works from PowerShell (NOT
reliably from this session's Bash -- a `gcc -c foo.c` invoked from Bash
failed silently with exit 1 and no stderr for unclear reasons; the same
command via PowerShell worked fine. **Do all C build/measurement work
via PowerShell, not Bash.**).

**Measured (not projected) speedup, replacing phase 1's projected
ceiling entirely:**
- RLCCircuit: 1/3 units recompiled, full=414.9ms±12.8ms,
  incremental=269.6ms±9.5ms, **measured_speedup=1.54x**
- ThermalNetwork: 2/9 units recompiled, full=910.7ms±50.6ms,
  incremental=408.7ms±41.1ms, **measured_speedup=2.23x**
- Both cells: fingerprint-verified true object reuse, and
  `outputs_identical=True` -- the incrementally-linked binary and a
  from-scratch binary produce byte-identical stdout on the same changed
  model. This IS a strong correctness proof already, though Feature C1
  below formalizes it as a proper numeric diff with tolerance.

Run `python src\measure_c.py` from PowerShell (repo root, venv active)
to reproduce; it deletes nothing on its own, so `rm -rf build_cache`
first if re-running from a clean cache is wanted (harmless either way,
just slower the second time since the "cold cache" build re-happens).

### Phase 2 commit log (newest last, matches `git log`)

1. `docs: open phase two, record phase-one findings in the readme` --
   opened README's phase-2 section with phase-1's mixed finding.
2. `feat: build causalized dependency graph with states as knowns` --
   **found and fixed a real Phase 1 bug**: `graph.py` identified each
   `f_x[i]`'s target *positionally* (assumed `f_x` ordered as
   `[y in dict-key order] + [x in dict-key order]`). Actually `f_x` is
   ordered by *equation appearance in source*, which differs from
   variable *declaration* order whenever a model's equation section
   isn't written in the same order as its declarations (true of
   ThermalNetwork). Fixed via `src/ir_equations.py`, which reads each
   equation's target from its own content (the arg of its
   `BuiltinCall{Der}` for a state equation, or the left operand of its
   top-level residual subtraction for an algebraic one), validated
   against `ir["y"]`/`ir["x"]` on every call. This bug did NOT change
   Phase 1's raw-graph headline SCC sizes (still `[8,1]` for
   ThermalNetwork) but DID corrupt my first causalization attempt before
   I caught it (see the note in this commit's body). Added
   `src/causal_graph.py`: a state's own equation now writes a distinct
   `("der", name)` node, never `("var", name)` -- states are knowns each
   timestep, not solved simultaneously with the algebraics that read
   them, so they can never sit on a cycle. Result: causalized largest SCC
   drops from 8 -> 1 (ThermalNetwork) and 2 -> 1 (RLCCircuit), matching
   `Model.structure()`'s independent BLT-based `algebraic_loops=0` for
   both.
3. `feat: diagnose integration-artifact versus genuine algebraic loops` --
   `src/diagnostic.py` classifies every fixture by comparing raw vs.
   causalized largest-SCC size. Verdict for both real fixtures:
   `integration-artifact`, not `genuine-algebraic-loop`. This means
   **Feature G2 (tearing/residual refinement) is not needed** -- no
   fixture currently has a genuine algebraic loop. (Stays in scope if a
   future model does.)
4. `test: add causalized-graph and diagnostic tests with teeth` -- 18
   new tests. Teeth proven by reverting the D1 fix and watching 5 tests
   go red with exactly the expected wrong verdict.
5. `feat: define recompilation units on the causalized graph` --
   `src/causal_units.py` wires `compute_units` (unchanged, already
   graph-agnostic) to the causalized graph. **Headline numbers:**
   ThermalNetwork raw_unit_count=2 -> causal_unit_count=9 (all
   singleton); RLCCircuit raw=2 -> causal=3 (all singleton).
6. `test: re-validate resolver soundness for the new unit definition` --
   `resolve_impact` and `check_soundness` both gained a `graph_builder`
   parameter so the same logic runs over either graph. Also fixed
   `actually_changed_equations`, which had the identical positional
   `f_x`-ordering bug. **Headline ripple numbers on the causalized graph,
   both independently confirmed sound:**
   - RLCCircuit: total_units=3, affected=['i'], ripple=1/3=33% (was 50% raw)
   - ThermalNetwork: total_units=9, affected=['Q1','T1'], ripple=2/9=22% (was 100% raw)

   This is the granularity-fix payoff: Phase 1's "the whole model
   collapsed" result for ThermalNetwork was the integration-artifact bug,
   not reality; the true ripple is small (2 of 9 units), consistent with
   the model's actual nearest-neighbor topology.
7. `feat: emit one C translation unit per recompilation unit` -- bespoke
   C emitter (`src/expr_c.py`, `src/model_layout.py`,
   `src/codegen_units.py`, `src/eval_order.py`), since Rumoca's own
   `embedded-c` target is monolithic. 9/9 ThermalNetwork unit files
   compiled standalone to non-empty `.o`.
8. `feat: compile per-unit objects and link a runnable simulation, and
   add full-rebuild baseline path` -- `src/c_build.py`: real subprocess
   `gcc` calls, timed. Linked and ran a real `.exe`, output matched the
   hand-verified trajectory exactly.
9. `feat: recompile only affected objects and relink incrementally, with
   measured timing` -- `src/measure_c.py`. **Measured speedup: RLCCircuit
   1.54x (1/3 units recompiled), ThermalNetwork 2.23x (2/9 units
   recompiled).** Fingerprint-verified true object reuse;
   `outputs_identical=True` for both (incremental and full-rebuild
   binaries produce byte-identical output on the same changed model).
   This is Rung 1 of the Section 6 fallback ladder -- the best case.
10. `test: validate incremental output against full rebuild` -- Feature
    C1. `src/correctness_c.py`: real numeric diff, atol=rtol=1e-9. Both
    cells: max_abs_error=0.0 exactly. Corrupted-output teeth test.
11. `test: cover incremental correctness edge cases` -- Feature C2. New
    `models/chain` fixture (pure forward chain) for the near-full-ripple
    case (3/3 units predicted affected, still byte-identical output);
    empty-change case (same model vs. itself, 0 units recompiled).
    "Genuine algebraic loop" case recorded as not-yet-exercised.
12. `feat: inject sensor-add and component-removal changes with
    soundness check` -- Features B2, B3. `add_sensor_thermal_network`
    (adds `Qtotal`, one new equation, sound, teeth-checked) and
    `remove_component_thermal_network` (removes room 3 cleanly, no
    dangling references, sound, teeth-checked) in `src/change.py`.

**Feature B1 (real MSL models) attempted, hit a genuine architectural
blocker, not committed -- see the detailed note above the commit log.**
In short: real MSL circuits generate Kirchhoff-law balance equations
with no single "target variable" per equation, which both
`ir_equations.py` and the C codegen currently assume. No commit for this
because nothing was built that's safe to ship; the finding itself is
documented above for whoever resumes.

**Section 3 (diagnosis), Section 4 (granularity fix), Section 5
(measured incremental recompile+relink), Section 7 (correctness
validation), and Section 8's B2/B3 (sensor-add, component-removal) are
all complete.** B1 (MSL) is a documented blocker. This covers roughly
Weeks 1-7 of the phase-2 PRD's own 8-10 week estimate, and crucially
includes Section 5, which the PRD itself calls "the hard, risk-bearing
part" that "may take longer than the rest of the phase combined" -- it
did not turn out to be a hard wall on this codebase.

### What's left in Phase 2 (not started)

- **Section 8 (Feature B1):** blocked, see the detailed note above --
  real MSL models need the tearing/residual-unit engineering described
  there before they can flow through this pipeline.
- **Section 9 (Features S1-S2):** structural metrics per model (largest
  SCC/tearing-block size, coupling density, states:algebraic ratio);
  relate ripple and measured speedup to those metrics across the suite.
  Can proceed now on the current fixture set (OneLine, DecoupledPair,
  RLCCircuit, ThermalNetwork, Chain) without waiting on B1.
- **Section 11:** six new figures from measured (not projected) data.
- **Section 16:** upgrade `docs/paper.md` to a full paper with measured
  results, the granularity fix as a named contribution, and the
  characterization findings.

### Known constraints / environment notes for whoever picks this up

- No Rust toolchain on this machine; the whole pipeline is
  Python-only, driving `rumoca` (pip package, `rumoca==0.9.20`) via its
  Python API (`rumoca.Session().load(...)`), not by building the Rust
  compiler from source.
- Python: use `.venv\Scripts\python.exe` (a venv built from the Windows
  Store Python 3.11.9 install, NOT the `python` on PATH in Bash, which
  resolves to a pip-less MSYS2 Python 3.14). PowerShell is the primary
  shell for anything venv-related; Bash is fine for git/file operations.
- gcc is available at `C:\msys64\mingw64\bin\gcc.exe`, confirmed working,
  for whatever C toolchain Section 5 ends up needing.
- Rumoca's Python API surface relevant to this project: `Session().load()`,
  `Model.to_json(stage="dae")` / `.to_dict(stage="dae")` (the IR this
  whole pipeline is built on), `Model.structure()` (independent BLT
  info: `n_blocks`, `n_algebraic_loops`, `is_matched` -- used as a
  cross-check, not a data source), `Model.simulate()`, `Model.codegen(target)`
  (target `"embedded-c"` emits one monolithic `.h`/`.c` pair, not
  per-unit -- relevant to Section 5's decision above).
- Git identity is already configured correctly at the global level
  (parth-garg01 / parth.garg2024@vitstudent.ac.in) -- no per-repo config
  needed, per the user's global CLAUDE.md instructions.

---

## Phase 1 status: COMPLETE (12 commits, see `prd.md`)

Built the full feasibility-study pipeline on the exported IR only (no
codegen, no linking): dependency graph -> recompilation units (SCCs) ->
change injection (component swap) -> graph-based impact resolver ->
ripple measurement -> soundness validation against an independent diff
-> figures -> paper draft (`docs/paper.md`).

**Headline phase-1 finding (superseded by phase-2's granularity fix for
ThermalNetwork, see above -- kept here for history):** RLCCircuit showed
50% ripple (1/2 units); ThermalNetwork showed 100% ripple (1/1 unit,
whole model collapsed) -- later diagnosed in phase 2 as an integration
artifact, not real coupling. The projected speedup ceiling
(`1/affected_fraction`) was explicitly labeled a projection, not a
measurement, per phase 1's own honesty rules.

Four fixture models (hand-written, since MSL is not bundled with the
`rumoca` pip package -- disclosed in `README.md` and `docs/paper.md`):
`OneLine`, `DecoupledPair`, `RLCCircuit`, `ThermalNetwork`, plus their
`_swapped` variants (component-swap change: nonlinear resistor for RLC,
proportional thermostat for ThermalNetwork's heater).

22 tests passing at phase-1 close (now 53, after phase-2 additions).
