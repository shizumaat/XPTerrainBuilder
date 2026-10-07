"""Lane v2wallcorridor twins (RULINGS 2026-09-08l / 08m / 08n / 08o; spec
``docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md`` §6 / §6a):

* DEPTH (08l/08o): a wall object's trench depth is its FLOOR SLAB when it
  carries one (crest − slab), else ``tunnel.bore_datum_m`` for every mouth
  kind — never the crest's height above the anchor; a bore END within
  ``bore_end_tolerance_m`` of the plate makes the object that bore's mouth
  and the OSM mouth PAIRS with it (no overlap refusal); a closed-end
  fallback with no road through the trench is refused by name.
* SEAT STATIONS (08o): the plate stations stand outside the EMITTED rim
  ring and outside the ramp beyond the wall end.
* LAW C (08m/08n): two kerb bands 10 m apart 1.9 m deep under a deck → a
  level corridor of TWO capless halves, the floor at the wall bottom, a
  ramp beyond each end at ``ramp_grade``; one band alone → nothing; bands
  25 m apart → nothing; a crossing family face → a closed BAY with one
  ramp; a ramp meeting AIRSIDE pavement stops and steepens to ≤
  ``max_ramp_grade``, refused loudly above it; a descending wall bottom
  → a GARAGE RAMP cut as authored, no synthetic ramp, refused above
  ``max_authored_grade``; headroom under ``min_headroom_m`` → refused;
  the generator's rows solve; ``seat = "none"``; the law register.
Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.tunnel_objects import read_corridors, signature
from auto_patch_v2.airport.wall_corridors import CLASS_BAY, CLASS_GARAGE, CLASS_LEVEL
from auto_patch_v2.airport.wall_family import read_wall_corridors
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import structures as structure_rows
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import render_patch
from auto_patch_v2.law import Law
from auto_patch_v2.law.cutout_schema import SEAT_NONE, WALL_BOTTOM
from auto_patch_v2.law.tables import is_structure_role, role_cap, role_side
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.constraints import Pin
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.pipeline.build import _plate_seats, plate_stations
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.structures import _pad_relief_m as _pad_relief, build_structures
from auto_patch_v2.planar.wall_corridor_ramps import (BAY_EXEMPT, GARAGE_ROLE, KIND, RAMP_ROLE,
                                                     wall_corridor_groups)
from auto_patch_v2.solve import Options, Status, solve_design

from test_tunnel_objects import _airport, _cells as _wall_cells, _rect, _slab, _wall_obj, _write


# ── synthetic OBJ8 ───────────────────────────────────────────────────────

def _vwall(vt, tris, x0, x1, z0, z1, y_z0, y_z1, top):
    """Four VERTICAL faces of a thin kerb band along authored z (no top,
    no bottom): the bottom at ``y_z0`` at ``z0`` running to ``y_z1`` at
    ``z1`` (level or descending), the top at ``top``."""
    b = len(vt)
    for x, z, yb in ((x0, z0, y_z0), (x1, z0, y_z0), (x1, z1, y_z1), (x0, z1, y_z1)):
        vt.append((x, yb, z))
        vt.append((x, top, z))
    for k in range(4):
        i, j = b + 2 * k, b + 2 * ((k + 1) % 4)
        tris += [(i, i + 1, j + 1), (i, j + 1, j)]


#: The synthetic corridor's own geometry, named because §34 (9) (5) reads
#: it: the walls run ``DECK_HALF_LEN_M`` each way from the midpoint and the
#: deck slab over them stops ``DECK_END_INSET_M`` short of each wall end,
#: so each half is COVERED for ``DECK_HALF_LEN_M − DECK_END_INSET_M`` of
#: its length and the rest of its wall stands in the open.
DECK_HALF_LEN_M = 40.0
DECK_END_INSET_M = 10.0
#: The covered start is walked at the group's station grid, so it lands
#: within one grid step of the plate's true edge.
STATION_TOL_M = 1.0


def _corridor_obj(path, width=10.0, depth=1.9, top=0.5, thick=0.3, deck_y=2.6, end_wall=False,
                  drop=0.0, half_len=DECK_HALF_LEN_M, one_band=False, end_top=None,
                  deck_inset=DECK_END_INSET_M, short=0.0):
    """Two kerb bands ``width`` apart between their inner faces, ``depth``
    under the seat, ``top`` above it, under a deck slab at ``deck_y``
    (``None`` = open air); ``end_wall`` closes the +z end, rising to
    ``end_top`` (default: the kerbs' own ``top``; ``basin.contact_band_m``
    or more over the ground makes it the BUILT WALL of spec §12h's W3);
    ``drop`` makes the bottom DESCEND from −depth at −z to −depth − drop
    at +z; ``deck_inset`` is how far short of each wall end the deck stops
    (0: the cover reaches the wall ends); ``short`` stops the +x band that
    far short of the +z end (two walls of UNEQUAL length)."""
    vt: list = []
    tris: list = []
    hw = width / 2.0
    _vwall(vt, tris, -hw - thick, -hw, -half_len, half_len, -depth, -depth - drop, top)
    if not one_band:
        _vwall(vt, tris, hw, hw + thick, -half_len, half_len - short, -depth, -depth - drop, top)
    if end_wall:
        _vwall(vt, tris, -hw, hw, half_len, half_len + thick, -depth - drop, -depth - drop,
               top if end_top is None else end_top)
    if deck_y is not None:
        _slab(vt, tris, -hw - 2.0, hw + 2.0, -half_len + deck_inset,
              half_len - deck_inset, deck_y, deck_y + 0.3)
    return _write(path, vt, tris)


@pytest.fixture(scope="module")
def law():
    # LAW C is read at every airport (spec §12h; RULINGS 2026-10-05g): the
    # identifier only resolves the ruleset.  The three general clauses are
    # twinned in ``test_v2wallmouth.py``.
    return Law.for_airport("OTHH")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8", newline="")
    return {
        "dir": d,
        # the depth law's objects (test_tunnel_objects' builders)
        "wall": _wall_obj(d / "wall.obj", end_a=True),                  # a skirt, no floor
        "floored": _wall_obj(d / "floored.obj", end_a=True, floor=True),  # a floor slab at −12
        # Law C
        "level": _corridor_obj(d / "level.obj"),
        # 07b (2) twins: the cover reaching both wall ends; one wall 8 m short
        "roofed": _corridor_obj(d / "roofed.obj", deck_inset=0.0, deck_y=6.0),
        "unequal": _corridor_obj(d / "unequal.obj", short=8.0),
        "single": _corridor_obj(d / "single.obj", one_band=True),
        "wide": _corridor_obj(d / "wide.obj", width=25.0),
        # §12h W3: the bay runs out from a BUILT WALL — its end wall rises
        # 2.5 m over the ground — under open sky (a deck 2.6 m over the
        # ground across a 10 m bay would stand ACROSS its mouth, under the
        # headroom: W1s reads that mouth closed)
        "bay": _corridor_obj(d / "bay.obj", end_wall=True, half_len=5.0, deck_y=None,
                             end_top=2.5),
        # a garage ramp under open sky with NOTHING at its deep end is two
        # bare walls (W3 refuses it); the garage's own wall closes ``garage``
        "garage_bare": _corridor_obj(d / "garage_bare.obj", depth=0.2, drop=3.0, deck_y=None),
        "garage": _corridor_obj(d / "garage.obj", depth=0.2, drop=3.0, deck_y=None,
                                end_wall=True, end_top=2.5),
        "steep": _corridor_obj(d / "steep.obj", depth=0.2, drop=25.0, deck_y=None),
        "low": _corridor_obj(d / "low.obj", deck_y=1.0),
    }


def _read(objs, law, placements, ways=()):
    airport = _airport(objs, law, placements, ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    return airport, cache, objects


def _cells(extra=()):
    """A runway far away and a GROUNDSIDE service road under the corridor
    (its host: cut, never a stop), plus ``extra`` cells."""
    return [Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside", "runway", {}),
            Cell(1, "service_road", "road1", _rect(-30, -150, 30, 150), (), None, None,
                 "groundside", "pavement", {})] + list(extra)


# ── the law register ─────────────────────────────────────────────────────

def test_law_register(law):
    tn = law.tables.structures.tunnel
    ob = tn.object
    wc = law.tables.structures.cutout.wall_corridor
    # 08l/08o: the depth datum and the bore-end tolerance
    assert ob.mouth_depth == "floor_slab"
    assert ob.bore_end_tolerance_m > ob.end_cap_open_m > 0.0
    assert not hasattr(ob, "floor_plate_max_m2")
    # Law C keys
    assert wc.mouth_depth == WALL_BOTTOM and wc.seat == SEAT_NONE
    assert 0.0 < wc.min_width_m < wc.max_width_m
    assert wc.min_wall_depth_m > 0.0 and wc.min_wall_length_m > 0.0 and wc.merge_gap_m >= 0.0
    assert 0.0 < wc.end_cap_cover_min <= 1.0 and wc.min_headroom_m > 0.0
    assert 0.0 < wc.max_ramp_grade < wc.max_authored_grade
    assert wc.parallel_max_deg > 0.0 and wc.station_m > 0.0
    # the two roles: structure, groundside, aliased for the oracle
    for role, cap in ((RAMP_ROLE, wc.max_ramp_grade), (GARAGE_ROLE, wc.max_authored_grade)):
        spec = law.tables.precedence.roles[role]
        assert spec.side == "groundside" and spec.structure and spec.value
        # RULINGS 2026-09-08u (2): the RAMP reads at the structure-ramp law's
        # 10 % (its own ceiling); the authored garage ramp keeps service_road
        # (no oracle law carries 25 % — the instrument limit stands, §7b row 3)
        assert spec.oracle_role == "tunnel_ramp"
        assert spec.oracle_law == ("structure_ramp" if role == RAMP_ROLE else "service_road")
        assert spec.oracle_cap == (wc.max_ramp_grade if role == RAMP_ROLE else None)
        assert is_structure_role(law, role) and role_side(law, role) == "groundside"
        assert role_cap(law, role).longitudinal == cap
        assert role not in law.tables.precedence.order


# ── DEPTH (08l / 08o) ────────────────────────────────────────────────────

def _bore(y_in, y_far=-400.0):
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    tags_r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((0.0, y_in), (0.0, y_far)), False, tags_t),
            OsmWay(-201, "big_roads", ((0.0, y_far), (0.0, y_far - 900.0)), False, tags_r))


def test_depth_is_the_floor_slab_else_the_bore_law(objs, law):
    """08l: a floor slab states the depth (crest − slab); a skirt takes
    ``bore_datum_m`` whatever the crest's height above the anchor."""
    tn = law.tables.structures.tunnel
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    skirt = signature(cache.geometry(str(objs["wall"])), cache.genuine(str(objs["wall"])), law)
    slab = signature(cache.geometry(str(objs["floored"])), cache.genuine(str(objs["floored"])), law)
    assert not isinstance(skirt, str) and skirt.floor_y is None
    assert not isinstance(slab, str) and slab.floor_y == pytest.approx(-12.0)
    # the object placed with its bore ending 10 m inside the closed end
    for name, depth in (("wall", tn.bore_datum_m), ("floored", 5.0 + 12.0)):
        airport, cache, objects = _read(objs, law, [(name, (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")],
                                        _bore(y_in=-40.0))
        cs, st = read_corridors(airport, objects, cache, law)
        assert len(cs) == 1, st.refused
        c = cs[0]
        assert c.mouth_kind == "bore" and c.depth_m == pytest.approx(depth)
        assert c.plate_y == pytest.approx(5.0)          # the crest stays the seat datum
        assert c.floor_z == pytest.approx(c.mouth_dem_z - depth)


def test_a_bore_end_within_the_tolerance_is_the_mouth_and_pairs(objs, law):
    """08o: the wall's closed end stands at authored z = −50 (frame y =
    +50 at heading 180 → the end wall at y = +50?  No: heading 180 puts
    the closed end at −y); a bore END 4 m OUTSIDE the plate (beyond
    ``end_cap_open_m`` 2, within ``bore_end_tolerance_m`` 5) makes the
    object that bore's mouth and the OSM mouth pairs with it — no OSM
    ramp, no overlap refusal."""
    ob = law.tables.structures.tunnel.object
    outside = ob.end_cap_open_m + (ob.bore_end_tolerance_m - ob.end_cap_open_m) / 2.0
    airport, cache, objects = _read(objs, law, [("wall", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")],
                                    _bore(y_in=-50.0 - outside))
    cs, st = read_corridors(airport, objects, cache, law)
    assert len(cs) == 1, st.refused
    c = cs[0]
    assert c.mouth_kind == "bore" and -101 in c.bore_ways
    # spec §29 (1): the far mouth at y = −400 must stand ON THE FIELD for
    # its OSM ramp to be built at all — the fixture's apron ends at −120,
    # so the classification is extended to reach it (the twin is about the
    # object taking the NEAR mouth, not about the mouth gate).
    cl = Classification(tuple(_wall_cells(y0=-450)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not sst.refused, sst.refused
    assert sst.mouths_replaced_by_object == 1 and sst.bores_replaced_by_object == 0
    t = [x for x in tunnels if x.source == "object"][0]
    assert -101 in t.replaced_ways
    # the bore's FAR mouth (y = −400) keeps its OSM ramp; none stands at the object
    osm = [x for x in tunnels if x.source == "osm"]
    assert len(osm) == 1 and osm[0].axis[0][1] == pytest.approx(-400.0, abs=5.0)


def test_the_mouth_gate_leaves_the_roofed_corridor_untouched(objs, law):
    """§29: the object/wall-corridor class (Laws B/C — the owner's EGLL
    exception, keyed on the PACK's geometry, never on OSM) does not pass
    through the OSM mouth gate.  With the fixture's own classification
    (the apron ends at y = −120, so the bore's far mouth at y = −400 is
    OFF the field) the corridor is still built exactly as before: only the
    off-field OSM ramp is gone."""
    ob = law.tables.structures.tunnel.object
    outside = ob.end_cap_open_m + (ob.bore_end_tolerance_m - ob.end_cap_open_m) / 2.0
    airport, cache, objects = _read(objs, law, [("wall", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")],
                                    _bore(y_in=-50.0 - outside))
    cs, st = read_corridors(airport, objects, cache, law)
    assert len(cs) == 1, st.refused
    cl = Classification(tuple(_wall_cells()), (), {}, ())
    _cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not sst.refused, sst.refused
    assert sst.mouths_off_field == 1 and sst.object_corridors == 1
    obj = [x for x in tunnels if x.source == "object"]
    assert len(obj) == 1 and -101 in obj[0].replaced_ways
    assert [x for x in tunnels if x.source == "osm"] == []


def test_a_bore_end_beyond_the_tolerance_is_not_the_mouth(objs, law):
    ob = law.tables.structures.tunnel.object
    airport, cache, objects = _read(objs, law, [("wall", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")],
                                    _bore(y_in=-50.0 - ob.bore_end_tolerance_m - 3.0))
    cs, st = read_corridors(airport, objects, cache, law)
    # no bore at the end, no facing placement, the closed end with a road
    # through the trench (the bore line crosses it? no — it ends outside):
    # refused by name as the closed-end fallback without a road
    assert not cs
    assert any("closed-end fallback" in r and "no mapped road" in r for r in st.refused), st.refused


def test_closed_end_fallback_with_a_road_through_is_a_mouth(objs, law):
    """A mapped road running THROUGH the trench lets the closed-end
    fallback stand (08o); its depth is the bore law's."""
    tn = law.tables.structures.tunnel
    road = (OsmWay(-301, "big_roads", ((0.0, -45.0), (0.0, 300.0)), False,
                   {"highway": "service"}),)
    airport, cache, objects = _read(objs, law, [("wall", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")], road)
    cs, st = read_corridors(airport, objects, cache, law)
    assert len(cs) == 1, st.refused
    assert cs[0].mouth_kind == "closed" and cs[0].depth_m == pytest.approx(tn.bore_datum_m)


# ── SEAT STATIONS (08o) ──────────────────────────────────────────────────

def test_plate_stations_stand_outside_the_emitted_rim_and_the_ramp_beyond(law):
    grid = law.tables.emit.identity.min_distinct_spacing_m
    step = law.tables.structures.bridge.abutment_sample_step_m
    rect = ((0.0, 0.0), (40.0, 0.0), (40.0, 12.0), (0.0, 12.0))
    # the emitted rim pushed 0.4 m OUTSIDE the outer face (08e deviation 2)
    rim = Polygon(rect).buffer(0.4, join_style="mitre")
    # the ramp beyond the wall end (x = 40 .. 70), 8 m wide about y = 6
    beyond = LineString([(40.0, 6.0), (70.0, 6.0)]).buffer(4.0 + 1.6 + grid)
    pts = plate_stations(rect, grid, step, tuple(rim.exterior.coords), beyond)
    assert pts
    assert all(not rim.contains(Point(p)) for p in pts)
    assert all(rim.exterior.distance(Point(p)) >= grid - 1e-6 for p in pts)
    assert all(not beyond.contains(Point(p)) for p in pts)
    # the ramp side keeps no station beyond the wall end line
    assert all(p[0] <= 40.0 + grid * 2.0 + 1e-6 for p in pts)


# ── LAW C (08m / 08n) ────────────────────────────────────────────────────

#: The fixture corridors run along ±y with a service way down that axis.
#: (RULINGS 2026-09-10ad: the 10z groundside-mouth clause (b'') is DELETED
#: — the road no longer admits anything; it is left here so these twins
#: read the same site as the round-2/3 measurements.)
def _axis_road(x: float = 0.0):
    return (OsmWay(-601, "airport_small_roads", ((x, -300.0), (x, 300.0)), False,
                   {"highway": "service"}),)


def _corridors(objs, law, name, ways=None):
    airport, cache, objects = _read(objs, law, [(name, (0.0, 0.0), 0.0, None, "OBJECT")],
                                    _axis_road() if ways is None else ways)
    recs, st = read_wall_corridors(airport, objects, cache, law)
    return airport, cache, objects, recs, st


def test_two_bands_under_a_deck_are_a_level_corridor_of_two_halves(objs, law):
    wc = law.tables.structures.cutout.wall_corridor
    airport, cache, objects, recs, st = _corridors(objs, law, "level")
    assert st.bands == 2 and st.pairs == 1 and st.corridors == 1, st.refused
    assert st.by_class == {CLASS_LEVEL: 2} and len(recs) == 2
    a, b = recs
    assert a.sibling == b.id and b.sibling == a.id
    for r in recs:
        assert r.cls == CLASS_LEVEL and r.ends == "open/open"
        assert r.width_m == pytest.approx(10.0, abs=0.05)
        assert r.length_m == pytest.approx(40.0, abs=0.05)
        # the floor = the wall bottom, 1.9 m under the ground, every station
        for z, g in zip(r.floors, r.grounds):
            assert g - z == pytest.approx(1.9, abs=0.02)
        # the synthetic deck prism has no underside: its top at 2.9 is the ceiling
        assert r.headroom_m == pytest.approx(2.9 + 1.9, abs=0.05)
    # the mouths meet at the midpoint
    assert a.axis[0] == pytest.approx(b.axis[0])
    groups = wall_corridor_groups(recs, law)
    assert len(groups) == 2 and all(g.kind == KIND and g.ramp_role == RAMP_ROLE for g in groups)
    assert all(not g.capped and not g.mouth_strip and not g.stop_at_pavement for g in groups)
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, (), groups)
    assert not sst.refused, sst.refused
    assert sst.wall_corridors == 2 and len(tunnels) == 2
    for t in tunnels:
        # THE RAMP RUNS THE WALLS' LENGTH (owner RULINGS 2026-10-07b (2)): at
        # grade at the walls' OUTER END (s 40), falling toward the building.
        # The deck slab covers each half for 30 of its 40 m (``_corridor_obj``:
        # ``half_len − 10``), so the uncovered wall is 10 m and 1.9 m of
        # depth would need 19 % over it — the knee moves back UNDER the
        # cover by the run ``max_ramp_grade`` needs (§34 (8), 14u): 19 m.
        assert t.source == KIND and t.design_grade == pytest.approx(wc.max_ramp_grade)
        assert t.top_s == pytest.approx(t.wall_length_m) and t.top_pinned and not t.clipped_by
        cover_s = DECK_HALF_LEN_M - DECK_END_INSET_M
        assert t.climb_from_s == pytest.approx(t.wall_length_m - 1.9 / wc.max_ramp_grade, abs=0.05)
        assert t.climb_from_s < cover_s - 1e-6
        assert any("back UNDER the building" in n for n in t.notes), t.notes
        # the published profile: the wall bottom to the knee, the design
        # line to the ground at the walls' outer end — nothing beyond it
        assert profile_z(t.profile, 0.0) == pytest.approx(t.mouth_z)
        assert profile_z(t.profile, t.climb_from_s) == pytest.approx(t.mouth_z, abs=1e-6)
        assert t.profile[-1][0] == pytest.approx(t.wall_length_m)
        assert profile_z(t.profile, t.top_s) == pytest.approx(
            airport.dem.z(*LineString(t.axis).interpolate(t.top_s).coords[0]), abs=1e-6)
    roles = {c.role for c in cl2.cells}
    assert RAMP_ROLE in roles and "retaining_wall" in roles and "tunnel_ramp" not in roles
    # seat = "none": never plate-seated
    class _PM:
        structures = tuple(tunnels)
        basins = ()
    assert _plate_seats(_PM(), law) == {}


def _ramps(objs, law, name):
    airport, _cache, objects, recs, st = _corridors(objs, law, name)
    assert st.by_class == {CLASS_LEVEL: 2} and len(recs) == 2, st.refused
    cl = Classification(tuple(_cells()), (), {}, ())
    _cl2, tunnels, sst = build_structures(airport, cl, law, objects, (),
                                          wall_corridor_groups(recs, law))
    assert not sst.refused and len(tunnels) == 2, sst.refused
    return airport, recs, tunnels


def test_a_cover_reaching_the_wall_end_still_ramps_the_full_wall_length(objs, law):
    """07b (2): with the deck over the walls' whole length nothing
    protrudes — the ramp is still the walls' FULL length (at grade at the
    outer end, the corridor's depth at s 0), never a run beyond the walls
    and never only the cap's run."""
    wc = law.tables.structures.cutout.wall_corridor
    airport, _recs, tunnels = _ramps(objs, law, "roofed")
    for t in tunnels:
        assert t.wall_length_m == pytest.approx(DECK_HALF_LEN_M, abs=0.05)
        assert t.climb_from_s == pytest.approx(0.0) and t.top_s == pytest.approx(t.wall_length_m)
        assert t.design_grade == pytest.approx(1.9 / t.wall_length_m, abs=0.002)
        assert t.design_grade < wc.max_ramp_grade and t.pinched is None
        assert t.profile[-1][0] == pytest.approx(t.wall_length_m)
        assert profile_z(t.profile, t.top_s) == pytest.approx(
            airport.dem.z(*LineString(t.axis).interpolate(t.top_s).coords[0]), abs=1e-6)


def test_walls_of_unequal_length_end_the_ramp_at_the_shorter_wall(objs, law):
    """07b (2) "at grade at the outer extent of the two retaining walls":
    the spec is silent on walls of unequal length (QUESTION to the owner);
    the corridor exists only where BOTH walls stand, so the ramp tops out
    at the SHORTER wall's end — on that side 8 m short of the other — and
    never runs past it."""
    _airport, recs, tunnels = _ramps(objs, law, "unequal")
    # the corridor is the walls' OVERLAP (80 − 8 m), halved at its midpoint
    assert sum(r.length_m for r in recs) == pytest.approx(2 * DECK_HALF_LEN_M - 8.0, abs=0.1)
    for t in tunnels:
        assert t.top_s == pytest.approx(t.wall_length_m)
        assert t.profile[-1][0] == pytest.approx(t.wall_length_m)
    # the two ramp tops stand at the overlap's ends: one at the LONGER
    # wall's end only where the shorter one also stands there
    a, b = (LineString(t.axis).interpolate(t.top_s) for t in tunnels)
    assert a.distance(b) == pytest.approx(2 * DECK_HALF_LEN_M - 8.0, abs=0.1)


@pytest.mark.parametrize("rise, wall_end, covered, closed, want", [
    # equal walls, 10 m protruding: 0.8 m at 8 % over the protruding run
    (0.8, 40.0, 30.0, False, (30.0, 0.08, 0.0, False)),
    # nothing protrudes: the full wall length, whatever grade (<= cap)
    (1.9, 40.0, None, False, (0.0, 1.9 / 40.0, 0.0, False)),
    # the span needs over the cap: the knee moves back under the building
    (1.9, 40.0, 30.0, False, (21.0, 0.1, 9.0, False)),
    # a service bay too short for the cap: exempt (07c (1)), no lift
    (1.9, 10.0, None, True, (0.0, 0.19, 0.0, True)),
])
def test_full_wall_ramp_plans(rise, wall_end, covered, closed, want):
    from auto_patch_v2.planar.wall_corridor_ramps import full_wall_ramp
    got = full_wall_ramp(10.0, ((0.0, 10.0 - rise), (wall_end, 10.0 - rise)), 10.0 - rise,
                         wall_end, covered, 0.10, closed)
    assert got[0] == pytest.approx(want[0]) and got[1] == pytest.approx(want[1])
    assert got[2] == pytest.approx(want[2]) and got[3] is want[3]


def test_an_open_half_too_short_for_the_cap_is_refused():
    from auto_patch_v2.planar.wall_corridor_ramps import full_wall_ramp
    why = full_wall_ramp(10.0, ((0.0, 8.1),), 8.1, 10.0, None, 0.10, False)
    assert isinstance(why, str) and "cannot run inside its walls" in why


def test_one_band_alone_and_bands_too_far_apart_are_nothing(objs, law):
    for name in ("single", "wide"):
        _airport_, _cache, _objects, recs, st = _corridors(objs, law, name)
        assert not recs and st.corridors == 0, (name, st.refused)


def test_a_crossing_family_face_closes_the_end_into_a_bay(objs, law):
    wc = law.tables.structures.cutout.wall_corridor
    co = law.tables.structures.cutout
    airport, cache, objects, recs, st = _corridors(objs, law, "bay")
    assert st.by_class == {CLASS_BAY: 1} and len(recs) == 1, st.refused
    r = recs[0]
    assert r.cls == CLASS_BAY and r.mouth_closed and not r.far_closed
    # s = 0 at the closed end, the floor overlapping the end wall
    assert r.length_m == pytest.approx(10.0 + co.floor_overlap_m, abs=0.6)
    groups = wall_corridor_groups(recs, law)
    assert groups[0].capped and groups[0].climbs
    cl = Classification(tuple(_cells()), (), {}, ())
    _cl2, tunnels, sst = build_structures(airport, cl, law, objects, (), groups)
    assert not sst.refused and len(tunnels) == 1, sst.refused
    t = tunnels[0]
    assert t.capped and not t.far_capped and t.top_pinned
    # 07b (2): the ramp is the size of the walls.  1.9 m over ~10.5 m of
    # wall is more than the cap carries, and the end is CLOSED — a SERVICE
    # BAY, EXEMPT from the cap (owner RULINGS 2026-10-07c (1)): the ramp
    # runs the walls' whole length at the grade they need, the floor is
    # NOT raised and there is no step at the door
    assert t.top_s == pytest.approx(t.wall_length_m) and t.climb_from_s == pytest.approx(0.0)
    assert t.design_grade == pytest.approx(1.9 / t.wall_length_m, abs=0.005)
    assert t.design_grade > wc.max_ramp_grade
    assert profile_z(t.profile, 0.0) == pytest.approx(t.mouth_dem_z - 1.9, abs=0.03)
    assert t.pinched is not None and t.pinched[0] == BAY_EXEMPT
    assert t.pinched[2] == pytest.approx(t.design_grade)
    assert not any("§47 (7)" in n for n in t.notes), t.notes
    assert any(BAY_EXEMPT in n for n in t.notes), t.notes
    assert profile_z(t.profile, t.top_s) == pytest.approx(t.mouth_dem_z, abs=0.03)
    # the solver prices the bay's ramp at its own grade, not the cap
    pm, _stats = build(airport, cl, law)
    rows = structure_rows(pm, law, airport)
    _ht = law.tables.emit.design.hard_tol_m
    assert any(type(r).__name__ == "Diff" and r.cap > wc.max_ramp_grade - _ht / r.d + 1e-9
               for r in rows)


def test_pavement_beyond_the_walls_neither_stops_nor_shortens_the_ramp(objs, law):
    """Owner RULINGS 2026-10-07b (2) retires 08m (a)'s stop-and-steepen
    and §34 (9)'s pinch: the ramp stands inside its own walls, so an
    apron beyond them — however near — changes nothing about it."""
    airport, cache, objects, recs, st = _corridors(objs, law, "level")
    groups = wall_corridor_groups(recs, law)
    cl = Classification(tuple(_cells()), (), {}, ())
    _cl, base, sst0 = build_structures(airport, cl, law, objects, (), groups)
    assert not sst0.refused and len(base) == 2, sst0.refused
    for off in (22.0, 2.0):
        apron = Cell(2, "apron", "apron1", _rect(-60, base[0].wall_length_m + off, 60, 200),
                     (), None, None, "airside", "apron", {})
        cl = Classification(tuple(_cells((apron,))), (), {}, ())
        _cl2, tunnels, sst = build_structures(airport, cl, law, objects, (), groups)
        assert not sst.refused and len(tunnels) == 2, sst.refused
        for t, b in zip(tunnels, base):
            assert not t.clipped_by and t.pinched is None and t.top_pinned
            assert (t.top_s, t.climb_from_s, t.design_grade) == pytest.approx(
                (b.top_s, b.climb_from_s, b.design_grade))
            assert t.profile == b.profile


def test_a_descending_wall_bottom_is_a_garage_ramp_cut_as_authored(objs, law):
    wc = law.tables.structures.cutout.wall_corridor
    airport, cache, objects, recs, st = _corridors(objs, law, "garage")
    assert st.by_class == {CLASS_GARAGE: 1} and len(recs) == 1, st.refused
    r = recs[0]
    assert r.cls == CLASS_GARAGE and r.mouth_closed and not r.far_closed
    # the floor descends 3 m over 80 m (3.75 %), read within the sample bias
    assert r.max_authored_grade == pytest.approx(3.0 / 80.0, abs=0.005)
    assert r.floors[0] < r.floors[-1]                       # deep end first
    assert r.grounds[-1] - r.floors[-1] <= law.tables.structures.basin.contact_band_m
    groups = wall_corridor_groups(recs, law)
    g = groups[0]
    assert not g.climbs and g.ramp_role == GARAGE_ROLE and g.design_grade == 0.0
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, (), groups)
    assert not sst.refused and len(tunnels) == 1, sst.refused
    t = tunnels[0]
    assert t.top_s == pytest.approx(t.wall_length_m) and not t.top_pinned
    assert profile_z(t.profile, 0.0) == pytest.approx(r.floors[0])
    assert GARAGE_ROLE in {c.role for c in cl2.cells}
    # steeper than the sanity cap: refused loudly
    _a, _c, _o, recs2, st2 = _corridors(objs, law, "steep")
    assert not recs2 and any("max_authored_grade" in x for x in st2.refused), st2.refused
    assert wc.max_authored_grade == role_cap(law, GARAGE_ROLE).longitudinal
    # spec §12h (3): the SAME descent with nothing built at its deep end —
    # no deck, no wall — is two bare walls under open sky: REFUSED by W3
    _a, _c, _o, recs3, st3 = _corridors(objs, law, "garage_bare")
    assert not recs3 and st3.corridors == 0
    assert any("REFUSED by W3" in x for x in st3.refused), st3.refused


def test_headroom_under_the_law_is_refused(objs, law):
    _a, _c, _o, recs, st = _corridors(objs, law, "low")
    assert not recs and any("min_headroom_m" in x for x in st.refused), st.refused


def test_generator_rows_solve_and_emit(objs, law):
    """The wall-bottom pins inside the walls, the descent rows beyond at
    ``max_ramp_grade``, the top at the ground; the LP solves; the emitted
    faces carry the oracle alias."""
    wc = law.tables.structures.cutout.wall_corridor
    airport, cache, objects = _read(objs, law, [("level", (0.0, 0.0), 0.0, None, "OBJECT")],
                                    _axis_road())
    cl = Classification(tuple(_cells()), (), {}, ())
    pm, stats = build(airport, cl, law)
    ts = [x for x in pm.structures if x.source == KIND]
    assert len(ts) == 2, stats.structures.refused
    rows = structure_rows(pm, law, airport)
    # spec §34 (6) as amended (RULINGS 2026-09-13ai): a ramp pair is priced
    # ``cap - [design] hard_tol_m / d`` so the solve's own held residual
    # lands the emitted row AT the cap, never over it
    _ht = law.tables.emit.design.hard_tol_m
    diffs = [r for r in rows if type(r).__name__ == "Diff"
             and r.cap == pytest.approx(max(0.0, wc.max_ramp_grade - _ht / r.d))]
    assert diffs
    pins = [r for r in rows if isinstance(r, Pin)]
    assert any(abs(r.z - ts[0].mouth_z) < 1e-6 for r in pins)
    cs, _counts, _w = generate(pm, law, airport)
    # THE DESIGN SURFACE (RULINGS 2026-09-08t): one least-squares solve, no
    # IIS — the solve is never infeasible, so the assertion is that it
    # returns a surface, and the ramp geometry below is the twin's subject
    sol, _rep = solve_design(pm, cs, law, Options())
    assert sol.status is Status.OPTIMAL, sol.message
    faces = [f for f in pm.faces.values() if f.role == RAMP_ROLE]
    assert faces
    # each face is judged against ITS OWN corridor: §47 (7) lifts the floor
    # of a corridor whose pinched run cannot reach the ground at the 10 %
    # cap (the residual stands at the covering plate's edge), so the two
    # corridors' floors are no longer the same number and a face may not be
    # priced against the other one's mouth
    lns = {t.id: LineString(t.axis) for t in ts}
    for f in faces:
        ids = list(pm.ring_vertices(f.ring))
        c0 = Point(sum(pm.vertices[v].xy[0] for v in ids) / len(ids),
                   sum(pm.vertices[v].xy[1] for v in ids) / len(ids))
        t = min(ts, key=lambda x: lns[x.id].distance(c0))
        ln = lns[t.id]
        for v in ids:
            p = Point(pm.vertices[v].xy)
            s_ = ln.project(p)
            # the FLAT floor runs to where the climb starts — which §34 (9)
            # (5) moves back from the wall end to the COVERING PLATE's edge
            # (``climb_from_s``), not to ``wall_length_m``.  The 08a floor
            # ring stood ``floor_overlap_m`` past the inner face and its
            # wall-end vertex was a station of its own; §47 (1) puts the
            # ring ON the face, so that vertex is now the climb's first
            # station and carries the climbed value.
            if ln.distance(p) <= t.half_width_m + 1e-6 and s_ <= t.climb_from_s + 1e-6 \
                    and s_ < ln.length - 1e-6:
                assert sol.z[v] == pytest.approx(t.mouth_z, abs=1e-6)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    text, _ways, _nodes = render_patch(surf, law, {}, {})
    assert "v='tunnel_ramp'" in text and f"v='{RAMP_ROLE}'" in text
    assert "k='o4_grade_law' v='structure_ramp'" in text and \
        "k='o4_grade_law_cap' v='0.1'" in text


def _pad(ref, x0, x1, y0=-50.0, y1=70.0):
    """A building pad standing OVER the corridor (footprint AND the ramp
    beyond the walls) — OTHH's terminal pad around the owner's bays."""
    return Cell(3, "building", ref, _rect(x0, y0, x1, y1), (), None, None,
                "groundside", "building", {})


def test_a_pad_is_cut_by_the_walls_and_nothing_beyond_them(objs, law):
    """Law C / spec §6a row 16 as amended by owner RULINGS 2026-10-07b (2):
    the ramp runs the walls' length, so the trench cuts the pad it stands
    in (08-26) and NOTHING beyond the walls — flat pad or pad on relief.

    HISTORY (the flat-pad host rule, 2026-09-08n), still held below:

    The defect this pins (measured on the OTHH closing tile build): the
    knife guarded EVERY pad under the ramp, so `building5` — the flat
    terminal pad the owner's loading bays stand in, a HOST — kept its
    ``weld_to_touching_pavement`` Flat over the ramp's own vertices.  Five
    pad flats gripped seven wall-corridor FLOOR vertices; the law ladder
    demoted ``wall_corridor_ramp`` by 1.392 m (the bays' full depth) and
    the tile build refused.  A pad cannot both host a ramp and hold it
    flat.
    """
    band = law.tables.structures.basin.contact_band_m
    airport, cache, objects, recs, st = _corridors(objs, law, "level")
    groups = wall_corridor_groups(recs, law)

    # FLAT in the fixture DEM's 0.5 %/x plane (0.2 m over 40 m) => a HOST:
    # it does not stop the ramp, and the ramp cuts it
    flat = _pad("host_pad", -20.0, 20.0)
    assert _pad_relief(airport, Polygon(flat.ring)) <= band
    cl = Classification(tuple(_cells((flat,))), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, (), groups)
    assert not sst.refused, sst.refused
    assert tunnels and not any(t.clipped_by for t in tunnels)
    kept = [c for c in cl2.cells if c.ref.startswith("host_pad")]
    before = Polygon(flat.ring).area
    after = sum(Polygon(c.ring).area - sum(Polygon(h).area for h in c.holes)
                for c in kept)
    assert after < before - 1.0, (before, after)          # the trench took its bite
    # ...and only the trench: 5 m past the wall end the pad stands whole
    on_ramp = Point(0.0, DECK_HALF_LEN_M + 5.0)
    assert any(Polygon(c.ring).covers(on_ramp) for c in kept)
    # ...and NO pad flat may grip a wall-corridor FLOOR vertex (the OTHH row)
    pm, _stats = build(airport, cl, law)
    cs, _c, _w = generate(pm, law, airport)
    floor = {p_.v for p_ in cs.pins if WALL_BOTTOM in p_.source.ruling}
    assert floor
    for f in cs.flats:
        if f.source.generator == "pads":
            assert not (set(f.group) & floor), (f.source.inputs, set(f.group) & floor)

    # ON RELIEF (1.5 m over 300 m): the same — nothing is built beyond the
    # walls, so there is no ramp for the pad to stop (the 08m (a) stop and
    # the LEMD Cargo-NEWCO@5/a guard were for the climb beyond the walls)
    relief = _pad("relief_pad", -150.0, 150.0)
    assert _pad_relief(airport, Polygon(relief.ring)) > band
    cl = Classification(tuple(_cells((relief,))), (), {}, ())
    cl3, tunnels3, sst3 = build_structures(airport, cl, law, objects, (), groups)
    assert tunnels3 and not any(t.clipped_by for t in tunnels3)
    kept3 = [c for c in cl3.cells if c.ref.startswith("relief_pad")]
    assert any(Polygon(c.ring).covers(on_ramp) for c in kept3)


# ── §34 (10) THE ROAD MARGIN IS GENERAL ─────────────────────────────────

def test_the_road_true_edge_is_the_centreline_plus_the_roads_own_half_width():
    """§34 (10) (owner RULINGS 2026-09-14bb/14bc/14bd): ONE derivation,
    read from the road's OWN emitted geometry, both ways.

    A carriageway emitted as TWO ribbons sharing their long edge (OTHH's
    route7: 2 x 3.77 m) gives each face one HALF of the road, so the
    face's own width IS the half-width and the true edge stands that far
    outside it.  A carriageway emitted WHOLE gives the full width, and the
    true edge stands half of it outside — the same physical line either
    way, which is the point of having one derivation.
    """
    from auto_patch_v2.planar.wall_corridor_ramps import road_true_edge

    def _cell(ref):
        return Cell(9, "service_road", ref, (), (), None, None, "groundside",
                    "pavement", {})

    # TWO ribbons sharing the long edge at y = 0: each 4 m wide, 100 m long
    left = Polygon([(0.0, -4.0), (100.0, -4.0), (100.0, 0.0), (0.0, 0.0)])
    right = Polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 4.0), (0.0, 4.0)])
    roads = [(left, _cell("route9#0")), (right, _cell("route9#1"))]
    got = road_true_edge(left, _cell("route9#0"), roads)
    # the half-width IS the ribbon's own 4 m: the true edge reaches the far
    # kerb at +4 and stands 4 m outside every other edge
    assert got.bounds == pytest.approx((-4.0, -8.0, 104.0, 4.0), abs=1e-6)

    # the SAME road emitted whole: 8 m across, the true edge half of it out
    whole = Polygon([(0.0, -4.0), (100.0, -4.0), (100.0, 4.0), (0.0, 4.0)])
    one = [(whole, _cell("route9"))]
    got2 = road_true_edge(whole, _cell("route9"), one)
    assert got2.bounds == pytest.approx((-4.0, -8.0, 104.0, 8.0), abs=1e-6)
    # ...and the kerb the ramp arrives at moved OUT by the half width in
    # both readings: 4 m beyond the face's own edge
    assert got.bounds[3] - left.bounds[3] == pytest.approx(4.0, abs=1e-6)
    assert got2.bounds[3] - whole.bounds[3] == pytest.approx(4.0, abs=1e-6)


def test_the_floor_profile_locates_every_sample_as_the_per_point_projection_does():
    """``_floor_profile`` reads the station of EVERY face sample in one
    ``shapely.line_locate_point`` call (review ``docs/lawcreview-12h.md``
    (A) 10, (D) 5): held EXACTLY equal to ``LineString.project`` one point
    at a time — on the vertices, between them, off the line and beyond
    both ends of a polyline with three bends."""
    import numpy as np
    import shapely

    ln = LineString([(0.0, 0.0), (30.0, 0.0), (45.0, 20.0), (45.0, 61.5), (12.25, 80.0)])
    pts = [tuple(c) for c in ln.coords]                                   # on the vertices
    pts += [(7.5, 0.0), (37.5, 10.0), (45.0, 33.3), (28.625, 70.75)]      # between them
    pts += [(11.0, 4.2), (41.0, 9.0), (52.5, 40.0), (30.0, 75.0), (44.0, 21.0)]   # off the line
    pts += [(-12.0, 0.0), (-3.0, -7.0), (0.0, 25.0),                      # beyond the start
            (5.0, 84.0), (-9.5, 92.25), (12.25, 120.0)]                   # beyond the end
    at_once = shapely.line_locate_point(ln, shapely.points(np.asarray(pts))).tolist()
    assert at_once == [ln.project(Point(p)) for p in pts]
    assert at_once[:5] == [0.0, 30.0, 55.0, 96.5, ln.length] and min(at_once) == 0.0
    assert max(at_once) == ln.length
