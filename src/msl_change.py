"""Feature 7: structural change injectors for the real-MSL-component
models (models/msl_rc_circuit, models/msl_resistor_network). Same
text-level source transformation discipline as src/change.py (phase 1),
applied to real Modelica.Electrical.Analog component instantiations
instead of hand-written flat equations.
"""
from __future__ import annotations

from pathlib import Path


def swap_resistor_to_conductor(
    source_path: str | Path = "models/msl_rc_circuit/MslRcCircuit.mo",
    out_path: str | Path = "models/msl_rc_circuit_swapped/MslRcCircuit.mo",
) -> Path:
    """Component swap: replace the linear resistor with its dual, an
    ideal linear conductor -- both are genuine MSL two-pin components
    (Interfaces.OnePort), same role, different governing equation
    (v=R*i vs i=G*v). Same role, different model, exactly the
    change-type definition.

    NOTE: the originally-planned swap (ConstantVoltage -> RampVoltage,
    a source-type swap) was abandoned after it surfaced that EVERY
    standard MSL Blocks.Sources signal generator (Ramp, Sine, ExpSine,
    ...) uses a `startTime`-conditional ("if time < startTime then ...")
    compiled by Rumoca into a synthetic, subscripted, "generated"
    Boolean condition-cache variable this project's expr_c.py cannot
    yet translate (a real gap: no "If" expression support at all).
    Properly supporting Rumoca's discrete/conditional-signal encoding is
    a substantial separate feature (closer in scope to Feature 6's
    "build only if a real target model needs it" boundary than to this
    one component swap), so this swap was changed to a component that
    needs none of it, rather than build that support under this
    feature's time budget. Recorded here, not silently substituted
    without explanation."""
    text = Path(source_path).read_text(encoding="utf-8")

    old = (
        "  Modelica.Electrical.Analog.Basic.Resistor R(R=100)\n"
        "    annotation (Placement(transformation(extent={{-40,20},{-20,40}})));\n"
    )
    new = (
        "  Modelica.Electrical.Analog.Basic.Conductor R(G=0.02)\n"
        "    annotation (Placement(transformation(extent={{-40,20},{-20,40}})));\n"
    )
    assert old in text, "expected Resistor instantiation+annotation not found"
    text = text.replace(old, new)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def add_power_sensor_equation(
    source_path: str | Path = "models/msl_rc_circuit/MslRcCircuit.mo",
    out_path: str | Path = "models/msl_rc_circuit_sensor/MslRcCircuit.mo",
) -> Path:
    """Sensor-add: a new equation computing the resistor's instantaneous
    power dissipation, reading two EXISTING variables (R.v, R.i),
    touching nothing else -- same pattern as phase 1/2's sensor-add
    (src/change.py's add_sensor_thermal_network)."""
    text = Path(source_path).read_text(encoding="utf-8")

    # The ConstantVoltage instantiation is one statement spanning TWO
    # lines (declaration, then its trailing annotation(...); on the next
    # line) -- the new declaration must go AFTER the whole statement
    # (including the annotation's closing ";"), not between them.
    anchor = (
        "  Modelica.Electrical.Analog.Sources.ConstantVoltage V(V=5)\n"
        "    annotation (Placement(transformation(extent={{-80,-20},{-60,0}})));\n"
    )
    assert anchor in text, "expected full ConstantVoltage declaration+annotation not found"
    text = text.replace(anchor, anchor + "  Real P_R \"Power dissipated in R, a derived sensor quantity\";\n")

    old_eq = "equation\n"
    new_eq = "equation\n  P_R = R.v * R.i;\n"
    assert old_eq in text
    text = text.replace(old_eq, new_eq, 1)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def remove_r3_from_resistor_network(
    source_path: str | Path = "models/msl_resistor_network/MslResistorNetwork.mo",
    out_path: str | Path = "models/msl_resistor_network_removed/MslResistorNetwork.mo",
) -> Path:
    """Component removal: delete R3 entirely (its instantiation and both
    connect() statements that reference it), leaving R2 as the sole
    parallel branch -- no dangling reference to R3 anywhere."""
    text = Path(source_path).read_text(encoding="utf-8")

    old_decl = (
        "  Modelica.Electrical.Analog.Basic.Resistor R3(R=300)\n"
        "    annotation (Placement(transformation(extent={{-10,-20},{10,0}})));\n"
    )
    assert old_decl in text
    text = text.replace(old_decl, "")

    old_conn1 = '  connect(R1.p, R3.n) annotation (Line(points={{-40,30},{-10,30},{-10,-10}}, color={0,0,255}));\n'
    old_conn2 = '  connect(R3.p, G.p) annotation (Line(points={{10,-10},{20,-10},{20,-40},{0,-40}}, color={0,0,255}));\n'
    assert old_conn1 in text and old_conn2 in text
    text = text.replace(old_conn1, "").replace(old_conn2, "")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def swap_thermal_conductor_to_resistor(
    source_path: str | Path = "models/msl_thermal_chain/MslThermalChain.mo",
    out_path: str | Path = "models/msl_thermal_chain_swapped/MslThermalChain.mo",
) -> Path:
    """Priority 3 (broadening the real-model corpus): the thermal-domain
    analog of swap_resistor_to_conductor() above -- ThermalConductor
    (Q_flow = G*dT) and ThermalResistor (dT = R*Q_flow) are genuine MSL
    duals sharing the same Interfaces.Element1D two-port interface, same
    role, different governing equation, exactly the change-type
    definition, on a different physical domain than every other real-MSL
    change type tested so far."""
    text = Path(source_path).read_text(encoding="utf-8")

    old = (
        "  Modelica.Thermal.HeatTransfer.Components.ThermalConductor G1(G=0.5)\n"
        "    annotation (Placement(transformation(extent={{-40,-10},{-20,10}})));\n"
    )
    new = (
        "  Modelica.Thermal.HeatTransfer.Components.ThermalResistor G1(R=2)\n"
        "    annotation (Placement(transformation(extent={{-40,-10},{-20,10}})));\n"
    )
    assert old in text, "expected ThermalConductor G1 instantiation+annotation not found"
    text = text.replace(old, new)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    print("wrote", swap_resistor_to_conductor())
    print("wrote", add_power_sensor_equation())
    print("wrote", remove_r3_from_resistor_network())
    print("wrote", swap_thermal_conductor_to_resistor())
