"""THE BANK and THE PAD PLANE — lane ``v2bank``'s twins (owner RULINGS
2026-09-09e and 2026-09-09c; spec ``docs/specs/auto-patch-v2/
design-surface-spec.md`` §9).

THE BANK (09e).  §8.4 measured that Ortho4XP's mesh does not blend: it
drapes the raw DEM up to the patch's constrained boundary, so a patch ring
16.6 m off the terrain builds a 16.8 m cliff one triangle wide.  Outside
every patch-boundary ring the patch now emits a BANK FOOT ring ON THE DEM
at ``d = max(bank_min_width_m, |z_ring − DEM(foot)| / bank_slope)``.

THE PAD PLANE (09c).  A pad is ONE PLANE: flat is a strong TARGET, 1 % of
tilt a HARD ceiling.  The merged ``Flat`` group — which made every pad
exactly flat and dragged everything welded to it to that one level — is
gone.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate, stack
from auto_patch_v2.constraints import pads as padgen
from auto_patch_v2.emit.bank import (BANK_KIND, BankReport, coverage_polygon,
                                     daylight_feet, intermediate_offsets,
                                     smooth_along, with_bank)
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import BANK_FEATURE, render_patch
from auto_patch_v2.model.constraints import Diff, Pin
from auto_patch_v2.solve import solve_design
from auto_patch_v2.solve.design import assemble, DesignReport, hard_rulings, \
    pad_flat_rulings, ruling_head
from auto_patch_v2.verify.pads import plane_fit
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot
from tests.auto_patch_v2.test_v2smooth import RUN_LEN, _airport, law  # noqa: F401


class _FlatDem:
    """Level ground at 700 m — so the ring's height above the DEM is
    exactly what the fixture sets it to."""

    provenance = {"synthetic": "level ground"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _built(law, dem, cells):                                # noqa: F811
    from auto_patch_v2.planar.build import build
    airport, r = _airport(law, dem, ())
    cl = Classification(tuple(cells), (), {}, ())
    pm, _st = build(airport, cl, law)
    return airport, pm, r


@pytest.fixture(scope="module")
def apron_map(law):                                         # noqa: F811
    """ONE apron with the zone law's graded strip around it, over level
    ground: a single patch body, so the bank is read against ITS ring and
    no neighbouring body shares it (that is the next twin's subject)."""
    cells = (
        Cell(0, "apron", "apron1", _rect(_rot(90.0), -200.0, 120.0, 200.0, 320.0),
             (), None, "D", "airside", "apron", {}),
    )
    return _built(law, _FlatDem(), cells)


def _bank(airport, pm, law, lift: float):                   # noqa: F811
    """The banked surface with EVERY vertex standing ``lift`` m above the
    level DEM (the solve is not what this reads — the bank's geometry is)."""
    from auto_patch_v2.solve.api import Solution, Status
    z = {v: 700.0 + lift for v in pm.vertices}
    sol = Solution(z, Status.OPTIMAL, None, 0, 0.0, "fixture")
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    rep = BankReport()
    return with_bank(surf, pm, law, airport, rep), surf, rep


# ── (1) THE BANK: the foot distance IS the ruling's formula ─────────────

def test_a_ring_six_metres_up_puts_its_foot_at_one_in_three(apron_map, law):  # noqa: F811
    """09e: ``d = |z_ring − DEM| / bank_slope`` — 6 m of fill at 0.33 is a
    foot 18.2 m out, and the foot stands ON the DEM."""
    airport, pm, _r = apron_map
    banked, surf, rep = _bank(airport, pm, law, 6.0)
    assert rep.rings >= 1 and rep.foot_vertices > 0
    d = law.tables.emit.design
    want = 6.0 / d.bank_slope                            # 18.18 m at 1:3
    # the statistics read the PLAN distance from each foot node to the
    # coverage: ``want`` along an edge, ``want * sqrt(2)`` at a mitred
    # right-angle corner (the corner's own perpendicular bank is still
    # ``want``), so the mean sits between the two and the max is the miter
    assert rep.max_m == pytest.approx(want * math.sqrt(2.0), abs=0.5), rep
    assert want - 0.5 <= rep.mean_m <= want * math.sqrt(2.0) + 0.5, rep
    # the foot IS the terrain (the FOOT ring's own vertices — the face's
    # intermediate rings, 09f-1, stand between the design z and this one)
    zof = {v.id: v.z for v in banked.vertices}
    foot_ids = {v for b in banked.breaklines if b.kind == BANK_KIND
                and "@" not in b.ref for v in b.vertices}
    assert foot_ids and all(abs(zof[v] - 700.0) < 1e-6 for v in foot_ids)
    # ... and the bank it makes is no steeper than the law's 1:3
    assert rep.max_slope <= d.bank_slope + 1e-3, rep


def test_a_ring_one_metre_up_takes_the_minimum_width(apron_map, law):  # noqa: F811
    """09e: ``max(bank_min_width_m, …)`` — 1 m of fill would want 3.0 m,
    the floor gives it 5.0."""
    airport, pm, _r = apron_map
    _banked, _surf, rep = _bank(airport, pm, law, 1.0)
    d = law.tables.emit.design
    assert 1.0 / d.bank_slope < d.bank_min_width_m       # the floor is what binds
    assert d.bank_min_width_m - 0.2 <= rep.mean_m <= \
        d.bank_min_width_m * math.sqrt(2.0) + 0.2, rep
    assert rep.max_m == pytest.approx(d.bank_min_width_m * math.sqrt(2.0),
                                      abs=0.2), rep
    # a bank at the FLOOR is gentler than the law's 1:3, never steeper
    assert rep.max_slope < d.bank_slope, rep


def test_the_foot_follows_the_ground_away_on_sloping_terrain(law):   # noqa: F811
    """RE-SCOPED for THE DAYLIGHT LINE (owner RULINGS 2026-09-09g, spec
    §11): the foot is no longer the fixed point of ``|z_ring - DEM(foot)| /
    bank_slope`` but the DAYLIGHT point of the 1:3 slope line
    (:func:`daylight_feet`).  On SMOOTH ground the two agree exactly, and
    this twin is the proof: on ground falling 10 % away from the ring a 6 m
    ring daylights at ``6 / (0.33 - 0.10)`` — the old fixed point's own
    answer."""
    class _Slope:
        provenance = {"synthetic": "10 % fall"}

        def z(self, x, y):
            return 700.0 - 0.10 * x

        def bounds(self):
            return (-1e4, -1e4, 1e4, 1e4)

    d = law.tables.emit.design
    pts = np.array([[0.0, 0.0]])
    nrm = np.array([[1.0, 0.0]])
    got, kind = daylight_feet(np.array([706.0]), pts, nrm, _Slope(),
                              d.bank_slope, d.bank_min_width_m,
                              d.bank_max_width_m, d.bank_sample_m,
                              d.bank_daylight_tol_m)
    want = 6.0 / (d.bank_slope - 0.10)
    assert float(got[0]) == pytest.approx(want, rel=0.02)
    assert int(kind[0]) == 1                             # a true daylight


# ── (2) THE FOOT STOPS AT THE NEXT PATCH RING ──────────────────────────

def test_the_foot_stops_at_a_neighbouring_ring(law):        # noqa: F811
    """09e: "where the foot would cross another patch ring the two rings
    share the bank (the foot stops at the other ring)".  Two patch bodies
    12 m apart, each standing 6 m up: unclipped each foot would run 18.2 m
    and land inside the other."""
    from shapely.geometry import LineString, Polygon
    from shapely.strtree import STRtree
    from auto_patch_v2.emit.bank import _ray_limit
    a = Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])
    b = Polygon([(112, 0), (212, 0), (212, 50), (112, 50)])
    segs = []
    for poly in (a, b):
        cs = list(poly.exterior.coords)
        segs.extend(LineString([cs[i], cs[i + 1]]) for i in range(len(cs) - 1))
    tree = STRtree(segs)
    d = law.tables.emit.design
    pts = np.array([[100.0, 25.0]])
    nrm = np.array([[1.0, 0.0]])
    want = 6.0 / d.bank_slope
    assert want > 12.0                                   # it WOULD cross
    got = _ray_limit(pts, nrm, np.array([want]), tree, segs, d.bank_min_width_m)
    assert float(got[0]) == pytest.approx(12.0, abs=0.05)
    # and a ray with nothing in its way keeps the formula's distance
    free = _ray_limit(np.array([[0.0, 25.0]]), np.array([[-1.0, 0.0]]),
                      np.array([want]), tree, segs, d.bank_min_width_m)
    assert float(free[0]) == pytest.approx(want, abs=1e-6)


