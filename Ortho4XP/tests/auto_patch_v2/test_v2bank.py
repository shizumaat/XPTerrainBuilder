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

import collections
import math

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate, stack
from auto_patch_v2.constraints import pads as padgen
from auto_patch_v2.emit.bank import (BANK_KIND, BankReport, coverage_polygon,
                                     daylight_feet, smooth_along, with_bank)
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


def test_a_ring_one_metre_up_carries_no_bank(apron_map, law):  # noqa: F811
    """§37 (3) THE BANK IS EMITTED WHERE IT IS LOAD-BEARING (owner RULINGS
    2026-09-13q item 8), superseding 09e's reading of this case.

    1 m of fill would want a 3.0 m bank and the ``bank_min_width_m`` floor
    would give it 5.0 — but ``bank_materiality_m`` is exactly
    ``bank_min_width_m * bank_slope`` (1.65 m), so the whole
    minimum-width regime IS the regime with no earthwork in it.  The ring
    and the DEM meet inside the narrowest bank the law knows; nothing is
    emitted and the mesh's own interpolation carries the metre."""
    from auto_patch_v2.emit.bank import bank_materiality_m
    airport, pm, _r = apron_map
    banked, _surf, rep = _bank(airport, pm, law, 1.0)
    d = law.tables.emit.design
    assert 1.0 / d.bank_slope < d.bank_min_width_m       # the floor would bind
    assert bank_materiality_m(d) == pytest.approx(1.65)
    assert 1.0 < bank_materiality_m(d)                   # ... and it is immaterial
    assert rep.rings == 0 and rep.foot_vertices == 0, rep
    assert rep.stations > 0 and rep.immaterial == rep.stations, rep
    assert rep.bare_rings == 1, rep
    assert not [b for b in banked.breaklines if b.kind == BANK_KIND]


def test_the_load_bearing_floor_is_derived_never_typed(law):   # noqa: F811
    """§37 (3): ``bank_materiality_m`` has ONE derivation site and is not
    a typed law value — it is the drop a minimum-width bank carries."""
    from auto_patch_v2.emit import bank as B
    d = law.tables.emit.design
    assert B.bank_materiality_m(d) == d.bank_min_width_m * d.bank_slope
    assert not hasattr(d, "bank_materiality_m")


def test_material_runs_pads_each_run_and_keeps_a_whole_ring_closed():
    """§37 (3): the load-bearing runs of a cyclic ring, each padded by one
    station on each side so the chain fades out on the ground; an
    all-material ring stays the closed ring; a ring with nothing
    load-bearing carries no chain at all."""
    from auto_patch_v2.emit.bank import material_runs
    assert material_runs([True] * 5) == [[0, 1, 2, 3, 4]]
    assert material_runs([False] * 5) == []
    assert material_runs([False, True, True, False, False]) == [[0, 1, 2, 3]]
    # the run that WRAPS the ring's seam is one run, not two
    assert material_runs([True, False, False, False, True]) == [[3, 4, 0, 1]]
    # TWO runs one station apart are ONE chain: padding them separately
    # would emit the same ground twice on two sets of nodes (duplicate
    # constrained segments — 09t's Triangle hazard, measured as 3
    # duplicate foot coordinates at CYXY and 14 at LEMD before the fix)
    assert material_runs([True, False, True]) == [[0, 1, 2]]
    assert material_runs([True, False, True, False, False, False, False]) \
        == [[6, 0, 1, 2, 3]]
    # ... and no chain is ever shorter than the 3 nodes the adapter emits
    assert all(len(r) >= 3 for r in material_runs(
        [True, False, False, False, False, True, False, False]))


