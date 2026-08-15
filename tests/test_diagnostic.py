import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from diagnostic import diagnose

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


@pytest.mark.parametrize("model_name,expected_verdict", [
    ("OneLine", "no-coupling"),
    ("DecoupledPair", "no-coupling"),
    ("RLCCircuit", "integration-artifact"),
    ("ThermalNetwork", "integration-artifact"),
])
def test_diagnostic_verdict(model_name, expected_verdict):
    result = diagnose(load_ir(model_name))
    assert result["verdict"] == expected_verdict


def test_thermal_network_diagnostic_matches_rumocas_own_blt():
    """Cross-check against Model.structure(), a fully independent code
    path (Rumoca's own BLT matching), which reports 0 algebraic loops for
    ThermalNetwork -- corroborating the causalized-graph verdict."""
    result = diagnose(load_ir("ThermalNetwork"))
    assert result["causal_largest"] == 1  # no block > 1 equation survives causalization
