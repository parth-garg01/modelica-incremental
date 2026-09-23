# Reproducing the journal-upgrade experiments

## Environment (as measured, 2026-09-23)

- Windows 11, build 26200 (`platform`: Windows-10-10.0.26200-SP0), AMD64, 12-thread Ryzen
  laptop, Balanced power plan, on AC power for every timed cell.
- Windows Defender real-time/on-access protection enabled (relevant to Phase 1).
- Python 3.11.9 in `.venv` (`pip install -r requirements.txt`), Rumoca 0.9.20
  (`rumoca.version()`).
- GCC 15.2.0 (MSYS2 Rev13) at `C:\msys64\mingw64\bin\gcc.exe`.
- Run every gcc-invoking script from PowerShell, not Git Bash: Git Bash's PATH makes
  gcc's `cc1.exe` load mismatched DLLs and fail silently.
- Keep the machine awake: a power-button or lid event enters Modern Standby, and this
  plan hibernates after 15 minutes of standby. Check each timed run with
  `src/journal_suspend_check.py` (or the Kernel-Power events for the run window).
- Do not run the full pytest suite before a measurement you want to keep:
  `tests/test_measure_msl.py` overwrites `results/measurements_msl.*`.

## Modelica Standard Library (sparse clone, not committed)

```
git clone --depth 1 --filter=blob:none --sparse https://github.com/modelica/ModelicaStandardLibrary.git msl_src
cd msl_src
git sparse-checkout set Modelica/Blocks/Continuous Modelica/Blocks/Interfaces Modelica/Blocks/Sources Modelica/Blocks/Types.mo Modelica/Electrical/Analog/Basic Modelica/Electrical/Analog/Examples Modelica/Electrical/Analog/Icons Modelica/Electrical/Analog/Interfaces Modelica/Electrical/Analog/Sources Modelica/Math/Random Modelica/Thermal/HeatTransfer ModelicaServices
```

Measured against MSL commit b756f9d (2026-04-27). A later MSL revision may change
generated equations.

## Commands (repo root, PowerShell, `$env:PYTHONPATH="src"`, `.\.venv\Scripts\python.exe -u ...`)

| Phase | Command | Output | Approx. time |
|---|---|---|---|
| 1 profile | `src\journal_profile_scale.py 50 1000 2000 5000` | `results/journal_upgrade_phase1_profile.csv` | ~1.5 h |
| 1 first-touch | `src\journal_phase1_firsttouch.py` (needs the N=5000 cache from the profile run) | `results/journal_upgrade_phase1_firsttouch.csv` | ~3 h |
| 2 source diff | `src\journal_phase2_verify_oracle.py` | `results/journal_upgrade_phase2_oracle_independent.{csv,json}` | ~5 min |
| 2 builds | `src\journal_baseline_compare.py --smoke`, then without flags | `results/journal_upgrade_phase2_timing.csv` | ~50 min |
| 2 stats | `src\journal_phase2_analyze.py` | `..._phase2_timing_stats.csv`, `..._phase2_pairwise.csv` | seconds |
| 3 validation | `src\journal_phase3_validate.py`; `src\journal_bridged_star_sets.py` | `results/journal_upgrade/rc_ladder_parallel/`, `bridged_star_sets.csv` | ~10 min |
| 4 locality | `src\journal_locality.py`; `src\journal_locality_sourcediff.py`; `src\journal_figures_locality.py` | `results/journal_upgrade/locality_parallel/`, `figures/journal_locality_ripple.*` | ~25 min |
| 5 states | `src\journal_state_ablation.py` | `results/journal_upgrade/states_ablation_parallel/` | ~10 min |
| 6 link | `src\journal_link_ablation.py 10 --smoke`, then `src\journal_link_ablation.py 100 500 1000`; reruns of suspend-flagged cells with `src\journal_link_rerun.py N:config` | `results/journal_upgrade/link_ablation_parallel/` | ~3 h |
| 6 checks/stats | `src\journal_suspend_check.py <csv>`; `src\journal_parallel_analysis.py` | `*_suspend_check.csv`, `docs/journal_upgrade/parallel_analysis/tables.md` | seconds |
| extra timing | `src\journal_extra_timing.py`; `src\journal_phase2_analyze.py results\journal_upgrade\extra_timing\extra_timing.csv results\journal_upgrade\extra_timing\extra` | `results/journal_upgrade/extra_timing/` | ~50 min |
| stats audit | `src\journal_stats_audit.py --selftest`; CLI on any results CSV | `results/journal_upgrade_stats_existing.csv` | seconds |

Graph-level tests (no builds): `python -m pytest tests\test_journal_naive_resolver.py tests\test_journal_rc_ladder.py`.

Deterministic outputs (unit counts, ripple, source-diff sets, figures) should reproduce
exactly; wall-clock timings will not. Expect run-to-run differences of 10-20% between
sessions, and occasional large first-touch outliers at N >= 500 with dynamic linking.
