# Combined PRD: From Working Prototype to Published Full-Length Paper

## Drift-Recompile, all remaining work as one phase

---

## 0. Where this picks up

The pipeline already works on two hand-written models. It produces a real, repeated, wall-clock incremental-versus-full-rebuild speedup (RLCCircuit 1.54 times, ThermalNetwork 2.23 times), the incrementally built binary is bit-identical to a full rebuild (maximum error 0.0), the graph-based resolver is sound and teeth-tested, and three change types (component swap, sensor add, component removal) all pass. One blocker is open: a real 7-state Cauer filter compiles under Rumoca but breaks the per-unit code generator, because its Kirchhoff-law equations do not have a single target variable per equation.

This document is the complete remaining project, from that state to a submitted full-length paper, expressed as one phase with three ordered stages.

---

## 1. The single goal

A published full-length paper, backed by a system that works on real Modelica models with implicit conservation equations, at a scale where full rebuilds are genuinely costly, with the break-even question answered: when does frequent structural change stop making incremental recompilation worth it.

Concretely, the phase is done when a reviewer can see all of the following:

1. The incremental-recompile pipeline running end to end on real standard-library-style models with implicit conservation equations, not just the explicit assignment-form subset it handles today.
2. Real measured speedup across a range of model sizes reaching at least one hundred thousand equations, reported honestly whether or not the speedup grows with scale.
3. A measured break-even change frequency, the point at which streaming incremental recompiles stop beating periodic full rebuilds.
4. Bit-identical correctness preserved throughout, with any use of tolerance stated and justified.
5. A full-length paper in a target venue's format, with a reproducibility package that regenerates the headline numbers from a clean clone.

---

## 2. The one ordering constraint you cannot violate

This is one phase, but the three stages inside it are strictly ordered, not parallel.

Stage A (generality) comes first. Stage B (scale and break-even) must not begin until Stage A is complete, because scale and break-even numbers measured on the explicit-form-only subset would not survive review. The scaled models in Stage B must be representative of real Modelica, which means they need the matching-driven code generation that Stage A builds. Scaling only the narrow subset that happens to be assignment-form would let a reviewer say you scaled a toy, and they would be right. Stage C (writeup and submission) follows the results, for the obvious reason.

Treat A, then B, then C as a hard sequence. Within each stage the features are also ordered.

---

## 3. Standing discipline carried forward

The rules that made the earlier work credible stay in force across all three stages. Do not relax them because the models get harder or larger.

1. Real measured numbers only. No projected speedups. Every number in the logs and the paper comes from an actual run.
2. Bit-identical correctness is the bar, not "within tolerance." A genuine nonlinear block may make bit-identical output impossible for one model. If that happens, switch that specific model to a stated, justified tolerance and say so plainly. Do not let one nonlinear model quietly lower the bar for the linear cases, which must stay bit-identical.
3. Every check must be teeth-tested. Break the code the check guards and confirm the right test goes red before trusting it.
4. The resolver never looks at the before-and-after diff. Its prediction is computed from the graph and verified against the diff independently, as a soundness check.
5. One commit per verified feature, with the real command output pasted into the commit body as evidence.
6. Honesty over cherry-picking. If a model class still does not work, document the wall precisely, the way the Cauer filter was documented, rather than dropping it.

---

## 4. The unified method

Same pipeline throughout. Source, then Rumoca producing the DAE intermediate representation together with its BLT matching and block structure, then the dependency graph, then recompilation units that now include coupled implicit blocks, then change injection, then the graph resolver, then the soundness check against the diff, then per-unit C code generation that is matching-driven and emits block solves for coupled units, then recompile only the affected units and relink against cached object files, then measure wall-clock time and diff simulation output. Stage B scales the inputs and adds a change-frequency dimension on top of this same pipeline. Stage C turns the results into a paper.

---

## 5. Build plan

One continuous commit list, grouped into the three ordered stages. Each feature states how to build it, the sanity check that must pass first, and the commit that closes it. Do not commit before the check passes and the evidence is pasted.

### Stage A: Generality on implicit-equation models

Feature 1: Surface the matching and block structure.
How: extract, per equation, the variable it is matched to and the block it belongs to, from Rumoca's BLT output, and carry both into your graph. Do not infer assignment form. Rumoca must have this, because it already simulates the Cauer filter correctly, so this is an integration task, not a reimplementation.
Check: on RLC and Thermal, the matched target for every equation agrees with what the current assignment-form generator produced, so the new source of truth reproduces old behavior. Paste the agreement.
Commit: feat: source equation-variable matching and block structure from the compiler.

Feature 2: Recompilation units over matched blocks.
How: redefine a recompilation unit as a BLT block. Singletons stay singletons, genuinely coupled equation sets become one coupled unit. Reconcile with the existing strongly-connected-component partition.
Check: units cover every equation with no overlap, the RLC and Thermal partitions match the prior work with no regression, and a model with a known coupled block yields one coupled unit rather than a scatter of singletons.
Commit: feat: define recompilation units over matched blt blocks.

