# One2One Agent Stack

**Status:** Approved — 37 agents, 4 tiers
**Version:** 1.0

The One2One Agent Stack is a self-evolving, command-chained agent hierarchy that
powers the entire console. One supreme agent fronts the user as the assistant;
below it a single operator governs three wing commands that supervise 32
specialist workers.

---

## 1. Command DNA

Every agent in the stack is built from the same nine operating traits. There is
no exception and no tier that gets to relax them.

| Trait | Meaning |
|---|---|
| In-sync | Every agent shares one live battle picture; no stale or contradicting state |
| Accurate | Never guesses; cites evidence or stays silent |
| Honest | Reports failure as loudly as success; no padding |
| Brutal | Kills weak hypotheses and wasted effort on sight |
| Smart | Reasons from first principles, not pattern memory |
| Shrewd | Reads the intent behind the move, not just the move |
| Precise | Exact tool, exact command, exact scope |
| Warrior | Ships under fire; degrades gracefully, never silently |
| Fast | Runs in parallel, streams results, never blocks on perfection |

---

## 2. Hierarchy (37 agents, 4 tiers)

```
APEX ──────────────── SUPREME  · user's assistant · approves evolution
 └─ COMMANDER ─────── OPERATOR · governs & operates all 35 · reports to APEX
     ├─ VANGUARD ──── INTEL COMMAND  · supervises 10 workers
     ├─ ONSLAUGHT ─── OFFENSE COMMAND · supervises 16 workers
     └─ TRIBUNAL ──── TRUTH COMMAND   · supervises  6 workers
```

- 32 workers, each owning its domain and its own responsible sub-toolset
- 3 wing leads supervise the 32 (all 35 supervised = workers + leads)
- 1 operator governs and operates all 35
- 1 supreme answers the user and is the voice of the whole stack

---

## 3. The Stack

### Tier 4 — Supreme

| Agent | Role |
|---|---|
| `APEX` | Supreme agent and user-facing assistant. Owns ethics and scope, gates every skill mutation, and is the single interface the user talks to. Reports to nobody. |

### Tier 3 — Operator

| Agent | Role |
|---|---|
| `COMMANDER` | Mission governor. Routes work across wings, enforces sequencing and parallelism, kills wasted effort, reconciles conflicts, and reports up to APEX. |

### Tier 2 — Wing Command (3)

| Agent | Command | Responsibility |
|---|---|---|
| `VANGUARD` | Intel | Owns the eyes — supervises all recon/OSINT/analysis workers, keeps the battle picture live |
| `ONSLAUGHT` | Offense | Owns the strike — supervises all web/network/exploit/post-ex workers, sequences the attack |
| `TRIBUNAL` | Truth | Owns the verdict — supervises validation, AI, mobile/cloud audit and reporting; the only wing allowed to say "proven" |

### Tier 1 — Workers (32)

#### VANGUARD — Intel Wing (10)

| Agent | Responsibility |
|---|---|
| `EYRIE` | Network & attack-surface recon |
| `SENTRY` | Port/service discovery, banner grab |
| `SPYGLASS` | Passive OSINT & footprinting |
| `VULTURE` | Deep-web/leak & metadata harvesting |
| `LIGHTHOUSE` | DNS/subdomain enumeration |
| `CARTO` | Topology & reachability mapping |
| `NETMINE` | Packet capture & traffic analysis |
| `WHISPER` | Steganography & covert-channel probes |
| `ORACLE` | Crypto weakness & weak-key detection |
| `MIRROR` | Evidence & artifact harvesting |

#### ONSLAUGHT — Offense Wing (16)

| Agent | Responsibility |
|---|---|
| `RAPTOR` | Web-app vulnerability scanner |
| `VIPER` | SQL injection specialist |
| `FIDDLER` | Request tampering & auth logic testing |
| `SPIDER` | Content discovery & crawling |
| `GHOST` | Session/auth bypass, impersonation |
| `JAMMER` | Wireless/BT/RF audit |
| `GATE` | Firewall/ACL & edge probing |
| `TUNNEL` | Pivoting & lateral-movement pathing |
| `SHATTER` | Password & hash cracking |
| `VAULT` | Credential/token hunting |
| `MIMIC` | Payload crafting & phishing lures |
| `IMPACT` | Exploit development & weaponization |
| `RAZOR` | Payload generation & obfuscation |
| `SCALPEL` | Reverse engineering & binary analysis |
| `ROOT` | Privilege escalation & post-exploitation |
| `MARIONETTE` | Persistence & C2 choreography |

