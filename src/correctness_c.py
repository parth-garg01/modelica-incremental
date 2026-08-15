"""Feature C1: real numeric diff between the incremental program's
simulation output and the full-rebuild program's output, on the same
changed model. Parses the CSV stdout both binaries produce (see
src/codegen_units.py's generate_driver) into columns and computes max
absolute / max relative error per column, never loosening the tolerance
to force a pass.
"""
from __future__ import annotations

TOLERANCE_ABS = 1e-9
TOLERANCE_REL = 1e-9


def parse_csv_output(text: str) -> tuple[list[str], list[list[float]]]:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    header = lines[0].split(",")
    rows = [[float(v) for v in line.split(",")] for line in lines[1:]]
    return header, rows


def diff_outputs(full_csv: str, incremental_csv: str, atol: float = TOLERANCE_ABS, rtol: float = TOLERANCE_REL) -> dict:
    full_header, full_rows = parse_csv_output(full_csv)
    incr_header, incr_rows = parse_csv_output(incremental_csv)

    if full_header != incr_header:
        return {
            "pass": False,
            "reason": f"column headers differ: {full_header} vs {incr_header}",
            "max_abs_error": None,
            "max_rel_error": None,
        }
    if len(full_rows) != len(incr_rows):
        return {
            "pass": False,
            "reason": f"row counts differ: {len(full_rows)} vs {len(incr_rows)}",
            "max_abs_error": None,
            "max_rel_error": None,
        }

    max_abs_error = 0.0
    max_rel_error = 0.0
    for full_row, incr_row in zip(full_rows, incr_rows):
        for a, b in zip(full_row, incr_row):
            abs_err = abs(a - b)
            rel_err = abs_err / abs(a) if a != 0 else abs_err
            max_abs_error = max(max_abs_error, abs_err)
            max_rel_error = max(max_rel_error, rel_err)

    passed = max_abs_error <= atol or max_rel_error <= rtol
    return {
        "pass": passed,
        "reason": None if passed else f"max_abs_error={max_abs_error} max_rel_error={max_rel_error} exceed tolerance",
        "max_abs_error": max_abs_error,
        "max_rel_error": max_rel_error,
        "atol": atol,
        "rtol": rtol,
    }


if __name__ == "__main__":
    from measure_c import run_cell

    for baseline_path, changed_path, model_name, seed in [
        ("models/rlc_circuit/RLCCircuit.mo", "models/rlc_circuit_swapped/RLCCircuit.mo", "RLCCircuit", ["i"]),
        ("models/thermal_network/ThermalNetwork.mo", "models/thermal_network_swapped/ThermalNetwork.mo",
         "ThermalNetwork", ["Q1"]),
    ]:
        result = run_cell(baseline_path, changed_path, model_name, seed, t_end=5.0, dt=0.5)
        diff = diff_outputs(result["full_output"], result["incremental_output"])
        print(f"{model_name}: {diff}")
