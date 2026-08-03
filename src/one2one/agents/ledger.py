"""Mission ledger — the single live battle picture for the stack.

Every mission COMMANDER submits is recorded here with its worker, wing and
status, then persisted as JSON under ``~/.one2one/agents/ledger.json``. The
ledger is the one source of truth the whole stack reads, so no two agents ever
hold contradicting state.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from one2one.constants import USER_CONFIG_DIR

LEDGER_FILE = USER_CONFIG_DIR / "agents" / "ledger.json"

_MISSION_FIELDS = (
    "id", "intent", "target", "worker", "wing", "operator",
    "supreme", "status", "created", "outcome",
)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_KILLED = "killed"
STATUS_REFUSED = "refused"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_mission_id(worker: str) -> str:
    return f"{worker}-{uuid4().hex[:8]}"


@dataclass
class Mission:
    id: str
    intent: str
    target: str = ""
    worker: str = ""
    wing: str = ""
    operator: str = "COMMANDER"
    supreme: str = "APEX"
    status: str = STATUS_PENDING
    created: str = ""
    outcome: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created:
            self.created = _now()


@dataclass
class MissionLedger:
    path: Path = field(default_factory=lambda: LEDGER_FILE)
    missions: list[Mission] = field(default_factory=list)

    def record(self, mission: Mission) -> Mission:
        self.missions = [m for m in self.missions if m.id != mission.id]
        self.missions.append(mission)
        self.save()
        return mission

    def get(self, mission_id: str) -> Mission | None:
        return next((m for m in self.missions if m.id == mission_id), None)

    def by_agent(self, agent: str) -> list[Mission]:
        return [m for m in self.missions if m.worker == agent]

    def by_wing(self, wing: str) -> list[Mission]:
        return [m for m in self.missions if m.wing == wing]

    def by_status(self, status: str) -> list[Mission]:
        return [m for m in self.missions if m.status == status]

    def recent(self, n: int = 10) -> list[Mission]:
        return self.missions[-n:]

    def picture(self) -> dict:
        counts = {}
        for m in self.missions:
            counts[m.status] = counts.get(m.status, 0) + 1
        return {"total": len(self.missions), **counts}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(m) for m in self.missions], indent=2),
            encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> "MissionLedger":
        path = Path(path) if path is not None else LEDGER_FILE
        if not path.exists():
            return cls(path=path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return cls(path=path)
        if not isinstance(data, list):
            return cls(path=path)
        missions = [
            Mission(**{k: item[k] for k in _MISSION_FIELDS if k in item})
            for item in data if isinstance(item, dict)
        ]
        return cls(path=path, missions=missions)
