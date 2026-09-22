# Journal-level research improvement plan

Read-only inspection pass. Nothing in the paper, code, experiments, figures,
or results was changed to produce this document.

**Source material inspected:** `paper/main.tex`, `README.md`,
`docs/results.md` (1161 lines, the full evidence ledger), `docs/progress.md`
(957 lines, the full commit-by-commit history), `docs/findings/*.md` (three
finding writeups: scaling bottlenecks, Cauer index-reduction gap, Rumoca
algebraic-loop bug), `docs/venue.md`, `src/` (36 files, 4,721 lines), `tests/`
(31 files, 2,147 lines), `results/` (CSV/parquet logs, fixtures, provenance),
`figures/`, `git log` (61 commits). Every claim below is tagged with its
evidence; anything I could not verify against the repository is marked
**UNVERIFIED**.

---

## 1. Executive summary

The repository already contains a genuinely unusual amount of rigor for a
project at this stage: every number in the paper traces to a script and a
log, correctness is checked bit-identical (not tolerance-based) on every
measured cell, two real bugs in third-party dependencies were found and
documented (networkx hash non-determinism, a Rumoca runtime convergence
bug), and negative/superseded results (the static-link plateau, the Cauer
filter gap) are kept in the record rather than deleted. This discipline is
itself close to a contribution, but it is not what a journal reviewer scores.

The paper's actual scientific claim is narrow and precise: **for index-1
Modelica models, a matching-derived dependency graph identifies a small set
of recompilation units that a structural edit invalidates, and rebuilding
only those units is measurably faster than rebuilding everything, provided
the link/assembly step is also made not to scale with total unit count.**
Everything currently in the paper is evidence for that one claim, gathered
on a small number of models (2 real MSL circuits + 1 real thermal circuit +
5 hand-written fixtures + 1 parameterized generator family).

The single largest gap between "conference-ready" and "journal-ready" is
not more figures — it is **breadth of evidence for generality** (more real
models, more topologies, more change types) and **a second baseline**
(currently the only comparison is incremental-vs-full-rebuild; there is no
comparison against a naive/weaker incremental strategy, so the paper cannot
show its specific design choices — SCC-based units, reachability-based
impact, dynamic linking — are better than the obvious alternatives, only
that they beat doing nothing). Both are addressable substantially from
infrastructure that already exists in the repo (Section 7, Section 8).

The second-largest gap is **the unresolved N=5,000 anomaly** (Section
2.1 of `docs/results.md`: speedup collapses from a clean trend to 3.33x at
14,999 equations, tentatively but not conclusively attributed to filesystem
overhead). A journal reviewer will find this data point immediately — it is
already in the repo — and an unexplained 10x-off outlier sitting next to an
otherwise-clean scaling claim is a credibility risk if left as is. Resolving
or at least properly characterizing it is higher-value than most new
experiments this plan proposes.

---

## 2. Current research contribution

**Exact research problem:** given a Modelica model and a localized
structural edit to it, how much of the compiled artifact set does the edit
actually invalidate, and can that subset be identified and rebuilt faster
than a full rebuild, without ever trusting the identification (every result
is checked bit-identical against ground truth).

**Actual technical contribution**, in descending order of what is genuinely
novel versus what is solid engineering:

1. A from-scratch equation-to-variable bipartite matching plus SCC/BLT
   partition, computed external to the compiler because Rumoca's own
   matched-stage IR is not exposed via its public API (`docs/results.md`
   §1.1 step 2). This is a real, disclosed engineering workaround, not a
   claimed algorithmic novelty — Kuhn's algorithm and Tarjan's SCC are both
   textbook (cited: Kuhn 1955, Hopcroft-Karp 1973, Tarjan 1972, Duff-Reid
   1978). The novelty is in *applying* this decomposition as a
   recompilation-unit boundary for an equation-based compiler, which is a
   genuinely underexplored angle (Make/Bazel-style incremental builds exist
   for file-based systems; the paper's related-work section correctly
   identifies this gap).
2. The "states are not edge sources" correction to the dependency graph
   (`docs/results.md` §1.4) — this is a real, non-obvious, and load-bearing
   finding: naively including states as read/write graph nodes manufactures
   false cycles (ThermalNetwork's true ripple is 22%, not the phase-1
   measured 100%). This is presented as a bug fix in the paper, but it is
   closer to a genuine technical insight about how to build this kind of
   dependency graph correctly, and could be foregrounded more as a
   contribution in its own right (it generalizes to any equation-based
   incremental-build design, not just this one).
3. Graph-reachability impact resolution, checked against an independent
   diff-based ground truth on every cell (soundness superset property).
   Solid, correctly validated, not itself novel (this is exactly what a
   Make-style dependency graph gives you), but the independent verification
   discipline is above what most systems papers do.
4. The diagnose-and-fix arc on the relink ceiling (static link → dynamic
   link, `docs/findings/scaling-bottlenecks.md` "Bottleneck 4 fix"): this is
   a legitimate systems contribution — identifying that the *build strategy*
   (not the impact-analysis logic) was the actual bottleneck, and that
   fixing it changes the asymptotic behavior of the whole system (flat
   1.8x-2.3x → growing 5.66x-27.01x). This is arguably the strongest single
   result in the paper.
5. A measured (not modeled) break-even change frequency. Genuinely useful
   and rare in incremental-build literature, which usually reasons about
   batching in the abstract.

**Engineering versus research contribution:** the C code generator
(`src/codegen_units.py`, `src/block_codegen.py`, `src/expr_c.py`, the
per-unit dynamic-library driver in `src/unit_codegen.py`) is necessary
infrastructure to make the timing claims real rather than projected, but it
is not itself a research contribution — it is a means of producing evidence.
The paper is correctly positioned as being about the matching/partition/
impact-analysis/link-strategy pipeline, not about the code generator, but a
journal reviewer in compilers could reasonably ask for more discussion of
why a hand-rolled linear-only C emitter is an acceptable substitute for a
real Modelica backend's code generation (see Gap 2, Section 6).

**Claims currently made** (from the abstract and conclusion) and their
support level, expanded fully in Section 4's claim-evidence matrix:
generality across the MSL corpus (weakly supported — n=3 real models plus 1
negative result); the growing-speedup finding (well supported within
149-2,999 equations, degrading badly by 14,999); the break-even number
(well supported for the one measured configuration, not shown to
generalize); "we report where the approach stops working as plainly as
where it works" (true and a real strength — Section 300 of the tex, the
Limitations section, is unusually honest for a paper at this stage).

**Assumptions embedded in the implementation** that bound applicability:
index-1 DAEs only (no Pantelides-style index reduction); linear coupled
blocks only (no Newton iteration for nonlinear algebraic loops); no
discrete/event signals (`If`-expression codegen unimplemented); change
detection assumed given (the injector always knows its own seed set);
single-machine, single-toolchain (Windows/MinGW/gcc) measurement, no
cross-platform validation; every experiment used the same one Windows
machine (`docs/results.md` header: "ran on one Windows machine").

---

## 3. Repository architecture map

