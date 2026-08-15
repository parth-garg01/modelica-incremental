import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from graph import build_dependency_graph
from units import compute_units

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"

MODEL_NAMES = ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork"]


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


def all_equation_names(ir: dict) -> set[str]:
    return set(ir["y"].keys()) | set(ir["x"].keys())


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_units_cover_every_equation_exactly_once(model_name):
    ir = load_ir(model_name)
    g = build_dependency_graph(ir)
    units = compute_units(g)

    covered = [eq for members in units.values() for eq in members]
    assert set(covered) == all_equation_names(ir)
    assert len(covered) == len(set(covered)), "an equation appears in more than one unit"


def test_decoupled_model_yields_all_singleton_units():
    ir = load_ir("DecoupledPair")
    g = build_dependency_graph(ir)
    units = compute_units(g)
    assert len(units) == 2
    assert all(len(members) == 1 for members in units.values())


def test_rlc_circuit_groups_the_coupled_pair_together():
    ir = load_ir("RLCCircuit")
    g = build_dependency_graph(ir)
    units = compute_units(g)
    member_sets = [set(m) for m in units.values()]
    assert {"i", "v"} in member_sets
    assert {"Vs"} in member_sets


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_unit_ids_are_stable_across_reruns(model_name):
    ir = load_ir(model_name)
    units_a = compute_units(build_dependency_graph(ir))
    units_b = compute_units(build_dependency_graph(ir))
    assert set(units_a.keys()) == set(units_b.keys())
