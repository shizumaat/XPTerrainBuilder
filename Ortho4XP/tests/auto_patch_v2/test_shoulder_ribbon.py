"""THE SHOULDER IS A RIBBON AT ITS OWN DEPTH (``classify/shoulder_ribbon``,
issue #1100): a taxiway leaving a shoulder ribbon for the apron is not the
runway's, even inside the graded strip.  Synthetic twins over the M1
synthetic airport (``test_classify._synthetic``: slab y = -15..15,
x = 0..1060, code 2 -> strip half width 40 m)."""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.classify import classify, load_rules  # noqa: E402
from auto_patch_v2.classify.shoulder_ribbon import ribbon_depth_m  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import Pavement, Surface  # noqa: E402
from test_classify import _synthetic  # noqa: E402

SLAB = box(0.0, -15.0, 1060.0, 15.0)
#: an 8 m shoulder ribbon along 400 m of the south edge, and a 30 m
#: taxiway leaving it to 38 m off the centreline (inside the 40 m strip)
RIBBON = box(300.0, -23.0, 700.0, -15.0)
LEG = box(480.0, -38.0, 510.0, -15.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _airport():
    a = _synthetic(gate=True, island=False)
    ring = tuple(unary_union([RIBBON, LEG]).exterior.coords)[:-1]
    return _dc.replace(a, pavements=a.pavements
                       + (Pavement("page", Surface.ASPHALT, ring, ()),))


def _factor(rules, f):
    return _dc.replace(rules, corridor=_dc.replace(
        rules.corridor, runway_shoulder_ribbon_factor=f))


def test_the_ribbon_depth_is_the_median_not_the_leg():
    face = unary_union([RIBBON, LEG])
    assert ribbon_depth_m(face, SLAB, 0.5, 50.0) == pytest.approx(8.0, abs=0.01)
    assert ribbon_depth_m(box(0, 100, 10, 110), SLAB, 0.5, 50.0) is None


def test_a_taxiway_leaving_the_ribbon_is_not_the_shoulder(law, rules):
    """Out to 15 + 1.5 x 8 = 27 m the page is the runway's shoulder; the
    leg beyond is §40 (5)'s remainder.  With the factor disarmed the whole
    leg stays inside the 40 m strip and is the runway's."""
    def shoulder_m2(cl):
        return sum(Polygon(c.ring, c.holes).area for c in cl.cells
                   if c.kind == "runway_shoulder")
    whole = classify(_airport(), law, _factor(rules, 0.0))
    cut = classify(_airport(), law, _factor(rules, 1.5))
    assert shoulder_m2(whole) == pytest.approx(400 * 8 + 30 * 15, rel=0.03)
    assert shoulder_m2(cut) == pytest.approx(400 * 8 + 30 * 4, rel=0.05)
    rest = [c for c in cut.cells if c.evidence.get("shoulder_beyond_band")]
    assert sum(Polygon(c.ring, c.holes).area for c in rest) == \
        pytest.approx(30 * 11, rel=0.05)
    assert all(c.role != "runway" for c in rest)
