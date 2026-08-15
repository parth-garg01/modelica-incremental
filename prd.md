# PRD: One-Week Feasibility Study for a Conference Short Paper

## Drift-Triggered Incremental Recompilation for Structurally-Evolving Digital Twins (preliminary results)

---

## 0. What this document is

This is an agent brief. It is written to be handed to an LLM coding IDE and executed with light human supervision. It scopes a one-week feasibility study whose output is a short, honest, publishable result plus the code and data behind it.

Read Section 2 and Section 3 before writing any code. Section 2 defines what is measured versus what is projected, and getting that distinction wrong makes the paper dishonest. Section 3 defines how the coding agent must behave, and it matters more than any single feature.

The scope is deliberately small. This is a feasibility study, not the full system. Do not expand it.

---

## 1. The paper (the goal)

The goal is a short paper, of the kind that fits a work-in-progress or short-paper track, presenting preliminary evidence that incremental recompilation of digital-twin simulation code is worth pursuing.

The honest central claim is this: for realistic localized structural changes to Modelica models, the set of compiled blocks that would need regenerating is a small, automatically identifiable fraction of the whole model. We measure that fraction on real models and use it to project an upper bound on the achievable speedup from incremental recompilation.

Note the word project. This week's work does not build a true incremental compiler, so it does not measure a real incremental compile time. It measures locality and projects the speedup ceiling that locality implies. The paper must say so plainly. A clearly-labeled feasibility study is publishable; a projected number dressed up as a measured one is not.

What the paper needs, all of which this brief produces:

1. A dependency-graph and recompilation-unit analysis of at least two real Modelica models.
2. A measured ripple result: for a catalogue of structural changes, what fraction of recompilation units each change affects.
3. A projected speedup ceiling derived from that ripple.
4. A soundness check showing the impact analysis does not under-report affected units.
5. Two or three figures and a short results write-up populated with real numbers.

Venue framing: aim at a short-paper, poster, or work-in-progress track rather than the main proceedings, since a one-week study is preliminary by nature. Confirm the specific venue's submission categories before writing, because they vary.

---

## 2. What is measured versus what is projected

Measured this week, using real runs on real models, and therefore reportable as data:

1. The dependency graph of each model, built from the compiler's exported intermediate representation.
2. The partition of each model into recompilation units.
3. The ripple, meaning the number and fraction of recompilation units affected by each injected change.
4. The full compile time of each model.
5. The soundness of the impact analysis, meaning whether the units it predicts as affected actually cover every unit whose compiled output changed.

Projected, not measured, and therefore reported as a projection with its assumptions stated:

1. The incremental speedup. Compute it as a ceiling, roughly one divided by the affected fraction, and label it as an optimistic upper bound that ignores relink and re-matching overhead. Do not present it as a measured runtime.

Why this split is honest and still worth publishing: the locality result is the load-bearing claim behind the whole idea. If local changes ripple across most of the model, incremental recompilation cannot help and the year-long project is not worth starting. If they stay local, the idea is validated and the speedup ceiling tells you how much is on the table. Measuring locality on real models is a real contribution even without a working incremental compiler.

---

## 3. How the coding agent must work

These rules override any instinct to look finished. Violating them produces a paper that cannot survive review.

