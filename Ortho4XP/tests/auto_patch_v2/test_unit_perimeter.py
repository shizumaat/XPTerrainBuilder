"""Twins of the perimeter grade (owner RULINGS 2026-11-25m (2)/(3), 25n;
spec ``docs/specs/underside-height-map-20261125.md`` §3, step 3):
``airport/unit_perimeter`` (the interval, the field, the cut-outs, the
record), ``airport/perimeter_grade`` (the raster grade and its judge) and
``auto_patch/terrain_cut_stage.perimeter_records``."""
from __future__ import annotations

import json
import types

import numpy as np
import pytest
from auto_patch_v2.airport import perimeter_grade as _pg
from auto_patch_v2.airport import terrain_fill as _tf
from auto_patch_v2.airport import unit_perimeter as _up
from auto_patch_v2.geom.terrain_deck import UNDER_M


def _per(e, n, lo, hi, *, far=None, plan=((), ()), step=1.0, cut=None, z0=100.0):
    e, n = np.asarray(e, float), np.asarray(n, float)
    ce, cn, cz = cut if cut is not None else ((), (), ())
    return _up.Perimeter("u", "r1", z0, "coherent", e, n, np.asarray(lo, float),
                         np.asarray(hi, float), np.zeros(len(e), bool),
                         np.zeros(len(e), bool) if far is None else np.asarray(far, bool),
                         np.asarray(plan[0], float), np.asarray(plan[1], float), step,
                         np.asarray(ce, float), np.asarray(cn, float), np.asarray(cz, float),
                         np.ones(len(cz), bool))


def test_interval_sheet_reads_its_top():
    m = types.SimpleNamespace(lo=np.array([-0.2, 0.0]), hi=np.array([0.0, -1.0]))
    lo, hi = _up._interval(m, 100.0)
    assert hi.tolist() == pytest.approx([100.0 - UNDER_M, 99.0 - UNDER_M])
    # a sheet: its lowest surface stands over its floor less UNDER_M -> hi alone
    assert lo.tolist() == pytest.approx([99.8, 99.0 - UNDER_M])


def test_off_interval_signs():
    assert _up.off_interval(np.array([1.0, 5.0, 9.0]), np.array([2.0] * 3),
                            np.array([8.0] * 3)).tolist() == [-1.0, 0.0, 1.0]


def test_field_shoulder_and_feather():
    p = _per([0.0], [0.0], [10.0], [11.0])
    x = np.array([5.0, 35.0, 70.0])
    g = np.array([8.0, 8.0, 8.0])
    out, which, _d = _up.field([p], x, np.zeros(3), g, shoulder_m=10.0, reach_m=60.0)
    # in the shoulder: raised to lo; half way down the feather: half; past it: kept
    assert out.tolist() == pytest.approx([10.0, 9.0, 8.0])
    assert which.tolist() == [0, 0, -1]


def test_field_lowers_to_hi_and_keeps_inside():
    p = _per([0.0, 0.0], [0.0, 1.0], [10.0, 10.0], [11.0, 11.0])
    out, _w, _d = _up.field([p], np.array([1.0, 1.0]), np.array([0.0, 0.5]),
                            np.array([14.0, 10.5]), shoulder_m=5.0)
    assert out.tolist() == pytest.approx([11.0, 10.5])


def test_field_far_station_is_no_target():
    p = _per([0.0], [0.0], [10.0], [11.0], far=[True])
    out, which, _d = _up.field([p], np.array([1.0]), np.array([0.0]), np.array([2.0]), 5.0)
    assert out.tolist() == [2.0] and which.tolist() == [-1]


def test_field_another_plan_holds_its_ground():
    a = _per([0.0], [0.0], [10.0], [11.0])
    b = _per([100.0], [0.0], [50.0], [51.0], plan=([4.0], [0.0]))
    out, which, _d = _up.field([a, b], np.array([4.0]), np.array([0.0]), np.array([2.0]), 10.0)
    assert out.tolist() == [2.0] and which.tolist() == [-1]


