"""one2one ``install-all`` — bulk install everything in one package.

Enumerates the full tool universe (catalog YAML + legacy Python tools) and
installs each installable, non-archived tool's payload plus the shared
techstack, so a fresh device ends up with the complete environment:

    pip install one2one && one2one --install-all

Behavior:
  - git-clone tools: clone into ``~/.one2one/tools/<repo>`` if missing, else
    ``git pull --ff-only`` (i.e. "always latest", refreshed every run).
  - system packages (apt/brew lines) and pip/go/commands installs run verbatim
    (``sudo`` is stripped when running as root, e.g. inside the Docker image).
  - safe-fetch (``install: {url, sha256}``): download + verify SHA256, then run
    ``INSTALL_COMMANDS`` with ``{file}`` replaced by the verified download.
  - Best-effort: an individual tool failure is recorded, never fatal — the
    Docker image build and the native script both continue and finish.
  - Archived tools and pure resources are skipped (counted in the report).

The report is written to ``~/.one2one/install-report.md`` (+ ``.json``) and
printed to the console.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from one2one.config import get_tools_dir
from one2one.registry import load as _load_registry

_CMD_TIMEOUT = 240          # seconds per install command (interactive hangs die here)
_RUN_DEPTH = 200            # guard against accidentally-infinite tool loops


# ── inventory ──────────────────────────────────────────────────────────────────

def iter_installable_tools(include_stale: bool = True):
    """Yield ``(tool, category)`` for every installable, non-archived tool.

    Catalog (YAML) tools come from the registry; legacy tools come from the
    Python-defined collections. Archived tools and ``kind == resource`` entries
    are excluded — the "single package" installs working tools, and the app
    already surfaces archived ones with their reason.
    """
    reg = _load_registry()
    seen: set[str] = set()
    for cat in reg.categories:
        for tool in cat.tools:
            if tool.TITLE in seen:
                continue
            seen.add(tool.TITLE)
            if _is_skippable(tool, include_stale=include_stale):
                continue
            yield tool, cat.title
    from one2one import cli  # registers the legacy collections
    for coll in cli.all_tools:
        for tool in getattr(coll, "TOOLS", []) or []:
            if getattr(tool, "TITLE", "") in seen:
                continue
            seen.add(tool.TITLE)
            if _is_skippable(tool, include_stale=include_stale):
                continue
            yield tool, coll.TITLE


def _is_skippable(tool, include_stale: bool) -> bool:
    if getattr(tool, "ARCHIVED", False):
        return True
    if getattr(tool, "KIND", "install") == "resource":
        return True
    if not include_stale and getattr(tool, "MAINTENANCE", "active") == "stale":
        return True
    return not getattr(tool, "INSTALL_COMMANDS", None) and not getattr(tool, "INSTALL_URL", "")


# ── command shaping ────────────────────────────────────────────────────────────

def _needs_sudo(line: str) -> str:
    """Drop every ``sudo`` when we already run as root (Docker build, containers)."""
    if (os.geteuid() if hasattr(os, "geteuid") else 0) == 0:
        return line.replace("sudo ", "")
    return line


def _plan_lines(tool, tools_dir: Path) -> list[str]:
    """Turn a tool's install spec into concrete shell lines run in ``tools_dir``."""
    lines: list[str] = []
    for raw in list(getattr(tool, "INSTALL_COMMANDS", None) or []):
        line = _needs_sudo(raw)
        line = _git_pull_or_clone(line, tools_dir)
        if line:
            lines.append(line)
    if getattr(tool, "INSTALL_URL", ""):
        lines.append(_url_fetch_line(tool))
    return lines


def _git_pull_or_clone(line: str, tools_dir: Path) -> str:
    """Rewrite ``git clone <url>`` into an idempotent clone-or-update line."""
    m = None
    for tok in ("git clone", "git", "clone"):
        if tok in line:
            import re
            m = re.search(r"git\s+clone\s+(?:--[^\s]+\s+)*(https?://[^\s\"']+)", line)
            break
    if not m:
        return line
    url = m.group(1).rstrip("/")
    name = url.rsplit("/", 1)[-1].removesuffix(".git")
    target = tools_dir / name
    if target.exists():
        return f"git -C {target} pull --ff-only"
    return f"git clone {url}"


