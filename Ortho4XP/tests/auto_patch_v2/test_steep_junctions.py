"""RULINGS 2026-10-26n (Q160-Q162): A STEEP RUNWAY FLATTENS WHERE TAXIWAYS
JOIN IT; NO LATERAL TWIST ON TAXIWAYS; APRONS AT A STEEP RUNWAY ARE
TERRACED (spec ``docs/findings/vnlk-junctions-lvnlk.md``).

The fixture is a synthetic runway (no airport): a 1200 m code 3D runway, one
stub joining it at x = 488.5..511.5 and one apron joining it at
x = -300..-200, with the thresholds set apart so the runway is steeper than
the 29ac pavement ceiling (steep) or only over its own cap (not steep).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.precedence import curve_k_of, view
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.runway_profile import (
    curve_stations,
    ridge_chains,
    runway_profile,
    runway_vertical_curve,
)
from auto_patch_v2.constraints.steep_apron import RULING, steep_apron_plane, terrace_refs
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import (
    airside_rate_per_m,
    pavement_fallback_cap,
    runway_vertical_curve_bound,
    strip_arc_rate_per_m,
    yielded_curve_rate,
)
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from test_routes import _RampDem, _rect

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, drop_m: float):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0 + drop_m,
                      "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubE", _rect(488.5, 22.5, 511.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "apron", "apronW", _rect(-300, 22.5, -200, 100), (), None, None,
             "airside", "apron", {}),
    )
    pm, _stats = build(airport, Classification(cells, (), {}, ()), law)
    return airport, with_runway_chord(pm, law, airport)


@pytest.fixture(scope="module")
def steep(law):
    return _airport(law, 150.0)           # 12.5 % pin to pin: over the 10 % ceiling


def _stations(pm, law, rw_id="09/27"):
    vw = view(pm, law)
    chs = ridge_chains(vw)[rw_id]
    st = curve_stations(vw.xy, chs, lambda v: vw.xy[v][0],
                        law.tables.emit.identity.min_distinct_spacing_m)
    return vw, st


def test_a_steep_runway_is_flat_across_each_junction_and_meets_its_pins(steep, law):
    _ap, pm = steep
    rc = pm.runway_caps["09/27"]
    assert rc.yielded and rc.g_pin > pavement_fallback_cap(law)
    assert len(rc.junctions) == 2
    # the apron joint (x -300..-200) and the stub mouth (x 488.5..511.5),
    # each covered by whole ridge chords, at the joining face's transverse cap
    a, b = rc.junctions
    assert a.u0 <= 300.0 and 400.0 <= a.u1 and b.u0 <= 1088.5 and 1111.5 <= b.u1
    assert a.t == b.t == pytest.approx(0.015)
    vw, st = _stations(pm, law)
    z = rc.profile_z
    assert z[st[0]] == pytest.approx(700.0) and z[st[-1]] == pytest.approx(850.0)
    cum = [0.0]
    for p, q in zip(st, st[1:]):
        cum.append(cum[-1] + vw.dist(p, q))
    for jn in rc.junctions:
        for k in range(len(st) - 1):
            if cum[k] >= jn.u0 - 1e-6 and cum[k + 1] <= jn.u1 + 1e-6:
                g = (z[st[k + 1]] - z[st[k]]) / (cum[k + 1] - cum[k])
                assert 0.0 < g <= jn.t
    # the rest takes the remaining grade: steeper than the pins' average
    assert rc.cap > rc.g_pin and rc.curve_k_m is not None


def test_the_rows_hold_the_junction_cap_and_the_yielded_curve(steep, law):
    airport, pm = steep
    rc = pm.runway_caps["09/27"]
    rows = runway_profile(pm, law, airport)
    flats = [r for r in rows if isinstance(r, Diff)
             and "junction flat" in " ".join(r.source.inputs)]
    assert flats and all(r.cap == pytest.approx(0.015) for r in flats)
    assert curve_k_of(pm, "09/27") == rc.curve_k_m
    law_b = runway_vertical_curve_bound(law, 10.0, 3, "D")
    got_b = runway_vertical_curve_bound(law, 10.0, 3, "D", yield_k_m=rc.curve_k_m)
    assert got_b > law_b
    curve = runway_vertical_curve(pm, law, airport)
    assert curve and max(r.hi for r in curve) > law_b
    # the designed profile meets every curve row with room
    zz = rc.profile_z
    for r in curve:
        if all(v in zz for v, _c in r.terms):
            val = sum(c * zz[v] for v, c in r.terms)
            assert r.lo - 1e-9 <= val <= r.hi + 1e-9


def test_the_published_record_names_the_junctions_and_the_curve(steep):
    _ap, pm = steep
    rec = pm.runway_caps["09/27"].as_dict("icao")
    assert [j["cap"] for j in rec["junctions"]] == [0.015, 0.015]
    assert rec["curve_k_m"] > 0.0 and rec["curve_rate_per_m"] > 0.0


def test_an_apron_a_steep_runway_joins_is_one_terrace_and_never_follows(steep, law):
    airport, pm = steep
    assert terrace_refs(pm, law) == ["apronW"]
    rows = steep_apron_plane(pm, law, airport)
    assert rows and all(r.source.ruling.startswith(RULING) for r in rows)
    apron = {f.id for f in pm.faces.values() if f.ref == "apronW"}
    assert not apron & set(pm.taxi_caps)          # 10-10j replaced at a steep runway


def test_a_runway_yielded_under_the_ceiling_keeps_the_uniform_yield(law):
    _ap, pm = _airport(law, 30.0)                 # 2.5 %: yielded, not steep
    rc = pm.runway_caps["09/27"]
    assert rc.yielded and not rc.junctions and rc.curve_k_m is None
    assert "junctions" not in rc.as_dict("icao")
    assert terrace_refs(pm, law) == []


def test_the_yielded_rate_accessors(law):
    assert yielded_curve_rate(law, None) is None
    r = yielded_curve_rate(law, 4.0)
    assert r == pytest.approx(0.01 / 4.0)
    own = float(law.ruleset.strip.arc_rate.per_metre)
    assert strip_arc_rate_per_m(law) == own
    assert strip_arc_rate_per_m(law, 4.0) == max(own, r)
    assert airside_rate_per_m(law, "runway", "D", 1.0, yield_k_m=4.0) >= r
    assert airside_rate_per_m(law, "runway", "D", 1.0) == airside_rate_per_m(law, "runway", "D")


def test_the_census_reads_the_published_curve_rate():
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    rates = cg._runway_curve_rates([{"ref": "A", "curve_rate_per_m": 0.002},
                                    {"ref": "B", "cap": 0.1}])
    assert rates == {"A": 0.002}
    old = cg._ACTIVE_RUNWAY_CURVE_RATE
    try:
        cg._ACTIVE_RUNWAY_CURVE_RATE = rates
        assert cg._curve_rate_of("A") == 0.002 and cg._curve_rate_of("A+B") == 0.002
        assert cg._curve_rate_of("B") == 0.0 and cg._curve_rate_of(None) == 0.0
    finally:
        cg._ACTIVE_RUNWAY_CURVE_RATE = old
