"""Graph-level tests for the phase-2 journal baseline (undirected
incidence closure, states as knowns) and the content-hash oracle.
Rumoca compiles and pure-Python codegen only: nothing here builds or
runs a binary."""
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from compile import compile_model
from journal_naive_resolver import FIXTURE_CELLS, content_hash_oracle, resolve_impact_naive
from matched_graph import build_matched_graph
from measure_msl import CELLS as MSL_CELLS
from resolver import resolve_impact
from soundness import check_soundness

MSL_PRESENT = (ROOT / "msl_src").exists()
CELLS = {c["label"]: c for c in FIXTURE_CELLS}
CELLS.update({f"msl{i}/{c['model_name']}": c for i, c in enumerate(MSL_CELLS)})


@lru_cache(maxsize=None)
def _pair(label):
    c = CELLS[label]
    if c.get("baseline_roots") and not MSL_PRESENT:
        pytest.skip("msl_src/ not present")
    base = compile_model(c["baseline_path"], c["model_name"], roots=c.get("baseline_roots")).ir
    chg = compile_model(c["changed_path"], c["model_name"], roots=c.get("changed_roots")).ir
    return base, chg


@pytest.mark.parametrize("label", CELLS)
def test_naive_baseline_is_sound(label):
    base, chg = _pair(label)
    result = check_soundness(base, chg, resolve_impact_naive(chg, CELLS[label]["seed"]),
                             graph_builder=build_matched_graph)
    assert result["sound"], result["missed_units"]


@pytest.mark.parametrize("label", CELLS)
def test_naive_soundness_has_teeth(label):
    base, chg = _pair(label)
    result = check_soundness(base, chg, resolve_impact_naive(chg, []), graph_builder=build_matched_graph)
    assert not result["sound"]


@pytest.mark.parametrize("label", CELLS)
def test_naive_is_superset_of_matching_method(label):
    """Undirected closure follows every edge the directed matched graph
    has (a matched variable is in its own equation's incidence set) with
    the same state-row cut, so it can only add units, never drop them."""
    _, chg = _pair(label)
    seed = CELLS[label]["seed"]
    paper = set(resolve_impact(chg, seed, graph_builder=build_matched_graph)["affected_units"])
    naive = resolve_impact_naive(chg, seed)
    assert paper <= set(naive["affected_units"])
    weak = resolve_impact_naive(chg, seed, states_as_knowns=False)
    assert set(naive["affected_units"]) <= set(weak["affected_units"])


@pytest.mark.parametrize("label", CELLS)
def test_naive_is_deterministic_and_seed_order_independent(label):
    _, chg = _pair(label)
    seed = CELLS[label]["seed"]
    a = resolve_impact_naive(chg, seed)
    b = resolve_impact_naive(chg, list(reversed(seed)))
    assert a["affected_units"] == b["affected_units"]
    assert a["affected_equations"] == b["affected_equations"]


@pytest.mark.parametrize("label", CELLS)
def test_oracle_is_sound_and_inside_matching_set(label):
    base, chg = _pair(label)
    c = CELLS[label]
    oracle = content_hash_oracle(c["model_name"], base, chg)
    result = check_soundness(base, chg, oracle, graph_builder=build_matched_graph)
    assert result["sound"], result["missed_units"]
    paper = set(resolve_impact(chg, c["seed"], graph_builder=build_matched_graph)["affected_units"])
    assert set(oracle["affected_units"]) <= paper


def test_naive_matches_matching_on_assignment_form_thermal_swap():
    """ThermalNetwork swap: the edited row Q1 = Kp*(Tset - T1) only
    shares Q1 with room 1's state row, which is a sink, so direction adds
    nothing here: both methods give {Q1, T1}."""
    _, chg = _pair("ThermalNetwork/swap")
    assert resolve_impact_naive(chg, ["Q1"])["affected_units"] == ["Q1", "T1"]


def test_naive_pays_for_missing_direction_on_sensor_add():
    """Qtotal = Q1env + Q2env + Q3env: without direction the sensor row
    might write any of the three, so the closure pulls in all three
    producers and their state rows (7 of 10), where the paper's method
    recompiles only Qtotal."""
    _, chg = _pair("ThermalNetwork/sensor-add")
    naive = resolve_impact_naive(chg, ["Qtotal"])["affected_units"]
    assert naive == ["Q1env", "Q2env", "Q3env", "Qtotal", "T1", "T2", "T3"]
