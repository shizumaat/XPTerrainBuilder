"""SERVICE-ROAD APRON SPINES — owner ruling RULINGS 2026-08-25h.

Spec: ``docs/specs/service-road-apron-spine-spec.md``.  The owner's model,
verbatim: *a truck route along/through an apron is a SPINE at the apron's
cap — like a taxiway, but 1 %.*

THE GAP THIS CLOSES, and why it is a gap and not a cap change.  Free-road
scoping (owner 2026-07-27 + R7a 2026-08-15) cuts a service centerline at
the stations where it stops being a free road and feeds only the FREE
stretches to the slice; the ruling says the rest "grades with the apron".
It did not — the contact stretches were DROPPED, so those roads reached
the grade graph with **no centerline at all**.  With nothing anchoring
them, the apron chain and the road family solved the same welded stations
independently, which is the alternating apron-vs-service sawtooth at the
owner's two back-edge ripple sites.

The five twins the spec names:
  (a) a through road inside an apron gets a 1 % profile and the apron
      chords to it;
  (b) the same road OUTSIDE the apron is unchanged (8 % / free road);
  (c) the reachability band's service exclusion is byte-identical — the
      airside-contamination regression class;
  (d) a shared apron/road edge emits one value series (no sawtooth);
  (e) the flag is default ON and OFF is byte-identical.
"""
from __future__ import annotations

import importlib
import math
import os
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch import config as C                          # noqa: E402
from auto_patch import grade_graph as GG                    # noqa: E402
from auto_patch import groundside as GS                     # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# §1 RECOGNITION — the free-road predicate's own complement
# ══════════════════════════════════════════════════════════════════════

def test_recognition_is_the_free_road_predicates_complement():
    """"reuse their predicates, never a third contact test" (spec §1.1).

    The apron-spine set is literally what ``free_road_subsegments``
    removed, so segmentation by contact comes for free: the same
    centerline yields apron-spine pieces inside contact and free-road
    pieces outside it.
    """
    whole = [LineString([(0.0, 0.0), (100.0, 0.0)])]
    free = [LineString([(0.0, 0.0), (40.0, 0.0)])]
    got = GS.apron_spine_subsegments(whole, free)
    assert len(got) == 1
    assert got[0].length == pytest.approx(60.0, abs=1e-6)
    assert got[0].coords[0] == pytest.approx((40.0, 0.0))
    # Degenerate ends: all free ⇒ no spine; none free ⇒ the whole line.
    assert GS.apron_spine_subsegments(whole, whole) == []
    assert GS.apron_spine_subsegments(whole, [])[0].length == \
        pytest.approx(100.0, abs=1e-6)


def test_one_centerline_can_be_both_along_its_length():
    """§1.1: "the same centerline may be apron-spine inside contact and a
    free road outside it"."""
    whole = [LineString([(0.0, 0.0), (300.0, 0.0)])]
    free = [LineString([(0.0, 0.0), (100.0, 0.0)]),
            LineString([(200.0, 0.0), (300.0, 0.0)])]
    got = GS.apron_spine_subsegments(whole, free)
    assert len(got) == 1
    assert got[0].length == pytest.approx(100.0, abs=1e-3)


# ══════════════════════════════════════════════════════════════════════
# §2 THE SPINE — (a) and (b)
# ══════════════════════════════════════════════════════════════════════

