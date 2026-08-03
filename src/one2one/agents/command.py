"""Command layer — COMMANDER (governor) and APEX (supreme assistant).

COMMANDER governs every mission: it owns the ledger, runs every mission through
the scope gate, routes it to a worker, and moves it through the status machine.
APEX is the user's single interface: it takes plain-English missions, refuses
out-of-scope work, dispatches through COMMANDER, and exposes the roster, the
live battle picture, and (P4) the self-development loop — every completed
mission is learned from, and skill patches are proposed and approved through
the tiered gate.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from one2one.agents import roster
from one2one.agents.evolution import Evolution
from one2one.agents.ledger import Mission, MissionLedger, new_mission_id
from one2one.agents.router import route
from one2one.agents.scope import Decision, Scope, ScopeGate
from one2one.agents.wing import WingReport, wing_lead_for, wing_report_dict

_HOST_RE = re.compile(
    r"(?i)\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b")

P0_NOTE = "worker adapter pending (P2/P3)"


@dataclass
class WorkerReport:
    worker: str
    executed: bool
    note: str
    findings: list = field(default_factory=list)
    intel: list = field(default_factory=list)


def dispatch_worker(mission: Mission) -> WorkerReport:
    """P0 worker stub: records honest 'not executed yet' reports. Replaced by
    real adapters in P2/P3 without touching the command flow."""
    return WorkerReport(
        worker=mission.worker,
        executed=False,
        note=f"{mission.worker}: {P0_NOTE}",
    )


def extract_target(prompt_text: str) -> str:
    """First host-like string in the prompt, else ''."""
    m = _HOST_RE.search(prompt_text or "")
    return m.group(0) if m else ""


class WorkerRegistry:
    """Maps worker callsigns to handlers; unregistered workers get the stub."""

    def __init__(self) -> None:
        self.handlers: dict[str, callable] = {}

    def register(self, worker: str, handler: callable) -> None:
        self.handlers[worker.upper()] = handler

    def dispatch(self, mission: Mission) -> WorkerReport:
        handler = self.handlers.get(mission.worker)
        if handler is None:
            return dispatch_worker(mission)
        return handler(mission)


class Commander:
    """Governs and operates all missions below APEX."""

    def __init__(self, ledger: MissionLedger | None = None,
                 gate: ScopeGate | None = None) -> None:
        self.ledger = ledger or MissionLedger()
        self.gate = gate or ScopeGate()

    def set_scope(self, scope: Scope) -> None:
        self.gate = ScopeGate(scope)

    def check_scope(self, target: str) -> Decision:
        return self.gate.check(target)

    def submit(self, intent: str, target: str = "") -> Mission:
        """Create a mission from intent, routed to a worker, ledgered pending."""
        decision = route(intent)
        mission = Mission(
            id=new_mission_id(decision.worker),
            intent=intent,
            target=target,
            worker=decision.worker,
            wing=decision.wing,
            operator=decision.operator,
            supreme=decision.supreme,
            status="pending",
        )
        self.ledger.record(mission)
        return mission

    def mission_for(self, worker: str, intent: str, target: str = "") -> Mission:
        """Create a mission pinned to a specific worker (parallel fan-out)."""
        mission = Mission(
            id=new_mission_id(worker),
            intent=intent,
            target=target,
            worker=worker,
            wing=roster.wing_of(worker),
            operator=roster.OPERATOR,
            supreme=roster.SUPREME,
            status="pending",
        )
        self.ledger.record(mission)
        return mission

    def start(self, mission: Mission) -> Mission:
        mission.status = "running"
        return self.ledger.record(mission)

    def complete(self, mission: Mission, outcome: dict | None = None) -> Mission:
        mission.status = "done"
        mission.outcome = outcome or {}
        return self.ledger.record(mission)

    def fail(self, mission: Mission, reason: str) -> Mission:
        mission.status = "failed"
        mission.outcome = {"error": reason}
        return self.ledger.record(mission)

    def kill(self, mission: Mission, reason: str) -> Mission:
        mission.status = "killed"
        mission.outcome = {"reason": reason}
        return self.ledger.record(mission)

    def picture(self) -> dict:
        return self.ledger.picture()

    def chain(self, worker: str) -> list[str]:
        return roster.chain_for(worker)


class Apex:
    """Supreme agent — the user's assistant and the stack's single voice."""

    def __init__(self, ledger: MissionLedger | None = None,
                 gate: ScopeGate | None = None,
                 workers: WorkerRegistry | None = None,
                 evolution: Evolution | None = None) -> None:
        self.commander = Commander(ledger=ledger, gate=gate)
        self.workers = workers or WorkerRegistry()
        self.evolution = evolution or Evolution(
            lessons_path=self.commander.ledger.path.parent / "lessons.json")

    def set_scope(self, scope: Scope) -> None:
        self.commander.set_scope(scope)
        self.evolution.gate.scope = self.commander.gate

    def _learn(self, mission: Mission) -> None:
        """P4: every terminal mission becomes a lesson the stack learns from."""
        self.evolution.learn_from_mission(mission)

    def ask(self, prompt_text: str, target: str = "", scope: Scope | None = None,
            stream=None) -> dict:
        """Accept a plain-English mission, gate it, route it, dispatch it.

        Returns a dict describing the decision: ``allowed`` is False for
        out-of-scope or target-less missions (the mission is refused and never
        routed). In-scope missions run through COMMANDER: dispatched to the
        routed worker, the wing lead reviews the worker's findings brutally,
        and the mission completes with both reports. ``stream`` receives each
        accepted finding as it passes the wing lead's review.
        """
        if scope is not None:
            self.set_scope(scope)
        target = (target or "").strip()
        if not target:
            target = extract_target(prompt_text)
        gate = self.commander.gate
        decision = gate.check(target)

        if not decision.allow:
            mission = self.commander.submit(prompt_text, target=decision.target)
            self.commander.kill(mission, f"scope gate: {decision.reason}")
            self._learn(mission)
            return {
                "allowed": False,
                "reason": decision.reason,
                "mission": mission,
                "report": None,
                "wing_report": None,
                "findings": [],
            }

        mission = self.commander.submit(prompt_text, target=decision.target)
        self.commander.start(mission)
        report = self.workers.dispatch(mission)
        wing_report: WingReport = wing_lead_for(mission.wing).supervise(
            mission, report, stream=stream)
        self.commander.complete(mission, {
            "worker_report": asdict(report),
            "wing_report": wing_report_dict(wing_report),
            "findings": [asdict(f) for f in wing_report.accepted],
        })
        self._learn(mission)
        return {
            "allowed": True,
            "reason": "in scope",
            "mission": mission,
            "report": report,
            "wing_report": wing_report,
            "findings": wing_report.accepted,
        }

    def ask_wide(self, prompt_text: str, target: str = "", workers=None,
                 scope: Scope | None = None, stream=None,
                 max_workers: int = 4) -> dict:
        """Fan one intent out to several workers in parallel (the Fast trait).

        By default the routed worker's whole wing runs; ``workers`` pins a
        specific subset. Each worker gets its own ledgered mission, runs on a
        thread, and its findings pass its wing lead's brutal review — accepted
        findings are streamed via ``stream`` as they surface (uplink). Ledger
        writes stay on the calling thread so the single battle picture is never
        corrupted by concurrent saves.
        """
        if scope is not None:
            self.set_scope(scope)
        target = (target or "").strip()
        if not target:
            target = extract_target(prompt_text)
        gate = self.commander.gate
        decision = gate.check(target)

        if not decision.allow:
            mission = self.commander.submit(prompt_text, target=decision.target)
            self.commander.kill(mission, f"scope gate: {decision.reason}")
            self._learn(mission)
            return {
                "allowed": False,
                "reason": decision.reason,
                "missions": [],
                "reports": {},
                "wing_reports": {},
                "findings": [],
            }

        chosen = self._resolve_workers(workers, route(prompt_text).wing)
        if not chosen:
            single = self.ask(prompt_text, target=decision.target, stream=stream)
            mission = single["mission"]
            return {
                "allowed": single["allowed"],
                "reason": single["reason"],
                "missions": [mission] if mission is not None else [],
                "reports": {mission.worker: asdict(single["report"])}
                           if single["report"] else {},
                "wing_reports": {mission.worker: wing_report_dict(
                    single["wing_report"])} if single["wing_report"] else {},
                "findings": single["findings"],
            }
        missions = [self.commander.mission_for(w, prompt_text, decision.target)
                    for w in chosen]
        for m in missions:
            self.commander.start(m)

        def run_one(mission) -> tuple[Mission, WorkerReport, WingReport]:
            report = self.workers.dispatch(mission)
            wing = wing_lead_for(mission.wing).supervise(
                mission, report, stream=stream)
            return mission, report, wing

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            outcomes = list(pool.map(run_one, missions))

        reports: dict[str, dict] = {}
        wing_reports: dict[str, dict] = {}
        findings: list = []
        for mission, report, wing in outcomes:
            self.commander.complete(mission, {
                "worker_report": asdict(report),
                "wing_report": wing_report_dict(wing),
                "findings": [asdict(f) for f in wing.accepted],
            })
            self._learn(mission)
            reports[mission.worker] = asdict(report)
            wing_reports[mission.worker] = wing_report_dict(wing)
            findings.extend(wing.accepted)
        return {
            "allowed": True,
            "reason": "in scope",
            "missions": missions,
            "reports": reports,
            "wing_reports": wing_reports,
            "findings": findings,
        }

    def _resolve_workers(self, workers, default_wing: str) -> list[str]:
        """The worker set for ask_wide: pinned list, else the whole wing."""
        if workers:
            out = [w.upper() for w in workers]
        else:
            out = roster.workers_in(default_wing)
        return [w for w in out if w in self.workers.handlers]

    # ── P4: the self-development loop ─────────────────────────────────────────

    def propose_patch(self, agent: str, kind: str, payload, rationale: str,
                      from_lessons=(), requires_scope: bool = False):
        """A worker proposes a skill patch drawn from its lessons."""
        return self.evolution.propose(agent, kind, payload, rationale,
                                      from_lessons, requires_scope)

    def approve_patch(self, patch) -> object:
        """Run the full gate, then propagate an approved patch with re-run."""
        return self.evolution.approve(patch)

    def patch_status(self, patch) -> dict:
        return self.evolution.status(patch)

    def evolution_picture(self) -> dict:
        """Lessons learned and the status of every proposed skill patch."""
        return {
            "lessons": self.evolution.lessons.picture(),
            "patches": {pid: self.evolution.status(p)
                        for pid, p in self.evolution.patches.items()},
        }

    def roster(self) -> list[dict]:
        return roster.roster()

    def status(self) -> dict:
        return self.commander.picture()

    def chain(self, worker: str) -> list[str]:
        return self.commander.chain(worker)
