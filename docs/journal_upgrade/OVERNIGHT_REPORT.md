# Journal-upgrade run: final report

Run window: first journal commit 2026-09-22 23:12 IST, last experiment 2026-09-23 16:43 IST (see Section 18 for the commit trail).
`paper/main.tex` was not modified. Every number below is cited to a committed result
file; nothing is projected.

## 1. Executive summary

The evidence now supports a clearer, narrower, better-defended contribution than the
current paper states, not a bigger one.

- What holds and is strengthened: incremental rebuilding over matching-derived units is
  bit-identical to a full rebuild on every correctness check in this run (70 of 70:
  Phase 1 10, Phase 2 33, link ablation 12, extra timing 15; excluding smoke tests), and its speedup grows with model size in steady state
  (22.2x at 2,999 equations this session; about 39x at 14,999 equations in steady
  state). The paper's one unexplained data point (3.3x at 14,999 equations) is explained:
  a first-touch filesystem/I/O overhead, not a scaling regime change.
- What must be narrowed: (a) graph reachability is a sound but conservative way to
  choose what to recompile; a generated-source diff recompiled 78% fewer units on the
  real MSL cells, was bit-identical on every cell, and was faster on 3 of 4; (b) the
  thermal-chain scaling results are evidence for the build system, not for matching-based
  impact analysis (a matching-free baseline selects the same units there); (c) about half
  of the headline dynamic-link speedup comes from the dynamic build's slower full rebuild
  (against the static full rebuild: 11.0x, not 22.2x, at N=1000); (d) "changes are local"
  is true only where states cut algebraic chains.
- What is new and supported: the matching's dependency direction beats a
  direction-agnostic closure exactly on models with long algebraic dependency chains
  (all 4 real MSL cells; signal chain 126 vs 250 units mid-chain) and ties elsewhere;
  reachability scope is the edited equation's forward algebraic cone (1,070 positions, six
  pre-stated predictions confirmed); static linking provably caps speedup (controlled
  same-session ablation); states-as-knowns is required (naive treatment collapses every
  chain into one whole-model unit and cannot be code-generated), though it is standard
  practice, not a novelty.

Judgement: the upgrade succeeded in making the contribution defensible and its limits
precise. It did not make the original central claim stronger as stated; it relocated the
contribution to the unit partition and build system, with reachability reframed as
semantic impact analysis.

## 2. Experiments completed

| Phase | Experiment | Result file(s) | Report |
|---|---|---|---|
| 1 | Stage profile N=50-5,000; first-touch discriminating experiment (W/F/FW) | `results/journal_upgrade_phase1_profile.csv`, `..._phase1_firsttouch.csv` | `phase1_scaling_diagnosis.md` |
| 2 | Independent source-diff verification; three-strategy builds on 11 cells | `results/journal_upgrade_phase2_*` | `phase2_oracle_verification.md` |
| 3 | RC ladder and BridgedStar validation; three-strategy sets on BridgedStar | `results/journal_upgrade/rc_ladder_parallel/`, `bridged_star_sets.csv` | this report, Sec. 6 |
| 4 | Locality sweep (1,070 positions) and per-position source diff | `results/journal_upgrade/locality_parallel/` | `phase4_locality.md` |
| 5 | States-as-knowns ablation | `results/journal_upgrade/states_ablation_parallel/` | `phase5_state_ablation.md` |
| 6 | Link-strategy ablation with suspend-checked reruns | `results/journal_upgrade/link_ablation_parallel/` | `phase6_link_ablation.md` |
| 7 | Statistical/provenance audit of existing data; stats on new data | `results/journal_upgrade_stats_existing.csv`, `parallel_analysis/tables.md` | `statistical_audit_existing.md` |
| extra | Signal-chain / BridgedStar / RC timing, three strategies | `results/journal_upgrade/extra_timing/` | `phase4_locality.md` Sec. 6; this report Sec. 6-7 |

## 3. Experiments that failed or were changed, and why

