"""Shared input surface — ONE line editor + ONE grammar for every prompt.

Both the home REPL (``repl.run_repl``) and every nested tool menu
(``core.One2OneTool.show_options`` / ``core.ask``) route through here, so line
editing, shared ↑↓ history, and the ``/``/``@`` grammar work everywhere. This
kills the arrow-key escape-leak that hit nested menus (they read via builtin
``input()`` with no readline; see the spec).

Leaf-ish module: it REUSES ``repl``'s completer/resolver/mention-opener and
``cli``'s data helpers via lazy in-function imports (no move, no import cycle —
mirrors how ``repl`` already lazy-imports ``cli``).
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from functools import lru_cache

# Dispatch signals — module-level unique objects so callers compare by identity
# and dispatch stays trivially testable offline.
CONTINUE = object()
QUIT = object()
BACK = object()

# tmux window count for the status line — TTL-cached so idle re-renders (every
# refresh_interval seconds) don't spawn a tmux process each time.
_RUNNING_CACHE = {"at": 0.0, "n": 0}


@dataclass(frozen=True)
class Open:
    """A ``@tool`` / ``@tag:`` mention the caller should open."""
    mention: str


@dataclass(frozen=True)
class PromptCtx:
    mode: str            # "home" | "tool"
    tool: object = None  # One2OneTool | None


# Set True by cli.main() under --classic / headless; forces the readline path so
# nested tool menus honour --classic too (not just the REPL).
FORCE_CLASSIC = False


def _cols(default: int = 80) -> int:
    import shutil
    return max(4, shutil.get_terminal_size((default, 24)).columns)


# Rounded input frame (Claude-cli-adjacent): pure ─ fill so the width never
# drifts on emoji in the status line, and both corners land at cols 0 / w-1 —
# aligning with the ` │` right rail that rprompt right-anchors on the input row.
def _box_top(w: int) -> str:    return "╭" + "─" * (w - 2) + "╮"
def _box_bottom(w: int) -> str: return "╰" + "─" * (w - 2) + "╯"


@lru_cache(maxsize=1)
def _catalog():
    """(tools_by_title, tag_index), built once from cli. Cached — the catalog is
    static for a session."""
    import one2one.cli as cli

    tag_index = cli._get_all_tags()
    tools_by_title = {t.TITLE: t for t, _ in cli._collect_all_tools() if t.TITLE}
    return tools_by_title, tag_index


def show_all_tags(tag_index):
    """Thin passthrough to repl.show_all_tags (kept as an attribute so tests can
    monkeypatch prompt.show_all_tags)."""
    from one2one import repl
    repl.show_all_tags(tag_index)


def open_mention(mention, tools_by_title=None, tag_index=None):
    """Resolve + open a ``@tool`` / ``@tag:`` mention. Reuses repl._open_mention.
    Args default to the cached catalog; injectable for tests."""
    from one2one import repl
    if tools_by_title is None or tag_index is None:
        tools_by_title, tag_index = _catalog()
    repl._open_mention(mention, tag_index, tools_by_title)


def status(ctx):
    """Line-2 content: breadcrumb · N tools · N tags · key hints. Single source
    for both the prompt_toolkit bottom toolbar and the classic-fallback banner."""
    tools_by_title, tag_index = _catalog()
    crumb = "home" if ctx.mode == "home" else getattr(ctx.tool, "TITLE", "tool")
    line = (
        f"{crumb} · {len(tools_by_title)} tools · {len(tag_index)} tags "
        "· @ tools  / cmds  ↑↓ history"
    )
    running = _running_count()
    if running:
        line += f" · ▶ {running} running"
    return line


def _running_count():
    """tmux window count for the status line, cached ~1.5s (incl. the enabled() check)."""
    from one2one import session
    now = time.monotonic()
    if now - _RUNNING_CACHE["at"] > 1.5:
        _RUNNING_CACHE["n"] = session.count() if session.enabled() else 0
        _RUNNING_CACHE["at"] = now
    return _RUNNING_CACHE["n"]


def dispatch(raw, ctx):
    """The ONE grammar. Returns CONTINUE | QUIT | BACK | Open. Never handles
    numbers — the menu owns its own numeric options (see core.show_options)."""
    import one2one.cli as cli

    raw = raw.strip()
    if not raw:
        return CONTINUE

    if raw.startswith("@"):
        return Open(raw)

    if raw.startswith("/"):
        parts = raw[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("quit", "q", "exit"):
            return QUIT
        if cmd in ("back", "b"):
            return BACK
        if cmd in ("help", "?", "h"):
            cli.show_help()
        elif cmd == "tags":
            _, tag_index = _catalog()
            show_all_tags(tag_index)
        elif cmd == "search":
            cli.search_tools(arg or None)
        elif cmd in ("run", "open"):
            return _run_command(arg, ctx)
        elif cmd in ("panes", "jobs"):
            from one2one import session
            _print_panes(session.windows())
        elif cmd == "attach":
            from one2one import session
            session.attach()
        elif cmd == "kill":
            from one2one import session
            if not arg:
                cli.console.print("[dim]Usage: /kill <label|all>[/dim]")
            else:
                session.kill(arg)
                cli.console.print(f"[dim]killed {arg}[/dim]")
        elif cmd == "config":
            cli.config_command(arg)
        elif cmd in ("ai", "recommend", "r"):
            cli.recommend_tools(arg or None)
        elif cmd == "skill":
            from one2one import repl
            repl.show_skill()
        elif cmd == "goal":
            from one2one import ai_goal
            ai_goal.run(arg, ctx)
        elif cmd in ("mythos", "redteam", "rt"):
            from one2one import mythos
            mythos.run(arg, ctx)
        elif cmd in ("find", "discover"):
            from one2one import discover
            discover.run(arg, ctx)
        elif cmd in ("agents", "stack"):
            _show_agents(cmd == "stack")
        elif cmd in ("clear", "cls"):
            _clear(ctx)
        elif cmd in ("uninstall", "remove"):
            _open_manager("uninstall")
        elif cmd == "update":
            _open_manager("update")
        else:
            cli.console.print(f"[dim]Unknown command /{cmd}. Try /help.[/dim]")
        return CONTINUE

    # Bare shell muscle-memory verbs work without a slash (home only — tool menus
    # intercept quit/exit before dispatch; see core.show_options).
    low = raw.lower()
    if low in ("quit", "exit", "q"):
        return QUIT
    if low in ("clear", "cls"):
        _clear(ctx)
        return CONTINUE

    # Otherwise bare text is context-aware natural language.
    if ctx.mode == "tool" and ctx.tool is not None:
        ctx.tool._ai_command(raw)      # AI2 for this tool
    else:
        cli.recommend_tools(raw)       # AI1 recommend at home
    return CONTINUE


def _clear(ctx):
    """Clear the screen; at home reprint the banner so the console stays branded.
    In a tool menu the caller's loop redraws its own table, so a bare clear suffices."""
    from one2one.core import clear_screen
    clear_screen()
    if ctx.mode == "home":
        import one2one.cli as cli
        cli.console.print(cli._build_header())


