# one2one UI/UX design — "the best of 2026"

**Status:** design spec (review before implementation)
**Scope:** interactive terminal console (rich + prompt_toolkit), headless CLI output
**Non-goals:** no full-screen TUI rewrite (Textual), no web UI, no loss of native
scrollback, no change to the headless/CLI contract.

---

## 1. Thesis

one2one is not a menu tree with AI bolted on. It is an **AI-native security
console**: one input surface, a universal grammar (`/` commands, `@` tools,
natural language), first-class engagements, and live awareness of what is running
and what was found. The 2026 redesign makes the interface *state*, not chrome:
the user always knows **where they are**, **what is running**, **what they are
allowed to hit**, and **what the console just learned** — in one glance, from any
screen.

Five pillars:

1. **Context, never chrome.** The header is not ASCII art; it is a status strip.
   Every pixel of vertical space reports state.
2. **Search is the home.** The 4-level numbered drill-down becomes a fuzzy-findable
   flat catalog. Everything is reachable in ≤2 keystrokes from anywhere.
3. **One grammar, every surface.** The existing `/ @ text` grammar already works at
   every prompt. Extend it, don't fork it. There is no screen you can get lost in.
4. **Live by default.** A single status strip carries scope, running panes, findings,
   model, and breadcrumb — refreshed on the existing idle timer.
5. **Restrained beauty.** One accent hue (theme-swappable), fixed semantic status
   colors, a tiny curated glyph set with cp1252-safe fallbacks, consistent 2-space
   rhythm, truecolor that adapts to light/dark terminals.

---

## 2. Design system

### 2.1 Color tokens

Replace ad-hoc `"bold magenta"`, `"#ff5fd7"`, `"dim white"` usages with named
tokens exposed from one module (`ui.py`). Semantic colors never change with theme;
only the accent family swaps (existing `/config` theme behavior, extended).

| Token | Meaning | Dark | Light | Notes |
|---|---|---|---|---|
| `fg` | body text | `#e0e0f0` | `#1a1a24` | |
| `fg-muted` | secondary text | `#9a9ab4` | `#5a5a70` | replaced `dim white` |
| `border` | rule/border | `#4a4a6a` | `#c8c8dc` | |
| `accent` | interactive + selection | theme hue | theme hue | existing 4 palettes |
| `ok` | success / in-scope / installed | `green` | `green` | constant |
| `err` | failure / out-of-scope | `red` | `red` | constant |
| `warn` | caution / theoretical finding | `yellow` | `amber` | constant |
| `info` | guidance | `cyan` | `teal` | constant |
| `spot` | the one security-state emphasis | `bright_red` | `dark_red` | reserved for scope/authorization |

Rules:
- Never express state **only** via color — always pair with a glyph or symbol.
- Light/dark adaptation: default `dark`; a `ui.dark` config key overrides. Selection
  uses `reverse` on `fg`/`bg` so it works in both.
- Token values live in `ui.py` and are consumed by rich Style objects and the
  prompt_toolkit Style dict in `prompt._session()` / `config_ui` — one source of
  truth, no literal hex scattered across modules.

### 2.2 Spacing & layout rhythm

- Horizontal unit = 1 space; content padding = 1 on single-line rows, 2 inside panels.
- Content width cap ≈ **110 columns**; on wider terminals, extra space goes to a
  right-aligned live region, never to wider text.
- Rules/dividers are 1 line, muted `border` color, `─` fill. Panels use the existing
  `ROUNDED` box but with `border` token, not a loud color.
- No column assumes > 60 cols; every table has a defined narrow-terminal fallback
  (columns fold or drop, never overflow).
- Section labels are **uppercase, bold, spaced** (e.g. `RECON`, `SCOPE`, `RUNNING`)
  — the visual hierarchy comes from case + weight, not decoration.

### 2.3 Typography & voice

- Monospace, terminal-native. Hierarchy = weight (`bold`) + case + color tokens.
- Voice: terse operator register. Commands/code in `fg` bold; prose in `fg-muted`.
- The brand is a **wordmark line**, not ASCII art:
  `one2one v3.0.0` + theme dot + the one-line mission on first run only.

### 2.4 Glyph kit (cp1252-safe)

One function, `ui.glyph(name)`, picks the widest glyph the console encoding can
print, falling back per glyph. This kills the class of Windows cp1252 crashes the
project already hit (`✓`/`◈`).

