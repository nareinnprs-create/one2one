# Changelog

All notable changes to **one2one** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/).

## [Unreleased] — single-package milestone (2026-08)

### Added
- **`one2one --install-all`** — one command installs the CLI **and every tool
  payload** (153 tools with concrete install commands). Idempotent
  clone-or-`git pull`, SHA-256-verified downloads, best-effort per tool, report
  at `~/.one2one/install-report.md` (+ `.json`).
- **`one2one --install-all --dry-run`** — print the full plan, install nothing.
- **Docker full image** — build-time install of all 153 payloads on a pinned
  Aug-2026 techstack (Go 1.26, Ruby 4.0, Node 24 LTS, PHP 8.5, OpenJDK 25,
  Python 3.14) over a pinned Kali-rolling digest.
- **Native single-package install** — `make install-all` /
  `scripts/install_all.sh`.
- `MAINTENANCE` field on tools (`stale` / `manual`) so acknowledged-legacy
  tools are curated explicitly instead of flagged forever.

### Changed
- Full 2026-08 curation audit of all 306 catalogued tools (262 unique):
  19 stale + 4 manual tools marked and verified; Stitch re-pointed to its real
  GitHub repo; Guymager/Dirb gained apt install hints. **Audit action list is
  empty.**
- Branding: ownership moved to `nareinnprs-create` across metadata, funding,
  .deb packaging and README sponsor/social links.

## [4.0.0] — 2026-08-03

First release as **one2one** at its new home, shipped to every channel.

### Added
- `/ask` console command.
- PyPI package (`pip install one2one`), `.deb` packaging, GitHub Container
  Registry image, CycloneDX SBOM + Sigstore attestations on every release.
- macOS CI (alongside Ubuntu).

### Changed
- Repo re-home to `github.com/nareinnprs-create/one2one`.
- Legacy pre-1.0 config dir migrates to `~/.one2one` on first run.
- `_split` no longer mangles Windows paths on POSIX hosts.

## [3.0.0]

- Agent-stack milestone: 37-agent command chain with a self-development loop.

## [2.0.0]

- **AI operator console rework** — 215 curated tools across 21 categories, the
  `/find` discovery engine, AI layer (`/ai`, `/goal`), tags and search.

## [1.x]

- Console milestone: rich category menus, install/run helpers.