# ── (3) THE TOE DOES NOT ZIGZAG ────────────────────────────────────────

def test_the_foot_chain_is_smoothed_along_itself(law):      # noqa: F811
    """09e: "a second-difference target along the foot chain so the bank's
    toe does not zigzag".  A saw-tooth of foot distances comes back with a
    fraction of its curvature and its mean intact."""
    n = 64
    raw = np.array([20.0 + (4.0 if k % 2 else -4.0) for k in range(n)])
    s = np.full(n, 6.0)
    out = smooth_along(raw, s, law.tables.emit.design.bank_foot_smooth)

    def curvature(v):
        return float(np.abs(np.roll(v, -1) - 2.0 * v + np.roll(v, 1)).sum())

    assert curvature(out) < 0.2 * curvature(raw)
    assert float(out.mean()) == pytest.approx(float(raw.mean()), abs=0.05)
    # a weight of zero is the identity (the law value is the only knob)
    assert smooth_along(raw, s, 0.0) is raw


# ── (4) WHAT THE PATCH EMITS, AND WHO IGNORES IT ───────────────────────

def test_the_bank_is_emitted_as_a_role_less_closed_way(apron_map, law):  # noqa: F811
    """One closed way per foot ring, ``o4_feature=bank_foot`` and NOTHING
    else — no ``role``, no ``aeroway``, no ``shapeID``: it is the terrain,
    it carries no grade law, and both censuses skip it."""
    airport, pm, _r = apron_map
    banked, _surf, rep = _bank(airport, pm, law, 6.0)
    assert any(b.kind == BANK_KIND for b in banked.breaklines)
    foot = next(b for b in banked.breaklines if b.kind == BANK_KIND)
    assert foot.vertices[0] == foot.vertices[-1]         # closed
    text, _ways, _nodes = render_patch(banked, law)
    assert f"v='{BANK_FEATURE}'" in text
    body = [w for w in text.split("<way ") if BANK_FEATURE in w][0]
    assert "k='role'" not in body and "k='aeroway'" not in body
    assert "k='shapeID'" not in body
    # the v1 census's register knows it and never judges it as a surface
    import tools.check_grade as cg
    assert BANK_FEATURE in cg.ROLE_LESS_FEATURE_CLASSES
    assert BANK_FEATURE not in cg.HOST_CAP_FEATURE_CLASSES