Feature 3: Matching-driven codegen for singleton units.
How: generate each singleton unit's C from its matched target variable rather than an assumed assignment.
Check: output is bit-identical to the prior work on both RLC and Thermal, maximum error 0.0. Paste the diff. This is a pure regression, so any nonzero error means the new path changed behavior and must be fixed before moving on.
Commit: feat: generate singleton-unit code from the matching.

Feature 4: Linear block solve for coupled units.
How: for a coupled linear block, emit C that assembles the small local linear system and solves it directly, which is fine at this size.
Check: on a hand-checkable coupled linear model, block-solve output is bit-identical to a full Rumoca compile of the same model. Teeth-test by perturbing the assembled system and confirming correctness fails.
Commit: feat: emit linear block solves for coupled units.

Feature 5: Cauer filter end to end.
How: drive the real 7-state Cauer low-pass filter, the model that hit the wall, fully through the new pipeline.
Check: it compiles, simulates, and its output is bit-identical to a full Rumoca compile, or, if a genuine nonlinear block forces it, within a stated and justified tolerance. Record the unit count and block sizes. Paste the result.
Commit: feat: compile and simulate the cauer filter end to end.

Feature 6: Nonlinear block solve, only if a real model needs it.
How: only if a target model has a genuinely nonlinear coupled block, emit a Newton iteration for it. Otherwise skip this feature and record that no tested model required it.
Check: on the model that needs it, output matches within a stated tolerance and the iteration converges, with the convergence check teeth-tested. If skipped, the commit body records why.
Commit: feat: emit nonlinear block solves where a model requires them.

Feature 7: Full change-type suite on real models.
How: run component swap, sensor add, and component removal against the Cauer filter and one more real standard-library-style model, through the whole detect, resolve, recompile, relink, and bit-diff path.
Check: the resolver is sound on every change, verified against the diff, output is bit-identical or within the stated tolerance, and every check is teeth-tested. Paste the soundness and correctness evidence.
Commit: test: validate all change types on real implicit-equation models.

Feature 8: Ripple and measured speedup on real models.
How: measure ripple and the real incremental-versus-full-rebuild wall-clock speedup on the real models, repeated with the spread reported, logged to parquet and CSV.
Check: one complete record per model-and-change cell with the timing spread present, and figures regenerate deterministically from the log. Paste a sample record.
Commit: feat: measure ripple and real speedup on implicit-equation models.

Feature 9: Update figures and draft for Stage A.
How: regenerate the figures and update the paper draft with the real-model results and an honest account of which model classes now work and which still do not.
Check: every new number traces to a log record or figure, and the limitations reflect the new frontier.
Commit: docs: update draft with real-model generality results.

### Stage B: Scale and break-even

Feature 10: Scaled model generator.
How: build a generator that produces parameterized versions of the model classes that now work, for example an RLC ladder of N segments and an N-room thermal network, at target sizes reaching at least one hundred thousand equations. Record equation and unit counts per size.
Check: the generator emits valid models at several sizes, equation counts match the requested sizes, and the largest target compiles under Rumoca.
Commit: feat: generate parameterized models across sizes up to industrial scale.

Feature 11: End-to-end correctness at scale.
How: run the full detect, resolve, recompile, relink, and bit-diff pipeline on the large generated models for a single local change.
Check: output is bit-identical to a full rebuild at every size tested, or within the stated tolerance for any nonlinear block, and the resolver stays sound. Paste evidence at the largest size that runs.
Commit: test: verify end-to-end correctness and soundness at scale.

Feature 12: Profile and harden the scaling path.
How: profile graph building, partition, and resolution at the largest sizes. If anything is superlinear, fix it with sparse structures or incremental construction. If nothing is superlinear, record the measured complexity and skip the fix.
Check: graph build, partition, and resolution time grow no worse than near-linearly across the size range, shown with real timings. Teeth-test any new fast path against the previous correct output.
Commit: perf: keep graph, partition, and resolver near-linear at scale.

Feature 13: Speedup versus model size.
How: measure the real incremental-versus-full-rebuild wall-clock speedup across the full size range, repeated with spread, logged.
Check: one complete record per size with spread, figures regenerate deterministically, and the trend is reported honestly whether or not speedup grows with size. Paste a record.
Commit: feat: measure incremental speedup across model sizes.

Feature 14: One-time overhead versus model size.
How: measure the cost of building the graph and partition, the setup paid once, across sizes, and express it relative to a full rebuild.
Check: overhead is logged per size and its ratio to full-rebuild time is reported, so the paper can state whether setup cost stays acceptable at scale.
Commit: feat: measure one-time graph and partition overhead across sizes.

Feature 15: Change-frequency harness.
How: build a harness that applies a sequence of structural changes over simulated time at a configurable rate, driving each through the incremental path, and separately through a batched full-rebuild path that rebuilds once per batch of accumulated changes.
Check: a short sequence runs to completion on a mid-size model, every change is logged with its affected units and both incremental and batched costs, and reruns give stable timings. Paste a sample sequence record.
Commit: feat: add change-frequency harness with incremental and batched paths.

