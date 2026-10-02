"""§39 (1) THE HAIRLINE LAW — the SHORE WELD, on the LEMD geometry that
made the defect (owner RULINGS 2026-09-13bk).

THE SITE, verbatim from the shipped ``Data+40-004.poly`` of app 1.0.327:
a WATER edge (marker 1) from 40.47647780, −3.54580410 to 40.47587640,
−3.54541440 — 74.5 m — and, running along it, three BANK FOOT segments
(marker 15) sharing BOTH endpoints exactly and passing through
40.47627733349, −3.54567419923 and 40.47607686682, −3.54554429923.  Those
two intermediate points are the chord split of the SAME line computed in
the tmerc metres frame; the mesh's own straight line is the degree-space
one, and the two are 0.0676 mm apart in the middle.  Triangle4XP must
recover both and cascades Steiner points into the wedge: 2,301,676
triangles under 0.1 m², a tile X-Plane would not load.

The weld drops the two interior splits — the segment they split survives
as the WATER's own — and the ring then SHARES the water edge exactly.
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.emit.osm_adapter import (WeldReport, shore_edges_of,
                                            weld_to_shore)
from auto_patch_v2.emit.surface import (GradedSurface, SurfaceBreakline,
                                        SurfaceFace, SurfaceVertex)
from auto_patch_v2.law import Law

#: The water edge, as the mesh constrains it (7-dp OSM coordinates).
A = (40.47647780, -3.54580410)
B = (40.47587640, -3.54541440)
#: The tmerc-frame chord splits the bank ring laid on it.
S1 = (40.47627733349, -3.54567419923)
S2 = (40.47607686682, -3.54554429923)

M_LAT = 111_320.0


def _m(p, q):
    k = M_LAT * math.cos(math.radians(p[0]))
    return math.hypot((q[0] - p[0]) * M_LAT, (q[1] - p[1]) * k)


def _dist_to_AB(p) -> float:
    """Metres from ``p`` to the straight DEGREE-space segment A→B."""
    k = M_LAT * math.cos(math.radians(A[0]))
    ax, ay = (A[1] - A[1]) * k, (A[0] - A[0]) * M_LAT
    bx, by = (B[1] - A[1]) * k, (B[0] - A[0]) * M_LAT
    px, py = (p[1] - A[1]) * k, (p[0] - A[0]) * M_LAT
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


@pytest.fixture
def law():
    return Law.for_airport("LEMD")


def _surface(ring_ll) -> GradedSurface:
    verts = tuple(SurfaceVertex(i, ll, 600.0) for i, ll in enumerate(ring_ll))
    ids = tuple(range(len(ring_ll)))
    return GradedSurface(icao="TEST", ruleset="icao", origin=A,
                         crs="+proj=tmerc", identity_dp=11, vertices=verts,
                         faces=(), breaklines=(
                             SurfaceBreakline(1, "bank_foot", "bank:46", ids),),
                         provenance={})


def test_the_defect_is_real_before_the_weld():
    """The two chord splits are 0.06 mm off the mesh's own water line —
    the hairline, in the numbers the scout measured."""
    assert _m(A, B) == pytest.approx(74.5, abs=0.2)
    d1, d2 = _dist_to_AB(S1), _dist_to_AB(S2)
    assert 5.0e-5 < d1 < 1.0e-4, d1          # 0.0594 mm at the site
    assert 5.0e-5 < d2 < 1.0e-4, d2
    # ... and they are chord splits: exactly on the tmerc-metres chord
    assert _m(A, S1) == pytest.approx(_m(S1, S2), abs=0.01)


def test_shore_weld_drops_the_chord_splits(law):
    """A run of interior splits along one water edge is welded away: the
    ring keeps the water's own vertices and nothing beside them."""
    ring = [A, S1, S2, B, (40.4757, -3.5470)]
    rep = WeldReport()
    out = weld_to_shore(_surface(ring), law, [(A, B)], rep)
    kept = [v.ll for v in out.vertices]
    assert S1 not in kept and S2 not in kept
    assert A in kept and B in kept
    assert rep.dropped == 2
    assert rep.stranded == 0
    assert rep.worst_mm_before == pytest.approx(0.0676, abs=0.02)


def test_a_vertex_near_a_water_vertex_is_snapped_onto_it(law):
    """Not beside it: ON it — the 11-dp identity join then makes them one
    node (water is a datum and already carries the vertex)."""
    off = (A[0] + 2.0e-6, A[1] + 1.0e-6)     # ~0.25 m away
    ring = [off, (40.4757, -3.5470), (40.4758, -3.5480)]
    rep = WeldReport()
    out = weld_to_shore(_surface(ring), law, [(A, B)], rep)
    assert rep.snapped == 1
    assert out.vertices[0].ll == A