1. Real data only. Every number in the logs, the figures, and the write-up must come from an actual run of the actual compiler on an actual model. Never invent a timing, a count, or an output. If a value cannot be produced, report that it cannot, rather than filling it in.
2. Show your work. For any claim that something ran or passed, paste the real command and its real output into the commit body or the run log. A claim with no pasted evidence is treated as not done.
3. Do not stub the core. Do not mock, fake, or hard-code the compiler call, the intermediate-representation export, the graph, or the measurements. Stubbing is allowed only for throwaway scaffolding that is deleted before the feature is committed, and never for anything that feeds a number into the paper.
4. Build a real impact resolver, not a circular one. The set of affected units must be computed from the dependency graph, by following dependencies outward from the changed equations and variables. It must not be computed by looking at which units changed in the before-and-after diff, because that is circular and measures nothing. The diff is used only afterward, to check the resolver, in the soundness test.
5. One commit per verified feature. Do not batch the whole project into one commit at the end. Do not commit a feature until its sanity check passes and the evidence is pasted. The commit list in Section 10 is the intended cadence.
6. Stop and report when blocked. If setup fails, a model will not compile, or the intermediate representation is not what this brief assumes, stop and report the exact error rather than inventing a workaround or a substitute number. A clear blocker report is a success, not a failure.
7. Stay minimal. Build only what this brief asks for. Do not add features, abstractions, or polish that the feasibility study does not need. Scope creep is the enemy of finishing in a week.
8. Every test must have teeth. Before trusting a test, break the code it checks and confirm the test goes red. A test that cannot fail is not evidence.
9. Record provenance. Log the exact compiler version, the exact model names and sources, and the machine the timings were taken on, so the paper is reproducible.

---

## 4. Tech stack

1. Compiler: Rumoca, installed as a Python package (it bundles the Rust compiler, so no separate Rust build is needed), and driven entirely from Python. The working surface is Rumoca's exported DAE intermediate representation in JSON form, not the compiler's internals. Record the exact installed version.
2. Language: Python. Use networkx for the dependency graph, pandas for the result logs, matplotlib for the figures, and pytest for the tests.
3. Timing: wall-clock timing around the compile call, each measurement repeated a few times with the spread reported, not a single sample.
4. Version control: git, with a conventional-commit style (feat, fix, test, chore, build, docs).

Do not modify the compiler's Rust internals in the one-week version. That is the year-long project, and it is out of scope here.

---

## 5. Method and pipeline

The feasibility pipeline, end to end:

1. Take a Modelica model and compile it with Rumoca, exporting the DAE intermediate representation to JSON. Record the full compile time.
2. Parse the JSON into a dependency graph whose nodes are equations and variables and whose edges record which depends on which.
3. Compute the strongly-connected components of that graph. These are the recompilation units, the smallest chunks that would be recompiled together.
4. Inject a structural change into the model source, for example swap one component for a different model of the same kind.
5. Recompile the changed model, export its intermediate representation, and diff it against the baseline to find which units actually changed.
6. Independently, run the graph-based impact resolver on the change to predict which units it affects.
7. Compare ripple (how many units the resolver flags) and check soundness (that the flagged set covers every unit the diff shows actually changed).
8. Compute the projected speedup ceiling from the affected fraction.

---

## 6. Build plan, feature by feature

Each feature states how to build it, the sanity check that must pass before moving on, and the commit that closes it. Do not commit before the check passes and the evidence is pasted.

Feature 1: Repository scaffold.
How: create a Python project with a README stating the paper's honest claim, a directory layout (source, models, results, figures, tests), a requirements file, and a gitignore.
Check: a fresh clone installs its dependencies cleanly and the test runner executes with zero tests.
Commit: chore: scaffold project, readme with paper claim, and layout.

Feature 2: Compiler installed and verified.
How: install Rumoca as a Python package, pin the version, and compile a one-line model through to its intermediate representation from Python.
Check: the one-line model produces a non-empty intermediate representation, and the exact compiler version is recorded in the README. Paste the version and the output.
Commit: build: install and pin the compiler, verify a minimal compile.

Feature 3: Sample models compiled and fixtures saved.
How: choose two or three small, recognizable models, compile each, export the DAE intermediate representation to JSON, and save those JSON files as fixtures in the repository. Record each model's name and source.
Check: every chosen model compiles and simulates, the saved JSON is non-empty, and the equation count in the JSON matches what the compiler reports. Paste the counts.
Commit: feat: compile sample models and save intermediate-representation fixtures.

Feature 4: Dependency graph from the intermediate representation.
How: parse the DAE JSON into a networkx dependency graph, with equations and variables as nodes and dependency edges between them.
Check: on a small hand-checkable model, the graph's nodes and edges match what you work out on paper, and a forward-reachability query on a known variable returns the expected equations. Paste the query result.
Commit: feat: build dependency graph from the intermediate representation.