| Name | Full | Fallback (cp1252 / non-UTF8) |
|---|---|---|
| `ready` | `●` | `*` |
| `missing` | `✗` | `x` |
| `running` | `▶` | `>` |
| `chevron` | `›` | `>` |
| `tick` | `✔` | `ok` |
| `bullet` | `•` | `-` |
| `arrow` | `↳` | `->` |
| `warn` | `⚠` | `!` |
| `link` | `↗` | `->` |
| `search` | `⌕` | `?` |
| `box-t/b/m/c` | `╭ ╮ ╰ ╯ │` | `+ + + + |` |
| `ellipsis` | `…` | `...` |
| `dot` | `·` | `|` |

- All emoji (category icons in `tool_definitions`) move to the **glyph kit too**:
  they render inconsistently across terminals. Category marks become single letters
  or the kit's symbols, not emoji.
- Every new component must go through the kit — a grep test can enforce "no bare
  `✓`/`◈`/`•` literal in source outside `ui.py`".

---

## 3. Screens

### 3.1 Home dashboard (replaces `build_menu` + ASCII header)

```
one2one v3.0.0                                        ● dark  ·  model: llama3
──────────────────────────────────────────────────────────────────────────
  ENGAGEMENT   acme-2026-08   ● 2 in-scope   ·  ! 1 excluded   ·  3 findings
  QUICK        /find     /mythos     /goal     /config     /help
──────────────────────────────────────────────────────────────────────────
  RUNNING                      RECENT FINDINGS               WORKSPACE
  ▶ nmap scan (w1)             ! HIGH subfinder plugin      acme-2026-08
  ▶ ffuf (w2)                  ! MED  open ports            recon · 3 runs
                               ok resolved 2026-07-31       last 2026-08-02 14:03
──────────────────────────────────────────────────────────────────────────
  ›                                                                       │
  ╰───────────────────────────────────────────────────────────────────────╯
  home · 320 tools · 24 tags · @ tools  / cmds  ·  ? help · Ctrl-P jump
```

- **Brand line** (1 row): wordmark, theme dot, model chip, auth note on first run.
- **Engagement strip** (1 row): the current engagement, in-scope/excluded counts,
  findings badge. Out-of-scope state turns the `!` **spot** color. This is the
  security-state "always visible" contract.
- **Quick actions** (1 row): hot chips for the AI flows.
- **Live region** (variable): 3 columns when ≥ 100 cols, stacked when narrower.
  Each cell is optional and collapses to `(none)` empty state.
  - RUNNING: from `session.windows()` + `/run` panes.
  - RECENT FINDINGS: newest N from the active engagement's `findings.json`.
  - WORKSPACE: engagement runs + last-run time + report link.
- **Input**: unchanged shared surface (`prompt.read_line`), `›` marker inside the
  existing rounded box. Typing anything searches; grammar still works.
- **Status line**: the existing `prompt.status(ctx)` — becomes the component
  `ui.StatusBar` used by every screen.

### 3.2 Command palette (new, Ctrl-P / `//`)

The "kill the tree" enabler. A prompt_toolkit overlay (like `config_ui`) fuzzy-matches
over one flat index: **all 320 tools, all tags, all 18 `/` commands, recent
commands, engagements.** Enter jumps — open a tool, run a `/` command, filter a tag,
open an engagement, or attach a pane.

`//` at the input (double slash) also opens it, so it works without knowing the
shortcut. Esc closes; ↑↓/j/k navigate; Tab completes.

### 3.3 Catalog / search results (replaces the numbered category grid)

- Flat, fuzzy-highlighted list (`ui.fuzzy()` wraps `difflib` + rich highlight).
  Right column = tag chips.
- Selection: **type to filter**, ↑↓/j/k + Enter opens, or type a number (kept for
  muscle memory). No nested drill required; breadcrumb always shows the path.
- Category no longer a "screen to descend" — it is a **tag** (`@tag:web`) plus a
  grouping line inside the flat list.
- Empty state: `no tools match "x"` + `\n/find` suggestion + a `@tag:` hint.

### 3.4 Tool screen

```
home / web attack / sqlmap                     [● installed]
──────────────────────────────────────────────────────────────────────────
  sqlmap — automatic SQL injection + database takeover tool
  USAGE        What you want                 Command
               find SQLi on a target         sqlmap -u <url> --batch
               dump the database             sqlmap -u <url> --dbs
  LAB-SAFE     🧪 THM/CTF-safe: only run against targets you own
  OPTIONS      1 Install   2 Run   3 Update   4 Open Folder   5 Project
  KEYMAP       c command   ? help   Esc/99 back   q quit
──────────────────────────────────────────────────────────────────────────
  ›
```

