import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ir_equations import equation_target, equation_targets

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


def test_thermal_network_targets_are_not_dict_key_order():
    """This is the phase-1 bug this module fixes: f_x is ordered by
    equation appearance, not by ir["y"]/ir["x"] dict-key (declaration)
    order. Confirm the two orders actually differ for this model, so this
    test would have caught the original positional-zip bug."""
    ir = load_ir("ThermalNetwork")
    dict_key_order = list(ir["y"].keys()) + list(ir["x"].keys())
    content_order = [name for _, name, _ in equation_targets(ir)]
    assert content_order != dict_key_order
    assert content_order == ["Q1", "Q1env", "Q2env", "Q3env", "Q12", "Q23", "T1", "T2", "T3"]


@pytest.mark.parametrize("model_name", ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork"])
def test_targets_exactly_match_declared_variables(model_name):
    ir = load_ir(model_name)
    results = equation_targets(ir)  # raises internally if targets don't match ir["y"]/ir["x"]
    assert len(results) == len(ir["y"]) + len(ir["x"])


def test_equation_target_rejects_an_equation_with_no_recognizable_target():
    with pytest.raises(ValueError):
        equation_target({"lhs": None, "rhs": {"Literal": {"value": {"Real": 1.0}}}})
