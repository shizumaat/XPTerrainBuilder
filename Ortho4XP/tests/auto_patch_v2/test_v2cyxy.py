"""THE CROSSING and THE PER-BODY DATUM (owner RULINGS 2026-09-09p (2)/(3);
spec ``docs/specs/auto-patch-v2/design-surface-spec.md`` §13/§14; lane
``v2cyxy``).

Two readings, both on synthetic maps:

* (2) A TAXIWAY CROSSING A RUNWAY RIDES THE CROWN.  The taxi centreline
  reaching the runway ring meets it at the runway's own EDGE — under the
  ridge by the crown drop, never below its own approach — and the section
  across the slab is edge -> ridge -> edge, a crest and never a dip.
  (At CYXY this is already what the surface does; the dip the owner read
  is the RUNWAY x RUNWAY crossing, attributed in the spec's §13.  This
  twin is the lock on the behaviour that IS right.)
* (3) TWO APRONS AT DIFFERENT TERRAIN LEVELS, joined by a taxiway, each
  sit at THEIR OWN terrain mean and the taxiway climbs between them —
  the per-body datum (``[design] body_datum``).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.runway_profile import ridge_chains
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import apron_roles
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot

RUN_LEN = 1200.0


class _PlaneDem:
    """A gentle plane: the runway's ground, nothing to fight about."""

    provenance = {"synthetic": "plane"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.004 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _TerraceDem:
    """THE HILL (09p (3)): flat at 700 m out to y = 200 m, then a ramp up
    to a second bench at 703 m beyond y = 400 m.  Two aprons, one on each
    bench, and the taxiway that has to climb between them — a 3 m rise
    over the 240 m of taxiway, which its 1.5 % cap CAN carry (a step the
    cap cannot carry is a law question, not a datum question)."""

    provenance = {"synthetic": "two benches 3 m apart"}

    def z(self, x: float, y: float) -> float:
        t = min(1.0, max(0.0, (y - 200.0) / 200.0))
        return 700.0 + 3.0 * t

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law, dem, *, thresholds=(700.0, 700.0)):
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      thresholds[0], "fixture"),
            RunwayEnd("27", r((RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      thresholds[1], "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, thresholds[0], (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key), r


def _solve(law, airport, cells, cuts=()):
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    pm, _st = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    return pm, np.asarray(sol.z, float), rep


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── (2) THE CROSSING RIDES THE CROWN ────────────────────────────────────

@pytest.fixture(scope="module")
def crossing(law):
    """A crowned runway crossed by ONE taxiway: a stub on each side at the
    same station, each with its centreline running out to a parallel."""
    airport, r = _airport(law, _PlaneDem())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, "primary_parallel", "taxiN", _rect(r, -400.0, 80.0, 400.0, 103.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiS", _rect(r, -400.0, -103.0, 400.0, -80.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(3, "stub", "stubN", _rect(r, -11.5, HALF_WIDTH, 11.5, 80.0), (), None,
             "D", "airside", "taxi", {}),
        Cell(4, "stub", "stubS", _rect(r, -11.5, -80.0, 11.5, -HALF_WIDTH), (), None,
             "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiN", (r((-400.0, 91.5)), r((400.0, 91.5)))),
            CutLine("taxi_centerline", "taxiS", (r((-400.0, -91.5)), r((400.0, -91.5)))),
            CutLine("taxi_centerline", "stubN", (r((0.0, HALF_WIDTH)), r((0.0, 91.5)))),
            CutLine("taxi_centerline", "stubS", (r((0.0, -HALF_WIDTH)), r((0.0, -91.5)))))
    return (*_solve(law, airport, cells, cuts), airport, r)


def _runway_frame(airport):
    (ax, ay), (bx, by) = airport.runways[0].ends[0].xy, airport.runways[0].ends[1].xy
    L = math.hypot(bx - ax, by - ay)
    return ax, ay, (bx - ax) / L, (by - ay) / L


def _ridge_z(pm, law, airport, z, s_at):
    """The built ridge elevation at station ``s_at`` (linear between the
    two ridge stations bracketing it)."""
    ax, ay, ux, uy = _runway_frame(airport)
    pts = []
    for ch in ridge_chains(view(pm, law)).get(airport.runways[0].id) or []:
        for v in ch:
            dx, dy = pm.vertices[v].xy[0] - ax, pm.vertices[v].xy[1] - ay
            pts.append((dx * ux + dy * uy, float(z[v])))
    pts.sort()
    assert pts, "the fixture's runway must carry a ridge"
    if s_at <= pts[0][0]:
        return pts[0][1]
    for (s0, z0), (s1, z1) in zip(pts, pts[1:]):
        if s0 <= s_at <= s1:
            t = (s_at - s0) / (s1 - s0) if s1 > s0 else 0.0
            return z0 * (1.0 - t) + z1 * t
    return pts[-1][1]


def _crossing_mouths(pm, law, z, airport):
    """The two centreline chains reaching the runway ring at the same
    station from opposite sides: ``(mouth vertex, station, offset, the
    chain walking OUTWARD)`` for each side."""
    ax, ay, ux, uy = _runway_frame(airport)
    rw_roles = set(law.tables.precedence.runway_family.members)
    out = []
    for bl in pm.breaklines.values():
        if bl.kind != "taxi_centerline":
            continue
        ch = bl.vertices(pm)
        for idx in (0, len(ch) - 1):
            v = ch[idx]
            if not any(pm.faces[f].role in rw_roles
                       for f in pm.vertices[v].incident_faces):
                continue
            dx, dy = pm.vertices[v].xy[0] - ax, pm.vertices[v].xy[1] - ay
            out.append((v, dx * ux + dy * uy, -dx * uy + dy * ux,
                        ch if idx == 0 else ch[::-1]))
    pairs = []
    for i, a in enumerate(out):
        for b in out[i + 1:]:
            if a[2] * b[2] < 0.0 and abs(a[1] - b[1]) < 25.0:
                pairs.append((a, b))
    return pairs


def test_a_taxi_crossing_rides_the_runways_crown(crossing, law):
    """09p (2): the section across the slab is edge -> ridge -> edge.  The
    ridge stands ABOVE both mouths (the crown), and no station of the
    crossing sits below both of its neighbours — the surface CRESTS over
    the runway, it never dips into it."""
    pm, z, _rep, airport, _r = crossing
    pairs = _crossing_mouths(pm, law, z, airport)
    assert pairs, "the fixture must put a taxiway across the runway"
    for a, b in pairs:
        ridge = _ridge_z(pm, law, airport, z, 0.5 * (a[1] + b[1]))
        # the mouths ARE the runway's edge: under the ridge by the crown
        # drop, and by no more than the transverse cap allows over the
        # half width
        for m in (a, b):
            drop = ridge - float(z[m[0]])
            assert drop >= -1e-6, \
                "a crossing mouth never stands ABOVE the ridge it crosses"
            assert drop <= 0.02 * abs(m[2]) + 0.05, \
                "the mouth sits at the crown's own fall, not below it"
        # the section across: approach A ... mouth A, ridge, mouth B ... approach B
        section = ([float(z[v]) for v in a[3][:4]][::-1]
                   + [ridge] + [float(z[v]) for v in b[3][:4]])
        k_ridge = 4
        assert section[k_ridge] >= max(section[k_ridge - 1],
                                       section[k_ridge + 1]) - 1e-6, \
            "the ridge is the high point of the crossing, never a dip"
        for k in range(1, len(section) - 1):
            assert section[k] >= min(section[k - 1], section[k + 1]) - 1e-6, \
                f"station {k} of the crossing sits below BOTH its neighbours"


# ── (3) THE PER-BODY DATUM ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def two_benches(law):
    """Two aprons 20 m apart in the ground, joined only by a taxiway."""
    airport, r = _airport(law, _TerraceDem())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, "apron", "apronLOW", _rect(r, -260.0, 100.0, -60.0, 190.0), (), None,
             "D", "airside", "apron", {}),
        Cell(2, "apron", "apronHIGH", _rect(r, -260.0, 430.0, -60.0, 520.0), (), None,
             "D", "airside", "apron", {}),
        Cell(3, "primary_parallel", "taxiG", _rect(r, -172.0, 190.0, -149.0, 430.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(4, "stub", "stubB", _rect(r, -172.0, HALF_WIDTH, -149.0, 100.0), (), None,
             "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiG",
                    (r((-160.5, 190.0)), r((-160.5, 430.0)))),
            CutLine("taxi_centerline", "stubB",
                    (r((-160.5, HALF_WIDTH)), r((-160.5, 100.0)))))
    return (*_solve(law, airport, cells, cuts), airport, r)


def _body_means(pm, law, z):
    """Per APRON BODY: ``(mean z, mean DEM)`` — the datum's own reading."""
    roles = apron_roles(law)
    parent: dict[int, int] = {}

    def find(v):
        parent.setdefault(v, v)
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for f in pm.faces.values():
        if f.role not in roles:
            continue
        vs = [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]
        for v in vs[1:]:
            parent[find(v)] = find(vs[0])
    acc: dict[int, set[int]] = {}
    for f in pm.faces.values():
        if f.role not in roles:
            continue
        for ring in (f.ring, *f.holes):
            for v in pm.ring_vertices(ring):
                acc.setdefault(find(v), set()).add(v)
    return {k: (float(np.mean([z[v] for v in vs])),
                float(np.mean([pm.vertices[v].dem_z for v in vs])))
            for k, vs in acc.items()}


def test_the_apron_roles_are_the_bodies_the_datum_sits(law):
    """The register: the datum's roles are exactly the ``apron`` bending
    class — never the runway family, never the taxi family, never a road."""
    roles = apron_roles(law)
    assert roles, "some role must carry a body datum"
    assert not (roles & set(law.tables.precedence.runway_family.members))
    assert not (roles & set(law.tables.precedence.taxi_family.members))
    assert not (roles & set(law.tables.families["road_cross_section"].roles))
    assert "apron" in roles


def test_each_apron_sits_on_its_own_terrain_mean(two_benches, law):
    """09p (3): the body's MEAN z is the MEAN DEM under it — so the apron
    up the hill sits up the hill instead of being levelled toward the
    runway.  Reported for EVERY body, so a second body cannot hide."""
    pm, z, rep, _airport, _r = two_benches
    assert rep.body_datum_rows >= 2, "each apron body carries its own datum row"
    means = _body_means(pm, law, z)
    assert len(means) >= 2, "the two aprons are two bodies (only a taxiway joins them)"
    for _k, (zm, dm) in means.items():
        assert abs(zm - dm) <= 0.5, \
            f"a body's mean z {zm:.2f} stands off its terrain mean {dm:.2f}"
    lo = min(means.values(), key=lambda p: p[1])
    hi = max(means.values(), key=lambda p: p[1])
    assert hi[1] - lo[1] > 2.0, "the fixture's two benches must differ"
    assert abs((hi[0] - lo[0]) - (hi[1] - lo[1])) <= 0.5, \
        "the high apron stays high: the bodies are NOT levelled together"


def test_the_taxiway_climbs_between_the_two_aprons(two_benches, law):
    """The other half of the ruling: the taxiway between the bodies climbs
    at its own cap instead of flattening — and it climbs the bench's own
    height, not the runway's."""
    pm, z, _rep, _airport, _r = two_benches
    bl = next(b for b in pm.breaklines.values()
              if b.kind == "taxi_centerline" and b.ref == "taxiG")
    ch = bl.vertices(pm)
    climb = float(z[ch[-1]]) - float(z[ch[0]])
    dem_climb = float(pm.vertices[ch[-1]].dem_z) - float(pm.vertices[ch[0]].dem_z)
    assert climb * dem_climb > 0.0, "the taxiway climbs the way the ground does"
    assert abs(climb) >= 0.8 * abs(dem_climb), \
        f"the taxiway climbs {climb:.2f} m where the ground climbs {dem_climb:.2f} m"


def test_the_body_datum_is_one_row_per_body_never_per_vertex(two_benches, law):
    """The ruling's shape: ONE row per body.  Reading it off the report
    keeps the promise auditable — a per-vertex datum would be the DEM pull
    08t answer 1 removed, wearing a datum's clothes."""
    pm, _z, rep, _airport, _r = two_benches
    means = _body_means(pm, law, _z_of(pm))
    assert rep.body_datum_rows == len(means), \
        "one datum row per apron body, and no more"


def _z_of(pm):
    return np.zeros(len(pm.vertices))