- Breadcrumb (top-left) + installed chip (top-right) + scope chip when relevant.
- USAGE cheatsheet becomes a real table (already exists in `show_info` — restyle).
- Options render as a single row of hot chips with numbers kept.
- `c` opens the AI command box inline; output returns to the tool screen.

### 3.5 Mythos / Goal pipeline (the agent flows)

Both `/mythos` and `/goal` render through one `ui.phase_stream` component:

```
  MYTHOS · six-agent red-team pipeline            target: example.com
  ────────────────────────────────────────────────────────────────────
  ▶ RECON        ⠙ gathering subdomains, hosts, certificates…  0:12
  ● HUNTER       3 findings · 2 high · 1 med
  ● ADVERSARIAL  1 theoretical — confirm before reporting
  ● EXPLOIT      sandbox PoC: no malicious behavior (verified)
  ○ TRIAGE       …
  ○ AI-SECURITY  …
  ────────────────────────────────────────────────────────────────────
  SO FAR    ! 3 high    ! 2 med    ! 0 low      → workspace: acme-2026-08/mythos
```

- One row per phase/step: spinner glyph → `● done` / `✗ failed` / `○ pending` /
  `! theoretical`. Live elapsed time where a step runs long.
- Findings **accumulate in a right-hand summary card** as they are produced
  (live), so the operator sees the yield grow without hunting the log.
- End: `Enter` opens the workspace, `@report` jumps to the report screen,
  `d` prints the JSON path. Offline/no-model degradation prints a `warn` badge
  once at the top, never mid-stream.

### 3.6 Findings & report

- Findings list: severity badges (`! high` spot/`! med` warn/`• low` info), title,
  tier tag (`theoretical` gets a warn chip), target. Grouped by severity, newest first.
- One-key actions per row: `Enter` detail, `o` open in browser (http-only guard,
  reuse `show_project_page`), `c` copy.
- Report screen renders the engagement's `report.md` as markdown (rich Markdown),
  breadcrumb `home / acme-2026-08 / report`.

### 3.7 Config

Keep the existing full-screen modal (`config_ui`) — it is already the right
interaction — restyle to the new tokens, add a `dark/light` row, and a live
`status` chip. Footer hints already match the KeyMap pattern below.

### 3.8 Headless

Unchanged contract. `--classic` keeps the legacy rich menu exactly as-is.
Headless output adopts tokens + ASCII `PASS`/`MISS` glyphs (already done for
benchmark).

---

## 4. Interaction model

### 4.1 Global keyboard map (every screen)

| Key | Action | Notes |
|---|---|---|
| `Esc` | back one level | also 99, `/back` — identical result |
| `Ctrl-P` / `//` | command palette | jump anywhere |
| `Ctrl-S` / `Ctrl-F` | fuzzy search | focus the flat catalog |
| `Ctrl-L` / `clear` | clear screen | re-prints current screen |
| `↑`/`↓` | history / list nav | existing shared history |
| `j`/`k` | list nav (vim) | only when a list is focused |
| `Tab` | complete / next | existing completer |
| `?` | context help | blocking, single key, per-screen |
| `q` / `Ctrl-D` / `Ctrl-C` | quit | at home; tool screens: back first |
| `Enter` | confirm / open | |

Guarantees:
- **No modal traps.** Every screen has at least two exits (`Esc` and a grammar verb).
- **Quit never requires a confirm** when nothing is running; with running panes it
  prints a one-line `N running — /kill all to stop` hint instead of an unknown prompt.
- **Discoverability without clutter**: hints live in the status strip / footer, not
  stacked at the prompt.

### 4.2 Grammar (unchanged core, extended everywhere)

- `/` commands, `@` tools/tags, bare text = AI — already the single grammar. It
  already works inside tool menus. Add: `//` palette, `/report` (open engagement
  report), `/engagements` (list/switch), and make `/mythos`, `/goal`, `/find`
  context-free (usable from any screen).
- Every `Open` result returns to the originating screen on `Esc` (breadcrumb stack
  is 1 level deep; the existing shallow walk-back is extended to a 3-level stack:
  home → catalog → tool).

### 4.3 Status bar contract

`ui.StatusBar` renders on every screen from `prompt.status(ctx)`:
`breadcrumb · N tools · N tags · running · findings badge · model chip`.
The security state (`● in-scope / ! excluded`) is always present when an
engagement exists, and the prompt box itself is tinted `spot` when any target is
out of scope.

---

## 5. Accessibility & robustness

