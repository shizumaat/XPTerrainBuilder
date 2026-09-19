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
        # RE-SCOPED (owner RULINGS 2026-09-10p, lane v2taxidatum): the
        # MOUTHS (k = 3, 5) are the runway's own crown EDGE, checked
        # exactly above.  With the taxi body on its own terrain mean the
        # ground beside the runway can stand ABOVE that edge (this
        # fixture's DEM tilts 0.004 across a runway pinned flat), and the
        # taxiway then falls into the edge as a real one does — the mouth
        # is a local minimum BY THE CROWN, not a sag in the crossing.
        # The ruling's "never a dip" is about the stations across the
        # slab and along the approaches, which is what is asserted here.
        for k in range(1, len(section) - 1):
            if k in (k_ridge - 1, k_ridge + 1):
                continue
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
    """The ruling's shape: a FIXED, TINY number of rows per body, never one
    per vertex — a per-vertex datum would be the DEM pull 08t answer 1
    removed, wearing a datum's clothes.

    RE-SCOPED TWICE.  10p made taxi bodies datum bodies and the count was
    apron + taxi; 10v took the taxi bodies back out (their level is their
    CHAIN'S TREND now) and made the apron datum the DEM's AFFINE fit —
    THREE rows per body (the mean and the two first moments), so the count
    is 3x the apron bodies, less any moment row a collinear body cannot
    carry."""
    pm, _z, rep, _airport, _r = two_benches
    means = _body_means(pm, law, _z_of(pm))
    assert rep.body_datum_bodies == len(means), "one datum BODY per apron body"
    assert rep.body_datum_rows <= 3 * len(means)
    assert rep.body_datum_rows >= len(means), "each body carries at least its mean"
    assert all(r["kind"] == "apron" for r in rep.body_datums)


def _z_of(pm):
    return np.zeros(len(pm.vertices))


# ── ROUND 2 (RULINGS 2026-09-09r) ───────────────────────────────────────

# (1) THE WOODBURY LOW-RANK DATUM

def _three_bodies(law):
    """Three apron bodies on three terrain levels plus a runway: the
    smallest map that exercises a rank-3 datum term."""
    airport, r = _airport(law, _TerraceDem())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, "apron", "apronLOW", _rect(r, -260.0, 100.0, -60.0, 190.0), (), None,
             "D", "airside", "apron", {}),
        Cell(2, "apron", "apronMID", _rect(r, 40.0, 250.0, 240.0, 340.0), (), None,
             "D", "airside", "apron", {}),
        Cell(3, "apron", "apronHIGH", _rect(r, -260.0, 430.0, -60.0, 520.0), (), None,
             "D", "airside", "apron", {}),
    )
    return airport, cells


def _solve_low_rank(law, airport, cells, mode):
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law, low_rank=mode)
    return np.asarray(sol.z, float), rep


def test_the_woodbury_datum_solves_the_same_surface_as_the_dense_rows(law):
    """09r (1): the per-body datum leaves the factorised matrix and comes
    back as the LOW-RANK term ``U Uᵀ`` — EXACT algebra, so the surface is
    the same one the dense rows gave, to the linear solver's own noise.
    (The reason for the change is wall, not surface: a mean over ``N``
    vertices is a dense ``N x N`` block in ``AᵀA``, ``O(Σ N²)`` over 342
    bodies at HECA — spec §14.5.)"""
    airport, cells = _three_bodies(law)
    z_dense, rep_dense = _solve_low_rank(law, airport, cells, "dense")
    assert rep_dense.body_datum_rows >= 3, "the fixture must carry three bodies"
    for mode in ("bordered", "woodbury"):
        z_lr, rep_lr = _solve_low_rank(law, airport, cells, mode)
        assert rep_lr.body_datum_rows == rep_dense.body_datum_rows
        worst = float(np.max(np.abs(z_lr - z_dense)))
        assert worst <= 1e-3, \
            f"the {mode} path moved the surface {worst:.6f} m from the dense rows"


