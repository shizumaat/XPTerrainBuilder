"""Lane ``tunnelwitness2`` twins — issues #65, #5 [SPJC-3], #12 [OTHH-1]
Q-12b (owner RULINGS 2026-09-27a (3) (4)).

#65: ``structure_service._rise_m`` read the ground over a bore against the
MEAN of its two ends, so a bore under ground that merely slopes read half
its own fall as a hill.  The rise is now the ground standing above THE
LINE BETWEEN THE TWO MOUTH GROUNDS.
"""
from __future__ import annotations

import types

import pytest
from shapely.geometry import LineString

from auto_patch_v2.planar.structure_service import _rise_m


class _Dem:
    provenance = {"source": "fixture"}

    def __init__(self, fn):
        self.fn = fn

    def z(self, x, y):
        return self.fn(x, y)

    def bounds(self):
        return (-20000.0, -20000.0, 20000.0, 20000.0)


def _ap(fn):
    return types.SimpleNamespace(dem=_Dem(fn))


# ── #65: the rise is read against the mouth chord ───────────────────────

def test_a_SLOPING_bore_under_flat_ground_reads_ZERO_rise():
    """SPJC -5724: the DEM falls 21.97 -> 21.44 m along 35 m.  Against the
    mean of the ends it read +0.27 m; against the chord it reads 0.  A
    bore falling 2.0 m (which passed ``terrain_rise_m`` 0.5 before) also
    reads 0."""
    ln = LineString([(300.0, -100.0), (335.0, -100.0)])
    spjc = _ap(lambda x, y: 21.97 - (0.53 / 35.0) * (x - 300.0))
    assert _rise_m(spjc, ln) == pytest.approx(0.0, abs=1e-9)
    steep = _ap(lambda x, y: 30.0 - (2.0 / 35.0) * (x - 300.0))
    assert _rise_m(steep, ln) == pytest.approx(0.0, abs=1e-9)


def test_a_real_HILL_reads_its_rise_over_the_chord_even_on_a_slope():
    """A ridge 3.0 m high over the middle of a bore whose mouths differ by
    2.0 m reads 3.0 m over the chord (the mean-of-ends read 4.0 there —
    the error ran both ways)."""
    ln = LineString([(0.0, 0.0), (100.0, 0.0)])

    def hill(x, y):
        base = 50.0 - 0.02 * x                      # 50.0 -> 48.0
        return base + (3.0 if 40.0 <= x <= 60.0 else 0.0)

    assert _rise_m(_ap(hill), ln) == pytest.approx(3.0, abs=1e-6)
    flat_hill = _ap(lambda x, y: 10.0 + (0.7 if 40.0 <= x <= 60.0 else 0.0))
    assert _rise_m(flat_hill, ln) == pytest.approx(0.7, abs=1e-6)


def test_a_bore_in_a_DIP_reads_no_rise():
    """Ground BELOW the chord everywhere is no cover at all."""
    ln = LineString([(0.0, 0.0), (100.0, 0.0)])
    dip = _ap(lambda x, y: 10.0 - (1.0 if 20.0 <= x <= 80.0 else 0.0))
    assert _rise_m(dip, ln) == pytest.approx(0.0, abs=1e-9)   # the mouths themselves


# ── #5 [SPJC-3]: an OSM tunnel inside the fence is its own witness ──────

from auto_patch_v2.classify.roles import Cell, Classification  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import (Airport, Boundary, OsmWay, Runway,  # noqa: E402
                                         RunwayEnd, SceneryPack)
from auto_patch_v2.model.frame import Frame  # noqa: E402
from auto_patch_v2.planar.structures import build_structures  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


SPJC_TAGS = {"highway": "secondary", "lanes": "3", "tunnel": "yes"}


