"""Lane ``tunnelwitness2`` twins — issues #65, #5 [SPJC-3], #12 [OTHH-1]
Q-12b (owner RULINGS 2026-09-27a (3) (4)).

#65: ``structure_service._rise_m`` read the ground over a bore against the
MEAN of its two ends, so a bore under ground that merely slopes read half
its own fall as a hill.  The rise is now the ground standing above THE
LINE BETWEEN THE TWO MOUTH GROUNDS.
"""
from __future__ import annotations

import types

import pytest
from shapely.geometry import LineString

from auto_patch_v2.planar.structure_service import _rise_m


class _Dem:
    provenance = {"source": "fixture"}

    def __init__(self, fn):
        self.fn = fn

    def z(self, x, y):
        return self.fn(x, y)

    def bounds(self):
        return (-20000.0, -20000.0, 20000.0, 20000.0)


def _ap(fn):
    return types.SimpleNamespace(dem=_Dem(fn))


# ── #65: the rise is read against the mouth chord ───────────────────────

def test_a_SLOPING_bore_under_flat_ground_reads_ZERO_rise():
    """SPJC -5724: the DEM falls 21.97 -> 21.44 m along 35 m.  Against the
    mean of the ends it read +0.27 m; against the chord it reads 0.  A
    bore falling 2.0 m (which passed ``terrain_rise_m`` 0.5 before) also
    reads 0."""
    ln = LineString([(300.0, -100.0), (335.0, -100.0)])
    spjc = _ap(lambda x, y: 21.97 - (0.53 / 35.0) * (x - 300.0))
    assert _rise_m(spjc, ln) == pytest.approx(0.0, abs=1e-9)
    steep = _ap(lambda x, y: 30.0 - (2.0 / 35.0) * (x - 300.0))
    assert _rise_m(steep, ln) == pytest.approx(0.0, abs=1e-9)


def test_a_real_HILL_reads_its_rise_over_the_chord_even_on_a_slope():
    """A ridge 3.0 m high over the middle of a bore whose mouths differ by
    2.0 m reads 3.0 m over the chord (the mean-of-ends read 4.0 there —
    the error ran both ways)."""
    ln = LineString([(0.0, 0.0), (100.0, 0.0)])

    def hill(x, y):
        base = 50.0 - 0.02 * x                      # 50.0 -> 48.0
        return base + (3.0 if 40.0 <= x <= 60.0 else 0.0)

    assert _rise_m(_ap(hill), ln) == pytest.approx(3.0, abs=1e-6)
    flat_hill = _ap(lambda x, y: 10.0 + (0.7 if 40.0 <= x <= 60.0 else 0.0))
    assert _rise_m(flat_hill, ln) == pytest.approx(0.7, abs=1e-6)


def test_a_bore_in_a_DIP_reads_no_rise():
    """Ground BELOW the chord everywhere is no cover at all."""
    ln = LineString([(0.0, 0.0), (100.0, 0.0)])
    dip = _ap(lambda x, y: 10.0 - (1.0 if 20.0 <= x <= 80.0 else 0.0))
    assert _rise_m(dip, ln) == pytest.approx(0.0, abs=1e-9)   # the mouths themselves


# ── #5 [SPJC-3]: an OSM tunnel inside the fence is its own witness ──────

from auto_patch_v2.classify.roles import Cell, Classification  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import (Airport, Boundary, OsmWay, Runway,  # noqa: E402
                                         RunwayEnd, SceneryPack)
from auto_patch_v2.model.frame import Frame  # noqa: E402
from auto_patch_v2.planar.structures import build_structures  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


SPJC_TAGS = {"highway": "secondary", "lanes": "3", "tunnel": "yes"}


