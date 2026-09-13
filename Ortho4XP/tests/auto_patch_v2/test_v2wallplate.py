"""§33 TWINS — THE PACK'S WALL OBJECTS GOVERN THE MOUTH (owner RULINGS
2026-09-13d items 5 / 6 / 9; Fable 2026-09-13i).

One test per clause:

* (1) EVERY REFUSED RESOURCE IS NAMED — the four suppressed prefixes are
  gone, and a resource the cheap 06f gate never SCREENED is counted, not
  enumerated;
* (2) THE THIN-PLATE WALL CLASS — a plate spanning a bore takes that
  bore's mouth to the OBJECT'S END, at the object's width, with the axis
  on the object's centre; a plate that merely CLIPS a mapped way is
  refused by name; both numbers come from the law;
* (3) THE MOUTH CREST IS THE ROAD'S GROUND — a DEM sample standing more
  than ``bore_datum_m`` over the approach's ground is an overbridge
  embankment and the crest reads the approach; an ordinary portal cover
  is untouched;
* (4) A TERRAIN DECK IS TIED TO ITS ENDS — its datum is the higher of
  (trench floor + ``clearance_m``) and the ground at its two mapped ends.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport import thin_plates as _tp
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, OsmWay, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar import structure_approach as _sa
from auto_patch_v2.planar.structures import build_structures


# ── the fixture: a flat field with a ridge across the road at x = 0 ──────

class _Dem:
    """700 m everywhere, plus an EMBANKMENT ridge ``height`` high in a
    band ``half_w`` either side of x = ``ridge_x`` (``None`` = no ridge) —
    a road crossing OVER the tunnel road, exactly LEMD's item 6."""

    provenance = {"synthetic": "flat 700 m with an optional embankment ridge"}

    def __init__(self, ridge_x: float | None = None, half_w: float = 4.0,
                 height: float = 8.0):
        self.ridge_x, self.half_w, self.height = ridge_x, half_w, height

    def z(self, x: float, y: float) -> float:
        if self.ridge_x is None:
            return 700.0
        d = abs(x - self.ridge_x)
        return 700.0 + (self.height * (1.0 - d / self.half_w) if d < self.half_w else 0.0)

    def bounds(self):
        return (-40000.0, -40000.0, 40000.0, 40000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


TAGS_T = {"highway": "secondary", "tunnel": "yes", "lanes": "2"}
TAGS_R = {"highway": "secondary", "lanes": "2"}
TAGS_B = {"highway": "secondary", "bridge": "yes", "lanes": "2"}


def _airport(law, ways=(), dem=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), tuple(ways), (), (), pack, dem or _Dem(),
                   law.ruleset_key)


# ── (2) the thin-plate wall class ────────────────────────────────────────

def _plate(x0: float, x1: float, half_w: float, bore_ways=(), bridge_ways=()):
    plan = Polygon(_rect(x0, -half_w, x1, half_w))
    return _tp.WallPlate("wall-plate:Fixture.obj@0", "objects/Fixture.obj", "dsf:obj1",
                         plan, ((x0, 0.0), (x1, 0.0)), x1 - x0, 2.0 * half_w,
                         1.03, 1.03, None, tuple(bore_ways), tuple(bridge_ways))


class _Placed:
    """The two fields ``authored_axis_ends`` reads off a placement."""

    def __init__(self, xy, heading_deg=0.0):
        self.xy, self.heading_deg = xy, heading_deg


def test_the_objects_own_box_is_the_corridor(law):
    """§33 (2): the AUTHORED box gives the axis (its long side), the WIDTH
    (its short side) and the PORTALS (the short sides' midpoints) — never
    the plan hull's minimum rotated rectangle, which minimises AREA and
    turns a tapered plate's axis off the object's own centre (measured
    LEMD Bridge3: 354.2 x 20.2 m by the hull rectangle, 354.2 x 25.1 m by
    the object)."""
    out = _tp.authored_axis_ends(_Placed((0.0, 0.0)), -13.6, 11.5, -354.2, 0.0)
    assert out is not None
    length, width, e0, e1 = out
    assert length == pytest.approx(354.2)
    assert width == pytest.approx(25.1)
    # the ends stand on the object's own centreline (x = the box's middle)
    assert e0 != e1
    assert math.hypot(e0[0] - e1[0], e0[1] - e1[1]) == pytest.approx(354.2, abs=0.01)


