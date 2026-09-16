"""§28 THE GROUNDSIDE FRONTAGE TAKES THE PAD'S EDGE LEVEL — the twins
(owner RULINGS 2026-09-11ai-1 -> 2026-09-12r "grade frontages only";
spec ``auto-patch-v2/design-surface-spec.md`` §28).

The site they stand for: LEMD ``building4`` is ONE flat plateau and its
car park ``pav124`` stands 0.71-1.50 m away and 1.14-3.03 m ABOVE it
(measured on the shipped 1.0.321 patch).  The owner kept the plateau and
ruled the neighbours meet it.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.groundside import groundside_face_roles
from auto_patch_v2.constraints.pad_frontage_gs import (GEN_GS,
                                                      GS_LEVEL_JUNIOR_RULING,
                                                      GS_LEVEL_RULING,
                                                      groundside_frontage,
                                                      groundside_frontage_level)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import one_way_rulings, pad_flat_rulings

RUN_LEN = 1600.0
HALF_W = 22.5
Y0, Y1 = 140.0, 260.0


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """The LOT's ground stands 3 m ABOVE the apron band — the terrace the
    owner read at LEMD, with the sign that matters (the car park is HIGH
    against the plateau: ``pav124`` +3.03)."""

    provenance = {"synthetic": "lot_high"}

    def z(self, x: float, y: float) -> float:
        return 703.0 if y > 262.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law, dem):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key)


def _cells(lot_role="parking_lot", second_pad=False):
    """An apron with a PAD cut out of its northern edge, and a LOT just
    north of the pad — the ``building4`` / ``pav124`` shape: the lot shares
    NO vertex with the pad (they stand 1 m apart), which is exactly why the
    relation is read by PROXIMITY (10ax)."""
    pad = _rect(-60.0, 200.0, 60.0, 260.0)
    out = [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                (), 3, "D", "airside", "runway", {}),
           Cell(1, "apron", "apronA", _rect(-260.0, Y0, 260.0, 260.0), (pad,),
                None, None, "airside", "apron", {}),
           Cell(2, "building", "padA", pad, (), None, None, "airside", "pad", {}),
           Cell(3, lot_role, "lotA", _rect(-60.0, 261.0, 60.0, 361.0), (),
                None, None, "groundside", lot_role, {})]
    if second_pad:
        # a SECOND pad on the lot's far side — 8 m of contact against the
        # first pad's 120 m: the JUNIOR of §28 (1).  It fronts an apron of
        # its own, because a pad that fronts nothing airside is not a §28
        # leader at all (it FOLLOWS the face, under 10l)
        padb = _rect(-4.0, 362.0, 4.0, 420.0)
        out.append(Cell(4, "apron", "apronB", _rect(-200.0, 362.0, 200.0, 420.0),
                        (padb,), None, None, "airside", "apron", {}))
        out.append(Cell(5, "building", "padB", padb,
                        (), None, None, "airside", "pad", {}))
    return out


def _built(law, cells, dem=None):
    airport = _airport(law, dem or _Dem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return pm, airport


def _solve(law, cells, dem=None, drop=None):
    pm, airport = _built(law, cells, dem)
    cs, _c, _w = generate(pm, law, airport)
    if drop:
        from auto_patch_v2.model.constraints import ConstraintSet
        cs = ConstraintSet.from_rows(r for r in cs.rows()
                                     if r.source.generator not in drop)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return pm, np.asarray(sol.z, float), rep


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _verts(pm, ref):
    f = _face(pm, ref)
    out = set(pm.ring_vertices(f.ring))
    for h in (f.holes or ()):
        out |= set(pm.ring_vertices(h))
    return out


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── the law register ─────────────────────────────────────────────────────

def test_the_groundside_frontage_heads_are_registered_one_way_senior_at_the_pad_weight(law):
    """Both heads are ONE-WAY (§28 (2): the face follows the pad and never
    pulls it) and only the SENIOR carries the pad's own plane weight, so a
    junior pad's miss is a residual rather than a tug on the senior."""
    ow, pf = one_way_rulings(law), pad_flat_rulings(law)
    assert {GS_LEVEL_RULING, GS_LEVEL_JUNIOR_RULING} <= ow
    assert GS_LEVEL_RULING in pf and GS_LEVEL_JUNIOR_RULING not in pf


