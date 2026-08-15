"""Inject a structural change into a model's Modelica source.

Phase 1 covered one change type: component swap. Phase 2 (Feature B2/B3)
adds sensor-add and component-removal.

Text-level source transformation, not IR surgery: the output is a new
.mo file that must independently compile and simulate through Rumoca,
same as any hand-written model.
"""
from __future__ import annotations

from pathlib import Path


def swap_thermal_heater_to_proportional(
    source_path: str | Path = "models/thermal_network/ThermalNetwork.mo",
    out_path: str | Path = "models/thermal_network_swapped/ThermalNetwork.mo",
) -> Path:
    """Swap room 1's constant heater (Q1 = Qheater) for a proportional
    thermostat (Q1 = Kp*(Tset - T1)). This is a genuine component swap:
    the constant-power heater and the proportional thermostat are both
    "a heater in room 1" (same role, same output Q1), but the thermostat
    introduces a new dependency of Q1 on T1 that the constant heater did
    not have.
    """
    text = Path(source_path).read_text(encoding="utf-8")

    old_param = "  parameter Real Qheater = 100.0;\n"
    new_params = "  parameter Real Kp = 20.0;\n  parameter Real Tset = 22.0;\n"
    assert old_param in text, "expected constant-heater parameter line not found"
    text = text.replace(old_param, new_params)

    old_eq = "  Q1 = Qheater;\n"
    new_eq = "  Q1 = Kp*(Tset - T1);\n"
    assert old_eq in text, "expected constant-heater equation line not found"
    text = text.replace(old_eq, new_eq)

    text = text.replace("model ThermalNetwork", "model ThermalNetwork", 1)
    text = text.replace(
        '"Three-room thermal network: each room exchanges heat with its neighbors\n'
        '   and with the ambient, and room 1 has a heater. This is the closest of\n'
        '   the three fixture models to a real digital-twin subsystem (a small\n'
        '   building-heating model), and it is the one used for the component-swap\n'
        '   change (swapping the heater model in room 1)."',
        '"Same as ThermalNetwork, with room 1\'s constant-power heater swapped for\n'
        '   a proportional thermostat: Q1 = Kp*(Tset - T1) instead of Q1 = Qheater.\n'
        '   This is the post-change model used to measure ripple."',
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def swap_rlc_resistor_to_nonlinear(
    source_path: str | Path = "models/rlc_circuit/RLCCircuit.mo",
    out_path: str | Path = "models/rlc_circuit_swapped/RLCCircuit.mo",
) -> Path:
    """Swap the linear resistor (v_R = R*i) for a cubic nonlinear resistor
    (v_R = R*i + alpha*i^3), a different model of the same two-terminal
    component."""
    text = Path(source_path).read_text(encoding="utf-8")

    old_param_block = "  parameter Real omega = 2.0;\n"
    new_param_block = "  parameter Real omega = 2.0;\n  parameter Real alpha = 0.1;\n"
    assert old_param_block in text
    text = text.replace(old_param_block, new_param_block)

    old_eq = "  L*der(i) = Vs - R*i - v;\n"
    new_eq = "  L*der(i) = Vs - R*i - alpha*i^3 - v;\n"
    assert old_eq in text
    text = text.replace(old_eq, new_eq)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def add_sensor_thermal_network(
    source_path: str | Path = "models/thermal_network/ThermalNetwork.mo",
    out_path: str | Path = "models/thermal_network_sensor/ThermalNetwork.mo",
) -> Path:
    """Add a new measurement equation, Qtotal = Q1env + Q2env + Q3env, a
    genuinely new variable and equation reading three EXISTING algebraic
    variables. Unlike a component swap (which edits an existing
    equation's formula), this ADDS an equation the resolver has never
    seen before -- exercising the soundness check's "equation present in
    the changed IR but not the baseline" path (src/soundness.py's
    actually_changed_equations already handles this: a name in one IR
    but not the other counts as changed)."""
    text = Path(source_path).read_text(encoding="utf-8")

    old_decl = "  Real Q1, Q12, Q23, Q1env, Q2env, Q3env;\n"
    new_decl = "  Real Q1, Q12, Q23, Q1env, Q2env, Q3env;\n  Real Qtotal;\n"
    assert old_decl in text, "expected algebraic-variable declaration line not found"
    text = text.replace(old_decl, new_decl)

    old_eq = "  Q23 = G23*(T2 - T3);\n"
    new_eq = "  Q23 = G23*(T2 - T3);\n  Qtotal = Q1env + Q2env + Q3env;\n"
    assert old_eq in text, "expected Q23 equation line not found"
    text = text.replace(old_eq, new_eq)

    text = text.replace(
        '"Three-room thermal network: each room exchanges heat with its neighbors\n'
        '   and with the ambient, and room 1 has a heater. This is the closest of\n'
        '   the three fixture models to a real digital-twin subsystem (a small\n'
        '   building-heating model), and it is the one used for the component-swap\n'
        '   change (swapping the heater model in room 1)."',
        '"Same as ThermalNetwork, with a new sensor added: Qtotal, summing the\n'
        '   three room-to-ambient heat losses. This is the sensor-add change."',
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def remove_component_thermal_network(
    source_path: str | Path = "models/thermal_network/ThermalNetwork.mo",
    out_path: str | Path = "models/thermal_network_removed/ThermalNetwork.mo",
) -> Path:
    """Remove room 3 entirely: its state T3, its heat-loss and coupling
    equations (Q3env, Q23), and every reference to them from room 2's
    equation (which loses the "- Q23" term it used to exchange heat with
    room 3). This is component removal: room 2 becomes the new end of
    the chain, with no dangling reference to anything that used to
    belong to room 3."""
    text = Path(source_path).read_text(encoding="utf-8")

    old_params = "  parameter Real G23 = 0.5;\n  parameter Real Tamb = 15.0;\n"
    new_params = "  parameter Real Tamb = 15.0;\n"
    assert old_params in text, "expected G23/Tamb parameter block not found"
    text = text.replace(old_params, new_params)

    old_vars = "  Real T1(start=15.0);\n  Real T2(start=15.0);\n  Real T3(start=15.0);\n  Real Q1, Q12, Q23, Q1env, Q2env, Q3env;\n"
    new_vars = "  Real T1(start=15.0);\n  Real T2(start=15.0);\n  Real Q1, Q12, Q1env, Q2env;\n"
    assert old_vars in text, "expected variable declaration block not found"
    text = text.replace(old_vars, new_vars)

    old_eqs = (
        "  Q1 = Qheater;\n"
        "  Q1env = Genv*(T1 - Tamb);\n"
        "  Q2env = Genv*(T2 - Tamb);\n"
        "  Q3env = Genv*(T3 - Tamb);\n"
        "  Q12 = G12*(T1 - T2);\n"
        "  Q23 = G23*(T2 - T3);\n"
        "\n"
        "  C1*der(T1) = Q1 - Q1env - Q12;\n"
        "  C2*der(T2) = Q12 - Q2env - Q23;\n"
        "  C3*der(T3) = Q23 - Q3env;\n"
    )
    new_eqs = (
        "  Q1 = Qheater;\n"
        "  Q1env = Genv*(T1 - Tamb);\n"
        "  Q2env = Genv*(T2 - Tamb);\n"
        "  Q12 = G12*(T1 - T2);\n"
        "\n"
        "  C1*der(T1) = Q1 - Q1env - Q12;\n"
        "  C2*der(T2) = Q12 - Q2env;\n"
    )
    assert old_eqs in text, "expected full equation block not found"
    text = text.replace(old_eqs, new_eqs)

    text = text.replace(
        '"Three-room thermal network: each room exchanges heat with its neighbors\n'
        '   and with the ambient, and room 1 has a heater. This is the closest of\n'
        '   the three fixture models to a real digital-twin subsystem (a small\n'
        '   building-heating model), and it is the one used for the component-swap\n'
        '   change (swapping the heater model in room 1)."',
        '"Same as ThermalNetwork, with room 3 removed entirely: no T3, no Q23,\n'
        '   no Q3env, and room 2 loses the Q23 term from its own derivative\n'
        '   equation. This is the component-removal change."',
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    p1 = swap_thermal_heater_to_proportional()
    print(f"wrote {p1}")
    p2 = swap_rlc_resistor_to_nonlinear()
    print(f"wrote {p2}")
    p3 = add_sensor_thermal_network()
    print(f"wrote {p3}")
    p4 = remove_component_thermal_network()
    print(f"wrote {p4}")