def test_v2_verify_never_builds_a_shape_from_the_bank(apron_map, law):  # noqa: F811
    """Spec §9.2 A8: a ``bank_foot`` breakline matches neither branch of
    ``verify/frame.Patch.of``, so no v2 family ever prices it."""
    from auto_patch_v2.verify.frame import Patch
    airport, pm, _r = apron_map
    banked, surf, _rep = _bank(airport, pm, law, 6.0)
    before = Patch.of(surf, law, {})
    after = Patch.of(banked, law, {})
    assert len(after.shapes) == len(before.shapes)
    assert len(after.features) == len(before.features)


def test_the_bank_touches_neither_the_planar_map_nor_the_solve(apron_map, law):  # noqa: F811
    """Spec §9.2 A1: the bank is built AFTER the solve, from the solution
    — no face, no edge, no vertex, so no law row changes."""
    airport, pm, _r = apron_map
    n_faces, n_v = len(pm.faces), len(pm.vertices)
    banked, surf, _rep = _bank(airport, pm, law, 6.0)
    assert (len(pm.faces), len(pm.vertices)) == (n_faces, n_v)
    assert len(banked.faces) == len(surf.faces)
    assert coverage_polygon(pm) is not None


# ── THE PAD PLANE (09c) ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pad_map(law):                                           # noqa: F811
    """An apron on ground falling 3 % across it, with a 60 x 40 m pad
    welded into the middle of it."""
    class _Three:
        provenance = {"synthetic": "3 % cross slope"}

        def z(self, x, y):
            return 700.0 + 0.03 * y

        def bounds(self):
            return (-9000.0, -9000.0, 9000.0, 9000.0)

    airport, r = _airport(law, _Three(), ())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(r, -200.0, 120.0, 200.0, 320.0), (), None,
             "D", "airside", "apron", {}),
        Cell(2, "building", "pad1", _rect(r, -30.0, 190.0, 30.0, 230.0), (), None,
             None, "groundside", "building", {}),
    )
    from auto_patch_v2.planar.build import build
    cl = Classification(tuple(cells), (), {}, ())
    pm, _st = build(airport, cl, law)
    return airport, pm, r


