"""AgentMemory — the stack's deeper, cross-session memory (Item 2).

The lesson log answers *"what happened?"*. AgentMemory answers the deeper
*"what do we know that survives?"* — durable, recallable facts distilled from
every lesson: which targets we have seen, which agents found what, how many
findings each target yielded, and which tools pulled their weight.

Facts are versioned, deduplicated on ``(kind, key, value)``, and persist to
``~/.one2one/agents/memory.json`` next to the lesson log. ``distill`` turns a
Lesson into facts at write-time, so memory deepens automatically every time the
evolution loop logs an outcome — no extra wiring, no network.

Recall is a simple deterministic query: ``recall(kind=..., key=..., value=...)``
or ``recall_for(entity)`` for everything we remember about one target/agent.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from one2one.constants import USER_CONFIG_DIR

MEMORY_FILE = USER_CONFIG_DIR / "agents" / "memory.json"

_FACT_FIELDS = (
    "id", "kind", "key", "value", "confidence", "source", "first_seen",
    "last_seen", "hits", "version",
)

_FACT_KINDS = ("target", "agent", "tool", "preference", "finding")

_CONFIDENCE = ("low", "medium", "high")

# Worker/scanning vocabularies map onto the memory scale so findings recorded
# with their native confidence (plausible/theoretical) stay valid.
_CONFIDENCE_MAP = {
    "plausible": "high", "firm": "high", "certain": "high",
    "theoretical": "low", "speculative": "low", "guess": "low",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_confidence(confidence: str) -> str:
    c = str(confidence or "medium").strip().lower()
    return _CONFIDENCE_MAP.get(c, c if c in _CONFIDENCE else "medium")


def new_fact_id() -> str:
    return f"fact-{uuid4().hex[:8]}"


@dataclass
class Fact:
    """One durable, recallable piece of stack memory."""
    id: str
    kind: str                    # target | agent | tool | preference
    key: str                     # the entity this fact is about
    value: str                   # what we know
    confidence: str = "medium"   # low | medium | high
    source: str = ""             # lesson/mission id that seeded this fact
    first_seen: str = ""
    last_seen: str = ""
    hits: int = 1                # how many times we re-confirmed it
    version: int = 1

    def __post_init__(self) -> None:
        now = _now()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now
        self.confidence = normalize_confidence(self.confidence)
        if self.kind not in _FACT_KINDS:
            raise ValueError(f"unknown fact kind {self.kind!r}")
        if self.confidence not in _CONFIDENCE:
            raise ValueError(f"unknown confidence {self.confidence!r}")


class AgentMemory:
    """Persistent fact ledger — record, recall, forget, distill."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else MEMORY_FILE
        self.facts: list[Fact] = []
        self.load()

    # ── persistence ────────────────────────────────────────────────────────────

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(f) for f in self.facts], indent=2),
            encoding="utf-8")

    def load(self) -> None:
        if not self.path.exists():
            self.facts = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError:
            self.facts = []
            return
        if not isinstance(data, list):
            self.facts = []
            return
        facts = []
        for item in data:
            if not isinstance(item, dict):
                continue
            item = {k: item[k] for k in _FACT_FIELDS if k in item}
            try:
                facts.append(Fact(**item))
            except (ValueError, TypeError):
                continue
        self.facts = facts

    # ── record (dedup by kind+key+value, refresh last_seen/hits) ───────────────

    def record(self, kind: str, key: str, value: str,
               confidence: str = "medium", source: str = "") -> Fact:
        key = str(key).strip()
        value = str(value).strip()
        if not key or not value:
            raise ValueError("fact key and value must be non-empty")
        existing = next(
            (f for f in self.facts
             if f.kind == kind and f.key == key and f.value == value), None)
        if existing is not None:
            existing.hits += 1
            existing.last_seen = _now()
            if source:
                existing.source = source
            self.save()
            return existing
        fact = Fact(id=new_fact_id(), kind=kind, key=key, value=value,
                    confidence=confidence, source=source)
        self.facts.append(fact)
        self.save()
        return fact

    # ── convenience recorders ──────────────────────────────────────────────────

    def remember_target(self, target: str, value: str,
                        confidence: str = "medium", source: str = "") -> Fact:
        return self.record("target", target, value, confidence, source)

    def remember_agent(self, agent: str, value: str,
                       confidence: str = "medium", source: str = "") -> Fact:
        return self.record("agent", agent, value, confidence, source)

    def remember_tool(self, tool: str, value: str,
                      confidence: str = "medium", source: str = "") -> Fact:
        return self.record("tool", tool, value, confidence, source)

    # ── recall ─────────────────────────────────────────────────────────────────

    def recall(self, kind: str | None = None, key: str | None = None,
               value: str | None = None) -> list[Fact]:
        out = self.facts
        if kind is not None:
            out = [f for f in out if f.kind == kind]
        if key is not None:
            out = [f for f in out if f.key == str(key)]
        if value is not None:
            out = [f for f in out if f.value == str(value)]
        return out

    def recall_for(self, entity: str) -> list[Fact]:
        """Everything we remember about one target or agent."""
        return self.recall(key=str(entity))

    def forget_entity(self, entity: str) -> int:
        """Forget every fact about an entity. Returns how many were dropped."""
        kept = [f for f in self.facts if f.key != str(entity)]
        dropped = len(self.facts) - len(kept)
        self.facts = kept
        self.save()
        return dropped

    # ── stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        kinds = {}
        for f in self.facts:
            kinds[f.kind] = kinds.get(f.kind, 0) + 1
        return {"total": len(self.facts), "kinds": kinds}

    def recent(self, n: int = 10) -> list[Fact]:
        return self.facts[-n:]

    # ── distillation: lesson → durable facts ───────────────────────────────────

    def distill(self, lesson) -> list[Fact]:
        """Turn a lesson into the durable facts the stack should keep.

        Called automatically by the evolution loop whenever a lesson is
        recorded, so memory deepens with zero extra ceremony.
        """
        from one2one.agents.lessons import Lesson

        if isinstance(lesson, dict):
            lesson = Lesson(**{k: lesson[k] for k in
                               ("id", "agent", "kind", "summary") if k in lesson})
        agent = getattr(lesson, "agent", "") or "STACK"
        target = getattr(lesson, "target", "") or ""
        outcome = getattr(lesson, "outcome", "") or "clean"
        findings = int(getattr(lesson, "findings", 0) or 0)
        source = getattr(lesson, "id", "")

        recorded = [self.remember_agent(
            agent, f"outcome:{outcome}", "high", source)]
        if target:
            recorded.append(self.remember_target(
                target, "seen", "high", source))
            if findings:
                recorded.append(self.remember_target(
                    target, f"findings:{findings}", "medium", source))
        return recorded


def load(path: Path | None = None) -> AgentMemory:
    return AgentMemory(path)


def demo() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        mem = AgentMemory(Path(td) / "memory.json")
        mem.remember_target("example.com", "seen", "high", "lesson-1")
        mem.remember_target("example.com", "findings:3", "medium", "lesson-1")
        mem.remember_agent("RAPTOR", "outcome:findings", "high", "lesson-1")
        mem.record("target", "example.com", "seen", "high", "lesson-2")  # re-confirm
        print(mem.stats())
        print("  example.com ->", [f.value for f in mem.recall_for("example.com")])
        print("  agents      ->", [f.value for f in mem.recall(kind="agent")])


if __name__ == "__main__":
    demo()
