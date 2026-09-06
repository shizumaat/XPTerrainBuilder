"""Lane v2bow2 twins (RULINGS 2026-09-06k):

(2) the junction mesh's plane rows are an ANISOTROPIC BOX along the
    serving stretch — a triangle diagonal to its centreline admits a
    gradient of √2 × cap on the diagonal and refuses beyond it; the cone
    (16 half-planes) refused it at cap · cos(π/16);
(1) ``[relaxation] runway_fit_weight = 0`` restores the 06e relaxation:
    stage 1 with the pipeline's weights IS the pure-variance program at
    the table's default, and carries the runway term only when the key
    is positive;
(3) the ``pad_flat`` reading tolerates the emit quantum: a relaxed pad
    laid EXACTLY at ``pad_slope_max`` and emitted at the coordinate
    quantum is no row.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest

from auto_patch_v2.constraints import junction_mesh as JM, stretches as S, taxi
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.roads import road_law_caps
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Linear, Source
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve import relax
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import FAMILY_PAD_FLAT
from auto_patch_v2.verify.pads import plane_fit_quantum

from test_pad_flat import _product, _published_relaxed_pad
from test_stretches import _junction_parts, site  # noqa: F401  (fixture)
from test_v2bow import hangar_slack  # noqa: F401  (fixture)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _holds(rows, z) -> bool:
    for r in rows:
        v = sum(c * z[i] for i, c in r.terms)
        if (r.lo is not None and v < r.lo - 1e-9) or (r.hi is not None and v > r.hi + 1e-9):
            return False
    return True


# ── (2) the box ──────────────────────────────────────────────────────────

def test_a_diagonal_gradient_passes_the_box_at_root_two_cap_and_fails_beyond():
    """One right triangle served by a centreline along x at cap c (both
    caps c): a plane whose gradient runs along the DIAGONAL at √2 · c has
    components (c, c) — inside the box, outside the cone; at 1.01 · √2 · c
    the box refuses it; the box states exactly TWO two-sided rows."""
    xy = {1: (0.0, 0.0), 2: (60.0, 0.0), 3: (0.0, 60.0)}
    tri = [1, 2, 3]
    cap = 0.015
    src = Source("twin", "box", ())
    box = taxi.box_rows(tri, xy, (1.0, 0.0), cap, cap, src)
    assert len(box) == 2 and all(isinstance(r, Linear) and r.lo == -r.hi for r in box)
    assert {round(r.hi, 9) for r in box} == {round(cap, 9)}
    cone = taxi.plane_rows(tri, xy, cap, src)
    d = 1.0 / math.sqrt(2.0)

    def field(g):  # gradient of magnitude g along the diagonal
        return {v: g * (x * d + y * d) for v, (x, y) in xy.items()}
    assert _holds(box, field(math.sqrt(2.0) * cap))
    assert not _holds(box, field(1.01 * math.sqrt(2.0) * cap))
    assert not _holds(cone, field(math.sqrt(2.0) * cap)), "the cone was the chord law"
    # along the axis the box is the longitudinal cap, across it the transverse
    across = taxi.box_rows(tri, xy, (1.0, 0.0), cap, 0.5 * cap, src)
    assert _holds(across, {v: cap * x for v, (x, _y) in xy.items()})
    assert not _holds(across, {v: 1.01 * cap * x for v, (x, _y) in xy.items()})
    assert _holds(across, {v: 0.5 * cap * y for v, (_x, y) in xy.items()})
    assert not _holds(across, {v: 0.51 * cap * y for v, (_x, y) in xy.items()})
    # the axis direction is free of sign and scale
    assert _holds(taxi.box_rows(tri, xy, (-3.0, 0.0), cap, cap, src), field(math.sqrt(2.0) * cap))
    assert taxi.box_rows(tri, xy, (0.0, 0.0), cap, cap, src) == []
    assert taxi.box_rows([1, 2, 2], xy, (1.0, 0.0), cap, cap, src) == []


def test_junction_triangles_are_boxed_along_their_serving_stretch(site, law):
    """On the stretches fixture (junction J crossed by A's D-lettered
    stretches along y = 91.5 and G's A-lettered stretch along x = 0):
    every triangle carries exactly two two-sided rows, the along axis is
    the nearest stretch's direction (x for A, y for G), the along cap the
    stretch's longitudinal, the across cap its transverse; no isotropic
    cone row remains."""
    airport, pm = site
    st = S.stretches(pm, law)
    vw = view(pm, law)
    caps = {"A": (law.ruleset.taxi.longitudinal.value(None, "A"),
                  law.ruleset.taxi.transverse.value(None, "A")),
            "D": (law.ruleset.taxi.longitudinal.value(None, "D"),
                  law.ruleset.taxi.transverse.value(None, "D"))}
    assert caps["A"][0] > caps["D"][0]
    rows = JM.junction_mesh(pm, law, airport)
    planes = [r for r in rows if isinstance(r, Linear)]
    assert planes and all(r.lo is not None and r.lo == -r.hi for r in planes)
    assert all(len(r.terms) == 3 for r in planes)
    n_tris = 0
    for f in _junction_parts(pm, vw):
        axes = JM.crossing_axes(vw, st, f.id)
        assert {(round(cl, 6), round(ct, 6)) for _p, cl, ct in axes} == \
            {tuple(round(c, 6) for c in caps["A"]), tuple(round(c, 6) for c in caps["D"])}
        tris = JM.face_triangles(vw, f.id)
        boxes = JM.triangle_boxes(vw, axes, tris)
        assert set(boxes) == set(tris)
        n_tris += len(tris)
        for (a, b, c), (axis, cl, ct) in boxes.items():
            cx = (vw.xy[a][0] + vw.xy[b][0] + vw.xy[c][0]) / 3.0
            cy = (vw.xy[a][1] + vw.xy[b][1] + vw.xy[c][1]) / 3.0
            near_g, near_a = abs(cx), cy - 91.5
            letter = "A" if near_g < near_a else "D"
            assert (cl, ct) == pytest.approx(caps[letter])
            ux, uy = axis
            if letter == "A":
                assert abs(uy) == pytest.approx(1.0) and abs(ux) < 1e-9
            else:
                assert abs(ux) == pytest.approx(1.0) and abs(uy) < 1e-9
            # the two rows of this triangle in the generator's output
            mine = [r for r in planes if {v for v, _c in r.terms} == {a, b, c}]
            assert len(mine) == 2
            assert {round(r.hi, 9) for r in mine} == {round(cl, 9), round(ct, 9)}
    # two rows per triangle over the parts' triangles; none of the 16-ray cone
    parts = {f.id for f in _junction_parts(pm, vw)}
    part_rows = [r for r in planes if any(i.startswith("face:") and int(i[5:]) in parts
                                           for i in r.source.inputs)]
    assert len(part_rows) == 2 * n_tris
    assert all("06k-2" in r.source.ruling for r in planes)


def test_a_face_no_stretch_crosses_is_served_by_the_nearest_stretch(law):
    """``triangle_boxes`` with no crossing axis takes the DIRECTION of the
    nearest fallback stretch at the face's own caps; with no stretch at
    all it states no box."""
    xy = {1: (0.0, 0.0), 2: (10.0, 0.0), 3: (0.0, 10.0)}

    class _VW:
        pass
    vw = _VW(); vw.xy = xy
    tris = [(1, 2, 3)]
    diag = ([(50.0, 50.0), (60.0, 60.0)], 0.03, 0.02)
    assert JM.triangle_boxes(vw, [], tris) == {}
    boxes = JM.triangle_boxes(vw, [], tris, [diag], (0.015, 0.01))
    (axis, cl, ct), = boxes.values()
    assert (cl, ct) == (0.015, 0.01)
    assert abs(abs(axis[0]) - math.sqrt(0.5)) < 1e-9 and abs(abs(axis[1]) - math.sqrt(0.5)) < 1e-9
    # a crossing axis wins over the fallback and carries ITS caps
    boxes = JM.triangle_boxes(vw, [diag], tris, [([(0.0, -1.0), (10.0, -1.0)], 0.01, 0.01)],
                              (0.015, 0.01))
    (axis, cl, ct), = boxes.values()
    assert (cl, ct) == (0.03, 0.02)
    # nearest_axis: the strictest longitudinal cap among tied axes
    tie = JM.nearest_axis((5.0, -1.0), [([(0.0, -2.0), (10.0, -2.0)], 0.03, 0.02),
                                        ([(0.0, 0.0), (10.0, 0.0)], 0.015, 0.01)])
    assert tie is not None and tie[1] == 0.015 and tie[2] == 0.01


# ── (1) runway_fit_weight ────────────────────────────────────────────────

def _with_fit(law: Law, w: float) -> Law:
    rl = _dc.replace(law.tables.emit.relaxation, runway_fit_weight=w)
    return Law(tables=_dc.replace(law.tables, emit=_dc.replace(law.tables.emit, relaxation=rl)),
               ruleset_key=law.ruleset_key)


def test_runway_fit_weight_zero_restores_the_06e_relaxation(hangar_slack, law):
    """At the table's default (0) stage 1 with the pipeline's weights is
    the pure-variance program: no linear column, the same slacks as the
    weightless control; at 1.0 the runway term enters (the 06h twin's
    ruled arm)."""
    airport, pm, cs = hangar_slack
    assert law.tables.emit.relaxation.runway_fit_weight == 0.0
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    cand = relax.full_scope(pm, law, cs)
    control = relax.stage1(pm, cs, cand, law, backend="pwl")
    default = relax.stage1(pm, cs, cand, law, backend="pwl", weights=w)
    assert control.status == default.status == "optimal"
    assert control.linear_cols == default.linear_cols == 0
    assert default.linear_rows == 0
    tol = law.tables.emit.materiality.elevation_m
    for x in cand:
        assert abs(control.slack.get(x.index, 0.0) - default.slack.get(x.index, 0.0)) <= tol
    on = relax.stage1(pm, cs, cand, _with_fit(law, 1.0), backend="pwl", weights=w)
    assert on.status == "optimal" and on.linear_cols > 0
    assert sum(on.slack.values()) > sum(default.slack.values()) + tol


# ── (3) the pad_flat quantum ────────────────────────────────────────────

def _lay_and_quantise(surf, pm, pad_ring_ids, slope: float, half_q: float):
    """The pad's ring on a plane of gradient ``slope`` along x, every
    elevation then rounded AGAINST the plane by the emit half-quantum in
    the direction that steepens the least-squares fit most (the worst
    lawful emission of an exactly-at-cap pad)."""
    import dataclasses
    ids = list(pad_ring_ids)
    xy = [pm.vertices[i].xy for i in ids]
    x0 = min(x for x, _y in xy)
    a = np.column_stack([np.ones(len(ids)), np.asarray(xy, float)])
    pinv = np.linalg.pinv(a)
    # the fitted gradient is (pinv[1] · z, pinv[2] · z); steepen along +x
    signs = np.sign(pinv[1])
    signs[signs == 0] = 1.0
    dz = {i: slope * (x - x0) + s * half_q for i, (x, _y), s in zip(ids, xy, signs)}
    verts = tuple(dataclasses.replace(v, z=v.z + dz[v.id]) if v.id in dz else v
                  for v in surf.vertices)
    return dataclasses.replace(surf, vertices=verts)


def test_a_pad_at_exactly_the_cap_emitted_at_the_quantum_is_no_row(law):
    airport, pm, surf, pub, _rep = _product(law, (730.0, 736.0))
    pad = next(f for f in surf.faces if f.role == "building")
    pub2 = dict(pub, relaxed_rows=[*pub.get("relaxed_rows", []), _published_relaxed_pad(surf, pad)])
    caps = road_law_caps(pm, law, airport)
    rl = law.tables.emit.relaxation
    half_q = 0.5 * law.tables.emit.materiality.elevation_m
    grade_tol = law.tables.emit.materiality.grade
    ids = list(pad.ring)
    # laid at the OLD reader's exact threshold (cap + grade materiality), then
    # emitted at the quantum: the old reading flags it, the ruled one forgives it
    laid = _lay_and_quantise(surf, pm, ids, rl.pad_slope_max + grade_tol, half_q)
    xy = [pm.vertices[i].xy for i in ids]
    z = {v.id: v.z for v in laid.vertices}
    resid, slope, sens = plane_fit_quantum(xy, [z[i] for i in ids])
    quantum = sens * half_q
    # the emission reads OVER cap + grade materiality (the 06k defect)
    # but inside the quantum: no row
    assert quantum > 0.0
    assert slope > rl.pad_slope_max + grade_tol, (slope, rl.pad_slope_max)
    assert slope <= rl.pad_slope_max + grade_tol + quantum
    assert census(laid, law, pub2, caps)[FAMILY_PAD_FLAT] == []
    # beyond the quantum it is still the 05f row, and the row names the quantum
    steep = _lay_and_quantise(surf, pm, ids, rl.pad_slope_max + 2.0 * quantum + grade_tol, half_q)
    rows = census(steep, law, pub2, caps)[FAMILY_PAD_FLAT]
    assert len(rows) == 1 and rows[0]["reading"] == "plane_slope"
    assert rows[0]["quantum"] == pytest.approx(quantum, abs=1e-6)
    # for a triangle the sensitivity is the census's own Σ 1/h_i
    from auto_patch_v2.verify.within import plane_fit_noise
    tri = [(0.0, 0.0), (30.0, 0.0), (0.0, 20.0)]
    _r, _s, sens3 = plane_fit_quantum(tri, [1.0, 2.0, 3.0])
    assert sens3 == pytest.approx(plane_fit_noise([(x, y, 0.0) for x, y in tri]), rel=1e-9)
