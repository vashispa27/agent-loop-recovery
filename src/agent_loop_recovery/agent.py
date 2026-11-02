"""LangGraph execution, checkpointed interruption, and bounded state repair."""

from __future__ import annotations

import operator
import time
from typing import Annotated, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent_loop_recovery.detector import NoProgressDetector
from agent_loop_recovery.policy import (
    AgentPolicy,
    PolicyDecision,
    PolicyError,
    ScriptedPolicy,
    policy_context,
)
from agent_loop_recovery.services import (
    NEW_TRACKING,
    OLD_TRACKING,
    ORDER_ID,
    ServiceClient,
    canonical_reference,
)

Mode = Literal["baseline", "halt", "recover"]


class AgentState(TypedDict):
    order_id: str
    tracking_id: str
    selected_reference: str
    planned_action: str
    attempts: int
    recoveries: int
    epoch: int
    status: str
    answer: str
    decision: dict
    events: Annotated[list[dict], operator.add]


def build_agent(
    client: ServiceClient,
    mode: Mode,
    max_attempts: int = 8,
    threshold: int = 3,
    policy: AgentPolicy | None = None,
):
    if mode not in ("baseline", "halt", "recover"):
        raise ValueError(f"Unknown mode: {mode}")
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    detector = NoProgressDetector(threshold)
    policy = policy or ScriptedPolicy()

    def event(state, kind, **values):
        return {
            "id": len(state["events"]) + 1,
            "kind": kind,
            "order_id": state["order_id"],
            "epoch": state["epoch"],
            **values,
        }

    def plan(state):
        if state["attempts"] >= max_attempts:
            return {"status": "budget_exhausted", "answer": "Attempt limit reached; escalate."}
        try:
            choice = policy.decide(policy_context(state, max_attempts))
            if not isinstance(choice, PolicyDecision):
                raise PolicyError("Policy must return a PolicyDecision")
            if choice.action == "track" and canonical_reference(
                choice.tracking_id
            ) != canonical_reference(state["tracking_id"]):
                raise PolicyError("Tracking reference must come from the current order state")
        except PolicyError:
            return {
                "status": "escalated",
                "answer": "Policy could not provide a valid decision; escalate to support.",
                "events": [event(state, "policy_error", reason="invalid_or_unavailable_policy")],
            }
        updates = {
            "planned_action": choice.action,
            "selected_reference": choice.tracking_id or "",
            "events": [
                event(
                    state,
                    "policy_decision",
                    action=choice.action,
                    tracking_id=choice.tracking_id,
                    reason=choice.reason,
                )
            ],
        }
        if choice.action == "escalate":
            updates.update(status="escalated", answer=f"Escalated to support: {choice.reason}")
        return updates

    def track(state):
        reference = state["selected_reference"]
        result = client.track(reference)
        updates = {
            "attempts": state["attempts"] + 1,
            "events": [
                event(
                    state,
                    "tool_result",
                    tool="track_shipment",
                    args={"tracking_id": reference},
                    result=result,
                )
            ],
        }
        if result.get("http_status") == 200 and result.get("status") == "in_transit":
            updates.update(
                status="completed",
                answer=f"Your order is in transit. {result['latest_event']}.",
            )
        elif result.get("http_status") != 404 or result.get("error") != "shipment_not_found":
            # Known transport failures take an explicit route, not a speculative loop verdict.
            updates.update(status="escalated", answer="Carrier unavailable; escalate to support.")
        return updates

    def monitor(state):
        if mode == "baseline":
            return {"decision": {"is_stalled": False, "reason": "detector_disabled"}}
        verdict = detector.evaluate(state["events"], state["order_id"], state["epoch"])
        decision = {
            "is_stalled": verdict.is_stalled,
            "reason": verdict.reason,
            "evidence_ids": list(verdict.evidence_ids),
        }
        updates = {"decision": decision}
        if verdict.is_stalled:
            updates["events"] = [event(state, "loop_detected", **decision)]
            if state["recoveries"] >= 1:
                updates.update(
                    status="escalated", answer="Recovery exhausted; escalate to support."
                )
        return updates

    def gate(state):
        action = interrupt(
            {
                "reason": state["decision"]["reason"],
                "evidence_ids": state["decision"]["evidence_ids"],
                "allowed_actions": ["refresh_order"],
            }
        )
        if not isinstance(action, dict) or action.get("action") != "refresh_order":
            return {"status": "escalated", "answer": "Unsupported recovery action."}
        return {"events": [event(state, "recovery_authorized", action="refresh_order")]}

    def recover(state):
        if state["recoveries"] >= 1:
            return {"status": "escalated", "answer": "Recovery exhausted; escalate to support."}
        # Only a read from the trusted order system is allowed; the policy cannot invent an ID.
        result = client.order(state["order_id"])
        updates = {
            "recoveries": state["recoveries"] + 1,
            "events": [
                event(
                    state,
                    "tool_result",
                    tool="refresh_order",
                    args={"order_id": state["order_id"]},
                    result=result,
                )
            ],
        }
        reference = result.get("tracking_id")
        if (
            result.get("http_status") != 200
            or result.get("order_id") != state["order_id"]
            or not isinstance(reference, str)
            or not reference.strip()
            or canonical_reference(reference) == canonical_reference(state["tracking_id"])
        ):
            updates.update(
                status="escalated",
                answer="Order refresh failed or provided no new shipment reference; escalate.",
            )
        else:
            updates.update(tracking_id=reference, epoch=state["epoch"] + 1)
        return updates

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
    graph.add_node("track", track)
    graph.add_node("monitor", monitor)
    graph.add_node("gate", gate)
    graph.add_node("recover", recover)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan",
        lambda s: (
            END
            if s["status"] != "running"
            else ("recover" if s["planned_action"] == "refresh_order" else "track")
        ),
    )
    graph.add_conditional_edges("track", lambda s: END if s["status"] != "running" else "monitor")
    graph.add_conditional_edges(
        "monitor",
        lambda s: (
            END if s["status"] != "running" else ("gate" if s["decision"]["is_stalled"] else "plan")
        ),
    )
    graph.add_conditional_edges("gate", lambda s: END if s["status"] != "running" else "recover")
    graph.add_conditional_edges("recover", lambda s: END if s["status"] != "running" else "plan")
    return graph.compile(checkpointer=InMemorySaver())