def test_a_long_foot_chord_is_split_at_the_law_and_lands_on_the_dem(law):  # noqa: F811
    """§37 (3): no emitted chord is longer than ``bank_chord_max_m`` and
    every split station is DEM-sampled (measured on the 1.0.324 KCLT
    products: 451 chords over 30 m, up to 5.6 m off the DEM mid-chord)."""
    from auto_patch_v2.emit.bank import split_chain
    d = law.tables.emit.design
    dem = _FlatDem()
    pts = [(0.0, 0.0), (100.0, 0.0)]
    out_p, out_z, added = split_chain(pts, [700.0, 700.0], dem,
                                      d.bank_chord_max_m, d.bank_split_tol_m,
                                      d.bank_min_width_m)
    assert added == 3 and len(out_p) == 5
    assert all(abs(z - 700.0) < 1e-9 for z in out_z)
    for a, b in zip(out_p, out_p[1:]):
        assert math.hypot(b[0] - a[0], b[1] - a[1]) <= d.bank_chord_max_m + 1e-9


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
    # RE-SCOPED (owner RULINGS 2026-09-10l/10y, merged 10ah; lane v2green):
    # ``[design] pad_flat_rulings`` names TWO heads now — the pad's flatness
    # target AND the SENIOR frontage LEVEL row — so ``Base.pad_flat`` carries
    # both.  The twin read ``2 x pad_flats`` (the pre-10l register) and went
    # red on 14 vs 12 at b38683d5.  DERIVED, not hard-coded: a two-sided
    # ``Diff`` enters the one-sided set as TWO rows, and each level row is
    # ALREADY one-sided (``constraints.pads._two_sided`` mints the equality
    # as its two halves, so the generator's own count is the row count).
    level = counts["pad_frontage_level"]
    # A PURE-HOLE PAD MINTS NO LEVEL ROW (owner RULINGS 2026-09-10ax (1)).
    # This fixture's pad sits WHOLLY inside the apron, so every one of its
    # four rim vertices is the apron's own (09-01g: one vertex, one value).
    # Under 10ax the row's FOLLOWERS are the pad's OWN vertices — a shared
    # contact is a pavement vertex and enters as a LEADER — so such a pad
    # has no degree of freedom of its own to govern: it is flush with the
    # apron's edge BY IDENTITY and needs no row.  Before 10ax the row
    # existed here with pavement followers, which is exactly how a pad's
    # mean moved the pavement +1.30 m at LEMD's T4S corner (10at).  The
    # positive case — a MIXED rim, and a pad fronting by PROXIMITY with no
    # shared vertex at all — is ``tests/auto_patch_v2/test_v2padprox.py``.
    assert level == 0, "a pure-hole pad is flush by identity"
    assert base.pad_flat
    assert len(base.pad_flat) == 2 * counts["pad_flats"] + level
    heads = collections.Counter(ruling_head(base.one[i][2]) for i in base.pad_flat)
    assert heads[padgen.FLAT_RULING] == 2 * counts["pad_flats"]
    assert heads[padgen.LEVEL_RULING] == level
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
    ceiling holds the tilt under 1 %.

    RE-SCOPED for the FRONTAGE LEVEL ROW (owner RULINGS 2026-09-10y, merged
    10ah; lane v2green).  The pad's residual from its own least-squares
    plane read 0.0000 before b38683d5 and 0.0249 m after it, and the
    INTERVENTIONAL arm below attributes every bit of that to 10y's level
    row, not to a bowl in the plate: with the ``pad_level`` rows dropped and
    nothing else changed the same solve puts the pad back on ONE plane
    inside the elevation materiality.

    The mechanism is the fixture's own over-determination, not a defect of
    the shipped design: this pad's rim is FOUR vertices and the two Pins
    take the diagonal, so every plane through them has the SAME mean
    (rotating about the pin axis moves the two free vertices in opposite
    directions).  10y's row states the pad's mean against its frontage's
    band value, so it asks for a mean no plane through those pins can
    have, and the solve trades ``pad_flat`` planarity against it at the
    same weight.  On a real pad the plate is many pairs against ONE mean
    row and the trade is ~1/n of this (LEMD, 10ah: ``pad_flat`` verify rows
    6 -> 7, DEFECTs 0).  ``frontage_near_miss`` is where the same row shows
    up as surface — see the sibling note in ``test_m3b``."""
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
    assert tilt <= cap + law.tables.emit.materiality.grade, tilt
    # THE NUMBER, and its attribution.  0.0249 m of plate residual, all of
    # it the 10y level row: the arm below is the identical solve with the
    # ``pad_level`` generator's rows removed and NOTHING else changed.
    assert resid <= 0.03, (resid, "the level row's trade, not a bowl")
    rows_no_level = [r for r in cs2.rows()
                     if r.source.generator != padgen.GEN_LEVEL]
    # RE-SCOPED (owner RULINGS 2026-09-10ax (1)): this fixture's pad is a
    # PURE HOLE in the apron, so it mints no level row at all now (see the
    # note in ``test_the_pad_is_no_longer_a_merged_flat_group``) and the
    # arm below is the SAME solve.  It still holds what it was written to
    # hold — one PLANE inside the 1 % ceiling under the two pins — and the
    # 0.0249 m plate residual it attributed to the level row is gone with
    # the row: ``resid`` above is now inside the same bar as ``resid_b``.
    assert len(rows_no_level) == len(list(cs2.rows()))
    sol_b, _rb = solve_design(pm, stack(rows_no_level), law)
    (resid_b, tilt_b), ids_b = _pad_plane(pm, sol_b.z, fid)
    assert resid_b <= tol, (resid_b, "one PLANE, not a bowl")
    assert tilt_b <= cap + law.tables.emit.materiality.grade, tilt_b
    assert max(sol_b.z[v] for v in ids_b) - min(sol_b.z[v] for v in ids_b) > tol


# ── (1b) THE LEVEL RINGS ARE DELETED (owner RULINGS 2026-09-09p (1) /
# 2026-09-09t): ONE foot ring per boundary, and the ENGINE blends the
# annulus (``O4_Mesh_Utils.bank_annulus_blend_values``) ────────────────

def test_a_six_metre_ring_emits_its_foot_and_no_level_ring(apron_map, law):  # noqa: F811
    """09t: the level rings are DELETED.  The 6 m ring that 09i/09j read at
    levels 3 m and 13 m now emits its FOOT ring and NOTHING between — no
    ``bank:N@LEVEL`` way exists any more — while the foot's own geometry
    (its z IS the DEM, its ring is CLOSED, its vertices are new) is
    untouched by the deletion."""
    airport, pm, _r = apron_map
    banked, surf, rep = _bank(airport, pm, law, 6.0)
    bank_bl = [b for b in banked.breaklines if b.kind == BANK_KIND]
    assert bank_bl, "the foot ring is still emitted"
    assert not [b for b in bank_bl if "@" in b.ref], \
        "a level ring survived the 09t deletion"
    assert not hasattr(rep, "face_rings")            # the statistic is gone
    zof = {v.id: v.z for v in banked.vertices}
    pre = {v.id for v in surf.vertices}
    for b in bank_bl:
        assert b.vertices[0] == b.vertices[-1]       # CLOSED (spec §10.5)
        assert all(v not in pre for v in b.vertices[:-1])
        assert all(abs(zof[v] - 700.0) < 1.0e-6 for v in b.vertices)
    assert "level" not in rep.line("TEST").lower()


# ── (1c) THE SHORE HAS NO BANK (owner RULINGS 2026-09-09z (3); spec §18)
# "Only set pavement node elevations, then the DEM should automatically
# grade into the water and blend with bathymetry data."  The daylight walk
# STOPS at the water line, the banked region is cut there, and nothing the
# patch emits stands in water. ─────────────────────────────────────────

class _ShoreDem(_FlatDem):
    """Level ground at 700 m with a CANAL beyond the apron's east edge —
    the production frame's water interface (``water_many`` /
    ``water_geometry``) and nothing more."""

    provenance = {"synthetic": "level ground with a canal"}

    #: the canal's west bank, in frame metres: 10 m off the apron
    #: coverage's east edge (x = 200), so an east ray meets water before
    #: the 6 m fill would daylight at 18 m
    SHORE_X = 210.0

    def water_many(self, xs, ys):
        xs = np.asarray(xs, float)
        wet = xs >= self.SHORE_X
        return wet, np.where(wet, 0.0, np.nan)

    def water_geometry(self, bounds=None):
        from shapely.geometry import box
        water = box(self.SHORE_X, -9000.0, 9000.0, 9000.0)
        if bounds is None:
            return water
        return water.intersection(box(*bounds))


@pytest.fixture(scope="module")
def shore_map(law):                                         # noqa: F811
    """The same single apron, with a canal 10 m off its east edge."""
    cells = (
        Cell(0, "apron", "apron1", _rect(_rot(90.0), -200.0, 120.0, 200.0, 320.0),
             (), None, "D", "airside", "apron", {}),
    )
    return _built(law, _ShoreDem(), cells)


def test_the_daylight_walk_stops_at_the_water_line(law):    # noqa: F811
    """09z (3): a ray whose station is WATER carries no earthwork beyond
    the shore — it is classified ``water`` and its foot never reaches the
    far bank; a ray already over water inside the minimum width carries
    NO foot at all (``d == 0``)."""
    from auto_patch_v2.emit.bank import FOOT_KINDS
    dem = _ShoreDem()
    d_law = law.tables.emit.design
    # four rays walking EAST from x = 300: the ground is level, so a dry
    # ray would run to the maximum width and never daylight
    pts = np.array([[202.0, 0.0], [200.0, 10.0], [206.0, 20.0], [-300.0, 0.0]])
    nrm = np.array([[1.0, 0.0]] * 4)
    z_ring = np.full(4, 706.0)
    d, kind = daylight_feet(
        z_ring, pts, nrm, dem, float(d_law.bank_slope),
        float(d_law.bank_min_width_m), float(d_law.bank_max_width_m),
        float(d_law.bank_sample_m), float(d_law.bank_daylight_tol_m))
    water = FOOT_KINDS.index("water")
    assert kind[0] == water and kind[1] == water
    assert (pts[0, 0] + d[0]) <= _ShoreDem.SHORE_X + 1.0e-9, \
        "a foot landed beyond the water line"
    assert kind[2] == water and d[2] == 0.0, \
        "water inside the minimum width leaves NO foot (09z (3))"
    assert kind[3] != water and d[3] > d_law.bank_min_width_m, \
        "the ray walking away from the water is untouched"


def test_no_bank_vertex_and_no_annulus_stands_in_water(shore_map, law):  # noqa: F811
    """09z (3): no foot node lands in water and the banked region — the
    annulus the mesh blends — is cut at the water line.  The patch sets
    pavement; the DEM grades into the canal on its own."""
    from shapely.geometry import Point
    airport, pm, _r = shore_map
    banked, _surf, rep = _bank(airport, pm, law, 6.0)
    water = _ShoreDem().water_geometry()
    bank_bl = [b for b in banked.breaklines if b.kind == BANK_KIND]
    assert bank_bl and rep.at_water > 0, "the fixture's east rays meet water"
    to_xy = airport.frame.transformers()[0]
    zof = {v.id: v for v in banked.vertices}
    for b in bank_bl:
        assert b.vertices[0] == b.vertices[-1], "the ring is still CLOSED"
        for v in b.vertices:
            lat, lon = zof[v].ll
            x, y = to_xy(lon, lat)
            assert not water.buffer(-0.01).contains(Point(x, y)), \
                f"a bank vertex stands in water at {lat:.6f},{lon:.6f}"
    cov = coverage_polygon(pm)
    foot = _foot_polygon(banked, bank_bl, airport)
    annulus = foot.difference(cov)
    assert annulus.intersection(water.buffer(-0.01)).area <= 1.0e-6, \
        "the annulus covers water"


def _foot_polygon(banked, bank_bl, airport):
    """The banked region as the emitted foot rings describe it."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    to_xy = airport.frame.transformers()[0]
    xy = {v.id: to_xy(v.ll[1], v.ll[0]) for v in banked.vertices}
    polys = []
    for b in bank_bl:
        ring = [xy[v] for v in b.vertices[:-1]]
        if len(ring) < 3:
            continue
        p = Polygon(ring)
        polys.append(p if p.is_valid else p.buffer(0))
    return unary_union(polys)


