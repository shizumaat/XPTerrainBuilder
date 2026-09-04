"""M5 twins (RULINGS 2026-09-04i, the law-ordered solve; 03i tiers):

* the tier ladder derives from the tables — runway family, taxi family,
  the singleton governed roles in ``order``, then the ungoverned + rigid
  roles last, no role list in code;
* an apron between two taxiways over 10 m of DEM relief solves OPTIMAL
  in the HARD set — taxiways within 1.5 %, apron within 1 %, the pad one
  flat value on its apron contact, no IIS (the DEM is a preference);
* a second runway PINNED 30 m above the first, reachable only through
  the taxi/apron chain (lawful reach ≈ 22 m: the runways may bend ±9 m), makes the hard set
  infeasible: the tiered solve holds both runways on their pins and
  every taxi row at 1.5 % (the taxi tier stays HARD — the apron and the
  pads close the gap), the apron (junior) yields, the pads follow, no
  IIS;
* a runway whose CIFP pins contradict its own cap stays infeasible in
  the tiered solve and the IIS names tier-0 rows only;
* pad↔pavement no-step pairs are published, pad-only↔pad-only never.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, no_step, precedence
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import is_rigid_role, role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Linear, Offset, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, displacement_by_role
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.tiers import demote, solve_law_ordered


class _Dem:
    """10 m of relief across the apron (y 103 → 300), flat elsewhere."""

    provenance = {"synthetic": "10 m ramp across the apron"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 10.0 * min(1.0, max(0.0, (y - 103.0) / 197.0))

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, second_runway_z: tuple[float, float] | None, rw1=(700.0, 706.0)):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, rw1[0], "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, rw1[1], "fixture"))
    runways = [Runway("09/27", 45.0, 1, ends, 3, "D")]
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(-200, 103, 200, 300), (), None, None,
             "airside", "apron", {}),
        Cell(4, "building", "pad1", _rect(-60, 150, 60, 200), (), None, None,
             "airside", "pad", {}),
        Cell(5, "secondary_parallel", "taxiC", _rect(-400, 300, 400, 323), (), None,
             "D", "airside", "taxi", {}),
        # a DETACHED pad beside the apron: its vertices touch no pavement
        Cell(8, "building", "pad2", _rect(230, 150, 290, 200), (), None, None,
             "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5))),
            CutLine("taxi_centerline", "stubB", ((0.0, 0.0), (0.0, 91.5))),
            CutLine("taxi_centerline", "taxiC", ((-400.0, 311.5), (400.0, 311.5)))]
    if second_runway_z is not None:
        e2 = (RunwayEnd("09R", (-600.0, 372.5), (60.5, -135.5), 0.0, 0.0,
                        second_runway_z[0], "fixture"),
              RunwayEnd("27L", (600.0, 372.5), (60.5, -135.5), 0.0, 0.0,
                        second_runway_z[1], "fixture"))
        runways.append(Runway("09R/27L", 45.0, 1, e2, 3, "D"))
        cells.append(Cell(6, "runway", "09R/27L", _rect(-600, 350, 600, 395), (), 3,
                          "D", "airside", "runway", {}))
        cells.append(Cell(7, "stub", "stubD", _rect(-11.5, 323, 11.5, 350), (), None,
                          "D", "airside", "taxi", {}))
        cuts.append(CutLine("taxi_centerline", "stubD", ((0.0, 311.5), (0.0, 372.5))))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, tuple(runways), (), (), {},
                      (), (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)
    pm, _stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    return airport, pm


def _over_cap(cs, sol, generators: set[str]) -> float:
    """Worst metres over cap among the named generators' Diff rows —
    the law's OWN population (an apron body chord beyond the gate is not
    a grade path, apron.py)."""
    worst = 0.0
    for d in cs.diffs:
        if d.source.generator in generators:
            worst = max(worst, abs(sol.z[d.a] - sol.z[d.b]) - d.cap * d.d)
    return worst


def test_tiers_derive_from_the_tables(law):
    tt = precedence.tiers(law)
    p = law.tables.precedence
    assert set(tt[0]) == set(p.runway_family.members)
    assert set(tt[1]) == set(p.taxi_family.members)
    assert all(precedence.is_governed(law, r) and not is_rigid_role(law, r)
               for t in tt[:-1] for r in t)
    assert {"building", "graded_strip", "retaining_wall"} <= set(tt[-1])
    assert all(role_cap(law, r) is None or is_rigid_role(law, r) for r in tt[-1])
    # every registered role is in exactly one tier, in the table's order
    flat = [r for t in tt for r in t]
    assert sorted(flat) == sorted(p.roles) and len(flat) == len(set(flat))
    named = [r for r in p.order if r in flat[:-len(tt[-1])]]
    assert [precedence.role_tier(law, r) for r in named] == sorted(
        precedence.role_tier(law, r) for r in named)


def test_apron_between_taxiways_over_relief_is_feasible_hard(law):
    airport, pm = _airport(law, None)
    cs, _counts, _w = generate(pm, law, airport)
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.OPTIMAL and not sol.iis
    assert rep.mode == "hard" and not rep.yielded
    assert _over_cap(cs, sol, {"taxi"}) <= 1e-6
    assert _over_cap(cs, sol, {"apron"}) <= 1e-6
    pad = next(f for f in pm.faces.values() if f.role == "building")
    zs = [sol.z[v] for v in pm.ring_vertices(pad.ring)]
    assert max(zs) - min(zs) < 1e-6                       # one flat value
    moved = displacement_by_role(pm, law, sol)
    assert moved["apron"]["over"] > 0                     # the apron left the 10 m DEM ramp


def test_pinned_runways_make_the_apron_yield_not_the_taxiways(law):
    airport, pm = _airport(law, (730.0, 736.0))
    cs, _counts, _w = generate(pm, law, airport)
    pins = [p for p in cs.pins]
    assert sorted(p.z for p in pins) == [700.0, 706.0, 730.0, 736.0]
    size: dict = {}
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options(), size_out=size)
    assert sol.status is Status.OPTIMAL and not sol.iis, sol.message
    assert rep.mode == "tiered" and rep.demoted > 0
    apron_tier = precedence.role_tier(law, "apron")
    assert precedence.role_tier(law, "stub") < rep.k_min <= apron_tier   # taxi hard, apron soft
    assert all(k >= rep.k_min for k in rep.yielded)
    # the search tried a depth that kept the apron hard and found it infeasible,
    # and its first attempt was the cheap one: the lowest tier alone
    assert any(k > apron_tier and st == "infeasible" for k, st, _w in rep.attempts)
    assert rep.attempts[0][0] == len(precedence.tiers(law)) - 1
    for p in pins:                                        # tier 0 held exactly
        assert abs(sol.z[p.v] - p.z) < 1e-6
    assert _over_cap(cs, sol, {"taxi"}) <= 1e-6
    assert _over_cap(cs, sol, {"runway_profile", "runway"}) <= 1e-6
    # the apron carried the relief the chain cannot span lawfully
    assert _over_cap(cs, sol, {"apron"}) > 0.3
    assert apron_tier in rep.yielded and rep.yielded[apron_tier]["rows"] > 0
    assert precedence.role_tier(law, "stub") not in rep.yielded
    for pad in (f for f in pm.faces.values() if f.role == "building"):
        zs = [sol.z[v] for v in pm.ring_vertices(pad.ring)]
        assert max(zs) - min(zs) < 1e-6
    assert "escalation" in size and not any(g.startswith("law:") for g in size["escalation"])


def test_iis_names_tier_zero_only(law):
    airport, pm = _airport(law, None, rw1=(700.0, 760.0))   # 5 % over 1,200 m
    cs, _counts, _w = generate(pm, law, airport)
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.INFEASIBLE and rep.mode == "tiered"
    assert sol.iis
    tt = precedence.tiers(law)
    for row, src in sol.iis:                          # inside ONE surface: the runway's
        assert isinstance(row, (Pin, Diff))
        for v in ((row.v,) if isinstance(row, Pin) else (row.a, row.b)):
            assert any(pm.faces[f].role in tt[0] for f in pm.vertices[v].incident_faces)


def test_demote_keeps_tier_zero_hard_and_prices_the_rest(law):
    airport, pm = _airport(law, (730.0, 736.0))
    cs, _c, _w = generate(pm, law, airport)
    cs2, demoted = demote(pm, law, cs)
    assert len(cs2.pins) == 4 and len(cs2.flats) == len(cs.flats)
    tt = precedence.tiers(law)

    def on_runway(v: int) -> bool:
        return any(pm.faces[f].role in tt[0] for f in pm.vertices[v].incident_faces)

    hard_diffs = [d for d in cs2.diffs if d.soft is None]
    assert hard_diffs and all(
        d.source.generator in ("runway_profile", "runway") or (on_runway(d.a) and on_runway(d.b))
        for d in hard_diffs)
    # k_min keeps the tiers above it hard: demoting the apron and below leaves taxi rows hard
    cs3, _d3 = demote(pm, law, cs, precedence.role_tier(law, "apron"))
    assert any(d.soft is None and d.source.generator == "taxi" for d in cs3.diffs)
    assert not any(d.soft is None and d.source.generator == "apron" for d in cs3.diffs)
    soft = [d for d in cs2.diffs if d.soft is not None and d.soft.startswith("law:")]
    assert soft and all(d.ceiling is None for d in soft)
    ranks = {int(d.soft.split(":")[1]) for d in soft}
    n = len(precedence.tiers(law))
    assert ranks <= set(range(n - 1))                     # rank 0 = the lowest tier
    assert len(demoted) == len(soft) + sum(
        1 for ln in cs2.linears if ln.soft is not None and ln.soft.startswith("law:"))


def test_pad_pavement_pairs_join_the_population(law):
    airport, pm = _airport(law, None)
    edges = no_step.no_step_edges(pm, law)
    pad_vs = {v for f in pm.faces.values() if f.role == "building"
              for v in pm.ring_vertices(f.ring)}
    pad_only = {v for v in pad_vs if all(pm.faces[f].role == "building"
                                          for f in pm.vertices[v].incident_faces)}
    assert pad_only, "the fixture's detached pad must have pad-only vertices"
    assert set(no_step.pad_only_vertices(pm, law)) == pad_only
    # the pavement list is the oracle's and carries no pad endpoint
    assert not any(a in pad_only or b in pad_only for a, b, *_ in edges)
    with_pad = no_step.pad_pavement_edges(pm, law)
    assert with_pad and all((a in pad_only) != (b in pad_only) for a, b, *_ in with_pad)
    cap = role_cap(law, "apron").longitudinal
    assert all(abs(c - cap) < 1e-12 for _a, _b, c, _d in with_pad)
    rows = no_step.no_step_pairs(pm, law, airport)
    assert len(rows) == len(edges) + len(with_pad)
    assert "building" in no_step.rigid_airside_roles(law)
    assert "building" not in no_step.no_step_roles(law)


def test_demote_turns_an_off_tier_offset_into_a_preference(law):
    """An ``Offset`` (a deck clearance, KCLT's bridges) off tier 0 becomes a
    one-sided ``Linear`` preference; on tier 0 it stays (measured KCLT:
    the first M5 replay crashed on ``Offset.soft``)."""
    airport, pm = _airport(law, None)
    apron = next(f for f in pm.faces.values() if f.role == "apron")
    a, b = pm.ring_vertices(apron.ring)[:2]
    rw = next(f for f in pm.faces.values() if f.role == "runway")
    ra, rb = pm.ring_vertices(rw.ring)[:2]
    src = Source("structures", "bridge.clearance_m", ())
    cs = ConstraintSet.from_rows([Offset(a, b, 5.0, src), Offset(ra, rb, 5.0, src)])
    cs2, demoted = demote(pm, law, cs)
    assert len(cs2.offsets) == 1 and cs2.offsets[0].a == ra
    assert len(cs2.linears) == 1 and len(demoted) == 1
    ln = cs2.linears[0]
    assert ln.soft.startswith("law:") and ln.ceiling is None
    assert ln.lo == 5.0 and ln.hi is None and dict(ln.terms) == {a: 1.0, b: -1.0}


def test_a_mixed_pad_vertex_is_not_pad_only(law):
    """A pad vertex shared with a groundside lot is the lot's (09-01g):
    never paired against airside pavement across the lawful terrace
    (measured SPJC: 7.2 m building|groundside_pavement rows)."""
    airport, pm = _airport(law, None)
    # re-role the detached pad's east neighbour: a groundside lot sharing its east edge
    from auto_patch_v2.classify.roles import Cell, Classification, CutLine
    frame = airport.frame
    cells = list(_cells_of(pm))
    cells.append(Cell(9, "groundside_pavement", "lot1", _rect(290, 150, 350, 200), (), None,
                      None, "groundside", "road", {}))
    pm2, _ = build(airport, Classification(tuple(cells), (), {}, ()), law)
    edges = no_step.no_step_edges(pm2, law) + no_step.pad_pavement_edges(pm2, law)
    shared = {v for v in pm2.vertices
              if {pm2.faces[f].role for f in pm2.vertices[v].incident_faces}
              == {"building", "groundside_pavement"}}
    assert shared
    assert not any(a in shared or b in shared for a, b, *_ in edges)


def _cells_of(pm):
    """The fixture's cells re-read from a planar map's faces (rings only)."""
    from auto_patch_v2.classify.roles import Cell
    for f in pm.faces.values():
        ring = tuple(pm.vertices[v].xy for v in pm.ring_vertices(f.ring))
        yield Cell(f.id, f.role, f.ref, ring, (), f.code_number, f.code_letter, f.side,
                   "pad" if f.role == "building" else f.role, {})


def test_verify_prices_the_pad_pairs_by_identity(law, tmp_path):
    """The round trip with a detached pad: the pad key is published, v2
    verify reads it (identity join) and reads zero on the solved surface;
    an endpoint no shape names is priced, never a reader KeyError
    (measured HECA: the first closing build crashed in verify)."""
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.pipeline.publication import publication
    from auto_patch_v2.verify import census
    from auto_patch_v2.constraints.roads import road_law_caps
    airport, pm = _airport(law, None)
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    assert pub["pad_pavement_no_step_edges"]
    rows = census(surf, law, pub, road_law_caps(pm, law, airport))
    assert rows["airside_no_step"] == []
    # an unknown-role endpoint: the reader still prices it
    from auto_patch_v2.verify.frame import Patch
    from auto_patch_v2.verify.no_step import no_step_direct
    import dataclasses
    p = Patch.of(surf, law, pub, road_law_caps(pm, law, airport))
    p = dataclasses.replace(p, shapes=[sh for sh in p.shapes if sh.role != "building"])
    assert isinstance(no_step_direct(p), list)
