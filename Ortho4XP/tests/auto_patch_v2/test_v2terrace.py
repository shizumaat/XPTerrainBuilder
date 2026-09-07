"""Twins for RULINGS 2026-09-06n (lane v2terrace): two apron cells no taxi
route joins are SEPARATE TERRACES — the vertices along their shared
boundary are split in the planar map, no row is priced across the joint,
the joint is declared in the sidecar ``terrace_joints`` and both censuses
read the emitted step as lawful; the same two cells with a taxilane
crossing the boundary are one terrace; a cell's inside chords are
unchanged; a joint inside the runway strip is never split."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints import apron, pads
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff, Flat, Linear, Offset, Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.verify.census import census_patch
from auto_patch_v2.verify.frame import Patch

ROOT = Path(__file__).resolve().parents[2]


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _StepDem:
    """Flat, 3 m higher east of x = 0 — the hangar terrace's own ground."""

    provenance = {"synthetic": "700 west of x=0, 703 east"}

    def z(self, x: float, y: float) -> float:
        return 703.0 if x > 0.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, cells, cuts, dem=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, dem or _StepDem(), law.ruleset_key)
    pm, stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    return airport, pm, stats


#: the aprons stand beyond the code-3 strip (75 m) so the keep-out never
#: touches the joint; the stub's centreline ENTERS apron A only
Y0, Y1 = 120.0, 170.0
CELLS = [
    Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {}),
    Cell(1, "stub", "stubA", _rect(-111.5, 22.5, -88.5, Y0), (), None, "D", "airside", "taxi", {}),
    Cell(2, "apron", "apronA", _rect(-200, Y0, 0, Y1), (), None, None, "airside", "apron", {}),
    Cell(3, "apron", "apronB", _rect(0, Y0, 200, Y1), (), None, None, "airside", "apron", {}),
]
STUB = CutLine("taxi_centerline", "stubA", ((-100.0, 0.0), (-100.0, Y0 + 25.0)))
LANE = CutLine("taxi_centerline", "laneAB", ((-100.0, Y0 + 25.0), (100.0, Y0 + 25.0)))


@pytest.fixture(scope="module")
def unjoined(law):
    return _airport(law, CELLS, [STUB])


@pytest.fixture(scope="module")
def joined(law):
    return _airport(law, CELLS, [STUB, LANE])


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _ids_of(row) -> tuple[int, ...]:
    if isinstance(row, (Diff, Offset)):
        return (row.a, row.b)
    if isinstance(row, Linear):
        return tuple(v for v, _c in row.terms)
    if isinstance(row, Flat):
        return tuple(row.group)
    return (row.v,)


# ── 1. no route across: split vertices, a joint declared, no row across ──

def test_two_cells_no_route_joins_are_split_and_declared(unjoined, law):
    airport, pm, stats = unjoined
    A, B = _face(pm, "apronA"), _face(pm, "apronB")
    ts = stats.terraces
    assert ts.joints == 1 and ts.refused_strip == 0 and ts.refused_map == 0, ts
    assert pm.terrace_group[A.id] != pm.terrace_group[B.id]
    (j,) = pm.terrace_joints
    assert {j.a, j.b} == {A.id, B.id}
    assert len(j.run) >= 2 and len(j.pairs) == len(j.run), j
    assert abs(j.length_m - (Y1 - Y0)) < 1.0
    gap = law.tables.emit.terrace.joint_gap_m
    for ia, ib in j.pairs:
        assert ia != ib
        (xa, ya), (xb, yb) = pm.vertices[ia].xy, pm.vertices[ib].xy
        assert abs(math.hypot(xa - xb, ya - yb) - gap) < 1e-6
        assert pm.vertices[ia].key != pm.vertices[ib].key
    # the two rings share NO vertex any more
    ra = set(pm.ring_vertices(A.ring))
    rb = set(pm.ring_vertices(B.ring))
    assert not ra & rb
    assert ts.split_vertices == len(j.pairs)
    # no row of any generator joins the two sides of a pair
    cs, counts, _w = generate(pm, law, airport)
    across = {frozenset(p) for p in j.pairs}
    for r in cs.rows():
        ids = set(_ids_of(r))
        for p in across:
            assert not p <= ids, (r.source.generator, r.source.ruling, sorted(ids))
    # and no row at all joins a vertex of A to a vertex of B
    for r in cs.rows():
        ids = set(_ids_of(r))
        assert not (ids & ra and ids & rb), (r.source.generator, sorted(ids))
    # the island (B: no station) attaches to no route — no reach band, no
    # no_step pair on its copies; A keeps its stub attachment
    from auto_patch_v2.constraints.routes import routes
    g = routes(pm, law, airport)
    assert not (rb & g.nodes)
    assert ra & g.nodes


