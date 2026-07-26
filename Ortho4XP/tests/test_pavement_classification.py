"""Pavement classification v1 — the evidence vote, the R-VETO, and the
R-SPLIT mouth cut.

Headless and hermetic: every layout here is hand-built in metre space
with a synthetic road feed and a synthetic OSM aeroway layer, so nothing
touches the production data root, X-Plane, or the network.

What each block pins:

* the vote — R1 keeps on positive airside evidence, R2/R3/R4/R5 demote on
  road / opening / parking / partial-road evidence, and R1 BEATS all of
  them (the owner's R-VETO: "a road inside, or sharing an edge with a
  real apron must follow the apron's grade");
* the mouth split — a wide body with a long thin road tail decomposes at
  the mouth, the body keeps apron, the tail leaves;
* the flank test — the SAME geometry with pavement along both flanks
  keeps its tail (R-VETO again: that road has not left the apron);
* the gate — OFF touches nothing;
* the ordering — a demotion severs the runway touch-chain, so the
  existing ``_reclassify_runway_disconnected_to_groundside`` cascade
  picks up whatever the demotion orphaned.
"""

from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import Polygon, box

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ``pipeline`` first: junction_repair ↔ elevation is an import cycle and
# the package's own CLAUDE.md requires entering through the pipeline.
import auto_patch.pipeline as _PIPELINE  # noqa: E402,F401
from auto_patch import pavement_classification as PC  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    ROLE_APRON,
    ROLE_BUILDING,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_RUNWAY,
    ROLE_SERVICE_ROAD,
    BuiltShape,
    PavementLayout,
)
from auto_patch.osm_load import AirportRoadNetwork  # noqa: E402

ANCHOR = (30.0, 31.0)


# ── fixture builders ─────────────────────────────────────────────────

def _layout(shapes=(), runway_union=None):
    layout = PavementLayout(icao="TEST", anchor=ANCHOR)
    layout.shapes = list(shapes)
    layout.runway_union = runway_union
    return layout


def _road_feed(layout, lines, tags=None, widths=None):
    """Publish a synthetic ``airport_road_network`` on ``layout``.

    ``lines`` are lists of metre-space points; they are projected back
    to lat/lon so the feed holds exactly what a real one would.
    """
    nodes, ways = {}, []
    node_id = 0
    for i, points in enumerate(lines):
        refs = []
        for x, y in points:
            latitude, longitude = layout.m_to_ll(x, y)
            nodes[str(node_id)] = (latitude, longitude)
            refs.append(str(node_id))
            node_id += 1
        way_tags = dict(highway="service")
        if tags and i in tags:
            way_tags.update(tags[i])
        ways.append((str(i), refs, way_tags))
    resolved = {str(i): (widths.get(i, 8.0) if widths else 8.0)
                for i in range(len(lines))}
    layout.airport_road_network = AirportRoadNetwork(
        "TEST", (29.9, 30.9, 30.1, 31.1), nodes, ways, {}, resolved,
        "test")
    layout._airport_road_feed_corridors_cache = None
    return layout


def _osm_aeroway(layout, features):
    """``features`` = [(aeroway value, [metre points], closed?)]."""
    nodes, ways = {}, []
    node_id = 0
    for i, (value, points, closed) in enumerate(features):
        pts = list(points)
        if closed and pts[0] != pts[-1]:
            pts.append(pts[0])
        refs = []
        for x, y in pts:
            latitude, longitude = layout.m_to_ll(x, y)
            nodes[f"n{node_id}"] = (latitude, longitude)
            refs.append(f"n{node_id}")
            node_id += 1
        ways.append((f"w{i}", refs, {"aeroway": value}))
    layout._osm_airport_features = (nodes, ways)
    return layout


def _rect(x0, y0, x1, y1):
    return box(x0, y0, x1, y1)


def _evidence(**kwargs):
    return PC.PavementEvidence(**kwargs)


# ═════════════════════════════════════════════════════════════════════
# The vote
# ═════════════════════════════════════════════════════════════════════

def test_r1_positive_airside_evidence_keeps_the_shape():
    """R1 — any of the three airside backings at or above the threshold."""
    for field in ("osm_apron", "stand", "taxi"):
        verdict, reason = PC.whole_shape_verdict(
            _evidence(area=50000.0, **{field: 0.30}))
        assert verdict == "airside", field
        assert "OSM airside" in reason