- **No color-only meaning.** Every state token pairs with a glyph (2.4).
- **Light/dark**: `ui.dark` config (default `dark`); rich theme adapts.
- **Width-aware**: cap ~110; every component has a narrow fallback (folds →
  stacks → single-line summary). No component may crash below 60 cols.
- **Non-TTY / `--classic`**: every new component defines its degraded rendering —
  status bar → one dim line, live region → skipped, palette → `/` completions,
  spinner → `...` ticks. The existing `prompt._use_pt()` gate is the switch.
- **Windows cp1252**: all glyphs through the kit (2.4); tests assert fallback
  output is ASCII-safe.

---

## 6. Component inventory (new `ui.py`)

| Component | Purpose |
|---|---|
| `glyph(name)` | cp1252-safe symbol set |
| `StatusBar` | breadcrumb + scope + running + findings + model |
| `Breadcrumb(parts)` | top-left path, 1-level click/type jump |
| `Chip(label, tone)` | `ok`/`err`/`warn`/`info`/`muted` small tag |
| `fuzzy(items, query)` | scored fuzzy match + rich highlight |
| `List` | flat selectable list (↑↓/j/k, type-to-filter) |
| `PhaseStream` | spinner→done row per agent/step (3.5) |
| `FindingsCards(findings)` | severity-grouped card list (3.6) |
| `LiveRegion(cells)` | 3-column dashboard region with fold/stack |
| `EmptyState(text, hint)` | consistent `(none)` / no-match |
| `KeyMap(keys)` | footer hint row (from 4.1 per screen) |
| `Palette()` | full-screen fuzzy jump (3.2) |

Dependencies: rich only (already a dep). No new packages. `config_ui` already
demonstrates the prompt_toolkit full-screen pattern the Palette reuses.

---

## 7. Implementation plan (phased, tests green at every step)

**P0 — Foundation (`ui.py`)** (no visual change, all tests stay green)
- Token map + `glyph()` kit + `StatusBar` + `Chip` + `EmptyState`.
- Refactor `core.py` / `cli.py` / `prompt.py` / `config_ui.py` to consume tokens.
- Tests: glyph fallback on cp1252, token wiring, StatusBar string, component unit tests.

**P1 — Kill the tree** (biggest UX win)
- `List` + `fuzzy` components; replace the home category grid with the flat
  catalog + breadcrumb; keep numbers working.
- `Palette` (Ctrl-P / `//`) over the one flat index.
- Tests: palette index completeness (all tools+tags+commands), fuzzy ordering,
  list keys, Esc/grammar exits.

**P2 — Live dashboard home**
- `LiveRegion` + engagement strip on home using existing `session`/`engagement`
  data; findings badge; scope tint.
- Narrow-terminal fold/stack behavior.
- Tests: region folds at width thresholds (monkeypatch `_cols`), badge counts,
  out-of-scope spot state.

**P3 — Agent console polish**
- `PhaseStream` for `/mythos` and `/goal`; live findings summary card.
- `FindingsCards` + report screen (`/report`, `/engagements`).
- Tests: phase state transitions, findings grouping, markdown render.

**P4 — Robustness & docs**
- Light/dark, non-TTY degradation pass, empty states, 60-col audit.
- README + HOW-TO-USE: replace ASCII screenshots with the new screens; add the
  keyboard map; document `//` and `/report`.

Each phase is shippable alone; P1 is the highest value, P2 the most visible.

---

## 8. Success criteria

- Reach any tool from home in **≤ 2 keystrokes + Enter** (was: 3 menu descents).
- No screen reachable where the user cannot immediately see where they are
  (breadcrumb) and what is running (status strip).
- **Zero** new Unicode crashes on Windows cp1252 terminals (glyph kit enforced).
- Full test suite green at every phase; `make check` on CI (Linux) and Windows.
- The `/ @ text` grammar works on **every** screen, including palette and config.
- Mythos/goal runs render live progress + a running findings total, and land in
  the engagement workspace with one-key access.

## 9. Open questions for review

1. **Keep numbers as a navigation fallback** in the flat catalog (muscle memory)
   or drop them? (Spec assumes keep.)
2. **Engagement creation UX**: auto-create + name on first `/mythos`/`/goal`
   (current headless default) or an explicit `/new` flow? (Spec assumes auto.)
3. **Emoji purge**: category emoji removed in favor of kit symbols — is the loss
   of personality acceptable for cross-terminal consistency? (Spec assumes yes.)
4. **`ui.dark` default**: dark (recommended, current look) vs follow terminal.
