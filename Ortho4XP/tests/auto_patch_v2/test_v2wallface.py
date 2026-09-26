"""Lane ``v2wallface`` twins — spec §47 (owner RULINGS 2026-09-17h/17j,
Fable 17k): THE TRENCH RINGS SIT ON THE WALL'S FACES, AND A WALLED RAMP
HOLDS THE CAP TO THE BUILDING.

* §47 (3) THE LATTICE FLOOR ``F`` — the MEASUREMENT, through the REAL
  arrangement call path (``planar/overlay.py:441``): the smallest
  separation at which two UNSNAPPED rings survive as two rings, over
  every sub-grid phase.  This twin pins it and pins the 09-01e "0.85 m
  merged" record's settlement (it is ``snap_out``'s, not the
  arrangement's);
* §47 (1)/(2)/(3) THE RING LADDER at t = 0.25 / 0.55 / 0.75 / 1.00 /
  2.00 m through the real corridor product: the rim ON the outer face
  (or yielded by exactly ``F − t``, named), the floor ON the inner face,
  the band ``max(t, F)``;
* §47.1 (8) THE TWO SEAM-PROBES the consumer census owed the lane:
  ``constraints/structures.on_floor`` with a rim on the face coinciding
  with foreign ground, and ``verify/structures._rim_edges`` under
  ``tunnel_mouth_canonical``.
"""
from __future__ import annotations

import math

import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.structure_geometry import rim_standoff, rim_yield_m
from auto_patch_v2.planar.structures import build_structures

from test_tunnel_objects import _cells, _corridors, _wall_obj

GRID = 0.5


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── §47 (3): the lattice floor, MEASURED ─────────────────────────────────

def _two_rings(d: float, dx: float, dy: float, theta: float, L: float, h: float):
    """A closed floor ring (half-width ``h``, length ``L``) and the rim
    ring ``d`` outside it, rotated and translated off the lattice."""
    c, s = math.cos(theta), math.sin(theta)

    def ring(hh: float, ll: float):
        pts = [(-ll, -hh), (ll, -hh), (ll, hh), (-ll, hh), (-ll, -hh)]
        return [(x * c - y * s + dx, x * s + y * c + dy) for x, y in pts]
    return ring(h, L / 2.0), ring(h + d, L / 2.0 + d)


def _survives(d: float, dx: float, dy: float, theta: float,
              L: float = 40.0, h: float = 4.0) -> bool:
    """Do the two rings survive THE REAL ARRANGEMENT as two rings?

    The call path is ``planar/overlay.build_arrangement``'s own, spelled
    here and nowhere else in this file: ``shapely.unary_union(unary_union
    (lines), grid_size=0.5)`` then ``shapely.polygonize``.  "Survives" is
    exactly two faces — the floor and a band that is a PROPER ANNULUS
    whose hole IS the floor — with the band nowhere of zero width (a
    shared vertex is a fusion, not a band)."""
    floor, rim = _two_rings(d, dx, dy, theta, L, h)
    noded = shapely.unary_union(
        unary_union([LineString(floor), LineString(rim)]), grid_size=GRID)
    polys = [g for g in shapely.get_parts(shapely.polygonize([noded]))
             if g.geom_type == "Polygon" and not g.is_empty]
    if len(polys) != 2:
        return False
    band = max(polys, key=lambda p: len(p.interiors))
    inner = polys[0] if polys[1] is band else polys[1]
    if len(band.interiors) != 1 or inner.interiors:
        return False
    hole = band.interiors[0]
    if abs(Polygon(hole).area - inner.area) > 1e-6:
        return False
    return min(band.exterior.distance(Point(c)) for c in hole.coords) > 1e-9


def _bad_phases(d: float, n: int = 9, L: float = 40.0, h: float = 4.0) -> int:
    return sum(not _survives(d, GRID * i / n, GRID * j / n, th, L, h)
               for i in range(n) for j in range(n)
               for th in (0.0, 0.1, 0.3, math.pi / 4, 0.9))


