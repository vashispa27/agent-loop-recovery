# Experiment 011: browser inspection of offline traces

Run date: November 4, 2026 (Asia/Kolkata).

The viewer now includes event counts and buttons to expand or collapse the entire
event timeline. Request counts use separate lines for easier scanning.

Reproduce the exports using the commands in [experiment 010](experiment-010.md),
then open the generated HTML files locally. Select each run, expand its events,
and compare the fields with the input JSON. No inference is involved.

Chrome 156 on macOS rendered the fresh demo's three runs with 16, 7 and 11 events.
Changing the selector updated outcomes, answers and carrier counts (8/3/4).
Expand-all opened every event in each run; collapse-all closed every event.
At an emulated 375 × 812 viewport, the local file rendered with network emulation
set to Offline and no horizontal document overflow. Visual inspection confirmed
readable summary wrapping. The 20-run held-out export rendered all 175 events;
three runs displayed evaluation flags. Every held-out run fit the narrow viewport.
Keyboard Enter activated the focused expand button and opened all events in the
selected trace. These are browser observations, not an automated cross-browser
regression suite or a comprehensive accessibility audit.

The held-out export reuses published traces; it does not rerun that experiment.
The fresh demo still completes recovery with four carrier calls and one refresh.
No live model benchmark or token savings are established. Policy-call rendering
with actual live inference remains unverified.

[Machine-readable observations](results/browser-checks.json) record this check.
