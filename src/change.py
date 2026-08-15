"""Inject a structural change into a model's Modelica source.

One change type this week: component swap. Swap a component's defining
equation for a different model of the same kind (same interface, same
role in the circuit/network, different internal behavior), which is
exactly the kind of localized structural edit a real digital twin would
need to absorb (a part replaced by a different part).

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


if __name__ == "__main__":
    p1 = swap_thermal_heater_to_proportional()
    print(f"wrote {p1}")
    p2 = swap_rlc_resistor_to_nonlinear()
    print(f"wrote {p2}")
