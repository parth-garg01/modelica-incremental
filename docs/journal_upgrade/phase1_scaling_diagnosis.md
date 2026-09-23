# Phase 1: diagnosis of the N=5,000 / 14,999-equation speedup anomaly

## 1. Original result

`results/measurements_validate_scale.csv` (produced by `src/validate_scale.py 2000 5000`,
which calls `measure_msl.run_cell(..., repeats=1)`): generated `ThermalChain5000`
(14,999 equations, 14,999 units), change = `swap_room_conductance` at room 2,500
(seed `Q2500env`), dynamic-link stripped-DLL build, Rumoca 0.9.20, Python 3.11.9,
MinGW-w64 GCC 15.2, one untimed warm-up then ONE timed full and ONE timed
incremental rebuild. Full 675.5 s, incremental 203.1 s, speedup 3.33x, bit-identical.
The same run at N=2,000 gave 30.53x, and the repeated sweep gave 27.01x at N=1,000, so
3.33x breaks the trend. Git revision of that run: the commit that added the file
(`git log --follow results/measurements_validate_scale.csv`); no provenance was
recorded at measurement time (see `statistical_audit_existing.md`).

In that `run_cell` call, before the timed incremental rebuild, the process had built
the baseline cache (15k new DLLs), then three full rebuilds (45k new DLLs), then a
warm-up incremental rebuild (15k new files).

## 2. Stage-by-stage profile (`src/journal_profile_scale.py`, `results/journal_upgrade_phase1_profile.csv`)

Same model family, same change (middle room), same dynamic-link build. One
end-to-end `incremental_rebuild_dynamic()` call, then its stages timed separately
(copy loop 3 times) and summed as a cross-check.

| N rooms (eqs) | End-to-end incr (s) | Recompile 2 DLLs | Copy cached DLLs (mean of 3) | Driver compile + link | Sum of parts | Copy share |
|---|---|---|---|---|---|---|
| 50 (149) | 1.00 | 0.14 | 0.10 | 0.70 | 0.94 | 10% |
| 1,000 (2,999) | 5.62 | 0.17 | 3.53 +/- 0.32 | 1.57 | 5.27 | 63% |
| 2,000 (5,999) | 10.02 | 0.17 | 6.86 +/- 0.27 | 2.29 | 9.33 | 68% |
| 5,000 (14,999) | **181.84** | 0.22 | 18.31 +/- 4.41 (22.9, 18.0, 14.1) | 5.96 | **24.48** | 10% |

- Up to N=2,000 the parts sum to within 7% of the end-to-end time. The copy loop
  scales linearly at about 1.15 ms per file and dominates; driver compile also
  grows linearly (the dynamic driver has one load/lookup per unit).
- At N=5,000 the end-to-end call (the FIRST incremental rebuild reading a cache
  written minutes earlier) took 181.8 s, while the same stages timed immediately
  afterwards summed to 24.5 s: 157 s unaccounted for. The anomaly reproduced
  (181.8 s vs the original 203.1 s).

## 3. Discriminating experiment (`src/journal_phase1_firsttouch.py`, `results/journal_upgrade_phase1_firsttouch.csv`)

Run 2026-09-23 02:01 to 05:13 IST, alone on the machine, against the same
14,999-DLL cache. Conditions fixed in advance. Windows Defender real-time and
on-access protection confirmed enabled (`Get-MpComputerStatus`). Defender CPU
(MsMpEng % Processor Time) sampled once per second during each timed rebuild.

| Condition | Rebuild times (s) | Defender CPU mean (% of one core) |
|---|---|---|
| W: existing cache, 5 consecutive rebuilds | **396.6**, 19.5, 16.2, 16.5, 16.3 | 91, 117, 134, 134, 128 |
| F: fresh copy of the cache (new files), rebuild immediately | 468.4, 457.7, 412.0 | 99, 73, 100 |
| FW: fresh copy, idle 10 minutes, then rebuild | 391.8, 396.8 | 101, 100 |

All 10 rebuilds: simulation output identical to the reference incremental build,
every reused DLL byte-identical to its cache.

Suspend check (Windows System log, Kernel-Power events, checked afterwards): the laptop
was in Modern Standby from 02:10:56 to 02:23:07 (power button, then lid), during the
untimed setup step and before the first timed rebuild (which started about 02:41). No
suspend event falls inside any timed rebuild of this experiment, so the timed values
stand; the setup duration below includes those 12 minutes.

