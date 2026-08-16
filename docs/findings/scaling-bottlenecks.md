# Finding: real scaling bottlenecks discovered while building toward 100,000 equations

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

## Bottleneck 3: Windows command-line length limit at link time

Found while running Feature 11's end-to-end correctness check at N=500
rooms (1499 recompilation units, 1501 object files including the
driver). `src/c_build.py`'s `link()` originally passed every object
file's full absolute path directly as a `gcc` command-line argument.
Windows' `CreateProcess` has a real, hard command-line length limit
(roughly 32KB); with 1501 long absolute paths, this was exceeded,
confirmed directly: `FileNotFoundError: [WinError 206] The filename or
extension is too long`.

**Fixed, not documented-around**: `link()` now writes a gcc/ld
"response file" (`@file` syntax, one path per line) and passes that
single `@responsefile` argument instead -- the standard mechanism gcc/ld
provide for exactly this situation, not a workaround. One subtlety hit
and fixed along the way: gcc's response-file parser treats `\` as an
escape character (as on a shell command line), which silently ate every
backslash in Windows paths (`C:\Users\...` became `C:Users...` in `ld`'s
own error output) -- fixed by writing paths with forward slashes in the
response file, which Windows' filesystem APIs accept natively and which
aren't escape-special.

## Bottleneck 4: relinking a large object count dominates incremental time

A second finding from the N=500 correctness run, not yet "fixed" (a
genuine design-level tradeoff, not a bug): with 1499 total units and
only 2 affected by the change, the incremental rebuild still took
11.3s against the full rebuild's 29.8s (measured_speedup=2.64x) -- a
real, bit-identical, correct result, but NOT proportional to the tiny
2/1499 affected fraction. Recompiling 2 files is near-instant;
**relinking still needs all 1499 cached objects**, and at this file
count that relink step, not recompilation, is what dominates
incremental time. This is exactly the failure mode the original
year-long prd.md's Section 10 playbook anticipated ("if relinking and
re-matching overhead swamps the saving... change the relink strategy:
cache compiled artifacts per unit and relink only the delta, using
incremental linking or shared objects rather than relinking
everything"). Not addressed in Stage B's current scope (this project's
relink strategy stays "relink everything" throughout); recorded here as
the honest reason speedup should be expected to plateau or even shrink,
not grow without bound, as N grows very large under the current design
-- exactly the kind of finding Feature 13 (speedup vs. model size) needs
to characterize precisely rather than assume away.

## Bottleneck 5: O(n^2) codegen, found and fixed (Feature 12)

Profiling the pipeline stage-by-stage on `ThermalChain{N}` surfaced a
second, genuinely fixable bottleneck -- this one in this project's own
code, not a third-party tool:

| N (rooms) | Equations | codegen (before) | codegen (after) |
|---|---|---|---|
| 100 | 299 | (not separately measured) | 0.033s |
| 1,000 | 2,999 | 3.13s | 0.37s |
| 5,000 | 14,999 | 88.86s | 1.81s |

Before the fix, codegen alone grew 28.4x for a 5x increase in model
size (log(28.4)/log(5) ~= 2.09, i.e. quadratic). Root cause: `src/
codegen_units.py`'s `generate_unit_c()` called `layout.name_to_c()`
(rebuilds a full O(N) dict) and `layout.y.index(name)` / `layout.x.
index(name)` (Python list `.index()`, an O(N) linear scan) -- all
INSIDE the function body, which runs once per recompilation unit in a
loop over all N units (`generate_all_unit_sources` in `src/unit_
codegen.py`). O(N) work done N times is O(N^2). `src/block_codegen.
py`'s `generate_block_unit_c()` had the identical pattern (`name in
layout.y`, `layout.y.index(name)`), and `src/unit_codegen.py`'s
`generate_unit_driver()` had a smaller-magnitude version of the same
bug over parameters and states (`layout.p.index(n)`, `layout.x.
index(n)` inside loops over all P params / X states, both O(N) on the
generated scaling models).

Fixed with O(1) dict-based lookups built ONCE per model and threaded
through every call site, not recomputed per unit: `Layout.
y_index_map()` / `Layout.x_index_map()` (new methods on `src/model_
layout.py`'s `Layout`), plus `name_to_c()` computed once in `generate_
all_unit_sources()` and `generate_unit_driver()` and passed as
optional parameters into `generate_unit_c()` / `generate_block_unit_c()`
(both fall back to computing them internally if omitted, for callers
generating a single unit in isolation, e.g. `block_codegen.py`'s own
`__main__` demo).

After the fix: codegen at N=5,000 went from 88.86s to 1.81s (a ~49x
speedup on this stage alone), and the growth from N=1,000 to N=5,000
(5x size) is now 4.85x time -- log(4.85)/log(5) ~= 0.99, i.e. linear,
not quadratic. Full pytest suite re-run clean after the fix: 144
passed, 1 xfailed, same as before -- no behavior change, only the
lookup mechanism changed (list scan -> dict lookup for the exact same
keys).

Compile time (Bottleneck 1, Rumoca's own O(n^1.7)) is now the
dominant cost by far at this scale (28.4s at N=5,000 vs. codegen's
1.81s) -- expected and consistent with Bottleneck 1's own measurements,
and not something this project's code can fix.

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
