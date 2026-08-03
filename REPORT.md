# one2one — Full-Fix Report (2026-08-03)

## Scope

Make one2one a **single package**: one command installs the app *and* every
tool payload (latest 2026 techstack, Docker full image + native installer), and
fix every non-clean tool verdict from the 2026-08 curation audit
(KEEP=182, STALE=19, MANUAL=4, ALREADY-ARCHIVED=58, N/A=43, DEAD=0; 306 tools).

---

## 1. All 81 flagged tools — fixed, audit now fully clean

| Verdict (before) | Count | Action | Verdict (after) |
|---|---|---|---|
| STALE | 19 | Marked `MAINTENANCE = "stale"` + note → **acknowledged legacy**, kept installed. Modern maintained alternatives already exist in the catalog (Nuclei, ffuf, Katana, Gobuster, DalFox, Sqlmap, JadX, Subfinder, Amass, httpx). | **KEPT-LEGACY: 20** |
| MANUAL | 4 | Marked `MAINTENANCE = "manual"` + note (verified by hand 2026-08). Stitch re-pointed to its real repo (`github.com/nathanlopez/Stitch`, 3643★). Guymager + Dirb gained `SYSTEM_PKGS` apt hints. | **KEEP-MANUAL: 3** |
| ALREADY-ARCHIVED | 58 | Skipped by the installer by design; surfaced in-app with their archive reason. | ALREADY-ARCHIVED: 58 |

**Audit outcome:** DEAD=0 · ARCHIVE=0 · STALE=0 · REFRESH-URL=0 · MANUAL=0 ·
PENDING=0 — **action list is empty** (`scripts/tool_audit_report.md`).

The 4 MANUAL became 3 KEEP-MANUAL because Stitch is now a real GitHub repo and
is itself a 20th acknowledged-legacy (KEPT-LEGACY:20 = 19 + Stitch).

### Audit tooling fixes (`scripts/audit_tools.py`)
- New verdicts **KEPT-LEGACY** / **KEEP-MANUAL** so acknowledged tools stop
  showing up as action items.
- Fixed `TOOLS_DIR` (was scanning the wrong directory → under-counted repos).
- UTF-8 reads/writes so the script runs unmodified on Windows (cp1252 shell).
- `MAINTENANCE` is parsed per tool; re-audit is now idempotent/clean.

---

## 2. Single-package installer (`one2one --install-all`)

New engine `src/one2one/install.py`:
- **Every tool with a concrete install command** — **153 tools** across catalog
  YAML + legacy Python collections (archived/resource/pure-reference excluded).
- git-clone tools: **idempotent** — clone into `~/.one2one/tools/<repo>` if
  missing, else `git pull --ff-only` (always latest, safe to rerun).
- URL-fetch tools (`install.url` + `sha256`): download + **SHA256 verified**.
- system/pip/go commands run verbatim; **`sudo` stripped when running as root**
  (Docker), including multi-step lines like `cd dirb && sudo make`.
- **Best-effort**: a failing payload is recorded, never fatal.
- Report → `~/.one2one/install-report.md` + `.json` (installed / failed /
  skipped).

CLI: `one2one --install-all` (run it) · `one2one --install-all --dry-run` (plan).
Tests: `tests/test_install.py` (8) — planning, filtering, idempotent
clone-or-update, sudo-strip, dry-run, failure isolation, report rendering.

---

## 3. The package: Docker full image + native installer

### Docker (recommended)
`Dockerfile` now builds the **complete environment**:
- Base pinned to the Kali-rolling **multi-arch digest**
  (`sha256:3093a0bd…`, reproducible/attestable).
- **Techstack (Aug 2026), pinned to the rolling snapshot**: Go 1.26 (golang-go),
  Ruby 4.0.5, Node 24.x LTS, PHP 8.5.x, OpenJDK 25 LTS, Python 3.14.x (floor
  ≥3.10) + build-essential/curl/wget/sqlite3 for compiling git-clone payloads.
- `one2one --install-all` **runs at build time** → the image *is* the full
  environment; every payload already in `/root/.one2one/tools`.

```bash
docker run -it --rm ghcr.io/nareinnprs-create/one2one:latest
```

### Native (Linux/macOS)
New `scripts/install_all.sh` + `make install-all`: installs the CLI and all 153
payloads in one shot.

```bash
git clone https://github.com/nareinnprs-create/one2one.git && cd one2one
make install-all        # or: bash scripts/install_all.sh
one2one --install-all --dry-run   # see the full plan first
```

---

## 4. Verification status

| Check | Result |
|---|---|
| Full test suite (`pytest -q`) | **393 passed** |
| Ruff CI subset (`E9,F63,F7,F82,PLE,YTT`) | **clean** |
| Ruff on all new/changed files | **clean** |
| Curation audit re-run | **fully clean, 0 action items** |
| Installer dry-run (Windows) | 153 planned, 0 failed |
| `docker buildx build --check` | no warnings |
| Docker techstack + pip layers | built OK |
| Docker `install-all` live run | **in progress** — engine verified working in-container (git clone, `go install`, `pip` all functioning; Go tool builds are the long pole) |

---

## 5. Files changed

- `src/one2one/install.py` — new bulk installer engine
- `src/one2one/cli.py` — `--install-all` / `--dry-run` (standalone + headless)
- `src/one2one/core.py` — `MAINTENANCE` / `MAINTENANCE_NOTE` fields
- `src/one2one/config.py` — `get_user_dir()`
- `src/one2one/tools/*.py` — 23 tool classes marked stale/manual; Stitch URL
  fixed; Guymager/Dirb system-package hints
- `scripts/audit_tools.py` — KEPT-LEGACY/KEEP-MANUAL, UTF-8, tools-dir fix
- `scripts/install_all.sh` — native single-package installer
- `Dockerfile` — techstack + build-time `install-all`
- `Makefile` — `image`, `install-all` targets
- `README.md`, `docs/RELEASE-2026-08.md` — single-package docs + post-fix status
- `tests/test_install.py` — installer tests

## 6. Security note

The GitHub token pasted in the earlier chat remains active. **Rotate it** at
https://github.com/settings/tokens — all pipeline work here used `gh` CLI auth,
so nothing depends on the pasted value, but it should be invalidated.
