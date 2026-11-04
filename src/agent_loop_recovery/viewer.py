"""Export demo or evaluation traces as a standalone, offline HTML viewer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def normalize_traces(data: object) -> list[dict]:
    """Accept full CLI traces or evaluation rows; reject summary-only artifacts."""
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty demo list or evaluation rows with full traces")
    traces = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each row must be an object")
        trace = row.get("trace", row)
        if not isinstance(trace, dict) or not isinstance(trace.get("events"), list):
            raise ValueError("Each row must contain a full event trace")
        if not all(isinstance(event, dict) for event in trace["events"]):
            raise ValueError("Trace events must be objects")
        traces.append({**row, **trace})
    return traces


def render_viewer(data: object) -> str:
    # Escape HTML delimiters before embedding JSON in a script data element.
    payload = json.dumps(normalize_traces(data), ensure_ascii=True).replace("<", "\\u003c")
    return TEMPLATE.replace("__TRACE_DATA__", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("Input and output must be different files")
    try:
        html = render_viewer(json.loads(args.input.read_text()))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"Offline viewer: {args.output}")


TEMPLATE = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
<title>Agent Loop Recovery · Trace viewer</title>
<style>
:root{color-scheme:dark;font:16px/1.6 system-ui;background:#101923;color:#e6edf3}
body{max-width:1100px;margin:auto;padding:32px 20px}h1{line-height:1.2}
p{color:#b9c8d6}label{display:block;font-weight:600}select{font:inherit;padding:10px;
background:#1c2b3a;color:inherit;border:1px solid #7890a5;border-radius:6px;max-width:100%}
button{font:inherit;padding:8px 12px;margin:0 8px 8px 0;background:#1c2b3a;
color:inherit;border:1px solid #7890a5;border-radius:6px;cursor:pointer}
#summary p{white-space:pre-line}
:focus-visible{outline:3px solid #69d9c6;outline-offset:3px}
#summary{padding:20px;background:#1c2b3a;margin:24px 0;border-left:4px solid #69d9c6}
details{border-bottom:1px solid #3b5063;padding:12px 0}
summary{cursor:pointer;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#16232f;padding:16px;font-size:13px}
small{color:#b9c8d6}noscript{color:#ffbca8}
</style>
<header><small>AGENT LOOP RECOVERY / LOCAL INSPECTION</small><h1>Follow the recovery trace</h1>
<p>Inspect decisions, tool results, detector evidence and recovery epochs.
This file works offline. Traces may include prompts; share only sanitized data.</p></header>
<main><label for="run">Choose a run</label><select id="run"></select>
<section id="summary" aria-live="polite"></section><h2>Event timeline</h2>
<p>Expand an event to inspect its complete recorded fields. Epochs separate recovery attempts.</p>
<p id="event-count" aria-live="polite"></p>
<button id="expand" type="button" aria-controls="events">Expand all events</button>
<button id="collapse" type="button" aria-controls="events">Collapse all events</button>
<div id="events"></div><h2>Policy calls</h2><div id="policy"></div></main>
<noscript>Enable JavaScript to inspect the embedded traces.</noscript>
<script id="data" type="application/json">__TRACE_DATA__</script>
<script>
const traces=JSON.parse(document.getElementById('data').textContent);
const select=document.getElementById('run');
function node(tag,text){const el=document.createElement(tag);el.textContent=text;return el;}
function detail(parent,label,value){const el=document.createElement('details');
el.append(node('summary',label),node('pre',JSON.stringify(value,null,2)));parent.append(el);}
traces.forEach((t,i)=>{const o=node('option',
`${t.case_id||t.scenario||'Trace'} / ${t.mode} / ${t.status}`);
o.value=i;select.append(o);});
function show(){const t=traces[Number(select.value)];const s=document.getElementById('summary');
s.replaceChildren(node('h2',`${t.status} · ${t.mode}`),
node('p',`Policy: ${t.policy||'unrecorded'}
Carrier requests: ${t.carrier_calls}
Recovery attempts: ${t.recovery_attempts}`),
node('p',t.answer||'No completed customer answer.'));
if(t.false_intervention||t.premature_escalation)s.append(node('p',
`Evaluation flags: false intervention=${!!t.false_intervention};
premature escalation=${!!t.premature_escalation}`));
const events=document.getElementById('events');events.replaceChildren();
document.getElementById('event-count').textContent=`${t.events.length} recorded events`;
t.events.forEach(e=>detail(events,
`#${e.id} · ${e.kind} · epoch ${e.epoch??'—'}${e.tool?' · '+e.tool:''}`,e));
const policy=document.getElementById('policy');policy.replaceChildren();
(t.policy_calls||[]).forEach((p,i)=>detail(policy,`Policy call ${i+1}`,p));
if(!t.policy_calls?.length)policy.append(node('p',
'No model calls recorded. Scripted tool counts do not measure token savings.'));
}
for(const [id,open] of [['expand',true],['collapse',false]]){
document.getElementById(id).addEventListener('click',()=>{
document.querySelectorAll('#events details').forEach(el=>{el.open=open;});});}
select.addEventListener('change',show);show();
</script></html>"""


if __name__ == "__main__":
    main()
