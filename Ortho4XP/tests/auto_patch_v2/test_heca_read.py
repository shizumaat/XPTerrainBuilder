"""The HECA-read twins (lane v2heca3, RULINGS 2026-09-06b; spec
``heca-read-20260906-spec.md`` §2–§4): the runway vertical curve is
hard, the graded strip is tied to the runway edge, a shared-anchor
family seats as one only for the members that agree.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest

from auto_patch_v2.constraints import GENERATORS, generate, roads, runway_profile, zones
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.solve.tiers import row_tier
from auto_patch_v2.solve.why import family_of
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import DEFECT_KEYS
from auto_patch_v2.verify.runway import FAMILY_VERTICAL_CURVE
from auto_patch_v2.verify.strips import FAMILY_STRIP_TRANSVERSE
from tests.auto_patch_v2.test_crown import build_diagonal


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def diagonal(law):
    return build_diagonal(law)


@pytest.fixture(scope="module")
def solved(diagonal, law):
    airport, pm, _ = diagonal
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    return cs, sol


def _census(diagonal, law, sol):
    airport, pm, _ = diagonal
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    return census(surf, law, pub, roads.road_law_caps(pm, law))


def _rows_hold(rows, z) -> bool:
    for r in rows:
        v = sum(c * z[i] for i, c in r.terms)
        if (r.lo is not None and v < r.lo - 1e-9) or (r.hi is not None and v > r.hi + 1e-9):
            return False
    return True


# ── law 1: the vertical curve ────────────────────────────────────────────

def test_curve_bound_is_the_tables_min_of_k_and_max_change(law):
    for key in ("icao", "faa"):
        lw = Law(tables=law.tables, ruleset_key=key)
        rs = lw.ruleset.runway
        unit = lw.tables.common.vertical_curve_k_grade_unit
        for cn, cl in ((1, "A"), (3, "D"), (4, "F")):
            k = rs.vertical_curve_k_m.value(cn, cl)
            mgc = rs.max_grade_change.value(cn, cl)
            short = T.runway_vertical_curve_bound(lw, 12.0, cn, cl)
            expect = min(mgc, 12.0 / k * unit)
            if rs.vertical_curve_min_change is not None:
                # FAA AAC A/B: under this change no curve is needed
                expect = max(expect, rs.vertical_curve_min_change.value(cn, cl) or 0.0)
            assert short == pytest.approx(expect)
            # a long spacing is capped by max_grade_change itself
            assert T.runway_vertical_curve_bound(lw, 1e6, cn, cl) == pytest.approx(mgc)
            assert short <= mgc
        if rs.vertical_curve_min_change is not None:
            mc = rs.vertical_curve_min_change.value(1, "A")
            if mc:
                assert T.runway_vertical_curve_bound(lw, 1.0, 1, "A") == pytest.approx(mc)


def test_curve_rows_are_hard_three_term_runway_tier_rows(diagonal, law):
    airport, pm, _ = diagonal
    rows = runway_profile.runway_vertical_curve(pm, law, airport)
    assert rows and all(isinstance(r, Linear) and r.soft is None and len(r.terms) == 3
                        and r.lo == -r.hi for r in rows)
    vw = view(pm, law)
    rw = airport.runways[0]
    chains = runway_profile.ridge_chains(vw)[rw.id]
    a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
    L = rw.length_m
    st = runway_profile.curve_stations(
        vw.xy, chains,
        lambda v: ((vw.xy[v][0] - a_xy[0]) * (b_xy[0] - a_xy[0])
                   + (vw.xy[v][1] - a_xy[1]) * (b_xy[1] - a_xy[1])) / L,
        law.tables.emit.identity.min_distinct_spacing_m)
    assert len(rows) == len(st) - 2                # one per interior station
    tt = T.tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    assert all(row_tier(pm, r, tier_of, len(tt) - 1) == 0 for r in rows)
    assert {family_of(r) for r in rows} == {"runway_vertical_curve"}
    names = [n for n, _ in GENERATORS]
    assert names.index("runway_vertical_curve") == names.index("runway_transverse") + 1


def test_zigzag_refused_k_curve_passes(diagonal, law, solved):
    """§2 twin: a 1.5 % up / 1.5 % down zigzag at one station breaks the
    rows; a parabola at K's own rate passes."""
    airport, pm, _ = diagonal
    rows = runway_profile.runway_vertical_curve(pm, law, airport)
    _cs, sol = solved
    z = list(sol.z)
    assert _rows_hold(rows, z)
    rw = airport.runways[0]
    cap = law.ruleset.runway.longitudinal.value(rw.code_number, rw.code_letter)
    # zigzag: every station gets ±cap × distance from the middle station
    r0 = rows[len(rows) // 2]
    mid = r0.terms[1][0]
    vw = view(pm, law)
    z2 = [z[v] + cap * vw.dist(mid, v) if v < len(z) else z[v] for v in range(len(z))]
    assert not _rows_hold(rows, z2)
    # the K-curve: z = a·s² with a = unit / (2K) changes grade by exactly
    # spacing / K per station (the bound, to rounding); at half that rate
    # the curve passes with margin, at twice it is refused
    k = law.ruleset.runway.vertical_curve_k_m.value(rw.code_number, rw.code_letter)
    unit = law.tables.common.vertical_curve_k_grade_unit
    a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
    ux, uy = (b_xy[0] - a_xy[0]) / rw.length_m, (b_xy[1] - a_xy[1]) / rw.length_m

    def parabola(a):
        z3 = list(z)
        for v in range(len(z)):
            s = (vw.xy[v][0] - a_xy[0]) * ux + (vw.xy[v][1] - a_xy[1]) * uy
            z3[v] = a * s * s
        return z3
    assert _rows_hold(rows, parabola(0.5 * unit / (2.0 * k)))
    assert not _rows_hold(rows, parabola(2.0 * unit / (2.0 * k)))


def test_reader_reads_the_same_law_as_a_defect(diagonal, law, solved):
    _cs, sol = solved
    rows = _census(diagonal, law, sol)
    assert FAMILY_VERTICAL_CURVE in DEFECT_KEYS
    assert rows[FAMILY_VERTICAL_CURVE] == []
    airport, pm, _ = diagonal
    vw = view(pm, law)
    rw = airport.runways[0]
    chain = max(runway_profile.ridge_chains(vw)[rw.id], key=len)
    mid = chain[len(chain) // 2]
    cap = law.ruleset.runway.longitudinal.value(rw.code_number, rw.code_letter)
    z2 = list(sol.z)
    for v in chain:
        z2[v] += cap * vw.dist(mid, v)          # the zigzag on the ridge
    rows2 = _census(diagonal, law, _dc.replace(sol, z=tuple(z2)))
    got = rows2[FAMILY_VERTICAL_CURVE]
    assert got and all(r["reading"] == "vertical_curve" for r in got)
    assert max(r["grade_pct"] for r in got) >= 100 * cap


# ── law 2: the strip tie ─────────────────────────────────────────────────

def test_strip_bound_is_the_zone_tables_transverse_cap(law):
    ag = law.tables.zones.adjacent_ground
    d = 40.0
    bmax = ag.runway.band_max_down.value(4, None)
    expect = ag.lip_max_down * ag.lip_width_m + bmax * (d - ag.lip_width_m)
    assert T.strip_transverse_bound(law, d, 4, "E") == pytest.approx(expect)
    assert T.strip_transverse_bound(law, d, 4, "E") == pytest.approx(
        -T.zone_bounds(law, "runway", d, 4, "E")[0])
    half = T.zone2_half_width_m(law, "runway", 4, "E")
    assert T.strip_transverse_bound(law, half + 1.0, 4, "E") is None


def test_strip_tie_rows_bind_strip_vertices_in_the_strip_tier(diagonal, law):
    airport, pm, _ = diagonal
    rows = zones.strip_transverse(pm, law, airport)
    # TWO-WAY since RULINGS 2026-09-06q (2): ``lo`` is ``-hi`` wherever
    # ``zone_bands`` does not already state the edge's floor, else ``None``
    assert rows and all(isinstance(r, Linear) and r.hi is not None
                        and (r.lo is None or r.lo == pytest.approx(-r.hi))
                        and r.soft is None for r in rows)
    strip = {v for f in pm.faces.values() if f.role == "graded_strip"
             for v in pm.vertices if f.id in pm.vertices[v].incident_faces}
    runway = {v for f in pm.faces.values() if f.role in ("runway", "runway_crossing")
              for v in pm.vertices if f.id in pm.vertices[v].incident_faces}
    tied = set()
    for r in rows:
        v = r.terms[0][0]
        # 06p (1): ANY role but the runway family's own vertices
        assert v not in runway and all(u in runway for u, _c in r.terms[1:])
        assert r.terms[0][1] == 1.0
        tied.add(v)
    tt = T.tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    lowest = len(tt) - 1
    # the row cites the strip face it touches: the strip's tier
    for r in rows:
        if r.source.inputs[0].startswith("face:"):
            assert pm.faces[int(r.source.inputs[0][5:])].role == "graded_strip"
            assert row_tier(pm, r, tier_of, lowest) == lowest
    assert any(r.source.inputs[0].startswith("face:") for r in rows)
    assert {family_of(r) for r in rows} == {"strip_transverse"}
    names = [n for n, _ in GENERATORS]
    assert names.index("strip_transverse") == names.index("zone_bands") + 1
    # the bound is the cap at the vertex's own lateral distance from the edge
    vw = view(pm, law)
    for r in rows[:50]:
        v = r.terms[0][0]
        (ax, ay), (bx, by) = vw.xy[r.terms[1][0]], vw.xy[r.terms[-1][0]]
        px, py = vw.xy[v]
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
        d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
        f = next(f for f in pm.faces.values() if f.role == "runway")
        assert r.hi == pytest.approx(T.strip_transverse_bound(law, d, f.code_number,
                                                              f.code_letter), abs=1e-6)


def test_strip_reader_flags_a_vertex_standing_over_the_cap(diagonal, law, solved):
    """The reader prices the same bound on the built surface: a strip-only
    vertex inside the runway zone lifted over ``strip_transverse_bound(d)``
    is one row (``direction = "above"``); the hard solve reads none."""
    _cs, sol = solved
    rows = _census(diagonal, law, sol)
    assert rows[FAMILY_STRIP_TRANSVERSE] == [], rows[FAMILY_STRIP_TRANSVERSE][:2]
    airport, pm, _ = diagonal
    vw = view(pm, law)
    rw = next(f for f in pm.faces.values() if f.role == "runway")
    rings = [vw.rings[f.id] for f in pm.faces.values() if f.role in ("runway", "runway_crossing")]
    half = T.zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter)
    rwy = airport.runways[0]
    a_xy, b_xy = rwy.ends[0].xy, rwy.ends[1].xy
    ux, uy = (b_xy[0] - a_xy[0]) / rwy.length_m, (b_xy[1] - a_xy[1]) / rwy.length_m
    best = None
    for v in pm.vertices:
        faces = pm.vertices[v].incident_faces
        if not faces or not all(pm.faces[f].role == "graded_strip" for f in faces):
            continue
        x, y = vw.xy[v]
        if not 0.0 < (x - a_xy[0]) * ux + (y - a_xy[1]) * uy < rwy.length_m:
            continue                       # abeam only: the end corridors are the skirt's
        d = min(_seg_dist((x, y), vw.xy[ring[i]], vw.xy[ring[(i + 1) % len(ring)]])
                for ring in rings for i in range(len(ring)))
        # inside the corridor (two identity floors short of its outer
        # ring, the reader's margin), off the lip
        lip = law.tables.zones.adjacent_ground.lip_width_m
        tol = law.tables.emit.identity.min_distinct_spacing_m
        if lip < d < half - 2.0 * tol and (best is None or d > best[0]):
            best = (d, v)
    assert best is not None
    d, v = best
    bound = T.strip_transverse_bound(law, d, rw.code_number, rw.code_letter)
    z2 = list(sol.z)
    z2[v] += 2.0 * bound + 1.0       # from under the mandatory-down to over the cap
    got = _census(diagonal, law, _dc.replace(sol, z=tuple(z2)))[FAMILY_STRIP_TRANSVERSE]
    assert got and got[0]["direction"] == "above" and got[0]["magnitude_m"] > bound
    assert got[0]["cap_pct"] == pytest.approx(100 * bound / d, rel=0.05)


def _seg_dist(p, a, b) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / l2))
    return math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy))
