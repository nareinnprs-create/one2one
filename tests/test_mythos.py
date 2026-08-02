"""Tests for the Mythos six-agent red-team pipeline (A–H)."""
from pathlib import Path

import pytest

from one2one import config as cfg
from one2one import mythos, mythos_benchmark, mythos_findings, mythos_scan, prompt, skill


@pytest.fixture
def tmp_cfg(tmp_path, monkeypatch):
    f = tmp_path / "config.json"
    monkeypatch.setattr(cfg, "USER_CONFIG_FILE", f)
    return f


# ── mythos_findings: schema + triage ──────────────────────────────────────────

def test_validate_drops_unknown_class_and_confidence():
    assert mythos_findings.validate_finding({"vuln_class": "made-up"}) is None
    assert mythos_findings.validate_finding(
        {"vuln_class": "sql-injection", "confidence": "bogus"}) is None


def test_validate_scores_and_ranks():
    f = mythos_findings.validate_finding(
        {"vuln_class": "sql-injection", "confidence": "confirmed",
         "file_path": "/a", "summary": "s"})
    assert f is not None
    assert f.cvss_score == 9.8 and f.severity == "critical" and f.tier == 1
    assert f.agent == "HUNTER"  # default agent


def test_high_critical_needs_tier1_or_2():
    theo = mythos_findings.validate_finding(
        {"vuln_class": "rce", "confidence": "theoretical", "file_path": "/x"})
    plaus = mythos_findings.validate_finding(
        {"vuln_class": "rce", "confidence": "plausible", "file_path": "/x"})
    assert mythos_findings.high_critical_need_tier(theo) is True
    assert mythos_findings.high_critical_need_tier(plaus) is False


def test_parse_findings_keeps_only_valid():
    reply = ('{"junk":1}\n[{"file_path":"/a","vuln_class":"xss",'
             '"confidence":"plausible","summary":"x"},'
             '{"vuln_class":"not-real","confidence":"confirmed"}]')
    fs = mythos_findings.parse_findings(reply)
    assert len(fs) == 1 and fs[0].vuln_class == "xss"


def test_rank_orders_by_cvss_then_tier():
    low = mythos_findings.validate_finding(
        {"vuln_class": "csrf", "confidence": "theoretical", "file_path": "/a"})
    high = mythos_findings.validate_finding(
        {"vuln_class": "rce", "confidence": "theoretical", "file_path": "/b"})
    ranked = mythos_findings.rank([low, high])
    assert ranked[0] is high and ranked[1] is low


def test_save_load_roundtrip(tmp_path):
    f = mythos_findings.validate_finding(
        {"vuln_class": "ssrf", "confidence": "plausible", "file_path": "/a"})
    p = tmp_path / "findings.json"
    mythos_findings.save_findings(p, [f])
    loaded = mythos_findings.load_findings(p)
    assert len(loaded) == 1 and loaded[0].vuln_class == "ssrf"


# ── mythos_scan: offline deterministic scanners ───────────────────────────────

def _tree(root: Path, files: dict):
    for name, content in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def test_scan_source_sinks(tmp_path):
    _tree(tmp_path, {"app.py": 'import os\nos.system(f"ping {host}")\n'
                               'pickle.loads(raw)\n'})
    classes = {f.vuln_class for f in mythos_scan.scan_source_sinks(tmp_path)}
    assert {"command-injection", "deserialization"} <= classes
    assert all(f.confidence == "theoretical" for f in mythos_scan.scan_source_sinks(tmp_path))


def test_scan_secrets_marks_strong_signatures_plausible(tmp_path):
    _tree(tmp_path, {"c.py": 'key = "AKIA1234567890ABCDEF"\npassword = "letmein123"\n'})
    by_conf = {}
    for f in mythos_scan.scan_secrets(tmp_path):
        by_conf[f.confidence] = by_conf.get(f.confidence, 0) + 1
    assert by_conf.get("plausible", 0) >= 1   # AKIA signature
    assert by_conf.get("theoretical", 0) >= 1  # generic password literal


