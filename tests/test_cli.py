import one2one.cli as one2one
from one2one.tags import TAXONOMY


def test_recommendation_tags_are_taxonomy_valid():
    # Every curated shortcut must map onto the one canonical vocabulary — guards
    # against typos like the old "port-scanner" (should be "port-scan").
    bad = {phrase: [t for t in tags if t not in TAXONOMY]
           for phrase, tags in one2one._RECOMMENDATIONS.items()
           if any(t not in TAXONOMY for t in tags)}
    assert not bad, bad


def test_tag_index_speaks_one_vocabulary_from_real_tags():
    idx = one2one._get_all_tags()
    # The whole index is taxonomy-valid (real tags + taxonomy-valid regex fallback).
    assert set(idx) <= set(TAXONOMY), sorted(set(idx) - set(TAXONOMY))
    # A tagged tool contributes exactly its real TAGS — no regex bleed.
    for tool, cat in one2one._collect_all_tools():
        if getattr(tool, "TAGS", None):
            here = {tg for tg in idx if (tool, cat) in idx[tg]}
            assert here == set(tool.TAGS), (tool.TITLE, here, tool.TAGS)
            break


def test_legacy_overlay_titles_match_real_tools():
    # Overlays apply by exact title — a typo would silently no-op. Guard it.
    import yaml
    import one2one.registry as registry
    f = registry.CATALOG_DIR / "legacy_overlays.yaml"
    entries = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("overlay", [])
    titles = {t.TITLE for t, _ in one2one._collect_all_tools()}
    missing = [e["title"] for e in entries if e["title"] not in titles]
    assert not missing, missing
    assert len(entries) >= 90                       # the curated legacy batch landed


def test_free_text_routes_to_recommend(monkeypatch):
    # NL-first: a plain intent string goes to the AI1 free-text path.
    seen = {}
    monkeypatch.setattr(one2one, "_recommend_freetext",
                        lambda intent: seen.setdefault("intent", intent))
    one2one.recommend_tools("crack a wifi handshake")
    assert seen["intent"] == "crack a wifi handshake"


def test_arg_parser_flags():
    p = one2one._build_arg_parser()
    ns = p.parse_args(["--engagement", "acme", "--targets", "example.com", "--ai-summary"])
    assert ns.engagement == "acme"
    assert ns.targets == "example.com"
    assert ns.pipeline is None        # default
    assert ns.ai_summary is True
    assert ns.report is False

def test_pipeline_runs_against_stored_targets(tmp_path, monkeypatch):
    import one2one.engagement as engagement
    monkeypatch.setattr(engagement, "ENGAGEMENTS_ROOT", tmp_path)
    engagement.create("acme", targets=["example.com"])  # targets already stored
    called = {}
    def fake_run(e, name):
        called["run"] = name
        return []
    monkeypatch.setattr(one2one.orchestrator, "run_pipeline", fake_run)
    monkeypatch.setattr(one2one.report, "generate_report", lambda e: e.report_file)
    args = one2one._build_arg_parser().parse_args(["--engagement", "acme", "--pipeline", "recon"])
    one2one._run_headless(args)
    assert called["run"] == "recon"   # ran with NO --targets

def test_load_targets_inline_vs_file(tmp_path):
    assert one2one._load_targets("example.com") == ["example.com"]
    f = tmp_path / "t.txt"
    f.write_text("a.com\nb.com\n\n")
    assert one2one._load_targets(str(f)) == ["a.com", "b.com"]

def test_run_headless_dispatches(tmp_path, monkeypatch):
    import one2one.engagement as engagement
    monkeypatch.setattr(engagement, "ENGAGEMENTS_ROOT", tmp_path)
    called = {}

    def fake_run(e, name):
        called["run"] = name
        return []
    monkeypatch.setattr(one2one.orchestrator, "run_pipeline", fake_run)

    def fake_report(e):
        called["report"] = True
        return e.report_file
    monkeypatch.setattr(one2one.report, "generate_report", fake_report)

    def fake_summary(e):
        called["summary"] = True
        return "ok"
    monkeypatch.setattr(one2one.ai_summary, "summarize", fake_summary)

    args = one2one._build_arg_parser().parse_args(
        ["--engagement", "acme", "--targets", "example.com", "--ai-summary"])
    one2one._run_headless(args)

    assert called["run"] == "recon"
    assert called["report"] is True
    assert called["summary"] is True