#### TRIBUNAL — Truth Wing (6)

| Agent | Responsibility |
|---|---|
| `SMOKE` | Evasion & AV-bypass analysis |
| `POCKET` | Mobile/Android/iOS audit |
| `NIMBUS` | Cloud & misconfiguration audit |
| `HONEY` | Social engineering & phishing campaigns |
| `SAGE` | Plain-English → tool + exact command (AI skill planner) |
| `CHRONICLE` | Findings fusion, evidence & report authoring |

---

## 4. Sync Protocol

1. **Downlink:** APEX → COMMANDER → wing lead → worker. Work arrives as a
   scoped mission (targets, rules of engagement, budget).
2. **Uplink:** workers stream findings up through their wing lead; leads fuse
   and escalate only what survives brutal self-review.
3. **Single picture:** all state flows through one live mission ledger
   (`COMMANDER`), so no two agents ever hold contradicting truth.
4. **Honesty contract:** a wing lead reporting "no findings" must mean "proven
   clean," not "didn't look."

---

## 5. Self-Development Loop (24/7)

Each agent runs a continuous evolution cycle. No agent waits for a human.

1. **Log** — every outcome, near-miss and rejected hypothesis is recorded as a
   lesson (structured, versioned).
2. **Mutate** — the agent proposes a skill patch from its lessons (new tool,
   sharper prompt, new detection).
3. **Gate** — the proposal climbs to the wing lead, then to `COMMANDER`, then to
   `APEX`, who approves or kills it. Ethics and scope are always the gate.
4. **Propagate** — approved patches sync to the whole stack so one agent's win
   becomes everyone's default.
5. **Re-run** — the mutated agent re-validates on its own regression set; a
   regression rolls the patch back automatically.

The stack gets sharper while idle — evolution never requires a mission.

---

## 6. Mapping onto One2One

The stack supersedes and absorbs the existing Mythos six-agent pipeline
(`src/one2one/mythos.py`) rather than running alongside it:

| Existing Mythos role | Absorbed into |
|---|---|
| RECON | `VANGUARD` / `EYRIE` |
| HUNTER | `ONSLAUGHT` / `RAPTOR` |
| ADVISER | `SAGE` |
| PHASE | `COMMANDER` |
| EXPLOIT | `ONSLAUGHT` / `IMPACT` |
| SENTINEL | `TRIBUNAL` / `CHRONICLE` |

User-facing surfaces: `APEX` is the voice of `/ai`, `/mythos`, `/redteam` and
the `/find` discovery. Worker output lands in the existing findings ledger and
report pipeline unchanged.

**`/ask`** runs plain-English missions straight through `APEX` from the console:
`/ask enumerate example.com` fans the intent through the scope gate, dispatches
to the routed worker (Mythos adapter), has the wing lead review the findings,
and logs everything to the live ledger (`/stack`). Default-deny: nothing is in
scope until the user authorizes targets via `/config mission_scope
example.com,*.example.org` — out-of-scope missions are killed at the gate and
still ledgered for the audit trail. (See `src/one2one/agents/console.py`.)

---

## 7. Build Plan

| Phase | Scope | Status |
|---|---|---|
| P0 | `APEX` + `COMMANDER` skeleton: mission ledger, scope gate, routing core | shipped (see `src/one2one/agents/`) |
| P1 | Three wing leads with brutal finding review; `MythosAdapter` over the pipeline so the stack runs today | shipped |
| P2 | First 10 workers (Intel wing) as agent modules over the existing tool catalog | shipped |
| P3 | Offense wing (16) + Truth wing (6); parallel dispatch + streamed findings | shipped |
| P4 | Lesson log, mutation, APEX approval gate, propagation, regression rollback | shipped (see `src/one2one/agents/lessons.py`, `src/one2one/agents/evolution.py`) |

Every phase must keep the existing gate green: `ruff` clean and `pytest -q`
all-passing on Windows.
