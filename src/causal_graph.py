"""Causalized dependency graph: states as knowns, not unknowns.

Phase 1's graph (src/graph.py) named a state-derivative equation's write
target after the state itself (("eq","T1") writes ("var","T1")), which is
wrong: a state's derivative equation computes der(T1), not T1. T1's own
value each timestep comes from the integrator (external to this graph),
not from solving the per-timestep algebraic system. By conflating "T1"
and "der(T1)" into one node, phase 1's graph let a state's derivative
equation feed back into anything that reads the state, creating cycles
that do not exist in the real per-timestep computation -- confirmed by
Model.structure(), whose BLT matching already treats states as knowns
and reports 0 algebraic loops for every phase-1 fixture.

This graph fixes that: state-derivative equations write a distinct
("der", name) node, never ("var", name). A state variable node can be
read by any equation (it is a genuine input each timestep) but is never
written within the per-timestep graph, so it can never sit on a cycle.
"""
from __future__ import annotations

import networkx as nx

from ir_equations import equation_targets


def _varrefs(node) -> set[str]:
    names: set[str] = set()

    def rec(o):
        if isinstance(o, dict):
            if "VarRef" in o:
                names.add(o["VarRef"]["name"]["name"])
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for item in o:
                rec(item)

    rec(node)
    return names


def build_causalized_graph(ir: dict) -> nx.DiGraph:
    y_names = list(ir["y"].keys())
    x_names = list(ir["x"].keys())
    p_names = list(ir["p"].keys())
    u_names = list(ir["u"].keys())

    g = nx.DiGraph()
    for name in y_names + x_names + p_names + u_names:
        g.add_node(("var", name))

    for kind, var_name, expr in equation_targets(ir):
        eq_node = ("eq", var_name)
        # A state's own equation defines der(state), a distinct quantity
        # from the state itself -- the state is a known each timestep,
        # supplied by the integrator, not solved for in this graph.
        write_node = ("der", var_name) if kind == "x" else ("var", var_name)
        g.add_node(eq_node, kind=kind)
        g.add_node(write_node)
        g.add_edge(eq_node, write_node)
        for read_name in _varrefs(expr):
            if read_name == "time" or read_name == var_name:
                # Drop the residual-form self-reference: an equation's own
                # defined quantity referencing itself is bookkeeping, not
                # a real dependency, and for a state this specifically
                # excludes the "integration edge" (state depending on its
                # own derivative) that Cause A identifies as the artifact.
                continue
            g.add_node(("var", read_name))
            g.add_edge(("var", read_name), eq_node)

    return g


if __name__ == "__main__":
    import json
    import sys

    from graph import build_dependency_graph
    from units import compute_units

    path = sys.argv[1] if len(sys.argv) > 1 else "results/fixtures/ThermalNetwork.json"
    ir = json.loads(open(path).read())

    raw_g = build_dependency_graph(ir)
    causal_g = build_causalized_graph(ir)

    raw_sccs = sorted((len([n for n in scc if n[0] == "eq"]) for scc in nx.strongly_connected_components(raw_g)), reverse=True)
    causal_sccs = sorted((len([n for n in scc if n[0] == "eq"]) for scc in nx.strongly_connected_components(causal_g)), reverse=True)
    raw_sccs = [s for s in raw_sccs if s > 0]
    causal_sccs = [s for s in causal_sccs if s > 0]

    print(f"{path}")
    print(f"  raw graph:      largest SCC (by #eqs) = {max(raw_sccs, default=0)}, sizes = {raw_sccs}")
    print(f"  causalized graph: largest SCC (by #eqs) = {max(causal_sccs, default=0)}, sizes = {causal_sccs}")
