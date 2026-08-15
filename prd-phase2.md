# PRD Phase 2: From Feasibility to Measured Incremental Recompilation

## Drift-Triggered Incremental Recompilation for Structurally-Evolving Digital Twins (from projected to measured)

---

## 0. Where phase 1 left off, and what this phase is

Phase 1 is done. It built the pipeline, measured how local structural changes are, and produced an honest mixed result: the RLC circuit showed a local change (about half the units affected), while the three-room thermal network showed the whole model collapsing into a single dependency block, so a local change appeared to touch everything.

That thermal result is the pivot for this phase. A nearest-neighbor thermal network should not collapse into one block, so before anything else this phase diagnoses why it did, and then fixes the unit definition so it survives feedback-heavy models. Alongside that, this phase does the one thing that turns the work from a preliminary note into a real paper: it replaces the projected speedup with a measured one, from a genuine partial recompile and relink, validated for numerical correctness.

Be honest with yourself about difficulty. Phase 1 stayed on the exported intermediate representation and never touched code generation or linking. This phase does touch them. The measured-speedup work in Section 5 is the hard, risk-bearing part, and it may take longer than the rest of the phase combined. That is expected. The fallback ladder in Section 6 exists for exactly that reason.

This is an agent brief again, written to be executed by an LLM coding IDE with light human supervision. Read Sections 2, 3, and 5 before writing code.

---

## 1. Goal of this phase

Primary goal: a measured incremental recompile-and-relink speedup on real models, using a recompilation-unit definition that does not collapse on feedback-heavy models, with numerical correctness validated against a full rebuild.

Secondary goals: broaden from hand-written fixtures to recognizable Modelica Standard Library models spanning a range of coupling structures, add the two remaining change types, and systematically characterize which structural properties predict benefit.

Publication goal: upgrade the phase-1 short-paper draft into a full paper carrying measured results, the granularity fix as a named contribution, and an empirical characterization of when the approach helps. That combination is what moves the work toward a main-track venue rather than a work-in-progress track.

---

## 2. How the coding agent must work

The phase-1 conduct rules still hold in full: real data only, paste real command output for every claim, never stub the core, one commit per verified feature, stop and report when blocked rather than inventing a workaround, stay minimal, and prove every test has teeth by breaking the code and watching the right test go red.

Three rules are sharpened for this phase, because this phase measures things and the temptation to fabricate a favorable measurement is higher.

1. The incremental time must come from a genuine partial recompile and relink. Never produce a measured incremental time by timing a full build and subtracting, by scaling a full time by a fraction, or by any arithmetic on the full build. If a real incremental path cannot be built, stop, say so, and drop to the fallback ladder in Section 6, labeling the result honestly as an estimate rather than a measurement.
2. Correctness must be a real numeric diff between the incremental program's simulation output and the full-rebuild program's output, on the same changed model. Never loosen the tolerance to force a pass. If the diff fails, fix the resolver or the invalidation logic, not the tolerance.
3. Report mixed and negative results plainly. If a model class does not benefit, that is a finding to state, not a failure to bury. The phase-1 thermal result is the model to follow here: honest, flagged, turned into a research direction.

---

## 3. Diagnose the granularity collapse (do this first)

Do not build the fix before you know which problem you have. There are two candidate causes and they need different fixes.

Cause A, an integration-feedback artifact. In simulation code generation the solver provides the states as knowns each timestep, and the model computes the algebraic variables and the state derivatives from them. If the phase-1 graph instead treated each state as depending on its own derivative, then any derivative that depends on a neighboring flow that depends on the state forms a cycle, and the whole feedback-coupled model becomes one strongly-connected component even though the per-timestep computation is acyclic. If this is the cause, the thermal ripple should drop sharply once the graph is rebuilt with states as knowns.

Cause B, a genuine algebraic loop. If, after treating states as knowns, a large strongly-connected block of algebraic equations still remains, then the model really does contain a large simultaneous system, and the collapse is real. This needs tearing or a finer unit definition, not a graph correction.

Feature D1: Causalized dependency graph.
How: rebuild the dependency graph over the unknowns that are actually solved each timestep, which are the algebraic variables and the state derivatives, with the states themselves treated as external inputs (knowns) and the integration edge excluded. Rumoca's pipeline runs a BLT matching stage before the DAE intermediate representation, so first inspect whether the exported representation already encodes this matched and causalized structure; if it does, derive the graph from it directly, and if it does not, compute the equation-to-unknown matching yourself with states excluded from the unknown set.
Sanity check: on the hand-checkable decoupled pair the causalized graph is unchanged, and on the thermal network the largest strongly-connected component is either much smaller than before (cause A) or still large (cause B). Paste the component sizes for both the raw and the causalized graph.
Commit: feat: build causalized dependency graph with states as knowns.

