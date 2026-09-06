"""Twins for RULINGS 2026-09-05ae (lane v2fix288; spec
``relaxation-without-certificate-spec.md`` §10):

1. CHORDS STAY INSIDE THEIR FACE — an apron with a building hole: the
   spine / frontage chords across the hole are absent from the
   generator (``chords_outside_face`` counted), the ring edges and the
   inside chords remain; the v2 verify reader prices the same
   population; the v1 oracle, reading sidecar ``face_holes``, prices no
   chord across the hole either; a junction triangle with an edge
   leaving its face is not a plane row and its edges are no mesh edges.
2. THE RELAXATION'S SHAPE — ``[relaxation] max_over_cap_factor``: a
   short edge never carries a metre (``slack_bound``), the hangar row's
   relaxed rows all hold ≤ factor × cap, the certificate states the
   worst factor.
3. ONE STRIP POPULATION — the generator's ``strip_longitudinal`` pairs
   and the reader's are the same set on a synthetic strip beside a
   runway end (both read ``strip_longitudinal_pairs`` /
   ``pavement_ring_vertices``); a hole ring's vertex is not pavement.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints import junction_mesh, strips
from auto_patch_v2.constraints.geometry import chords_covered, face_cover
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law, tables
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff, Linear, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import face_holes_ll, face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve import relax, variance
from auto_patch_v2.solve.api import Solution
from auto_patch_v2.solve.tiers import solve_law_ordered
from auto_patch_v2.verify import strips as vstrips
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import within_shape

ROOT = Path(__file__).resolve().parents[2]


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _FlatDem:
    provenance = {"synthetic": "flat 700 m"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _HangarDem:
    """1.5 % along the runway (x), 10 % across the apron (y beyond 40)."""

    provenance = {"synthetic": "1.5 % in x, 10 % in y across the hangar row"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.015 * (x + 600.0) + 0.10 * max(0.0, y - 40.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, cells, cuts, dem, pins=(700.0, 700.0)):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, pins[0], "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, pins[1], "fixture"))
    runways = [Runway("09/27", 45.0, 1, ends, 3, "D")]
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, tuple(runways), (), (), {},
                      (), (), (), (), (), (), (), pack, dem, law.ruleset_key)
    pm, _stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    return airport, pm


HOLE = _rect(-40, 95, 40, 115)


@pytest.fixture(scope="module")
def holed_apron(law):
    """A stub at x = 0 leads to an apron (−200..200 × 80..130) with a
    BUILDING standing inside it (the hole −40..40 × 95..115): the owner's
    HECA site in miniature.  The apron is 50 m deep so a BODY chord from
    the mouth edge to the far edge (50 m, inside the 60 m body gate)
    crosses the hole — a chord every reader prices."""
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubA", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "apron", "apron1", _rect(-200, 80, 200, 130), (HOLE,), None, None,
             "airside", "apron", {}),
        Cell(3, "building", "hangar", HOLE, (), None, None, "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "stubA", ((0.0, 0.0), (0.0, 80.0)))]
    return _airport(law, cells, cuts, _FlatDem())


def _vid(pm, x, y):
    for vid, v in pm.vertices.items():
        if math.hypot(v.xy[0] - x, v.xy[1] - y) < 0.6:
            return vid
    raise AssertionError(f"no vertex at ({x}, {y})")


def _apron_face(pm):
    return next(f for f in pm.faces.values() if f.role == "apron")


# ── 1. chords stay inside their face ────────────────────────────────────

def test_apron_chords_across_the_hole_are_no_rows(holed_apron, law):
    airport, pm = holed_apron
    f = _apron_face(pm)
    assert f.holes, "the building must be a hole of the apron face"
    cs, counts, _w = generate(pm, law, airport, only={"apron_within_shape"})
    pairs = {(min(r.a, r.b), max(r.a, r.b)) for r in cs.diffs if r.source.generator == "apron"}
    mouth = _vid(pm, 0, 80)                     # the stub centreline's spine vertex
    far, mid_e, far_e = _vid(pm, 0, 130), _vid(pm, 50, 130), _vid(pm, 150, 130)
    s50, n50 = _vid(pm, 50, 80), _vid(pm, 50, 130)
    ne, nw = _vid(pm, 40, 115), _vid(pm, -40, 115)
    se, sw = _vid(pm, 40, 95), _vid(pm, -40, 95)
    key = lambda a, b: (min(a, b), max(a, b))
    # ABSENT: the chords from the mouth THROUGH the hole (to the far edge
    # at x = 0 — 50 m, a body chord too — and x = 50), the hole's diagonal
    # (a frontage chord between two pad vertices, priced on the hole ring)
    assert key(mouth, far) not in pairs and key(mouth, mid_e) not in pairs
    assert key(sw, ne) not in pairs and key(se, nw) not in pairs
    # PRESENT: the spine chord that passes BESIDE the hole, the 50 m body
    # chord beside it, the hole's own edges (ring edges of the apron).
    # (Outer-ring ↔ hole-ring pairs are not a population of this
    # generator — each ring is priced on its own.)
    assert key(mouth, far_e) in pairs and key(s50, n50) in pairs
    assert key(sw, se) in pairs and key(se, ne) in pairs
    assert counts["apron_within_shape.chords_outside_face"] >= 4
    # EVERY row's chord lies inside the face (the rule, universally)
    vw = view(pm, law)
    cover = face_cover(vw.face_ring_xy(f.id), [[vw.xy[v] for v in h] for h in vw.holes[f.id]],
                       tables.snap_margin_m(law))
    segs = [(vw.xy[a], vw.xy[b]) for a, b in pairs]
    assert all(chords_covered(cover, segs))
    # and the exact face (no tolerance) refuses the dropped ones
    from shapely.geometry import LineString, Polygon
    exact = Polygon(vw.face_ring_xy(f.id), [[vw.xy[v] for v in h] for h in vw.holes[f.id]])
    assert not exact.covers(LineString([vw.xy[mouth], vw.xy[far]]))
    assert exact.covers(LineString([vw.xy[mouth], vw.xy[far_e]]))
    assert exact.covers(LineString([vw.xy[s50], vw.xy[n50]]))


def _steep_solution(pm):
    """A surface steep enough that EVERY priced pair is over cap, and
    that tells the two 50 m vertical chords apart by their rise: the
    chord THROUGH the hole (x = 0) rises 1.5 m, the one beside it
    (x = 50) 4.0 m."""
    z = [700.0 + 0.05 * v.xy[0] + 0.03 * v.xy[1] + 0.001 * v.xy[0] * v.xy[1]
         for _vid, v in sorted(pm.vertices.items())]
    return Solution(tuple(z), Status.OPTIMAL, None)


CROSSING = (50.0, 1.5)      # (distance, rise) of the chord through the hole
BESIDE = (50.0, 4.0)        # the chord beside it


def _signatures(rows, dist, rise):
    return {(round(d, 1), round(r, 1)) for d, r in zip(dist, rise)}


def test_verify_reader_prices_the_same_apron_population(holed_apron, law):
    airport, pm = holed_apron
    sol = _steep_solution(pm)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    assert pub["face_holes"] == face_holes_ll(pm) and len(pub["face_holes"]) >= 1
    p = Patch.of(surf, law, pub)
    within, _x = within_shape(p)
    apron_rows = [r for r in within if r["roles"] == "apron|apron"]
    assert apron_rows, "a steep plane must fire the apron rows"
    sh = next(s for s in p.shapes if s.role == "apron")
    holes = [f.xy for f in p.features if f.feature == "gap_interior_ring" and f.host == sh.key]
    assert len(holes) == 1
    from shapely.geometry import LineString, Polygon
    exact = Polygon(sh.xy, holes)
    tol = tables.snap_margin_m(law)
    for r in apron_rows:
        a, b = r["site_m"]
        assert exact.buffer(tol).covers(LineString([a, b])), r
    # the 50 m body chord through the hole is no row; the one beside it is
    sig = _signatures(apron_rows, [r["distance_m"] for r in apron_rows],
                      [r["magnitude_m"] for r in apron_rows])
    assert CROSSING not in sig and BESIDE in sig, sorted(sig)


def test_oracle_reads_face_holes_and_prices_no_chord_across_the_hole(holed_apron, law, tmp_path):
    airport, pm = holed_apron
    sol = _steep_solution(pm)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    sys.path.insert(0, str(ROOT / "tools" / "harness"))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    assert cg.SIDECAR_LAW_KEYS["face_holes"] == "face_holes_ll"
    ctx = cg.law_context_from_sidecar(paths.patch)
    assert ctx["face_holes_ll"], "the sidecar must carry the apron's hole"
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    rows = [v for v in fam.get("within_shape", []) if v.way_a.role == "apron"]
    assert rows, "the oracle must price the apron under a steep plane"
    sig = _signatures(rows, [v.distance_m for v in rows], [v.de_m for v in rows])
    assert CROSSING not in sig and BESIDE in sig, sorted(sig)
    # the same patch read WITHOUT the key prices the chord across the hole
    # (the pre-05ae reading): the key is what the oracle's rule rides on
    fam0: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam0, quiet=True, top_n=0,
                           face_holes_ll=None)
    rows0 = [v for v in fam0.get("within_shape", []) if v.way_a.role == "apron"]
    sig0 = _signatures(rows0, [v.distance_m for v in rows0], [v.de_m for v in rows0])
    assert CROSSING in sig0 and BESIDE in sig0, sorted(sig0)


NOTCHED = ((0, 0), (100, 0), (100, 60), (64.1, 60), (59.3, 13.8), (54.4, 60), (0, 60))
NOTCH_HOLE = ((47.7, 30.0), (53.2, 30.0), (53.2, 43.0), (47.7, 43.0))


def test_junction_triangle_leaving_its_face_is_not_a_row(law):
    """A junction with a deep notch and a hole: the Delaunay mesh holds
    triangles whose centroid is inside the face but whose edge crosses
    the notch or the hole — those are not plane rows and their edges no
    mesh edges (RULINGS 2026-09-05ae(1))."""
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubA", _rect(-11.5, 22.5, 11.5, 300), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "junction", "jct", tuple((x + 20.0, y + 300.0) for x, y in NOTCHED),
             (tuple((x + 20.0, y + 300.0) for x, y in NOTCH_HOLE),), None, "D",
             "airside", "junction", {}),
        Cell(3, "building", "box", tuple((x + 20.0, y + 300.0) for x, y in NOTCH_HOLE),
             (), None, None, "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "stubA", ((0.0, 0.0), (0.0, 300.0)))]
    airport, pm = _airport(law, cells, cuts, _FlatDem())
    vw = view(pm, law)
    f = next(x for x in pm.faces.values() if x.role == "junction")
    tris = junction_mesh.face_triangles(vw, f.id)
    assert tris, "the notched junction must still carry a mesh"
    cover = face_cover(vw.face_ring_xy(f.id), [[vw.xy[v] for v in h] for h in vw.holes[f.id]],
                       tables.snap_margin_m(law))
    edges = junction_mesh.face_mesh_edges(vw, f.id, tris)
    assert all(chords_covered(cover, [(vw.xy[a], vw.xy[b]) for a, b in sorted(edges)]))
    # the rule bit: the unfiltered Delaunay (centroid inside) has a
    # triangle whose edge leaves the face
    from shapely.geometry import LineString, Polygon
    from shapely.ops import triangulate
    poly = Polygon(vw.face_ring_xy(f.id), [[vw.xy[v] for v in h] for h in vw.holes[f.id]])
    raw = [t for t in triangulate(poly) if poly.contains(t.centroid)]
    leaving = [t for t in raw if any(
        not poly.buffer(tables.snap_margin_m(law)).covers(LineString(seg))
        for seg in zip(list(t.exterior.coords)[:-1], list(t.exterior.coords)[1:]))]
    assert leaving and len(tris) < len(raw)
    # and the sidecar's mesh_edges are the filtered set
    published = junction_mesh.mesh_edges_ll(pm, law)
    assert len(published) == len({e for e in edges})


# ── 2. the relaxation's shape ───────────────────────────────────────────

def _relaxed(kind, row):
    return relax.Relaxed(0, row, kind, 0, None, getattr(row, "d", 1.0))


def test_slack_bound_never_lets_a_short_edge_carry_a_metre(law):
    src = Source("apron", "common.roles.apron ring edge (2026-08-21b)", ())
    factor = law.tables.emit.relaxation.max_over_cap_factor
    assert factor == 2.0
    short = Diff(0, 1, 0.01, 2.55, src)              # the HECA edge that carried 1.33 m
    g = variance.slack_bound(_relaxed("diff", short), factor)
    assert g == pytest.approx((factor - 1.0) * 0.01)
    assert g * short.d == pytest.approx(0.0255, abs=1e-9)       # 0.03 m, never 1.33 m
    lin = Linear(((0, 1.0), (1, -1.0)), -0.015 * 20.0 - 0.1, 0.015 * 20.0 + 0.1, src)
    s = variance.slack_bound(_relaxed("linear", lin), factor)
    assert s == pytest.approx((factor - 1.0) * (0.015 * 20.0 + 0.1))
    tie = Linear(((0, 1.0), (1, -1.0)), 0.0, 0.0, src)   # a weld / plane tie: never opens
    assert variance.slack_bound(_relaxed("linear", tie), factor) == 0.0
    assert variance.slack_bound(_relaxed("diff", short), None) == math.inf
    assert variance.slack_bound(_relaxed("pad", short), factor) == math.inf


@pytest.fixture(scope="module")
def hangar(law):
    """The hangar row of ``test_relax`` (hard-infeasible; the last resort runs)."""
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubW", _rect(-161.5, 22.5, -138.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "stub", "stubE", _rect(138.5, 22.5, 161.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "hangar_apron", _rect(-200, 80, 200, 120), (), None, None,
             "airside", "apron", {}),
        Cell(4, "building", "hangar1", _rect(-190, 120, -70, 170), (), None, None,
             "airside", "pad", {}),
        Cell(5, "building", "hangar2", _rect(-60, 120, 60, 170), (), None, None,
             "airside", "pad", {}),
        Cell(6, "building", "hangar3", _rect(70, 120, 190, 170), (), None, None,
             "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "stubW", ((-150.0, 0.0), (-150.0, 100.0))),
            CutLine("taxi_centerline", "stubE", ((150.0, 0.0), (150.0, 100.0)))]
    airport, pm = _airport(law, cells, cuts, _HangarDem(), pins=(700.0, 718.0))
    cs, _c, _w = generate(pm, law, airport)
    return airport, pm, cs


def test_relaxed_rows_hold_the_over_cap_factor(hangar, law):
    airport, pm, cs = hangar
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.OPTIMAL and rep.mode == "relaxed"
    rl = rep.relaxation
    factor = law.tables.emit.relaxation.max_over_cap_factor
    tol = law.tables.emit.materiality.grade
    cert = rl["certificate"]
    assert cert["ok"] and cert["max_over_cap_factor"] == factor
    assert 1.0 < cert["over_cap_factor_max_seen"] <= factor + tol
    for r in rl["rows"]:
        if r["kind"] == "diff":
            assert r["cap_after"] <= factor * r["cap"] + tol, r
            assert r["slack_m"] <= (factor - 1.0) * r["cap"] * r["distance_m"] + 1e-6, r
    assert "worst over-cap factor" in rl["line"]
    # the spread twin's bound restated with the factor: the largest carrier
    # is at most (factor − 1) × cap × its own chord, so no row is a cliff
    sm = rl["stats_m"]
    assert sm["max"] <= (factor - 1.0) * max(r["cap"] * r.get("distance_m", 0.0)
                                             for r in rl["rows"] if r["kind"] == "diff") + 1e-6


# ── 3. one strip population ────────────────────────────────────────────

def test_strip_population_is_one_helper_on_both_sides(holed_apron, law):
    airport, pm = holed_apron
    vw = view(pm, law)
    strip_faces = vw.faces_of_role(("graded_strip",))
    assert strip_faces, "the runway's zone-2 strips must exist"
    rows = strips.strip_longitudinal(pm, law, airport)
    gen = {tuple(sorted(v for v, _c in r.terms)) for r in rows}
    sol = _steep_solution(pm)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    p = Patch.of(surf, law, {})
    pav = vstrips._pavement_ids(p)
    reader = set()
    for rings, unit, code, L, letter, _a, _b in vstrips.groups(p):
        for sh in vstrips._strips(p):
            for i, j, _ds in strips.strip_longitudinal_pairs(sh.ids, sh.xy, unit, rings[0], pav):
                reader.add(tuple(sorted((sh.ids[i], sh.ids[j]))))
    assert gen == reader and gen
    # the reader's violators under the steep plane are all generator pairs
    for r in vstrips.strip_longitudinal(p):
        a, b = r["site_m"]
        ids = {vid for vid, xy in p.xy.items() if math.hypot(xy[0] - a[0], xy[1] - a[1]) < 0.01
               or math.hypot(xy[0] - b[0], xy[1] - b[1]) < 0.01}
        assert tuple(sorted(ids)) in gen
    # the pavement population: outer rings of capped faces, never a hole ring
    hole_v = {v for f in pm.faces.values() for h in f.holes for v in pm.ring_vertices(h)}
    outer_v = {v for f in pm.faces.values() for v in pm.ring_vertices(f.ring)}
    pav_gen = strips.pavement_ring_vertices((vw.caps[fid], vw.rings[fid]) for fid in pm.faces)
    assert pav_gen == pav
    assert not (hole_v - outer_v) & pav_gen
