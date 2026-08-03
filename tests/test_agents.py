"""Tests for the One2One Agent Stack P0 skeleton: roster, scope gate,
mission ledger, intent router, and the APEX/COMMANDER command layer."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from one2one import agents
from one2one.agents import roster, workers
from one2one.agents.ledger import MissionLedger
from one2one.agents.router import route
from one2one.agents.scope import Scope, normalize_target
from one2one.mythos_findings import MythosFinding


# ── roster: the approved 37 ───────────────────────────────────────────────────

def test_roster_has_37_agents():
    assert len(agents.get_roster()) == 37


def test_roster_wings_and_counts():
    assert len(roster.WORKERS) == 32
    assert len(roster.workers_in(roster.VANGUARD)) == 10
    assert len(roster.workers_in(roster.ONSLAUGHT)) == 16
    assert len(roster.workers_in(roster.TRIBUNAL)) == 6


def test_roster_tiers():
    assert roster.tier_of("APEX") == 4
    assert roster.tier_of("COMMANDER") == 3
    assert roster.tier_of("VANGUARD") == 2
    assert roster.tier_of("EYRIE") == 1


def test_chain_is_worker_wing_operator_supreme():
    assert roster.chain_for("EYRIE") == ["EYRIE", "VANGUARD", "COMMANDER", "APEX"]
    assert roster.chain_for("VIPER") == ["VIPER", "ONSLAUGHT", "COMMANDER", "APEX"]
    assert roster.chain_for("SAGE") == ["SAGE", "TRIBUNAL", "COMMANDER", "APEX"]


# ── scope gate: default-deny ──────────────────────────────────────────────────

def test_normalize_target_strips_scheme_port_path():
    assert normalize_target("https://Example.com:8443/x/y") == "example.com"
    assert normalize_target("example.com") == "example.com"


def test_scope_allows_in_and_denies_out():
    s = Scope(name="t", scope_in=["*.example.com"],
              scope_out=["admin.example.com"])
    assert s.allows("www.example.com") is True
    assert s.allows("admin.example.com") is False
    assert s.allows("evil.com") is False


def test_empty_scope_default_denies_everything():
    s = Scope()
    assert s.allows("example.com") is False
    assert "no scope" in s.reason("example.com")


def test_scope_gate_empty_target_denied():
    gate = agents.ScopeGate(Scope(scope_in=["example.com"]))
    d = gate.check("")
    assert d.allow is False and "empty target" in d.reason


def test_scope_from_engagement():
    e = {"name": "acme", "scope_in": ["*.example.com"], "scope_out": ["admin.example.com"]}
    s = Scope.from_engagement(type("E", (), e)())
    assert s.allows("www.example.com") is True
    assert s.allows("admin.example.com") is False


def test_local_target_denied_by_default():
    gate = agents.ScopeGate(Scope())
    assert gate.check("code:./src").allow is False
    assert "local" in gate.check("code:./src").reason


def test_local_target_allowed_when_local_scope():
    gate = agents.ScopeGate(Scope(local=True))
    assert gate.check("code:./src").allow is True
    assert gate.check("binary:./challenge.bin").allow is True
    assert gate.check("example.com").allow is False  # hosts still need scope_in


# ── mission ledger: persistence ───────────────────────────────────────────────

def test_ledger_roundtrip(tmp_path):
    p = tmp_path / "ledger.json"
    ledger = MissionLedger(path=p)
    m = ledger.record(agents.Mission(id="EYRIE-abc", intent="recon",
                                     worker="EYRIE", wing="VANGUARD",
                                     status="done"))
    loaded = MissionLedger.load(p)
    assert loaded.get("EYRIE-abc") is not None
    assert loaded.get("EYRIE-abc").status == "done"
    assert loaded.picture() == {"total": 1, "done": 1}


def test_ledger_record_replaces_by_id_and_counts(tmp_path):
    ledger = MissionLedger(path=tmp_path / "ledger.json")
    a = agents.Mission(id="a", intent="x", worker="EYRIE", status="pending")
    b = agents.Mission(id="a", intent="y", worker="EYRIE", status="running")
    ledger.record(a)
    ledger.record(b)
    assert ledger.picture()["total"] == 1
    assert ledger.picture()["running"] == 1


def test_ledger_queries(tmp_path):
    ledger = MissionLedger(path=tmp_path / "ledger.json")
    ledger.record(agents.Mission(id="1", intent="a", worker="EYRIE",
                                 wing="VANGUARD", status="done"))
    ledger.record(agents.Mission(id="2", intent="b", worker="VIPER",
                                 wing="ONSLAUGHT", status="killed"))
    assert len(ledger.by_agent("EYRIE")) == 1
    assert len(ledger.by_wing("ONSLAUGHT")) == 1
    assert len(ledger.by_status("killed")) == 1


# ── intent router ─────────────────────────────────────────────────────────────

def test_route_recon_to_eyrie():
    d = route("full network recon and enumerate hosts on example.com")
    assert d.worker == "EYRIE" and d.wing == "VANGUARD"


def test_route_sql_injection_to_viper():
    d = route("test for SQL injection on the login form")
    assert d.worker == "VIPER"


def test_route_specific_token_beats_generic():
    d = route("crack password hashes")
    assert d.worker == "SHATTER"


def test_route_unknown_falls_back_to_sage():
    d = route("shuffle the quantum bananas")
    assert d.worker == "SAGE"
    assert d.confidence == 0.0


def test_route_chain_is_built():
    d = route("report on all findings")
    assert d.worker == "CHRONICLE"
    assert d.chain == ["CHRONICLE", "TRIBUNAL", "COMMANDER", "APEX"]


# ── command layer: APEX + COMMANDER ───────────────────────────────────────────

def _apex(tmp_path, scope):
    ledger = MissionLedger(path=tmp_path / "ledger.json")
    return agents.Apex(ledger=ledger, gate=agents.ScopeGate(scope))


def test_apex_ask_in_scope_routes_and_completes(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    out = apex.ask("recon the attack surface", target="www.example.com")
    assert out["allowed"] is True
    m = out["mission"]
    assert m.worker == "EYRIE" and m.wing == "VANGUARD"
    assert m.status == "done"
    assert m.supreme == "APEX" and m.operator == "COMMANDER"
    assert out["report"].executed is False  # P0 stub, honest about it


def test_apex_ask_out_of_scope_is_killed(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    out = apex.ask("recon the attack surface", target="evil.org")
    assert out["allowed"] is False
    assert out["mission"].status == "killed"
    assert "not in scope" in out["reason"]


def test_apex_ask_default_denies_without_scope(tmp_path):
    apex = _apex(tmp_path, Scope())
    out = apex.ask("recon the attack surface", target="example.com")
    assert out["allowed"] is False
    assert "no scope" in out["reason"]


def test_apex_ask_extracts_target_from_prompt(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["example.com", "*.example.com"]))
    out = apex.ask("scan https://Example.com:8443/web")
    assert out["allowed"] is True
    assert out["mission"].target == "example.com"


def test_apex_ask_without_any_target_is_refused(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    out = apex.ask("recon the attack surface")
    assert out["allowed"] is False


def test_commander_state_machine(tmp_path):
    ledger = MissionLedger(path=tmp_path / "ledger.json")
    commander = agents.Commander(ledger=ledger)
    m = commander.submit("crack password hashes", target="db.example.com")
    assert m.status == "pending" and m.worker == "SHATTER"
    commander.start(m)
    assert m.status == "running"
    commander.complete(m, {"ok": True})
    assert m.status == "done"
    failed = commander.submit("exploit the box", target="x.example.com")
    commander.fail(failed, "no reachable target")
    assert failed.status == "failed"
    assert ledger.picture()["failed"] == 1


def test_commander_scope_gate_blocks_out_of_scope(tmp_path):
    commander = agents.Commander(gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])))
    assert commander.check_scope("evil.org").allow is False
    assert commander.check_scope("app.example.com").allow is True


# ── P1: wing leads — brutal review ────────────────────────────────────────────

def _finding(vuln_class, confidence, file_path="/a"):
    return MythosFinding(agent="HUNTER", phase=2, file_path=file_path,
                         vuln_class=vuln_class, confidence=confidence,
                         summary="x")


def test_wing_lead_escalates_clean_findings():
    lead = agents.wing_lead_for(roster.VANGUARD)
    report = agents.WorkerReport(worker="EYRIE", executed=True, note="ran",
                                 findings=[_finding("insecure-config", "plausible")])
    w = lead.supervise(None, report)
    assert len(w.accepted) == 1 and len(w.rejected) == 0
    assert "escalated" in w.verdict


def test_wing_lead_rejects_duplicate_and_theoretical_high():
    lead = agents.wing_lead_for(roster.ONSLAUGHT)
    report = agents.WorkerReport(
        worker="RAPTOR", executed=True, note="ran",
        findings=[
            _finding("sql-injection", "plausible"),
            _finding("sql-injection", "plausible"),      # duplicate
            _finding("rce", "theoretical"),              # high + tier 3
        ])
    w = lead.supervise(None, report)
    assert len(w.accepted) == 1
    assert len(w.rejected) == 2
    reasons = " ".join(r["reason"] for r in w.rejected)
    assert "duplicate" in reasons and "tier 1-2" in reasons


def test_wing_lead_clean_verdict_when_nothing_found():
    lead = agents.wing_lead_for(roster.TRIBUNAL)
    w = lead.supervise(None, agents.WorkerReport(worker="SAGE", executed=True,
                                                 note="ran"))
    assert w.accepted == [] and "clean" in w.verdict


def test_wing_lead_validates_raw_dict_findings():
    lead = agents.wing_lead_for(roster.VANGUARD)
    report = agents.WorkerReport(worker="EYRIE", executed=True, note="ran",
                                 findings=[{"vuln_class": "sql-injection",
                                            "confidence": "plausible",
                                            "file_path": "/x", "summary": "s"}])
    w = lead.supervise(None, report)
    assert len(w.accepted) == 1
    assert isinstance(w.accepted[0], MythosFinding)


# ── P1: worker registry + Mythos adapter ──────────────────────────────────────

def test_registry_unregistered_falls_back_to_stub():
    reg = agents.WorkerRegistry()
    m = agents.Mission(id="x", intent="recon", worker="EYRIE")
    r = reg.dispatch(m)
    assert r.executed is False and "pending" in r.note


def test_registry_routes_to_registered_handler():
    reg = agents.WorkerRegistry()
    calls = []
    def handler(mission):
        calls.append(mission.worker)
        return agents.WorkerReport(mission.worker, True, "handled")
    reg.register("eyrie", handler)
    r = reg.dispatch(agents.Mission(id="x", intent="recon", worker="EYRIE"))
    assert r.executed is True and calls == ["EYRIE"]


def test_mythos_adapter_runs_headless_pipeline(monkeypatch, tmp_path):
    fake = SimpleNamespace(findings=[_finding("insecure-config", "plausible")])
    seen = []
    def fake_pipeline(target):
        seen.append(target)
        return fake
    monkeypatch.setattr(agents.adapters.MythosAdapter,
                        "_run_pipeline", staticmethod(fake_pipeline))
    m = agents.Mission(id="x", intent="recon", worker="EYRIE", target="example.com")
    r = agents.MythosAdapter().run(m)
    assert r.executed is True and seen == ["example.com"]
    assert len(r.findings) == 1


def test_mythos_adapter_code_target_uses_run_code(monkeypatch):
    from one2one import mythos
    seen = []
    monkeypatch.setattr(mythos, "run_code",
                        lambda path, interactive=False: seen.append(path) or SimpleNamespace(findings=[]))
    r = agents.MythosAdapter().run(agents.Mission(
        id="x", intent="audit", worker="SCALPEL", target="code:./src"))
    assert seen == ["./src"] and r.executed is True


def test_mythos_adapter_no_target_does_not_run(monkeypatch):
    from one2one import mythos
    monkeypatch.setattr(mythos, "run_headless", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    r = agents.MythosAdapter().run(agents.Mission(id="x", intent="recon", worker="EYRIE"))
    assert r.executed is False


def test_apex_with_registered_worker_escalates_findings(tmp_path):
    reg = agents.WorkerRegistry()
    def handler(mission):
        return agents.WorkerReport(mission.worker, True, "handled",
                                   findings=[_finding("xss", "plausible")])
    reg.register("RAPTOR", handler)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask("scan for xss", target="app.example.com")
    assert out["allowed"] is True
    assert out["mission"].status == "done"
    assert out["report"].executed is True
    assert out["wing_report"].lead == "ONSLAUGHT"
    assert len(out["findings"]) == 1
    assert out["mission"].outcome["wing_report"]["accepted"][0]["vuln_class"] == "xss"


def test_apex_out_of_scope_never_dispatches(tmp_path):
    reg = agents.WorkerRegistry()
    reg.register("EYRIE", lambda m: (_ for _ in ()).throw(AssertionError("no dispatch")))
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask("recon", target="evil.org")
    assert out["allowed"] is False
    assert out["report"] is None and out["findings"] == []
    assert out["mission"].status == "killed"


# ── P2: Intel-wing worker modules ─────────────────────────────────────────────

def _read_file_runner(argv, timeout):
    path = argv[-1]
    if Path(path).is_file():
        return Path(path).read_text(encoding="utf-8", errors="replace")
    return ""


def _boom_runner(argv, timeout):
    raise OSError("tool not installed")


def test_intel_wing_registers_10_real_handlers():
    reg = agents.WorkerRegistry()
    workers.register_intel_wing(reg, runner=_read_file_runner)
    assert set(reg.handlers) == set(workers.INTEL_CALLSIGNS)
    assert len(workers.INTEL_CALLSIGNS) == 10
    assert "MIRROR" in reg.handlers


def test_default_workers_register_all_32():
    reg = agents.WorkerRegistry()
    workers.register_default_workers(reg, runner=_read_file_runner)
    assert set(reg.handlers) == set(roster.WORKERS)
    assert len(reg.handlers) == 32


def test_worker_plan_builds_and_dedups_steps():
    w = workers.EyrieWorker(runner=_read_file_runner)
    steps = w.plan("example.com")
    assert steps and all(isinstance(s, workers.Step) for s in steps)
    argvs = [tuple(s.argv) for s in steps]
    assert len(set(argvs)) == len(argvs)          # catalog + builtin overlap deduped
    assert any(s.source == "builtin" for s in steps)


def test_worker_missing_tool_is_skipped_not_raised():
    w = workers.EyrieWorker(runner=_boom_runner)
    report = w.run(SimpleNamespace(target="example.com"))
    assert isinstance(report, agents.WorkerReport)
    assert report.executed is False and report.findings == []


def test_worker_no_target_does_not_run():
    w = workers.SentryWorker(runner=_boom_runner)
    report = w.run(SimpleNamespace(target=""))
    assert report.executed is False and "no target" in report.note


def test_mirror_harvests_secret_evidence(tmp_path):
    p = tmp_path / "leak.txt"
    p.write_text("AWS_ACCESS_KEY_ID = AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    w = workers.MirrorWorker(runner=_read_file_runner)
    report = w.run(SimpleNamespace(target=f"binary:{p}"))
    assert report.executed is True
    assert any(f.vuln_class == "hardcoded-secret"
               and f.confidence == "plausible"
               for f in report.findings)


def test_worker_binary_target_strips_kind_prefix(tmp_path):
    p = tmp_path / "leak.txt"
    p.write_text("-----BEGIN RSA PRIVATE KEY-----\n", encoding="utf-8")
    w = workers.MirrorWorker(runner=_read_file_runner)
    report = w.run(SimpleNamespace(target=f"binary:{p}"))
    assert any("private key" in f.summary for f in report.findings)


def test_split_keeps_windows_paths():
    argv = workers._split("strings C:\\lab\\file.txt")
    if os.name == "nt":
        assert argv == ["strings", "C:\\lab\\file.txt"]
    else:
        assert argv[1] == "C:\\lab\\file.txt" or "\\" in argv[1]


def test_apex_intel_worker_escalates_evidence(tmp_path):
    p = tmp_path / "leak.txt"
    p.write_text("ghp_123456789012345678901234567890123456\n", encoding="utf-8")
    reg = agents.WorkerRegistry()
    workers.register_intel_wing(reg, runner=_read_file_runner)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(local=True)),
                       workers=reg)
    out = apex.ask("collect evidence artifacts", target=f"binary:{p}")
    assert out["allowed"] is True
    assert out["mission"].worker == "MIRROR"
    assert out["mission"].status == "done"
    assert out["wing_report"].lead == "VANGUARD"
    assert any(f.vuln_class == "hardcoded-secret" for f in out["findings"])


# ── P3: Offense + Truth worker modules, parallel dispatch, streaming ──────────

def test_offense_wing_registers_16_real_handlers():
    reg = agents.WorkerRegistry()
    workers.register_offense_wing(reg, runner=_boom_runner)
    assert set(reg.handlers) == set(roster.workers_in(roster.ONSLAUGHT))
    assert len(reg.handlers) == 16


def test_truth_wing_registers_6_real_handlers():
    reg = agents.WorkerRegistry()
    workers.register_truth_wing(reg, runner=_boom_runner)
    assert set(reg.handlers) == set(roster.workers_in(roster.TRIBUNAL))
    assert len(reg.handlers) == 6


def test_worker_classes_cover_all_32_callsigns():
    callsigns = [cls.CALLSIGN for cls in workers.WORKER_CLASSES]
    assert sorted(callsigns) == sorted(roster.WORKERS)
    assert len(callsigns) == len(set(callsigns)) == 32


def test_every_worker_degrades_without_tools():
    for cls in workers.WORKER_CLASSES:
        w = cls(runner=_boom_runner)
        report = w.run(SimpleNamespace(target="example.com"))
        assert isinstance(report, agents.WorkerReport)
        assert report.executed is False
        assert report.worker == cls.CALLSIGN


def test_sage_plans_recommended_commands():
    w = workers.SageWorker(runner=_boom_runner)
    report = w.run(SimpleNamespace(target="example.com"))
    labels = {i["label"] for i in report.intel}
    assert labels == {"recommended_command"}
    planned = [" ".join(s.argv) for s in w.plan("example.com")]
    assert [i["value"] for i in report.intel] == planned
    assert report.findings == []


def test_ask_wide_fans_out_to_whole_wing(tmp_path):
    reg = agents.WorkerRegistry()
    workers.register_intel_wing(reg, runner=_read_file_runner)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask_wide("recon the attack surface", target="www.example.com")
    assert out["allowed"] is True
    assert {m.worker for m in out["missions"]} == set(roster.workers_in(roster.VANGUARD))
    assert all(m.status == "done" for m in out["missions"])
    assert out["reports"] and len(out["reports"]) == 10
    assert apex.status()["done"] == 10


def test_ask_wide_pins_specific_workers(tmp_path):
    reg = agents.WorkerRegistry()
    workers.register_offense_wing(reg, runner=_boom_runner)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask_wide("audit web apps", target="app.example.com",
                        workers=["RAPTOR", "VIPER", "GHOST"])
    assert {m.worker for m in out["missions"]} == {"RAPTOR", "VIPER", "GHOST"}
    assert all(m.wing == "ONSLAUGHT" for m in out["missions"])


def test_ask_wide_out_of_scope_is_killed(tmp_path):
    reg = agents.WorkerRegistry()
    workers.register_intel_wing(reg, runner=_read_file_runner)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask_wide("recon the attack surface", target="evil.org")
    assert out["allowed"] is False and out["missions"] == []
    assert "not in scope" in out["reason"]


def test_ask_streams_accepted_findings(tmp_path):
    reg = agents.WorkerRegistry()
    streamed = []
    def handler(mission):
        return agents.WorkerReport(mission.worker, True, "handled",
                                   findings=[_finding("xss", "plausible"),
                                             _finding("sql-injection", "theoretical")])
    reg.register("RAPTOR", handler)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask("scan for xss", target="app.example.com",
                   stream=streamed.append)
    assert [f.vuln_class for f in streamed] == ["xss"]
    assert len(out["findings"]) == 1


def test_ask_wide_streams_from_multiple_workers(tmp_path):
    reg = agents.WorkerRegistry()
    streamed = []
    def handler(mission):
        return agents.WorkerReport(mission.worker, True, "handled",
                                   findings=[_finding("insecure-config", "plausible")])
    for w in ("EYRIE", "SENTRY"):
        reg.register(w, handler)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask_wide("recon the target", target="www.example.com",
                        workers=["EYRIE", "SENTRY"], stream=streamed.append)
    assert len(streamed) == 2
    assert len(out["findings"]) == 2


def test_wing_lead_streams_accepted_only(tmp_path):
    lead = agents.wing_lead_for(roster.ONSLAUGHT)
    streamed = []
    report = agents.WorkerReport(
        worker="RAPTOR", executed=True, note="ran",
        findings=[_finding("sql-injection", "plausible"),
                  _finding("rce", "theoretical")])
    wing = lead.supervise(None, report, stream=streamed.append)
    assert [f.vuln_class for f in streamed] == ["sql-injection"]
    assert len(wing.accepted) == 1 and len(wing.rejected) == 1


# ── P4: the self-development loop ─────────────────────────────────────────────

def test_lesson_ledger_roundtrip(tmp_path):
    p = tmp_path / "lessons.json"
    ll = agents.LessonLedger(path=p)
    ll.record(agents.Lesson(id="MIRROR-abc", agent="MIRROR", kind="outcome",
                            summary="x", outcome="findings", findings=1))
    ll.record(agents.Lesson(id="EYRIE-def", agent="EYRIE", kind="near-miss",
                            summary="y"))
    loaded = agents.LessonLedger.load(p)
    assert loaded.get("MIRROR-abc").outcome == "findings"
    assert len(loaded.by_agent("EYRIE")) == 1
    assert loaded.picture() == {"total": 2, "outcome": 1, "near-miss": 1}
    assert len(loaded.recent(1)) == 1


def test_lesson_rejects_unknown_kind():
    with pytest.raises(ValueError):
        agents.Lesson(id="x", agent="MIRROR", kind="bogus", summary="x")


def test_apex_learns_from_each_mission(tmp_path):
    reg = agents.WorkerRegistry()
    def handler(mission):
        return agents.WorkerReport(mission.worker, True, "handled",
                                   findings=[_finding("xss", "plausible")])
    reg.register("RAPTOR", handler)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask("scan for xss", target="app.example.com")
    lessons = apex.evolution.lessons.by_agent("RAPTOR")
    assert len(lessons) == 1
    assert lessons[0].kind == "outcome" and lessons[0].outcome == "findings"
    assert lessons[0].findings == 1
    assert lessons[0].mission_id == out["mission"].id
    assert (tmp_path / "lessons.json").exists()


def test_apex_learns_killed_mission(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    out = apex.ask("recon", target="evil.org")
    lessons = apex.evolution.lessons.by_agent(out["mission"].worker)
    assert lessons and lessons[-1].outcome == "killed"


def test_apex_ask_wide_learns_each_mission(tmp_path):
    reg = agents.WorkerRegistry()
    workers.register_intel_wing(reg, runner=_boom_runner)
    apex = agents.Apex(ledger=MissionLedger(path=tmp_path / "ledger.json"),
                       gate=agents.ScopeGate(Scope(scope_in=["*.example.com"])),
                       workers=reg)
    out = apex.ask_wide("recon the attack surface", target="www.example.com")
    assert apex.evolution.lessons.picture()["total"] == 10
    assert apex.evolution_picture()["lessons"]["total"] == 10


def test_propose_rejects_unknown_agent_or_kind(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    with pytest.raises(ValueError):
        apex.propose_patch("NOTAWORKER", "add-signature",
                           ("a", "b", r"c", "plausible"), "x")
    with pytest.raises(ValueError):
        apex.propose_patch("MIRROR", "bogus", ("a", "b", r"c", "plausible"), "x")


def _unpatch(evo, patch):
    from one2one.agents.evolution import _remove_from_class, _worker_class
    for callsign in evo.applied.get(patch.id, []):
        cls = _worker_class(callsign)
        if cls is not None:
            _remove_from_class(cls, patch)


def test_patch_full_gate_approval_and_propagation(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    p = apex.propose_patch(
        "MIRROR", "add-signature",
        ("hardcoded-secret", "Slack token",
         r"xox[baprs]-[A-Za-z0-9-]{10,}", "plausible"),
        "lessons show Slack tokens leaking")
    a = apex.approve_patch(p)
    try:
        assert a.status == "active"
        assert a.approved_by == ["VANGUARD", "COMMANDER", "APEX"]
        applied_to = apex.patch_status(a)["applied_to"]
        assert set(applied_to) == {"MIRROR", "VAULT", "SCALPEL", "POCKET", "NIMBUS"}
        assert "Slack token" in [s[1] for s in workers.MirrorWorker.SIGNATURES]
        results = agents.run_regression(workers.MirrorWorker,
                                        agents.REGRESSION_CASES["MIRROR"])
        assert all(r.passed for r in results)
    finally:
        _unpatch(apex.evolution, a)
    assert "Slack token" not in [s[1] for s in workers.MirrorWorker.SIGNATURES]


def test_patch_regression_rollback_on_multiple_workers(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    p = apex.propose_patch(
        "MIRROR", "add-signature",
        ("hardcoded-secret", "credential assignment",
         r"\b[A-Za-z]+\s*=\s*[A-Za-z0-9_.-]+", "plausible"),
        "lessons show loose credential assignments leaking")
    a = apex.approve_patch(p)
    try:
        assert a.status == "rolled-back"
        assert "regression rollback" in a.note
        assert "MIRROR" in a.note and "VAULT" in a.note and "POCKET" in a.note
        applied_to = apex.patch_status(a)["applied_to"]
        assert set(applied_to) == {"SCALPEL", "NIMBUS"}
        assert not any("credential assignment" in s[1]
                       for s in workers.MirrorWorker.SIGNATURES)
        assert any("credential assignment" in s[1]
                   for s in workers.ScalpelWorker.SIGNATURES)
    finally:
        _unpatch(apex.evolution, a)
    assert not any("credential assignment" in s[1]
                   for s in workers.ScalpelWorker.SIGNATURES)


def test_patch_restricted_kind_killed(tmp_path):
    apex = _apex(tmp_path, Scope(scope_in=["*.example.com"]))
    p = agents.SkillPatch(id="MIRROR-rigged", agent="MIRROR", kind="run-command",
                          payload=("nmap", "{target} -p-", "x"),
                          rationale="directly injected, not proposable")
    apex.evolution.patches[p.id] = p
    a = apex.approve_patch(p)
    assert a.status == "killed"
    assert "never allowed" in a.chain[-1]["reason"]
    assert a.approved_by == ["VANGUARD", "COMMANDER"]


def test_scoped_patch_default_denied(tmp_path):
    apex = _apex(tmp_path, Scope())
    p = apex.propose_patch(
        "MIRROR", "add-signature",
        {"target": "secret.example.com", "sig": ("hardcoded-secret", "x",
                                                  r"y", "plausible")},
        "needs an authorized scope", requires_scope=True)
    a = apex.approve_patch(p)
    assert a.status == "killed"
    assert a.approved_by == ["VANGUARD"]
    assert "default-deny" in a.chain[-1]["reason"]


def test_set_scope_syncs_evolution_gate(tmp_path):
    apex = _apex(tmp_path, Scope())
    p = apex.propose_patch(
        "MIRROR", "add-signature",
        {"target": "app.example.com", "sig": ("hardcoded-secret", "x",
                                               r"y", "plausible")},
        "needs an authorized scope", requires_scope=True)
    assert apex.evolution.gate.scope_ok(p) is False
    apex.set_scope(Scope(scope_in=["*.example.com"]))
    assert apex.evolution.gate.scope_ok(p) is True
