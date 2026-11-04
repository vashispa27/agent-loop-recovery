"""Exercise installed command entry points and verify the synthetic demo contract."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    output = Path("artifacts/ci-demo.json")
    subprocess.run(["loop-recovery", "--output", str(output)], check=True)
    reports = json.loads(output.read_text())
    expected = [
        ("baseline", "budget_exhausted", 8, 0),
        ("halt", "paused", 3, 0),
        ("recover", "completed", 4, 1),
    ]
    actual = [(r["mode"], r["status"], r["carrier_calls"], r["recovery_attempts"]) for r in reports]
    if actual != expected or any(r["policy_calls"] for r in reports):
        raise RuntimeError(f"Unexpected scripted demo outcomes: {actual}")
    for source, target in [
        (output, "artifacts/ci-viewer.html"),
        (Path("docs/results/held-out-baselines.json"), "artifacts/ci-held-out.html"),
    ]:
        subprocess.run(
            [sys.executable, "-m", "agent_loop_recovery.viewer", str(source), "--output", target],
            check=True,
        )
        if not Path(target).is_file() or Path(target).stat().st_size == 0:
            raise RuntimeError(f"Missing viewer export: {target}")
    print("Verified demo contract and two offline exports; no model inference.")


if __name__ == "__main__":
    main()
