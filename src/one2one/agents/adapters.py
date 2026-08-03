"""Worker adapters — real execution behind the roster (P1: the Mythos leg).

A WorkerRegistry maps each of the 32 worker callsigns to a handler that turns a
Mission into a WorkerReport. P1 ships one real adapter — MythosAdapter — which
runs the existing six-agent pipeline against the mission's target, so the stack
can run today: network targets run the headless pipeline, ``code:``/``binary:``
targets run the codebase/binary deep-dives. Without a model or tools the
pipeline degrades to offline scanning; it never fabricates. Findings flow up as
``MythosFinding`` objects for the wing lead to review before escalation.
"""
from __future__ import annotations

from one2one.agents.command import WorkerReport, dispatch_worker
from one2one.agents.roster import WORKERS


class WorkerRegistry:
    """Maps worker callsigns to handlers; unregistered workers get the P0 stub."""

    def __init__(self) -> None:
        self.handlers: dict[str, callable] = {}

    def register(self, worker: str, handler: callable) -> None:
        self.handlers[worker.upper()] = handler

    def dispatch(self, mission) -> WorkerReport:
        handler = self.handlers.get(mission.worker)
        if handler is None:
            return dispatch_worker(mission)
        return handler(mission)


class MythosAdapter:
    """Runs the real Mythos pipeline for a mission's target."""

    def run(self, mission) -> WorkerReport:
        target = (mission.target or "").strip()
        if not target:
            return WorkerReport(mission.worker, False,
                                f"{mission.worker}: no target — nothing ran")
        session = self._run_pipeline(target)
        findings = list(getattr(session, "findings", None) or [])
        return WorkerReport(
            mission.worker,
            True,
            f"mythos pipeline ran for {target!r}; {len(findings)} finding(s)",
            findings)

    @staticmethod
    def _run_pipeline(target: str):
        """Route a target to the matching headless Mythos entry point."""
        from one2one import mythos
        kind = target.split(":", 1)[0]
        if kind == "code":
            return mythos.run_code(target[5:], interactive=False)
        if kind == "binary":
            return mythos.run_binary(target[7:], interactive=False)
        return mythos.run_headless(target)


def register_mythos(registry: WorkerRegistry,
                    workers: list[str] | None = None) -> WorkerRegistry:
    """Wire the Mythos adapter onto every worker (or a chosen subset)."""
    adapter = MythosAdapter()
    for worker in (workers if workers is not None else list(WORKERS)):
        registry.register(worker, adapter.run)
    return registry
