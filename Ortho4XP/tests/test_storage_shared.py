"""#2029: one storage scan measured in the background and shared
(``o4_engine.storage_shared``): Settings > Storage opens with it at once."""
from __future__ import annotations

from o4_engine import storage as STORAGE
from o4_engine import storage_shared as SHARED


def _reset(monkeypatch):
    monkeypatch.setattr(SHARED, "_STATE",
                        {"scan": None, "at": 0.0, "running": False})


def test_nothing_measured_yet_starts_a_scan(monkeypatch):
    _reset(monkeypatch)
    started = []
    monkeypatch.setattr(SHARED, "refresh", lambda *a, **k: started.append(1) or True)
    out = SHARED.storage_scan_cached()
    assert out == {"scan": None, "age_s": None, "updating": True} and started


def test_every_scan_is_the_shared_one(monkeypatch):
    _reset(monkeypatch)
    SHARED.remember({"root": "/data", "stores": []})
    out = SHARED.storage_scan_cached()
    assert out["scan"]["root"] == "/data" and out["updating"] is False
    assert 0 <= out["age_s"] < 5


def test_the_background_scan_waits_for_the_build_then_remembers(monkeypatch):
    _reset(monkeypatch)
    SHARED._STATE["running"] = True
    monkeypatch.setattr(SHARED, "_BUSY_POLL_S", 0.0)
    building = iter([True, True, False])
    monkeypatch.setattr(STORAGE, "storage_scan",
                        lambda: SHARED.remember({"root": "/after"}) or {})
    SHARED._work(lambda: next(building), 0.0)
    assert SHARED._STATE["scan"] == {"root": "/after"}
    assert SHARED._STATE["running"] is False


def test_a_run_s_end_refreshes(monkeypatch):
    _reset(monkeypatch)
    calls = []
    monkeypatch.setattr(SHARED, "refresh", lambda *a, **k: calls.append(a) or True)

    class Session:
        _building = False

        def subscribe(self, handler):
            self.handler = handler

    session = Session()
    SHARED.watch(session, delay_s=0.0)
    assert len(calls) == 1                       # the start's scan

    class RunDone:
        pass
    session.handler(RunDone())
    assert len(calls) == 2