def _show_agents(show_picture: bool = False) -> None:
    """/agents — print the 37-agent stack; /stack — print the live mission ledger."""
    from rich.panel import Panel
    from rich.table import Table

    from one2one import agents
    from one2one.agents.ledger import LEDGER_FILE, MissionLedger
    import one2one.cli as cli

    cli.console.print()
    if show_picture:
        ledger = MissionLedger.load(LEDGER_FILE)
        pic = ledger.picture()
        summary = " · ".join(f"{k}: {v}" for k, v in pic.items() if k != "total")
        cli.console.print(Panel(
            f"[bold]{pic['total']}[/bold] missions · {summary}",
            title="[bold magenta]COMMANDER — live battle picture[/bold magenta]",
            border_style="magenta"))
        table = Table(box=None)
        table.add_column("id", style="dim")
        table.add_column("worker", style="bold cyan")
        table.add_column("wing", style="magenta")
        table.add_column("target", style="green")
        table.add_column("status", style="yellow")
        table.add_column("created", style="dim")
        for m in ledger.recent(15):
            table.add_row(m.id, m.worker, m.wing or "-", m.target or "-",
                          m.status, m.created[:19])
        cli.console.print(table)
        return
    table = Table(title="[bold]ONE2ONE AGENT STACK — 37 agents[/bold]", box=None)
    table.add_column("agent", style="bold cyan")
    table.add_column("tier", style="magenta")
    table.add_column("wing", style="yellow")
    table.add_column("responsibility")
    for row in agents.get_roster():
        table.add_row(row["name"], f"T{row['tier']}",
                      row["wing_name"] if row["wing"] else "-",
                      row["responsibility"])
    cli.console.print(table)


