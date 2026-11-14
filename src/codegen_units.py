"""Generate one C header (shared model interface) and one .c file per
recompilation unit, plus a driver that runs a fixed-step forward-Euler
simulation calling each unit's compute function in dependency order.

This is a bespoke, scoped C emitter (see src/expr_c.py's docstring for
why: Rumoca's own `embedded-c` codegen target emits one monolithic file
per model, not one per recompilation unit, and splitting that output
post-hoc would be substantial reverse-engineering). It only needs to
handle the operators the fixture models actually use.
"""
from __future__ import annotations

from pathlib import Path

from expr_c import expr_to_c, extract_state_equation
from ir_equations import equation_targets
from linear_block import CONST, affine_form
from model_layout import Layout, sanitize_c_ident


def _literal_value(expr: dict) -> float:
    lit = expr["Literal"]["value"]
    if "Real" in lit:
        return float(lit["Real"])
    if "Integer" in lit:
        return float(lit["Integer"])
    if "Boolean" in lit:
        return 1.0 if lit["Boolean"] else 0.0
    raise NotImplementedError(f"unsupported literal for initial value: {lit}")


def model_prefix(model_name: str) -> str:
    return model_name.upper()


def generate_header(model_name: str, layout: Layout) -> str:
    prefix = model_prefix(model_name)
    lines = [
        "#pragma once",
        "#include <stddef.h>",
        "",
        "/* Unit sources spell their export as __declspec(dllexport) (Windows).",
        "   Elsewhere, map it to default symbol visibility so dlopen/dlsym can",
        "   find the function. */",
        "#ifndef _WIN32",
        "#define __declspec(x) __attribute__((visibility(\"default\")))",
        "#endif",
        "",
        "typedef double real_t;",
        "",
    ]
    for i, n in enumerate(layout.x):
        lines.append(f"#define {prefix}_X_{sanitize_c_ident(n)} {i}")
    for i, n in enumerate(layout.y):
        lines.append(f"#define {prefix}_Y_{sanitize_c_ident(n)} {i}")
    for i, n in enumerate(layout.p):
        lines.append(f"#define {prefix}_P_{sanitize_c_ident(n)} {i}")
    lines += [
        "",
        f"enum {{ {prefix}_NX = {max(len(layout.x), 1)}, "
        f"{prefix}_NY = {max(len(layout.y), 1)}, "
        f"{prefix}_NP = {max(len(layout.p), 1)} }};",
        "",
        "typedef struct {",
        "    real_t time;",
        f"    real_t x[{prefix}_NX];",
        f"    real_t dx[{prefix}_NX];",
        f"    real_t y[{prefix}_NY];",
        f"    real_t p[{prefix}_NP];",
        f"}} {model_name}_t;",
        "",
    ]
    for n in layout.y:
        lines.append(f"void {model_name}_compute_{sanitize_c_ident(n)}({model_name}_t *v);")
    for n in layout.x:
        lines.append(f"void {model_name}_compute_der_{sanitize_c_ident(n)}({model_name}_t *v);")
    lines.append("")
    return "\n".join(lines)


def generate_unit_c(
    model_name: str, kind: str, name: str, expr: dict, layout: Layout,
    name_to_c: dict[str, str] | None = None,
    y_index_map: dict[str, int] | None = None,
    x_index_map: dict[str, int] | None = None,
) -> str:
    """`name_to_c`/`y_index_map`/`x_index_map` are optional precomputed
    caches (see Layout.y_index_map()'s docstring for why this matters at
    scale): pass them when generating many units in a loop to avoid
    O(N) work (a dict build, a list.index() scan) repeated N times.
    Computed on the fly if omitted, for callers generating just one unit."""
    if name_to_c is None:
        name_to_c = layout.name_to_c()
    if y_index_map is None:
        y_index_map = layout.y_index_map()
    if x_index_map is None:
        x_index_map = layout.x_index_map()
    ident = sanitize_c_ident(name)
    lines = [f'#include "{model_name}.h"', "#include <math.h>", ""]
    if kind == "y":
        # Solved via the SAME affine-form extraction Feature 4 uses for
        # coupled blocks (src/linear_block.py), not by naively assuming
        # `name` sits alone on one side of the residual (the equation
        # `name` was MATCHED to is not guaranteed to be the equation
        # whose natural/syntactic left-hand side IS `name` -- confirmed
        # against a real MSL component: Resistor's Ohm's-law equation
        # naturally targets R.v, but the bipartite matcher can assign it
        # to solve for R.i instead, when R.v's own dedicated equation
        # already claimed R.v. The old naive "just take the other side"
        # extraction silently emitted `R.i = R.R_actual * R.i` -- a
        # self-referential, wrong assignment -- for exactly this case).
        row = affine_form(expr["rhs"], {name}, name_to_c)
        coef_c = row.get(name, "0.0")
        const_c = row.get(CONST, "0.0")
        idx = y_index_map[name]
        lines += [
            # dllexport: harmless when this .c is compiled to a plain .o
            # and statically linked (verified directly: a dllexport'd
            # function links and runs identically in a normal .exe), and
            # required when compiled straight to its own per-unit .dll
            # for the dynamic-link incremental build path
            # (src/c_build.py's *_dynamic() functions, src/unit_codegen.py's
            # generate_unit_driver_dynamic()) -- one codegen path serves
            # both build strategies.
            f"__declspec(dllexport) void {model_name}_compute_{ident}({model_name}_t *v) {{",
            f"    v->y[{idx}] = (-({const_c})) / ({coef_c});",
            "}",
        ]
    else:
        coef, rhs = extract_state_equation(expr)
        rhs_c = expr_to_c(rhs, name_to_c)
        idx = x_index_map[name]
        body = f"({rhs_c})" if coef is None else f"({rhs_c}) / ({expr_to_c(coef, name_to_c)})"
        lines += [
            f"__declspec(dllexport) void {model_name}_compute_der_{ident}({model_name}_t *v) {{",
            f"    v->dx[{idx}] = {body};",
            "}",
        ]
    lines.append("")
    return "\n".join(lines)


