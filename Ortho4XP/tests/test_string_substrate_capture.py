"""Tests for the string-substrate CAPTURE side (Fable RULING 4,
2026-07-31 — docs/specs/s1-taut-chord-constructor-spec.md, second
rulings block; §10(i) FIRED AND CLOSED).

Headless, synthetic, tmp_path-free (nothing is written): every fixture
is hand-built metre-space geometry plus a hand-built OSM ways/nodes
pair, so the ruled properties are asserted directly rather than through
an airport build.  ZERO BUILDS.

These drive the REAL production capture — ``pipeline._capture_string_
substrate``, gate included — not a re-implementation of it.  That
matters: the defect this plumbing exists to fix (gap 2) was created by
asserting two objects were the same because they "should be".

The ruled properties under test:
  1. write-once — a second write RAISES, never a silent overwrite;
  2. both tiers present, both in the layout's own ``to_m`` metre frame
     (ONE projection);
  3. the fingerprint is THE ONE fingerprint (the hook's own function),
     stable across re-capture of identical input and sensitive to a
     changed input;
  4. ★ THE GAP-2 REGRESSION GUARD — the captured apt tier survives
     ``centerline_recognition``'s post-recognition REASSIGNMENT of
     ``layout.apt_taxi_centerlines``, which is the whole reason the
     capture deep-copies at the S2 snapshot;
  5. gate OFF ⇒ no capture, no import, no new attribute;
  6. an empty OSM tier is LAWFUL degradation, not an error;
  7. the OSM tier is the RAW population the dead scorer's branch
     defined, and service apt pieces are CARRIED (Ruling 5's
     substrate corollary).
"""

from __future__ import annotations

import math
import os
import sys

import pytest
from shapely.geometry import LineString

from auto_patch.apt_dat_reader import TaxiCenterline
from auto_patch.layout import PavementLayout, _projection
from auto_patch.osm_load import capture_osm_taxi_linework
from auto_patch.pipeline import _capture_string_substrate

GATE = "O4_TAUT_STRING_CONSTRUCTION"
ANCHOR = (30.1, 31.4)          # HECA-ish; any anchor works


# ──────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setenv(GATE, "1")


def _layout() -> PavementLayout:
    return PavementLayout(icao="TEST", anchor=ANCHOR)


def _to_m():
    return _projection(ANCHOR)


def _apt_pieces():
    """Two apt.dat routes + one SERVICE route (row 1206)."""
    return [
        TaxiCenterline(line=LineString([(0.0, 0.0), (300.0, 0.0)]),
                       seg_sizes=["C"], is_service=False, name="A"),
        TaxiCenterline(line=LineString([(300.0, 0.0), (300.0, 200.0)]),
                       seg_sizes=["C"], is_service=False, name="B"),
        TaxiCenterline(line=LineString([(0.0, 50.0), (120.0, 50.0)]),
                       seg_sizes=["A"], is_service=True, name="SVC"),
    ]


def _osm_fixture():
    """``(nodes, ways)`` in the loader's own shapes.

    ``nodes`` maps id -> (lat, lon); ``ways`` are
    ``(way_id, node_refs, tags)``.  Includes the three exclusions the
    scorer's branch applied, so the population assertions are real:
    a non-taxiway way, a single-node way, and a sub-1 m way.
    """
    nodes = {
        "n1": (30.1000, 31.4000),
        "n2": (30.1000, 31.4020),      # ~192 m east
        "n3": (30.1010, 31.4020),      # ~111 m north of n2
        "n4": (30.1200, 31.4300),
        "n5": (30.12000, 31.43000005),  # ~5 mm from n4 -> under 1 m
    }
    ways = [
        ("w100", ["n1", "n2", "n3"], {"aeroway": "taxiway", "ref": "A"}),
        ("w101", ["n2", "n3"], {"aeroway": "taxiway"}),
        # excluded: not a taxiway (this is the WIDER processed tier's
        # population, deliberately not ours)
        ("w102", ["n1", "n2"], {"aeroway": "parking_position"}),
        ("w103", ["n1", "n2"], {"aeroway": "apron"}),
        # excluded: fewer than 2 resolvable nodes
        ("w104", ["n1", "MISSING"], {"aeroway": "taxiway"}),
        # excluded: shorter than 1.0 m
        ("w105", ["n4", "n5"], {"aeroway": "taxiway"}),
    ]
    return nodes, ways


def _capture(layout, *, apt=None, osm=True):
    nodes, ways = _osm_fixture() if osm else ({}, [])
    _capture_string_substrate(
        layout, "TEST",
        _apt_pieces() if apt is None else apt,
        nodes, ways, _to_m())


