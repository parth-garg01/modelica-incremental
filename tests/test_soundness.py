import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from compile import compile_model
from resolver import resolve_impact
from soundness import check_soundness

CELLS = [
    ("models/rlc_circuit/RLCCircuit.mo", "models/rlc_circuit_swapped/RLCCircuit.mo", "RLCCircuit", ["i"]),
    ("models/thermal_network/ThermalNetwork.mo", "models/thermal_network_swapped/ThermalNetwork.mo",
     "ThermalNetwork", ["Q1"]),
]


def _result(baseline_path, changed_path, model_name, seed):
    baseline = compile_model(baseline_path, model_name)
    changed = compile_model(changed_path, model_name)
    impact = resolve_impact(changed.ir, seed)
    return check_soundness(baseline.ir, changed.ir, impact)


def test_rlc_circuit_resolver_is_sound():
    result = _result(*CELLS[0])
    assert result["sound"]
    assert result["missed_units"] == []


def test_thermal_network_resolver_is_sound():
    result = _result(*CELLS[1])
    assert result["sound"]
    assert result["missed_units"] == []


def test_ground_truth_finds_exactly_the_edited_equation():
    """The independent IR diff (not the resolver) should find precisely the
    equation each change injector edited, nothing more or less."""
    result = _result(*CELLS[0])
    assert result["actually_changed_equations"] == ["i"]
    result = _result(*CELLS[1])
    assert result["actually_changed_equations"] == ["Q1"]


def test_soundness_check_catches_an_under_reporting_resolver():
    """Teeth check: simulate a detector that missed the change entirely
    (empty seed set, a realistic failure mode -- e.g. a change-point
    detector that never fires). The soundness check must flag this as
    unsound, since the actually-changed unit is not covered."""
    baseline_path, changed_path, model_name, _real_seed = CELLS[0]
    baseline = compile_model(baseline_path, model_name)
    changed = compile_model(changed_path, model_name)

    broken_impact = resolve_impact(changed.ir, [])  # no seed -> resolver predicts nothing
    result = check_soundness(baseline.ir, changed.ir, broken_impact)

    assert result["sound"] is False
    assert result["missed_units"] == ["i+v"]
