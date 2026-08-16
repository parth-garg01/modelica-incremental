"""Feature 5: the Cauer filter hit genuine index reduction (see
docs/findings/cauer-index-reduction.md) and was not used as the
flagship. This is the real-MSL-component flagship instead:
models/msl_rc_circuit/MslRcCircuit.mo, a series R-C circuit built from
genuine Modelica.Electrical.Analog.Basic/Sources components wired with
connect() -- exercising real anonymous KCL/KVL residual equations (the
actual generality gap Feature 1 was built to close) -- with a single
capacitor, so a capacitor-only loop (the index-reduction cause found in
Cauer) is not topologically possible. Confirmed index-1:
Model.structure() reports blocks=23 (all singleton), algebraic_loops=0,
matched=true, and this project's own matching (src/matching.py) achieves
a full 23/23 match.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from c_build import compile_c, link, run_sim
from compile import compile_model
from correctness_c import diff_outputs
from matching import compute_matching
from model_layout import build_layout
from unit_codegen import write_unit_sources

MODEL_PATH = "models/msl_rc_circuit/MslRcCircuit.mo"
ROOTS = ["msl_src", "models/msl_rc_circuit"]
BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_test" / "msl_rc"

MSL_SRC = Path(__file__).resolve().parent.parent / "msl_src"
pytestmark = pytest.mark.skipif(
    not MSL_SRC.exists(),
    reason="msl_src/ (gitignored MSL sparse clone) not present -- see docs/progress.md "
           "for the clone/sparse-checkout command to reproduce it",
)


@pytest.fixture(autouse=True)
def _clean_build_dir():
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    yield
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)


def test_matching_achieves_full_match_on_real_msl_component_circuit():
    result = compile_model(MODEL_PATH, "MslRcCircuit", roots=ROOTS)
    m = compute_matching(result.ir)
    assert m.is_matched is True
    assert m.unmatched_equations == []
    assert len(result.ir["f_x"]) == 23


def _build_and_run(t_end: float, dt: float) -> str:
    result = compile_model(MODEL_PATH, "MslRcCircuit", roots=ROOTS)
    layout = build_layout(result.ir)
    src_dir = BUILD_ROOT / "src"
    written = write_unit_sources("MslRcCircuit", result.ir, layout, src_dir)

    build_dir = BUILD_ROOT / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    objs = []
    for key, path in written.items():
        if key == "header":
            continue
        o_path = build_dir / (path.stem + ".o")
        compile_c(path, o_path)
        objs.append(o_path)
    exe = build_dir / "MslRcCircuit.exe"
    link(objs, exe)
    return run_sim(exe, t_end, dt)


def _expected_rc_charging_csv(t_end: float, dt: float, n_algebraic: int) -> tuple[str, int]:
    """Independent ground truth from basic RC circuit theory (KVL: V0 =
    i*R + V_C, i = C*dV_C/dt => dV_C/dt = (V0-V_C)/(R*C)), applied with
    the SAME forward-Euler recursion and dt this project's own driver
    uses -- not Rumoca's simulate() (a different, adaptive/implicit
    integration scheme that will not bit-match a fixed-step explicit
    Euler driver at any finite dt; see docs/findings/
    rumoca-algebraic-loop-bug.md's note on why this project checks
    against independent analytical ground truth rather than assuming a
    reference simulator's numbers are the bar). Returns (csv_header_row_
    count_matching_stub, vc_index) is not meaningful here -- returns just
    the list of expected C.v values, %g-formatted to match the C driver's
    own printf("%g", ...) precision exactly (a plain higher-precision
    Python float would show a ~1e-6 false "discrepancy" that is really
    just printf rounding, not a real numerical difference)."""
    V0, R, C = 5.0, 100.0, 0.01
    vc = 0.0
    values = []
    t = 0.0
    while t <= t_end + 1e-9:
        values.append(f"{vc:g}")
        vc = vc + dt * (V0 - vc) / (R * C)
        t += dt
    return values


def test_matches_independent_rc_charging_recursion_exactly():
    """The rigorous ground truth check (see docstring above for why this,
    not Rumoca's simulate(), is the comparison): C.v must match the
    independent RC discrete recursion exactly, to %g printf precision."""
    output = _build_and_run(5.0, 0.5)
    lines = output.strip().splitlines()
    header = lines[0].split(",")
    cv_idx = header.index("C.v")
    actual = [line.split(",")[cv_idx] for line in lines[1:]]

    expected = _expected_rc_charging_csv(5.0, 0.5, n_algebraic=22)
    assert actual == expected


def test_agrees_closely_with_rumocas_own_simulation():
    """Cross-check, not the primary correctness bar: Rumoca's own
    Model.simulate() (trustworthy here, unlike CoupledDynamic -- see
    docs/findings/rumoca-algebraic-loop-bug.md) should track the
    continuous analytical solution V_C(t) = V0*(1-exp(-t/(R*C))) closely.
    A generous tolerance is used because Rumoca's solver and this
    project's fixed-step forward Euler are DIFFERENT integration schemes
    and are not expected to agree beyond the continuous solution both
    approximate."""
    import math

    import rumoca as rm

    session = rm.Session(roots=ROOTS)
    m = session.load(MODEL_PATH, model="MslRcCircuit")
    result = m.simulate(t=(0, 3), dt=0.5)
    df = result.to_dataframe()

    V0, R, C = 5.0, 100.0, 0.01
    for t, row in df.iterrows():
        expected = V0 * (1 - math.exp(-t / (R * C)))
        assert abs(row["C.v"] - expected) < 0.05, f"at t={t}, Rumoca gave {row['C.v']}, analytical is {expected}"
