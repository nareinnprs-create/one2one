"""Console-facing agent entry — /ask missions (G1).

Wires the P0-P4 library stack into the interactive console: builds an APEX with
the persistent ledger (the one /stack reads) and the real Mythos worker adapter,
then runs plain-English missions inside the configured ``mission_scope``.
Default-deny: with no scope configured, /ask refuses everything until the user
authorizes targets via /config mission_scope.
"""
from __future__ import annotations


def scope_from_text(scope_text: str):
    """Parse comma-separated scope-in targets into a named Scope."""
    from one2one.agents.scope import Scope
    scope_in = [t.strip() for t in (scope_text or "").split(",") if t.strip()]
    return Scope(name="mission", scope_in=scope_in)


def configured_scope():
    """The scope the stack enforces, in priority order:

    1. The active engagement's scope (when an engagement is active) — so the
       gate and the engagement share ONE source of truth.
    2. The ``mission_scope`` config (default-deny when empty).
    """
    from one2one import config, engagement
    active = engagement.active()
    if active is not None:
        return active.to_scope()
    return scope_from_text(config.load().get("mission_scope", ""))


def default_apex():
    """A console APEX: persistent ledger, Mythos workers, configured scope."""
    from one2one.agents.adapters import register_mythos
    from one2one.agents.command import Apex, WorkerRegistry
    from one2one.agents.ledger import MissionLedger

    workers = register_mythos(WorkerRegistry())
    apex = Apex(ledger=MissionLedger.load(), workers=workers)
    apex.set_scope(configured_scope())
    return apex


def run_mission(intent: str, stream=None) -> dict:
    """Run one plain-English mission through the console APEX.

    ``stream`` is an optional callable invoked with each accepted finding as it
    passes the wing lead's review. Returns ``Apex.ask``'s result dict.
    """
    return default_apex().ask(intent, stream=stream)


def stack_memory():
    """The stack's persistent deeper memory, next to the console lesson log."""
    from one2one.agents.ledger import LEDGER_FILE
    from one2one.agents.memory import AgentMemory
    return AgentMemory(LEDGER_FILE.parent / "memory.json")
