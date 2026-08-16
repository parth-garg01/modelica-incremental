"""Feature 4 end-to-end: real gcc compile + link + run of the coupled
CoupledDynamic model, checked against an INDEPENDENTLY hand-derived
analytical solution rather than Rumoca's own Model.simulate() output --
see test_rumoca_simulate_has_a_known_bug_on_this_model below for why.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from c_build import compile_c, link, run_sim
from compile import compile_model
from correctness_c import diff_outputs
from model_layout import build_layout
from unit_codegen import write_unit_sources

BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_test" / "unit_codegen"


@pytest.fixture(autouse=True)
def _clean_build_dir():
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    yield
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)


def _build_and_run(model_name: str, source_path: str, t_end: float, dt: float) -> str:
    result = compile_model(source_path, model_name)
    layout = build_layout(result.ir)
    src_dir = BUILD_ROOT / model_name / "src"
    written = write_unit_sources(model_name, result.ir, layout, src_dir)

    build_dir = BUILD_ROOT / model_name / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    objs = []
    for key, path in written.items():
        if key == "header":
            continue
        o_path = build_dir / (path.stem + ".o")
        compile_c(path, o_path)
        objs.append(o_path)
    exe = build_dir / f"{model_name}.exe"
    link(objs, exe)
    return run_sim(exe, t_end, dt)


def _expected_coupled_dynamic_csv(t_end: float, dt: float) -> str:
    """Independent ground truth: y1 = 0.6*x, y2 = -0.2*x (hand-solved from
    y1 = 2*y2+x, y2 = 3*y1-2*x), evaluated at the SAME forward-Euler x
    trajectory this project's own driver uses (x(t+dt) = x(t)*(1-dt))."""
    lines = ["time,x,y1,y2"]
    x, t = 1.0, 0.0
    while t <= t_end + 1e-9:
        lines.append(f"{t:g},{x:g},{0.6*x:g},{-0.2*x:g}")
        x *= (1 - dt)
        t += dt
    return "\n".join(lines) + "\n"


def test_coupled_block_matches_independent_analytical_solution():
    output = _build_and_run("CoupledDynamic", "models/coupled_dynamic/CoupledDynamic.mo", 3.0, 0.5)
    expected = _expected_coupled_dynamic_csv(3.0, 0.5)
    diff = diff_outputs(expected, output)
    assert diff["pass"] is True
    assert diff["max_abs_error"] == 0.0


def test_singleton_only_model_still_correct_through_the_unified_driver():
    """No-regression check: the SAME unit_codegen path (built for Feature
    4's coupled blocks) must still produce the known-correct ThermalNetwork
    trajectory for a model with no coupled units at all."""
    output = _build_and_run("ThermalNetwork", "models/thermal_network/ThermalNetwork.mo", 1.0, 0.5)
    expected = (
        "time,T1,T2,T3,Q1,Q12,Q23,Q1env,Q2env,Q3env\n"
        "0,15,15,15,100,0,0,0,0,0\n"
        "0.5,40,15,15,100,12.5,0,5,0,0\n"
        "1,60.625,18.125,15,100,21.25,1.5625,9.125,0.625,0\n"
    )
    diff = diff_outputs(expected, output)
    assert diff["pass"] is True
    assert diff["max_abs_error"] == 0.0


@pytest.mark.xfail(reason="documents a real bug in Rumoca's own algebraic-loop "
                           "solver, not this project's code -- see "
                           "docs/findings/rumoca-algebraic-loop-bug.md; xfail so "
                           "this is caught (and re-investigated) if a Rumoca "
                           "upgrade ever fixes it")
def test_rumoca_simulate_has_a_known_bug_on_this_model():
    """Rumoca's own Model.simulate() gets the FIRST timestep (t=0) right
    (y1=0.6, y2=-0.2, matching the correct initial algebraic solve) but
    is wrong from the second timestep onward for CoupledDynamic, on every
    one of the 5 available solvers (auto, rk-like, bdf, esdirk34,
    trbdf2): y2 comes out exactly equal to x at every subsequent step,
    which is wrong (the correct solution is y2 = -0.2*x throughout,
    independently verified by hand and by this project's own linear
    block solve -- see test_coupled_block_matches_independent_analytical_
    solution above, which matches the correct answer exactly at every
    step). This test's ASSERTION is that Rumoca is correct at the second
    step; it is expected to fail (xfail) as a permanent record of the
    discrepancy."""
    import rumoca as rm

    session = rm.Session()
    m = session.load("models/coupled_dynamic/CoupledDynamic.mo", model="CoupledDynamic")
    result = m.simulate(t=(0, 0.2), dt=0.1)
    df = result.to_dataframe()
    y2_at_second_step = df.iloc[1]["y2"]
    x_at_second_step = df.iloc[1]["x"]
    expected_y2 = -0.2 * x_at_second_step
    assert abs(y2_at_second_step - expected_y2) < 1e-6, (
        f"expected y2 = -0.2*x = {expected_y2}, Rumoca gave y2={y2_at_second_step} "
        f"(== x={x_at_second_step}, the aliasing bug)"
    )
