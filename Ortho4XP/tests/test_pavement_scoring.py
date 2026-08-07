"""Pavement scoring classifier v2 — evidence fusion, shadow phase.

Spec: ``docs/specs/pavement-scoring-classifier-spec.md``.

Headless and hermetic, exactly like ``test_pavement_classification``:
every layout is hand-built in metre space with synthetic apt.dat
records, a synthetic road feed and a synthetic OSM aeroway layer, so
nothing touches the production data root, X-Plane or the network.  The
one test that needs a real apt.dat writes a four-line one into
``tmp_path`` and points the finder at that tree.

What each block pins:

* the NAME BUCKETS — the row-110 keyword priority the whole name prior
  rests on (service beats taxi beats apron, empty/None safe);
* the EVIDENCE LAYERS — ``score_sources`` buckets each named polygon
  into the right ``CoverIndex`` and totals the named area;
* RELIABILITY — an airport with no sources reads all-zero (so silence
  is never negative evidence), a rich one reads in (0, 1], and both are
  memoised per layout;
* the FEATURE VECTOR — coverage fractions and the two morphology flags;
* the HARD GATES — G-FREE-ROAD, G-VETO, G-CHAIN and the G-CONFLICT
  fallback when two of them contradict each other;
* the VERDICT — argmax + margin band, and the development ruling that a
  LOW-confidence shape keeps the legacy chain's answer;
* the SHADOW PASS — it scores every eligible shape, skips fragments,
  publishes decisions with lat/lon, and MUTATES NOTHING;
* the GLOBAL-AIRPORTS CROSS-REFERENCE — off without a root, memoised,
  and reading the default pack's names when one is there;
* the GATE — ``PAVEMENT_SCORE_V2 = "off"`` stashes nothing.
"""

from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import LineString, Polygon, box

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ``pipeline`` first: junction_repair ↔ elevation is an import cycle and
# the package's own CLAUDE.md requires entering through the pipeline.
import auto_patch.pipeline as _PIPELINE  # noqa: E402,F401
from auto_patch import pavement_classification as PC  # noqa: E402
from auto_patch import pavement_scoring as PS  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    ROLE_APRON,
    ROLE_BUILDING,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_JUNCTION,
    ROLE_RUNWAY,
    BuiltShape,
    PavementLayout,
)
from auto_patch.osm_load import AirportRoadNetwork  # noqa: E402

ANCHOR = (30.0, 31.0)


@pytest.fixture(autouse=True)
def _shadow_mode(monkeypatch):
    """Pin the gate to ``shadow`` for every test in this module.

    ``PAVEMENT_SCORE_V2`` is env-overridable, so without this the suite's
    verdict would depend on whoever last exported
    ``O4_PAVEMENT_SCORE_V2``.  The gate-OFF test re-patches on top.
    """
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_V2", "shadow")


# ── fixture builders ─────────────────────────────────────────────────

def _layout(shapes=(), **fields):
    """A bare :class:`PavementLayout` with ``fields`` stashed on it.

    Every test builds a FRESH layout: ``evidence_sources`` /
    ``score_sources`` / ``source_reliability`` all memoise on the layout
    object, so a shared fixture would leak one test's evidence into the
    next one's verdict.
    """
    layout = PavementLayout(icao="TEST", anchor=ANCHOR)
    layout.shapes = list(shapes)
    for key, value in fields.items():
        setattr(layout, key, value)
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


# ═════════════════════════════════════════════════════════════════════
# The apt.dat row-110 name buckets
# ═════════════════════════════════════════════════════════════════════

def test_name_bucket_maps_the_three_keyword_families():
    assert PS._name_bucket("TWY A") == "taxi"
    assert PS._name_bucket("Taxilane B7") == "taxi"
    assert PS._name_bucket("RAMP 1") == "apron"
    assert PS._name_bucket("Terminal Apron") == "apron"
    assert PS._name_bucket("SERVICE ROAD") == "service"
    assert PS._name_bucket("GSE staging") == "service"


def test_name_bucket_priority_is_service_then_taxi_then_apron():
    """Order matters: "SERVICE ROAD" is a road, not "road-the-noun".

    A name carrying tokens from two families must resolve to the more
    specific one — service beats taxi beats apron.
    """
    assert PS._name_bucket("TAXIWAY SERVICE ROAD") == "service"
    assert PS._name_bucket("APRON PERIMETER ROAD") == "service"
    assert PS._name_bucket("TWY A RAMP") == "taxi"
    assert PS._name_bucket("TERMINAL RAMP") == "apron"


def test_name_bucket_is_empty_and_none_safe():
    assert PS._name_bucket("") is None
    assert PS._name_bucket(None) is None
    assert PS._name_bucket("   ") is None
    assert PS._name_bucket("Charlie") is None


# ═════════════════════════════════════════════════════════════════════
# Stage 1 — the v2-only evidence layers
# ═════════════════════════════════════════════════════════════════════

TWY_POLY = box(0.0, 0.0, 100.0, 20.0)
RAMP_POLY = box(200.0, 0.0, 300.0, 100.0)
SVC_POLY = box(400.0, 0.0, 500.0, 10.0)
GRAVEL_POLY = box(600.0, 0.0, 700.0, 50.0)


def _named_records_layout():
    return _layout(apt_pavement_records=[
        (TWY_POLY, "TWY A", 1),
        (RAMP_POLY, "RAMP 1", 2),
        (SVC_POLY, "SERVICE ROAD", 1),
        (GRAVEL_POLY, "Charlie", 3),
    ])


def test_score_sources_buckets_named_polygons_by_keyword():
    sources = PS.score_sources(_named_records_layout())
    # A probe sitting wholly inside one named polygon reads 1.0 there
    # and 0.0 in every other bucket.
    probes = {
        "name_taxi": box(10.0, 5.0, 40.0, 15.0),
        "name_apron": box(220.0, 20.0, 280.0, 80.0),
        "name_service": box(410.0, 2.0, 460.0, 8.0),
    }
    for bucket, probe in probes.items():
        for name in ("name_taxi", "name_apron", "name_service"):
            covered = getattr(sources, name).cover_fraction(probe)
            assert covered == pytest.approx(1.0 if name == bucket else 0.0,
                                            abs=1e-6), (bucket, name)


def test_score_sources_cover_fraction_is_the_overlap_ratio():
    sources = PS.score_sources(_named_records_layout())
    # Half in the RAMP polygon, half on bare ground.
    probe = box(150.0, 0.0, 250.0, 100.0)
    assert sources.name_apron.cover_fraction(probe) == pytest.approx(
        0.5, abs=1e-6)


def test_score_sources_unpaved_layer_and_named_area():
    layout = _named_records_layout()
    sources = PS.score_sources(layout)
    # Only the gravel record (surface_code 3) is unpaved…
    assert sources.unpaved.cover_fraction(
        box(610.0, 10.0, 690.0, 40.0)) == pytest.approx(1.0, abs=1e-6)
    assert sources.unpaved.cover_fraction(TWY_POLY) == pytest.approx(0.0)
    # …and it is UNNAMED, so it contributes no named area.
    assert sources.named_area_m2 == pytest.approx(
        TWY_POLY.area + RAMP_POLY.area + SVC_POLY.area)


def test_score_sources_memoizes_on_the_layout():
    layout = _named_records_layout()
    first = PS.score_sources(layout)
    assert PS.score_sources(layout) is first
    assert layout._pavement_score_sources is first


def test_score_sources_builds_truck_and_spine_territory():
    truck = LineString([(0.0, -50.0), (0.0, 50.0)])
    spine = LineString([(0.0, 200.0), (300.0, 200.0)])
    layout = _layout(apt_service_centerlines=[(truck, "SVC 1")],
                     apt_taxi_centerlines=[(spine, "A")],
                     apt_only_pavement_polys=[box(0.0, 0.0, 50.0, 50.0)])
    sources = PS.score_sources(layout)
    assert sources.truck_len_m == pytest.approx(100.0)
    assert sources.spine_len_m == pytest.approx(300.0)
    # 8 m truck buffer, 25 m spine buffer (config defaults).
    assert sources.truck_corridors.cover_fraction(
        box(-4.0, -10.0, 4.0, 10.0)) == pytest.approx(1.0, abs=1e-6)
    assert sources.truck_corridors.cover_fraction(
        box(20.0, -10.0, 30.0, 10.0)) == pytest.approx(0.0)
    assert sources.spine_buffers.cover_fraction(
        box(50.0, 190.0, 150.0, 210.0)) == pytest.approx(1.0, abs=1e-6)
    assert sources.apt_only.cover_fraction(
        box(10.0, 10.0, 20.0, 20.0)) == pytest.approx(1.0, abs=1e-6)


