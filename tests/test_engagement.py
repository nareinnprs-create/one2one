import one2one.engagement as engagement
from one2one.engagement import Engagement


def _root(tmp_path, monkeypatch):
    monkeypatch.setattr(engagement, "ENGAGEMENTS_ROOT", tmp_path)


def test_create_and_load_roundtrip(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", targets=["example.com"], scope_in=["*.example.com"])
    e.save()
    assert (tmp_path / "acme" / "engagement.json").exists()
    loaded = engagement.load("acme")
    assert loaded.name == "acme"
    assert loaded.targets == ["example.com"]
    assert loaded.scope_in == ["*.example.com"]


def test_scope_matching(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", scope_in=["*.example.com"], scope_out=["admin.example.com"])
    assert e.in_scope("dev.example.com") is True
    assert e.in_scope("admin.example.com") is False
    assert e.in_scope("evil.test") is False


def test_scope_defaults_to_targets(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", targets=["example.com"])
    assert e.in_scope("example.com") is True


def test_get_or_create_is_idempotent(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    a = engagement.get_or_create("acme", targets=["example.com"])
    b = engagement.get_or_create("acme")
    assert b.targets == ["example.com"]


def test_log_appends(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme")
    e.log("hello")
    assert "hello" in e.log_file.read_text()


def test_to_scope_maps_to_scope_gate(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", scope_in=["*.example.com"],
                          scope_out=["admin.example.com"])
    scope = e.to_scope()
    assert scope.name == "engagement:acme"
    assert scope.allows("dev.example.com") is True
    assert scope.allows("admin.example.com") is False
    assert scope.allows("evil.test") is False
    assert scope.allows("code:./x") is False          # local denied by default


def test_to_scope_local_via_roe(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", scope_in=["*.example.com"],
                          roe={"local": True})
    scope = e.to_scope()
    assert scope.allows("code:./src") is True


def test_roe_and_notes_roundtrip(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", targets=["example.com"],
                          roe={"authorized_actions": "passive+active",
                               "local": False}, notes="Q3 test window")
    loaded = engagement.load("acme")
    assert loaded.roe["authorized_actions"] == "passive+active"
    assert loaded.notes == "Q3 test window"


def test_active_activation(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    engagement.create("a")
    engagement.create("b")
    assert engagement.active().name == "b"      # last created is active
    engagement.activate("a")
    assert engagement.active().name == "a"
    for e in engagement.list_all():
        assert (e.name == "a") == e.active


def test_close_and_list_all(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    engagement.create("acme", targets=["example.com"])
    assert len(engagement.list_all()) == 1
    engagement.close("acme")
    assert engagement.active() is None
    assert engagement.load("acme").active is False


def test_load_tolerates_old_shape(tmp_path, monkeypatch):
    """Engagements saved before ROE fields existed still load (defaults fill in)."""
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", targets=["example.com"])
    (tmp_path / "acme" / "engagement.json").write_text(
        '{"name": "acme", "created": "2026-01-01T00:00:00", '
        '"scope_in": ["*.example.com"], "scope_out": [], "targets": '
        '["example.com"], "runs": []}', encoding="utf-8")
    loaded = engagement.load("acme")
    assert loaded.active is True
    assert loaded.roe == {}
    assert loaded.notes == ""
