"""Tests for memory-assisted workers (Item 4, agent power).

A worker constructed with deeper memory refuses to re-report findings the stack
already knows (moving them to ``report.known``) and records brand-new findings
as facts, so the next mission on the same target stays honest.
"""
from types import SimpleNamespace

from one2one.agents.evolution import Evolution, PatchGate
from one2one.agents.memory import AgentMemory
from one2one.agents.workers import WORKER_CLASSES
from one2one.agents.workflows import WorkflowRegistry


def _worker(callsign, runner, memory=None):
    cls = next(c for c in WORKER_CLASSES if c.CALLSIGN == callsign)
    return cls(runner=runner, memory=memory)


def _aws_runner(output):
    return lambda argv, timeout: output


# ── baseline: no memory, behavior unchanged ──────────────────────────────────

def test_worker_without_memory_reports_everything(tmp_path):
    w = _worker("VAULT", _aws_runner("AKIAIOSFODNN7EXAMPLE\n"))
    report = w.run(SimpleNamespace(target="example.com"))
    assert len(report.findings) == 1
    assert report.known == []


# ── first pass: findings recorded as memory facts ────────────────────────────

def test_memory_worker_records_new_findings(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    w = _worker("VAULT", _aws_runner("AKIAIOSFODNN7EXAMPLE\n"), mem)
    report = w.run(SimpleNamespace(target="example.com"))
    assert len(report.findings) == 1
    assert report.known == []
    fact = mem.recall(kind="finding", key="example.com")
    assert len(fact) == 1
    assert fact[0].value.startswith("hardcoded-secret|")
    assert fact[0].source == "VAULT"


# ── second pass: known findings suppressed, not re-reported ──────────────────

def test_memory_worker_suppresses_known_findings(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    first = _worker("VAULT", _aws_runner("AKIAIOSFODNN7EXAMPLE\n"), mem)
    first.run(SimpleNamespace(target="example.com"))

    second = _worker("VAULT", _aws_runner("AKIAIOSFODNN7EXAMPLE\n"), mem)
    report = second.run(SimpleNamespace(target="example.com"))
    assert report.findings == []
    assert len(report.known) == 1
    assert "suppressed" in report.note
    assert len(mem.recall(kind="finding", key="example.com")) == 1  # no dup


def test_suppression_is_target_specific(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    _worker("VAULT", _aws_runner("AKIAIOSFODNN7EXAMPLE\n"), mem).run(
        SimpleNamespace(target="a.example.com"))
    report = _worker("VAULT", _aws_runner("AKIAIOSFODNN7EXAMPLE\n"), mem).run(
        SimpleNamespace(target="b.example.com"))
    assert len(report.findings) == 1          # other target still reports
    assert report.known == []


# ── evolution records finding facts on mission completion ────────────────────

def test_evolution_learns_finding_facts(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    evo.learn_from_mission(SimpleNamespace(
        id="m-1", worker="VAULT", target="example.com", status="completed",
        outcome={"findings": [
            {"vuln_class": "hardcoded-secret", "summary": "AWS access key",
             "confidence": "plausible"}]}))
    facts = evo.memory.recall(kind="finding", key="example.com")
    assert [f.value for f in facts] == ["hardcoded-secret|AWS access key"]


def test_evolution_finding_fact_enables_suppression(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    evo.learn_from_mission(SimpleNamespace(
        id="m-1", worker="VAULT", target="example.com", status="completed",
        outcome={"findings": [
            {"vuln_class": "hardcoded-secret", "summary": "AWS access key",
             "confidence": "plausible"}]}))
    w = _worker("VAULT", _aws_runner("AKIAIOSFODNN7EXAMPLE\n"), evo.memory)
    report = w.run(SimpleNamespace(target="example.com"))
    assert report.findings == []
    assert len(report.known) == 1


# ── workflow execution is memory-assisted ────────────────────────────────────

def test_workflow_run_memory_suppresses_across_runs(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    reg.register("secret-sweep", [("VAULT", "strings {target}", "sweep")])

    def runner(argv, timeout):
        return "AKIAIOSFODNN7EXAMPLE\n"

    first = reg.run("secret-sweep", "example.com", runner=runner, memory=mem)
    assert len(first["findings"]) == 1
    second = reg.run("secret-sweep", "example.com", runner=runner, memory=mem)
    assert second["findings"] == []
    assert len(second["known"]) == 1
    assert len(mem.recall(kind="finding")) == 1


# ── regression harness stays memory-free ─────────────────────────────────────

def test_regression_still_runs_without_memory(tmp_path):
    from one2one.agents.evolution import REGRESSION_CASES, run_regression
    results = run_regression(
        next(c for c in WORKER_CLASSES if c.CALLSIGN == "VAULT"),
        REGRESSION_CASES["VAULT"], target="regression")
    assert all(r.passed for r in results)
