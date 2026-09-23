# Journal-upgrade run status (read this first when resuming)

Standing rules:
- Commits as parth-garg01 / parth.garg2024@vitstudent.ac.in, NO Claude co-author
  trailer, path-limited (`git commit --only <paths>`), in meaningful units; push
  completed work to origin/master (fast-forward only, never force).
- Never modify existing results files; new results go to new files.
- Timing experiments run one at a time, alone, on AC power (the harness waits for AC).
  Never run the full pytest suite (tests/test_measure_msl.py overwrites
  results/measurements_msl.*).
- gcc-invoking Python via PowerShell, not Git Bash.
- No em dashes. Do not modify paper/main.tex until the final paper plan is complete.
- The Phase 1 mechanism is "first-touch filesystem/I/O overhead"; antivirus scanning is
  only a likely contributor, never stated as the cause.
- Keep the laptop awake: power-button and lid events put it into Modern Standby, and it
  hibernates after 15 minutes of standby. Check every timed cell with
  src/journal_suspend_check.py; rerun flagged cells once, keep both rows.

## Pre-registered timing policy

1 first rebuild + 5 timed repeats per condition, raw times stored, statistics with and
without the first; full/incremental interleaved (link ablation) or the Phase 2
run_cell_strategies flow (strategy comparisons, rotated order); 95% t-CI, Fieller for
speedups; pre-registered win/tie rule (Welch CI excludes 0); no adaptive re-running,
no outlier removal.

## Progress: RUN COMPLETE (2026-09-23 16:45 IST)

All phases done and committed; experimentation deliberately stopped (Phase 8 decision in
OVERNIGHT_REPORT.md Section 3). Do not rerun anything on resume.

| Deliverable | File |
|---|---|
| Phase reports | phase0_checklist.md, phase1_scaling_diagnosis.md, phase2_oracle_verification.md, phase4_locality.md, phase5_state_ablation.md, phase6_link_ablation.md, statistical_audit_existing.md |
| Paper upgrade plan | final_paper_plan.md |
| Final report | OVERNIGHT_REPORT.md |
| Reproduction | REPRODUCE.md |

Next step belongs to the user: decide the paper framing (OVERNIGHT_REPORT.md Section 20),
then rewrite paper/main.tex per final_paper_plan.md.