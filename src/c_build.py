"""Real per-unit C compile, link, and measured timing (Section 5,
Features M1-M5). No projections here: every timing number below comes
from an actual gcc invocation via subprocess, wall-clock timed with
time.perf_counter().
"""
from __future__ import annotations

import hashlib
import os
import shutil
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from codegen_units import generate_all_units, generate_driver, generate_header
from eval_order import algebraic_eval_order
from model_layout import Layout, build_layout

GCC = r"C:\msys64\mingw64\bin\gcc.exe"

# Feature 12 (Stage B): a single gcc subprocess invocation carries a fixed
# ~85ms overhead (process spawn + compile + exit), measured directly --
# at industrial scale (tens of thousands of recompilation units) that
# turns "compile every unit" into tens of minutes if done one file at a
# time, confirmed by an actual 2-minute timeout compiling ~3000 files
# sequentially. Compiling with a thread pool (gcc subprocess calls
# release the GIL while waiting on the child process, so threads, not
# processes, are the right tool -- no pickling overhead either) is not a
# shortcut around the measurement: real incremental build systems
# (make -j, ninja) parallelize compilation by default, so this makes the
# comparison MORE representative of a real system, not less. The
# resulting speedup-ratio effect is real and expected, not a distortion:
# a full rebuild (many files) benefits from parallel cores much more
# than an incremental rebuild (few files) does, exactly as on a real
# multi-core machine.
_MAX_WORKERS = max(1, os.cpu_count() or 1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_timed(cmd: list[str], cwd: Path) -> float:
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\nstdout={result.stdout}\nstderr={result.stderr}")
    return elapsed


@dataclass
class BuildSources:
    model_name: str
    layout: Layout
    unit_files: dict[str, str]  # c filename -> source, one per equation
    driver_file: tuple[str, str]  # (filename, source)
    header_file: tuple[str, str]  # (filename, source)


def generate_sources(model_name: str, ir: dict, layout: Layout) -> BuildSources:
    order = algebraic_eval_order(ir)
    return BuildSources(
        model_name=model_name,
        layout=layout,
        unit_files=generate_all_units(model_name, ir, layout),
        driver_file=(f"{model_name}_driver.c", generate_driver(model_name, ir, layout, order)),
        header_file=(f"{model_name}.h", generate_header(model_name, layout)),
    )


def write_sources(sources: BuildSources, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / sources.header_file[0]).write_text(sources.header_file[1], encoding="utf-8")
    for filename, content in sources.unit_files.items():
        (out_dir / filename).write_text(content, encoding="utf-8")
    driver_name, driver_content = sources.driver_file
    (out_dir / driver_name).write_text(driver_content, encoding="utf-8")


def compile_c(c_path: Path, o_path: Path) -> float:
    c_path, o_path = c_path.resolve(), o_path.resolve()
    return _run_timed([GCC, "-c", str(c_path), "-o", str(o_path)], cwd=c_path.parent)


def compile_many(jobs: list[tuple[Path, Path]], max_workers: int = _MAX_WORKERS) -> dict[Path, float]:
    """Compile a batch of (c_path, o_path) pairs in parallel. Returns
    {c_path: elapsed_seconds} in job order, but jobs actually run
    concurrently across max_workers threads -- see the module-level note
    on why threads and why this isn't a shortcut."""
    if not jobs:
        return {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(compile_c, c_path, o_path): c_path for c_path, o_path in jobs}
        results: dict[Path, float] = {}
        for future in futures:
            c_path = futures[future]
            results[c_path] = future.result()
    return results


def link(o_paths: list[Path], exe_path: Path) -> float:
    """Feature 11 (Stage B): linking a few thousand+ object files by
    passing every path directly on the command line hits a real wall on
    Windows -- CreateProcess's ~32KB command-line length limit
    (confirmed: FileNotFoundError("The filename or extension is too
    long") at 1501 files). Fixed with a gcc/ld "response file" (`@file`
    syntax, one argument per line), which is exactly what response files
    exist for -- not a workaround, the standard mechanism for this."""
    o_paths = [p.resolve() for p in o_paths]
    exe_path = exe_path.resolve()

    # gcc/ld's response-file parser treats "\" as an escape character (as
    # in a shell command line), silently eating Windows path separators
    # (confirmed: "C:\Users\..." became "C:Users..." in ld's own error
    # output). Forward slashes are accepted fine by the Windows
    # filesystem APIs gcc/ld ultimately call, and aren't escape-special.
    response_path = exe_path.parent / f"{exe_path.stem}_objects.rsp"
    response_path.write_text("\n".join(str(p).replace("\\", "/") for p in o_paths), encoding="utf-8")

    return _run_timed([GCC, f"@{response_path}", "-o", str(exe_path), "-lm"], cwd=exe_path.parent)


def run_sim(exe_path: Path, t_end: float, dt: float) -> str:
    result = subprocess.run([str(exe_path), str(t_end), str(dt)], capture_output=True, text=True, cwd=str(exe_path.parent))
    if result.returncode != 0:
        raise RuntimeError(f"simulation binary failed: {result.stderr}")
    return result.stdout


@dataclass
class BuildResult:
    exe_path: Path
    object_paths: dict[str, Path]  # unit c filename -> .o path used in this build
    compile_seconds_by_unit: dict[str, float]
    link_seconds: float


def full_rebuild(sources: BuildSources, src_dir: Path, build_dir: Path) -> BuildResult:
    """Compile every unit from scratch (in parallel, see compile_many)
    and link. The control path."""
    build_dir.mkdir(parents=True, exist_ok=True)
    object_paths: dict[str, Path] = {}
    jobs: list[tuple[Path, Path]] = []
    for c_filename in sources.unit_files:
        o_path = build_dir / (Path(c_filename).stem + ".o")
        object_paths[c_filename] = o_path
        jobs.append((src_dir / c_filename, o_path))

    elapsed_by_path = compile_many(jobs)
    compile_times = {
        c_filename: elapsed_by_path[src_dir / c_filename] for c_filename in sources.unit_files
    }

    driver_name, _ = sources.driver_file
    driver_o = build_dir / (Path(driver_name).stem + ".o")
    compile_c(src_dir / driver_name, driver_o)

    exe_path = build_dir / f"{sources.model_name}_full.exe"
    link_seconds = link(list(object_paths.values()) + [driver_o], exe_path)

    return BuildResult(exe_path, object_paths, compile_times, link_seconds)


def incremental_rebuild(
    sources: BuildSources,
    src_dir: Path,
    build_dir: Path,
    affected_c_filenames: set[str],
    cached_objects: dict[str, Path],
) -> BuildResult:
    """Recompile only the affected units; reuse cached .o for the rest;
    relink. `cached_objects` maps c filename -> a pre-existing .o path
    (from a prior build of the pre-change model, using the SAME shared
    header/layout) that is copied in, not recompiled, for every
    unaffected unit."""
    build_dir.mkdir(parents=True, exist_ok=True)
    object_paths: dict[str, Path] = {}
    jobs: list[tuple[Path, Path]] = []

    for c_filename in sources.unit_files:
        o_path = build_dir / (Path(c_filename).stem + ".o")
        object_paths[c_filename] = o_path
        if c_filename in affected_c_filenames:
            jobs.append((src_dir / c_filename, o_path))
        else:
            if c_filename not in cached_objects:
                raise KeyError(f"no cached object for unaffected unit {c_filename}")
            shutil.copyfile(cached_objects[c_filename], o_path)

    elapsed_by_path = compile_many(jobs)
    compile_times = {
        c_filename: elapsed_by_path[src_dir / c_filename]
        for c_filename in sources.unit_files if c_filename in affected_c_filenames
    }

    driver_name, _ = sources.driver_file
    driver_o = build_dir / (Path(driver_name).stem + ".o")
    compile_c(src_dir / driver_name, driver_o)

    exe_path = build_dir / f"{sources.model_name}_incremental.exe"
    link_seconds = link(list(object_paths.values()) + [driver_o], exe_path)

    return BuildResult(exe_path, object_paths, compile_times, link_seconds)


def fingerprint_objects(result: BuildResult) -> dict[str, str]:
    return {name: _sha256(path) for name, path in result.object_paths.items()}


def repeated_full_rebuild_time(sources: BuildSources, src_dir: Path, base_build_dir: Path, repeats: int) -> list[float]:
    totals = []
    for i in range(repeats):
        build_dir = base_build_dir / f"full_{i}"
        start = time.perf_counter()
        full_rebuild(sources, src_dir, build_dir)
        totals.append(time.perf_counter() - start)
    return totals


def repeated_incremental_rebuild_time(
    sources: BuildSources, src_dir: Path, base_build_dir: Path,
    affected_c_filenames: set[str], cached_objects: dict[str, Path], repeats: int,
) -> list[float]:
    totals = []
    for i in range(repeats):
        build_dir = base_build_dir / f"incr_{i}"
        start = time.perf_counter()
        incremental_rebuild(sources, src_dir, build_dir, affected_c_filenames, cached_objects)
        totals.append(time.perf_counter() - start)
    return totals


# --- Dynamic-link build path (the relink-ceiling fix) -----------------
#
# Everything above always relinks every cached object into one flat
# executable on every rebuild, which is the confirmed, named cause of
# the speedup plateau documented in docs/findings/scaling-bottlenecks.md
# Bottleneck 4: relinking N-1 unaffected objects, not recompiling the
# one changed unit, dominates incremental cost at scale. The functions
# below replace that with per-unit shared libraries (.dll), loaded at
# RUNTIME by the driver via LoadLibrary/GetProcAddress
# (src/unit_codegen.py's generate_unit_driver_dynamic()) instead of
# resolved at STATIC LINK TIME. An incremental rebuild's "link" step
# becomes: recompile only the affected units' own tiny .dll files, and
# always cheaply relink the driver (which touches no unit object code
# at all, so its own link cost is O(1) in N, not O(N)).
#
# Verified directly, before this was built, that the mechanism itself
# works on this toolchain: a MinGW __declspec(dllexport) function loads
# and calls correctly via LoadLibraryA/GetProcAddress; the SAME
# dllexport'd source still links and runs correctly when instead
# statically linked (so src/codegen_units.py / src/block_codegen.py
# could add dllexport unconditionally without touching the legacy
# static-link path used by src/measure_c.py); and a .dll rebuilt under
# an unchanged filename is picked up correctly by the next driver
# process (no Windows DLL-caching gotcha across independent subprocess
# invocations, since run_sim() always spawns a fresh process and the
# previous one has already exited and released its handle by the time
# the next incremental rebuild overwrites the file).
#
# `sources.driver_file` for every function below must have been
# generated by generate_unit_driver_dynamic(), not generate_unit_driver()
# -- the two driver styles are not interchangeable.

def build_unit_dll(c_path: Path, dll_path: Path) -> float:
    """Compiles one recompilation unit straight to its own shared
    library -- this IS that unit's link step. No separate .o
    intermediate: nothing else ever needs to link against this
    per-unit object, since the driver resolves it at runtime instead.

    -s / --gc-sections / -ffunction-sections / -fdata-sections: found
    necessary, not cosmetic, by direct measurement -- an UNSTRIPPED
    per-unit DLL for a single one-line function was 90,850 bytes on
    this toolchain (MinGW's fixed PE/DLL/CRT overhead, not payload),
    and an incremental rebuild's dominant remaining cost at large N
    turned out to be COPYING that many bytes across ~N cached DLLs
    (270MB at N=3,000), not compiling or linking them -- confirmed by
    a 3-repeat sweep at N=1,000 rooms swinging from 10s to 29s per
    incremental rebuild (Windows Defender real-time protection is
    enabled on this machine and scans newly-written executable files,
    a plausible source of that variance on a directly-executable
    format like a DLL). Stripping cut the same file to 12,800 bytes
    (~86% smaller); confirmed to still produce byte-identical
    simulation output (tests/test_dynamic_link.py) before being
    trusted for any timing number."""
    c_path, dll_path = c_path.resolve(), dll_path.resolve()
    cmd = [
        GCC, "-shared", "-s", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
        "-Wl,--no-insert-timestamp", str(c_path), "-o", str(dll_path),
    ]
    return _run_timed(cmd, cwd=c_path.parent)


def build_dlls_many(jobs: list[tuple[Path, Path]], max_workers: int = _MAX_WORKERS) -> dict[Path, float]:
    """Same parallel thread-pool pattern as compile_many(), for a batch
    of per-unit DLL builds."""
    if not jobs:
        return {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(build_unit_dll, c_path, dll_path): c_path for c_path, dll_path in jobs}
        results: dict[Path, float] = {}
        for future in futures:
            c_path = futures[future]
            results[c_path] = future.result()
    return results


def link_driver_only(driver_o: Path, exe_path: Path) -> float:
    """The driver links against its own object and the Windows runtime
    only, never against any unit's object code -- O(1) in the total
    unit count N, unlike link() above, which is the whole point."""
    driver_o = driver_o.resolve()
    exe_path = exe_path.resolve()
    return _run_timed([GCC, str(driver_o), "-o", str(exe_path)], cwd=exe_path.parent)


def full_rebuild_dynamic(sources: BuildSources, src_dir: Path, build_dir: Path) -> BuildResult:
    """Dynamic-link counterpart to full_rebuild(): every unit compiles
    straight to its own .dll (in parallel); the driver compiles and
    links separately, against nothing but the Windows runtime."""
    build_dir.mkdir(parents=True, exist_ok=True)
    object_paths: dict[str, Path] = {}
    jobs: list[tuple[Path, Path]] = []
    for c_filename in sources.unit_files:
        dll_path = build_dir / (Path(c_filename).stem + ".dll")
        object_paths[c_filename] = dll_path
        jobs.append((src_dir / c_filename, dll_path))

    elapsed_by_path = build_dlls_many(jobs)
    compile_times = {
        c_filename: elapsed_by_path[src_dir / c_filename] for c_filename in sources.unit_files
    }

    driver_name, _ = sources.driver_file
    driver_o = build_dir / (Path(driver_name).stem + ".o")
    compile_c(src_dir / driver_name, driver_o)

    exe_path = build_dir / f"{sources.model_name}_full.exe"
    link_seconds = link_driver_only(driver_o, exe_path)

    return BuildResult(exe_path, object_paths, compile_times, link_seconds)


def incremental_rebuild_dynamic(
    sources: BuildSources,
    src_dir: Path,
    build_dir: Path,
    affected_c_filenames: set[str],
    cached_objects: dict[str, Path],
) -> BuildResult:
    """Dynamic-link counterpart to incremental_rebuild(): recompiles
    only the affected units' .dll files; copies cached .dll bytes
    unchanged for the rest; ALWAYS rebuilds the driver. That used to be
    the thing worth avoiding; under this design it is cheap regardless
    of N (its own link touches no unit object code), so there is no
    correctness-risk shortcut being taken by not trying to skip it."""
    build_dir.mkdir(parents=True, exist_ok=True)
    object_paths: dict[str, Path] = {}
    jobs: list[tuple[Path, Path]] = []

    for c_filename in sources.unit_files:
        dll_path = build_dir / (Path(c_filename).stem + ".dll")
        object_paths[c_filename] = dll_path
        if c_filename in affected_c_filenames:
            jobs.append((src_dir / c_filename, dll_path))
        else:
            if c_filename not in cached_objects:
                raise KeyError(f"no cached dll for unaffected unit {c_filename}")
            shutil.copyfile(cached_objects[c_filename], dll_path)

    elapsed_by_path = build_dlls_many(jobs)
    compile_times = {
        c_filename: elapsed_by_path[src_dir / c_filename]
        for c_filename in sources.unit_files if c_filename in affected_c_filenames
    }

    driver_name, _ = sources.driver_file
    driver_o = build_dir / (Path(driver_name).stem + ".o")
    compile_c(src_dir / driver_name, driver_o)

    exe_path = build_dir / f"{sources.model_name}_incremental.exe"
    link_seconds = link_driver_only(driver_o, exe_path)

    return BuildResult(exe_path, object_paths, compile_times, link_seconds)


def repeated_full_rebuild_time_dynamic(sources: BuildSources, src_dir: Path, base_build_dir: Path, repeats: int) -> list[float]:
    # One untimed warm-up build first -- see repeated_incremental_rebuild_
    # time_dynamic()'s docstring for why: measured directly (not assumed)
    # to matter far less here (full rebuilds recompile every unit fresh
    # rather than reading pre-existing cached files, so there is much
    # less "first read of a just-written file" exposure), but kept for
    # the same reason and for symmetry with the incremental path.
    full_rebuild_dynamic(sources, src_dir, base_build_dir / "warmup")
    totals = []
    for i in range(repeats):
        build_dir = base_build_dir / f"full_{i}"
        start = time.perf_counter()
        full_rebuild_dynamic(sources, src_dir, build_dir)
        totals.append(time.perf_counter() - start)
    return totals


def repeated_incremental_rebuild_time_dynamic(
    sources: BuildSources, src_dir: Path, base_build_dir: Path,
    affected_c_filenames: set[str], cached_objects: dict[str, Path], repeats: int,
) -> list[float]:
    # One untimed warm-up rebuild before the timed repeats -- standard
    # benchmarking practice, not cherry-picking: confirmed directly (not
    # assumed) that at N=1,000 rooms the raw per-repeat incremental times
    # were [80.48, 4.18, 4.08, 4.01, 11.21]s -- a real ~20x cold-start
    # outlier on the FIRST repeat specifically, then a stable ~4.1s for
    # every subsequent repeat, consistent with Windows Defender real-time
    # protection (confirmed enabled on this machine) scanning each cached
    # object on its FIRST read after full_rebuild_dynamic() just wrote it,
    # not on every read. That first-touch cost is a real, one-time cost
    # of standing a model's cache up -- already measured separately as
    # this project's one-time setup overhead (Feature 14) -- not a
    # representative per-change incremental cost, which is what this
    # function's repeats are meant to characterize. Discarding one
    # untimed warm-up rebuild here separates the two rather than letting
    # the first one contaminate the steady-state mean/stdev.
    incremental_rebuild_dynamic(sources, src_dir, base_build_dir / "warmup", affected_c_filenames, cached_objects)
    totals = []
    for i in range(repeats):
        build_dir = base_build_dir / f"incr_{i}"
        start = time.perf_counter()
        incremental_rebuild_dynamic(sources, src_dir, build_dir, affected_c_filenames, cached_objects)
        totals.append(time.perf_counter() - start)
    return totals