- Parallel analysis agents (five, then one "parallel worker"): three stopped on the
  user's instruction to pause Phase 3+ during Phase 2 verification; the worker stopped on
  an account usage limit. Their unfinished code was reviewed, fixed where needed (probe
  outputs not persisted; stale output paths; duplicate data), rerun, and verified against
  their drafts (identical on every deterministic metric) before use.
- RC ladder full timing sweep: skipped by decision; graph-level validation showed it is
  structurally the same as the thermal chain after causalization. One confirmation build
  kept: RcLadder1000 bit-identical, 24.25x for the paper method.
- Thermal-chain locality timing: skipped by decision; scope is constant (2 units) at all
  positions, so timing more positions would only measure noise.
- Link-ablation cells contaminated by power-button standby / hibernate (3 cells): excluded
  and rerun once each; originals kept.
- Decision to stop experimenting (Phase 8): after the extra timing cells, no remaining
  experiment would change a conclusion at reasonable cost. Making source-diff selection the
  pipeline's actual mechanism is engineering, not new evidence (the source diff was already
  built and verified on every strategy cell where it applied), so it is a recommendation
  (Section 20), not an experiment run here.
- Unattended-resume watchdog: written and tested, but not launched; the auto-mode safety
  classifier blocked starting a process that spawns unattended sessions, so that is the
  user's decision.

## 4. N=5,000 / 14,999-equation diagnosis

Reproduced (first incremental rebuild 181.8 s vs original 203.1 s; measured parts sum to
24.5 s). Discriminating experiment: consecutive rebuilds 396.6 s then 16.2-19.5 s; rebuilds
from a fresh copy 412-468 s; after a 10-minute idle wait still 392-397 s. Demonstrated:
a per-file first-touch filesystem/I/O overhead (about 25-30 ms per file), paid
synchronously, independent of compilation. Steady-state speedup about 39x against the
original full rebuild, continuing the trend. Antivirus on-access scanning is a likely
contributing mechanism, not an established cause. Classification: host-environment effect
interacting with a design property (one new DLL per unit per rebuild). Confidence: high on
first-touch cost, moderate on antivirus contribution, low on the exact trigger.

## 5. Baseline results (Phase 2)

Matching-free baseline = undirected incidence closure from the seeds, states as knowns
(strongest sound closure without a matching), mapped onto the same units and codegen.
Paper method beats it on 4/4 real MSL cells (18-42% less incremental time; baseline
recompiles every unit there) and on ThermalNetwork sensor-add; ties on the other fixtures
and on all thermal chains (identical unit sets). 33/33 builds bit-identical. Source diff:
recompiles 7 units vs the paper method's 32 across the MSL cells, faster on 3/4, tie on 1;
bit-identical on 11/11 cells, with a guard proving the built set equals an independently
computed diff.

## 6. RC ladder results

RcLadder N=10-1000: 2N+1 equations, fully matched, all-singleton units equal to Rumoca's
block count, sin(time) emitted and driven correctly, every edit sound with a constant 2
(resistance swap) or 1 (probe) affected units at any position and size. Redundant with the
thermal chain as topology evidence. BridgedStar (star, N genuine 5-equation coupled
blocks): partition equals Rumoca's count; edits sound with 3 affected units at any branch;
paper 3, baseline 3, source diff 1 at every size. Builds: RcLadder1000 (2,001 units)
bit-identical, sin(time) confirmed at build level, paper method 24.25x [23.24, 25.34];
BridgedStar250 (250 coupled 5-blocks) bit-identical, three-way tie at about 13x (paper
13.06x, baseline 13.44x, source diff 13.65x).

## 7. Locality results

Scope = forward algebraic cone of the edited equation, cut at the next state: constant 2
(room loss) or 3 (exchange) units on thermal chains at every position and size; exactly
N-k+1 on the signal chain; 5 (then 5-j+1) on sensor pipelines behind a state. Every one of
1,070 positions sound, structure unchanged, all six pre-stated predictions confirmed. Per
position, baseline selects the whole signal chain (250) everywhere; source diff is 1 unit
everywhere. Timing (SignalChain500, three strategies, all bit-identical): paper method
1.15x / 1.92x / 14.16x at stages 1 / 250 / 500 (build time follows the 500 / 251 / 1 units
selected); baseline about 1.0x at every stage; source diff 13.5x-16.9x at every stage.
Under reachability, recompilation cost is local only where states cut algebraic chains.

