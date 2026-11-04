# Experiment 012: clean installation and continuous verification

Run date: November 4, 2026 (Asia/Kolkata).

A fresh local Git clone with no existing virtual environment installed the locked
project with uv 0.13.5 and CPython 3.11.15 on macOS ARM64. The proposed workflow
and smoke-check files were copied into that clone before checking them; ignored
artifacts and the original environment were not copied. The dependency cache was
available, so this is not a cold-cache or offline installation test.

## Reproduction

```bash
uv sync --locked --extra dev --python 3.11
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/verify_demo.py
git diff --exit-code
```

The working tree passed all 84 tests in 53.12 seconds. The isolated clone passed
all 84 tests in 53.81 seconds. Both passed Ruff lint and format checks and locked
installation. No dependency or lockfile changes were required. The smoke command
invokes the installed CLI, verifies its exact scripted outcomes and request
counts, checks that no model calls occurred, and exports fresh demo and published
held-out traces to two nonempty offline HTML files. Baseline exhausted eight
carrier requests, halt paused after three, and recovery completed after four
with one refresh. Exporting published held-out traces does not rerun that matrix.

The new [Checks workflow](../.github/workflows/ci.yml) runs these checks on Ubuntu
with Python 3.11 for pushes and pull requests. Third-party actions are pinned to
commit SHAs, dependencies are locked, repository permissions are read-only, and
checkout does not retain credentials. Its setup follows the official
[uv GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/).
The ten-minute job limit bounds execution. The workflow invokes no live provider.

These local measurements do not themselves establish hosted Linux CI success;
consult the [workflow runs](https://github.com/vashispa27/agent-loop-recovery/actions/workflows/ci.yml)
for the result for a specific commit. The HTML smoke check verifies export, not
browser rendering; browser observations remain in experiment 011. Live-model
inference remains unverified as described in experiment 003.