def run_experiment(
    client: ServiceClient,
    mode: Mode,
    scenario: str,
    max_attempts: int = 8,
    threshold: int = 3,
    policy: AgentPolicy | None = None,
    *,
    initial_tracking: str | None = None,
) -> dict:
    policy = policy or ScriptedPolicy()
    graph = build_agent(client, mode, max_attempts, threshold, policy)
    initial: AgentState = {
        "order_id": ORDER_ID,
        "tracking_id": initial_tracking
        or (NEW_TRACKING if scenario in ("healthy", "carrier-delay") else OLD_TRACKING),
        "selected_reference": "",
        "planned_action": "track",
        "attempts": 0,
        "recoveries": 0,
        "epoch": 0,
        "status": "running",
        "answer": "",
        "decision": {},
        "events": [],
    }
    # Separate LangGraph safety ceiling; attempt limit above counts actual carrier requests.
    config = {"configurable": {"thread_id": "demo"}, "recursion_limit": max_attempts * 5 + 20}
    started = time.perf_counter()
    result = graph.invoke(initial, config=config)
    interrupted = bool(result.get("__interrupt__"))
    resumed = False
    if interrupted and mode == "recover":
        result = graph.invoke(Command(resume={"action": "refresh_order"}), config=config)
        resumed = True
    state = graph.get_state(config).values
    return {
        "mode": mode,
        "scenario": scenario,
        "policy": policy.name,
        "status": "paused" if result.get("__interrupt__") else state["status"],
        "carrier_calls": state["attempts"],
        "recovery_attempts": state["recoveries"],
        "interrupted": interrupted,
        "resumed": resumed,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "answer": state["answer"],
        "events": state["events"],
        "policy_calls": list(getattr(policy, "calls", [])),
    }