def test_cut_ceiling_only_under_interiors():
    p = _per([0.0], [0.0], [0.0], [1.0], cut=([5.0], [5.0], [90.0]))
    c = _up.cut_ceiling([p], np.array([5.2, 20.0]), np.array([5.1, 20.0]))
    assert c[0] == 90.0 and np.isinf(c[1])


def test_record_round_trip():
    to_xy, to_ll = _up.projector(types.SimpleNamespace(crs="+proj=tmerc +lat_0=49 +lon_0=6"))
    p = _per([10.0, 20.0], [5.0, 6.0], [1.0, 2.0], [3.0, 4.0], plan=([12.0], [5.5]),
             cut=([15.0], [5.0], [0.5]))
    d = json.loads(json.dumps(p.to_dict(to_ll)))
    q = _up.from_dict(d, to_xy)
    assert q.e.tolist() == pytest.approx(p.e.tolist(), abs=0.02)
    assert q.lo.tolist() == p.lo.tolist() and q.cut_z.tolist() == [0.5]
    assert q.plan_n.tolist() == pytest.approx([5.5], abs=0.02)


def _raster(n=41, z=0.0, frozen_cols=()):
    alt = np.full((n, n), z)
    dl = 1.0 / 11016.0

    def frozen(rows, cols, lons, lats):
        return np.isin(cols, list(frozen_cols))
    return _tf.Raster(alt, 6.0, 49.0 + (n - 1) * dl, dl, dl, frozen if frozen_cols else None)


def test_grade_raises_free_postings_and_judge_counts():
    to_xy, to_ll = _up.projector(types.SimpleNamespace(crs="+proj=tmerc +lat_0=49 +lon_0=6"))
    r = _raster()
    cx, cy = to_xy(np.array([6.0 + 20 / 11016.0]), np.array([49.0 + 20 / 11016.0]))
    p = _per(cx, cy, [2.0], [3.0])
    before = _pg.judge(r, to_xy, to_ll, [p])[0]
    assert before["free"] == 1 and before["over"] == 1
    rep = _pg.perimeter_grade(r, to_xy, to_ll, [p])
    assert rep["raised"] > 0 and rep["lowered"] == 0
    after = _pg.judge(r, to_xy, to_ll, [p])[0]
    assert after["over"] == 0


def test_grade_never_moves_a_frozen_posting():
    to_xy, to_ll = _up.projector(types.SimpleNamespace(crs="+proj=tmerc +lat_0=49 +lon_0=6"))
    r = _raster(frozen_cols=range(15, 26))
    cx, cy = to_xy(np.array([6.0 + 20 / 11016.0]), np.array([49.0 + 20 / 11016.0]))
    p = _per(cx, cy, [2.0], [3.0])
    _pg.perimeter_grade(r, to_xy, to_ll, [p])
    assert np.all(r.alt[:, 15:26] == 0.0)
    assert _pg.judge(r, to_xy, to_ll, [p])[0]["patch"] == 1


def test_grade_cuts_an_open_interior():
    to_xy, to_ll = _up.projector(types.SimpleNamespace(crs="+proj=tmerc +lat_0=49 +lon_0=6"))
    r = _raster(z=5.0)
    lon, lat = 6.0 + 20 / 11016.0, 49.0 + 20 / 11016.0
    cx, cy = to_xy(np.array([lon]), np.array([lat]))
    sx, sy = to_xy(np.array([lon + 3 / 11016.0]), np.array([lat]))
    p = _per(sx, sy, [4.0], [6.0], cut=(cx, cy, [1.0]), step=30.0)
    rep = _pg.perimeter_grade(r, to_xy, to_ll, [p])
    assert rep["cut"] >= 1 and r.alt[20, 20] == pytest.approx(1.0)
    assert _pg.judge(r, to_xy, to_ll, [p])[0]["uncut"] == 0


