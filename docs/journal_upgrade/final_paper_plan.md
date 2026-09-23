# Journal paper upgrade plan (based only on results obtained)

Status: sections marked PENDING depend on timing runs still in progress (link ablation,
signal-chain / BridgedStar / RC timing) and contain no numbers yet. Everything else
cites a committed result. `paper/main.tex` has not been modified.

Evidence base: `phase1_scaling_diagnosis.md`, `phase2_oracle_verification.md`,
`phase4_locality.md`, `phase5_state_ablation.md`, `statistical_audit_existing.md`,
RC ladder / BridgedStar validation (`results/journal_upgrade/rc_ladder_parallel/`,
`bridged_star_sets.csv`), link ablation (PENDING), extra timing (PENDING).

## 1. Revised research question

Old (implicit): can matching-based impact analysis make incremental recompilation of
Modelica models fast and correct?

Revised: **what does it take to make equation-based (Modelica) models incrementally
rebuildable, and which parts of that pipeline carry the benefit?** Three separable
parts, each with its own evidence:
1. a unit partition derived from an equation-to-variable matching (with states as
   knowns), which turns an acausal model into independently compilable units;
2. a build system that caches per-unit artifacts and loads them at run time;
3. a change-impact analysis over the matched graph, which identifies which units'
   VALUES an edit can affect (semantic impact), distinct from which units' CODE must be
   recompiled (the generated-source diff).

## 2. Revised contributions

1. Matching-derived recompilation units for acausal equation-based models, with the
   states-as-knowns requirement quantified by ablation (naive treatment collapses every
   generated chain into one whole-model unit, disagrees with the compiler's own block
   structure on 10/16 models, and cannot be code-generated). Presented as a necessary
   methodological requirement, not a novelty (standard causalization practice).
2. An incremental build over those units that is bit-identical to a full rebuild on
   every measured cell (original sweeps plus 33 Phase 2 strategy-cell builds plus all new
   cells), with speedup growing with model size in steady state (5.25x to 25.21x from 149
   to 2,999 equations in Phase 2; about 39x at 14,999 equations in steady state, Phase 1).
3. A separation of semantic impact from recompilation scope, with evidence: reachability
   is sound but conservative for recompilation (source diff recompiled 78% fewer units on
   the MSL cells and was faster on 3 of 4, bit-identical on 11/11 cells); reachability's
   scope is the edited equation's forward algebraic cone (1,070 edit positions, six
   pre-stated predictions all confirmed); the matching's dependency direction beats a
   direction-agnostic closure exactly where long algebraic chains exist (4/4 MSL cells;
   signal chain 126 vs 250 units mid-chain), and ties elsewhere.
4. Measured characterization of what limits incremental builds at scale: the per-unit
   file materialization of the build (linear copy cost, plus a first-touch filesystem/I/O
   overhead of about 25-30 ms per file on this host that dominated the one anomalous
   N=5,000 measurement), and the link strategy's contribution (PENDING, link ablation).
5. A break-even change frequency (existing result; keep, with the harness caveat).

Removed or demoted: "resolve impact by reachability, then recompile the predicted units"
as the recompilation mechanism (Phase 2); the states-as-knowns fix as a stand-alone
contribution (Phase 5).

## 3. Experiments to include in the paper

| Experiment | Where | Status |
|---|---|---|
| Real MSL speedup and ripple (existing Table III), refreshed by Phase 2 paper-method numbers | Results | done |
| Three-strategy comparison (paper / matching-free baseline / source diff), 11 cells, bit-identical, timing with CIs | Results, new section | done |
| Speedup vs size (existing Table IV) plus the N=5,000 steady-state point and first-touch cost | Results | done |
| Locality: scope vs edit position, four model families, with predictions | Results, new section | done (graph); timing PENDING |
| States-as-knowns ablation | Methodology, short | done |
| Link-strategy ablation (static vs dynamic, stripped vs not, both baselines) | Results | PENDING |
| Topology generality: BridgedStar (coupled blocks, star) | Results, short | graph done; timing PENDING |
| Break-even (existing) | Results | existing, keep with caveat |

Supplementary or internal only: RC ladder (structurally redundant with the thermal chain;
one confirmation build PENDING), stage-by-stage profiles below N=5,000, the stats audit's
full mismatch list, the Phase 1 setup-hashing observation, determinism audits.

## 4. Claims that must be weakened or corrected

- Abstract MSL speedup range "1.09x-2.27x": wrong (2.27 is a generated model; current data
  1.19x-1.81x, Phase 2 1.17x-1.93x for the paper method). Correct it.
- "Resolves a change's impact by graph reachability" as the way to decide recompilation:
  reframe as semantic impact; recompilation scope via content (source diff), or justify.
- Thermal-chain scaling as evidence for matching: attribute to the build system; a
  matching-free closure selects the same units there.
