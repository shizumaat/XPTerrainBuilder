"""Round 10 — tunnel emission: evidence before depth, walls never cover ramps.

Spec: ``docs/specs/round10-tunnel-emission-spec.md`` including its
2026-08-11 AMENDMENTS (A1-A7), which supersede several lines of the
frozen text after the implementer measured them against the code:

R10-1/A1/A6  NO PHYSICAL EVIDENCE, NO DEPTH — and THE COVER IS THE DECK.
          Per mapped way, below-grade geometry is emitted iff the DEM
          probe MEASURED a cut, OR (``layer < 0`` AND the probe could not
          measure at all), OR (tag evidence AND the way is NOT mostly
          under a building AND it IS meaningfully under airside
          pavement).  A1's first two disjuncts alone refused KCLT area
          1's four building-passthroughs (right) and all 8 of OTHH's
          mapped bores (wrong): a bare-earth DEM carries no cut under a
          man-made bore, so WHAT COVERS THE BORE is the discriminator —
          a building is a deck the road passes under at grade, an apron
          is a deck the road passes under in a bore.
          ``tunnel=building_passage`` never seeds SYNTHETIC depth.  Every
          refusal mints a ``tunnel_passthrough_findings`` record carrying
          both cover fractions, the layer value and the deciding reason.
R10-2/A4/A7(c)  A wall/roof/cap NEVER covers tunnel pavement, and ALL
          surviving pieces >= 0.5 m2 are kept — the largest-piece rule
          was a silent deletion of the other arcs.
          ``tunnel_unwalled_mouth`` is the reported backstop, EXEMPTING
          light-touch clusters (cap + roof, no side walls, by owner
          ruling 2026-07-17).
R10-3/A3/A5/A7(b)  Facing portals across an open gap are DISTINCT
          entrances: dedup keys on PORTAL IDENTITY, never walk overlap.
          A same-road facing pair is ONE lowered stretch — the gap emits
          a single roofless walled corridor at the pair's JOINT depth,
          and neither portal ramps to grade inside it.  Mouth depth is
          floored by ``BRIDGE_ROAD_CLEARANCE_M`` below the measured deck.
A2 struck the stationing bullet: mouths already anchor at mapped end
nodes, so there is no stationing test here — the 10 m acceptance is
carried by the dedup law and pinned by ``TestFacingBoresBothEmit``.
A7(a) ratified the ``_cut_measured`` / ``cut_detected`` evidence-vs-mode
split, pinned by ``tests/test_tunnel_dem_cut_portals.py``'s gate-off test
passing unmodified.

All fixtures are synthetic and headless (local-metre geometry built in
code, monkeypatched road loader + DEM sampler; no network, no X-Plane
install, nothing written) — the idiom of
``tests/test_tunnel_dem_cut_portals.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from auto_patch import bridges  # noqa: E402
from auto_patch import config as _CFG  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    BuiltShape,
    PavementLayout,
    ROLE_BOUNDARY,
    ROLE_BUILDING,
    ROLE_JUNCTION,
    ROLE_RETAINING_WALL,
    ROLE_TUNNEL_RAMP,
)

ANCHOR_LATITUDE = 35.2202
ANCHOR_LONGITUDE = -80.9459
ANCHOR = (ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
TILE_LATITUDE = 35
TILE_LONGITUDE = -81

AIRPORT_SURFACE_M = 100.0
# A cut deeper than ``TUNNEL_DEM_CUT_MIN_DROP_M`` (3.0) so the probe
# reports one; the spec's illustrative "2.0 m cut" sits BELOW the
# detector's own floor and could never reach the clamp under test.
DEEP_TRENCH_FLOOR_M = 80.0
SHALLOW_TRENCH_FLOOR_M = 96.5      # a 3.5 m cut — detected, but the
#                                    crossing needs 5.1 m of clearance


# ══════════════════════════════════════════════════════════════════
# Scene builders
# ══════════════════════════════════════════════════════════════════
def _road_network(tunnel_tags: dict) -> tuple[dict, list, set, dict]:
    """One ``tunnel`` way east-west under a taxiway strip, with a 400 m
    surface approach at each mapped end.  ``tunnel_tags`` carries the
    tag set under test (``tunnel``/``layer``)."""
    _to_m, m_to_ll = bridges._local_meter_projections(ANCHOR)
    nodes_m = {
        "A": (-60.0, 0.0), "M": (0.0, 0.0), "B": (60.0, 0.0),
        "W1": (-160.0, 0.0), "W2": (-260.0, 0.0), "W3": (-460.0, 0.0),
        "E1": (160.0, 0.0), "E2": (260.0, 0.0), "E3": (460.0, 0.0),
    }
    nodes_r = {nid: m_to_ll(x, y) for nid, (x, y) in nodes_m.items()}
    tags = {"highway": "unclassified"}
    tags.update(tunnel_tags)
    ways_r = [
        ("TUN", ["A", "M", "B"], tags),
        ("APPW", ["A", "W1", "W2", "W3"], {"highway": "unclassified"}),
        ("APPE", ["B", "E1", "E2", "E3"], {"highway": "unclassified"}),
    ]
    return nodes_r, ways_r, {"TUN"}, {}


def _facing_network() -> tuple[dict, list, set, dict]:
    """TWO mapped bores separated by an OPEN 56 m gap — KCLT's area-2
    shape (F|-255 end 1 and F|-251's end, 55.5 m apart).  The roadway
    across the gap is ONE surface way, so each bore's outward approach
    walks it: the pre-A3 overlap dedup deleted one entrance entirely."""
    _to_m, m_to_ll = bridges._local_meter_projections(ANCHOR)
    nodes_m = {
        # west bore: -160 .. -60 ; gap: -60 .. -4 ; east bore: -4 .. 96
        "WA": (-160.0, 0.0), "WM": (-110.0, 0.0), "WB": (-60.0, 0.0),
        "EA": (-4.0, 0.0), "EM": (46.0, 0.0), "EB": (96.0, 0.0),
        "W1": (-260.0, 0.0), "W2": (-460.0, 0.0),
        "E1": (196.0, 0.0), "E2": (396.0, 0.0),
    }
    nodes_r = {nid: m_to_ll(x, y) for nid, (x, y) in nodes_m.items()}
    bore = {"highway": "unclassified", "tunnel": "yes", "layer": "-1"}
    ways_r = [
        ("WEST", ["WA", "WM", "WB"], dict(bore)),
        ("EAST", ["EA", "EM", "EB"], dict(bore)),
        # the shared open roadway between the two mapped mouths
        ("GAP", ["WB", "EA"], {"highway": "unclassified"}),
        ("APPW", ["WA", "W1", "W2"], {"highway": "unclassified"}),
        ("APPE", ["EB", "E1", "E2"], {"highway": "unclassified"}),
    ]
    return nodes_r, ways_r, {"WEST", "EAST"}, {}


def _boundary_ribbon() -> BuiltShape:
    """A DENSIFIED boundary ring along the road corridor.

    ``_airport_elevation_at`` reads the nearest ribbon VERTEX within
    200 m, so a plain 4-corner box leaves mid-corridor portals with no
    airport elevation and the whole scene silently drops.
    """
    ring = ([(x, -120.0) for x in range(-560, 561, 40)]
            + [(x, 120.0) for x in range(560, -561, -40)])
    return BuiltShape(polygon=Polygon(ring), role=ROLE_BOUNDARY,
                      ref="airport_boundary",
                      node_altitudes=[AIRPORT_SURFACE_M] * (len(ring) + 1))


def _building_covered_network() -> tuple[dict, list, set, dict]:
    """KCLT area 1's shape: the bore runs under a BUILDING, well clear of
    any pavement — the cover that says "at grade"."""
    _to_m, m_to_ll = bridges._local_meter_projections(ANCHOR)
    nodes_m = {
        "A": (-60.0, 300.0), "M": (0.0, 300.0), "B": (60.0, 300.0),
        "W1": (-160.0, 300.0), "W2": (-360.0, 300.0),
        "E1": (160.0, 300.0), "E2": (360.0, 300.0),
    }
    nodes_r = {nid: m_to_ll(x, y) for nid, (x, y) in nodes_m.items()}
    ways_r = [
        ("TUN", ["A", "M", "B"],
         {"highway": "service", "tunnel": "yes", "layer": "-1"}),
        ("APPW", ["A", "W1", "W2"], {"highway": "service"}),
        ("APPE", ["B", "E1", "E2"], {"highway": "service"}),
    ]
    return nodes_r, ways_r, {"TUN"}, {}


def _layout(with_building: bool = False, with_taxiway: bool = True,
            building_box=None) -> PavementLayout:
    layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
    if with_taxiway:
        # The pavement over the bore — A6's "the pavement is the deck".
        layout.shapes.append(BuiltShape(
            polygon=box(-40.0, -200.0, 40.0, 200.0),
            role=ROLE_JUNCTION, ref="taxiway"))
    layout.shapes.append(_boundary_ribbon())
    if with_building or building_box is not None:
        # A footprint covering the WHOLE bore — KCLT area 1's 100 %
        # cover fraction, the evidence that refuses it.
        layout.shapes.append(BuiltShape(
            polygon=(building_box if building_box is not None
                     else box(-80.0, -40.0, 80.0, 40.0)),
            role=ROLE_BUILDING, ref="building1"))
    return layout


def _install(monkeypatch, *, network, dem):
    """Wire ``network`` and a DEM sampler.  ``dem`` maps local metres to
    an elevation, or to ``None`` for an UNUSABLE probe."""
    monkeypatch.setattr(bridges, "_load_tunnel_road_network",
                        lambda _layout: network)
    to_m, _m_to_ll = bridges._local_meter_projections(ANCHOR)

    def _sample(_dem, _tile_lat, _tile_lon, lat, lon):
        x_m, y_m = to_m(lon, lat)
        return dem(x_m, y_m)

    monkeypatch.setattr(bridges, "_sample_dem", _sample)


def _flat_dem(_x, _y):
    return AIRPORT_SURFACE_M


def _no_dem(_x, _y):
    return None


def _trench(floor_m: float, half_width_m: float = 6.0):
    def _dem(_x, y_m):
        return floor_m if abs(y_m) <= half_width_m else AIRPORT_SURFACE_M
    return _dem


def _refs(layout, *names) -> list:
    return [s for s in layout.shapes
            if getattr(s, "ref", "") in names]


_BELOW_GRADE_REFS = ("tunnel_ramp", "tunnel_mouth", "tunnel_wall",
                     "tunnel_roof", "tunnel_cap", "tunnel_corridor")


# ══════════════════════════════════════════════════════════════════
# 1. R10-1 / A1 — the passthrough twin
# ══════════════════════════════════════════════════════════════════
class TestNoEvidenceNoDepth:
    """A flat DEM refuses below-grade geometry whatever the tag says."""

    def test_flat_dem_untagged_layer_emits_nothing(self, monkeypatch):
        # Nothing covers this bore, so no A6 disjunct can rescue it.
        _install(monkeypatch, network=_road_network({"tunnel": "yes"}),
                 dem=_flat_dem)
        layout = _layout(with_taxiway=False)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert _refs(layout, *_BELOW_GRADE_REFS) == []

    def test_flat_dem_records_a_finding_with_cover_and_layer(
            self, monkeypatch):
        # A1: the refusal is EVIDENCE, never silence — a wrongly refused
        # real bore has to be visible.  Cover fraction is recorded and is
        # NOT what admitted or refused the portal.
        _install(monkeypatch,
                 network=_road_network({"tunnel": "yes", "layer": "-1"}),
                 dem=_flat_dem)
        layout = _layout(with_building=True)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        findings = getattr(layout, "tunnel_passthrough_findings", [])
        assert findings, "a refused portal must mint a finding"
        one = findings[0]
        assert one["way_id"] == "TUN"
        assert one["layer"] == "-1"
        assert one["median_cross_road_depth_m"] == pytest.approx(
            0.0, abs=0.05)
        assert one["building_cover_fraction"] == pytest.approx(1.0)

    def test_layer_below_with_a_USABLE_flat_dem_still_emits_nothing(
            self, monkeypatch):
        # A1's core, superseding the frozen spec's "layer=-1 ⇒ synthetic
        # survives": the measured flatness OUTRANKS the tag.  This is the
        # KCLT area-1 class exactly (four layer=-1 service ways, cross-
        # road relief 0.016-0.222 m, emitting ramps at −8 m).
        _install(monkeypatch,
                 network=_road_network({"tunnel": "yes", "layer": "-1"}),
                 dem=_flat_dem)
        layout = _layout(with_taxiway=False)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert _refs(layout, *_BELOW_GRADE_REFS) == []

    def test_layer_below_with_an_UNUSABLE_dem_keeps_the_synthetic(
            self, monkeypatch):
        # The one surviving synthetic case: an explicit below-grade
        # statement the DEM cannot corroborate BECAUSE IT CANNOT MEASURE.
        _install(monkeypatch,
                 network=_road_network({"tunnel": "yes", "layer": "-1"}),
                 dem=_no_dem)
        layout = _layout()
        emitted = bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert emitted >= 1
        assert _refs(layout, "tunnel_ramp"), (
            "layer<0 with no usable DEM keeps the synthetic fallback")

    def test_building_passage_never_seeds_synthetic_depth(
            self, monkeypatch):
        # Covered-at-grade by definition.  With no cut and layer<0 it is
        # refused where a plain `tunnel=yes` would have been admitted by
        # the unusable-DEM branch.
        _install(monkeypatch,
                 network=_road_network(
                     {"tunnel": "building_passage", "layer": "-1"}),
                 dem=_no_dem)
        layout = _layout()
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert _refs(layout, *_BELOW_GRADE_REFS) == []

    def test_a_pavement_covered_bore_admits_with_NO_cut(
            self, monkeypatch):
        # A6, the OTHH class: 8 mapped bores under aprons on dead-flat
        # desert.  A bare-earth DEM carries no cut under a man-made bore,
        # so "no cut" refused every one of them; the APRON over the bore
        # is the deck that says it is one.
        _install(monkeypatch,
                 network=_road_network({"tunnel": "yes", "layer": "-1"}),
                 dem=_flat_dem)
        layout = _layout()          # the taxiway strip covers the bore
        emitted = bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert emitted >= 1
        assert _refs(layout, *_BELOW_GRADE_REFS), (
            "pavement cover admits a bore the DEM cannot show")

    def test_a_building_covered_way_still_refuses(self, monkeypatch):
        # A6 must not re-admit KCLT area 1.  Same flat DEM, same tags —
        # the cover is a BUILDING, so the road is at grade under it.
        _install(monkeypatch,
                 network=_building_covered_network(),
                 dem=_flat_dem)
        layout = _layout(building_box=box(-80.0, 260.0, 80.0, 340.0))
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert _refs(layout, *_BELOW_GRADE_REFS) == []
        findings = getattr(layout, "tunnel_passthrough_findings", [])
        assert findings
        one = findings[0]
        assert one["admitted_by"] is None
        assert one["refused_because"] == "building_cover"
        assert one["building_cover_fraction"] >= 0.9
        assert one["airside_pavement_cover_fraction"] < 0.1

    def test_open_ground_with_a_tunnel_tag_and_no_cover_refuses(
            self, monkeypatch):
        # The third population: tagged, no cut, and covered by NOTHING.
        # Neither disjunct fires — a tag alone never digs a hole.
        _install(monkeypatch,
                 network=_road_network({"tunnel": "yes", "layer": "-1"}),
                 dem=_flat_dem)
        layout = _layout(with_taxiway=False)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert _refs(layout, *_BELOW_GRADE_REFS) == []
        findings = getattr(layout, "tunnel_passthrough_findings", [])
        assert findings
        assert findings[0]["refused_because"] == "no_cover_no_cut"

    def test_the_cover_thresholds_straddle_the_measured_gap(self):
        # The constants are only defensible inside the measured gaps:
        # passthroughs 0.98-1.00 building / <=0.02 pavement, real bores
        # 0.00 building / >=0.18 pavement.
        assert 0.02 < bridges.TUNNEL_PASSTHROUGH_BUILDING_COVER_FRAC < 0.98
        assert 0.02 < bridges.TUNNEL_BORE_PAVEMENT_COVER_FRAC < 0.18

    def test_a_real_cut_still_emits(self, monkeypatch):
        # The counter-example that keeps the law honest: R10-1 refuses
        # UNEVIDENCED depth, never evidenced depth.
        _install(monkeypatch, network=_road_network({"tunnel": "yes"}),
                 dem=_trench(DEEP_TRENCH_FLOOR_M))
        layout = _layout()
        emitted = bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert emitted >= 1
        assert _refs(layout, "tunnel_mouth")


# ══════════════════════════════════════════════════════════════════
# 2. R10-2 / A4 — the wall-cut twin
# ══════════════════════════════════════════════════════════════════
class TestCoverNeverCoversTunnelPavement:
    """A wall/roof/cap is cut against the tunnel pavement union, and
    every surviving arc is kept."""

    def test_a_ring_split_into_three_arcs_keeps_all_three(self):
        # The largest-piece regression pin: one long wall bar crossed by
        # two ramps splits into 3 arcs.  `parts9[0]` shipped ONE.
        wall = BuiltShape(polygon=box(0.0, 0.0, 100.0, 4.0),
                          role=ROLE_RETAINING_WALL, ref="tunnel_wall",
                          altitude=100.0)
        ramps = unary_union([box(30.0, -1.0, 40.0, 5.0),
                             box(60.0, -1.0, 70.0, 5.0)])
        pieces = bridges._tunnel_cover_pieces(wall, ramps)
        assert len(pieces) == 3
        assert all(p.ref == "tunnel_wall" for p in pieces)
        assert all(p.altitude == 100.0 for p in pieces)
        assert sum(p.polygon.area for p in pieces) == pytest.approx(
            100.0 * 4.0 - 2 * 10.0 * 4.0)
        for piece in pieces:
            assert piece.polygon.intersection(ramps).area == \
                pytest.approx(0.0, abs=1e-9)

    def test_pieces_below_the_floor_are_dropped(self):
        wall = BuiltShape(polygon=box(0.0, 0.0, 10.0, 4.0),
                          role=ROLE_RETAINING_WALL, ref="tunnel_wall",
                          altitude=100.0)
        # Leaves a 0.1 x 4 m = 0.4 m2 sliver on the left, 5.9 x 4 right.
        ramps = box(0.1, -1.0, 4.1, 5.0)
        pieces = bridges._tunnel_cover_pieces(wall, ramps)
        assert len(pieces) == 1
        assert pieces[0].polygon.area == pytest.approx(5.9 * 4.0)

    def test_a_sloped_wall_keeps_a_profile_on_every_piece(self):
        wall = BuiltShape(polygon=box(0.0, 0.0, 100.0, 4.0),
                          role=ROLE_RETAINING_WALL, ref="tunnel_wall",
                          altitude_high=110.0, altitude_low=100.0)
        pieces = bridges._tunnel_cover_pieces(
            wall, box(40.0, -1.0, 50.0, 5.0))
        assert len(pieces) == 2
        for piece in pieces:
            assert piece.node_altitudes, (
                "a clipped sloped rect converts to per-vertex values — "
                "ring-order slope semantics do not survive a clip")
            assert piece.altitude_high is None
            assert piece.altitude_low is None

    def test_finalize_cuts_walls_roofs_and_caps_patch_wide(self):
        # A4: the finalize pass is the only one that sees CROSS-CLUSTER
        # ordering — a later cluster's ramp landing on an earlier
        # cluster's wall.  ``tunnel_mouth`` is in the cutting union
        # because it is road surface, and there is no overlap tolerance.
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        pre = {id(s) for s in layout.shapes}
        for ref, geom in (
                ("tunnel_wall", box(0.0, 0.0, 100.0, 4.0)),
                ("tunnel_roof", box(0.0, 10.0, 100.0, 14.0)),
                ("tunnel_cap", box(0.0, 20.0, 100.0, 24.0))):
            layout.shapes.append(BuiltShape(
                polygon=geom, role=ROLE_RETAINING_WALL, ref=ref,
                altitude=100.0))
        layout.shapes.append(BuiltShape(
            polygon=box(30.0, -5.0, 40.0, 30.0), role=ROLE_TUNNEL_RAMP,
            ref="tunnel_ramp", altitude=92.0))
        layout.shapes.append(BuiltShape(
            polygon=box(60.0, -5.0, 70.0, 30.0), role=ROLE_TUNNEL_RAMP,
            ref="tunnel_mouth", altitude=92.0))
        bridges._finalize_tunnel_emission(
            layout, [], 0.0, None, pre, 1)
        pavement = unary_union(
            [s.polygon for s in layout.shapes
             if s.ref in ("tunnel_ramp", "tunnel_mouth")])
        covers = [s for s in layout.shapes
                  if s.ref in ("tunnel_wall", "tunnel_roof", "tunnel_cap")]
        # 3 bars x 3 arcs each — nothing deleted by a largest-piece rule.
        assert len(covers) == 9
        for cover in covers:
            assert cover.polygon.intersection(pavement).area == \
                pytest.approx(0.0, abs=1e-9)

    def test_finalize_clips_a_roof_off_pavement(self):
        # R10-3: the roof plate is half a carriageway WIDE, so clipping
        # only its bore centreline left it overhanging the taxiway it was
        # cover for (KCLT roof 1723 over junction 1668).
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        pre = {id(s) for s in layout.shapes}
        layout.shapes.append(BuiltShape(
            polygon=box(0.0, 0.0, 40.0, 20.0), role=ROLE_RETAINING_WALL,
            ref="tunnel_roof", altitude=100.0))
        pavement = box(30.0, 0.0, 200.0, 20.0)
        bridges._finalize_tunnel_emission(
            layout, [], 0.0, pavement, pre, 1)
        roofs = [s for s in layout.shapes if s.ref == "tunnel_roof"]
        assert roofs, "a grazing roof is clipped, not dropped whole"
        for roof in roofs:
            assert roof.polygon.intersection(pavement).area == \
                pytest.approx(0.0, abs=1e-9)


# ══════════════════════════════════════════════════════════════════
# 3. R10-2 / A3 — dedup keys on portal identity; unwalled backstop
# ══════════════════════════════════════════════════════════════════
class TestDedupKeysOnPortalIdentity:

    def test_a_restated_station_is_dropped(self):
        nodes_m = {"a": (0.0, 0.0), "b": (5.0, 0.0)}
        rows = [("a", "W1", [(0.0, 0.0), (100.0, 0.0)]),
                ("b", "W2", [(5.0, 0.0), (105.0, 0.0)])]
        kept = bridges._dedup_portal_walks(rows, nodes_m, 35.0)
        assert [r[1] for r in kept] == ["W1"]

    def test_facing_stations_beyond_the_cluster_distance_both_survive(self):
        # KCLT's 55.5 m gap: two DISTINCT entrances, both keep their
        # mouth.  The pre-A3 overlap test deleted one of them.
        nodes_m = {"a": (0.0, 0.0), "b": (55.5, 0.0)}
        rows = [("a", "W1", [(0.0, 0.0), (-100.0, 0.0)]),
                ("b", "W2", [(55.5, 0.0), (155.5, 0.0)])]
        kept = bridges._dedup_portal_walks(rows, nodes_m, 35.0)
        assert [r[1] for r in kept] == ["W1", "W2"]

    def test_a_ways_own_two_portals_never_dedup(self):
        nodes_m = {"a": (0.0, 0.0), "b": (5.0, 0.0)}
        rows = [("a", "W1", [(0.0, 0.0), (-100.0, 0.0)]),
                ("b", "W1", [(5.0, 0.0), (105.0, 0.0)])]
        kept = bridges._dedup_portal_walks(rows, nodes_m, 35.0)
        assert len(kept) == 2


class TestFacingBoresBothEmit:
    """A3 end-to-end: the acceptance shape that the 48.3 m KCLT miss
    came from — two mapped bores across an open gap."""

    def _emit(self, monkeypatch):
        _install(monkeypatch, network=_facing_network(),
                 dem=_trench(DEEP_TRENCH_FLOOR_M))
        layout = _layout()
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        return layout

    def test_both_facing_mouths_are_emitted(self, monkeypatch):
        layout = self._emit(monkeypatch)
        mouths = _refs(layout, "tunnel_mouth")
        # Each bore's INNER (gap-facing) mapped end keeps a mouth: the
        # 10 m acceptance bullet is carried here, not by anchor edits.
        inner = [m for m in mouths
                 if -70.0 <= m.polygon.centroid.x <= 10.0]
        assert len(inner) >= 2, (
            "facing entrances across an open gap BOTH emit a mouth")

    def test_the_gap_is_one_open_corridor(self, monkeypatch):
        layout = self._emit(monkeypatch)
        corridors = _refs(layout, "tunnel_corridor")
        assert len(corridors) == 1, (
            "the gap between two close mouths of one road is ONE "
            "lowered surface")
        # Acceptance shape: flat within 0.5 m end to end.
        corridor = corridors[0]
        if corridor.altitude is None:
            assert abs(corridor.altitude_high
                       - corridor.altitude_low) <= 0.5

    def test_the_two_facing_mouths_agree_on_one_depth(self, monkeypatch):
        # "the whole area is lowered … and flat between the two mouths":
        # a facing pair is ONE system at ONE depth, so a per-end reading
        # never tilts the surface between them.
        layout = self._emit(monkeypatch)
        inner = [m.altitude for m in _refs(layout, "tunnel_mouth")
                 if -70.0 <= m.polygon.centroid.x <= 10.0
                 and m.altitude is not None]
        assert len(inner) >= 2
        assert max(inner) - min(inner) <= 0.5

    def test_no_ramp_to_grade_inside_the_gap(self, monkeypatch):
        layout = self._emit(monkeypatch)
        corridor = _refs(layout, "tunnel_corridor")[0]
        for ramp in _refs(layout, "tunnel_ramp"):
            assert ramp.polygon.intersection(
                corridor.polygon).area == pytest.approx(0.0, abs=1e-6), (
                "ramps to grade emit only at the system's OUTER "
                "approaches")

    def test_no_wall_covers_any_tunnel_pavement(self, monkeypatch):
        layout = self._emit(monkeypatch)
        pavement = [s.polygon for s in layout.shapes
                    if s.ref in ("tunnel_ramp", "tunnel_mouth")]
        covers = [s.polygon for s in layout.shapes
                  if s.ref in ("tunnel_wall", "tunnel_roof", "tunnel_cap")]
        if not (pavement and covers):
            pytest.skip("scene emitted no cover/pavement pair")
        overlap = unary_union(covers).intersection(
            unary_union(pavement)).area
        assert overlap == pytest.approx(0.0, abs=1e-6)


def _facing_row(way_id, station, toward, mouth_grade, deck=None,
                carriage_w=10.0):
    """One ``portal_data`` row stationed at ``station`` whose outward
    approach heads at ``toward``."""
    return ("n" + way_id, way_id, [station, toward], "service",
            AIRPORT_SURFACE_M, AIRPORT_SURFACE_M, False, carriage_w,
            True, mouth_grade, [], deck, None)


class TestFacingSameRoadDetection:
    """A3's facing test is MUTUAL, same-road, and bounded by the open-cut
    design limit — never merely "a bore is near"."""

    _WAYS = {"W1": (["a"], {"highway": "service", "name": "Yorkmont"}),
             "W2": (["b"], {"highway": "service", "name": "Yorkmont"}),
             "W3": (["c"], {"highway": "service", "name": "Other"})}

    def test_same_road_facing_portals_pair_up(self):
        rows = [_facing_row("W1", (0.0, 0.0), (55.5, 0.0), 95.0),
                _facing_row("W2", (55.5, 0.0), (0.0, 0.0), 95.0)]
        idx, pairs = bridges._facing_same_road_portals(
            rows, self._WAYS, _CFG.TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M)
        assert pairs == [(0, 1)]
        assert idx == {0, 1}

    def test_a_different_road_never_pairs(self):
        rows = [_facing_row("W1", (0.0, 0.0), (55.5, 0.0), 95.0),
                _facing_row("W3", (55.5, 0.0), (0.0, 0.0), 95.0)]
        _idx, pairs = bridges._facing_same_road_portals(
            rows, self._WAYS, _CFG.TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M)
        assert pairs == []

    def test_portals_leading_AWAY_never_pair(self):
        rows = [_facing_row("W1", (0.0, 0.0), (-100.0, 0.0), 95.0),
                _facing_row("W2", (55.5, 0.0), (155.5, 0.0), 95.0)]
        _idx, pairs = bridges._facing_same_road_portals(
            rows, self._WAYS, _CFG.TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M)
        assert pairs == []

    def test_beyond_the_open_cut_limit_never_pairs(self):
        far = float(_CFG.TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M) + 20.0
        rows = [_facing_row("W1", (0.0, 0.0), (far, 0.0), 95.0),
                _facing_row("W2", (far, 0.0), (0.0, 0.0), 95.0)]
        _idx, pairs = bridges._facing_same_road_portals(
            rows, self._WAYS, _CFG.TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M)
        assert pairs == []


class TestOpenCutCorridor:
    """Owner ruling 2026-08-11: "the two close together tunnel mouths
    indicate the whole area is lowered … and flat between the two
    mouths" — the gap is ONE depressed surface, not two ramps."""

    def _emit(self, grade_a, grade_b, deck=AIRPORT_SURFACE_M):
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        rows = [_facing_row("W1", (0.0, 0.0), (55.5, 0.0), grade_a, deck),
                _facing_row("W2", (55.5, 0.0), (0.0, 0.0), grade_b, deck)]
        zones: list = []
        n = bridges._emit_facing_corridors(
            layout, rows, [(0, 1)], zones, 0.6, 1.0,
            lambda x, y: AIRPORT_SURFACE_M)
        return n, layout

    def test_equal_mouth_grades_emit_ONE_flat_corridor(self):
        floor = AIRPORT_SURFACE_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M)
        n, layout = self._emit(floor, floor)
        assert n == 1
        corridors = _refs(layout, "tunnel_corridor")
        assert len(corridors) == 1
        corridor = corridors[0]
        assert corridor.role == ROLE_TUNNEL_RAMP
        assert corridor.altitude == pytest.approx(floor, abs=0.01), (
            "a flat cut ships ONE altitude — no rounding tilts it")
        assert corridor.altitude_high is None
        # Acceptance: flat within 0.5 m end to end.
        assert corridor.polygon.area == pytest.approx(55.5 * 10.0, rel=0.02)

    def test_unequal_mouth_grades_interpolate_linearly(self):
        n, layout = self._emit(94.0, 92.0)
        assert n == 1
        corridor = _refs(layout, "tunnel_corridor")[0]
        assert corridor.altitude is None
        assert sorted([corridor.altitude_low,
                       corridor.altitude_high]) == [
            pytest.approx(92.0), pytest.approx(94.0)]

    def test_the_corridor_is_walled_both_sides_and_roofless(self):
        floor = AIRPORT_SURFACE_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M)
        _n, layout = self._emit(floor, floor)
        walls = _refs(layout, "tunnel_wall")
        assert len(walls) == 2, "one retaining wall down each side"
        corridor = _refs(layout, "tunnel_corridor")[0]
        for wall in walls:
            assert wall.node_altitudes, "walls follow the DEM"
            assert wall.polygon.intersection(
                corridor.polygon).area == pytest.approx(0.0, abs=1e-9)
        assert _refs(layout, "tunnel_roof") == [], (
            "an open cut is roofless — the gap is not tagged tunnel")

    def test_the_corridor_takes_the_clearance_floor(self):
        # The DEM's shallow read (98.0) loses to the clearance the
        # crossing requires.
        _n, layout = self._emit(98.0, 98.0)
        corridor = _refs(layout, "tunnel_corridor")[0]
        assert corridor.altitude == pytest.approx(
            AIRPORT_SURFACE_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M),
            abs=0.01)

    def test_the_corridor_is_tunnel_pavement_for_both_cutting_laws(self):
        assert "tunnel_corridor" in bridges._TUNNEL_PAVEMENT_REFS
        assert "tunnel_corridor" in bridges._TUNNEL_PAVEMENT_CUT_REFS


