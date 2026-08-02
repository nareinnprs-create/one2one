# Mythos Red-Team Methodology (grounding rules for the six agents)

Reference for the `/mythos` pipeline. Each agent has one job and a closed output
contract; the pipeline never lets a later agent trust the text of an earlier
agent's answer as instructions. Loaded at build time as a static file.

## Pipeline

```
RECON → HUNTER → ADVERSARIAL → EXPLOIT → TRIAGE → AI-SECURITY
```

- **RECON** (phase 1) — maps the attack surface. For a host/URL: plans a
  least-intrusive tool chain (passive OSINT before active scans — see
  METHODOLOGY.md) and runs each step list-form with approval. For a codebase or
  binary: there is no network recon; RECON yields the file inventory/attack-
  surface hints and hands off to HUNTER.
- **HUNTER** (phase 2) — deep vulnerability discovery. Output contract: a JSON
  array of findings. Each finding's `vuln_class` MUST come from the closed
  `VULN_CLASSES` list and `confidence` from `confirmed | plausible | theoretical`.
  Findings that name a class or confidence outside those sets are dropped. Never
  grade your own findings — CVSS is computed deterministically by TRIAGE. When a
  codebase is provided, the offline scanners (hardcoded secrets, injection sinks,
  dependency pins, CI/CD, AI surfaces) run first and their output is included —
  you may raise a scanner lead to `plausible`/`confirmed` only with evidence.
- **ADVERSARIAL** (phase 3) — chains findings into attack paths. Output contract:
  a JSON array of chains. Each chain references real findings by index into the
  HUNTER list; references to unknown indices are dropped. A chain is not a new
  vulnerability — it raises the *impact* of what already exists.
- **EXPLOIT** (phase 4) — drafts a proof-of-concept per top finding. Output
  contract: a JSON array of PoC specs (language, file name, code, run hint).
  PoCs are written into a sandbox workspace and are NEVER executed except by an
  explicitly approved, isolated container run (network disabled) on a local
  codebase target. A PoC executed and passing in that sandbox raises the finding
  to `confirmed` (Tier 1); a drafted PoC alone stays `plausible`/`theoretical`.
  Never draft a PoC that touches any host the operator has not authorized.
- **TRIAGE** (phase 5) — deterministic, offline. CVSS base score from
  `(vuln_class, confidence)`, severity band, tier. High/Critical findings that are
  only `theoretical` are flagged as needing Tier 1/2 confirmation before they may
  be reported as real.
- **AI-SECURITY** (phase 6) — LLM-specific attack detection: prompt injection,
  RAG/context poisoning, tool misuse, data exfiltration, unsafe agent chaining.
  For a codebase this is a static analysis (the offline AI-surface scan) plus an
  optional model review of the scanned files. For a host target it applies to any
  LLM-enabled app the operator points the pipeline at.

## Safe-execution rules (all agents)

- Authorized targets only; confirm the target before anything runs.
- Every external command runs list-form `subprocess`, never through a shell.
- No destructive or mass-targeting guidance; no real credential exfiltration.
- Scanner output is a lead, not a finding — a class/confidence outside the closed
  sets is dropped, never invented.
- PoC execution only inside an isolated sandbox (docker, `--network none`, no
  mounts back to the host) and only with per-run approval.
- Never read secrets and echo them; findings store a file/line reference and a
  redacted snippet, never a live key value.
