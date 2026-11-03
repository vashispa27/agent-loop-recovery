# Experiment 007: timeout and exhausted-budget behavior

Run date: November 3, 2026 (Asia/Kolkata).

## Method

Six scripted-policy runs use the real HTTP client with an injected `httpx`
transport. Timeout cases raise `ReadTimeout` at the transport boundary; they do
not wait for a real network timeout and do not measure network latency. Other
cases return synthetic HTTP responses. No inference or external service is used.

```bash
uv run python -m agent_loop_recovery.failure_checks --output artifacts/failure-checks.json
uv run pytest -q
```

[Published traces](results/failure-checks.json) include every requested path and
terminal outcome. The regular loopback HTTP demo remains a separate control.

## Measured outcomes

| Fault or boundary | Carrier budget | Outcome | Carrier calls | Order calls | Interrupted |
| --- | ---: | --- | ---: | ---: | --- |
| Carrier timeout | 8 | escalated | 1 | 0 | no |
| Order timeout | 8 | escalated | 3 | 1 | yes |
| Persistent not-found after refresh | 8 | escalated | 6 | 1 | yes |
| Budget ends exactly at detector threshold | 3 | budget_exhausted | 3 | 0 | no |
| Budget ends after refresh | 4 | budget_exhausted | 4 | 1 | yes |
| Success on final permitted request | 4 | completed | 4 | 1 | yes |

Timeouts now retain the sanitized `service_timeout` error in tool observations,
separate from other unavailable-service failures. Carrier timeouts escalate
immediately without a stall verdict; order timeouts consume the single refresh
attempt and escalate. Raw exception diagnostics are excluded.

Previously, reaching the detector threshold on the last allowed carrier request
could pause and refresh despite having no remaining carrier budget. Exhaustion
now takes precedence over detection at that boundary. Recovery also checks the
carrier budget before issuing an order request. A successful final carrier call
still completes; the budget does not discard a useful result.

## Limits

These are deterministic failure-path checks, not reliability rates or live model
results. The existing two-second HTTP timeout is a per-operation limit, not an
end-to-end deadline. Backoff waits and policy inference have separate bounds.
There is no hard cancellation of an in-flight business request. The experiment
does not compare held-out policy performance or estimate token savings.
