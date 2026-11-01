import pytest

from agent_loop_recovery.agent import build_agent, run_experiment
from agent_loop_recovery.services import NEW_TRACKING, OLD_TRACKING, ORDER_ID, fixture_services


@pytest.mark.parametrize(
    ("mode", "status", "calls", "recoveries"),
    [
        ("baseline", "budget_exhausted", 8, 0),
        ("halt", "paused", 3, 0),
        ("recover", "completed", 4, 1),
    ],
)
def test_stale_label_end_to_end(mode, status, calls, recoveries):
    with fixture_services("stale-label") as client:
        report = run_experiment(client, mode, "stale-label")
    assert report["status"] == status
    assert report["carrier_calls"] == calls
    assert report["recovery_attempts"] == recoveries
    if mode == "recover":
        assert report["interrupted"] and report["resumed"]
        assert "in transit" in report["answer"]
        refresh = next(e for e in report["events"] if e.get("tool") == "refresh_order")
        assert refresh["result"]["tracking_id"] == NEW_TRACKING
        assert report["events"][-1]["epoch"] == 1


@pytest.mark.parametrize("mode", ["baseline", "halt", "recover"])
@pytest.mark.parametrize(("scenario", "calls"), [("healthy", 1), ("carrier-delay", 3)])
def test_useful_work_is_not_interrupted(mode, scenario, calls):
    with fixture_services(scenario) as client:
        report = run_experiment(client, mode, scenario)
    assert report["status"] == "completed"
    assert report["carrier_calls"] == calls
    assert not report["interrupted"]
    assert report["recovery_attempts"] == 0


@pytest.mark.parametrize("scenario", ["unrecoverable", "order-outage"])
def test_recovery_failure_escalates_without_retrying_forever(scenario):
    with fixture_services(scenario) as client:
        report = run_experiment(client, "recover", scenario)
    assert report["status"] == "escalated"
    assert report["recovery_attempts"] == 1
    assert report["carrier_calls"] == 3


def test_hard_budget_still_applies_before_detector_threshold():
    with fixture_services("stale-label") as client:
        report = run_experiment(client, "recover", "stale-label", max_attempts=2)
    assert report["status"] == "budget_exhausted"
    assert report["carrier_calls"] == 2
    assert not report["interrupted"]


def test_checkpoint_really_pauses_and_can_resume():
    from langgraph.types import Command

    with fixture_services("stale-label") as client:
        graph = build_agent(client, "halt")
        config = {"configurable": {"thread_id": "test-pause"}}
        initial = {
            "order_id": ORDER_ID,
            "tracking_id": OLD_TRACKING,
            "selected_reference": "",
            "attempts": 0,
            "recoveries": 0,
            "epoch": 0,
            "status": "running",
            "answer": "",
            "decision": {},
            "events": [],
        }
        result = graph.invoke(initial, config)
        assert result["__interrupt__"]
        snapshot = graph.get_state(config)
        assert snapshot.next == ("gate",)
        assert snapshot.values["attempts"] == 3
        assert snapshot.values["recoveries"] == 0
        result = graph.invoke(Command(resume={"action": "refresh_order"}), config)
        assert result["status"] == "completed"
        assert result["attempts"] == 4


def test_second_stall_cannot_trigger_unbounded_recoveries():
    class BrokenCarrier:
        def track(self, _reference):
            return {"http_status": 404, "error": "shipment_not_found"}

        def order(self, _order_id):
            return {"http_status": 200, "order_id": ORDER_ID, "tracking_id": NEW_TRACKING}

    report = run_experiment(BrokenCarrier(), "recover", "stale-label")
    assert report["status"] == "escalated"
    assert report["carrier_calls"] == 6
    assert report["recovery_attempts"] == 1


def test_carrier_outage_uses_explicit_error_route():
    class UnavailableCarrier:
        def track(self, _reference):
            return {"http_status": 503, "error": "service_unavailable"}

    report = run_experiment(UnavailableCarrier(), "recover", "stale-label")
    assert report["status"] == "escalated"
    assert report["carrier_calls"] == 1
    assert not report["interrupted"]
