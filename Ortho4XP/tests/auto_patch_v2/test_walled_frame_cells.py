"""Walled multi-bridge frames, the object stage (spec
``docs/specs/walled-multibridge-frames-spec.md`` W6 / W9): a frame whose
deck pieces carry span cuts on two axes is cut into CELLS
(``geom/plate_cells``), each span seated on its own end lines, the rest
moved rigidly with the end line it lies beyond, every piece published
(``Member.deck_rings``).  Synthetic and hermetic."""
from __future__ import annotations

import math
import random
import types

import numpy as np
import shapely
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import deck_plates as DP
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_split as OS
from auto_patch_v2.airport import rebake_plan as RP
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.geom.plate_cells import SpanAxis, planes_of, span_cells
from auto_patch_v2.model.deck_piece import DeckPiece
from auto_patch_v2.model.rebake import Member, RebakePlan, Unit

LAT0, LON0 = 40.0, -3.0
ML, MO = AR._m_per_deg(LAT0)


def _ll(x: float, z: float) -> tuple[float, float]:
    """Authored frame (heading 0: x east, z south) to ``(lat, lon)``."""
    return LAT0 - z / ML, LON0 + x / MO


def _box(x0, x1, z0, z1):
    return ((x0, z0), (x1, z0), (x1, z1), (x0, z1))


#: an L: piece A spans x 0..40 (its axis x), piece B spans z 60..100 (axis z)
A = SpanAxis((0.0, 10.0), (40.0, 10.0), ((0.0, 40.0),), _box(0, 40, 0, 20))
B = SpanAxis((90.0, 60.0), (90.0, 100.0), ((0.0, 40.0),), _box(80, 100, 60, 100))


def _holds(c, x, z):
    return all((p[0] * x + p[1] * z > p[2]) if p[3] else (p[0] * x + p[1] * z >= p[2])
               for p in c.planes)


def test_two_axis_cells_tile_the_plan_once():
    cells = span_cells([A, B], 0.5)
    assert cells is not None and len(cells) == 6
    assert [c.kind for c in cells.cells] == ["rest", "span", "rest"] * 2
    rng = random.Random(3)
    for _ in range(2000):
        x, z = rng.uniform(-200, 300), rng.uniform(-200, 300)
        hit = [k for k, c in enumerate(cells.cells) if _holds(c, x, z)]
        assert len(hit) == 1 and hit[0] == cells.band_of(x, z)
    # each piece's own span on its own axis
    assert cells.band_of(20.0, 10.0) == 1 and cells.band_of(90.0, 80.0) == 4
    assert cells.band_of(-5.0, 10.0) == 0 and cells.band_of(60.0, 5.0) == 2
    assert cells.anchor_of(0) == (1, 0) and cells.anchor_of(5) == (4, 1)


def test_a_band_is_the_two_plane_cell():
    assert planes_of((1.0, 0.0, -math.inf, 5.0)) == ((-1.0, -0.0, -5.0, True),)
    assert planes_of((1.0, 0.0, 2.0, 5.0)) == ((1.0, 0.0, 2.0, False),
                                               (-1.0, -0.0, -5.0, True))


def _piece(ax: SpanAxis, ends) -> DeckPiece:
    st = tuple(_ll(*q) for q in ends)
    return DeckPiece(tuple(_ll(*q) for q in ax.ring), "airside", st, (0.0,) * len(st),
                     (_ll(*ax.a), _ll(*ax.b), ax.spans, 0.015))


def _member():
    pa = _piece(A, ((0.0, 5.0), (0.0, 15.0), (40.0, 5.0), (40.0, 15.0)))
    pb = _piece(B, ((85.0, 60.0), (95.0, 60.0), (85.0, 100.0), (95.0, 100.0)))
    rider = DeckPiece(tuple(_ll(*q) for q in _box(50, 55, 30, 35)))
    return types.SimpleNamespace(id="dsf:obj1", resource="objects/deck.obj", deck_kind="flag",
                                 origin=(LAT0, LON0), heading_deg=0.0, zero_y=0.0,
                                 plate_stations=(), deck_spans=(),
                                 deck_rings=(pa, pb, rider))


def _ground(lat, lon):
    """A's a end at 100, its b end at 100.4; B's ends at 101 and 101.2."""
    x, z = (lon - LON0) * MO, (LAT0 - lat) * ML
    if x < 60.0:
        return 100.0 + 0.01 * x
    return 101.0 + 0.005 * (z - 60.0)


