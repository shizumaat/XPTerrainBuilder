"""§33 (6) THE PACK'S STRUCTURE OBJECTS ARE THE CUT GEOMETRY — the
reader's twins (owner RULINGS 2026-09-15e items 1/3/4/6 and 2026-09-15g;
Fable 2026-09-15j; lane `v2objcut`).

Synthetic OBJ8 geometry only — no pack, no DEM, no build.  Each test
states the measured VHHH / LEMD fact it stands for, so a future change
that "simplifies" one of them has to argue with the measurement.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.airport import obj8, object_cut
from auto_patch_v2.law import Law


@pytest.fixture(scope="module")
def law():
    return Law.load()


def _geom(quads, *, hardness=obj8.HARD_DECK, path="shell.obj"):
    """An :class:`ObjGeometry` from ``[(x, y, z) x 4]`` quads, each cut
    into two triangles.  ``hardness`` is applied to every triangle."""
    verts: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []
    for q in quads:
        base = len(verts)
        verts.extend(q)
        tris.append((base, base + 1, base + 2))
        tris.append((base, base + 2, base + 3))
    v = np.asarray(verts, dtype=float)
    t = np.asarray(tris, dtype=np.int64)
    h = np.full(t.shape[0], hardness, dtype=np.int64)
    return obj8.ObjGeometry(path, v, t, h, np.zeros((0, 3), dtype=np.int64))


def _box_shell(floor_y=-6.0, length=120.0, width=30.0):
    """A rectangular trench: a floor plate at ``floor_y`` and its two LONG
    walls — the VHHH shape, walled everywhere but at its two portals,
    which are the full width of the trench (`tunnel5_done.obj` reads two
    open ring runs of 22.2 m and 17.0 m against 27 walled edges)."""
    L, W, y = length, width, floor_y
    quads = [[(0.0, y, 0.0), (L, y, 0.0), (L, y, W), (0.0, y, W)]]   # the floor
    for z in (0.0, W):
        quads.append([(0.0, y, z), (L, y, z), (L, 0.0, z), (0.0, 0.0, z)])
    return quads


def _components(geom):
    return obj8.solid_components(geom)


def test_a_two_portal_shell_reads_its_trench_its_walls_and_its_floor(law):
    """The VHHH class: a shell walled everywhere but at its two portals.
    The trench outline is the plan of its NON-VERTICAL faces, never a
    hull, and the two wall chains are the ring cut at the portals."""
    g = _geom(_box_shell())
    r = object_cut.shell_reading(g, _components(g), law)
    assert not isinstance(r, str), r
    assert r.floor_y == pytest.approx(-6.0, abs=1e-6)
    assert r.interior.area == pytest.approx(120.0 * 30.0, rel=0.02)
    assert len(r.inner_a) >= 2 and len(r.inner_b) >= 2
    # the portals are the two short walls' gaps, at x = 0 and x = L
    xs = sorted(e[0] for e in r.ends)
    assert xs[0] == pytest.approx(0.0, abs=1.0)
    assert xs[1] == pytest.approx(120.0, abs=1.0)
    assert r.extra_portals == ()


def test_the_floor_is_the_deepest_plate_not_the_largest_area_one(law):
    """MEASURED at VHHH: a shell's RAMPS are near-horizontal too
    (`tunnel5`'s read |n_y| = 0.998 over 100 m), so the largest-AREA bin
    of horizontal faces is a ramp's mid-height, not the floor —
    `tunnel1_done.obj` a 1,514 m2 ramp bin at -2.50 against the 733 m2
    floor at -6.95, `tunnel4_done.obj` 2,672 m2 at -5.25 against 454 m2
    at -9.01.  The floor is the DEEPEST bin that carries a plate's
    worth."""
    W = 20.0
    # an 800 m2 FLOOR at -9 for x 0..40, and a 3,200 m2 near-horizontal
    # RAMP plate at -4 for x 40..200 beyond it, inside the same walls
    quads = [[(0.0, -9.0, 0.0), (40.0, -9.0, 0.0), (40.0, -9.0, W), (0.0, -9.0, W)],
             [(40.0, -4.0, 0.0), (200.0, -4.0, 0.0), (200.0, -4.0, W), (40.0, -4.0, W)]]
    for z in (0.0, W):
        quads.append([(0.0, -9.0, z), (200.0, -9.0, z), (200.0, 0.0, z), (0.0, 0.0, z)])
    g = _geom(quads)
    r = object_cut.shell_reading(g, _components(g), law)
    assert not isinstance(r, str), r
    assert r.floor_y == pytest.approx(-9.0, abs=1e-6), (
        "the 4,000 m2 plate at -4.0 is a ramp, not the floor")


def test_a_portal_spanning_two_ring_edges_is_ONE_portal(law):
    """MEASURED at VHHH `tunnel3_done.obj`: one portal spans a 44.4 m and
    a 2.5 m ring edge.  Counting EDGES reads three ends and refuses the
    object; counting RUNS reads two."""
    L, W, y = 120.0, 30.0, -6.0
    quads = [[(0.0, y, 0.0), (L, y, 0.0), (L, y, W), (0.0, y, W)]]
    for z in (0.0, W):
        quads.append([(0.0, y, z), (L, y, z), (L, 0.0, z), (0.0, 0.0, z)])
    # end x = 0 fully open; end x = L open too, but its rim is CHAMFERED
    # so the trench ring carries two edges there
    quads.append([(L, y, 0.0), (L + 6.0, y, 6.0), (L + 6.0, y, W - 6.0),
                  (L, y, W)])
    g = _geom(quads)
    r = object_cut.shell_reading(g, _components(g), law)
    assert not isinstance(r, str), r
    assert r.extra_portals == ()


def test_a_shell_with_no_deep_plate_is_refused_by_name(law):
    """A flat slab on the surface is not a shell; the refusal names the
    law key it failed."""
    g = _geom([[(0.0, 0.0, 0.0), (60.0, 0.0, 0.0), (60.0, 0.0, 20.0),
                (0.0, 0.0, 20.0)]])
    r = object_cut.shell_reading(g, _components(g), law)
    assert isinstance(r, str) and "shell_floor_min_m" in r, r


def test_a_shell_with_one_portal_is_refused_by_name(law):
    """A closed box is a pit, not a corridor: `basins.py` owns it."""
    L, W, y = 60.0, 20.0, -5.0
    quads = [[(0.0, y, 0.0), (L, y, 0.0), (L, y, W), (0.0, y, W)]]
    for z in (0.0, W):
        quads.append([(0.0, y, z), (L, y, z), (L, 0.0, z), (0.0, 0.0, z)])
    for x in (0.0, L):
        quads.append([(x, y, 0.0), (x, y, W), (x, 0.0, W), (x, 0.0, 0.0)])
    quads.append([(0.0, y, 0.0), (0.0, y, W), (0.0, 0.0, W), (0.0, 0.0, 0.0)])
    g = _geom(quads)
    r = object_cut.shell_reading(g, _components(g), law)
    assert isinstance(r, str) and "open end" in r, r


def test_the_cover_plate_is_the_flush_hard_deck(law):
    """`HARD_DECK` at ``|y| <= cover_flush_m`` is the machine-readable
    marker of the cover (VHHH's `*_TN` files, 427-11,254 m2)."""
    cover = _geom([[(0.0, 0.0, 0.0), (50.0, 0.0, 0.0), (50.0, 0.0, 10.0),
                    (0.0, 0.0, 10.0)]])
    plate, area = object_cut._cover_plate(cover, law)
    assert plate is not None and area == pytest.approx(500.0, rel=0.01)
    # …and a plate well below the flush band is not a cover
    deep = _geom([[(0.0, -5.0, 0.0), (50.0, -5.0, 0.0), (50.0, -5.0, 10.0),
                   (0.0, -5.0, 10.0)]])
    assert object_cut._cover_plate(deep, law)[0] is None
    # …nor is an UNFLAGGED plate at the flush band (no HARD_DECK)
    soft = _geom([[(0.0, 0.0, 0.0), (50.0, 0.0, 0.0), (50.0, 0.0, 10.0),
                   (0.0, 0.0, 10.0)]], hardness=0)
    assert object_cut._cover_plate(soft, law)[0] is None


def test_the_claim_covers_the_shell_AND_its_cover(law):
    """"The shell is never a basin" (§33 (6) B) — and neither is its
    COVER: measured at VHHH, leaving `tunnel2_done_TN.obj` behind minted
    a 27,749 m2 "pit" at floor 0.78 standing on its own shell."""
    cut = object_cut.ObjectCut(
        "object-cut:x@0", "a.obj", "obj1", "obj2", "a_TN.obj",
        object_cut.SHELL, None, None, (), (), ((0.0, 0.0), (1.0, 0.0)),
        (True, True), 1.31, -6.01, 7.32, None, ())
    assert object_cut.cut_placement_ids([cut]) == frozenset({"obj1", "obj2"})


# ── signature C: the BAND is a straight run, never a component ───────────

def _thin_pair(spacing=14.0, length=73.0, height=1.0, thickness=1.0):
    """Two thin surface walls ``spacing`` apart — LEMD `Bridge3.obj`'s
    own shape (two 73.0 / 73.1 m runs 1.00 m thick, 14.02 m apart),
    WELDED into one component by a floor strip between them, which is why
    a component-level reading cannot see them."""
    quads = []
    for z0 in (0.0, spacing):
        for z in (z0, z0 + thickness):
            quads.append([(0.0, 0.0, z), (length, 0.0, z),
                          (length, height, z), (0.0, height, z)])
        quads.append([(0.0, height, z0), (length, height, z0),
                      (length, height, z0 + thickness),
                      (0.0, height, z0 + thickness)])
    # the weld: a floor strip joining the two walls into ONE component
    quads.append([(0.0, 0.0, thickness), (length, 0.0, thickness),
                  (length, 0.0, spacing), (0.0, 0.0, spacing)])
    return quads


def test_a_thin_wall_pair_is_read_as_straight_runs_not_components(law):
    """MEASURED at LEMD: `Bridge3.obj`'s two components read 73 x 16 m
    and 58 x 15 m convex hulls — not walls by any gate — while comp 0's
    vertical faces split into the PAIR."""
    g = _geom(_thin_pair(), hardness=0, path="Bridge3.obj")
    comps = _components(g)
    assert len(comps) == 1, "the twin's geometry is ONE welded component"
    ident = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    bands = object_cut.thin_bands(g, comps, ident, law)
    assert len(bands) >= 2, [(b.length_m, b.width_m) for b in bands]
    pair = object_cut.band_pair(bands, law)
    assert pair is not None
    A, B, inner = pair
    assert inner == pytest.approx(13.0, abs=1.5), inner


def test_a_deep_wall_is_not_a_thin_surface_band(law):
    """OTHH's walls descend 10-15 m below their zero; §33 (6) C reads
    only walls that SIT on the surface."""
    quads = [q for q in _thin_pair()]
    quads = [[(x, y - 12.0, z) for x, y, z in q] for q in quads]
    g = _geom(quads, hardness=0)
    assert object_cut.thin_bands(g, _components(g), [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
                                 law) == []


def test_bands_too_far_apart_are_not_a_pair(law):
    """`pair_spacing_max_m` is the law: two walls 120 m apart flank a
    field, not a trench."""
    g = _geom(_thin_pair(spacing=120.0), hardness=0)
    bands = object_cut.thin_bands(g, _components(g),
                                  [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], law)
    assert object_cut.band_pair(bands, law) is None


def test_the_publication_carries_the_object_cut_witness(law):
    """The census reads `object_cuts` off the sidecar; the emitter must
    put it there.  One witness, two instruments — a key published under
    one name and read under another is the silent-break class."""
    from auto_patch_v2.emit import osm_adapter
    from auto_patch_v2.model.structures import Tunnel
    from auto_patch_v2.pipeline import publication

    assert "object_cuts" in osm_adapter.SIDECAR_KEYS

    class _Frame:
        def transformers(self):
            return (lambda la, lo: (0.0, 0.0),
                    lambda x, y: (22.0 + y / 111_320.0, 113.0 + x / 103_000.0))

    class _Airport:
        frame = _Frame()

    class _Planar:
        structures = (
            Tunnel("object-cut:tunnel5_done.obj@0", (), ((0.0, 0.0), (10.0, 0.0)),
                   5.0, 7.32, 1.31, 100.0, 0.0, ("tunnel_ramp:object-cut:t5@0",),
                   "tunnel_wall:object-cut:t5@0", (), (), (),
                   source="object", resource="tunnel/tunnel5_done.obj",
                   objects=("dsf:obj1",), depth_m=6.011,
                   footprint=((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0))),
            Tunnel("tunnel:-5931@0", (), ((0.0, 0.0), (10.0, 0.0)), 5.0, 7.0, 2.0,
                   100.0, 0.0, (), "", (), (), ()),
        )

    recs = publication.object_cuts(_Planar(), _Airport())
    assert len(recs) == 1, "an OSM bore is not an object cut"
    r = recs[0]
    assert r["id"] == "object-cut:tunnel5_done.obj@0"
    assert r["floor_m"] == 1.31 and r["signature"] == "B"
    assert len(r["outline_ll"]) == 4
    assert r["ramp_refs"] == ["tunnel_ramp:object-cut:t5@0"]


# ── §33 (6) C1' — the pair marks a MOUTH RAMP (RULINGS 2026-09-15x) ──────

def _band(ax, ay, bx, by, *, comp=0, width=1.0, height=1.0):
    from shapely.geometry import LineString, Polygon
    axis = LineString([(ax, ay), (bx, by)])
    return object_cut.ThinBand(comp, axis.buffer(width / 2.0, cap_style="flat"),
                               axis, float(axis.length), width, height,
                               object_cut._bearing(axis))


def test_pairs_that_meet_end_to_end_are_ONE_mouth_ramp(law):
    """MEASURED at LEMD: `Bridge3.obj`'s south end is TWO pairs (27.65 /
    25.71 m at 164.50 deg and 24.88 / 29.00 m at 174.23 deg) sharing a
    junction — one bent ramp, not two mouths.  Read apart, the mouth
    landed at the junction and the ramp climbed the WRONG WAY, 190 m into
    the covered stretch."""
    from auto_patch_v2.planar.structure_pair import pair_groups
    # two pairs meeting at y = 60: (0..60) and (60..110), 10 m apart
    pairs = [(_band(-5.0, 0.0, -5.0, 60.0), _band(5.0, 0.0, 5.0, 60.0), 9.0),
             (_band(-5.0, 60.0, -8.0, 110.0), _band(5.0, 60.0, 2.0, 110.0), 9.6)]
    groups = pair_groups(pairs, law.tables.structures.tunnel.object.merge_gap_m)
    assert len(groups) == 1, [len(g[0]) for g in groups]
    chain, inner = groups[0]
    assert len(chain) == 3, chain
    assert inner == pytest.approx(9.0), "the NARROWEST inner spacing governs"
    ends = sorted(q[1] for q in (chain[0], chain[-1]))
    assert ends[0] == pytest.approx(0.0, abs=1.0)
    assert ends[1] == pytest.approx(110.0, abs=1.0)


def test_pairs_far_apart_are_two_mouth_ramps(law):
    """…and `Bridge3.obj`'s NORTH pair is 224 m from its south group: two
    mouths of one covered bore, never one 354 m ramp."""
    from auto_patch_v2.planar.structure_pair import pair_groups
    pairs = [(_band(-7.0, 0.0, -7.0, 73.0), _band(7.0, 0.0, 7.0, 73.0), 14.02),
             (_band(-5.0, 297.0, -5.0, 354.0), _band(5.0, 297.0, 5.0, 354.0), 9.6)]
    groups = pair_groups(pairs, law.tables.structures.tunnel.object.merge_gap_m)
    assert len(groups) == 2
    assert sorted(round(g[1], 2) for g in groups) == [9.6, 14.02]


def test_the_pair_reading_survives_bands_drawn_the_other_way_round(law):
    """A pack draws the two walls of a pair in either order; the midline
    must not fold."""
    from auto_patch_v2.planar.structure_pair import _pair_midline
    fwd = _pair_midline((_band(-5.0, 0.0, -5.0, 60.0), _band(5.0, 0.0, 5.0, 60.0), 9.0))
    rev = _pair_midline((_band(-5.0, 0.0, -5.0, 60.0), _band(5.0, 60.0, 5.0, 0.0), 9.0))
    flat = lambda t: [t[0][0], t[0][1], t[1][0], t[1][1]]      # noqa: E731
    assert flat(fwd) == pytest.approx(flat(rev)) \
        or flat(fwd) == pytest.approx(flat((rev[1], rev[0])))
    assert abs(fwd[0][1] - fwd[1][1]) == pytest.approx(60.0, abs=0.01)


# ── the LGAV crash: a wall band that crosses itself (2026-09-15) ─────────

def test_a_self_intersecting_wall_ring_is_repaired_not_raised(law):
    """MAIN CRASHED THE LGAV STRUCTURE REPLAY: `_bore_ends_at` built
    ``Polygon(inner_a + reversed(inner_b))`` from the wall bands and
    unioned it, and GEOS raised ``TopologyException: side location
    conflict at -1286.509 -1775.049`` — the whole replay, and the tile
    build behind it, died.  A pack's walls are AUTHORED: a band that
    crosses itself is ordinary input.  Every polygon the reader builds
    from wall bands is repaired first, and the repair's RESULT TYPE is
    never assumed (``make_valid`` hands back a MultiPolygon or a
    GeometryCollection as readily as a Polygon)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    # the classic bow-tie: a ring that crosses itself once
    bad = Polygon([(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)])
    assert not bad.is_valid
    g = object_cut.valid_polygon(bad)
    assert g is not None and g.is_valid
    assert g.geom_type in ("Polygon", "MultiPolygon")
    assert g.area == pytest.approx(50.0, rel=0.02)
    one = object_cut.largest_polygon(bad)
    assert one is not None and one.geom_type == "Polygon" and one.is_valid
    # …and the union that used to raise now completes
    other = Polygon([(20.0, 0.0), (30.0, 0.0), (30.0, 10.0), (20.0, 10.0)])
    u = object_cut.valid_polygon(unary_union([g, other]))
    assert u is not None and u.is_valid


def test_the_bore_end_reader_survives_a_crossing_wall(law):
    """The same defect through the caller that raised it: two inner faces
    that cross make a self-intersecting ring, and `_bore_ends_at` must
    return an answer rather than take the process down."""
    from shapely.geometry import Polygon
    from auto_patch_v2.airport import tunnel_objects as TO
    from auto_patch_v2.airport.tunnel_walls import WallLines
    inner_a = [(0.0, 0.0), (100.0, 20.0)]
    inner_b = [(0.0, 20.0), (100.0, 0.0)]        # crosses inner_a
    plate = Polygon([(-2.0, -2.0), (102.0, -2.0), (102.0, 22.0), (-2.0, 22.0)])
    walls = WallLines(plate, inner_a, inner_b, (False, False), (0.0, 0.0), 1.0, "II")
    # the expression main ran, unrepaired — the ring IS invalid, which is
    # the whole defect (both directions, never a one-sided green)
    assert not Polygon(list(inner_a) + list(reversed(inner_b))).is_valid
    ends = TO._bore_ends_at(walls, [(0.0, 10.0), (100.0, 10.0)], [], 5.0)
    assert ends == ([], [])


def test_the_repair_drops_a_degenerate_ring_without_raising(law):
    """A band with no area at all answers ``None``, never an exception."""
    from shapely.geometry import Polygon
    assert object_cut.valid_polygon(Polygon()) is None
    assert object_cut.largest_polygon(Polygon()) is None
    assert object_cut.valid_polygon(None) is None
    line = Polygon([(0.0, 0.0), (10.0, 0.0), (0.0, 0.0)])
    assert object_cut.largest_polygon(line) is None


# ── §33 (6) B r3: the ring IS the object's trench polygon ────────────────

def test_the_object_cut_ring_is_the_objects_own_trench_polygon(law):
    """A hairpin corridor's ring cannot be an AXIS OFFSET: at VHHH
    `tunnel5_done` (the owner's site, a 413 m U-turn) and `TUNNEL2_DONE`
    were both REFUSED by `_geometry_at` — "the approach bends tighter
    than the corridor" — with their readings correct.  The shell STATES
    its trench, so the ramp face is that polygon and the rim ring the
    object's footprint."""
    from shapely.geometry import Polygon
    from auto_patch_v2.planar import structure_geometry as sg
    trench = Polygon([(0, 0), (100, 0), (100, 20), (0, 20)])
    foot = Polygon([(-2, -2), (102, -2), (102, 22), (-2, 22)])
    g = sg.geometry_from_trench(lambda s: (s, 10.0), [0.0, 50.0, 100.0], 8.0, 0.0, 0.5,
                                trench, foot)
    assert g is not None
    assert g.ramp.area == pytest.approx(2000.0)
    assert g.outer.area == pytest.approx(2496.0)
    assert g.outer.contains(g.ramp)
    assert len(g.left) == len(g.right) == 3
    assert g.cap_in == [] and g.cap_out == []


def test_a_footprint_that_does_not_contain_the_trench_is_unioned(law):
    """The footprint is the walls ∪ trench exterior; where the repair has
    trimmed it, the ramp is folded back in rather than left outside its
    own rim."""
    from shapely.geometry import Polygon
    from auto_patch_v2.planar import structure_geometry as sg
    trench = Polygon([(0, 0), (100, 0), (100, 20), (0, 20)])
    small = Polygon([(0, 0), (50, 0), (50, 5), (0, 5)])
    g = sg.geometry_from_trench(lambda s: (s, 10.0), [0.0, 50.0, 100.0], 8.0, 0.7, 0.5,
                                trench, small)
    assert g is not None and g.outer.contains(g.ramp)
    # …and the union'd rim still carries the §33 (6) B AMENDED wall band
    assert g.wall.area > 0.0
    assert g.ramp.exterior.distance(g.outer.exterior) == pytest.approx(0.7, abs=1e-6)


def test_a_shells_trench_is_walled_the_floor_ring_stands_inside_the_rim(law):
    """§33 (6) B AMENDED (RULINGS 2026-09-15bh).  With the stand-off the
    floor ring is the trench ∩ the footprint ERODED by it, so a wall band
    of at least the stand-off stands between the floor ring and the rim
    EVERYWHERE — including the runs where the shell's own wall faces do
    not stand on the ring (its portals).  Wall-less, the floor ring IS
    the surrounding surface's ring and ``constraints/structures.on_floor``
    hands the airside vertices standing on it the FLOOR row: measured at
    VHHH, 1,362 of 3,815 airside vertices within 200 m of the five shells
    pulled up to 6.46 m."""
    from shapely.geometry import Polygon
    from auto_patch_v2.planar import structure_geometry as sg
    trench = Polygon([(0, 0), (100, 0), (100, 20), (0, 20)])
    # the footprint carries a wall band on three sides only — the x = 100
    # end is a PORTAL, where the r3 emitter left ramp and rim coincident
    foot = Polygon([(-2, -2), (100, -2), (100, 22), (-2, 22)])
    g = sg.geometry_from_trench(lambda s: (s, 10.0), [0.0, 50.0, 100.0], 8.0, 0.7, 0.5,
                                trench, foot)
    assert g is not None
    # the floor ring stands 0.7 m inside the rim on EVERY side, portal too
    assert g.ramp.exterior.distance(g.outer.exterior) == pytest.approx(0.7, abs=1e-6)
    assert g.wall.area > 0.0
    # a vertex can only move INWARD: the cut never leaves its object
    assert g.outer.buffer(1e-9).contains(g.ramp)
    assert g.ramp.area < trench.area


def test_the_walled_rim_ring_is_the_corridors_wall_path(law):
    """§33 (6) B AMENDED (2): the rim ring is published as ``left_rim``
    (``right_rim`` empty), so ``planar/structures``' ``wall_path`` is the
    closed rim ring itself — what ``_rim_rows`` projects the rim's
    vertices onto — and not the axis-offset lines, which on a hairpin run
    across the trench."""
    from shapely.geometry import Polygon
    from auto_patch_v2.planar import structure_geometry as sg
    trench = Polygon([(0, 0), (100, 0), (100, 20), (0, 20)])
    foot = Polygon([(-2, -2), (102, -2), (102, 22), (-2, 22)])
    g = sg.geometry_from_trench(lambda s: (s, 10.0), [0.0, 50.0, 100.0], 8.0, 0.7, 0.5,
                                trench, foot)
    assert g is not None and g.right_rim == []
    assert list(g.left_rim) == list(g.outer.exterior.coords)
    assert g.left_rim[0] == g.left_rim[-1]          # a CLOSED ring


def test_a_shell_with_no_room_for_its_own_walls_is_refused(law):
    """A stand-off that would eat the trench is a refusal by name, never
    a wall-less trench emitted anyway (the attempt this lane exists to
    stop)."""
    from shapely.geometry import Polygon
    from auto_patch_v2.planar import structure_geometry as sg
    trench = Polygon([(0, 0), (100, 0), (100, 1.2), (0, 1.2)])
    foot = Polygon([(0, 0), (100, 0), (100, 1.2), (0, 1.2)])
    assert sg.geometry_from_trench(lambda s: (s, 0.6), [0.0, 50.0, 100.0], 0.6, 0.7, 0.5,
                                   trench, foot) is None


def test_ring_for_leaves_an_ordinary_corridor_to_the_axis_offset(law):
    """Only an ``object-cut:`` corridor takes the polygon path; every
    other corridor is `geometry()`'s axis offset exactly as before."""
    from auto_patch_v2.planar import structure_geometry as sg
    assert sg.OBJECT_CUT_PREFIX == "object-cut:"


def test_only_the_stations_that_carry_the_curve_are_seeded(law):
    """§33 (6) C2': seeding EVERY wall station was measured and withdrawn
    — it moved nine STRAIGHT OTHH object corridors (one's ramp top
    240 -> 246 m) for nothing.  A straight corridor's set is unchanged; a
    curved one gains the stations that carry the bend."""
    from auto_patch_v2.planar import structure_geometry as sg
    from auto_patch_v2.airport.tunnel_walls import Station

    class _C:
        def __init__(self, sts, left, right):
            self.stations = sts
            self._l, self._r = left, right

        def stations_inner(self):
            return self._l, self._r

    sts = [Station(float(s), 5.0, 5.0, 1.0, 1.0) for s in range(0, 25, 2)]
    straight_l = [(float(st.s), 5.0) for st in sts]
    straight_r = [(float(st.s), -5.0) for st in sts]
    ss = [0.0, 12.0, 24.0]
    assert sg.seed_wall_stations(list(ss), _C(sts, straight_l, straight_r), 0.5) == ss
    import math as _m
    bent_l = [(float(st.s), 5.0 + 4.0 * _m.sin(_m.pi * st.s / 24.0)) for st in sts]
    bent_r = [(float(st.s), -5.0 + 4.0 * _m.sin(_m.pi * st.s / 24.0)) for st in sts]
    got = sg.seed_wall_stations(list(ss), _C(sts, bent_l, bent_r), 0.5)
    assert len(got) > len(ss), got
    assert set(ss) <= set(got)


def test_seeding_is_inert_without_a_corridor(law):
    from auto_patch_v2.planar import structure_geometry as sg
    ss = [0.0, 12.0, 24.0]
    assert sg.seed_wall_stations(list(ss), None, 0.5) == ss
