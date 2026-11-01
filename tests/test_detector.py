import pytest

from agent_loop_recovery.detector import NoProgressDetector


def call(index, epoch=0, order_id="A", error="shipment_not_found", status=404):
    return {
        "id": index,
        "kind": "tool_result",
        "tool": "track_shipment",
        "order_id": order_id,
        "epoch": epoch,
        "args": {"tracking_id": f"different-format-{index}"},
        "result": {"http_status": status, "error": error},
    }


def test_changed_arguments_do_not_hide_same_goal_failure():
    verdict = NoProgressDetector().evaluate([call(i) for i in range(3)], "A", 0)
    assert verdict.is_stalled
    assert verdict.evidence_ids == (0, 1, 2)


def test_evidence_cannot_leak_between_orders_or_recovery_epochs():
    events = [call(1), call(2), call(3, epoch=1), call(4, order_id="B")]
    assert not NoProgressDetector().evaluate(events, "A", 0).is_stalled
    assert not NoProgressDetector().evaluate(events, "A", 1).is_stalled


def test_success_breaks_failure_streak():
    events = [call(1), call(2), call(3, error=None, status=200), call(4)]
    assert not NoProgressDetector().evaluate(events, "A", 0).is_stalled


def test_successful_repeated_tool_use_is_allowed():
    events = [call(i, error=None, status=200) for i in range(8)]
    assert not NoProgressDetector().evaluate(events, "A", 0).is_stalled


def test_different_failures_do_not_match_this_rule():
    events = [call(1), call(2), call(3, error="rate_limited", status=429)]
    assert not NoProgressDetector().evaluate(events, "A", 0).is_stalled


def test_invalid_threshold():
    with pytest.raises(ValueError):
        NoProgressDetector(1)