def test_perimeter_records_one_per_group(tmp_path):
    from auto_patch import terrain_cut_stage as _tcs
    rec = {"unit": "u", "row": "r1", "z0": 1.0, "why": "coherent", "step": 1.0,
           "stations": {"lat": [49.0], "lon": [6.0], "lo": [0.0], "hi": [1.0],
                        "far": [0]}, "plan": {"lat": [], "lon": []},
           "cut": {"lat": [], "lon": [], "z": [], "open": []}}
    for name in ("o4_v2_rebake_XXXX.json", "o4_v2_rebake_XXXX.screen.json"):
        (tmp_path / name).write_text(json.dumps({"icao": "XXXX", "perimeters": [rec]}),
                                     encoding="utf-8", newline="\n")
    got = _tcs.perimeter_records(str(tmp_path))
    assert len(got) == 1 and got[0]["icao"] == "XXXX"
    assert _tcs.perimeter_records(str(tmp_path), ["YYYY"]) == []


def test_plan_and_screen_carry_perimeters():
    from auto_patch_v2.model.rebake import RebakePlan
    p = RebakePlan("XXXX", "pack", "/root", (), (), {}, perimeters=({"unit": "u"},))
    q = RebakePlan.from_json(p.to_json())
    assert q.perimeters == ({"unit": "u"},)
    bare = RebakePlan("XXXX", "pack", "/root", (), (), {})
    assert "perimeters" not in bare.to_dict()


def _map(t, t_from, base, h, composite=False):
    n = len(h)
    return types.SimpleNamespace(footless=False, t=t, t_from=t_from, base=base,
                                 composite=composite, airside=np.zeros(n, bool),
                                 h=np.asarray(h, float), lo=np.asarray(h, float) - 0.2,
                                 hi=np.asarray(h, float))


def test_population_doubt_keeps_todays_zero_only_near_its_base():
    # t 0.2 m off today's base: today's zero is known within the grade's tolerance
    m = _map(0.2, "feet", 0.0, [0.0, 0.1, 0.2])
    assert _up._zero(m, 344.28, 344.28 + m.h) == (pytest.approx(344.28), "today's zero")
    # t read off its feet 6 m under its base: neither zero is known, no grade
    far = _map(-6.0, "feet", 0.0, [0.0, 0.1, 0.2])
    assert _up._zero(far, 344.28, 344.28 + far.h) is None


def test_population_coherent_and_no_pad_problem_spots():
    m = _map(0.01, "airside", 0.0, [0.0, 0.0, 0.0])
    assert _up._zero(m, 100.0, 100.0 + m.h) == (pytest.approx(100.0), "coherent")
    # off every pad: graded only where a station stands over GAP_M off
    flat = _map(0.0, "feet", 0.0, [0.0, 0.0, 0.0])
    assert _up._zero(flat, None, np.array([50.0, 50.0, 50.0])) is None
    bumpy = _map(0.0, "feet", 0.0, [0.0, 0.0, 0.0])
    got = _up._zero(bumpy, None, np.array([50.0, 50.0, 52.0]))
    assert got is not None and got[1] == "no pad" and got[0] == pytest.approx(50.0)


def test_the_cut_stage_grades_a_record_in_its_own_frame():
    from auto_patch import terrain_cut_stage as _tcs
    r = _raster()
    lon, lat = 6.0 + 20 / 11016.0, 49.0 + 20 / 11016.0
    rec = {"icao": "XXXX", "unit": "u", "row": "r1", "z0": 2.0, "why": "coherent",
           "step": 1.0, "stations": {"lat": [lat], "lon": [lon], "lo": [2.0], "hi": [3.0],
                                     "far": [0]},
           "plan": {"lat": [], "lon": []}, "cut": {"lat": [], "lon": [], "z": [], "open": []}}
    moved = _tcs._grade_perimeters(r, [rec])
    assert moved > 0 and r.sample(np.array([lon]), np.array([lat]))[0] == pytest.approx(2.0)
