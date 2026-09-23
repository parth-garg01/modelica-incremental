"""Journal upgrade, phase 3: change injectors for src/scaled_models.py's
generate_rc_ladder(N), mirroring swap_room_conductance's style (a literal
text edit on the generated source, written to its own output path, with
the seed equation known because the injector authored the edit).
"""
from __future__ import annotations

from pathlib import Path


def _edit(source_path: str | Path, out_path: str | Path, old: str, new: str) -> Path:
    text = Path(source_path).read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected exactly one occurrence of {old!r}"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text.replace(old, new), encoding="utf-8")
    return out_path


def swap_segment_resistance(source_path: str | Path, i: int, out_path: str | Path) -> Path:
    """Segment i's current equation divides by 2*R instead of R (a genuine
    formula edit, not a parameter override: the factor is not tied to any
    declared parameter). Seed equation: I{i}."""
    upstream = "Vs" if i == 1 else f"V{i-1}"
    return _edit(
        source_path, out_path,
        f"  I{i} = ({upstream} - V{i})/R;\n",
        f"  I{i} = ({upstream} - V{i})/(2*R);\n",
    )


def add_segment_probe(source_path: str | Path, i: int, out_path: str | Path) -> Path:
    """Add a power probe on segment i: a new variable P{i} and a new
    equation P{i} = V{i}*I{i} (a structural edit: the equation set and
    the variable set both grow by one). Seed equation: P{i}."""
    text = Path(source_path).read_text(encoding="utf-8")
    assert f"Real P{i};" not in text, f"probe P{i} already present"
    assert text.count("\nequation\n") == 1, "expected exactly one equation section"
    text = text.replace("\nequation\n", f"\n  Real P{i};\nequation\n  P{i} = V{i}*I{i};\n")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path