def test_the_lattice_floor_is_the_cell_diameter(law):
    """§47 (3): ``cutout.ring_floor_m`` IS the measurement — the smallest
    separation at which every phase survives.  Measured (lane
    ``v2wallface``, 2026-09-17), 405 phases per rung on this family:
    0.25 fuses 403, 0.50 fuses 91, 0.55 fuses 28, 0.60 fuses 132 under
    the strict (no shared vertex) reading, 0.65 fuses 34, 0.68 fuses 4,
    and 0.70 upward fuse none — but 0.70 DOES fail a curved pair (8 of
    324, below), so F is the cell DIAMETER."""
    F = law.tables.structures.cutout.ring_floor_m
    assert F == pytest.approx(math.sqrt(2.0) * GRID, abs=1e-4)
    # below the floor the rings fuse...
    assert _bad_phases(0.25) > 100
    assert _bad_phases(0.50) > 0
    assert _bad_phases(0.65) > 0
    # ...at and above it, never
    for d in (F, 0.75, 0.85, 1.00):
        assert _bad_phases(d) == 0, d


def test_a_curved_pair_is_what_rules_out_0_70(law):
    """0.70 m survives every phase of a straight pair and fails a CURVED
    one — which is why F is the cell diameter and not the measured 0.70.
    (24-gon rings, R = 20 m: 8 of 324 phases fuse at 0.70, none at
    0.7071.)"""
    F = law.tables.structures.cutout.ring_floor_m

    def curved(d, dx, dy, th, n=24, R=20.0):
        c, s = math.cos(th), math.sin(th)

        def ring(r):
            pts = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n))
                   for k in range(n)]
            pts.append(pts[0])
            return [(x * c - y * s + dx, x * s + y * c + dy) for x, y in pts]
        noded = shapely.unary_union(
            unary_union([LineString(ring(R)), LineString(ring(R + d))]), grid_size=GRID)
        polys = [p for p in shapely.get_parts(shapely.polygonize([noded]))
                 if p.geom_type == "Polygon" and not p.is_empty]
        if len(polys) != 2:
            return False
        band = max(polys, key=lambda p: len(p.interiors))
        if len(band.interiors) != 1:
            return False
        return min(band.exterior.distance(Point(q))
                   for q in band.interiors[0].coords) > 1e-9

    def bad(d):
        return sum(not curved(d, GRID * i / 9, GRID * j / 9, th)
                   for i in range(9) for j in range(9) for th in (0.0, 0.13, 0.4, 0.77))
    assert bad(0.70) > 0
    assert bad(F) == 0


def test_the_09_01e_0_85_m_record_is_snap_outs_not_the_arrangements():
    """§47 (3) settles the 09-01e record ("two points 0.85 m apart both
    round to ONE 0.5 m grid point").  VERTEX ROUNDING CANNOT DO IT — the
    cell diameter is 0.7071 — and the measurement finds no segment
    hot-pixel fusion above it either.  ``snap_out`` can: it rounds a
    point AWAY FROM ITS OWN ORIGIN, so a point whose origin lies on the
    far side is pushed up to a full grid step TOWARD the other ring.
    §47 (1)/(2) retire ``snap_out`` for these rings, so 0.85 does not
    raise F."""
    from auto_patch_v2.planar.structure_geometry import snap_out
    a, b = (0.999, 0.999), (1.601, 1.601)
    assert math.dist(a, b) == pytest.approx(0.8514, abs=1e-3)
    sa = snap_out(a, (0.0, 0.0), GRID)         # floor, origin inside
    sb = snap_out(b, (2.4, 2.4), GRID)         # rim, origin outside -> pushed in
    assert math.dist(sa, sb) == pytest.approx(math.sqrt(2.0) * GRID, abs=1e-9)
    # ...and 0.85 apart survives the ARRANGEMENT untouched
    assert _bad_phases(0.85) == 0


# ── §47 (1)/(2)/(3): the ring ladder on the real corridor product ────────

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    d = tmp_path_factory.mktemp("wallface") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    out = {"dir": d}
    for t in (0.25, 0.55, 0.75, 1.00, 2.00):
        # the crest plate must clear ``plate_min_area_m2`` (100 m2) for the
        # object to READ as a wall at all: 2 x t x length
        out[t] = _wall_obj(d / f"w{int(t * 100):03d}.obj", thick=t, end_a=True,
                           length=max(100.0, 70.0 / t))
    return out


