"""Permanent regression test for the bug class found in src/matching.py:
networkx's hopcroft_karp_matching turned out to be non-deterministic
ACROSS PROCESSES because Python's per-process string hash randomization
(PYTHONHASHSEED) leaked into its internal traversal order. Fixed there
with a hand-rolled Kuhn's algorithm, but the fix for one call site
doesn't prove the rest of the pipeline (dependency graph construction,
strongly-connected-component partitioning) is safe -- this test spawns
src/determinism_probe.py as a fresh subprocess under several different
explicit PYTHONHASHSEED values and requires byte-identical output across
all of them, end to end (raw units, causalized units, matching, BLT
blocks), for every fixture including the real MSL Cauer filter.

Manually audited once with 20 process runs under unset (freely
randomized) PYTHONHASHSEED before this test was written -- all 20
identical. This test pins a handful of specific seeds instead (fast,
deterministic to run in CI) as the permanent, automatic version of that
audit.
"""
import os
import subprocess
import sys
from pathlib import Path

PROBE = str(Path(__file__).resolve().parent.parent / "src" / "determinism_probe.py")
PYTHON = sys.executable

# Deliberately varied, not sequential: 0 is a common "disable
# randomization" convention and might mask a bug that only shows up with
# certain hash distributions, so most seeds here are arbitrary large
# values plus 0 and 1 as boundary cases.
SEEDS = ["0", "1", "42", "8675309", "2147483647"]


def _run_with_seed(seed: str) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    result = subprocess.run(
        [PYTHON, PROBE],
        env=env,
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert result.returncode == 0, f"probe failed under PYTHONHASHSEED={seed}: {result.stderr}"
    return result.stdout


def test_full_pipeline_is_deterministic_across_hash_seeds():
    outputs = {seed: _run_with_seed(seed) for seed in SEEDS}
    reference_seed = SEEDS[0]
    reference = outputs[reference_seed]
    for seed, output in outputs.items():
        assert output == reference, (
            f"pipeline output differs between PYTHONHASHSEED={reference_seed} and "
            f"PYTHONHASHSEED={seed} -- a hash-order-dependent nondeterminism regression"
        )