def test_a_shared_vertex_is_projected_not_dropped(law):
    """Dropping a vertex two sequences share would leave a T-junction —
    the same defect one dimension down.  It is PROJECTED ONTO the chord
    instead (owner RULINGS 2026-09-13bt (5') / 13cg (i)): it lands on the
    line the mesh constrains, so the mesher splits that segment there and
    no wedge exists."""
    verts = tuple(SurfaceVertex(i, ll, 600.0)
                  for i, ll in enumerate([A, S1, S2, B, (40.4757, -3.5470)]))
    surf = GradedSurface(
        icao="TEST", ruleset="icao", origin=A, crs="+proj=tmerc",
        identity_dp=11, vertices=verts, faces=(),
        breaklines=(SurfaceBreakline(1, "bank_foot", "a", (0, 1, 2, 3, 4)),
                    SurfaceBreakline(2, "bank_foot", "b", (1, 2))),
        provenance={})
    rep = WeldReport()
    out = weld_to_shore(surf, law, [(A, B)], rep)
    assert rep.dropped == 0
    assert rep.projected == 2 and rep.stranded == 0
    moved = [v.ll for v in out.vertices][1:3]
    assert moved != [S1, S2]
    for ll in moved:
        assert _dist_to_AB(ll) < 1.0e-9, (
            "a projected vertex stands ON the mesh's own straight segment")


def test_a_lawful_run_a_metre_away_is_untouched(law):
    """The law is the identity spacing (0.5 m), not "near water"."""
    far = [(p[0] + 4.0e-5, p[1]) for p in (A, S1, S2, B)]   # ~2.0 m off the line
    rep = WeldReport()
    out = weld_to_shore(_surface(far), law, [(A, B)], rep)
    assert rep.candidates == 0 and rep.dropped == 0 and rep.snapped == 0
    assert [v.ll for v in out.vertices] == far


class _FakeWater:
    lat, lon = 40, -4

    def __init__(self, polys):
        self.polys = polys


class _FakeDem:
    def __init__(self, polys):
        self._w = _FakeWater(polys)

    def water(self, lat, lon):
        return self._w if (lat, lon) == (40, -4) else None


def test_shore_edges_of_reads_the_tile_witness_in_lat_lon():
    """The witness is the core's own ``TileWater.polys`` (tile-relative
    degrees), returned as lat/lon edges — never a second water source."""
    from shapely.geometry import Polygon
    poly = Polygon([(A[1] + 4, A[0] - 40), (B[1] + 4, B[0] - 40),
                    (B[1] + 4 + 1e-4, B[0] - 40 - 1e-4),
                    (A[1] + 4 + 1e-4, A[0] - 40 - 1e-4)])
    edges = shore_edges_of(_FakeDem([poly]), _surface([A, S1, S2, B]))
    assert edges
    got = {(tuple(round(c, 7) for c in a), tuple(round(c, 7) for c in b))
           for a, b in edges}
    want = (tuple(round(c, 7) for c in A), tuple(round(c, 7) for c in B))
    assert want in got or want[::-1] in got


# ── §39 (iii) THE IDENTITY JOIN MERGES A SUB-SPACING SEGMENT ────────────
# (owner RULINGS 2026-09-13cg (iii)).  Measured on the round-1 arms: LEMD
# 932 emitted constrained segments under the 0.5 m spacing, KCLT 1,635,
# VMMC 1,631, the shortest 5.6 micrometres at 35.2153165, −80.9285365.

def _square(law, *extra):
    """A 40 m apron ring, plus whatever extra vertices are given."""
    base = [(40.4760, -3.5460), (40.4760, -3.5455),
            (40.4763, -3.5455), (40.4763, -3.5460)]
    pts = list(base) + list(extra)
    verts = tuple(SurfaceVertex(i, ll, 600.0) for i, ll in enumerate(pts))
    ring = tuple(range(len(pts)))
    return GradedSurface(icao="TEST", ruleset="icao", origin=base[0],
                         crs="+proj=tmerc", identity_dp=11, vertices=verts,
                         faces=(SurfaceFace(1, "apron", "pav1", ring, (), "airside"),),
                         breaklines=(), provenance={})


