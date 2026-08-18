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

import networkx as nx

from block_codegen import generate_block_unit_c
from codegen_units import generate_header, model_prefix
from eval_order import unit_eval_order
from expr_c import expr_to_c
from graph import _varrefs
from matched_codegen import generate_unit_c
from matched_units import compute_matched_units
from matching import compute_matching
from model_layout import Layout, sanitize_c_ident


def unit_function_suffix(unit_id: str, members: list[str]) -> str:
    """A valid C identifier fragment for this unit's compute function
    name and source filename -- sanitized, since a real MSL variable
    name (e.g. "R.p.i") or a coupled unit id (src/matched_units.py's
    "+"-joined convention, e.g. "y1+y2") can contain characters that
    aren't valid in a C identifier."""
    raw = members[0] if len(members) == 1 else unit_id
    return sanitize_c_ident(raw)


def generate_all_unit_sources(model_name: str, ir: dict, layout: Layout) -> dict[str, str]:
    m = compute_matching(ir)
    units = compute_matched_units(ir)

    # Built ONCE per model, not per unit -- see Layout.y_index_map()'s
    # docstring: passing these through avoids the confirmed O(N^2)
    # bottleneck (an O(N) dict build / list scan repeated N times, once
    # per recompilation unit).
    name_to_c = layout.name_to_c()
    y_index_map = layout.y_index_map()
    x_index_map = layout.x_index_map()

    files: dict[str, str] = {}
    for unit_id, members in units.items():
        suffix = unit_function_suffix(unit_id, members)
        filename = f"{model_name}_unit_{suffix}.c"
        if len(members) == 1:
            i = m.var_to_eq[members[0]]
            kind = "y" if m.eq_kind[i] == "algebraic" else "x"
            files[filename] = generate_unit_c(
                model_name, kind, members[0], ir["f_x"][i], layout,
                name_to_c, y_index_map, x_index_map,
            )
        else:
            indices = [m.var_to_eq[name] for name in members]
            files[filename] = generate_block_unit_c(
                model_name, suffix, indices, members, ir, layout,
                name_to_c, y_index_map, x_index_map,
            )
    return files


def _driver_name_to_c(layout: Layout) -> dict[str, str]:
    """Same slot layout as Layout.name_to_c(), but with "v." (dot access
    to a stack-local struct) instead of "v->" (pointer access) -- this is
    only used for generating the driver's own init code, which owns its
    ModelName_t as a plain local, not a pointer."""
    mapping = {"time": "v.time"}
    for i, n in enumerate(layout.x):
        mapping[n] = f"v.x[{i}]"
    for i, n in enumerate(layout.y):
        mapping[n] = f"v.y[{i}]"
    for i, n in enumerate(layout.p):
        mapping[n] = f"v.p[{i}]"
    return mapping


def _param_eval_order(ir: dict, layout: Layout) -> list[str]:
    """A parameter's default/start value can be an arbitrary expression
    referencing another parameter (real Modelica feature, confirmed
    against a real MSL component: Resistor's `T` parameter defaults to
    `T_ref`, not a literal) -- topologically order parameter
    initialization by that dependency, the same way unit_eval_order does
    for algebraic units."""
    g = nx.DiGraph()
    g.add_nodes_from(layout.p)
    for n in layout.p:
        if n not in ir["p"]:
            continue
        for ref in _varrefs(ir["p"][n]["start"]) & set(layout.p):
            if ref != n:
                g.add_edge(ref, n)
    try:
        return list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as e:
        raise ValueError("parameter start-value expressions have a cycle") from e


