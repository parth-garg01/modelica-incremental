"""Stable variable-slot layout shared by every recompilation unit's C file
and the driver, for one experiment (a baseline model + its changed
variant).

Built as the UNION of every state/algebraic/parameter name across BOTH
IRs, in first-seen order, so a name present in only one of the two
(e.g. ThermalNetwork's swap drops "Qheater" and adds "Kp"/"Tset") gets
its own stable slot without renumbering any name shared by both. This is
what makes "recompile only the changed unit, relink against cached
objects for the rest" valid: unaffected units are compiled once against
this shared header and never need re-emitting just because some other
part of the model's variable set changed.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Layout:
    x: list[str] = field(default_factory=list)  # states
    y: list[str] = field(default_factory=list)  # algebraics
    p: list[str] = field(default_factory=list)  # parameters

    def name_to_c(self) -> dict[str, str]:
        mapping = {"time": "v->time"}
        for i, n in enumerate(self.x):
            mapping[n] = f"v->x[{i}]"
        for i, n in enumerate(self.y):
            mapping[n] = f"v->y[{i}]"
        for i, n in enumerate(self.p):
            mapping[n] = f"v->p[{i}]"
        return mapping


def _union_first_seen(*name_lists: list[str]) -> list[str]:
    seen: list[str] = []
    seen_set: set[str] = set()
    for names in name_lists:
        for n in names:
            if n not in seen_set:
                seen.append(n)
                seen_set.add(n)
    return seen


def build_layout(*irs: dict) -> Layout:
    return Layout(
        x=_union_first_seen(*[list(ir["x"].keys()) for ir in irs]),
        y=_union_first_seen(*[list(ir["y"].keys()) for ir in irs]),
        p=_union_first_seen(*[list(ir["p"].keys()) for ir in irs]),
    )
