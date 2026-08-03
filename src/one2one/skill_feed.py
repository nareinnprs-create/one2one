"""Skill-feed sync — continuous intel intake for the self-development loop.

``/feed`` pulls new skills for the worker stack: a bundled seed bank plus any
user-authored feed files in ``~/.one2one/feeds/*.yaml``. Each candidate is a
``SkillPatch`` proposal that climbs the SAME tiered gate as a worker's own
mutations (worker → wing lead → COMMANDER → APEX) and is only applied after it
survives the regression set on every worker in its domain.

Two kinds of feed entries exist:
  * signatures — (vuln_class, label, regex, confidence) detection rules
  * intel      — (label, regex) output triage patterns
  * builtin    — (tool, argv_template, purpose) fallback steps
  * workflow   — (name, steps) a multi-worker playbook for the whole stack

Everything is deterministic and offline: the seed bank ships with the package,
user feeds are plain YAML, and a persisted feed-state file (keyed by a hash of
each candidate) keeps re-runs idempotent — a candidate is proposed once unless
it changed. No network is required and no candidate is ever applied without
the gate approving it.

Feed file shape (one per ``~/.one2one/feeds/*.yaml``):

    candidates:
      - agent: MIRROR
        kind: signature            # signature | intel | builtin
        label: OpenAI API key
        pattern: "sk-[A-Za-z0-9]{20,}"
        confidence: plausible      # signatures only
        vuln_class: hardcoded-secret
        rationale: seen in the wild this week
      - agent: NIMBUS
        kind: intel
        label: s3_bucket
        pattern: "s3://[a-z0-9.-]+"
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from one2one.constants import USER_CONFIG_DIR

FEEDS_DIR = USER_CONFIG_DIR / "feeds"
FEED_STATE_FILE = USER_CONFIG_DIR / "agents" / "feed-state.json"

# ── bundled seed bank ─────────────────────────────────────────────────────────
# Each entry mirrors a SkillPatch proposal. Applied only after the gate
# approves AND the worker's regression set still passes.
SEED_FEED: list[dict] = [
    {"agent": "MIRROR", "kind": "signature",
     "vuln_class": "hardcoded-secret", "label": "OpenAI API key",
     "pattern": r"(?i)\bsk-(?:proj-)?[a-zA-Z0-9]{20,}\b", "confidence": "plausible",
     "rationale": "seed bank: OpenAI keys leak in commits and artifacts."},
    {"agent": "VAULT", "kind": "signature",
     "vuln_class": "hardcoded-secret", "label": "Slack webhook",
     "pattern": r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/",
     "confidence": "plausible",
     "rationale": "seed bank: Slack incoming-webhook URLs are routinely committed."},
    {"agent": "VAULT", "kind": "signature",
     "vuln_class": "hardcoded-secret", "label": "Stripe secret key",
     "pattern": r"(?i)\bsk_live_[0-9a-zA-Z]{20,}\b", "confidence": "plausible",
     "rationale": "seed bank: live Stripe keys are a top credential find."},
    {"agent": "POCKET", "kind": "signature",
     "vuln_class": "hardcoded-secret", "label": "Google API key",
     "pattern": r"\bAIza[0-9A-Za-z\-_]{35}\b", "confidence": "plausible",
     "rationale": "seed bank: Google API keys surface in Android resources."},
    {"agent": "NIMBUS", "kind": "signature",
     "vuln_class": "sensitive-data-exposure", "label": "public S3 bucket URL",
     "pattern": r"(?i)s3://[a-z0-9][a-z0-9.-]{1,62}", "confidence": "plausible",
     "rationale": "seed bank: open S3 buckets are a common cloud exposure."},
    {"agent": "ORACLE", "kind": "signature",
     "vuln_class": "crypto-misuse", "label": "SHA-1 used for security",
     "pattern": r"(?i)\bsha1\b", "confidence": "theoretical",
     "rationale": "seed bank: SHA-1 remains deprecated for security use."},
    {"agent": "ROOT", "kind": "intel",
     "label": "sudoers_line", "pattern": r"(?i)^\S+\s+ALL=\(ALL:?ALL?\)\s+",
     "rationale": "seed bank: weak sudoers lines are a privesc lead."},
    {"agent": "LIGHTHOUSE", "kind": "intel",
     "label": "ns_record", "pattern": r"(?i)\bns\s+\S+\.\s*$",
     "rationale": "seed bank: authoritative NS records enrich subdomain work."},
    {"agent": "RAPTOR", "kind": "builtin",
     "tool": "nuclei", "argv_template": "nuclei -u {target} -severity high,critical -silent",
     "purpose": "high-severity template scan", "rationale": "seed bank: focus the web scan."},
    # Workflow playbooks — multi-worker chains gated like any other skill gain.
    {"agent": "EYRIE", "kind": "workflow", "name": "recon-chain",
     "steps": [["EYRIE", "nmap -sV {target}", "service version discovery"],
               ["CARTO", "dnsrecon -d {target} -t std", "dns enumeration"],
               ["SPYGLASS", "whois {target}", "registrant intel"]],
     "rationale": "seed bank: first-pass external recon playbook."},
    {"agent": "MIRROR", "kind": "workflow", "name": "find-secrets-chain",
     "steps": [["MIRROR", "strings {target}", "extract candidate secrets"],
               ["VAULT", "trufflehog filesystem {target}", "credential sweep"],
               ["POCKET", "strings {target}", "mobile artifact sweep"]],
     "rationale": "seed bank: hunt hardcoded secrets across an artifact."},
]


def _candidate_hash(entry: dict) -> str:
    """Stable hash of the candidate's actionable fields (not its rationale)."""
    key = json.dumps({
        "agent": str(entry.get("agent", "")).upper(),
        "kind": entry.get("kind", ""),
        "vuln_class": entry.get("vuln_class", ""),
        "label": entry.get("label", ""),
        "pattern": entry.get("pattern", ""),
        "confidence": entry.get("confidence", ""),
        "tool": entry.get("tool", ""),
        "argv_template": entry.get("argv_template", ""),
        "purpose": entry.get("purpose", ""),
        "name": entry.get("name", ""),
        "steps": json.dumps(entry.get("steps", []), sort_keys=True),
    }, sort_keys=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _read_state(path: Path) -> set[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict):
        return set()
    return set(data.get("applied", []) or [])


def _write_state(path: Path, applied: set[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"applied": sorted(applied)}, indent=2),
                    encoding="utf-8")


