# Experiment 001: obsolete tracking reference

Run date: November 1, 2026 (Asia/Kolkata).

## Question

Can a bounded controller recover a stalled support workflow by repairing its
cached shipment reference? Does detection alone accomplish the customer task?

## Method

Run the same LangGraph workflow in three modes against freshly initialized HTTP
fixtures. The agent policy is scripted to reproduce an unsuccessful retry pattern;
it is not an LLM. An obsolete shipping label produces a carrier 404; the order
service returns the replacement label. No external business service is contacted.

Defaults: maximum 8 carrier requests, detector threshold 3 consecutive matching
failures, at most 1 recovery. Each mode has an independent in-memory checkpointer
and fresh HTTP service state. The experiment measures actual carrier requests and
terminal outcomes. Recovery adds a separate order-service request.

Reproduce:

```bash
uv run loop-recovery --verbose --output artifacts/stale-label.json
uv run loop-recovery --scenario healthy
uv run loop-recovery --scenario carrier-delay
uv run loop-recovery --scenario unrecoverable
uv run loop-recovery --scenario order-outage
uv run pytest -q
```

## Observed outcomes

Cells show `outcome / carrier requests / recovery attempts`.

| Scenario | Hard limit only | Detect and halt | Detect and recover |
| --- | --- | --- | --- |
| Obsolete label | budget exhausted / 8 / 0 | paused / 3 / 0 | completed / 4 / 1 |
| Healthy tracking | completed / 1 / 0 | completed / 1 / 0 | completed / 1 / 0 |
| Carrier propagation delay (first 2 requests fail) | completed / 3 / 0 | completed / 3 / 0 | completed / 3 / 0 |
| Order system returns unchanged reference | budget exhausted / 8 / 0 | paused / 3 / 0 | escalated / 3 / 1 |
| Order service unavailable | budget exhausted / 8 / 0 | paused / 3 / 0 | escalated / 3 / 1 |

For the obsolete label, recovery makes **5 total business-service requests**: 4
carrier requests and 1 order refresh. Baseline makes 8 carrier requests and fails
to answer. These numbers depend on the chosen hard limit and detector threshold;
they are not a general percentage improvement.

Tests also verify that a second stall after refreshing cannot trigger another
recovery, successful repeated calls do not match the detector, evidence stays
isolated by order and epoch, a carrier outage takes an explicit error path, and
a low hard budget can terminate before the detector activates.

## What this demonstrates

Halting stops wasted work but leaves the task incomplete. A separate, bounded
recovery action can repair state and allow successful continuation. Checkpoint
inspection confirms that halt mode really pauses at the gate before any refresh;
resume executes the recovery node and completes using the new reference.

## What it does not demonstrate

- That a real LLM naturally produces these retries, or would fail to self-correct.
- That rules outperform simpler explicit error handling. Immediate order refresh
  is an important future baseline and may be the best choice for this workflow.
- That three failures reliably imply a loop. A longer legitimate carrier delay
  would also match this rule. There is no statistical accuracy claim from 5 fixtures.
- Token savings, calibrated confidence, semantic understanding, network-scale
  performance, durable recovery, or production carrier behavior.

The next experiment should introduce a real model that may retry, self-correct,
or escalate, without instructing it to loop. Preserve all outcomes and compare
with immediate refresh and backoff baselines before claiming detector value.
