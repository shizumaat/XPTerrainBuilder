"""An admitted unit written whole at its underside zero (RULINGS 2026-11-25m
(4), 25n (2); spec ``docs/specs/underside-height-map-20261125.md`` §2, step
2: ``airport/underside_seat``) and rung L0 (``unit_storey.contact_level``)."""
from __future__ import annotations

import dataclasses as _dc
from types import SimpleNamespace

import numpy as np
from auto_patch_v2.airport import anchor_rule as ar
from auto_patch_v2.airport import terrain_shaped as ts
from auto_patch_v2.airport import underside_seat as us
from auto_patch_v2.airport import unit_storey as ust
from auto_patch_v2.geom import underside_map as um
from shapely.geometry import LineString, box


def _map(t, base, *, composite=True, t_from="airside", unit="unit:0#0",
         key=("dsf:obj1",), h=None):
    """A 20 x 10 m slab's map: stations along its edge, the west half airside."""
    g = um.Layers(0.0, 0.0, 1.0, *(np.zeros((10, 20)) for _ in range(5)))
    plan = np.ones((10, 20), dtype=bool)
    e = np.array([0.5, 5.5, 10.5, 15.5, 19.5, 19.5])
    n = np.array([0.5, 0.5, 0.5, 0.5, 5.0, 9.5])
    hh = np.full(len(e), float(t)) if h is None else np.asarray(h, float)
    air = e < 10.0
    return um.UndersideMap(tuple(key), unit, g, plan, e, n, hh, hh, hh,
                           np.zeros(len(e), int), np.ones(len(e), int), air, (), float(t),
                           t_from, (float(t),), 0.0, True, base=float(base),
                           composite=composite)


def _ll(x, y):
    return (y * 1e-5, x * 1e-5)           # (lat, lon): a metre is 1e-5 deg here