def test_a_thin_plate_moves_the_mouth_to_the_objects_end_at_its_width(law):
    """§33 (2) / bar 5: a bore mouth inside a plate that SPANS its bore is
    the object's — it moves to the object's end (the rectangle's short-side
    midpoint, so the axis is the object's centre) and takes the object's
    width, and the ramp keeps the mapped road beyond."""
    # the bore runs x -100..0 (its mapped end at x = 0, 1.0 m off centre);
    # the plate spans x -177..+177 and is 25.1 m wide
    bore = OsmWay(-101, "big_roads", ((-100.0, 1.0), (0.0, 1.0)), False, TAGS_T)
    road = OsmWay(-201, "big_roads", ((0.0, 1.0), (400.0, 1.0)), False, TAGS_R)
    ways = [bore, road]
    bores = _sa.chains([bore])
    ms, dropped = _sa.mouths(bores, ways, law, 600.0)
    east = [m for m in ms if m.xy[0] > -1.0]
    assert len(east) == 1 and east[0].width_m == pytest.approx(7.0)   # lanes x 3.5

    plate = _plate(-177.0, 177.0, 12.55, bore_ways=((-101, 100.0),))
    out, notes = _sa.apply_plates(list(ms), [plate], ways, law, 600.0)
    moved = [m for m in out if m.xy[0] > 100.0]
    assert len(moved) == 1, notes
    m = moved[0]
    assert m.xy == pytest.approx((177.0, 0.0))          # the object's end
    assert abs(m.xy[1]) <= 0.3                          # bar: axis on its centre
    assert m.width_m == pytest.approx(25.1)             # bar: the object's width
    assert m.inward[0] < 0.0                            # into the plate
    # BOTH of the bore's mouths stand inside the plate, so both move —
    # one to each of the object's ends (Bridge3 governs -5931's two mouths)
    assert len(notes) == 2 and all("wall-plate:Fixture.obj@0" in n for n in notes)
    # the west mouth stands outside the plate's bore reach but INSIDE its
    # plan, and it belongs to the same bore, so it moves to the far end
    west = [m for m in out if m.xy[0] < 0.0]
    assert len(west) == 1 and west[0].xy == pytest.approx((-177.0, 0.0))


def test_a_mouth_outside_every_plate_is_untouched(law):
    bore = OsmWay(-101, "big_roads", ((-100.0, 1.0), (0.0, 1.0)), False, TAGS_T)
    ways = [bore, OsmWay(-201, "big_roads", ((0.0, 1.0), (400.0, 1.0)), False, TAGS_R)]
    ms, _d = _sa.mouths(_sa.chains([bore]), ways, law, 600.0)
    plate = _plate(2000.0, 2354.0, 12.55, bore_ways=((-999, 100.0),))
    out, notes = _sa.apply_plates(list(ms), [plate], ways, law, 600.0)
    assert notes == []
    assert [m.xy for m in out] == [m.xy for m in ms]
    assert [m.width_m for m in out] == [m.width_m for m in ms]


def test_the_thin_plate_floor_is_read_from_the_law(law):
    """The class's gate is ``[tunnel.object] thin_plate_min_m``, never a
    literal — LEMD's Bridge3 spans 1.03 m and its plates 1.0-1.5 m."""
    assert law.tables.structures.tunnel.object.thin_plate_min_m == pytest.approx(1.0)
    least_skirt = min(law.tables.structures.tunnel.object.skirt_min_depth_m,
                      law.tables.structures.tunnel.object.edge_wall_min_skirt_m)
    assert law.tables.structures.tunnel.object.thin_plate_min_m < least_skirt


# ── (3) the mouth crest is the road's ground ─────────────────────────────

def _one_tunnel(law, dem, ways):
    cells = [Cell(0, "apron", "apron1", _rect(-300, -120, 300, 120), (), None, None,
                  "airside", "apron", {})]
    cl = Classification(tuple(cells), (), {}, ())
    _c, tunnels, stats = build_structures(_airport(law, ways, dem), cl, law)
    return tunnels, stats