# ──────────────────────────────────────────────────────────────────
# 5. Gate
# ──────────────────────────────────────────────────────────────────

def test_gate_off_grows_no_attribute_and_imports_nothing(monkeypatch):
    """Ruling 4: gate OFF ⇒ no capture, no import, no new attribute.

    The import half is load-bearing: ``taut_string`` must stay
    unimported in a gate-off build, and the capture's fingerprint
    import sits after the gate's early return.
    """
    monkeypatch.delenv(GATE, raising=False)
    taut = "auto_patch.elevation_per_surface.route_profile.taut_string"
    monkeypatch.delitem(sys.modules, taut, raising=False)

    layout = _layout()
    _capture(layout)

    assert not hasattr(layout, "string_substrate_src"), (
        "gate OFF must not grow the attribute at all")
    assert taut not in sys.modules, (
        "gate OFF must not import taut_string — gate-off byte-identity "
        "depends on it")


def test_gate_explicit_zero_is_off(monkeypatch):
    monkeypatch.setenv(GATE, "0")
    layout = _layout()
    _capture(layout)
    assert not hasattr(layout, "string_substrate_src")


# ──────────────────────────────────────────────────────────────────
# 1. Write-once
# ──────────────────────────────────────────────────────────────────

def test_field_is_written_once(gate_on):
    layout = _layout()
    _capture(layout)
    assert isinstance(layout.string_substrate_src, dict)
    assert set(layout.string_substrate_src) == {"apt", "osm", "fingerprint"}


def test_second_write_raises(gate_on):
    """A second write is an ERROR, not a silent overwrite."""
    layout = _layout()
    _capture(layout)
    first = layout.string_substrate_src

    with pytest.raises(RuntimeError, match="write-once"):
        _capture(layout)

    assert layout.string_substrate_src is first, (
        "the failed second write must not have disturbed the first")


# ──────────────────────────────────────────────────────────────────
# 2. Both tiers, ONE projection
# ──────────────────────────────────────────────────────────────────

def test_both_tiers_present(gate_on):
    layout = _layout()
    _capture(layout)
    src = layout.string_substrate_src
    assert len(src["apt"]) == 3, "all three apt pieces, service included"
    assert len(src["osm"]) == 2, "only the two lawful aeroway=taxiway ways"


def test_apt_tier_is_in_layout_metre_frame(gate_on):
    """The apt tier is already metre-space; capture must not reproject."""
    layout = _layout()
    _capture(layout)
    coords = [c for c, _svc in layout.string_substrate_src["apt"]]
    assert coords[0] == ((0.0, 0.0), (300.0, 0.0))
    assert coords[1] == ((300.0, 0.0), (300.0, 200.0))


def test_osm_tier_is_in_layout_to_m_space_not_degrees(gate_on):
    """ONE projection: the OSM tier is metres under the layout's own
    ``to_m``, never lon/lat and never a second projection.

    Asserted against the layout's ``to_m`` applied directly to the
    fixture's lon/lat — the measured property, not "it looks metric".
    """
    layout = _layout()
    _capture(layout)
    to_m = _to_m()
    nodes, _ = _osm_fixture()

    by_id = dict(layout.string_substrate_src["osm"])
    got = by_id["w100"]
    want = tuple(to_m(nodes[n][1], nodes[n][0]) for n in ("n1", "n2", "n3"))
    assert got == want

    # And it is genuinely metres: the first node sits on the anchor.
    assert got[0] == pytest.approx((0.0, 0.0), abs=1e-9)
    assert 150.0 < math.dist(got[0], got[1]) < 250.0


# ──────────────────────────────────────────────────────────────────
# 3. The ONE fingerprint
# ──────────────────────────────────────────────────────────────────

def test_fingerprint_is_the_hooks_own_function(gate_on):
    """Capture must store what the HOOK recomputes — one function, one
    content.  Two implementations of "the same hash" would make the
    hook's assertion vacuous the first time they drifted.
    """
    from auto_patch.elevation_per_surface.route_profile.taut_string import (
        substrate_fingerprint)

    layout = _layout()
    _capture(layout)
    src = layout.string_substrate_src
    assert src["fingerprint"] == substrate_fingerprint(src["apt"], src["osm"])


def test_fingerprint_stable_across_recapture_of_identical_input(gate_on):
    a, b = _layout(), _layout()
    _capture(a)
    _capture(b)
    assert (a.string_substrate_src["fingerprint"]
            == b.string_substrate_src["fingerprint"])


