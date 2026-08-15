"""Recompilation units: strongly-connected components of the dependency
graph, restricted to their equation members.

A recompilation unit is the smallest set of equations that would have to
be recompiled together, because they are mutually data-dependent through
the variables they read and write. A variable-only SCC (a variable that
participates in no feedback loop) is not itself a unit -- units are
equation sets, with the graph used only to discover which equations are
coupled.

The unit id is the equations' own names joined and sorted, so ids are
stable across re-runs on an unchanged model: no synthetic counters, no
insertion-order dependence.
"""
from __future__ import annotations

import networkx as nx


def compute_units(g: nx.DiGraph) -> dict[str, list[str]]:
    units: dict[str, list[str]] = {}
    for scc in nx.strongly_connected_components(g):
        eq_names = sorted(n[1] for n in scc if n[0] == "eq")
        if not eq_names:
            continue
        unit_id = "+".join(eq_names)
        units[unit_id] = eq_names
    return units


def equation_to_unit(units: dict[str, list[str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for unit_id, eq_names in units.items():
        for eq_name in eq_names:
            mapping[eq_name] = unit_id
    return mapping


if __name__ == "__main__":
    import json
    import sys

    from graph import build_dependency_graph

    path = sys.argv[1] if len(sys.argv) > 1 else "results/fixtures/RLCCircuit.json"
    ir = json.loads(open(path).read())
    g = build_dependency_graph(ir)
    units = compute_units(g)
    print(f"{len(units)} units:")
    for unit_id, members in units.items():
        print(f"  {unit_id}: {members}")
