"""Tests for the console-facing agent entry (/ask missions, G1)."""
from one2one.agents import console as agents_console
from one2one.agents import roster


# ── scope_from_text: parse + default-deny semantics ───────────────────────────

def test_scope_from_text_parses():
    s = agents_console.scope_from_text("example.com, *.example.org")
    assert s.allows("example.com") is True
    assert s.allows("www.example.org") is True
    assert s.allows("evil.com") is False


def test_scope_from_text_empty_is_default_deny():
    s = agents_console.scope_from_text("")
    assert s.allows("example.com") is False
    assert "no scope" in s.reason("example.com")


# ── configured_scope: reads config.mission_scope ─────────────────────────────

def test_configured_scope_reads_config(monkeypatch):
    monkeypatch.setattr("one2one.config.load",
                        lambda: {"mission_scope": "*.example.com"})
    s = agents_console.configured_scope()
    assert s.allows("www.example.com") is True
    assert s.allows("evil.com") is False


def test_configured_scope_defaults_empty(monkeypatch):
    monkeypatch.setattr("one2one.config.load", lambda: {})
    s = agents_console.configured_scope()
    assert s.allows("example.com") is False


# ── default_apex: persistent ledger + Mythos workers ─────────────────────────

def test_default_apex_wires_mythos_workers(tmp_path, monkeypatch):
    monkeypatch.setattr("one2one.agents.ledger.LEDGER_FILE",
                        tmp_path / "ledger.json")
    apex = agents_console.default_apex()
    assert len(apex.workers.handlers) == len(roster.WORKERS)   # all 32 wired


def test_default_apex_gate_default_denies(tmp_path, monkeypatch):
    monkeypatch.setattr("one2one.agents.ledger.LEDGER_FILE",
                        tmp_path / "ledger.json")
    apex = agents_console.default_apex()
    d = apex.commander.gate.check("example.com")
    assert d.allow is False and "no scope" in d.reason


# ── run_mission: the /ask path ───────────────────────────────────────────────

def test_run_mission_refuses_when_out_of_scope(tmp_path, monkeypatch):
    monkeypatch.setattr("one2one.agents.ledger.LEDGER_FILE",
                        tmp_path / "ledger.json")
    monkeypatch.setattr("one2one.config.load", lambda: {"mission_scope": ""})
    res = agents_console.run_mission("enumerate example.com")
    assert res["allowed"] is False
    assert "no scope" in res["reason"]
    assert res["mission"].status == "killed"
    assert res["findings"] == []
    assert (tmp_path / "ledger.json").exists()   # refused mission is ledgered


def test_run_mission_allowed_with_scope_uses_stub_worker(tmp_path, monkeypatch):
    monkeypatch.setattr("one2one.agents.ledger.LEDGER_FILE",
                        tmp_path / "ledger.json")
    from one2one.agents.command import Apex, WorkerRegistry
    from one2one.agents.ledger import MissionLedger

    apex = Apex(ledger=MissionLedger.load(), workers=WorkerRegistry())
    apex.set_scope(agents_console.scope_from_text("example.com"))
    monkeypatch.setattr(agents_console, "default_apex", lambda: apex)

    res = agents_console.run_mission("enumerate example.com")
    assert res["allowed"] is True
    assert res["mission"].status == "done"
    assert res["mission"].target == "example.com"
    assert res["report"].executed is False        # P0 stub: honest "not executed"
