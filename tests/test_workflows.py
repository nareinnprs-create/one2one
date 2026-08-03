"""Tests for workflow playbooks — multi-worker chains (Item 3)."""
from pathlib import Path

import pytest

from one2one.agents.evolution import Evolution, PatchGate
from one2one.agents.workflows import WORKFLOW_FILE, WorkflowRegistry, load


def _steps():
    return [
        ("EYRIE", "nmap -sV {target}", "service versions"),
        ("CARTO", "dnsrecon -d {target} -t std", "dns enumeration"),
    ]


# ── registry basics ───────────────────────────────────────────────────────────

def test_register_get_and_roundtrip(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    wf = reg.register("recon-chain", _steps(), source="seed")
    assert wf.name == "recon-chain"
    assert len(wf.steps) == 2
    assert reg.get("recon-chain").source == "seed"
    loaded = WorkflowRegistry(tmp_path / "workflows.json")
    assert loaded.names() == ["recon-chain"]
    assert loaded.get("recon-chain").steps[0][0] == "EYRIE"


def test_register_dedup_by_name(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    reg.register("recon-chain", _steps(), source="seed")
    wf2 = reg.register("recon-chain", [("EYRIE", "nmap -sV {target}", "x")],
                       source="patch-2")
    assert len(reg.all()) == 1
    assert wf2.source == "patch-2"            # refreshed in place
    assert reg.get("recon-chain").steps[0][2] == "x"


def test_register_rejects_empty_name(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    with pytest.raises(ValueError):
        reg.register("   ", _steps())


def test_load_tolerates_corrupt(tmp_path):
    p = tmp_path / "workflows.json"
    p.write_text("{ nope [", encoding="utf-8")
    assert WorkflowRegistry(p).all() == []
    assert load(tmp_path / "missing.json").all() == []


# ── validation (the workflow's "regression") ─────────────────────────────────

def test_validate_ok_for_real_workers(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    wf = reg.register("recon-chain", _steps())
    assert reg.validate(wf) == []


def test_validate_flags_unknown_worker_and_empty_template(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    wf = reg.register("bad", [
        ("NOPE", "nmap {target}", "phantom worker"),
        ("EYRIE", "", "no template"),
    ])
    issues = reg.validate(wf)
    assert len(issues) == 2
    assert any("unknown worker" in i for i in issues)
    assert any("empty argv" in i for i in issues)


# ── execution ─────────────────────────────────────────────────────────────────

def test_run_combines_worker_reports(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    reg.register("recon-chain", _steps())

    def runner(argv, timeout):
        return "Nmap scan report for 10.0.0.1\n80/tcp open  http\n"

    out = reg.run("recon-chain", "10.0.0.1", runner=runner)
    assert out["name"] == "recon-chain"
    assert out["executed"] is True
    assert out["errors"] == []
    assert any(i["label"] == "open_port" for i in out["intel"])


def test_run_requires_known_workflow_and_target(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    with pytest.raises(KeyError):
        reg.run("ghost-chain", "example.com")
    reg.register("recon-chain", _steps())
    out = reg.run("recon-chain", "")
    assert out["executed"] is False
    assert "no target" in out["errors"][0]


def test_run_invalid_workflow_refuses(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    reg.register("bad", [("NOPE", "nmap {target}", "phantom")])
    out = reg.run("bad", "example.com")
    assert out["executed"] is False
    assert out["errors"]


# ── evolution gate integration ────────────────────────────────────────────────

def test_add_workflow_patch_approved_and_registered(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    patch = evo.propose("EYRIE", "add-workflow",
                        ("recon-chain", _steps()),
                        "seed feed playbook")
    approved = evo.approve(patch)
    assert approved.status == "active"
    assert approved.note.startswith("workflow 'recon-chain' registered")
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    assert reg.get("recon-chain") is not None
    assert reg.get("recon-chain").source == patch.id


def test_add_workflow_invalid_is_killed_at_gate(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    patch = evo.propose("EYRIE", "add-workflow",
                        ("phantom", [("NOPE", "nmap {target}", "x")]),
                        "bad playbook")
    approved = evo.approve(patch)
    assert approved.status == "killed"
    assert "refused" in approved.note


def test_propose_rejects_workflow_from_nonworker(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    with pytest.raises(ValueError):
        evo.propose("COMMANDER", "add-workflow", ("x", []), "no")


# ── module surface ────────────────────────────────────────────────────────────

def test_workflow_file_points_at_user_config():
    assert Path(WORKFLOW_FILE).name == "workflows.json"


def test_describe_renders_steps(tmp_path):
    reg = WorkflowRegistry(tmp_path / "workflows.json")
    wf = reg.register("recon-chain", _steps())
    assert "EYRIE: service versions" in wf.describe()


def test_demo_runs():
    import one2one.agents.workflows as w
    w.demo()
