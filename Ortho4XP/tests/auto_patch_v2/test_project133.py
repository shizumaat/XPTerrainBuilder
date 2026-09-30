"""Issue #133 (RULINGS 2026-09-30ad): a YIELDED runway is built uniformly
between its pins, and the runway projection names every row it withdraws.

KASE 15/33 (CIFP thresholds 2.003 % apart, §50 yields the FAA 1.5 % cap
to 2.023 %): every profile row was HELD at ``[design] hard_tol_m`` (0.02
m, 0.17 pp over a 12 m chord — eight times the 0.02 pp yield margin), so
the ridge spent that tolerance on every chord and drifted metres off the
pin line toward the DEM (north end 3.30 m under the chord, 2.03-2.39 %
built, 94 hard rows over the bar); the projection, handed that surface
with the neighbouring pavement fixed, found the coupled rows infeasible
and its elastic LP withdrew the rows AT THE RWY 33 PIN (the cheapest
slack), which the §50.3 guard refused.  The fix is the envelope
(``runway_profile.yield_envelope``): one ``Band`` per ridge station
between the governing pins, around the pin line and no wider than the
yield margin reaches from the nearer pin — a band has no per-chord
tolerance to accumulate.

The twins, on a synthetic two-pin runway at 2.0 % under ICAO code 3's
1.5 % over ground with a hollow near the low end (the DEM-trend pull
that sagged KASE) with a taxiway
stub tied to its edge:

1. the yielded runway carries the envelope, an un-yielded one none;
2. the solved ridge lies in the envelope, every 250 m bin at the yielded
   grade, nothing under the low pin, and the projection settles the
   runway (never refused); a withdrawn row, if any, is named with its
   feet and is never the runway family's own;
3. without the envelope the same fixture drifts off the pin line (the
   mechanism, interventional);
4. every row the legacy elastic arm withdraws is named, feet and all.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints import runway_profile as rp
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.runway_profile import ridge_chains
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Band
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design

LENGTH_M = 1200.0
WIDTH_M = 30.0
LOW_Z = 700.0
#: 2.0 % over 1,200 m against ICAO code 3's 1.5 % — KASE's shape, scaled
DROP_M = 24.0
BIN_M = 250.0
#: the pre-registered bin tolerance (brief #133): 0.05 pp around the cap
BIN_TOL = 0.0005
#: the hollow's depth under the pin line, 250 m from the low end
HOLLOW_M = 3.0


class _Hollow:
    """The ground the pins stand on, with a HOLLOW near the low end: the
    §21 trend target follows it (a real frame, not a degraded one), which
    is the pull that sagged KASE's north end 3.30 m under its chord."""

    provenance = {"synthetic": "pin line with a 3 m hollow"}

    def z(self, x: float, y: float) -> float:
        t = (x + LENGTH_M / 2.0) / LENGTH_M
        return (LOW_Z + DROP_M * t
                - HOLLOW_M * float(np.exp(-((x + 350.0) / 150.0) ** 2)))

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, drop_m):
    half = LENGTH_M / 2.0
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("10", (-half, 0.0), (60.5, -135.5), 0.0, 0.0,
                      LOW_Z, "fixture"),
            RunwayEnd("28", (half, 0.0), (60.5, -135.5), 0.0, 0.0,
                      LOW_Z + drop_m, "fixture"))
    rw = Runway("10/28", WIDTH_M, 1, ends, 3, "C")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, LOW_Z, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, _Hollow(),
                      law.ruleset_key)
    w = WIDTH_M / 2.0
    cells = (Cell(0, "runway", "10/28", _rect(-half, -w, half, w), (), 3, "C",
                  "airside", "runway", {}),
             # a stub tied to the runway edge mid-length: the pavement the
             # projection holds at its design value
             Cell(1, "stub", "stubA", _rect(-11.5, w, 11.5, 60.0), (), None,
                  "C", "airside", "taxi", {}))
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    return airport, with_runway_chord(pm, law, airport)


def _ridge(pm, law):
    vw = view(pm, law)
    ch = [v for c in ridge_chains(vw).get("10/28", []) for v in c]
    return vw, sorted(set(ch), key=lambda v: vw.xy[v][0])


def _solve(law, airport, pm):
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return cs, np.asarray(sol.z, float), rep


def _pin_line_misses(pm, law, z):
    """Per ridge station: ``z − pin line`` (the ridge in axis order)."""
    vw, ridge = _ridge(pm, law)
    s = np.array([vw.xy[v][0] for v in ridge])
    line = LOW_Z + DROP_M * (s - s[0]) / (s[-1] - s[0])
    return s, np.array([z[v] for v in ridge]) - line


@pytest.fixture(scope="module")
def over(law):
    return _airport(law, DROP_M)


# ── 1. the envelope exists where the cap yielded, and nowhere else ──────

