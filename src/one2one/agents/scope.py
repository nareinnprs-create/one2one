"""Scope gate — the safety rail every mission crosses. Default-deny.

A mission is only allowed when its target matches ``scope_in`` and is not
excluded by ``scope_out``. With no scope configured the gate refuses
everything: the stack never acts on un-scoped work. Mirrors the engagement
model in ``one2one.engagement`` but stands alone so the gate never depends on
an engagement existing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from urllib.parse import urlparse


def normalize_target(target: str) -> str:
    """Host form of a target: scheme/port/path stripped, lowercased.

    ``https://Example.com:8443/path`` → ``example.com``; bare hosts pass through.
    Local targets (``code:``/``binary:``) are left untouched — the gate handles
    them separately via the ``local`` flag.
    """
    t = (target or "").strip().lower().rstrip(".")
    if not t:
        return ""
    if t.startswith(("code:", "binary:")):
        return t
    if "://" in t:
        t = urlparse(t).netloc or t
    t = t.split(":", 1)[0]
    t = t.split("/", 1)[0]
    return t.rstrip(".")


def is_local_target(target: str) -> bool:
    """True for filesystem targets (code:./dir, binary:./file) vs hosts."""
    return (target or "").strip().lower().startswith(("code:", "binary:"))


def _pattern(entry: str) -> str:
    return (entry or "").strip().lower().rstrip(".")


@dataclass
class Decision:
    allow: bool
    reason: str
    target: str = ""


@dataclass
class Scope:
    name: str = ""
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)
    local: bool = False          # authorizes code:/binary: filesystem targets

    @classmethod
    def from_engagement(cls, engagement: object) -> "Scope":
        """Build from a one2one.engagement.Engagement-like object."""
        return cls(
            name=str(getattr(engagement, "name", "")),
            scope_in=list(getattr(engagement, "scope_in", None) or []),
            scope_out=list(getattr(engagement, "scope_out", None) or []),
        )

    def allows(self, target: str) -> bool:
        if is_local_target(target):
            return self.local
        host = normalize_target(target)
        if not host:
            return False
        if any(fnmatch(host, _pattern(p)) for p in self.scope_out):
            return False
        return any(fnmatch(host, _pattern(p)) for p in self.scope_in)

    def reason(self, target: str) -> str:
        if is_local_target(target):
            if self.local:
                return "in scope (local target authorized)"
            return "default-deny: local target requires Scope(local=True)"
        host = normalize_target(target)
        if not host:
            return "default-deny: empty target"
        if not self.scope_in:
            name = f" (engagement '{self.name}')" if self.name else ""
            return f"default-deny: no scope set{name}"
        if any(fnmatch(host, _pattern(p)) for p in self.scope_out):
            return f"target '{host}' excluded by scope-out"
        return f"target '{host}' not in scope-in"

    def describe(self) -> str:
        parts = [f"scope '{self.name or '(unnamed)'}'"]
        if self.scope_in:
            parts.append("in: " + ", ".join(self.scope_in))
        if self.scope_out:
            parts.append("out: " + ", ".join(self.scope_out))
        if self.local:
            parts.append("local: yes")
        return " · ".join(parts)


class ScopeGate:
    """Holds a Scope and answers target checks with a default-deny Decision."""

    def __init__(self, scope: Scope | None = None) -> None:
        self.scope = scope or Scope()

    def check(self, target: str) -> Decision:
        if is_local_target(target):
            return Decision(self.scope.local, self.scope.reason(target),
                            (target or "").strip())
        host = normalize_target(target)
        if not host:
            return Decision(False, "default-deny: empty target", target or "")
        return Decision(self.scope.allows(host), self.scope.reason(host), host)
