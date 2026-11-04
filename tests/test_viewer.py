import pytest

from agent_loop_recovery.viewer import normalize_traces, render_viewer


def test_trace_content_cannot_close_embedded_script():
    trace = {"events": [{"kind": "tool_result", "result": "</script><script>alert(1)</script>"}]}
    html = render_viewer([trace])
    assert "</script><script>alert(1)" not in html
    assert r"\u003c/script>" in html


def test_demo_and_evaluation_preserve_trace_and_flags():
    trace = {"events": [{"id": 1, "epoch": 1}], "status": "completed"}
    assert normalize_traces([trace]) == [trace]
    result = normalize_traces({"rows": [{"trace": trace, "false_intervention": True}]})
    assert result[0]["false_intervention"] is True
    assert result[0]["events"] == trace["events"]


@pytest.mark.parametrize(
    "data", [{}, [], {"rows": [{"status": "completed"}]}, [None], [{"events": [3]}]]
)
def test_reject_summary_or_malformed_data(data):
    with pytest.raises(ValueError):
        normalize_traces(data)
