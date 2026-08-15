"""Compile the fixture models and save their DAE intermediate representation
as JSON fixtures, with a manifest recording provenance and equation counts.
"""
from __future__ import annotations

import json
from pathlib import Path

from compile import compile_model, provenance

FIXTURES_DIR = Path("results/fixtures")

MODELS = [
    ("models/one_line/OneLine.mo", "OneLine", "hand-written, one-state decay ODE, used as the compiler smoke test"),
    ("models/decoupled_pair/DecoupledPair.mo", "DecoupledPair",
     "hand-written, two independent first-order decays with no coupling; "
     "ground truth for singleton recompilation units"),
    ("models/rlc_circuit/RLCCircuit.mo", "RLCCircuit",
     "hand-written, canonical series RLC circuit; inductor current and "
     "capacitor voltage are genuinely coupled through the loop equation"),
    ("models/thermal_network/ThermalNetwork.mo", "ThermalNetwork",
     "hand-written, three-room thermal network with a heater in room 1; "
     "used for the component-swap change injection"),
]


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"provenance": provenance(), "models": []}

    for source_path, model_name, description in MODELS:
        result = compile_model(source_path, model_name)
        n_equations = len(result.ir["y"]) + len(result.ir["x"])

        fixture_path = FIXTURES_DIR / f"{model_name}.json"
        fixture_path.write_text(result.ir_json, encoding="utf-8")

        manifest["models"].append({
            "model_name": model_name,
            "source_path": source_path,
            "description": description,
            "fixture_path": str(fixture_path),
            "n_states": len(result.ir["x"]),
            "n_algebraic": len(result.ir["y"]),
            "n_equations": n_equations,
            "compile_seconds": result.compile_seconds,
        })
        print(f"{model_name}: n_equations={n_equations} "
              f"(states={len(result.ir['x'])}, algebraic={len(result.ir['y'])}), "
              f"compile={result.compile_seconds:.4f}s -> {fixture_path}")

    manifest_path = FIXTURES_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
