from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.services import SCENARIOS, fixture_services


def main():
    parser = argparse.ArgumentParser(
        description="Compare hard limits, loop detection, and recovery."
    )
    parser.add_argument(
        "--mode", choices=("compare", "baseline", "halt", "recover"), default="compare"
    )
    parser.add_argument("--scenario", choices=SCENARIOS, default="stale-label")
    parser.add_argument("--max-attempts", type=int, default=8)
    parser.add_argument("--threshold", type=int, default=3)
    parser.add_argument("--output", type=Path, help="Write full JSON traces (synthetic data only).")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.max_attempts < 1 or args.threshold < 2:
        parser.error("max-attempts must be positive and threshold must be at least 2")

    modes = ("baseline", "halt", "recover") if args.mode == "compare" else (args.mode,)
    reports = []
    print(f"Scenario: {args.scenario} | Policy: scripted-faulty-policy | Local HTTP fixtures\n")
    print(f"{'Mode':<12} {'Outcome':<20} {'Carrier calls':>14} {'Recovery attempts':>18}")
    for mode in modes:
        # Each mode gets a fresh service instance; delay counters cannot leak between modes.
        with fixture_services(args.scenario) as client:
            report = run_experiment(client, mode, args.scenario, args.max_attempts, args.threshold)
        reports.append(report)
        print(
            f"{mode:<12} {report['status']:<20} "
            f"{report['carrier_calls']:>14} {report['recovery_attempts']:>18}"
        )
        if args.verbose:
            for event in report["events"]:
                if event["kind"] == "tool_result":
                    print(f"  #{event['id']} {event['tool']} {event['args']} → {event['result']}")
                else:
                    print(f"  #{event['id']} {event['kind']}")
            if report["answer"]:
                print("  " + report["answer"])
    print("\nScripted runs measure tool calls, not LLM tokens or API cost.")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reports, indent=2) + "\n")
        print(f"Full traces: {args.output}")


if __name__ == "__main__":
    main()
