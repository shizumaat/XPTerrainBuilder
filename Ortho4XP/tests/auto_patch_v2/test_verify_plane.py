"""``verify.within.plane_gradient`` — the v1 reader's arithmetic exactly
(``check_grade.plane_reading``): the plane-fit rounding envelope and the
undeclared-vertex crown interval (2026-09-04, lane v2resid)."""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.verify.frame import Patch, Shape
from auto_patch_v2.verify.within import plane_fit_noise, plane_gradient

LAT0, LON0 = 0.0, 0.0


def _patch(xy, z, role="junction", crown=()):
    """A one-triangle patch in the census frame; ``crown`` = per-vertex
    drops (``None`` = undeclared) published as ``crown_drops``."""
    law = Law.for_airport("CYXY")
    ids = (0, 1, 2)
    ll = {}
    for i, (x, y) in zip(ids, xy):
        lat = LAT0 + math.degrees(y / 6371000.0)
        lon = LON0 + math.degrees(x / 6371000.0)
        ll[i] = (lat, lon)
    pub = {"crown_drops": [(ll[i][0], ll[i][1], d) for i, d in zip(ids, crown)
                           if d is not None]}
    sh = Shape(0, role, "pav1", ids, tuple(xy), tuple(z))
    return Patch(law, LAT0, LON0, dict(zip(ids, xy)), dict(zip(ids, z)), ll,
                 (sh,), (), pub)


SLIVER = ((0.0, 0.0), (47.0, 0.0), (23.5, 0.5))


def test_a_sliver_at_cap_is_not_flagged_for_its_emit_quantum():
    assert plane_gradient(_patch(SLIVER, (10.00, 10.70, 10.36))) == []


def test_a_sliver_genuinely_over_cap_is_still_flagged():
    rows = plane_gradient(_patch(SLIVER, (10.00, 10.70, 10.85)))
    assert len(rows) == 1 and rows[0]["grade_pct"] > 10.0
    assert rows[0]["cap_pct"] == pytest.approx(1.5)


def test_plane_fit_noise_is_the_sum_of_inverse_altitudes():
    pts = [(0.0, 0.0, 0.0), (47.0, 0.0, 0.0), (23.5, 0.5, 0.0)]
    assert abs(plane_fit_noise(pts) - (1 / 0.5 + 2 / 0.99995)) < 1e-2
    assert plane_fit_noise([(0, 0, 0), (1, 0, 0), (2, 0, 0)]) == 0.0


TRI = ((0.0, 0.0), (30.0, 0.0), (15.0, 25.0))


def test_an_undeclared_vertex_is_unknown_not_on_the_ridge():
    # two runway-edge vertices declared 0.30, the stub's own vertex absent:
    # raw 1.2 %, ridge-default 2.4 % — lawful under the interval
    assert plane_gradient(_patch(TRI, (10.0, 10.0, 9.7), crown=(0.3, 0.3, None))) == []
    # fully declared with C on the ridge: the 2.4 % is the reading
    rows = plane_gradient(_patch(TRI, (10.0, 10.0, 9.7), crown=(0.3, 0.3, 0.0)))
    assert len(rows) == 1 and abs(rows[0]["grade_pct"] - 2.4) < 0.1


def test_no_declaration_reads_raw():
    assert len(plane_gradient(_patch(TRI, (10.0, 10.0, 11.0)))) == 1
    assert plane_gradient(_patch(TRI, (10.0, 10.0, 10.2))) == []
