"""M2 twins: the constraint generators on a small synthetic planar map,
the assemble/solve round trip, the IIS naming a contradictory pin pair,
the osm writer's mesh-read contract, and v2 verify against the v1
census on v2's own patch (the row-set diff; skipped without the shared
data repo)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import GENERATORS, generate, stack
from auto_patch_v2.constraints import (apron, no_step, pads, precedence,
                                       roads, runway_profile, strips, taxi,
                                       transverse, zones)
from auto_patch_v2.constraints.geometry import (TransectAxis, TransectShape,
                                                long_axis, principal_axis,
                                                walk_transects)
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import SIDECAR_KEYS, write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.constraints import (ConstraintSet, Diff, Flat,
                                             Linear, Pin, Source)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, solve_design
from auto_patch_v2.verify import census

ROOT = Path(__file__).resolve().parents[2]


# ── the synthetic airport: one runway, a parallel taxiway, an apron with
#    a pad, on a sloping DEM ─────────────────────────────────────────────

class _PlaneDem:
    provenance = {"synthetic": "plane 1 % up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.01 * x + 0.002 * y

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def synthetic(law):
    # off the graticule: a vertex ON a tile line is a seam DEM pin (seams.py)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _PlaneDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(-200, 103, 200, 250), (), None, None,
             "airside", "apron", {}),
        Cell(4, "building", "pad1", _rect(-60, 200, 60, 250), (), None, None,
             "airside", "pad", {}),
        Cell(5, "service_road", "road1", _rect(200, 103, 230, 250), (), None,
             None, "groundside", "road", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5))),
            CutLine("taxi_centerline", "stubB", ((0.0, 0.0), (0.0, 91.5))),
            CutLine("road_centerline", "road1", ((215.0, 103.0), (215.0, 250.0))))
    cl = Classification(cells, cuts, {}, ())
    pm, stats = build(airport, cl, law)
    return airport, pm, stats


# ── generators, one twin each ────────────────────────────────────────────

def test_precedence_derives_tiers_from_the_tables(law):
    from auto_patch_v2.law import tables
    gov = tables.governed_roles(law)
    ungov = tables.ungoverned_roles(law)
    assert "runway" in gov and "apron" in gov and "building" in gov
    assert "graded_strip" in ungov and "retaining_wall" in ungov
    assert not set(gov) & set(ungov)
    assert pads.rigid_roles(law) == ("building",)
    assert "building" not in no_step.no_step_roles(law)


def test_runway_generator_pins_profile_and_crown(synthetic, law):
    airport, pm, _ = synthetic
    rows = runway_profile.runway_profile(pm, law, airport)
    pins = [r for r in rows if isinstance(r, Pin)]
    assert sorted(p.z for p in pins) == [700.0, 706.0]
    diffs = [r for r in rows if isinstance(r, Diff)]
    caps = {round(d.cap, 4) for d in diffs}
    # ICAO code 3: the end-zone cap binds precision approaches only and no
    # CIFP category is loaded, so the body cap governs end to end
    assert caps == {0.015}
    crown = runway_profile.runway_crown(pm, law, airport)
    assert crown and all(isinstance(r, Linear) and r.lo is None for r in crown)
    drops = runway_profile.crown_drops(pm, law, airport)
    assert max(drops.values()) == pytest.approx(0.01 * 22.5, abs=1e-3)
    for r in rows + crown:
        assert r.source.generator == "runway_profile" and r.source.inputs


def test_taxi_apron_road_pair_populations(synthetic, law):
    airport, pm, _ = synthetic
    taxi_roles = set(law.tables.precedence.taxi_family.members)
    t = [r for r in taxi.taxi_chain(pm, law, airport)
         if pm.faces[int(r.source.inputs[0][5:])].role in taxi_roles]
    # a hop is priced at the face's transverse cap over the perpendicular
    # distance (06p (2)): a Diff to a station, a three-term Linear to a
    # virtual foot — the graph's own LATERAL caps say which
    from auto_patch_v2.constraints.routes import LATERAL, routes
    g = routes(pm, law, airport)
    assert t and {round(float(c), 9) for c, k, f in zip(g.cap, g.kind, g.face)
                  if k == LATERAL and pm.faces[int(f)].role in taxi_roles} == {0.015}
    assert {round(r.cap, 9) for r in t if isinstance(r, Diff)} <= {0.015}
    c = taxi.taxi_centerlines(pm, law, airport)
    assert c and all(isinstance(r, Diff) for r in c)
    a = apron.apron_within_shape(pm, law, airport)
    # THE TIERED APRON LAW (owner 2026-09-06w): every apron pair is HARD at
    # 1.5 % and carries the 1 % PREFERENCE row beside it; no 5 % (the
    # back-edge class is not modelled yet); body chords stop at the gate
    hard = [r for r in a if r.soft is None]
    pref = [r for r in a if r.soft is not None]
    assert {r.cap for r in hard} == {0.015} and {r.cap for r in pref} == {0.01}
    assert len(hard) == len(pref) and all(r.ceiling is None for r in pref)
    assert law.tables.common.apron_fan_ramp_max not in {r.cap for r in a}
    body = [r for r in a if r.source.ruling.startswith("apron body chord")]
    assert body and all(r.d <= law.tables.emit.within_shape.apron_body_chord_max_m for r in body)
    rd = roads.road_within_shape(pm, law, airport)
    # the road touches the apron (1 %) and the taxiway (1.5 %): lateral
    # contiguity binds each road face at the strictest touching class
    assert {r.cap for r in rd} <= {0.08, 0.02, 0.015}
    assert roads.road_law_caps(pm, law)
    assert any(r.source.ruling.startswith("road_cross_section") for r in rd)


def test_transverse_generator_matches_the_walk(synthetic, law):
    airport, pm, _ = synthetic
    axes = transverse.axes(pm, law)
    assert axes and any(a.is_service for a in axes) and any(not a.is_service for a in axes)
    rows = transverse.transverse(pm, law, airport)
    assert rows
    for r in rows:
        assert isinstance(r, Linear) and 2 <= len(r.terms) <= 4
        assert abs(sum(c for _v, c in r.terms)) < 1e-9        # a difference row
        assert r.lo == -r.hi


def test_no_step_pairs_and_rate(synthetic, law):
    airport, pm, _ = synthetic
    edges = no_step.no_step_edges(pm, law)
    assert edges and all(d <= law.tables.emit.no_step.window_m for *_x, d in edges)
    rate = no_step.no_step_rate(pm, law, airport)
    assert rate and all(len(r.terms) == 3 for r in rate)


def test_zone_bands_are_relative_and_pocket_ruled(synthetic, law):
    airport, pm, _ = synthetic
    rows = zones.zone_bands(pm, law, airport)
    assert rows
    for r in rows:
        assert isinstance(r, Linear) and r.terms[0][1] == 1.0
        assert r.lo is None or r.lo < 0.0
        assert r.hi is None or r.hi < 0.0                  # mandatory down
    strip = {v for f in pm.faces.values() if f.role == "graded_strip"
             for v in pm.ring_vertices(f.ring)}
    bound = {r.terms[0][0] for r in rows}
    pav = precedence.view(pm, law).pavement_vertices
    assert bound <= strip - pav


def test_strip_families_and_pads(synthetic, law):
    airport, pm, _ = synthetic
    vw = precedence.view(pm, law)
    g = strips.runway_groups(vw, airport)
    assert len(g) == 1 and g[0].code_number == 3 and len(g[0].rings) == 3
    assert strips.strip_longitudinal(pm, law, airport)
    assert strips.strip_arc(pm, law, airport)
    assert isinstance(strips.raoa(pm, law, airport), list)   # ICAO: runs (may be empty here)
    flats = pads.pad_flats(pm, law, airport)
    assert len(flats) == 1 and isinstance(flats[0], Flat)
    pad_face = next(f for f in pm.faces.values() if f.role == "building")
    assert set(pm.ring_vertices(pad_face.ring)) <= set(flats[0].group)


# ── assemble / solve / IIS ───────────────────────────────────────────────

def test_assemble_solve_emit_verify_round_trip(synthetic, law, tmp_path):
    airport, pm, _ = synthetic
    cs, counts, _w = generate(pm, law, airport)
    # every generator's count, plus a generator's own ``<name>.<stat>`` keys
    # (apron_within_shape.chords_outside_face, RULINGS 2026-09-05ae(1))
    assert {k.split(".", 1)[0] for k in counts} == {n for n, _f in GENERATORS} | {"seam_pin_pair_exempt", "structure_datum_withdrawn"}
    assert "apron_within_shape.chords_outside_face" in counts
    sol = solve_design(pm, cs, law)[0]
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    assert sol.residual is not None
    z = sol.z
    for p in cs.pins:
        assert z[p.v] == pytest.approx(p.z, abs=1e-6)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, z)
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    assert paths.patch.exists() and paths.sidecar.exists()
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))
    fired = {k: len(v) for k, v in rows.items() if v}
    # THE CENSUS REPORTS, THE SOLVE AIMS (RULINGS 2026-09-08t).  Under the
    # design surface every family but the runway's is a TARGET, so this twin
    # no longer reads "nothing fires": it reads that what fires is what the
    # solve itself reports as MISSED, and that the DEFECT families — the
    # runway laws the solve holds as constraints — read zero.
    from auto_patch_v2.verify.census import DEFECT_KEYS
    assert not [k for k in DEFECT_KEYS if rows.get(k)], {k: len(rows[k]) for k in DEFECT_KEYS}
    assert fired, "the fixture's residual classes are reported, never hidden"


def test_bench_style_instance_round_trip(law):
    """A benchmark-style instance (the solver-benchmark generator's
    shape: a jittered grid over a ridged DEM, breakline chains under
    caps, pins along a profile, a flat group, bands) assembled through
    v2's own stack: the feasible instance solves under 1 s at 2.5k
    vertices; the infeasible variant reports INFEASIBLE with an IIS."""
    import random
    from auto_patch_v2.model.planar import (Breakline, Edge, EdgeKind, Face,
                                            PlanarMap, Vertex)
    rnd = random.Random(1)
    n_side = 50
    verts, edges, faces = {}, {}, {}
    vid = 0
    ids = {}
    for i in range(n_side):
        for j in range(n_side):
            x, y = i * 20.0 + rnd.uniform(-3, 3), j * 20.0 + rnd.uniform(-3, 3)
            dem = 700.0 + 40.0 * math.exp(-((x - 500) ** 2) / 8e4) + 0.005 * y
            ids[(i, j)] = vid
            verts[vid] = Vertex(vid, (x, y), (60.5 + y * 9e-6, -135.5 + x * 1.8e-5),
                                dem, ())
            vid += 1
    eid = 0
    def edge(a, b, L, R):
        nonlocal eid
        edges[eid] = Edge(eid, min(a, b), max(a, b), L, R, EdgeKind.BOUNDARY)
        eid += 1
        return eid - 1
    fid = 0
    ring_edges = {}
    for i in range(n_side - 1):
        for j in range(n_side - 1):
            a, b, c, d = ids[(i, j)], ids[(i + 1, j)], ids[(i + 1, j + 1)], ids[(i, j + 1)]
            ring_edges[fid] = (a, b, c, d)
            fid += 1
    # one edge per pair, both faces named
    pair_faces: dict = {}
    for f, (a, b, c, d) in ring_edges.items():
        for u, v in ((a, b), (b, c), (c, d), (d, a)):
            pair_faces.setdefault((min(u, v), max(u, v)), []).append(f)
    eids = {}
    for (u, v), fs in pair_faces.items():
        eids[(u, v)] = edge(u, v, fs[0], fs[1] if len(fs) > 1 else None)
    inc: dict = {v: set() for v in verts}
    for f, (a, b, c, d) in ring_edges.items():
        cyc = tuple(eids[(min(u, v), max(u, v))] for u, v in ((a, b), (b, c), (c, d), (d, a)))
        role = "runway" if 20 <= f // (n_side - 1) <= 22 else "apron"
        faces[f] = Face(f, role, f"q{f}", cyc, (), 4 if role == "runway" else None,
                        "D" if role == "runway" else None)
        for v in (a, b, c, d):
            inc[v].add(f)
    for v in verts:
        verts[v] = Vertex(v, verts[v].xy, verts[v].key, verts[v].dem_z, tuple(sorted(inc[v])))
    chain = [ids[(i, 21)] for i in range(n_side)]
    bl = Breakline(0, "runway_profile", "rwy", tuple(
        eids[(min(a, b), max(a, b))] for a, b in zip(chain, chain[1:])))
    pm = PlanarMap("BENCH", verts, edges, faces, {0: bl})
    src = Source("bench", "synthetic", ())
    rows = [Pin(chain[0], 700.0, src), Pin(chain[-1], 712.0, src)]
    for a, b in zip(chain, chain[1:]):
        rows.append(Diff(a, b, 0.0125, math.dist(verts[a].xy, verts[b].xy), src))
    for (u, v) in eids:
        rows.append(Diff(u, v, 0.05, math.dist(verts[u].xy, verts[v].xy), src))
    rows.append(Flat(tuple(ids[(i, j)] for i in range(5, 8) for j in range(5, 8)), src))
    cs = ConstraintSet.from_rows(rows)
    sol = solve_design(pm, cs, law)[0]
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    # 08t: the law rows are TARGETS of a least-squares solve, so the
    # certificate reports a residual instead of a feasibility proof — the
    # PINS are exact (the equalities), the rest is the surface's own answer
    assert sol.wall_s < 5.0
    assert sol.residual.max_pin_m < 1e-6 and sol.residual.max_flat_m < 1e-6
    assert sol.residual.max_m < 0.5, sol.residual
    bad = ConstraintSet.from_rows(rows + [Pin(chain[1], 720.0, Source("bad", "x", ()))])
    sol2 = solve_design(pm, bad, law)[0]
    # 08t: no infeasible branch — the contradiction is a RESIDUAL the
    # certificate names (the pin the fixture added cannot be met with the law)
    assert sol2.residual is not None and sol2.residual.max_m > 1.0


# ── the osm writer's mesh-read contract ──────────────────────────────────

def test_osm_writer_contract(synthetic, law, tmp_path):
    airport, pm, _ = synthetic
    cs, *_r = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    paths = write_patch(surf, law, tmp_path, pub)
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")          # v1: the oracle's reader
    feats: dict = {}
    nodes, ways = cg._parse_osm(paths.patch, feature_out=feats)
    assert len(nodes) == len(pm.vertices)              # one node per vertex
    assert all(w.nids[0] == w.nids[-1] for w in ways)  # rings closed
    assert all(w.role for w in ways) and all(w.elevs[0] is not None for w in ways)
    assert "crown_spine" in feats
    runway = [w for w in ways if w.role == "runway"]
    assert runway and all(w.tags.get("o4_single_poly") == "1" for w in runway)
    side = json.loads(paths.sidecar.read_text())
    assert set(side) <= set(SIDECAR_KEYS)
    assert side["ruleset"] == law.ruleset_key and side["axes"] and side["crown_drops"]
    with pytest.raises(ValueError):
        write_patch(surf, law, tmp_path / "bad", {"not_a_key": []})


# ── verify == the v1 census on v2's own CYXY patch (row-set diff) ────────

DATA = Path("/Users/noah/XPTerrainBuilderData")


@pytest.mark.skipif(not (DATA / "Elevation_data").is_dir(), reason="shared data repo")
def test_cyxy_verify_matches_v1_census(tmp_path):
    from auto_patch_v2.pipeline.build import Config, build as build_v2
    from auto_patch_v2.planar.__main__ import default_inputs
    res = build_v2("CYXY", default_inputs(), tmp_path, Config())
    assert res.solution.status in (Status.OPTIMAL, Status.FEASIBLE)
    assert res.wall["total"] < 10.0
    sys.path.insert(0, str(ROOT / "tools" / "harness"))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    fam: dict = {}
    cg.run_checks_law_true(res.paths.patch, family_out=fam, quiet=True, top_n=0)
    # RULINGS 2026-09-08d (2): a row a yielding family holds above its cap
    # is counted APART on both readers (oracle: ``yielded_by_08d`` out of
    # scope; v2 verify: ``yielded_by``) — the lockstep is over the rest
    from auto_patch_v2.verify.census import YIELDED_KEY
    v1 = {k: n for k, n in ((k, sum(1 for r in v if getattr(r, "out_of_scope", None)
                                    != cg.YIELDED_OUT_OF_SCOPE))
                            for k, v in fam.items() if not k.startswith("_") and v) if n}
    v2 = {k: n for k, n in ((k, sum(1 for r in v if not r.get(YIELDED_KEY)))
                            for k, v in res.verify_rows.items() if v) if n}
    # the families v2 reads must agree with the oracle's counts wherever
    # both read the same population; a v1 family v2 has no reader for is
    # listed in verify.census.NOT_IMPLEMENTED
    from auto_patch_v2.verify.census import NOT_IMPLEMENTED
    # THE LOCKSTEP UNDER THE DESIGN SURFACE (RULINGS 2026-09-08t).  Every law
    # but the runway family's is now a TARGET, so the built surface carries
    # rows sitting a few centimetres either side of their caps instead of
    # inside them, and the two readers' pair POPULATIONS (the oracle's
    # proximity join, v2's identity join) no longer coincide row for row on a
    # family where dozens of rows hover at the bound.  The lockstep the twin
    # keeps: both readers see the same FAMILIES, within a stated tolerance of
    # each other, and the DEFECT families — the runway laws the solve holds as
    # CONSTRAINTS (RULINGS 2026-09-08v) — read ZERO on both.
    from auto_patch_v2.verify.census import DEFECT_KEYS
    for k, n in v1.items():
        if k in NOT_IMPLEMENTED:
            continue
        got = v2.get(k, 0)
        if k in DEFECT_KEYS:
            assert got == 0 == n, (k, n, got)
            continue
        assert abs(got - n) <= max(2, 0.2 * n) or k in ("within_shape",), (k, n, got)
    for k in DEFECT_KEYS:
        assert not res.verify_rows.get(k), (k, res.verify_rows.get(k))
