from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.model_policy import CodexPolicy
from agent_loop_recovery.policy import ScriptedPolicy
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
    parser.add_argument("--policy", choices=("scripted", "codex"), default="scripted")
    parser.add_argument("--model", default="gpt-6.1-sol", help="Model used by the optional policy.")
    parser.add_argument("--policy-timeout", type=float, default=60)
    parser.add_argument("--policy-max-calls", type=int, default=4)
    args = parser.parse_args()
    if args.max_attempts < 1 or args.threshold < 2:
        parser.error("max-attempts must be positive and threshold must be at least 2")
    if not 0 < args.policy_timeout <= 300 or not 1 <= args.policy_max_calls <= 32:
        parser.error("policy-timeout must be in (0, 300] and policy-max-calls in [1, 32]")

    modes = ("baseline", "halt", "recover") if args.mode == "compare" else (args.mode,)
    reports = []
    print(f"Scenario: {args.scenario} | Policy: {args.policy} | Local HTTP fixtures\n")
    print(f"{'Mode':<12} {'Outcome':<20} {'Carrier calls':>14} {'Recovery attempts':>18}")
    for mode in modes:
        try:
            policy = (
                CodexPolicy(
                    args.model, timeout=args.policy_timeout, max_calls=args.policy_max_calls
                )
                if args.policy == "codex"
                else ScriptedPolicy()
            )
        except ValueError as exc:
            parser.error(str(exc))
        # Each mode gets a fresh service instance; delay counters cannot leak between modes.
        with fixture_services(args.scenario) as client:
            report = run_experiment(
                client, mode, args.scenario, args.max_attempts, args.threshold, policy
            )
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
    if args.policy == "scripted":
        print("\nScripted runs measure tool calls, not LLM tokens or API cost.")
    else:
        print("\nModel usage and decisions are in policy_calls; no monetary savings are inferred.")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reports, indent=2) + "\n")
        print(f"Full traces: {args.output}")


if __name__ == "__main__":
    main()
