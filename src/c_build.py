"""Real per-unit C compile, link, and measured timing (Section 5,
Features M1-M5). No projections here: every timing number below comes
from an actual gcc invocation via subprocess, wall-clock timed with
time.perf_counter().
"""
from __future__ import annotations

import hashlib
import shutil
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from codegen_units import generate_all_units, generate_driver, generate_header
from eval_order import algebraic_eval_order
from model_layout import Layout, build_layout

GCC = r"C:\msys64\mingw64\bin\gcc.exe"


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


def link(o_paths: list[Path], exe_path: Path) -> float:
    o_paths = [p.resolve() for p in o_paths]
    exe_path = exe_path.resolve()
    return _run_timed([GCC, *[str(p) for p in o_paths], "-o", str(exe_path), "-lm"], cwd=exe_path.parent)


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
    """Compile every unit from scratch and link. The control path."""
    build_dir.mkdir(parents=True, exist_ok=True)
    compile_times: dict[str, float] = {}
    object_paths: dict[str, Path] = {}

    for c_filename in sources.unit_files:
        c_path = src_dir / c_filename
        o_path = build_dir / (Path(c_filename).stem + ".o")
        compile_times[c_filename] = compile_c(c_path, o_path)
        object_paths[c_filename] = o_path

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
    compile_times: dict[str, float] = {}
    object_paths: dict[str, Path] = {}

    for c_filename in sources.unit_files:
        o_path = build_dir / (Path(c_filename).stem + ".o")
        if c_filename in affected_c_filenames:
            compile_times[c_filename] = compile_c(src_dir / c_filename, o_path)
        else:
            if c_filename not in cached_objects:
                raise KeyError(f"no cached object for unaffected unit {c_filename}")
            shutil.copyfile(cached_objects[c_filename], o_path)
        object_paths[c_filename] = o_path

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
