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

## Progress

| Phase | State | Commit / file |
|---|---|---|
| 0 checklist | done | docs/journal_upgrade/phase0_checklist.md |
| 1 N=5,000 diagnosis | done | 0c58548, 28c53b4, 9d98afe; phase1_scaling_diagnosis.md |
| 2 oracle verification | done | d9412bb; phase2_oracle_verification.md |
| 3 RC ladder / BridgedStar | graph done; timing PENDING | 42e964e, 1ae7909 |
| 4 locality | graph done; signal-chain timing PENDING | 66a068c; phase4_locality.md |
| 5 states ablation | done | 79d9990, 98c82d7; phase5_state_ablation.md |
| 6 link ablation | RUNNING (logs/link_ablation.log) | results/journal_upgrade/link_ablation_parallel/ |
| 7 stats audit | existing data done; rerun on new data PENDING | 5ef238b |
| 8/9 final plan | draft committed, PENDING sections | 301b770; final_paper_plan.md |
| OVERNIGHT_REPORT.md | not started | |

## Queue (strictly in order)

1. Finish link ablation (N=1000: dynamic_stripped, static, dynamic_unstripped).
2. Rerun suspend-flagged link cells once each: N=100 dynamic_stripped, N=500
   dynamic_unstripped (`python -u src/journal_link_ablation.py` needs a small wrapper to
   run single configs; append rows marked rerun, keep originals).
3. `python -u src/journal_extra_timing.py` (SignalChain500 stages 1/250/500, BridgedStar250,
   RcLadder1000), then suspend-check it.
4. Stats over new data (src/journal_stats_audit.py, src/journal_parallel_analysis.py after
   validating it), phase6_link_ablation.md, fill PENDING sections, OVERNIGHT_REPORT.md,
   commit, push.
