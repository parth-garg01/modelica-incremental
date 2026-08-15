"""Topological evaluation order for algebraic equations, from the
causalized graph. States don't need ordering (they're knowns each step,
supplied by the integrator); algebraic equations that read other
algebraic equations' outputs must be evaluated after them.
"""
from __future__ import annotations

import networkx as nx

from causal_graph import build_causalized_graph


def algebraic_eval_order(ir: dict) -> list[str]:
    g = build_causalized_graph(ir)
    y_names = list(ir["y"].keys())

    # Subgraph of just the algebraic equation nodes, with an edge a -> b
    # meaning "b reads a's output" (b must be evaluated after a).
    sub = nx.DiGraph()
    sub.add_nodes_from(y_names)
    for a in y_names:
        for succ in g.successors(("var", a)):
            if succ[0] == "eq" and succ[1] in y_names:
                sub.add_edge(a, succ[1])

    try:
        return list(nx.topological_sort(sub))
    except nx.NetworkXUnfeasible as e:
        raise ValueError(
            "algebraic equations have a real cycle -- topological evaluation "
            "order does not exist; this model needs Feature G2's tearing "
            "refinement, not this simple sequential evaluator"
        ) from e
