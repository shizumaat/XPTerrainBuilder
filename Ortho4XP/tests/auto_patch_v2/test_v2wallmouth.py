"""Lane lawc396 twins (owner RULINGS 2026-10-05e / 05g / 05h; spec
``docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md`` §12h; issue #396):
LAW C IS UNCONDITIONAL UNDER ONE GENERAL RULE.  A kerb-wall candidate that
passes the old rules is admitted iff it has an OPEN MOUTH (W1s: nothing of
ANY placement across an end, below grade or at grade up to the headroom),
its arms run out from a BUILT STRUCTURE (W3: a deck over the trench or an
above-grade wall at an end) and the open mouth stands ON THE FIELD.

One twin per clause and per degenerate case of §12h (3), from synthetic
packs: the Law C corridor of ``test_v2wallcorridor`` plus a CLOSER
placement of ANOTHER resource across a mouth, and a cells list for the
field.  The fixture corridor runs along ±y with its mouths at y = ±40,
10 m wide, floor 1.9 m under ground at 700.  Law values are read from the
tables, never retyped.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import re

import pytest
from shapely.geometry import Point

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import wall_family as WF
from auto_patch_v2.airport import wall_mouth as WM
from auto_patch_v2.airport.wall_corridors import CLASS_BAY, CLASS_GARAGE, CLASS_LEVEL
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build as planar_build
from auto_patch_v2.planar.structure_approach import FieldRegion, cover_polygons, wall_field

from test_tunnel_objects import _airport, _rect, _slab, _write
from test_v2wallcorridor import _corridor_obj, _vwall

#: the fixture corridor's mouths (frame y) and where a closer is placed
MOUTH_Y = 40.0
BOTH = ((0.0, MOUTH_Y), (0.0, -MOUTH_Y))


@pytest.fixture(scope="module")
def law():
    # any identifier: no law table is keyed by an airport (RULINGS 05e)
    return Law.for_airport("ZZZZ")


def _block(path, x0, x1, z0, z1, y0, y1):
    vt: list = []
    tris: list = []
    _slab(vt, tris, x0, x1, z0, z1, y0, y1)
    return _write(path, vt, tris)


def _vsheet(path, x0, x1, y0, y1):
    """ONE vertical quad across the axis at authored z = 0 — a door mesh,
    a fence: no thickness at all."""
    return _write(path, [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)],
                  [(0, 1, 2), (0, 2, 3)])


def _hsheet(path, x0, x1, z0, z1, y):
    """ONE horizontal quad at authored height ``y`` — a painted ground
    sheet, a canopy skin."""
    return _write(path, [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)],
                  [(0, 2, 1), (0, 3, 2)])


def _jet_bridge(path):
    """A bridge body 4-6 m up across the axis on two 0.5 m legs."""
    vt: list = []
    tris: list = []
    _slab(vt, tris, -8.0, 8.0, -1.5, 1.5, 4.0, 6.0)
    _slab(vt, tris, -3.0, -2.5, -0.25, 0.25, 0.0, 3.9)
    _slab(vt, tris, 2.5, 3.0, -0.25, 0.25, 0.0, 3.9)
    return _write(path, vt, tris)


def _unequal_arms(path, depth=1.9, top=0.5, thick=0.3, short_to=20.0):
    """The Law C corridor with one arm running 40 m each way and the other
    stopping at authored z = ``short_to`` on the +z side, under a deck."""
    vt: list = []
    tris: list = []
    _vwall(vt, tris, -5.0 - thick, -5.0, -40.0, 40.0, -depth, -depth, top)
    _vwall(vt, tris, 5.0, 5.0 + thick, -40.0, short_to, -depth, -depth, top)
    _slab(vt, tris, -7.0, 7.0, -30.0, 10.0, 2.6, 2.9)
    return _write(path, vt, tris)


@pytest.fixture(scope="module")
def objs(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("packmouth") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    wc = law.tables.structures.cutout.wall_corridor
    eps = law.tables.structures.rebake.plate_seat_min_delta_m
    band = law.tables.structures.basin.contact_band_m
    assert eps < 0.12 < 0.15 < band < 2.5 <= wc.max_wall_height_m < wc.min_headroom_m < 4.0
    # the fixture floor is 1.9 m down: the lintel is under the floor's
    # headroom bar, the low canopy at or over it
    assert band < 1.5 and 3.0 < wc.min_headroom_m <= 2.0 + 1.9
    return {
        "dir": d,
        "deck": _corridor_obj(d / "deck.obj"),                       # under a deck
        "sky": _corridor_obj(d / "sky.obj", deck_y=None),            # under open sky
        "garage": _corridor_obj(d / "garage.obj", depth=0.2, drop=3.0, deck_y=None,
                                end_wall=True, end_top=2.5),
        "unequal": _unequal_arms(d / "unequal.obj"),
        # THE CLOSERS, each another resource, each placed ON a mouth
        "slab_below": _block(d / "slab_below.obj", -5.0, 5.0, -1.0, 1.0, -1.5, -0.5),
        "wall": _block(d / "wall.obj", -5.0, 5.0, -0.2, 0.2, 0.0, 2.5),
        "door": _vsheet(d / "door.obj", -5.0, 5.0, 0.0, 3.0),
        "fence": _vsheet(d / "fence.obj", -5.0, 5.0, 0.0, 1.2),
        "kerb": _block(d / "kerb.obj", -5.0, 5.0, -0.2, 0.2, 0.0, 0.15),
        "ground": _hsheet(d / "ground.obj", -5.0, 5.0, -2.0, 2.0, 0.12),
        "paint": _hsheet(d / "paint.obj", -5.0, 5.0, -2.0, 2.0, eps / 2.0),
        "canopy": _hsheet(d / "canopy.obj", -8.0, 8.0, -3.0, 3.0, 4.0),
        # 2.0 m over the ground = 3.9 m over the 1.9 m deep floor: OVERHEAD
        "low_canopy": _hsheet(d / "low_canopy.obj", -8.0, 8.0, -3.0, 3.0, 2.0),
        # 3.0 m over the floor (1.1 m over the ground): under rule 5's bar
        "lintel": _hsheet(d / "lintel.obj", -8.0, 8.0, -3.0, 3.0, 3.0 - 1.9),
        # a garage ramp whose SHALLOW end lies 1.5 m under the ground
        "garage_deep": _corridor_obj(d / "garage_deep.obj", depth=1.5, drop=3.0, deck_y=None,
                                     end_wall=True, end_top=2.5),
        "jet_bridge": _jet_bridge(d / "jet_bridge.obj"),
        "half_wall": _block(d / "half_wall.obj", -5.0, -0.5, -0.2, 0.2, 0.0, 2.5),
    }


def _cells(y0=-150.0, y1=150.0, x0=-30.0, x1=30.0):
    return [Cell(1, "service_road", "road1", _rect(x0, y0, x1, y1), (), None, None,
                 "groundside", "pavement", {})]


def _beside(standoff):
    """A cover BESIDE the corridor: 1 m inside the standoff of its plan
    extent (the deck's edge at x = 7, so the family gate lets it through)
    and beyond the standoff of both mouths' midpoints (0, ±40) — with the
    distance from either mouth."""
    x0 = 7.0 + standoff - 1.0
    return _cells(-10.0, 10.0, x0, x0 + 100.0), math.hypot(x0, MOUTH_Y - 10.0)


def _read(objs, law, corridor, closers=(), cells=None, measure=False):
    """The corridor at the origin with each ``(name, xy)`` of ``closers``
    placed beside it; ``cells`` (a list) hands the field."""
    placements = [(corridor, (0.0, 0.0), 0.0, None, "OBJECT")] + \
        [(name, xy, 0.0, None, "OBJECT") for name, xy in closers]
    airport = _airport(objs, law, placements)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    field = None if cells is None else wall_field(Classification(tuple(cells), (), {}, ()), law)
    recs, st = WF.read_wall_corridors(airport, objects, cache, law, measure=measure,
                                      field=field)
    return recs, st


def _at(name, where=BOTH):
    return [(name, xy) for xy in where]


# ── W1s: the open mouth ──────────────────────────────────────────────────

def test_an_open_mouth_under_a_deck_is_admitted_and_the_line_names_every_clause(objs, law):
    recs, st = _read(objs, law, "deck", cells=_cells())
    assert st.corridors == 1 and st.by_class == {CLASS_LEVEL: 2}, st.refused
    assert st.field_read is True and st.field_cells == 1
    (line,) = st.admission
    # THE LINE (§12h (4)): every clause, in order, each with its witness
    order = ["candidate deck.obj bands", "(a) admitted", "(d) kerb 0.50 m", "ends family 0%/0%",
             "headroom 4.80 m (plate comp", "FIELD end 0 0.0 m of cover",
             "MOUTH end 0 below 0.00 / at-grade 0.00 (closer none), end 1 below 0.00",
             "W1s open ends 0, 1", "W3 plate (plate comp", "-> ADMITTED level"]
    at = [line.index(tok) for tok in order]
    assert at == sorted(at), line


@pytest.mark.parametrize("closer, band", [
    ("slab_below", "below"),        # a foreign slab in the trench opening
    ("wall", "at-grade"),           # a wall
    ("door", "at-grade"),           # a roll-up door mesh: one sheet
    ("fence", "at-grade"),          # a fence
    ("kerb", "at-grade"),           # a 0.15 m kerb or step (RULINGS 05h (1))
    ("ground", "at-grade"),         # a ground slab 0.12 m proud (LEMD's apron sheet)
    ("lintel", "at-grade"),         # a roof under min_headroom_m over the FLOOR
])
def test_a_foreign_placement_across_both_mouths_refuses_by_w1s(objs, law, closer, band):
    recs, st = _read(objs, law, "deck", _at(closer), cells=_cells())
    assert recs == [] and st.corridors == 0
    (line,) = st.admission
    assert "W1s REFUSED — no open mouth" in line and "ADMITTED" not in line
    # the closer is NAMED: its resource and its placement, at both ends
    assert f"closer {closer}.obj@dsf:obj1 1.00 of W" in line
    assert f"closer {closer}.obj@dsf:obj2 1.00 of W" in line
    key = "below 1.00" if band == "below" else "at-grade 1.00"
    assert line.count(key) == 2, line
    assert any("REFUSED by W1s" in r and f"{closer}.obj" in r for r in st.refused)


@pytest.mark.parametrize("above, share", [
    ("canopy", "0.00"),             # a canopy over the headroom closes nothing
    # OVERHEAD IS MEASURED FROM THE FLOOR (rule 5's bar; review (A) 7): a
    # roof 2.0 m over the ground is 3.9 m over the floor a vehicle is on
    ("low_canopy", "0.00"),
    ("jet_bridge", "0.10"),         # the body is overhead; two 0.5 m legs of 10 m
    ("paint", "0.00"),              # a sheet under ε over the ground is the ground
])
def test_what_stands_over_or_beside_the_mouth_leaves_it_open(objs, law, above, share):
    recs, st = _read(objs, law, "deck", _at(above), cells=_cells())
    assert st.by_class == {CLASS_LEVEL: 2}, st.refused
    (line,) = st.admission
    assert line.count(f"at-grade {share}") == 2 and "W1s open ends 0, 1" in line, line


def test_one_mouth_closed_by_a_foreign_placement_is_a_bay_at_the_other(objs, law):
    """RULINGS 2026-10-05h (2): THE CLASS READS THE COMPOSED OPENNESS — the
    level pair with a wall of another resource across one mouth is a bay
    whose ramp is beyond the other, and the note names the closer."""
    recs, st = _read(objs, law, "deck", [("wall", BOTH[0])], cells=_cells())
    assert st.by_class == {CLASS_BAY: 1} and len(recs) == 1, st.refused
    r = recs[0]
    assert r.mouth_closed and not r.far_closed
    (line,) = st.admission
    assert "ends family 0%/0%" in line           # rule 4 saw both ends open
    assert "W1s open end " in line and "-> ADMITTED bay" in line
    assert any("closed by the pack across its mouth" in n and "wall.obj@dsf:obj1" in n
               for n in r.notes), r.notes
    # the SAME pair with nothing across it is the level corridor of two halves
    recs0, _st0 = _read(objs, law, "deck", cells=_cells())
    assert {x.cls for x in recs0} == {CLASS_LEVEL}


def test_half_a_wall_across_the_mouth_does_not_close_it(objs, law):
    wc = law.tables.structures.cutout.wall_corridor
    recs, st = _read(objs, law, "deck", _at("half_wall"), cells=_cells())
    (line,) = st.admission
    assert 0.45 < wc.end_cap_cover_min and line.count("at-grade 0.45") == 2, line
    assert st.by_class == {CLASS_LEVEL: 2}


# ── W3: the arms run out from a built structure ──────────────────────────

def test_two_bare_walls_under_open_sky_are_refused_by_w3(objs, law):
    recs, st = _read(objs, law, "sky", cells=_cells())
    assert recs == [] and st.corridors == 0
    (line,) = st.admission
    assert "headroom open air" in line and "W1s open ends 0, 1" in line
    assert "W3 REFUSED — open air, no wall at either end (at-grade wall cover 0.00 / 0.00)" in line
    assert any("REFUSED by W3" in r for r in st.refused)


def test_an_above_grade_wall_at_the_closed_end_is_w3_and_a_kerb_is_not(objs, law):
    band = law.tables.structures.basin.contact_band_m
    recs, st = _read(objs, law, "sky", [("wall", BOTH[1])], cells=_cells())
    assert st.by_class == {CLASS_BAY: 1}, st.refused
    (line,) = st.admission
    assert "W3 wall at end " in line and "1.00 of W, z_max +2.50 m over ground" in line
    assert 2.5 >= band
    # a KERB across that end closes it (W1s) but is no wall (W3): refused
    recs2, st2 = _read(objs, law, "sky", [("kerb", BOTH[1])], cells=_cells())
    assert recs2 == [] and "W3 REFUSED" in st2.admission[0], st2.admission
    assert 0.15 < band


def test_a_garage_ramp_has_one_mouth_and_its_w3_at_the_deep_end(objs, law):
    recs, st = _read(objs, law, "garage", cells=_cells())
    assert st.by_class == {CLASS_GARAGE: 1}, st.refused
    (line,) = st.admission
    deep = 0 if recs[0].floors[0] <= recs[0].floors[-1] else 1
    assert deep == 0                                  # s = 0 at the deep end
    assert "W1s open end 0;" in line or "W1s open end 1;" in line
    assert "W3 wall at end " in line and "-> ADMITTED garage_ramp" in line
    # the shallow mouth closed by a foreign wall: no open mouth at all
    shallow = BOTH[0] if "W1s open end 0" in line else BOTH[1]
    recs2, st2 = _read(objs, law, "garage", [("wall", shallow)], cells=_cells())
    assert recs2 == [] and "W1s REFUSED" in st2.admission[0], st2.admission


def test_an_overhead_face_is_in_neither_band_and_is_no_wall(objs, law):
    """Review (A) 7: a face whose lowest point stands at or above the
    mouth's floor + ``min_headroom_m`` is read in NEITHER band and never as
    W3's wall — at the same height over the GROUND a deeper floor's lintel
    is still a closer."""
    ceiling = law.tables.structures.cutout.wall_corridor.min_headroom_m
    _objects, _cache, rd = _reader(objs, law, [("low_canopy", BOTH[0])])
    end = ((-5.0, MOUTH_Y), (5.0, MOUTH_Y))
    over = rd.mouths().read(end, 702.0 - ceiling, 700.0)          # exactly at the bar
    assert (over.below, over.at_grade, over.wall) == (0.0, 0.0, 0.0)
    assert over.closer is None
    under = rd.mouths().read(end, 702.0 - ceiling + 0.01, 700.0)  # 1 cm under it
    assert under.at_grade == pytest.approx(1.0) and under.wall == pytest.approx(1.0)
    assert under.closer.resource == "low_canopy.obj"


# ── FIELD ────────────────────────────────────────────────────────────────

def test_field_on_off_and_not_read(objs, law):
    standoff = law.tables.structures.tunnel.mouth_standoff_m
    # ON: the cover under the corridor
    _r, st = _read(objs, law, "deck", cells=_cells())
    assert st.corridors == 1 and "FIELD end 0 0.0 m of cover" in st.admission[0]
    # OFF: a cover within the standoff of the family's plan extent and
    # beyond it from both mouths — the CANDIDATE's own FIELD clause refuses
    cells_off, dist = _beside(standoff)
    assert dist > standoff
    recs, st_off = _read(objs, law, "deck", cells=cells_off, measure=True)
    assert recs == [] and st_off.field_read is True and st_off.off_field_families == 0
    (line,) = st_off.admission
    assert f"FIELD REFUSED — nearest cover {dist:.1f} m from end" in line
    assert f"(> mouth_standoff_m {standoff:g})" in line
    assert "MOUTH" not in line and "W1s" not in line        # cheapest refusal first
    assert any("REFUSED by FIELD" in r for r in st_off.refused)
    row = st_off.narrow_cut[0]
    assert row["field"] is False and row["field_m"] == pytest.approx(dist, abs=0.05)
    assert row["admitted"] is False and row["w1s"] is None
    # just inside the standoff: read, and on
    near = MOUTH_Y + standoff - 1.0
    _r, st_near = _read(objs, law, "deck", cells=_cells(near, near + 100.0))
    assert st_near.corridors == 1, st_near.refused
    # NOT READ: no classification handed — said on the line and in the stats
    recs_n, st_n = _read(objs, law, "deck")
    assert st_n.field_read is False and st_n.field_cells == 0 and len(recs_n) == 2
    assert "FIELD not read (no cover handed)" in st_n.admission[0]


def test_the_family_gate_refuses_an_off_field_family_whole(objs, law):
    """§12h (4) STEP 0 (review ``docs/lawcreview-12h.md`` (B)): a family no
    member of which stands within the standoff of the cover is refused in
    ONE line before any band is read — in a build and in the ``measure``
    replay alike — and never without a field."""
    standoff = law.tables.structures.tunnel.mouth_standoff_m
    far = (0.0, 150.0 + MOUTH_Y + standoff + 200.0)      # 200 m beyond the cover's reach
    two = [("deck", (0.0, 0.0), 0.0, None, "OBJECT"), ("deck", far, 0.0, None, "OBJECT")]
    airport = _airport(objs, law, two)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    field = wall_field(Classification(tuple(_cells()), (), {}, ()), law)
    _n, fams = WF.wall_families(objects, cache, law)
    assert len(fams) == 2
    # the far family ALONE: one line, nothing read, no index
    rd = WF.wall_reader(airport, objects, cache, law, field=field)
    (fk_far, ks_far), = [f for f in fams if objects[f[1][0]].xy == far]
    fam, pairs = WF.read_family(rd, fk_far, [objects[k] for k in ks_far])
    assert pairs == [] and fam.off_field_families == 1 and rd.mouth_index is None
    assert (fam.families, fam.bands, fam.pairs, fam.admission) == (0, 0, 0, [])
    (line,) = fam.refused
    assert line.startswith("family ") and "(1 members, deck.obj): off the field" in line
    assert line.endswith(f"nearest cover {standoff + 200.0:.1f} m (> mouth_standoff_m "
                         f"{standoff:g}); no band read"), line
    # the whole read, build and measure alike: the on-field family alone is counted
    for measure in (False, True):
        recs, st = WF.read_wall_corridors(airport, objects, cache, law, measure=measure,
                                          field=field)
        assert st.off_field_families == 1 and st.corridors == 1 and len(recs) == 2
        assert (st.families, st.bands, st.pairs) == (1, 2, 1) and len(st.admission) == 1
        assert st.refused == [line]
    # NO FIELD HANDED: the gate is not applied (FIELD is not read)
    recs, st = WF.read_wall_corridors(airport, objects, cache, law)
    assert st.off_field_families == 0 and st.corridors == 2 and st.refused == []
    assert all("FIELD not read" in a for a in st.admission)


def test_the_field_predicate_is_the_mapped_tunnel_laws_cover_test(law):
    """``wall_mouth.FieldCover`` lives under ``airport`` (the layer order
    forbids importing ``planar``'s ``FieldRegion`` there): the twin holds
    its verdict to ``FieldRegion.on_cover`` on the same polygons."""
    cl = Classification(tuple(_cells()) + (
        Cell(2, "apron", "apron1", _rect(200, -50, 400, 50), (((250, -10), (300, -10), (300, 10), (250, 10)),),
             None, None, "airside", "apron", {}),), (), {}, ())
    field = wall_field(cl, law)
    assert list(field.polys) == cover_polygons(cl)
    assert field.standoff_m == law.tables.structures.tunnel.mouth_standoff_m
    cover = WM.FieldCover(field)
    region = FieldRegion(list(field.polys), field.standoff_m)
    for xy in [(0.0, 0.0), (0.0, 299.0), (0.0, 300.0), (0.0, 300.5), (275.0, 0.0),
               (180.0, 0.0), (551.0, 0.0), (-181.0, 300.0)]:
        assert cover.holds(xy) is region.on_cover(Point(xy)), xy
        assert cover.holds(xy) is (cover.distance_m(xy) <= field.standoff_m), xy
    assert WM.FieldCover(WM.WallField((), 150.0)).holds((0.0, 0.0)) is False


def test_the_build_path_always_reads_the_field(objs, law):
    """§12h (4): ``planar.build`` derives ONE ``WallField`` from the
    classification it is handed and reads the walls under it."""
    airport = _airport(objs, law, [("deck", (0.0, 0.0), 0.0, None, "OBJECT")])
    cells = [Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside",
                  "runway", {})] + _cells()
    _pm, st = planar_build(airport, Classification(tuple(cells), (), {}, ()), law)
    assert st.wall_corridors.field_read is True and st.wall_corridors.field_cells == 2
    assert st.wall_corridors.corridors == 1, st.wall_corridors.refused


# ── the degenerate cases of §12h (3) not covered above ───────────────────

def test_unequal_arms_ignore_the_longer_arms_run_on(objs, law):
    """The longer arm's run-on is not part of the corridor: the halves end
    at the OVERLAP's end (y = −20: authored +z is frame −y) and a wall
    across the LONG arm's own end (y = −40) closes nothing.

    WHERE THE MOUTH SEGMENT STANDS for such a pair is rule 4's own
    ``end_line`` — the end of the pair's MIDLINE, which runs halfway into
    the run-on (y = −30 here), with the last station's half widths.  §12h
    (1) defines M_k as that segment and §12h (3) says "at the overlap
    window's end"; for arms of unequal length the two differ by half the
    run-on.  This twin pins the reading as it is (rule 4 unchanged — its
    covers are OTHH's identity bar) and the lane's report carries the
    difference for the spec author."""
    recs, st = _read(objs, law, "unequal", cells=_cells())
    assert st.by_class == {CLASS_LEVEL: 2}, st.refused
    ys = sorted(r.axis[-1][1] for r in recs)
    assert ys[0] == pytest.approx(-20.0, abs=1.0) and ys[1] == pytest.approx(40.0, abs=1.0)
    _r, st_run = _read(objs, law, "unequal", [("wall", (0.0, -40.0))], cells=_cells())
    assert st_run.by_class == {CLASS_LEVEL: 2}, st_run.admission
    _r, st_at = _read(objs, law, "unequal", [("wall", (0.0, -30.0))], cells=_cells())
    assert st_at.by_class == {CLASS_BAY: 1}, st_at.admission


# ── the pack-wide mouth index (§12h (5)) ─────────────────────────────────

def _reader(objs, law, closers=(), cells=None):
    placements = [("deck", (0.0, 0.0), 0.0, None, "OBJECT")] + \
        [(n, xy, 0.0, None, "OBJECT") for n, xy in closers]
    airport = _airport(objs, law, placements)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    field = None if cells is None else wall_field(Classification(tuple(cells), (), {}, ()), law)
    return objects, cache, WF.wall_reader(airport, objects, cache, law, field=field)


def test_the_index_is_built_once_on_the_first_mouth_query_and_never_before(objs, law):
    standoff = law.tables.structures.tunnel.mouth_standoff_m
    # a candidate FIELD refuses never reaches a mouth query: no index at all
    objects, cache, rd = _reader(objs, law, _at("wall"), _beside(standoff)[0])
    _placements, fams = WF.wall_families(objects, cache, law)
    for fk, ks in fams:
        WF.read_family(rd, fk, [objects[k] for k in ks])
    assert rd.mouth_index is None
    # on the field: ONE index for the reader, two queries per candidate
    objects, cache, rd = _reader(objs, law, _at("wall"), _cells())
    _placements, fams = WF.wall_families(objects, cache, law)
    for fk, ks in fams:
        WF.read_family(rd, fk, [objects[k] for k in ks])
    index = rd.mouth_index
    assert index is not None and rd.mouths() is index and index.queries == 2
    # the WHOLE pack is its population — the closers are no family of the pair
    assert [o.id for o in index.placed] == [o.id for o in objects]


def test_a_stock_library_placement_is_not_read_across_a_mouth(objs, law):
    """Stock catalogue assets are excluded exactly as rule 1 excludes them."""
    objects, cache, rd = _reader(objs, law, _at("wall"))
    stock = [objects[0]] + [_dc.replace(o, path="lib/airport/landscape/wall.obj")
                            for o in objects[1:]]
    index = WM.MouthIndex(stock, cache, rd.airport.dem.z, law)
    assert [o.id for o in index.placed] == [objects[0].id]
    end = ((-5.0, MOUTH_Y), (5.0, MOUTH_Y))
    assert index.read(end, 698.1, 700.0).at_grade == 0.0
    assert rd.mouths().read(end, 698.1, 700.0).at_grade == pytest.approx(1.0)


def test_the_mouth_reading_states_both_bands_the_wall_and_the_closer(objs, law):
    eps = law.tables.structures.rebake.plate_seat_min_delta_m
    _objects, _cache, rd = _reader(objs, law, [("wall", BOTH[0]), ("slab_below", BOTH[1])])
    north = rd.mouths().read(((-5.0, MOUTH_Y), (5.0, MOUTH_Y)), 698.1, 700.0)
    assert north.below == 0.0 and north.at_grade == pytest.approx(1.0)
    assert north.wall == pytest.approx(1.0) and north.wall_top_m == pytest.approx(2.5)
    assert north.closer_below is None and north.closer.resource == "wall.obj"
    assert (north.closer.z_min, north.closer.z_max) == pytest.approx((700.0, 702.5))
    south = rd.mouths().read(((-5.0, -MOUTH_Y), (5.0, -MOUTH_Y)), 698.1, 700.0)
    assert south.below == pytest.approx(1.0) and south.at_grade == 0.0 and south.wall == 0.0
    assert south.closer.resource == "slab_below.obj" and south.closer.placement == "dsf:obj2"
    # a floor AT the ground leaves no below-grade band to close
    flat = rd.mouths().read(((-5.0, -MOUTH_Y), (5.0, -MOUTH_Y)), 700.0 - eps, 700.0)
    assert flat.below == 0.0
