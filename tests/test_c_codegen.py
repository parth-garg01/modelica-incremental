import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from expr_c import expr_to_c, extract_algebraic_rhs, extract_state_equation
from ir_equations import equation_targets
from model_layout import build_layout

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


def test_thermal_network_algebraic_c_expressions_match_source_by_hand():
    """Hand-checkable: Q1env = Genv*(T1 - Tamb) should translate exactly."""
    ir = load_ir("ThermalNetwork")
    layout = build_layout(ir)
    name_to_c = layout.name_to_c()
    for kind, name, expr in equation_targets(ir):
        if name == "Q1env":
            c_code = expr_to_c(extract_algebraic_rhs(expr), name_to_c)
            assert c_code == f"({name_to_c['Genv']} * ({name_to_c['T1']} - {name_to_c['Tamb']}))"
            return
    pytest.fail("Q1env not found")


def test_thermal_network_state_equation_divides_by_coefficient():
    """C1*der(T1) = Q1 - Q1env - Q12  ->  der(T1) = (Q1-Q1env-Q12) / C1."""
    ir = load_ir("ThermalNetwork")
    layout = build_layout(ir)
    name_to_c = layout.name_to_c()
    for kind, name, expr in equation_targets(ir):
        if kind == "x" and name == "T1":
            coef, rhs = extract_state_equation(expr)
            assert coef is not None
            coef_c = expr_to_c(coef, name_to_c)
            assert coef_c == name_to_c["C1"]
            return
    pytest.fail("T1 state equation not found")


def test_one_line_state_equation_has_no_coefficient():
    """der(x) = -k*x has no explicit coefficient multiplying der(x)."""
    ir = load_ir("OneLine")
    for kind, name, expr in equation_targets(ir):
        coef, rhs = extract_state_equation(expr)
        assert coef is None
        return


def test_expr_to_c_rejects_unknown_variable():
    with pytest.raises(KeyError):
        expr_to_c({"VarRef": {"name": {"name": "nonexistent"}}}, {})


def test_expr_to_c_rejects_unsupported_op():
    with pytest.raises(NotImplementedError):
        expr_to_c({"Binary": {"op": "Mod", "lhs": {"Literal": {"value": {"Real": 1.0}}},
                               "rhs": {"Literal": {"value": {"Real": 2.0}}}}}, {})
