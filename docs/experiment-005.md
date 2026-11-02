# Experiment 005: expanded fixture matrix

Run date: November 2, 2026 (Asia/Kolkata).

## Method

Evaluate all eight frozen synthetic cases in the original three modes: hard
attempt limit, detect and halt, and detect and recover. Each of the 24 runs uses
fresh local HTTP services, graph state, and the scripted fault-injection policy.
No model inference or external business service is used. The carrier budget is
8, the detector threshold is 3, and recovery permits at most one order refresh.
Neither parameters nor fixture membership were changed after inspecting results.

```bash
uv sync --locked --extra dev
uv run python -m agent_loop_recovery.evaluation --split all \
  --output artifacts/expanded-fixtures.json
uv run pytest tests/test_evaluation.py -q
```

The [published artifact](results/expanded-fixtures.json) contains the parameters,
manifest, summaries, all 24 traces, tool results, and policy decisions. Its manifest
SHA-256 is `393bac755eb7cfe17b66e0fee7eb50626c24a41b812eaeb6f0858e266202e3d1`,
identical to [experiment 004](experiment-004.md). All tuning outcomes and request
counts reproduce that earlier artifact. Elapsed milliseconds are observations
from this local run; they are not a latency benchmark or reproducibility target.

## Measured results

Carrier and order counts include failed requests. Business calls are their sum.
A false intervention is a detector interruption on a fixture explicitly labeled
as recoverable through ordinary retries without an order refresh.

| Split | Mode | Completed / runs | Carrier calls | Order calls | Business calls | False interventions |
| --- | --- | --- | --- | --- | --- | --- |
| Tuning | Hard limit | 2 / 4 | 20 | 0 | 20 | 0 |
| Tuning | Halt | 2 / 4 | 10 | 0 | 10 | 0 |
| Tuning | Recover | 3 / 4 | 11 | 2 | 13 | 0 |
| Held-out | Hard limit | 1 / 4 | 22 | 0 | 22 | 0 |
| Held-out | Halt | 0 / 4 | 10 | 0 | 10 | 1 |
| Held-out | Recover | 0 / 4 | 13 | 3 | 16 | 1 |
| All | Hard limit | 3 / 8 | 42 | 0 | 42 | 0 |
| All | Halt | 2 / 8 | 20 | 0 | 20 | 1 |
| All | Recover | 3 / 8 | 24 | 5 | 29 | 1 |

Cells below show `outcome; carrier + order requests`.

| Case | Hard limit | Halt | Recover |
| --- | --- | --- | --- |
| Obsolete label | budget exhausted; 8 + 0 | paused; 3 + 0 | completed; 4 + 1 |
| Known shipment | completed; 1 + 0 | completed; 1 + 0 | completed; 1 + 0 |
| Two-request delay | completed; 3 + 0 | completed; 3 + 0 | completed; 3 + 0 |
| Unchanged order | budget exhausted; 8 + 0 | paused; 3 + 0 | escalated; 3 + 1 |
| Four-request delay | completed; 5 + 0 | paused; 3 + 0 | escalated; 3 + 1 |
| Mismatched order | budget exhausted; 8 + 0 | paused; 3 + 0 | escalated; 3 + 1 |
| Replacement absent | budget exhausted; 8 + 0 | paused; 3 + 0 | escalated; 6 + 1 |
| Carrier outage | escalated; 1 + 0 | escalated; 1 + 0 | escalated; 1 + 0 |

## Interpretation

The four-request delay exposes a concrete regression: the baseline succeeds on
request 5, while detection interrupts on request 3. Recovery then reads the same
reference it already has and escalates. Both detector modes falsely intervene on
the one held-out case labeled recoverable without refresh. Delay here is measured
in request count, not elapsed time; the result does not evaluate timed backoff.

Recovery fixes the obsolete label but loses the longer-delay success. Its aggregate
completion count therefore matches the hard-limit baseline, 3 of 8, despite using
29 rather than 42 business calls. Fewer calls alone do not establish a better
customer outcome. Halt uses 20 calls but completes only 2 of 8 cases.

The mismatch case refuses the other order's reference and makes no further carrier
request. When the replacement shipment is absent, recovery tries the new reference
three times in a fresh epoch, then escalates without a second refresh. A carrier
503 takes the explicit escalation path immediately in all modes and is not counted
as a repeated not-found loop. These outcomes are safety boundaries, not successes.

## Validation and limits

Regression coverage checks held-out split isolation, the delay failure, refusal
of a mismatched order, the one-refresh bound across epochs, outage behavior, and
request totals against actual trace events. Artifact verification checks all 24
rows, unchanged tuning results and manifest, and empty model-call records.

These eight authored cases are behavioral controls, not independent population
samples. Held-out means membership was fixed before this run; it does not imply
real-world generalization or statistical precision. No threshold was selected
using these results. Immediate refresh and bounded backoff are still missing
comparisons, and parameter sensitivity has not been measured here. The failed
[model availability attempt](experiment-003.md) remains the only live attempt;
there is no completed live-model benchmark or token/monetary savings claim.
