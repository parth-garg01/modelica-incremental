"""Recompilation units on the causalized graph (Section 4, Feature G1).

Phase 1 defined a recompilation unit as the equation-only membership of
an SCC of the *raw* dependency graph (src/graph.py), which spuriously
merges any state whose derivative equation reads an algebraic variable
that is itself a function of that same state -- confirmed in D1/D2 to be
an integration artifact, not real coupling, for every current fixture.

The fix is definitional, not a new algorithm: `compute_units` (src/units.py)
already operates on any equation/variable digraph, filtering to ("eq", *)
nodes per SCC -- it works unchanged on the causalized graph
(src/causal_graph.py), which is what this module wires up as the new
default. A ("der", name) node is a pure sink (Feature D1), so it can
never join an SCC with more than one equation; the only way two
equations can now land in the same unit is a genuine simultaneous
algebraic dependency, not an integration edge.
"""
from __future__ import annotations

from causal_graph import build_causalized_graph
from units import compute_units, equation_to_unit


def compute_causal_units(ir: dict) -> dict[str, list[str]]:
    return compute_units(build_causalized_graph(ir))


if __name__ == "__main__":
    import json
    from pathlib import Path

    import graph as raw_graph_module
    import units as units_module

    FIXTURES = Path("results/fixtures")
    for model_name in ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork"]:
        ir = json.loads((FIXTURES / f"{model_name}.json").read_text())
        raw_units = units_module.compute_units(raw_graph_module.build_dependency_graph(ir))
        causal_units = compute_causal_units(ir)
        print(f"{model_name}: raw_unit_count={len(raw_units)} -> causal_unit_count={len(causal_units)}")
        print(f"  raw:    {sorted(raw_units.keys())}")
        print(f"  causal: {sorted(causal_units.keys())}")