def test_score_sources_on_a_bare_layout_is_all_empty():
    sources = PS.score_sources(_layout())
    assert not sources.name_apron
    assert not sources.name_taxi
    assert not sources.name_service
    assert not sources.truck_corridors
    assert sources.named_area_m2 == 0.0
    assert sources.truck_len_m == 0.0
    assert sources.truck_lines is None


# ═════════════════════════════════════════════════════════════════════
# Stage 0 — per-airport source reliability
# ═════════════════════════════════════════════════════════════════════

def test_reliability_of_an_empty_airport_is_all_zero():
    """Silence is not negative evidence: an absent source scores 0."""
    reliability = PS.source_reliability(_layout())
    assert (reliability.apt_names, reliability.osm_aeroway,
            reliability.road_feed, reliability.truck, reliability.spine,
            reliability.alt_apt) == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    # …and every feature therefore contributes nothing.
    assert reliability.of("name_apron") == 0.0
    assert reliability.of("osm_taxi") == 0.0
    # Purely geometric features are always fully trusted.
    assert reliability.of("wide_blob") == 1.0
    assert reliability.of("runway_connected") == 1.0


def _rich_layout():
    """An airport with all five primary sources present."""
    field_poly = box(0.0, 0.0, 400.0, 400.0)
    layout = _layout(
        source_pavement_union=field_poly,
        apt_pavement_records=[(box(0.0, 0.0, 200.0, 200.0), "RAMP 1", 1)],
        apt_service_centerlines=[
            (LineString([(0.0, 300.0), (0.0, 600.0)]), "SVC")],
        apt_taxi_centerlines=[
            (LineString([(0.0, 250.0), (700.0, 250.0)]), "A")],
    )
    _osm_aeroway(layout, [
        ("apron", [(0.0, 0.0), (150.0, 0.0), (150.0, 150.0), (0.0, 150.0)],
         True),
        ("taxiway", [(0.0, 250.0), (400.0, 250.0)], False),
    ])
    _road_feed(layout, [
        [(0.0, 380.0), (400.0, 380.0)],
        [(200.0, 300.0), (200.0, 400.0)],
    ])
    return layout


def test_reliability_of_a_rich_airport_is_in_the_unit_interval():
    reliability = PS.source_reliability(_rich_layout())
    for source in ("apt_names", "osm_aeroway", "road_feed", "truck",
                   "spine"):
        value = getattr(reliability, source)
        assert 0.0 < value <= 1.0, (source, value)
    # apt names: 200x200 named of a 400x400 field.
    assert reliability.apt_names == pytest.approx(0.25)
    # road feed: 2 ways of the 25 that count as "fully present".
    assert reliability.road_feed == pytest.approx(2.0 / 25.0)
    # truck: 300 m of the 500 m denominator.
    assert reliability.truck == pytest.approx(300.0 / 500.0)
    # spine: 700 m of the 1000 m denominator.
    assert reliability.spine == pytest.approx(700.0 / 1000.0)


def test_reliability_memoizes_on_the_layout():
    layout = _rich_layout()
    first = PS.source_reliability(layout)
    assert PS.source_reliability(layout) is first
    assert layout._pavement_score_reliability is first


def test_reliability_clamps_an_over_supplied_source_at_one():
    layout = _layout(
        source_pavement_union=box(0.0, 0.0, 100.0, 100.0),
        # Named polygons covering FOUR times the source pavement area.
        apt_pavement_records=[(box(0.0, 0.0, 200.0, 200.0), "RAMP 1", 1)],
        apt_taxi_centerlines=[
            (LineString([(0.0, 0.0), (0.0, 9000.0)]), "A")],
    )
    reliability = PS.source_reliability(layout)
    assert reliability.apt_names == 1.0
    assert reliability.spine == 1.0


# ═════════════════════════════════════════════════════════════════════
# Stage 2 — the per-shape feature vector
# ═════════════════════════════════════════════════════════════════════

def test_features_read_a_fully_overlapping_osm_apron_as_one():
    shape = _rect(0.0, 0.0, 100.0, 20.0)
    layout = _layout([BuiltShape(polygon=shape, role=ROLE_APRON)])
    _osm_aeroway(layout, [("apron", [(-20.0, -20.0), (120.0, -20.0),
                                     (120.0, 40.0), (-20.0, 40.0)], True)])
    features = PS.shape_features(shape, layout)
    assert features["osm_apron"] == pytest.approx(1.0, abs=1e-6)
    assert features["osm_taxi"] == 0.0
    assert features["name_apron"] == 0.0
    # 100 x 20 m fits an aircraft, so it is not vehicle-only pavement…
    assert features["narrow_only"] == 0.0
    # …and it is nowhere 50 m across, so it is not an apron blob either.
    assert features["wide_blob"] == 0.0


def test_features_flag_a_five_metre_corridor_as_vehicle_only():
    """R3 semantics: nowhere on this shape can an aircraft fit."""
    corridor = _rect(0.0, 0.0, 100.0, 5.0)
    layout = _layout([BuiltShape(polygon=corridor, role=ROLE_APRON)])
    features = PS.shape_features(corridor, layout)
    assert features["narrow_only"] == 1.0
    assert features["wide_blob"] == 0.0


def test_features_flag_a_wide_blob():
    blob = _rect(0.0, 0.0, 300.0, 300.0)
    layout = _layout([BuiltShape(polygon=blob, role=ROLE_APRON)])
    features = PS.shape_features(blob, layout)
    assert features["wide_blob"] == 1.0
    assert features["narrow_only"] == 0.0


def test_features_report_connectivity_only_when_the_guard_is_live():
    shape = _rect(0.0, 0.0, 100.0, 100.0)
    layout = _layout([BuiltShape(polygon=shape, role=ROLE_APRON)])
    inert = PS.shape_features(shape, layout, connected=None)
    assert (inert["runway_connected"], inert["runway_disconnected"]) == (
        0.0, 0.0)
    on = PS.shape_features(shape, layout, connected=True)
    assert (on["runway_connected"], on["runway_disconnected"]) == (1.0, 0.0)
    off = PS.shape_features(shape, layout, connected=False)
    assert (off["runway_connected"], off["runway_disconnected"]) == (0.0, 1.0)


def test_features_measure_perimeter_enclosure_against_other_pavement():
    tail = _rect(300.0, 142.0, 700.0, 158.0)
    owner = BuiltShape(polygon=_rect(0.0, 0.0, 300.0, 300.0),
                       role=ROLE_APRON)
    flanks = [
        BuiltShape(polygon=_rect(300.0, 100.0, 700.0, 141.0),
                   role=ROLE_APRON),
        BuiltShape(polygon=_rect(300.0, 159.0, 700.0, 200.0),
                   role=ROLE_APRON),
    ]
    layout = _layout([owner] + flanks)
    adjacency = PC._pavement_adjacency_index(layout)
    features = PS.shape_features(tail, layout, adjacency=adjacency,
                                 owner=owner)
    assert features["enclosed_by_airside"] > 0.8
    assert features["open_perimeter"] == pytest.approx(
        1.0 - features["enclosed_by_airside"], abs=1e-3)
    # With no adjacency index at all the flanks read empty.
    bare = PS.shape_features(tail, _layout())
    assert bare["enclosed_by_airside"] == 0.0
    assert bare["open_perimeter"] == 1.0


def test_features_read_third_party_provenance_from_the_apt_only_layer():
    shape = _rect(0.0, 0.0, 100.0, 100.0)
    # apt.dat drew only the western half; the rest came from a DSF.
    layout = _layout(apt_only_pavement_polys=[box(0.0, 0.0, 50.0, 100.0)])
    features = PS.shape_features(shape, layout)
    assert features["third_party_source"] == pytest.approx(0.5, abs=1e-6)
    # No apt.dat-only layer at all ⇒ no provenance claim either way.
    assert PS.shape_features(shape, _layout())["third_party_source"] == 0.0


# ═════════════════════════════════════════════════════════════════════
# Stage 3 — the hard gates
# ═════════════════════════════════════════════════════════════════════

def _corridor():
    """Road-width (12 m) and long: the only shape SERVICE may claim."""
    return _rect(0.0, 0.0, 400.0, 12.0)