Feature 16: Break-even measurement.
How: sweep change frequency and measure cumulative incremental cost against cumulative batched full-rebuild cost, finding the crossing point where streaming incremental recompiles stop beating periodic full rebuilds.
Check: the sweep produces an actual crossing, or, if incremental always wins in the tested range, that is reported honestly with the range stated, and the crossing is stable across repeats. Paste the crossing point.
Commit: feat: measure the break-even change frequency.

Feature 17: Scaling and break-even figures.
How: regenerate figures for speedup versus size, overhead versus size, and the break-even crossing, all deterministically from the logs.
Check: every figure regenerates identically and contains no value absent from the logs.
Commit: feat: generate scaling and break-even figures.

### Stage C: Publication

Feature 18: Target venue and format.
How: choose a specific venue and track, obtain its template, page limit, and deadline, and record them in the repository.
Check: the venue, track, deadline, and page limit are recorded, and the paper draft is moved into the venue template and still builds.
Commit: docs: adopt target venue template and record submission constraints.

Feature 19: Full-length restructure.
How: expand the short-paper draft into the full-length structure the venue expects, with the scale and break-even results as the core evaluation.
Check: every expected section is present, and every quantitative claim traces to a log record or figure.
Commit: docs: restructure draft into full-length paper.

Feature 20: Related-work and positioning pass.
How: write a related-work section positioning the contribution against existing simulation-compiler, incremental-build, and drift-detection work, and state the novel gap explicitly.
Check: the section cites the key prior work accurately and the gap statement is specific, not hand-waved.
Commit: docs: add related-work and positioning section.

Feature 21: Reproducibility package.
How: assemble an artifact of the code, the models, the experiment scripts, and a single documented command sequence that regenerates the headline numbers and figures from a clean clone. If the venue has artifact evaluation, follow its checklist.
Check: a clean clone, following only the documented steps, regenerates the headline speedup, the break-even crossing, and the figures, with numbers matching the paper within the reported spread. Paste the regeneration output.
Commit: docs: add reproducibility package and regeneration script.

Feature 22: Threats to validity and final limitations.
How: write an honest threats-to-validity and limitations section covering the model classes that still do not work, the generated-versus-real-model question, the reused detector, and any tolerance used for nonlinear blocks.
Check: every known limitation from the whole project is represented, and none is overstated or hidden.
Commit: docs: add threats to validity and final limitations.

Feature 23: Internal review and submission.
How: do a full internal read for correctness, clarity, and claim-to-evidence traceability, fix what it surfaces, and submit.
Check: a checklist confirms every claim traces to evidence, the paper fits the page limit, the artifact regenerates, and the submission is complete. Paste the checklist.
Commit: docs: finalize paper and submit.

---

## 6. What good looks like

1. Real implicit-equation models, including the Cauer filter, run the entire pipeline with bit-identical correctness, or a single clearly-justified tolerance where a genuine nonlinear block appears.
2. A real measured speedup across model sizes up to at least one hundred thousand equations, with the scaling trend reported honestly.
3. A measured break-even change frequency, or an honest statement that incremental won across the entire tested range, with that range given.
4. A full-length paper in the target venue's format whose headline numbers regenerate from a clean clone, with limitations and the remaining frontier stated rather than hidden.

---

## 7. If parts turn out harder than expected

1. If general implicit blocks are too much for the time, scope the claim to linear conservation blocks, which already cover RLC circuits, thermal and hydraulic networks, and much of the analog and thermal libraries. Defer nonlinear blocks to future work. This is still a large, honest step up and reviewers accept a clearly-scoped extension.
2. If bit-identical correctness becomes impossible on a nonlinear model, move that one model to a stated tolerance justified against solver error, and keep bit-identical as the bar for every linear case.
3. If scaling exposes a bottleneck you cannot fully fix in time, report the largest size that runs cleanly and the measured growth rate honestly, rather than extrapolating past what you measured.
4. If the break-even sweep shows incremental always winning in the range you can afford to test, that is a legitimate result. State the tested range and do not claim a crossing you did not observe.
5. If Rumoca does not expose the matching and block structure cleanly, that is a real integration cost. Budget for it and report it, and if it is genuinely blocked, that limitation is itself a finding about the tooling.

---

## 8. Known unknowns

This is a large single phase, and the honest part of that is Stage B. Scaling to large models routinely surfaces problems that are invisible on single-digit-unit models, most often superlinear behavior in graph building, partition, or resolution that never mattered before. Feature 12 exists to catch and fix that, but the fix could grow into work of its own, and you cannot fully size it until you run at scale. Treat that as expected for a project like this, not as a sign the plan is wrong. Everything else in the phase is well understood from the work already done; Stage B is where genuine surprises are most likely to live.
