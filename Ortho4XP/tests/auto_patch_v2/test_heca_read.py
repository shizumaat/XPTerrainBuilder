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
from auto_patch_v2.emit import rebake as R
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
from tests.auto_patch_v2.test_m6a_rebake import _feet_member, _flat, _unit


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
    assert rows and all(isinstance(r, Linear) and r.lo is None and r.hi is not None
                        and r.soft is None for r in rows)
    strip = {v for f in pm.faces.values() if f.role == "graded_strip"
             for v in pm.vertices if f.id in pm.vertices[v].incident_faces}
    runway = {v for f in pm.faces.values() if f.role in ("runway", "runway_crossing")
              for v in pm.vertices if f.id in pm.vertices[v].incident_faces}
    for r in rows:
        v = r.terms[0][0]
        assert v in strip and all(u in runway for u, _c in r.terms[1:])
        assert r.terms[0][1] == 1.0
    tt = T.tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    lowest = len(tt) - 1
    assert all(row_tier(pm, r, tier_of, lowest) == lowest for r in rows)
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


# ── law 3: the seat splits where the members disagree ────────────────────

def _anchor_then(z_anchor: float, z_low: float, z_high: float, split: float = 0.5):
    """A sampler answering ``z_anchor`` on its FIRST call (the unit's
    anchor, the base of the rendered plane), then ``z_low`` south of
    ``split`` and ``z_high`` north of it."""
    seen = {"n": 0}

    def s(lat, lon):
        seen["n"] += 1
        if seen["n"] == 1:
            return (z_anchor, False)
        return ((z_low if lat < split else z_high), False)
    return s


def test_three_agree_the_fourth_seats_apart(law, monkeypatch):
    """§4 twin: three members at one delta, one 30 m off → three move
    together, the fourth by its own delta, the coalition recorded."""
    rb = law.tables.structures.rebake
    pl = _unit(_feet_member("a", 0.0), _feet_member("b", 0.0), _feet_member("c", 0.0),
               _feet_member("d", 0.0, lat0=1.0))
    # anchor 710, the three read 705 (delta −5), d reads 680 (delta −30)
    us = R.seat(pl, _anchor_then(710.0, 705.0, 680.0), law).units[0]
    by = {m.resource.rsplit("/", 1)[-1]: m for m in us.members}
    assert us.bakes and us.delta_m == pytest.approx(-5.0)
    assert all(not by[k].seated_apart for k in ("a.obj", "b.obj", "c.obj"))
    d = by["d.obj"]
    assert d.seated_apart and d.delta_m == pytest.approx(-30.0)
    assert d.family_delta_m == pytest.approx(-5.0) and "seated_apart" in d.note
    assert any("family split" in f for f in us.findings)
    c = R.SeatResult("ZZZZ", (us,)).counts()
    assert c["units_split"] == 1 and c["members_apart"] == 1 and c["resources_baked"] == 4
    # the decision carries the member's own delta and the provenance note
    # (the OBJ8 read stubbed: one solid triangle per member)
    from auto_patch import engine_v2, obj8_reader

    class _Geom:
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        solid_triangles = [(0, 1, 2)]
    monkeypatch.setattr(obj8_reader, "load_object_file", lambda path: _Geom())
    dec = engine_v2._decision_from_seats(pl, R.SeatResult("ZZZZ", (us,)), measure_only=False)
    assert all(x == pytest.approx(-30.0) for x in dec.delta_by_resource_and_vertex["objects/d.obj"].values())
    assert all(x == pytest.approx(-5.0) for x in dec.delta_by_resource_and_vertex["objects/a.obj"].values())
    assert dec.decision_kind_by_resource["objects/d.obj"] == "v2_feet_apart"
    assert "seated_apart" in dec.seat_note_by_resource["objects/d.obj"]
    assert "coalition -5.000" in dec.seat_note_by_resource["objects/d.obj"]
    assert dec.seat_datum_by_resource["objects/d.obj"] == pytest.approx(710.0 - 30.0)
    assert (rb.min_delta_m > 0) and "objects/a.obj" not in dec.seat_note_by_resource


def test_a_roof_piece_over_the_familys_ground_follows(law):
    """OTHH unit:21's class: two members at y = 0 on flat ground and one
    whose feet are 6.4 m up over the SAME ground — its own delta would
    drop it to the ground; it is on the family (I-8) and follows, the
    unit seats as one."""
    pl = _unit(_feet_member("AuxBuilding_19_000", 0.0), _feet_member("AuxBuilding_19_001", 0.0),
               _feet_member("AuxBuilding_19_002", 6.4))
    us = R.seat(pl, _flat(710.0), law).units[0]
    assert us.delta_m == pytest.approx(0.0) and us.skip_reason.startswith("below_threshold")
    roof = us.members[2]
    assert roof.delta_m == pytest.approx(-6.4) and not roof.founding
    assert not roof.seated_apart and not roof.apart_stays
    assert R.SeatResult("OTHH", (us,)).counts()["units_split"] == 0


