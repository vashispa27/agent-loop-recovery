import httpx
import pytest

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.failure_checks import evaluate_failures
from agent_loop_recovery.services import ServiceClient, fixture_services


def test_failure_matrix_has_bounded_requests_and_correct_terminal_outcomes():
    rows = evaluate_failures()["rows"]
    expected = [
        ("escalated", 1, 0, False),
        ("escalated", 3, 1, True),
        ("escalated", 6, 1, True),
        ("budget_exhausted", 3, 0, False),
        ("budget_exhausted", 4, 1, True),
        ("completed", 4, 1, True),
    ]
    for row, (status, carrier, refresh, interrupted) in zip(rows, expected, strict=True):
        trace = row["trace"]
        assert trace["status"] == status
        assert trace["carrier_calls"] == carrier
        assert trace["recovery_attempts"] == refresh
        assert trace["interrupted"] == interrupted
        assert len(row["requests"]) == carrier + refresh
        assert not trace["policy_calls"]
    for row in rows[:2]:
        assert row["trace"]["events"][-1]["result"]["error"] == "service_timeout"


@pytest.mark.parametrize("mode", ["baseline", "halt", "recover"])
def test_exact_threshold_budget_does_not_pause_or_refresh(mode):
    with fixture_services("stale-label") as client:
        trace = run_experiment(client, mode, "stale-label", max_attempts=3)
    assert trace["status"] == "budget_exhausted"
    assert trace["carrier_calls"] == 3
    assert trace["recovery_attempts"] == 0
    assert not trace["interrupted"]


@pytest.mark.parametrize("exception", [httpx.ConnectTimeout, httpx.ReadTimeout])
def test_timeout_is_sanitized(exception):
    def respond(request):
        raise exception("private diagnostic", request=request)

    client = ServiceClient("http://fixture.invalid", transport=httpx.MockTransport(respond))
    assert client.track("synthetic") == {"http_status": 503, "error": "service_timeout"}