| Component | File(s) | Role |
|---|---|---|
| A. Compiler front end | `src/compile.py` | Wraps Rumoca's Python API (`Session().load()`, `to_json(stage="dae")`); the only stage not written by this project |
| B. Matching | `src/matching.py` (234 lines) | Hand-rolled deterministic Kuhn's bipartite matcher; the module docstring documents the API wall and the networkx non-determinism bug |
| C. Recompilation-unit construction | `src/matched_units.py`, `src/units.py`, `src/graph.py`, `src/causal_graph.py`, `src/causal_units.py` | BLT-block/SCC computation over the matched graph; `causal_*` files are the superseded phase-2 path kept only because a regression test proves the two definitions agree byte-for-byte |
| D. Dependency/impact analysis | `src/resolver.py` (65 lines), `src/matched_graph.py` | `resolve_impact()`: pure `networkx.descendants()` reachability from a seed set |
| E. Code generation | `src/codegen_units.py`, `src/matched_codegen.py`, `src/block_codegen.py`, `src/linear_block.py`, `src/expr_c.py`, `src/model_layout.py`, `src/eval_order.py` | Affine-form extraction + Gaussian elimination for coupled blocks; singleton and coupled paths share one code path (a real prior bug forced this unification) |
| F. Incremental build system | `src/c_build.py` (434 lines, largest file), `src/unit_codegen.py` (370 lines, 2nd largest) | Both static-link (`.o`/direct link) and dynamic-link (`.dll`/runtime load) paths coexist; `unit_codegen.py` has the driver codegen for both |
| G. Cache/reuse mechanism | `src/c_build.py`'s `fingerprint_objects()` | SHA-256 of every unaffected object/library checked against cached baseline every cell |
| H. Correctness validation | `src/correctness_c.py`, `src/soundness.py` | Two independent mechanisms: numeric diff (atol=rtol=1e-9) and literal stdout string equality; soundness checked against an independently recomputed before/after IR diff, never against the resolver's own output |
| I. Model generators | `src/scaled_models.py` (148 lines) | `generate_thermal_chain(N)` (3N-1 eq, the only generator actually used in every Stage B experiment) and `generate_rc_ladder(N)` (2N+1 eq, built, validated, **never used in a measurement**) |
| J. Real Modelica models | `models/msl_*`, `msl_src/` (gitignored MSL sparse clone) | 3 real MSL-derived models actually measured: MslRcCircuit (23 eq), MslResistorNetwork (35 eq), MslThermalChain (20 eq); CauerLowPassAnalog (69 eq) is a documented negative result, never run through codegen |
| K. Experiment scripts | `src/measure_c.py`, `src/measure_msl.py`, `src/measure_scale.py`, `src/measure_overhead.py`, `src/change_frequency.py`, `src/break_even.py`, `src/validate_scale.py` | One script per experiment family; all timed with real subprocess `time.perf_counter()` calls, never arithmetic-derived |
| L. Timing infrastructure | inside `c_build.py`/`measure_*.py` | `repeated_*_time()` wrappers; warm-up-discard logic added for the dynamic-link path only |
| M. Statistical/repetition infrastructure | `measure_scale.py`, `measure_msl.py` | Mean ± stdev over 3-5 repeats; no confidence intervals, no effect sizes, no randomized execution order currently computed anywhere |
| N. Tests | `tests/*.py` (31 files, 2,147 lines, 152 passed/1 xfailed at last recorded run) | Includes teeth tests (deliberately break a check, confirm it fails) and a 5-seed determinism audit (`test_determinism_audit.py`) |
| O. Figures | `src/figures.py`, `src/figures_msl.py`, `src/figures_scale.py` | Deterministic SVG+PDF export (pinned hash salt, stripped timestamps); byte-identical regeneration is itself tested |
| P. Reproducibility infra | `results/measurements_provenance.json`, `docs/results.md`'s citation-per-number discipline | Strong for a project this size; no containerization, no cross-machine replication, no seed/version pinning file beyond `rumoca==0.9.20` in `requirements.txt` |

**Unused infrastructure that makes new experiments cheap:**
- `generate_rc_ladder(N)` exists, is tested, and has never produced a
  measurement (`docs/results.md` §1.3). This is a second model topology
  ready to use for a topology-generality experiment at near-zero
  implementation cost.
- The dynamic-link and static-link build paths **both still exist** in
  `c_build.py`/`unit_codegen.py` side by side (dynamic-link was added, not
  substituted). This means an ablation comparing them directly (a natural
  "link-strategy ablation") is close to free — the paper already reports
  both numbers at small scale (§3.4 of `docs/results.md`) but never plots
  them side by side as a controlled ablation across the size sweep.
- `src/msl_change.py` and `src/change.py` support three change types (swap,
  sensor-add, removal) already implemented and tested; only swap and
  removal are exercised at the generated-model scale sweep. Sensor-add at
  scale is untested.
- `src/validate_scale.py` (a correctness-only, `repeats=1` harness distinct
  from the speed-measurement harness) is already the right tool for pushing
  bit-identical validation further without paying for repeated-timing cost
  — it produced the N=2,000/5,000 data points and could be pushed further
  cheaply for correctness-only evidence even where speed measurement is too
  expensive.

**Experiments partially implemented but not reported in the paper:**
- N=2,000 and N=5,000 correctness+one-off-speed data (`docs/results.md`
  §2.1) exist in `results/measurements_validate_scale.csv` but are **not**
  in `paper/main.tex` at all — the paper's scale table stops at 2,999
  equations (Table IV). This is a significant omission: the paper's own
  Limitations section (item 1) references "5,999 and 14,999" one-off
  numbers narratively but the actual table showing the trend breaking down
  is not shown to the reader.
- `docs/results.md` §3.1-3.2 (the superseded static-link plateau) is
  richly documented in the results ledger but compressed to a few
  sentences in the paper — the full before/after contrast (with the
  disproportionate-stdev evidence) is a stronger scientific story than
  the paper currently tells it.

---

## 4. Claim-evidence matrix