def test_fingerprint_changes_when_apt_geometry_changes(gate_on):
    base = _layout()
    _capture(base)

    moved = _apt_pieces()
    moved[0] = TaxiCenterline(
        line=LineString([(0.0, 0.0), (300.0, 1.0)]),   # 1 m move
        seg_sizes=["C"], is_service=False, name="A")
    other = _layout()
    _capture(other, apt=moved)

    assert (other.string_substrate_src["fingerprint"]
            != base.string_substrate_src["fingerprint"])


def test_fingerprint_changes_when_service_flag_changes(gate_on):
    base = _layout()
    _capture(base)

    flipped = _apt_pieces()
    flipped[2] = TaxiCenterline(
        line=flipped[2].line, seg_sizes=["A"], is_service=False, name="SVC")
    other = _layout()
    _capture(other, apt=flipped)

    assert (other.string_substrate_src["fingerprint"]
            != base.string_substrate_src["fingerprint"])


def test_fingerprint_changes_when_a_tier_is_lost(gate_on):
    """The failure mode the fingerprint exists for: a tier silently
    going missing between capture and hook."""
    both, apt_only = _layout(), _layout()
    _capture(both)
    _capture(apt_only, osm=False)
    assert (apt_only.string_substrate_src["fingerprint"]
            != both.string_substrate_src["fingerprint"])


# ──────────────────────────────────────────────────────────────────
# 4. ★ THE GAP-2 REGRESSION GUARD
# ──────────────────────────────────────────────────────────────────

def test_apt_tier_survives_recognition_reassignment(gate_on, monkeypatch):
    """★ The measured defect Ruling 4 exists for.

    ``centerline_recognition.recognize_curved_centerlines`` REASSIGNS
    ``layout.apt_taxi_centerlines`` to merged / resampled / re-split
    geometry a few lines after the S2 snapshot.  So the hook-time
    attribute is a processed proxy of the snapshot, not the snapshot —
    asserting the two are equal at the hook is a proxy BY CONSTRUCTION
    (gap 2).

    This test runs the REAL recognition pass over a synthetic airport
    and pins that (a) recognition genuinely reassigned — otherwise the
    test would pass vacuously and prove nothing — and (b) the captured
    apt tier is untouched by it.
    """
    from auto_patch.centerline_recognition import recognize_curved_centerlines

    monkeypatch.setenv("O4_RECOGNIZED_CENTERLINES", "1")

    layout = _layout()
    pieces = _apt_pieces()
    # This is the S2 snapshot assignment, verbatim from pipeline.py's
    # "Preserve the full input centerline set" site.
    layout.apt_taxi_centerlines = list(pieces)
    _capture(layout, apt=layout.apt_taxi_centerlines)

    captured = [c for c, _svc in layout.string_substrate_src["apt"]]
    fp_before = layout.string_substrate_src["fingerprint"]
    before = list(layout.apt_taxi_centerlines)

    # A painted centerline that RIDES route A (0.5 m offset, well
    # inside _RIDE_TOL_M / _TOUCH_TOL_M, ride length >> _MIN_RIDE_M).
    layout._painted_lines_m = [
        LineString([(10.0, 0.5), (150.0, 0.5), (290.0, 0.5)])]

    n_reco = recognize_curved_centerlines(layout, "TEST")

    # (a) NON-VACUITY: recognition must actually have fired and
    #     replaced the attribute with different geometry.
    assert n_reco > 0, "recognition did not fire — the guard would be vacuous"
    assert layout.apt_taxi_centerlines is not before
    after_coords = [tuple(t.line.coords) for t in layout.apt_taxi_centerlines]
    before_coords = [tuple(t.line.coords) for t in before]
    assert after_coords != before_coords, (
        "recognition did not change the geometry — the guard would be vacuous")

    # (b) THE PROPERTY: the captured tier is untouched.
    assert [c for c, _svc in layout.string_substrate_src["apt"]] == captured
    assert layout.string_substrate_src["fingerprint"] == fp_before
    assert captured[0] == ((0.0, 0.0), (300.0, 0.0))


