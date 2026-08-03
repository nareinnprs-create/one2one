"""Tests for the skill-feed sync (continuous intel intake / Item 1)."""
import re

from one2one import skill_feed
from one2one.agents.evolution import Evolution, PatchGate
from one2one.skill_feed import (
    SEED_FEED,
    _candidate_hash,
    _to_patch,
    all_candidates,
    sync,
    user_candidates,
)

# ── seed bank is well-formed ──────────────────────────────────────────────────

def test_seed_entries_are_complete():
    assert SEED_FEED, "seed bank must not be empty"
    for e in SEED_FEED:
        assert e["agent"], "every seed entry needs a worker callsign"
        assert e["kind"] in ("signature", "intel", "builtin", "workflow")
        assert e.get("label") or e.get("tool") or e.get("name"), \
            "needs label or tool or name"
        if e["kind"] in ("signature", "intel"):
            re.compile(e["pattern"])          # patterns must compile
        if e["kind"] == "signature":
            assert e.get("vuln_class"), "signature needs a vuln_class"
            assert e.get("confidence") in ("plausible", "theoretical")
        if e["kind"] == "workflow":
            assert e.get("steps"), "workflow needs steps"


def test_seed_callsigns_are_tier1_workers():
    from one2one.agents import roster
    for e in SEED_FEED:
        assert e["agent"] in roster.WORKERS, e["agent"]


# ── candidate hashing + dedupe ────────────────────────────────────────────────

def test_candidate_hash_is_stable_and_distinct():
    a = dict(SEED_FEED[0])
    assert _candidate_hash(a) == _candidate_hash(dict(a))
    b = {**a, "pattern": a["pattern"] + "x"}
    assert _candidate_hash(a) != _candidate_hash(b)


def test_all_candidates_deduplicates(tmp_path):
    feed = tmp_path / "dup.yaml"
    feed.write_text(_FIXED_FEED, encoding="utf-8")
    entries = all_candidates(feeds_dir=tmp_path)
    labels = [e.get("label") or e.get("tool") for e in entries]
    assert labels.count("Dup token") == 1


# ── user feeds ───────────────────────────────────────────────────────────────

def test_user_candidates_loaded_with_source(tmp_path):
    tmp_path.joinpath("my.yaml").write_text(
        "candidates:\n"
        "  - agent: VAULT\n"
        "    kind: signature\n"
        "    vuln_class: hardcoded-secret\n"
        "    label: My custom token\n"
        "    pattern: 'mysecret-[0-9]+'\n"
        "    confidence: plausible\n", encoding="utf-8")
    got = user_candidates(tmp_path)
    assert len(got) == 1
    assert got[0]["from"] == "my.yaml"
    assert got[0]["label"] == "My custom token"


def test_broken_user_feed_is_skipped(tmp_path):
    tmp_path.joinpath("bad.yaml").write_text(": this: is: not: yaml [", encoding="utf-8")
    assert user_candidates(tmp_path) == []


# ── sync through the real gate ────────────────────────────────────────────────

def test_sync_proposes_and_applies(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    state = tmp_path / "feed-state.json"
    report = sync(evo, all_candidates(include_seed=False, feeds_dir=tmp_path),
                  feed_state_path=state)
    assert report["proposed"] == 0          # no candidates -> nothing to do
    assert state.read_text(encoding="utf-8")

    entries = all_candidates(include_seed=True, feeds_dir=tmp_path)
    report = sync(evo, entries, feed_state_path=state)
    assert report["proposed"] == len(entries)
    assert report["applied"] == len(entries)     # seed bank passes the gate
    assert report["rejected"] == 0

    again = sync(evo, entries, feed_state_path=state)
    assert again["already"] == len(entries)      # idempotent re-run
    assert again["proposed"] == 0


def test_sync_records_real_patches(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    sync(evo, [SEED_FEED[0]], feed_state_path=tmp_path / "feed-state.json")
    live = [s[1] for s in _mirror_signatures()]
    assert "OpenAI API key" in live          # runtime overlay landed


def test_changed_candidate_is_reproposed(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    entry = {**SEED_FEED[0], "pattern": r"\bfoo-123\b"}
    sync(evo, [entry], feed_state_path=tmp_path / "feed-state.json")
    again = sync(evo, [{**entry, "pattern": r"\bbar-456\b"}],
                 feed_state_path=tmp_path / "feed-state.json")
    assert again["already"] == 0
    assert again["proposed"] == 1


# ── translation ───────────────────────────────────────────────────────────────

def test_to_patch_kind_mapping(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    sig = _to_patch(SEED_FEED[0], evo)
    assert sig.kind == "add-signature"
    assert sig.payload[0] == SEED_FEED[0]["vuln_class"]

    intel = next(e for e in SEED_FEED if e["kind"] == "intel")
    assert _to_patch(intel, evo).kind == "add-intel"

    builtin = next(e for e in SEED_FEED if e["kind"] == "builtin")
    assert _to_patch(builtin, evo).kind == "add-builtin"

    wf = next(e for e in SEED_FEED if e["kind"] == "workflow")
    patch = _to_patch(wf, evo)
    assert patch.kind == "add-workflow"
    assert patch.payload[0] == wf["name"]


def test_to_patch_rejects_unknown_kind(tmp_path):
    evo = Evolution(lessons_path=tmp_path / "lessons.json", gate=PatchGate())
    assert _to_patch({"agent": "VAULT", "kind": "mind-control"}, evo) is None


def test_demo_runs():
    skill_feed.demo()          # smoke: no crash, prints the bank


# ── helpers ───────────────────────────────────────────────────────────────────

_FIXED_FEED = """candidates:
  - agent: VAULT
    kind: signature
    vuln_class: hardcoded-secret
    label: Dup token
    pattern: 'dup-tok-[0-9]+'
    confidence: plausible
  - agent: VAULT
    kind: signature
    vuln_class: hardcoded-secret
    label: Dup token
    pattern: 'dup-tok-[0-9]+'
    confidence: plausible
"""


def _mirror_signatures():
    from one2one.agents.workers import WORKER_CLASSES
    for cls in WORKER_CLASSES:
        if cls.CALLSIGN == "MIRROR":
            return cls.SIGNATURES
    raise AssertionError("MIRROR worker not found")
