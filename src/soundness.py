"""Soundness validation: check that the graph-based impact resolver's
predicted affected-unit set is a superset of the units that ACTUALLY
changed, where "actually changed" is discovered independently by diffing
the baseline and post-change compiled IR (never by looking at the
resolver's own output).

This is the check the resolver is not allowed to see: if the resolver
under-reports (misses a unit whose compiled content really changed),
this test must catch it.

PHASE 2: `graph_builder` selects which dependency graph check_soundness
uses to independently recompute the ground-truth unit mapping. Defaults
to the raw graph (phase 1 behavior); pass build_causalized_graph to
re-validate against the causalized unit definition (Feature G3); pass
build_matched_graph (Stage A) for real models with anonymous KCL/KVL
residuals, which the raw/causalized graphs cannot process at all.
"""
from __future__ import annotations

from matching import compute_matching

# Position/identity bookkeeping that changes with source-file byte offsets
# and declaration order even when an equation's actual semantics did not
# change (e.g. inserting a new parameter shifts every later def_id). These
# are stripped before comparing two equations' compiled expressions.
_STRIP_KEYS = {"span", "source_span", "start_span", "min_span", "max_span", "nominal_span", "source", "def_id"}


def _strip_identity_metadata(node):
    if isinstance(node, dict):
        return {k: _strip_identity_metadata(v) for k, v in node.items() if k not in _STRIP_KEYS}
    if isinstance(node, list):
        return [_strip_identity_metadata(item) for item in node]
    return node


def actually_changed_equations(baseline_ir: dict, changed_ir: dict) -> set[str]:
    """Ground truth: which equations' compiled expression differs between
    the baseline and post-change IR, ignoring position/identity metadata.
    Equations present in one IR but not the other count as changed too.

    STAGE A: targets come from src/matching.py's bipartite matching
    (`eq_to_var`), not src/ir_equations.equation_targets() (which raises
    on any model with an anonymous KCL/KVL residual -- every real MSL
    model). Proven behavior-preserving on every fully-assignment-form
    fixture by Feature 1's agrees_with_natural_targets() (matching.py's
    assignment is IDENTICAL to equation_targets()'s on those models), so
    this is a strict generalization, not a behavior change, for anything
    already working before Stage A.
    """
    baseline_match = compute_matching(baseline_ir)
    changed_match = compute_matching(changed_ir)
    baseline_eqs = {name: baseline_ir["f_x"][i] for i, name in baseline_match.eq_to_var.items()}
    changed_eqs = {name: changed_ir["f_x"][i] for i, name in changed_match.eq_to_var.items()}

    diffed: set[str] = set()
    for name in set(baseline_eqs) | set(changed_eqs):
        if name not in baseline_eqs or name not in changed_eqs:
            diffed.add(name)
            continue
        if _strip_identity_metadata(baseline_eqs[name]) != _strip_identity_metadata(changed_eqs[name]):
            diffed.add(name)
    return diffed


def check_soundness(baseline_ir: dict, changed_ir: dict, resolver_result: dict, graph_builder=None) -> dict:
    from graph import build_dependency_graph
    from units import compute_units, equation_to_unit

    if graph_builder is None:
        graph_builder = build_dependency_graph

    changed_eq_names = actually_changed_equations(baseline_ir, changed_ir)

    # Units are recomputed independently here, from changed_ir directly --
    # NOT borrowed from resolver_result -- so this ground-truth mapping does
    # not inherit any bug specific to the resolver's own traversal logic.
    g = graph_builder(changed_ir)
    units = compute_units(g)
    eq_to_unit = equation_to_unit(units)

    actually_changed_units = {eq_to_unit[eq] for eq in changed_eq_names if eq in eq_to_unit}
    predicted_units = set(resolver_result["affected_units"])

    missed = actually_changed_units - predicted_units
    return {
        "actually_changed_equations": sorted(changed_eq_names),
        "actually_changed_units": sorted(actually_changed_units),
        "predicted_units": sorted(predicted_units),
        "sound": len(missed) == 0,
        "missed_units": sorted(missed),
    }


if __name__ == "__main__":
    from compile import compile_model
    from resolver import resolve_impact

    for baseline_path, changed_path, model_name, seed in [
        ("models/rlc_circuit/RLCCircuit.mo", "models/rlc_circuit_swapped/RLCCircuit.mo", "RLCCircuit", ["i"]),
        ("models/thermal_network/ThermalNetwork.mo", "models/thermal_network_swapped/ThermalNetwork.mo",
         "ThermalNetwork", ["Q1"]),
    ]:
        baseline = compile_model(baseline_path, model_name)
        changed = compile_model(changed_path, model_name)
        impact = resolve_impact(changed.ir, seed)
        result = check_soundness(baseline.ir, changed.ir, impact)
        print(f"{model_name}:")
        print(f"  actually_changed_equations={result['actually_changed_equations']}")
        print(f"  actually_changed_units={result['actually_changed_units']}")
        print(f"  predicted_units={result['predicted_units']}")
        print(f"  sound={result['sound']} missed_units={result['missed_units']}")