def test_r1_vetoes_every_landside_rule():
    """R-VETO: a real apron stays apron however much road crosses it.

    The owner's ruling in one assertion — this evidence trips R2 (road
    92 %), R4 (parking 90 %) and R5 at once, and R1 still wins.
    """
    verdict, _ = PC.whole_shape_verdict(_evidence(
        area=80000.0, road=0.92, parking=0.90, osm_apron=0.40,
        d_runway=900.0))
    assert verdict == "airside"


def test_r2_road_corridor_dominates():
    verdict, reason = PC.whole_shape_verdict(
        _evidence(area=90302.0, road=0.753, d_runway=900.0))
    assert verdict == "groundside"
    assert reason.startswith("road")


def test_r2_needs_the_airside_evidence_to_be_weak():
    """Road-dominant but with 15 % airside backing: R2 must not fire."""
    verdict, _ = PC.whole_shape_verdict(
        _evidence(area=90000.0, road=0.75, osm_apron=0.15, d_runway=20.0))
    assert verdict == "airside"


def test_r3_nowhere_wide_enough_for_an_aircraft():
    verdict, reason = PC.whole_shape_verdict(
        _evidence(area=10682.0, road=0.10, opening_vehicle=True))
    assert verdict == "groundside"
    assert "opening" in reason


def test_r4_parking_lot():
    verdict, reason = PC.whole_shape_verdict(
        _evidence(area=20000.0, road=0.05, parking=0.55, d_runway=800.0))
    assert verdict == "groundside"
    assert reason.startswith("parking")


def test_r5_partial_road_no_airside_evidence_away_from_the_runway():
    verdict, reason = PC.whole_shape_verdict(
        _evidence(area=5000.0, road=0.20, d_runway=800.0))
    assert verdict == "groundside"
    assert "no airside evidence" in reason
    # …the SAME shape beside a runway is airside (a shoulder, not a lot).
    verdict, _ = PC.whole_shape_verdict(
        _evidence(area=5000.0, road=0.20, d_runway=40.0))
    assert verdict == "airside"


def test_no_evidence_at_all_keeps_the_shape():
    """The classifier votes on POSITIVE evidence: silence is a keep."""
    verdict, reason = PC.whole_shape_verdict(_evidence(area=50000.0))
    assert verdict == "airside"
    assert reason == "no groundside evidence"


# ═════════════════════════════════════════════════════════════════════
# Evidence measurement against the real sources
# ═════════════════════════════════════════════════════════════════════

def test_evidence_reads_the_road_feed_and_the_aeroway_layer():
    apron = _rect(0.0, 0.0, 200.0, 200.0)
    layout = _layout([BuiltShape(polygon=apron, role=ROLE_APRON)])
    # One road straight through the middle, 8 m wide (+1 m shoulder each
    # side by the shared corridor law) ⇒ 10 m of 200 m = 5 %.
    _road_feed(layout, [[(-50.0, 100.0), (250.0, 100.0)]])
    _osm_aeroway(layout, [("apron", [(0.0, 0.0), (100.0, 0.0),
                                     (100.0, 200.0), (0.0, 200.0)], True)])
    sources = PC.evidence_sources(layout)
    evidence = PC.shape_evidence(apron, sources)
    assert evidence.road == pytest.approx(10.0 / 200.0, abs=0.01)
    assert evidence.osm_apron == pytest.approx(0.5, abs=0.01)
    assert evidence.airside == pytest.approx(0.5, abs=0.01)


def test_missing_evidence_layers_read_zero_not_error():
    apron = _rect(0.0, 0.0, 100.0, 100.0)
    layout = _layout([BuiltShape(polygon=apron, role=ROLE_APRON)])
    sources = PC.evidence_sources(layout)
    evidence = PC.shape_evidence(apron, sources)
    assert (evidence.road, evidence.airside, evidence.parking) == (
        0.0, 0.0, 0.0)


# ═════════════════════════════════════════════════════════════════════
# R-SPLIT — the mouth cut
# ═════════════════════════════════════════════════════════════════════

