"""Measure a fixed threshold/budget grid over the frozen synthetic fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_loop_recovery.evaluation import evaluate

THRESHOLDS = (2, 3, 5)
BUDGETS = (3, 6, 8)


def sweep() -> dict:
    cells = []
    manifest_hash = None
    for budget in BUDGETS:
        for threshold in THRESHOLDS:
            result = evaluate("all", max_attempts=budget, threshold=threshold)
            manifest_hash = result["manifest_sha256"]
            # Keep case-level measurements small; the evaluation CLI reproduces
            # complete event traces for any individual parameter pair.
            rows = [{k: v for k, v in row.items() if k != "trace"} for row in result["rows"]]
            cells.append({"parameters": result["parameters"], "rows": rows})
    return {
        "schema_version": 1,
        "inference": "none; deterministic scripted policy",
        "manifest_sha256": manifest_hash,
        "thresholds": list(THRESHOLDS),
        "carrier_budgets": list(BUDGETS),
        "cells": cells,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = sweep()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Measured {len(result['cells'])} cells / 216 case-strategy runs")


if __name__ == "__main__":
    main()
