import json
import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from causal_graph import build_causalized_graph
from graph import build_dependency_graph

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


def eq_scc_sizes(g: nx.DiGraph) -> list[int]:
    sizes = [len([n for n in scc if n[0] == "eq"]) for scc in nx.strongly_connected_components(g)]
    return sorted((s for s in sizes if s > 0), reverse=True)


def test_decoupled_pair_causalized_graph_unchanged():
    """No states depend on each other's algebraic outputs here, so
    causalization should not change anything."""
    ir = load_ir("DecoupledPair")
    raw = eq_scc_sizes(build_dependency_graph(ir))
    causal = eq_scc_sizes(build_causalized_graph(ir))
    assert raw == causal == [1, 1]


def test_rlc_circuit_causalization_removes_the_integration_artifact():
    """Phase 1's {i, v} coupling was purely the integration edge (each
    state depends on the other's CURRENT value, not a simultaneous
    algebraic solve). Causalizing (states as knowns) must reduce it to
    all-singleton, matching Model.structure()'s algebraic_loops=0."""
    ir = load_ir("RLCCircuit")
    raw = eq_scc_sizes(build_dependency_graph(ir))
    causal = eq_scc_sizes(build_causalized_graph(ir))
    assert raw == [2, 1]
    assert causal == [1, 1, 1]


def test_thermal_network_causalization_removes_the_collapse():
    """The phase-1 8-equation collapse must disappear entirely once states
    are treated as knowns, matching Model.structure()'s 9 blocks / 0
    algebraic loops for this model."""
    ir = load_ir("ThermalNetwork")
    raw = eq_scc_sizes(build_dependency_graph(ir))
    causal = eq_scc_sizes(build_causalized_graph(ir))
    assert raw == [8, 1]
    assert causal == [1] * 9


@pytest.mark.parametrize("model_name", ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork"])
def test_causalized_der_targets_are_never_read(model_name):
    """A ("der", name) node must never be read by any equation -- states
    are knowns each timestep, so nothing in the per-timestep graph should
    depend on a freshly-computed derivative."""
    ir = load_ir(model_name)
    g = build_causalized_graph(ir)
    for node in g.nodes:
        if node[0] == "der":
            assert list(g.successors(node)) == [], f"{node} has outgoing edges, should be a sink"
