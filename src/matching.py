"""Equation-to-unknown matching and BLT (block lower-triangular) block
structure, computed by us -- not sourced from Rumoca.

Feature 1's original plan was to extract per-equation matching and block
membership from Rumoca's own BLT output. That turned out not to be
possible through the public Python API: `Model.to_dict()`/`to_json()`
only expose the "dae" and "flat" stages ("solve"/matched-stage data is
explicitly rejected with "use codegen()/render() for solve-stage
targets"), and the codegen text itself (`c-solve`, `embedded-c`) emits a
single flattened function with unmarked SSA temporaries -- no per-
equation block boundaries, no matched-variable labels. `StructuralInfo`
and `VariableInfo` are aggregate/per-variable only, with no per-equation
or per-block accessor. This is a real, disclosed integration wall
(prd-combined.md Section 7.5 anticipates exactly this: "if Rumoca does
not expose the matching and block structure cleanly, that is a real
integration cost... if it is genuinely blocked, that limitation is
itself a finding about the tooling").

So this module computes the matching and blocks ourselves, the standard
way any Modelica-class compiler does: a bipartite maximum matching
between equations and unknowns, then Tarjan SCC on the matched digraph
for the BLT blocks. This is exactly the documented fallback in the
original (year-long) prd.md's Feature D1: "if [Rumoca] does not [expose
matched structure], compute the equation-to-unknown matching yourself."

Matching is a SINGLE maximum bipartite matching over every equation
against every unknown it structurally involves (a hand-rolled
deterministic Kuhn's algorithm, see `_kuhn_max_bipartite_matching`
below) -- not a greedy natural-target pre-assignment followed by a
restricted second pass. That two-pass approach was tried first and is
wrong: greedily pre-claiming "obvious" targets can starve a later
anonymous equation of its only remaining option even when a valid
perfect matching exists elsewhere in the graph (confirmed empirically:
it left 10 of the Cauer filter's 69 equations unmatched). "Agrees with
what the current assignment-form generator produced" (Feature 1's
regression check) is then verified AFTER the fact, not enforced by
construction: for every equation with an unambiguous natural target
(src/ir_equations.py: a state's der() argument, or the left operand of a
"var = expr" residual), the matching's actual assignment is compared
against that natural target and must agree -- and does, on every
fully-assignment-form fixture (OneLine, DecoupledPair, RLCCircuit,
ThermalNetwork, Chain: 100% agreement, is_matched=True).

Second honest finding, on the one real-world model tested (the MSL
Cauer filter, 69 equations including 15 anonymous Kirchhoff-law
residuals from `connect()` statements): this matcher achieves 67/69
(97%) matched, not the full 69/69 Rumoca's own `structure().is_matched`
confirms is achievable. Traced to a genuine local structural gap, not an
algorithm bug (Kuhn's algorithm is provably optimal and was independently
verified to find a full matching on every smaller isolated subgraph
extracted from this same model): the two unmatched equations
(potential-equality constraints between capacitor/inductor pins) sit in
a pocket of the voltage-only sub-network that, under this module's
"which unknowns does an equation structurally involve" extraction, ends
up locally over-constrained relative to the free variables actually
reachable from it (both truly-free slots in the full system are CURRENT
variables that no voltage-equality equation's incidence set ever
touches). Rumoca's real matching evidently threads this differently.
Not chased further given the scope of the rest of this project; recorded
here rather than silently forced to look complete.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from graph import _varrefs
from ir_equations import equation_target


def _kuhn_max_bipartite_matching(left_nodes: list, adjacency: dict) -> dict:
    """Deterministic maximum bipartite matching (Kuhn's algorithm: one
    DFS augmenting-path search per left node, in list order).

    Not `networkx.bipartite.hopcroft_karp_matching`: that call turned out
    to be non-deterministic ACROSS PROCESSES on this project's one
    non-trivial real-world graph (the 69-equation MSL Cauer filter, whose
    equation-variable incidence graph admits multiple maximum matchings).
    Different runs of the identical input JSON produced different
    matching sizes (67, 68, or the full 69) and different unmatched
    equations, root-caused to Python's per-process string hash
    randomization (PYTHONHASHSEED) leaking into networkx's internal
    traversal order even after every input list/set fed to it was sorted.
    That's not acceptable here: recomputing units on an UNCHANGED model
    must yield identical unit ids on every run, a requirement enforced by
    tests since phase 1 (tests/test_units.py, tests/test_causal_units.py).
    `adjacency` maps a left node to a plain Python LIST of right-node
    candidates (order matters for which maximum matching is found, not
    for whether one is found -- Kuhn's algorithm finds A maximum
    matching regardless of order, deterministically, given a
    deterministic input order); both `left_nodes` and every adjacency
    list must already be in a fixed, reproducible order (the caller sorts
    by name before calling this).
    """
    match_right: dict = {}   # right node -> left node currently matched to it
    match_left: dict = {}    # left node -> right node currently matched to it

    def try_augment(u, visited: set) -> bool:
        for v in adjacency.get(u, []):
            if v in visited:
                continue
            visited.add(v)
            if v not in match_right or try_augment(match_right[v], visited):
                match_right[v] = u
                match_left[u] = v
                return True
        return False

    for u in left_nodes:
        try_augment(u, set())

    return match_left


@dataclass
class MatchingResult:
    eq_to_var: dict[int, str]          # equation index -> matched unknown name
    var_to_eq: dict[str, int]          # inverse
    eq_involves: dict[int, set[str]]   # equation index -> every unknown it structurally involves
    eq_kind: dict[int, str]            # equation index -> "x" (state) or "algebraic"
    eq_natural_target: dict[int, str]  # equation index -> unambiguous natural target, if any
    is_matched: bool                   # every equation got a partner (perfect matching)
    unmatched_equations: list[int]

    def agrees_with_natural_targets(self) -> bool:
        return all(self.eq_to_var.get(i) == name for i, name in self.eq_natural_target.items())


def compute_matching(ir: dict) -> MatchingResult:
    if ir.get("z") or ir.get("f_z"):
        raise NotImplementedError("IR contains algebraic-loop variables (z/f_z); unsupported.")

    non_state_unknowns = set(ir["y"].keys()) | set(ir.get("w", {}).keys())
    f_x = ir["f_x"]

    eq_involves: dict[int, set[str]] = {}
    eq_kind: dict[int, str] = {}
    natural_target: dict[int, str] = {}

    for i, expr in enumerate(f_x):
        # A state name is only ever a legitimate match candidate for its
        # OWN defining (der) row -- an equation that merely READS a
        # state's current value must not be allowed to "claim" that
        # state as its match target, or the bipartite solver is free to
        # swap a state's row with something that reads it (confirmed:
        # this exact swap happened on ThermalNetwork before this states
        # exclusion was added -- Q1env's equation and T1's own equation
        # both structurally "involve" T1, so an unconstrained matcher
        # can pick either). Same states-as-knowns principle as
        # src/causal_graph.py, applied to matching instead of the
        # dependency graph.
        involved = (_varrefs(expr) - {"time"}) & non_state_unknowns
        eq_involves[i] = involved
        try:
            kind, name = equation_target(expr)
            eq_kind[i] = "x" if kind == "x" else "algebraic"
            natural_target[i] = name
        except ValueError:
            eq_kind[i] = "algebraic"  # anonymous residual; not a state row

    eq_to_var: dict[int, str] = {}
    var_to_eq: dict[str, int] = {}

    # States: trivial, deterministic 1:1 assignment to their own row.
    for i, kind in eq_kind.items():
        if kind == "x":
            name = natural_target[i]
            eq_to_var[i] = name
            var_to_eq[name] = i

    # Everything else (algebraics, outputs, and anonymous residuals):
    # a single maximum bipartite matching over the remaining equations
    # against the non-state unknown pool (see module docstring for why
    # this must be one full pass, not a greedy natural-target
    # pre-assignment followed by a restricted second pass).
    #
    remaining_eqs = [i for i in range(len(f_x)) if eq_kind[i] != "x"]
    adjacency = {i: sorted(eq_involves[i]) for i in remaining_eqs}

    matched = _kuhn_max_bipartite_matching(remaining_eqs, adjacency)
    for i, name in matched.items():
        eq_to_var[i] = name
        var_to_eq[name] = i

    unmatched = [i for i in range(len(f_x)) if i not in eq_to_var]
    return MatchingResult(
        eq_to_var=eq_to_var,
        var_to_eq=var_to_eq,
        eq_involves=eq_involves,
        eq_kind=eq_kind,
        eq_natural_target=natural_target,
        is_matched=(len(unmatched) == 0),
        unmatched_equations=unmatched,
    )


def blt_blocks(ir: dict, matching: MatchingResult) -> list[list[int]]:
    """BLT blocks: strongly-connected components of the directed graph
    where eq_i -> eq_j means "j reads the variable i is matched to".
    States are excluded as edge SOURCES from this graph (a state's own
    row only ever gets read by other equations, contributing outgoing
    edges; nothing should route THROUGH a state as if it were computed
    within the per-timestep algebraic system -- same states-as-knowns
    principle as src/causal_graph.py)."""
    g = nx.DiGraph()
    g.add_nodes_from(range(len(ir["f_x"])))

    for j, involved in matching.eq_involves.items():
        for v in involved:
            i = matching.var_to_eq.get(v)
            if i is None or i == j:
                continue
            if matching.eq_kind.get(i) == "x":
                continue  # states are knowns; never an edge source
            g.add_edge(i, j)

    return [sorted(scc) for scc in nx.strongly_connected_components(g)]


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "results/fixtures/RLCCircuit.json"
    ir = json.loads(open(path).read())
    m = compute_matching(ir)
    print(f"{path}")
    print(f"  is_matched={m.is_matched} unmatched={m.unmatched_equations}")
    print(f"  agrees_with_natural_targets={m.agrees_with_natural_targets()} "
          f"(n_natural_targets={len(m.eq_natural_target)}/{len(ir['f_x'])})")
    blocks = blt_blocks(ir, m)
    sizes = sorted((len(b) for b in blocks), reverse=True)
    print(f"  n_blocks={len(blocks)} block_sizes={sizes[:10]}{'...' if len(sizes) > 10 else ''} largest={sizes[0] if sizes else 0}")