def test_a_dem_with_no_water_witness_banks_exactly_as_before(apron_map, law):  # noqa: F811
    """S15: the witness is read through ``getattr`` — a sampler without
    one claims NO water, so every synthetic fixture and the authored
    ``DemSampler`` bank bit-for-bit what they banked before 09z (3)."""
    airport, pm, _r = apron_map
    banked, _surf, rep = _bank(airport, pm, law, 6.0)
    assert rep.at_water == 0
    assert rep.foot_vertices > 0 and rep.rings >= 1


# ── §38 (3) NO BANK ALONG A TILE SEAM (owner RULINGS 2026-09-13ah /
# 13an; spec design-surface-spec §38 (3)) ───────────────────────────────
# 13am measured that the 2 x ``seam.half_width_m`` slit between two tile
# pieces was closed ONLY because ``emit.design.bank_min_width_m`` (5.0,
# emit.toml:445) happened to EQUAL ``emit.seam.half_width_m`` (5.0,
# emit.toml:86) — two independently typed constants.  13an measured what
# the near-miss costs: the two collars met 1.6 mm apart, a bank foot chain
# followed the crack 0.0237 m off the meridian, and Triangle4XP split that
# one 5.32 m segment 16,298 times against the unsplittable tile border.
# The band is now unioned into the coverage EXPLICITLY and the derived
# bank pieces are cut by it, so neither the closure nor the keep-out
# depends on the two constants agreeing.