class TestUnwalledMouthFinding:

    def _layout_with_mouth(self, cover: Polygon | None):
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        pre = {id(s) for s in layout.shapes}
        layout.shapes.append(BuiltShape(
            polygon=box(0.0, 0.0, 10.0, 6.0), role=ROLE_TUNNEL_RAMP,
            ref="tunnel_mouth", altitude=92.0))
        if cover is not None:
            layout.shapes.append(BuiltShape(
                polygon=cover, role=ROLE_RETAINING_WALL,
                ref="tunnel_wall", altitude=100.0))
        return layout, pre

    def test_an_open_mouth_is_reported(self):
        layout, pre = self._layout_with_mouth(None)
        bridges._record_tunnel_mouth_walling(layout, pre, None)
        findings = getattr(layout, "tunnel_unwalled_mouth", [])
        assert findings
        assert findings[0]["uncovered_m"] == pytest.approx(32.0, abs=0.5)

    def test_a_walled_mouth_is_not_reported(self):
        # A ring standing off the mouth by less than the graze clearance
        # answers its whole perimeter.
        ring = box(-0.5, -0.5, 10.5, 6.5).difference(
            box(0.0, 0.0, 10.0, 6.0))
        layout, pre = self._layout_with_mouth(ring)
        bridges._record_tunnel_mouth_walling(layout, pre, None)
        assert not getattr(layout, "tunnel_unwalled_mouth", [])


