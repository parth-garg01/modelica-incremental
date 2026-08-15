"""Graph-based impact resolver.

Given a change, expressed as the names of the equations whose defining
formula was directly edited (the "seed" equations -- known because the
change injector authored the edit, not discovered by diffing), predict
the set of recompilation units affected by following dependency edges
outward from those equations in the POST-CHANGE dependency graph.

This is deliberately not computed from a before/after IR diff. Diffing
tells you what actually changed, which is exactly the ground truth used
to check this resolver in the soundness test (Feature 10) -- using it
here would make the resolver circular and prove nothing.
"""
from __future__ import annotations

import networkx as nx

from graph import build_dependency_graph
from units import compute_units, equation_to_unit


def resolve_impact(post_change_ir: dict, seed_equation_names: list[str]) -> dict:
    g = build_dependency_graph(post_change_ir)
    units = compute_units(g)
    eq_to_unit = equation_to_unit(units)

    affected_eq_names: set[str] = set()
    for seed in seed_equation_names:
        seed_node = ("eq", seed)
        if seed_node not in g:
            raise ValueError(f"seed equation {seed!r} not found in the post-change graph")
        affected_eq_names.add(seed)
        for node in nx.descendants(g, seed_node):
            if node[0] == "eq":
                affected_eq_names.add(node[1])

    affected_units = {eq_to_unit[eq] for eq in affected_eq_names}

    return {
        "seed_equations": sorted(seed_equation_names),
        "affected_equations": sorted(affected_eq_names),
        "affected_units": sorted(affected_units),
        "total_units": len(units),
        "units": units,
    }


if __name__ == "__main__":
    from compile import compile_model

    for source_path, model_name, seed in [
        ("models/thermal_network_swapped/ThermalNetwork.mo", "ThermalNetwork", ["Q1"]),
        ("models/rlc_circuit_swapped/RLCCircuit.mo", "RLCCircuit", ["i"]),
    ]:
        result = compile_model(source_path, model_name)
        impact = resolve_impact(result.ir, seed)
        print(f"{model_name} (seed={seed}):")
        print(f"  total_units={impact['total_units']} "
              f"affected_units={impact['affected_units']}")
        print(f"  affected_equations={impact['affected_equations']}")
