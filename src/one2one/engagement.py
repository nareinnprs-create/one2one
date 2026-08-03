"""First-class engagement + persisted workspace. Deterministic, code-owned."""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from one2one.constants import USER_CONFIG_DIR

if TYPE_CHECKING:
    from one2one.agents.scope import Scope

ENGAGEMENTS_ROOT = USER_CONFIG_DIR / "engagements"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Engagement:
    name: str
    created: str
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    runs: list[dict] = field(default_factory=list)
    active: bool = True
    roe: dict = field(default_factory=dict)   # rules of engagement (see create)
    notes: str = ""

    @property
    def workspace(self) -> Path:
        return ENGAGEMENTS_ROOT / self.name

    @property
    def raw_dir(self) -> Path:
        return self.workspace / "raw"

    @property
    def findings_file(self) -> Path:
        return self.workspace / "findings.json"

    @property
    def report_file(self) -> Path:
        return self.workspace / "report.md"

    @property
    def report_draft_file(self) -> Path:
        return self.workspace / "report.draft.md"

    @property
    def log_file(self) -> Path:
        return self.workspace / "run.log"

    def in_scope(self, host: str) -> bool:
        if any(fnmatch(host, p) for p in self.scope_out):
            return False
        return any(fnmatch(host, p) for p in self.scope_in)

    def is_excluded(self, host: str) -> bool:
        """True if host matches any scope_out exclusion pattern."""
        return any(fnmatch(host, p) for p in self.scope_out)

    def to_scope(self) -> "Scope":
        """Build a scope-gate Scope from this engagement's scope_in/scope_out.

        Lets the mission scope gate and the engagement share ONE source of
        truth: when an engagement is active, its scope is what /ask and the
        stack enforce. Local (code:/binary:) targets stay denied unless the
        engagement's ROE explicitly opts them in.
        """
        from one2one.agents.scope import Scope
        return Scope(name=f"engagement:{self.name}",
                     scope_in=list(self.scope_in),
                     scope_out=list(self.scope_out),
                     local=bool((self.roe or {}).get("local")))

    def log(self, msg: str) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"{_now()} {msg}\n")

    def add_run(self, run: dict) -> None:
        self.runs.append(run)
        self.save()

    def save(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "engagement.json").write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8")


def load(name: str) -> Engagement | None:
    f = ENGAGEMENTS_ROOT / name / "engagement.json"
    if not f.exists():
        return None
    data = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return Engagement(**{k: data[k] for k in Engagement.__dataclass_fields__ if k in data})


def create(name: str, targets: list[str] | None = None,
           scope_in: list[str] | None = None,
           scope_out: list[str] | None = None,
           roe: dict | None = None, notes: str = "") -> Engagement:
    targets = targets or []
    # default scope-in to the targets themselves when none given
    scope_in = scope_in if scope_in is not None else list(targets)
    e = Engagement(name=name, created=_now(), scope_in=scope_in,
                   scope_out=scope_out or [], targets=targets, runs=[],
                   active=True, roe=roe or {}, notes=notes)
    e.save()
    for other in list_all():
        if other.name != name and other.active:
            other.active = False
            other.save()
    return e


def get_or_create(name: str, targets: list[str] | None = None,
                  roe: dict | None = None, notes: str = "") -> Engagement:
    existing = load(name)
    if existing:
        if targets:
            existing.targets = targets
            if not existing.scope_in:
                existing.scope_in = list(targets)
            existing.save()
        return existing
    return create(name, targets=targets, roe=roe, notes=notes)


def list_all() -> list[Engagement]:
    """Every engagement, sorted by name. Missing/corrupt dirs are skipped."""
    if not ENGAGEMENTS_ROOT.is_dir():
        return []
    out = []
    for d in sorted(ENGAGEMENTS_ROOT.iterdir()):
        if d.is_dir():
            e = load(d.name)
            if e is not None:
                out.append(e)
    return out


def active() -> Engagement | None:
    """The currently-active engagement, or None if none is active."""
    return next((e for e in list_all() if e.active), None)


def activate(name: str) -> Engagement | None:
    """Make one engagement active (deactivating the rest). Returns it or None."""
    if load(name) is None:
        return None
    for e in list_all():
        e.active = (e.name == name)
        e.save()
    return load(name)


def deactivate(name: str) -> Engagement | None:
    """Turn an engagement off without deleting it."""
    e = load(name)
    if e is None:
        return None
    e.active = False
    e.save()
    return e


def close(name: str) -> Engagement | None:
    """Mark an engagement complete (inactive). Returns it or None."""
    return deactivate(name)