def _pad_face(pm):
    return next(f for f in pm.faces.values() if f.ref == "pad1")


def _pad_plane(pm, z, fid):
    f = pm.faces[fid]
    ids = [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]
    ids = list(dict.fromkeys(ids))
    return plane_fit([pm.vertices[v].xy for v in ids], [z[v] for v in ids]), ids


def test_the_pad_is_no_longer_a_merged_flat_group(pad_map, law):  # noqa: F811
    """09c: the flatness is a TARGET (``[design] pad_flat``) and the 1 %
    tilt a HARD ceiling (``[design] hard_rulings``) — not one column."""
    _airport_, pm, _r = pad_map
    flats = padgen.pad_flats(pm, law, None)
    ceil = padgen.pad_slope_ceiling(pm, law, None)
    assert flats and not any(hasattr(r, "group") for r in flats)
    assert all(isinstance(r, Diff) and r.cap == 0.0 for r in flats)
    assert all(r.cap == law.tables.emit.within_shape.pad_slope_max for r in ceil)
    assert ruling_head(flats[0]) in pad_flat_rulings(law)
    assert ruling_head(ceil[0]) in hard_rulings(law)
    cs, counts, _w = generate(pm, law, _airport_)
    assert not cs.flats                                   # nothing merges a pad now
    assert counts["pad_flats"] > 0
    rep = DesignReport()
    base = assemble(pm, cs, law, rep)
    # a two-sided ``Diff`` enters the one-sided set as TWO rows
    assert base.pad_flat and len(base.pad_flat) == 2 * counts["pad_flats"]
    assert rep.hard_rows >= counts["pad_slope_ceiling"]


def test_a_pad_on_a_three_percent_apron_stays_flat_and_welds(pad_map, law):  # noqa: F811
    """09c: "targeting flat".  Nothing forces the pad off level, so it
    comes out one plane inside the elevation materiality — and it is
    welded: its rim vertices ARE the apron's (05t, identity, not a row)."""
    airport, pm, _r = pad_map
    fid = _pad_face(pm).id
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    (resid, tilt), ids = _pad_plane(pm, sol.z, fid)
    spread = max(sol.z[v] for v in ids) - min(sol.z[v] for v in ids)
    tol = law.tables.emit.materiality.elevation_m
    assert spread <= tol, (spread, resid, tilt)
    assert tilt <= law.tables.emit.within_shape.pad_slope_max
    # THE WELD (05t): the pad's rim vertices are shared with the apron's
    # face, so the gap is zero by identity — never a row that could open one
    apron = next(f for f in pm.faces.values() if f.ref == "apron1")
    shared = set(ids) & set(pm.ring_vertices(apron.ring)) | {
        v for h in apron.holes for v in pm.ring_vertices(h)} & set(ids)
    assert shared, "the pad welds into the apron it sits in"
    assert all(abs(sol.z[v] - sol.z[v]) < 1e-12 for v in shared)