def test_capture_is_immune_to_mutation_of_the_source_objects(gate_on):
    """The deep copy is materialisation into tuples of floats — prove
    it by mutating the source list AND its shapely geometry."""
    layout = _layout()
    pieces = _apt_pieces()
    layout.apt_taxi_centerlines = list(pieces)
    _capture(layout, apt=layout.apt_taxi_centerlines)
    captured = [c for c, _svc in layout.string_substrate_src["apt"]]

    layout.apt_taxi_centerlines.clear()
    pieces[0].line = LineString([(9999.0, 9999.0), (10000.0, 10000.0)])

    assert [c for c, _svc in layout.string_substrate_src["apt"]] == captured
    assert captured[0] == ((0.0, 0.0), (300.0, 0.0))


# ──────────────────────────────────────────────────────────────────
# 6. Lawful degradation
# ──────────────────────────────────────────────────────────────────

def test_empty_osm_tier_is_lawful_not_an_error(gate_on):
    """The known cwd / worktree trap: no OSM cache ⇒ apt.dat-only
    substrate.  Lawful, logged, and never a raise."""
    layout = _layout()
    _capture(layout, osm=False)
    src = layout.string_substrate_src
    assert src["osm"] == []
    assert len(src["apt"]) == 3
    assert src["fingerprint"]


def test_empty_both_tiers_still_writes_the_field(gate_on):
    layout = _layout()
    _capture(layout, apt=[], osm=False)
    assert layout.string_substrate_src["apt"] == []
    assert layout.string_substrate_src["osm"] == []


# ──────────────────────────────────────────────────────────────────
# 7. Populations
# ──────────────────────────────────────────────────────────────────

def test_osm_population_is_the_scorer_branch_population():
    """RAW ``aeroway=taxiway`` linear ways only — the population
    Ruling 4(b) names.  ``parking_position`` belongs to the WIDER
    processed tier (``pavement.centerlines``) and must not leak in;
    the <2-node and <1 m drops mirror the scorer's branch exactly.
    """
    nodes, ways = _osm_fixture()
    got = capture_osm_taxi_linework(nodes, ways, _to_m())
    assert [w.way_id for w in got] == ["w100", "w101"]


def test_osm_capture_is_raw_not_processed():
    """No linemerge, no RDP, no bend-split, no ref filtering: w100 keeps
    all three of its own nodes and w101 is kept despite having no
    ``ref`` (the processed tier drops unrefed lines)."""
    nodes, ways = _osm_fixture()
    got = {w.way_id: w.coords for w in capture_osm_taxi_linework(
        nodes, ways, _to_m())}
    assert len(got["w100"]) == 3
    assert "w101" in got


def test_service_apt_pieces_are_carried(gate_on):
    """Ruling 5's substrate corollary: service pieces COUNT for
    membership / coverage and are excluded only from the STRUNG
    domain, so the capture must NOT filter them out."""
    layout = _layout()
    _capture(layout)
    flags = [svc for _c, svc in layout.string_substrate_src["apt"]]
    assert flags == [False, False, True]


def test_hook_reader_consumes_the_captured_field(gate_on):
    """END TO END: the hook's OWN reader must accept what capture
    writes — field shape, fingerprint and all.

    This is the property Ruling 4 is for: the object at the hook is the
    object phase 1 measured.  ``substrate_from_carriage`` recomputes the
    fingerprint and RAISES on mismatch, so a green run here is the
    identity proof, not a shape guess.
    """
    from auto_patch.elevation_per_surface.route_profile.taut_string import (
        substrate_from_carriage)

    layout = _layout()
    _capture(layout)

    logged: list[str] = []
    sub = substrate_from_carriage(layout, station_m=5.0, log=logged.append)

    assert sub is not None
    assert any("fp " in m for m in logged), (
        "the hook must log the denominator line")


def test_hook_reader_rejects_a_tampered_field(gate_on):
    """Non-vacuity for the test above: if the carried tiers are altered
    after capture, the hook's assertion must FIRE."""
    from auto_patch.elevation_per_surface.route_profile.taut_string import (
        substrate_from_carriage)

    layout = _layout()
    _capture(layout)
    layout.string_substrate_src["apt"].pop()

    with pytest.raises(AssertionError, match="fingerprint mismatch"):
        substrate_from_carriage(layout, station_m=5.0)


def test_capture_reads_no_osm_file(gate_on, monkeypatch):
    """No second read of any OSM file: the capture is handed the
    already-loaded nodes/ways and must never reach the loader."""
    import auto_patch.osm_load as OL

    def _boom(*a, **k):
        raise AssertionError("capture re-read the OSM cache")

    monkeypatch.setattr(OL, "_load_osm_airports", _boom)
    monkeypatch.setattr(OL, "_load_osm_tile", _boom)

    layout = _layout()
    _capture(layout)
    assert len(layout.string_substrate_src["osm"]) == 2
