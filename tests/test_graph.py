import json
import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from graph import build_dependency_graph

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"


def load_graph(model_name: str) -> nx.DiGraph:
    ir = json.loads((FIXTURES / f"{model_name}.json").read_text())
    return build_dependency_graph(ir)


def test_decoupled_pair_hand_checked_reachability():
    """x1 and x2 are independent; k1 must only reach the x1 branch."""
    g = load_graph("DecoupledPair")
    reachable = nx.descendants(g, ("var", "k1"))
    assert reachable == {("eq", "x1"), ("var", "x1")}


def test_decoupled_pair_no_cross_branch_edges():
    g = load_graph("DecoupledPair")
    assert not nx.has_path(g, ("eq", "x1"), ("eq", "x2"))
    assert not nx.has_path(g, ("eq", "x2"), ("eq", "x1"))


def test_rlc_circuit_hand_checked_reachability():
    """v feeds both di/dt (v appears in the loop equation) and its own
    equation; it does not reach Vs, since Vs only depends on time-varying
    source parameters, not on the circuit state."""
    g = load_graph("RLCCircuit")
    reachable = nx.descendants(g, ("var", "v"))
    assert reachable == {("eq", "i"), ("eq", "v"), ("var", "i")}
    assert ("eq", "Vs") not in reachable


def test_rlc_circuit_node_and_edge_counts():
    """Hand count: vars = {Vs, i, v, R, L, C, Vamp, omega} (8), eqs = {Vs, i, v} (3)."""
    g = load_graph("RLCCircuit")
    var_nodes = [n for n in g.nodes if n[0] == "var"]
    eq_nodes = [n for n in g.nodes if n[0] == "eq"]
    assert len(var_nodes) == 8
    assert len(eq_nodes) == 3


@pytest.mark.parametrize("model_name", ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork"])
def test_every_equation_has_exactly_one_defining_node(model_name):
    g = load_graph(model_name)
    eq_nodes = [n for n in g.nodes if n[0] == "eq"]
    assert len(eq_nodes) == len(set(eq_nodes))
