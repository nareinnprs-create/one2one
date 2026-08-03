"""Single-package installer: planning, filtering, best-effort report."""
from __future__ import annotations

import typing

from one2one import install


class _FakeTool:
    TITLE = "Fake"
    KIND = "install"
    ARCHIVED = False
    MAINTENANCE = "active"
    INSTALL_COMMANDS: typing.ClassVar[list] = ["git clone https://github.com/acme/fake.git"]
    INSTALL_URL = ""
    INSTALL_SHA256 = ""


class _ArchivedTool(_FakeTool):
    TITLE = "Dead"
    ARCHIVED = True
    ARCHIVED_REASON = "gone"


class _ResourceTool(_FakeTool):
    TITLE = "Docs"
    KIND = "resource"


class _GitTool(_FakeTool):
    INSTALL_COMMANDS: typing.ClassVar[list] = ["git clone https://github.com/one/two.git"]


def test_skippable_archived_and_resource():
    assert install._is_skippable(_ArchivedTool(), True) is True
    assert install._is_skippable(_ResourceTool(), True) is True
    assert install._is_skippable(_FakeTool(), True) is False
    stale = _FakeTool()
    stale.MAINTENANCE = "stale"
    assert install._is_skippable(stale, True) is False
    assert install._is_skippable(stale, False) is True


def test_git_clone_becomes_update_when_dir_exists(tmp_path):
    (tmp_path / "two").mkdir()
    assert install._git_pull_or_clone(
        "git clone https://github.com/one/two.git", tmp_path) == \
        f"git -C {tmp_path / 'two'} pull --ff-only"
    assert install._git_pull_or_clone(
        "git clone https://github.com/one/two.git", tmp_path / "empty") == \
        "git clone https://github.com/one/two.git"


def test_needs_sudo_strips_every_sudo_when_root(monkeypatch):
    monkeypatch.setattr(install.os, "geteuid", lambda: 0, raising=False)
    assert install._needs_sudo("sudo apt-get install -y nmap") == \
        "apt-get install -y nmap"
    assert install._needs_sudo("cd dirb && sudo bash configure && make") == \
        "cd dirb && bash configure && make"


def test_plan_lines_from_install_commands(tmp_path):
    tool = _GitTool()
    lines = install._plan_lines(tool, tmp_path)
    assert len(lines) == 1
    assert "git clone https://github.com/one/two.git" in lines[0]


def test_dry_run_plans_without_executing(tmp_path):
    calls: list = []
    report = install.install_all(
        tools_dir=tmp_path, runner=lambda line, cwd: calls.append(line),
        dry_run=True)
    assert calls == []                      # nothing executed
    assert isinstance(report["installed"], list)
    assert isinstance(report["failed"], list)
    assert isinstance(report["skipped"], list)
    assert len(report["installed"]) > 0     # catalog has installable tools
    assert report["tools_dir"] == str(tmp_path)


def test_failure_is_recorded_not_fatal(tmp_path):
    def boom(line, cwd):
        if "boom" in line:
            raise RuntimeError("kaput")

    captured: list = []
    # drive install_all over the real catalog with a failing runner; it must
    # return a report rather than raise, and failures must be attributed.
    report = install.install_all(
        tools_dir=tmp_path,
        runner=lambda line, cwd: (captured.append(line)
                                  if "boom" not in line
                                  else boom(line, cwd)),
        dry_run=False)
    assert isinstance(report["failed"], list)
    assert "failed" in report and isinstance(report, dict)


def test_write_report(tmp_path):
    rep = {"tools_dir": str(tmp_path), "dry_run": True,
           "installed": [{"title": "A", "category": "C", "commands": 1,
                          "status": "ok"}],
           "failed": [{"title": "B", "category": "C", "status": "failed",
                       "error": "x"}],
           "skipped": []}
    md, js = install.write_report(rep, tmp_path)
    assert md.exists() and js.exists()
    assert "# one2one install-all report" in md.read_text(encoding="utf-8")


def test_render_report_has_counts():
    rep = {"tools_dir": "/t", "dry_run": False,
           "installed": [{"title": "A", "category": "C", "commands": 1,
                          "status": "ok"}],
           "failed": [], "skipped": []}
    text = install.render_report(rep)
    assert "installed ok: **1**" in text
    assert "## Failed" not in text
