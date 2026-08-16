"""Feature 7: full change-type suite (component swap, sensor add,
component removal) on real implicit-equation models, through the whole
detect (seed), resolve, and bit-diff path. Soundness verified against
the independently-computed diff (src/soundness.py, now matching-based --
see Feature 7's soundness.py generalization), each with a teeth check.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from c_build import compile_c, link, run_sim
from compile import compile_model
from matched_graph import build_matched_graph
from model_layout import build_layout
from resolver import resolve_impact
from soundness import check_soundness
from unit_codegen import write_unit_sources

BUILD_ROOT = Path(__file__).resolve().parent.parent / "build_test" / "msl_change_types"


@pytest.fixture(autouse=True)
def _clean_build_dir():
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    yield
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)


def _build_and_run(path, model_name, roots, t_end, dt):
    result = compile_model(path, model_name, roots=roots)
    layout = build_layout(result.ir)
    src_dir = BUILD_ROOT / model_name / "src"
    written = write_unit_sources(model_name, result.ir, layout, src_dir)
    build_dir = BUILD_ROOT / model_name / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    objs = []
    for key, p in written.items():
        if key == "header":
            continue
        o_path = build_dir / (p.stem + ".o")
        compile_c(p, o_path)
        objs.append(o_path)
    exe = build_dir / f"{model_name}.exe"
    link(objs, exe)
    return run_sim(exe, t_end, dt)

MSL_SRC = Path(__file__).resolve().parent.parent / "msl_src"
pytestmark = pytest.mark.skipif(not MSL_SRC.exists(), reason="msl_src/ not present")

CELLS = {
    "swap": dict(
        base_path="models/msl_rc_circuit/MslRcCircuit.mo",
        chg_path="models/msl_rc_circuit_swapped/MslRcCircuit.mo",
        model_name="MslRcCircuit",
        base_roots=["msl_src", "models/msl_rc_circuit"],
        chg_roots=["msl_src", "models/msl_rc_circuit_swapped"],
        seed=["R.G_actual", "R.i"],
    ),
    "sensor-add": dict(
        base_path="models/msl_rc_circuit/MslRcCircuit.mo",
        chg_path="models/msl_rc_circuit_sensor/MslRcCircuit.mo",
        model_name="MslRcCircuit",
        base_roots=["msl_src", "models/msl_rc_circuit"],
        chg_roots=["msl_src", "models/msl_rc_circuit_sensor"],
        seed=["P_R"],
    ),
    "removal": dict(
        base_path="models/msl_resistor_network/MslResistorNetwork.mo",
        chg_path="models/msl_resistor_network_removed/MslResistorNetwork.mo",
        model_name="MslResistorNetwork",
        base_roots=["msl_src", "models/msl_resistor_network"],
        chg_roots=["msl_src", "models/msl_resistor_network_removed"],
        seed=["G.p.i", "R1.p.i", "V.n.v"],
    ),
}


def _compile_pair(cell):
    baseline = compile_model(cell["base_path"], cell["model_name"], roots=cell["base_roots"])
    changed = compile_model(cell["chg_path"], cell["model_name"], roots=cell["chg_roots"])
    return baseline, changed


@pytest.mark.parametrize("label", CELLS.keys())
def test_change_type_is_sound_on_real_model(label):
    cell = CELLS[label]
    baseline, changed = _compile_pair(cell)
    impact = resolve_impact(changed.ir, cell["seed"], graph_builder=build_matched_graph)
    result = check_soundness(baseline.ir, changed.ir, impact, graph_builder=build_matched_graph)
    assert result["sound"] is True, f"{label}: missed {result['missed_units']}"
    assert result["missed_units"] == []


@pytest.mark.parametrize("label", CELLS.keys())
def test_change_type_soundness_has_teeth(label):
    """Empty seed (simulated missed detector signal) must be caught as
    unsound on every one of the three real-model change types, not just
    the hand-written fixtures from earlier phases."""
    cell = CELLS[label]
    baseline, changed = _compile_pair(cell)
    broken_impact = resolve_impact(changed.ir, [], graph_builder=build_matched_graph)
    result = check_soundness(baseline.ir, changed.ir, broken_impact, graph_builder=build_matched_graph)
    assert result["sound"] is False
    assert len(result["missed_units"]) > 0


def test_swap_seed_needs_the_newly_introduced_variable_too():
    """Regression-documenting test: seeding only with R.i (the visibly
    edited equation) is NOT sufficient for the Resistor->Conductor swap
    -- Conductor introduces a genuinely NEW derived quantity
    (R.G_actual, replacing Resistor's R.R_actual) that must also be
    seeded, or soundness fails. Confirmed this during development
    (missed=['R.G_actual'] with seed=['R.i'] alone); kept as a permanent
    regression test. Same lesson as the (abandoned, see
    src/msl_change.py's docstring) voltage-source swap attempt: swapping
    a component for a DIFFERENT one of the same kind can introduce
    equations with no counterpart in the baseline at all, not just edit
    an existing one -- a real detector would need to report the new
    equation's identity too, not just "the swapped component changed"."""
    cell = CELLS["swap"]
    baseline, changed = _compile_pair(cell)
    incomplete_impact = resolve_impact(changed.ir, ["R.i"], graph_builder=build_matched_graph)
    result = check_soundness(baseline.ir, changed.ir, incomplete_impact, graph_builder=build_matched_graph)
    assert result["sound"] is False
    assert "R.G_actual" in result["missed_units"]


def test_removal_leaves_no_dangling_reference_and_ripple_is_moderate():
    cell = CELLS["removal"]
    baseline, changed = _compile_pair(cell)
    all_names = set(changed.ir["y"].keys()) | set(changed.ir["x"].keys())
    assert not any(n.startswith("R3.") for n in all_names)

    impact = resolve_impact(changed.ir, cell["seed"], graph_builder=build_matched_graph)
    ripple = len(impact["affected_units"]) / impact["total_units"]
    assert 0.0 < ripple < 1.0  # a real, non-trivial, non-total ripple


def test_sensor_add_output_satisfies_the_power_identity_exactly():
    """Real compile+run: P_R must equal R.v*R.i at every timestep, an
    exact algebraic identity (not an approximation), checked against the
    actual compiled binary's own other two columns -- not a separately
    hand-derived value, so this can't pass by coincidence."""
    output = _build_and_run(
        "models/msl_rc_circuit_sensor/MslRcCircuit.mo", "MslRcCircuit",
        ["msl_src", "models/msl_rc_circuit_sensor"], 3.0, 0.5,
    )
    lines = output.strip().splitlines()
    header = lines[0].split(",")
    rv_idx, ri_idx = header.index("R.v"), header.index("R.i")
    pr_idx = header.index("P_R")
    for line in lines[1:]:
        row = [float(v) for v in line.split(",")]
        assert abs(row[pr_idx] - row[rv_idx] * row[ri_idx]) < 1e-9


def test_removal_output_matches_hand_computed_reduced_divider():
    """With R3 removed, the divider is a plain series R1+R2: V=10,
    R1=100, R2=200, total=300 => I=0.03333..., V_R2=I*200=6.6667...
    (up from the pre-removal V_R2=5.4545... with R3 in parallel -- a
    real, verifiable change in circuit behavior, not just structure)."""
    output = _build_and_run(
        "models/msl_resistor_network_removed/MslResistorNetwork.mo", "MslResistorNetwork",
        ["msl_src", "models/msl_resistor_network_removed"], 1.0, 1.0,
    )
    lines = output.strip().splitlines()
    header = lines[0].split(",")
    row = [float(v) for v in lines[1].split(",")]
    values = dict(zip(header, row))
    assert abs(abs(values["R2.v"]) - 6.666667) < 1e-4
    assert abs(abs(values["R1.v"]) - 3.333333) < 1e-4