def _body_with_tail(tail_length_m=400.0, tail_width_m=16.0):
    """A 300x300 m apron body with one long thin arm off its east side.

    The arm is the owner's "5 km of thin roadway" in miniature: it
    leaves the body through a mouth exactly as wide as the arm.
    """
    half = 0.5 * tail_width_m
    return Polygon([
        (0.0, 0.0), (300.0, 0.0),
        (300.0, 150.0 - half),
        (300.0 + tail_length_m, 150.0 - half),
        (300.0 + tail_length_m, 150.0 + half),
        (300.0, 150.0 + half),
        (300.0, 300.0), (0.0, 300.0),
    ])


def test_mouth_split_separates_a_long_thin_tail_from_a_wide_body():
    result = PC.split_body_and_tails(_body_with_tail())
    assert result.n_cuts >= 1
    assert len(result.tails) == 1
    tail = result.tails[0]
    assert tail.area == pytest.approx(400.0 * 16.0, rel=0.05)
    assert result.body.area == pytest.approx(300.0 * 300.0, rel=0.05)
    # The cut is AT the mouth: body and tail share the chord, no gap.
    assert result.body.distance(tail) < 0.01


def test_a_compact_apron_is_not_split():
    """No thin arm ⇒ no cut ⇒ the polygon comes back whole."""
    result = PC.split_body_and_tails(_rect(0.0, 0.0, 300.0, 300.0))
    assert result.tails == []
    assert result.n_cuts == 0
    assert result.body.area == pytest.approx(300.0 * 300.0)


def test_a_short_nib_is_not_a_tail():
    """An arm shorter than the minimum tail length stays with the body."""
    result = PC.split_body_and_tails(_body_with_tail(tail_length_m=25.0))
    assert result.tails == []
    assert result.body.area == pytest.approx(
        _body_with_tail(tail_length_m=25.0).area)


def test_a_corridor_between_two_pads_is_not_a_tail():
    """A DUMBBELL — pad, corridor, pad — has not "left the apron".

    Cutting the corridor out would leave the body in two pieces, and
    ``BuiltShape.polygon`` is a single ring by contract, so the shape
    stays whole.  (This is the case that reached
    ``groundside._verts_buckets`` as a MultiPolygon ``exterior``
    AttributeError on the first HECA build of the feature.)
    """
    dumbbell = Polygon([
        (0.0, 0.0), (200.0, 0.0), (200.0, 142.0),
        (500.0, 142.0), (500.0, 0.0), (700.0, 0.0), (700.0, 300.0),
        (500.0, 300.0), (500.0, 158.0), (200.0, 158.0), (200.0, 300.0),
        (0.0, 300.0),
    ])
    result = PC.split_body_and_tails(dumbbell)
    assert result.tails == []
    assert result.body.geom_type == "Polygon"
    assert result.body.area == pytest.approx(dumbbell.area)


def test_a_wide_arm_is_not_a_tail():
    """An arm wider than a carriageway is apron, not road."""
    result = PC.split_body_and_tails(
        _body_with_tail(tail_length_m=400.0, tail_width_m=90.0))
    assert result.tails == []


# ── the flank test ───────────────────────────────────────────────────

def test_flank_test_passes_a_tail_with_empty_terrain_on_both_sides():
    tail = _rect(300.0, 142.0, 700.0, 158.0)
    body = BuiltShape(polygon=_rect(0.0, 0.0, 300.0, 300.0),
                      role=ROLE_APRON)
    layout = _layout([body])
    index = PC._pavement_adjacency_index(layout)
    # The only other pavement is the body the tail was cut from, and it
    # is excluded as the tail's owner — the mouth chord is not a flank.
    assert PC._flank_contact_fraction(tail, index, owner=body) == 0.0


def test_flank_test_fails_a_tail_with_pavement_along_both_sides():
    """R-VETO in geometry: a road running THROUGH apron pavement."""
    tail = _rect(300.0, 142.0, 700.0, 158.0)
    body = BuiltShape(polygon=_rect(0.0, 0.0, 300.0, 300.0),
                      role=ROLE_APRON)
    layout = _layout([
        body,
        BuiltShape(polygon=_rect(300.0, 100.0, 700.0, 141.0),
                   role=ROLE_APRON),
        BuiltShape(polygon=_rect(300.0, 159.0, 700.0, 200.0),
                   role=ROLE_APRON),
    ])
    index = PC._pavement_adjacency_index(layout)
    assert PC._flank_contact_fraction(tail, index, owner=body) > 0.8


