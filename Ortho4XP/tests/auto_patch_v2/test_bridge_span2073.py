"""#2073 (owner 2026-11-13T22:48Z on #1939 site 3: "don't try to grade the
bridge at all"): THE PAGE A DECKLESS MAPPED BRIDGE CARRIES IS NOT GRADED
OVER THE SPAN.

* ``airport/bridge_span``: a groundside road / lot face the bridge's
  centreline crosses, with vertices both over the span and beyond an end,
  is CARRIED; its span vertices are named.  A page the bridge passes over
  (no vertex beyond an end) is not.
* ``constraints/bridge_span_release``: every grade row between a span
  vertex and another vertex of the carried face is withdrawn; rows among
  the approach vertices stay, and so does a row another pavement face holds;
  a span vertex no other pavement holds takes its ground as target.
* ``pipeline/publication.lifted_caps``: the census lifts the carried face.
"""
from __future__ import annotations

import dataclasses as dc

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.constraints import Diff, Source
from tests.auto_patch_v2.test_pad_touch import _lot
from tests.auto_patch_v2.test_roads609e import _map

BRIDGE = {"bridge": "yes", "highway": "service", "layer": "1"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _built(law, way_pts, ring):
    """A lot page (the pack's asphalt along a road) and one mapped bridge."""
    airport, pm = _map(law, [_lot(1, "dsf:pol1", ring)], only=[])
    way = OsmWay(-1063, "airport_small_roads", way_pts, False, dict(BRIDGE))
    return dc.replace(airport, osm_ways=(way,)), pm


# the page runs from x = 0 (the bank) to x = 300; the bridge spans 100..200
ALONG = ((0.0, 90.0), (150.0, 90.0), (300.0, 90.0),
         (300.0, 110.0), (150.0, 110.0), (0.0, 110.0))


def test_a_page_along_the_bridge_is_carried_its_span_vertices_named(law):
    from auto_patch_v2.airport.bridge_span import bridge_span_faces
    airport, pm = _built(law, ((100.0, 100.0), (200.0, 100.0)), ALONG)
    spans = bridge_span_faces(pm, law, airport)
    assert len(spans) == 1
    (fid, span), = spans.items()
    assert pm.faces[fid].ref == "dsf:pol1"
    assert {round(pm.vertices[v].xy[0]) for v in span} == {150}
    # no bridge, or a bridge the structures built a deck for: nothing
    assert bridge_span_faces(pm, law, dc.replace(airport, osm_ways=())) == {}


def test_a_page_the_bridge_passes_over_is_not_carried(law):
    from auto_patch_v2.airport.bridge_span import bridge_span_faces
    # the bridge crosses the page's width: every vertex beside the span
    airport, pm = _built(law, ((150.0, 0.0), (150.0, 200.0)), ALONG)
    assert bridge_span_faces(pm, law, airport) == {}


def test_span_rows_are_withdrawn_the_approach_keeps_its_own(law):
    from auto_patch_v2.airport.bridge_span import bridge_span_faces
    from auto_patch_v2.constraints.bridge_span_release import span_lifts, span_release
    from auto_patch_v2.pipeline.publication import lifted_caps
    airport, pm = _built(law, ((100.0, 100.0), (200.0, 100.0)), ALONG)
    spans = bridge_span_faces(pm, law, airport)
    pm = dc.replace(pm, bridge_span=spans)
    (fid, span), = spans.items()
    ring = sorted(set(pm.ring_vertices(pm.faces[fid].ring)), key=lambda v: pm.vertices[v].xy)
    s = next(iter(span))
    bank = [v for v in ring if v not in span]
    src = Source("roads", "common.roles longitudinal (2026-08-03)", (f"face:{fid}",))
    across = Diff(s, bank[0], 0.05, 150.0, src)
    approach = Diff(bank[0], bank[1], 0.05, 20.0, src)
    out, n = span_release([across, approach], pm, law)
    assert n == 1 and out[0] == approach
    # a span vertex no other pavement holds takes its own ground as target
    targets = {r.terms[0][0]: r.lo for r in out[1:]}
    assert set(targets) == set(span)
    assert targets[s] == pytest.approx(pm.vertices[s].dem_z)
    assert fid in span_lifts(pm, law)
    assert fid in lifted_caps(pm, law)
