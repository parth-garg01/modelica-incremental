"""Translate a Rumoca DAE residual-expression JSON node into a C
expression string, given a lookup from variable name to its C access
expression (e.g. "v->x[0]", "v->p[2]").

Scoped to the operators actually present in the four fixture models:
Binary Add/Sub/Mul/Div/Pow, Unary Minus, BuiltinCall Sin/Cos/Der, VarRef,
Literal. Anything else raises NotImplementedError rather than silently
emitting wrong C -- this is a bespoke codegen for a feasibility study,
not a general Modelica-to-C compiler.
"""
from __future__ import annotations

_BINARY_OPS = {
    "Add": "+", "Sub": "-", "Mul": "*", "Div": "/",
}


def expr_to_c(node: dict, name_to_c: dict[str, str]) -> str:
    if "VarRef" in node:
        name = node["VarRef"]["name"]["name"]
        if name not in name_to_c:
            raise KeyError(f"no C access expression registered for variable {name!r}")
        return name_to_c[name]

    if "Literal" in node:
        value = node["Literal"]["value"]
        if "Real" in value:
            return repr(float(value["Real"]))
        if "Integer" in value:
            return f"{int(value['Integer'])}.0"
        if "Boolean" in value:
            return "1.0" if value["Boolean"] else "0.0"
        raise NotImplementedError(f"unsupported literal value: {value}")

    if "Binary" in node:
        op = node["Binary"]["op"]
        lhs = expr_to_c(node["Binary"]["lhs"], name_to_c)
        rhs = expr_to_c(node["Binary"]["rhs"], name_to_c)
        if op in _BINARY_OPS:
            return f"({lhs} {_BINARY_OPS[op]} {rhs})"
        if op in ("Pow", "Exp"):
            return f"pow({lhs}, {rhs})"
        raise NotImplementedError(f"unsupported binary op: {op}")

    if "Unary" in node:
        op = node["Unary"]["op"]
        # The operand key is "rhs" (mirroring Binary's lhs/rhs naming),
        # not "arg" -- confirmed against OneLine's "der(x) = -x", the
        # first equation in this whole project to actually exercise a
        # Unary node through codegen; the previous "arg" key was wrong
        # from the start and had never been run until Feature 3's
        # regression check against all 5 clean fixtures caught it.
        arg = expr_to_c(node["Unary"]["rhs"], name_to_c)
        if op in ("Minus", "Neg"):
            return f"(-{arg})"
        raise NotImplementedError(f"unsupported unary op: {op}")

    if "BuiltinCall" in node:
        fn = node["BuiltinCall"]["function"]
        args = [expr_to_c(a, name_to_c) for a in node["BuiltinCall"]["args"]]
        c_fn = {"Sin": "sin", "Cos": "cos", "Tan": "tan", "Exp": "exp", "Sqrt": "sqrt"}.get(fn)
        if c_fn is None:
            raise NotImplementedError(f"unsupported builtin call: {fn}")
        return f"{c_fn}({', '.join(args)})"

    raise NotImplementedError(f"unsupported expression node: {list(node.keys())}")


def extract_algebraic_rhs(expr: dict) -> dict:
    """For an algebraic equation's residual (var - rhs = 0), return the
    original rhs expression node."""
    return expr["rhs"]["Binary"]["rhs"]


def _der_coefficient(node: dict) -> dict | None | bool:
    """If `node` is exactly `Der(x)` or `coef*Der(x)` (either operand
    order), return the coefficient expr (or None for a bare Der). Returns
    False (not a der pattern at all) otherwise -- False, not None, since
    None is itself a meaningful "no coefficient" result."""
    if "BuiltinCall" in node and node["BuiltinCall"]["function"] == "Der":
        return None
    if "Binary" in node and node["Binary"]["op"] == "Mul":
        mul_lhs, mul_rhs = node["Binary"]["lhs"], node["Binary"]["rhs"]
        if "BuiltinCall" in mul_rhs and mul_rhs["BuiltinCall"]["function"] == "Der":
            return mul_lhs
        if "BuiltinCall" in mul_lhs and mul_lhs["BuiltinCall"]["function"] == "Der":
            return mul_rhs
    return False


def extract_state_equation(expr: dict) -> tuple[dict | None, dict]:
    """For a state equation's residual, return (coefficient_expr_or_None,
    rhs_expr) such that der(state) = rhs_expr [/ coefficient_expr].

    The der(state) term (bare, or coefficient-multiplied, either operand
    order) can be on EITHER side of the original equation's "=" -- e.g.
    a hand-written "coef*der(x) = rhs" puts it on the residual's top-level
    lhs, but MSL's own Capacitor writes its defining equation the other
    way, "i = C*der(v)", putting it on the residual's top-level rhs
    (confirmed against models/msl_rc_circuit's compiled IR; the earlier
    lhs-only version raised NotImplementedError on this real MSL
    component the first time a model using it was compiled). Both sides
    are checked; when the der term is on the residual's rhs, the sign
    doesn't flip (residual = lhs - rhs = 0 => lhs = coef*der(x) => der(x)
    = lhs/coef, the same formula, just returning the OTHER side's
    expression as the "rhs_expr" to divide).
    """
    top = expr["rhs"]["Binary"]
    lhs, rhs = top["lhs"], top["rhs"]

    coef = _der_coefficient(lhs)
    if coef is not False:
        return coef, rhs

    coef = _der_coefficient(rhs)
    if coef is not False:
        return coef, lhs

    raise NotImplementedError(
        f"unsupported state-equation source form: der() term not found directly "
        f"on either side of the top-level residual (lhs keys={list(lhs.keys())}, "
        f"rhs keys={list(rhs.keys())})"
    )