def test_a_mouth_on_an_overbridge_embankment_reads_the_approachs_ground(law):
    """§33 (3) / bar 6: the DEM at the mouth stands 6 m over the approach's
    ground — more than ``bore_datum_m`` + ``split_tol_m`` — so it is an
    embankment crossing the road, not the portal's cover; the crest reads
    the approach and the ramp climbs instead of descending."""
    bore = OsmWay(-101, "big_roads", ((-200.0, 0.0), (0.0, 0.0)), False, TAGS_T)
    road = OsmWay(-201, "big_roads", ((0.0, 0.0), (260.0, 0.0)), False, TAGS_R)
    tn_law = law.tables.structures.tunnel
    flat, s_flat = _one_tunnel(law, _Dem(), [bore, road])
    ridge, s_ridge = _one_tunnel(law, _Dem(ridge_x=-2.0), [bore, road])
    east_flat = [t for t in flat if t.axis[0][0] > -1.0][0]
    east_ridge = [t for t in ridge if t.axis[0][0] > -1.0][0]
    # the DEM the mouth samples: 700 on the flat field, ~707 on the ridge
    assert east_flat.mouth_dem_z == pytest.approx(700.0, abs=0.05)
    assert s_flat.crest_from_approach == []
    assert s_ridge.crest_from_approach and "-101" in s_ridge.crest_from_approach[0]
    # ...and the CREST comes back to the approach's ground + bore_datum_m,
    # so the mouth floor is the road's own level and the ramp CLIMBS
    assert east_ridge.mouth_dem_z == pytest.approx(700.0 + tn_law.bore_datum_m, abs=0.05)
    assert east_ridge.mouth_z == pytest.approx(700.0, abs=0.05)


def test_an_ordinary_portal_cover_is_not_capped(law):
    """The cap bites only beyond ``bore_datum_m + split_tol_m``: a portal
    whose cover stands within the bore datum of the road keeps its DEM
    crest, so the other corridors do not move."""
    bore = OsmWay(-101, "big_roads", ((-200.0, 0.0), (0.0, 0.0)), False, TAGS_T)
    road = OsmWay(-201, "big_roads", ((0.0, 0.0), (260.0, 0.0)), False, TAGS_R)
    tunnels, stats = _one_tunnel(law, _Dem(), [bore, road])
    assert stats.crest_from_approach == []
    for t in tunnels:
        assert t.mouth_dem_z == pytest.approx(700.0, abs=0.05)


# ── (4) a terrain deck is tied to its ends ───────────────────────────────

def test_a_terrain_deck_carries_the_ground_at_its_two_mapped_ends(law):
    """§33 (4) / bar 9: the deck record carries the ground at the mapped
    bridge way's TWO ENDS — the constraint generator holds the deck at the
    higher of that and (trench floor + ``clearance_m``), the ramp beneath
    yielding downward.  Without them nothing tied the deck to anything:
    LEMD's -6288/-6291 came out at the DEM in the trench, 603.8, against an
    apron at 606.5."""
    bore = OsmWay(-101, "big_roads", ((-200.0, 0.0), (0.0, 0.0)), False, TAGS_T)
    road = OsmWay(-201, "big_roads", ((0.0, 0.0), (400.0, 0.0)), False, TAGS_R)
    deck = OsmWay(-301, "big_roads", ((60.0, -40.0), (60.0, 40.0)), False, TAGS_B)
    tunnels, _stats = _one_tunnel(law, _Dem(), [bore, road, deck])
    decks = [d for t in tunnels for d in t.decks if d.datum == "dem"]
    assert decks, "the mapped bridge way makes a terrain deck"
    for d in decks:
        assert len(d.end_z) == 2 and len(d.end_ref) == 2 and len(d.end_xy) == 2
        assert all(not math.isnan(z) for z in d.end_z)
        assert all(z == pytest.approx(700.0, abs=0.05) for z in d.end_z)
        # both ends stand in the fixture apron: the deck meets THAT surface's
        # own solved value, not the DEM under it
        assert set(d.end_ref) == {"apron1"}


# ── (1) every screened resource is named ─────────────────────────────────