def _open_manager(which):
    """Open the Update/Uninstall tool (tools/tool_manager.py) directly from the
    console, so `/uninstall` and `/update` reach it without hunting the last menu
    item. `which` is 'uninstall' or 'update'; reuses the existing tool, no new logic."""
    from one2one.tools.tool_manager import UninstallTool, UpdateTool
    tool = UninstallTool() if which == "uninstall" else UpdateTool()
    tool.show_options()


def _slug(title):
    """Turn a tool title into a tmux window label: lowercase, non-alnum → '-'."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "tool"


def _usage_banner(tool):
    """One-line pane header from the tool's USAGE cheatsheet, or None.

    USAGE is ``[(task, command), …]`` (see core.One2OneTool.USAGE); use the
    first task label, falling back to its command.
    """
    usage = getattr(tool, "USAGE", None)
    if usage:
        task, cmd = usage[0]
        return task or cmd
    return None


def _print_panes(windows):
    from one2one.core import console
    if not windows:
        console.print("[dim]No background panes.[/dim]")
        return
    for idx, name in windows:
        console.print(f"  [cyan]{name}[/cyan] [dim](window {idx})[/dim]")


def _run_command(arg, ctx):
    """``/run [tool] [args…] [&]`` — trailing ``&`` backgrounds via tmux (when
    enabled); otherwise opens the tool's foreground menu (unchanged slice 2a)."""
    import one2one.cli as cli
    from one2one import session

    arg = arg.strip()
    bg = arg.endswith("&")
    if bg:
        arg = arg[:-1].strip()
    if not arg:
        return Open("@")  # bare "/run" — let the resolver print "no tool"

    first = arg.split()[0]
    if bg and session.enabled():
        from one2one import config, repl
        tools_by_title, _ = _catalog()
        tool = repl._resolve(first, tools_by_title)
        if tool is None:
            cli.console.print(f"[dim]No tool matches '{first}'.[/dim]")
            return CONTINUE

        cwd = tool._get_tool_dir() or str(config.get_tools_dir())
        command = arg if arg != first else None  # bare tool name → prepared shell only
        resolved = session.run(_slug(tool.TITLE), cwd, command=command,
                                banner=_usage_banner(tool))
        cli.console.print(
            f"[green]▶ started '{resolved}' in background — /attach to view[/green]")
        return CONTINUE

    if bg:  # & requested but unavailable
        cli.console.print(
            "[dim]tmux not available (or background off) — opening inline. "
            "See /config.[/dim]")
    return Open("@" + first)


def _message(ctx):
    if ctx.mode == "tool":
        return f"{getattr(ctx.tool, 'TITLE', 'tool')} ❯ "
    return "one2one ❯ "


