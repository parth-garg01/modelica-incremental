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
        arg = expr_to_c(node["Unary"]["arg"], name_to_c)
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


def extract_state_equation(expr: dict) -> tuple[dict | None, dict]:
    """For a state equation's residual, return (coefficient_expr_or_None,
    rhs_expr) such that der(state) = rhs_expr [/ coefficient_expr].

    Handles two source forms actually used by the fixtures:
      der(x) = rhs                  -> top.lhs is BuiltinCall{Der}     -> (None, top.rhs)
      coef*der(x) = rhs             -> top.lhs is Binary{Mul, ., Der}  -> (coef, top.rhs)
    """
    top = expr["rhs"]["Binary"]
    lhs = top["lhs"]
    rhs = top["rhs"]

    if "BuiltinCall" in lhs and lhs["BuiltinCall"]["function"] == "Der":
        return None, rhs

    if "Binary" in lhs and lhs["Binary"]["op"] == "Mul":
        mul_lhs, mul_rhs = lhs["Binary"]["lhs"], lhs["Binary"]["rhs"]
        if "BuiltinCall" in mul_rhs and mul_rhs["BuiltinCall"]["function"] == "Der":
            return mul_lhs, rhs
        if "BuiltinCall" in mul_lhs and mul_lhs["BuiltinCall"]["function"] == "Der":
            return mul_rhs, rhs

    raise NotImplementedError(f"unsupported state-equation source form: {list(lhs.keys())}")
