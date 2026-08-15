"""Collapse diagnostic: for every fixture, report the strongly-connected-
component size distribution in the raw graph and the causalized graph,
and classify every large (size > 1) block as an integration artifact
(shrinks to singletons once states are treated as knowns) or a genuine
algebraic loop (a block of size > 1 survives causalization).
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from causal_graph import build_causalized_graph
from graph import build_dependency_graph

FIXTURES = Path("results/fixtures")
FIXTURE_MODELS = ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork"]


def _eq_scc_sizes(g: nx.DiGraph) -> list[int]:
    sizes = [len([n for n in scc if n[0] == "eq"]) for scc in nx.strongly_connected_components(g)]
    return sorted((s for s in sizes if s > 0), reverse=True)


def diagnose(ir: dict) -> dict:
    raw_sizes = _eq_scc_sizes(build_dependency_graph(ir))
    causal_sizes = _eq_scc_sizes(build_causalized_graph(ir))

    raw_largest = raw_sizes[0] if raw_sizes else 0
    causal_largest = causal_sizes[0] if causal_sizes else 0

    if raw_largest <= 1:
        verdict = "no-coupling"
    elif causal_largest <= 1:
        verdict = "integration-artifact"
    elif causal_largest < raw_largest:
        verdict = "partially-genuine-algebraic-loop"
    else:
        verdict = "genuine-algebraic-loop"

    return {
        "raw_scc_sizes": raw_sizes,
        "causal_scc_sizes": causal_sizes,
        "raw_largest": raw_largest,
        "causal_largest": causal_largest,
        "verdict": verdict,
    }


def main() -> None:
    for model_name in FIXTURE_MODELS:
        ir = json.loads((FIXTURES / f"{model_name}.json").read_text())
        result = diagnose(ir)
        print(f"{model_name}:")
        print(f"  raw SCC sizes (eqs)={result['raw_scc_sizes']}, largest={result['raw_largest']}")
        print(f"  causal SCC sizes (eqs)={result['causal_scc_sizes']}, largest={result['causal_largest']}")
        print(f"  verdict: {result['verdict']}")


if __name__ == "__main__":
    main()
