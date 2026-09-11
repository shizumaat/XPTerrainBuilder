"""THE FOOT ROWS — round 6's twins (owner RULINGS 2026-09-11q; spec
``object-placement-spec.md`` §11b).

Round 5's bare-ground BODY PAD is withdrawn: a rigid plane cut into
sloping ground steps wherever an unpadded neighbour straddles its edge.
A body on bare ground now takes FOOT ROWS instead — its level is the
least-squares fit of ``dem(foot) - (y_foot - y_zero)`` over its
ground-contact feet, each foot takes one target row priced at ``[design]
ground_datum``, and feasibility is the fit's residual against
``bank_slope`` x the nearest-foot distance.

Four readings, all on the same lawful adjacent ground the ground-datum
twins use (``test_v2grounddem``), so nothing but the foot rows is in
play:

1. a nine-column body whose authored relief MATCHES the ground's fall —
   the rows fire, the solved sheet carries every foot, and NO ``pad_flat``
   row exists (no pad entity was minted);
2. the same body over ground that does NOT fall that way — INFEASIBLE, no
   rows, reported with its residual;
3. two neighbouring bodies — no STEP between them: the sheet's slope
   between their nearest feet stays inside ``bank_slope``;
4. a body standing on the APRON — pavement is senior (09af-1), no rows,
   reported with its role.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import foot_rows as FR
from auto_patch_v2.planar.group import Foot, Group, GroupSet, ground_fit
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect  # noqa: F401
from tests.auto_patch_v2.test_v2grounddem import (_LawfulDem, _X0, _X1, _Y0, _Y1,
                                                  _lawful_z)
from tests.auto_patch_v2.test_v2smooth import _airport, law  # noqa: F401

#: the colonnade: nine column feet on a line 7 m apart, out on the south
#: strip where the ground is lawful and falls away from the runway edge
_PITCH = 7.0
_FEET_X = -200.0
_FEET_Y0 = _Y0 - 12.0


def _apron_cell(r):
    """a small apron out on the ground, for reading (4)"""
    return Cell(9, "apron", "apronA", _rect(r, 120.0, _Y0 - 70.0, 220.0, _Y0 - 20.0),
                (), None, "D", "airside", "apron", {})


def _cells(r, *, apron: bool = False):
    out = [Cell(0, "runway", "09/27", _rect(r, _X0, _Y0, _X1, _Y1), (), 3, "D",
                "airside", "runway", {})]
    if apron:
        out.append(_apron_cell(r))
    return tuple(out)


def _feet(airport, r, xs_ys, ys):
    """``Foot`` per (x, y) frame point, carrying the authored ``y``."""
    _to_xy, to_ll = airport.frame.transformers()
    out = []
    for (x, y), fy in zip(xs_ys, ys):
        lat, lon = to_ll(*r((x, y)))
        out.append(Foot(lat=lat, lon=lon, y=float(fy)))
    return tuple(out)


def _group(gid, feet, *, bank=0.0):
    y0 = float(min(f.y for f in feet))
    return Group(gid=gid, bodies=((0, 0, 0),), senior=(0, 0, 0), y_zero=y0,
                 feet=tuple(feet), span_m=0.0, cross_placement=False,
                 long_span=False)


def _with_groups(airport, groups):
    gs = GroupSet(tuple(groups), {}, {})
    return _dc.replace(airport, groups=gs)


def _colonnade(airport, r, *, x=_FEET_X, matched: bool, n: int = 9):
    """``n`` column feet on a line running AWAY from the runway edge.

    ``matched``: the authored ``y`` reproduces the ground's own fall
    there, which is what a designer who modelled the real hillside
    authors.  Otherwise the columns are authored on ONE plane (the flat
    body), which on falling ground is the fight §11b (3) calls
    infeasible."""
    pts = [(x, _FEET_Y0 - i * _PITCH) for i in range(n)]
    zs = [_lawful_z(px, py) for px, py in pts]
    ys = [z - min(zs) for z in zs] if matched else [0.0] * n
    return _group("body", _feet(airport, r, pts, ys))


def _arm(law, dem, groups, *, apron=False):                       # noqa: F811
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.solve import solve_design
    airport, r = _airport(law, dem, ())
    made = groups(airport, r)
    airport = _with_groups(airport, made)
    pm, _st = build(airport, Classification(_cells(r, apron=apron), (), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    cs, counts, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    return airport, r, pm, cs, sol, rep, counts


def _surface_at(pm, law, airport, sol, foot):
    """The solved sheet under one foot — the SAME barycentric reading the
    row was minted with."""
    to_xy, _ = airport.frame.transformers()
    idx = FR._FaceIndex(pm, law)
    terms = idx.terms_at(to_xy(foot.lon, foot.lat))
    if terms is None:
        return None
    return sum(c * float(sol.z[v]) for v, c in terms)


# ── (1) the matched colonnade: the rows fire and the feet are carried ──

@pytest.fixture(scope="module")
def matched(law):                                                 # noqa: F811
    return _arm(law, _LawfulDem(), lambda a, r: [_colonnade(a, r, matched=True)])


def test_matched_relief_fires_rows_and_mints_no_pad(matched, law):  # noqa: F811
    _airport_, _r, _pm, cs, _sol, rep, counts = matched
    assert FR.STATS["foot_rows"]["bare"] == 1, FR.STATS["foot_rows"]
    # two one-sided rows per foot, nine feet, none off the sheet
    assert FR.STATS["foot_rows"]["rows"] == 9
    assert FR.STATS["foot_rows"]["feet_off_sheet"] == 0
    assert counts["foot_rows"] == 18
    assert rep.foot_rows == counts["foot_rows"]
    # NO PAD ENTITY (spec §11b (1)): round 5's bare-ground minting is
    # withdrawn, so the pad generators produce nothing here
    assert counts["pad_flats"] == 0
    assert counts["pad_slope_ceiling"] == 0
    heads = {r.source.ruling for r in cs.linears}
    assert FR.RULING in heads


def test_matched_relief_carries_every_foot(matched, law):          # noqa: F811
    airport, _r, pm, _cs, sol, _rep, _counts = matched
    g = airport.groups.groups[0]
    fit = ground_fit(g.feet, g.y_zero, FR._sampler(airport.dem,
                                                   airport.frame.transformers()[0]),
                     float(law.tables.emit.design.bank_slope))
    assert fit is not None and fit.feasible
    worst = 0.0
    for j, i in enumerate(fit.keep):
        z = _surface_at(pm, law, airport, sol, g.feet[i])
        assert z is not None, "a foot fell outside every face"
        worst = max(worst, abs(z - fit.targets[j]))
    # 0.05 m is the ground datum's own accuracy on this fixture (the
    # bending sheet against the DEM's curvature — ``test_v2grounddem``
    # reads the strip to the same tolerance); the residual is REPORTED
    assert worst <= 0.05, f"worst foot {worst:.3f} m from its target"


def test_the_rows_move_the_sheet_off_the_dem_ripple(law):          # noqa: F811
    """THE INTERVENTIONAL READING: the ground under the colonnade RIPPLES
    (±0.15 m over a 14 m wave) while the body is authored on the smooth
    ramp the designer saw.  Two arms, one tree, one code version: with the
    body (rows fire) and without it (the ground datum alone).  The foot
    rows must carry the feet CLOSER to the authored profile than the bare
    datum does — otherwise they are decoration."""
    class _Ripple(_LawfulDem):
        provenance = {"synthetic": "lawful ground + a 0.15 m ripple"}

        def z(self, x: float, y: float) -> float:
            import math
            return super().z(x, y) + 0.15 * math.sin(y * 2.0 * math.pi / 14.0)

    dem = _Ripple()
    pts_of = lambda: [(_FEET_X, _FEET_Y0 - i * _PITCH) for i in range(9)]

    def body(a, r):
        pts = pts_of()
        zs = [_lawful_z(px, py) for px, py in pts]
        return [_group("smooth", _feet(a, r, pts, [z - min(zs) for z in zs]))]

    airport, r, pm, _cs, sol, _rep, counts = _arm(law, dem, body)
    assert counts["foot_rows"] > 0
    ctrl_a, ctrl_r, ctrl_pm, _c2, ctrl_sol, _r2, ctrl_counts = _arm(
        law, dem, lambda a, rr: [])
    assert ctrl_counts["foot_rows"] == 0
    g = airport.groups.groups[0]
    fit = ground_fit(g.feet, g.y_zero,
                     FR._sampler(dem, airport.frame.transformers()[0]),
                     float(law.tables.emit.design.bank_slope))
    arm = ctrl = 0.0
    for j, i in enumerate(fit.keep):
        t = fit.targets[j]
        za = _surface_at(pm, law, airport, sol, g.feet[i])
        zc = _surface_at(ctrl_pm, law, ctrl_a, ctrl_sol, g.feet[i])
        assert za is not None and zc is not None
        arm = max(arm, abs(za - t))
        ctrl = max(ctrl, abs(zc - t))
    assert arm < ctrl - 0.01, f"rows {arm:.3f} m vs no-rows {ctrl:.3f} m"


# ── (2) the same body over ground that does NOT fall that way ─────────

class _FlatDem:
    """One level plane — the ground a colonnade authored for a hillside
    does not belong on."""

    provenance = {"synthetic": "flat ground"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def test_a_body_whose_relief_fights_the_ground_is_refused(law):    # noqa: F811
    """The nine columns authored as a STAIRCASE — 0.7 m per 7 m bay —
    standing on flat ground.  The fit's residual (the half-spread, 2.5 m)
    beats ``bank_slope`` x the nearest-foot distance (1:3 over 7 m =
    2.33 m), so the rows are REFUSED, the body keeps its low-side anchor,
    and the residual is REPORTED (§11b (3))."""
    def groups(a, r):
        pts = [(_FEET_X, _FEET_Y0 - i * _PITCH) for i in range(9)]
        return [_group("stair", _feet(a, r, pts, [0.7 * i for i in range(9)]))]
    _a, _r, _pm, _cs, _sol, rep, counts = _arm(law, _FlatDem(), groups)
    st = FR.STATS["foot_rows"]
    assert st["infeasible"] == 1 and st["bare"] == 0, st
    assert counts["foot_rows"] == 0 and rep.foot_rows == 0
    v = [v for v in FR.VERDICTS if v.verdict == "infeasible"]
    assert v and v[0].residual_m > v[0].limit_m
    # the ANCHOR is the LOW-SIDE foot (§11b (4)), reported with its residual
    assert v[0].anchor_lat != 0.0


def test_a_matched_body_is_feasible_however_steep_the_ground(law):  # noqa: F811
    """The answer to round 5's open question: the SAME staircase over
    ground that actually falls that way is feasible at zero cost."""
    class _Stair(_FlatDem):
        provenance = {"synthetic": "ground falling 0.1 per metre"}

        def z(self, x: float, y: float) -> float:
            return 700.0 - 0.1 * (y - _FEET_Y0)

    def groups(a, r):
        pts = [(_FEET_X, _FEET_Y0 - i * _PITCH) for i in range(9)]
        return [_group("stair", _feet(a, r, pts, [0.7 * i for i in range(9)]))]
    _a, _r, _pm, _cs, _sol, _rep, _counts = _arm(law, _Stair(), groups)
    st = FR.STATS["foot_rows"]
    assert st["infeasible"] == 0 and st["bare"] == 1, st
    v = [v for v in FR.VERDICTS if v.verdict == "bare"]
    assert v and v[0].residual_m <= 0.01, v


# ── (3) two neighbours: no step between them ───────────────────────────

def test_two_neighbouring_bodies_leave_no_step(law):               # noqa: F811
    def groups(a, r):
        return [_colonnade(a, r, x=_FEET_X, matched=True),
                _colonnade(a, r, x=_FEET_X + 30.0, matched=True)]
    airport, _r, pm, _cs, sol, _rep, _counts = _arm(law, _LawfulDem(), groups)
    assert FR.STATS["foot_rows"]["bare"] == 2, FR.STATS["foot_rows"]
    to_xy, _ = airport.frame.transformers()
    a, b = airport.groups.groups
    bank = float(law.tables.emit.design.bank_slope)
    worst = 0.0
    for fa in a.feet:
        za = _surface_at(pm, law, airport, sol, fa)
        pa = to_xy(fa.lon, fa.lat)
        near = min(b.feet, key=lambda f: (to_xy(f.lon, f.lat)[0] - pa[0]) ** 2
                   + (to_xy(f.lon, f.lat)[1] - pa[1]) ** 2)
        zb = _surface_at(pm, law, airport, sol, near)
        pb = to_xy(near.lon, near.lat)
        d = ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5
        if za is None or zb is None or d <= 0.0:
            continue
        worst = max(worst, abs(za - zb) / d)
    assert worst <= bank, f"a step: {worst:.3f} between neighbouring bodies"


# ── (4) pavement is senior ─────────────────────────────────────────────

def test_a_body_on_the_apron_takes_no_rows(law):                   # noqa: F811
    def groups(a, r):
        pts = [(130.0 + 10.0 * i, _Y0 - 45.0) for i in range(5)]
        return [_group("onapron", _feet(a, r, pts, [0.0, 0.4, 0.8, 1.2, 1.6]))]
    _a, _r, _pm, _cs, _sol, rep, counts = _arm(law, _LawfulDem(), groups, apron=True)
    st = FR.STATS["foot_rows"]
    assert st["pavement"] == 1, st
    assert counts["foot_rows"] == 0 and rep.foot_rows == 0
    v = [v for v in FR.VERDICTS if v.verdict == "pavement"]
    assert v and "apron" in v[0].roles
