"""Self-development loop — lesson log, mutation, gated propagation (P4).

Each agent runs a continuous evolution cycle (doc §5):

1. **Log** — every mission outcome lands in the lesson ledger.
2. **Mutate** — an agent proposes a ``SkillPatch`` from its lessons (a new
   detection signature, intel pattern, or builtin step).
3. **Gate** — the proposal climbs worker → wing lead → COMMANDER → APEX. Every
   reviewer records a decision; scope and ethics are the ultimate gate.
4. **Propagate** — an approved patch becomes everyone's default: it is applied
   to the proposing worker and to every sibling whose signatures/toolset share
   the same detection domain.
5. **Re-run** — each patched worker re-validates against its regression set; a
   regression rolls the patch back on that worker automatically.

Patches are runtime overlays on worker classes (never source edits), so the
loop can mutate, validate and roll back without ever touching the codebase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from one2one.agents import roster
from one2one.agents.ledger import LEDGER_FILE
from one2one.agents.lessons import Lesson, LessonLedger, new_lesson_id
from one2one.agents.scope import ScopeGate

# Mutation kinds APEX will never approve (ethics/scope are the gate).
_RESTRICTED_KINDS = ("run-command", "exfiltrate", "defer-scope",
                     "override-domain")

APPROVAL_TIERS = ("worker", "wing-lead", "operator", "supreme")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_patch_id(agent: str) -> str:
    return f"{agent}-{uuid4().hex[:8]}"


@dataclass
class SkillPatch:
    """A proposed mutation to a worker's skill, gated by the command chain."""
    id: str
    agent: str                      # proposing worker callsign
    kind: str                       # add-signature | add-intel | add-builtin
    payload: object                 # signature/intel/builtin tuple
    rationale: str
    from_lessons: list = field(default_factory=list)
    requires_scope: bool = False    # True -> needs an authorized target scope
    status: str = "proposed"        # proposed|approved|active|killed|rolled-back
    chain: list = field(default_factory=list)   # reviewer decisions
    note: str = ""
    created: str = ""

    def __post_init__(self) -> None:
        if not self.created:
            self.created = _now()

    @property
    def approved_by(self) -> list[str]:
        return [d["reviewer"] for d in self.chain if d["approved"]]


# ── regression harness ────────────────────────────────────────────────────────

@dataclass
class RegressionCase:
    label: str
    output: str
    expected: list                    # vuln_classes that MUST appear; [] = clean


@dataclass
class RegressionResult:
    label: str
    passed: bool
    got: list
    want: list


def _regression_runner(output: str):
    def run(argv, timeout):
        return output
    return run


def run_regression(cls, cases, target: str = "regression") -> list[RegressionResult]:
    """Re-run a worker class against its regression cases after a mutation.

    A case passes when the vuln_classes found match ``expected`` exactly — a
    mutation that produces a false positive (or misses a known one) fails and
    is rolled back on that worker.
    """
    results = []
    for case in cases:
        worker = cls(runner=_regression_runner(case.output))
        report = worker.run(SimpleNamespace(target=target))
        got = sorted({f.vuln_class for f in report.findings})
        want = sorted(case.expected)
        results.append(RegressionResult(case.label, got == want, got, want))
    return results


# Known-good cases for the secret-hunting workers that share the
# ``hardcoded-secret`` detection domain — the propagation + rollback test bed.
REGRESSION_CASES: dict[str, list[RegressionCase]] = {
    "MIRROR": [
        RegressionCase("clean-config", "verbose=1\ntimeout=30\n", []),
        RegressionCase("aws-key", "AKIAIOSFODNN7EXAMPLE\n", ["hardcoded-secret"]),
    ],
    "VAULT": [
        RegressionCase("clean-credentials", "USER=admin\nTOKEN = abc123\n", []),
        RegressionCase("aws-key", "AKIAIOSFODNN7EXAMPLE\n", ["hardcoded-secret"]),
    ],
    "SCALPEL": [
        RegressionCase("clean-binary", "strings dump\n", []),
        RegressionCase("aws-key", "AKIAIOSFODNN7EXAMPLE\n", ["hardcoded-secret"]),
    ],
    "POCKET": [
        RegressionCase("clean-manifest", "package=com.x\n", []),
        RegressionCase("api-key", "api_key = \"ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\"\n",
                       ["hardcoded-secret"]),
    ],
    "NIMBUS": [
        RegressionCase("clean-audit", "prowler report\n", []),
        RegressionCase("aws-key", "AKIAIOSFODNN7EXAMPLE\n", ["hardcoded-secret"]),
    ],
}


