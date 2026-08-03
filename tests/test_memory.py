"""Tests for AgentMemory — the stack's deeper, cross-session memory (Item 2)."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from one2one.agents.evolution import Evolution
from one2one.agents.lessons import Lesson
from one2one.agents.memory import MEMORY_FILE, AgentMemory, Fact, load

# ── record + dedup ────────────────────────────────────────────────────────────

def test_record_and_dedup(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    f1 = mem.remember_target("example.com", "seen", "high", "lesson-1")
    f2 = mem.remember_target("example.com", "seen", "high", "lesson-2")
    assert f1.id == f2.id                       # same fact re-confirmed
    assert f2.hits == 2
    assert mem.stats()["total"] == 1
    assert mem.recall_for("example.com")[0].last_seen >= f1.first_seen


def test_record_requires_key_and_value(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    with pytest.raises(ValueError):
        mem.record("target", "  ", "x")
    with pytest.raises(ValueError):
        mem.record("target", "x", " ")


def test_invalid_kind_rejected_but_confidence_normalized(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    with pytest.raises(ValueError):
        mem.record("banana", "k", "v")
    # Native worker vocabularies map onto the memory scale (plausible→high);
    # unknown values fall back to medium instead of crashing the write.
    assert mem.record("target", "a", "v1", confidence="plausible").confidence == "high"
    assert mem.record("target", "b", "v2", confidence="nonsense").confidence == "medium"


# ── persistence ───────────────────────────────────────────────────────────────

def test_roundtrip(tmp_path):
    p = tmp_path / "memory.json"
    mem = AgentMemory(p)
    mem.remember_agent("RAPTOR", "outcome:findings", "high", "l1")
    mem.remember_tool("nuclei", "worked", "medium", "l1")
    loaded = AgentMemory(p)
    assert loaded.stats()["total"] == 2
    assert {f.value for f in loaded.recall(kind="tool")} == {"worked"}


def test_corrupt_and_missing_files_tolerated(tmp_path):
    bad = tmp_path / "memory.json"
    bad.write_text("{ not json [", encoding="utf-8")
    assert AgentMemory(bad).facts == []
    missing = tmp_path / "nope.json"
    assert AgentMemory(missing).facts == []
    assert load(missing).stats() == {"total": 0, "kinds": {}}


def test_old_shape_records_skipped(tmp_path):
    p = tmp_path / "memory.json"
    p.write_text('[{"id": "x"}, "junk", {"id": "y", "kind": "target", '
                 '"key": "t", "value": "v", "confidence": "high", '
                 '"first_seen": "2026-01-01", "last_seen": "2026-01-01", '
                 '"hits": 1, "version": 1}]', encoding="utf-8")
    mem = AgentMemory(p)
    assert [f.id for f in mem.facts] == ["y"]


# ── recall ────────────────────────────────────────────────────────────────────

def test_recall_filters(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    mem.remember_target("a.com", "seen", "high", "l1")
    mem.remember_agent("EYRIE", "outcome:clean", "high", "l2")
    mem.remember_agent("EYRIE", "outcome:findings", "high", "l3")
    assert len(mem.recall(kind="agent")) == 2
    assert len(mem.recall(kind="agent", value="outcome:clean")) == 1
    assert len(mem.recall(key="EYRIE")) == 2


def test_forget_entity(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    mem.remember_target("a.com", "seen", "high", "l1")
    mem.remember_target("b.com", "seen", "high", "l2")
    assert mem.forget_entity("a.com") == 1
    assert mem.stats()["total"] == 1
    assert mem.recall_for("a.com") == []


# ── distillation ──────────────────────────────────────────────────────────────

def _lesson(**kw):
    base = dict(id="L-1", agent="RAPTOR", kind="outcome",
                summary="scan", mission_id="m1", target="web.example.com",
                outcome="findings", findings=3, version=1)
    base.update(kw)
    return Lesson(**base)


def test_distill_records_agent_target_and_findings(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    facts = mem.distill(_lesson())
    values = {(f.kind, f.key, f.value) for f in facts}
    assert ("agent", "RAPTOR", "outcome:findings") in values
    assert ("target", "web.example.com", "seen") in values
    assert ("target", "web.example.com", "findings:3") in values


def test_distill_clean_mission_records_no_findings_fact(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    mem.distill(_lesson(outcome="clean", findings=0))
    assert mem.recall(value="findings:0") == []
    assert len(mem.recall_for("web.example.com")) == 1   # just "seen"


def test_distill_dedups_across_missions(tmp_path):
    mem = AgentMemory(tmp_path / "memory.json")
    mem.distill(_lesson(id="L-1"))
    mem.distill(_lesson(id="L-2"))
    seen = [f for f in mem.recall(value="seen")]
    assert len(seen) == 1
    assert seen[0].hits == 2


# ── evolution integration ─────────────────────────────────────────────────────

def test_evolution_distills_lessons_into_memory(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json")
    mission = SimpleNamespace(
        id="m-1", worker="RAPTOR", target="web.example.com", status="completed",
        outcome={"findings": [{"id": "f1"}]})
    evo.learn_from_mission(mission)
    assert evo.memory.stats()["total"] == 3
    assert {f.value for f in evo.memory.recall_for("web.example.com")} == {
        "seen", "findings:1"}
    assert evo.memory.path == tmp_path / "memory.json"


def test_evolution_memory_persists_across_instances(tmp_path):
    evo1 = Evolution(lessons_path=tmp_path / "lessons.json")
    evo1.learn_from_mission(SimpleNamespace(
        id="m-1", worker="EYRIE", target="intel.example.org",
        status="completed", outcome={"findings": []}))
    evo2 = Evolution(lessons_path=tmp_path / "lessons.json")
    assert evo2.memory.recall_for("intel.example.org")[0].value == "seen"
    assert evo2.lessons.picture()["total"] == 1


# ── module helpers ────────────────────────────────────────────────────────────

def test_memory_file_points_at_user_config():
    assert Path(MEMORY_FILE).name == "memory.json"
    assert str(MEMORY_FILE).endswith(str(Path("agents") / "memory.json"))


def test_fact_validation():
    f = Fact(id="f", kind="target", key="t", value="v")
    assert f.first_seen and f.hits == 1 and f.version == 1
    assert f.last_seen >= f.first_seen


def test_demo_runs():
    import one2one.agents.memory as m
    m.demo()