def test_a_yielded_runway_carries_its_envelope_and_an_unyielded_one_none(
        over, law):
    airport, pm = over
    rc = pm.runway_caps["10/28"]
    assert rc.yielded and rc.cap_law == 0.015
    assert rc.g_pin == pytest.approx(DROP_M / LENGTH_M, rel=1e-3)
    bands = [r for r in rp.runway_profile(pm, law, airport)
             if isinstance(r, Band) and "yield envelope" in r.source.ruling]
    _vw, ridge = _ridge(pm, law)
    assert len(bands) == len(ridge) - 2          # every station between the pins
    m = float(law.tables.emit.design.runway_yield_margin)
    for b in bands:
        assert b.lo <= b.hi
        # never wider than the margin reaches over half the span
        assert b.hi - b.lo <= m * LENGTH_M + 1e-6
    # the head is the longitudinal law's: HARD, no new ruling
    assert all(b.source.ruling.split(" (")[0] == "rulesets.runway.longitudinal"
               for b in bands)
    airport1, pm1 = _airport(law, 12.0)          # 1.0 %: fits the table
    assert not pm1.runway_caps["10/28"].yielded
    assert not [r for r in rp.runway_profile(pm1, law, airport1)
                if isinstance(r, Band)]


# ── 2. the runway is built on its pin line, and the projection settles it

def test_the_yielded_runway_is_built_uniformly_and_the_projection_settles_it(
        over, law):
    airport, pm = over
    rc = pm.runway_caps["10/28"]
    _cs, z, rep = _solve(law, airport, pm)
    pr = rep.runway_projection
    assert not pr.status.startswith("refused"), pr.line()
    held = float(law.tables.emit.design.hard_tol_m)
    assert pr.after_family_m <= held + 1e-6, pr.line()
    # a withdrawn row is named, feet and all — and is never the family's own
    for rec in pr.withdrawn:
        assert rec["feet"] and not all(f["family"] for f in rec["feet"]), rec
    s, miss = _pin_line_misses(pm, law, z)
    m = float(law.tables.emit.design.runway_yield_margin)
    reach = m * np.minimum(s - s[0], s[-1] - s)
    assert np.all(np.abs(miss) <= reach + held + 1e-6), \
        float(np.max(np.abs(miss) - reach))
    # nothing under the low pin, every 250 m bin at the yielded grade
    assert float(np.min(miss + LOW_Z + DROP_M * (s - s[0]) / (s[-1] - s[0]))) \
        >= LOW_Z - held
    zr = miss + LOW_Z + DROP_M * (s - s[0]) / (s[-1] - s[0])
    for a in np.arange(s[0], s[-1] - 1.0, BIN_M):
        b = min(a + BIN_M, s[-1])
        g = (np.interp(b, s, zr) - np.interp(a, s, zr)) / (b - a)
        assert abs(g - rc.cap) <= BIN_TOL + (rc.cap - rc.g_pin), (a, g, rc.cap)


# ── 3. the mechanism, interventional: no envelope, the ridge drifts ─────

def test_without_the_envelope_the_ridge_drifts_off_the_pin_line(
        over, law, monkeypatch):
    airport, pm = over
    _cs, z_on, _r = _solve(law, airport, pm)
    monkeypatch.setattr(rp, "yield_envelope", lambda *a, **k: [])
    _cs, z_off, _r = _solve(law, airport, pm)
    _s, miss_on = _pin_line_misses(pm, law, z_on)
    _s, miss_off = _pin_line_misses(pm, law, z_off)
    m = float(law.tables.emit.design.runway_yield_margin)
    # the rows alone spend the held tolerance chord after chord: the ridge
    # leaves the margin's reach; the envelope keeps it inside
    assert float(np.max(np.abs(miss_off))) > m * LENGTH_M / 2.0
    assert float(np.max(np.abs(miss_on))) < float(np.max(np.abs(miss_off)))


# ── 4. a withdrawn row is named ───────────────────────────────────────

def test_every_row_the_elastic_arm_withdraws_is_named_with_its_feet(
        law, monkeypatch):
    """The legacy elastic arm (the §50.3 TFFJ class, the yield DISABLED so
    the runway's own rows are infeasible between its pins): the report
    names every withdrawn row — generator, ruling, slack, violation left —
    and every foot (vertex, roles, fixed, in the family), so a refusal is
    read by row, never re-derived by hand (#133: KASE's 13 were found only
    by instrumenting the drop set)."""
    import auto_patch_v2.constraints.runway_yield as ry
    monkeypatch.setattr(ry, "derive", lambda pm, law, airport: {})
    airport, pm = _airport(law, DROP_M)
    assert not pm.runway_caps
    _cs, _z, rep = _solve(law, airport, pm)
    pr = rep.runway_projection
    assert pr.elastic_rows > 0, pr.line()
    assert len(pr.withdrawn) == pr.elastic_rows
    for rec in pr.withdrawn:
        assert rec["generator"] and rec["ruling"] and rec["slack_m"] > 0.0
        assert "after_m" in rec
        for f in rec["feet"]:
            assert {"v", "roles", "fixed", "family"} <= set(f)
    assert "withdrawn" in pr.as_dict()
