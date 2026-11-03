"""Reproducible fault-injected HTTP transport checks; no live inference."""

import argparse
import json
from pathlib import Path

import httpx

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.services import NEW_TRACKING, ORDER_ID, ServiceClient


def evaluate_failures():
    rows = []
    for fault, budget in [
        ("carrier-timeout", 8),
        ("order-timeout", 8),
        ("persistent-not-found", 8),
        ("budget-at-threshold", 3),
        ("budget-after-refresh", 4),
        ("success-on-final-attempt", 4),
    ]:
        requests = []

        def respond(request, requests=requests, fault=fault):
            requests.append(request.url.path)
            order = request.url.path.startswith("/orders/")
            if fault == "carrier-timeout" or (fault == "order-timeout" and order):
                raise httpx.ReadTimeout("Injected timeout", request=request)
            if order:
                return httpx.Response(200, json={"order_id": ORDER_ID, "tracking_id": NEW_TRACKING})
            if fault == "success-on-final-attempt" and NEW_TRACKING in request.url.path:
                return httpx.Response(200, json={"status": "in_transit", "latest_event": "Sorted"})
            return httpx.Response(404, json={"error": "shipment_not_found"})

        client = ServiceClient("http://fixture.invalid", transport=httpx.MockTransport(respond))
        trace = run_experiment(client, "recover", "stale-label", max_attempts=budget)
        rows.append({"fault": fault, "budget": budget, "requests": requests, "trace": trace})
    return {"method": "scripted policy with injected HTTP transport", "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evaluate_failures(), indent=2) + "\n")


if __name__ == "__main__":
    main()
