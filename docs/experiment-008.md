# Experiment 008: held-out baseline comparison

Run date: November 3, 2026 (Asia/Kolkata).

## Method

Run the frozen four-case held-out split with all five deterministic strategies,
using fresh loopback HTTP services and graph state for each of 20 traces. Carrier
budget remains 8, detector threshold 3, and order refresh budget 1. Neither
parameters nor fixture membership changed. These cases were already inspected in
experiment 005; this is a comparison on a fixed split, not a blind evaluation.
No model inference or external business service is used.

```bash
uv sync --locked --extra dev
uv run python -m agent_loop_recovery.evaluation --split held-out --include-baselines \
  --output artifacts/held-out-baselines.json
uv run pytest -q
```

[Full measured traces](results/held-out-baselines.json) retain the same manifest
hash as experiment 005 and reproduce its original three strategies' outcomes and
request counts. Counts include failed requests; business requests are carrier
plus order requests.

## Results

| Strategy | Completed / 4 | Carrier | Order | False detector interventions | Premature escalations |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 1 | 22 | 0 | 0 | 0 |
| halt | 0 | 10 | 0 | 1 | 0 |
| recover | 0 | 13 | 3 | 1 | 1 |
| immediate-refresh | 0 | 11 | 3 | 0 | 1 |
| bounded-backoff | 1 | 22 | 0 | 0 | 0 |

On the four-request propagation delay, baseline and backoff complete on carrier
request 5. Halt pauses at request 3; recovery escalates after 3 carrier and 1 order
request because the refreshed reference is unchanged. Immediate refresh also
escalates, after just 1 carrier and 1 order request. Its lower request count
comes with a lost completion. Backoff requests four waits totaling 0.11 seconds
on this case. Delay advances by request count, so waiting has no causal benefit
in these fixtures and is not a real carrier latency measurement.

The other held-out cases cannot complete: an order identity mismatch, absent
replacement shipment, and carrier outage. Immediate refresh refuses the mismatch
after 1 carrier and 1 order read, exhausts 8 carrier requests plus 1 order read
when the replacement is absent, and escalates on the first carrier outage.
Backoff exhausts 8 requests on each unrepairable reference and escalates on the
first outage. These explicit failure outcomes are not successful answers.

## Metric interpretation and limits

`false_intervention` continues to mean a detector interruption on a fixture marked
recoverable through ordinary retries. New per-row `premature_escalation` means
an escalated terminal outcome on such a fixture. It exposes harm from a policy
that never triggers the detector. The labels overlap for recovery; do not add
them together. Halt is paused, so it has a false intervention but no escalation.
These are fixture-ground-truth labels, not production error-rate estimates.

All five strategies fail at least one useful task across the broader fixtures:
immediate refresh repairs obsolete labels cheaply but abandons delays; backoff
preserves delay completion but cannot repair stale state. This comparison does
not establish detector superiority. Four authored held-out cases do not support
statistical generalization, token savings, or monetary savings. Live inference
remains unverified after experiment 003. Threshold and budget sensitivity are not
measured in this report.
