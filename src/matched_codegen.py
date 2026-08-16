"""Feature 3: singleton-unit C generation driven by src/matching.py's
actual matching result, not by re-deriving each equation's target
independently via src/ir_equations.py's `equation_target()`.

Phase 2's codegen (src/codegen_units.py's `generate_all_units`) calls
`ir_equations.equation_targets(ir)`, which finds each equation's target
purely from that equation's OWN content (its der() argument, or the left
operand of its "var = expr" residual) -- it never looks at the matching
at all, so it happens to work only because every current fixture is
fully assignment-form, where the "obvious" per-equation target and the
graph-theoretically matched target always coincide (proven exactly by
`MatchingResult.agrees_with_natural_targets()`, see src/matching.py and
tests/test_matching.py). This module removes that coincidence: codegen
here is driven BY the matching (`matching.eq_to_var[i]`,
`matching.eq_kind[i]`), which is the representation Feature 2's units
and (eventually) Feature 4's coupled-block solves are built on, so the
whole pipeline agrees with itself by construction from here on rather
than by two independent paths happening to land on the same answer.

Only handles singleton blocks (one equation, one matched variable) --
Feature 4 adds coupled-block (multi-equation) codegen; asking this
module to emit code for a model with a genuine coupled block raises
rather than silently emitting wrong single-equation code for one member
of it.
"""
from __future__ import annotations

from codegen_units import generate_unit_c, unit_source_filename
from matched_units import compute_matched_units
from matching import compute_matching
from model_layout import Layout


def generate_all_units_from_matching(model_name: str, ir: dict, layout: Layout) -> dict[str, str]:
    m = compute_matching(ir)
    units = compute_matched_units(ir)

    non_singleton = {uid: members for uid, members in units.items() if len(members) > 1}
    if non_singleton:
        raise NotImplementedError(
            f"{model_name} has {len(non_singleton)} coupled (non-singleton) unit(s) "
            f"{list(non_singleton.keys())}; matched-driven singleton codegen (Feature 3) "
            f"does not handle coupled blocks -- that is Feature 4."
        )

    files = {}
    for i, name in m.eq_to_var.items():
        kind = "y" if m.eq_kind[i] == "algebraic" else "x"
        expr = ir["f_x"][i]
        filename = f"{model_name}_unit_{name}.c"
        files[filename] = generate_unit_c(model_name, kind, name, expr, layout)
    return files


if __name__ == "__main__":
    import json
    import sys

    from compile import compile_model
    from model_layout import build_layout
    from codegen_units import generate_all_units

    path = sys.argv[1] if len(sys.argv) > 1 else "models/rlc_circuit/RLCCircuit.mo"
    model_name = sys.argv[2] if len(sys.argv) > 2 else "RLCCircuit"

    result = compile_model(path, model_name)
    layout = build_layout(result.ir)

    matched_files = generate_all_units_from_matching(model_name, result.ir, layout)
    original_files = generate_all_units(model_name, result.ir, layout)

    same = matched_files.keys() == original_files.keys() and all(
        matched_files[k] == original_files[k] for k in matched_files
    )
    print(f"{model_name}: {len(matched_files)} files, identical to phase-2 codegen: {same}")
    if not same:
        for k in sorted(set(matched_files) | set(original_files)):
            if matched_files.get(k) != original_files.get(k):
                print(f"  DIFFERS: {k}")