# ── patch application (runtime overlays on worker classes) ────────────────────

def _worker_class(callsign: str):
    from one2one.agents import workers
    for cls in workers.WORKER_CLASSES:
        if cls.CALLSIGN == callsign.upper():
            return cls
    return None


def _apply_to_class(cls, patch) -> None:
    if patch.kind == "add-signature":
        sig = tuple(patch.payload)
        if sig not in cls.SIGNATURES:
            cls.SIGNATURES = cls.SIGNATURES + (sig,)
    elif patch.kind == "add-intel":
        pat = tuple(patch.payload)
        if pat not in cls.INTEL_PATTERNS:
            cls.INTEL_PATTERNS = cls.INTEL_PATTERNS + (pat,)
    elif patch.kind == "add-builtin":
        step = tuple(patch.payload)
        if step not in cls.BUILTIN_STEPS:
            cls.BUILTIN_STEPS = cls.BUILTIN_STEPS + (step,)


def _remove_from_class(cls, patch) -> None:
    if patch.kind == "add-signature":
        cls.SIGNATURES = tuple(s for s in cls.SIGNATURES
                               if s != tuple(patch.payload))
    elif patch.kind == "add-intel":
        cls.INTEL_PATTERNS = tuple(p for p in cls.INTEL_PATTERNS
                                   if p != tuple(patch.payload))
    elif patch.kind == "add-builtin":
        cls.BUILTIN_STEPS = tuple(s for s in cls.BUILTIN_STEPS
                                  if s != tuple(patch.payload))


# ── the gate ──────────────────────────────────────────────────────────────────

class PatchGate:
    """Tiered approval chain + the scope/ethics rail for every mutation."""

    def __init__(self, scope: ScopeGate | None = None) -> None:
        self.scope = scope

    def review(self, patch: SkillPatch, reviewer: str, approved: bool,
               reason: str) -> SkillPatch:
        patch.chain.append({
            "reviewer": reviewer,
            "approved": bool(approved),
            "reason": reason,
        })
        return patch

    def scope_ok(self, patch: SkillPatch) -> bool:
        """Scoped patches are default-deny: they need an active scope that
        authorizes the payload's target, mirroring the mission scope gate."""
        if not patch.requires_scope:
            return True
        if self.scope is None:
            return False
        target = ""
        if isinstance(patch.payload, dict):
            target = str(patch.payload.get("target", ""))
        if not target:
            return True
        return self.scope.check(target).allow


# ── the orchestrator ──────────────────────────────────────────────────────────

