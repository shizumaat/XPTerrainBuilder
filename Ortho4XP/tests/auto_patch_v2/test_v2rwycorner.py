"""§35 THE RUNWAY-END CORNER (Fable 2026-09-13; RULINGS 2026-09-13q item 1).

A strip vertex BEYOND a runway end and LATERAL of its width carried no
law row at all: ``zones.abeam`` drops every runway-family band beyond the
runway's own extent, and ``strips._end_foot_rows`` bound only
``t ∈ [0, 1]`` along the end edge.  Measured at KCLT 18C/36C's south end
(1.0.324): 4.98 m over 4.62 m and 5.07 m over 3.91 m against a runway cut
6.44 m into the hill — the cockpit block's two critical-visual rows.

The twins:

* the corner is bound — a runway end over falling ground, a strip vertex
  3 m DIAGONAL of the corner is bound within ``end_skirt.max_down_grade``
  × its true plan distance, to the NEAREST point of the end edge;
* one derivation, no gap — ``zones.abeam`` still refuses the corner (the
  lateral law stays the lateral law: the fix is the chord, not a wider
  ``abeam``), and the end corridor's rect is ALREADY as wide laterally as
  the zone-2 half-width, which is why clamping ``t`` closes the whole gap;
* an ABEAM vertex is unchanged by the clamp (the clamp is the identity
  there and the plan distance is the along-axis distance).
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.constraints import strips, zones
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build

#: the runway's half-width and the end the ground falls away from
HALF = 22.5
END_X = 600.0


class _FallingDem:
    """Flat over the runway, falling hard beyond its 09/27 east end — the
    KCLT 18C/36C class (the runway cut into the hill is the mirror of a
    runway standing above falling ground; either way the corner quadrant
    is what the DEM alone would take)."""

    provenance = {"synthetic": "flat to x=600, then −8 % beyond the end"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 0.08 * max(0.0, x - END_X)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def synthetic(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-END_X, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0,
                      "fixture"),
            RunwayEnd("27", (END_X, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0,
                      "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _FallingDem(),
                      law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-END_X, -HALF, END_X, HALF), (), 3,
             "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (),
             None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA",
                    ((-400.0, 91.5), (400.0, 91.5))),)
    cl = Classification(cells, cuts, {}, ())
    pm, _stats = build(airport, cl, law)
    return airport, pm


def _group(pm, law, airport):
    vw = view(pm, law)
    (g,) = strips.runway_groups(vw, airport)
    return vw, g


def _corner_vertices(vw, g):
    """Every graded-strip vertex BEYOND an end and LATERAL of the runway's
    own half-width but still INSIDE the zone-2 corridor — the §35
    quadrant.  Outside zone 2 the ground is zone 3, the DEM, and no
    pavement reaches it (``zone_bounds``): that is not a gap, it is the
    law."""
    from auto_patch_v2.law.tables import zone2_half_width_m
    half = zone2_half_width_m(vw.law, "runway", g.code_number, g.code_letter)
    ux, uy = g.unit
    out = []
    for f in vw.faces_of_role(("graded_strip",)):
        for v in vw.rings[f.id]:
            x, y = vw.xy[v]
            s = (x - g.axis_a[0]) * ux + (y - g.axis_a[1]) * uy
            off = abs(-(x - g.axis_a[0]) * uy + (y - g.axis_a[1]) * ux)
            if g.width_m / 2.0 < off <= half and (s < 0.0 or s > g.length_m):
                out.append((v, s, off))
    return out


def test_the_corner_quadrant_exists_in_the_fixture(synthetic, law):
    airport, pm = synthetic
    vw, g = _group(pm, law, airport)
    assert _corner_vertices(vw, g), \
        "the fixture must carry strip vertices beyond an end and outside the width"


def test_the_corner_is_bound_to_the_nearest_point_of_the_end_edge(synthetic, law):
    """§35 (1): every corner vertex carries an end-skirt row, bound over
    its TRUE PLAN DISTANCE to the nearest point of the end edge."""
    airport, pm = synthetic
    vw, g = _group(pm, law, airport)
    cap = law.ruleset.end_skirt.max_down_grade
    rows = strips.end_corridor_longitudinal(pm, law, airport)
    bound = {t[0] for r in rows if isinstance(r, Linear) for t in r.terms}
    corners = _corner_vertices(vw, g)
    assert corners
    missing = [v for v, _s, _o in corners if v not in bound]
    assert not missing, f"unbound runway-end corner vertices: {missing}"

    # the row's own arithmetic: the bound is cap × the plan distance to the
    # nearest point of the end edge, and the feet are that edge's two ends
    ends = {}
    for r in rows:
        if not isinstance(r, Linear) or len(r.terms) != 3:
            continue
        (v, cv), (a, ca), (b, cb) = r.terms
        if cv != 1.0:
            continue
        ends.setdefault(v, []).append((r, a, b, -ca, -cb))
    for v, _s, _o in corners:
        assert v in ends, v
        r, a, b, wa, wb = ends[v][0]
        x, y = vw.xy[v]
        (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
        qx = ax * wa + bx * wb
        qy = ay * wa + by * wb
        d = math.hypot(x - qx, y - qy)
        assert wa + wb == pytest.approx(1.0)
        assert -r.lo == pytest.approx(r.hi)
        assert r.hi >= cap * d           # the bound is cap·d (+ the noise q)
        assert r.hi == pytest.approx(cap * d, abs=0.3)


def test_a_three_metre_diagonal_corner_is_held_within_cap_times_d(synthetic, law):
    """The spec's own twin: the strip vertex about 3 m DIAGONALLY off the
    corner of the falling end is bound at exactly ``max_down_grade × d``
    (plus the instrument's noise allowance ``q``, the form every end-skirt
    row takes) against the nearest point of the end edge — where before it
    carried no row at all and kept §23's datum, the DEM."""
    airport, pm = synthetic
    vw, g = _group(pm, law, airport)
    cap = law.ruleset.end_skirt.max_down_grade
    q = (law.tables.emit.instrument.strip_edge_noise_m
         - law.tables.emit.materiality.elevation_m)
    rows = {r.terms[0][0]: r
            for r in strips.end_corridor_longitudinal(pm, law, airport)
            if isinstance(r, Linear) and len(r.terms) == 3
            and r.terms[0][1] == 1.0}
    ux, uy = g.unit
    cx = g.axis_b[0] - uy * (g.width_m / 2.0)
    cy = g.axis_b[1] + ux * (g.width_m / 2.0)
    best = None
    for v, s, _off in _corner_vertices(vw, g):
        if s <= g.length_m:
            continue
        x, y = vw.xy[v]
        dc = math.hypot(x - cx, y - cy)
        if best is None or dc < best[0]:
            best = (dc, v)
    assert best is not None, "no corner vertex at the falling end"
    dc, v = best
    # the lip ring 3 m out in each direction: 3√2 = 4.24 m off the corner
    assert dc == pytest.approx(3.0 * math.sqrt(2.0), abs=0.5), \
        f"the diagonal vertex is {dc:.2f} m off the corner"
    r = rows[v]
    _, (a, ca), (b, cb) = r.terms
    x, y = vw.xy[v]
    (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
    d = math.hypot(x - (ax * -ca + bx * -cb), y - (ay * -ca + by * -cb))
    assert r.hi == pytest.approx(cap * d + q, abs=1e-9)
    assert r.lo == pytest.approx(-(cap * d + q), abs=1e-9)


def test_the_falling_dem_would_break_the_corner_rows(synthetic, law):
    """The fix BITES: on this fixture the raw DEM — what the corner
    quadrant held before §35 — breaks its own new rows, so the solve is
    forced off it (the KCLT 36C class, 4.98 / 5.07 m)."""
    airport, pm = synthetic
    vw, g = _group(pm, law, airport)
    rows = {r.terms[0][0]: r
            for r in strips.end_corridor_longitudinal(pm, law, airport)
            if isinstance(r, Linear) and len(r.terms) == 3
            and r.terms[0][1] == 1.0}
    broken = []
    for v, _s, _off in _corner_vertices(vw, g):
        r = rows.get(v)
        if r is None:
            continue
        _, (a, ca), (b, cb) = r.terms
        dz = (pm.vertices[v].dem_z
              - (pm.vertices[a].dem_z * -ca + pm.vertices[b].dem_z * -cb))
        if dz < r.lo or dz > r.hi:
            broken.append((v, round(dz, 3), round(r.lo, 3)))
    assert broken, "the DEM must violate the new corner rows for the fix to bite"


def test_the_lateral_law_still_refuses_the_corner(synthetic, law):
    """ONE derivation, both gates: the fix is the chord, not a widened
    ``abeam``.  A re-widened ``abeam`` would put the runway band back on a
    vertex beyond the runway's extent — the very thing v1's
    ``adjacent_ground_envelope`` ruled out ("runway ENDS are explicitly
    out of scope") — so this twin holds it shut."""
    airport, pm = synthetic
    ctx = zones._context(pm, law, airport)
    assert ctx is not None
    vw, g = _group(pm, law, airport)
    corners = _corner_vertices(vw, g)
    assert corners
    runway_edges = [k for k, e in enumerate(ctx.edges) if e[2] == "runway"]
    assert runway_edges
    for v, _s, _o in corners:
        assert not any(ctx.abeam(v, k) for k in runway_edges), \
            f"vertex {v} is beyond the runway extent: no lateral band binds it"


def test_the_end_rect_is_already_as_wide_as_the_zone_two_half_width(synthetic, law):
    """Why the rect is NOT widened a second time (§35 (1)'s alternative):
    ``runway_groups`` already builds the end corridor at
    ``max(width, zone-2 half-width)``, so the two gates tile the plane
    once ``t`` is clamped."""
    from auto_patch_v2.law.tables import zone2_half_width_m
    airport, pm = synthetic
    vw, g = _group(pm, law, airport)
    half = zone2_half_width_m(law, "runway", g.code_number, g.code_letter)
    assert half is not None and half > g.width_m / 2.0
    ux, uy = g.unit
    # a point at the zone-2 outer bound, 5 m beyond the end, is inside the rect
    px = g.axis_b[0] + ux * 5.0 - uy * half
    py = g.axis_b[1] + uy * 5.0 + ux * half
    from auto_patch_v2.constraints.geometry import point_in_rect_ring
    assert point_in_rect_ring(px, py, g.rings[2])


def test_an_abeam_vertex_is_unchanged_by_the_clamp(synthetic, law):
    """The clamp is the identity for a vertex abeam the width, and the
    plan distance to a perpendicular end edge IS the along-axis distance
    the old code used — the corner fix must not move the LEMD 18R/36L lip
    rows it was written for (2026-09-04e)."""
    airport, pm = synthetic
    vw, g = _group(pm, law, airport)
    cap = law.ruleset.end_skirt.max_down_grade
    ux, uy = g.unit
    rows = {r.terms[0][0]: r for r in strips.end_corridor_longitudinal(pm, law, airport)
            if isinstance(r, Linear) and len(r.terms) == 3 and r.terms[0][1] == 1.0}
    seen = 0
    for f in vw.faces_of_role(("graded_strip",)):
        for v in vw.rings[f.id]:
            x, y = vw.xy[v]
            s = (x - g.axis_a[0]) * ux + (y - g.axis_a[1]) * uy
            off = abs(-(x - g.axis_a[0]) * uy + (y - g.axis_a[1]) * ux)
            beyond = s - g.length_m
            if off > g.width_m / 2.0 or beyond < 1.0 or v not in rows:
                continue
            seen += 1
            assert rows[v].hi == pytest.approx(cap * beyond, abs=0.31)
    assert seen, "the fixture must carry abeam end-corridor vertices too"