def _spjc(law, fence=_rect(-800, -800, 800, 800), bore_pts=((300.0, -100.0), (335.0, -100.0)),
          tags=SPJC_TAGS, partition=None, extra_cells=()):
    """SPJC -5724's shape: a 35 m ``secondary`` bore on a plane falling
    0.53 m, the nearest classified cell off it, inside a fence."""
    frame = Frame("ZZZZ", origin=(-12.03, -77.11), identity_dp=11)
    ends = (RunwayEnd("16", (0.0, 600.0), (0, 0), 0.0, 0.0, 22.0, "fixture"),
            RunwayEnd("34", (0.0, -600.0), (0, 0), 0.0, 0.0, 22.0, "fixture"))
    rw = Runway("16/34", 45.0, 1, ends, 4, "E")
    bore = OsmWay(-5724, "big_roads", tuple(bore_pts), False, dict(tags))
    # the road continues from both mouths, as -5708 / -5723 do at SPJC
    (ax, ay), (bx, by) = bore_pts[0], bore_pts[-1]
    road = {"highway": "secondary", "lanes": "3"}
    ways = (bore, OsmWay(-5708, "big_roads", ((ax - 150.0, ay), (ax, ay)), False, road),
            OsmWay(-5723, "big_roads", ((bx, by), (bx + 150.0, by)), False, road))
    fences = (Boundary("boundary0", fence, ()),) if fence else ()
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 22.0, (rw,), (), (), {}, (),
                      (), fences, (), ways, (), (), pack,
                      _Dem(lambda x, y: 21.97 - 0.015 * (x - 300.0)),
                      law.ruleset_key, partition=partition)
    cells = [Cell(0, "runway", "16/34", _rect(-22, -600, 22, 600), (), 4, "E",
                  "airside", "runway", {}),
             # the nearest classified cell stands OFF the bore's line (SPJC's
             # pav49 is 211 m away), so neither ramp is stopped by it
             Cell(1, "apron", "pav49", _rect(360, 40, 460, 140), (), None, None,
                  "airside", "apron", {})] + list(extra_cells)
    return build_structures(airport, Classification(tuple(cells), (), {}, ()), law)


def _refusals(st):
    return [ln for ln in st.mouths_off_field_nearest if "NOT A TERRAIN TUNNEL" in ln]


def test_an_OSM_tunnel_INSIDE_the_fence_under_nothing_is_BUILT(law):
    """Owner RULINGS 2026-09-27a (4): "an OSM ``tunnel=yes`` way INSIDE the
    airport boundary IS a terrain-tunnel witness on its own".  SPJC -5724:
    cover 0.0 m, no crossing, rise 0.00 over its chord, no layer — and
    both mouths are built."""
    _cl, tunnels, st = _spjc(law)
    assert st.bores == 1 and st.tunnels == 2, st.mouths_off_field_nearest
    assert not _refusals(st)


def test_the_same_bore_with_NO_fence_or_OUTSIDE_it_is_still_refused(law):
    """Outside the fence the existing witnesses apply: the VMMC class
    (16d) stays closed.  A bore STRADDLING the fence line does not lie
    inside it either."""
    for fence in (None, _rect(-800, -800, 200, 800), _rect(-800, -800, 320, 800)):
        _cl, _t, st = _spjc(law, fence=fence)
        assert st.tunnels == 0, fence
        named = _refusals(st)
        assert len(named) == 1 and "-5724 PASSES UNDER NOTHING AT GRADE" in named[0]


def test_the_fence_reads_a_MAPPED_tunnel_only(law):
    """The fence trusts OSM's ``tunnel`` tag, so it reads only a bore every
    way of which carries an admitted one — a ``building_passage`` is not a
    bore at all (§26) and a synthesised §34 (5) underpass is not OSM's."""
    from auto_patch_v2.planar.structure_service import _osm_tunnel
    from auto_patch_v2.planar.structure_underpass import UNDERPASS_TAG
    tn = law.tables.structures.tunnel
    mk = lambda tags: types.SimpleNamespace(ways=[types.SimpleNamespace(tags=tags)])  # noqa: E731
    assert _osm_tunnel(mk(SPJC_TAGS), tn.admitted_values)
    assert not _osm_tunnel(mk(dict(SPJC_TAGS, tunnel="building_passage")), tn.admitted_values)
    assert not _osm_tunnel(mk(dict(SPJC_TAGS, **{UNDERPASS_TAG: "-1"})), tn.admitted_values)