def _write_obj(path, vt, tris):
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    lines += ["IDX " + " ".join(str(i) for i in idx[k:k + 10]) for k in range(0, len(idx), 10)]
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return path


def _box_obj(path, hx, hz, y0, y1):
    """A closed box over the plan rectangle ±hx by ±hz, y0..y1 — LEMD's
    Bridge3 in miniature: a PLATE, all its solids above the seat."""
    vt: list = []
    tris: list = []
    quad = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    for x, z in quad:
        vt.append((x, y0, z))
        vt.append((x, y1, z))
    for k in range(4):
        i, j = 2 * k, 2 * ((k + 1) % 4)
        tris += [(i, i + 1, j + 1), (i, j + 1, j)]
    tris += [(1, 3, 5), (1, 5, 7), (0, 4, 2), (0, 6, 4)]
    return _write_obj(path, vt, tris)


@pytest.fixture(scope="module")
def plate_pack(tmp_path_factory, law):
    from auto_patch_v2.airport import obj8
    from auto_patch_v2.model.airport import DsfObject
    d = tmp_path_factory.mktemp("plates") / "objects"
    d.mkdir()
    _box_obj(d / "plate.obj", 12.55, 177.1, -0.03, 1.003)     # 25.1 x 354.2, 1.03 m
    _box_obj(d / "stub.obj", 3.0, 4.0, 0.0, 4.0)              # a stub in plan
    _box_obj(d / "thick.obj", 12.55, 177.1, -0.03, 6.0)       # 6 m: not a plate
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    bore = OsmWay(-101, "big_roads", ((0.0, -150.0), (0.0, 150.0)), False, TAGS_T)
    ap = _airport(law, [bore])
    placed = []
    for k, n in enumerate(("plate", "stub", "thick")):
        placed.append(obj8.PlacedObject(f"dsf:obj{k}", str(d / f"{n}.obj"), str(d / f"{n}.obj"),
                                        (0.0, 0.0), 0.0, "OBJECT", 700.0, 0.0, 0.0, (), None,
                                        None, None, ()))
    return ap, placed, cache


def test_the_plate_is_read_and_the_thick_and_stub_bodies_are_not(plate_pack, law):
    """§33 (2): the class is exactly the GAP the wall pre-screen leaves —
    ``thin_plate_min_m`` up to ``least_skirt``.  A 6 m body is a building,
    not a plate; a stub in plan is refused by the same length gate the
    wall reader uses.  Without the ceiling the class swallowed 112 LEMD
    "plates", a 1,035 x 557 m cargo terminal among them."""
    from auto_patch_v2.airport.thin_plates import read_plates
    ap, placed, cache = plate_pack
    plates, stats = read_plates(ap, placed, cache, law)
    assert [p.id.split(":")[1] for p in plates] == ["plate.obj@0"]
    p = plates[0]
    assert p.kind == "bore" and [w for w, _L in p.bore_ways] == [-101]
    assert p.width_m == pytest.approx(25.1, abs=0.05)
    assert p.length_m == pytest.approx(354.2, abs=0.05)
    assert p.top_z is None                     # a DRAPED placement states no datum
    assert any("DRAPED" in n for n in p.notes)


def test_every_screened_resource_is_named_with_its_verdict(plate_pack, law):
    """§33 (1): the four suppressed prefixes are GONE.  ``read_corridors``
    refused LEMD's Bridge3 for "no wall skirt" and said so to nobody — 77
    of 182 screened resources carried a verdict no report ever printed.
    Every resource the pre-screen READ is now named; the ones the cheap
    06f gate skipped before reading are COUNTED (``not_screened``)."""
    from auto_patch_v2.airport.tunnel_objects import read_corridors
    ap, placed, cache = plate_pack
    corridors, stats = read_corridors(ap, placed, cache, law)
    assert corridors == []
    named = {r.split(" x")[0].split(": ")[0] for r in stats.refused}
    assert {"plate.obj", "stub.obj", "thick.obj"} <= named, stats.refused
    assert any("no wall skirt" in r for r in stats.refused)
    assert any("a stub: the plan extent" in r or "a stub: the hull" in r
               for r in stats.refused)
    # the counter exists and is a COUNT, never a list of a thousand names
    assert isinstance(stats.not_screened, int)
