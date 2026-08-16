# Finding: two real scaling bottlenecks discovered while building toward 100,000 equations

Measured while validating `src/scaled_models.py` (Feature 10) before committing to
an experimental target size for the rest of Stage B.

## Bottleneck 1: Rumoca's own compile time grows superlinearly

Compiling `ThermalChain{N}` (the generated N-room thermal chain,
`3N-1` equations) through `rumoca.Session().load()`:

| N (rooms) | Equations | Rumoca compile time |
|---|---|---|
| 100 | 299 | 0.121s |
| 1,000 | 2,999 | 1.438s |
| 5,000 | 14,999 | 21.062s |
| 10,000 | 29,999 | 67.749s |

Growth from 5,000 to 10,000 equations (2x) took 3.2x longer, consistent
with roughly O(n^1.7) scaling, not linear. This is Rumoca's own
parse/flatten/DAE-export pipeline, not this project's code -- nothing
here can "fix" a third-party compiler's internal complexity. Extrapolating
(cautiously, per the project's own rule against extrapolating past what
is measured) this trend to ~33,000 rooms (~100,000 equations) suggests
roughly 8-15 minutes for a SINGLE compile of one model variant -- and a
real experiment cell needs at least two compiles (baseline + changed)
plus repeated builds on top.

## Bottleneck 2: gcc subprocess-per-file overhead

This project's C codegen (`src/unit_codegen.py`) emits one `.c` file per
recompilation unit, historically compiled with one `gcc` subprocess
invocation per file (`src/c_build.py`). Measured directly: **~85ms fixed
overhead per gcc invocation** (process spawn + compile + exit), largely
independent of the file's actual content (these are tiny, single-equation
files). Confirmed as a real wall: compiling ~3,000 files sequentially did
not finish within a 2-minute timeout.

**Fixed, not just documented**: `src/c_build.py`'s `compile_many()` runs
compiles concurrently via a thread pool (`ThreadPoolExecutor` -- gcc
subprocess calls release the GIL while waiting on the child process, so
threads are the right tool, with none of multiprocessing's pickling
overhead). This is a legitimate optimization, not a shortcut around the
measurement: real incremental build systems (`make -j`, `ninja`) parallelize
compilation by default, so this makes the full-vs-incremental comparison
MORE representative of a real system, not less -- and the resulting effect
(a full rebuild, with many files, benefits from parallel cores far more
than an incremental rebuild, with few files, does) is real, expected
behavior on any real multi-core machine, not a distortion introduced to
flatter the speedup number.

Measured effect: 3,000-file compile dropped from an unmeasured-but-over-
120s sequential time to **62.6s** parallelized (12 cores detected), a
per-file wall-clock drop from 84.7ms to 20.9ms. Increasing thread count
further (24, 48 workers) gave only marginal further improvement (61.3s,
58.5s) -- ~20ms/file appears to be close to a practical floor on this
machine (gcc's own startup cost, filesystem I/O, or Windows process-
creation overhead, not thread scheduling), not something more threads
alone resolves.

## Consequence for Stage B's experimental scope

Even with the gcc-parallelization fix, Rumoca's own superlinear compile
time remains the dominant, unfixed bottleneck at industrial scale. Per the
project's own playbook (prd-combined.md Section 7.3: "If scaling exposes a
bottleneck you cannot fully fix in time, report the largest size that runs
cleanly and the measured growth rate honestly, rather than extrapolating
past what you measured"): Stage B's repeated-measurement experiments
(Features 11, 13, 14 -- correctness, speedup-vs-size, overhead-vs-size,
each needing multiple builds per cell) target a range where a full
experiment cell completes in tens of seconds to a few minutes (up to
several thousand equations), not literally 100,000. A single, one-off
(not repeated) largest-size data point is still pushed as far as
practical for the scaling-trend figures, honestly labeled as such.