def test_rest_cells_translate_rigidly_with_their_end_line():
    counts: dict = {}
    fp = DP.frame_plates([_member()], 2.0, counts)
    assert fp is not None and counts["deck_cell_frames"] == 1
    seats = DP._band_seats(fp, _ground, counts)
    mean_all = (2 * 100.0 + 2 * 100.4 + 2 * 101.0 + 2 * 101.2) / 8
    (d0, _s0, w0), (_d1, _s1, w1), (d2, _s2, w2) = seats[:3]
    assert not w0 and not w2                       # rest: rigid, no warp
    assert math.isclose(d0, 100.0 - mean_all, abs_tol=1e-6)
    assert math.isclose(d2, 100.4 - mean_all, abs_tol=1e-6)
    # each span graded on its own end lines
    (_xa, _za, da), (_xb, _zb, db) = w1[0][1]
    assert abs((db - da) - 0.4) < 1e-3
    (_x, _z, ea), (_x2, _z2, eb) = seats[4][2][0][1]
    assert abs((eb - ea) - 0.2) < 1e-3 and counts["deck_span_graded"] == 2


def test_no_body_lost_from_a_two_axis_frame():
    a = AR.Anchor(AR.OTHER, LAT0, LON0, 4.0, "frame zero", surface_z=104.0,
                  offset=(0.0, 4.0, 0.0))
    rec = Split(0, "dsf:obj1", "objects/deck.obj", "/x/deck.obj", LAT0, LON0, 0.0,
                (Body(0, AR.OTHER, (0,), a, "objects/deck__b0.obj"),))
    fp = DP.frame_plates([_member()], 2.0, {})
    counts: dict = {}
    out = DP.split_record(rec, _member(), fp, _ground, counts)
    assert len(out.bodies) == 6 and "deck_span_bands_dropped" not in counts
    assert len({b.body_id for b in out.bodies}) == 6
    assert all(isinstance(b.band[0], tuple) for b in out.bodies)


def _write(path, verts, tris) -> str:
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(tris) * 3}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.5 0.5" for x, y, z in verts]
    out += [f"IDX\t{q}" for t in tris for q in t]
    out += ["", f"TRIS\t0 {len(tris) * 3}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def test_a_floor_under_both_spans_is_clipped_into_every_cell(tmp_path):
    v = [(-50.0, 0.0, -50.0), (150.0, 0.0, -50.0), (150.0, 0.0, 150.0), (-50.0, 0.0, 150.0)]
    path = _write(tmp_path / "floor.obj", v, [(0, 2, 1), (0, 3, 2)])
    cells = span_cells([A, B], 0.5)
    comps = tuple(range(len(obj8.solid_components(obj8.parse_obj8(path)))))
    cuts = [OS.BodyCut(k, comps, (0.0, float(k), 0.0), band=cells.band(k))
            for k in range(len(cells))]
    res = OS.split_obj8(path, cuts, "objects/floor.obj")
    assert not res.kept_whole and len(res.files) == len(cells)
    area = 0.0
    for f in res.files:
        q = tmp_path / f"b{f.body_id}.obj"
        q.write_text(f.text, encoding="utf-8", newline="\n")
        g = obj8.parse_obj8(str(q))
        f3 = g.vertices[g.solid][:, :, [0, 2]]
        area += 0.5 * np.abs(np.cross(f3[:, 1] - f3[:, 0], f3[:, 2] - f3[:, 0])).sum()
    assert abs(area - 200.0 * 200.0) < 0.5       # every square metre in one cell


def test_deck_rings_publish_every_piece_and_round_trip():
    pieces = ((((0, 0), (40, 0), (40, 20), (0, 20)), "airside", ((0, 5), (40, 5)),
               (0.1, -0.1), ((0, 10), (40, 10), ((0.0, 40.0),), 0.015)),
              (((80, 60), (100, 60), (100, 100), (80, 100)), "road", ((90, 60),), (0.0,), ()))
    deck = shapely.MultiPolygon([shapely.Polygon(pieces[0][0]), shapely.Polygon(pieces[1][0]),
                                 shapely.box(50, 30, 55, 35)])
    rings = RP._deck_rings(types.SimpleNamespace(hard_deck=deck), pieces,
                           lambda x, y: (y * 1e-5, x * 1e-5))
    assert [p.tag for p in rings] == ["airside", "road", "rider"]
    assert rings[0].span_cut[2] == ((0.0, 40.0),) and rings[0].tops == (0.1, -0.1)
    m = Member("dsf:obj1", "r", "/a", "/l", 0.0, deck_rings=rings)
    plan = RebakePlan("ICAO", "p", "/p", (Unit("u", (0.0, 0.0), 0.0, (m,)),), (), {})
    back = RebakePlan.from_json(plan.to_json()).units[0].members[0]
    assert back.deck_rings == rings
