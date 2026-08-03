"""Workflow playbooks — reusable multi-worker chains (Item 3, capability
expansion).

A workflow is a named playbook: an ordered list of ``(worker, argv_template,
purpose)`` steps that fans a single intent across several Tier-1 workers. Where
a SkillPatch taught a single worker a new signature or builtin, an
``add-workflow`` patch teaches the whole stack a reusable technique.

Workflows live in ``~/.one2one/agents/workflows.json`` beside the lesson log.
They arrive through the SAME evolution gate as every other skill change (the
seed feed ships starter playbooks, the gate approves them), and they can be
run from the console with ``/workflow run <name> <target>`` — always inside the
authorized scope: the caller must check ``configured_scope().check(target)``
before dispatching, mirroring the mission gate.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from one2one.constants import USER_CONFIG_DIR

WORKFLOW_FILE = USER_CONFIG_DIR / "agents" / "workflows.json"

_WORKFLOW_FIELDS = ("name", "steps", "source", "created", "version")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Workflow:
    """A named, gated playbook of worker steps."""
    name: str
    steps: list = field(default_factory=list)   # [(worker, argv, purpose), ...]
    source: str = ""                            # the patch/lesson that seeded it
    created: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        if not self.created:
            self.created = _now()
        self.steps = [tuple(s) for s in self.steps]

    def describe(self) -> list[str]:
        return [f"{worker}: {purpose}" for worker, _tmpl, purpose in self.steps]


class WorkflowRegistry:
    """Persistent, code-owned playbook ledger."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else WORKFLOW_FILE
        self.workflows: dict[str, Workflow] = {}
        self.load()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            [asdict(w) for w in self.workflows.values()], indent=2),
            encoding="utf-8")

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError:
            return
        if not isinstance(data, list):
            return
        for item in data:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            item = {k: item[k] for k in _WORKFLOW_FIELDS if k in item}
            try:
                wf = Workflow(**item)
            except (TypeError, ValueError):
                continue
            if wf.steps and self.validate(wf) == []:
                self.workflows[wf.name] = wf

    # ── registry ops ───────────────────────────────────────────────────────────

    def register(self, name: str, steps, source: str = "") -> Workflow:
        """Add or refresh a playbook. Deduplicates by name."""
        name = str(name).strip()
        if not name:
            raise ValueError("workflow name must be non-empty")
        wf = Workflow(name=name, steps=[tuple(s) for s in steps], source=source)
        if name in self.workflows:                # refresh in place
            wf.created = self.workflows[name].created
        self.workflows[name] = wf
        self.save()
        return wf

    def get(self, name: str) -> Workflow | None:
        return self.workflows.get(name)

    def all(self) -> list[Workflow]:
        return list(self.workflows.values())

    def names(self) -> list[str]:
        return sorted(self.workflows)

    # ── static validity (the workflow's "regression") ──────────────────────────

    def validate(self, wf: Workflow) -> list[str]:
        """Every step must reference a Tier-1 worker and a fillable template."""
        from one2one.agents import roster
        issues = []
        for i, (worker, template, purpose) in enumerate(wf.steps, start=1):
            worker = (worker or "").upper()
            if not worker or worker not in roster.WORKERS:
                issues.append(f"step {i}: unknown worker {worker!r}")
            if not (template or "").strip():
                issues.append(f"step {i}: empty argv template")
        return issues

    # ── execution ──────────────────────────────────────────────────────────────

    def run(self, name: str, target: str, runner=None, memory=None) -> dict:
        """Run a playbook against a target. Caller must scope-gate first.

        Each step is executed by its owning worker (best-effort, never raises)
        and analyzed with that worker's signatures/intel. When ``memory`` is
        given, each worker is memory-assisted: findings the stack already knows
        are suppressed instead of re-reported. Returns a combined report dict:
        ``{name, steps, findings, intel, known, executed, errors}``.
        """
        from one2one.agents.workers import WORKER_CLASSES, Step, _fill, _split

        wf = self.get(name)
        if wf is None:
            raise KeyError(f"no workflow named {name!r}")
        issues = self.validate(wf)
        if issues:
            return {"name": name, "steps": len(wf.steps), "findings": [],
                    "intel": [], "known": [], "executed": False,
                    "errors": issues}

        classes = {cls.CALLSIGN: cls for cls in WORKER_CLASSES}
        combined: dict = {"name": name, "steps": len(wf.steps),
                          "findings": [], "intel": [], "known": [],
                          "executed": False, "errors": []}
        target = (target or "").strip()
        if not target:
            combined["errors"].append("no target — nothing ran")
            return combined
        target = target.split(":", 1)[-1] if target.startswith(
            ("code:", "binary:")) else target

        for worker, template, purpose in wf.steps:
            cls = classes.get((worker or "").upper())
            if cls is None:
                combined["errors"].append(f"skip {worker}: no worker module")
                continue
            w = cls(runner=runner, memory=memory)
            step = Step(tool=template.split()[0] if template.split() else worker,
                        argv=_split(_fill(template, target)), purpose=purpose,
                        source="workflow")
            report = w.analyze(target, w.execute([step]))
            combined["findings"].extend(
                asdict(f) for f in report.findings)
            combined["intel"].extend(report.intel)
            combined["known"].extend(asdict(f) for f in report.known)
            combined["executed"] = combined["executed"] or report.executed
        return combined


def load(path: Path | None = None) -> WorkflowRegistry:
    return WorkflowRegistry(path)


def demo() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        reg = WorkflowRegistry(Path(td) / "workflows.json")
        wf = reg.register("recon-chain", [
            ("EYRIE", "nmap -sV {target}", "service versions"),
            ("CARTO", "dnsrecon -d {target} -t std", "dns enumeration"),
        ], source="seed")
        print(f"{wf.name}: {reg.validate(wf) or 'valid'}")
        print("  " + "\n  ".join(wf.describe()))
        print(f"persisted -> {reg.get('recon-chain').name}")