def test_the_emitted_step_is_lawful_in_both_censuses(unjoined, law, tmp_path):
    airport, pm, _stats = unjoined
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    (j,) = pm.terrace_joints
    steps = [abs(sol.z[a] - sol.z[b]) for a, b in j.pairs]
    assert max(steps) > 1.0, steps                 # B floats to its own ground: a real step
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    assert len(pub["terrace_joints"]) == 1
    rec = pub["terrace_joints"][0]
    assert rec["step_m"] >= max(steps) - 0.011 and len(rec["points"]) == len(j.run)
    assert rec["kind"] == "apron_terrace" and rec["faced"] is True
    # v2 verify: the step readers forgive the declared step; nothing else fires across it
    p = Patch.of(surf, law, pub)
    rows = census_patch(p)
    for fam in ("vertex_to_edge_step", "mid_edge_step", "cross_shape", "stacked_nodes",
                "within_shape", "airside_no_step"):
        assert not rows[fam], (fam, rows[fam][:2])
    # the same patch read with the declaration withheld prices the step
    p0 = Patch.of(surf, law, {k: v for k, v in pub.items() if k != "terrace_joints"})
    rows0 = census_patch(p0)
    assert rows0["vertex_to_edge_step"] or rows0["mid_edge_step"]
    # the v1 oracle over the written patch: the joint is a declared terrace
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    sys.path.insert(0, str(ROOT / "tools" / "harness"))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    ctx = cg.law_context_from_sidecar(paths.patch)
    assert ctx["terrace_joints_ll"] and len(ctx["terrace_joints_ll"]) == 1
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    for key in ("terrace_joint_route", "terrace_joint_strip", "terrace_actual_step",
                "vertex_to_edge_step", "mid_edge_step", "cross_shape", "stacked_nodes"):
        assert not fam.get(key), (key, fam.get(key)[:2])
    fam0: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam0, quiet=True, top_n=0,
                           terrace_joints_ll=None)
    assert fam0.get("vertex_to_edge_step") or fam0.get("mid_edge_step")


# ── 2. a taxilane across: coupled along the lane only ────────────────────

def test_a_taxilane_crossing_the_boundary_joins_the_cells(joined, law):
    airport, pm, stats = joined
    A, B = _face(pm, "apronA"), _face(pm, "apronB")
    assert stats.terraces.joints == 0 and not pm.terrace_joints
    assert pm.terrace_group[A.id] == pm.terrace_group[B.id]
    ra, rb = set(pm.ring_vertices(A.ring)), set(pm.ring_vertices(B.ring))
    shared = ra & rb
    assert shared, "the cells share their boundary vertices"
    from auto_patch_v2.constraints.routes import routes
    g = routes(pm, law, airport)
    assert rb & g.nodes, "B attaches to the lane"
    # the lane's station on the boundary is what joins them
    station = {v for b in pm.breaklines.values() if b.kind == "taxi_centerline"
               for v in b.vertices(pm)}
    assert shared & station


# ── 3. a cell's inside chords are unchanged ──────────────────────────────