Feature D2: Collapse diagnostic.
How: write a diagnostic that, for every fixture, reports the strongly-connected-component size distribution in the raw variable graph and in the causalized graph, and labels each large block as integration-artifact or genuine-algebraic-loop.
Sanity check: the diagnostic classifies the RLC circuit and the thermal network, and its verdict matches what you can confirm by reading the two models. Paste the report.
Commit: feat: diagnose integration-artifact versus genuine algebraic loops.

The outcome of D1 and D2 decides whether Section 4 needs only Fix A, or also Fix B.

---

## 4. Fix the recompilation-unit granularity

Feature G1: Units on the causalized graph.
How: redefine recompilation units as the strongly-connected components of the causalized graph, so that spurious integration cycles no longer merge unrelated blocks.
Sanity check: units still cover every equation with no overlap, identifiers are stable across an unchanged re-run, and the thermal network's unit count increases relative to phase 1 if cause A held. Paste before-and-after unit counts for every fixture.
Commit: feat: define recompilation units on the causalized graph.

Feature G2: Tearing or residual-level refinement, conditional on the diagnosis.
How: only if D2 found a genuine algebraic loop. Break the large block into a finer structure. First investigate whether Rumoca exposes tearing of algebraic loops in its representation, and if it does, define units at the level of the torn structure so a local equation change touches only part of the block. If tearing is not exposed, fall back to residual-function-level units, where each equation's residual is treated as its own recompilable artifact and the block shares a solver harness that is relinked rather than regenerated. Document which route was taken and why.
Sanity check: for a model with a genuine algebraic loop, a change confined to one equation resolves to a strict subset of the block rather than the whole block. Paste the affected set.
Commit: feat: refine units for genuine algebraic loops via tearing or residuals.

Feature G3: Soundness re-validation.
How: re-run the phase-1 soundness discipline against the new unit definition. Recompile the changed model, find the units whose generated output actually changed, and confirm the graph-based resolver's predicted set is a superset of that actually-changed set. The resolver must still be computed from the graph, never from the diff.
Sanity check: predicted covers actual for every change and fixture, and deliberately removing a real dependency edge makes the resolver under-report and this test fail. Paste both runs.
Commit: test: re-validate resolver soundness for the new unit definition.

---

## 5. Build a real incremental recompile and relink

This is the credibility core of the phase. The vehicle is Rumoca's embedded-C backend, which lets you turn recompilation units into ordinary C translation units and use a standard C toolchain, where an incremental rebuild is genuinely recompiling a few object files and relinking.

Feature M1: Per-unit C emission.
How: emit one C translation unit per recompilation unit through the C backend. Investigate first whether the C backend already emits per-unit files or a single monolithic file; if it emits one file, split it so each unit becomes its own translation unit, either by post-processing the generated C or by adjusting the code generation. This split is the main engineering work of the phase.
Sanity check: the number of generated C translation units equals the number of recompilation units, and each compiles on its own to an object file. Paste the file list and one successful per-unit compile.
Commit: feat: emit one C translation unit per recompilation unit.

Feature M2: Compile and link into a runnable simulation.
How: compile every unit's C file to an object file and link them, together with whatever runtime and solver harness the backend needs, into a runnable simulation program. Fix the C compiler and its optimization flags and record them.
Sanity check: the linked program runs and reproduces the phase-1 baseline output for an unchanged model within tolerance. Paste the run.
Commit: feat: compile per-unit objects and link a runnable simulation.

Feature M3: Full-rebuild baseline path.
How: implement the control that compiles all objects from scratch and links, with the same harness and flags, on any change.
Sanity check: the baseline output matches M2 for an unchanged model, and its total time is stable across repeated runs. Paste the timings with their spread.
Commit: feat: add full-rebuild baseline compile-and-link path.

Feature M4: Incremental path.
How: on a change, recompile only the affected units' object files, reuse the cached objects for untouched units, and relink. Confirm by object-file fingerprints that only the affected objects were rebuilt.
Sanity check: the count of recompiled objects equals the resolver's affected set, and untouched objects are byte-identical to their cached versions. Paste the fingerprint comparison.
Commit: feat: recompile only affected objects and relink incrementally.

Feature M5: Measured timing.
How: measure, repeated with spread reported, the full rebuild time and the incremental time, and split the incremental time into detection, affected-unit recompilation, and relink. These are measured values from real toolchain runs, not projections.
Sanity check: every logged cell has all timing components with their spread, and the incremental time is a real sum of measured per-unit compiles plus a measured link, not derived from the full time. Paste a sample record.
Commit: feat: measure full and incremental compile-and-link times.

---

## 6. Fallback ladder if a true relink is blocked

If the C backend resists being split into per-unit translation units, do not fake a measurement. Drop down this ladder and label the result at whatever rung you land on.