def test_gate_free_road_denies_service_to_anything_but_a_corridor():
    """The free-road ruling: a wide residue stays one surface."""
    blob = _rect(0.0, 0.0, 300.0, 300.0)
    record = PS.score_shape(blob, _layout())
    assert "G-FREE-ROAD" in record["gates"]
    assert PS.CLASS_SERVICE not in record["candidates"]
    # …and the corridor version keeps SERVICE eligible.
    corridor_record = PS.score_shape(_corridor(), _layout())
    assert "G-FREE-ROAD" not in corridor_record["gates"]
    assert PS.CLASS_SERVICE in corridor_record["candidates"]


def test_gate_veto_removes_only_groundside_on_apron_evidence():
    """R-VETO protects APRONS from LANDSIDE demotion — and nothing
    else.  SERVICE stays a candidate (TAXI-vs-SERVICE is a scores
    question; CYXY ground truth 2026-07-28: the broad veto flipped true
    service roads 42/43/166 to TAXI), and taxi names/lines are not
    apron evidence."""
    corridor = _corridor()
    layout = _layout([BuiltShape(polygon=corridor, role=ROLE_APRON)])
    # An OSM apron polygon over the western third — above the 0.25 gate.
    _osm_aeroway(layout, [("apron", [(0.0, 0.0), (160.0, 0.0),
                                     (160.0, 12.0), (0.0, 12.0)], True)])
    record = PS.score_shape(corridor, layout)
    assert record["features"]["osm_apron"] >= PS.PAVEMENT_SCORE_VETO_FRAC
    assert "G-VETO" in record["gates"]
    assert PS.CLASS_SERVICE in record["candidates"]
    assert PS.CLASS_GROUNDSIDE not in record["candidates"]


def test_gate_veto_ignores_taxi_flavored_evidence():
    """A shape covered only by OSM taxiway lines is airside-ish but NOT
    apron-veto territory — GROUNDSIDE must stay a candidate."""
    corridor = _corridor()
    layout = _layout([BuiltShape(polygon=corridor, role=ROLE_APRON)])
    _osm_aeroway(layout, [("taxiway", [(0.0, 6.0), (480.0, 6.0)], False)])
    record = PS.score_shape(corridor, layout)
    assert record["features"]["osm_taxi"] > PS.PAVEMENT_SCORE_VETO_FRAC
    assert "G-VETO" not in record["gates"]
    assert PS.CLASS_GROUNDSIDE in record["candidates"]


def test_gate_chain_removes_the_aircraft_classes_when_disconnected():
    corridor = _corridor()
    record = PS.score_shape(corridor, _layout(), connected=False)
    assert "G-CHAIN" in record["gates"]
    assert PS.CLASS_APRON not in record["candidates"]
    assert PS.CLASS_TAXI not in record["candidates"]
    assert set(record["candidates"]) == {PS.CLASS_SERVICE,
                                         PS.CLASS_GROUNDSIDE}
    # ``connected=None`` (the terminal-less guard) fires no gate at all.
    assert "G-CHAIN" not in PS.score_shape(
        corridor, _layout(), connected=None)["gates"]


def test_gate_conflict_reopens_every_class_when_the_law_contradicts():
    """OSM says apron, the touch-chain says unreachable: no answer.

    The gates between them empty the candidate set, so the law has
    given no verdict — the scorer must reopen all four classes and flag
    the contradiction rather than pick from an empty set.  Needs a WIDE
    shape now: on a road-width corridor the narrowed veto leaves
    SERVICE open, so the set never empties there.
    """
    blob = _rect(0, 0, 200, 200)
    layout = _layout([BuiltShape(polygon=blob, role=ROLE_APRON)])
    _osm_aeroway(layout, [("apron", [(-10, -10), (210, -10), (210, 210),
                                     (-10, 210)], True)])
    record = PS.score_shape(blob, layout, connected=False)
    assert "G-FREE-ROAD" in record["gates"]
    assert "G-VETO" in record["gates"]
    assert "G-CHAIN" in record["gates"]
    assert "G-CONFLICT" in record["gates"]
    assert record["candidates"] == sorted(PS.CLASSES)


# ═════════════════════════════════════════════════════════════════════
# Stage 4 — verdict and confidence
# ═════════════════════════════════════════════════════════════════════

def test_strong_apron_evidence_wins_with_high_confidence():
    apron = _rect(0.0, 0.0, 300.0, 300.0)
    layout = _layout(
        [BuiltShape(polygon=apron, role=ROLE_APRON)],
        source_pavement_union=apron,
        apt_pavement_records=[(apron, "RAMP 1", 1)],
    )
    # The whole field is named apron ⇒ apt-name reliability 1.0.
    assert PS.source_reliability(layout).apt_names == pytest.approx(1.0)
    record = PS.score_shape(apron, layout, legacy_class=PS.CLASS_APRON)
    assert record["winner"] == PS.CLASS_APRON
    assert record["band"] == "HIGH"
    assert record["margin"] >= PS.PAVEMENT_SCORE_MARGIN_HIGH
    assert record["final"] == PS.CLASS_APRON
    assert record["scores"][PS.CLASS_APRON] > record["scores"][PS.CLASS_TAXI]


def test_strong_taxi_evidence_wins_for_a_spine_threaded_corridor():
    corridor = _rect(0.0, 0.0, 400.0, 30.0)
    layout = _layout(
        [BuiltShape(polygon=corridor, role=ROLE_JUNCTION)],
        source_pavement_union=corridor,
        apt_pavement_records=[(corridor, "TWY A", 1)],
        apt_taxi_centerlines=[
            (LineString([(0.0, 15.0), (1000.0, 15.0)]), "A")],
    )
    record = PS.score_shape(corridor, layout, legacy_class=PS.CLASS_TAXI)
    assert record["features"]["spine_cover"] == pytest.approx(1.0, abs=1e-6)
    assert record["features"]["spine_thread"] > 0.0
    assert record["winner"] == PS.CLASS_TAXI
    assert record["band"] == "HIGH"


def test_no_evidence_at_all_is_no_guess_and_the_legacy_verdict_stands(
        monkeypatch):
    """Nothing scores ⇒ ``winner is None``, band LOW, legacy survives.

    An empty weight matrix is the cleanest way to stage "no layer said
    anything about this shape": the geometry features always fire (they
    are pure morphology at reliability 1), so silencing the matrix is
    what an evidence-free airport looks like from the argmax's side.
    """
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_WEIGHTS", {})
    shape = _rect(0.0, 0.0, 200.0, 200.0)
    record = PS.score_shape(shape, _layout())
    assert record["winner"] is None
    assert record["margin"] == 0.0
    assert record["band"] == "LOW"
    assert set(record["scores"].values()) == {0.0}
    # Without a legacy verdict there is simply no answer…
    assert record["final"] is None
    # …and with one, the development ruling hands the shape back to it.
    with_legacy = PS.score_shape(shape, _layout(),
                                 legacy_class=PS.CLASS_GROUNDSIDE)
    assert with_legacy["winner"] is None
    assert with_legacy["final"] == PS.CLASS_GROUNDSIDE


def test_a_low_margin_shape_falls_back_to_the_legacy_verdict(monkeypatch):
    """The development ruling, with the scorer actually having a winner."""
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_WEIGHTS", {
        "wide_blob": {"APRON": 1.0, "TAXI": 0.95},
    })
    shape = _rect(0.0, 0.0, 300.0, 300.0)
    record = PS.score_shape(shape, _layout(), legacy_class=PS.CLASS_TAXI)
    assert record["winner"] == PS.CLASS_APRON
    assert record["band"] == "LOW"
    assert record["final"] == PS.CLASS_TAXI


def test_the_decision_record_carries_the_whole_audit_trail():
    shape = _rect(0.0, 0.0, 300.0, 300.0)
    record = PS.score_shape(shape, _layout(), legacy_class=PS.CLASS_APRON)
    assert set(record) == {"features", "scores", "gates", "candidates",
                           "winner", "margin", "band", "legacy", "final"}
    assert set(record["scores"]) == set(PS.CLASSES)
    assert record["legacy"] == PS.CLASS_APRON
    assert "wide_blob" in record["features"]


# ═════════════════════════════════════════════════════════════════════
# The shadow pass
# ═════════════════════════════════════════════════════════════════════

