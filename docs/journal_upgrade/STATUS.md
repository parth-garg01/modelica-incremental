# Overnight run status (read this first when resuming)

Task spec: the user's overnight journal-upgrade prompt (Phases 0-9 plus
OVERNIGHT_REPORT.md). Standing user instructions for this run:
- Target about 32 meaningful commits total, as user parth-garg01 /
  parth.garg2024@vitstudent.ac.in, with NO Claude co-author trailer.
- Never modify or delete existing results files; new results go to new files.
- Run gcc/timing experiments via PowerShell, one at a time (never two heavy
  builds at once; parallel runs corrupt timing).
- No em dashes anywhere.
- Do not touch paper/main.tex until the final paper plan exists.

## Progress

| Phase | State | Notes |
|---|---|---|
| 0 checklist | done | docs/journal_upgrade/phase0_checklist.md |
| 1 N=5,000 diagnosis | running | src/journal_profile_scale.py; N=50, N=1000 done in results/journal_upgrade_phase1_profile.csv; N=2000+5000 running, log in logs/phase1_profile_2000_5000.log |
| 2 naive baseline | agent drafting (graph-level only) | timing runs pending, must be serial |
| 3 RC ladder | agent validating (graph-level only) | timing runs pending |
| 4 locality | agent computing ripple sweep (graph-level only) | timing at sampled positions pending |
| 5 state ablation | agent | |
| 6 link ablation | not started | needs serial timing runs |
| 7 stats audit | agent (existing CSVs) | rerun on new CSVs at the end |
| 8 reassess | not started | |
| 9 paper plan + OVERNIGHT_REPORT.md | not started | |

## Early finding (Phase 1)

Copy-cached-DLLs share of one incremental rebuild: 10% at N=50, 63% at
N=1000 (3.53s of 5.62s). Consistent with the ledger's hypothesis that the
O(N) per-rebuild copy dominates at large N. Awaiting N=2000/5000.
