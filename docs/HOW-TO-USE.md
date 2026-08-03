# How to use one2one

Step-by-step walkthroughs of the console. Every step below is something you type
and something you get back — no prior knowledge of the codebase needed.

> **Authorized targets only.** Everything here assumes you own the target or hold
> written permission to test it. one2one never runs a step without asking you
> first, and never invents results.

- [1. First run](#1-first-run)
- [2. Learn the grammar in 60 seconds](#2-learn-the-grammar-in-60-seconds)
- [3. Open and install a tool](#3-open-and-install-a-tool)
- [4. Find a tool that isn't in the catalog (`/find`)](#4-find-a-tool-that-isnt-in-the-catalog-find)
- [5. Plan and run an objective (`/goal`)](#5-plan-and-run-an-objective-goal)
- [6. Run the Mythos red-team pipeline (`/mythos`)](#6-run-the-mythos-red-team-pipeline-mythos)
- [7. Connect a model (`/config`)](#7-connect-a-model-config)
- [8. Add a GitHub token for `/find` (`/config github`)](#8-add-a-github-token-for-find-config-github)
- [9. Run tools in background panes](#9-run-tools-in-background-panes)
- [10. Headless mode: engagements, pipelines, reports](#10-headless-mode-engagements-pipelines-reports)

---

## 1. First run

1. Install it (see the [README](../README.md#installation)). From a checkout, the
   quickest path that puts `one2one` on your PATH is:

   ```bash
   git clone https://github.com/nareinnprs-create/one2one.git
   cd one2one
   pipx install .
   ```

2. Launch it:

   ```bash
   one2one
   ```

3. On the first launch one2one creates its home directory — nothing is
   written outside it:

   | Path | What it is |
   |---|---|
   | `~/.one2one/config.json` | your settings (defaults on first run) |
   | `~/.one2one/.env` | commented secrets template, `chmod 600` — no active secret in it |
   | `~/.one2one/tools/` | where tools you install are cloned/built |
   | `~/.one2one/history` | your `↑`/`↓` command history |

4. You land on the banner + prompt. The header line tells you what you have:
   OS, IP, and `22 categories · 217 active · 59 archived` (that count includes
   the built-in Update/Uninstall menu; the tool catalog itself is
   [21 categories / 215 tools](TOOLS.md)).

5. Type `/help` for the command card, and `q` (or `/quit`, `Ctrl-D`) to leave.

If your terminal isn't interactive, or `prompt_toolkit` isn't available, you get
the classic numbered menu instead — same features, numbers instead of commands.
Force it any time with `one2one --classic`.

---

## 2. Learn the grammar in 60 seconds

There are exactly three things you can type:

| You type | It means | Example |
|---|---|---|
| `/…` | a command you run | `/search subdomain` |
| `@…` | a thing you name | `@nmap`, `@tag:osint` |
| anything else | plain-English "what I want to do" | `crack a wifi handshake` |

Try these in order:

1. `/tags` — prints every tag with its tool count (63 tags in use).
2. `@tag:osint` — lists the tools carrying that tag, then lets you pick one by
   number.
3. `@nmap` — opens a tool straight away (matching is case-insensitive with a
   fuzzy fallback, so `@nmpa` still finds it).
4. `/search wordlist` — keyword search over names, descriptions and tags.
5. `crack a wifi handshake` — no slash, no at-sign: the recommender reads your
   words and shows matching tools.

Tab completes commands, tool names and tags. `↑`/`↓` walk your history.
`Ctrl-C` clears the current line; `Ctrl-D` exits.

---

## 3. Open and install a tool

1. Open it: `@nuclei` (or `/run nuclei`).
2. You get the tool's card: description, project link, and — where curated — a
   usage cheatsheet of real commands for common tasks.
3. Choose from the numbered menu:
   - `1` install the tool
   - `2` run it
   - `c` (or `cmd`) ask for the exact command for a goal, when the tool has a
     usage cheatsheet — it answers from the curated cheatsheet first, and only
     asks a model if nothing matches. Nothing is executed; you get a command to
     read and copy.
   - `98` open the project page
   - `99` back
4. Inside a category listing, `97` installs every not-yet-installed tool in that
   category and `98` opens the archived tools of that category (if it has any).

If a tool is already on your PATH from your distro (`apt`, `brew`, Kali's
metapackages), one2one reuses that binary instead of re-cloning it.

---

## 4. Find a tool that isn't in the catalog (`/find`)

`/find` answers "what should I use for X?" — first from the 215 curated tools,
then from the GitHub search API, ranked with a reason for each hit. It is
**suggest-only**: it never clones, installs or runs anything, and it makes **zero
model calls**.

1. Ask in plain English:

   ```
   /find hidden directories on a website
   ```

2. You get two blocks:

   - **In your toolbox (vetted)** — matching tools already in the catalog.
   - **Found on GitHub — NOT vetted by us** — up to 5 maintained repos with
     stars, license, a one-line description, the reason each ranked
     (`16446★ · trusted author (ships in our catalog) · active · matches: fuzzer, web`)
     and a `git clone …` line to copy. Read the repo before you run it — that
     warning is there because nobody has vetted these for you.

3. To keep one, press `a` at the prompt, then the result number:

   ```
   [a] add one to your toolbox · [Enter] done: a
   which? 1-5: 2
   Added.  /Users/you/.one2one/found.yaml
   ```

4. What that writes: an entry in **`~/.one2one/found.yaml`** under a
   `Discovered tools` category — title, tags, description, project URL. It
   deliberately stores **no install or run command**, so a discovered entry can
   never execute anything; it is a bookmark that shows up in your menu and in
   `/search` on the next launch.

5. Out-of-scope asks are refused *before* any network call, with an authorized
   alternative where one exists:

   ```
   /find build a wifi jammer
   Out of scope: Jamming is a denial-of-service attack and is out of scope. For
   authorized work, wifi AUDITING tools test your own/scoped networks:
   aircrack-ng, hcxtools, wifite (offline WPA/WPA2 handshake cracking).
   ```

   Defensive and DFIR phrasing ("detect a SYN flood", "hunt for…", "triage AV
   false positives") is never refused.

Without a token you get 10 searches per minute from GitHub. See
[step 7](#7-add-a-github-token-for-find-config-github) to raise that to 30.

---

## 5. Plan and run an objective (`/goal`)

`/goal` turns one objective into a short, ordered plan of real commands, then
runs the steps **you** approve, one at a time.

1. State the objective:

   ```
   /goal find live subdomains of example.com
   ```

2. one2one plans (one model call, made against a vetted operator
   methodology) and prints the plan: each step's tool, the exact argv it would
   run, why it's there, and — for tools you don't have — an install hint.

3. Confirm authorization. Nothing runs before you answer `y`:

   ```
   ⚠  This goal will run tools against:  example.com
      Confirm you are AUTHORIZED to test this target? [y/N]
   ```

4. Approve step by step:

   ```
   ─ step 1/4 ─ subfinder -d example.com -silent
     [y] run  [s] skip  [e] edit  [q] abort  ›
   ```

   - `y` runs it (list-form, never through a shell) and prints the output when it
     finishes — steps run in the goal's workspace directory, with a 30-minute cap
   - `s` skips it
   - `e` lets you edit the command first — the edited command is what gets run
     *and* what gets logged
   - `q` aborts the rest

   Steps whose tool isn't installed are skipped automatically and reported at
   the end, with the install hint from the plan.

5. Everything lands in a timestamped workspace:

   ```
   ~/.one2one/goals/2026-07-26T18-40-12-123456/
   ├── plan.json          the drafted plan
   ├── run.log            UTC-stamped: authorization, per-step decision, outcome
   └── step-1-subfinder.txt   raw output of each step you ran
   ```

Two guarantees worth knowing: the model is called **once**, for planning only,
and tool output is **never** fed back to it — so nothing a target prints can
steer the next step. And a step is only ever a list of arguments, never a shell
string.

No model configured? `/goal` says so and falls back to plain tool
recommendations for the same objective.

---

## 6. Run the Mythos red-team pipeline (`/mythos`)

`/mythos` (aliases `/redteam`, `/rt`) runs the six-agent red-team pipeline on an
**authorized** target:

```
/mythos example.com            # network/host: recon → hunter → adversarial → exploit → triage → ai-security
/mythos code:./src             # codebase deep-dive: offline scans + model review
/mythos binary:./challenge     # binary analysis
```

The pipeline is RECON → HUNTER → ADVERSARIAL → EXPLOIT → TRIAGE → AI-SECURITY.
Each agent has a **closed output contract**: the model may only return findings
using the fixed vulnerability-class vocabulary and the three-tier confidence
model, so it can never invent a class. Offline deterministic scanners run first
and their leads are included in every agent prompt; TRIAGE scores CVSS / tier /
severity offline, never through the model. With no model reachable, the whole run
degrades to those offline scans — nothing is fabricated.

What each phase does:

- **RECON** plans real recon commands for a host/URL and runs them with per-step
  approval (`[y]` run · `[s]` skip · `[q]` abort). Code/binary targets skip it.
- **HUNTER** feeds recon output or code material to the model and validates every
  finding it returns against the closed sets.
- **ADVERSARIAL** chains real findings into attack paths; chains referencing
  unknown findings are dropped.
- **EXPLOIT** drafts PoCs into a sandbox workspace. For a local `code:` target
  they can be validated at runtime in an isolated docker container
  (`--network none`, read-only code mount) with explicit per-run approval — gated
  by `mythos_sandbox` in `/config`.
- **TRIAGE** ranks deterministically (confirmed > plausible > theoretical) and
  flags high/critical findings that are only theoretical (needs Tier 1/2).
- **AI-SECURITY** scans for LLM-specific risks (prompt injection, RAG poisoning,
  tool misuse, exfiltration, unsafe agent chaining); on network targets it also
  runs the **AI self-test**, probing this app's own AI layer for injection
  resistance.

Everything lands in a timestamped workspace under `~/.one2one/mythos/`:

```
mythos_findings.json   ranked findings (closed vocabulary, deterministic scores)
chains.json            attack paths with real finding indices
self_test.json         AI prompt-injection probe results
mythos_report.md       Markdown report
```

---

## 7. Connect a model (`/config`)

The AI layer is opt-in and bring-your-own-key. Without it everything still works:
recommendations fall back to a keyword matcher, `/find` never needed a model, and
commands come from the curated cheatsheets.

**Option A — a hosted OpenAI-compatible endpoint**

1. Open the settings editor:

   ```
   /config
   ```

   `↑`/`↓` move, `←`/`→` change a value (saved immediately), `Enter` edits a
   free-text row, `t` tests the connection, `Esc` closes.

2. Set `ai_base_url` (e.g. `https://api.openai.com/v1`) and `ai_model`.
3. Select the `ai_key` row, press `Enter`, paste your key. It is masked while
   typing and written to `~/.one2one/.env` (mode 600) — **never** to
   `config.json`, never printed back.
4. Test it:

   ```
   /config test
   ✓ AI connection OK  <your-model> replied 'connected'
   ```

**Option B — a local model with Ollama**

1. Install and start [Ollama](https://ollama.com), then `ollama pull llama3`.
2. Leave `ai_base_url` empty and set `ai_model` to the model you pulled.
3. `/config test` to confirm.

Any key can also be set in one line, e.g. `/config theme cyan`,
`/config show_archived true`, `/config background_runner off`. Environment
variables (`ONE2ONE_AI_BASE_URL`, `ONE2ONE_AI_MODEL`,
`ONE2ONE_AI_KEY`, `ONE2ONE_AI_PROVIDER`) always win over `config.json`.

---

## 8. Add a GitHub token for `/find` (`/config github`)

Optional. It buys one thing: GitHub's search rate limit goes from **10 to 30
requests per minute**. The token needs **no scopes and no permissions at all** —
never grant it any.

1. Check your current state:

   ```
   /config github
   ○ GitHub  no token configured — unauthenticated search is 10 req/min
   ```

   one2one then prints the exact steps. They are:

2. GitHub → your profile picture → **Settings**
3. Left sidebar → **Developer settings**
4. **Personal access tokens → Fine-grained tokens → Generate new token**
5. Name it (e.g. `one2one-find`) and pick an expiration.
6. Resource owner: yourself. Repository access: **leave the default — do NOT
   select any repositories.**
7. Permissions: **select none at all.** (GitHub: *"Tokens always include
   read-only access to all public repositories on GitHub."*)
8. Generate the token and copy it.
9. Add it to `~/.one2one/.env` (the file is already `chmod 600`):

   ```
   ONE2ONE_GITHUB_TOKEN=ghp_your-token-here
   ```

10. Verify:

    ```
    /config github
    ✓ GitHub token OK  token OK — search limit 30 req/min
    ```

Classic tokens work too: **Developer settings → Tokens (classic) → Generate new
token → tick NO scopes at all.** `GITHUB_TOKEN` / `GH_TOKEN` from your
environment are picked up as well. The token is never echoed back and is only
ever sent to `api.github.com`.

---

## 9. Run tools in background panes

Long scans shouldn't block your console. If **tmux** is installed, one2one
keeps one detached session called `one2one` and gives each background job its
own labeled window.

1. Add ` &` to a `/run`:

   ```
   /run nmap -sV -oA scan 10.0.0.5 &
   ▶ started 'nmap' in background — /attach to view
   ```

   A bare `/run nmap &` opens a shell already `cd`'d into the tool's directory,
   with the tool's first cheatsheet command typed in as a comment.

2. See what's running — the status line under the prompt shows `▶ N running`, and:

   ```
   /panes          (alias /jobs)
     nmap (window 0)
   ```

3. Watch one: `/attach` — this hands your terminal to tmux. Press `Ctrl-b` then
   `d` to detach and come back to the console.
4. Stop one, or all: `/kill nmap` · `/kill all`.

No tmux? Nothing breaks — one2one says so and opens the tool inline instead.
Turn backgrounding off entirely with `/config background_runner off`.

---

## 10. Headless mode: engagements, pipelines, reports

The same catalog drives a non-interactive orchestrator, for CI or a scripted
engagement. Findings are normalized into one `findings.json` you can grep, diff
or feed into other tooling.

```bash
# create/extend an engagement and run the default recon pipeline against it
one2one --engagement acme --targets example.com --pipeline recon

# a file of targets, one per line
one2one --engagement acme --targets ./scope.txt --pipeline recon

# (re)generate the deterministic Markdown report
one2one --engagement acme --report

# opt-in AI passes over the REAL findings only
one2one --engagement acme --ai-summary
one2one --engagement acme --ai-report     # writes report.draft.md
```

`--engagement` is required in headless mode unless you're running a Mythos
standalone flag. Out-of-scope targets are flagged and logged before anything runs.
`--ai-summary` and `--ai-report` only ever summarize findings that exist — the
deterministic `report.md` is never overwritten by the AI draft.

Mythos has the same headless surface:

```bash
# full six-agent pipeline against engagement targets (optional content fuzzing)
one2one --engagement acme --targets example.com --mythos --fuzz /path/to/words.txt

# codebase deep-dive / binary analysis — no engagement needed
one2one --mythos-code ./src
one2one --mythos-binary ./challenge

# standalone checks — no engagement needed
one2one --ai-self-test        # E1 prompt-injection harness (offline-safe)
one2one --mythos-benchmark    # H3 scanner scoring: recall / precision
```

`--ai-self-test` and `--mythos-benchmark` are fully offline; `--mythos` /
`--mythos-code` / `--mythos-binary` hit the model only if one is configured and
degrade to the offline scanners otherwise.

---

## Where things live

| Path | Contents |
|---|---|
| `~/.one2one/config.json` | settings (`/config`) |
| `~/.one2one/.env` | API key + GitHub token, mode 600 |
| `~/.one2one/found.yaml` | tools you kept from `/find` |
| `~/.one2one/goals/<utc-timestamp>/` | `/goal` plan, run log, step output |
| `~/.one2one/mythos/<utc-timestamp>/` | `/mythos` findings, chains, self-test, report, PoCs |
| `~/.one2one/tools/` | installed tools |
| `~/.one2one/one2one.log` | command/audit log |
| `~/.one2one/history` | prompt history |

Related reading: [full tool catalog](TOOLS.md) ·
[operator playbook](../src/one2one/skill/OPERATOR.md) (also `/skill`) ·
[SECURITY.md](../SECURITY.md) · [CONTRIBUTING.md](../CONTRIBUTING.md)