class _Shape:
    def __init__(self, role, polygon=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.node_altitudes = node_altitudes


class _Layout:
    canonical_points = None
    apt_taxi_centerlines: list = []

    def __init__(self, shapes=(), apron_spines=(), free=()):
        self.shapes = list(shapes)
        self._apron_spine_subsegments = list(apron_spines)
        self._slice_service_subsegments = list(free)


def _specs(layout):
    return GG.centerline_specs(layout)


def test_a_the_apron_spine_carries_the_APRON_cap():
    """(a) The road centerline inside the apron gets a 1 % profile — the
    apron's cap, not the road's 8 %."""
    spine = LineString([(0.0, 0.0), (120.0, 0.0)])
    specs = _specs(_Layout(apron_spines=[spine]))
    mine = [sp for sp in specs if sp[3][0] == "apron_spine"]
    assert mine, "the apron-spine segment produced no centerline spec"
    pts, seg_caps, is_service, key, rpts = mine[0]
    assert seg_caps and all(c == pytest.approx(C.APRON_MAX_GRADE)
                            for c in seg_caps)
    assert seg_caps[0] != pytest.approx(C.SERVICE_ROAD_MAX_GRADE)


def test_b_the_free_road_remainder_is_unchanged():
    """(b) The same road OUTSIDE the apron keeps the road cap."""
    free = LineString([(200.0, 0.0), (300.0, 0.0)])
    specs = _specs(_Layout(free=[free]))
    mine = [sp for sp in specs if sp[3][0] == "svc"]
    assert mine
    _pts, seg_caps, _svc, _k, _r = mine[0]
    assert all(c == pytest.approx(C.SERVICE_ROAD_MAX_GRADE)
               for c in seg_caps)


def test_c_the_band_exclusion_is_untouched():
    """(c) ``REACH_NO_SERVICE_SPINES`` STANDS (spec §2.2).

    An apron spine joins the GRADING scaffold, never the reachability
    band's route graph.  ``is_service`` is what the band filters on, so
    it must stay TRUE even though the cap is now the apron's — a spine
    that joined the band would be the airside-contamination regression
    class the roadseal round already paid for once.
    """
    spine = LineString([(0.0, 0.0), (120.0, 0.0)])
    specs = _specs(_Layout(apron_spines=[spine]))
    mine = [sp for sp in specs if sp[3][0] == "apron_spine"][0]
    assert mine[2] is True, (
        "an apron spine left the service class — the reachability band "
        "would now justify a ceiling through a truck route")
    assert C.REACH_NO_SERVICE_SPINES is True


def test_the_apron_spine_never_carries_its_cap_into_a_threaded_shape():
    """``_route_taxi_cap`` must keep returning None for a service
    centerline: the SPINE-FRAME upgrade carries a route's cap
    longitudinally through the shapes it threads, and a truck route may
    not hand its rate to anything (the free-road ruling).  The apron
    spine changes what the ROAD is capped at, not what it can donate."""
    class _CL:
        def __init__(self):
            self.is_service = True
            self.cap = C.APRON_MAX_GRADE
            self.route_idx = 0
    ctx = GG.GradeContext(centerlines=[_CL()], routes=[])
    assert GG._route_taxi_cap({0}, 0, ctx) is None


# ══════════════════════════════════════════════════════════════════════
# §3 NO ALTERNATION — (d)
# ══════════════════════════════════════════════════════════════════════

def _road_and_apron(alts):
    """A road ring welded along a shared edge with an apron, carrying
    ``alts`` on its stations."""
    xs = [0.0, 10.0, 20.0, 30.0, 40.0]
    top = [(x, 6.0) for x in xs]
    bot = [(x, 0.0) for x in reversed(xs)]
    ring = bot + top                       # y=0 flank is the shared edge
    road = Polygon(ring)
    # The apron carries THE SAME stations along y=0, so the two rings
    # share EDGES by canonical identity — which is the 25b contact notion
    # the instrument reuses.  An apron with one long edge shares no edge
    # key at all, and is correctly invisible to it.
    apron = Polygon([(x, 0.0) for x in xs]
                    + [(40.0, -30.0), (0.0, -30.0)])
    return _Layout(shapes=[_Shape("apron", apron),
                           _Shape("service_road", road, list(alts))])


def test_d_a_sawtooth_along_a_shared_edge_is_COUNTED():
    """The instrument must SEE the defect it exists for: adjacent
    stations alternating up-down-up beyond the tolerance."""
    saw = [10.0, 11.0, 10.0, 11.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    n = GS.count_edge_alternation(_road_and_apron(saw))
    assert n > 0, "the alternation instrument missed a 1 m sawtooth"


def test_d_a_steady_ramp_is_NOT_counted():
    """A road that simply CLIMBS along the edge is not a ripple.  Counting
    sign changes rather than raw deltas is what separates the two — a
    tolerance on |dz| alone would flag every graded road."""
    ramp = [10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8]
    assert GS.count_edge_alternation(_road_and_apron(ramp)) == 0


def test_d_sub_tolerance_wobble_is_NOT_counted():
    """Below ``EDGE_ALTERNATION_TOL_M`` it is emit noise, not authorship
    alternation."""
    tiny = C.EDGE_ALTERNATION_TOL_M * 0.3
    wob = [10.0, 10.0 + tiny, 10.0, 10.0 + tiny, 10.0,
           10.0, 10.0, 10.0, 10.0, 10.0]
    assert GS.count_edge_alternation(_road_and_apron(wob)) == 0


def test_d_a_road_with_no_apron_contact_is_not_examined():
    lay = _road_and_apron([10.0, 11.0, 10.0, 11.0, 10.0,
                           10.0, 10.0, 10.0, 10.0, 10.0])
    lay.shapes = [s for s in lay.shapes if s.role != "apron"]
    assert GS.count_edge_alternation(lay) == 0


# ══════════════════════════════════════════════════════════════════════
# §e THE FLAG
# ══════════════════════════════════════════════════════════════════════

def test_e_the_flag_is_default_on():
    assert C.SERVICE_APRON_SPINE is True
    assert C.EDGE_ALTERNATION_TOL_M == 0.25


def test_e_the_flag_off_is_byte_identical(monkeypatch):
    """OFF ⇒ no apron-spine centerline is minted at all, so every
    downstream reader sees exactly the pre-ruling graph."""
    monkeypatch.setenv("O4_SERVICE_APRON_SPINE", "0")
    for m in ("auto_patch.config", "auto_patch.grade_graph"):
        importlib.reload(sys.modules[m])
    try:
        import auto_patch.grade_graph as GG2
        spine = LineString([(0.0, 0.0), (120.0, 0.0)])
        specs = GG2.centerline_specs(_Layout(apron_spines=[spine]))
        assert not [sp for sp in specs if sp[3][0] == "apron_spine"]
    finally:
        monkeypatch.delenv("O4_SERVICE_APRON_SPINE", raising=False)
        for m in ("auto_patch.config", "auto_patch.grade_graph"):
            importlib.reload(sys.modules[m])


def test_d_contact_is_canonical_edge_identity_never_proximity():
    """An apron whose boundary runs along the same line but carries NO
    shared vertices is not a 25b contact and the instrument must not
    invent one — "canonical identity, never proximity"."""
    saw = [10.0, 11.0, 10.0, 11.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    lay = _road_and_apron(saw)
    lay.shapes = [s for s in lay.shapes if s.role != "apron"] + [
        _Shape("apron", Polygon([(0.0, 0.0), (40.0, 0.0),
                                 (40.0, -30.0), (0.0, -30.0)]))]
    assert GS.count_edge_alternation(lay) == 0