def _shadow_layout():
    """A runway, an OSM-backed apron, a road-covered lot, and a sliver.

    The terminal is what arms the runway touch-chain guard (an airport
    with no ``ROLE_BUILDING`` leaves connectivity inert).
    """
    runway = BuiltShape(polygon=_rect(-500.0, 0.0, 0.0, 45.0),
                        role=ROLE_RUNWAY, ref="09/27")
    apron = BuiltShape(polygon=_rect(0.0, 0.0, 200.0, 200.0),
                       role=ROLE_APRON, ref="apron-1")
    lot = BuiltShape(polygon=_rect(400.0, 0.0, 460.0, 600.0),
                     role=ROLE_GROUNDSIDE_PAVEMENT, ref="lot-1")
    sliver = BuiltShape(polygon=_rect(700.0, 0.0, 703.0, 2.5),
                        role=ROLE_APRON, ref="sliver-1")
    terminal = BuiltShape(polygon=_rect(0.0, 300.0, 60.0, 360.0),
                          role=ROLE_BUILDING, ref="terminal")
    layout = _layout([runway, apron, lot, sliver, terminal],
                     runway_union=runway.polygon,
                     source_pavement_union=box(-500.0, 0.0, 703.0, 600.0),
                     apt_pavement_records=[
                         (box(0.0, 0.0, 200.0, 200.0), "RAMP 1", 1)])
    _osm_aeroway(layout, [("apron", [(0.0, 0.0), (200.0, 0.0),
                                     (200.0, 200.0), (0.0, 200.0)], True)])
    _road_feed(layout, [[(430.0, -20.0), (430.0, 620.0)]], widths={0: 40.0})
    return layout, {"runway": runway, "apron": apron, "lot": lot,
                    "sliver": sliver, "terminal": terminal}


def _snapshot(layout):
    return [(s.role, s.ref, s.polygon.wkb,
             None if s.node_altitudes is None else tuple(s.node_altitudes),
             s.altitude)
            for s in layout.shapes]


def test_shadow_pass_scores_every_eligible_shape_and_skips_fragments():
    layout, shapes = _shadow_layout()
    summary = PS.shadow_classify(layout, icao="TEST")
    assert summary["mode"] == "shadow"
    # The runway and the terminal are out of scope, the sliver is below
    # PAVEMENT_SCORE_MIN_AREA_M2 (3 x 2.5 = 7.5 m² < 10) — apron + lot
    # remain.
    assert shapes["sliver"].polygon.area < PS.PAVEMENT_SCORE_MIN_AREA_M2
    assert summary["shapes"] == 2
    assert summary["shapes"] == len(layout.pavement_score_decisions)
    assert {d["ref"] for d in layout.pavement_score_decisions} == {
        "apron-1", "lot-1"}
    assert summary["agree"] + summary["disagree"] == summary["shapes"]
    assert layout.pavement_score_summary is summary


def test_shadow_pass_mutates_nothing():
    """Spec §10.4: shadow mode must leave a byte-identical patch."""
    layout, _shapes = _shadow_layout()
    before = _snapshot(layout)
    PS.shadow_classify(layout, icao="TEST")
    assert _snapshot(layout) == before


def test_shadow_decisions_carry_geometry_and_provenance():
    layout, _shapes = _shadow_layout()
    PS.shadow_classify(layout, icao="TEST")
    for record in layout.pavement_score_decisions:
        assert "lat" in record and "lon" in record
        assert 29.0 < record["lat"] < 31.0
        assert 30.0 < record["lon"] < 32.0
        assert record["area_m2"] >= PS.PAVEMENT_SCORE_MIN_AREA_M2
        assert record["legacy"] == PS.LEGACY_ROLE_TO_CLASS[record["role"]]
        assert record["band"] in ("HIGH", "MED", "LOW")


def test_shadow_summary_publishes_reliability_and_the_confusion_matrix():
    layout, _shapes = _shadow_layout()
    summary = PS.shadow_classify(layout, icao="TEST")
    assert set(summary["reliability"]) == {
        "apt_names", "osm_aeroway", "road_feed", "truck", "spine",
        "alt_apt"}
    assert summary["seconds"] >= 0.0
    for key, count in summary["confusion"].items():
        legacy, _arrow, winner = key.partition("->")
        assert legacy in PS.CLASSES and winner in PS.CLASSES
        assert count >= 1
    assert sum(summary["confusion"].values()) == summary["disagree"]


def test_shadow_pass_reads_injected_evidence_sources():
    """The supported seam: a pre-stashed ``EvidenceSources`` is reused.

    ``evidence_sources`` memoises on ``layout._pavement_class_sources``,
    so a hand-built layer set drives the scorer without a road feed.
    """
    lot = BuiltShape(polygon=_rect(0.0, 0.0, 200.0, 200.0),
                     role=ROLE_APRON, ref="lot-1")
    layout = _layout([lot])
    layout._pavement_class_sources = PC.EvidenceSources(
        road_corridors=PC.CoverIndex([box(-10.0, -10.0, 210.0, 210.0)]),
        parking_corridors=PC.CoverIndex([box(0.0, 0.0, 200.0, 200.0)]),
        n_road_ways=40,
    )
    summary = PS.shadow_classify(layout, icao="TEST")
    assert summary["shapes"] == 1
    record = layout.pavement_score_decisions[0]
    assert record["features"]["road_cover"] == pytest.approx(1.0, abs=1e-6)
    assert record["features"]["parking_cover"] == pytest.approx(1.0,
                                                                abs=1e-6)
    assert record["winner"] == PS.CLASS_GROUNDSIDE
    assert summary["disagree"] == 1
    assert summary["confusion"] == {"APRON->GROUNDSIDE": 1}


def test_shadow_pass_on_an_airport_with_no_scorable_shape():
    layout = _layout([BuiltShape(polygon=_rect(0.0, 0.0, 100.0, 45.0),
                                 role=ROLE_RUNWAY)])
    summary = PS.shadow_classify(layout, icao="TEST")
    assert summary["shapes"] == 0
    assert not hasattr(layout, "pavement_score_decisions")
    assert layout.pavement_score_summary is summary


# ── the runway touch-chain ───────────────────────────────────────────

def test_runway_connectivity_is_inert_without_a_terminal():
    """The legacy guard: no building ⇒ no landside ⇒ no verdict."""
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 45.0),
                        role=ROLE_RUNWAY)
    apron = BuiltShape(polygon=_rect(0.0, 0.0, 200.0, 45.0),
                       role=ROLE_APRON)
    assert PS.runway_connectivity(_layout([runway, apron])) == {}


def test_runway_connectivity_walks_the_touch_chain():
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 200.0),
                        role=ROLE_RUNWAY)
    linked = BuiltShape(polygon=_rect(0.0, 0.0, 200.0, 200.0),
                        role=ROLE_APRON)
    island = BuiltShape(polygon=_rect(600.0, 0.0, 800.0, 200.0),
                        role=ROLE_APRON)
    terminal = BuiltShape(polygon=_rect(0.0, 400.0, 60.0, 460.0),
                          role=ROLE_BUILDING)
    layout = _layout([runway, linked, island, terminal])
    connectivity = PS.runway_connectivity(layout)
    assert connectivity[id(runway)] is True
    assert connectivity[id(linked)] is True
    assert connectivity[id(island)] is False
    # Buildings are never links, so the terminal is not in the chain set.
    assert id(terminal) not in connectivity


# ═════════════════════════════════════════════════════════════════════
# Severance — the round-4 CUT at the reachability contour
# ═════════════════════════════════════════════════════════════════════

def _pinched_layout():
    """A runway-connected apron whose far lobe hangs off an 8 m pinch.

    The pinch is narrower than any plausible aircraft-path width
    (11–18 m sweep range), so the erosion core breaks there: the west
    half is taxiable from the runway, the east lobe is not — but as ONE
    shape the whole thing reads connected (one corner within reach).
    """
    from shapely.ops import unary_union
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 100.0),
                        role=ROLE_RUNWAY)
    terminal = BuiltShape(polygon=_rect(-100.0, 300.0, -40.0, 360.0),
                          role=ROLE_BUILDING)
    straddler = BuiltShape(
        polygon=unary_union([_rect(0.0, 0.0, 200.0, 100.0),
                             _rect(200.0, 46.0, 220.0, 54.0),
                             _rect(220.0, 0.0, 420.0, 100.0)]),
        role=ROLE_APRON, ref="pinched")
    return _layout([runway, terminal, straddler]), straddler


