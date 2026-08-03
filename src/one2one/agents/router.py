"""Intent router — maps plain-English missions to the right worker.

A fixed keyword table scores the mission text; the longest matching token wins
(more specific beats more generic). No match routes to SAGE, the AI skill
planner, which is the stack's generic fallback for plain-English requests.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from one2one.agents import roster

DEFAULT_WORKER = "SAGE"

_INTENT: dict[str, str] = {
    # Intel wing
    "attack surface": "EYRIE", "recon": "EYRIE", "enumerate": "EYRIE",
    "footprint": "SPYGLASS", "osint": "SPYGLASS", "whois": "SPYGLASS",
    "dns": "LIGHTHOUSE", "subdomain": "LIGHTHOUSE", "domain": "LIGHTHOUSE",
    "port": "SENTRY", "service scan": "SENTRY", "banner": "SENTRY",
    "topology": "CARTO", "reachability": "CARTO",
    "packet": "NETMINE", "capture": "NETMINE", "traffic": "NETMINE", "pcap": "NETMINE",
    "stegano": "WHISPER", "steganography": "WHISPER", "covert": "WHISPER",
    "crypto": "ORACLE", "cipher": "ORACLE", "tls": "ORACLE", "weak key": "ORACLE",
    "artifact": "MIRROR", "evidence": "MIRROR", "forensic": "MIRROR",
    # Offense wing
    "web": "RAPTOR", "xss": "RAPTOR", "csrf": "RAPTOR", "ssrf": "RAPTOR",
    "scan": "RAPTOR", "vulnerability": "RAPTOR",
    "sqli": "VIPER", "sql": "VIPER", "injection": "VIPER",
    "fuzz": "FIDDLER", "tamper": "FIDDLER", "logic": "FIDDLER",
    "crawl": "SPIDER", "content discovery": "SPIDER", "directory": "SPIDER",
    "session": "GHOST", "auth": "GHOST", "bypass": "GHOST", "impersonation": "GHOST",
    "wifi": "JAMMER", "wireless": "JAMMER", "bluetooth": "JAMMER", "rf": "JAMMER",
    "firewall": "GATE", "acl": "GATE", "edge": "GATE",
    "pivot": "TUNNEL", "lateral": "TUNNEL", "movement": "TUNNEL",
    "password": "SHATTER", "hash": "SHATTER", "crack": "SHATTER", "brute force": "SHATTER",
    "credential": "VAULT", "token": "VAULT", "secret hunt": "VAULT",
    "phish": "HONEY", "phishing": "HONEY", "social engineering": "HONEY",
    "payload": "MIMIC", "lure": "MIMIC", "maldoc": "MIMIC",
    "exploit": "IMPACT", "weapon": "IMPACT", "poc": "IMPACT", "pwn": "IMPACT",
    "obfuscate": "RAZOR", "obfuscation": "RAZOR", "evasion": "SMOKE",
    "reverse": "SCALPEL", "binary": "SCALPEL", "malware": "SCALPEL", "disassemble": "SCALPEL",
    "privesc": "ROOT", "privilege": "ROOT", "escalation": "ROOT",
    "persist": "MARIONETTE", "c2": "MARIONETTE", "backdoor": "MARIONETTE", "implant": "MARIONETTE",
    # Truth wing
    "mobile": "POCKET", "android": "POCKET", "ios": "POCKET",
    "cloud": "NIMBUS", "aws": "NIMBUS", "s3": "NIMBUS", "misconfig": "NIMBUS",
    "report": "CHRONICLE", "summarize": "CHRONICLE", "write-up": "CHRONICLE",
    "plan": "SAGE", "tool": "SAGE", "command": "SAGE", "recommend": "SAGE",
}

# Longer tokens are more specific; break ties toward the more common term.
_MAX_TOKEN = max(len(t) for t in _INTENT)


@dataclass
class RoutingDecision:
    intent: str
    worker: str
    wing: str
    operator: str
    supreme: str
    chain: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    confidence: float = 0.0


def route(text: str) -> RoutingDecision:
    """Decide which worker owns a mission text, plus its command chain."""
    intent = (text or "").strip().lower()
    best_worker: str | None = None
    best_score = 0
    matched: list[str] = []
    for token, worker in _INTENT.items():
        if token in intent:
            matched.append(token)
            if len(token) > best_score:
                best_score = len(token)
                best_worker = worker
    worker = best_worker or DEFAULT_WORKER
    wing = roster.wing_of(worker)
    confidence = min(1.0, best_score / _MAX_TOKEN)
    return RoutingDecision(
        intent=intent,
        worker=worker,
        wing=wing,
        operator=roster.OPERATOR,
        supreme=roster.SUPREME,
        chain=roster.chain_for(worker),
        matched=matched,
        confidence=confidence,
    )
