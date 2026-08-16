import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from units import compute_units

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"

MODELS = ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork", "Chain",
          "CoupledAlgebraic", "CoupledDynamic", "MslRcCircuit"]


@pytest.mark.parametrize("model_name", MODELS)
def test_scc_over_matched_graph_equals_matched_units_directly(model_name):
    ir = json.loads((FIXTURES / f"{model_name}.json").read_text())
    via_matching = compute_matched_units(ir)
    via_graph = compute_units(build_matched_graph(ir))
    assert via_matching == via_graph