Feature 5: Recompilation units.
How: compute the strongly-connected components of the graph and treat each as a recompilation unit with a stable identifier.
Check: every equation lands in exactly one unit, a model known to be fully decoupled yields all singleton units, and re-running on an unchanged model yields identical unit identifiers.
Commit: feat: compute recompilation units from strongly-connected components.

Feature 6: Graph and unit tests.
How: write pytest tests for graph construction, reachability, and unit coverage and stability, on at least two model structures.
Check: the suite passes, and a deliberately introduced wrong edge or a forced overlap makes a test fail. Paste both the passing run and the deliberately-broken failing run.
Commit: test: add graph and recompilation-unit tests with teeth.

Feature 7: Change injection.
How: implement injecting one structural change into a model source, starting with a component swap, producing a new valid model. Add a sensor-add change only if time allows.
Check: the changed model compiles and simulates, and it differs from the original in exactly the intended place and nowhere else.
Commit: feat: inject a structural change into a model.

Feature 8: Graph-based impact resolver.
How: given a change, compute the set of recompilation units it affects by following dependencies outward from the changed equations and variables in the graph. This must be computed from the graph, not from the intermediate-representation diff.
Check: on a small model, the resolver's affected set matches the set you compute by hand, and a change confined to one unit resolves to only that unit. Paste the comparison.
Commit: feat: resolve affected units from the dependency graph.

Feature 9: Ripple and projected speedup measurement.
How: for each model and change, measure the full compile time (repeated, with spread), count total and affected units, compute the affected fraction, and compute the projected speedup ceiling as one divided by the affected fraction, clearly labeled as an optimistic upper bound. Log everything.
Check: the log has one complete record per model-and-change cell with no missing fields, and the timing spread across repeats is reported, not a single sample. Paste a sample record.
Commit: feat: measure ripple and compute projected speedup ceiling.

Feature 10: Soundness validation.
How: recompile the changed model, export its intermediate representation, diff it against the baseline to find the units that actually changed, and confirm the resolver's predicted set is a superset of that actually-changed set.
Check: for every change tested, the predicted set covers the actually-changed set, and deliberately deleting a real dependency edge causes the resolver to under-report and this test to fail. Paste both runs.
Commit: test: validate impact-resolver soundness against the diff.

Feature 11: Analysis and figures.
How: write a script that reads the logs and produces the figures in Section 8 and a short generated results summary, all from the logged data with no hand-editing.
Check: each figure regenerates from the logs identically, axes and units are labelled, and no figure contains any value not present in the logs.
Commit: feat: generate figures and results summary from logged data.

Feature 12: Paper draft populated.
How: fill the paper outline in Section 13 with the real numbers and figures, including the limitations section verbatim from Section 12.
Check: every quantitative claim in the draft traces to a specific log record or figure, and the limitations section is present and honest.
Commit: docs: draft short paper with real results and limitations.

---

## 7. Parameters

Kept small on purpose, because this is a feasibility study.

Models: two or three small, recognizable Modelica models, ideally from the standard library so reviewers know them. One should have some genuine coupling so the units are not all singletons.

Change types: start with one, a component swap. Add a sensor-add change only if the first is finished with time to spare. Do not attempt all change types this week.

Metrics logged per model-and-change cell:

1. Total recompilation units.
2. Affected recompilation units, and the affected fraction.
3. Full compile time, repeated, reported with its spread.
4. Projected speedup ceiling, labeled as an upper bound.
5. Soundness, a pass or fail on whether predicted units cover actually-changed units.

---

## 8. Figures to generate

Two required, a third if time allows. All from logged data, saved as vector formats for the paper.