def test_the_body_datum_rows_never_enter_the_factorised_matrix(law):
    """The mechanism itself: ``assemble`` keeps the datum rows in their own
    accumulator, so the base matrix the active set factorises carries NOT
    ONE of them — which is what removes the dense block."""
    from auto_patch_v2.solve.design import DesignReport, assemble
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    airport, cells = _three_bodies(law)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    rep = DesignReport()
    base = assemble(pm, cs, law, rep)
    assert base.body is not None and base.body.n == rep.body_datum_rows >= 3
    assert not any(own and own[0] == "body_datum" for own in base.rows.owner), \
        "a body datum row reached the ALWAYS-ON matrix"


# (2) THE RUNWAY x RUNWAY CROSSING

XW = 15.0            # the secondary runway's half width
SEC_HALF = 500.0     # the secondary's half length


def _crossing_airport(law, dem, *, primary=(700.0, 706.0), secondary=(701.0, 701.0)):
    """TWO runways crossing at the origin, their threshold chords in
    CONFLICT over the shared slab (the CYXY 02/20 shape, spec §13.2): the
    long runway's chord reads 703.0 m at the crossing, the short one's
    701.0 — the same ~2 m disagreement 02/20 has with 14R/32L.  Under
    RULINGS 2026-09-09z (1) the SHORT runway governs (its threshold is
    500 m from the node against 600 m), and the long one grades to 701.0
    inside its own laws — the fixture ``test_v2crossing.py`` reads."""
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends_p = (RunwayEnd("09", r((-RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                        primary[0], "fixture"),
              RunwayEnd("27", r((RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                        primary[1], "fixture"))
    ends_s = (RunwayEnd("18", r((0.0, -SEC_HALF)), (60.5, -135.5), 0.0, 0.0,
                        secondary[0], "fixture"),
              RunwayEnd("36", r((0.0, SEC_HALF)), (60.5, -135.5), 0.0, 0.0,
                        secondary[1], "fixture"))
    rw_p = Runway("09/27", 45.0, 1, ends_p, 3, "D")
    rw_s = Runway("18/36", 30.0, 2, ends_s, 3, "C")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    ap = Airport("ZZZZ", "Synthetic", frame, primary[0], (rw_p, rw_s), (), (), {}, (),
                 (), (), (), (), (), (), pack, dem, law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, -XW,
                                         HALF_WIDTH), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, "runway", "09/27", _rect(r, XW, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside",
             "runway", {}),
        Cell(2, "runway", "18/36", _rect(r, -XW, -SEC_HALF, XW, -HALF_WIDTH), (),
             3, "C", "airside", "runway", {}),
        Cell(3, "runway", "18/36", _rect(r, -XW, HALF_WIDTH, XW, SEC_HALF), (),
             3, "C", "airside", "runway", {}),
        Cell(4, "runway_crossing", "09/27+18/36",
             _rect(r, -XW, -HALF_WIDTH, XW, HALF_WIDTH), (), 3, "D", "airside",
             "runway_crossing", {}),
    )
    return ap, r, cells


@pytest.fixture(scope="module")
def runway_crossing(law):
    airport, r, cells = _crossing_airport(law, _PlaneDem())
    return (*_solve(law, airport, cells), airport, r)


# 09r (2)'s FOUR TWINS ARE DELETED with the mechanism they locked (owner
# RULINGS 2026-09-09z (1) replaced "the primary governs" — the longer
# runway — with the NEAREST-THRESHOLD anchor; refuted mechanisms are
# deleted, not kept gated).  Their successors are
# ``tests/auto_patch_v2/test_v2crossing.py``; the fixture above stays,
# because the hard-set twins below read it.


# (3) THE HARD SET SETTLES

def test_the_hard_set_settles_at_the_crossing(runway_crossing, law):
    """09r (3): the polish iterates the augmented-Lagrangian multipliers
    until every hard row is within ``hard_tol_m``.  A shipped patch never
    reads HARD SET NOT SETTLED.  (Round 1 stopped on the first stalled
    round and left CYXY's crossing vertical-curve row at 0.0121 against
    its 0.00081 bound — 15x.)"""
    from auto_patch_v2.law.tables import design as design_law
    _pm, _z, rep, _airport, _r = runway_crossing
    d = design_law(law)
    assert rep.hard_rows > 0, "the fixture must state hard runway rows"
    assert rep.hard_settled, (
        f"HARD SET NOT SETTLED: {rep.hard_max_violation_m:.5f} m of "
        f"{rep.hard_worst} after {rep.hard_rounds} polish round(s)")
    assert rep.hard_max_violation_m <= d.hard_tol_m
    assert rep.hard_rounds <= d.polish_rounds_max
    assert "HARD SET SETTLED" in rep.line()


def test_a_flat_polish_round_no_longer_ends_the_loop(law, monkeypatch):
    """09r (3)'s mechanism.  Round 1 stopped the polish on the FIRST round
    that bought less than a tolerance and shipped whatever it had.  The
    loop now runs to ``polish_rounds_max`` and, where the set still is not
    held, says so BY NAME — the crossing whose conflict its secondary
    cannot climb inside its own laws leaves a vertical-curve row over its
    bound, and the report NAMES that ruling instead of reading settled.

    §50 (owner RULINGS 2026-09-18d (3), lane ``tffjcap``) REMOVED THIS
    FIXTURE'S INFEASIBILITY, by design: the conflict is a PIN conflict
    (700 -> node 690 -> 706 over 600 m either side, 1.67 % and 2.67 %
    against code 3's 1.5 %), and the cap now yields to the pins, so the
    same fixture SETTLES — asserted below as the second arm.  The 09r (3)
    mechanism this twin exists for is unchanged, so it is read with the
    yield DISABLED, which is exactly the problem it was written against.
    """
    import auto_patch_v2.constraints.runway_yield as _ry
    from auto_patch_v2.law.tables import design as design_law
    d = design_law(law)
    # ARM 2 first (the §50 effect, on the untouched law): the pins are
    # truth, the cap yields, and the hard set holds.
    airport, _r, cells = _crossing_airport(law, _PlaneDem(),
                                           secondary=(690.0, 690.0))
    _pm, _z, rep_yield = _solve(law, airport, cells)
    assert rep_yield.hard_settled and \
        rep_yield.hard_max_violation_m <= d.hard_tol_m + 1e-9
    # ARM 1: the same fixture with the yield disabled — the pre-§50
    # problem, and the polish naming its failure.
    monkeypatch.setattr(_ry, "derive", lambda pm, law, airport: {})
    airport, _r, cells = _crossing_airport(law, _PlaneDem(),
                                           secondary=(690.0, 690.0))
    _pm, _z, rep = _solve(law, airport, cells)
    assert rep.hard_rounds == d.polish_rounds_max, \
        "the loop runs its rounds instead of stopping on the first flat one"
    assert not rep.hard_settled and rep.hard_max_violation_m > d.hard_tol_m
    assert rep.hard_worst, "an unsettled hard set is named, never silent"
    assert "HARD SET NOT SETTLED" in rep.line()


def test_a_reachable_crossing_settles_its_hard_set(law):
    """The other side of 09r (3): where the secondary CAN climb into the
    primary inside its own laws, the polish holds every hard row and the
    report reads SETTLED — the certificate the ruling asks for."""
    from auto_patch_v2.law.tables import design as design_law
    d = design_law(law)
    airport, _r, cells = _crossing_airport(law, _PlaneDem(),
                                           secondary=(697.0, 697.0))
    _pm, _z, rep = _solve(law, airport, cells)
    assert rep.hard_settled and rep.hard_max_violation_m <= d.hard_tol_m, (
        f"{rep.hard_max_violation_m:.5f} m of {rep.hard_worst}")
    assert rep.hard_rounds <= d.polish_rounds_max
    assert "HARD SET SETTLED" in rep.line()


# ── ROUND 3 (RULINGS 2026-09-09v): THE DATUM'S VERTEX SET IS SHAPE MEMBERSHIP

def _road_along_a_boundary(law):
    """apronA west of an 8 m service road, apronB east of it and SHORTER —
    so the road shares more vertices with A and 08r-2 welds it to A.  The
    road's FAR edge (x = +4) is therefore A's, although those vertices are
    ring vertices of apronB's faces: the two readings of "B's vertices"
    disagree exactly there."""
    airport, r = _airport(law, _PlaneDem())
    ring_a = ((-200.0, 100.0), (-4.0, 100.0)) \
        + tuple((-4.0, float(y)) for y in range(120, 500, 20)) \
        + ((-4.0, 500.0), (-200.0, 500.0))
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, "apron", "apronA", tuple(r(p) for p in ring_a), (), None, "D",
             "airside", "apron", {}),
        Cell(2, "service_road", "road", _rect(r, -4.0, 100.0, 4.0, 500.0), (), None,
             "D", "airside", "strip", {}),
        Cell(3, "apron", "apronB", _rect(r, 4.0, 140.0, 200.0, 460.0), (), None, "D",
             "airside", "apron", {}),
    )
    return airport, cells


def test_a_boundary_vertex_enters_exactly_one_bodys_datum_mean(law):
    """09v: the per-body datum's vertex set is SHAPE MEMBERSHIP
    (``shape_of_vertex``), never the ring vertices of the body's faces.
    A road along a boundary keeps the level of the shape it is welded to
    (08r-2), so the vertices on its FAR edge — apronB's ring, A's label —
    are NOT in apronB's mean: under the face-ring reading they were, and
    B's datum pulled the road off A's level (the red twin's 0.24-0.29 m
    ``service_road|service_road`` rows).  No vertex is in two means."""
    from auto_patch_v2.planar import shapes as S
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.solve.design import DesignReport, assemble
    airport, cells = _road_along_a_boundary(law)
    pm, st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    base = assemble(pm, cs, law, DesignReport())
    assert st.shapes.shapes >= 2, st.shapes.by_shape
    road = next(f for f in pm.faces.values() if f.ref == "road")
    A = pm.shape_of_face[road.id]
    B = next(pm.shape_of_face[f.id] for f in pm.faces.values()
             if f.ref == "apronB" and f.id in pm.shape_of_face)
    assert A != B, "the road's shape and its neighbour must be two bodies"
    assert all(pm.shape_of_vertex.get(v, S.NO_SHAPE) == A
               for v in S._face_vertices(pm, road.id)), \
        "08r-2: the whole road is welded to A"
    # RE-SCOPED (owner RULINGS 2026-09-10v (2)): a body carries THREE rows
    # (mean + two first moments), so a column legitimately sits in three
    # ROWS — of ONE body.  The ruling's invariant is unchanged and is read
    # off the BODIES: no vertex is in two bodies' fits.
    body_of: dict[int, int] = {}
    for k, m in enumerate(base.body_meta):
        for v in m.vertices:
            assert body_of.setdefault(v, k) == k, \
                "a vertex entered two bodies' datum fits"
    b_bodies = {body_of.get(v) for v, sh in pm.shape_of_vertex.items() if sh == B}
    b_bodies.discard(None)
    assert b_bodies, "apronB must carry a datum body"
    # the road's FAR edge: apronB's ring vertices, A's label (08r-2)
    far = [v for v in S._face_vertices(pm, road.id)
           if any(pm.faces[f].ref == "apronB"
                  for f in pm.vertices[v].incident_faces)]
    assert far, "the fixture must share the road's far edge with apronB"
    for v in far:
        assert body_of.get(v) not in b_bodies, \
            "a far-edge vertex the road owns entered apronB's fit"