def generate_unit_driver(model_name: str, ir: dict, layout: Layout) -> str:
    prefix = model_prefix(model_name)
    m = compute_matching(ir)
    units = compute_matched_units(ir)
    order = unit_eval_order(ir)
    driver_name_to_c = _driver_name_to_c(layout)
    # O(1) lookups instead of `layout.p.index(n)`/`layout.x.index(n)`
    # (O(N) list scans) inside a loop over all P params / X states --
    # same O(N^2) pattern as Layout.y_index_map()'s docstring describes
    # for unit codegen, confirmed to matter at scale since P and X both
    # grow with N on the generated scaling models.
    p_index_map = {n: i for i, n in enumerate(layout.p)}
    x_index_map = {n: i for i, n in enumerate(layout.x)}

    param_inits = [
        f"    v.p[{p_index_map[n]}] = {expr_to_c(ir['p'][n]['start'], driver_name_to_c)};"
        for n in _param_eval_order(ir, layout) if n in ir["p"]
    ]
    state_inits = [
        f"    v.x[{x_index_map[n]}] = {expr_to_c(ir['x'][n]['start'], driver_name_to_c)};"
        for n in layout.x if n in ir["x"]
    ]

    algebraic_calls = [
        f"    {model_name}_compute_{unit_function_suffix(uid, units[uid])}(&v);"
        for uid in order
    ]
    state_unit_ids = [uid for uid, members in units.items() if set(members) & set(layout.x)]
    der_calls = [
        f"    {model_name}_compute_der_{sanitize_c_ident(units[uid][0])}(&v);"
        for uid in state_unit_ids
    ]
    state_updates = [f"    v.x[{i}] += dt * v.dx[{i}];" for i in range(len(layout.x))]

    header_row = ",".join(["time"] + layout.x + layout.y)
    print_row = ['printf("%g", v.time);'] + \
        [f'printf(",%g", v.x[{i}]);' for i in range(len(layout.x))] + \
        [f'printf(",%g", v.y[{i}]);' for i in range(len(layout.y))] + \
        ['printf("\\n");']

    # State units are defined as compute_der_<name> (see matched_codegen's
    # generate_unit_c), not compute_<name> -- this used to declare the
    # wrong prototype for every state unit (harmless in itself, since
    # nothing ever called the wrongly-named one, but wrong is wrong).
    unit_prototypes = [
        f"void {model_name}_compute_der_{unit_function_suffix(uid, members)}({model_name}_t *v);"
        if set(members) & set(layout.x)
        else f"void {model_name}_compute_{unit_function_suffix(uid, members)}({model_name}_t *v);"
        for uid, members in units.items()
    ]

    return "\n".join([
        f'#include "{model_name}.h"',
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <string.h>",
        "",
        *unit_prototypes,
        "",
        "int main(int argc, char **argv) {",
        "    double t_end = argc > 1 ? atof(argv[1]) : 10.0;",
        "    double dt = argc > 2 ? atof(argv[2]) : 0.01;",
        f"    {model_name}_t v;",
        # Zero-init, not just leaving it uninitialized: the shared
        # variable-slot layout (src/model_layout.py) is the UNION of
        # baseline and changed variable names, so a change that REMOVES
        # a variable (e.g. Feature 7's R3 removal) leaves its slot with
        # no equation ever writing to it in the changed model's driver.
        # Uninitialized stack memory there is not just cosmetic: it read
        # as different (random) garbage between separately-built full
        # and incremental binaries, making a real correctness check
        # (output must be identical) fail on OTHERWISE-irrelevant
        # orphaned slots. memset makes any unwritten slot deterministic.
        "    memset(&v, 0, sizeof(v));",
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


def dll_filename(model_name: str, unit_id: str, members: list[str]) -> str:
    """Same base name as the unit's .c/.o file (unit_function_suffix),
    just a .dll extension -- src/c_build.py's *_dynamic() build
    functions write each unit's shared library under exactly this name,
    and this function is the single place both codegen and the build
    functions derive it from, so they cannot silently drift apart."""
    return f"{model_name}_unit_{unit_function_suffix(unit_id, members)}.dll"


def generate_unit_driver_dynamic(model_name: str, ir: dict, layout: Layout) -> str:
    """Feature: relink ceiling fix. Same simulation logic as
    generate_unit_driver() above, but every unit is called through a
    function pointer resolved at RUNTIME via LoadLibrary/GetProcAddress
    against that unit's own per-unit .dll, instead of a direct call
    resolved at STATIC LINK TIME against a .o baked into this one
    executable. This is what makes an incremental rebuild's "link" step
    stop scaling with the total unit count N: recompiling one changed
    unit only ever touches that unit's own .dll, and this driver
    executable itself only ever links against the Windows runtime, never
    against any unit's object code, so it does not need relinking when a
    unit's IMPLEMENTATION changes (only when the SET of units changes,
    e.g. a sensor-add/removal change type, and even then its own link is
    O(1) in N -- see src/c_build.py's incremental_rebuild_dynamic()).
    Verified mechanism directly before building this: a MinGW-compiled
    __declspec(dllexport) function loads and calls correctly via
    LoadLibraryA/GetProcAddress, is unaffected by being present when the
    SAME source is instead statically linked, and a DLL file rebuilt
    under an unchanged filename is picked up correctly by the next
    driver process (Windows does not stale-cache it once the previous
    process holding the handle has exited)."""
    prefix = model_prefix(model_name)
    m = compute_matching(ir)
    units = compute_matched_units(ir)
    order = unit_eval_order(ir)
    driver_name_to_c = _driver_name_to_c(layout)
    p_index_map = {n: i for i, n in enumerate(layout.p)}
    x_index_map = {n: i for i, n in enumerate(layout.x)}

    param_inits = [
        f"    v.p[{p_index_map[n]}] = {expr_to_c(ir['p'][n]['start'], driver_name_to_c)};"
        for n in _param_eval_order(ir, layout) if n in ir["p"]
    ]
    state_inits = [
        f"    v.x[{x_index_map[n]}] = {expr_to_c(ir['x'][n]['start'], driver_name_to_c)};"
        for n in layout.x if n in ir["x"]
    ]

    def _load_line(var_name: str, dll_name: str, fn_name: str) -> str:
        return f'    {prefix}_unit_fn {var_name} = {prefix}_load_unit("{dll_name}", "{fn_name}");'

    algebraic_var_names = {uid: f"fn_{unit_function_suffix(uid, units[uid])}" for uid in order}
    algebraic_loads = [
        _load_line(
            algebraic_var_names[uid], dll_filename(model_name, uid, units[uid]),
            f"{model_name}_compute_{unit_function_suffix(uid, units[uid])}",
        )
        for uid in order
    ]
    algebraic_calls = [f"    {algebraic_var_names[uid]}(&v);" for uid in order]

    state_unit_ids = [uid for uid, members in units.items() if set(members) & set(layout.x)]
    der_var_names = {uid: f"fn_der_{sanitize_c_ident(units[uid][0])}" for uid in state_unit_ids}
    der_loads = [
        _load_line(
            der_var_names[uid], dll_filename(model_name, uid, units[uid]),
            f"{model_name}_compute_der_{sanitize_c_ident(units[uid][0])}",
        )
        for uid in state_unit_ids
    ]
    der_calls = [f"    {der_var_names[uid]}(&v);" for uid in state_unit_ids]

    state_updates = [f"    v.x[{i}] += dt * v.dx[{i}];" for i in range(len(layout.x))]

    header_row = ",".join(["time"] + layout.x + layout.y)
    print_row = ['printf("%g", v.time);'] + \
        [f'printf(",%g", v.x[{i}]);' for i in range(len(layout.x))] + \
        [f'printf(",%g", v.y[{i}]);' for i in range(len(layout.y))] + \
        ['printf("\\n");']

    return "\n".join([
        f'#include "{model_name}.h"',
        "#include <windows.h>",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <string.h>",
        "",
        f"typedef void (*{prefix}_unit_fn)({model_name}_t *);",
        "",
        f"static {prefix}_unit_fn {prefix}_load_unit(const char *dll_name, const char *fn_name) {{",
        "    HMODULE h = LoadLibraryA(dll_name);",
        "    if (!h) {",
        '        fprintf(stderr, "LoadLibrary(%s) failed: %lu\\n", dll_name, GetLastError());',
        "        exit(1);",
        "    }",
        f"    {prefix}_unit_fn fn = ({prefix}_unit_fn)GetProcAddress(h, fn_name);",
        "    if (!fn) {",
        '        fprintf(stderr, "GetProcAddress(%s, %s) failed: %lu\\n", dll_name, fn_name, GetLastError());',
        "        exit(1);",
        "    }",
        "    return fn;",
        "}",
        "",
        "int main(int argc, char **argv) {",
        "    double t_end = argc > 1 ? atof(argv[1]) : 10.0;",
        "    double dt = argc > 2 ? atof(argv[2]) : 0.01;",
        f"    {model_name}_t v;",
        "    memset(&v, 0, sizeof(v));",
        "    v.time = 0.0;",
        *algebraic_loads,
        *der_loads,
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


def write_unit_sources_dynamic(model_name: str, ir: dict, layout: Layout, out_dir: Path) -> dict[str, Path]:
    """Same as write_unit_sources() above, except the driver is
    generated by generate_unit_driver_dynamic() -- LoadLibrary/
    GetProcAddress dispatch against per-unit .dll files, not direct
    calls resolved at static link time. The unit .c sources themselves
    are identical either way (dllexport is a no-op for static linking,
    verified directly -- see c_build.py's module docstring); only the
    driver and how the caller subsequently builds it differ."""
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
    driver_path.write_text(generate_unit_driver_dynamic(model_name, ir, layout), encoding="utf-8")
    written["driver"] = driver_path

    return written
