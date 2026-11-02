import json
import os
import textwrap

import pytest

from agent_loop_recovery.agent import run_experiment
from agent_loop_recovery.model_policy import CodexPolicy, build_policy_prompt, parse_decision
from agent_loop_recovery.policy import PolicyContext, PolicyDecision, PolicyError, ToolObservation
from agent_loop_recovery.services import OLD_TRACKING, ORDER_ID, fixture_services


def context():
    return PolicyContext(ORDER_ID, OLD_TRACKING, 0, 0, 8, 1, ())


def fake_cli(tmp_path, *, login="Logged in using ChatGPT", behavior="decide"):
    """A real local process simulating the CLI protocol; never model inference."""
    audit = tmp_path / "audit.json"
    executable = tmp_path / "fake codex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent(f"""\
            import json, os, sys, time
            from pathlib import Path
            if 'login' in sys.argv:
                print({login!r})
                raise SystemExit(0)
            Path({str(audit)!r}).write_text(json.dumps({{'argv':sys.argv,'env_keys':list(os.environ)}}))
            if {behavior!r} == 'timeout':
                time.sleep(5)
            if {behavior!r} == 'failure':
                print('private credential diagnostics', file=sys.stderr)
                raise SystemExit(1)
            if {behavior!r} == 'model-unavailable':
                message=json.dumps({{'error':{{'code':'model_not_found'}}}})
                print(json.dumps({{'type':'error','message':message}}))
                raise SystemExit(1)
            prompt=sys.stdin.read()
            state=json.loads(prompt.split('Observations and budgets:\\n')[1])
            failed=bool(state['observations']) and state['observations'][-1]['error']
            decision=(
                {{'action':'refresh_order','tracking_id':None,'reason':'Check the order source'}}
                if failed and not state['recoveries'] else
                {{'action':'track','tracking_id':state['tracking_id'],'reason':'Track label'}}
            )
            if {behavior!r} != 'missing':
                out=Path(sys.argv[sys.argv.index('--output-last-message')+1])
                out.write_text('not JSON' if {behavior!r} == 'invalid' else json.dumps(decision))
            print(json.dumps({{'type':'turn.completed','usage':{{'input_tokens':100,'output_tokens':20}}}}))
        """)
    )
    executable.chmod(0o700)
    return str(executable), audit


def test_fake_transport_performs_bounded_self_correction_over_http(tmp_path, monkeypatch):
    binary, audit = fake_cli(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("CODEX_API_KEY", "test-secret")
    monkeypatch.setenv("UNRELATED_PROJECT_SECRET", "test-secret")
    policy = CodexPolicy(binary=binary)
    with fixture_services("stale-label") as client:
        report = run_experiment(client, "recover", "stale-label", policy=policy)
    assert report["status"] == "completed"
    assert report["carrier_calls"] == 2
    assert report["recovery_attempts"] == 1
    assert not report["interrupted"]
    assert len(report["policy_calls"]) == 3
    # These are protocol-fixture values, not measured live-model tokens.
    assert report["policy_calls"][0]["usage"] == {"input_tokens": 100, "output_tokens": 20}
    captured = json.loads(audit.read_text())
    assert not {"OPENAI_API_KEY", "CODEX_API_KEY", "UNRELATED_PROJECT_SECRET"} & set(
        captured["env_keys"]
    )
    assert "--ignore-user-config" in captured["argv"]
    assert 'forced_login_method="chatgpt"' in captured["argv"]
    assert captured["argv"][captured["argv"].index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in captured["argv"]
    assert "shell_tool" in captured["argv"]
    assert "apps" in captured["argv"]


def test_api_key_login_is_rejected_before_inference(tmp_path):
    binary, audit = fake_cli(tmp_path, login="Logged in using an API key")
    policy = CodexPolicy(binary=binary)
    with pytest.raises(PolicyError, match="chatgpt_login_required"):
        policy.decide(context())
    assert not audit.exists()
    assert policy.calls[0]["status"] == "failed"


def test_policy_call_budget_prevents_another_process(tmp_path):
    binary, _ = fake_cli(tmp_path)
    policy = CodexPolicy(binary=binary, max_calls=1)
    assert policy.decide(context()).action == "track"
    with pytest.raises(PolicyError, match="policy_call_budget_exhausted"):
        policy.decide(context())
    assert len(policy.calls) == 1


@pytest.mark.parametrize(
    "behavior", ["failure", "missing", "invalid", "timeout", "model-unavailable"]
)
def test_transport_failure_escalates_without_business_requests(tmp_path, behavior):
    binary, _ = fake_cli(tmp_path, behavior=behavior)
    policy = CodexPolicy(binary=binary, timeout=0.2 if behavior == "timeout" else 2)
    with fixture_services("healthy") as client:
        report = run_experiment(client, "recover", "healthy", policy=policy)
    assert report["status"] == "escalated"
    assert report["carrier_calls"] == 0
    assert report["policy_calls"][0]["status"] == "failed"
    assert "private credential" not in json.dumps(report)
    if behavior == "model-unavailable":
        assert report["policy_calls"][0]["error"] == "policy_model_unavailable"


def test_missing_cli_is_reported_without_model_usage():
    policy = CodexPolicy(binary="/nonexistent/policy-executable")
    with pytest.raises(PolicyError, match="codex_cli_not_found"):
        policy.decide(context())
    assert policy.calls[0]["usage"] == {}


@pytest.mark.parametrize(
    "raw",
    [
        "{}",
        "[]",
        "not JSON",
        '{"action":"track","tracking_id":"TRK-1","reason":"ok","extra":1}',
        '{"action":"complete","tracking_id":null,"reason":"done"}',
        '{"action":"track","tracking_id":123,"reason":"check"}',
    ],
)
def test_untrusted_model_output_cannot_bypass_contract(raw):
    with pytest.raises(PolicyError):
        parse_decision(raw)


def test_valid_structured_output_round_trips():
    assert parse_decision('{"action":"refresh_order","tracking_id":null,"reason":"check"}') == (
        PolicyDecision("refresh_order", reason="check")
    )


def test_prompt_contains_observations_and_does_not_request_failure():
    state = PolicyContext(
        ORDER_ID,
        OLD_TRACKING,
        1,
        0,
        8,
        1,
        (ToolObservation("track_shipment", 404, "shipment_not_found", None, OLD_TRACKING),),
    )
    prompt = build_policy_prompt(state)
    assert "shipment_not_found" in prompt
    assert "You may self-correct" in prompt
    assert "deliberately loop" not in prompt
    assert json.loads(prompt.split("Observations and budgets:\n")[1])["recoveries"] == 0


@pytest.mark.parametrize("timeout,max_calls", [(0, 4), (301, 4), (30, 0), (30, 33)])
def test_invalid_policy_limits(timeout, max_calls):
    with pytest.raises(ValueError):
        CodexPolicy(timeout=timeout, max_calls=max_calls)


@pytest.mark.skipif(os.name != "posix", reason="POSIX child process group behavior")
def test_timeout_terminates_child_process_group(tmp_path):
    import signal
    import sys

    from agent_loop_recovery.model_policy import _run

    pid_file = tmp_path / "child.pid"
    script = (
        "import subprocess,sys,time;"
        'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
        f'open({str(pid_file)!r},"w").write(str(p.pid));'
        "time.sleep(30)"
    )
    with pytest.raises(PolicyError, match="policy_timeout"):
        _run([sys.executable, "-c", script], env=dict(os.environ), cwd=str(tmp_path), timeout=0.5)
    pid = int(pid_file.read_text())
    try:
        # A killed process can briefly remain a zombie; inspect status rather than kill(0).
        import subprocess

        status = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
        )
        assert not status.stdout.strip() or status.stdout.strip().startswith("Z")
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
