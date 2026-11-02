import pytest

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.policy import PolicyDecision, PolicyError
from agent_loop_recovery.services import NEW_TRACKING, fixture_services


class RefreshAfterFailure:
    name = "refresh-after-failure"

    def decide(self, context):
        if context.observations and not context.recoveries:
            assert context.observations[-1].error == "shipment_not_found"
            return PolicyDecision("refresh_order", reason="Recheck the source of truth")
        return PolicyDecision("track", context.tracking_id)


@pytest.mark.parametrize("mode", ["baseline", "halt", "recover"])
def test_policy_can_self_correct_without_detector_intervention(mode):
    with fixture_services("stale-label") as client:
        report = run_experiment(client, mode, "stale-label", policy=RefreshAfterFailure())
    assert report["status"] == "completed"
    assert report["carrier_calls"] == 2
    assert report["recovery_attempts"] == 1
    assert not report["interrupted"]
    assert report["events"][-1]["result"]["tracking_id"] == NEW_TRACKING


def test_policy_can_escalate_without_a_business_request():
    class Escalate:
        name = "escalate"

        def decide(self, context):
            return PolicyDecision("escalate", reason="Need a support specialist")

    class NoRequests:
        def track(self, _reference):
            pytest.fail("Escalation should not call the carrier")

        def order(self, _order_id):
            pytest.fail("Escalation should not refresh the order")

    report = run_experiment(NoRequests(), "recover", "stale-label", policy=Escalate())
    assert report["status"] == "escalated"
    assert report["carrier_calls"] == report["recovery_attempts"] == 0
    assert "support specialist" in report["answer"]


def test_policy_cannot_guess_a_tracking_reference_not_observed_from_order():
    class InventedReference:
        name = "invented-reference"

        def decide(self, context):
            return PolicyDecision("track", NEW_TRACKING)

    with fixture_services("stale-label") as client:
        report = run_experiment(client, "recover", "stale-label", policy=InventedReference())
    assert report["status"] == "escalated"
    assert report["carrier_calls"] == 0


def test_policy_selected_refresh_cannot_exceed_recovery_budget():
    class AlwaysRefresh:
        name = "always-refresh"

        def decide(self, context):
            return PolicyDecision("refresh_order")

    with fixture_services("stale-label") as client:
        report = run_experiment(client, "baseline", "stale-label", policy=AlwaysRefresh())
    assert report["status"] == "escalated"
    assert report["recovery_attempts"] == 1
    assert report["carrier_calls"] == 0


@pytest.mark.parametrize(
    "values",
    [
        {"action": "delete_order"},
        {"action": "track"},
        {"action": "track", "tracking_id": "../other-order"},
        {"action": "track", "tracking_id": "x" * 129},
        {"action": "refresh_order", "tracking_id": "injected-reference"},
        {"action": "escalate"},
        {"action": "escalate", "reason": "x" * 501},
    ],
)
def test_malformed_decisions_are_rejected(values):
    with pytest.raises(PolicyError):
        PolicyDecision(**values)


def test_noncontract_policy_output_escalates_safely():
    class WrongType:
        name = "wrong-type"

        def decide(self, context):
            return {"action": "track", "tracking_id": context.tracking_id}

    with fixture_services("healthy") as client:
        report = run_experiment(client, "recover", "healthy", policy=WrongType())
    assert report["status"] == "escalated"
    assert report["carrier_calls"] == 0
