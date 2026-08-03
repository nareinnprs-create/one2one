"""Wing leads — the three supervisors over the 32 workers (P1).

Each wing lead owns its command and performs the brutal self-review the stack
is named for: worker findings that are invalid, duplicated, or High/Critical
without a runtime-validating tier are rejected on sight. Only what survives is
escalated to COMMANDER/APEX. The honesty contract from the stack spec holds:
a wing reporting "no findings" means "proven clean", not "didn't look".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache

from one2one.agents import roster
from one2one.mythos_findings import (
    MythosFinding, high_critical_need_tier, validate_finding,
)

WING_LEADS = (roster.VANGUARD, roster.ONSLAUGHT, roster.TRIBUNAL)


@dataclass
class WingReport:
    lead: str
    wing: str
    accepted: list = field(default_factory=list)      # list[MythosFinding]
    rejected: list = field(default_factory=list)      # list[dict]
    note: str = ""
    verdict: str = ""


class WingLead:
    """Supervisor of one wing: receives worker reports, reviews them brutally."""

    def __init__(self, name: str) -> None:
        self.name = name.upper()
        self.wing = self.name
        self.workers = roster.workers_in(self.wing)
        self.responsibility = roster.responsibility(self.name)

    def supervise(self, mission, report, stream=None) -> WingReport:
        """Review a worker report; escalate only what survives.

        ``stream`` is an optional callback invoked with each accepted finding as
        it passes review — the uplink side of the sync protocol (workers stream
        findings up through their wing lead).
        """
        accepted: list[MythosFinding] = []
        rejected: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for finding in self._as_findings(report):
            key = (finding.file_path, finding.vuln_class)
            if key in seen:
                rejected.append({
                    "file_path": finding.file_path,
                    "vuln_class": finding.vuln_class,
                    "confidence": finding.confidence,
                    "reason": "duplicate (same target, same class)",
                })
                continue
            seen.add(key)
            if high_critical_need_tier(finding):
                rejected.append({
                    "file_path": finding.file_path,
                    "vuln_class": finding.vuln_class,
                    "confidence": finding.confidence,
                    "reason": "high/critical finding must be tier 1-2 "
                              "(validated), not theoretical",
                })
                continue
            accepted.append(finding)
            if stream is not None:
                stream(finding)

        verdict = (
            "clean — nothing survived brutal review"
            if not accepted else
            f"{len(accepted)} finding(s) escalated to COMMANDER"
        )
        note = report.note if report is not None else "no worker report"
        if rejected:
            note += f" · {len(rejected)} rejected"
        return WingReport(lead=self.name, wing=self.wing, accepted=accepted,
                          rejected=rejected, note=note, verdict=verdict)

    @staticmethod
    def _as_findings(report) -> list[MythosFinding]:
        out: list[MythosFinding] = []
        for item in getattr(report, "findings", None) or []:
            if isinstance(item, MythosFinding):
                out.append(item)
            elif isinstance(item, dict):
                f = validate_finding(item)
                if f is not None:
                    out.append(f)
        return out


@lru_cache(maxsize=3)
def wing_lead_for(wing: str) -> WingLead:
    """The lead instance for a wing callsign (VANGUARD/ONSLAUGHT/TRIBUNAL)."""
    return WingLead(wing)


def wing_report_dict(report: WingReport) -> dict:
    """Serialisable view of a WingReport (findings as dicts)."""
    data = asdict(report)
    data["accepted"] = [asdict(f) for f in report.accepted]
    data["rejected"] = [dict(r) for r in report.rejected]
    return data
