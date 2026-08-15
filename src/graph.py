"""Build a dependency graph from Rumoca's DAE intermediate representation.

Nodes are equations and variables:
  ("var", name)  a state, algebraic, input, or parameter variable
  ("eq", name)   the equation that defines that variable (the state's
                 derivative equation, for a state; the direct defining
                 equation, for an algebraic variable)

Edges record dependency:
  ("var", r) -> ("eq", name)   equation `name` reads variable r
  ("eq", name) -> ("var", name) equation `name` defines/writes variable name

PHASE 2 CORRECTION: phase 1 identified each f_x[i]'s target by *position*,
assuming f_x is ordered as [y in dict-key order] followed by [x in
dict-key order]. That assumption is wrong -- f_x is ordered by equation
appearance in the source, while y/x dict order follows variable
*declaration* order, a different ordering whenever a model's equation
section isn't written in the same order as its declarations (true of
ThermalNetwork). This build now identifies each equation's target from
the equation's own content (src/ir_equations.py), not its position, and
validates the recovered target set against ir["y"]/ir["x"] on every call.
"""
from __future__ import annotations

import networkx as nx

from ir_equations import equation_targets


def _varrefs(node) -> set[str]:
    """Collect every variable name referenced anywhere in an expression tree."""
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


def build_dependency_graph(ir: dict) -> nx.DiGraph:
    y_names = list(ir["y"].keys())
    x_names = list(ir["x"].keys())
    p_names = list(ir["p"].keys())
    u_names = list(ir["u"].keys())

    g = nx.DiGraph()
    for name in y_names + x_names + p_names + u_names:
        g.add_node(("var", name))

    for kind, var_name, expr in equation_targets(ir):
        eq_node = ("eq", var_name)
        g.add_node(eq_node, kind=kind)
        g.add_edge(eq_node, ("var", var_name))
        for read_name in _varrefs(expr):
            if read_name == "time":
                continue
            g.add_node(("var", read_name))
            g.add_edge(("var", read_name), eq_node)

    return g


if __name__ == "__main__":
    import json
    import sys

    ir = json.loads(open(sys.argv[1] if len(sys.argv) > 1 else "results/fixtures/RLCCircuit.json").read())
    g = build_dependency_graph(ir)
    print(f"nodes={g.number_of_nodes()} edges={g.number_of_edges()}")
    for n in g.nodes:
        print(" ", n, "in:", [p for p in g.predecessors(n)], "out:", [s for s in g.successors(n)])
