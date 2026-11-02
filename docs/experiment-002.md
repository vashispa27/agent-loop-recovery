# Experiment 002: self-correction through structured policy decisions

Run date: November 2, 2026 (Asia/Kolkata).

## Question

Can a policy repair a stale shipment reference before the detector intervenes,
while the graph retains control over tools and recovery budgets?

## Method

The graph accepts `AgentPolicy.decide(PolicyContext) -> PolicyDecision`.
Decisions are `track`, `refresh_order`, or `escalate`. A deliberately simple
`RefreshAfterFailure` policy requests one order refresh after its first failed
carrier lookup, then tracks the current reference. This policy is scripted;
there is no model inference in this experiment.

The integration tests run it in all three modes against fresh local HTTP services
with the obsolete-label fixture. Reproduce with:

```bash
uv sync --locked --extra dev
uv run pytest tests/test_policy.py -q
uv run loop-recovery --verbose --output artifacts/scripted-policy.json
```

The last command retains the intentionally faulty default policy as a control.

## Observed results

| Policy | Mode | Outcome | Carrier requests | Order refreshes | Detector interruption |
| --- | --- | --- | --- | --- | --- |
| Refresh after first failure | baseline | completed | 2 | 1 | no |
| Refresh after first failure | halt | completed | 2 | 1 | no |
| Refresh after first failure | recover | completed | 2 | 1 | no |
| Faulty formatting retries | baseline | budget exhausted | 8 | 0 | no |
| Faulty formatting retries | halt | paused | 3 | 0 | yes |
| Faulty formatting retries | recover | completed | 4 | 1 | yes |

The self-correcting policy makes three total business-service requests. The
faulty policy with detector-triggered recovery makes five. This fixture supports
the simpler explicit refresh strategy; it does not establish the detector as
necessary or better.

## Contract checks

The graph rejects unknown actions, malformed references, and tracking references
that do not match the order's observed reference. Formatting changes are allowed;
a policy cannot guess the replacement reference to bypass refreshing the order.
An explicit escalation performs no business request. Repeated policy-selected
refreshes cannot exceed the one-refresh budget, even in baseline mode.

Completion still requires a successful carrier observation. The policy cannot
manufacture a final customer answer. Policy decisions and tool observations have
separate trace entries. The full suite passed 35 tests.

## Limits

The policy is deterministic and designed for this known failure. No language
model was evaluated, and these figures do not measure token savings or accuracy
on unseen scenarios. The original experiment remains a seeded fault-injection
control. A model-backed policy should be allowed to self-correct or escalate and
must be evaluated without instructions to deliberately loop.
