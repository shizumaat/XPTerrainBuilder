"""RULINGS 2026-10-30d: WHERE A RUNWAY'S LONGITUDINAL CAP YIELDS
(``runway_cap_yield``, 2026-09-18d / #1342), THE GRADED STRIP'S
LONGITUDINAL CAP YIELDS WITH IT TO THE SAME GRADE — in the generator
(``constraints.strips.strip_longitudinal``), v2 verify and the census.

The fixture is test_steep_junctions' synthetic code 3D runway (no airport),
its thresholds set 30 m apart: 2.5 % pin to pin, over its own cap.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from auto_patch_v2.constraints.precedence import yield_cap_of
from auto_patch_v2.constraints.strips import strip_longitudinal
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import strip_longitudinal_cap
from auto_patch_v2.verify.frame import Patch
from test_steep_junctions import _airport

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cap(cap, yielded):
    return SimpleNamespace(cap=cap, yielded=yielded)


def test_the_strip_cap_accessor_raises_only_to_a_yield(law):
    own = float(law.ruleset.strip.longitudinal.value(3, "D"))
    assert strip_longitudinal_cap(law, 3, "D") == own
    assert strip_longitudinal_cap(law, 3, "D", own + 0.01) == own + 0.01
    assert strip_longitudinal_cap(law, 3, "D", own - 0.001) == own   # never tighter


def test_the_solve_side_reads_only_yielded_runways():
    pm = SimpleNamespace(runway_caps={"A": _cap(0.0268, True), "B": _cap(0.015, False)})
    assert yield_cap_of(pm, "A") == 0.0268 and yield_cap_of(pm, "A+B") == 0.0268
    assert yield_cap_of(pm, "B") is None and yield_cap_of(None, "A") is None


def test_the_published_side_reads_only_yielded_records():
    p = SimpleNamespace(publication={"runway_caps": [
        {"ref": "A", "cap": 0.0268, "yielded": True},
        {"ref": "B", "cap": 0.015, "yielded": False}]})
    assert Patch.runway_yield_cap(p, "A") == 0.0268
    assert Patch.runway_yield_cap(p, "B+A") == 0.0268
    assert Patch.runway_yield_cap(p, "B") is None


def test_the_census_reads_the_same_yield_as_the_generator(law):
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    caps = cg._runway_yield_caps([{"ref": "A", "cap": 0.0268, "yielded": True},
                                  {"ref": "B", "cap": 0.015, "yielded": False}])
    assert caps == {"A": 0.0268}
    old = cg._ACTIVE_RUNWAY_YIELD_CAP
    try:
        cg._ACTIVE_RUNWAY_YIELD_CAP = caps
        assert cg._yield_cap_of("A+B") == 0.0268 and cg._yield_cap_of("B") is None
    finally:
        cg._ACTIVE_RUNWAY_YIELD_CAP = old
    for y in (None, 0.0268):
        census, _rate = cg._strip_longitudinal_law(3, "D", law.ruleset_key, yield_cap=y)
        assert census == pytest.approx(strip_longitudinal_cap(law, 3, "D", y))


def test_the_generator_rows_follow_the_yielded_runway(law, monkeypatch):
    airport, pm = _airport(law, 30.0)
    rc = pm.runway_caps["09/27"]
    own = float(law.ruleset.strip.longitudinal.value(3, "D"))
    assert rc.yielded and rc.cap > own
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    rows = strip_longitudinal(pm, law, airport)
    import auto_patch_v2.constraints.strips as strips
    monkeypatch.setattr(strips, "yield_cap_of", lambda _pm, _ref: None)
    unyielded = strip_longitudinal(pm, law, airport)
    assert rows and len(rows) == len(unyielded)
    for r, u in zip(rows, unyielded, strict=True):
        ds = (u.hi - q) / own
        assert r.hi == pytest.approx(rc.cap * ds + q)
        assert r.lo == pytest.approx(-r.hi)