def _spjc(law, fence=_rect(-800, -800, 800, 800), bore_pts=((300.0, -100.0), (335.0, -100.0)),
          tags=SPJC_TAGS, partition=None, extra_cells=()):
    """SPJC -5724's shape: a 35 m ``secondary`` bore on a plane falling
    0.53 m, the nearest classified cell off it, inside a fence."""
    frame = Frame("ZZZZ", origin=(-12.03, -77.11), identity_dp=11)
    ends = (RunwayEnd("16", (0.0, 600.0), (0, 0), 0.0, 0.0, 22.0, "fixture"),
            RunwayEnd("34", (0.0, -600.0), (0, 0), 0.0, 0.0, 22.0, "fixture"))
    rw = Runway("16/34", 45.0, 1, ends, 4, "E")
    bore = OsmWay(-5724, "big_roads", tuple(bore_pts), False, dict(tags))
    # the road continues from both mouths, as -5708 / -5723 do at SPJC
    (ax, ay), (bx, by) = bore_pts[0], bore_pts[-1]
    road = {"highway": "secondary", "lanes": "3"}
    ways = (bore, OsmWay(-5708, "big_roads", ((ax - 150.0, ay), (ax, ay)), False, road),
            OsmWay(-5723, "big_roads", ((bx, by), (bx + 150.0, by)), False, road))
    fences = (Boundary("boundary0", fence, ()),) if fence else ()
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 22.0, (rw,), (), (), {}, (),
                      (), fences, (), ways, (), (), pack,
                      _Dem(lambda x, y: 21.97 - 0.015 * (x - 300.0)),
                      law.ruleset_key, partition=partition)
    cells = [Cell(0, "runway", "16/34", _rect(-22, -600, 22, 600), (), 4, "E",
                  "airside", "runway", {}),
             # the nearest classified cell stands OFF the bore's line (SPJC's
             # pav49 is 211 m away), so neither ramp is stopped by it
             Cell(1, "apron", "pav49", _rect(360, 40, 460, 140), (), None, None,
                  "airside", "apron", {})] + list(extra_cells)
    return build_structures(airport, Classification(tuple(cells), (), {}, ()), law)


def _refusals(st):
    return [ln for ln in st.mouths_off_field_nearest if "NOT A TERRAIN TUNNEL" in ln]


def test_an_OSM_tunnel_INSIDE_the_fence_under_nothing_is_BUILT(law):
    """Owner RULINGS 2026-09-27a (4): "an OSM ``tunnel=yes`` way INSIDE the
    airport boundary IS a terrain-tunnel witness on its own".  SPJC -5724:
    cover 0.0 m, no crossing, rise 0.00 over its chord, no layer — and
    both mouths are built."""
    _cl, tunnels, st = _spjc(law)
    assert st.bores == 1 and st.tunnels == 2, st.mouths_off_field_nearest
    assert not _refusals(st)


def test_the_same_bore_with_NO_fence_or_OUTSIDE_it_is_still_refused(law):
    """Outside the fence the existing witnesses apply: the VMMC class
    (16d) stays closed.  A bore STRADDLING the fence line does not lie
    inside it either."""
    for fence in (None, _rect(-800, -800, 200, 800), _rect(-800, -800, 320, 800)):
        _cl, _t, st = _spjc(law, fence=fence)
        assert st.tunnels == 0, fence
        named = _refusals(st)
        assert len(named) == 1 and "-5724 PASSES UNDER NOTHING AT GRADE" in named[0]


def test_the_fence_reads_a_MAPPED_tunnel_only(law):
    """The fence trusts OSM's ``tunnel`` tag, so it reads only a bore every
    way of which carries an admitted one — a ``building_passage`` is not a
    bore at all (§26) and a synthesised §34 (5) underpass is not OSM's."""
    from auto_patch_v2.planar.structure_service import _osm_tunnel
    from auto_patch_v2.planar.structure_underpass import UNDERPASS_TAG
    tn = law.tables.structures.tunnel
    mk = lambda tags: types.SimpleNamespace(ways=[types.SimpleNamespace(tags=tags)])  # noqa: E731
    assert _osm_tunnel(mk(SPJC_TAGS), tn.admitted_values)
    assert not _osm_tunnel(mk(dict(SPJC_TAGS, tunnel="building_passage")), tn.admitted_values)
    assert not _osm_tunnel(mk(dict(SPJC_TAGS, **{UNDERPASS_TAG: "-1"})), tn.admitted_values)


# ── #12 Q-12b: a bore entering a PACK building unit is refused ──────────

def _ll_ring(x0, y0, x1, y1):
    to_ll = Frame("ZZZZ", origin=(-12.03, -77.11), identity_dp=11).transformers()[1]
    return tuple(to_ll(x, y) for x, y in _rect(x0, y0, x1, y1))


def _part(base_y, height_m, ring, **kw):
    la = [c[0] for c in ring]
    lo = [c[1] for c in ring]
    return types.SimpleNamespace(base_y=base_y, height_m=height_m, rings=(ring,),
                                 box=(min(la), min(lo), max(la), max(lo)),
                                 line=kw.get("line", False), scatter=False)