1. Ripple distribution. A histogram or bar plot of the fraction of recompilation units affected, across models and changes. A distribution concentrated at the low end is the visual proof that changes are local. This is the headline figure.
2. Projected speedup ceiling. A bar plot of the projected upper-bound speedup per model and change, with a clear caption stating it is a projection that ignores relink overhead.
3. Optional: recompilation-unit-size distribution. A histogram of equations per unit, to characterize the partition.

---

## 9. If the results are weak

Diagnose the symptom and change the named aspect, rather than concluding the idea failed.

1. If ripple is large, meaning most changes affect most of the model, narrow the claim to loosely-coupled modular models and report honestly that tightly-coupled models do not benefit. A scoped or even partly negative result, clearly measured, is still a publishable feasibility finding.
2. If the intermediate-representation diff is noisy, meaning unrelated units appear to change between runs, stabilize the export by pinning the compiler version and any options, and confirm the diff is deterministic before trusting ripple numbers.
3. If setup blocks, meaning a model will not compile or the export is not as assumed, fall back to simpler models and report the blocker precisely. Do not substitute invented numbers to keep moving.

---

## 10. Commit plan

The ordered list, one commit per verified feature, nothing committed before its check passes and its evidence is pasted. About twelve commits, mapped to the week.

1. chore: scaffold project, readme with paper claim, and layout.
2. build: install and pin the compiler, verify a minimal compile.
3. feat: compile sample models and save intermediate-representation fixtures.
4. feat: build dependency graph from the intermediate representation.
5. feat: compute recompilation units from strongly-connected components.
6. test: add graph and recompilation-unit tests with teeth.
7. feat: inject a structural change into a model.
8. feat: resolve affected units from the dependency graph.
9. feat: measure ripple and compute projected speedup ceiling.
10. test: validate impact-resolver soundness against the diff.
11. feat: generate figures and results summary from logged data.
12. docs: draft short paper with real results and limitations.

---

## 11. One-week schedule

1. Day 1: Features 1 and 2. Get the environment and compiler working, and do not move on until a real compile succeeds.
2. Day 2: Features 3 and 4. Fixtures and the dependency graph.
3. Day 3: Features 5 and 6. Recompilation units and their tests.
4. Day 4: Features 7 and 8. Change injection and the graph-based resolver.
5. Day 5: Features 9 and 10. Ripple measurement and soundness validation.
6. Days 6 and 7: Features 11 and 12. Figures, results summary, and the paper draft.

If a day slips, cut the optional sensor-add change and the optional third figure before cutting anything else. Protect the soundness validation and the ripple measurement, because those are the paper's evidence.

---

## 12. Limitations to state in the paper

State all of these plainly. Reviewers respect honesty about a preliminary study and punish overclaiming.

1. The speedup is projected from measured locality, not measured from a working incremental compiler. It is an optimistic upper bound that ignores relink and re-matching overhead.
2. There is no true incremental recompilation or relinking in this study. Building that is the proposed future work.
3. The model set is small and the change catalogue is minimal, so the results are indicative, not conclusive.
4. The analysis assumes the exported intermediate representation faithfully reflects what a real incremental compiler would regenerate, which a full implementation would need to confirm.
5. Detection of the structural change is out of scope here and is assumed, not evaluated.

---

## 13. Paper outline

Fill each section with the real numbers and figures produced above.

1. Abstract. The problem, the honest claim about measured locality and projected speedup, and the headline ripple number.
2. Introduction. Why digital twins drift when the real machine changes, and why full rebuilds are costly, leading to the question of whether incremental recompilation is feasible.
3. Background and related work. How simulation compilers turn a model into code and compute equation dependencies, how software build systems avoid rebuilding everything, and where existing large-scale and incremental compiler efforts sit relative to this idea.
4. Method. The pipeline from Section 5, the definition of a recompilation unit, and the graph-based impact resolver.
5. Preliminary results. The ripple measurement, the projected speedup ceiling, the soundness result, and the figures.
6. Limitations. The list from Section 12, stated verbatim.
7. Future work. The full incremental recompilation and relink system, a larger model set and change catalogue, and a real measured speedup, which together form the year-long project this study motivates.
