"""THE RUNWAY CREST STANDS AT FIELD ON OLD DATA (owner RULINGS 2026-11-06c
(1), #1915): "field elevation is the highest point of the runways".  Where
the DEM is flagged older than the airport (``airport/old_dem_fill``'s
witness, ``FillDem.predates_airport``) no runway target stands above the
apt.dat field elevation — the pins stay, the crest keeps its place and drops
to field; elsewhere the crest over field is a report line only and the
geometry is untouched (``constraints/runway_chord``)."""
from __future__ import annotations

import math

import pytest
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.runway_chord import runway_chord_targets
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build


class _Hill:
    """A hill 8 m high under the runway, its top 150 m east of the middle."""

    provenance = {"synthetic": "hill"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 8.0 * max(0.0, 1.0 - abs(x - 150.0) / 500.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _OldHill(_Hill):
    """The same hill, flagged OLDER THAN THE AIRPORT (the fill witness)."""

    predates_airport = True


class _Slope:
    """A steady 0.5 % slope, west to east: a normal sloping runway."""

    provenance = {"synthetic": "slope"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.005 * (x + 600.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _OldSlope(_Slope):
    predates_airport = True


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


RUNWAY = Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside",
              "runway", {})


def _targets(law, dem, thresholds, field):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thresholds[0], "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thresholds[1], "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, field, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, dem, law.ruleset_key)
    pm, _stats = build(airport, Classification((RUNWAY,), (), {}, ()), law)
    rep: dict = {}
    t = runway_chord_targets(pm, law, airport, rep)
    ridge = sorted((pm.vertices[v].xy[0], z) for v, z in t.items()
                   if abs(pm.vertices[v].xy[1]) < 0.01)
    return t, ridge, rep["by_runway"][0]


def test_an_old_dem_runways_crest_never_exceeds_field(law):
    """Over the old hill the trend's crest (over 703 m) is lowered to the
    field elevation (702 m): the ends stay at their pins, the highest point
    stays near the hill's station and stands at field."""
    _t, ridge, row = _targets(law, _OldHill(), (700.0, 700.0), 702.0)
    _t0, ridge0, row0 = _targets(law, _Hill(), (700.0, 700.0), 702.0)
    assert max(z for _x, z in ridge0) > 703.0                 # the hill is over field
    assert max(z for _x, z in ridge) <= 702.0 + 1e-6          # capped at field
    assert max(z for _x, z in ridge) > 702.0 - 0.05           # and lowered TO it, not below
    for x, z in ridge:
        if abs(abs(x) - 600.0) < 0.01:
            assert z == pytest.approx(700.0)                  # the ends at their pins
    crest = max(ridge, key=lambda q: q[1])[0]
    crest0 = max(ridge0, key=lambda q: q[1])[0]
    assert abs(crest - crest0) < 100.0                        # the crest keeps its place
    assert 0.0 < row["bow_scale"] < 1.0 and row["crest_over_field_m"] <= 1e-6
    assert row["field_capped"] and not row0["field_capped"]
    assert row0["bow_scale"] == 1.0 and row0["crest_over_field_m"] > 1.0     # report only


def test_a_normal_runway_is_untouched_byte_for_byte(law):
    """Off old data the crest over field is a report line, never geometry,
    and a normal sloping runway (its high end at field) is untouched with or
    without the witness."""
    _t0, _r0, row0 = _targets(law, _Hill(), (700.0, 700.0), 702.0)
    assert row0["crest_over_field_m"] > 1.0 and row0["bow_scale"] == 1.0
    a, _ra, rowa = _targets(law, _Slope(), (700.0, 706.0), 706.0)
    b, _rb, rowb = _targets(law, _OldSlope(), (700.0, 706.0), 706.0)
    assert a == b
    assert rowa["bow_scale"] == rowb["bow_scale"] == 1.0
    assert not rowa["field_capped"] and not rowb["field_capped"]
    assert all(math.isfinite(z) for z in a.values())
