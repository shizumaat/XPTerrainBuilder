"""Owner RULINGS 2026-11-18c (an exception to 2026-10-22o): a deck of an
object floor's frame whose two ends land on mapped roads above its seated
top, and which only bears on the frame from under it, is seated by its own
end lines — flush at the lower road, the other end's step listed (#1138)."""
from __future__ import annotations

import math
from types import SimpleNamespace as NS

from auto_patch_v2.airport import floor_deck_ends as FDE
from auto_patch_v2.airport import terrain_shaped as TS

LAT, LON, ZERO = 39.84, -104.67, 1626.5
ML = 111_132.0
MO = ML * math.cos(math.radians(LAT))
LAW = FDE._Law(normal_y_min=0.7, bin_m=0.5, area_tie=0.9, min_elevation_m=2.0,
               min_span_m=10.0, step_m=5.0, tol_m=0.3, touch_m=1.0)


def _box(x0, y0, z0, sx, h, sz):
    v = [(x0, y0, z0), (x0 + sx, y0, z0), (x0 + sx, y0, z0 + sz), (x0, y0, z0 + sz),
         (x0, y0 + h, z0), (x0 + sx, y0 + h, z0), (x0 + sx, y0 + h, z0 + sz),
         (x0, y0 + h, z0 + sz)]
    t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _obj(path, boxes):
    v: list = []
    t: list = []
    for b in boxes:
        bv, bt = _box(*b)
        t += [(p + len(v), q + len(v), r + len(v)) for p, q, r in bt]
        v += bv
    idx = [i for tri in t for i in tri]
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(v)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.0 0.0" for x, y, z in v]
    out += [""] + [f"IDX\t{q}" for q in idx] + ["", f"TRIS\t0 {len(idx)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


#: two walls along the track (north-south), their tops at y 3.5
WALLS = [(0.0, 0.0, -40.0, 1.0, 3.5, 80.0), (20.0, 0.0, -40.0, 1.0, 3.5, 80.0)]
#: the deck across them (east-west, 31 m by 10 m), its top at y 4.0
DECK = [(-5.0, 3.5, -5.0, 31.0, 0.5, 10.0)]


def _scene(tmp_path, walls=WALLS, deck=DECK):
    _obj(tmp_path / "walls.obj", walls)
    _obj(tmp_path / "deck.obj", deck)
    rows = [NS(def_path=name, lat=LAT, lon=LON, heading_deg=0.0)
            for name in ("walls.obj", "deck.obj")]
    recs = [{"id": f"dsf:obj{i}", "resource": r.def_path, "datum": "object_floor",
             "seat": TS.OBJECT_FLOOR_SEAT, "elevation": ZERO} for i, r in enumerate(rows)]
    return NS(placements=rows), recs


def _surface(west=1634.7, east=1636.0, roads=("w", "e")):
    """The frame's floor everywhere, a road beyond each end of the deck."""
    def east_of(lon):
        return (lon - LON) * MO

    def z(la, lo):
        x = east_of(lo)
        return west if x < -5.0 else east if x > 26.0 else ZERO

    def roles_many(lats, lons):
        out = []
        for lo in lons:
            x = east_of(lo)
            road = ("w" in roads and x < -5.0) or ("e" in roads and x > 26.0)
            out.append("service_road" if road else "graded_strip")
        return out
    z.roles = NS(roles_many=roles_many)
    return z


def test_the_deck_is_seated_flush_at_its_lower_road(tmp_path):
    dump, recs = _scene(tmp_path)
    (d,) = FDE.end_lifts(dump, recs, _surface(), str(tmp_path), LAW)
    assert d.id == "dsf:obj1"
    assert abs(d.lift - (1634.7 - (ZERO + 4.0))) < 1e-6       # +4.20 onto the west road
    assert d.ground[d.flush] == 1634.7
    assert abs(d.step - 1.3) < 1e-6                           # the east road's, for #1138
    out = FDE.lifted(recs, (d,))
    assert out[0] == recs[0]                                  # the walls stay at the floor
    assert out[1]["seat"] == TS.DECK_ENDS_SEAT
    assert abs(out[1]["elevation"] - (ZERO + d.lift)) < 1e-3
    assert "flush" in FDE.log_line(d) and "#1138" in FDE.log_line(d)


def test_the_seat_is_the_rows_whole_msl_seat(tmp_path):
    dump, recs = _scene(tmp_path)
    lifts = FDE.end_lifts(dump, recs, _surface(), str(tmp_path), LAW)
    seats = TS.row_seats(dump, FDE.lifted(recs, lifts), frozenset())
    by = {m.index: m for m in seats}
    assert by[0].elevation == ZERO and by[0].why == "object_floor"
    assert by[1].why == "object_floor_deck_ends" and by[1].elevation > ZERO + 4.0


def test_an_end_off_any_road_keeps_the_frame_seat(tmp_path):
    dump, recs = _scene(tmp_path)
    assert FDE.end_lifts(dump, recs, _surface(roads=("w",)), str(tmp_path), LAW) == ()


def test_a_road_within_the_tolerance_of_the_deck_keeps_the_frame_seat(tmp_path):
    dump, recs = _scene(tmp_path)
    flush = ZERO + 4.0 + 0.2
    assert FDE.end_lifts(dump, recs, _surface(west=flush), str(tmp_path), LAW) == ()


def test_a_mate_rising_beside_the_deck_keeps_it_with_the_frame(tmp_path):
    # a wall standing up past the deck top beside its north edge: no bearing
    dump, recs = _scene(tmp_path, walls=WALLS + [(5.0, 0.0, -5.6, 8.0, 6.0, 0.5)])
    assert FDE.end_lifts(dump, recs, _surface(), str(tmp_path), LAW) == ()


def test_no_law_no_lift(tmp_path):
    dump, recs = _scene(tmp_path)
    assert FDE.end_lifts(dump, recs, _surface(), str(tmp_path), None) == ()