def test_a_sub_spacing_segment_is_merged_away(law):
    """A 5.6 micrometre neighbour — KCLT's own shortest — is not a vertex."""
    from auto_patch_v2.emit.osm_adapter import merge_sub_spacing
    tiny = (40.4763 + 5.6e-6 / M_LAT, -3.5460)
    rep = WeldReport()
    out = merge_sub_spacing(_square(law, tiny), law, rep)
    assert rep.merged == 1
    assert len(out.faces[0].ring) == 4
    assert tiny not in [v.ll for v in out.vertices]


def test_the_survivor_keeps_its_coordinate(law):
    """Nothing MOVES: one of the two disappears and the other stands where
    it stood.  WHICH one is :func:`survivor_key`'s — the lower canonical
    coordinate — and NOT the vertex more sequences share (issue #199).

    This test carried the OLD law: ``tiny`` is shared by the breakline, so
    the degree rule kept it and dropped the ring's own corner.  Under the
    pair-local key the ring corner has the lower latitude and survives, and
    the junction's coordinate MOVES — by 0.2 m here, always under
    ``min_distinct_spacing_m``, the band inside which the law says the two
    were never distinct vertices.  REPORTED as a deviation on #199, not
    decided here; the ring does not tear either way (below)."""
    from auto_patch_v2.emit.osm_adapter import merge_sub_spacing
    tiny = (40.4763 + 0.2 / M_LAT, -3.5460)
    corner = (40.4763, -3.5460)
    surf = _square(law, tiny)
    surf = type(surf)(**{**surf.__dict__,
                         "breaklines": (SurfaceBreakline(1, "bank_foot", "b",
                                                         (4, 0)),)})
    out = merge_sub_spacing(surf, law, WeldReport())
    kept = [v.ll for v in out.vertices]
    assert corner in kept, "the lower canonical coordinate survives"
    assert tiny not in kept
    # NO RING TEARS: the breakline that met the ring at ``tiny`` meets it
    # at the survivor — the merge remaps the dropped vertex EVERYWHERE.
    kept_id = next(v.id for v in out.vertices if v.ll == corner)
    assert kept_id in out.breaklines[0].vertices
    assert set(out.faces[0].ring) & set(out.breaklines[0].vertices)


# ── §39 (iii) THE SURVIVOR IS THE PAIR'S OWN (issue #199) ───────────────
# ``merge_sub_spacing`` kept the senior by ``(sequences sharing the vertex,
# then the lower id)``.  Both terms read the WHOLE arrangement, so the
# emitted node set flipped between the two members of a 0.5 m pair that
# both exist in the planar map of every arm — 4 pairs measured at HECA
# against sw1003 (RULINGS 2026-10-02k mechanism 3), among them #150's
# "building9 vertex moved 0.5 m, unattributed".

#: The HECA pair of issue #199's first table row (apron ``pav1`` /
#: ``building9``): 0.5 m apart, and the survivor FLIPPED between arms.
H_PAIR_A = (30.11003015117, 31.39688841457)
H_PAIR_B = (30.11003015049, 31.39688322676)
#: Somewhere else entirely in the layout — the "unrelated upstream set".
H_ELSEWHERE = (30.10560435655, 31.39003118471)


def _pair_surface(*, ids, degrees, extra=()):
    """The #199 pair as a face ring, with the pair's GLOBAL IDS and the
    DEGREES of its two members both under the caller's control.

    ``ids`` is the (a, b) id pair; ``degrees`` is how many extra sequences
    each member is shared by; ``extra`` are unrelated vertices added to the
    ring elsewhere in the layout.  The pair's own geometry never changes,
    so a survivor rule that reads only the pair must return the same answer
    for every combination."""
    far = [(30.1110, 31.3980), (30.1110, 31.3960), (30.1100, 31.3960)]
    pts = {ids[0]: H_PAIR_A, ids[1]: H_PAIR_B}
    nxt = max(ids) + 1
    ring = [ids[0], ids[1]]
    for ll in list(extra) + far:
        pts[nxt] = ll
        ring.append(nxt)
        nxt += 1
    breaks = []
    for member, n in zip(ids, degrees):
        for _k in range(n):
            # a two-vertex open chain: it SHARES ``member`` (so the member's
            # degree rises) and its other end is 100 m away, out of the
            # merge's reach
            pts[nxt] = (30.1120 + 1e-4 * nxt, 31.3990)
            breaks.append(SurfaceBreakline(len(breaks) + 1, "bank_foot",
                                           f"b{len(breaks) + 1}",
                                           (member, nxt)))
            nxt += 1
    verts = tuple(SurfaceVertex(i, ll, 600.0) for i, ll in sorted(pts.items()))
    return GradedSurface(icao="TEST", ruleset="icao", origin=H_PAIR_A,
                         crs="+proj=tmerc", identity_dp=11, vertices=verts,
                         faces=(SurfaceFace(1, "apron", "pav1", tuple(ring),
                                            (), "airside"),),
                         breaklines=tuple(breaks), provenance={})