def _with_seam_band(pm, y0: float, y1: float, x0: float, x1: float):
    """``pm`` with one declared seam band — the rectangle
    ``[x0, x1] x [y0, y1]`` in frame metres (``PlanarMap.seam_band_rings``
    is what ``planar/build`` writes from ``planar/overlay.seam_bands``)."""
    import dataclasses as _dc
    ring = ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))
    return _dc.replace(pm, seam_band_rings=(ring,))


def _law_with(law, *, half_width_m=None, bank_min_width_m=None):  # noqa: F811
    """``law`` with one emit constant changed, IN MEMORY (the loader's own
    refusal is the twin below; this one reads the EMITTER)."""
    import dataclasses as _dc
    emit = law.tables.emit
    if half_width_m is not None:
        emit = _dc.replace(emit, seam=_dc.replace(emit.seam,
                                                  half_width_m=half_width_m))
    if bank_min_width_m is not None:
        emit = _dc.replace(emit, design=_dc.replace(
            emit.design, bank_min_width_m=bank_min_width_m))
    return _dc.replace(law, tables=_dc.replace(law.tables, emit=emit))


@pytest.mark.parametrize("half_m", [5.0, 3.0, 1.0])
def test_the_seam_slit_needs_no_constant_coincidence(apron_map, law, half_m):  # noqa: F811
    """The band is cut out of the coverage and closed again by the LAW, at
    three different ``seam.half_width_m`` values against one unchanged
    ``bank_min_width_m`` of 5.0: no bank foot node lands inside the band at
    any of them.  With the closure left to the collar, a half width the
    collar does not reach re-opens the slit and a 1:3 foot ring appears
    down the middle of the runway (13am (2))."""
    airport, pm, _r = apron_map
    l2 = _law_with(law, half_width_m=half_m)
    x0, y0, x1, y1 = coverage_polygon(pm).bounds
    yc = 0.5 * (y0 + y1)                       # a band THROUGH the coverage
    pm2 = _with_seam_band(pm, yc - half_m, yc + half_m,
                          x0 - 500.0, x1 + 500.0)
    from auto_patch_v2.solve.api import Solution, Status
    z = {v: 706.0 for v in pm2.vertices}
    sol = Solution(z, Status.OPTIMAL, None, 0, 0.0, "fixture")
    surf = graded_surface(pm2, l2, sol, airport.frame.origin,
                          airport.frame.crs, {})
    rep = BankReport()
    banked = with_bank(surf, pm2, l2, airport, rep)
    assert rep.seam_bands == 1, (
        "the emitter did not see the declared seam band — the cut and the "
        "coverage union are both no-ops and the twin proves nothing")
    to_xy = airport.frame.transformers()[0]
    xy = {v.id: to_xy(v.ll[1], v.ll[0]) for v in banked.vertices}
    # inside the band AND over the coverage's own span — the band's stubs
    # BEYOND the airport are where the patch boundary legitimately turns
    # the corner, and the ring the ruling forbids is the one down the
    # MIDDLE of the runway
    inside = [v for b in banked.breaklines if b.kind == BANK_KIND
              for v in b.vertices
              if abs(xy[v][1] - yc) <= half_m and x0 < xy[v][0] < x1]
    assert not inside, (
        f"{len(inside)} bank foot node(s) inside a {half_m} m half-width "
        f"seam band while bank_min_width_m stayed "
        f"{law.tables.emit.design.bank_min_width_m} — the slit closure is "
        f"still riding on the two constants agreeing (RULINGS 13am (2))")


def test_the_law_refuses_a_collar_that_cannot_reach_the_band(law):  # noqa: F811
    """§38 (3)/13an (e): the relation between the two constants is asserted
    at LAW LOAD, by name, instead of being a silent coincidence — a collar
    narrower than the band's half width is refused before any build."""
    from auto_patch_v2.law.model import LawError, _check_cross_refs
    bad = _law_with(law, half_width_m=9.0, bank_min_width_m=5.0)
    with pytest.raises(LawError, match="bank_min_width_m"):
        _check_cross_refs(bad.tables)
