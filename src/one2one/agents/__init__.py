"""One2One Agent Stack — the self-evolving command chain.

P0 delivered the command skeleton (roster, scope gate, ledger, router,
APEX/COMMANDER). P1 adds the three wing leads with brutal finding review and a
real worker adapter over the Mythos pipeline. P2 ships the 10 Intel workers,
P3 the 16 Offense and 6 Truth workers with parallel dispatch and streamed
findings, and P4 the self-development loop: every mission is logged as a
lesson, workers propose skill patches, and APEX gates and propagates them with
regression rollback.
"""
from . import adapters, command, evolution, ledger, lessons, roster, router, scope, wing
from .adapters import MythosAdapter, WorkerRegistry, register_mythos
from .command import Apex, Commander, WorkerReport, dispatch_worker, extract_target
from .evolution import (
    APPROVAL_TIERS, Evolution, PatchGate, REGRESSION_CASES, SkillPatch,
    run_regression,
)
from .ledger import (
    Mission, MissionLedger, STATUS_DONE, STATUS_FAILED, STATUS_KILLED,
    STATUS_PENDING, STATUS_REFUSED, STATUS_RUNNING,
)
from .lessons import LESSON_KINDS, Lesson, LessonLedger
from .roster import (
    AGENTS, OPERATOR, ONSLAUGHT, SUPREME, TRIBUNAL, VANGUARD, WORKERS, WINGS,
)
from .scope import Decision, Scope, ScopeGate, normalize_target
from .wing import WingLead, WingReport, WING_LEADS, wing_lead_for


def get_roster() -> list[dict]:
    """All 37 agents as dicts (callsign, tier, wing, responsibility)."""
    return roster.roster()


__all__ = [
    "AGENTS", "OPERATOR", "ONSLAUGHT", "SUPREME", "TRIBUNAL", "VANGUARD",
    "WORKERS", "WINGS", "get_roster",
    "Apex", "Commander", "WorkerReport", "WorkerRegistry", "dispatch_worker",
    "extract_target", "MythosAdapter", "register_mythos",
    "Mission", "MissionLedger",
    "STATUS_DONE", "STATUS_FAILED", "STATUS_KILLED", "STATUS_PENDING",
    "STATUS_REFUSED", "STATUS_RUNNING",
    "Decision", "Scope", "ScopeGate", "normalize_target",
    "WingLead", "WingReport", "WING_LEADS", "wing_lead_for",
    "APPROVAL_TIERS", "Evolution", "PatchGate", "REGRESSION_CASES",
    "SkillPatch", "run_regression",
    "LESSON_KINDS", "Lesson", "LessonLedger",
]
