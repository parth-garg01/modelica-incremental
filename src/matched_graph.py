"""Bridges src/matching.py's matching result into the same bipartite
("eq", name)/("var", name)/("der", name) graph shape src/causal_graph.py
produces, so src/resolver.py and src/soundness.py (both parameterized by
a `graph_builder(ir) -> nx.DiGraph` callable, unchanged since phase 2)
can run over the matching-based partition instead of the SCC-over-
causalized-graph partition -- the one that actually works on real MSL
models with anonymous KCL/KVL residual equations
(src/ir_equations.equation_target(), which causal_graph.py depends on,
raises on those; src/matching.py does not, since it never needs a
"natural target" to determine what an equation structurally involves).

nx.strongly_connected_components(build_matched_graph(ir)) reproduces
src/matched_units.compute_matched_units(ir)'s blocks exactly (verified
in tests/test_matched_graph.py) -- this module exists purely as an
adapter, not a new definition of coupling.
"""
from __future__ import annotations

import networkx as nx

from matching import compute_matching


def build_matched_graph(ir: dict) -> nx.DiGraph:
    m = compute_matching(ir)

    g = nx.DiGraph()
    for i, name in m.eq_to_var.items():
        eq_node = ("eq", name)
        write_node = ("der", name) if m.eq_kind[i] == "x" else ("var", name)
        g.add_node(eq_node, kind=m.eq_kind[i])
        g.add_node(write_node)
        g.add_edge(eq_node, write_node)
        for read_name in m.eq_involves[i]:
            if read_name == name:
                continue
            g.add_node(("var", read_name))
            g.add_edge(("var", read_name), eq_node)

    return g


if __name__ == "__main__":
    import json
    import sys

    from matched_units import compute_matched_units
    from units import compute_units

    path = sys.argv[1] if len(sys.argv) > 1 else "results/fixtures/MslRcCircuit.json"
    ir = json.loads(open(path).read())

    via_matching = compute_matched_units(ir)
    via_graph = compute_units(build_matched_graph(ir))
    print(f"{path}: matched_units={len(via_matching)} graph-scc-units={len(via_graph)} "
          f"identical={via_matching == via_graph}")
