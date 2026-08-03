"""The approved One2One Agent Stack roster — 37 agents across 4 tiers.

Pure data + lookups sourced from ``docs/AGENT_STACK.md``: callsigns, wings,
tiers and responsibilities. No behavior lives here — the command layer reads
this roster to route work and build the command chain.

Tiers: 1 worker · 2 wing lead · 3 operator · 4 supreme
Wings: VANGUARD (Intel) · ONSLAUGHT (Offense) · TRIBUNAL (Truth)
"""
from __future__ import annotations

SUPREME = "APEX"
OPERATOR = "COMMANDER"

VANGUARD = "VANGUARD"
ONSLAUGHT = "ONSLAUGHT"
TRIBUNAL = "TRIBUNAL"

_WING_NAMES = {
    VANGUARD: "Intel Command",
    ONSLAUGHT: "Offense Command",
    TRIBUNAL: "Truth Command",
}

_INTEL = [
    "EYRIE", "SENTRY", "SPYGLASS", "VULTURE", "LIGHTHOUSE",
    "CARTO", "NETMINE", "WHISPER", "ORACLE", "MIRROR",
]

_OFFENSE = [
    "RAPTOR", "VIPER", "FIDDLER", "SPIDER", "GHOST", "JAMMER",
    "GATE", "TUNNEL", "SHATTER", "VAULT", "MIMIC", "IMPACT",
    "RAZOR", "SCALPEL", "ROOT", "MARIONETTE",
]

_TRUTH = [
    "SMOKE", "POCKET", "NIMBUS", "HONEY", "SAGE", "CHRONICLE",
]

WORKERS = _INTEL + _OFFENSE + _TRUTH
WINGS = (VANGUARD, ONSLAUGHT, TRIBUNAL)

# callsign -> (wing, tier, responsibility)
_AGENTS: dict[str, tuple[str, int, str]] = {
    SUPREME: ("", 4, "Supreme agent and user-facing assistant; owns ethics and "
                     "scope, approves every skill mutation, reports to nobody."),
    OPERATOR: ("", 3, "Mission governor; routes work across wings, enforces "
                      "sequencing and parallelism, kills wasted effort, reports "
                      "to APEX."),
    VANGUARD: (VANGUARD, 2, "Intel Command — supervises all recon/OSINT/analysis "
                            "workers; keeps the battle picture live."),
    ONSLAUGHT: (ONSLAUGHT, 2, "Offense Command — supervises all web/network/"
                              "exploit/post-ex workers; sequences the strike."),
    TRIBUNAL: (TRIBUNAL, 2, "Truth Command — supervises validation, AI, mobile/"
                            "cloud audit and reporting; owns the verdict."),
    # ── Intel wing (10) ────────────────────────────────────────────────────
    "EYRIE":     (VANGUARD, 1, "Network & attack-surface recon"),
    "SENTRY":    (VANGUARD, 1, "Port/service discovery, banner grab"),
    "SPYGLASS":  (VANGUARD, 1, "Passive OSINT & footprinting"),
    "VULTURE":   (VANGUARD, 1, "Deep-web/leak & metadata harvesting"),
    "LIGHTHOUSE":(VANGUARD, 1, "DNS/subdomain enumeration"),
    "CARTO":     (VANGUARD, 1, "Topology & reachability mapping"),
    "NETMINE":   (VANGUARD, 1, "Packet capture & traffic analysis"),
    "WHISPER":   (VANGUARD, 1, "Steganography & covert-channel probes"),
    "ORACLE":    (VANGUARD, 1, "Crypto weakness & weak-key detection"),
    "MIRROR":    (VANGUARD, 1, "Evidence & artifact harvesting"),
    # ── Offense wing (16) ───────────────────────────────────────────────────
    "RAPTOR":    (ONSLAUGHT, 1, "Web-app vulnerability scanner"),
    "VIPER":     (ONSLAUGHT, 1, "SQL injection specialist"),
    "FIDDLER":   (ONSLAUGHT, 1, "Request tampering & auth logic testing"),
    "SPIDER":    (ONSLAUGHT, 1, "Content discovery & crawling"),
    "GHOST":     (ONSLAUGHT, 1, "Session/auth bypass, impersonation"),
    "JAMMER":    (ONSLAUGHT, 1, "Wireless/BT/RF audit"),
    "GATE":      (ONSLAUGHT, 1, "Firewall/ACL & edge probing"),
    "TUNNEL":    (ONSLAUGHT, 1, "Pivoting & lateral-movement pathing"),
    "SHATTER":   (ONSLAUGHT, 1, "Password & hash cracking"),
    "VAULT":     (ONSLAUGHT, 1, "Credential/token hunting"),
    "MIMIC":     (ONSLAUGHT, 1, "Payload crafting & phishing lures"),
    "IMPACT":    (ONSLAUGHT, 1, "Exploit development & weaponization"),
    "RAZOR":     (ONSLAUGHT, 1, "Payload generation & obfuscation"),
    "SCALPEL":   (ONSLAUGHT, 1, "Reverse engineering & binary analysis"),
    "ROOT":      (ONSLAUGHT, 1, "Privilege escalation & post-exploitation"),
    "MARIONETTE":(ONSLAUGHT, 1, "Persistence & C2 choreography"),
    # ── Truth wing (6) ──────────────────────────────────────────────────────
    "SMOKE":     (TRIBUNAL, 1, "Evasion & AV-bypass analysis"),
    "POCKET":    (TRIBUNAL, 1, "Mobile/Android/iOS audit"),
    "NIMBUS":    (TRIBUNAL, 1, "Cloud & misconfiguration audit"),
    "HONEY":     (TRIBUNAL, 1, "Social engineering & phishing campaigns"),
    "SAGE":      (TRIBUNAL, 1, "Plain-English → tool + exact command (AI skill planner)"),
    "CHRONICLE": (TRIBUNAL, 1, "Findings fusion, evidence & report authoring"),
}

assert len(_AGENTS) == 37, len(_AGENTS)

AGENTS = _AGENTS  # public view: name -> (wing, tier, responsibility)


def responsibility(name: str) -> str:
    return _AGENTS[name][2]


def tier_of(name: str) -> int:
    return _AGENTS[name][1]


def wing_of(name: str) -> str:
    return _AGENTS[name][0]


def wing_name(wing: str) -> str:
    return _WING_NAMES.get(wing, wing)


def is_worker(name: str) -> bool:
    return _AGENTS.get(name, ("", 0, ""))[1] == 1


def workers_in(wing: str) -> list[str]:
    return [w for w in WORKERS if wing_of(w) == wing]


def chain_for(worker: str) -> list[str]:
    """The fixed command chain: worker → wing lead → operator → supreme."""
    wing = wing_of(worker)
    return [worker, wing, OPERATOR, SUPREME]


def roster() -> list[dict]:
    """All 37 agents as dicts (callsign, tier, wing, responsibility)."""
    out = []
    for name, (wing, tier, resp) in _AGENTS.items():
        out.append({
            "name": name,
            "tier": tier,
            "wing": wing,
            "wing_name": wing_name(wing),
            "responsibility": resp,
        })
    return out