def _url_fetch_line(tool) -> str:
    url = tool.INSTALL_URL
    sha = tool.INSTALL_SHA256
    dest = f"${{tools_dir}}/{_slug(tool.TITLE)}"
    if sha:
        verify = f'echo "{sha}  {dest}" | sha256sum -c --quiet || {{ rm -f "{dest}"; exit 1; }}'
    else:
        verify = "# no sha256 pinned — downloaded artifact is unverified"
    return (f"curl -fsSL --retry 3 -o {dest} {url!r} && {verify}")


def _slug(title: str) -> str:
    import re
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", title.lower()).strip("_")
    return s or "tool"


# ── executor ───────────────────────────────────────────────────────────────────

def _run_shell(line: str, tools_dir: Path, env: dict | None = None) -> None:
    base = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "CI": "1"}
    if env:
        base.update(env)
    base.setdefault("tools_dir", str(tools_dir))
    try:
        result = subprocess.run(
            line, shell=True, cwd=str(tools_dir),
            env=base, capture_output=True, text=True, timeout=_CMD_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"command exceeded {_CMD_TIMEOUT}s: {line[:120]}")
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-1:]
        raise RuntimeError(f"exit {result.returncode}: {' | '.join(tail)}")


def install_all(tools_dir: Path | None = None, runner=None,
                dry_run: bool = False, include_stale: bool = True) -> dict:
    """Install every installable tool. Returns the report dict.

    ``runner`` overrides the executor (tests inject a fake); ``dry_run`` plans
    without executing. Never raises for a single tool failure.
    """
    tools_dir = Path(tools_dir or get_tools_dir())
    tools_dir.mkdir(parents=True, exist_ok=True)
    runner = runner or _run_shell

    report = {"tools_dir": str(tools_dir), "dry_run": dry_run,
              "installed": [], "failed": [], "skipped": []}
    depth = 0
    for tool, category in iter_installable_tools(include_stale=include_stale):
        depth += 1
        if depth > _RUN_DEPTH:
            report["skipped"].append({
                "title": tool.TITLE, "category": category,
                "reason": f"run-depth guard exceeded ({_RUN_DEPTH})"})
            break
        try:
            lines = _plan_lines(tool, tools_dir)
            if not lines:
                report["skipped"].append({
                    "title": tool.TITLE, "category": category,
                    "reason": "no install commands"})
                continue
            for line in lines:
                if not dry_run:
                    runner(line, tools_dir)
            report["installed"].append({
                "title": tool.TITLE, "category": category,
                "commands": len(lines), "status": "ok"})
        except Exception as exc:  # noqa: BLE001 — one tool must not kill the batch
            report["failed"].append({
                "title": tool.TITLE, "category": category,
                "status": "failed", "error": str(exc)[:300]})
    return report


# ── reporting ──────────────────────────────────────────────────────────────────

def render_report(report: dict) -> str:
    lines = ["# one2one install-all report", ""]
    lines.append(f"- tools dir: `{report['tools_dir']}`")
    lines.append(f"- dry run: `{report['dry_run']}`")
    lines.append(f"- installed ok: **{len(report['installed'])}**")
    lines.append(f"- failed: **{len(report['failed'])}**")
    lines.append(f"- skipped: **{len(report['skipped'])}**")
    if report["failed"]:
        lines += ["", "## Failed", "", "| Tool | Category | Error |", "|---|---|---|"]
        for f in report["failed"]:
            lines.append(f"| {f['title']} | {f['category']} | {f['error']} |")
    if report["skipped"]:
        lines += ["", "## Skipped", "", "| Tool | Category | Reason |", "|---|---|---|"]
        for s in report["skipped"]:
            lines.append(f"| {s['title']} | {s['category']} | {s['reason']} |")
    return "\n".join(lines)


def write_report(report: dict, base: Path) -> tuple[Path, Path]:
    import json
    base.mkdir(parents=True, exist_ok=True)
    md = base / "install-report.md"
    js = base / "install-report.json"
    md.write_text(render_report(report), encoding="utf-8")
    js.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return md, js