def test_sever_cuts_a_pinched_lobe_off_at_the_contour():
    layout, straddler = _pinched_layout()
    parent_area = straddler.polygon.area
    assert PS.sever_unreachable(layout) == 1
    pieces = [s for s in layout.shapes
              if getattr(s, "from_severance_cut", False)]
    assert straddler not in layout.shapes
    assert len(pieces) == 2
    assert all(s.role == ROLE_APRON for s in pieces)
    assert all(s.ref == "pinched" for s in pieces)
    assert all(s.from_route_proximity_cut for s in pieces)
    # Coverage is preserved: the cut re-partitions, it never drops.
    assert sum(s.polygon.area for s in pieces) == pytest.approx(
        parent_area, abs=2.0)
    # Each piece now scores against its OWN connectivity: the west side
    # is taxiable, the severed lobe is decisively beyond the threshold.
    connectivity = PS.runway_connectivity(layout)
    west = min(pieces, key=lambda s: s.polygon.centroid.x)
    east = max(pieces, key=lambda s: s.polygon.centroid.x)
    assert connectivity[id(west)] is True
    assert connectivity[id(east)] is False


def test_sever_is_inert_without_a_terminal():
    layout, straddler = _pinched_layout()
    layout.shapes = [s for s in layout.shapes if s.role != ROLE_BUILDING]
    assert PS.sever_unreachable(layout) == 0
    assert straddler in layout.shapes


def test_sever_leaves_a_fully_reachable_shape_alone():
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 100.0),
                        role=ROLE_RUNWAY)
    terminal = BuiltShape(polygon=_rect(-100.0, 300.0, -40.0, 360.0),
                          role=ROLE_BUILDING)
    apron = BuiltShape(polygon=_rect(0.0, 0.0, 300.0, 100.0),
                       role=ROLE_APRON)
    layout = _layout([runway, terminal, apron])
    assert PS.sever_unreachable(layout) == 0
    assert apron in layout.shapes


def test_sever_ignores_a_sub_threshold_remainder():
    """An unreachable nub below the area floor is not worth a seam."""
    from shapely.ops import unary_union
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 100.0),
                        role=ROLE_RUNWAY)
    terminal = BuiltShape(polygon=_rect(-100.0, 300.0, -40.0, 360.0),
                          role=ROLE_BUILDING)
    nubbed = BuiltShape(
        polygon=unary_union([_rect(0.0, 0.0, 200.0, 100.0),
                             _rect(200.0, 48.5, 205.0, 51.5)]),
        role=ROLE_APRON)
    layout = _layout([runway, terminal, nubbed])
    assert PS.sever_unreachable(layout) == 0
    assert nubbed in layout.shapes


def test_sever_spares_a_route_touched_remainder():
    """Route-touch trumps the erosion PER PIECE: an authored taxi route
    running through the pinch into the lobe vouches for it — severing
    would buy nothing but a seam, so the shape stays whole."""
    from types import SimpleNamespace
    layout, straddler = _pinched_layout()
    layout.apt_taxi_centerlines = [SimpleNamespace(
        line=LineString([(100.0, 50.0), (350.0, 50.0)]),
        is_service=False)]
    assert PS.sever_unreachable(layout) == 0
    assert straddler in layout.shapes
    # ... and the whole shape reads connected, per the landed ruling.
    assert PS.runway_connectivity(layout)[id(straddler)] is True


def test_enact_severs_and_demotes_the_landside_piece(monkeypatch):
    """End-to-end round 4: enactment cuts the straddler, the severed
    lobe re-scores disconnected (G-CHAIN) and demotes to groundside,
    while the taxiable side stays airside.  The lobe carries ROAD
    evidence (like the real CYXY #104 lot) — a lobe with taxi-only
    access would instead stay airside under G-TAXI-ONLY (owner
    2026-07-28, #208 vs #104: access type decides)."""
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_V2", "on")
    layout, straddler = _pinched_layout()
    _road_feed(layout, [[(225.0, 20.0 + 12.0 * i), (415.0, 20.0 + 12.0 * i)]
                        for i in range(6)])
    summary = PS.enact_classify(layout, icao="TEST")
    assert summary["severed"] == 1
    pieces = [s for s in layout.shapes
              if getattr(s, "from_severance_cut", False)]
    assert len(pieces) == 2
    west = min(pieces, key=lambda s: s.polygon.centroid.x)
    east = max(pieces, key=lambda s: s.polygon.centroid.x)
    assert east.role == ROLE_GROUNDSIDE_PAVEMENT
    assert west.role in (ROLE_APRON, ROLE_JUNCTION)
    severed_records = [r for r in layout.pavement_score_decisions
                       if r.get("severed")]
    assert len(severed_records) == 2
    assert any("G-CHAIN" in r["gates"] for r in severed_records)


# ═════════════════════════════════════════════════════════════════════
# Abutment laws — standing free-road law + building airside face
# (owner rulings 2026-07-28)
# ═════════════════════════════════════════════════════════════════════

def test_gate_apron_edge_binds_a_road_corridor_to_the_apron():
    """Standing law: a service road running along the edge of an apron
    becomes apron — SERVICE is gated off an apron-bound corridor."""
    corridor = _corridor()                      # 480 × 6 m at y ∈ [0, 6]
    apron = BuiltShape(polygon=_rect(0.0, -200.0, 480.0, 0.0),
                       role=ROLE_APRON)
    owner = BuiltShape(polygon=corridor, role=ROLE_JUNCTION)
    layout = _layout([apron, owner])
    record = PS.score_shape(corridor, layout, owner=owner)
    assert record["features"]["apron_edge_bound"] >= \
        PS.PAVEMENT_SCORE_APRON_EDGE_FRAC
    assert "G-APRON-EDGE" in record["gates"]
    assert PS.CLASS_SERVICE not in record["candidates"]


def test_gate_apron_edge_leaves_a_free_road_alone():
    """A corridor crossing open ground far from any apron is a FREE
    road — SERVICE stays eligible."""
    corridor = _corridor()
    apron = BuiltShape(polygon=_rect(0.0, -500.0, 480.0, -300.0),
                       role=ROLE_APRON)
    owner = BuiltShape(polygon=corridor, role=ROLE_JUNCTION)
    layout = _layout([apron, owner])
    record = PS.score_shape(corridor, layout, owner=owner)
    assert record["features"]["apron_edge_bound"] == 0.0
    assert "G-APRON-EDGE" not in record["gates"]
    assert PS.CLASS_SERVICE in record["candidates"]


def test_gate_taxi_only_access_keeps_pavement_airside():
    """Owner 2026-07-28 (CYXY #208 vs #104): access type decides.  A
    shape whose only connection is taxiway pavement (zero road/truck
    evidence) cannot be groundside even when erosion-disconnected;
    give it road evidence and the gate stands down."""
    stub = BuiltShape(polygon=_rect(-60.0, 20.0, 0.0, 40.0),
                      role=ROLE_JUNCTION)
    owner = BuiltShape(polygon=_rect(0.0, 0.0, 80.0, 60.0),
                       role=ROLE_JUNCTION)
    layout = _layout([stub, owner])
    record = PS.score_shape(owner.polygon, layout, owner=owner,
                            connected=False)
    assert record["features"]["taxi_contact"] == 1.0
    assert "G-TAXI-ONLY" in record["gates"]
    assert "GROUNDSIDE" not in record["candidates"]
    assert "SERVICE" not in record["candidates"]
    # With road coverage (the #104 profile) the landside candidates
    # survive.
    layout = _layout([stub, owner])
    _road_feed(layout, [[(5.0, 10.0 + 8.0 * i), (75.0, 10.0 + 8.0 * i)]
                        for i in range(5)])
    record = PS.score_shape(owner.polygon, layout, owner=owner,
                            connected=False)
    assert "G-TAXI-ONLY" not in record["gates"]
    assert "GROUNDSIDE" in record["candidates"]


def test_gate_abut_keeps_building_face_pavement_airside():
    """Owner 2026-07-28 (SPJC): apron always abuts the airside side of
    buildings — a building-abutting, not-disconnected shape loses the
    SERVICE and GROUNDSIDE candidates."""
    pad = BuiltShape(polygon=_rect(0.0, 50.0, 60.0, 110.0),
                     role=ROLE_BUILDING)
    owner = BuiltShape(polygon=_rect(0.0, 0.0, 60.0, 50.0),
                       role=ROLE_APRON)
    layout = _layout([pad, owner])
    record = PS.score_shape(owner.polygon, layout, owner=owner,
                            connected=True)
    assert record["features"]["building_abut"] == 1.0
    assert "G-ABUT" in record["gates"]
    assert PS.CLASS_SERVICE not in record["candidates"]
    assert PS.CLASS_GROUNDSIDE not in record["candidates"]
    # The landside face of a building is NOT protected: disconnected
    # pavement behind the terminal keeps its landside candidates.
    record = PS.score_shape(owner.polygon, layout, owner=owner,
                            connected=False)
    assert "G-ABUT" not in record["gates"]


