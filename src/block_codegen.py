"""Feature 4: C generation for a coupled (non-singleton) BLT block.

Assembles the block's small local linear system (src/linear_block.py)
and solves it directly with Gaussian elimination + partial pivoting, a
general variable-length-array (C99) solver shared by every coupled unit
in a model rather than one hand-sized solver per block.

Scope: linear coupled blocks only (src/linear_block.py raises on any
genuinely nonlinear term -- a product or quotient of two unknowns, or an
unknown inside a transcendental call -- which propagates up through
here). Nonlinear block solves are Feature 6, built only if a real target
model turns out to need one.
"""
from __future__ import annotations

from linear_block import build_linear_system
from model_layout import Layout

_SOLVER_NAME = "rumoca_solve_linear_nxn"

_SOLVER_C = f"""\
static void {_SOLVER_NAME}(int n, real_t A[n][n], real_t *b, real_t *x) {{
    for (int col = 0; col < n; col++) {{
        int pivot = col;
        for (int row = col + 1; row < n; row++) {{
            if (fabs(A[row][col]) > fabs(A[pivot][col])) {{
                pivot = row;
            }}
        }}
        if (pivot != col) {{
            for (int k = 0; k < n; k++) {{
                real_t tmp = A[col][k];
                A[col][k] = A[pivot][k];
                A[pivot][k] = tmp;
            }}
            real_t tmpb = b[col];
            b[col] = b[pivot];
            b[pivot] = tmpb;
        }}
        for (int row = col + 1; row < n; row++) {{
            real_t factor = A[row][col] / A[col][col];
            for (int k = col; k < n; k++) {{
                A[row][k] -= factor * A[col][k];
            }}
            b[row] -= factor * b[col];
        }}
    }}
    for (int row = n - 1; row >= 0; row--) {{
        real_t sum = b[row];
        for (int k = row + 1; k < n; k++) {{
            sum -= A[row][k] * x[k];
        }}
        x[row] = sum / A[row][row];
    }}
}}
"""


def generate_block_unit_c(
    model_name: str, unit_function_name: str, member_equation_indices: list[int],
    unknown_names: list[str], ir: dict, layout: Layout,
    name_to_c: dict[str, str] | None = None,
    y_index_map: dict[str, int] | None = None,
    x_index_map: dict[str, int] | None = None,
) -> str:
    """`member_equation_indices` and `unknown_names` must already be in
    the SAME fixed order (row i's equation corresponds to unknown i).
    `name_to_c`/`y_index_map`/`x_index_map` are optional precomputed
    caches (see Layout.y_index_map()'s docstring): pass them when
    generating many blocks in a loop to avoid rebuilding a dict or
    scanning `layout.y`/`layout.x` with `in`/`.index()` (both O(N)) once
    per unknown per block."""
    if name_to_c is None:
        name_to_c = layout.name_to_c()
    if y_index_map is None:
        y_index_map = layout.y_index_map()
    if x_index_map is None:
        x_index_map = layout.x_index_map()
    equations = [(i, ir["f_x"][i]) for i in member_equation_indices]
    A, b = build_linear_system(equations, unknown_names, name_to_c)
    n = len(unknown_names)

    lines = [f'#include "{model_name}.h"', "#include <math.h>", "", _SOLVER_C, ""]
    lines.append(f"void {model_name}_compute_{unit_function_name}({model_name}_t *v) {{")
    lines.append(f"    real_t A[{n}][{n}];")
    lines.append(f"    real_t b[{n}];")
    lines.append(f"    real_t x[{n}];")
    for i in range(n):
        for j in range(n):
            lines.append(f"    A[{i}][{j}] = {A[i][j]};")
        lines.append(f"    b[{i}] = {b[i]};")
    lines.append(f"    {_SOLVER_NAME}({n}, A, b, x);")
    for i, name in enumerate(unknown_names):
        if name in y_index_map:
            idx = y_index_map[name]
            lines.append(f"    v->y[{idx}] = x[{i}];")
        elif name in x_index_map:
            idx = x_index_map[name]
            lines.append(f"    v->dx[{idx}] = x[{i}];")
        else:
            raise ValueError(f"unknown {name!r} is neither a declared algebraic nor a state")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    from compile import compile_model
    from matched_units import compute_matched_units
    from matching import compute_matching
    from model_layout import build_layout, sanitize_c_ident

    path = sys.argv[1] if len(sys.argv) > 1 else "models/coupled_algebraic/CoupledAlgebraic.mo"
    model_name = sys.argv[2] if len(sys.argv) > 2 else "CoupledAlgebraic"

    result = compile_model(path, model_name)
    layout = build_layout(result.ir)
    m = compute_matching(result.ir)
    units = compute_matched_units(result.ir)

    for unit_id, members in units.items():
        if len(members) <= 1:
            continue
        member_indices = [m.var_to_eq[name] for name in members]
        c_source = generate_block_unit_c(model_name, sanitize_c_ident(unit_id), member_indices, members, result.ir, layout)
        print(c_source)
