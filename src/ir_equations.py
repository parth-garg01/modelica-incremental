"""Robustly identify which variable each f_x[i] residual equation defines.

Phase 1 assumed f_x is ordered as [y-equations in dict order] followed by
[x-derivative-equations in dict order], verified only by matching the
total *count* against Model.structure().n_equations. That assumption is
wrong: f_x is ordered by equation appearance in the source, while the y/x
dicts are ordered by variable *declaration* appearance -- two different
orderings whenever a model's equation section isn't written in the same
order as its variable declarations (true of ThermalNetwork, since its
`Real Q1, Q12, Q23, Q1env, Q2env, Q3env;` declaration order differs from
its `Q1 = ...; Q1env = ...; Q2env = ...; Q3env = ...; Q12 = ...; Q23 = ...;`
equation order). Positional zip silently mislabels equations whenever
this happens.

Fixed here by reading the target directly out of each residual
expression's own content instead of assuming a position: a state's
equation is identified by the (exactly one) BuiltinCall{Der} node inside
it, whose argument names the state; an algebraic equation's target is the
left operand of the top-level `lhs - rhs` residual subtraction, which is
a direct VarRef to the variable Rumoca solved that equation for.
"""
from __future__ import annotations

import json


def _find_der_targets(node) -> list[str]:
    names: list[str] = []

    def rec(o):
        if isinstance(o, dict):
            if "BuiltinCall" in o and o["BuiltinCall"].get("function") == "Der":
                for arg in o["BuiltinCall"].get("args", []):
                    if isinstance(arg, dict) and "VarRef" in arg:
                        names.append(arg["VarRef"]["name"]["name"])
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for item in o:
                rec(item)

    rec(node)
    return names


def equation_target(expr: dict) -> tuple[str, str]:
    """Returns (kind, name): kind is "x" for a state-derivative equation,
    "y" for an algebraic equation; name is the variable it defines."""
    der_targets = _find_der_targets(expr)
    if der_targets:
        distinct = set(der_targets)
        if len(distinct) != 1:
            raise ValueError(f"equation has {len(distinct)} distinct der() targets, expected 1: {distinct}")
        return "x", der_targets[0]

    top = expr.get("rhs", {})
    binary = top.get("Binary") if isinstance(top, dict) else None
    if binary and binary.get("op") == "Sub":
        lhs_node = binary.get("lhs")
        if isinstance(lhs_node, dict) and "VarRef" in lhs_node:
            return "y", lhs_node["VarRef"]["name"]["name"]

    raise ValueError(f"could not determine equation target: {json.dumps(expr)[:300]}")


def equation_targets(ir: dict) -> list[tuple[str, str, dict]]:
    """List of (kind, name, expr) for every entry in ir['f_x'], with name
    determined by content, not position. Also validates that the content-
    derived (kind, name) set exactly matches ir['y']/ir['x'] -- catching
    any equation whose target isn't a declared variable at all."""
    if ir.get("z") or ir.get("f_z"):
        raise NotImplementedError("IR contains algebraic-loop variables (z/f_z); unsupported.")

    results = [(*equation_target(expr), expr) for expr in ir["f_x"]]

    found_y = {name for kind, name, _ in results if kind == "y"}
    found_x = {name for kind, name, _ in results if kind == "x"}
    expected_y = set(ir["y"].keys())
    expected_x = set(ir["x"].keys())
    if found_y != expected_y:
        raise ValueError(f"algebraic targets {found_y} != declared y {expected_y}")
    if found_x != expected_x:
        raise ValueError(f"state targets {found_x} != declared x {expected_x}")

    return results


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "results/fixtures/ThermalNetwork.json"
    ir = json.loads(open(path).read())
    for i, (kind, name, _) in enumerate(equation_targets(ir)):
        print(f"f_x[{i}] -> kind={kind} name={name}")
