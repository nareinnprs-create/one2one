"""Worker modules — the 32 Tier-1 agents over the tool catalog (P2/P3).

Each worker is a small deterministic agent: it owns a set of catalog
tags/tools, plans a target-specific step list (catalog ``usage`` commands + a
builtin fallback), executes steps best-effort (list-form subprocess, missing
tools skipped, never raises), and analyzes the captured output against
closed-vocabulary signatures. Findings are ``MythosFinding`` objects produced
only from real evidence; everything else is recorded as ``intel`` — a wing
reporting nothing means proven clean, not "didn't look".

P2 shipped the 10 Intel-wing modules (VANGUARD); P3 ships the 16 Offense
(ONSLAUGHT) and 6 Truth (TRIBUNAL) modules plus parallel dispatch.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache

from one2one.agents import roster
from one2one.agents.command import WorkerReport
from one2one.mythos_findings import MythosFinding

_STEP_TIMEOUT = 120
_KIND_PREFIXES = ("code:", "binary:")


def _split(cmd: str) -> list:
    """Split a command line for list-form subprocess, Windows-safe.

    ``shlex.split`` defaults to POSIX quoting rules, which swallow backslashes
    in Windows paths (``C:\\lab\\file`` becomes ``Clabfile``). On ``nt`` we keep
    the literal args so local ``code:``/``binary:`` targets survive untouched.
    """
    return shlex.split(cmd, posix=(os.name != "nt"))


def _strip_kind(target: str) -> str:
    """Drop a ``code:``/``binary:`` scope prefix for command building."""
    t = (target or "").strip()
    for prefix in _KIND_PREFIXES:
        if t.lower().startswith(prefix):
            return t[len(prefix):]
    return t


@dataclass
class Step:
    tool: str
    argv: list
    purpose: str
    source: str = "builtin"


@dataclass
class RunResult:
    step: Step
    ok: bool
    stdout: str = ""
    error: str = ""


def _default_runner(argv: list, timeout: int) -> str:
    proc = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False)
    return proc.stdout or ""


@lru_cache(maxsize=1)
def _load_catalog():
    from one2one.registry import load
    try:
        return load()
    except Exception:
        return None


def _fill(template: str, target: str) -> str:
    return (template.replace("{target}", target).replace("<target>", target)
                    .replace("{host}", target).replace("<host>", target))


class Worker:
    """Base for all 32 Tier-1 agents: plan → execute → analyze, offline."""

    CALLSIGN = ""
    TITLE = ""
    TAGS: tuple = ()
    CATALOG_KEYS: tuple = ()            # title substrings that match this worker
    BUILTIN_STEPS: tuple = ()           # (tool, argv_template, purpose)
    SIGNATURES: tuple = ()              # (vuln_class, label, regex, confidence)
    INTEL_PATTERNS: tuple = ()          # (label, regex)

    def __init__(self, runner=None, catalog=None) -> None:
        self.runner = runner or _default_runner
        self._catalog = catalog if catalog is not None else _load_catalog()
        self.responsibility = roster.responsibility(self.CALLSIGN)

    # ── planning ───────────────────────────────────────────────────────────────
    def catalog_steps(self, target: str) -> list[Step]:
        steps: list[Step] = []
        if self._catalog is None:
            return steps
        for cat in self._catalog.categories:
            for tool in getattr(cat, "tools", None) or []:
                tags = set(getattr(tool, "TAGS", None) or [])
                title = str(getattr(tool, "TITLE", "")).lower()
                if not (tags & set(self.TAGS)) and not any(
                        k in title for k in self.CATALOG_KEYS):
                    continue
                cmd, purpose = self._first_command(tool)
                if not cmd:
                    continue
                argv = _split(_fill(cmd, target))
                steps.append(Step(tool=tool.TITLE, argv=argv,
                                  purpose=purpose, source="catalog"))
        return steps

    def builtin_steps(self, target: str) -> list[Step]:
        return [Step(tool=t, argv=_split(_fill(tmpl, target)),
                     purpose=p, source="builtin")
                for t, tmpl, p in self.BUILTIN_STEPS]

    def plan(self, target: str) -> list[Step]:
        seen: set[tuple] = set()
        steps: list[Step] = []
        for step in self.catalog_steps(target) + self.builtin_steps(target):
            key = tuple(step.argv)
            if key in seen:
                continue
            seen.add(key)
            steps.append(step)
        return steps

    @staticmethod
    def _first_command(tool) -> tuple[str, str]:
        usage = getattr(tool, "USAGE", None) or []
        if usage:
            task, cmd = usage[0]
            return str(cmd), str(task)
        run = getattr(tool, "RUN_COMMANDS", None) or []
        if run:
            return str(run[0]), "catalog run"
        return "", ""

    # ── execution ──────────────────────────────────────────────────────────────
    def execute(self, steps: list[Step]) -> list[RunResult]:
        results: list[RunResult] = []
        for step in steps:
            try:
                out = self.runner(step.argv, _STEP_TIMEOUT)
                results.append(RunResult(step=step, ok=True, stdout=out or ""))
            except (subprocess.TimeoutExpired, OSError) as exc:
                results.append(RunResult(step=step, ok=False,
                                         error=str(exc) or type(exc).__name__))
        return results

    # ── analysis ───────────────────────────────────────────────────────────────
    def analyze(self, target: str, results: list[RunResult]) -> WorkerReport:
        combined = "\n".join(r.stdout for r in results if r.ok)
        intel: list[dict] = []
        for label, pattern in self.INTEL_PATTERNS:
            for m in re.finditer(pattern, combined, re.IGNORECASE):
                intel.append({"label": label, "value": m.group(0).strip()})

        findings: list[MythosFinding] = []
        seen: set[tuple] = set()
        for vuln_class, label, pattern, confidence in self.SIGNATURES:
            for m in re.finditer(pattern, combined, re.IGNORECASE):
                key = (target, vuln_class, label)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(MythosFinding(
                    agent=self.CALLSIGN, phase=2, file_path=target,
                    vuln_class=vuln_class, confidence=confidence, summary=label))

        ok_count = sum(1 for r in results if r.ok)
        note = (f"{len(self.plan(target))} steps planned, {ok_count} ran; "
                f"{len(findings)} finding(s), {len(intel)} intel item(s)")
        return WorkerReport(worker=self.CALLSIGN, executed=ok_count > 0,
                            note=note, findings=findings, intel=intel)

    def run(self, mission) -> WorkerReport:
        target = (mission.target or "").strip()
        if not target:
            return WorkerReport(self.CALLSIGN, False,
                                f"{self.CALLSIGN}: no target — nothing ran")
        path = _strip_kind(target)
        return self.analyze(path, self.execute(self.plan(path)))


# ── The 10 Intel workers ───────────────────────────────────────────────────────
IntelWorker = Worker  # P2-era alias: the base is the shared worker machinery.

class EyrieWorker(Worker):
    CALLSIGN = "EYRIE"
    TITLE = "Network & attack-surface recon"
    TAGS = ("recon", "scanner", "network")
    CATALOG_KEYS = ("nmap", "naabu", "recon")
    BUILTIN_STEPS = (
        ("nmap", "nmap -sn {target}", "host discovery (ping sweep)"),
        ("nmap", "nmap -F {target}", "common open ports"),
    )
    INTEL_PATTERNS = (
        ("host_up", r"Nmap scan report for (\S+)"),
        ("open_port", r"(\d+)/tcp\s+open\s+(\S+)"),
    )


class SentryWorker(Worker):
    CALLSIGN = "SENTRY"
    TITLE = "Port/service discovery, banner grab"
    TAGS = ("port-scan", "scanner", "network")
    CATALOG_KEYS = ("nmap", "naabu", "masscan")
    BUILTIN_STEPS = (
        ("nmap", "nmap -sV -Pn {target}", "service + version detection"),
    )
    SIGNATURES = (
        ("insecure-config", "Telnet (23) open — cleartext",
         r"\b23/tcp\s+open\s+telnet\b", "plausible"),
        ("insecure-config", "FTP (21) open — cleartext",
         r"\b21/tcp\s+open\s+ftp\b", "plausible"),
        ("insecure-config", "SNMP (161/udp) exposed",
         r"\b161/udp\s+open\b", "plausible"),
    )
    INTEL_PATTERNS = (
        ("open_port", r"(\d+)/(tcp|udp)\s+open\s+(\S+)"),
    )


class SpyglassWorker(Worker):
    CALLSIGN = "SPYGLASS"
    TITLE = "Passive OSINT & footprinting"
    TAGS = ("osint", "lookup", "online-service")
    CATALOG_KEYS = ("whois", "harvester", "spiderfoot", "osint")
    BUILTIN_STEPS = (
        ("whois", "whois {target}", "WHOIS footprint"),
    )
    INTEL_PATTERNS = (
        ("email", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        ("registrar", r"(?i)^\s*registrar:\s*(.+)$"),
    )


class VultureWorker(Worker):
    CALLSIGN = "VULTURE"
    TITLE = "Deep-web/leak & metadata harvesting"
    TAGS = ("osint", "metadata", "document", "pdf-extraction")
    CATALOG_KEYS = ("exiftool", "metadata", "metagoofil")
    BUILTIN_STEPS = ()
    INTEL_PATTERNS = (
        ("metadata", r"(?i)^([a-z0-9][a-z0-9 ]{0,30}):\s*(.+)$"),
    )


class LighthouseWorker(Worker):
    CALLSIGN = "LIGHTHOUSE"
    TITLE = "DNS/subdomain enumeration"
    TAGS = ("dns", "subdomain-enum", "enumeration")
    CATALOG_KEYS = ("dnsx", "subfinder", "dns", "dig", "nslookup")
    BUILTIN_STEPS = (
        ("dig", "dig +short any {target}", "pull DNS records"),
    )
    INTEL_PATTERNS = (
        ("host", r"(?i)\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b"),
    )


class CartoWorker(Worker):
    CALLSIGN = "CARTO"
    TITLE = "Topology & reachability mapping"
    TAGS = ("network", "enumeration", "recon")
    CATALOG_KEYS = ("traceroute", "mtr", "nmap")
    BUILTIN_STEPS = (
        ("traceroute", "traceroute -n {target}", "route to target"),
    )
    INTEL_PATTERNS = (
        ("hop", r"^\s*\d+\s+(\S+)"),
    )


class NetmineWorker(Worker):
    CALLSIGN = "NETMINE"
    TITLE = "Packet capture & traffic analysis"
    TAGS = ("pcap", "sniffing", "network")
    CATALOG_KEYS = ("tcpdump", "tshark", "wireshark")
    BUILTIN_STEPS = (
        ("tcpdump", "tcpdump -c 100 -nn", "capture 100 packets"),
    )
    SIGNATURES = (
        ("sensitive-data-exposure", "cleartext Basic auth in capture",
         r"(?i)authorization:\s*basic", "plausible"),
        ("sensitive-data-exposure", "plaintext credential in capture",
         r"(?i)\b(password|passwd|pwd)\s*=\s*\S+", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("proto", r"(?i)\b(tcp|udp)\s+0x[0-9a-f]{2}\b"),
    )


class WhisperWorker(Worker):
    CALLSIGN = "WHISPER"
    TITLE = "Steganography & covert-channel probes"
    TAGS = ("steganography", "image", "binary")
    CATALOG_KEYS = ("steghide", "zsteg", "steg")
    BUILTIN_STEPS = ()
    INTEL_PATTERNS = (
        ("embedded", r"(?i)\bembedded\s+file\b"),
    )


class OracleWorker(Worker):
    CALLSIGN = "ORACLE"
    TITLE = "Crypto weakness & weak-key detection"
    TAGS = ("recon", "scanner", "network")
    CATALOG_KEYS = ("ssl", "tls", "cipher", "sslyze")
    BUILTIN_STEPS = (
        ("openssl", "openssl s_client -connect {target}:443 -brief",
         "probe TLS ciphers"),
    )
    SIGNATURES = (
        ("crypto-misuse", "RC4 cipher offered", r"(?i)rc4", "plausible"),
        ("crypto-misuse", "SSLv3 enabled", r"(?i)sslv3", "plausible"),
        ("crypto-misuse", "TLSv1.0 enabled", r"(?i)tlsv1\b", "plausible"),
        ("crypto-misuse", "3DES cipher offered", r"(?i)3des", "plausible"),
    )
    INTEL_PATTERNS = (
        ("cipher", r"(?i)(cipher\s*[:=]\s*[^,;\s]+)"),
    )


class MirrorWorker(Worker):
    CALLSIGN = "MIRROR"
    TITLE = "Evidence & artifact harvesting"
    TAGS = ("forensics", "git-secrets", "reporting")
    CATALOG_KEYS = ("strings", "trufflehog", "gitleaks", "forensic")
    BUILTIN_STEPS = (
        ("strings", "strings {target}", "scan for printable evidence"),
    )
    SIGNATURES = (
        ("hardcoded-secret", "AWS access key", r"\bAKIA[0-9A-Z]{16}\b", "plausible"),
        ("hardcoded-secret", "private key block",
         r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----", "plausible"),
        ("hardcoded-secret", "GitHub token", r"\bghp_[A-Za-z0-9]{36}\b", "plausible"),
        ("hardcoded-secret", "API key literal",
         r"(?i)\b(?:api[_-]?key|secret|token)\s*[=:]\s*['\"]?[A-Za-z0-9]{16,}",
         "theoretical"),
    )


# ── The 16 Offense workers (ONSLAUGHT) ────────────────────────────────────────

class RaptorWorker(Worker):
    CALLSIGN = "RAPTOR"
    TITLE = "Web-app vulnerability scanner"
    TAGS = ("web", "vuln-scan", "scanner")
    CATALOG_KEYS = ("nuclei", "nikto", "skipfish", "zap", "wapiti")
    BUILTIN_STEPS = (
        ("nuclei", "nuclei -u {target} -silent", "default template scan"),
    )
    SIGNATURES = (
        ("insecure-config", "server banner disclosed",
         r"(?i)^server:\s*\S+", "plausible"),
        ("xss", "reflected payload echoed back",
         r"(?i)(<script[^>]*>[^<]*</script>)", "theoretical"),
        ("insecure-config", "directory listing exposed",
         r"(?i)index of /", "plausible"),
    )
    INTEL_PATTERNS = (
        ("url", r"https?://[^\s\"']+"),
    )


class ViperWorker(Worker):
    CALLSIGN = "VIPER"
    TITLE = "SQL injection specialist"
    TAGS = ("sql-injection", "web", "scanner")
    CATALOG_KEYS = ("sqlmap", "ghauri", "sqlscan", "nosqlmap")
    BUILTIN_STEPS = (
        ("sqlmap", "sqlmap -u {target} --batch", "auto-detect SQLi"),
    )
    SIGNATURES = (
        ("sql-injection", "database error string exposed",
         r"(?i)(you have an error in your sql|sqlsyntaxerror|"
         r"unclosed quotation mark|mysql_fetch|ora-[0-9]{5})", "plausible"),
        ("sql-injection", "blind boolean probe reflects",
         r"(?i)\b(?:or|and)\s+1\s*=\s*1\b", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("dbms", r"(?i)\b(mysql|mariadb|postgresql|postgres|"
                 r"microsoft sql server|oracle database)\b"),
    )


class FiddlerWorker(Worker):
    CALLSIGN = "FIDDLER"
    TITLE = "Request tampering & auth logic testing"
    TAGS = ("web", "api", "fuzzing")
    CATALOG_KEYS = ("ffuf", "arjun", "mitmproxy", "burp", "zap")
    BUILTIN_STEPS = (
        ("ffuf", "ffuf -u {target}/FUZZ -w wordlist.txt -mc 200",
         "fuzz endpoints"),
    )
    SIGNATURES = (
        ("logic-flaw", "privilege/price parameter exposed to tamper",
         r"(?i)\b(role|price|admin|isadmin|privilege)\s*[=:]\s*\S+",
         "theoretical"),
    )
    INTEL_PATTERNS = (
        ("endpoint", r"(?i)\b(?:get|post|put|delete)\s+/\S+"),
    )


class SpiderWorker(Worker):
    CALLSIGN = "SPIDER"
    TITLE = "Content discovery & crawling"
    TAGS = ("crawler", "web", "enumeration")
    CATALOG_KEYS = ("gobuster", "dirsearch", "dirb", "feroxbuster", "katana")
    BUILTIN_STEPS = (
        ("gobuster", "gobuster dir -u {target} -w wordlist.txt",
         "directory brute force"),
    )
    SIGNATURES = (
        ("sensitive-data-exposure", "sensitive path reachable",
         r"(?i)/(\S*)(admin|backup|config|\.env|\.git|database|private)/?",
         "theoretical"),
        ("insecure-config", "directory listing exposed",
         r"(?i)index of /", "plausible"),
    )
    INTEL_PATTERNS = (
        ("discovered_path", r"(?i)\[?[0-9]{3}\]?\s*/\S+"),
    )


class GhostWorker(Worker):
    CALLSIGN = "GHOST"
    TITLE = "Session/auth bypass, impersonation"
    TAGS = ("web", "credentials", "api")
    CATALOG_KEYS = ("cookie", "session", "burp", "evilginx")
    BUILTIN_STEPS = ()
    SIGNATURES = (
        ("auth-bypass", "short/predictable session token",
         r"(?i)\b(?:session|sessionid|token)\s*[=:]\s*['\"]?[a-z0-9]{1,8}\b",
         "theoretical"),
    )
    INTEL_PATTERNS = (
        ("session", r"(?i)\b(?:session|sid|token)\s*[=:]\s*\S+"),
    )


class JammerWorker(Worker):
    CALLSIGN = "JAMMER"
    TITLE = "Wireless/BT/RF audit"
    TAGS = ("wireless", "sniffing", "recon")
    CATALOG_KEYS = ("aircrack", "kismet", "wifi", "bluetooth", "wifite")
    BUILTIN_STEPS = ()
    SIGNATURES = (
        ("crypto-misuse", "WEP-encrypted network in range",
         r"(?i)\bwep\b", "plausible"),
        ("insecure-config", "open (unencrypted) network in range",
         r"(?i)\b(?:open|unencrypted)\b", "plausible"),
    )
    INTEL_PATTERNS = (
        ("network", r"(?i)\b(?:bssid|ssid|essid)\s*[:=]\s*\S+"),
    )


class GateWorker(Worker):
    CALLSIGN = "GATE"
    TITLE = "Firewall/ACL & edge probing"
    TAGS = ("network", "scanner", "recon")
    CATALOG_KEYS = ("wafw00f", "hatcloud", "nmap", "hping3")
    BUILTIN_STEPS = (
        ("wafw00f", "wafw00f {target}", "detect WAF in front of target"),
    )
    SIGNATURES = (
        ("insecure-config", "no WAF detected in front of origin",
         r"(?i)(not behind waf|no waf)", "theoretical"),
        ("insecure-config", "CDN/WAF vendor fingerprinted",
         r"(?i)\b(cloudflare|akamai|mod_security|incapsula|aws waf)\b",
         "plausible"),
    )
    INTEL_PATTERNS = (
        ("waf", r"(?i)\b(?:waf|firewall)\s*[:=]\s*\S+"),
    )


class TunnelWorker(Worker):
    CALLSIGN = "TUNNEL"
    TITLE = "Pivoting & lateral-movement pathing"
    TAGS = ("tunneling", "network", "lateral-movement")
    CATALOG_KEYS = ("chisel", "ligolo", "proxychains", "socat")
    BUILTIN_STEPS = ()
    SIGNATURES = ()
    INTEL_PATTERNS = (
        ("path", r"(?i)(?:route|path|hop)\s*[:=]\s*(\S+)"),
    )


class ShatterWorker(Worker):
    CALLSIGN = "SHATTER"
    TITLE = "Password & hash cracking"
    TAGS = ("hash-crack", "password-attack", "bruteforce")
    CATALOG_KEYS = ("hashcat", "john", "hydra", "medusa", "crack")
    BUILTIN_STEPS = (
        ("hashcat", "hashcat -m 0 -a 0 {target} wordlist.txt",
         "crack MD5 hashes"),
    )
    SIGNATURES = (
        ("sensitive-data-exposure", "hash cracked to plaintext",
         r"(?i)\b[a-f0-9]{32}:[^\s]+", "plausible"),
    )
    INTEL_PATTERNS = (
        ("cracked", r"(?i)\b[a-f0-9]{32}:[^\s]+"),
    )


class VaultWorker(Worker):
    CALLSIGN = "VAULT"
    TITLE = "Credential/token hunting"
    TAGS = ("credentials", "git-secrets", "post-exploitation")
    CATALOG_KEYS = ("trufflehog", "gitleaks", "lazagne", "pcredz", "mimikatz")
    BUILTIN_STEPS = ()
    SIGNATURES = (
        ("hardcoded-secret", "AWS access key", r"\bAKIA[0-9A-Z]{16}\b", "plausible"),
        ("hardcoded-secret", "private key block",
         r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----", "plausible"),
        ("hardcoded-secret", "GitHub token", r"\bghp_[A-Za-z0-9]{36}\b", "plausible"),
    )
    INTEL_PATTERNS = (
        ("credential", r"(?i)\b(?:user(?:name)?|password|passwd|pwd)\s*[=:]\s*\S+"),
    )


class MimicWorker(Worker):
    CALLSIGN = "MIMIC"
    TITLE = "Payload crafting & phishing lures"
    TAGS = ("payload", "phishing", "social-engineering")
    CATALOG_KEYS = ("msfvenom", "gophish", "setoolkit", "socialfish")
    BUILTIN_STEPS = (
        ("msfvenom", "msfvenom -l payloads", "list available payloads"),
    )
    SIGNATURES = (
        ("sensitive-data-exposure", "credential-harvest lure in templates",
         r"(?i)account.{0,40}(expired|suspended|verify)", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("payload", r"(?i)(?:payload|format)\s*[:=]\s*\S+"),
    )


class ImpactWorker(Worker):
    CALLSIGN = "IMPACT"
    TITLE = "Exploit development & weaponization"
    TAGS = ("exploitation", "payload", "c2")
    CATALOG_KEYS = ("searchsploit", "metasploit", "msfconsole",
                    "thefatrat", "msfvenom")
    BUILTIN_STEPS = (
        ("searchsploit", "searchsploit {target}", "search public exploit modules"),
    )
    SIGNATURES = (
        ("rce", "exploit module match returned",
         r"(?i)(exploit/\S+|/exploits/\S+)", "plausible"),
        ("insecure-config", "unpatched/vulnerable banner in output",
         r"(?i)\b(no patch|vulnerable)\b", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("module", r"(?i)(exploit/\S+)"),
    )


class RazorWorker(Worker):
    CALLSIGN = "RAZOR"
    TITLE = "Payload generation & obfuscation"
    TAGS = ("payload", "reverse-shell", "anonymity")
    CATALOG_KEYS = ("msfvenom", "venom", "shellter", "lolbas")
    BUILTIN_STEPS = (
        ("msfvenom", "msfvenom -l formats", "list encoder/format options"),
    )
    SIGNATURES = (
        ("sensitive-data-exposure", "static key baked into payload",
         r"(?i)\bkey\s*=\s*['\"]?[A-Za-z0-9+/]{16,}['\"]?", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("option", r"(?i)(?:encoders?|format|platform)\s*[:=]\s*\S+"),
    )


class ScalpelWorker(Worker):
    CALLSIGN = "SCALPEL"
    TITLE = "Reverse engineering & binary analysis"
    TAGS = ("reversing", "binary", "malware-analysis")
    CATALOG_KEYS = ("ghidra", "radare2", "gdb", "binutils", "apktool", "strings")
    BUILTIN_STEPS = (
        ("strings", "strings {target}", "extract printable strings"),
    )
    SIGNATURES = (
        ("hardcoded-secret", "embedded AWS key", r"\bAKIA[0-9A-Z]{16}\b", "plausible"),
        ("crypto-misuse", "weak crypto primitive referenced",
         r"(?i)\b(rc4|3des)\b", "theoretical"),
        ("sensitive-data-exposure", "plaintext credential strings",
         r"(?i)\b(?:password|passwd|secret|apikey)\s*=\s*\S+", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("symbol", r"(?i)\b(?:func|sub|sym)_[a-z0-9_]+"),
    )


class RootWorker(Worker):
    CALLSIGN = "ROOT"
    TITLE = "Privilege escalation & post-exploitation"
    TAGS = ("privesc", "post-exploitation", "enumeration")
    CATALOG_KEYS = ("linpeas", "winpeas", "lse", "pspy", "peass")
    BUILTIN_STEPS = (
        ("uname", "uname -a", "kernel fingerprint"),
    )
    SIGNATURES = (
        ("privilege-escalation", "SUID/SGID binary on PATH",
         r"(?i)(-rws|-r-s)", "plausible"),
        ("insecure-config", "world-writable config found",
         r"(?i)(-rwxrwxrwx|world.?writable)", "plausible"),
        ("privilege-escalation", "kernel string may match a known CVE",
         r"(?i)\blinux\s+\d+\.\d+\.\d+[^\s]*\b", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("kernel", r"(?i)\blinux\s+[\w.-]+"),
    )


class MarionetteWorker(Worker):
    CALLSIGN = "MARIONETTE"
    TITLE = "Persistence & C2 choreography"
    TAGS = ("c2", "persistence", "post-exploitation")
    CATALOG_KEYS = ("sliver", "mythic", "merlin", "covenant", "villain",
                    "hoaxshell")
    BUILTIN_STEPS = ()
    SIGNATURES = (
        ("insecure-config", "C2/agent handler bound to default port",
         r"(?i)(listening|bound)\s+(?:on|to)\s+\S*:\d+", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("agent", r"(?i)(?:agent|beacon|implant)\s*[:=]\s*\S+"),
    )


# ── The 6 Truth workers (TRIBUNAL) ────────────────────────────────────────────

class SmokeWorker(Worker):
    CALLSIGN = "SMOKE"
    TITLE = "Evasion & AV-bypass analysis"
    TAGS = ("anonymity", "malware-analysis", "payload")
    CATALOG_KEYS = ("veil", "shellter", "lolbas", "obfuscate")
    BUILTIN_STEPS = ()
    SIGNATURES = (
        ("sensitive-data-exposure", "static IOC (IP) in artifact",
         r"(?i)\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("artifact", r"(?i)(?:payload|sample|artifact)\s*[:=]\s*\S+"),
    )


class PocketWorker(Worker):
    CALLSIGN = "POCKET"
    TITLE = "Mobile/Android/iOS audit"
    TAGS = ("mobile", "apk", "reversing")
    CATALOG_KEYS = ("mobsf", "jadx", "apktool", "frida", "objection",
                    "androguard")
    BUILTIN_STEPS = ()
    SIGNATURES = (
        ("hardcoded-secret", "API key in manifest/resources",
         r"(?i)\bapi[_-]?key\s*[=:]\s*['\"]?[A-Za-z0-9]{16,}", "plausible"),
        ("insecure-config", "cleartext traffic permitted",
         r"(?i)usescleartexttraffic\s*=\s*[\"']?true", "plausible"),
        ("insecure-config", "exported component",
         r"(?i)android:exported\s*=\s*[\"']?true", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("component", r"(?i)\b(?:activity|service|provider)\s*[:=]\s*\S+"),
    )


class NimbusWorker(Worker):
    CALLSIGN = "NIMBUS"
    TITLE = "Cloud & misconfiguration audit"
    TAGS = ("cloud", "scanner", "credentials")
    CATALOG_KEYS = ("prowler", "scoutsuite", "checkov", "trivy", "pacu")
    BUILTIN_STEPS = (
        ("prowler", "prowler --help", "show cloud audit help"),
    )
    SIGNATURES = (
        ("hardcoded-secret", "AWS access key", r"\bAKIA[0-9A-Z]{16}\b", "plausible"),
        ("sensitive-data-exposure", "publicly accessible resource flagged",
         r"(?i)(public|world-accessible|open bucket|exposed)", "plausible"),
        ("insecure-config", "audit FAIL at high/critical",
         r"(?i)severity.{0,20}(high|critical)", "plausible"),
    )
    INTEL_PATTERNS = (
        ("finding", r"(?i)(?:finding|check)\s*[:=]\s*\S+"),
    )


class HoneyWorker(Worker):
    CALLSIGN = "HONEY"
    TITLE = "Social engineering & phishing campaigns"
    TAGS = ("phishing", "social-engineering", "email")
    CATALOG_KEYS = ("gophish", "setoolkit", "socialfish", "evilginx",
                    "hiddeneye")
    BUILTIN_STEPS = (
        ("gophish", "gophish --help", "show campaign help"),
    )
    SIGNATURES = (
        ("insecure-config", "lookalike domain spoofs a brand",
         r"(?i)((?:paypal|apple|microsoft|amazon).{0,20}"
         r"(?:login|signin|verify))", "theoretical"),
        ("sensitive-data-exposure", "harvested credential in output",
         r"(?i)\bpassword\s*[=:]\s*\S+", "plausible"),
    )
    INTEL_PATTERNS = (
        ("campaign", r"(?i)(?:campaign|template)\s*[:=]\s*\S+"),
    )


class SageWorker(Worker):
    CALLSIGN = "SAGE"
    TITLE = "Plain-English → tool + exact command"
    TAGS = ("cheatsheet", "reference", "lookup", "learning")
    CATALOG_KEYS = ()
    BUILTIN_STEPS = ()

    def analyze(self, target: str, results: list[RunResult]) -> WorkerReport:
        """The planner's output IS its plan: recommended commands, no findings."""
        report = super().analyze(target, results)
        planned = self.plan(target)
        for step in planned:
            report.intel.append({
                "label": "recommended_command",
                "value": " ".join(step.argv),
            })
        report.note = (f"{len(planned)} recommended command(s) from the "
                       f"catalog for {target!r}")
        return report