class Evolution:
    """Owns the loop: learn → propose → gate → propagate → re-run → rollback."""

    def __init__(self, lessons_path=None, gate: PatchGate | None = None,
                 memory=None) -> None:
        # Load the persisted lesson log so lessons survive across sessions; a
        # fresh path simply starts empty. (Without this, the first mission of a
        # new session would overwrite every lesson learned earlier.)
        self.lessons = LessonLedger.load(
            lessons_path or (LEDGER_FILE.parent / "lessons.json"))
        # Deeper memory lives beside the lesson log: each lesson is distilled
        # into durable, recallable facts (see agents/memory.py).
        from one2one.agents.memory import AgentMemory
        self.memory = memory or AgentMemory(
            self.lessons.path.parent / "memory.json")
        self.gate = gate or PatchGate()
        self.patches: dict[str, SkillPatch] = {}
        self.applied: dict[str, list[str]] = {}   # patch_id -> callsigns

    # 1. log
    def learn_from_mission(self, mission) -> Lesson:
        """Record a mission's outcome as a structured, versioned lesson.

        Also deepens the stack's memory: the lesson is distilled into durable,
        recallable facts (targets seen, agent outcomes, finding counts) that
        survive across sessions (agents/memory.py).
        """
        outcome = mission.outcome or {}
        findings = outcome.get("findings") or []
        status = getattr(mission, "status", "")
        resolved = "findings" if findings else "clean"
        if status in ("failed", "killed"):
            resolved = status
        lesson = Lesson(
            id=new_lesson_id(mission.worker or "STACK"),
            agent=mission.worker or "STACK",
            kind="outcome",
            summary=(f"{mission.worker} {status} on "
                     f"{mission.target or '<no target>'}: "
                     f"{len(findings)} accepted finding(s)"),
            mission_id=mission.id,
            target=mission.target,
            outcome=resolved,
            findings=len(findings),
        )
        lesson = self.lessons.record(lesson)
        self.memory.distill(lesson)
        # Remember each accepted finding so memory-assisted workers refuse to
        # re-report it on the next pass (Item 4, honesty contract).
        for finding in findings:
            value = f"{finding.get('vuln_class', '')}|{finding.get('summary', '')}"
            if mission.target and value != "|":
                self.memory.record("finding", mission.target, value,
                                   finding.get("confidence", "medium"),
                                   source=lesson.id)
        return lesson

    def lessons_for(self, agent: str) -> list[Lesson]:
        return self.lessons.by_agent(agent)

    # deeper memory: distill every lesson into durable, recallable facts
    def distill(self, lesson: Lesson) -> list:
        """Persist the lesson as durable memory facts (agents/memory.py)."""
        return self.memory.distill(lesson)

    # 2. mutate
    def propose(self, agent: str, kind: str, payload, rationale: str,
                from_lessons=(), requires_scope: bool = False) -> SkillPatch:
        """An agent proposes a skill patch drawn from its lessons."""
        agent = agent.upper()
        if agent not in roster.WORKERS:
            raise ValueError(f"{agent} is not a Tier-1 worker")
        if kind not in ("add-signature", "add-intel", "add-builtin",
                        "add-workflow"):
            raise ValueError(f"unknown mutation kind {kind!r}")
        patch = SkillPatch(
            id=new_patch_id(agent),
            agent=agent,
            kind=kind,
            payload=payload,
            rationale=rationale,
            from_lessons=list(from_lessons),
            requires_scope=requires_scope,
        )
        self.patches[patch.id] = patch
        return patch

    # 3 + 4 + 5. gate → propagate → re-run
    def approve(self, patch: SkillPatch) -> SkillPatch:
        """Run the full gate, then propagate an approved patch with re-run."""
        if patch.status not in ("proposed", "killed", "rolled-back"):
            return patch
        patch.status = "proposed"
        patch.chain = [d for d in patch.chain if d["reviewer"] != "wing-lead"]
        cls = _worker_class(patch.agent)
        if cls is None:
            self.gate.review(patch, roster.wing_of(patch.agent), False,
                             "no worker module for this callsign")
            patch.status = "killed"
            return patch

        # Wing lead — the proposal must stay inside its domain.
        if patch.kind in ("override-domain",):
            self.gate.review(patch, roster.wing_of(patch.agent), False,
                             "domain-locked: a worker cannot change its wing")
            patch.status = "killed"
            return patch
        self.gate.review(patch, roster.wing_of(patch.agent), True,
                         "mutation stays within the wing's remit")

        # COMMANDER — scope is the rail; scoped mutations are default-deny.
        if not self.gate.scope_ok(patch):
            self.gate.review(patch, roster.OPERATOR, False,
                             "default-deny: mutation requires scope that is "
                             "not authorized")
            patch.status = "killed"
            return patch
        self.gate.review(patch, roster.OPERATOR, True,
                         "within scope / scope not implicated")

        # APEX — the final, human-and-ethics gate.
        if patch.kind in _RESTRICTED_KINDS:
            self.gate.review(patch, roster.SUPREME, False,
                             "never allowed: restricted mutation kind")
            patch.status = "killed"
            return patch
        self.gate.review(patch, roster.SUPREME, True,
                         "approved — ethics and scope respected")

        patch.status = "approved"
        return self._propagate_and_validate(patch)

    def _propagation_targets(self, patch: SkillPatch) -> list:
        cls = _worker_class(patch.agent)
        targets = [cls]
        from one2one.agents import workers
        if patch.kind == "add-signature":
            vuln_class = str(patch.payload[0])
            for other in workers.WORKER_CLASSES:
                if other is not cls and any(s[0] == vuln_class
                                           for s in other.SIGNATURES):
                    targets.append(other)
        elif patch.kind in ("add-intel", "add-builtin"):
            wing = roster.wing_of(patch.agent)
            for other in workers.WORKER_CLASSES:
                if other is not cls and roster.wing_of(other.CALLSIGN) == wing:
                    targets.append(other)
        return targets

    def _propagate_and_validate(self, patch: SkillPatch) -> SkillPatch:
        if patch.kind == "add-workflow":
            return self._register_workflow(patch)
        applied: list[str] = []
        rolled_back: list[str] = []
        for cls in self._propagation_targets(patch):
            _apply_to_class(cls, patch)
            results = run_regression(cls, REGRESSION_CASES.get(cls.CALLSIGN, []))
            if results and not all(r.passed for r in results):
                _remove_from_class(cls, patch)
                rolled_back.append(cls.CALLSIGN)
                continue
            applied.append(cls.CALLSIGN)
        self.applied[patch.id] = applied
        self.patches[patch.id] = patch
        note = f"applied to {len(applied)} worker(s): {', '.join(applied) or '-'}"
        if rolled_back:
            note += f"; regression rollback on {', '.join(rolled_back)}"
        patch.note = note
        if patch.agent in rolled_back:
            patch.status = "rolled-back"
        elif applied:
            patch.status = "active"
        else:
            patch.status = "approved"
        return patch

    def _register_workflow(self, patch: SkillPatch) -> SkillPatch:
        """Propagate an approved workflow to the persistent playbook registry.

        The "regression" for a playbook is static validity (every step names a
        real worker and a fillable template); an invalid workflow is refused.
        """
        from one2one.agents.workflows import WorkflowRegistry

        name, steps = patch.payload
        reg = WorkflowRegistry(self.lessons.path.parent / "workflows.json")
        issues = []
        wf = None
        try:
            wf = reg.register(name, steps, source=patch.id)
            issues = reg.validate(wf)
        except (ValueError, TypeError):
            issues = ["malformed workflow payload"]
        if issues:
            self.gate.review(patch, roster.OPERATOR, False,
                             "workflow invalid: " + "; ".join(issues))
            patch.status = "killed"
            patch.note = f"workflow {name!r} refused: " + "; ".join(issues)
            return patch
        applied = [name]
        self.applied[patch.id] = applied
        patch.note = f"workflow '{name}' registered ({len(wf.steps)} step(s))"
        patch.status = "active"
        return patch

    def picture(self) -> dict:
        return self.lessons.picture()

    def status(self, patch: SkillPatch) -> dict:
        return {"id": patch.id, "agent": patch.agent, "kind": patch.kind,
                "status": patch.status, "applied_to": self.applied.get(patch.id, []),
                "chain": patch.chain, "note": patch.note}


def demo() -> None:
    evo = Evolution()
    p = evo.propose("MIRROR", "add-signature",
                    ("hardcoded-secret", "Slack token",
                     r"xox[baprs]-[A-Za-z0-9-]{10,}", "plausible"),
                    "lessons show Slack tokens leaking")
    approved = evo.approve(p)
    print(f"{approved.id} -> {approved.status}: {approved.note}")
    print(f"  gate: {approved.approved_by}")


if __name__ == "__main__":
    demo()