def test_a_pad_whose_contacts_admit_no_flat_solution_tilts_within_one_percent(
        pad_map, law):                                      # noqa: F811
    """09c: "with up to 1 % allowance where no other solution exists".
    Two opposite rim vertices are PINNED 0.30 m apart over the pad's 60 m
    length — no flat plane satisfies both — so the pad tilts, and the hard
    ceiling holds the tilt under 1 %."""
    airport, pm, _r = pad_map
    fid = _pad_face(pm).id
    rim = list(dict.fromkeys(pm.ring_vertices(pm.faces[fid].ring)))
    xy = {v: pm.vertices[v].xy for v in rim}
    a, b = max(((p, q) for p in rim for q in rim),
               key=lambda pq: (xy[pq[0]][0] - xy[pq[1]][0]) ** 2
               + (xy[pq[0]][1] - xy[pq[1]][1]) ** 2)
    span = math.dist(xy[a], xy[b])
    cs, _c, _w = generate(pm, law, airport)
    z0 = 700.0 + 0.03 * 210.0
    src = padgen.pad_flats(pm, law, airport)[0].source
    cs2 = stack(list(cs.rows()) + [Pin(a, z0, src), Pin(b, z0 + 0.30, src)])
    sol, _rep = solve_design(pm, cs2, law)
    (resid, tilt), ids = _pad_plane(pm, sol.z, fid)
    spread = max(sol.z[v] for v in ids) - min(sol.z[v] for v in ids)
    tol = law.tables.emit.materiality.elevation_m
    cap = law.tables.emit.within_shape.pad_slope_max
    assert spread > tol, "the pins leave no flat solution"
    assert 0.30 / span <= cap                       # the fixture asks for < 1 %
    assert resid <= tol, (resid, "one PLANE, not a bowl")
    assert tilt <= cap + law.tables.emit.materiality.grade, tilt


# ── (1b) THE BANK FACE IS AUTHORED (owner RULINGS 2026-09-09f-1) ────────

def test_the_offsets_start_at_the_first_ring_then_run_every_spacing():
    """09f-1 as amended by 09i (1): the FIRST intermediate ring stands
    ``bank_first_ring_m`` out, then one every spacing, all strictly inside
    the bank.  A foot 18.2 m out gets levels at 3 and 13 m; a foot 59 m out
    gets six; a foot at the 5 m minimum now gets the 3 m ring (that band is
    where the mesh's squeeze reads); a foot AT the first ring gets none."""
    assert intermediate_offsets(18.2, 10.0, 3.0) == [3.0, 13.0]
    assert intermediate_offsets(59.0, 10.0, 3.0) == [
        3.0, 13.0, 23.0, 33.0, 43.0, 53.0]
    assert intermediate_offsets(5.0, 10.0, 3.0) == [3.0]
    assert intermediate_offsets(13.0, 10.0, 3.0) == [3.0]
    assert intermediate_offsets(3.0, 10.0, 3.0) == []


