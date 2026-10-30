"""#1692 twins (owner RULINGS 2026-10-30f (1) / (5)): a pack hard deck over a
mapped road that no airside pavement crosses — a ROAD OVERPASS — is read
before the solve (``planar/overpass_deck``), published as its deck member's
plate (``pipeline/rebake_inputs``) and seated with its zero on the road
beneath, the whole frame with it, a body off the map included
(``airport/airside_deck_seat``)."""
from __future__ import annotations

import types

from shapely.geometry import box as _sbox

from auto_patch_v2.airport import airside_deck_seat as ADS
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline import rebake_inputs as RI
from auto_patch_v2.planar import overpass_deck as OD
from auto_patch_v2.planar.deck_bridge import deck_bridges

LAW = Law.for_airport("")
THICK = LAW.tables.structures.basin.min_solid_thickness_m
FRAME = Frame("ZZZZ", origin=(36.0, -86.0), identity_dp=11)


def _box(x, z, w, d, h, y0=0.0):
    x1, z1, y1 = x + w, z + d, y0 + h
    v = [(x, y0, z), (x1, y0, z), (x1, y0, z1), (x, y0, z1),
         (x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def _write(path, top):
    """A 16 x 50 m hard deck at ``top`` on two abutment blocks past the
    road (z -25..-12 and 12..25), their feet 5 m under the zero."""
    comps = [_box(-8.0, -25.0, 16.0, 50.0, 0.3, y0=top - 0.3),
             _box(-8.0, -25.0, 16.0, 13.0, top + 5.0, y0=-5.0),
             _box(-8.0, 12.0, 16.0, 13.0, top + 5.0, y0=-5.0)]
    verts = [p for comp in comps for tri in comp for p in tri]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    n0 = 3 * len(comps[0])
    out += ["ATTR_hard_deck concrete", f"TRIS 0 {n0}", "ATTR_no_hard",
            f"TRIS {n0} {3 * (len(comps[1]) + len(comps[2]))}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _read(tmp_path, top=7.5, road=True, taxi=False):
    deck = _sbox(-8.0, -25.0, 8.0, 25.0)
    o = types.SimpleNamespace(
        id="dsf:obj9", path="objects/crossing.obj", resolved=_write(tmp_path / "c.obj", top),
        xy=(0.0, 0.0), heading_deg=0.0, kind="OBJECT", anchor_z=100.0, agl_m=0.0,
        deck_kind="flag", hard_deck=deck, deck_top_z=100.0 + top, plan_bbox=deck)
    ways = [types.SimpleNamespace(id=-7, points=[(-60.0, 1.0), (60.0, 1.0)],
                                  tags={"highway": "secondary"})] if road else []
    airport = types.SimpleNamespace(frame=FRAME, osm_ways=ways)
    cells = ()
    if taxi:
        cells = tuple(Cell(i, "primary_parallel", f"t:{i}", tuple(b.exterior.coords)[:-1], (),
                           None, None, "airside", "pavement", {})
                      for i, b in enumerate((_sbox(-5, -80, 5, -25), _sbox(-5, 25, 5, 80))))
    cl = types.SimpleNamespace(cells=cells)
    cache = O.ResourceCache(THICK)
    decks = deck_bridges([o], cache, cl, airport, LAW)[0] if cells else ()
    return OD.road_overpasses([o], cache, cl, airport, LAW, decks)


def test_a_hard_deck_over_a_mapped_road_is_an_overpass_read_before_the_solve(tmp_path):
    """30f (1) / (5): the deck spans the mapped road, stands the clearance
    over its zero, and no pavement runs across it — its stations are the
    road's centreline under the deck."""
    (ov,), notes = _read(tmp_path)
    assert ov.object_id == "dsf:obj9" and ov.ways == (-7,) and abs(ov.top_y - 7.5) < 1e-6
    assert ov.stations and all(abs(y - 1.0) < 1e-6 and -8.0 <= x <= 8.0 for x, y in ov.stations)
    assert "road overpass" in notes[0]


def test_no_road_no_clearance_or_a_taxiway_across_is_no_overpass(tmp_path):
    assert _read(tmp_path, road=False) == ((), [])
    assert _read(tmp_path, top=2.0)[0] == ()
    assert _read(tmp_path, taxi=True)[0] == ()      # a hard-deck BRIDGE (deck_bridge)


def test_the_overpass_plate_seats_the_frame_on_the_road_beneath_off_the_map_too():
    """The deck member's plate is the road beneath (y 0.0); class A reads
    the zero there and every body rides it — a body whose own anchor reads
    no surface (an abutment off the map) is anchored at the plate's seat."""
    ov = OD._Overpass("dsf:obj9", "objects/crossing.obj", (), ((0.0, 1.0), (5.0, 1.0)), (-7,), 7.5)
    plates = RI._edge_seat_plates(types.SimpleNamespace(structures=(), overpasses=(ov,)), set())
    y, st, clear, kind = plates["dsf:obj9"]
    assert (y, clear, kind) == (0.0, 0.0, RI.OVERPASS_PLATE) and len(st) == 2
    m = types.SimpleNamespace(plate_kind=kind, plate_y=y,
                              plate_stations=((36.0, -86.0), (36.0, -85.9999)))
    zero, where, seat = ADS.airside_zero(m, (), lambda la, lo: 167.0)
    assert abs(zero - 167.0) < 1e-9 and "road beneath" in where and seat[2] == 167.0
    off = AR.Anchor(AR.OTHER, 36.0003, -86.0, -5.5, "no design surface under any foot", None,
                    offset=(0.0, -5.5, -15.0))
    rec = Split(0, "dsf:obj8", "objects/crossing.obj", "/x/objects/crossing.obj",
                36.0, -86.0, 0.0, (Body(0, AR.OTHER, (0,), off, "objects/crossing__b0.obj"),))
    b = ADS.airside_deck(rec, types.SimpleNamespace(resource="objects/crossing.obj"),
                         (zero, where, seat), {}).bodies[0]
    assert b.anchor.surface_z == 167.0 and abs(b.anchor.surface_z - b.anchor.y_zero - 167.0) < 1e-9
    assert (b.anchor.lat, b.anchor.lon) == (seat[0], seat[1])