1. Best, and the target: real per-unit object compile and relink, as in Section 5. The speedup is measured.
2. If per-unit linking into one program is blocked but standalone unit compilation works: compile each affected unit as its own translation unit and measure its compile time directly, then report incremental cost as the measured sum of affected-unit compiles plus a measured link time. This is measured per-unit compilation and is far stronger than a projection, though you must note any caveat about compiling a unit outside its full program context.
3. Worst, only if both above are blocked: a refined projection that applies the measured per-unit compile times from rung 2 to the change set. This is still a projection and must be labeled as one, but it is grounded in measured per-unit timings rather than the phase-1 fraction-based estimate.

Switching to OpenModelica, whose code generation is more mature but harder to modify, is a legitimate option if Rumoca's C backend is a hard wall, but treat it as a last resort and budget real ramp-up time before committing.

Whichever rung you reach, the granularity fix and the characterization results in Sections 4 and 9 stand on their own and remain a real contribution.

---

## 7. Real correctness validation

Now that an incremental build produces a runnable program, correctness becomes a real measurement rather than a claim.

Feature C1: Incremental-versus-full correctness.
How: run the incremental program and the full-rebuild program on the same changed model and diff their simulation output within the fixed tolerance from phase 1.
Sanity check: outputs agree within tolerance for every change tested, and artificially corrupting one output makes the diff report a mismatch. Paste both.
Commit: test: validate incremental output against full rebuild.

Feature C2: Edge cases.
How: cover the change that, even after the granularity fix, still touches most of the model; the empty change; and a change inside a genuine algebraic loop. The incremental result must either match the full rebuild within tolerance or fall back cleanly to a full rebuild.
Sanity check: every edge case either matches or falls back correctly, and none silently produces a wrong answer. Paste the runs.
Commit: test: cover incremental correctness edge cases.

---

## 8. Broaden models and change types

Feature B1: Real Modelica Standard Library models.
How: the standard library is freely available on its own even though it is not bundled with the compiler package, and the compiler is tested against it, so pull it separately and point the compiler at recognizable models. If any model needs flattening the compiler cannot do directly, lower it to flat Modelica with an external compiler first and feed that in. Choose several models spanning a spectrum from loosely-coupled and feed-forward-like to feedback-heavy, so the characterization in Section 9 has range.
Sanity check: each added model compiles, simulates, and partitions into units, and its source and version are recorded. Paste the unit counts.
Commit: feat: integrate real standard-library models spanning coupling structures.

Feature B2: Sensor-add change injector.
How: implement injecting a new sensor or measurement equation, with its own soundness check that the resolver's predicted affected units cover the units whose output actually changed.
Sanity check: the augmented model compiles and simulates, has exactly one more measurement equation, and the soundness check passes and can be made to fail by removing a real edge. Paste both.
Commit: feat: inject sensor-add changes with soundness check.

Feature B3: Component-removal change injector.
How: implement removing a component and cleaning up its equations, with the same soundness discipline.
Sanity check: the reduced model compiles with no dangling references, and soundness holds and has teeth. Paste both.
Commit: feat: inject component-removal changes with soundness check.

---

## 9. Systematic characterization

This is the scientific payoff. The phase-1 result was two anecdotes, RLC local and thermal global. This phase turns that into an empirical relationship between model structure and benefit.

Feature S1: Structural metrics.
How: for each model, compute structural metrics that plausibly predict benefit, such as the largest strongly-connected or tearing-block size after causalization, the coupling density, and the ratio of states to algebraic variables.
Sanity check: metrics compute for every model and their values order the models the way you would expect from reading them. Paste the metric table as prose or a log record.
Commit: feat: compute structural metrics per model.

Feature S2: Characterization analysis.
How: across the whole model suite and all change types, relate the post-fix ripple and the measured speedup to the structural metrics, and state which property predicts benefit.
Sanity check: the relationship is derived only from logged data, and the models fall along it in a way you can explain from their structure. Paste the summary.
Commit: feat: characterize benefit against model structure.

---

## 10. Parameters

Independent variables: the model, chosen to span the coupling spectrum; model size; change type, now three of them; change frequency; and the structural metrics from S1.

Control variables, held fixed and reported: the numerical comparison tolerance; the solver and time step; the C compiler and its optimization flags; and the link-cache state, warm or cold.

Dependent variables, logged per cell: full rebuild time; incremental time split into detection, affected-unit recompilation, and relink; the measured speedup; the affected fraction under the new unit definition; correctness as maximum absolute error and a pass or fail against tolerance; the structural metrics; and the derived break-even change rate now computed from measured incremental cost.

Every cell must be complete, and the harness must refuse to log a partial record, exactly as in phase 1.

---

## 11. Graphs to generate

All from logged data, regenerated deterministically, saved as vector figures.

