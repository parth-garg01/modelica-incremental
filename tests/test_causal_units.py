import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from causal_units import compute_causal_units

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"
MODEL_NAMES = ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork"]


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


def all_equation_names(ir: dict) -> set[str]:
    return set(ir["y"].keys()) | set(ir["x"].keys())


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_causal_units_cover_every_equation_exactly_once(model_name):
    ir = load_ir(model_name)
    units = compute_causal_units(ir)
    covered = [eq for members in units.values() for eq in members]
    assert set(covered) == all_equation_names(ir)
    assert len(covered) == len(set(covered))


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_causal_unit_ids_stable_across_reruns(model_name):
    ir = load_ir(model_name)
    a = compute_causal_units(ir)
    b = compute_causal_units(ir)
    assert set(a.keys()) == set(b.keys())


def test_thermal_network_unit_count_increases_relative_to_raw():
    """The headline granularity-fix result: phase 1's 2-unit ThermalNetwork
    partition (an 8-equation blob plus a singleton) becomes 9 singleton
    units once units are defined on the causalized graph."""
    ir = load_ir("ThermalNetwork")
    units = compute_causal_units(ir)
    assert len(units) == 9
    assert all(len(members) == 1 for members in units.values())


def test_rlc_circuit_unit_count_increases_relative_to_raw():
    """Phase 1's {i, v} coupled unit was also an integration artifact;
    causalized units for RLCCircuit are all singletons (3, up from 2)."""
    ir = load_ir("RLCCircuit")
    units = compute_causal_units(ir)
    assert len(units) == 3
    assert all(len(members) == 1 for members in units.values())