def test_a_building_on_its_own_ground_seats_apart_even_out_of_band(law):
    """HECA's class: a member authored 5 m up whose feet stand on ground
    5 m HIGHER than the family's (85 m of relief around one anchor) is
    on the land, not on the family — outside the coalition it seats by
    its own delta."""
    pl = _unit(_feet_member("base_a", 0.0), _feet_member("base_b", 0.0),
               _feet_member("upper", 5.0, lat0=1.0))
    # anchor 710; the family floats 10 m over a cut (delta −10); the
    # upper member's ground is 10 m lower still: its own delta is −25
    us = R.seat(pl, _anchor_then(710.0, 700.0, 690.0), law).units[0]
    assert us.delta_m == pytest.approx(-10.0)
    up = us.members[2]
    assert up.ground_m == pytest.approx(690.0) and up.delta_m == pytest.approx(-25.0)
    assert up.seated_apart and up.family_delta_m == pytest.approx(-10.0)


def test_a_floating_member_is_not_a_facility(law):
    """05p/05q read with the rule's own words: a facility stands BELOW the
    mesh by more than the contact band.  A family floating 35 m over a
    cut with one member floating 7 m has no facility — the 7 m member is
    outside the coalition and seats apart."""
    depth = law.tables.structures.basin.contact_band_m
    pl = _unit(_feet_member("a", 0.0), _feet_member("b", 0.0), _feet_member("c", 0.0),
               _feet_member("d", 0.0, lat0=1.0))
    us = R.seat(pl, _anchor_then(710.0, 675.0, 703.0), law).units[0]      # family −35, d −7
    by = {m.resource.rsplit("/", 1)[-1]: m for m in us.members}
    assert us.delta_m == pytest.approx(-35.0)
    assert not by["d.obj"].facility and by["d.obj"].seated_apart
    assert by["d.obj"].delta_m == pytest.approx(-7.0)
    # ...while a member genuinely sunk under the mesh beyond the band still is
    pl2 = _unit(_feet_member("a", 0.0), _feet_member("b", 0.0), _feet_member("c", 0.0),
                _feet_member("pit", -(depth + 1.5)))
    us2 = R.seat(pl2, _flat(710.0), law).units[0]
    assert us2.members[3].facility and not us2.members[3].seated_apart


def test_outside_the_coalition_but_under_the_threshold_stays(law):
    rb = law.tables.structures.rebake
    small = 0.5 * rb.min_delta_m
    assert small > rb.agreement_window_m
    pl = _unit(_feet_member("a", 0.0), _feet_member("b", 0.0),
               _feet_member("c", 0.0, lat0=1.0))
    us = R.seat(pl, _anchor_then(710.0, 705.0, 710.0 + small), law).units[0]   # family −5, c +small
    c = us.members[2]
    assert us.delta_m == pytest.approx(-5.0)
    assert c.apart_stays and not c.seated_apart and c.delta_m == pytest.approx(small)
    from auto_patch.engine_v2 import _decision_from_seats
    dec = _decision_from_seats(pl, R.SeatResult("ZZZZ", (us,)), measure_only=False)
    assert "objects/c.obj" not in dec.delta_by_resource_and_vertex
    assert "seated apart" in dict(dec.skipped)["objects/c.obj"]


def test_a_resource_apart_at_two_anchors_takes_its_own_median(law):
    """One file, one delta (I-4 per resource): the same resource seated
    apart at two anchors with two own deltas bakes at their median."""
    m1 = _feet_member("a", 0.0)
    m2 = _feet_member("b", 0.0)
    far1 = _feet_member("twice", 0.0, lat0=1.0)
    far2 = _feet_member("twice", 0.0, lat0=2.0)
    plan = R.RebakePlan("ZZZZ", "p", "/p", (
        R.Unit("unit:1", (0.0, 0.0), 0.0, (m1, m2, far1)),
        R.Unit("unit:2", (0.0, 0.0), 0.0, (m1, m2, far2))), (), {})

    calls = {"n": 0}

    def s(lat, lon):
        calls["n"] += 1
        if lat < 0.5:
            # the anchor reads 710 (first call of each unit), the family 705
            return ((710.0 if calls["n"] == 1 or lat == 0.0 and lon == 0.0 else 705.0), False)
        return ((680.0 if lat < 1.5 else 678.0), False)
    res = R.seat(plan, s, law)
    a1 = next(m for m in res.units[0].members if m.resource.endswith("twice.obj"))
    a2 = next(m for m in res.units[1].members if m.resource.endswith("twice.obj"))
    assert a1.seated_apart and a2.seated_apart
    assert a1.delta_m == pytest.approx(-31.0) and a2.delta_m == pytest.approx(-31.0)
    assert "own median" in a1.note
    assert all(not u.held for u in res.units)