1. Measured speedup versus model size. The real version of the phase-1 projected figure, and the headline of the paper.
2. Ripple before and after the granularity fix. The figure that shows the fix worked, with the thermal network as the clearest case.
3. Ripple and measured speedup versus the structural metric, across the suite. The characterization figure that turns the phase-1 anecdote into a claim.
4. Time breakdown, full versus incremental, split into detection, recompilation, and relink. Shows where the saving comes from.
5. Correctness, maximum absolute error per experiment with the tolerance drawn as a reference line. Proves equivalence.
6. Break-even versus change frequency, using the measured incremental cost rather than a projection.

---

## 12. If the results are weak

Diagnose the symptom and change the named aspect, and do not fudge.

1. If the thermal network is still fully coupled after causalization, then it holds a genuine algebraic loop; apply the tearing or residual refinement in G2, and if the block still resists, scope the claim to model classes without large tearing-resistant loops and report that boundary as the finding.
2. If measured speedup is below one on small models, then relink and harness overhead dominates at small scale; report the crossover size, since the honest story becomes helps at scale, which matches the factory-and-infrastructure motivation.
3. If correctness fails, then the resolver under-invalidated; widen the affected set to include units that share a solver harness or an initialization with the changed unit, and never loosen the tolerance to pass.
4. If the C-backend split is a hard wall, drop to the fallback ladder in Section 6, label the result as an estimate at whatever rung you reach, and still ship the granularity fix and the characterization, which do not depend on the relink working.

The meta-rule from phase 1 still governs: a clearly scoped, honestly measured result beats an overreaching one, and a well-characterized negative or mixed result is publishable.

---

## 13. Commit plan

Ordered, one commit per verified feature, evidence pasted, nothing committed before its sanity check and the standing regression gate pass. About twenty-one commits. Feature G2 is conditional on the diagnosis and may be skipped if no genuine algebraic loop is found, and any feature that grows large may split, so the exact count may shift.

1. docs: open phase two, record phase-one findings in the readme.
2. feat: build causalized dependency graph with states as knowns.
3. feat: diagnose integration-artifact versus genuine algebraic loops.
4. test: add causalized-graph and diagnostic tests with teeth.
5. feat: define recompilation units on the causalized graph.
6. feat: refine units for genuine algebraic loops via tearing or residuals.
7. test: re-validate resolver soundness for the new unit definition.
8. feat: emit one C translation unit per recompilation unit.
9. feat: compile per-unit objects and link a runnable simulation.
10. feat: add full-rebuild baseline compile-and-link path.
11. feat: recompile only affected objects and relink incrementally.
12. feat: measure full and incremental compile-and-link times.
13. test: validate incremental output against full rebuild.
14. test: cover incremental correctness edge cases.
15. feat: integrate real standard-library models spanning coupling structures.
16. feat: inject sensor-add changes with soundness check.
17. feat: inject component-removal changes with soundness check.
18. feat: compute structural metrics per model.
19. feat: characterize benefit against model structure.
20. feat: generate measured figures and the results summary from logs.
21. docs: upgrade the paper draft to a full paper with measured results.

---

## 14. Timeline

Honest and phase-mapped, with the warning that the measured-relink work is the risky part and may expand.

1. Weeks 1 to 2: diagnosis and granularity fix, commits 1 through 7. Do not proceed until you know whether the thermal collapse was an artifact or a genuine loop.
2. Weeks 3 to 6: the real recompile-and-relink infrastructure, commits 8 through 12. This is the hard, risk-bearing chunk. If the C-backend split resists, this is where the fallback ladder is invoked.
3. Week 6: correctness validation, commits 13 and 14, which becomes possible as soon as a real incremental program exists.
4. Weeks 7 to 8: broader models and the two new change types, commits 15 through 17.
5. Weeks 8 to 9: characterization and figures, commits 18 through 20.
6. Week 10: the paper upgrade, commit 21.

Roughly eight to ten weeks of focused work, or two to three months part time. If Section 5 resists, let it take the time it needs rather than faking a measurement, and lean on the fallback ladder to keep the rest of the phase moving.

---

## 15. Limitations to keep stating in the paper

1. Detection of the structural change is still reused and assumed, not evaluated.
2. Any measured relink is measured on the C backend, so the other backends are uncharacterized.
3. The model suite is broader than phase one but still bounded, and standard-library coverage is partial.
4. If any speedup number rests on the fallback ladder rather than a true relink, it is an estimate and is labeled as one.

---

## 16. Paper upgrade

The phase-one draft was a short, work-in-progress feasibility note. This phase gives it what a full paper needs: a measured speedup instead of a projection, the granularity fix as a named contribution with its diagnosis and its limits, an empirical characterization of which model structures benefit, correctness validated against a full rebuild, and a broader set of recognizable models. Keep the honest framing of the mixed result as a strength rather than smoothing it away, since the value of the work is precisely that it says clearly where incremental recompilation helps and where it does not.