Additional observation (logged at 02:29 in `logs/phase1_firsttouch_observations.log`):
the script's setup step only READ and hashed the 14,997 cached DLLs (last read
about three hours earlier), yet took about 45 minutes wall-clock (about 33 minutes
excluding the 12-minute standby), using 27 s of Python CPU in
total while Defender ran at 94% of a core. Similarly, each rep's post-rebuild
correctness hashing of the 15k freshly written build-directory DLLs took about 8
minutes (the gaps between W timestamps), for trivial Python CPU.

## 4. Diagnosis

- **Steady-state cost is linear and small.** Once the files involved have been
  touched, an incremental rebuild at N=5,000 takes 16.2 to 19.5 s (W reps 1-4,
  mean 17.1 s), consistent with the linear per-file copy cost plus the linear
  driver compile. Against the original single full rebuild (675.5 s) that is about
  39x, continuing the trend (27.0x at N=1,000, 30.5x at N=2,000). Caveat: both full
  rebuild values at N=5,000 are single measurements (675.5 s original; 972.2 s for
  this session's cache build, which ran while analysis agents were active).
- **The anomaly is a first-touch cost of about 380 to 450 s at N=5,000**, roughly
  25 to 30 ms per file. It appears in the first rebuild after the cache was set up,
  in every rebuild from a freshly created copy, and in plain read-only hashing of
  files not read recently.
- **Waiting does not remove it** (FW = F): it is not a background scan backlog that
  drains with time; it is paid synchronously when the files are opened.
- **Demonstrated result: a first-touch filesystem/I/O overhead.** What the
  experiment establishes is that opening files not recently touched costs about 25
  to 30 ms per file on this host, independent of compilation and of how long one
  waits. The underlying mechanism is NOT established.
- **Likely contributing mechanism (not proven causality): antivirus on-access
  scanning.** Windows Defender real-time protection is enabled, and its CPU use is
  about one full core during every slow operation, which involves no compiler work.
  But Defender CPU was also high during the fast W reps, so CPU level does not
  separate slow from fast; and the pattern is not fully explained: W rep 0 was slow
  even though the setup step had just read every cache file. Other contributors are
  not ruled out (filesystem metadata and directory-creation costs at 15k files per
  directory, NTFS/cache-manager behavior, the laptop's power state). A bounded
  scan-result cache is one UNVERIFIED possibility. Establishing causality would need
  a controlled run with the build directories excluded from on-access scanning (a
  host security change, not made here) or on a host without on-access scanning.

Classification (task categories): **mainly A (a host-environment effect on the
measurement) interacting with B (a build-system design property)**. It is not C:
the steady-state cost does not change regime. The design property is that every
incremental rebuild materializes one new executable file per unit (N DLLs copied
into a fresh directory), so any per-file first-touch cost scales with N and
dominates at large N. The original 3.33x was a single timed rebuild that paid most
of this cost.

**Confidence:** high that the anomaly is a per-file first-touch filesystem/I/O cost,
not compilation, linking, the change, or a scaling regime change (reproduced; parts
measured; conditions discriminate). Moderate that antivirus scanning contributes.
Low on the exact mechanism and trigger.

## 5. Implications for the scaling claim

- The growing-speedup claim can extend to 14,999 equations for steady-state
  rebuilds (about 39x at N=5,000, n=4 warm reps, single full-rebuild reference),
  stated with the caveat above.
- A real operational limitation must be stated: on this host, the first rebuild
  after a cache is created or left idle for hours costs about 400 s at N=5,000
  (more than half the full rebuild), due to first-touch filesystem/I/O overhead
  (antivirus on-access scanning is a likely contributor, not an established cause;
  other hosts may differ). For a digital twin that
  rebuilds rarely, this first-touch cost, not the steady state, may be the cost
  actually experienced.
- The fix direction is the one the paper's future work already names: stop
  materializing N files per rebuild (reuse a persistent build directory in place,
  or load cached DLLs directly from the cache). That would remove the per-rebuild
  O(N) file creation that both the copy cost and this first-touch cost scale with.
  Not implemented here (a build-architecture change, outside this upgrade's scope).
- Timing methodology: one warm-up does not guarantee warm state at large N; the
  per-file first-touch cost can leak into timed repeats (also seen as run-position
  outliers in Phase 2). Report first-rebuild and steady-state costs separately.
