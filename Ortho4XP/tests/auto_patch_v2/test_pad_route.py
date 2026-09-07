"""Twins for the PAD CONTACT law (lane v2padroute; RULINGS 2026-09-04r
under 03h/03i + 04o): a pad↔pavement no-step pair exists only FROM the
pad's contact vertices (the rim vertices shared with airside pavement)
TO pavement reachable along pavement inside the route window, priced
Σ cap·len along that path — never a free-standing chord from the pad's
body; a detached pad has no pairs; the sidecar and v2 verify read one
population.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, no_step
from auto_patch_v2.constraints.routes import route_path, routes
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.highs import solve
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.no_step import no_step_direct


class _RampDem:
    provenance = {"synthetic": "plane 2 % in y"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.02 * max(0.0, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _dense_rect(x0, y0, x1, y1, step):
    """A rectangle ring with a vertex every ``step`` m (an apron rim at
    emit spacing: the contact's K nearest must spill past the pavement
    list's own K)."""
    pts = []
    for (ax, ay), (bx, by) in zip(_rect(x0, y0, x1, y1), _rect(x0, y0, x1, y1)[1:] + _rect(x0, y0, x1, y1)[:1]):
        n = max(1, int(round(math.hypot(bx - ax, by - ay) / step)))
        pts.extend((ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n))
    return tuple(pts)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def site(law):
    """test_routes' loop (apron 17.5 m north of the runway, joined to it
    only by ~830 m of taxiway) plus TWO pads: ``pad1`` ATTACHED along the
    apron's south edge, its body 2.5 m from the runway edge (a chord pair
    well inside the window — the refuted population); ``pad2`` DETACHED
    east of the apron, touching nothing.  The stub's 1202 taxilane runs
    through the apron TO THE STAND (its cut ends on pad1's frontage at
    (−100, 40)): under RULINGS 2026-09-05aa the apron's vertices attach
    to that lane by lateral hops, so the contacts' route neighbourhood
    is the frontage and the lane — a lane ending 60 m short would leave
    every contact's K nearest already in the pavement list."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubE", _rect(488.5, 22.5, 511.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiA", _rect(-120, 190, 520, 213), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "stub", "stubW", _rect(-111.5, 140, -88.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(4, "apron", "apron1", _dense_rect(-200, 40, 0, 140, 5.0), (), None, None,
             "airside", "apron", {}),
        Cell(5, "building", "pad1", _rect(-150, 25, -100, 40), (), None, None,
             "airside", "pad", {}),
        Cell(6, "building", "pad2", _rect(20, 60, 60, 100), (), None, None,
             "airside", "pad", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubE", ((500.0, 0.0), (500.0, 201.5))),
            CutLine("taxi_centerline", "taxiA", ((-100.0, 201.5), (500.0, 201.5))),
            CutLine("taxi_centerline", "stubW", ((-100.0, 40.0), (-100.0, 201.5))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _verts(pm, ref):
    return {v for f in pm.faces.values() if f.ref == ref
            for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}


def _role_verts(pm, role):
    return {v for f in pm.faces.values() if f.role == role
            for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}


def test_contact_is_the_shared_frontage_and_a_detached_pad_has_none(site, law):
    _a, pm = site
    contacts = no_step.pad_contacts(pm, law)
    pad1 = next(f.id for f in pm.faces.values() if f.ref == "pad1")
    pad2 = next(f.id for f in pm.faces.values() if f.ref == "pad2")
    assert pad1 in contacts and pad2 not in contacts
    apron = _role_verts(pm, "apron")
    assert set(contacts[pad1]) == _verts(pm, "pad1") & apron
    assert all(abs(pm.vertices[v].xy[1] - 40.0) < 1e-9 for v in contacts[pad1])
    assert len(_verts(pm, "pad1") - apron) >= 2               # the body exists


def test_pad_pairs_leave_the_contact_only_along_pavement(site, law):
    _a, pm = site
    g = routes(pm, law)
    pav = no_step.no_step_edges(pm, law)
    pad = no_step.pad_pavement_edges(pm, law, pav)
    assert pad, "an attached pad's contact must pair along its apron"
    contacts = set(no_step.pad_contacts(pm, law)[
        next(f.id for f in pm.faces.values() if f.ref == "pad1")])
    body = _verts(pm, "pad1") - contacts
    detached = _verts(pm, "pad2")
    runway = _role_verts(pm, "runway")
    rw_edge = [v for v in runway if abs(pm.vertices[v].xy[1] - 22.5) < 1e-9
               and -150 <= pm.vertices[v].xy[0] <= -100]
    assert rw_edge and all(
        min(math.hypot(pm.vertices[b].xy[0] - pm.vertices[r].xy[0],
                       pm.vertices[b].xy[1] - pm.vertices[r].xy[1]) for r in rw_edge)
        < law.tables.emit.no_step.window_m for b in body), "the refuted chord was in the window"
    every = pav + pad
    # no pad-body vertex and no detached-pad vertex is an endpoint anywhere
    assert not any(a in body or b in body or a in detached or b in detached
                   for a, b, *_ in every)
    # no pad↔runway pair at all: the pad reaches the runway only by the loop
    assert not any((a in _verts(pm, "pad1")) and b in runway or
                   (b in _verts(pm, "pad1")) and a in runway for a, b, *_ in every)
    own = _verts(pm, "pad1")
    seen = {(a, b) for a, b, *_ in pav}
    for a, b, cap, d in pad:
        c, u = (a, b) if a in contacts else (b, a)
        assert c in contacts and u not in own and u in g.nodes
        assert (a, b) not in seen                              # not the pavement list's
        assert d <= law.tables.emit.no_step.window_m + 1e-9
        rp = route_path(g, a, b, max_len=law.tables.emit.no_step.window_m)
        assert rp is not None
        dist, bud, _p = rp
        assert dist == pytest.approx(d, abs=1e-6)
        assert cap * d == pytest.approx(bud, abs=1e-6)         # Σ cap·len along the path
    apron_cap = law.ruleset.apron.longitudinal if hasattr(law.ruleset, "apron") else None
    apron = _role_verts(pm, "apron")
    on_apron = [cap for a, b, cap, _d in pad
                if (a in apron and b in apron) and a not in _role_verts(pm, "stub")
                and b not in _role_verts(pm, "stub")]
    # the apron's cap along the apron's own edges; a path walking the
    # lane THROUGH the apron carries the lane's taxiway cap on that part
    # (RULINGS 2026-09-06t, lane v2routecap) — never below the apron cap,
    # never above the lane's letter
    # (RULINGS 2026-09-06w: the apron's HARD cap is 1.5 %, the taxiway's)
    from auto_patch_v2.law.tables import role_cap
    apron_cap = role_cap(law, "apron").longitudinal
    lane_cap = law.ruleset.taxi.longitudinal.value(None, None)
    assert on_apron and all(min(apron_cap, lane_cap) - 1e-9 <= c <= max(apron_cap, lane_cap) + 1e-9
                            for c in on_apron), on_apron
    assert any(c == pytest.approx(apron_cap) for c in on_apron)


def test_pad_pairs_are_apron_law_in_the_solve(site, law):
    """The pad rows belong to the contact's owner (the apron tier), never
    the ungoverned tier the chord population sat in (HECA tier 8)."""
    from auto_patch_v2.law import tables
    from auto_patch_v2.solve.tiers import row_tier
    airport, pm = site
    cs, _c, _w = generate(pm, law, airport)
    tt = tables.tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    lowest = len(tt) - 1
    rows = [d for d in cs.diffs if "pad contact" in d.source.ruling]
    assert rows
    assert {row_tier(pm, r, tier_of, lowest) for r in rows} <= {tier_of["apron"], tier_of["stub"]}


def test_sidecar_and_verify_read_the_pad_population(site, law):
    airport, pm = site
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS)
    assert sol.status.value == "optimal"
    pub = publication(pm, law, airport, sol.z)
    pav = no_step.no_step_edges(pm, law)
    pad = no_step.pad_pavement_edges(pm, law, pav)
    assert len(pub["pad_pavement_no_step_edges"]) == len(pad)
    ll = {vid: [v.key[0], v.key[1]] for vid, v in pm.vertices.items()}
    for rec, (a, b, cap, d) in zip(pub["pad_pavement_no_step_edges"], pad):
        assert rec["a"] == ll[a] and rec["b"] == ll[b]
        assert rec["dist_m"] == pytest.approx(d, abs=1e-4)
        assert rec["budget_m"] == pytest.approx(cap * d, abs=1e-6)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    assert no_step_direct(Patch.of(surf, law, pub, {})) == []
    a, b, cap, d = pad[0]
    z = list(sol.z)
    z[b] += cap * d + 1.0
    surf2 = graded_surface(pm, law, _dc.replace(sol, z=z), airport.frame.origin,
                           airport.frame.crs, {})
    rows = no_step_direct(Patch.of(surf2, law, pub, {}))
    assert rows and all(r["family"] == "airside_no_step" for r in rows)


@pytest.fixture(scope="module")
def near_miss(law):
    """The ``site`` plus ``pad3``: a pad 0.7 m NORTH of the apron's edge
    (a sub-metre source gap inside ``frontage_near_miss_m``, welded to
    nothing) — RULINGS 2026-09-05ab: it attaches to the route graph at
    its CONTACT, the frontage row's apron vertex, so its pair rows reach
    the pavement through the apron exactly as a welded rim's do."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    gap = 0.7
    assert gap < law.tables.structures.building_pad.frontage_near_miss_m
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubE", _rect(488.5, 22.5, 511.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiA", _rect(-120, 190, 520, 213), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "stub", "stubW", _rect(-111.5, 140, -88.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(4, "apron", "apron1", _dense_rect(-200, 40, 0, 140, 5.0), (), None, None,
             "airside", "apron", {}),
        Cell(5, "building", "pad3", _rect(-60, 140 + gap, -30, 160), (), None, None,
             "airside", "pad", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubE", ((500.0, 0.0), (500.0, 201.5))),
            CutLine("taxi_centerline", "taxiA", ((-100.0, 201.5), (500.0, 201.5))),
            CutLine("taxi_centerline", "stubW", ((-100.0, 40.0), (-100.0, 201.5))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def test_near_miss_pad_attaches_at_its_contact_and_keeps_its_pair_rows(near_miss, law):
    """§9 twin (RULINGS 2026-09-05ab): the near-miss pad's rim vertices
    on the frontage are CONTACTS; the graph joins each to its apron
    vertex by one CONTACT edge; the pad's pair rows leave through it
    along the pavement; a walk from the pad passes THROUGH the contact."""
    from auto_patch_v2.constraints.pads import frontage_contacts
    from auto_patch_v2.constraints.routes import CONTACT, route_path
    airport, pm = near_miss
    pad = next(f.id for f in pm.faces.values() if f.ref == "pad3")
    fc = [c for c in frontage_contacts(pm, law) if c[2] == pad]
    assert fc, "the 0.7 m gap is a near-miss frontage"
    pad_v = {c[1] for c in fc}
    apron_v = {c[0] for c in fc}
    assert pad_v <= _verts(pm, "pad3") and apron_v <= _role_verts(pm, "apron")
    assert not (_verts(pm, "pad3") & _role_verts(pm, "apron"))       # welded to nothing
    contacts = no_step.pad_contacts(pm, law)
    assert pad in contacts and set(contacts[pad]) == pad_v
    g = routes(pm, law, airport)
    assert pad_v <= g.nodes
    expect = {}
    for e, j, _pid, d, _cap, _sf in sorted(fc, key=lambda c: (c[3], c[0])):
        expect.setdefault(j, e)                       # the least gap is the doorway
    assert {p: g.contact_of[p] for p in pad_v} == expect and set(g.contact_of) >= pad_v
    n_contact = sum(1 for k in g.kind if k == CONTACT)
    assert n_contact == len(pad_v) == g.stats["contact"]
    # the doorway is the least gap (the endpoint straight across the
    # 0.7 m sliver); the same ring edge's far endpoint fires 5 m away
    gap_m = max(c[3] for c in fc if c[0] == expect[c[1]] and c[1] in pad_v)
    assert 0.4 < gap_m < 0.8              # the map snaps the 0.7 m gap to its identity grid
    pav = no_step.no_step_edges(pm, law, airport)
    pairs = no_step.pad_pavement_edges(pm, law, pav, airport)
    mine = [(a, b, c, d) for a, b, c, d in pairs if a in pad_v or b in pad_v]
    assert mine, "the near-miss pad's contacts pair along the pavement"
    taxi_v = _role_verts(pm, "primary_parallel") | _role_verts(pm, "stub")
    assert any((a in taxi_v) or (b in taxi_v) for a, b, _c, _d in mine), \
        "the pad reaches the taxiway through its apron"
    # a walk from the pad starts through its contact and never returns
    p0 = min(pad_v)
    far = max(taxi_v & g.nodes, key=lambda v: pm.vertices[v].xy[0])
    d, bud, path = route_path(g, p0, far)
    assert path[0] == p0 and path[1] == g.contact_of[p0] and p0 not in path[1:]
    assert d >= gap_m - 1e-6
    # every pad pair is priced exactly as a pavement pair along its path
    for a, b, cap, dd in mine:
        r = route_path(g, a, b)
        assert r is not None and r[0] == pytest.approx(dd, abs=1e-6)
        assert cap * dd == pytest.approx(r[1], abs=1e-6)
