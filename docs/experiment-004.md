# Experiment 004: split fixtures and evaluation runner

Run date: November 2, 2026 (Asia/Kolkata).

## Method

The runner freezes eight synthetic cases in `evaluation.CASES`, with four tuning
and four held-out cases. Each row starts fresh loopback HTTP services, a fresh
graph, and the scripted faulty policy. No inference is performed. The manifest
and its SHA-256 are included in every output so changed fixtures are visible.

Tuning cases cover an obsolete reference, healthy tracking, a two-request
propagation delay, and an unchanged order reference. Held-out cases cover a
four-request delay, an order identity mismatch, an absent replacement shipment,
and carrier unavailability. Held-out membership is fixed, but those evaluation
rows have not been run for this report. These cases are authored behavioral
controls, not random samples or evidence of generalization to real users.

Reproduce the measured tuning run:

```bash
uv sync --locked --extra dev
uv run python -m agent_loop_recovery.evaluation --split tuning \
  --output artifacts/tuning-fixtures.json
```

Use `--split held-out` or `--split all` to explicitly evaluate the other split.
The default threshold is 3 and carrier budget is 8; both are CLI options.
The [published tuning artifact](results/tuning-fixtures.json) contains all 12
traces, parameters, manifest, and summary. Elapsed times vary between runs;
request counts and outcomes are deterministic. Timing is not a latency benchmark.

## Observed tuning results

| Mode | Completed / runs | Carrier calls | Order calls | False interventions |
| --- | --- | --- | --- | --- |
| Hard limit only | 2 / 4 | 20 | 0 | 0 |
| Detect and halt | 2 / 4 | 10 | 0 | 0 |
| Detect and recover | 3 / 4 | 11 | 2 | 0 |

Recovery completes the obsolete-label case but escalates when the order reference
is unchanged. All modes complete healthy tracking and the two-request delay.
Counts include failed requests. Total business requests are carrier plus order
calls; these measurements do not imply token or monetary savings.

The false-intervention label means the detector interrupted a fixture explicitly
marked as able to succeed through ordinary retries without a refresh. It is
counted separately from completion. A validation test lowers the threshold to 2:
halt and recover then interrupt the two-request delay, while the hard-limit
baseline completes. Recovery escalates because refreshing returns its existing
reference. Zero false interventions at the default threshold therefore says
little about longer delays; the held-out delay is intended to expose that limit.

## Validation and limits

Tests check split isolation, actual HTTP outcomes, request accounting, independent
delay counters, false-intervention labeling, and invalid runner inputs. The
original demo remains baseline 8 calls, halt 3, recover 4 plus one order refresh.

The runner currently compares only the original three modes with a scripted
policy. Immediate-refresh and bounded-backoff comparisons, full held-out results,
and sensitivity measurements are not supplied here. The optional live policy
remains unverified after the availability failure in experiment 003.
