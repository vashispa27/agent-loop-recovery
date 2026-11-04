# Experiment 010: offline trace inspection

Run date: November 4, 2026 (Asia/Kolkata).

The new `agent_loop_recovery.viewer` command converts existing full traces into
one offline HTML file. It accepts the CLI's list of reports and the evaluator's
rows containing nested traces. A run selector shows outcomes, policy identity,
carrier counts, recovery attempts, answers and evaluation flags. Expandable
entries retain complete event fields, including detector evidence and epochs;
recorded policy calls have their own section.

Reproduce:

```bash
uv run loop-recovery --output artifacts/viewer-demo.json
uv run python -m agent_loop_recovery.viewer artifacts/viewer-demo.json \
  --output artifacts/trace-viewer.html
uv run python -m agent_loop_recovery.viewer docs/results/held-out-baselines.json \
  --output artifacts/held-out-viewer.html
```

[Export checks](results/viewer-checks.json) record 3 fresh demo traces with 34
events and 20 previously published held-out traces with 175 events. Neither
input contains model calls. The fresh demo retains baseline/halt/recover carrier
counts of 8/3/4 and one recovery refresh. Exporting the held-out artifact does
not rerun its experiment.

Seven focused tests check demo/evaluation normalization, preservation of epochs
and labels, rejection of summary-only or malformed event data, and escaping of
script-closing payloads. JSON is embedded with escaped HTML delimiters; the UI
renders trace fields using text content. A content security policy blocks network
resources. Generated JavaScript passed `node --check`. Locked dependency sync,
Ruff checks and the full Python suite passed (84 tests).

Browser rendering and interactive behavior have not yet been validated. This is
an inspection tool, not a replay engine, schema auditor, or latency benchmark.
It embeds all supplied fields, so exporting is not a sanitization step. No model
inference was attempted; the availability limit from experiment 003 remains.
