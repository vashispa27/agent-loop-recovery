"""An inspectable rule baseline, not an LLM or semantic classifier."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    is_stalled: bool
    reason: str
    evidence_ids: tuple[int, ...] = ()


class NoProgressDetector:
    def __init__(self, threshold: int = 3):
        if threshold < 2:
            raise ValueError("threshold must be at least 2")
        self.threshold = threshold

    def evaluate(self, events: list[dict], order_id: str, epoch: int) -> Verdict:
        # Scope evidence to one business goal and the current recovery epoch.
        calls = [
            event
            for event in events
            if event.get("kind") == "tool_result"
            and event.get("tool") == "track_shipment"
            and event.get("order_id") == order_id
            and event.get("epoch") == epoch
        ]
        recent = calls[-self.threshold :]
        if len(recent) < self.threshold:
            return Verdict(False, "insufficient_evidence")
        if all(
            event["result"].get("error") == "shipment_not_found"
            and event["result"].get("http_status") == 404
            for event in recent
        ):
            return Verdict(
                True,
                "Repeated shipment lookup failures for the same order without progress",
                tuple(event["id"] for event in recent),
            )
        return Verdict(False, "no_repeated_failure")
