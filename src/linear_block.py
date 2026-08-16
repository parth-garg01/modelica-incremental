"""Extract an affine (linear) form from a residual expression, over a
given set of "unknown" variable names -- the equations of one coupled
BLT block, expressed in terms of that block's OWN member variables, with
everything else (states, parameters, other units' already-computed
outputs) treated as opaque "known" leaves.

For a block of N mutually-coupled equations over N unknowns, running
this over each equation's full residual (`expr["rhs"]`, since this
project's IR convention always residualizes as `lhs=null,
rhs=original_lhs - original_rhs`) gives one row of a linear system
`A*x + c = 0`, i.e. `A*x = -c` -- which src/block_codegen.py assembles
and solves directly (Feature 4: "for a coupled linear block, emit C that
assembles the small local linear system and solves it directly").

Every intermediate value here is a C EXPRESSION STRING (via
src/expr_c.py's expr_to_c), not a re-serialized AST: this module only
ever needs to hand C source to the codegen layer, never JSON back to
Rumoca, so building strings directly is simpler than round-tripping
through AST node objects.

A subtree that contains no reference to any unknown is never recursed
into further -- it is handed to expr_to_c as one opaque "known" leaf
directly, which is both simpler and correct (a parameter-dependent
coefficient like "R1*Vin" does not need decomposing, it only needs to be
evaluated at runtime as one C expression). A subtree where genuinely
NONLINEAR combination of two or more unknowns is detected (their product
or quotient, or an unknown inside a transcendental call) raises --
that is Feature 6 (nonlinear block solve) territory, not this one.
"""
from __future__ import annotations

from expr_c import expr_to_c
from graph import _varrefs

CONST = None  # sentinel key for the constant (non-unknown) term


def _contains_unknown(node, unknown_names: set[str]) -> bool:
    return bool(_varrefs(node) & unknown_names)


def _merge_add(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = f"(({out[k]}) + ({v}))" if k in out else v
    return out


def _negate(a: dict) -> dict:
    return {k: f"(-({v}))" for k, v in a.items()}


def _scale(a: dict, factor_c: str) -> dict:
    return {k: f"(({v}) * ({factor_c}))" for k, v in a.items()}


def affine_form(node: dict, unknown_names: set[str], name_to_c: dict[str, str]) -> dict:
    """Returns {unknown_name: coefficient_c_expr, ..., CONST: constant_c_expr}.
    A key absent means that unknown's coefficient is exactly zero in this
    (sub)expression. Every value present is a nonempty C expression
    string; combine with "+" across returned dicts for a full sum."""
    if not _contains_unknown(node, unknown_names):
        return {CONST: expr_to_c(node, name_to_c)}

    if "VarRef" in node:
        name = node["VarRef"]["name"]["name"]
        if name in unknown_names:
            return {name: "1.0"}
        return {CONST: expr_to_c(node, name_to_c)}  # unreachable given the guard above, kept for clarity

    if "Binary" in node:
        op = node["Binary"]["op"]
        lhs, rhs = node["Binary"]["lhs"], node["Binary"]["rhs"]
        if op == "Add":
            return _merge_add(affine_form(lhs, unknown_names, name_to_c), affine_form(rhs, unknown_names, name_to_c))
        if op == "Sub":
            return _merge_add(affine_form(lhs, unknown_names, name_to_c), _negate(affine_form(rhs, unknown_names, name_to_c)))
        if op == "Mul":
            lhs_has, rhs_has = _contains_unknown(lhs, unknown_names), _contains_unknown(rhs, unknown_names)
            if lhs_has and rhs_has:
                raise NotImplementedError(f"nonlinear term (product of two unknowns): {expr_to_c(node, name_to_c)}")
            if lhs_has:
                return _scale(affine_form(lhs, unknown_names, name_to_c), expr_to_c(rhs, name_to_c))
            return _scale(affine_form(rhs, unknown_names, name_to_c), expr_to_c(lhs, name_to_c))
        if op == "Div":
            if _contains_unknown(rhs, unknown_names):
                raise NotImplementedError(f"nonlinear term (division by an unknown): {expr_to_c(node, name_to_c)}")
            return _scale(affine_form(lhs, unknown_names, name_to_c), f"(1.0 / ({expr_to_c(rhs, name_to_c)}))")
        raise NotImplementedError(f"unsupported binary op in affine extraction: {op}")

    if "Unary" in node:
        op = node["Unary"]["op"]
        if op in ("Minus", "Neg"):
            return _negate(affine_form(node["Unary"]["rhs"], unknown_names, name_to_c))
        raise NotImplementedError(f"unsupported unary op in affine extraction: {op}")

    raise NotImplementedError(
        f"an unknown appears inside an unsupported node for affine extraction: {list(node.keys())}"
    )


def build_linear_system(equations: list[tuple[int, dict]], unknown_names: list[str], name_to_c: dict[str, str]) -> tuple[list[list[str]], list[str]]:
    """`equations` is [(equation_index, residual_expr), ...] in the same
    order as `unknown_names` (row i's equation matches unknown i's own
    natural row for readability, though any consistent order works since
    this is a general linear solve, not a triangular one). Returns
    (A, b) as lists of C expression strings: A[i][j] is the coefficient
    of unknown_names[j] in equation i's residual; b[i] is that residual's
    negated constant term (so A*x = b represents the original system)."""
    n = len(unknown_names)
    unknown_set = set(unknown_names)
    A: list[list[str]] = []
    b: list[str] = []
    for _, expr in equations:
        row = affine_form(expr["rhs"], unknown_set, name_to_c)
        A.append([row.get(name, "0.0") for name in unknown_names])
        const_c = row.get(CONST, "0.0")
        b.append(f"(-({const_c}))")
    return A, b
