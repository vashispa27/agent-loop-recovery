"""Frozen synthetic splits and a reproducible, scripted HTTP evaluation runner."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.baselines import BoundedBackoffPolicy, ImmediateRefreshPolicy
from agent_loop_recovery.services import (
    NEW_TRACKING,
    OLD_TRACKING,
    FixtureConfig,
    fixture_services,
)


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    split: str
    initial_tracking: str
    config: FixtureConfig
    recoverable_without_refresh: bool = False


# Freeze membership before evaluating the held-out split. These are synthetic
# behavioral cases, not independent samples from a real-world distribution.
CASES = (
    EvaluationCase("obsolete-label", "tuning", OLD_TRACKING, FixtureConfig()),
    EvaluationCase("known-shipment", "tuning", NEW_TRACKING, FixtureConfig(), True),
    EvaluationCase(
        "two-request-delay", "tuning", NEW_TRACKING, FixtureConfig(delay_requests=2), True
    ),
    EvaluationCase(
        "unchanged-order", "tuning", OLD_TRACKING, FixtureConfig(order_tracking=OLD_TRACKING)
    ),
    EvaluationCase(
        "four-request-delay", "held-out", NEW_TRACKING, FixtureConfig(delay_requests=4), True
    ),
    EvaluationCase(
        "mismatched-order", "held-out", OLD_TRACKING, FixtureConfig(order_id="ORD-OTHER")
    ),
    EvaluationCase(
        "replacement-absent", "held-out", OLD_TRACKING, FixtureConfig(shipment_exists=False)
    ),
    EvaluationCase(
        "carrier-outage", "held-out", NEW_TRACKING, FixtureConfig(carrier_unavailable=True)
    ),
)


def manifest() -> list[dict]:
    return [asdict(case) for case in CASES]


def evaluate(
    split: str = "tuning",
    *,
    max_attempts: int = 8,
    threshold: int = 3,
    include_baselines: bool = False,
) -> dict:
    if split not in ("tuning", "held-out", "all"):
        raise ValueError("Unknown evaluation split")
    if max_attempts < 1 or threshold < 2:
        raise ValueError("Positive attempt budget and threshold >= 2 required")
    modes = ("baseline", "halt", "recover")
    if include_baselines:
        modes += ("immediate-refresh", "bounded-backoff")
    rows = []
    for case in CASES:
        if split != "all" and case.split != split:
            continue
        for mode in modes:
            policy = (
                ImmediateRefreshPolicy()
                if mode == "immediate-refresh"
                else BoundedBackoffPolicy()
                if mode == "bounded-backoff"
                else None
            )
            # Never reuse request counters or graph state between rows.
            with fixture_services("stale-label", config=case.config) as client:
                trace = run_experiment(
                    client,
                    "baseline" if policy else mode,
                    case.id,
                    max_attempts,
                    threshold,
                    initial_tracking=case.initial_tracking,
                    policy=policy,
                )
            order_calls = sum(e.get("tool") == "refresh_order" for e in trace["events"])
            rows.append(
                {
                    "case_id": case.id,
                    "split": case.split,
                    "status": trace["status"],
                    "mode": mode,
                    "carrier_calls": trace["carrier_calls"],
                    "order_calls": order_calls,
                    "business_calls": trace["carrier_calls"] + order_calls,
                    "interrupted": trace["interrupted"],
                    # Fixture-defined label: useful retrying would eventually succeed.
                    "false_intervention": (
                        trace["interrupted"] and case.recoverable_without_refresh
                    ),
                    "requested_wait_seconds": getattr(policy, "waits", []),
                    "trace": trace,
                }
            )
    summaries = {}
    for mode in modes:
        group = [row for row in rows if row["mode"] == mode]
        summaries[mode] = {
            "runs": len(group),
            "completed": sum(r["status"] == "completed" for r in group),
            "carrier_calls": sum(r["carrier_calls"] for r in group),
            "order_calls": sum(r["order_calls"] for r in group),
            "false_interventions": sum(r["false_intervention"] for r in group),
        }
    return {
        "schema_version": 1,
        "inference": "none; deterministic policies",
        "include_baselines": include_baselines,
        "split": split,
        "parameters": {"max_attempts": max_attempts, "threshold": threshold},
        "manifest_sha256": hashlib.sha256(
            json.dumps(manifest(), sort_keys=True).encode()
        ).hexdigest(),
        "manifest": manifest(),
        "summary": summaries,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("tuning", "held-out", "all"), default="tuning")
    parser.add_argument("--max-attempts", type=int, default=8)
    parser.add_argument("--threshold", type=int, default=3)
    parser.add_argument("--include-baselines", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_attempts < 1 or args.threshold < 2:
        parser.error("max-attempts must be positive; threshold must be >= 2")
    result = evaluate(
        args.split,
        max_attempts=args.max_attempts,
        threshold=args.threshold,
        include_baselines=args.include_baselines,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
