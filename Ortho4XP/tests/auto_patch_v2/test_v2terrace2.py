"""Twins for RULINGS 2026-09-07c (lane v2terrace2, spec §4): an apron cell
whose two route contacts disagree by more than the apron cap can hold
along the in-shape path between them is CUT into two terraces — the cut
declared as a joint, the pieces in different groups, no row across, the
census reading the step as lawful; the same cell with agreeing contacts
stays one terrace; one contact / no contact are 06n unchanged."""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.no_step import reach_band_values
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff, Flat, Linear, Offset
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.territories import terrace_territories
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.verify.census import census_patch
from auto_patch_v2.verify.frame import Patch


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _StepDem:
    """700 west of x = 0, 715 east — each terrace has its own ground to
    settle to (the runway stays at its 700 pins)."""

    provenance = {"synthetic": "700 west of x=0, 715 east"}

    def z(self, x: float, y: float) -> float:
        return 715.0 if x > 0.0 and y > 60.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, cells, cuts):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, _StepDem(), law.ruleset_key)
    cl = Classification(tuple(cells), tuple(cuts), {}, ())
    pm, _stats = build(airport, cl, law)
    bands = reach_band_values(pm, law, airport)
    pm2, stats = terrace_territories(pm, law, airport, cl, bands)
    return airport, pm2, stats, bands


#: the apron stands beyond the code-3 strip keep-out; the west stub is a
#: short route from the runway, the east route an L-shaped taxiway whose
#: length sets how far the two contacts' ceilings disagree
Y0, Y1 = 120.0, 180.0
RUNWAY = Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {})
APRON = Cell(1, "apron", "apron", _rect(-150, Y0, 150, Y1), (), None, None, "airside", "apron", {})
STUB_W = Cell(2, "stub", "stubW", _rect(-161.5, 22.5, -138.5, Y0), (), None, "D", "airside", "taxi", {})
CUT_W = CutLine("taxi_centerline", "stubW", ((-150.0, 0.0), (-150.0, Y0 + 25.0)))


def _east(top: float):
    ring = ((588.5, 22.5), (611.5, 22.5), (611.5, top + 11.5), (138.5, top + 11.5),
            (138.5, Y1), (161.5, Y1), (161.5, top - 11.5), (588.5, top - 11.5))
    cell = Cell(3, "stub", "stubE", ring, (), None, "D", "airside", "taxi", {})
    cut = CutLine("taxi_centerline", "stubE", ((600.0, 0.0), (600.0, top), (150.0, top), (150.0, Y1 - 25.0)))
    return cell, cut


def _ids_of(row):
    if isinstance(row, (Diff, Offset)):
        return (row.a, row.b)
    if isinstance(row, Linear):
        return tuple(v for v, _c in row.terms)
    if isinstance(row, Flat):
        return tuple(row.group)
    return (row.v,)


def _apron_faces(pm):
    return [f for f in pm.faces.values() if f.ref == "apron"]


# ── 1. two contacts disagreeing beyond the hold: a joint across the cell ──

@pytest.fixture(scope="module")
def disagreeing(law):
    cell, cut = _east(900.0)           # ~1,700 m east route vs ~150 m west: ≈ 23 m apart by ceiling
    return _airport(law, [RUNWAY, APRON, STUB_W, cell], [CUT_W, cut])


