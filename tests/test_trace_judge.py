import json
import subprocess
from unittest.mock import patch

import pytest
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from agent_loop_recovery.trace_judge import (
    Event,
    LocalJudge,
    TraceCapture,
    parse_verdict,
    sanitize,
    suspicious,
)


def test_real_graph_capture_and_sanitization():
    class State(TypedDict):
        email: str

    graph = StateGraph(State)
    graph.add_node("search", lambda state: state)
    graph.add_edge(START, "search")
    graph.add_edge("search", END)
    capture = TraceCapture()
    graph.compile().invoke(
        {"email": "private@example.com"},
        config={"callbacks": [capture], "configurable": {"thread_id": "t"}},
    )
    events = capture.snapshot("t")
    assert events and events[0].identity == "search"
    assert "private@example.com" not in json.dumps([e.payload for e in events])
    assert [e.sequence for e in events] == sorted(e.sequence for e in events)


def test_pairing_limits_and_paraphrases():
    capture = TraceCapture(window_size=6, max_threads=1, max_active=2)
    for n, query in enumerate(["find cats", "search felines", "look for kittens"]):
        capture.on_tool_start({"name": "search"}, query, run_id=n, metadata={"thread_id": "t"})
        capture.on_tool_end("no new results", run_id=n)
    assert suspicious(capture.snapshot("t"))
    assert all(e.identity == "search" for e in capture.snapshot("t"))
    assert not suspicious([Event("t", str(n), n, "tool_end", "", {}) for n in range(4)])
    capture.on_tool_start({}, "x", run_id=9, metadata={"thread_id": "other"})
    assert not capture.snapshot("t")
    assert capture.dropped == 1
    assert sanitize({"api_key": "secret"}) == {"api_key": "[redacted]"}


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        "[]",
        "garbage",
        '{"verdict":"loop","confidence":true,"reason":"x"}',
        '{"verdict":"loop","confidence":NaN,"reason":"x"}',
        '{"verdict":"loop","confidence":1.1,"reason":"x"}',
    ],
)
def test_malformed(text):
    with pytest.raises(ValueError):
        parse_verdict(text)


def test_timeout_budget_and_prompt_limit():
    judge = LocalJudge("python", calls=1)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 1)):
        with pytest.raises(subprocess.TimeoutExpired):
            judge.judge([])
    with pytest.raises(RuntimeError):
        judge.judge([])
    with pytest.raises(ValueError):
        LocalJudge("python").judge([Event("t", "r", 0, "tool_start", "s", "x" * 25000)])
