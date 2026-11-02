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


@pytest.mark.parametrize("kwargs", [{"split": "unknown"}, {"max_attempts": 0}, {"threshold": 1}])
def test_invalid_evaluation_configuration_fails_before_requests(kwargs):
    with pytest.raises(ValueError):
        evaluate(**kwargs)