## 8. State-aware dependency results

State-aware partition equals Rumoca's block count on 16/16 models; naive (states as edge
sources) disagrees on 10/16, collapses every thermal chain into a single whole-model unit
(100% ripple at every size), and produces units the code generator cannot emit. Both
sound. Standard causalization practice: present as a required methodological choice with
ablation evidence, not a contribution.

## 9. Link-strategy ablation results

Static relink grows linearly (median 0.99, 9.76, 22.73 s at N=100/500/1000) and speedup
falls 3.10x, 2.30x, 1.98x: a scaling ceiling. Dynamic stripped: link step about 0.09 s at
every N, speedup 9.79x, 18.15x, 22.23x [19.01, 26.71]. Dynamic full rebuild costs about 2x
the static one; against the static full rebuild the gain is 3.9x, 9.4x, 11.0x. Unstripped
DLLs: erratic incremental rebuilds at N>=500 (CV about 100%) with no suspend event. Paper
Table IV reproduces in trend; values 10-20% lower this session.

## 10. Statistical analysis

No committed pre-existing results file stored raw repeats; several key numbers were n=1.
New data: all raw repeats stored; per condition n, mean, median, sd, CV, 95% t-CI,
min/max; Fieller intervals for speedups; pre-registered win/tie rule with calibration (1 of
12 identical-work pairs flagged, consistent with a 5% rule); repeated measurements of one
configuration are treated as measurement noise, not independent populations. Every timed
cell checked against the Windows suspend log. Paper-vs-data mismatches found by the audit
are listed in `statistical_audit_existing.md` and Section 12.

## 11. Existing claims that are now stronger

Bit-identical correctness (now including source-diff builds); growing speedup with size
(now controlled against static linking, and explained at 14,999 equations); matching's
value (now shown against a real baseline and located structurally); locality (now
characterized with predictions); break-even and codegen-bug results unchanged.

## 12. Existing claims that must be weakened or corrected

Reachability as the recompilation mechanism; thermal-chain scaling as evidence for
matching; the same-config speedup ratio as the headline without the static baseline;
"changes are local" without the structural condition; abstract MSL range "1.09x-2.27x"
(data: 1.19x-1.81x; 2.27 was a generated model); "under about 9%" spread (10.4%);
"roughly threefold" step plateau (about 16x); overhead "non-trending" (rises 1.32-1.66%);
"two real circuits" (three real models); "3.3x, unexplained" (now explained).

## 13. New scientifically supported findings

1. Semantic impact (reachability) and recompilation scope (source diff) are different sets;
   the latter was sufficient for bit-identical builds on every tested cell.
2. Matching's direction advantage appears exactly where long algebraic chains exist.
3. Reachability scope is the forward algebraic cone bounded by states.
4. Static linking caps incremental speedup; dynamic linking removes the cap at the price of
   a ~2x slower full rebuild.
5. At large N the dominant remaining costs are per-unit file materialization and a
   first-touch filesystem/I/O overhead, which can make the first rebuild after idle cost
   more than half a full rebuild.

## 14. Remaining limitations

Index-1 only; linear coupled blocks only; no events; change detection out of scope; one
machine, OS, toolchain and front end; laptop host with on-access antivirus and user
interaction (suspend events); three real MSL models; n=3-5 repeats; source diff's safety
depends on hashing all compilation inputs and always rebuilding the driver; the per-rebuild
copy of cached DLLs remains O(N).

## 15. Recommended journal paper structure

