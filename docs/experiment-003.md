# Experiment 003: bounded model-policy transport and availability

Run date: November 2, 2026 (Asia/Kolkata).

## Question

Can the same shipment graph accept an optional structured model decision while
retaining control of tools, recovery, authentication mode, and execution budgets?

## Implementation

`CodexPolicy` invokes a separately installed Codex CLI in a temporary read-only
working directory. It requests the exact `PolicyDecision` schema and validates
the result again before the graph executes it. The prompt permits tracking,
refreshing the order, or escalating; it does not instruct the model to become
stuck. The prompt text and the synthetic observations are saved with each call.

The adapter first verifies ChatGPT sign-in. Provider-key environment variables
are excluded, custom execution configuration is ignored, and the execution
requires ChatGPT authentication with no API-key fallback. Model-driven shell,
browser, app, plugin, and delegation tools are disabled. Actual business HTTP
calls remain in the graph. A per-decision timeout and a separate model-call
limit bound execution; POSIX timeouts kill the child process group.

The CLI features and structured-output flags were checked against Codex CLI
0.155.1 and the official [non-interactive execution documentation](https://learn.chatgpt.com/docs/noninteractive).

## Observed live attempt

Reproduce, assuming an installed CLI and existing ChatGPT sign-in:

```bash
codex --version
codex login status
uv run loop-recovery --policy codex --mode baseline --scenario stale-label \
  --model gpt-6.1-sol --policy-max-calls 1 --policy-timeout 30 \
  --output artifacts/model-policy-smoke.json
```

The CLI authenticated with ChatGPT, but its provider rejected the requested
`gpt-6.1-sol` model with `model_not_found`: the model was not supported for this
CLI/account combination. The adapter classified that response as
`policy_model_unavailable` and the graph escalated before making any carrier or
order-service request. It did not switch models or authentication modes.

| Observation | Result |
| --- | --- |
| Requested model | `gpt-6.1-sol` |
| Requested reasoning effort | medium |
| Attempted model decisions | 1 |
| Valid decisions returned | 0 |
| Carrier requests / order refreshes | 0 / 0 |
| Graph outcome | escalated |
| Usage counters | not provided; no token or cost inference |

The sanitized [result and exact prompt](results/model-policy-smoke.json) are
published with this report. This is a failed availability smoke test, not evidence
of model reasoning, loop detection, self-correction, or a completed task.

## Deterministic transport and graph checks

The test suite uses a local executable that simulates the CLI protocol. It is a
test double, not an LLM. Its three structured responses choose track, refresh,
and track; running that policy against real loopback HTTP fixtures completes
the stale-label task with two carrier requests and one order refresh.

Other checks cover an API-key login rejected before inference, missing binary,
nonzero exit, unavailable model, missing or malformed JSON, unrecognized actions,
call-budget exhaustion, timeout, and child-process cleanup. Secret sentinel
environment variables are excluded from the child. CLI diagnostics are not
copied into public traces. Protocol-fixture usage values are synthetic assertions
and are not reported as real model usage.

Validation:

```bash
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run loop-recovery --output artifacts/scripted-control.json
```

All 57 tests passed. The scripted control remained unchanged: baseline exhausted
8 carrier calls, halt paused after 3, and recovery completed on carrier call 4
with one order refresh.

## Remaining limits

A completed live-model experiment is still unverified. Rerunning with a model
explicitly available to the local CLI would be a separate experiment; any such
run must disclose its actual model and all outcomes. This adapter is for trusted,
local synthetic demonstrations. Do not expose it as a public inference service or
distribute account credentials. No account credentials are included in the repo.