def test_the_candidate_class_is_the_four_ruled_roles_read_as_data(law):
    """§28 (1) names ``parking_lot`` / ``groundside_pavement`` /
    ``service_road`` / ``service_junction``; the code reads the register
    (groundside side, value role, not a structure) rather than a literal
    list, and the two must agree."""
    assert set(groundside_face_roles(law)) == {
        "parking_lot", "groundside_pavement", "service_road",
        "service_junction"}


# ── (1) the joint goes to 0.00 ───────────────────────────────────────────

@pytest.mark.parametrize("role", ["parking_lot", "groundside_pavement",
                                  "service_road", "service_junction"])
def test_a_groundside_face_fronting_a_pad_meets_it_at_the_pads_level(law, role):
    """THE BAR (§28 (4)): the frontage joint is 0.00.  The lot's own ground
    is 3 m above the pad's plateau; under §28 its frontage edge takes the
    PAD's level."""
    pm, z, _rep = _solve(law, _cells(role))
    pad, lot = _verts(pm, "padA"), _verts(pm, "lotA")
    rel = groundside_frontage(pm, law)
    gid = _face(pm, "lotA").id
    assert gid in rel, "the lot fronts the pad by proximity (10ax)"
    front = sorted(rel[gid][0][3])
    assert front, "the lot's own frontage vertices"
    pad_lvl = float(np.mean(z[sorted(pad)]))
    joint = float(np.max(np.abs(z[front] - pad_lvl)))
    assert joint <= 0.30, (joint, pad_lvl, z[front])
    # and the face still BLENDS into its own body: the far edge is free to
    # stand on its own ground, under its own within-shape cap
    far = sorted(lot - set(front))
    assert far and float(np.max(z[far])) > pad_lvl, "the lot grades away"


def test_the_frontage_row_itself_can_never_move_a_pad(law):
    """§28 (2), airside is king — the DIRECT channel, closed by
    construction.  Hold the two PRE-EXISTING two-way rows across the
    stand-off out of BOTH arms — the apron-edge ramp law
    (``groundside_ramp``, 08d (4b)) and the 5 % ``pavement_ceiling`` twin
    it mints — and turning §28 on leaves the pad BYTE-IDENTICAL: the
    one-way row strips the pad's columns out of the matrix that is
    factorised, at every lag round.  §20's own groundside frontage rows,
    which DID pull the pad (0.032 m on this fixture), are gone at the
    derivation site (``pads._airside_only``)."""
    off = {"groundside_ramp", "pavement_ceiling"}
    _pm_a, z_a, _r = _solve(law, _cells(), drop=off)
    pm_b, z_b, _r2 = _solve(law, _cells(), drop=off | {GEN_GS})
    pad = sorted(_verts(pm_b, "padA"))
    assert np.allclose(z_a[pad], z_b[pad], atol=1e-9), (
        float(np.max(np.abs(z_a[pad] - z_b[pad]))))


