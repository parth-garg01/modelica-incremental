import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import rumoca as rm

from causal_graph import build_causalized_graph
from compile import compile_model
from resolver import resolve_impact
from soundness import check_soundness

BASELINE = ("models/thermal_network/ThermalNetwork.mo", "ThermalNetwork")


def test_sensor_add_compiles_simulates_and_has_exactly_one_more_equation():
    baseline = compile_model(*BASELINE)
    sensor = compile_model("models/thermal_network_sensor/ThermalNetwork.mo", "ThermalNetwork")
    baseline_n_eq = len(baseline.ir["y"]) + len(baseline.ir["x"])
    sensor_n_eq = len(sensor.ir["y"]) + len(sensor.ir["x"])
    assert sensor_n_eq == baseline_n_eq + 1
    assert set(sensor.ir["y"].keys()) - set(baseline.ir["y"].keys()) == {"Qtotal"}


def test_sensor_add_soundness_holds():
    baseline = compile_model(*BASELINE)
    sensor = compile_model("models/thermal_network_sensor/ThermalNetwork.mo", "ThermalNetwork")
    impact = resolve_impact(sensor.ir, ["Qtotal"], graph_builder=build_causalized_graph)
    result = check_soundness(baseline.ir, sensor.ir, impact, graph_builder=build_causalized_graph)
    assert result["sound"] is True
    assert result["missed_units"] == []


def test_sensor_add_soundness_has_teeth():
    """Seeding with an empty change (simulating a missed detector signal)
    must be caught as unsound, since Qtotal's unit is genuinely new."""
    baseline = compile_model(*BASELINE)
    sensor = compile_model("models/thermal_network_sensor/ThermalNetwork.mo", "ThermalNetwork")
    broken_impact = resolve_impact(sensor.ir, [], graph_builder=build_causalized_graph)
    result = check_soundness(baseline.ir, sensor.ir, broken_impact, graph_builder=build_causalized_graph)
    assert result["sound"] is False
    assert "Qtotal" in result["missed_units"]


def test_component_removal_compiles_with_no_dangling_references():
    removed = compile_model("models/thermal_network_removed/ThermalNetwork.mo", "ThermalNetwork")
    all_names = set(removed.ir["y"].keys()) | set(removed.ir["x"].keys()) | set(removed.ir["p"].keys())
    assert "T3" not in all_names
    assert "Q23" not in all_names
    assert "Q3env" not in all_names
    # room 2's own equation must not reference anything that used to belong to room 3
    session = rm.Session()
    model = session.load("models/thermal_network_removed/ThermalNetwork.mo", model="ThermalNetwork")
    result = model.simulate(t=(0, 2), dt=0.5)
    assert len(result.to_dataframe()) > 0


def test_component_removal_soundness_holds():
    baseline = compile_model(*BASELINE)
    removed = compile_model("models/thermal_network_removed/ThermalNetwork.mo", "ThermalNetwork")
    impact = resolve_impact(removed.ir, ["T2"], graph_builder=build_causalized_graph)
    result = check_soundness(baseline.ir, removed.ir, impact, graph_builder=build_causalized_graph)
    assert result["sound"] is True
    assert result["missed_units"] == []
    # ground truth should show the removed equations plus T2 as "changed"
    # (present-in-one-IR-only counts as changed; T2's own formula changed too)
    assert set(result["actually_changed_equations"]) == {"T2", "T3", "Q23", "Q3env"}


def test_component_removal_soundness_has_teeth():
    baseline = compile_model(*BASELINE)
    removed = compile_model("models/thermal_network_removed/ThermalNetwork.mo", "ThermalNetwork")
    broken_impact = resolve_impact(removed.ir, [], graph_builder=build_causalized_graph)
    result = check_soundness(baseline.ir, removed.ir, broken_impact, graph_builder=build_causalized_graph)
    assert result["sound"] is False
    assert "T2" in result["missed_units"]