def test_a_six_metre_ring_authors_its_levels_at_three_and_thirteen_metres(apron_map, law):  # noqa: F811
    """THE 09i (1) TWIN: a 6 m ring with an 18.2 m foot gets levels at 3 m
    and 13 m of plan — the first at ``bank_first_ring_m``, then one every
    ``bank_ring_spacing_m`` — each z LINEAR between the ring's design z
    (706) and the foot's DEM z (700): 706 − 6 × 3/18.18 = 705.0 and
    706 − 6 × 13/18.18 = 701.7.  The chains carry the SAME ``bank_foot``
    register as the foot (no new consumer).

    RE-SCOPED for 09h (spec §11): the level ring is now
    ``cover.buffer(t) ∩ banked_region`` — valid by construction — so it no
    longer carries one vertex per foot node; on this mitred rectangle it is
    the four corners of the offset rectangle.  Its Z is unchanged: the same
    bank field, the same linear fraction."""
    airport, pm, _r = apron_map
    banked, _surf, rep = _bank(airport, pm, law, 6.0)
    d = law.tables.emit.design
    assert rep.face_rings >= 1 and rep.face_vertices > 0
    assert rep.face_rings_invalid == 0                   # 09h's own gate
    face = [b for b in banked.breaklines if b.kind == BANK_KIND and "@" in b.ref]
    lv1 = [b for b in face if b.ref.endswith("@1")]
    # EVERY level ring is CLOSED — the mesh needs a closed way to seed the
    # band (spec §10.5: open chains reverted the bank to the DEM, 306 %)
    assert len(lv1) == 1 and lv1[0].vertices[0] == lv1[0].vertices[-1]
    lv2 = [b for b in face if b.ref.endswith("@2")]
    assert len(lv2) == 1 and lv2[0].vertices[0] == lv2[0].vertices[-1]
    zof = {v.id: v.z for v in banked.vertices}
    foot_ids = {v for b in banked.breaklines if b.kind == BANK_KIND
                and "@" not in b.ref for v in b.vertices}
    # RE-SCOPED for RULINGS 2026-09-09j (``bank_ring_spacing_m`` 10 → 3 m):
    # the levels stand at first + k·spacing while INSIDE the perpendicular
    # bank (18.18 m on this rectangle); a level with no room (``cov.buffer(t)
    # ∩ banked`` = ``banked`` itself) is skipped.  (A mitred corner is the
    # SAME bank seen diagonally — 09f-1's per-vertex construction authored a
    # deeper level there because it measured the corner RAY.)
    import math as _m
    n_inside = 1 + _m.floor((18.18 - d.bank_first_ring_m) / d.bank_ring_spacing_m)
    assert 2 <= rep.face_levels <= n_inside
    assert not [b for b in face if b.ref.endswith(f"@{n_inside + 1}")]
    assert foot_ids
    bank_w = 6.0 / d.bank_slope
    for chain, t_out in ((lv1, d.bank_first_ring_m),
                         (lv2, d.bank_first_ring_m + d.bank_ring_spacing_m)):
        inner = [zof[v] for b in chain for v in b.vertices if v not in foot_ids]
        assert inner
        # every level vertex is strictly between the DEM and the design ring
        assert all(700.0 < z <= 706.0 for z in inner)
        assert min(inner) == pytest.approx(706.0 - 6.0 * (t_out / bank_w),
                                           abs=0.15)


def test_a_minimum_width_bank_authors_the_first_ring_only(apron_map, law):  # noqa: F811
    """09i (1) RE-SCOPES 09f-1's "a 5 m minimum bank has no room for a
    ring": the FIRST level ring stands at ``bank_first_ring_m`` (3 m), which
    is inside the minimum bank by law — that innermost band is exactly where
    the mesh's harmonic squeeze reads.  There is no second: 13 m is outside
    a 5 m bank."""
    airport, pm, _r = apron_map
    banked, _surf, rep = _bank(airport, pm, law, 1.0)
    assert rep.face_levels == 1 and rep.face_rings >= 1
    assert rep.face_rings_invalid == 0
    levels = [b for b in banked.breaklines
              if b.kind == BANK_KIND and "@" in b.ref]
    assert levels and all(b.ref.endswith("@1") for b in levels)
    zof = {v.id: v.z for v in banked.vertices}
    foot_ids = {v for b in banked.breaklines if b.kind == BANK_KIND
                and "@" not in b.ref for v in b.vertices}
    inner = [zof[v] for b in levels for v in b.vertices if v not in foot_ids]
    assert inner and all(700.0 <= z <= 701.0 for z in inner)
