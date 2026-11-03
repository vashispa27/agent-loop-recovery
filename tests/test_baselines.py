import pytest

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.baselines import BoundedBackoffPolicy, ImmediateRefreshPolicy
from agent_loop_recovery.evaluation import evaluate
from agent_loop_recovery.services import fixture_services


def test_immediate_refresh_repairs_without_detector():
    with fixture_services("stale-label") as client:
        trace = run_experiment(client, "baseline", "stale-label", policy=ImmediateRefreshPolicy())
    assert trace["status"] == "completed"
    assert trace["carrier_calls"] == 2
    assert not trace["interrupted"]
    assert sum(e.get("tool") == "refresh_order" for e in trace["events"]) == 1


def test_backoff_waits_are_capped_and_stop_at_attempt_budget():
    waits = []
    policy = BoundedBackoffPolicy(sleeper=waits.append)
    with fixture_services("stale-label") as client:
        trace = run_experiment(client, "baseline", "stale-label", max_attempts=5, policy=policy)
    assert trace["status"] == "budget_exhausted"
    assert trace["carrier_calls"] == 5
    assert waits == [0.01, 0.02, 0.04, 0.04]
    assert policy.waits == waits
    assert not any(e.get("tool") == "refresh_order" for e in trace["events"])


@pytest.mark.parametrize("base,cap", [(0, 1), (1, 0.5), (float("nan"), 1), (1, float("inf"))])
def test_invalid_backoff_parameters(base, cap):
    with pytest.raises(ValueError):
        BoundedBackoffPolicy(base, cap)


def test_tuning_baselines_expose_refresh_tradeoff():
    result = evaluate(include_baselines=True)
    assert len(result["rows"]) == 20
    rows = {(r["case_id"], r["mode"]): r for r in result["rows"]}
    immediate = rows["two-request-delay", "immediate-refresh"]
    backoff = rows["two-request-delay", "bounded-backoff"]
    assert immediate["status"] == "escalated"
    assert immediate["order_calls"] == 1
    assert not immediate["interrupted"]
    assert backoff["status"] == "completed"
    assert backoff["requested_wait_seconds"] == [0.01, 0.02]
    assert backoff["order_calls"] == 0
    assert all(not r["trace"]["policy_calls"] for r in result["rows"])
