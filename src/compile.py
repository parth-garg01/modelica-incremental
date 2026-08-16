"""Thin wrapper around the Rumoca Python API: compile a Modelica model and
export its DAE intermediate representation. No mocking, no stubbing: every
call here hits the real compiler.
"""
from __future__ import annotations

import json
import platform
import time
from dataclasses import dataclass
from pathlib import Path

import rumoca as rm


@dataclass
class CompileResult:
    model_name: str
    source_path: str
    ir: dict
    ir_json: str
    compile_seconds: float


def compile_model(source_path: str | Path, model_name: str, roots: list[str] | None = None) -> CompileResult:
    """Compile `model_name` out of `source_path` and export its DAE IR.

    `source_path` is resolved relative to the current working directory,
    matching how `rumoca.Session().load()` resolves paths (no explicit
    `roots` needed for a single-file model). `roots` is needed for any
    model that references an external library (e.g. the Modelica
    Standard Library sparse-cloned into msl_src/) via `import`/qualified
    type names.
    """
    source_path = Path(source_path)
    session = rm.Session(roots=roots) if roots else rm.Session()
    start = time.perf_counter()
    model = session.load(str(source_path), model=model_name)
    elapsed = time.perf_counter() - start
    ir_json = model.to_json(stage="dae")
    ir = json.loads(ir_json)
    return CompileResult(
        model_name=model_name,
        source_path=str(source_path),
        ir=ir,
        ir_json=ir_json,
        compile_seconds=elapsed,
    )


def provenance() -> dict:
    return {
        "rumoca_version": rm.version(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


if __name__ == "__main__":
    result = compile_model("models/one_line/OneLine.mo", "OneLine")
    print(f"Compiled {result.model_name} in {result.compile_seconds:.4f}s")
    print(f"IR is non-empty: {len(result.ir_json) > 0} ({len(result.ir_json)} chars)")
    print("Provenance:", json.dumps(provenance(), indent=2))
