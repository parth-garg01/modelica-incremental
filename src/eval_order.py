"""Topological evaluation order for algebraic equations, from the
causalized graph. States don't need ordering (they're knowns each step,
supplied by the integrator); algebraic equations that read other
algebraic equations' outputs must be evaluated after them.
"""
from __future__ import annotations

import networkx as nx

from causal_graph import build_causalized_graph
from matched_units import compute_matched_units
from matching import compute_matching


def unit_eval_order(ir: dict) -> list[str]:
    """Feature 4's general version of algebraic_eval_order below: works
    over RECOMPILATION UNITS (src/matched_units.py -- possibly coupled
    multi-equation blocks), not individual equations, so it is well-
    defined for models with a genuine coupled block (algebraic_eval_order
    would see a graph cycle there and correctly refuse). Every block is
    either a single state's own row or one-or-more algebraic equations --
    states are never part of a coupled block by construction
    (src/matching.py excludes them from the bipartite candidate pool
    entirely) -- so only algebraic units need ordering; state units are
    always evaluated last, after every algebraic unit, using already-
    known current state values."""
    m = compute_matching(ir)
    units = compute_matched_units(ir)
    states = set(ir["x"].keys())

    var_to_unit = {name: uid for uid, members in units.items() for name in members}
    algebraic_units = [uid for uid, members in units.items() if not (set(members) & states)]

    g = nx.DiGraph()
    g.add_nodes_from(algebraic_units)
    for uid in algebraic_units:
        member_indices = [m.var_to_eq[name] for name in units[uid]]
        reads: set[str] = set()
        for i in member_indices:
            reads |= m.eq_involves[i]
        reads -= set(units[uid])  # self-references within the block aren't cross-unit deps
        reads -= states           # states are knowns; no ordering edge needed
        for r in reads:
            other_unit = var_to_unit.get(r)
            if other_unit and other_unit != uid:
                g.add_edge(other_unit, uid)

    try:
        return list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as e:
        raise ValueError(
            "algebraic units have a cross-unit cycle -- topological evaluation "
            "order does not exist; this would mean src/matched_units.py failed "
            "to merge a genuinely coupled cluster into one block"
        ) from e


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
