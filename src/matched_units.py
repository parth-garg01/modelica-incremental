"""Feature 2: recompilation units redefined as BLT blocks (src/matching.py),
not strongly-connected components of the hand-built causalized graph
(src/causal_graph.py + src/units.py, phase 2's definition).

The two definitions agree everywhere they can be directly compared (see
tests/test_matched_units.py): both are, at bottom, "which equations must
be regenerated together because they are mutually data-dependent." The
phase-2 SCC-over-causalized-graph approach only ever discovered
integration artifacts and never found a genuine multi-equation block on
any fixture available at the time (states-as-knowns collapses every
coupling that phase 1's raw graph found to singletons). BLT blocks from
a real equation-to-unknown matching are the more general and more
standard definition -- they correctly identify a genuine algebraic loop
as ONE coupled unit (see CoupledAlgebraic below), which the causalized
SCC approach was never actually tested against, because no such fixture
existed until this feature needed one to test with.

Unit ids follow the same convention as src/units.py: the matched
variable names of a block's member equations, sorted and "+"-joined.
Equations matching's Kuhn algorithm could not match (Cauer's two
index-reduction casualties, see docs/findings/cauer-index-reduction.md)
get a unit id of the form "UNMATCHED_<index>" instead of a variable
name, since there is no matched variable to name them after; this is
never hit on any fixture used past Feature 1, but must not crash.
"""
from __future__ import annotations

from matching import blt_blocks, compute_matching


def compute_matched_units(ir: dict) -> dict[str, list[str]]:
    m = compute_matching(ir)
    blocks = blt_blocks(ir, m)

    units: dict[str, list[str]] = {}
    for block in blocks:
        names = sorted(m.eq_to_var.get(i, f"UNMATCHED_{i}") for i in block)
        unit_id = "+".join(names)
        units[unit_id] = names
    return units


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "results/fixtures/CoupledAlgebraic.json"
    ir = json.loads(open(path).read())
    units = compute_matched_units(ir)
    print(f"{path}: {len(units)} units")
    for unit_id, members in units.items():
        print(f"  {unit_id}: {members}")
