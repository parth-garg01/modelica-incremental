import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from causal_graph import build_causalized_graph
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
    impact = resolve_impact(changed.ir, seed, graph_builder=build_causalized_graph)
    return impact, check_soundness(baseline.ir, changed.ir, impact, graph_builder=build_causalized_graph)


def test_rlc_circuit_causal_resolver_is_sound_and_more_local():
    """Granularity-fix result: ripple drops from 1/2 (phase 1, raw graph)
    to 1/3 (causalized), since 'v' is no longer spuriously coupled to 'i'
    through the integration edge."""
    impact, result = _result(*CELLS[0])
    assert result["sound"]
    assert result["missed_units"] == []
    assert impact["total_units"] == 3
    assert impact["affected_units"] == ["i"]


def test_thermal_network_causal_resolver_is_sound_and_dramatically_more_local():
    """The headline granularity-fix result: ripple drops from 1/1 = 100%
    (phase 1, raw graph, the whole model looked like one unit) to 2/9 =
    22% (causalized) -- Q1's unit and the T1 unit it now feeds, nothing
    else."""
    impact, result = _result(*CELLS[1])
    assert result["sound"]
    assert result["missed_units"] == []
    assert impact["total_units"] == 9
    assert sorted(impact["affected_units"]) == ["Q1", "T1"]


def test_causal_soundness_check_catches_an_under_reporting_resolver():
    """Teeth check, same discipline as phase 1's Feature 10: a detector
    that misses the change entirely (empty seed) must be flagged unsound
    against the causalized ground truth too. Note: the content-diff ground
    truth only flags 'Q1' here (its text literally changed; 'T1's own
    formula is byte-identical before/after, even though it needs
    recompiling due to the new coupling) -- that asymmetry is exactly why
    resolve_impact's graph-based propagation exists, rather than relying
    on the content diff alone."""
    baseline_path, changed_path, model_name, _real_seed = CELLS[1]
    baseline = compile_model(baseline_path, model_name)
    changed = compile_model(changed_path, model_name)

    broken_impact = resolve_impact(changed.ir, [], graph_builder=build_causalized_graph)
    result = check_soundness(baseline.ir, changed.ir, broken_impact, graph_builder=build_causalized_graph)

    assert result["sound"] is False
    assert set(result["missed_units"]) == {"Q1"}
