"""Lesson log — the stack's memory (P4, the self-development loop).

Every mission outcome, near-miss and rejected hypothesis is recorded as a
structured, versioned ``Lesson`` under ``~/.one2one/agents/lessons.json``. The
lesson log is what the evolution loop reads to propose skill patches: an agent
mutates from its own lessons, not from guesswork. Mirrors the mission ledger's
shape (``ledger.py``) so the two battle-picture files stay consistent.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from one2one.constants import USER_CONFIG_DIR

LESSON_FILE = USER_CONFIG_DIR / "agents" / "lessons.json"

_LESSON_FIELDS = (
    "id", "agent", "kind", "summary", "mission_id", "target", "outcome",
    "findings", "version", "created",
)

LESSON_KINDS = ("outcome", "near-miss", "rejected-hypothesis")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_lesson_id(agent: str) -> str:
    return f"{agent}-{uuid4().hex[:8]}"


@dataclass
class Lesson:
    id: str
    agent: str
    kind: str                    # outcome | near-miss | rejected-hypothesis
    summary: str
    mission_id: str = ""
    target: str = ""
    outcome: str = ""            # clean | findings | failed | killed
    findings: int = 0
    version: int = 1             # schema version; bumped on migration
    created: str = ""

    def __post_init__(self) -> None:
        if not self.created:
            self.created = _now()
        if self.kind not in LESSON_KINDS:
            raise ValueError(f"unknown lesson kind {self.kind!r}")


@dataclass
class LessonLedger:
    path: Path = field(default_factory=lambda: LESSON_FILE)
    lessons: list[Lesson] = field(default_factory=list)

    def record(self, lesson: Lesson) -> Lesson:
        self.lessons = [l for l in self.lessons if l.id != lesson.id]
        self.lessons.append(lesson)
        self.save()
        return lesson

    def get(self, lesson_id: str) -> Lesson | None:
        return next((l for l in self.lessons if l.id == lesson_id), None)

    def by_agent(self, agent: str) -> list[Lesson]:
        return [l for l in self.lessons if l.agent == agent]

    def by_kind(self, kind: str) -> list[Lesson]:
        return [l for l in self.lessons if l.kind == kind]

    def recent(self, n: int = 20) -> list[Lesson]:
        return self.lessons[-n:]

    def picture(self) -> dict:
        counts = {}
        for l in self.lessons:
            counts[l.kind] = counts.get(l.kind, 0) + 1
        return {"total": len(self.lessons), **counts}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(l) for l in self.lessons], indent=2),
            encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> "LessonLedger":
        path = Path(path) if path is not None else LESSON_FILE
        if not path.exists():
            return cls(path=path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return cls(path=path)
        if not isinstance(data, list):
            return cls(path=path)
        lessons = []
        for item in data:
            if not isinstance(item, dict):
                continue
            item = {k: item[k] for k in _LESSON_FIELDS if k in item}
            try:
                lessons.append(Lesson(**item))
            except (ValueError, TypeError):
                continue
        return cls(path=path, lessons=lessons)