| Claim | Evidence in repository | Evidence in paper | Strength | Reviewer concern | Required action |
|---|---|---|---|---|---|
| Incremental rebuild is bit-identical to full rebuild | `results/measurements_*.csv`, SHA-256 fingerprinting, 2 independent diff mechanisms, `tests/test_dynamic_link.py`, `tests/test_scale_correctness.py` | Table II caption + prose throughout | **SUPPORTED** | none significant | none |
| Speedup grows with model size (5.66x→27.01x) | `results/measurements_scale.csv`, 3 repeats, tight stdev (<9%) | Table IV, Fig. speedup_vs_size | **SUPPORTED**, but only for 149-2,999 eq | The trend is not shown to continue past 2,999 in a repeated-measurement sense; the one-off N=5,999/14,999 points are narrated, not tabulated, and the N=5,000 point directly contradicts the trend (3.33x) | Either explain/fix the N=5,000 anomaly or explicitly bound the claim's validity range in the abstract, not just the limitations section |
| Real-model generality (MSL) | 3 real models, 4 change cells | Table III (MSL speedup) | **PARTIALLY SUPPORTED** | n=3 real models is thin for a "generalizes to real MSL components" claim; all 3 are simple series/parallel topologies, none has a genuine coupled block exercised at the real-model scale except MslResistorNetwork's 14-eq block (not separately highlighted as a coupled-block validation) | Broaden real-model corpus (Section 9) |
| Compiler-independent / general applicability to "Modelica models" | none beyond the above | Abstract implies broad applicability via "Modelica digital twins" title | **UNSUPPORTED as stated broadly** — single front end (Rumoca), single index class (index-1), single toolchain (MinGW/gcc), single OS (Windows) | A reviewer versed in Modelica tooling will ask whether this transfers to OpenModelica/Dymola-compiled models or is Rumoca-IR-specific | Either narrow the title/abstract's scope explicitly or add a second front-end data point (high cost, see Section 8) |
| Break-even change frequency is a real, usable number | `results/measurements_break_even.csv`, 3 repeats of full rebuild, independent rerun-stability check | Table V, Fig. break_even_crossing | **SUPPORTED for the one measured configuration** (N=300 rooms, this harness's specific streaming implementation) | The break-even threshold itself moved from 4 to 2 purely because of an artifact of the *harness's own* fresh-directory-per-step design (`docs/results.md` §6.3) — this makes the number closer to "a property of this test harness" than "a property of the system," which is exactly the kind of thing a journal reviewer flags | Fix the harness's own O(N) copy cost (already named as future work) before treating the break-even number as portable, or explicitly caveat it as harness-bound |
| Codegen O(n²) bug found and fixed, ~49x | `docs/findings/scaling-bottlenecks.md` Bottleneck 5, before/after table, unchanged regression suite | Table II (codegen), §on2 | **SUPPORTED** | none significant | none |
| Scale reaches "industrial" range | N=500 (full pipeline verified), N=1,000 (repeated speedup), N=5,000 (codegen profiling only), N=10,000 (Rumoca compile-only) | Limitations item 1 states this honestly | **NEEDS MORE VALIDATION** — self-disclosed | A reviewer will ask why 10^5 equations (the originally stated target per `prd-combined.md`) was not reached; the paper's own honesty here is a strength, but "index reduction and scale beyond a few thousand equations are both out of reach" (abstract) undersells that codegen/matching/graph stages ARE confirmed near-linear to 14,999 — only the *link/copy* step and the *front-end compile* step are the actual scale blockers | Clarify in the paper which stage is the actual scale bottleneck (front-end parse + per-file copy, not the paper's own algorithmic contributions) |
| "Every claim... checked at the same level of evidence" (Conclusion) | Broadly true per the ledger | Conclusion prose | **SUPPORTED as a project-discipline claim**, not itself a scientific result | A reviewer may read this as slightly self-congratulatory rhetoric rather than a falsifiable claim | Consider softening or grounding it with one concrete forward pointer (e.g., "every number in this paper cites a script and a log, in a public repository") |
| Linear-coupled-block scope is sufficient | No tested model (real or hand-written) needs nonlinear codegen | Limitations item 4 | **SUPPORTED as a negative/scoping claim**, not demonstrated as a general sufficiency result | A reviewer may ask: is this because nonlinear loops are rare in practice, or because the corpus never had a chance to contain one? These are different claims | Either find/construct one real nonlinear-loop model to test the boundary, or reframe the claim more narrowly ("no nonlinear loop appeared in this corpus," not "nonlinear loops don't matter") |

---

## 5. Current strengths (worth preserving, not diluting)

- **Bit-identical correctness on every cell**, not asserted once. This is
  rare and should stay the paper's spine, not be diluted by adding looser
  tolerance-based experiments later for convenience.
- **Two real, independently verified third-party bugs found**
  (networkx Hopcroft-Karp non-determinism; Rumoca's algebraic-loop solver).
  These are citable findings in their own right and could be pulled into a
  short "artifacts of building on real infrastructure" subsection — this is
  exactly the kind of grounded, unglamorous detail that distinguishes a
  system that was actually built from one that is only simulated in a
  paper.
- **Honest negative results retained** (static-link plateau, Cauer gap,
  N=5,000 anomaly all still visible in the evidence ledger even though some
  are compressed or omitted from the paper itself).
- **The diagnose-then-fix narrative arc** (relink ceiling → dynamic
  linking) is a genuinely compelling systems story and is already
  well-told in the paper.
- **The break-even framing** is a rare, practically useful contribution;
  most incremental-build papers stop at "faster," not "faster, and here is
  when you should actually use it."

---

## 6. Journal-level gaps

For each: what's missing, why a reviewer cares, whether it's necessary,
whether the existing repo can address it, what new work it would need, and
what experiment would show the improvement.

**1. Novelty.** Missing: an explicit statement of what specifically is new
versus Make/Bazel-style incremental builds beyond "the units are equations
not files." Reviewer cares because "we applied a well-known idea (matching,
SCC, reachability, incremental build) to a new domain" needs to show the
domain transfer was non-trivial — and it clearly was (the states-as-knowns
graph correction, the singleton/coupled codegen unification bug, the
relink-vs-recompile cost inversion at scale) but the paper doesn't
foreground these as the actual novel contributions distinct from "we built
a thing." **Necessary: yes. Addressable from existing repo: yes** — this is
a writing/framing fix, not new experiments (Category E, presentation).

**2. Technical depth.** Missing: discussion of why a from-scratch,
linear-only, index-1-only C emitter is an acceptable stand-in for a real
Modelica compiler backend, and what would be required to generalize it.
Reviewer cares because a compilers-audience journal will want to know the
approach isn't an artifact of a toy backend. **Necessary: yes, at least as
discussion. Addressable: yes, writing-only** (the limitations already state
the boundary; a dedicated "what would nonlinear/index>1 support require"
paragraph, drawing on the already-written Future Work section, would help).

**3. Experimental depth.** Missing: no experiment varies *change size*
(e.g., how many equations a single edit touches) as an independent
variable — every measured change is a single component swap/add/remove.
Missing: no experiment on *change locality* (central vs. peripheral node in
the topology) despite the paper's central claim being about locality.
Reviewer cares because "ripple is local" is asserted from 4-5 data points,
not systematically varied. **Necessary: yes, this is probably the single
highest-value addition. Addressable from existing repo: substantially** —
`scaled_models.py`'s parameterized generator already supports editing any
room index; a systematic sweep over edit position × chain length needs
only a new driver script reusing `measure_scale.py`'s existing
`run_cell()`-style plumbing (Category B: stronger empirical validation).

**4. Validation.** Missing: cross-checking against a second Modelica
front end (OpenModelica) or against Rumoca's own runtime for the models
where Rumoca's runtime is trustworthy (it wasn't, for the coupled-block
models — see the Rumoca bug finding — but it was for the real MSL models).
Reviewer cares because "validated against an independent analytical
solution" only covers the 2-3 hand-derived cases; the real MSL models are
validated only by "matches a full rebuild," not against an independent
ground truth for absolute correctness (only relative correctness).
**Necessary: partially** — relative correctness (incremental == full) is
actually the paper's real claim and is well covered; absolute correctness
against a second compiler is a nice-to-have, high cost (new toolchain
install), **UNVERIFIED whether OpenModelica is installed on this
machine**.

**5. Comparison with existing methods.** Missing entirely: there is no
baseline other than full rebuild. Reviewer cares a great deal — a journal
reviewer will ask "compared to what?" The paper implicitly compares against
"rebuild everything," which is the weakest possible baseline. A stronger
paper would also compare against at least one naive incremental strategy
(e.g., "recompile every unit reachable from the changed *file*/*component*
in the source-level connect graph," without the matching-based
partitioning) to show the matching/partitioning step itself adds value
over a cruder dependency notion. **Necessary: yes, high value. Addressable:
moderate implementation** — a naive baseline (source-level connect-graph
reachability, skipping the matching/BLT step entirely) could be built from
existing pieces (the MSL models' connect() structure is already parsed by
Rumoca; a coarser resolver is a new, smaller `resolver_naive.py`).

**6. Generalizability.** Covered above (Gap in Claim-Evidence Matrix, row
2). **Addressable: yes**, using `generate_rc_ladder` (already built,
unused) plus 2-3 more real MSL corpus models (Category B).

