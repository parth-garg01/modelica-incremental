"""Run as a standalone script (subprocess, one fresh interpreter per
call) to fingerprint the FULL pipeline's output for every fixture: raw
dependency graph units, causalized units, matching, and BLT blocks.
Printed as JSON so tests/test_determinism_audit.py can spawn this with
several different PYTHONHASHSEED values and diff the output byte-for-
byte -- the real, permanent regression test for the class of bug found
in src/matching.py (networkx's hopcroft_karp_matching leaking Python's
per-process string hash randomization into its result).
"""
import json
from pathlib import Path

from graph import build_dependency_graph
from causal_graph import build_causalized_graph
from units import compute_units
from matching import compute_matching, blt_blocks

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"
MODELS = ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork", "Chain", "CauerLowPassAnalog"]


def fingerprint() -> dict:
    out = {}
    for name in MODELS:
        ir = json.loads((FIXTURES / f"{name}.json").read_text())
        entry = {}

        try:
            raw_units = compute_units(build_dependency_graph(ir))
            entry["raw_units"] = sorted(raw_units.keys())
            causal_units = compute_units(build_causalized_graph(ir))
            entry["causal_units"] = sorted(causal_units.keys())
        except ValueError:
            # graph.py/causal_graph.py require a single clean target per
            # equation; Cauer's anonymous KCL residuals don't have one.
            entry["raw_units"] = "UNSUPPORTED (anonymous residuals)"
            entry["causal_units"] = "UNSUPPORTED (anonymous residuals)"

        m = compute_matching(ir)
        entry["matching"] = sorted(m.eq_to_var.items())
        entry["blocks"] = sorted(sorted(b) for b in blt_blocks(ir, m))

        out[name] = entry
    return out


if __name__ == "__main__":
    print(json.dumps(fingerprint(), default=str, sort_keys=True))