# ── the split, end to end through the pass ───────────────────────────

def _split_layout(flanked: bool):
    """A real apron body (OSM-backed) with a road-backed thin tail."""
    apron_shape = BuiltShape(polygon=_body_with_tail(), role=ROLE_APRON)
    shapes = [apron_shape]
    if flanked:
        shapes += [
            BuiltShape(polygon=_rect(300.0, 100.0, 700.0, 141.0),
                       role=ROLE_APRON),
            BuiltShape(polygon=_rect(300.0, 159.0, 700.0, 200.0),
                       role=ROLE_APRON),
        ]
    layout = _layout(shapes)
    # A road down the middle of the tail, wide enough to back it.
    _road_feed(layout, [[(280.0, 150.0), (720.0, 150.0)]],
               widths={0: 14.0})
    # OSM apron polygon covering the BODY only — the tail has none.
    _osm_aeroway(layout, [("apron", [(0.0, 0.0), (300.0, 0.0),
                                     (300.0, 300.0), (0.0, 300.0)], True)])
    return layout, apron_shape


def test_split_demotes_the_road_tail_and_keeps_the_body_apron():
    layout, apron_shape = _split_layout(flanked=False)
    summary = PC.classify_pavement_v1(layout, icao="TEST")
    assert summary["splits"] == 1
    assert summary["tails"] == 1
    # The body kept its airside role and its area…
    assert apron_shape.role == ROLE_APRON
    assert apron_shape.polygon.area == pytest.approx(300.0 * 300.0, rel=0.05)
    # …and the tail became a landside shape of its own.
    tails = [s for s in layout.shapes
             if s.role in (ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD)]
    assert len(tails) == 1
    assert tails[0].polygon.area == pytest.approx(400.0 * 16.0, rel=0.05)


def test_split_tail_that_tracks_a_road_centerline_becomes_a_service_road():
    layout, _ = _split_layout(flanked=False)
    PC.classify_pavement_v1(layout, icao="TEST")
    tails = [s for s in layout.shapes if s is not layout.shapes[0]]
    assert [s.role for s in tails] == [ROLE_SERVICE_ROAD]


def test_r_veto_keeps_a_road_that_never_left_the_apron():
    """Same body, same road, but pavement along BOTH flanks of the tail.

    The road is inside the apron, so it "must follow the apron's grade":
    no split, no demotion, the body keeps every square metre.
    """
    layout, apron_shape = _split_layout(flanked=True)
    summary = PC.classify_pavement_v1(layout, icao="TEST")
    assert summary["splits"] == 0
    assert summary["flips"] == 0
    assert apron_shape.role == ROLE_APRON
    assert apron_shape.polygon.area == pytest.approx(
        _body_with_tail().area, rel=0.001)


# ═════════════════════════════════════════════════════════════════════
# The pass: whole-shape demotion, the gate, and the cascade
# ═════════════════════════════════════════════════════════════════════

def _road_blob_layout():
    """A runway, a genuine apron chained to it, and a landside road blob
    between them — the HECA shape in miniature."""
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 45.0),
                        role=ROLE_RUNWAY)
    apron = BuiltShape(polygon=_rect(0.0, 0.0, 200.0, 200.0),
                       role=ROLE_APRON)
    road_blob = BuiltShape(polygon=_rect(200.0, 0.0, 260.0, 600.0),
                           role=ROLE_APRON)
    layout = _layout([runway, apron, road_blob],
                     runway_union=runway.polygon)
    _road_feed(layout, [[(230.0, -20.0), (230.0, 620.0)]],
               widths={0: 40.0})
    _osm_aeroway(layout, [("apron", [(0.0, 0.0), (200.0, 0.0),
                                     (200.0, 200.0), (0.0, 200.0)], True)])
    return layout, runway, apron, road_blob


def test_whole_shape_demotion_of_a_road_blob():
    layout, _runway, apron, road_blob = _road_blob_layout()
    summary = PC.classify_pavement_v1(layout, icao="TEST")
    assert summary["flips"] == 1
    assert road_blob.role in (ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD)
    assert apron.role == ROLE_APRON            # OSM-backed ⇒ R1 keep
    assert summary["flip_area_m2"] == pytest.approx(60.0 * 600.0, rel=0.01)