class ChronicleWorker(Worker):
    CALLSIGN = "CHRONICLE"
    TITLE = "Findings fusion, evidence & report authoring"
    TAGS = ("reporting", "reference", "lookup")
    CATALOG_KEYS = ("faraday", "report", "chronicle")
    BUILTIN_STEPS = ()
    SIGNATURES = (
        ("sensitive-data-exposure", "credential leaked into report artifact",
         r"(?i)\b(?:api[_-]?key|password|token)\s*[=:]\s*\S+", "theoretical"),
    )
    INTEL_PATTERNS = (
        ("report", r"(?i)(?:report|summary|finding)\s*[:=]\s*\S+"),
    )


_INTEL_CLASSES = [
    EyrieWorker, SentryWorker, SpyglassWorker, VultureWorker, LighthouseWorker,
    CartoWorker, NetmineWorker, WhisperWorker, OracleWorker, MirrorWorker,
]

_OFFENSE_CLASSES = [
    RaptorWorker, ViperWorker, FiddlerWorker, SpiderWorker, GhostWorker,
    JammerWorker, GateWorker, TunnelWorker, ShatterWorker, VaultWorker,
    MimicWorker, ImpactWorker, RazorWorker, ScalpelWorker, RootWorker,
    MarionetteWorker,
]