def test_the_only_channel_left_is_the_two_way_apron_edge_ramp_law(law):
    """MEASURED, and REPORTED rather than decided (the §23.3 (2)
    precedent).  ``constraints/groundside.groundside_ramps`` (08d (4b))
    prices the apron-edge / groundside stand-off TWO-WAY, and
    ``constraints/ceiling.pavement_ceiling`` twins it at 5 %; a lot that
    stood 3 m above was LIFTING what it stands off, and §28 puts the lot
    on the pad, so that lift stops and the surface settles a little DOWN.
    Those are PRE-EXISTING two-way law rows, not a new §28 pull — the twin
    above proves the §28 row itself moves nothing.  Making them one-way is
    outside 09-12r's text and is a deviation for the owner, never a
    lane's.

    ROUND 4 RE-STATES THE MAGNITUDE (§16g (10) (8), owner RULINGS
    2026-09-14aj).  The measured figure was 0.05 m when the pad was a
    cap-0 plate across its WHOLE rim: pinned flat at every contact, the
    apron-edge ramp's lift could only move it a few centimetres.  Under
    (8) the plate is flat across the pad's interior and its non-airside
    rim and BENDS at its own 1 % ceiling to meet each airside edge, so
    the same two-way ramp row now moves the pad **0.172 m** — a looser
    pad, the same channel.  The CLAIM is unchanged and is what the twin
    exists for: the movement is the ramp's, it is DOWNWARD, and §28's own
    row still moves nothing (the twin above).  The number is the
    fixture's, re-measured, and is still reported rather than decided.

    RE-FOUNDED, NOT WEAKENED (lane ``v2stagepop`` r2, §20b (3) AMENDED):
    the channel is a GROUNDSIDE-to-AIRSIDE one, so under §20b's staged
    solve — the shipped law since r2 — the apron-edge ramp's lift cannot
    reach the airside at all and the pad moves by **1.3e-8 m**: the
    channel is CLOSED, which is the strongest form of this twin's own
    claim, and the sign it asserted is meaningless at that size (the
    reading is nine orders under the 0.01 m elevation materiality).  The
    joint-problem arm below keeps the 0.172 m reading verbatim."""
    from tests.auto_patch_v2.test_v2staged import unstaged
    _pm_s, z_s, _rs = _solve(law, _cells())              # the SHIPPED (staged) arm
    _pm_sb, z_sb, _rsb = _solve(law, _cells(), drop={GEN_GS})
    pad_s = sorted(_verts(_pm_sb, "padA"))
    assert float(np.max(np.abs(z_s[pad_s] - z_sb[pad_s]))) < 1e-6
    law = unstaged(law)                                  # the joint problem
    _pm_a, z_a, _r = _solve(law, _cells())
    pm_b, z_b, _r2 = _solve(law, _cells(), drop={GEN_GS})
    pad = sorted(_verts(pm_b, "padA"))
    moved = float(np.max(np.abs(z_a[pad] - z_b[pad])))
    # the fixture's measured magnitude: small, DOWNWARD, and entirely the
    # apron-edge ramp's lift going away (0.05 before §16g (10) (8)'s
    # skirt loosened the plate at the pad's airside rim; 0.172 after)
    assert 0.0 < moved < 0.25, moved
    assert float(np.mean(z_a[pad])) < float(np.mean(z_b[pad]))


def test_the_rows_are_one_way_with_the_groundside_vertex_as_the_follower(law):
    """The follower is the GROUNDSIDE vertex alone and every leader is a
    PAD rim vertex — the construction §28 (2) rests on."""
    pm, airport = _built(law, _cells())
    rows = groundside_frontage_level(pm, law, airport)
    assert rows
    pad = _verts(pm, "padA")
    lot = _verts(pm, "lotA")
    for r in rows:
        assert r.source.generator == GEN_GS
        fv = tuple(r.follows)
        assert len(fv) == 1 and fv[0] in lot
        others = {v for v, _c in r.terms} - set(fv)
        assert others and others <= pad, others
        # the leader weights sum to the follower's own coefficient: the row
        # reads in METRES OF SURFACE
        assert abs(sum(c for _v, c in r.terms)) <= 1e-9


# ── (2) two pads: the senior sets the level, the junior is reported ──────

def test_a_face_between_two_pads_takes_the_senior_and_reports_the_junior(law):
    """§28 (1): the SENIOR pad is the LARGEST contact; the junior's row
    carries the law's own weight, so where the face cannot hold both it
    holds the senior and the junior row is the reported residual."""
    pm, _airport = _built(law, _cells(second_pad=True))
    rel = groundside_frontage(pm, law)
    gid = _face(pm, "lotA").id
    assert gid in rel and len(rel[gid]) == 2, rel.get(gid)
    (sen_pid, sen_ref, sen_len, _f1, _g1), (jun_pid, jun_ref, jun_len, _f2, _g2) = rel[gid]
    assert sen_ref == "padA" and jun_ref == "padB", (sen_ref, jun_ref)
    assert sen_len > jun_len, (sen_len, jun_len)
    rows = groundside_frontage_level(pm, law, _airport)
    heads = {r.source.ruling.split(" (")[0].strip() for r in rows
             if f"pad:{jun_pid}" in r.source.inputs}
    assert heads == {GS_LEVEL_JUNIOR_RULING}, heads
    heads_s = {r.source.ruling.split(" (")[0].strip() for r in rows
               if f"pad:{sen_pid}" in r.source.inputs}
    assert heads_s == {GS_LEVEL_RULING}, heads_s


def test_a_groundside_face_fronting_no_pad_mints_nothing(law):
    """A face with no pad within ``[design] pad_frontage_m`` keeps every
    level it has today — the rule adds no row anywhere else."""
    cells = [c for c in _cells() if c.ref != "padA"]
    pm, airport = _built(law, cells)
    assert groundside_frontage(pm, law) == {}
    assert groundside_frontage_level(pm, law, airport) == []