# ═════════════════════════════════════════════════════════════════════
# G-BOUNDARY — airside never crosses the OSM aerodrome boundary
# (owner ruling 2026-07-28)
# ═════════════════════════════════════════════════════════════════════

def _fence(layout, max_x=100.0):
    """An ``aeroway=aerodrome`` polygon covering everything west of
    ``max_x`` (the fence line)."""
    return _osm_aeroway(layout, [
        ("aerodrome",
         [(-600.0, -600.0), (max_x, -600.0), (max_x, 600.0),
          (-600.0, 600.0)], True)])


def test_gate_boundary_forces_groundside_when_entirely_outside():
    layout = _fence(_layout(), max_x=100.0)
    record = PS.score_shape(_rect(150.0, 0.0, 250.0, 50.0), layout)
    assert "G-BOUNDARY" in record["gates"]
    assert "APRON" not in record["candidates"]
    assert "TAXI" not in record["candidates"]
    assert record["winner"] == "GROUNDSIDE"
    assert record["features"]["outside_boundary"] == pytest.approx(
        1.0, abs=0.01)


def test_gate_boundary_spares_a_fence_crosser():
    """Owner refinement 2026-07-28: contiguous pavement legitimately
    spans the fence (airside apron + outside lot) — a crosser gets NO
    gate; the outside fraction stays plain groundside evidence for the
    rest of the rules."""
    layout = _fence(_layout(), max_x=100.0)
    record = PS.score_shape(_rect(50.0, 0.0, 150.0, 50.0), layout)
    assert "G-BOUNDARY" not in record["gates"]
    assert "APRON" in record["candidates"]
    assert record["features"]["outside_boundary"] == pytest.approx(
        0.5, abs=0.01)
    assert record["scores"]["GROUNDSIDE"] > 0.0


def test_gate_boundary_tolerates_digitization_noise():
    """A shape lying on the fence line with a 3 % sliver INSIDE is
    still "entirely outside" under the 95 % threshold — mapping noise
    must not defeat the guarantee."""
    layout = _fence(_layout(), max_x=100.0)
    record = PS.score_shape(_rect(97.0, 0.0, 197.0, 50.0), layout)
    assert "G-BOUNDARY" in record["gates"]
    assert record["features"]["outside_boundary"] == pytest.approx(
        0.97, abs=0.005)


def test_gate_boundary_overrides_the_veto():
    """The guarantee is categorical: OSM apron evidence entirely
    outside the fence is contradictory data — both gates log,
    groundside wins."""
    layout = _fence(_layout(), max_x=100.0)
    _osm_aeroway(layout, [
        ("aerodrome",
         [(-600.0, -600.0), (100.0, -600.0), (100.0, 600.0),
          (-600.0, 600.0)], True),
        ("apron",
         [(150.0, 0.0), (250.0, 0.0), (250.0, 50.0), (150.0, 50.0)],
         True)])
    record = PS.score_shape(_rect(150.0, 0.0, 250.0, 50.0), layout)
    assert "G-VETO" in record["gates"]
    assert "G-BOUNDARY" in record["gates"]
    assert record["winner"] == "GROUNDSIDE"


def test_boundary_is_inert_without_an_aerodrome_way():
    record = PS.score_shape(_rect(50.0, 0.0, 150.0, 50.0), _layout())
    assert record["features"]["outside_boundary"] == 0.0
    assert "G-BOUNDARY" not in record["gates"]


# ═════════════════════════════════════════════════════════════════════
# G-ENCLAVE — groundside can never be surrounded by airside
# (owner ruling 2026-07-28)
# ═════════════════════════════════════════════════════════════════════

def test_gate_enclave_removes_groundside():
    record = PS.score_shape(_rect(0.0, 0.0, 60.0, 60.0), _layout(),
                            enclosed=True)
    assert "G-ENCLAVE" in record["gates"]
    assert "GROUNDSIDE" not in record["candidates"]


def test_enclosure_is_a_region_test_not_a_ring_cover():
    """The shape-scoped ring-cover predicate is RETIRED (spec
    enclave-region-law-spec §1-2): the enclave is a published REGION and
    the test is point-in-region.  Its blind spot is what this pins — a
    shape that does NOT fill its enclave still reads enclosed, which the
    old ``_enclosed_by_airside`` could never do (the specimen sliver read
    0.0 % ring coverage inside a void whose rim is 100 % apron)."""
    from auto_patch import enclaves as EN

    assert not hasattr(PS, "_enclosed_by_airside")
    donut = BuiltShape(
        polygon=_rect(0.0, 0.0, 300.0, 300.0).difference(
            _rect(100.0, 100.0, 200.0, 200.0)),
        role=ROLE_JUNCTION)
    pad = BuiltShape(polygon=_rect(-50.0, -50.0, -10.0, -10.0),
                     role=ROLE_APRON)
    # A 4 m² sliver floating in the middle of the 100x100 m void: three
    # of its flanks face bare ground, and it is far under the scorer's
    # 10 m² candidate floor.
    sliver = BuiltShape(polygon=_rect(148.0, 148.0, 150.0, 150.0),
                        role=ROLE_GROUNDSIDE_PAVEMENT)
    layout = _layout([donut, pad, sliver])
    records = EN.publish_airside_enclaves(layout)
    assert len(records) == 1
    assert records[0].area_m2 == pytest.approx(10000.0)
    assert EN.shape_in_enclave(layout, sliver) is True
    assert EN.point_in_enclave(layout, 150.0, 150.0) is True
    # Outside the void — and outside the union — is not an enclave.
    assert EN.point_in_enclave(layout, -30.0, -30.0) is False
    assert EN.point_in_enclave(layout, 1000.0, 1000.0) is False


def test_enclosure_escape_clause_defeats_the_region():
    """The owner's escape clause, applied ONCE in the publication: a
    touching tunnel/bridge shape means the region is not an enclave, so
    nothing downstream can forget the clause."""
    from auto_patch import enclaves as EN
    from auto_patch.layout import ROLE_TUNNEL_RAMP

    donut = BuiltShape(
        polygon=_rect(0.0, 0.0, 300.0, 300.0).difference(
            _rect(100.0, 100.0, 200.0, 200.0)),
        role=ROLE_JUNCTION)
    pad = BuiltShape(polygon=_rect(-50.0, -50.0, -10.0, -10.0),
                     role=ROLE_APRON)
    layout = _layout([donut, pad])
    assert len(EN.publish_airside_enclaves(layout)) == 1

    ramp = BuiltShape(polygon=_rect(140.0, 195.0, 160.0, 205.0),
                      role=ROLE_TUNNEL_RAMP)
    layout2 = _layout([donut, pad, ramp])
    assert EN.publish_airside_enclaves(layout2) == []
    assert EN.point_in_enclave(layout2, 150.0, 150.0) is False


def test_enclave_band_keepout_is_pocket_scoped():
    """The band keep-out is scoped to POCKET-width enclaves: an airfield
    INFIELD is a bounded complement component too, and its graded strips
    are the bands' own ground (Annex 14 §3.4.11-13).  The width law is
    the gap law's own ``GAP_FILL_MAX_WIDTH_M`` — never a second number."""
    from auto_patch import enclaves as EN
    from auto_patch.config import GAP_FILL_MAX_WIDTH_M

    wide = 3.0 * GAP_FILL_MAX_WIDTH_M
    donut = BuiltShape(
        polygon=_rect(0.0, 0.0, wide + 200.0, wide + 200.0).difference(
            _rect(100.0, 100.0, 100.0 + wide, 100.0 + wide)),
        role=ROLE_JUNCTION)
    pad = BuiltShape(polygon=_rect(-50.0, -50.0, -10.0, -10.0),
                     role=ROLE_APRON)
    layout = _layout([donut, pad])
    records = EN.publish_airside_enclaves(layout)
    assert len(records) == 1
    # Published as an enclave (G-ENCLAVE and the gap blocker both see
    # it) — but NOT band keep-out territory.
    assert EN.point_in_enclave(layout, 100.0 + wide / 2, 100.0 + wide / 2)
    assert EN.enclave_band_keepout_union(layout) is None
    assert EN.enclave_band_keepout_prepared(layout) is None