def test_gate_off_touches_nothing(monkeypatch):
    monkeypatch.setattr(PC, "PAVEMENT_CLASS_V1", False)
    layout, _runway, apron, road_blob = _road_blob_layout()
    before = [(s.role, s.polygon.wkb) for s in layout.shapes]
    summary = PC.classify_pavement_v1(layout, icao="TEST")
    assert summary["enabled"] is False
    assert summary["flips"] == 0
    assert [(s.role, s.polygon.wkb) for s in layout.shapes] == before
    assert not hasattr(layout, "_pavement_class_sources")


def test_no_evidence_available_is_a_skip_not_a_guess():
    """No road feed and no aeroway layer ⇒ the pass must not demote."""
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 45.0),
                        role=ROLE_RUNWAY)
    blob = BuiltShape(polygon=_rect(200.0, 0.0, 260.0, 600.0),
                      role=ROLE_APRON)
    layout = _layout([runway, blob], runway_union=runway.polygon)
    summary = PC.classify_pavement_v1(layout, icao="TEST")
    assert summary["flips"] == 0
    assert blob.role == ROLE_APRON


def test_demotion_severs_the_runway_touch_chain():
    """ORDERING: the pass runs before the runway-disconnected classifier,
    so an apron reachable ONLY through a demoted shape is picked up by
    that existing cascade in the same build.

    Chain: runway — road blob — outer apron.  The outer apron is genuine
    aircraft pavement by its own evidence (no road on it), but its only
    route back to the runway is through the blob; once the blob leaves
    the airside graph the outer apron is a landside island.
    """
    from auto_patch.junction_repair import (
        _reclassify_runway_disconnected_to_groundside)

    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 200.0),
                        role=ROLE_RUNWAY)
    blob = BuiltShape(polygon=_rect(0.0, 0.0, 60.0, 200.0),
                      role=ROLE_APRON)
    outer = BuiltShape(polygon=_rect(60.0, 0.0, 260.0, 200.0),
                       role=ROLE_APRON)
    # The runway-disconnected pass only runs at airports that HAVE a
    # terminal (user 2026-06-11) — give it one, well clear of the chain.
    terminal = BuiltShape(polygon=_rect(400.0, 400.0, 460.0, 460.0),
                          role=ROLE_BUILDING)
    layout = _layout([runway, blob, outer, terminal],
                     runway_union=runway.polygon)
    _road_feed(layout, [[(30.0, -20.0), (30.0, 220.0)]], widths={0: 40.0})
    _osm_aeroway(layout, [("apron", [(0.0, 0.0), (0.0, 0.0)], False)])

    # Before: both aprons chain to the runway.
    assert _reclassify_runway_disconnected_to_groundside(
        layout, icao="TEST") == 0

    summary = PC.classify_pavement_v1(layout, icao="TEST")
    assert summary["flips"] == 1
    assert blob.role in (ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD)
    assert outer.role == ROLE_APRON            # not this pass's doing

    # After: the cascade fires on the now-orphaned outer apron.
    assert _reclassify_runway_disconnected_to_groundside(
        layout, icao="TEST") == 1
    assert outer.role == ROLE_GROUNDSIDE_PAVEMENT


def test_summary_is_published_on_the_layout():
    layout, _runway, _apron, _blob = _road_blob_layout()
    PC.classify_pavement_v1(layout, icao="TEST")
    assert layout.pavement_class_summary["flips"] == 1
    assert len(layout.pavement_class_decisions) == 2
    assert {d["verdict"] for d in layout.pavement_class_decisions} == {
        "airside", "groundside"}


def test_tiny_residue_slivers_never_vote():
    """A sub-threshold sliver is a geometry artefact, not a car park."""
    sliver = BuiltShape(polygon=_rect(200.0, 0.0, 205.0, 10.0),
                        role=ROLE_APRON)
    layout = _layout([sliver])
    _road_feed(layout, [[(202.0, -20.0), (202.0, 30.0)]], widths={0: 40.0})
    summary = PC.classify_pavement_v1(layout, icao="TEST")
    assert summary["candidates"] == 0
    assert sliver.role == ROLE_APRON