def _partition(*members):
    """``members``: ``(id, resource, deck_kind, parts)``."""
    ms = [types.SimpleNamespace(id=i, resource=r, deck_kind=d, deck_ring=None,
                                scatter=False, parts=tuple(p)) for i, r, d, p in members]
    return types.SimpleNamespace(units=(types.SimpleNamespace(id="unit:24", members=ms),))


EAST_END = _ll_ring(325, -115, 360, -85)      # holds the bore's east mouth (335, -100)


def test_a_bore_into_a_multi_storey_PACK_CAR_PARK_is_REFUSED_even_inside_the_fence(law):
    """OTHH ``tunnel:-10442`` (Q-12b, ratified 27a (3)): both mouths stand
    in ``OTHH_Terminal_Parking_000`` — 0.67 m floor slabs at 0.52 / 3.45 m,
    every one a LEAF by §16g's walled test, the car park 4.1 m over its
    zero.  (a) runs before the fence: the building's ramp is not a
    terrain tunnel inside the fence either."""
    park = _partition(("dsf:obj1", "Buildings/Terminal/OTHH_Terminal_Parking_000.obj",
                       "candidate", (_part(0.52, 0.67, EAST_END),
                                     _part(3.45, 0.67, EAST_END))))
    _cl, tunnels, st = _spjc(law, partition=park)
    assert st.tunnels == 0 and not tunnels
    named = _refusals(st)
    assert len(named) == 1, st.mouths_off_field_nearest
    assert "-5724 ENTERS A PACK BUILDING" in named[0]
    assert "OTHH_Terminal_Parking_000.obj (unit:24) stands 4.1 m" in named[0]


def test_SUNK_trench_geometry_DECKS_and_TUNNEL_OBJECTS_are_not_buildings(law):
    """What a real tunnel ends in stays built: HECA's ``concrete_3`` (base
    -1.84, 2.66 m: 0.82 m over its zero) and GEML's portal geometry (base
    -26); a DECK member (HECA ``T3_road``, ``deck_kind`` flag) however
    tall; a pack tunnel object read as a corridor (by placement id)."""
    sunk = _partition(("dsf:obj2", "concrete_3.obj", "", (_part(-1.84, 2.66, EAST_END),)),
                      ("dsf:obj3", "GEML_Misc2.obj", "candidate",
                       (_part(-26.2, 12.8, EAST_END),)))
    _cl, _t, st = _spjc(law, partition=sunk)
    assert st.tunnels == 2 and not _refusals(st), st.mouths_off_field_nearest
    deck = _partition(("dsf:obj4", "T3_road.obj", "flag", (_part(0.0, 9.0, EAST_END),)))
    _cl, _t, st = _spjc(law, partition=deck)
    assert st.tunnels == 2 and not _refusals(st)
    from auto_patch_v2.planar.structure_service import _PackBuildings
    tun = _partition(("dsf:obj14034", "Objects/tunnels/tunnel middle - east.obj",
                      "candidate", (_part(-15.0, 20.0, EAST_END),)))
    ap = types.SimpleNamespace(partition=tun,
                               frame=Frame("ZZZZ", origin=(-12.03, -77.11), identity_dp=11))
    assert _PackBuildings(ap, law).at((335.0, -100.0)) is not None
    assert _PackBuildings(ap, law, (), {"dsf:obj14034"}).at((335.0, -100.0)) is None


def test_the_pack_building_reads_its_RING_not_its_plan_box(law):
    """``Part.box`` is the solid's plan box and a footprint ring can stand
    past it (OTHH ``tunnel south west 2``: its ring runs 16 m beyond the
    box, where -5214 ends).  The index is the ring's own bounds."""
    from auto_patch_v2.planar.structure_service import _PackBuildings
    p = _part(0.5, 6.0, EAST_END)
    p.box = (p.box[0], p.box[1], p.box[0] + 1e-6, p.box[1] + 1e-6)     # a tiny box
    ap = types.SimpleNamespace(partition=_partition(("dsf:obj5", "Garage.obj", "", (p,))),
                               frame=Frame("ZZZZ", origin=(-12.03, -77.11), identity_dp=11))
    hit = _PackBuildings(ap, law).at((335.0, -100.0))
    assert hit is not None and hit[0] == "Garage.obj" and hit[2] == pytest.approx(6.5)
