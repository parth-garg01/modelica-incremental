"""Combined per-unit C source generation: dispatches each recompilation
unit (src/matched_units.py) to singleton codegen (Feature 3,
src/matched_codegen.py's generate_unit_c) or coupled-block codegen
(Feature 4, src/block_codegen.py's generate_block_unit_c) by its member
count, and generates a driver that calls units in dependency order
(src/eval_order.py's unit_eval_order) instead of per-equation order.

This supersedes src/codegen_units.py's generate_all_units/generate_driver
for any model that might have a coupled block; models that don't (every
fixture through Feature 2) produce identical per-unit C to the phase-2
path, since a singleton unit's codegen is unchanged (Feature 3 already
proved this bit-identical).
"""
from __future__ import annotations

from pathlib import Path

from block_codegen import generate_block_unit_c
from codegen_units import generate_header, model_prefix
from eval_order import unit_eval_order
from matched_codegen import generate_unit_c
from matched_units import compute_matched_units
from matching import compute_matching
from model_layout import Layout


def unit_function_suffix(unit_id: str, members: list[str]) -> str:
    return members[0] if len(members) == 1 else unit_id.replace("+", "_")


def generate_all_unit_sources(model_name: str, ir: dict, layout: Layout) -> dict[str, str]:
    m = compute_matching(ir)
    units = compute_matched_units(ir)

    files: dict[str, str] = {}
    for unit_id, members in units.items():
        suffix = unit_function_suffix(unit_id, members)
        filename = f"{model_name}_unit_{suffix}.c"
        if len(members) == 1:
            i = m.var_to_eq[members[0]]
            kind = "y" if m.eq_kind[i] == "algebraic" else "x"
            files[filename] = generate_unit_c(model_name, kind, members[0], ir["f_x"][i], layout)
        else:
            indices = [m.var_to_eq[name] for name in members]
            files[filename] = generate_block_unit_c(model_name, suffix, indices, members, ir, layout)
    return files


def generate_unit_driver(model_name: str, ir: dict, layout: Layout) -> str:
    prefix = model_prefix(model_name)
    m = compute_matching(ir)
    units = compute_matched_units(ir)
    order = unit_eval_order(ir)

    param_inits = [
        f"    v.p[{prefix}_P_{n}] = {_literal(ir['p'][n]['start'])!r};"
        for n in layout.p if n in ir["p"]
    ]
    state_inits = [
        f"    v.x[{prefix}_X_{n}] = {_literal(ir['x'][n]['start'])!r};"
        for n in layout.x if n in ir["x"]
    ]

    algebraic_calls = [
        f"    {model_name}_compute_{unit_function_suffix(uid, units[uid])}(&v);"
        for uid in order
    ]
    state_unit_ids = [uid for uid, members in units.items() if set(members) & set(layout.x)]
    der_calls = [
        f"    {model_name}_compute_der_{units[uid][0]}(&v);"
        for uid in state_unit_ids
    ]
    state_updates = [f"    v.x[{i}] += dt * v.dx[{i}];" for i in range(len(layout.x))]

    header_row = ",".join(["time"] + layout.x + layout.y)
    print_row = ['printf("%g", v.time);'] + \
        [f'printf(",%g", v.x[{i}]);' for i in range(len(layout.x))] + \
        [f'printf(",%g", v.y[{i}]);' for i in range(len(layout.y))] + \
        ['printf("\\n");']

    unit_prototypes = [
        f"void {model_name}_compute_{unit_function_suffix(uid, members)}({model_name}_t *v);"
        for uid, members in units.items()
    ]

    return "\n".join([
        f'#include "{model_name}.h"',
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "",
        *unit_prototypes,
        "",
        "int main(int argc, char **argv) {",
        "    double t_end = argc > 1 ? atof(argv[1]) : 10.0;",
        "    double dt = argc > 2 ? atof(argv[2]) : 0.01;",
        f"    {model_name}_t v;",
        "    v.time = 0.0;",
        *param_inits,
        *state_inits,
        f'    printf("{header_row}\\n");',
        "    while (v.time <= t_end + 1e-9) {",
        *algebraic_calls,
        *print_row,
        *der_calls,
        *state_updates,
        "        v.time += dt;",
        "    }",
        "    return 0;",
        "}",
        "",
    ])


def _literal(expr: dict) -> float:
    lit = expr["Literal"]["value"]
    if "Real" in lit:
        return float(lit["Real"])
    if "Integer" in lit:
        return float(lit["Integer"])
    raise NotImplementedError(f"unsupported literal for initial value: {lit}")


def write_unit_sources(model_name: str, ir: dict, layout: Layout, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    header_path = out_dir / f"{model_name}.h"
    header_path.write_text(generate_header(model_name, layout), encoding="utf-8")
    written["header"] = header_path

    for filename, source in generate_all_unit_sources(model_name, ir, layout).items():
        path = out_dir / filename
        path.write_text(source, encoding="utf-8")
        written[filename] = path

    driver_path = out_dir / f"{model_name}_driver.c"
    driver_path.write_text(generate_unit_driver(model_name, ir, layout), encoding="utf-8")
    written["driver"] = driver_path

    return written