def test_enact_enclave_reverdicts_surrounded_groundside(monkeypatch):
    """End-to-end: road evidence demotes an island apron to groundside,
    but it is fully surrounded by airside — the topological rule says
    that verdict is wrong, and the enclave sweep re-verdicts it back to
    airside."""
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_V2", "on")
    runway = BuiltShape(polygon=_rect(-400.0, 0.0, 0.0, 100.0),
                        role=ROLE_RUNWAY)
    donut = BuiltShape(
        polygon=_rect(0.0, 0.0, 300.0, 300.0).difference(
            _rect(100.0, 100.0, 200.0, 200.0)),
        role=ROLE_JUNCTION)
    island = BuiltShape(polygon=_rect(100.0, 100.0, 200.0, 200.0),
                        role=ROLE_APRON)
    layout = _layout([runway, donut, island])
    # Enough road ways criss-crossing the island for full road-feed
    # reliability, half of them parking aisles — the demotion evidence
    # (road + parking coverage outscores the island's apron geometry).
    _road_feed(layout,
               [[(100.0, 101.0 + 4.0 * i), (200.0, 101.0 + 4.0 * i)]
                for i in range(25)],
               tags={i: {"service": "parking_aisle"}
                     for i in range(0, 25, 2)})
    summary = PS.enact_classify(layout, icao="TEST")
    assert summary["enclaves"] == 1
    assert island.role == ROLE_APRON
    enclave_records = [r for r in layout.pavement_score_decisions
                       if "G-ENCLAVE" in r["gates"]]
    assert enclave_records
    assert enclave_records[-1]["winner"] in ("APRON", "TAXI")


# ═════════════════════════════════════════════════════════════════════
# The Global-Airports cross-reference
# ═════════════════════════════════════════════════════════════════════

def test_alt_sources_without_an_xplane_root_are_a_no_op():
    layout = _layout()
    PS.ensure_alt_sources(layout, "TEST", None)
    assert layout._pavement_score_alt_rel == 0.0
    assert layout._pavement_score_alt_done is True
    assert PS.source_reliability(layout).alt_apt == 0.0


def test_alt_sources_without_an_icao_are_a_no_op(tmp_path):
    layout = _layout()
    PS.ensure_alt_sources(layout, "", str(tmp_path))
    assert layout._pavement_score_alt_rel == 0.0


def test_alt_sources_run_once_per_layout(tmp_path, monkeypatch):
    """Memoisation: the second call must not reach the finder at all."""
    from auto_patch import apt_dat_reader

    layout = _layout()
    PS.ensure_alt_sources(layout, "TEST", None)

    # ``ensure_alt_sources`` swallows every exception (a failed
    # cross-reference must never break a build), so a raising spy would
    # pass vacuously — count the calls instead.
    calls = []
    monkeypatch.setattr(apt_dat_reader, "find_all_airport_apt_dats",
                        lambda *a, **k: calls.append(a) or [])
    PS.ensure_alt_sources(layout, "TEST", str(tmp_path))
    assert calls == []
    assert layout._pavement_score_alt_rel == 0.0


def _write_global_apt_dat(root, layout, icao="ZZZZ"):
    """Write a Global-Airports apt.dat the real finder will discover.

    Layout: ``Custom Scenery/Global Airports/Earth nav data/apt.dat``
    (the v11 location ``find_all_airport_apt_dats`` searches).  The
    pavement ring and the 1201 nodes are given in the LAYOUT's metre
    frame and projected back to lat/lon, so the alt geometry lands
    exactly where the test expects it.
    """
    directory = os.path.join(root, "Custom Scenery", "Global Airports",
                             "Earth nav data")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "apt.dat")

    def ll(x, y):
        latitude, longitude = layout.m_to_ll(x, y)
        return f"{latitude:.9f} {longitude:.9f}"

    lines = [
        "I",
        "1100 Generated by the test suite",
        "",
        f"1 100 0 0 {icao} Scoring Test Field",
        "110 1 0.25 0.0 RAMP 1",
        f"111 {ll(0.0, 0.0)}",
        f"111 {ll(200.0, 0.0)}",
        f"111 {ll(200.0, 200.0)}",
        f"113 {ll(0.0, 200.0)}",
        "110 1 0.25 0.0 TWY A",
        f"111 {ll(300.0, 0.0)}",
        f"111 {ll(500.0, 0.0)}",
        f"111 {ll(500.0, 40.0)}",
        f"113 {ll(300.0, 40.0)}",
        f"1201 {ll(300.0, 20.0)} both 1 N1",
        f"1201 {ll(500.0, 20.0)} both 2 N2",
        "1202 1 2 twoway taxiway_C A",
        "99",
    ]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def test_alt_sources_read_the_default_packs_names_and_network(tmp_path):
    root = str(tmp_path / "X-Plane 12")
    layout = _layout(source_pavement_union=box(0.0, 0.0, 500.0, 200.0))
    path = _write_global_apt_dat(root, layout)

    PS.ensure_alt_sources(layout, "ZZZZ", root)

    sources = PS.score_sources(layout)
    assert sources.alt_path == path
    # The named polygons landed in the right buckets, in metre space.
    assert sources.alt_name_apron.cover_fraction(
        box(50.0, 50.0, 150.0, 150.0)) == pytest.approx(1.0, abs=0.02)
    assert sources.alt_name_taxi.cover_fraction(
        box(350.0, 10.0, 450.0, 30.0)) == pytest.approx(1.0, abs=0.02)
    assert not sources.alt_name_service
    # …and the 1202 network became buffered taxi territory.
    assert sources.alt_taxi_territory.cover_fraction(
        box(350.0, 10.0, 450.0, 30.0)) == pytest.approx(1.0, abs=0.02)
    # Reliability self-discounts: alignment (1.0 here — the alt pavement
    # sits inside our source union) x informativeness (everything named,
    # 200 m of a 1000 m network denominator).
    assert layout._pavement_score_alt_rel == pytest.approx(
        1.0 * (0.5 * 1.0 + 0.5 * 0.2), abs=0.05)
    assert PS.source_reliability(layout).alt_apt == pytest.approx(
        layout._pavement_score_alt_rel)


def test_alt_names_feed_the_score_of_a_shape_the_pack_never_named(tmp_path):
    root = str(tmp_path / "X-Plane 12")
    apron = _rect(0.0, 0.0, 200.0, 200.0)
    layout = _layout([BuiltShape(polygon=apron, role=ROLE_APRON)],
                     source_pavement_union=box(0.0, 0.0, 500.0, 200.0))
    _write_global_apt_dat(root, layout)
    PS.ensure_alt_sources(layout, "ZZZZ", root)
    record = PS.score_shape(apron, layout, legacy_class=PS.CLASS_APRON)
    assert record["features"]["name_apron"] == 0.0      # our pack: silent
    assert record["features"]["alt_name_apron"] == pytest.approx(
        1.0, abs=0.02)
    assert record["scores"][PS.CLASS_APRON] > 0.0
    assert record["winner"] == PS.CLASS_APRON


def test_alt_sources_survive_an_unreadable_pack(tmp_path):
    """Cross-reference evidence is additive: a bad file must not raise."""
    root = str(tmp_path / "X-Plane 12")
    directory = os.path.join(root, "Custom Scenery", "Global Airports",
                             "Earth nav data")
    os.makedirs(directory)
    with open(os.path.join(directory, "apt.dat"), "w",
              encoding="utf-8") as handle:
        handle.write("I\n1100 Broken\n\n1 100 0 0 ZZZZ Nothing Here\n99\n")
    layout = _layout(source_pavement_union=box(0.0, 0.0, 500.0, 200.0))
    PS.ensure_alt_sources(layout, "ZZZZ", root)
    assert layout._pavement_score_alt_rel == 0.0
    assert PS.score_sources(layout).alt_path == ""


# ═════════════════════════════════════════════════════════════════════
# The gate
# ═════════════════════════════════════════════════════════════════════

def test_mode_off_scores_nothing_and_stashes_nothing(monkeypatch):
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_V2", "off")
    layout, _shapes = _shadow_layout()
    before = _snapshot(layout)
    summary = PS.shadow_classify(layout, icao="TEST")
    assert summary["mode"] == "off"
    assert summary["shapes"] == 0
    assert not hasattr(layout, "pavement_score_decisions")
    assert layout.pavement_score_summary is summary
    assert _snapshot(layout) == before
    # Not even the evidence layers were built.
    assert not hasattr(layout, "_pavement_class_sources")
    assert not hasattr(layout, "_pavement_score_sources")