def unit_source_filename(model_name: str, unit_id: str) -> str:
    # unit_id is "+"-joined member equation names (src/units.py); "+" and
    # "." (real MSL qualified names, e.g. "R.p.i") aren't valid
    # filename/identifier characters on all platforms, so sanitize.
    return f"{model_name}_unit_{sanitize_c_ident(unit_id)}.c"


def generate_all_units(model_name: str, ir: dict, layout: Layout) -> dict[str, str]:
    """Returns {c_filename: c_source} for every equation in ir, one file each
    (current fixtures all causalize to singleton units, so "one file per
    recompilation unit" and "one file per equation" coincide; a future
    model with a genuine multi-equation unit would need Feature G2's
    tearing/residual refinement before this 1:1 assumption holds)."""
    name_to_c = layout.name_to_c()
    y_index_map = layout.y_index_map()
    x_index_map = layout.x_index_map()
    files = {}
    for kind, name, expr in equation_targets(ir):
        filename = f"{model_name}_unit_{name}.c"
        files[filename] = generate_unit_c(
            model_name, kind, name, expr, layout, name_to_c, y_index_map, x_index_map
        )
    return files


def generate_driver(model_name: str, ir: dict, layout: Layout, eval_order_y: list[str]) -> str:
    prefix = model_prefix(model_name)
    param_inits = []
    for n in layout.p:
        if n in ir["p"]:
            param_inits.append(f"    v.p[{prefix}_P_{sanitize_c_ident(n)}] = {_literal_value(ir['p'][n]['start'])!r};")
    state_inits = []
    for n in layout.x:
        if n in ir["x"]:
            state_inits.append(f"    v.x[{prefix}_X_{sanitize_c_ident(n)}] = {_literal_value(ir['x'][n]['start'])!r};")

    algebraic_calls = [f"    {model_name}_compute_{sanitize_c_ident(n)}(&v);" for n in eval_order_y if n in layout.y]
    der_calls = [f"    {model_name}_compute_der_{sanitize_c_ident(n)}(&v);" for n in layout.x if n in ir["x"]]
    state_updates = [f"    v.x[{i}] += dt * v.dx[{i}];" for i in range(len(layout.x))]

    header_row = ",".join(["time"] + layout.x + layout.y)
    print_row = ['printf("%g", v.time);'] + \
        [f'printf(",%g", v.x[{i}]);' for i in range(len(layout.x))] + \
        [f'printf(",%g", v.y[{i}]);' for i in range(len(layout.y))] + \
        ['printf("\\n");']

    return "\n".join([
        f'#include "{model_name}.h"',
        "#include <stdio.h>",
        "#include <stdlib.h>",
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


def write_model_sources(model_name: str, ir: dict, layout: Layout, eval_order_y: list[str], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    header_path = out_dir / f"{model_name}.h"
    header_path.write_text(generate_header(model_name, layout), encoding="utf-8")
    written["header"] = header_path

    for filename, source in generate_all_units(model_name, ir, layout).items():
        path = out_dir / filename
        path.write_text(source, encoding="utf-8")
        written[filename] = path

    driver_path = out_dir / f"{model_name}_driver.c"
    driver_path.write_text(generate_driver(model_name, ir, layout, eval_order_y), encoding="utf-8")
    written["driver"] = driver_path

    return written
