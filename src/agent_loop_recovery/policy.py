"""Typed, bounded decisions shared by scripted and model-backed policies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

Action = Literal["track", "refresh_order", "escalate"]
_REFERENCE = re.compile(r"[A-Za-z0-9-]{1,128}\Z")


class PolicyError(ValueError):
    """A policy could not return an admissible decision."""


@dataclass(frozen=True)
class ToolObservation:
    tool: str
    http_status: int
    error: str | None
    status: str | None
    tracking_id: str | None


@dataclass(frozen=True)
class PolicyContext:
    order_id: str
    tracking_id: str
    attempts: int
    recoveries: int
    max_attempts: int
    max_recoveries: int
    observations: tuple[ToolObservation, ...]


@dataclass(frozen=True)
class PolicyDecision:
    action: Action
    tracking_id: str | None = None
    reason: str = ""

    def __post_init__(self):
        if self.action not in ("track", "refresh_order", "escalate"):
            raise PolicyError("Unknown policy action")
        if not isinstance(self.reason, str) or len(self.reason) > 500:
            raise PolicyError("Policy reason must be text of at most 500 characters")
        if self.action == "track":
            if not isinstance(self.tracking_id, str) or not _REFERENCE.fullmatch(self.tracking_id):
                raise PolicyError(
                    "Tracking reference must contain 1–128 letters, digits, or hyphens"
                )
        elif self.tracking_id is not None:
            raise PolicyError("Only track decisions may supply a tracking reference")
        if self.action == "escalate" and not self.reason.strip():
            raise PolicyError("Escalation requires a reason")


class AgentPolicy(Protocol):
    name: str

    def decide(self, context: PolicyContext) -> PolicyDecision: ...


class ScriptedPolicy:
    """Fault injection: keep changing ID formatting despite failed observations."""

    name = "scripted-faulty-policy"

    def decide(self, context: PolicyContext) -> PolicyDecision:
        reference = context.tracking_id
        variants = (reference, reference.lower(), reference.replace("-", ""))
        return PolicyDecision(
            "track", variants[context.attempts % len(variants)], "Retry the cached reference"
        )


def policy_context(state: dict, max_attempts: int) -> PolicyContext:
    """Provide typed tool observations, never the mutable graph state itself."""
    observations = tuple(
        ToolObservation(
            tool=event["tool"],
            http_status=event["result"]["http_status"],
            error=event["result"].get("error"),
            status=event["result"].get("status"),
            tracking_id=event["result"].get("tracking_id"),
        )
        for event in state["events"]
        if event["kind"] == "tool_result"
    )
    return PolicyContext(
        order_id=state["order_id"],
        tracking_id=state["tracking_id"],
        attempts=state["attempts"],
        recoveries=state["recoveries"],
        max_attempts=max_attempts,
        max_recoveries=1,
        observations=observations,
    )