def test_legacy_role_map_covers_the_four_classes():
    assert set(PS.LEGACY_ROLE_TO_CLASS.values()) == set(PS.CLASSES)
    assert PS.LEGACY_ROLE_TO_CLASS[ROLE_APRON] == PS.CLASS_APRON
    assert PS.LEGACY_ROLE_TO_CLASS[ROLE_JUNCTION] == PS.CLASS_TAXI
    assert PS.LEGACY_ROLE_TO_CLASS[ROLE_GROUNDSIDE_PAVEMENT] == (
        PS.CLASS_GROUNDSIDE)
    # Out-of-scope families are simply not scored (spec §3).
    assert ROLE_RUNWAY not in PS.LEGACY_ROLE_TO_CLASS
    assert ROLE_BUILDING not in PS.LEGACY_ROLE_TO_CLASS


def test_a_concave_shape_scores_without_a_rectangle_assumption():
    """An L-shaped apron still scores: nothing here assumes a box."""
    ell = Polygon([(0.0, 0.0), (300.0, 0.0), (300.0, 100.0),
                   (100.0, 100.0), (100.0, 300.0), (0.0, 300.0)])
    record = PS.score_shape(ell, _layout(), legacy_class=PS.CLASS_APRON)
    assert record["winner"] in PS.CLASSES
    assert 0.0 <= record["margin"] <= 1.0


# ═════════════════════════════════════════════════════════════════════
# Phase B — enactment (owner approval 2026-07-28)
# ═════════════════════════════════════════════════════════════════════

def _enact_mode(monkeypatch):
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_V2", "on")


def test_enact_is_a_no_op_outside_on_mode(monkeypatch):
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_V2", "shadow")
    shape = BuiltShape(polygon=_rect(0, 0, 100, 100), role=ROLE_JUNCTION)
    layout = _layout([shape])
    summary = PS.enact_classify(layout, icao="TEST")
    assert summary["enacted"] == 0
    assert shape.role == ROLE_JUNCTION


def test_enact_flips_a_strong_apron_junction(monkeypatch):
    _enact_mode(monkeypatch)
    blob = _rect(0, 0, 200, 200)          # wide blob, fully OSM-apron
    shape = BuiltShape(polygon=blob, role=ROLE_JUNCTION)
    layout = _layout([shape])
    _osm_aeroway(layout, [("apron",
                           [(-10, -10), (210, -10), (210, 210),
                            (-10, 210)], True)])
    summary = PS.enact_classify(layout, icao="TEST")
    assert shape.role == ROLE_APRON
    # The legacy neck-split re-eval trigger must NOT be set — under
    # enactment the scorer is the only classifier (owner 2026-07-28)
    # and that flag would invite the legacy pass to overturn this.
    assert not getattr(shape, "reclassified_from_junction", False)
    assert summary["enacted"] == 1
    assert summary["flips"] == {"TAXI->APRON": 1}


def test_enact_leaves_low_margin_shapes_to_the_legacy_passes(
        monkeypatch):
    _enact_mode(monkeypatch)
    # Weights emptied: every score is 0 -> winner None -> band LOW.
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_WEIGHTS", {})
    shape = BuiltShape(polygon=_rect(0, 0, 200, 200), role=ROLE_JUNCTION)
    layout = _layout([shape])
    summary = PS.enact_classify(layout, icao="TEST")
    assert shape.role == ROLE_JUNCTION
    assert summary["enacted"] == 0
    assert summary["low"] == 1


def test_enact_road_narrow_ruling_votes_service_not_groundside(
        monkeypatch):
    """Owner 2026-07-28: narrow + road-covered is a SERVICE road even
    when too short to thread — must NOT demote to groundside."""
    _enact_mode(monkeypatch)
    # One synthetic way would score road-feed reliability 1/25 and mute
    # the road evidence (the scaling working as designed) — pin the
    # knob so this single-way feed reads as a fully-present source.
    knobs = dict(PS.PAVEMENT_SCORE_RELIABILITY)
    knobs["road_ways"] = 1.0
    monkeypatch.setattr(PS, "PAVEMENT_SCORE_RELIABILITY", knobs)
    fragment = _rect(0, 0, 40, 8)         # 40x8 m road fragment
    shape = BuiltShape(polygon=fragment, role=ROLE_APRON)
    layout = _layout([shape])
    _road_feed(layout, [[(-50, 4), (90, 4)]], widths={0: 8.0})
    summary = PS.enact_classify(layout, icao="TEST")
    assert shape.role in (PS.ROLE_SERVICE_ROAD,
                          PS.ROLE_SERVICE_JUNCTION), \
        f"expected SERVICE role, got {shape.role}"
    assert summary["flips"].get("APRON->SERVICE") == 1


# ═════════════════════════════════════════════════════════════════════
# Boundary SOURCES (owner ruling 2026-07-29: "ensure we have airport
# boundary data for role classification") — relation-mapped aerodromes
# + the apt.dat row-130 fallback
# ═════════════════════════════════════════════════════════════════════

def _fence_relation(layout, max_x=100.0, reverse_second=True):
    """The same fence as :func:`_fence`, mapped as a RELATION
    (multipolygon): two OPEN member ways sharing endpoint nodes, the
    ``aeroway=aerodrome`` tag on the relation only (member ways carry
    no aeroway tag — exactly the shape the loader returns for
    relation-mapped airports)."""
    corners = [(-600.0, -600.0), (max_x, -600.0), (max_x, 600.0),
               (-600.0, 600.0)]
    nodes = {}
    refs = []
    for i, (x, y) in enumerate(corners):
        latitude, longitude = layout.m_to_ll(x, y)
        nodes[f"b{i}"] = (latitude, longitude)
        refs.append(f"b{i}")
    frag_a = [refs[0], refs[1], refs[2]]
    frag_b = [refs[2], refs[3], refs[0]]
    if reverse_second:
        frag_b = frag_b[::-1]          # exercise reversed stitching
    ways = [("wa", frag_a, {}), ("wb", frag_b, {})]
    relations = [("r1", ["wa", "wb"], {"aeroway": "aerodrome"})]
    layout._osm_airport_features = (nodes, ways, relations)
    return layout


def test_gate_boundary_from_relation_mapped_aerodrome():
    """A relation-mapped fence must gate exactly like a closed-way
    fence (the pipeline used to drop relations on the floor)."""
    layout = _fence_relation(_layout(), max_x=100.0)
    record = PS.score_shape(_rect(150.0, 0.0, 250.0, 50.0), layout)
    assert "G-BOUNDARY" in record["gates"]
    assert record["winner"] == "GROUNDSIDE"
    assert record["features"]["outside_boundary"] == pytest.approx(
        1.0, abs=0.01)


def test_relation_fence_with_missing_member_is_skipped_not_guessed():
    """An unstitchable relation (member way absent from the layer)
    contributes nothing — no boundary, no gate."""
    layout = _fence_relation(_layout(), max_x=100.0)
    nodes, ways, relations = layout._osm_airport_features
    layout._osm_airport_features = (nodes, ways[:1], relations)
    record = PS.score_shape(_rect(150.0, 0.0, 250.0, 50.0), layout)
    assert "G-BOUNDARY" not in record["gates"]
    assert record["features"]["outside_boundary"] == 0.0


def test_boundary_row130_fallback_when_osm_has_no_aerodrome():
    """No OSM aerodrome way or relation ⇒ the apt.dat row-130 fence
    (``layout.airport_boundary``, metre space) takes over, so
    classification always has a boundary wherever apt.dat drew one."""
    layout = _layout(airport_boundary=box(-600.0, -600.0, 100.0, 600.0))
    record = PS.score_shape(_rect(150.0, 0.0, 250.0, 50.0), layout)
    assert "G-BOUNDARY" in record["gates"]
    assert record["winner"] == "GROUNDSIDE"
    assert record["features"]["outside_boundary"] == pytest.approx(
        1.0, abs=0.01)


def test_osm_aerodrome_way_beats_row130_fallback():
    """When BOTH exist the OSM fence wins (row-130 is the fallback,
    not a union partner — their disagreement is OSM's to own)."""
    layout = _fence(_layout(), max_x=100.0)
    layout.airport_boundary = box(-600.0, -600.0, 400.0, 600.0)
    record = PS.score_shape(_rect(150.0, 0.0, 250.0, 50.0), layout)
    # inside the row-130 fence but outside the OSM fence ⇒ still gated
    assert "G-BOUNDARY" in record["gates"]