- "Changes are local": replace with the structural statement (scope = forward algebraic
  cone bounded by states), including the counterexample (signal-chain head edit = full
  rebuild under reachability).
- Speedup ratios: report absolute incremental times and both baselines; the dynamic-link
  full rebuild used as the denominator is slower than the static one (stats audit: about
  17.8x vs 27.0x at N=1,000 against the static baseline). Final wording PENDING link ablation.
- "Under about 9%" spread (actual 10.4% at N=250), "roughly threefold" per-step plateau
  (actually about 16x), overhead "non-trending" (rises 1.32%-1.66%), "two real circuits"
  (three real models): fix each (stats audit list).
- The N=5,000 anomaly: replace "unexplained" with the first-touch diagnosis, stated as a
  demonstrated filesystem/I/O overhead with antivirus scanning as a likely contributor,
  not a proven cause.

## 5. Claims that can now be strengthened

- Correctness: bit-identical on every build in this upgrade, including the source-diff
  builds, with a guard proving the built set equals an independently computed diff.
- Scale: steady-state incremental rebuild at 14,999 equations is about 17 s (n=4 warm
  repeats), continuing the growing-speedup trend; the old "3.3x, unexplained" point is
  explained.
- Matching's value: now demonstrated against a real baseline, and located precisely
  (long algebraic chains), rather than asserted.
- Locality: characterized over 1,070 positions with confirmed predictions.

## 6. Figures and tables to add

- Table: three-strategy comparison (units recompiled, incremental time with 95% CI,
  speedup with Fieller CI, bit-identical flag) for the 11 Phase 2 cells.
- Figure: affected units vs relative edit position (`figures/journal_locality_ripple`),
  plus source-diff line (constant 1) for the signal chain.
- Table: N=5,000 first-touch experiment (W / F / FW conditions).
- Figure or table: link ablation, absolute full and incremental times for three configs
  across sizes (PENDING).
- Small table: states-as-knowns ablation (units, largest unit, ripple, codegen outcome).

## 7. Sections to expand, condense, remove

- Expand Methodology: separate "unit partition", "build system", "impact analysis";
  pseudocode for matching, SCC partition, reachability, source diff.
- New Results subsections: baselines; locality; link ablation; first-touch cost.
- Condense: the narrative of bug fixes (quadratic codegen can stay as a short
  engineering note; the networkx non-determinism finding can move to a threats/notes box).
- Remove: claims that rely on the superseded static-link numbers without both baselines.

## 8. Revised limitations

Index-1 only (Cauer filter needs index reduction); linear coupled blocks only; no
discrete/event code generation; change detection out of scope (seeds come from the
injector); single machine, single OS, single toolchain, laptop on the Balanced power plan
with on-access antivirus scanning; the per-rebuild file materialization and first-touch
cost at large N; real-model corpus of three MSL models plus generated families; timing
n = 3-5 per condition; the source diff's safety depends on hashing all compilation inputs
(unit source, shared header, flags) and on the driver always being rebuilt.

## 9. Threats to validity (new section)

Internal: timing noise on small models (process-spawn floor about 0.8 s); run-position
effects at large N (first-touch cost leaking past one warm-up); host suspend events
(three occurred during this upgrade; every timed cell is checked against the Windows
event log, affected cells are rerun and both rows kept); power state (timed cells gated
on AC power). Construct: bit-identical stdout on one simulation trace per cell as the
correctness criterion. External: one compiler front end (Rumoca 0.9.20), one C toolchain,
Windows only; generated models are assignment-form, while real MSL models are
connect-generated; conclusions about matching's value depend on that structural property.

## 10. Statistical reporting changes

Per condition: n, mean, median, sd, CV, 95% t-CI, min/max, and raw values in the
repository; Fieller 95% intervals for speedups; pre-registered win/tie rule for strategy
comparisons with the calibration result (1/12 identical-work pairs flagged); both
"first repeat discarded" and "all repeats" statistics; no outlier removal; deterministic
metrics (unit counts, ripple, flags) reported without intervals.

## 11. Related-work gaps

Content-hashing build systems (Make, Bazel, ccache-style caching) as the natural
comparison for the source-diff finding; incremental/separate compilation in equation-based
languages (e.g. Modelica separate compilation, FMI-based modular approaches); BLT
causalization treating states as knowns (textbook material to cite for the Phase 5
point). Citations must be verified before use.

## 12. Reproducibility material

Every result file is in `results/` with the producing script; the phase reports cite
commands and commits; a single `REPRODUCE.md` listing environment (Rumoca 0.9.20,
Python 3.11.9, GCC 15.2, Windows build, power plan, antivirus state), the MSL sparse
clone commands, and one command per experiment is still to be written; per-cell machine
state and suspend checks are stored with the new timing data.
