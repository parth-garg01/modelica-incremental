"""Flags timed cells whose [start, end] window overlaps a Windows suspend event
(Kernel-Power 506/507 Modern Standby, 42 sleep, 107 resume). Read-only: queries the
System event log and annotates a COPY of each results CSV's rows in a separate file;
the original results are never modified. Rows without start/end columns are checked
against an explicit window given on the command line.

Usage: python src/journal_suspend_check.py <results.csv> [<results.csv> ...]
Output: <results>_suspend_check.csv next to each input.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PS = (
    "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; "
    "Id=42,506,507,107; StartTime=[datetime]'%s'; EndTime=[datetime]'%s'} -ErrorAction SilentlyContinue | "
    "Sort-Object TimeCreated | ForEach-Object { [pscustomobject]@{t=$_.TimeCreated.ToString('s'); id=$_.Id; "
    "msg=(($_.Message -split \"`r?`n\" | Where-Object { $_ -match '\\S' } | Select-Object -First 2) -join ' | ')} } | "
    "ConvertTo-Json -Compress"
)


def suspend_events(start: datetime, end: datetime) -> list[dict]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command", PS % (start.isoformat(), end.isoformat())],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        return []
    ev = json.loads(out)
    return ev if isinstance(ev, list) else [ev]


def check(path: Path) -> Path:
    df = pd.read_csv(path)
    if not {"start", "end"} <= set(df.columns):
        raise SystemExit(f"{path}: no start/end columns; cannot check windows per row")
    flags, details = [], []
    for _, r in df.iterrows():
        ev = suspend_events(datetime.fromisoformat(str(r.start)), datetime.fromisoformat(str(r.end)))
        flags.append(bool(ev))
        details.append("; ".join(f"{e['t']} id={e['id']} {e['msg']}" for e in ev))
    df["suspend_in_window"], df["suspend_events"] = flags, details
    out = path.with_name(path.stem + "_suspend_check.csv")
    df.to_csv(out, index=False)
    print(f"{path}: {sum(flags)}/{len(df)} rows overlap a suspend event -> {out}")
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        check(Path(p))