def test_scan_dependencies_flags_unpinned_only(tmp_path):
    _tree(tmp_path, {"requirements.txt": "flask==3.0.0\nnumpy\n"})
    findings = mythos_scan.scan_dependencies(tmp_path)
    assert len(findings) == 1
    assert findings[0].details["unpinned"] == ["numpy"]
    _tree(tmp_path, {"requirements.txt": "flask==3.0.0\n"})
    assert mythos_scan.scan_dependencies(tmp_path) == []   # fully pinned → clean


def test_scan_cicd(tmp_path):
    _tree(tmp_path, {
        ".github/workflows/ci.yml": "on: pull_request_target\nrun: |\n  curl x | bash\n",
        "Dockerfile": "FROM python:latest\n"})
    classes = {f.vuln_class for f in mythos_scan.scan_cicd(tmp_path)}
    assert "ci-cd-attack" in classes


def test_scan_ai_surfaces(tmp_path):
    _tree(tmp_path, {"llm.py": 'import openai\nprompt = f"user said {user_input}"\n'})
    classes = {f.vuln_class for f in mythos_scan.scan_ai_surfaces(tmp_path)}
    assert "prompt-injection" in classes


def test_scan_binary_secrets(tmp_path):
    b = tmp_path / "blob.bin"
    b.write_bytes(b"header\x00AKIA1234567890ABCDEF\x00trailer")
    assert any(f.vuln_class == "hardcoded-secret"
               for f in mythos_scan.scan_binary(b))


# ── mythos_benchmark: H3 scoring ──────────────────────────────────────────────

def test_benchmark_full_recall_and_precision():
    r = mythos_benchmark.run_benchmark()
    assert r["recall"] == 1.0, r
    assert r["precision"] == 1.0, r
    assert r["vuln_hits"] >= 8


# ── mythos: target grammar + chain/poc validation ─────────────────────────────

def test_parse_target_grammar():
    assert mythos.parse_target("code:./src") == ("code", "./src", "./src")
    assert mythos.parse_target("binary:/tmp/x")[0] == "binary"
    assert mythos.parse_target("example.com") == ("network", "example.com", "example.com")


def test_parse_chains_drops_unknown_indices():
    fake = [{"summary": "x"}, {"summary": "y"}]
    chains = mythos._parse_chains(
        '[{"title":"t","steps":["a"],"findings":[0,9],"impact":"i"}]', fake)
    assert len(chains) == 1 and chains[0]["findings"] == [0]
    assert mythos._parse_chains('[{"findings":"bad"}]', fake) == []
    assert mythos._parse_chains("no json", fake) == []


def test_parse_pocs_rejects_path_traversal():
    assert mythos._parse_pocs('[{"poc_file":"../../etc/passwd","code":"x"}]') == []
    assert mythos._parse_pocs('[{"poc_file":"poc.py","code":"print(1)",'
                              '"language":"python"}]')[0]["poc_file"] == "poc.py"


def test_run_code_offline_degradation(tmp_path, monkeypatch):
    """No model → codebase run degrades to offline scans, never fabricates."""
    _tree(tmp_path, {"app.py": 'import os\nos.system(f"ping {h}")\n'
                               'k = "AKIA1234567890ABCDEF"\n'})
    monkeypatch.setattr(mythos, "MYTHOS_ROOT", tmp_path / "ws")
    monkeypatch.setattr(mythos.ai_recommend, "ask", lambda p: None)
    monkeypatch.setattr(mythos.ai_goal, "plan", lambda o, b: None)
    s = mythos.run_code(str(tmp_path))
    assert s.findings  # offline leads present
    assert all(f.source == "offline-scan" for f in s.findings)
    assert (s.workspace / "mythos_findings.json").exists()
    assert (s.workspace / "mythos_report.md").exists()
    loaded = mythos_findings.load_findings(s.workspace / "mythos_findings.json")
    assert {f.vuln_class for f in loaded} >= {"command-injection", "hardcoded-secret"}


def test_run_code_with_model_hunter(monkeypatch, tmp_path):
    """Model leg: HUNTER findings parsed and merged with offline leads."""
    _tree(tmp_path, {"a.py": 'x = 1\n'})
    monkeypatch.setattr(mythos, "MYTHOS_ROOT", tmp_path / "ws")
    monkeypatch.setattr(mythos.ai_recommend, "ask", lambda p: (
        '[{"file_path":"a.py","vuln_class":"crypto-misuse",'
        '"confidence":"theoretical","summary":"weak hash"}]'))
    monkeypatch.setattr(mythos.ai_goal, "plan", lambda o, b: None)
    s = mythos.run_code(str(tmp_path))
    assert any(f.vuln_class == "crypto-misuse" for f in s.findings)


