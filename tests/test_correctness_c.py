import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from correctness_c import diff_outputs, parse_csv_output

SAMPLE = "time,x,y\n0,1.0,2.0\n0.5,1.5,2.5\n"


def test_identical_outputs_pass_with_zero_error():
    result = diff_outputs(SAMPLE, SAMPLE)
    assert result["pass"] is True
    assert result["max_abs_error"] == 0.0
    assert result["max_rel_error"] == 0.0


def test_corrupted_output_fails_and_reports_the_error():
    """Teeth check: artificially corrupt one output (as the sanity check
    for Feature C1 requires) and confirm the diff reports a mismatch
    rather than silently passing."""
    corrupted = "time,x,y\n0,1.0,2.0\n0.5,999.0,2.5\n"
    result = diff_outputs(SAMPLE, corrupted)
    assert result["pass"] is False
    assert result["max_abs_error"] == 997.5


def test_mismatched_row_count_fails():
    shorter = "time,x,y\n0,1.0,2.0\n"
    result = diff_outputs(SAMPLE, shorter)
    assert result["pass"] is False
    assert "row counts differ" in result["reason"]


def test_mismatched_header_fails():
    different_header = "time,x,z\n0,1.0,2.0\n0.5,1.5,2.5\n"
    result = diff_outputs(SAMPLE, different_header)
    assert result["pass"] is False
    assert "column headers differ" in result["reason"]


def test_parse_csv_output():
    header, rows = parse_csv_output(SAMPLE)
    assert header == ["time", "x", "y"]
    assert rows == [[0.0, 1.0, 2.0], [0.5, 1.5, 2.5]]