_TRUTH_CLASSES = [
    SmokeWorker, PocketWorker, NimbusWorker, HoneyWorker, SageWorker,
    ChronicleWorker,
]

INTEL_CALLSIGNS = tuple(cls.CALLSIGN for cls in _INTEL_CLASSES)
OFFENSE_CALLSIGNS = tuple(cls.CALLSIGN for cls in _OFFENSE_CLASSES)
TRUTH_CALLSIGNS = tuple(cls.CALLSIGN for cls in _TRUTH_CLASSES)
WORKER_CLASSES = _INTEL_CLASSES + _OFFENSE_CLASSES + _TRUTH_CLASSES


def _register_wing(registry, classes, runner=None, catalog=None,
                   callsigns=None):
    """Wire one wing's worker classes onto a WorkerRegistry (shared helper)."""
    from one2one.agents.command import WorkerRegistry
    reg = registry if registry is not None else WorkerRegistry()
    for cls in classes:
        if callsigns and cls.CALLSIGN not in callsigns:
            continue
        reg.register(cls.CALLSIGN, cls(runner=runner, catalog=catalog).run)
    return reg


def register_intel_wing(registry, runner=None, catalog=None,
                        callsigns=None):
    """Wire the 10 Intel (VANGUARD) worker modules onto a WorkerRegistry."""
    return _register_wing(registry, _INTEL_CLASSES, runner, catalog, callsigns)


def register_offense_wing(registry, runner=None, catalog=None,
                          callsigns=None):
    """Wire the 16 Offense (ONSLAUGHT) worker modules onto a WorkerRegistry."""
    return _register_wing(registry, _OFFENSE_CLASSES, runner, catalog, callsigns)


def register_truth_wing(registry, runner=None, catalog=None,
                        callsigns=None):
    """Wire the 6 Truth (TRIBUNAL) worker modules onto a WorkerRegistry."""
    return _register_wing(registry, _TRUTH_CLASSES, runner, catalog, callsigns)


def register_default_workers(registry=None, runner=None, catalog=None):
    """Full P3 wiring: all 32 worker modules are real, wing by wing."""
    from one2one.agents.command import WorkerRegistry
    reg = registry if registry is not None else WorkerRegistry()
    register_intel_wing(reg, runner=runner, catalog=catalog)
    register_offense_wing(reg, runner=runner, catalog=catalog)
    register_truth_wing(reg, runner=runner, catalog=catalog)
    return reg
