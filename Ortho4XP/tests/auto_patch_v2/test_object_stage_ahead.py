"""#412 2b: a tile's later airports planned ahead (``object_stage``'s
``_Ahead``): a half is taken only when it is the half the loop would
compute now; a queued task the caller dropped never starts."""
from __future__ import annotations

import concurrent.futures as cf
import os
import types

from auto_patch import object_stage as STAGE
from auto_patch_v2.airport import file_witness as FW


class _Plan:
    def __init__(self, text):
        self.text = text

    def to_json(self):
        return self.text


def _job(**kw):
    job = {"plan_path": "/p/o4_v2_rebake_ZZZZ.json", "icao": "ZZZZ", "key": "ZZZZ",
           "foreign": (), "write_enabled": True, "measure_only": False}
    job.update(kw)
    return job


def _result(tmp_path, **kw):
    f = tmp_path / "read.txt"
    f.write_text("x", encoding="utf-8", newline="\n")
    st = os.stat(f)
    r = {"half": object(), "error": None, "plan_sha": STAGE._plan_sha(_Plan("{}")),
         "start_ns": st.st_mtime_ns + 1, "written": [],
         "opened": {str(f): (st.st_size, st.st_mtime_ns)}}
    r.update(kw)
    return r, f


def _refusal(r, **kw):
    args = dict(plan_=_Plan("{}"), plan_key="ZZZZ", foreign=(), write_enabled=True,
                measure_only=False)
    args.update(kw)
    return STAGE._ahead_refusal(r, _job(), **args)


def test_the_same_half_is_taken(tmp_path):
    r, _f = _result(tmp_path)
    assert _refusal(r) == ""


def test_a_different_input_is_refused(tmp_path):
    r, _f = _result(tmp_path)
    assert "plan differs" in _refusal(r, plan_=_Plan('{"a": 1}'))
    assert "sibling" in _refusal(r, foreign=(("x",),))
    assert "sibling" in _refusal(r, measure_only=True)
    assert _refusal(dict(r, error="boom")) == "boom"
    assert _refusal(dict(r, half=None)) == "nothing planned"


def test_a_file_changed_or_written_while_read_is_refused(tmp_path):
    r, f = _result(tmp_path)
    st = os.stat(f)
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000))
    assert "changed since" in _refusal(r)
    r, f = _result(tmp_path)
    r["start_ns"] = os.stat(f).st_mtime_ns         # modified at/after the start
    assert "written while" in _refusal(r)
    r["written"] = [str(f)]                         # ... by the worker itself
    assert _refusal(r) == ""


def test_take_of_a_plan_never_started_computes_here():
    ahead = STAGE._Ahead([_job()])                  # not started: no thread
    assert ahead.take("/p/o4_v2_rebake_ZZZZ.json", _Plan("{}"), "ZZZZ", (),
                      True, False) is None
    assert ahead.take("/p/other.json", _Plan("{}"), "", (), True, False) is None
    ahead.close()


def test_a_taken_half_replays_its_lines_and_files(tmp_path, capsys):
    ahead = STAGE._Ahead([_job()])
    r, f = _result(tmp_path, lines=["  [v2 placement] ZZZZ: planned"],
                   reads={"/r/a": (1, 2)}, written=["/w/b"])
    ahead._started.add("/p/o4_v2_rebake_ZZZZ.json")
    ahead._done["/p/o4_v2_rebake_ZZZZ.json"] = r
    rec = FW.FileRecorder(writes=True)
    rec.recording(True)
    try:
        half = ahead.take("/p/o4_v2_rebake_ZZZZ.json", _Plan("{}"), "ZZZZ", (),
                          True, False)
    finally:
        rec.recording(False)
    assert half is r["half"]
    assert "/r/a" in rec._paths and "/w/b" in rec._written
    assert "ZZZZ: planned" in capsys.readouterr().out


def test_the_gated_pool_never_starts_a_dropped_task(monkeypatch):
    from auto_patch import slot_gated_pool as GATED
    monkeypatch.setattr(GATED._SLOTS, "try_take",
                        lambda n, what="": types.SimpleNamespace(
                            count=1, release=lambda: None))
    monkeypatch.setattr(GATED._SLOTS, "want_slot", lambda wants=True: None)
    started, dropped = [], {2, 3}
    ex = cf.ThreadPoolExecutor(max_workers=1)

    def start(t):
        started.append(t)
        return ex, ex.submit(lambda: t)
    GATED.run(range(5), width=1, start=start, on_done=lambda t, f: None,
              teardown=lambda e, f, t: None, poll_s=0.01,
              drop=lambda t: t in dropped)
    ex.shutdown()
    assert started == [0, 1, 4]


def test_a_worker_half_mark_falls_back_to_the_serial_ground(monkeypatch):
    calls = []
    half = STAGE._PlanHalf(types.SimpleNamespace(icao="ZZZZ"), None, (), {}, [], [],
                          None, "", "", "", "pack", {(1, 2): "mesh:abc"}, None)
    from auto_patch_v2.airport import tile_route as R

    def fake_ground(*a, **k):
        def z(la, lo):
            return None
        z.mark = lambda t: (calls.append(t), "dem")[1]
        return z
    monkeypatch.setattr(R, "neighbour_ground", fake_ground)
    mark = STAGE._guest_mark(half, types.SimpleNamespace(lat=1, lon=2))
    assert mark((1, 2)) == "mesh:abc" and calls == []
    assert mark((1.0, 3.0)) == "dem" and calls == [(1, 3)]


def test_an_airport_the_loop_never_places_gets_no_half(tmp_path, monkeypatch):
    """No unit and nothing generated: the loop skips it, so the worker
    computes no half (and clones no pack for one)."""
    from auto_patch_v2.model import rebake as RB
    plan = tmp_path / "o4_v2_rebake_ZZZZ.json"
    plan.write_text("{}", encoding="utf-8", newline="\n")
    monkeypatch.setattr(RB.RebakePlan, "from_json",
                        staticmethod(lambda text: types.SimpleNamespace(units=[])))
    monkeypatch.setattr(STAGE, "_plan_half", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("a half was computed")))
    out = {"half": None, "plan_sha": None, "reads": {}, "written": []}
    STAGE._plan_ahead_half(_job(plan_path=str(plan), screen=None,
                                patch_dir=str(tmp_path)), out)
    assert out["half"] is None and out["plan_sha"] is None