# ══════════════════════════════════════════════════════════════════
# 4. R10-3 / A5 — mouth depth from clearance
# ══════════════════════════════════════════════════════════════════
class TestMouthDepthFromClearance:
    """A 1-arcsec DEM under-resolves a narrow cut; it may report DEEPER
    than the clearance the crossing requires, never shallower."""

    def _mouths(self, monkeypatch, floor_m):
        _install(monkeypatch, network=_road_network({"tunnel": "yes"}),
                 dem=_trench(floor_m))
        layout = _layout()
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        return _refs(layout, "tunnel_mouth")

    def test_a_shallow_dem_cut_is_floored_at_the_clearance(
            self, monkeypatch):
        # 3.5 m of measured cut, 5.1 m structurally required.
        mouths = self._mouths(monkeypatch, SHALLOW_TRENCH_FLOOR_M)
        assert mouths
        floor = AIRPORT_SURFACE_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M)
        for mouth in mouths:
            assert mouth.altitude == pytest.approx(floor, abs=0.05), (
                "the mouth sits a full road clearance below the deck")

    def test_a_deep_dem_cut_is_left_alone(self, monkeypatch):
        # The clamp is a FLOOR, not a target: the DEM may say deeper.
        mouths = self._mouths(monkeypatch, DEEP_TRENCH_FLOOR_M)
        assert mouths
        for mouth in mouths:
            assert mouth.altitude == pytest.approx(
                DEEP_TRENCH_FLOOR_M, abs=0.1)

    def test_the_clearance_constant_is_the_deck_one(self):
        # A5: the deck-clearance constant, never the 4.2 m acceptance
        # minimum and never a new knob.
        assert float(_CFG.BRIDGE_ROAD_CLEARANCE_M) == pytest.approx(5.1)
