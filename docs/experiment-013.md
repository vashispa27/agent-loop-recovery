# Generic trace triage and local judge boundary

This independently implemented prototype was informed by review of the reference
[trace schema](https://github.com/Tusharaws/agent-circuit-breaker/blob/455c0d52aa4ceda7b3c1f37df3ce385564913554/schemas/src/schemas/trace_event.py),
[callbacks](https://github.com/Tusharaws/agent-circuit-breaker/blob/455c0d52aa4ceda7b3c1f37df3ce385564913554/interceptor/src/interceptor/graph_hooks.py),
[prefilter](https://github.com/Tusharaws/agent-circuit-breaker/blob/455c0d52aa4ceda7b3c1f37df3ce385564913554/evaluator/src/evaluator/prefilter.py)
and [MLX adapter](https://github.com/Tusharaws/agent-circuit-breaker/blob/455c0d52aa4ceda7b3c1f37df3ce385564913554/evaluator/src/evaluator/slm.py).
No upstream source is vendored. No compatible upstream license was identified.

## Implemented behavior

`TraceCapture` accepts generic LangGraph node and tool callbacks, pairs start/end
by run ID, preserves thread identity, assigns monotonic arrival sequence numbers,
and sanitizes payloads before storing bounded in-memory windows. Thread and active
run counts are bounded; oldest entries are evicted and counted. There is no
transport reorder buffer: ordering is callback arrival order, not distributed
causal order. Identifier fields must be opaque IDs. Regex redaction covers secret
keys, bearer strings and emails, not arbitrary PII or credentials in free text.
There is no claim of comprehensive sanitization.

The prefilter counts event kind plus tool/node identity while ignoring arguments.
Unidentified events do not count. Healthy pagination deliberately reaches the
judge; prefilter suspicion must never be treated as a halt decision.

`LocalJudge` runs a separate MLX worker with a hard subprocess timeout, a call
budget, a prompt size limit and a 200-token generation cap. It requires exact
JSON verdict/confidence/reason fields, finite confidence and bounded reason text.
Malformed generations yield a null verdict; timeout and worker failures propagate.
There is no fallback detector or automatic halt on these failures. Default model
is `mlx-community/Qwen2.5-0.5B-Instruct-4bit`, which was not cached or evaluated.
The optional worker needs an independently installed `mlx-lm` environment.

## Actual local inference

A cached LiquidAI model was initially attempted but lacked safetensors; all six
worker attempts failed before generation. The available cached
`Qwen/Qwen3-0.6B-MLX-4bit` then ran locally via MLX, offline, without paid services.
The [first six generations](results/generic-judge-thinking.json) consumed their
200-token cap in reasoning and produced no parseable verdict. With thinking
disabled, the [second six generations](results/generic-judge.json) still violated
the strict JSON contract (fences and extra fields). Both artifacts contain actual
prompts, sanitized outputs, model IDs and measured wall latency including load.
Usage is null because this adapter does not collect token counters.

All six final cases reached the prefilter: search paraphrases, recurrent failures,
cyclic actions, healthy pagination, legitimate retry, and measurable progress.
There were **zero valid structured verdicts in six final attempts**. False positive
and false negative rates cannot be established from invalid verdicts. Expected
labels are hand-authored synthetic controls, not a validated benchmark. No
successful semantic detection or capture-to-halt timing was measured.

Reproduce using an existing cached model and MLX environment:

```bash
MLX_PYTHON=/path/to/mlx/environment/bin/python HF_HUB_OFFLINE=1 \
JUDGE_MODEL=Qwen/Qwen3-0.6B-MLX-4bit \
uv run python scripts/check_generic_judge.py
```

## Validation and capability gaps

Locked sync, Ruff lint and format checks passed. The full suite passed 93 tests
in 52.89 seconds, including real LangGraph callback capture, pairing, window
bounds, redaction, paraphrase triage, malformed verdicts, timeouts and budgets.
`uv run python scripts/verify_demo.py` passed: baseline/halt/recover made 8/3/4
carrier calls, recovery refreshed once, and both offline exports succeeded.
This end-to-end demonstration remains scripted and shipping-specific. Its
checkpoint boundary is the existing `gate` node using `InMemorySaver`; the generic
judge has no connection to that gate. Recovery remains separate and opt-in.

Missing parity components: Redis Streams and durable queue consumption; distributed
ordering and backpressure; complete LLM callbacks and usage capture; comprehensive
PII sanitization; a reliable structured semantic judge; authenticated halt API and
registry; generic checkpoint-backed guard wiring; persisted halt history and
retention cleanup; generic trace/verdict dashboard; create_agent middleware.
Existing offline viewer supports the original demo traces, not this generic schema.
No full architecture parity, generic model-to-halt demonstration, token savings,
or production readiness is claimed. Earlier hosted CI success applies to the
previous commit; consult the current commit's Checks run for its status.
