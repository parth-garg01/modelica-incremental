"""Relink-ceiling fix: the dynamic-link build path (per-unit .dll,
loaded at runtime via LoadLibrary/GetProcAddress -- src/c_build.py's
full_rebuild_dynamic()/incremental_rebuild_dynamic(), src/unit_codegen.py's
generate_unit_driver_dynamic()) must produce the exact same behavior as
the original static-link path (one flat .exe, always relinked) it is
meant to replace for measurement purposes. Proven here directly, not
assumed: same model, same inputs, two different build mechanisms, byte-
identical simulation output required.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from c_build import (
    compile_c, fingerprint_objects, full_rebuild_dynamic, incremental_rebuild_dynamic,
    link, run_sim,
)
from compile import compile_model
from correctness_c import diff_outputs
from model_layout import build_layout
from unit_codegen import write_unit_sources, write_unit_sources_dynamic

BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_test" / "dynamic_link"


@pytest.fixture(autouse=True)
def _clean_build_dir():
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    yield
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)


def _build_and_run_static(model_name: str, source_path: str, t_end: float, dt: float) -> str:
    result = compile_model(source_path, model_name)
    layout = build_layout(result.ir)
    src_dir = BUILD_ROOT / model_name / "static_src"
    written = write_unit_sources(model_name, result.ir, layout, src_dir)

    build_dir = BUILD_ROOT / model_name / "static_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    objs = []
    for key, path in written.items():
        if key == "header":
            continue
        o_path = build_dir / (path.stem + ".o")
        compile_c(path, o_path)
        objs.append(o_path)
    exe = build_dir / f"{model_name}_static.exe"
    link(objs, exe)
    return run_sim(exe, t_end, dt)


def _build_and_run_dynamic(model_name: str, source_path: str, t_end: float, dt: float) -> str:
    from c_build import BuildSources, generate_sources

    result = compile_model(source_path, model_name)
    layout = build_layout(result.ir)
    src_dir = BUILD_ROOT / model_name / "dynamic_src"
    write_unit_sources_dynamic(model_name, result.ir, layout, src_dir)

    from codegen_units import generate_header
    from unit_codegen import generate_all_unit_sources, generate_unit_driver_dynamic

    sources = BuildSources(
        model_name=model_name,
        layout=layout,
        unit_files=generate_all_unit_sources(model_name, result.ir, layout),
        driver_file=(f"{model_name}_driver.c", generate_unit_driver_dynamic(model_name, result.ir, layout)),
        header_file=(f"{model_name}.h", generate_header(model_name, layout)),
    )
    build_dir = BUILD_ROOT / model_name / "dynamic_build"
    result_build = full_rebuild_dynamic(sources, src_dir, build_dir)
    return run_sim(result_build.exe_path, t_end, dt)


def _expected_coupled_dynamic_csv(t_end: float, dt: float) -> str:
    lines = ["time,x,y1,y2"]
    x, t = 1.0, 0.0
    while t <= t_end + 1e-9:
        lines.append(f"{t:g},{x:g},{0.6*x:g},{-0.2*x:g}")
        x *= (1 - dt)
        t += dt
    return "\n".join(lines) + "\n"


def test_dynamic_link_matches_static_link_on_coupled_model():
    """A genuine coupled block (linear-system solve, not just a
    singleton assignment) must behave identically whether its unit is
    statically linked into one exe or loaded from its own .dll at
    runtime."""
    static_out = _build_and_run_static("CoupledDynamic", "models/coupled_dynamic/CoupledDynamic.mo", 3.0, 0.5)
    dynamic_out = _build_and_run_dynamic("CoupledDynamic", "models/coupled_dynamic/CoupledDynamic.mo", 3.0, 0.5)
    assert dynamic_out == static_out

    expected = _expected_coupled_dynamic_csv(3.0, 0.5)
    diff = diff_outputs(expected, dynamic_out)
    assert diff["pass"] is True
    assert diff["max_abs_error"] == 0.0


def test_dynamic_link_matches_static_link_on_singleton_only_model():
    static_out = _build_and_run_static("ThermalNetwork", "models/thermal_network/ThermalNetwork.mo", 1.0, 0.5)
    dynamic_out = _build_and_run_dynamic("ThermalNetwork", "models/thermal_network/ThermalNetwork.mo", 1.0, 0.5)
    assert dynamic_out == static_out


def test_incremental_dynamic_rebuild_is_bit_identical_to_full_and_reuses_unaffected_dlls():
    """The actual point of the relink-ceiling fix: an incremental rebuild
    under the dynamic path must still be bit-identical to a full rebuild,
    and every unaffected unit's .dll must be byte-for-byte the one
    copied from cache, not silently recompiled or diverged."""
    from c_build import BuildSources
    from codegen_units import generate_header
    from unit_codegen import generate_all_unit_sources, generate_unit_driver_dynamic
    from resolver import resolve_impact
    from matched_graph import build_matched_graph
    from measure_msl import _affected_c_filenames

    model_name = "ThermalNetwork"
    baseline_path = "models/thermal_network/ThermalNetwork.mo"
    changed_path = "models/thermal_network_swapped/ThermalNetwork.mo"

    baseline = compile_model(baseline_path, model_name)
    changed = compile_model(changed_path, model_name)
    layout = build_layout(baseline.ir, changed.ir)

    def _sources(ir):
        return BuildSources(
            model_name=model_name,
            layout=layout,
            unit_files=generate_all_unit_sources(model_name, ir, layout),
            driver_file=(f"{model_name}_driver.c", generate_unit_driver_dynamic(model_name, ir, layout)),
            header_file=(f"{model_name}.h", generate_header(model_name, layout)),
        )

    from c_build import write_sources
    baseline_sources = _sources(baseline.ir)
    changed_sources = _sources(changed.ir)
    baseline_src_dir = BUILD_ROOT / "cell" / "baseline_src"
    changed_src_dir = BUILD_ROOT / "cell" / "changed_src"
    write_sources(baseline_sources, baseline_src_dir)
    write_sources(changed_sources, changed_src_dir)

    cache_build = full_rebuild_dynamic(baseline_sources, baseline_src_dir, BUILD_ROOT / "cell" / "cache")

    impact = resolve_impact(changed.ir, ["Q1"], graph_builder=build_matched_graph)
    affected = _affected_c_filenames(model_name, changed.ir, impact)
    assert 0 < len(affected) < len(changed_sources.unit_files)

    full_result = full_rebuild_dynamic(changed_sources, changed_src_dir, BUILD_ROOT / "cell" / "full")
    incr_result = incremental_rebuild_dynamic(
        changed_sources, changed_src_dir, BUILD_ROOT / "cell" / "incr", affected, cache_build.object_paths,
    )

    full_fp = fingerprint_objects(full_result)
    incr_fp = fingerprint_objects(incr_result)
    cache_fp = fingerprint_objects(cache_build)

    for c_filename in changed_sources.unit_files:
        if c_filename not in affected:
            assert incr_fp[c_filename] == cache_fp.get(c_filename, incr_fp[c_filename]), (
                f"unaffected unit {c_filename}'s incremental .dll is not byte-identical to the cached one"
            )

    full_output = run_sim(full_result.exe_path, 1.0, 0.5)
    incr_output = run_sim(incr_result.exe_path, 1.0, 0.5)
    assert full_output == incr_output
