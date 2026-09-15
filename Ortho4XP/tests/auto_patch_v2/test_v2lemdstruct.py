"""THE FOUR LEMD 1.0.336 DERIVATIONS (Fable 2026-09-14; RULINGS
2026-09-14bp) — lane ``v2lemdstruct``.  One test per clause:

* (1) §34 (5) (a) THE UNDERPASS CLIP IS THE DECK CELL'S — a deck cell
  ASYMMETRIC about the way's centreline clips the bore to the cell, not
  to a centreline ribbon, and the clip is the cell ACROSS THE AXIS (a
  junction blob's whole plan bores every road standing in it);
* (2) §24 (1) (a) THE RIM IS THE WALL — REFUTED AS RULED and reported
  instead: the at-grade reference is a per-component contour, so the ring
  is measured against it and never moved onto it;
* (3) §33 (2) (a) THE PLATE MOUTH IS CLAMPED TO THE COVERED EXTENT — a
  viaduct plate longer than its bore leaves the portal at the bore's own
  end (twinned in ``test_v2wallplate.py``, beside the §33 (2) clause it
  amends);
* (4) §33 (4) / §34.5 (6) AMENDED — the deck spans THE WAY, and two
  parallel bridge ways sharing a crossing are ONE deck group reaching the
  ways' own ends.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString, Polygon
from shapely.strtree import STRtree

from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import basin_geometry as _bg
from auto_patch_v2.planar import structure_deck as _sd
from auto_patch_v2.planar import structure_underpass as _su

from test_v2rampwalk import _airport, TAGS_R          # the shared fixtures


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _C:
    """A governed pavement cell, as ``_deck_cell`` reads one."""

    kind = "pavement"
    role = "taxiway"
    ref = "pav157"


# ── (1) the underpass clip is the deck cell's ────────────────────────────

def test_the_clip_follows_an_asymmetric_deck_cell(law):
    """§34 (5) (a) (RULINGS 2026-09-14bp item 1).  LEMD taxiway F-6's way
    −1230 runs 0.25 m from ``pav157``'s NORTH kerb and 16.3 m from its
    south edge: a ribbon SYMMETRIC about the OSM centreline put the south
    mouth 10.0 m INSIDE the 16.6 m taxiway, the trench floor 5.48 m under
    the pavement with the grade break in it.  The clip is the CELL's own
    footprint across the axis, eroded by the rim stand-off and one
    identity step — so the bore leaves the pavement at the pavement's own
    south edge."""
    tn = law.tables.structures.tunnel
    grid = max(law.tables.emit.identity.min_distinct_spacing_m, 0.1)
    erode = tn.wall_gap_m + tn.wall_band_width_m + grid
    # the deck runs along +x; the cell spans y in [-0.25, +16.3]
    deck = OsmWay(-1230, "airport", ((-60.0, 0.0), (60.0, 0.0)), False,
                  {"aeroway": "taxiway", "bridge": "yes", "layer": "1"})
    road = OsmWay(-5820, "big_roads", ((0.0, -200.0), (0.0, 200.0)), False, TAGS_R)
    cell = Polygon([(-200.0, -0.25), (200.0, -0.25), (200.0, 16.3), (-200.0, 16.3)])
    airport = _airport(law, ways=[deck, road])
    ways, _parents, notes = _su.underpass_bores(airport, law, [_C()], [cell])
    assert len(ways) == 1, notes
    ys = sorted(q[1] for q in ways[0].points)
    # the bore reaches the cell's own two kerbs, less the erosion: NOT a
    # ribbon centred on y = 0
    # the south kerb, brought in by the erosion; the north side has less
    # room than the erosion needs and floors at one identity step
    assert ys[-1] == pytest.approx(16.3 - erode, abs=0.05)
    assert ys[0] == pytest.approx(-grid, abs=0.05)
    assert abs(ys[0]) < abs(ys[-1]) - 5.0, "the clip must not be symmetric"
    assert "the deck CELL's footprint across the axis" in notes[0]


def test_a_blob_cells_whole_plan_never_becomes_the_clip(law):
    """§34 (5) (a), measured: ``pav157`` is a 200,195 m2 junction BLOB, and
    clipping the bored road to the CELL'S WHOLE PLAN bored 7 roads instead
    of 2 (LEMD bores 70 → 75, tunnels 50 → 53) — every road standing
    anywhere in the junction.  The cell states where the crossing is
    COVERED, which is the band between its kerbs at the way's own
    stations, so a road 150 m away in the same cell is untouched."""
    deck = OsmWay(-1230, "airport", ((-30.0, 0.0), (30.0, 0.0)), False,
                  {"aeroway": "taxiway", "bridge": "yes", "layer": "1", "width": "23"})
    under = OsmWay(-5820, "big_roads", ((0.0, -200.0), (0.0, 200.0)), False, TAGS_R)
    far = OsmWay(-5821, "big_roads", ((120.0, -200.0), (120.0, 200.0)), False, TAGS_R)
    blob = Polygon([(-160.0, -160.0), (160.0, -160.0), (160.0, 160.0), (-160.0, 160.0)])
    airport = _airport(law, ways=[deck, under, far])
    ways, _p, notes = _su.underpass_bores(airport, law, [_C()], [blob])
    assert {w.id for w in ways} == {-5820}, notes


# ── (2) the rim is the wall — REFUTED AS RULED, reported ─────────────────

def test_the_rim_is_reported_against_the_at_grade_reference_never_snapped(law):
    """§24 (1) (a) (RULINGS 2026-09-14bp item 5) ruled the rim station
    SNAPS onto the shell's at-grade outer face.  REFUTED by measurement
    and deleted: ``obj8.at_grade_geometry`` clips each component at ONE
    plane — the DEM under that component's centroid — so over LEMD's T4S
    pit (ground 593 … 599 across the plate) it is a CONTOUR through the
    middle of the shell, reading median 19.73 m / worst 51.67 m from the
    region ring with only 24 of 111 stations within 2 m.  Snapping to it
    would drag a 28,345 m2 cut ~20 m inward.  What stands is the REPORT."""
    ring = Polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])
    # a "wall" the reference puts 20 m inside the ring, as the contour does
    contour = STRtree([LineString([(20.0, 20.0), (80.0, 20.0), (80.0, 80.0),
                                   (20.0, 80.0), (20.0, 20.0)])])
    dists, probe = _bg.rim_wall_report(ring, [contour], 10.0, 2.0)
    assert dists and min(dists) == pytest.approx(20.0, abs=1e-6)
    assert probe[2.0] == 0 and probe[6.0] == 0 and probe[25.0] > 0
    # the module exports no snap: the ring is never moved onto that line
    assert not hasattr(_bg, "rim_on_wall")


# ── (4) the deck spans the way; parallel ways are one deck ───────────────

def _bridge(wid, y):
    return OsmWay(wid, "big_roads", ((-60.0, y), (60.0, y)), False,
                  {"highway": "service", "bridge": "yes", "lanes": "2"})


def test_the_deck_spans_the_way_not_the_corridor(law):
    """§33 (4) / §34.5 (6) AMENDED (RULINGS 2026-09-14bp item 10; the
    owner's words: "that's bridge extent to cover the terrain cutting down
    to the road running under it").  The face was clipped to the tunnel
    corridor ⊕ 2 m, so LEMD's two decks ended 15–21 m short of way −6288's
    own nodes and a 2.2 m notch daylighted into the cutting past them."""
    axis = LineString([(0.0, -100.0), (0.0, 100.0)])
    w = _bridge(-6288, 0.0)
    lines = [LineString(w.points)]
    out = _sd.deck_intervals(axis, 10.0, [w], lines, STRtree(lines), law)
    assert len(out) == 1
    face = out[0][3]
    x0, _y0, x1, _y1 = face.bounds
    # the WAY's own extent (120 m), never the corridor's 2 x (10 + 2) m
    assert x1 - x0 == pytest.approx(120.0, abs=0.01)


def test_two_parallel_bridge_ways_are_one_deck_group(law):
    """§33 (4) as amended: two mapped bridge ways that share a crossing and
    run parallel are ONE bridge — one FACE (the strip between the
    carriageways closed: the owner's "no small gap here") and ONE
    transverse plane at each end (``group_way``'s matched mean ends).
    Measured LEMD −6288 / −6291: clipped and end-equalised independently,
    their east levels solved 606.91 against 608.40 with a three-node rim
    sliver between them."""
    axis = LineString([(0.0, -100.0), (0.0, 100.0)])
    ws = [_bridge(-6288, 0.0), _bridge(-6291, 9.0)]
    lines = [LineString(w.points) for w in ws]
    ivals = _sd.deck_intervals(axis, 10.0, ws, lines, STRtree(lines), law)
    assert len(ivals) == 2
    # their s-ranges along the axis are DISJOINT (that is what two parallel
    # carriageways are), so a strict overlap test would group nothing
    (_w0, a0, a1, _f0), (_w1, b0, b1, _f1) = ivals
    assert max(a0, b0) > min(a1, b1)
    grid = law.tables.emit.identity.min_distinct_spacing_m
    items = _sd.deck_items(ivals, [], grid, law)
    assert len(items) == 1, "the two carriageways are ONE deck"
    _w, _s0, _s1, face, pav, dways, closed = items[0]
    assert not pav and {x.id for x in dways} == {-6288, -6291}
    assert closed > 0.0 and face.geom_type == "Polygon"
    assert len(face.interiors) == 0, "no rim sliver between the carriageways"
    # one transverse plane: the group's ends are the members' matched means
    gw = _sd.group_way(list(dways))
    assert gw.points[0] == pytest.approx((-60.0, 4.5))
    assert gw.points[1] == pytest.approx((60.0, 4.5))
    # ...and a way that crosses the same corridor at an angle is NOT grouped
    skew = OsmWay(-7000, "big_roads", ((-60.0, -60.0), (60.0, 60.0)), False,
                  {"highway": "service", "bridge": "yes", "lanes": "2"})
    lines2 = lines + [LineString(skew.points)]
    iv2 = _sd.deck_intervals(axis, 10.0, ws + [skew], lines2, STRtree(lines2), law)
    assert len(_sd.deck_groups(iv2, law)) == 2


def test_a_gap_wider_than_the_law_keeps_two_faces(law):
    """§33 (4) as amended: a gap WIDER than ``[bridge]
    deck_group_gap_max_m`` is not a bridge's median but real ground
    between two separate structures, and each way keeps its own face."""
    axis = LineString([(0.0, -100.0), (0.0, 100.0)])
    far = law.tables.structures.bridge.deck_group_gap_max_m + 20.0
    ws = [_bridge(-6288, 0.0), _bridge(-6291, far)]
    lines = [LineString(w.points) for w in ws]
    ivals = _sd.deck_intervals(axis, 10.0, ws, lines, STRtree(lines), law)
    items = _sd.deck_items(ivals, [], 0.5, law)
    assert len(items) == 2 and all(not it[4] for it in items)


def test_a_group_that_cannot_close_keeps_one_face_per_way(law):
    """§33 (4) as amended, the transitive case: ``deck_groups`` unions by
    PAIRS, so three ways each within ``deck_group_gap_max_m`` of the next
    land in ONE group that spans more than the cap.  ``_deck_face`` then
    cannot close it — and must hand the members back one face each, never
    the largest piece alone (which would DELETE two decks silently)."""
    axis = LineString([(0.0, -200.0), (0.0, 200.0)])
    cap = law.tables.structures.bridge.deck_group_gap_max_m
    ws = [_bridge(-1, 0.0), _bridge(-2, cap * 0.9 + 7.0), _bridge(-3, 2 * (cap * 0.9 + 7.0))]
    lines = [LineString(w.points) for w in ws]
    ivals = _sd.deck_intervals(axis, 10.0, ws, lines, STRtree(lines), law)
    assert len(_sd.deck_groups(ivals, law)) == 1, "the three chain into one group"
    items = _sd.deck_items(ivals, [], 0.5, law)
    assert len(items) == 3, "no deck may be dropped when the group cannot close"
    assert {it[0].id for it in items} == {-1, -2, -3}
