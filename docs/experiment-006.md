# Experiment 006: immediate refresh and bounded backoff

Run date: November 3, 2026 (Asia/Kolkata).

## Method

Two deterministic policies run with detection disabled and the same graph safety
limits: eight carrier requests and at most one order refresh. Immediate refresh
reads the order after the first shipment-not-found. Bounded backoff keeps the
trusted reference and waits 10, 20, then at most 40 milliseconds before each
subsequent retry. These deliberately short demo delays are not production advice.
There is no inference. Every row uses fresh graph state and local HTTP services.

```bash
uv sync --locked --extra dev
uv run python -m agent_loop_recovery.evaluation --split tuning --include-baselines \
  --output artifacts/simple-baselines.json
```

The [artifact](results/simple-baselines.json) contains 20 tuning traces, including
the three existing modes as controls. Fixture membership, threshold 3, and budget
8 are unchanged. The additional policies are opt-in; the default evaluation and
demo keep their existing behavior. No new held-out baseline comparison is
included in this report.

## Measured tuning results

| Strategy | Completed / runs | Carrier requests | Order requests |
| --- | --- | --- | --- |
| Hard limit, faulty policy | 2 / 4 | 20 | 0 |
| Detect and halt | 2 / 4 | 10 | 0 |
| Detect and recover | 3 / 4 | 11 | 2 |
| Immediate refresh | 2 / 4 | 5 | 3 |
| Bounded backoff | 2 / 4 | 20 | 0 |

Immediate refresh completes the obsolete-label case with two carrier requests
and one order read, compared with recovery's four carrier requests and one order
read. It also refreshes prematurely on the two-request propagation delay: the
order returns the same reference, so the existing recovery validation escalates.
An unchanged order similarly escalates. Healthy tracking completes in one request.

Backoff completes healthy tracking and the two-request delay, which requests waits
of 0.01 and 0.02 seconds. Obsolete and unchanged references each exhaust eight
carrier attempts, requesting seven waits totaling 0.23 seconds per case. No wait
occurs after the final attempt, and no order reads occur. Across all four cases,
requested waits total 0.49 seconds. Traces include individual requested waits and
observed graph elapsed time; scheduler overhead makes these different quantities.

## Interpretation and limits

Immediate refresh is a useful simpler alternative for known stale-reference
errors, but indiscriminate refresh loses a naturally recoverable delay case.
Backoff alone cannot repair an obsolete reference. The fixture's propagation delay
advances by request count, not elapsed time: these results demonstrate the retry
schedule and bounded execution, not any benefit of waiting in a real carrier.

The existing `false_intervention` field counts detector interruptions only. It is
false for these detector-free policies even when immediate refresh is harmful;
completion and order counts expose that failure separately. Do not interpret zero
detector interruptions as zero harmful actions.

Tests cover repair without detector involvement, capped wait sequences, stopping
at the carrier budget, invalid delay configuration, tuning isolation, request
counts, and the premature refresh regression. All data is synthetic. Tool counts
do not measure token savings, monetary cost, or real-world success rates. The
[unavailable live-model experiment](experiment-003.md) remains unverified.