See `final_paper_plan.md`: Introduction (revised question); Background and related work
(adds content-hash build systems, separate compilation in equation-based languages);
Methodology (unit partition with states-as-knowns; build system; impact analysis vs
recompile scope); Experimental setup (host, power, suspend checks, statistics policy);
Results (correctness; three-strategy comparison; locality; scaling with link ablation and
first-touch cost; break-even); Threats to validity; Limitations; Conclusion.

## 16. Recommended figures and tables

Three-strategy table (11 cells); locality figure (`figures/journal_locality_ripple`) with
source-diff line; first-touch W/F/FW table; link-ablation figure (absolute full and
incremental times, three configs, three sizes); states-ablation table; signal-chain
timing vs units recompiled (three strategies, stages 1/250/500).

## 17. Exact files changed

New code (src/): journal_profile_scale.py, journal_phase1_firsttouch.py,
journal_naive_resolver.py, journal_baseline_compare.py, journal_phase2_verify_oracle.py,
journal_phase2_analyze.py, journal_stats_audit.py, journal_state_ablation.py,
journal_generators.py, journal_rc_changes.py, journal_phase3_validate.py,
journal_bridged_star_sets.py, journal_locality.py, journal_locality_sourcediff.py,
journal_figures_locality.py, journal_parallel_timing.py, journal_link_ablation.py,
journal_link_rerun.py, journal_suspend_check.py, journal_parallel_analysis.py,
journal_extra_timing.py. Tests: test_journal_naive_resolver.py (42), test_journal_rc_ladder.py (7).
Removed before commit: src/journal_parallel_runs.py (a stopped worker's draft, superseded
by journal_extra_timing.py, never committed). Scripts: scripts/watchdog.ps1, scripts/register_2am_resume.ps1. Docs: docs/journal-plan.md,
docs/journal_upgrade/*.md, docs/journal_upgrade/parallel_analysis/tables.md. Results: only
new files under results/ (no existing results file modified). Figures:
figures/journal_locality_ripple.{svg,pdf}. .gitignore: build caches, generated models,
logs, the report template. Not modified: paper/main.tex, any pre-existing src/, tests/,
results/ or figures/ file.

## 18. Git commits created

All as parth-garg01 <parth.garg2024@vitstudent.ac.in>, no AI attribution (three early
commits had a Claude trailer removed by a local, tree-preserving rewrite before any push;
backup branch `backup/pre-trailer-fix` kept locally). In order (b4b7e08..HEAD):
d7bd0f7, 0e01690, 1e8d6db, a0e1305, edf2f76, 5ef238b, f2c8a64, 8c106d1, d9412bb,
0c58548, 28c53b4, 79d9990, 42e964e, 1ae7909, 753d614, 98c82d7, 66a068c, 9d98afe,
6fb14b1, 301b770, 4eb3f5a, de8616e, 577b497, 913a9f9, bfc5ff3, b7722f7, c195cb2, then
the commits adding REPRODUCE.md and this report (see `git log`).

## 19. Experiments that should NOT be in the paper

The RC ladder sweep (redundant); the thermal-chain locality timing (constant scope); the
states-ablation semantic probe (tests a reading the toggle does not implement); single
unrepeated cells (validate_scale N=2,000/5,000 speedups; profile end-to-end numbers) except
as diagnosis; the unstripped DLL numbers as a design alternative (a reconstruction, only
useful to show why stripping matters); anything measured during a flagged suspend window.

## 20. What remains before journal submission

1. Decide the framing (Section 1): unit partition + build system as the contribution,
   reachability as semantic impact, content-based recompilation.
2. Optionally implement content-based recompile selection as the pipeline's actual
   mechanism (small: the source diff already exists) and re-run the Phase 2 table under it.
3. Rewrite paper/main.tex per `final_paper_plan.md`; fix every mismatch in Section 12.
4. Add REPRODUCE.md; archive the repository with a DOI.
5. Optional, higher cost: remove per-rebuild DLL copying (persistent build directory) and
   re-measure first-touch and large-N scaling; a second host without on-access scanning to
   test the antivirus contribution; more real MSL models with long algebraic chains.
6. Verify every new citation before use.