def user_candidates(feeds_dir: Path | None = None) -> list[dict]:
    """Candidates from user feed files (``~/.one2one/feeds/*.yaml``)."""
    import yaml
    feeds_dir = feeds_dir or FEEDS_DIR
    out: list[dict] = []
    if not feeds_dir.is_dir():
        return out
    for path in sorted(feeds_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue          # a broken user feed must never break the sync
        for entry in (data.get("candidates") or []):
            if isinstance(entry, dict) and entry.get("agent") and entry.get("kind"):
                entry = {**entry, "from": str(path.name)}
                out.append(entry)
    return out


def all_candidates(include_seed: bool = True,
                   feeds_dir: Path | None = None) -> list[dict]:
    """Seed bank + user feeds, deduplicated by candidate hash."""
    entries = (list(SEED_FEED) if include_seed else []) + user_candidates(feeds_dir)
    seen: set[str] = set()
    out: list[dict] = []
    for e in entries:
        h = _candidate_hash(e)
        if h in seen:
            continue
        seen.add(h)
        out.append(e)
    return out


def _to_patch(entry: dict, evolution):
    """Translate a feed entry into the matching SkillPatch proposal kind."""
    agent = str(entry.get("agent", "")).upper()
    kind = entry.get("kind", "")
    if kind == "signature":
        payload = (entry.get("vuln_class", ""), entry.get("label", ""),
                   entry.get("pattern", ""), entry.get("confidence", ""))
        return evolution.propose(agent, "add-signature", payload,
                                 entry.get("rationale", "skill feed"))
    if kind == "intel":
        payload = (entry.get("label", ""), entry.get("pattern", ""))
        return evolution.propose(agent, "add-intel", payload,
                                 entry.get("rationale", "skill feed"))
    if kind == "builtin":
        payload = (entry.get("tool", ""), entry.get("argv_template", ""),
                   entry.get("purpose", ""))
        return evolution.propose(agent, "add-builtin", payload,
                                 entry.get("rationale", "skill feed"))
    if kind == "workflow":
        payload = (entry.get("name", ""), entry.get("steps", []))
        return evolution.propose(agent, "add-workflow", payload,
                                 entry.get("rationale", "skill feed"))
    return None


def sync(evolution, entries: list[dict] | None = None,
         feed_state_path: Path | None = None) -> dict:
    """Propose + gate every new feed candidate.

    Returns a report: ``{proposed, applied, rejected, already, notes: [...]}``.
    Idempotent — a candidate already in feed-state is skipped unless it changed.
    """
    applied_state = _read_state(feed_state_path or FEED_STATE_FILE)
    entries = entries if entries is not None else all_candidates()
    report: dict = {"proposed": 0, "applied": 0, "rejected": 0,
                    "already": 0, "notes": []}
    for entry in entries:
        h = _candidate_hash(entry)
        if h in applied_state:
            report["already"] += 1
            continue
        patch = _to_patch(entry, evolution)
        if patch is None:
            report["rejected"] += 1
            report["notes"].append(f"unknown feed kind: {entry.get('kind')!r}")
            continue
        report["proposed"] += 1
        approved = evolution.approve(patch)
        if approved.status in ("active", "approved"):
            applied_state.add(h)
            report["applied"] += 1
            report["notes"].append(f"{approved.id} → {approved.status} "
                                   f"({approved.note})")
        else:
            report["rejected"] += 1
            report["notes"].append(f"{patch.id} → {approved.status} "
                                   f"(gate refused)")
    _write_state(feed_state_path, applied_state)
    return report


def _read_state(path: Path) -> set[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return set(data.get("applied", []) or [])


def _write_state(path: Path, applied: set[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"applied": sorted(applied)}, indent=2),
                    encoding="utf-8")


def run(feed_state_path: Path | None = None,
        feeds_dir: Path | None = None) -> dict:
    """Console entry for ``/feed``: build the real evolution stack and sync.

    The active engagement's scope (when one is active) gates scoped mutations;
    otherwise the gate is default-deny for scoped patches and permissive for
    signature/intel/builtin skill gains (those never touch a target).
    """
    from one2one.agents.evolution import Evolution, PatchGate
    from one2one.agents.ledger import LEDGER_FILE
    from one2one.agents.scope import ScopeGate
    from one2one.engagement import active as active_engagement

    state = feed_state_path or FEED_STATE_FILE
    engagement = active_engagement()
    scope = engagement.to_scope() if engagement is not None else ScopeGate().scope
    evo = Evolution(lessons_path=LEDGER_FILE.parent / "lessons.json",
                    gate=PatchGate(scope))
    return sync(evo, all_candidates(include_seed=True, feeds_dir=feeds_dir),
                feed_state_path=state)


def demo() -> None:
    entries = all_candidates()
    print(f"skill-feed: {len(entries)} candidate(s) "
          f"({len(SEED_FEED)} seed, {len(user_candidates())} user)")
    for e in entries:
        print(f"  {e['agent']:<10} {e['kind']:<10} {e.get('label', e.get('tool', ''))}")
    assert all(_candidate_hash(e) for e in entries)


if __name__ == "__main__":
    demo()