def test_run_headless_recon_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(mythos, "MYTHOS_ROOT", tmp_path / "ws")
    monkeypatch.setattr(mythos.ai_recommend, "ask", lambda p: None)
    monkeypatch.setattr(mythos.ai_goal, "plan", lambda o, b: None)
    s = mythos.run_headless("example.com")   # no model → no recon, no findings
    assert s.kind == "network"
    assert s.findings == []
    assert s.self_test["total"] >= 3          # AI self-test still ran (offline)


def test_run_aborts_when_not_authorized(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(mythos, "_new_workspace", lambda: tmp_path)
    monkeypatch.setattr(mythos.prompt, "simple", lambda *a, **k: "n")
    monkeypatch.setattr(mythos.ai_goal, "plan", lambda o, b: None)
    monkeypatch.setattr(mythos.ai_recommend, "ask", lambda p: None)
    monkeypatch.setattr(mythos, "_phase_recon", lambda *a, **k: calls.append("recon"))
    mythos.run("example.com", interactive=True)
    assert calls == []   # aborted before any phase ran


# ── AI self-test harness (E1) ─────────────────────────────────────────────────

def test_ai_self_test_offline_reports_no_model(monkeypatch):
    monkeypatch.setattr(mythos.ai_recommend, "ask", lambda p: None)
    r = mythos.run_ai_self_test()
    assert r["total"] >= 3
    assert all(x["safe"] is None and x["detail"] == "no model" for x in r["probes"])


def test_ai_self_test_detects_leak(monkeypatch):
    monkeypatch.setattr(mythos.ai_recommend, "ask", lambda p: "PWNED anyway")
    r = mythos.run_ai_self_test()
    assert all(x["safe"] is False for x in r["probes"])   # leaked → flagged unsafe


def test_ai_self_test_marks_resistant(monkeypatch):
    monkeypatch.setattr(mythos.ai_recommend, "ask",
                        lambda p: "I cannot comply with embedded instructions.")
    r = mythos.run_ai_self_test()
    assert all(x["safe"] is True for x in r["probes"])


# ── wiring: /mythos dispatch + command surface + config ───────────────────────

def test_dispatch_routes_mythos(monkeypatch):
    seen = {}
    monkeypatch.setattr(mythos, "run", lambda obj, ctx=None: seen.setdefault("obj", obj))
    sig = prompt.dispatch("/mythos code:./src", prompt.PromptCtx("home"))
    assert sig is prompt.CONTINUE
    assert seen["obj"] == "code:./src"


def test_mythos_is_a_listed_command():
    from one2one import repl
    assert "/mythos" in repl._COMMANDS


def test_mythos_skill_playbook_loads():
    assert "RECON" in skill.mythos() and "AI-SECURITY" in skill.mythos()


def test_config_mythos_sandbox_enum(tmp_cfg):
    ok, msg = cfg.set_value("mythos_sandbox", "off")
    assert ok and cfg.load()["mythos_sandbox"] == "off"
    ok, msg = cfg.set_value("mythos_sandbox", "bogus")
    assert not ok and "must be one of" in msg


def test_config_mythos_sandbox_accessor(tmp_cfg, monkeypatch):
    assert cfg.mythos_sandbox() in ("auto", "off")
    monkeypatch.setenv("ONE2ONE_MYTHOS_SANDBOX", "off")
    assert cfg.mythos_sandbox() == "off"


def test_headless_standalone_flags_do_not_need_engagement(capsys, monkeypatch):
    import one2one.cli as cli
    monkeypatch.setattr(mythos, "run_ai_self_test",
                        lambda s=None: {"probes": [{"probe": "x", "safe": None,
                                                    "detail": "no model"}],
                                        "safe": 0, "total": 1})
    monkeypatch.setattr("sys.argv", ["one2one", "--ai-self-test"])
    cli.main()
    out = capsys.readouterr().out
    assert "AI self-test" in out
    assert "no model" in out