**7. Scalability.** The N=5,000 anomaly is the concrete, immediate issue.
**Necessary: yes, high priority** — an unexplained regression sitting next
to a "speedup grows with size" headline claim is exactly the kind of thing
a careful reviewer finds and uses to discount the whole scaling claim.
**Addressable: yes**, with moderate implementation (profiling the N=5,000
cell's incremental-rebuild step-by-step, the way Bottleneck 4/5 were
originally diagnosed) — this is squarely in the repository's own existing
methodology, just not yet applied to this specific data point.

**8. Ablation studies.** None currently exist in the sense of isolating
component contributions. The paper has natural ablation opportunities
already sitting in its own git history (static-link vs. dynamic-link is
literally an A/B measured pair) that are narrated as a before/after fix
rather than presented as a controlled ablation figure. **Necessary: yes.
Addressable: yes, near-zero new implementation** — both code paths already
exist and are both tested; a dedicated ablation figure could be built
almost entirely from data that already exists in
`results/measurements_scale.csv` (dynamic) plus a fresh, short re-run of
the static-link path at the same sizes (Category B, cheap).

**9. Correctness/soundness.** Already strong (Section 5). One real gap:
soundness (`check_soundness`, the independent-diff superset check) is
explicitly **not** re-run at Stage B's generated scale beyond N=299
(`docs/results.md` §10, last paragraph) — it is inferred from
`outputs_identical` rather than independently reproven. **Necessary:
moderate** — worth closing for the largest sizes tested, cheap to do since
the machinery exists.

**10. Reproducibility.** Strong within-machine (provenance file, pinned
package version, deterministic figure regeneration). Missing:
cross-machine/cross-run validation (everything ran on one Windows machine);
no Docker/container/lockfile beyond `requirements.txt`; no public artifact
DOI. **Necessary: yes for a journal artifact-evaluation-style expectation,
lower priority than the scientific gaps.** **Addressable:** packaging is
Category D work, cheap relative to new science.

**11. Statistical rigor.** Currently: mean ± stdev over 3-5 repeats, no
confidence intervals, no effect sizes reported, no randomized execution
order (each size is measured as its own block, not interleaved), warm-up
handling inconsistent (applied to the dynamic-link scale sweep, not
applied — and explicitly reasoned about why not — to the change-frequency
harness). **Necessary: yes, moderate value** — reviewers in a
systems/measurement-conscious venue will want CIs at minimum; the raw data
already exists to compute them retroactively (no new experiments needed,
Category D).