def test_the_island_cell_keeps_its_inside_chords(unjoined, law):
    airport, pm, _stats = unjoined
    B = _face(pm, "apronB")
    rb = list(pm.ring_vertices(B.ring))
    rows = [r for r in apron.apron_within_shape(pm, law, airport)
            if f"face:{B.id}" in r.source.inputs]
    assert rows and all(set((r.a, r.b)) <= set(rb) for r in rows)
    # the CONTROL: the same cell standing alone (no neighbour, nothing to
    # split) prices the same population — ring edges and the chords inside
    # the body gate; the joint changed no inside chord
    _ap, pm1, st1 = _airport(law, [CELLS[0], CELLS[3]], [])
    assert st1.terraces.joints == 0
    B1 = _face(pm1, "apronB")
    rows1 = [r for r in apron.apron_within_shape(pm1, law, _ap)
             if f"face:{B1.id}" in r.source.inputs]
    assert len(rows1) == len(rows), (len(rows1), len(rows))
    assert sorted(round(r.cap, 6) for r in rows1) == sorted(round(r.cap, 6) for r in rows)
    assert max(abs(a.d - b.d) for a, b in zip(sorted(rows1, key=lambda r: r.d),
                                             sorted(rows, key=lambda r: r.d))) <= 1.0
    # the island's rim retreated by the gap and nothing else moved
    xs = sorted({round(pm.vertices[v].xy[0], 3) for v in rb})
    assert 0.0 < xs[0] <= law.tables.emit.terrace.joint_gap_m and xs[-1] == 200.0


# ── 4. a joint inside the runway strip is never split ────────────────────

def test_a_joint_inside_the_runway_strip_stays_welded(law):
    cells = [
        CELLS[0],
        Cell(1, "stub", "stubA", _rect(-111.5, 22.5, -88.5, 40), (), None, "D", "airside", "taxi", {}),
        Cell(2, "apron", "apronA", _rect(-200, 40, 0, 90), (), None, None, "airside", "apron", {}),
        Cell(3, "apron", "apronB", _rect(0, 40, 200, 90), (), None, None, "airside", "apron", {}),
    ]
    _airport_, pm, stats = _airport(law, cells, [CutLine("taxi_centerline", "stubA",
                                                        ((-100.0, 0.0), (-100.0, 65.0)))])
    A, B = _face(pm, "apronA"), _face(pm, "apronB")
    assert pm.terrace_group[A.id] != pm.terrace_group[B.id]
    assert stats.terraces.refused_strip > 0 and stats.terraces.joints == 0
    assert set(pm.ring_vertices(A.ring)) & set(pm.ring_vertices(B.ring))


# ── 5. a pad across the joint belongs to one cell; no frontage across ────

def test_a_pad_on_the_island_never_fronts_the_other_cell(law):
    pad = _rect(0.8, Y0 + 10, 40, Y0 + 40)          # inside B, 0.8 m off the joint
    cells = CELLS[:3] + [
        Cell(3, "apron", "apronB", _rect(0, Y0, 200, Y1), (pad,), None, None, "airside", "apron", {}),
        Cell(4, "building", "hangar", pad, (), None, None, "airside", "pad", {}),
    ]
    airport, pm, stats = _airport(law, cells, [STUB])
    A, B, H = _face(pm, "apronA"), _face(pm, "apronB"), _face(pm, "hangar")
    assert stats.terraces.joints == 1
    assert pm.terrace_group[H.id] == pm.terrace_group[B.id] != pm.terrace_group[A.id]
    ra = set(pm.ring_vertices(A.ring))
    for e, jv, pid, _d, _cap, sf in pads.frontage_contacts(pm, law):
        assert sf != A.id and e not in ra, "no frontage across the joint"


def test_the_law_table_carries_the_terrace_keys(law):
    tt = law.tables.emit.terrace
    assert tt.cell_roles == ("apron",) and "junction" in tt.neighbour_roles
    assert tt.joint_gap_m > law.tables.emit.identity.min_distinct_spacing_m
    assert tt.max_step_m > 0.0
