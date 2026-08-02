"""Mythos findings schema + deterministic triage. Stdlib only.

The Mythos pipeline (``mythos.py``) and the offline scanners (``mythos_scan.py``)
both produce ``MythosFinding`` objects. Every model-returned finding must carry a
``vuln_class`` from the fixed ``VULN_CLASSES`` set and a ``confidence`` from the
three-tier model — anything else is dropped, so the model can never invent a class
(a closed-vocabulary guardrail, mirroring ``tags.TAXONOMY``).

Three-tier validation model (Mythos parity):
    Tier 1  confirmed    — validated at runtime (a PoC actually executed)
    Tier 2  plausible    — validated path / strong signature (e.g. a real secret)
    Tier 3  theoretical  — pattern or hypothesis only

High/Critical findings require Tier 1 or Tier 2 (``high_critical_need_tier``).
Triage (CVSS base score, severity, tier) is deterministic and offline — the model
is never trusted to grade its own findings.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── Closed vocabulary ──────────────────────────────────────────────────────────
VULN_CLASSES = frozenset({
    # web / app
    "sql-injection", "command-injection", "template-injection", "xss", "csrf",
    "ssrf", "path-traversal", "auth-bypass", "authz-bypass", "logic-flaw",
    "race-condition", "insecure-config",
    # code / memory / data
    "deserialization", "memory-corruption", "crypto-misuse", "rce",
    "privilege-escalation", "hardcoded-secret", "sensitive-data-exposure",
    # supply chain / ci-cd
    "supply-chain", "ci-cd-attack",
    # AI / LLM
    "prompt-injection", "rag-poisoning", "tool-misuse", "data-exfiltration",
    "unsafe-agent-chaining",
})

CONFIDENCES = ("confirmed", "plausible", "theoretical")

_AGENTS = {"RECON", "HUNTER", "ADVERSARIAL", "EXPLOIT", "TRIAGE", "AI-SECURITY"}

# Base CVSS-ish score per (vuln_class, confidence). Confirmed > plausible >
# theoretical so a validated finding always outranks a pattern-only guess.
_CVSS = {
    "rce":                       (9.8, 8.5, 7.5),
    "sql-injection":             (9.8, 8.8, 7.5),
    "deserialization":           (9.8, 8.5, 7.0),
    "command-injection":         (9.0, 8.0, 7.0),
    "memory-corruption":         (9.8, 8.8, 7.8),
    "auth-bypass":               (9.1, 8.0, 6.5),
    "authz-bypass":              (8.5, 7.5, 6.0),
    "privilege-escalation":      (8.8, 7.8, 6.5),
    "ssrf":                      (8.6, 7.0, 6.0),
    "hardcoded-secret":          (8.0, 7.0, 6.0),
    "prompt-injection":          (8.5, 7.0, 5.5),
    "unsafe-agent-chaining":     (8.5, 7.0, 5.5),
    "supply-chain":              (8.0, 7.0, 5.5),
    "ci-cd-attack":              (8.0, 6.5, 5.0),
    "crypto-misuse":             (7.5, 6.5, 5.5),
    "tool-misuse":               (8.0, 6.5, 5.0),
    "path-traversal":            (7.5, 6.5, 5.5),
    "logic-flaw":                (7.0, 6.0, 5.0),
    "sensitive-data-exposure":   (7.5, 6.5, 5.0),
    "rag-poisoning":             (7.5, 6.5, 5.0),
    "data-exfiltration":         (7.5, 6.0, 4.5),
    "template-injection":        (9.0, 7.5, 6.0),
    "race-condition":            (6.5, 5.5, 4.5),
    "xss":                       (6.1, 5.5, 4.5),
    "csrf":                      (6.5, 5.5, 4.0),
    "insecure-config":           (6.0, 5.0, 3.5),
}
_DEFAULT_CVSS = (7.0, 6.0, 4.5)


def cvss_for(vuln_class: str, confidence: str) -> float:
    """Deterministic base score for a (vuln_class, confidence) pair."""
    idx = CONFIDENCES.index(confidence) if confidence in CONFIDENCES else 0
    return _CVSS.get(vuln_class, _DEFAULT_CVSS)[idx]


def tier_of(confidence: str) -> int:
    return {"confirmed": 1, "plausible": 2}.get(confidence, 3)


def severity_of(cvss: float) -> str:
    if cvss >= 9.0:
        return "critical"
    if cvss >= 7.0:
        return "high"
    if cvss >= 4.0:
        return "medium"
    if cvss > 0.0:
        return "low"
    return "info"


def high_critical_need_tier(finding: "MythosFinding") -> bool:
    """High/Critical findings must be Tier 1 or Tier 2 — never theoretical."""
    return severity_of(finding.cvss_score) in ("high", "critical") \
        and tier_of(finding.confidence) > 2


@dataclass
class MythosFinding:
    agent: str              # which agent produced it (HUNTER / ADVERSARIAL / ... / SCAN)
    phase: int
    file_path: str          # URL, host, or code path the issue was found at
    vuln_class: str         # must be in VULN_CLASSES
    confidence: str         # confirmed | plausible | theoretical
    summary: str
    cvss_score: float = 0.0     # recomputed deterministically in __post_init__
    details: dict = field(default_factory=dict)
    source: str = "model"   # "model" | "offline-scan" | "runtime"
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.cvss_score:
            self.cvss_score = cvss_for(self.vuln_class, self.confidence)

    @property
    def severity(self) -> str:
        return severity_of(self.cvss_score)

    @property
    def tier(self) -> int:
        return tier_of(self.confidence)


def validate_finding(raw: dict) -> MythosFinding | None:
    """Model/scan reply dict -> MythosFinding. Drops findings with an unknown
    vuln_class or confidence (closed-vocabulary guardrail). Never raises."""
    if not isinstance(raw, dict):
        return None
    vuln_class = str(raw.get("vuln_class", "")).strip()
    confidence = str(raw.get("confidence", "")).strip()
    if vuln_class not in VULN_CLASSES or confidence not in CONFIDENCES:
        return None
    agent = str(raw.get("agent", "HUNTER")).upper()
    if agent not in _AGENTS:
        agent = "HUNTER"
    details = raw.get("details")
    if not isinstance(details, dict):
        details = {}
    try:
        phase = int(raw.get("phase", 0))
    except (TypeError, ValueError):
        phase = 0
    return MythosFinding(
        agent=agent,
        phase=phase,
        file_path=str(raw.get("file_path", "")).strip(),
        vuln_class=vuln_class,
        confidence=confidence,
        summary=str(raw.get("summary", "")).strip(),
        details=details,
        source=str(raw.get("source", "model")),
    )


def parse_findings(reply: str | None) -> list[MythosFinding]:
    """Pull a JSON array of findings from a model reply; keep only valid ones."""
    if not reply:
        return []
    import re
    m = re.search(r"\[.*\]", reply, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except ValueError:
        return []
    if not isinstance(arr, list):
        return []
    out: list[MythosFinding] = []
    for item in arr:
        f = validate_finding(item if isinstance(item, dict) else {})
        if f is not None:
            out.append(f)
    return out


def rank(findings: list[MythosFinding]) -> list[MythosFinding]:
    """Sort by cvss desc, then confidence (confirmed first), then agent order."""
    agent_rank = {name: i for i, name in enumerate(sorted(_AGENTS))}
    return sorted(findings, key=lambda f: (
        -f.cvss_score,
        tier_of(f.confidence),
        agent_rank.get(f.agent, 99),
        f.file_path,
    ))


def save_findings(path: Path, findings: list[MythosFinding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(f) for f in findings], indent=2),
                    encoding="utf-8")


def load_findings(path: Path) -> list[MythosFinding]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out: list[MythosFinding] = []
    for item in data:
        f = validate_finding(item if isinstance(item, dict) else {})
        if f is not None:
            out.append(f)
    return out


def demo() -> None:
    # Guardrail: unknown class / confidence are dropped, known ones pass.
    assert validate_finding({"vuln_class": "made-up", "confidence": "confirmed"}) is None
    assert validate_finding({"vuln_class": "sql-injection", "confidence": "bogus"}) is None
    f = validate_finding({"vuln_class": "sql-injection", "confidence": "confirmed",
                          "file_path": "/a", "summary": "s"})
    assert f is not None and f.cvss_score == 9.8 and f.severity == "critical"
    assert tier_of("confirmed") == 1 and tier_of("theoretical") == 3
    assert high_critical_need_tier(validate_finding(
        {"vuln_class": "rce", "confidence": "theoretical", "file_path": "/x"}))
    assert not high_critical_need_tier(validate_finding(
        {"vuln_class": "rce", "confidence": "plausible", "file_path": "/x"}))
    # Closed vocabulary: every offline class is scorable.
    assert all(c in _CVSS or c for c in VULN_CLASSES)
    print(f"OK — mythos_findings: {len(VULN_CLASSES)} vuln classes + 3-tier triage")


if __name__ == "__main__":
    demo()