**12. Practical significance.** The break-even result is the strongest
practical-significance evidence and should be foregrounded more. Missing:
any discussion of memory/storage overhead of keeping N cached DLLs around
(a real operational cost of this design, currently unmeasured anywhere).
**Necessary: yes, moderate — a natural reviewer question** ("what does this
cost in disk/memory to maintain?"). **Addressable: cheap** — disk usage of
`build_cache`/build directories is already implicitly present in existing
run artifacts; a `du`-equivalent measurement is a few lines.

**13. Related work.** Present and reasonably scoped (Make, Bazel, MARCO,
OpenModelica, FMI, Grieves on digital twins, Abbasi on drift). Missing:
any citation to incremental-compilation literature specifically for
equation-based/DAE systems outside Modelica (e.g., incremental structural
analysis in other simulation domains), and no discussion of
incremental-linking literature (relevant given Gap 5/8 above touch exactly
that problem). **UNVERIFIED whether such prior work exists to cite** —
worth a literature search before claiming a gap, not assumed.

**14. Limitations.** Already unusually thorough (8 enumerated items in the
paper, 12 in `docs/results.md`). No action needed beyond keeping them in
sync (the paper's list is a subset of the results ledger's list — verify
nothing load-bearing was dropped in the paper's compression pass).

**15. Threats to validity.** Implicitly covered inside Limitations but not
labeled as a distinct "Threats to Validity" section, which many journal
templates expect explicitly (internal validity: single-machine noise;
external validity: single front end, single toolchain, single OS;
construct validity: does "bit-identical" fully capture "correct" for a
model this project's own emitter could theoretically miscompile in a
way that happens to match a wrong full rebuild — unlikely but worth one
sentence). **Necessary: yes, low implementation cost, Category E.**

**16. Journal-level presentation.** Current paper is 6 pages, IEEE
conference-shaped (compressed prose, single-column figures, dense limitation
lists). A journal submission typically wants more depth per section, not
just more content — expanding Methodology with the actual matching/BLT
algorithm pseudocode (currently only prose-described) would help technical
depth without requiring new experiments. **Necessary: yes. Addressable:
Category E, writing-only.**

---

## 7. Existing evidence that could strengthen the paper (currently unused or underused)

| Item | Location | Demonstrates | Reproducible? | Publication-quality? | Verification still needed |
|---|---|---|---|---|---|
| N=2,000/5,000 correctness+one-off speed | `results/measurements_validate_scale.csv` | Bit-identical correctness continues to 14,999 eq; speed trend breaks down at 14,999 | Yes, `src/validate_scale.py` | Correctness data: yes. Speed data: no (single-rep, already flagged noisy) | Re-run repeated (3x) at N=2,000 and N=5,000 specifically to know if 3.33x is a real effect or single-run noise before either publishing or omitting it |
| Static-link vs. dynamic-link at identical sizes | `results/measurements_scale.csv` (superseded static numbers preserved in `docs/results.md` §3.1) plus current dynamic numbers | A clean, already-measured ablation of the link-strategy design choice | Static-link path still exists in code (`c_build.py`), so yes | Data exists; needs to be re-plotted as one paired figure rather than two separate tables | None — this is nearly free, just needs a new figure script |
| MSL real-model 4th cell (MslThermalChain) | `results/measurements_msl.csv`, "Priority 3" entry | Cross-domain generalization (thermal, not just electrical) | Yes, in the standing test sweep | Yes — already in the paper (Table III has 4 rows) | None, already used |
| `generate_rc_ladder(N)` | `src/scaled_models.py`, tested, never measured | A second topology/coupling-flavor family for a generality claim beyond thermal chains | Yes, generator exists and is unit-tested | Not yet — no measurement run | Needs a measurement pass through `measure_scale.py`-equivalent logic |
| Break-even harness's per-step timing breakdown | `docs/results.md` §6.3 ("`[step: incremental_s]`" list) | The harness's own O(N) copy-per-step cost, isolated numerically | Yes | As a diagnostic, yes; not currently a paper figure | Could become a supporting figure explaining *why* the break-even point moved, strengthening rather than undermining the result |
| Superseded static-link stdev evidence | `docs/results.md` §3.1-3.2 | The "relink dominates" diagnosis, evidenced by disproportionate stdev growth | Yes, numbers already recorded | Yes, this is good evidence, currently only narrated in ~2 paper sentences | None — a compression/expansion decision for the paper draft |
| Full pytest suite counts across time | `docs/progress.md` (83→99→106→110→113→134→144→152 tests) | Regression-suite growth alongside feature growth, evidence of engineering discipline | Yes | Supplementary/appendix material at best, not a headline result | None |

---

## 8. Candidate research extensions

Classified HIGH / MEDIUM / LOW / NOT WORTH DOING, and separately (Section 9)
classified by contribution type.

**HIGH VALUE**
- Systematic change-size and change-locality sweep (edit position ×
  topology depth, on the existing `generate_thermal_chain` family). Directly
  strengthens the paper's central "changes are local" claim with more than
  4-5 anecdotal data points.
- Resolve or properly characterize the N=5,000 anomaly. Small implementation
  cost (reuse existing profiling methodology), removes the single biggest
  credibility risk in the current evidence base.
- A naive baseline (coarser, non-matching-based impact resolution) to show
  the matching/partitioning step earns its complexity. This directly
  answers "compared to what" and is the single most reviewer-obvious
  missing piece.
- Link-strategy ablation as a first-class figure (static vs. dynamic at
  matched sizes) — nearly free, high narrative value, directly supports the
  paper's own "we diagnosed and fixed this" story with a controlled
  comparison instead of a before/after narrative.
- `generate_rc_ladder` measurement pass — a second topology family at very
  low cost, strengthens generality claims beyond thermal chains.

**MEDIUM VALUE**
- Broaden real MSL corpus by 2-4 more models (different domains: mechanical,
  hydraulic if available in the MSL subset already cloned; more electrical
  topologies with genuine coupled blocks). Real cost: sourcing/wiring models,
  Rumoca-compatibility risk (MSL coverage in Rumoca is unverified beyond
  what's already been tried).
- Confidence intervals / proper statistical treatment on existing data
  (retroactive, no new experiments needed).
- Disk/memory overhead measurement of the cached-DLL design.
- Soundness re-verification (independent diff check, not just
  `outputs_identical`) at the largest tested sizes.
- Formalize a "Threats to Validity" subsection.

**LOW VALUE**
- Cross-platform (Linux/macOS) replication. Real external-validity value,
  but high cost (new environment setup, likely different toolchain
  behavior around the exact antivirus/filesystem effects the paper
  currently attributes speed anomalies to — which is itself informative but
  expensive) relative to what it buys for this paper's specific claims.
- Second Modelica front end (OpenModelica) comparison. High value in
  principle, very high cost (a second compiler toolchain, a second IR
  format to adapt the matcher to), likely out of proportion to the paper's
  scope.

**NOT WORTH DOING** (for this paper specifically, though real engineering
work in general)
- Full Pantelides index reduction implementation. The paper already
  correctly identifies and precisely bounds this gap (`docs/findings/
  cauer-index-reduction.md` is genuinely excellent scoping work); actually
  implementing index reduction is a compiler-backend-scale project on its
  own and would dilute rather than strengthen this paper's focused claim.
  Better treated as a clearly-scoped "not this paper" boundary, which it
  already is.
- Nonlinear (Newton) block codegen. No model in the corpus needs it; adding
  it speculatively for "completeness" would be untested code with no
  experiment to validate it, actively worse than the current honest
  "not needed by anything tested" scoping.
- Discrete/event-driven signal support. Same reasoning — a real, large
  feature (If-expression / event-condition codegen) with no experiment plan
  currently justifying its cost for this paper's specific contribution.

---

## 9. "More experiments" versus "new science" classification

| Proposed change | Classification | Why |
|---|---|---|
| Naive-baseline comparison (Gap 5) | **A. New scientific contribution** | Currently the paper cannot claim its design choices (matching-based partitioning specifically, versus a cruder dependency notion) are *necessary* — only that doing *something* incremental beats nothing. A baseline turns this into an actual comparative claim. |
| Change-size/locality sweep (Gap 3) | **A/B mixed — mostly A** | Turns "ripple is local" from an anecdote (4-5 hand-picked changes) into a characterized relationship (ripple as a function of edit position and topology), which is closer to a real finding about the *mechanism* than more repetitions of the same experiment. |
| Resolving the N=5,000 anomaly | **B. Stronger empirical validation** | Doesn't add a new mechanism or claim — it either confirms the existing growing-speedup claim more rigorously or narrows its validity range honestly. Necessary regardless of framing. |
| Link-strategy ablation figure | **B, verging on A** | The comparison already exists as raw numbers; presenting it as a controlled ablation makes an implicit claim (dynamic linking specifically, not just "engineering effort," is what fixed scaling) explicit and testable, which is more than cosmetic. |
| `generate_rc_ladder` measurement | **B. Stronger empirical validation** | Same mechanism, different topology — broadens the evidence base for an existing claim, does not create a new one. |
| Broader real MSL corpus | **B. Stronger empirical validation** | Same reasoning; more real models is evidence depth, not new science, unless a genuinely different structural pattern (e.g., a real coupled/algebraic-loop-bearing real model) is found, which would upgrade this to A. |
| Confidence intervals, warm-up consistency | **D. Better reproducibility / rigor presentation** | Does not change any conclusion, changes how confidently it can be stated. |
| Disk/memory overhead measurement | **C. Better engineering characterization**, borderline B | Useful practical information, not evidence for or against the paper's central claim. |
| Threats-to-validity section, expanded Methodology | **E. Better presentation only** | No new evidence; improves how existing evidence is read. |
| Cross-platform replication | **B, high cost** | Would strengthen external validity but doesn't change the mechanism claimed. |
| Second Modelica front end | **A, if attempted, very high cost** | Would be a genuine generality contribution (compiler-independence) but is a different-scale project. |

---

## 10. Possible journal-level research directions (neutral, not ranked)

**Direction 1 — "Locality is characterized, not anecdotal."** Central
question: what structural properties of a model and an edit predict ripple
size and speedup? Current evidence: 4-5 real/hand-written change cells plus
a fixed-position edit in the generated sweep. Missing evidence: systematic
variation of edit position, edit type, and topology depth/branching.
Implementation: a new sweep driver over `scaled_models.py` (or a small new
generator family with tunable branching factor), reusing all existing
measurement/correctness machinery. Expected figures: ripple vs. edit
position (a "locality profile" plot), ripple vs. topology branching factor.
Retained from current paper: everything (this direction extends, does not
replace, existing results). Restructuring needed: Results section grows a
new subsection; Limitations item about "small real-model corpus" can be
partially retired for the *generated-model* half of the generality claim
(real-model breadth remains a separate, honestly-scoped limitation). Major
risk: if ripple turns out to correlate simply with edit position in an
obvious way (e.g., purely with topology depth), this could read as a
confirmatory rather than surprising result — still journal-worthy as
rigorous characterization, but less dramatic. Difficulty: moderate (new
driver script, no new codegen).

**Direction 2 — "Necessity, not just sufficiency, of the matching-based
design."** Central question: does the matching/BLT partitioning step
actually earn its complexity over a simpler dependency notion? Current
evidence: none (no baseline exists). Missing evidence: a naive baseline
(e.g., component-level or file-level reachability instead of
equation-level matched-unit reachability) measured on the same models.
Implementation: a new, deliberately cruder resolver (`resolver_naive.py`),
reusing the existing correctness/timing harness. Expected figures/tables: a
paired bar chart, ripple and speedup, matching-based vs. naive, same
models. Retained: all current results stand unchanged; this adds a column,
not a rewrite. Restructuring: a new "Baselines" subsection in Methodology
plus a new Results subsection. Major risk: if the naive baseline turns out
to be nearly as good (plausible on these specific simple topologies — chain
and star-like circuits may not stress-test the difference between
component-level and equation-level granularity), that is itself a valuable,
honest finding, but would blunt the paper's implicit claim that fine-grained
matching-based partitioning matters. Difficulty: moderate (a new, simpler
resolver plus a driver reusing existing infrastructure); genuinely the
highest expected-value direction per unit of implementation cost.

**Direction 3 — "The link/assembly step is the real scaling story."**
Central question: reframe the paper's contribution more explicitly around
the finding that *dependency-graph-based impact analysis was never the
bottleneck* — the build/link/assembly strategy was, both times (relink at
N~1,000, per-file copy at N~5,000+). Current evidence: strong (Bottleneck
4, Bottleneck 4 fix, the N=5,000 anomaly consistent with the same class of
cost). Missing evidence: closing the loop on the O(N) copy-per-rebuild cost
that Future Work already names (reusing a persistent build directory
in-place instead of copying into a fresh one every time) — this would be
new engineering, potentially resolving the N=5,000 anomaly and pushing
scale further in one motion. Implementation: moderate-to-substantial (a
persistent-build-directory design, likely non-trivial on Windows given the
antivirus-interaction findings already documented). Expected result: either
confirms the hypothesis (speedup keeps growing past 2,999 once the O(N)
copy is removed) or reveals a new, different bottleneck — both are
publishable. Retained: the entire existing pipeline and result set; this is
additive. Restructuring: Future Work section becomes a Results section;
title/abstract could shift emphasis toward "identifying and eliminating
build-system bottlenecks in incremental equation-based compilation" as the
throughline. Major risk: implementation risk is real (this is systems work,
not measurement work) and the antivirus-interaction confound already
documented makes clean before/after comparison harder to reason about.
Difficulty: substantial.

**Direction 4 — "Scope the claim narrowly and go deep on rigor instead of
breadth."** Central question: rather than broadening the model corpus or
adding baselines, treat the paper as a rigorously bounded case study — index-1
linear-coupled Modelica models on one toolchain — and maximize statistical
and methodological rigor within that scope (confidence intervals, ablations
of matching/partitioning/impact-resolution/caching in isolation, formal
threats-to-validity treatment, the naive baseline from Direction 2 as an
ablation rather than a generality claim). Current evidence: nearly all of it
already exists in some form (Section 7). Missing evidence: the statistical
treatment layer (Category D work) plus the ablations from Gap 8. Implementation: 
low-to-moderate (mostly analysis of existing data plus 1-2 new ablation runs).
Expected figures: an ablation table (component removed → effect on
speedup/ripple), CI bands on all existing timing figures. Retained: the
entire current evidence base, reorganized rather than extended. Restructuring:
moderate — Results section reorganized around ablations rather than purely
chronological narrative; Limitations section's scope boundaries become more
central to the paper's framing rather than an apology at the end.
Major risk: this direction produces a narrower, more modest paper that may
read as less ambitious even though it is more rigorous — a real editorial
tradeoff, not a technical one. Difficulty: low-moderate, the fastest path
to a defensible journal submission.

These four are not mutually exclusive — Direction 2 (naive baseline) and
Direction 4 (rigor/ablations) compose naturally, and Direction 1 (locality
sweep) strengthens either. Direction 3 is the highest-risk, highest-reward,
and the most different in character from the others (systems engineering
versus measurement/analysis).

---

## 11. Experiment plan

Only experiments judged HIGH or MEDIUM value in Section 8 are detailed here.

### E1. Naive-baseline comparison

- **RQ:** Does equation-level, matching-based recompilation-unit
  partitioning identify a materially smaller affected set than a coarser,
  component/file-level dependency notion, on the same models and changes?
- **Hypothesis:** Yes — the matching-based partition should show lower
  ripple (smaller affected fraction) and comparable-or-better speedup than
  a naive resolver, because it operates at equation granularity rather than
  component granularity.
- **Independent variables:** resolver strategy (matching-based vs. naive
  component-reachability), model, change type.
- **Dependent variables:** affected-unit fraction (ripple), measured
  speedup, wall-clock resolution time itself (the naive resolver should be
  cheaper to compute, which is a real tradeoff worth reporting even if it
  loses on ripple).
- **Controlled variables:** same models, same injected changes, same
  build/link strategy (dynamic-link, current default), same machine,
  interleaved repeats.
- **Models/datasets:** the existing MSL corpus (MslRcCircuit,
  MslResistorNetwork, MslThermalChain) plus the ThermalChain generator at
  2-3 sizes.
- **Repetitions:** 5 per cell for the small MSL models (matches existing
  practice given known small-model noise), 3 per cell for generated models
  (matches existing scale-sweep practice).
- **Baseline:** the naive resolver itself is the "baseline" being compared
  against the paper's existing matching-based method (which becomes the
  "treatment").
- **Metrics:** ripple, speedup, resolver computation time.
- **Expected figure:** paired bar chart (matching-based vs. naive), ripple
  and speedup, per model.
- **Supports the claim if:** matching-based ripple is meaningfully lower
  (not just numerically lower — report effect size, not just point
  estimates) on at least the models with genuine coupled blocks
  (MslResistorNetwork's 14-eq block is the best test case, since a
  component-level resolver would likely treat the whole coupled component
  group as one unit regardless).
- **Would weaken/falsify the claim if:** naive and matching-based ripple
  are statistically indistinguishable across the whole corpus — this would
  be an honest, still-valuable finding (the corpus's topologies may simply
  not need equation-level granularity), and should be reported as such
  rather than suppressed.

### E2. Change-size and change-locality sweep

- **RQ:** How does affected-unit fraction (ripple) vary with the structural
  position of an edit within a model's topology, and does the relationship
  match a simple locality model (e.g., ripple proportional to
  distance-to-boundary) or something more complex?
- **Hypothesis:** ripple is small and roughly constant for edits near the
  "leaf" end of a chain/tree topology and does not grow with total model
  size (consistent with the existing "2 of 3N-1 units affected" finding),
  but may grow for edits nearer a shared/central component.
- **Independent variables:** edit position (room index in the chain
  generator, 1..N), model size N.
- **Dependent variables:** ripple, speedup, absolute affected-unit count.
- **Controlled variables:** edit type (fixed to one, e.g. conductance swap,
  to isolate position as the only varying factor), toolchain, machine.
- **Models:** `generate_thermal_chain(N)` at 1-2 fixed sizes (e.g. N=250
  and N=1,000, reusing already-validated sizes), edit position swept across
  the full range at some practical sampling interval (e.g. every 10th room,
  not every single one, to bound cost).
- **Repetitions:** 3 per position (matches existing scale-sweep practice);
  consider fewer repeats per position with more positions sampled, given
  the existing evidence that ripple itself (unlike timing) is perfectly
  deterministic run to run — position-sweep breadth likely matters more
  than repeat depth here.
- **Baseline:** none needed — this experiment characterizes the existing
  method's own behavior, not a comparison.
- **Metrics:** ripple as a function of position, absolute affected count.
- **Expected figure:** ripple (or affected-unit count) vs. edit position,
  one line per model size.
- **Supports the claim if:** ripple stays small and roughly independent of
  N regardless of position, i.e., the "changes are local" claim holds
  uniformly, not just at the one position tested so far.
- **Would weaken/falsify the claim if:** ripple grows sharply near
  particular topology positions (e.g., a shared bus/ground node) — this
  would be a genuinely important finding bounding the claim's real
  applicability, not a failure to hide.

### E3. Resolve the N=5,000 anomaly

- **RQ:** Is the 3.33x speedup collapse at N=5,000 (14,999 equations) a
  real, reproducible effect of the still-present O(N) per-rebuild copy
  cost, or single-run noise?
- **Hypothesis:** it is the O(N) copy cost, per the paper's own existing
  diagnosis pattern (Bottleneck 4/4-fix), now dominating again at a larger
  N than the original fix was validated against.
- **Independent variables:** none new — this is a targeted re-measurement
  plus profiling, not a sweep.
- **Dependent variables:** speedup, and (new) a stage-by-stage timing
  breakdown of the incremental-rebuild step specifically (matching how
  Bottleneck 5's O(n²) codegen bug was originally isolated: instrument each
  substep, not just the total).
- **Controlled variables:** same model, same machine, same build strategy.
- **Models:** `ThermalChain{5000}` (already generated once for this exact
  purpose).
- **Repetitions:** this specific cell was previously run only once (75
  minutes); given the cost, **at minimum 2 more repeats** are needed before
  treating any number as more than anecdotal — budget and machine-time
  permitting, given the ~75-minute-per-run cost documented in
  `docs/results.md` §2.1.
- **Statistical treatment:** given the extreme per-run cost, report the
  small-n result honestly with explicit caveats rather than pretending
  n=2-3 gives a tight CI; consider a cheaper proxy (measure just the
  per-file copy step directly, in isolation, at N=5,000, without a full
  incremental-rebuild timing) as an alternative to full expensive re-runs.
- **Baseline:** none — this is root-cause diagnosis, not a comparison.
- **Metrics:** wall-clock breakdown: recompile time, copy/assembly time,
  driver relink time.
- **Expected output:** either a table showing copy time dominates at
  N=5,000 (confirming the hypothesis, consistent with the existing
  `du -sh`-timeout evidence already in `docs/results.md` §2.1) or a
  different, newly-identified cost.
- **Supports the claim if:** the breakdown confirms copy/assembly
  dominates, which converts an "unexplained anomaly" into a "known,
  named, consistent-with-theory limitation" — this is a real improvement
  in the paper's credibility even without fixing the underlying cost.
- **Would weaken the claim if:** the breakdown reveals something new and
  inconsistent with the existing bottleneck theory — still worth reporting,
  but would require re-examining whether the growing-speedup trend is as
  well-understood as currently claimed.

### E4. Link-strategy ablation (near-zero-cost)

- **RQ:** How much of the observed speedup improvement (flat 1.8x-2.3x →
  growing 5.66x-27.01x) is attributable specifically to dynamic linking,
  isolated from any other change made at the same time (DLL stripping,
  warm-up handling)?
- **Hypothesis:** dynamic linking is the dominant factor, per the existing
  causal diagnosis, but the DLL-stripping and warm-up fixes (Section 8 of
  `docs/findings/scaling-bottlenecks.md`) each contribute measurably too —
  currently conflated into one "the fix" narrative.
- **Independent/dependent/controlled variables, models, repetitions:**
  reuse exactly the existing `measure_scale.py` harness and sizes; sweep
  three configurations (static-link; dynamic-link unstripped, no warm-up;
  dynamic-link stripped + warm-up, i.e. current) rather than two.
- **Baseline:** static-link (already measured, `docs/results.md` §3.1).
- **Metrics:** speedup, stdev (the stdev-reduction evidence is itself part
  of the finding).
- **Expected figure:** 3-line or 3-bar-group comparison across sizes.
- **Cost:** low — two of three configurations already have full data;
  only the "unstripped, no warm-up" middle configuration needs fresh
  measurement, and only at 1-2 sizes to confirm the attribution, not the
  full 5-point sweep.
- **Supports the claim if:** dynamic linking alone (even unstripped, no
  warm-up) recovers most of the growth; stripping/warm-up refine variance,
  not the core trend.
- **Would weaken/refine the claim if:** stripping turns out to be load-
  bearing for the *trend*, not just the *variance* — still a fine result,
  just a more nuanced one than currently told.

---

## 12. Baselines and ablations

**Baselines** (only where implementable/justifiable, per the task's own
constraint):
- **Full rebuild** — already the paper's baseline throughout. Keep.
- **Naive component/file-level reachability resolver** (E1 above) — the
  single most valuable addition; directly implementable by reusing the
  existing `resolver.py` interface with a coarser graph construction.
- Alternative matching strategy (e.g., a different maximum-matching
  algorithm) is **not** a meaningful baseline here — the paper's own
  finding is that matching *correctness/determinism* was the issue (the
  networkx bug), not that a different matching algorithm would find a
  materially different partition. **Not recommended** as a baseline; the
  determinism finding is already the relevant contribution on this axis.
- Alternative partitioning (e.g., not using SCC/BLT blocks, using some
  looser clustering) is possible but its main value would be *as* the
  naive baseline in E1, not as a separate experiment — recommend folding
  into E1 rather than treating as distinct.
- Alternative caching/relinking strategy is exactly Direction 3 (Section
  10) — implementable but substantial, treat as a possible future-work
  item rather than a baseline for this submission cycle unless the team
  wants to pursue Direction 3 specifically.

**Ablations** (isolating contribution of each pipeline stage):
- **Matching** — ablate by comparing against E1's naive resolver (a
  resolver that doesn't need a matching at all). This is the practical way
  to isolate matching's contribution without inventing an artificial
  "matching-free but still equation-level" variant, which would not
  correspond to any real design point.
- **Recompilation-unit partitioning (BLT/SCC)** — the "states are not edge
  sources" correction (Section 1.4 of `docs/results.md`) is *already* a
  natural ablation (raw graph vs. causalized graph), fully measured
  (RLCCircuit 50%→33%, ThermalNetwork 100%→22%), but presented as a bug
  fix rather than an ablation figure. **Recommend re-presenting this
  existing data as an explicit ablation table** — near-zero additional
  cost, meaningfully strengthens the paper's demonstrated understanding of
  its own design choices.
- **Graph reachability (impact resolution)** — already validated via the
  independent soundness check (superset property); an ablation here would
  mean comparing reachability against, e.g., recompiling every unit in the
  same connected component regardless of direction — low expected value,
  **not recommended**, the soundness check already establishes reachability
  is both necessary (nothing missed) and reasonably tight (ripple stays
  small).
- **Caching** — ablate by disabling cache reuse (always recompile
  everything the resolver marks, but never reuse *any* cached object even
  for unaffected units) — this reduces to "full rebuild," already measured.
  **Not a new experiment, already covered.**
- **Incremental code generation** — not separately ablatable in the
  current design (codegen always runs per-unit); not applicable.
- **Incremental linking (dynamic vs. static)** — this is E4 above.

---

## 13. Reproducibility improvements

- Pin all tool versions in one place (currently `rumoca==0.9.20` is in
  `requirements.txt`; gcc/MinGW version, OS build, and Python patch version
  are recorded in `results/measurements_provenance.json` but not
  cross-checked against a single canonical "environment.md").
- Add explicit confidence intervals (or at minimum, min/max alongside
  mean±stdev) to every timing table — computable from data already logged
  in the CSVs, no new experiments needed.
- Consider archiving the repository with a DOI-bearing artifact (e.g.
  Zenodo/Software Heritage) at submission time — standard journal
  expectation, near-zero technical cost, purely a submission-process step.
- The `msl_src/` MSL sparse clone is gitignored and not committed —
  document the exact clone/sparse-checkout commands in a dedicated
  `REPRODUCE.md` (currently split across `README.md` and `docs/progress.md`
  prose) so a reviewer can reconstruct the full corpus without archaeology.
- **UNVERIFIED:** whether the exact gcc/MinGW version installed on the
  measurement machine is captured anywhere beyond "MinGW-w64 GCC 15.2" in
  the paper's Experimental Setup sentence — worth confirming this matches
  `results/measurements_provenance.json` exactly before submission.

---

## 14. Risk and feasibility analysis

| Item | Technical risk | Time cost (rough) | Dependency |
|---|---|---|---|
| E1 naive baseline | Low — reuses existing resolver interface | Small (new resolver + reused driver) | None |
| E2 locality sweep | Low | Small-moderate (new sweep driver, reused everything else) | None |
| E3 N=5,000 diagnosis | Moderate — expensive per-run (~75 min), Windows Defender confound already complicates causal attribution | Moderate (2-3 more ~75-min runs, or a cheaper isolated copy-step measurement) | None, but expensive in wall-clock machine time |
| E4 link-strategy ablation | Low | Small (1-2 new size points on an existing, already-built code path) | None |
| Ablation table (states-as-knowns) | None — data already exists | Trivial (repackaging) | None |
| Broader real MSL corpus | Moderate — Rumoca's actual MSL coverage beyond what's been tried is **UNVERIFIED** | Moderate-high, uncertain | Needs exploratory spikes before committing to specific new models |
| Statistical CI layer | None | Small | None, retroactive on existing data |
| Direction 3 (persistent build dir) | High — real systems engineering, antivirus-interaction confound already documented as hard to fully isolate | High | Best treated as a separate, longer-horizon effort |
| Cross-platform replication | Moderate-high — different filesystem/AV behavior could change conclusions in confusing ways | High | Lower priority given the paper's claims don't currently depend on OS-independence |
| Second front end (OpenModelica) | High — new IR format, unverified compatibility | Very high | Not recommended for this submission cycle |

---

## 15. Recommended phased work plan

**Phase 0 — Repository cleanup / reproducibility fixes**
- Objective: close the gap between what's measured and what's written up;
  fix the paper/ledger sync issue (N=2,000/5,000 data exists but isn't in
  the paper).
- Files: `paper/main.tex`, possibly a new `docs/reproduce.md`.
- Expected output: paper's scale table extended or footnoted with the
  N=2,000/5,000 data and an honest characterization of the anomaly (even
  before E3 resolves it); CI/stdev columns added to existing tables from
  already-logged data.
- Scientific value: low-medium (no new evidence, but closes an existing
  credibility gap).
- Difficulty: low.
- Cost: hours, not days.
- Dependency: none.

**Phase 1 — Experiments requiring little or no new implementation**
- E4 (link-strategy ablation, partial), the states-as-knowns ablation
  repackaging, `generate_rc_ladder` measurement pass, disk/memory overhead
  measurement.
- Expected output: 2-3 new figures/tables, all from data that's either
  already collected or trivially collectable with existing scripts.
- Scientific value: medium (Category B, strengthens existing claims).
- Difficulty: low.
- Dependency: Phase 0 not required but natural to sequence after.

**Phase 2 — Experiments requiring moderate implementation**
- E1 (naive baseline — highest priority item in this phase), E2 (locality
  sweep), E3 (N=5,000 diagnosis).
- Expected output: a new "Baselines" subsection with the naive-resolver
  comparison; a locality-characterization figure; a resolved or precisely
  bounded N=5,000 anomaly.
- Scientific value: high (E1 is Category A, E2 is A/B, E3 removes a
  credibility risk).
- Difficulty: moderate.
- Dependency: E1 should come first — it is the highest-value, lowest-risk
  item across the entire plan.

**Phase 3 — Potential major research extensions**
- Direction 3 (persistent build directory / closing the remaining O(N)
  cost) if pursued; broader real MSL corpus if Rumoca coverage permits;
  cross-platform replication if targeting a venue that expects it.
- Scientific value: potentially high (Direction 3 could both resolve E3
  and push the scale claim further in one motion) but high implementation
  and time risk.
- Difficulty: substantial.
- Dependency: E3's diagnosis should inform whether Direction 3 is worth
  attempting at all (if the N=5,000 breakdown reveals something other than
  the expected copy-cost story, the fix target changes).

**Phase 4 — Paper restructuring and journal presentation**
- Expand Methodology with algorithm-level detail (pseudocode for the
  matching/BLT/reachability pipeline); add an explicit Threats to Validity
  subsection; reframe the contributions list per Section 6's novelty
  discussion; integrate whichever of Phase 1-3's results were completed.
- Scientific value: none directly (Category E), but necessary to make the
  above evidence legible to a journal reviewer.
- Difficulty: low-moderate (writing, not implementation).
- Dependency: should follow, not precede, at least Phase 1 and the E1
  baseline from Phase 2, since the paper's structure (especially a new
  Baselines section) depends on what those experiments actually show.

---

## 16. Expected final paper structure (if Phases 0-2 and Direction 2/4 are pursued)

1. Introduction (contributions list reframed per Section 6's novelty
   discussion — foreground the states-as-knowns correction and the
   relink-vs-recompile diagnosis as findings, not just "we built X")
2. Background and Related Work (unchanged, possibly +1-2 citations per
   Gap 13's literature check)
3. Methodology (expanded with matching/BLT/reachability pseudocode)
4. Baselines (**new** — the naive resolver from E1)
5. Experimental Setup (unchanged)
6. Results
   - 6.1 Generality on real MSL models (unchanged)
   - 6.2 Matching-based vs. naive partitioning (**new**, E1)
   - 6.3 Locality characterization (**new**, E2)
   - 6.4 The quadratic codegen bug (unchanged)
   - 6.5 Speedup vs. model size, including the extended range and the
     N=5,000 anomaly's diagnosis (extended, E3)
   - 6.6 Link-strategy ablation (**new**, E4, folds in the existing
     static/dynamic narrative as a controlled comparison)
   - 6.7 One-time setup overhead (unchanged)
   - 6.8 Break-even change frequency (unchanged, possibly with the
     harness's own O(N) cost caveat made more explicit per the
     claim-evidence matrix)
7. Threats to Validity (**new**, separated out of Limitations)
8. Limitations (trimmed to genuine open scope boundaries: index reduction,
   nonlinear blocks, discrete/event signals, change detection, single
   toolchain/machine)
9. Future Work (Direction 3 if not pursued this cycle, else folded into
   Results)
10. Conclusion

---

## 17. Questions/decisions for you before any implementation starts

1. **Priority order:** does E1 (naive baseline) match your own sense of
   what a reviewer would push back on hardest, or do you see the
   generality gap (more real models) as more urgent than a baseline
   comparison? These pull implementation effort in different directions
   (baseline building vs. model sourcing).
2. **N=5,000 anomaly:** given the ~75-minute cost per full-pipeline run at
   that size, are you willing to spend several hours of machine time on
   E3, or would you prefer the cheaper option (isolate and measure just the
   copy/assembly step directly, without a full repeated-timing run) even
   though it's less conclusive?
3. **Direction 3 (persistent build directory):** this is the
   highest-risk/highest-reward item in the whole plan (real systems
   engineering, could resolve E3 and extend the scale claim in one motion,
   but the antivirus-interaction confound already documented makes clean
   attribution hard). Do you want this scoped into the current
   submission cycle, or explicitly deferred to future work as it is now?
4. **Broader real-model corpus:** how much time do you want spent
   exploring what fraction of MSL actually compiles cleanly through Rumoca
   before committing to specific new real models? This is genuinely
   **UNVERIFIED** territory (Rumoca's MSL coverage beyond what's already
   been tried is unknown) and could turn into unplanned exploratory time.
5. **Venue:** `docs/venue.md` records EOOLT as the researched target but
   notes its 2026 deadline already passed and the paper is currently
   written in IEEE format as an explicit placeholder pending your
   decision. Is there now a specific journal in mind (which would fix the
   page budget, related-work expectations, and formatting target for
   Phase 4), or should this plan continue to assume a generic
   Modelica/simulation-systems journal audience?
6. **Scope ambition:** Section 10 offered four directions that are not
   mutually exclusive. Do you want this developed as (a) a modestly
   broadened version of the current paper (Phases 0-2 only, fastest path
   to submission), or (b) a more ambitious rework centered on Direction 2
   (baseline-driven) or Direction 3 (systems-engineering-driven)? This is
   the single biggest lever on total time investment.

No code, paper, or experiment changes have been made. This document is the
complete output of the requested inspection and planning pass.