def _use_pt():
    """prompt_toolkit only on an interactive TTY and not forced classic."""
    if FORCE_CLASSIC:
        return False
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    try:
        import prompt_toolkit  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _session():
    """One shared PromptSession → one ↑↓ history for the whole app. History is
    persisted to ~/.one2one/history so past commands survive across runs."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.output import DummyOutput
    from prompt_toolkit.styles import Style
    from one2one import repl
    from one2one.constants import THEME_HEX, USER_HISTORY_FILE

    tools_by_title, tag_index = _catalog()
    _ht = repl.HTCompleter(tools_by_title.keys(), tag_index.keys())

    class _PTCompleter(Completer):
        def get_completions(self, document, complete_event):
            yield from _ht.get_completions(document, complete_event)

    USER_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        completer=_PTCompleter(),
        complete_while_typing=True,
        history=FileHistory(str(USER_HISTORY_FILE)),
        style=Style.from_dict({
            "bottom-toolbar": "noreverse",   # no bar fill — frame/hint set their own colours
            "frame": "#4a4a6a",              # rounded box rails + corners (neutral, subtle)
            "hint": "#b0b0d0",               # status line under the box
            "prompt": f"bold {THEME_HEX}",   # follows the configured theme
        }),
    )
    try:
        return PromptSession(**kwargs)
    except Exception as exc:
        if sys.platform != "win32":
            raise
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
        if not isinstance(exc, NoConsoleScreenBufferError):
            raise
        # Windows with no real console (pytest, piped stdin): prompt_toolkit's
        # default Win32Output can't query the console. Fall back to a
        # discard-output session — same completer/history wiring, no terminal.
        return PromptSession(output=DummyOutput(), **kwargs)


def read_line(ctx):
    """Read one line of grammar-aware input: a rule-topped prompt on an
    interactive TTY, readline-backed off-TTY/classic. Both EOF (Ctrl-D) and
    Ctrl-C exit — the latter propagates to cli.main's handler ("Exiting…")."""
    if _use_pt():
        from prompt_toolkit.formatted_text import FormattedText
        session = _session()

        def message():                       # callable → reflows the top border on resize
            w = _cols()
            return FormattedText([
                ("class:frame", _box_top(w) + "\n"),
                ("class:frame", "│ "),
                ("class:prompt", _message(ctx)),
            ])

        def toolbar():                        # bottom rail + status hints, below the box
            return FormattedText([
                ("class:frame", _box_bottom(_cols()) + "\n"),
                ("class:hint", " " + status(ctx)),
            ])

        try:
            return session.prompt(
                message,
                rprompt=FormattedText([("class:frame", " │")]),   # right rail on the input row
                bottom_toolbar=toolbar,
                refresh_interval=2,
            )
        except EOFError:
            raise SystemExit(0)
        # KeyboardInterrupt is intentionally NOT caught: Ctrl-C exits (cli.main).
    # Fallback: readline gives line editing (kills the escape leak) even here.
    from one2one.core import console
    console.print(f"[dim]{status(ctx)}[/dim]")
    return simple(_message(ctx))


def simple(prompt, default=""):
    """Plain readline-backed line read (confirmations / Press-Enter). No grammar,
    no completer. EOF or Ctrl-C → SystemExit(0) (matches the old core.ask)."""
    try:
        import readline  # noqa: F401 (side effect: enables libedit/readline editing)
    except ImportError:
        pass
    from rich.text import Text
    from one2one.core import console

    # Render rich markup in the prompt label, then read via plain input().
    label = Text.from_markup(prompt).plain if "[" in prompt else prompt
    try:
        line = input(label)
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]bye[/dim]")
        raise SystemExit(0)
    return line if line != "" else default


def demo():
    """Self-check: the grammar returns the right signals offline (no TTY, model)."""
    assert dispatch("/quit", PromptCtx("home")) is QUIT
    assert dispatch("/back", PromptCtx("tool")) is BACK
    assert dispatch("@nmap", PromptCtx("home")) == Open("@nmap")
    assert dispatch("   ", PromptCtx("home")) is CONTINUE
    s = status(PromptCtx("home"))
    assert "home" in s and "tools" in s
    # Input frame: both rails span the full width and corners bracket the row.
    for w in (4, 20, 80, 137):
        top, bot = _box_top(w), _box_bottom(w)
        assert len(top) == len(bot) == w, (w, len(top), len(bot))
        assert top[0] == "╭" and top[-1] == "╮"
        assert bot[0] == "╰" and bot[-1] == "╯"
    print("OK — prompt: dispatch signals + status + input frame")


if __name__ == "__main__":
    demo()
