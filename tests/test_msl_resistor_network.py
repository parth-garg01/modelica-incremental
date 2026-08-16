"""Second real-MSL-component model (Feature 7's "one more real
standard-library-style model"): a resistor voltage divider whose R2/R3
parallel branch produces a genuine 14-equation LINEAR coupled block
(Model.structure(): blocks=22, algebraic_loops=1) -- a real-world stress
test for Feature 4's linear block solve at a larger scale than the
2-equation CoupledAlgebraic/CoupledDynamic fixtures.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from c_build import compile_c, link, run_sim
from compile import compile_model
from matching import blt_blocks, compute_matching
from model_layout import build_layout
from unit_codegen import write_unit_sources

MODEL_PATH = "models/msl_resistor_network/MslResistorNetwork.mo"
ROOTS = ["msl_src", "models/msl_resistor_network"]
BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_test" / "msl_resistor_network"

MSL_SRC = Path(__file__).resolve().parent.parent / "msl_src"
pytestmark = pytest.mark.skipif(not MSL_SRC.exists(), reason="msl_src/ not present")


@pytest.fixture(autouse=True)
def _clean_build_dir():
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    yield
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)


def test_matching_finds_the_real_coupled_block():
    result = compile_model(MODEL_PATH, "MslResistorNetwork", roots=ROOTS)
    m = compute_matching(result.ir)
    assert m.is_matched is True
    blocks = blt_blocks(result.ir, m)
    assert len(blocks) == 22  # matches Model.structure().n_blocks exactly
    sizes = sorted((len(b) for b in blocks), reverse=True)
    assert sizes[0] == 14  # the genuine R1/R2/R3 coupled block


def test_divider_output_matches_hand_computed_circuit_theory():
    """V=10V, R1=100 in series with (R2=200 || R3=300 = 120).
    Total R = 220, I = 10/220 = 0.045454..., V_R1 = I*100 = 4.5454...,
    V_parallel = I*120 = 5.4545... (also matches Rumoca's own static
    solve: R1.v=-4.545454, R2.v=R3.v=-5.454546, sign is a reference-
    direction convention, magnitude is what physics constrains)."""
    result = compile_model(MODEL_PATH, "MslResistorNetwork", roots=ROOTS)
    layout = build_layout(result.ir)
    src_dir = BUILD_ROOT / "src"
    written = write_unit_sources("MslResistorNetwork", result.ir, layout, src_dir)

    build_dir = BUILD_ROOT / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    objs = []
    for key, path in written.items():
        if key == "header":
            continue
        o_path = build_dir / (path.stem + ".o")
        compile_c(path, o_path)
        objs.append(o_path)
    exe = build_dir / "MslResistorNetwork.exe"
    link(objs, exe)
    output = run_sim(exe, 1.0, 1.0)

    lines = output.strip().splitlines()
    header = lines[0].split(",")
    row = lines[1].split(",")
    values = dict(zip(header, (float(v) for v in row)))

    assert abs(abs(values["R1.v"]) - 4.545454) < 1e-4
    assert abs(abs(values["R2.v"]) - 5.454545) < 1e-4
    assert abs(abs(values["R3.v"]) - 5.454545) < 1e-4
    assert abs(values["R2.v"] - values["R3.v"]) < 1e-9  # parallel branch: same voltage
