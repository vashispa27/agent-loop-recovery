import pytest

from agent_loop_recovery.evaluation import CASES, evaluate


def test_frozen_splits_have_unique_cases_and_distinct_conditions():
    assert len({case.id for case in CASES}) == len(CASES) == 8
    tuning = {case.config for case in CASES if case.split == "tuning"}
    held_out = {case.config for case in CASES if case.split == "held-out"}
    assert tuning.isdisjoint(held_out)
    assert sum(case.split == "tuning" for case in CASES) == 4


def test_tuning_matrix_measures_http_outcomes_with_fresh_state():
    result = evaluate()
    rows = {(r["case_id"], r["mode"]): r for r in result["rows"]}
    assert len(rows) == 12
    assert {r["split"] for r in rows.values()} == {"tuning"}
    assert rows["obsolete-label", "recover"]["status"] == "completed"
    assert rows["obsolete-label", "recover"]["business_calls"] == 5
    assert rows["unchanged-order", "recover"]["status"] == "escalated"
    for mode in ("baseline", "halt", "recover"):
        delay = rows["two-request-delay", mode]
        assert delay["carrier_calls"] == 3
        assert delay["status"] == "completed"
        assert not delay["interrupted"]
        assert not delay["false_intervention"]
    assert result["summary"]["recover"] == {
        "runs": 4,
        "completed": 3,
        "carrier_calls": 11,
        "order_calls": 2,
        "false_interventions": 0,
    }


def test_false_intervention_is_measured_against_fixture_ground_truth():
    # Changing the threshold exposes a premature interruption even on tuning data.
    result = evaluate(threshold=2)
    delay_rows = [r for r in result["rows"] if r["case_id"] == "two-request-delay"]
    assert [r["false_intervention"] for r in delay_rows] == [False, True, True]
    assert delay_rows[0]["status"] == "completed"
    assert delay_rows[2]["status"] == "escalated"


def test_held_out_matrix_exposes_delay_regression_and_bounds_failed_repairs():
    result = evaluate("held-out")
    rows = {(r["case_id"], r["mode"]): r for r in result["rows"]}
    assert len(rows) == 12
    assert {r["split"] for r in rows.values()} == {"held-out"}
    delay = [rows["four-request-delay", mode] for mode in ("baseline", "halt", "recover")]
    assert [r["status"] for r in delay] == ["completed", "paused", "escalated"]
    assert [r["carrier_calls"] for r in delay] == [5, 3, 3]
    assert [r["false_intervention"] for r in delay] == [False, True, True]
    mismatch = rows["mismatched-order", "recover"]
    assert mismatch["status"] == "escalated"
    assert (mismatch["carrier_calls"], mismatch["order_calls"]) == (3, 1)
    absent = rows["replacement-absent", "recover"]
    assert absent["status"] == "escalated"
    assert (absent["carrier_calls"], absent["order_calls"]) == (6, 1)
    assert absent["trace"]["recovery_attempts"] == 1
    assert {e["epoch"] for e in absent["trace"]["events"]} == {0, 1}
    for mode in ("baseline", "halt", "recover"):
        outage = rows["carrier-outage", mode]
        assert outage["status"] == "escalated"
        assert (outage["carrier_calls"], outage["order_calls"]) == (1, 0)
        assert not outage["interrupted"]
    for row in rows.values():
        events = row["trace"]["events"]
        assert row["carrier_calls"] == sum(e.get("tool") == "track_shipment" for e in events)
        assert row["order_calls"] == sum(e.get("tool") == "refresh_order" for e in events)
        assert row["business_calls"] == row["carrier_calls"] + row["order_calls"]


@pytest.mark.parametrize("kwargs", [{"split": "unknown"}, {"max_attempts": 0}, {"threshold": 1}])
def test_invalid_evaluation_configuration_fails_before_requests(kwargs):
    with pytest.raises(ValueError):
        evaluate(**kwargs)
