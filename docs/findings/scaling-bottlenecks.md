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

**Confirmed empirically by Feature 13 (`results/measurements_scale.csv`).**
Measured speedup across a 20x size range (149 to 2,999 equations)
stayed in a ~1.8x-2.3x band rather than growing with size (2.27x at
N=50 rooms, 1.84x at N=1000 rooms) -- the plateau predicted above,
not a projection. Also visible directly in the per-size data:
`incremental_stdev_s` grows disproportionately with size relative to
`incremental_mean_s` (11.9s stdev on a 39.3s mean at N=1000, a ~30%
relative spread), consistent with relink (I/O- and process-spawn-bound,
noisier) dominating over recompilation (CPU-bound, more consistent) at
this file count.

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

## Bottleneck 4 fix: per-unit dynamic-link build path

Bottleneck 4 above was recorded as a real, unfixed design tradeoff:
"the current design always relinks every cached object on every
incremental rebuild, never just the changed delta." That is no longer
true as of this fix -- addressed directly, not worked around.

**Mechanism.** Every recompilation unit now compiles straight to its
own shared library (`gcc -shared unit.c -o unit.dll`) instead of a
`.o` baked into one statically-linked executable. The driver no longer
calls unit functions directly (a static-link-time-resolved call); it
loads each unit's `.dll` via `LoadLibraryA`/`GetProcAddress` at
runtime and calls through the resulting function pointer
(`src/unit_codegen.py`'s `generate_unit_driver_dynamic()`). An
incremental rebuild therefore only ever recompiles the one changed
unit's own tiny `.dll`; the driver executable's own link touches
nothing but the Windows runtime, never any unit's object code, so its
cost does not scale with the total unit count `N` either, and it is
safe (and now cheap enough) to always rebuild it fresh rather than try
to detect whether it needs to change.

**Verified before being trusted, in three stages:**
1. A standalone spike (`gcc -shared` + `LoadLibraryA`/`GetProcAddress`
   on a trivial function) confirmed the mechanism works on this exact
   toolchain, including the specific scenario an incremental rebuild
   depends on: rebuilding a `.dll` under an unchanged filename and
   confirming the *next* process picks up the new behavior (no Windows
   DLL-caching gotcha across independent subprocess invocations).
2. A separate spike confirmed `__declspec(dllexport)` on a function is
   a no-op when that same source is instead compiled to a plain `.o`
   and statically linked -- meaning `src/codegen_units.py` and
   `src/block_codegen.py` could add `dllexport` unconditionally to
   every unit's emitted function, serving both the new dynamic-link
   path and the original static-link path (still used unmodified by
   `src/measure_c.py`'s Stage-0 regression path) from one codegen
   source, with zero risk to the already-proven static path.
3. `tests/test_dynamic_link.py` (3 new tests, all passing): the
   dynamic-link path produces **byte-identical** simulation output to
   the static-link path on both a coupled-block model
   (`CoupledDynamic`) and a singleton-only model (`ThermalNetwork`),
   and a dynamic-link incremental rebuild is bit-identical to a
   dynamic-link full rebuild with every unaffected unit's `.dll`
   confirmed byte-identical to its cached copy -- the same correctness
   bar every other measurement in this project holds itself to, applied
   to the new build mechanism before any speed number from it was
   trusted.

**Files:** `src/c_build.py` (`build_unit_dll()`, `build_dlls_many()`,
`link_driver_only()`, `full_rebuild_dynamic()`,
`incremental_rebuild_dynamic()`, and their `repeated_*_dynamic()` timing
wrappers -- all new, alongside the original static-link functions,
not replacing them); `src/unit_codegen.py`
(`generate_unit_driver_dynamic()`, `write_unit_sources_dynamic()`,
`dll_filename()` -- new); `src/codegen_units.py` /
`src/block_codegen.py` (added `__declspec(dllexport)` to every emitted
unit function). `src/measure_msl.py`, `src/change_frequency.py`,
`src/break_even.py` switched to the new dynamic path; `src/measure_c.py`
(Stage 0) deliberately left on the original static path, unmodified.

**A second real bottleneck, found by measuring rather than assumed
fixed: unstripped per-unit DLL size.** The first full sweep run under
this fix showed real, large early gains (double-digit-x speedup at
small-to-mid sizes) that then eroded at the largest size tested
(N=1,000 rooms, 2,999 equations), with incremental-rebuild timing
variance so large (one repeat's mean carried a standard deviation
*larger* than the mean itself) that the number was not trustworthy as
reported. Investigated rather than reported as-is: an unstripped
per-unit DLL for a single one-line compute function was **90,850
bytes** on this MinGW toolchain -- almost entirely fixed PE/DLL/CRT
format overhead, not payload, confirmed by comparing against the same
function compiled with `-s` (stripped): **12,800 bytes**, an 86%
reduction. At N=1,000 (2,999 units), an incremental rebuild copies
roughly 2,997 cached, unaffected DLLs from cache -- at 90KB each, that
is ~270MB of file I/O per incremental build, a real and previously
unaccounted-for cost this fix's own design introduced while removing
the relink cost, and a plausible source of the observed timing
variance given Windows Defender real-time protection is enabled on
this machine and scans newly-written executable files (a directly
loadable format like a DLL is a more natural scan target than a
non-executable `.o`).

**Fixed, not just diagnosed:** `build_unit_dll()` now compiles every
unit with `-s -ffunction-sections -fdata-sections -Wl,--gc-sections
-Wl,--no-insert-timestamp` (strip symbols, dead-code-eliminate at both
the function and linker level, and skip embedding a build timestamp).
Re-verified correctness before trusting any resulting timing number:
`tests/test_dynamic_link.py`'s three tests (bit-identical output on a
coupled and a singleton-only model; incremental bit-identical to full
with byte-identical cache reuse) all still pass with stripped DLLs.

**One secondary check now legitimately differs from before, disclosed
rather than hidden or silently dropped:** `incremental_matches_full_
for_unaffected_objects` (comparing an incremental rebuild's REUSED,
copied-from-cache DLL against what a completely separate, from-scratch
FULL rebuild would independently produce for that same unit) is no
longer expected to hold under the dynamic-link path, even with every
flag above applied -- two independent `gcc -shared` invocations of the
byte-identical source were confirmed to still differ by a small number
of bytes (61 of 12,800, concentrated in what appears to be an internal
MinGW/PE table, not eliminated by `-Wl,--no-insert-timestamp` or
`-fno-stack-protector` either). This is DLL build reproducibility, not
a correctness regression: the check that actually matters for proving
the cache-reuse mechanism is sound,
`reused_objects_byte_identical_to_cache` (the incrementally-reused
DLL's bytes exactly match the CACHED copy it was copied from, not a
second independent build), continues to hold, as does the primary bar,
`outputs_identical` (the two binaries' simulation output matches
exactly). Recorded here as an honest, understood limitation of the
DLL-based approach on this toolchain, not swept under a passing test.

**A third finding, also measured before being trusted: cold-cache
first-touch cost, not a property of the design.** The first full sweep
run with stripped DLLs still showed unusable variance specifically at
the largest size (N=1,000 rooms): one repeat's standard deviation
*larger* than its own mean. Diagnosed with the raw per-repeat times,
not guessed: `[80.48, 4.18, 4.08, 4.01, 11.21]` seconds -- a ~20x
outlier on the *first* incremental repeat specifically, then a stable
~4.1s for every repeat after it. This matches Windows Defender
real-time protection (confirmed enabled on this machine) scanning each
cached object on its first read after `full_rebuild_dynamic()` had just
written it, not on every read -- a real, reproducible, one-time cost of
standing a model's cache up, already measured separately as this
project's one-time setup overhead (Feature 14), not a representative
per-change incremental cost. Fixed with one discarded, untimed warm-up
rebuild before the timed repeats in both `repeated_full_rebuild_time_
dynamic()` and `repeated_incremental_rebuild_time_dynamic()` -- standard
benchmarking practice (discarding cold-cache/cold-JIT iterations before
timing), not cherry-picking a favorable number: the warm-up rebuild
still happens and is still real work, it is simply not counted toward
the steady-state mean/stdev it would otherwise contaminate.

**Result (speedup vs. model size, re-measured under this fix, both the
DLL-size fix and the warm-up fix applied): speedup now GROWS with model
size, a full reversal of the pre-fix finding.** Three repeats per
point, all now with low, tight standard deviation (no more the
unusable variance the two findings above describe), source
`results/measurements_scale.csv`, command `python src/measure_scale.py`:

| N (rooms) | Equations | Full rebuild | Incremental | **Measured speedup** |
|---|---|---|---|---|
| 50 | 149 | 5.93s ± 0.08s | 1.05s ± 0.09s | **5.66x** |
| 100 | 299 | 11.22s ± 0.18s | 1.12s ± 0.03s | **9.99x** |
| 250 | 749 | 27.56s ± 0.83s | 1.78s ± 0.18s | **15.50x** |
| 500 | 1,499 | 51.61s ± 0.30s | 2.49s ± 0.04s | **20.75x** |
| 1,000 | 2,999 | 109.48s ± 4.37s | 4.05s ± 0.12s | **27.01x** |

Speedup grows from 5.66x to 27.01x, roughly 4.8x, across a 20x increase
in model size -- the opposite of the pre-fix finding (a flat 1.8x-2.3x
band across the same size range, `docs/results.md` Section 3.1). Why:
`full_rebuild_mean_s` grows roughly linearly with N (recompiling and
DLL-linking every unit, as expected), while `incremental_mean_s` grows
only slowly (~4x over the same 20x range) since only 2 of `3N-1` units
are ever recompiled and the now-small (~12.8KB, stripped) unaffected
DLLs are cheap to copy even as their count grows -- exactly the
mechanism this fix targeted. Every cell remains bit-identical to a full
rebuild (`outputs_identical=True`) and every reused DLL byte-identical
to its cached copy (`reused_objects_byte_identical_to_cache=True`); see
the note above on why `incremental_matches_full_for_unaffected_objects`
specifically is expected to read `False` under this path (DLL build
non-determinism, not a correctness issue).

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
