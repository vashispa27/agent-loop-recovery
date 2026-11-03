"""Simple deterministic alternatives to detecting a stalled policy."""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from agent_loop_recovery.policy import PolicyContext, PolicyDecision


class ImmediateRefreshPolicy:
    """Refresh once after the first not-found; retain the graph's safety limits."""

    name = "immediate-refresh"

    def decide(self, context: PolicyContext) -> PolicyDecision:
        if (
            context.observations
            and context.observations[-1].error == "shipment_not_found"
            and context.recoveries < context.max_recoveries
        ):
            return PolicyDecision("refresh_order", reason="Refresh after first not-found")
        return PolicyDecision("track", context.tracking_id, "Track current trusted reference")


class BoundedBackoffPolicy:
    """Retry the current reference with capped exponential waits, without refreshing.

    The graph bounds carrier attempts. Wait records expose requested delays;
    they are not measured wall-clock latency. Inject a sleeper for unit tests.
    """

    name = "bounded-backoff"

    def __init__(
        self,
        base_seconds: float = 0.01,
        cap_seconds: float = 0.04,
        *,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if (
            not math.isfinite(base_seconds)
            or not math.isfinite(cap_seconds)
            or base_seconds <= 0
            or cap_seconds < base_seconds
        ):
            raise ValueError("Finite positive base and cap >= base required")
        self.base_seconds = base_seconds
        self.cap_seconds = cap_seconds
        self.sleeper = sleeper
        self.waits: list[float] = []

    def decide(self, context: PolicyContext) -> PolicyDecision:
        delay = 0.0
        if context.attempts and context.observations[-1].error == "shipment_not_found":
            # Saturate before exponentiating to keep large budgets safe.
            exponent = min(context.attempts - 1, 1023)
            delay = min(self.cap_seconds, self.base_seconds * 2.0**exponent)
            self.sleeper(delay)
            self.waits.append(delay)
        return PolicyDecision("track", context.tracking_id, f"Retry after {delay:g} seconds")