def _airport_at(pack, law, t: float):
    """One wall object of MEASURED thickness ``t`` with a bore at its
    closed end — the §47 ladder's fixture."""
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    bore = (OsmWay(-101, "big_roads", ((0.0, -40.0), (0.0, -400.0)), False, tags_t),
            OsmWay(-201, "big_roads", ((0.0, -400.0), (0.0, -1300.0)), False,
                   {"highway": "secondary", "lanes": "2"}))
    name = f"w{int(t * 100):03d}"
    objs = {"dir": pack["dir"], name: pack[t]}
    airport, objects, _cache, cs, st = _corridors(
        objs, law, [(name, (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")], bore)
    assert st.corridors == 1, st.refused
    return airport, objects, cs


def _corridor_at(pack, law, t: float):
    airport, objects, cs = _airport_at(pack, law, t)
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    return cs[0], cl2, tunnels, sst


@pytest.mark.parametrize("t", [0.25, 0.55, 0.75, 1.00, 2.00])
def test_the_ring_ladder(pack, law, t):
    """§47 (1): the FLOOR ring is the inner face and the RIM ring the
    outer face, so the band is the wall's own ``t``.  §47 (3): where
    ``t < F`` the FLOOR STAYS on the inner face and the RIM YIELDS
    outward by exactly ``F − t`` (OTHH's 0.25 / 0.55 m Dewatering
    shells)."""
    co = law.tables.structures.cutout
    F = co.ring_floor_m
    c, cl2, tunnels, sst = _corridor_at(pack, law, t)
    assert not [r for r in sst.refused if ".obj" in r], sst.refused
    # the wall READER's own measurement is what the law reads — at
    # ``wall_sample_m`` 2.0 m the 0.25 m authored shell reads 0.50 m, and
    # that reading (not the author's number) is the band's input
    t_read = c.stations[len(c.stations) // 2].thick_l
    assert t_read == pytest.approx(t, abs=0.05) or (t < 0.5 and t_read <= 0.55)
    band = rim_standoff(t_read, co)[1]
    assert band == pytest.approx(max(t_read, F))
    assert rim_yield_m(t_read, co) == pytest.approx(max(F - t_read, 0.0))
    # NO SHELL IS REFUSED FOR THINNESS (§47 (3))
    near = c.footprint.buffer(5.0)
    ramps = [Polygon(x.ring) for x in cl2.cells if x.role == "tunnel_ramp"
             and near.intersects(Polygon(x.ring))]
    walls = [Polygon(x.ring, x.holes) for x in cl2.cells if x.role == "retaining_wall"
             and near.intersects(Polygon(x.ring, x.holes))]
    assert ramps and walls
    ramp_u = unary_union(ramps)
    # THE FLOOR IS ON THE INNER FACE: the ramp is the corridor's own
    # trench, not the trench ⊕ an overlap (the 08a law), to within the
    # station chords
    assert ramp_u.area == pytest.approx(c.trench.area, rel=0.02)
    # THE RIM IS ON THE OUTER FACE (or yielded by exactly F − t): every
    # rim vertex stands the designed band off the floor ring
    dists = [ramp_u.exterior.distance(Point(p)) for w in walls for p in w.exterior.coords
             if ramp_u.exterior.distance(Point(p)) > 1e-6
             and c.walls.buffer(3.0 * max(t_read, F)).contains(Point(p))]
    assert dists
    assert min(dists) == pytest.approx(band, abs=1e-6)
    # (the closed end's corner is the MITRE of the two outer faces, issue
    # #16: √2 × the band from the floor corner, never more)
    assert max(dists) <= band * math.sqrt(2.0) + GRID + 1e-6
    # §47 (2): THE EMIT PATH NEVER LEAVES THE WALL — the rim stands
    # inside the walls' own footprint ⊕ the named yield, never a grid
    # step outside it (the 08e OWED deviation (2): ≈ 0.4 m OUTSIDE a
    # 1.0 m wall)
    # (the END CAPS are excluded for the reason ``trench_outside_m``'s
    # docstring gives: a corridor's axis starts at its MOUTH — the end
    # wall's OUTER face — so the cap, which stands the END wall's own
    # band beyond s = 0, lands outside the wall polygon by construction.
    # That origin is the corridor READER's, not this ring law's.)
    # the yield is against the wall's REAL plan thickness, which for a
    # 0.25 m shell is NOT what the station reader reports: at
    # ``wall_sample_m`` 2.0 m every station of the 0.25 m object reads
    # 0.50 m, so the rim stands F − 0.25 = 0.457 m past the outer face
    # where the named yield (F − 0.50) is 0.207 m.  The over-report is
    # the WALL READER's (``airport/tunnel_objects``), not this ring law's,
    # and it is what the twin allows for.
    wb, tb = c.walls.bounds, c.trench.bounds
    t_real = min(tb[0] - wb[0], wb[2] - tb[2])
    allowed = c.walls.buffer(rim_yield_m(t_real, co) + 1e-3,
                             join_style="mitre", mitre_limit=2.0)
    ax = LineString(c.axis)
    outside = [p for w in walls for p in w.exterior.coords
               if not allowed.contains(Point(p))
               and ramp_u.exterior.distance(Point(p)) > 1e-6
               and c.walls.buffer(3.0 * max(t_read, F)).contains(Point(p))
               and c.mouth_thickness_m <= ax.project(Point(p))
               <= c.length_m - c.far_thickness_m]
    assert not outside, outside[:3]
    # §47 (5): 05n-2 reads 0 with NO overlap term
    tn = [x for x in tunnels if x.source == "object"][0]
    assert tn.trench_outside_max_m == 0.0


def test_the_designed_band_is_not_readable_off_the_emitted_product(pack, law):
    """§47 (4) MEASURED AND REFUTED AS WRITTEN: the bar cannot be the
    DESIGNED band ``max(t, F)``, because the arrangement snap-rounds BOTH
    rings to the 0.5 m identity lattice and each vertex may move half a
    cell diagonal toward the other.  Designed → smallest emitted
    rim-to-floor distance, measured here: 0.7071 → 0.500, 1.0000 → 0.707,
    2.0000 → 1.803 — and, since the walled cap corner became the MITRE of
    the two outer faces (issue #16, lane ``tunnelwitness``; the 1.0 / 2.0
    rungs were read at the diagonal-cut corner), 0.500 / 1.000 / 2.000.  What DOES hold at every rung is the thing §47 (3)
    exists for: the rings never FUSE (0 shared vertices).  So
    ``structure_rim_gap`` keeps the identity spacing as its bar."""
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.constraints import structures as C
    from auto_patch_v2.constraints.precedence import view
    co = law.tables.structures.cutout
    spacing = law.tables.emit.identity.min_distinct_spacing_m
    want = {0.55: 0.500, 1.00: 1.000, 2.00: 2.000}
    for t, emitted in want.items():
        airport, objects, cs = _airport_at(pack, law, t)
        pm, _stats = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
        tns = [x for x in pm.structures if x.source == "object"]
        walls, ramps = C.wall_faces_of(pm, tns), C.ramp_faces_of(pm, tns)
        vw = view(pm, law)
        roles = {"tunnel_ramp", "door_ramp", "wall_corridor_ramp", "garage_ramp",
                 "tunnel_trench"}
        ramp_vs = {v for fs in ramps.values() for f in fs for v in pm.ring_vertices(f.ring)}
        pts = [pm.vertices[v].xy for v in ramp_vs]
        for tn in tns:
            rim = [v for f in walls.get(tn.id, ()) for v in pm.ring_vertices(f.ring)
                   if not any(pm.faces[fid].role in roles for fid in vw.vertex_faces[v])]
            assert rim and not (set(rim) & ramp_vs)          # NEVER fused
            d = min(min(math.hypot(pm.vertices[v].xy[0] - q[0], pm.vertices[v].xy[1] - q[1])
                        for q in pts) for v in rim)
            assert d == pytest.approx(emitted, abs=0.01)
            band = rim_standoff(cs[0].stations[len(cs[0].stations) // 2].thick_l, co)[1]
            # issue #16 (the walled cap corner is the MITRE): the corner
            # squeeze is gone, so the 1.0 m rung now reads its band exactly;
            # the others still read under it — never over
            assert d <= band + 1e-6
            assert d >= spacing - 1e-6                                  # ...but distinct
    from auto_patch_v2.verify import structures as V
    import inspect
    assert "min_distinct_spacing_m" in inspect.getsource(V.structure_rim_gap)


# ── §47.1 (8): THE TWO SEAM-PROBES ──────────────────────────────────────

def test_seam_probe_on_floor_with_the_rim_on_the_face(pack, law):
    """SEAM-PROBE 1 — ``constraints/structures.on_floor`` (``:242-258``)
    with the rim ON the face, where it may coincide with foreign ground
    (the 15bh VHHH class).

    ``on_floor`` drops a wall-ring vertex from the RIM's own row set (it
    is the ramp's).  The 15bh failure was the rim and the floor FUSING,
    after which airside vertices standing on the shared ring took the
    FLOOR row.  §47 (3)'s ``F`` is what forbids that: with the band at
    ``max(t, F)`` no rim vertex is ever a floor vertex, whatever the
    wall's thickness — measured here on the thinnest shell in the ladder
    (0.25 m, the whole band a yield)."""
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.constraints import structures as C
    from auto_patch_v2.constraints.precedence import view
    c, _cl2, _tn, _sst = _corridor_at(pack, law, 0.25)
    objs = {"dir": pack["dir"], "w025": pack[0.25]}
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    bore = (OsmWay(-101, "big_roads", ((0.0, -40.0), (0.0, -400.0)), False, tags_t),
            OsmWay(-201, "big_roads", ((0.0, -400.0), (0.0, -1300.0)), False,
                   {"highway": "secondary", "lanes": "2"}))
    airport, objects, _cache, cs, _st = _corridors(
        objs, law, [("w025", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")], bore)
    pm, _stats = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    tunnels = [x for x in pm.structures if x.source == "object"]
    assert tunnels
    walls = C.wall_faces_of(pm, tunnels)
    ramps = C.ramp_faces_of(pm, tunnels)
    vw = view(pm, law)
    ramp_roles = {"tunnel_ramp", "door_ramp", "wall_corridor_ramp", "garage_ramp",
                  "tunnel_trench"}

    def on_floor(v: int) -> bool:
        return any(pm.faces[fid].role in ramp_roles for fid in vw.vertex_faces[v])

    ramp_vs = {v for fs in ramps.values() for f in fs for v in pm.ring_vertices(f.ring)}
    for tn in tunnels:
        wall_vs = {v for f in walls.get(tn.id, ()) for v in pm.ring_vertices(f.ring)}
        rim_vs = [v for v in wall_vs if not on_floor(v)]
        # THE FINDING: the void's exterior (the RIM) and its hole (the
        # FLOOR) share NO vertex — the rim keeps a full row set even at
        # 0.25 m of authored wall, because the band is F, not t
        assert rim_vs, tn.id
        assert not (set(rim_vs) & ramp_vs)
        # ...and every rim vertex stands at least the lattice floor off
        # every floor vertex in plan: the fusion 15bh read cannot recur
        floor_pts = [pm.vertices[v].xy for v in ramp_vs]
        spacing = law.tables.emit.identity.min_distinct_spacing_m
        for v in rim_vs:
            x, y = pm.vertices[v].xy
            assert min(math.hypot(x - q[0], y - q[1]) for q in floor_pts) >= spacing - 1e-6


def test_seam_probe_rim_edges_under_tunnel_mouth_canonical(law):
    """SEAM-PROBE 2 — ``verify/structures._rim_edges`` (``:308``) under
    ``tunnel_mouth_canonical``.

    THE FINDING: §47 moves NO rim this reader sees.  Its cap search runs
    at ``reach = wall_gap_m + wall_band_width_m + 1`` = 2.6 m of the
    mouth line, and (a) its ramp population is the ``tunnel_ramp`` ROLE
    only — door wells (``door_ramp``) and wall corridors
    (``wall_corridor_ramp`` / ``garage_ramp``) are not in it at all; (b)
    every OBJECT corridor is skipped by its own ``on_object`` gate (the
    sidecar's ``tunnel_objects`` axes), which §47 does not touch; and (c)
    an OSM BORE's rim law is ``wall_gap_m + wall_band_width_m``, which
    §47 leaves exactly where it was (only ``rim_standoff`` — the OBJECT
    wall path — changes).  So the edge set ``_rim_edges`` returns and the
    distances the cap search prices are unchanged by this lane."""
    from auto_patch_v2.verify import structures as V
    import inspect
    tn = law.tables.structures.tunnel
    assert V._ramps.__doc__ is None                       # the role list is the body
    assert 'sh.role == "tunnel_ramp"' in inspect.getsource(V._ramps)
    src = inspect.getsource(V.tunnel_mouth_canonical)
    assert "on_object" in src and "tunnel_objects" in src
    reach = tn.wall_gap_m + tn.wall_band_width_m + 1.0
    assert reach == pytest.approx(2.6)
    # the OSM bore's rim stand-off — the only one this reader prices —
    # is not a ``rim_standoff`` value at all
    assert tn.wall_gap_m + tn.wall_band_width_m == pytest.approx(1.6)
    assert "rim_standoff" not in inspect.getsource(V)
    # ...and the one OBJECT cap that does move (an end wall's cap stands
    # at its own thickness now, not ``rim_standoff`` of it) stays inside
    # the reader's reach for every OTHH end wall (2.00-2.53 m measured)
    co = law.tables.structures.cutout
    for t in (2.00, 2.53):
        assert rim_standoff(t, co)[1] <= reach