def test_disagreeing_contacts_cut_the_cell_into_two_terraces(disagreeing, law):
    airport, pm, stats, bands = disagreeing
    tt = law.tables.emit.terrace
    pieces = _apron_faces(pm)
    assert stats.cut_cells == 1 and stats.seams == 1 and len(pieces) == 2, (stats.cuts, stats.refused_why)
    (seam,) = stats.seam_pairs
    a, b, ca, cb, over = seam
    d = stats.joints[0][3]
    assert abs(ca - cb) > 0.015 * d + tt.min_step_m, seam
    assert over > 0.0
    # the two pieces are different groups and share no vertex any more
    g = pm.terrace_group
    assert g[pieces[0].id] != g[pieces[1].id]
    r0 = set(pm.ring_vertices(pieces[0].ring))
    r1 = set(pm.ring_vertices(pieces[1].ring))
    assert not r0 & r1
    # the joint is declared with the cut path as its run, every vertex split
    joints = [j for j in pm.terrace_joints if {j.a, j.b} == {pieces[0].id, pieces[1].id}]
    assert len(joints) == 1
    (j,) = joints
    assert len(j.pairs) == len(j.run) >= 2, j
    gap = tt.joint_gap_m
    for ia, ib in j.pairs:
        (xa, ya), (xb, yb) = pm.vertices[ia].xy, pm.vertices[ib].xy
        assert abs(math.hypot(xa - xb, ya - yb) - gap) < 1e-6
    assert stats.welded_cut_vertices == 0
    # each piece holds the contacts of ONE stub (west of x = 0 or east of it)
    station = {x for bl in pm.breaklines.values() if bl.kind == "taxi_centerline"
               for x in bl.vertices(pm)}
    per_piece = [sorted(v for v in pm.ring_vertices(f.ring) if v in station and v in bands)
                 for f in pieces]
    assert all(c for c in per_piece), per_piece
    sides = [{pm.vertices[v].xy[0] < 0.0 for v in c} for c in per_piece]
    assert all(len(sd) == 1 for sd in sides) and sides[0] != sides[1], per_piece
    assert {pm.vertices[a].xy[0] < 0.0, pm.vertices[b].xy[0] < 0.0} == {True, False}
    # no row of any generator joins a vertex of one piece to the other
    cs, _c, _w = generate(pm, law, airport)
    for r in cs.rows():
        ids = set(_ids_of(r))
        assert not (ids & r0 and ids & r1), (r.source.generator, sorted(ids))


def test_the_cut_step_is_lawful_in_the_census(disagreeing, law):
    airport, pm, _stats, _bands = disagreeing
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    pieces = _apron_faces(pm)
    (j,) = [j for j in pm.terrace_joints if {j.a, j.b} == {pieces[0].id, pieces[1].id}]
    steps = [abs(sol.z[a] - sol.z[b]) for a, b in j.pairs]
    assert max(steps) > 1.0, steps                  # each terrace solves to its own contact
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    rec = [r for r in pub["terrace_joints"] if set(r["faces"]) == {pieces[0].id, pieces[1].id}]
    assert len(rec) == 1 and rec[0]["kind"] == "apron_terrace"
    assert rec[0]["step_m"] >= max(steps) - 0.011
    p = Patch.of(surf, law, pub)
    rows = census_patch(p)
    for fam in ("vertex_to_edge_step", "mid_edge_step", "cross_shape", "stacked_nodes",
                "within_shape", "airside_no_step"):
        assert not rows[fam], (fam, rows[fam][:2])
    p0 = Patch.of(surf, law, {k: v for k, v in pub.items() if k != "terrace_joints"})
    rows0 = census_patch(p0)
    assert rows0["vertex_to_edge_step"] or rows0["mid_edge_step"]


# ── 2. agreeing contacts: one terrace, no cut ────────────────────────────

def test_agreeing_contacts_keep_one_terrace(law):
    cell, cut = _east(200.0)           # ≈ 500 m east route: the cap holds the difference across 300 m
    _airport_, pm, stats, _bands = _airport(law, [RUNWAY, APRON, STUB_W, cell], [CUT_W, cut])
    assert stats.contacts >= 2 and stats.joint_pairs == 0 and stats.cut_cells == 0, stats.joints
    assert len(_apron_faces(pm)) == 1
    assert not pm.terrace_joints


# ── 3. one contact / no contact: 06n unchanged ───────────────────────────

def test_one_contact_is_no_partition(law):
    _airport_, pm, stats, _bands = _airport(law, [RUNWAY, APRON, STUB_W], [CUT_W])
    assert stats.contacts >= 1 and stats.joint_pairs == 0 and stats.cut_cells == 0 and stats.seams == 0
    assert len(_apron_faces(pm)) == 1 and not pm.terrace_joints


def test_no_contact_is_an_island(law):
    _airport_, pm, stats, _bands = _airport(law, [RUNWAY, APRON], [])
    assert stats.contacts == 0 and stats.cut_cells == 0
    assert stats.terraces_split.islands == 1 and not pm.terrace_joints
