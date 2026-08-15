"""Build a dependency graph from Rumoca's DAE intermediate representation.

Nodes are equations and variables:
  ("var", name)  a state, algebraic, input, or parameter variable
  ("eq", name)   the equation that defines that variable (the state's
                 derivative equation, for a state; the direct defining
                 equation, for an algebraic variable)

Edges record dependency:
  ("var", r) -> ("eq", name)   equation `name` reads variable r
  ("eq", name) -> ("var", name) equation `name` defines/writes variable name

This is built directly from the DAE `f_x` expression list (one entry per
algebraic variable in `y`, in order, followed by one entry per state in
`x`, in order -- verified against Model.structure().n_equations for every
fixture model). `z`/`f_z` (algebraic-loop variables) are not present in
any fixture model and are treated as an unsupported IR shape rather than
silently ignored.
"""
from __future__ import annotations

import networkx as nx


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
    f_x = ir["f_x"]

    if ir.get("z") or ir.get("f_z"):
        raise NotImplementedError(
            "IR contains algebraic-loop variables (z/f_z); this graph "
            "builder only supports the f_x = [y equations..., x-derivative "
            "equations...] shape verified on the fixture models."
        )

    expected = len(y_names) + len(x_names)
    if len(f_x) != expected:
        raise ValueError(
            f"f_x has {len(f_x)} entries but len(y)+len(x) = {expected}; "
            "the assumed IR ordering does not hold for this model."
        )

    g = nx.DiGraph()
    for name in y_names + x_names + p_names + u_names:
        g.add_node(("var", name))

    targets = [("y", n) for n in y_names] + [("x", n) for n in x_names]
    for (kind, var_name), expr in zip(targets, f_x):
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
