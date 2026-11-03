# Experiment 009: threshold and carrier-budget sensitivity

Run date: November 3, 2026 (Asia/Kolkata).

## Method

A fixed grid crosses thresholds 2, 3, and 5 with carrier budgets 3, 6, and 8.
Each cell runs all eight frozen synthetic cases in baseline, halt, and recover
modes: 216 fresh loopback HTTP runs with the scripted faulty policy. There is no
model inference. The one-order-refresh limit is unchanged. The manifest hash
matches experiment 005; the default cell reproduces its outcomes and counts.

```bash
uv sync --locked --extra dev
uv run python -m agent_loop_recovery.sensitivity --output artifacts/sensitivity.json
uv run python -m agent_loop_recovery.evaluation --split all --threshold 5 \
  --max-attempts 6 --output artifacts/threshold-5-budget-6-traces.json
```

The [compact artifact](results/sensitivity.json) retains all case-level outcomes,
parameters, and request counts. The second command illustrates how to reproduce
full event traces for a cell. No elapsed-time or token-savings claim is made.

## Measured results

Cells show **completed out of 8 / total business requests / false detector
interventions**. Business requests include carrier and order reads, even failures.

| Carrier budget | Threshold | Baseline | Halt | Recover |
| ---: | ---: | --- | --- | --- |
| 3 | 2 | 2 / 20 / 0 | 1 / 14 / 2 | 2 / 22 / 2 |
| 3 | 3 | 2 / 20 / 0 | 2 / 20 / 0 | 2 / 20 / 0 |
| 3 | 5 | 2 / 20 / 0 | 2 / 20 / 0 | 2 / 20 / 0 |
| 6 | 2 | 3 / 34 / 0 | 1 / 14 / 2 | 2 / 23 / 2 |
| 6 | 3 | 3 / 34 / 0 | 2 / 20 / 1 | 3 / 29 / 1 |
| 6 | 5 | 3 / 34 / 0 | 3 / 30 / 0 | 4 / 36 / 0 |
| 8 | 2 | 3 / 42 / 0 | 1 / 14 / 2 | 2 / 23 / 2 |
| 8 | 3 | 3 / 42 / 0 | 2 / 20 / 1 | 3 / 29 / 1 |
| 8 | 5 | 3 / 42 / 0 | 3 / 30 / 0 | 4 / 38 / 0 |

Threshold 2 falsely interrupts both propagation-delay cases and recovery completes
only 2/8 with budgets 6 or 8. Threshold 3 preserves the two-request delay but
abandons the four-request delay, completing 3/8. Threshold 5 lets both delays
complete naturally and repairs the obsolete label on carrier request 6, reaching
4/8 with either larger budget. At budget 6 that repair succeeds on the last
permitted request. Increasing the threshold also spends more requests on errors
that cannot be repaired: at budget 8 recovery uses 38 business requests rather
than 29 at threshold 3.

With budget 3 and threshold at least 3, exhaustion precedes detection; all three
modes match at 2/8 and 20 requests. Zero false interventions in those cells does
not indicate a successful detector. At threshold 2, recovery can repair the
obsolete label within three carrier requests, but loses the short-delay success:
aggregate completion remains 2/8, with two extra order reads overall.

## Interpretation and limits

There is a concrete tradeoff between waiting long enough for legitimate retries,
leaving budget for repair, and spending requests on irreparable state. These
results do not select a production threshold. The held-out cases have already
been inspected; this sweep is descriptive sensitivity analysis, not a new
held-out validation or evidence of generalization. Defaults remain unchanged.
The delay fixtures advance by request count rather than elapsed time. Immediate
refresh and backoff comparisons remain in experiments 006 and 008; they do not
use this detector threshold and are not rerun in this grid.

Validation: locked dependency sync, Ruff lint and format checks, all 77 tests,
and the original demo passed. Artifact checks verified all 216 row budgets,
one-refresh bounds, business-request sums, unchanged manifest, and default-cell
reproduction. Live-model inference remains unverified after experiment 003.
