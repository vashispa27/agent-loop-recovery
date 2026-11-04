"""Bounded real local-model checks; outputs sanitized synthetic data only."""

import json
import os
import time
from pathlib import Path

from agent_loop_recovery.trace_judge import Event, LocalJudge, suspicious

cases = {
    "search_paraphrases": (["find cats", "search felines", "look for kittens"], "loop"),
    "recurrent_failures": (["timeout", "timeout again", "still timed out"], "loop"),
    "cyclic_actions": (["open A", "open B", "open A", "open B"] * 2, "loop"),
    "pagination": (["page 1: new items", "page 2: new items", "page 3: new items"], "progress"),
    "legitimate_retry": (["timeout", "retry 1", "success: task complete"], "progress"),
    "measurable_progress": (["1 file fixed", "2 files fixed", "3 files fixed"], "progress"),
}
judge = LocalJudge(
    os.environ["MLX_PYTHON"],
    model=os.environ.get("JUDGE_MODEL", "mlx-community/Qwen2.5-0.5B-Instruct-4bit"),
    calls=6,
    timeout=45,
)
rows = []
for name, (outputs, expected) in cases.items():
    events = [
        Event(name, str(i), i, "tool_start", "search" if "search" in name else "act", x)
        for i, x in enumerate(outputs)
    ]
    start = time.monotonic()
    row = {"case": name, "expected": expected, "prefilter": suspicious(events)}
    try:
        row["inference"] = judge.judge(events)
        row["matches_expected"] = (row["inference"]["verdict"] or {}).get("verdict") == expected
    except Exception as exc:
        row["error_type"] = type(exc).__name__
    row["elapsed_seconds"] = time.monotonic() - start
    rows.append(row)
path = Path("docs/results/generic-judge.json")
path.write_text(json.dumps({"results": rows}, indent=2) + "\n")
print(json.dumps(rows, indent=2))