def _pad(ref, x0, x1, y0, y1, z):
    ring = tuple(_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    return ar.PadRing(ref, ring, (z,) * 4)


def _obj(i, agl=0.0, bbox=None, **kw):
    return SimpleNamespace(id=f"dsf:obj{i}", path=f"o{i}.obj", agl_m=agl,
                           plan_bbox=bbox, deck_kind=kw.get("deck_kind", ""),
                           walled_plate=None, zero_y=kw.get("zero_y", 0.0))


def _airport(maps, ground=366.5):
    """``ground``: our DEM everywhere (366.5: the composites' floor at
    ``D - t + h`` on the ``low`` pad, so their ground is no FAR)."""
    dem = SimpleNamespace(z_many=lambda x, y: np.full(len(x), float(ground)))
    frame = SimpleNamespace(transformers=lambda: (None, _ll))
    rows = sorted({r for m in maps for r in m.key} | {"dsf:obj3"})
    part = SimpleNamespace(units=(SimpleNamespace(
        id="unit:0", members=tuple(SimpleNamespace(id=r, parts=()) for r in rows)),))
    return SimpleNamespace(undersides={m.key: m for m in maps}, frame=frame, dem=dem,
                           partition=part, clusters=())


def test_the_seat_is_named_for_the_writer():
    assert us.SEAT in ts._WHY and ts._WHY[us.SEAT] == "underside_map"


def test_zero_is_d_less_t_and_a_coherent_composite_keeps_todays():
    assert us._unit_zero(_map(-6.19, -6.6), "composite", 366.52) == 366.52 + 6.19
    assert us._unit_zero(_map(0.32, 0.30), "composite", 376.2) == 376.2 - 0.30
    assert us._unit_zero(_map(0.8, 0.0, composite=False), "mis-zeroed", 375.6) == 375.6 - 0.8


def test_the_pad_is_the_one_under_the_airside_contacts():
    m = _map(-6.0, -6.6)
    pads = [_pad("low", -1, 10, -1, 11, 366.5), _pad("high", 10, 21, -1, 11, 373.0)]
    assert us._unit_pad(m, pads, _ll) == ("low", 366.5)
    # airside contacts on the apron, off every pad: the pad its feet stand on
    m = _dc.replace(m, layers=_dc.replace(m.layers, foot=np.where(
        np.arange(20)[None, :] >= 15, 0.0, np.nan) * np.ones((10, 1))))
    assert us._unit_pad(m, [_pad("feet", 14, 21, -1, 11, 366.0)], _ll) == ("feet", 366.0)
    # stations on the edge, the pad drawn a little inside it: the pad beside
    edge = m
    inner = [_pad("inner", 1.0, 9.0, 1.0, 9.0, 366.2)]
    assert us._unit_pad(edge, inner, _ll) == (None, None)
    assert us._unit_pad(edge, inner, _ll, lambda lo, la: (lo * 1e5, la * 1e5), 3.0) \
        == ("inner", 366.2)
    assert us._unit_pad(m, [], _ll) == (None, None)


def test_refusals_keep_todays_seat():
    m = _map(-6.0, -6.6)
    ok = {"dsf:obj1": _obj(1)}
    assert us._whole_refusal(m, ["dsf:obj1"], ok, set(), {}, set()) is None
    assert us._whole_refusal(m, ["dsf:obj1"], ok, {"dsf:obj1"}, {}, set()) \
        == "row seated by another rule"
    assert us._whole_refusal(m, ["dsf:obj1"], {"dsf:obj1": _obj(1, deck_kind="flag")},
                            set(), {}, set()) == "deck family"
    assert us._whole_refusal(m, ["dsf:obj1"], {"dsf:obj1": _obj(1, zero_y=2.0)},
                            set(), {}, set()) == "converted MSL row"
    shared = {"dsf:obj1": {"unit:0#0", "unit:0#1"}}
    single = _map(0.8, 0.0, composite=False, t_from="feet")
    assert us._whole_refusal(single, ["dsf:obj1"], ok, set(), shared, {"unit:0#1"}) \
        == "row shared with another grounded unit"
    # a composite's rows are one authored frame: its other buildings ride it
    assert us._whole_refusal(m, ["dsf:obj1"], ok, set(), shared, {"unit:0#1"}) is None
    # a composite at its frame's zero near its base: today's readers seat it
    assert us._whole_refusal(_map(0.14, 0.06), ["dsf:obj1"], ok, set(), {}, set()) \
        == "today's readers seat its airside floor"
    assert us._whole_refusal(m, ["dsf:obj1"], ok, set(), shared, set()) is None  # footless
    lib = SimpleNamespace(**{**vars(_obj(1)), "path": "lib/people/p.obj"})
    assert us._whole_refusal(m, ["dsf:obj1"], {"dsf:obj1": lib}, set(), {}, set()) \
        == "library object"
    far = SimpleNamespace(**{**vars(_obj(1)), "resolved": "/other/lib/w.obj"})
    assert us._whole_refusal(m, ["dsf:obj1"], {"dsf:obj1": far}, set(), {}, set(), 3.0,
                             "/packs/P") == "library object"
    two = {"dsf:obj1": _obj(1), "dsf:obj2": _obj(2, agl=1.0)}
    assert us._whole_refusal(m, ["dsf:obj1", "dsf:obj2"], two, set(), {}, set()) \
        == "rows disagree on their lift"


def test_records_write_the_rows_whole_and_a_rider_rides():
    m = _map(0.9, 0.0, key=("dsf:obj1", "dsf:obj2"), composite=False, t_from="feet")
    # a mis-zeroed unit: ground confirms when our DEM stands at D - t + h
    m = _dc.replace(m, h=np.full(len(m.e), 0.9))
    objs = [_obj(1), _obj(2), _obj(3, agl=2.0, bbox=box(2, 2, 6, 6)),
            _obj(5, bbox=box(3, 3, 5, 5))]          # obj5: another frame's prop
    ap = _airport([m])
    ap.dem = SimpleNamespace(z_many=lambda x, y: np.full(len(x), 366.5))
    recs, rep = us.seat_records(ap, [_pad("low", -1, 21, -1, 11, 366.5)], objs, set(), 0.5)
    by = {r["id"]: r for r in recs}
    assert set(by) == {"dsf:obj1", "dsf:obj2", "dsf:obj3"}, rep
    assert by["dsf:obj1"]["elevation"] == 365.6 and by["dsf:obj3"]["elevation"] == 367.6


def test_a_composite_writes_its_whole_origin_set():
    m = _map(-6.0, -6.6, key=("dsf:obj1", "dsf:obj2"))
    objs = [_obj(1), _obj(2), _obj(3, agl=2.0, bbox=box(2, 2, 6, 6)),
            _obj(4, bbox=box(40, 40, 50, 50))]
    pads = [_pad("low", -1, 10, -1, 11, 366.5)]
    recs, rep = us.seat_records(_airport([m]), pads, objs, set(), 0.5)
    by = {r["id"]: r for r in recs}
    assert set(by) == {"dsf:obj1", "dsf:obj2", "dsf:obj3"}
    assert by["dsf:obj1"]["elevation"] == 372.5 and by["dsf:obj1"]["seat"] == us.SEAT
    assert by["dsf:obj3"]["elevation"] == 374.5 and by["dsf:obj3"]["rider"]
    assert rep[0]["z0"] == 372.5 and rep[0]["riders"] == 1
    assert "written whole" in us.log_line("TEST", rep)


def test_coherent_doubt_and_off_pad_units_are_not_written():
    pads = [_pad("low", -1, 10, -1, 11, 366.5)]
    coherent = _map(0.02, 0.0, composite=False)
    assert us.seat_records(_airport([coherent]), pads, [_obj(1)], set(), 0.5) == ([], [])
    assert us.seat_records(_airport([_map(-6.0, -6.6)]), [], [_obj(1)], set(), 0.5) \
        == ([], [])
    recs, rep = us.seat_records(_airport([_map(-6.0, -6.6)]), pads, [_obj(1)],
                                {"dsf:obj1"}, 0.5)
    assert recs == [] and rep[0]["refused"] == "row seated by another rule"


def test_rung_l0_reads_the_contacts_along_the_face():
    m = _map(0.0, 0.0, h=[0.0, 0.0, 0.0, 0.0, 4.1, 4.1])
    ap = _airport([m])
    face = LineString([(19.5, 0.0), (19.5, 10.0)])
    assert ust._contact_level(ap, 0, face, 0.0, 3.0, 3.0) == 4.1
    assert ust._contact_level(ap, 0, LineString([(0, 20), (5, 20)]), 0.0, 3.0, 3.0) is None
    assert ust._contact_level(ap, 0, face, 4.0, 3.0, 3.0) is None    # all within a storey


def test_a_zero_leaving_its_ground_far_is_doubt():
    """S0 (lane lellxpit; 25f): a composite whose zero leaves half or more
    of its non-airside stations a storey off our ground is not written."""
    pads = [_pad("low", -1, 10, -1, 11, 366.5)]
    m = _map(-6.0, -6.6, key=("dsf:obj1", "dsf:obj2"))
    recs, rep = us.seat_records(_airport([m], ground=382.0), pads,
                                [_obj(1), _obj(2)], set(), 0.5)
    assert recs == [] and rep == []