def _survivor_ll(law, surf):
    """Which member of the #199 pair the merge kept."""
    from auto_patch_v2.emit.osm_adapter import merge_sub_spacing
    out = merge_sub_spacing(surf, law, WeldReport())
    kept = {v.ll for v in out.vertices}
    assert (H_PAIR_A in kept) != (H_PAIR_B in kept), (
        "exactly one member of a sub-spacing pair survives")
    return H_PAIR_A if H_PAIR_A in kept else H_PAIR_B


def test_the_pair_of_199_is_under_the_spacing(law):
    """The fixture IS the issue's pair: 0.5 m apart, so the merge acts."""
    assert _m(H_PAIR_A, H_PAIR_B) < float(
        law.tables.emit.identity.min_distinct_spacing_m)


def test_the_survivor_key_reads_only_the_vertexs_own_coordinate():
    """The key of a vertex is its ``ll`` at the identity, and nothing
    else — no id, no degree, no neighbour."""
    from auto_patch_v2.emit.osm_adapter import (SURVIVOR_IS_MINIMUM,
                                                survivor_key)
    assert SURVIVOR_IS_MINIMUM is True
    assert survivor_key(H_PAIR_A, 11) == H_PAIR_A
    assert survivor_key(H_PAIR_B, 11) < survivor_key(H_PAIR_A, 11)
    # the key rounds AT the identity: a difference below the written
    # coordinate cannot decide a survivor
    below = (H_PAIR_B[0] + 1e-13, H_PAIR_B[1])
    assert survivor_key(below, 11) == survivor_key(H_PAIR_B, 11)


@pytest.mark.parametrize("ids", [(1, 2), (2, 1), (907, 11), (11, 907)])
@pytest.mark.parametrize("degrees", [(0, 0), (3, 0), (0, 3), (1, 2)])
def test_the_same_pair_keeps_the_same_survivor_whatever_its_ids_and_degrees(
        law, ids, degrees):
    """ISSUE #199, THE BAR: the pair's geometry decides, so renumbering the
    vertices or changing how many sequences each member is shared by must
    not move the survivor.  Under the old ``(degree, -id)`` rule EVERY one
    of these 16 combinations could answer differently."""
    got = _survivor_ll(law, _pair_surface(ids=ids, degrees=degrees))
    assert got == H_PAIR_B


def test_an_unrelated_vertex_elsewhere_changes_no_survivor(law):
    """#199's mechanism, as a synthetic layout: an upstream set that adds a
    vertex SOMEWHERE ELSE (a plateau cut adding faces) renumbers ids and
    shifts degrees.  The pair's survivor must not notice."""
    base = _survivor_ll(law, _pair_surface(ids=(1, 2), degrees=(0, 0)))
    with_extra = _survivor_ll(
        law, _pair_surface(ids=(1, 2), degrees=(0, 0), extra=(H_ELSEWHERE,)))
    renumbered = _survivor_ll(
        law, _pair_surface(ids=(40, 41), degrees=(2, 1),
                           extra=(H_ELSEWHERE,)))
    assert base == with_extra == renumbered == H_PAIR_B


def test_a_lawful_ring_is_untouched(law):
    from auto_patch_v2.emit.osm_adapter import merge_sub_spacing
    rep = WeldReport()
    surf = _square(law)
    out = merge_sub_spacing(surf, law, rep)
    assert rep.merged == 0 and out is surf


def test_a_triangle_is_never_collapsed_away(law):
    """Three vertices are the smallest thing the mesh can constrain."""
    from auto_patch_v2.emit.osm_adapter import merge_sub_spacing
    d = 0.1 / M_LAT
    pts = [(40.4760, -3.5460), (40.4760 + d, -3.5460), (40.4760, -3.5460 + d)]
    verts = tuple(SurfaceVertex(i, ll, 600.0) for i, ll in enumerate(pts))
    surf = GradedSurface(icao="TEST", ruleset="icao", origin=pts[0],
                         crs="+proj=tmerc", identity_dp=11, vertices=verts,
                         faces=(SurfaceFace(1, "apron", "p", (0, 1, 2), (), "airside"),),
                         breaklines=(), provenance={})
    out = merge_sub_spacing(surf, law, WeldReport())
    assert len(out.faces[0].ring) == 3
