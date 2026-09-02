"""Tunnel portal fidelity — the four owner rulings of 2026-08-07 (OTHH).

Spec: ``docs/specs/tunnel-portal-fidelity-spec.md``; rulings:
``docs/RULINGS.md`` "2026-08-07 — Tunnel portal fidelity: four rulings".

All fixtures are synthetic and headless (local-metre geometry built in
code, no network, no X-Plane install) — the idiom of
``tests/test_implied_tunnel_level_crossing.py``.

C-1  ``_synthesize_implied_crossing_bores`` — a MAPPED ``tunnel=yes``
     way's merged bore interval snaps to the mapped extent ALWAYS, so
     the portal sits at the true mouth (s=0 / s=L) instead of 61 m
     inside the bore.
C-2  the low-connector open-cut record excludes ``_had_tunnel`` ways —
     a mapped bore's interior gap is roofed by definition and merges
     COVERED.

Both control arms are UN-TAGGED ways, and R4 (owner spec
``round4-othh-fixes``, 2026-08-10) has since ruled that a purely
geometric crossing is never a tunnel: they are DECLINED outright, and
the pre-R4 implied-bore geometry each was written for is asserted under
R4's named fallback (``O4_IMPLIED_TUNNEL_TAG_EVIDENCE=0``).
C-3  ``_emit_low_corridor_connectors`` cuts the corridor back by
     ``_TUNNEL_GRAZE_CLEARANCE_M`` (0.6 m), clear of the 0.5 m
     shared-vertex intern bucket.
C-4  ``_finalize_tunnel_emission`` — a ``tunnel_ramp`` piece is emitted
     WHOLE over pavement and CUTS it; a wall over pavement its own
     ramp removed survives; a ramp mostly on a runway-family shape is
     dropped loudly instead of cutting it.

THE RAMP-CUT BOUNDARIES ROUND (spec
``docs/specs/tunnel-ramp-cut-boundaries-spec.md``, rulings
``docs/RULINGS.md`` "2026-08-07 — Ramp-cut boundaries: walls, grades,
buildings") continues in the same file, because it is the same emitter
and the same cut:

W/G-1 the ruling-4 cut widens to a CLEARANCE ANNULUS (``wall_gap_m +
     retaining_wall_width_m``) — no remaining pavement vertex can sit in
     a ramp ring's ``SHARED_VERTEX_TOL_M`` intern bucket, so the
     cross-boundary value adoption that minted +665 adjudicated rows is
     geometrically impossible — and the tunnel's own perimeter wall band
     owns that annulus instead of being dropped as "under pavement".
     Adjacent ramp pieces of one walk present ONE value at each shared
     cross-edge node.
B-1  a ramp never crosses a building pad edge: the pad is neither cut nor
     buried, the open ramp CLIPS at the pad edge, and a piece left with
     nothing visible drops with its way id and the pad's shapeID named.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from shapely.geometry import Point, box
from shapely.ops import unary_union

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import O4_UI_Utils as UI  # noqa: E402
from auto_patch import bridges  # noqa: E402
from auto_patch import config as _CFG  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    BuiltShape,
    ROLE_BUILDING,
    ROLE_RUNWAY,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_RETAINING_WALL,
    ROLE_TUNNEL_RAMP,
    SHARED_VERTEX_TOL_M,
)


# ──────────────────────────────────────────────────────────────────
# C-1 / C-2 — the mapped-bore re-split scene
# ──────────────────────────────────────────────────────────────────
# The OTHH geometry at unit scale: an 810 m road running north, mapped
# as ONE ``tunnel=yes`` way, with our pavement crossing it 62 m from the
# south mouth (the stretch that used to fall under the 100 m mapped-end
# preservation threshold).
_WAY_LENGTH_M = 810.0
_CROSS_1 = (62.0, 112.0)        # first pavement crossing, s-interval
_CROSS_2 = (198.0, 248.0)       # second crossing → 86 m interior gap
_EDGE_MARGIN_M = 1.0            # TAXI_EDGE_BREAK_MARGIN_M
_END_STUB_M = 0.05              # the way-end clamp the splitter uses
# ``low_connector_max_gap_m`` as production computes it (2 x 8 m depth /
# 3.5 % planning grade) — well above both the 86 m gap and the 100 m
# open-cut design cap, so the gap MERGES either way and only its VISIBLE
# form (open cut vs covered roof) is under test.
_LOW_CONNECTOR_MAX_GAP_M = 2.0 * 8.0 / 0.035


def _mapped_bore_scene(crossings) -> tuple:
    """A single north-running road way crossed by ``crossings`` pavement
    boxes.  Returns ``(layout, nodes_m, way_node_ids)`` in local metres.
    """
    shapes = [
        BuiltShape(polygon=box(400.0, y0, 600.0, y1), role="apron")
        for (y0, y1) in crossings
    ]
    layout = SimpleNamespace(shapes=shapes)
    nodes_m = {"n1": (500.0, 0.0), "n2": (500.0, _WAY_LENGTH_M)}
    return layout, nodes_m, ["n1", "n2"]


def _piece_extent(piece, nodes_m) -> tuple:
    """The (s_start, s_end) arc extent of a returned way piece — the
    scene's way runs due north from y=0, so s == y."""
    ys = [nodes_m[n][1] for n in piece[1]]
    return (min(ys), max(ys))


def _bores(ways: list) -> list:
    return [w for w in ways if "o4_implied_tunnel" in w[2]]


def _surface_pieces(ways: list) -> list:
    return [w for w in ways if "o4_implied_tunnel" not in w[2]]


def _split(layout, nodes_m, way_ids, tags, low_gap_m=0.0):
    return bridges._synthesize_implied_crossing_bores(
        layout, nodes_m, [("road1", way_ids, tags)], None,
        low_connector_max_gap_m=low_gap_m, node_tags=None)


class TestMappedEndPreservation:
    """C-1 (ruling 1): a mapped bore's portal sits at the MAPPED mouth,
    unconditionally — the 62 m mouth stretch is covered tunnel, not
    mapper sloppiness."""

    def test_mapped_bore_portal_at_mapped_end(self) -> None:
        """The merged interval snaps to both way ends: one bore covering
        the whole mapped extent, no below-grade piece inside it."""
        layout, nodes_m, way_ids = _mapped_bore_scene([_CROSS_1])
        ways, gaps = _split(layout, nodes_m, way_ids,
                            {"highway": "primary", "tunnel": "yes"})
        bores = _bores(ways)
        assert len(bores) == 1
        start, end = _piece_extent(bores[0], nodes_m)
        # Portal at s=0 and s=L (within the 5 cm way-end clamp), NOT at
        # the pavement edge 61 m in.
        assert start == pytest.approx(_END_STUB_M, abs=0.01)
        assert end == pytest.approx(_WAY_LENGTH_M - _END_STUB_M, abs=0.01)
        # Everything outside the bore is the 5 cm end stub — no surface
        # (excavated-ramp) stretch survives inside the mapped extent.
        for piece in _surface_pieces(ways):
            s0, s1 = _piece_extent(piece, nodes_m)
            assert s1 - s0 <= 2.0 * _END_STUB_M
        assert gaps == []

    def test_untagged_crossing_is_declined_and_the_fallback_is_unchanged(
            self, monkeypatch) -> None:
        """The un-tagged control arm, in both laws.

        SUPERSEDED PREMISE, REWRITTEN.  This twin was
        ``test_implied_bore_portal_unchanged_at_pavement_edge`` and read
        the un-tagged case as C-1's regression control: the SAME geometry
        without a tunnel tag keeps the implied-bore split, portal one
        margin outside the pavement edge.  R4 (owner spec
        ``round4-othh-fixes``, 2026-08-10; config
        ``IMPLIED_TUNNEL_TAG_EVIDENCE``) rules that A PURELY GEOMETRIC
        CROSSING IS NEVER A TUNNEL: synthesis now requires the crossing
        way — or a way its chain reaches within
        ``IMPLIED_TUNNEL_TAG_EVIDENCE_M`` (100 m) — to carry
        ``tunnel=yes`` or ``layer`` < 0.  Measured at OTHH on 1.0.229:
        the S1 ramps at (25.2531, 51.6209) were engine-FABRICATED under
        untagged tertiary ways with no OSM tunnel on their chain at all.

        This scene's way is untagged with nothing else in it, so under
        R4 it is DECLINED — returned unsplit, with no bore and no gap.
        The contrast C-1 needs is preserved: the mapped sibling above
        snaps its portal to the mapped mouth, this one is not a tunnel.
        And the pre-R4 geometry the twin was written for is asserted
        exactly as it was, under R4's own named fallback
        (``O4_IMPLIED_TUNNEL_TAG_EVIDENCE=0``).
        """
        layout, nodes_m, way_ids = _mapped_bore_scene([_CROSS_1])
        ways, gaps = _split(layout, nodes_m, way_ids,
                            {"highway": "primary"})
        assert _bores(ways) == [], (
            "an untagged geometric crossing synthesised a bore — R4")
        assert gaps == []
        # Declined means UNTOUCHED: one piece, its own id and tags, the
        # whole way — not a split whose bore was merely dropped.
        assert len(ways) == 1
        assert ways[0][0] == "road1"
        assert ways[0][2] == {"highway": "primary"}
        assert _piece_extent(ways[0], nodes_m) == (0.0, _WAY_LENGTH_M)

        # THE PRE-RULING LAW, under its gate: the original assertions.
        monkeypatch.setattr(bridges, "IMPLIED_TUNNEL_TAG_EVIDENCE", False)
        layout, nodes_m, way_ids = _mapped_bore_scene([_CROSS_1])
        ways, gaps = _split(layout, nodes_m, way_ids,
                            {"highway": "primary"})
        bores = _bores(ways)
        assert len(bores) == 1
        start, end = _piece_extent(bores[0], nodes_m)
        assert start == pytest.approx(_CROSS_1[0] - _EDGE_MARGIN_M, abs=0.01)
        assert end == pytest.approx(_CROSS_1[1] + _EDGE_MARGIN_M, abs=0.01)
        # The long surface approaches on both sides are what the walk
        # ramps along — the behaviour C-1 must not disturb.
        lengths = sorted(s1 - s0
                         for (s0, s1) in (_piece_extent(p, nodes_m)
                                          for p in _surface_pieces(ways)))
        assert lengths[-1] > 100.0
        assert gaps == []


class TestMappedBoreInteriorIsRoofed:
    """C-2 (ruling 2): an interior gap of a MAPPED bore never becomes an
    open cut; the implied (KDFW) bore still records it."""

    def test_mapped_bore_interior_gap_not_dug_open(self) -> None:
        layout, nodes_m, way_ids = _mapped_bore_scene([_CROSS_1, _CROSS_2])
        ways, gaps = _split(layout, nodes_m, way_ids,
                            {"highway": "primary", "tunnel": "yes"},
                            low_gap_m=_LOW_CONNECTOR_MAX_GAP_M)
        assert gaps == []
        # Both crossings are inside ONE merged bore spanning the mapped
        # extent (the gap merged COVERED, per C-1 clamped to the ends).
        bores = _bores(ways)
        assert len(bores) == 1
        start, end = _piece_extent(bores[0], nodes_m)
        assert start == pytest.approx(_END_STUB_M, abs=0.01)
        assert end == pytest.approx(_WAY_LENGTH_M - _END_STUB_M, abs=0.01)

    def test_untagged_double_crossing_is_declined_before_any_gap(
            self, monkeypatch) -> None:
        """The KDFW control arm, in both laws.

        SUPERSEDED PREMISE, REWRITTEN.  As
        ``test_implied_bore_interior_gap_still_dug_open`` this twin
        asserted that the un-tagged double crossing still records its
        86 m interior gap for the flat low-connector emit.  R4 (owner
        spec ``round4-othh-fixes``, 2026-08-10; config
        ``IMPLIED_TUNNEL_TAG_EVIDENCE``) declines the whole synthesis
        for a purely geometric crossing, so there is no bore to record a
        gap BETWEEN — the OTHH 1.0.229 fabrication this ruling closed.
        C-2's contrast survives: the mapped sibling above roofs its
        interior gap by definition; this way is not a tunnel at all.
        The KDFW behaviour is asserted unchanged under R4's own named
        fallback (``O4_IMPLIED_TUNNEL_TAG_EVIDENCE=0``) — a real KDFW
        underpass carries the tag evidence R4 asks for.
        """
        layout, nodes_m, way_ids = _mapped_bore_scene([_CROSS_1, _CROSS_2])
        ways, gaps = _split(layout, nodes_m, way_ids,
                            {"highway": "primary"},
                            low_gap_m=_LOW_CONNECTOR_MAX_GAP_M)
        assert gaps == []
        assert _bores(ways) == []
        assert len(ways) == 1
        assert _piece_extent(ways[0], nodes_m) == (0.0, _WAY_LENGTH_M)

        # THE PRE-RULING LAW, under its gate: the original assertions.
        monkeypatch.setattr(bridges, "IMPLIED_TUNNEL_TAG_EVIDENCE", False)
        layout, nodes_m, way_ids = _mapped_bore_scene([_CROSS_1, _CROSS_2])
        ways, gaps = _split(layout, nodes_m, way_ids,
                            {"highway": "primary"},
                            low_gap_m=_LOW_CONNECTOR_MAX_GAP_M)
        assert len(gaps) == 1
        gap_line, corridor_width_m = gaps[0]
        assert gap_line.length == pytest.approx(
            _CROSS_2[0] - _CROSS_1[1], abs=0.01)      # 86 m
        assert corridor_width_m > 0.0
        # The two crossings merged across the gap into one bore.
        bores = _bores(ways)
        assert len(bores) == 1
        start, end = _piece_extent(bores[0], nodes_m)
        assert start == pytest.approx(_CROSS_1[0] - _EDGE_MARGIN_M, abs=0.01)
        assert end == pytest.approx(_CROSS_2[1] + _EDGE_MARGIN_M, abs=0.01)


# ──────────────────────────────────────────────────────────────────
# C-3 — corridor cutback clearance
# ──────────────────────────────────────────────────────────────────
class TestLowCorridorCutbackClearance:
    """C-3 (ruling 3): the low-corridor cutback clears the same 0.6 m as
    every other tunnel emitter, so a corridor corner can never land in a
    solved pavement vertex's 0.5 m intern bucket."""

    def test_corridor_cut_back_by_graze_clearance(self) -> None:
        layout = SimpleNamespace(shapes=[])
        corridor = box(0.0, 0.0, 100.0, 40.0)
        gate = box(60.0, -10.0, 200.0, 50.0)
        exclusion_zones: list = []
        n_rects = bridges._emit_low_corridor_connectors(
            layout, [corridor], exclusion_zones, gate,
            lambda x, y: 100.0, lambda x, y: 100.0,
            tunnel_depth_m=8.0, wall_gap_m=0.6,
            retaining_wall_width_m=1.0)
        assert n_rects == 1
        connectors = [s for s in layout.shapes
                      if s.ref == "tunnel_low_connector"]
        assert len(connectors) == 1
        clearance = connectors[0].polygon.distance(gate)
        assert clearance >= bridges._TUNNEL_GRAZE_CLEARANCE_M - 1e-6
        # The point of the ruling: strictly outside the intern bucket.
        assert clearance > SHARED_VERTEX_TOL_M


# ──────────────────────────────────────────────────────────────────
# C-4 — the ramp wins over pavement
# ──────────────────────────────────────────────────────────────────
_RAMP_BOX = box(40.0, -20.0, 60.0, 120.0)       # 20 x 140 m


def _finalize(layout, gate_union, pre_emit_shape_ids, ramp_way_ids=None):
    return bridges._finalize_tunnel_emission(
        layout, [], 0.5, gate_union, pre_emit_shape_ids, 1,
        ramp_way_ids=ramp_way_ids)


def _ramp_shape(polygon=_RAMP_BOX, altitude=92.0) -> BuiltShape:
    ring = len(polygon.exterior.coords)
    return BuiltShape(polygon=polygon, role=ROLE_TUNNEL_RAMP,
                      ref="tunnel_ramp",
                      node_altitudes=[altitude] * ring)


class TestRampWinsOverPavement:
    """C-4 (ruling 4): the ramp is emitted whole and the pavement it
    surfaces through is CUT (the R13 helper), except over the runway
    family, where the ramp is dropped loudly instead."""

    def test_ramp_emitted_whole_and_pavement_cut(self) -> None:
        """71 % of the ramp lies on a service junction: pre-ruling the
        ramp dropped whole; now the ramp survives intact and the
        pavement is cut by its footprint."""
        pavement = BuiltShape(polygon=box(0.0, 0.0, 100.0, 100.0),
                              role=ROLE_SERVICE_JUNCTION,
                              node_altitudes=[100.0] * 5)
        ramp = _ramp_shape()
        layout = SimpleNamespace(shapes=[pavement, ramp])
        pre_emit = {id(pavement)}
        _finalize(layout, pavement.polygon, pre_emit)

        ramps = [s for s in layout.shapes if s.ref == "tunnel_ramp"]
        assert len(ramps) == 1
        assert ramps[0] is ramp
        assert ramps[0].polygon.area == pytest.approx(_RAMP_BOX.area)

        pav = [s for s in layout.shapes if s.role == ROLE_SERVICE_JUNCTION]
        assert len(pav) == 2        # cut into the two sides of the ramp
        cut_area = sum(s.polygon.area for s in pav)
        expected = 100.0 * 100.0 - _RAMP_BOX.intersection(
            pavement.polygon).area
        assert cut_area == pytest.approx(expected, abs=0.01)
        assert cut_area == pytest.approx(8000.0, abs=0.01)
        for piece in pav:
            assert piece.polygon.intersection(ramp.polygon).area \
                == pytest.approx(0.0, abs=1e-6)

    def test_wall_follows_its_ramp_but_is_otherwise_unchanged(self) -> None:
        """A wall over pavement its own ramp REMOVED survives; a wall
        over untouched pavement still drops (behaviour unchanged)."""
        # A service-road strip the ramp swallows: both remainders are
        # under the helper's 5 m2 floor, so the shape goes entirely.
        swallowed = BuiltShape(polygon=box(39.0, 0.0, 61.0, 3.0),
                               role=ROLE_SERVICE_ROAD,
                               node_altitudes=[100.0] * 5)
        untouched = BuiltShape(polygon=box(0.0, 50.0, 10.0, 60.0),
                               role=ROLE_SERVICE_ROAD,
                               node_altitudes=[100.0] * 5)
        wall_on_cut = BuiltShape(polygon=box(39.0, 0.0, 39.9, 3.0),
                                 role=ROLE_RETAINING_WALL,
                                 ref="tunnel_wall",
                                 node_altitudes=[100.0] * 5)
        wall_on_kept = BuiltShape(polygon=box(2.0, 52.0, 4.0, 54.0),
                                  role=ROLE_RETAINING_WALL,
                                  ref="tunnel_wall",
                                  node_altitudes=[100.0] * 5)
        ramp = _ramp_shape()
        layout = SimpleNamespace(
            shapes=[swallowed, untouched, ramp, wall_on_cut, wall_on_kept])
        gate = swallowed.polygon.union(untouched.polygon)
        _finalize(layout, gate, {id(swallowed), id(untouched)})

        roads = [s for s in layout.shapes if s.role == ROLE_SERVICE_ROAD]
        assert [s.polygon.bounds for s in roads] == [untouched.polygon.bounds]
        walls = [s for s in layout.shapes if s.ref == "tunnel_wall"]
        assert wall_on_cut in walls
        assert wall_on_kept not in walls
        assert [s for s in layout.shapes if s.ref == "tunnel_ramp"] == [ramp]

    def test_ramp_over_runway_is_dropped_loudly(self, capsys) -> None:
        """SAFETY FLOOR: a ramp mostly on a runway-family shape is
        dropped, named in the log, and the runway is NOT cut."""
        runway = BuiltShape(polygon=box(0.0, 0.0, 200.0, 50.0),
                            role=ROLE_RUNWAY, ref="09L/27R",
                            node_altitudes=[100.0] * 5)
        ramp = _ramp_shape(polygon=box(90.0, 10.0, 110.0, 40.0))
        layout = SimpleNamespace(shapes=[runway, ramp])
        UI.verbosity = 1
        _finalize(layout, runway.polygon, {id(runway)},
                  ramp_way_ids={id(ramp): "-917"})

        assert [s for s in layout.shapes if s.ref == "tunnel_ramp"] == []
        kept_runways = [s for s in layout.shapes if s.role == ROLE_RUNWAY]
        assert len(kept_runways) == 1
        assert kept_runways[0].polygon.area == pytest.approx(200.0 * 50.0)
        out = capsys.readouterr().out
        assert "-917" in out
        assert "09L/27R" in out
        assert "never cuts a runway-family shape" in out

    def test_runway_family_excluded_from_the_ramp_cut_set(self) -> None:
        """The cut set is R13's minus the runway family — a ramp that
        only grazes a runway still never cuts it."""
        cut_roles = bridges._tunnel_ramp_cut_roles()
        assert not (cut_roles & bridges._RAMP_NEVER_CUT_ROLES)
        assert ROLE_SERVICE_JUNCTION in cut_roles
        assert ROLE_SERVICE_ROAD in cut_roles

        runway = BuiltShape(polygon=box(0.0, 0.0, 200.0, 50.0),
                            role=ROLE_RUNWAY,
                            node_altitudes=[100.0] * 5)
        # 10 % of the ramp on the runway — below the drop fraction.
        ramp = _ramp_shape(polygon=box(90.0, 40.0, 110.0, 140.0))
        layout = SimpleNamespace(shapes=[runway, ramp])
        _finalize(layout, runway.polygon, {id(runway)})

        assert [s for s in layout.shapes if s.ref == "tunnel_ramp"] == [ramp]
        kept_runways = [s for s in layout.shapes if s.role == ROLE_RUNWAY]
        assert len(kept_runways) == 1
        assert kept_runways[0].polygon.area == pytest.approx(200.0 * 50.0)


# ══════════════════════════════════════════════════════════════════════
# THE RAMP-CUT BOUNDARIES ROUND
# spec ``docs/specs/tunnel-ramp-cut-boundaries-spec.md``
# ══════════════════════════════════════════════════════════════════════
#
# One synthetic portal cluster, emitted through the REAL entry points
# (``_emit_portal_cluster`` then ``_finalize_tunnel_emission``) so the
# perimeter wall band, the ramp cut and the pavement-overlap clip are
# exercised in the order production runs them.
_WALL_GAP_M = 0.6
_WALL_WIDTH_M = 1.0
_ANNULUS_M = _WALL_GAP_M + _WALL_WIDTH_M
_APT_ELEV = 100.0
_TUNNEL_DEPTH_M = 8.0


def _portal(walk_pts, way_id="-917", far_dem=104.0, carriage_w=22.0):
    """One ``portal_data`` row: the 8-field prefix ``_emit_portal_cluster``
    slices (never destructure whole — the tuple grew DEM-cut fields)."""
    return (f"n{way_id}", way_id, walk_pts, "primary", _APT_ELEV,
            far_dem, False, carriage_w)


def _emit_cluster(walks, layout, way_ids=None, gate=None, far_dem=104.0):
    """Emit ONE cluster of ``walks`` into ``layout``; returns
    ``(n_emitted, exclusion_zones)``."""
    way_ids = way_ids or [f"-{917 + i}" for i in range(len(walks))]
    nodes_m = {}
    portal_data = []
    for wid, walk in zip(way_ids, walks):
        row = _portal(walk, way_id=wid, far_dem=far_dem)
        nodes_m[row[0]] = walk[0]
        portal_data.append(row)
    exclusion_zones: list = []
    n = bridges._emit_portal_cluster(
        list(range(len(walks))), portal_data, nodes_m, layout,
        exclusion_zones, 22.0, _TUNNEL_DEPTH_M, _WALL_GAP_M,
        _WALL_WIDTH_M, _WALL_WIDTH_M / 2.0, lambda x, y: _APT_ELEV,
        airside_gate_union=gate)
    return n, exclusion_zones


def _refs(layout, ref):
    return [s for s in layout.shapes if getattr(s, "ref", "") == ref]


def _ring_altitudes(shape):
    """``[(vertex, altitude), …]`` for one emitted shape, decoding the
    encoding it actually shipped: explicit ``node_altitudes`` (closed
    ring), the 4-corner sloped rect (ring order 0,3 = high / 1,2 = low —
    the ``_rect_from_axis_extended`` convention), or a flat altitude."""
    ring = list(shape.polygon.exterior.coords)
    if shape.node_altitudes:
        alts = list(shape.node_altitudes)
        return [(ring[i], alts[i])
                for i in range(min(len(ring), len(alts)))]
    if shape.altitude_high is not None and shape.altitude_low is not None:
        corners = ring[:-1] if ring[0] == ring[-1] else ring
        if len(corners) != 4:
            return []
        hi, lo = shape.altitude_high, shape.altitude_low
        return list(zip(corners, [hi, lo, lo, hi]))
    if shape.altitude is not None:
        return [(v, shape.altitude) for v in ring]
    return []


def _shared_corner_spread(shapes):
    """``(n_shared_corners, worst_disagreement_m)`` over every vertex that
    two or more of ``shapes`` both carry."""
    seen: dict = {}
    for idx, shape in enumerate(shapes):
        for vertex, alt in _ring_altitudes(shape):
            key = (round(vertex[0], 6), round(vertex[1], 6))
            seen.setdefault(key, {})[idx] = alt
    shared = [v for v in seen.values() if len(v) > 1]
    worst = max((max(v.values()) - min(v.values()) for v in shared),
                default=0.0)
    return len(shared), worst


class TestClearanceAnnulus:
    """W/G-1 (spec §2): the ruling-4 cut is the WALL BAND's annulus, not
    the bare ramp union — so no pavement vertex survives inside a ramp
    ring's intern bucket, and the band that owns the annulus is not
    dropped as "under pavement"."""

    @staticmethod
    def _scene(clearance_m):
        pavement = BuiltShape(polygon=box(-50.0, -60.0, 200.0, 60.0),
                              role=ROLE_SERVICE_JUNCTION,
                              node_altitudes=[_APT_ELEV] * 5)
        layout = SimpleNamespace(shapes=[pavement])
        walk = [(0.0, 0.0), (40.0, 0.0), (80.0, 0.0),
                (120.0, 0.0), (160.0, 0.0)]
        _n, zones = _emit_cluster([walk], layout, gate=pavement.polygon)
        bridges._finalize_tunnel_emission(
            layout, zones, 0.5, pavement.polygon, {id(pavement)}, 1,
            ramp_way_ids={}, ramp_cut_clearance_m=clearance_m)
        return layout

    def test_no_pavement_vertex_survives_in_a_ramp_rings_intern_bucket(
            self) -> None:
        """THE minting vector, closed geometrically.  Ruling 4 removed the
        0.6 m graze push, so a solved pavement vertex could sit ON a ramp
        ring — one intern bucket, one value, welded across a wall."""
        layout = self._scene(_ANNULUS_M)
        ramps = unary_union([s.polygon for s in _refs(layout, "tunnel_ramp")])
        pavement = [s for s in layout.shapes
                    if s.role == ROLE_SERVICE_JUNCTION]
        assert pavement, "the cut removed the pavement entirely"
        vertices = [v for s in pavement
                    for ring in [s.polygon.exterior, *s.polygon.interiors]
                    for v in ring.coords]
        nearest = min(Point(v).distance(ramps.boundary) for v in vertices)
        assert nearest > SHARED_VERTEX_TOL_M, (
            f"a pavement vertex sits {nearest:.3f} m from a ramp ring — "
            f"inside the {SHARED_VERTEX_TOL_M} m intern bucket, which is "
            f"the cross-boundary value adoption this cut exists to make "
            f"impossible")
        assert nearest >= _ANNULUS_M - 1e-6

    def test_the_bare_ramp_union_cut_is_what_left_them_touching(self) -> None:
        """The control arm: with NO clearance (the parent round's cut) the
        pavement boundary lands exactly ON the ramp ring."""
        layout = self._scene(0.0)
        ramps = unary_union([s.polygon for s in _refs(layout, "tunnel_ramp")])
        pavement = [s for s in layout.shapes
                    if s.role == ROLE_SERVICE_JUNCTION]
        vertices = [v for s in pavement
                    for ring in [s.polygon.exterior, *s.polygon.interiors]
                    for v in ring.coords]
        nearest = min(Point(v).distance(ramps.boundary) for v in vertices)
        assert nearest < SHARED_VERTEX_TOL_M

    def test_the_perimeter_band_owns_the_annulus(self) -> None:
        """The band is judged against the POST-CUT pavement, so it stands
        in the annulus its own ramp's cut cleared — instead of being
        dropped as a piece "under pavement" (which is what happens with
        the bare-union cut, the control below)."""
        layout = self._scene(_ANNULUS_M)
        walls = _refs(layout, "tunnel_wall")
        assert walls, "the perimeter wall band was dropped over its own cut"
        ramps = unary_union([s.polygon for s in _refs(layout, "tunnel_ramp")])
        pavement = unary_union(
            [s.polygon for s in layout.shapes
             if s.role == ROLE_SERVICE_JUNCTION])
        for wall in walls:
            assert wall.polygon.intersection(pavement).area \
                == pytest.approx(0.0, abs=1e-6), (
                    "the band overlaps surviving pavement — the cut is "
                    "narrower than the band")
            assert wall.polygon.intersection(ramps).area \
                == pytest.approx(0.0, abs=1e-6)
        # Every cut edge reads pavement | wall | ramp: the band sits
        # between them, touching neither's surface.
        assert unary_union([w.polygon for w in walls]).area > 100.0

    def test_without_the_annulus_the_band_is_dropped_as_under_pavement(
            self) -> None:
        assert _refs(self._scene(0.0), "tunnel_wall") == []


class TestRampInternalCornerAgreement:
    """W/G-1 (spec §2, third bullet): adjacent ramp pieces of ONE portal
    walk — chain quads, the fork throat, the fork arms — must present ONE
    value at each shared cross-edge node, BEFORE ``to_osm`` shape-order
    precedence picks a winner.  OTHH ways -11758/-11759 disagreed by
    0.96 m; on this scene the pre-fix disagreement is 3.39 m."""

    # A cluster whose walk BENDS (so the effective-space grade clamp
    # fires: the miter-shortened inner edges shrink Σeffective below the
    # centreline sum) and then FORKS (so the throat and both arms hang
    # off the bore's realized top).
    _SHARED = [(0.0, 0.0), (20.0, 0.0), (40.0, 6.0),
               (60.0, 14.0), (80.0, 22.0)]
    _ARM_A = _SHARED + [(110.0, 40.0), (150.0, 70.0)]
    _ARM_B = _SHARED + [(110.0, 20.0), (150.0, 0.0)]
    _FAR_DEM = 104.0

    def _emit(self):
        layout = SimpleNamespace(shapes=[])
        _emit_cluster([self._ARM_A, self._ARM_B], layout,
                      far_dem=self._FAR_DEM)
        return layout

    def test_the_scene_actually_forces_the_grade_clamp(self) -> None:
        """Guard: without the clamp firing this scene proves nothing.  The
        walk's nominal grade is far over the ramp law, so ``_emit_chain``
        MUST clamp the bore's top below the planned handoff."""
        walk_len = sum(
            Point(a).distance(Point(b))
            for a, b in zip(self._ARM_A, self._ARM_A[1:]))
        nominal = ((self._FAR_DEM - (_APT_ELEV - _TUNNEL_DEPTH_M))
                   / walk_len)
        assert nominal > float(_CFG.TUNNEL_RAMP_MAX_GRADE)
        ramps = _refs(self._emit(), "tunnel_ramp")
        assert len(ramps) >= 4, "the cluster did not fork"

    def test_shared_cross_edge_nodes_carry_one_value(self) -> None:
        """REWRITTEN against §5-SUPPLEMENT item 1 (spec ``cd25f56c``;
        canonical-mouth ruling 2026-08-30 "ONE ramp surface descending
        the corridor centre"; accepted RULINGS 2026-08-31i).  The old
        bar (``n_shared >= 8``) counted the quad chain's INTERNAL
        cross-edges — the very seams the supplement dissolved by
        emitting each contiguous run as ONE surface.  The shared
        corners that remain are exactly the three real handoffs (bore
        surface → throat, throat → each arm, 2 corners each), and the
        agreement law is unchanged: ONE value per shared node, before
        ``to_osm`` shape-order precedence can pick a winner."""
        ramps = _refs(self._emit(), "tunnel_ramp")
        n_shared, worst = _shared_corner_spread(ramps)
        assert n_shared >= 6, (
            f"only {n_shared} shared corners — the scene stopped "
            f"exercising the bore/throat/arm handoff (three handoffs x "
            f"two corners each)")
        assert worst <= 0.01, (
            f"adjacent ramp pieces disagree by {worst:.3f} m at a shared "
            f"cross-edge node; ``to_osm`` shape order would decide which "
            f"value the node keeps and mint the difference as a defect "
            f"inside the loser")

    def test_the_throat_landing_joins_both_the_bore_and_the_arms(
            self) -> None:
        """The specific handoff: the throat's flat landing IS the bore's
        realized top AND both arms' start.

        REWRITTEN against §5-SUPPLEMENT item 1 (spec ``cd25f56c``;
        canonical-mouth ruling 2026-08-30; accepted RULINGS
        2026-08-31i): the bore run and the arms are no longer chains of
        sloped ``altitude_high``/``altitude_low`` quads but ONE
        node_altitudes surface per contiguous run, so the seating is
        read from the surfaces' own per-vertex values — the bore
        surface's realized top and each arm's lowest station."""
        ramps = _refs(self._emit(), "tunnel_ramp")
        throats = [s for s in ramps
                   if s.node_altitudes and len(set(s.node_altitudes)) == 1]
        assert len(throats) == 1
        landing = throats[0].node_altitudes[0]
        sloped = [s for s in ramps
                  if s.node_altitudes and len(set(s.node_altitudes)) > 1]
        assert len(sloped) >= 3, (
            "the cluster lost its bore surface or an arm — nothing "
            "left to hand off through the throat")
        assert landing in {max(s.node_altitudes) for s in sloped}, (
            "the throat is not seated on the elevation the bore reached")
        assert sum(1 for s in sloped
                   if min(s.node_altitudes) == landing) >= 2, (
            "the arms did not start from the throat's landing")

    def test_the_flat_quad_encoding_cannot_disagree_beyond_the_floor(
            self) -> None:
        """A quad shipped FLAT offers the average at both cross-edges, so
        it disagrees with each neighbour by half the threshold.  The
        threshold is the 0.01 m materiality floor doubled."""
        assert bridges._TUNNEL_RAMP_FLAT_QUAD_M / 2.0 <= 0.01


class TestRampNeverCrossesABuildingPadEdge:
    """B-1 (owner ruling 2026-08-07, spec §4): "A ramp should never cross
    a building pad edge.  Either the tunnel is under the building and the
    ramp stops at the building edge, or the building is mis-identified and
    shouldn't be there in the first place." """

    _WALK = [(0.0, 0.0), (40.0, 0.0), (80.0, 0.0),
             (120.0, 0.0), (160.0, 0.0)]
    _PAD_BOX = box(90.0, -40.0, 200.0, 40.0)

    @staticmethod
    def _scene(pad_box):
        pad = BuiltShape(polygon=pad_box, role=ROLE_BUILDING,
                         node_altitudes=[_APT_ELEV] * 5)
        layout = SimpleNamespace(shapes=[pad])
        _n, zones = _emit_cluster(
            [TestRampNeverCrossesABuildingPadEdge._WALK], layout)
        return layout, pad, zones

    def test_the_ramp_stops_at_the_pad_edge_and_the_pad_is_untouched(
            self) -> None:
        layout, pad, _z = self._scene(self._PAD_BOX)
        ramps = _refs(layout, "tunnel_ramp")
        assert ramps, "every ramp piece was dropped"
        for ramp in ramps:
            assert ramp.polygon.intersection(pad.polygon).area \
                == pytest.approx(0.0, abs=1e-6), (
                    "a tunnel ramp crosses a building pad edge")
            assert ramp.polygon.distance(pad.polygon) \
                >= bridges._TUNNEL_GRAZE_CLEARANCE_M - 1e-6, (
                    "the ramp stops at the pad edge without the "
                    "vertex-bucket clearance every other tunnel piece keeps")
        # NEITHER CUT NOR BURIED: the pad ring is exactly as it was.
        assert layout.shapes[0] is pad
        assert pad.polygon.equals(self._PAD_BOX)
        assert pad.node_altitudes == [_APT_ELEV] * 5

    def test_a_ramp_merely_TOUCHING_the_pad_still_gets_the_clearance(
            self) -> None:
        """v3 amendment (2026-08-09): B-1 used to trigger on ``overlap
        area > 0``, so a ramp whose corner sits EXACTLY on the pad ring
        (zero-area tangency) escaped the 0.6 m standoff, landed inside
        that ring vertex's ``SHARED_VERTEX_TOL_M`` intern bucket, and
        ``to_osm``'s authority precedence welded its below-grade profile
        onto the building (measured at OTHH: ramp -11489 dragging
        building1's node -24372 to −4.29; the ruling-4 specimen was the
        same pad at −3.74).  The trigger is now intersection with the
        pad BUFFERED by the clearance, so tangency is clipped too."""
        # Where does the UNCLIPPED ramp end?  Put the pad's edge there.
        free = SimpleNamespace(shapes=[])
        _emit_cluster([self._WALK], free)
        edge = max(r.polygon.bounds[2] for r in _refs(free, "tunnel_ramp"))
        tangent_pad = box(edge, -40.0, edge + 110.0, 40.0)
        layout, pad, _z = self._scene(tangent_pad)
        ramps = _refs(layout, "tunnel_ramp")
        assert ramps, "every ramp piece was dropped"
        for ramp in ramps:
            assert ramp.polygon.intersection(pad.polygon).area \
                == pytest.approx(0.0, abs=1e-6)
            assert ramp.polygon.distance(pad.polygon) \
                >= bridges._TUNNEL_GRAZE_CLEARANCE_M - 1e-6, (
                    "a TANGENT ramp escaped the vertex-bucket clearance — "
                    "its corner can be interned into the pad ring")
        # The pad itself is still neither cut nor buried.
        assert layout.shapes[0] is pad
        assert pad.polygon.equals(tangent_pad)
        assert pad.node_altitudes == [_APT_ELEV] * 5

    def test_an_OVERLAPPING_ramp_keeps_the_pre_v3_behaviour(self) -> None:
        """The trigger change must not move the overlapping case: the
        ramp is still clipped back to the same standoff it had before."""
        layout, pad, _z = self._scene(self._PAD_BOX)
        ramps = _refs(layout, "tunnel_ramp")
        assert ramps
        assert max(r.polygon.bounds[2] for r in ramps) \
            == pytest.approx(90.0 - bridges._TUNNEL_GRAZE_CLEARANCE_M,
                             abs=0.05)

    def test_a_ramp_wholly_under_the_pad_drops_naming_way_and_pad(
            self, capsys) -> None:
        """The overlap is COVERED BORE, not emitted — and the drop is
        loud, so a mis-identified building is visible as a data-quality
        case instead of a silent hole in the ramp.

        FIXTURE UPDATED for §5-SUPPLEMENT item 1 (spec ``cd25f56c``;
        canonical-mouth ruling 2026-08-30; accepted RULINGS
        2026-08-31i): a contiguous run now emits as ONE surface, so the
        old scene's partly-covered walk no longer produces a chain quad
        wholly under the pad — the one surface is CLIPPED at the pad
        edge instead (the sibling tests pin that).  The drop path B-1
        guards fires when the WHOLE surface lies under the pad, so
        that is the scene here: the pad covers the entire walk."""
        UI.verbosity = 1
        full_pad = box(-30.0, -40.0, 200.0, 40.0)
        layout, pad, zones = self._scene(full_pad)
        out = capsys.readouterr().out
        assert "-917" in out, "the source way is not named in the drop log"
        assert "shapeID 0" in out, "the building pad is not named"
        assert "DROPPED whole" in out
        # Nothing of the open ramp is emitted — the whole run is
        # covered bore — and the walls follow their ramp out.
        assert _refs(layout, "tunnel_ramp") == []
        # The pad itself is neither cut nor buried.
        assert layout.shapes[0] is pad
        assert pad.polygon.equals(full_pad)
        assert pad.node_altitudes == [_APT_ELEV] * 5
        # The exclusion-zone register followed the drop: no stale ramp
        # footprint survives to carve the boundary ribbon under the pad.
        assert [z for z in zones if z.intersects(pad.polygon)] == []
        # …and the partly-covered control scene still names the CLIP.
        _l2, _p2, _z2 = self._scene(self._PAD_BOX)
        out2 = capsys.readouterr().out
        assert "-917" in out2
        assert "clipped" in out2
        assert _refs(_l2, "tunnel_ramp"), (
            "the partly-covered walk should clip, not drop")

    def test_the_clipped_ramp_keeps_its_profile_and_never_stretches_it(
            self) -> None:
        """The clip reuses the graze-clip conversion: every surviving
        vertex holds the altitude the UNCLIPPED piece planned there, so
        the ramp's grade is unchanged and its range only shrinks."""
        no_pad = SimpleNamespace(shapes=[])
        _emit_cluster([self._WALK], no_pad)
        planned = {}
        for shape in _refs(no_pad, "tunnel_ramp"):
            for vertex, alt in _ring_altitudes(shape):
                planned[(round(vertex[0], 3), round(vertex[1], 3))] = alt
        planned_lo = min(planned.values())
        planned_hi = max(planned.values())

        layout, _pad, _z = self._scene(self._PAD_BOX)
        clipped = _refs(layout, "tunnel_ramp")
        values = [a for s in clipped for _v, a in _ring_altitudes(s)]
        assert values
        assert min(values) >= planned_lo - 1e-6
        assert max(values) <= planned_hi + 1e-6, (
            "the clipped ramp stretched its profile over the shorter run")
        # Where the clip kept an ORIGINAL vertex, it kept its value too.
        kept = 0
        for shape in clipped:
            for vertex, alt in _ring_altitudes(shape):
                key = (round(vertex[0], 3), round(vertex[1], 3))
                if key in planned:
                    assert alt == pytest.approx(planned[key], abs=0.01)
                    kept += 1
        assert kept >= 4, "no original vertex survived — nothing was tested"

    def test_buildings_are_neither_in_the_cut_set_nor_the_drop_set(
            self) -> None:
        """Spec §4, first bullet: the runway floor DROPS a ramp, buildings
        CLIP it — so ``ROLE_BUILDING`` belongs to neither register."""
        assert ROLE_BUILDING not in bridges._tunnel_ramp_cut_roles()
        assert ROLE_BUILDING not in bridges._RAMP_NEVER_CUT_ROLES

    def test_the_exclusion_zones_follow_the_clipped_ramp(self) -> None:
        """The ramp footprints are also the boundary-ribbon subtraction's
        input; a stale PRE-clip footprint would carve the ribbon out over
        ground the ramp no longer occupies."""
        layout, pad, zones = self._scene(self._PAD_BOX)
        ramp_zones = [z for z in zones if z.intersects(pad.polygon)]
        # Only the perimeter wall band may still touch the pad (it is
        # clipped off it by the pavement-overlap clip in finalize).
        # The band is ONE ref again — the §T5 foot RETIRED (RULINGS
        # 2026-09-01c) — so ``_WALL_BAND_REFS`` is the register the
        # zone must belong to.
        band = [w for w in layout.shapes
                if getattr(w, "ref", "") in bridges._WALL_BAND_REFS
                and w.polygon is not None and not w.polygon.is_empty]
        for zone in ramp_zones:
            assert any(zone.equals(w.polygon.buffer(0))
                       or zone.intersection(w.polygon).area > 0.5
                       for w in band), (
                "a RAMP exclusion zone still covers the building pad")


# ══════════════════════════════════════════════════════════════════════
# F-1 — A FORK REQUIRES SUSTAINED DIVERGENCE
# spec ``docs/specs/tunnel-fork-sustain-spec.md`` §2
# ══════════════════════════════════════════════════════════════════════
#
# The probe used to fork on the FIRST station whose member spread crossed
# ``cluster_span + _div_margin`` and stop looking, so a momentary wobble
# read as a Y-split.  MEASURED at OTHH's A-site: twin one-way service
# carriageways 9.52 m apart at the portal, drifting 8.3-9.8 m for 150 m,
# crossing the 11.50 m threshold at s ≈ 157.5 m on a 1.2 m relative
# splay — and then converging to 0.00 m, because the two carriageways
# MERGE at a shared end node.  The emitted arms overlapped by 93.89 m²
# and minted 16 cross-arm adoption rows (worst 42.46 % against the 4 %
# ramp cap).


def _cluster_ramps(walks, half_width_m=12.0, far_dem=104.0):
    """Emit ONE cluster from ``walks`` and return its ramp shapes."""
    layout = SimpleNamespace(shapes=[])
    _emit_cluster(walks, layout,
                  way_ids=[f"-{917 + i}" for i in range(len(walks))],
                  far_dem=far_dem)
    return _refs(layout, "tunnel_ramp")


def _throats(ramps):
    """The fan-throat pieces: a ramp carrying ONE flat node_altitudes
    value over a ring wider than a quad — emitted only on the fork path.
    """
    return [s for s in ramps
            if s.node_altitudes and len(set(s.node_altitudes)) == 1
            and len(s.polygon.exterior.coords) > 5]


class TestForkRequiresSustainedDivergence:
    """F-1: a cluster forks only when the divergence HOLDS to the end of
    the probe window.  Both arms of the behaviour are pinned — the
    genuine Y-split must keep forking."""

    # A real Y: one shared stem, then two arms that keep separating.
    _STEM = [(0.0, 0.0), (20.0, 0.0), (40.0, 0.0), (60.0, 0.0)]
    _Y_A = _STEM + [(100.0, 25.0), (150.0, 60.0), (200.0, 100.0)]
    _Y_B = _STEM + [(100.0, -25.0), (150.0, -60.0), (200.0, -100.0)]

    @staticmethod
    def _twin(offset_m):
        """A twin carriageway: ~9.5 m apart at the portal, a mid-run
        splay that crosses the threshold, then a merge to 0 m — the OTHH
        A-site shape."""
        pts = []
        for i in range(0, 241, 10):
            splay = 1.0 + 0.35 * math.sin(i / 240.0 * math.pi)
            taper = max(0.0, 1.0 - max(0.0, (i - 180.0) / 60.0))
            pts.append((float(i), offset_m * splay * taper))
        return pts

    def test_a_genuine_y_split_still_forks(self) -> None:
        """The behaviour F-1 must NOT change: monotone divergence to the
        end of the probe window is a real fork, and still emits the fan
        throat that bridges the bore to the arms."""
        ramps = _cluster_ramps([self._Y_A, self._Y_B])
        assert _throats(ramps), (
            "a genuine Y-split stopped forking — F-1 over-reached")
        # …and the throat still joins both sides (the §2 corner law).
        n_shared, worst = _shared_corner_spread(ramps)
        assert worst <= 0.01

    def test_converging_twin_carriageways_do_not_fork(self) -> None:
        """The defect: a spread that crosses the threshold and then falls
        back is twin-carriageway noise, not a Y-split.  One combined
        surface, no throat, no two arms to intern into each other."""
        ramps = _cluster_ramps([self._twin(4.76), self._twin(-4.76)])
        assert ramps, "the converging-twin cluster emitted nothing"
        assert not _throats(ramps), (
            "converging twin carriageways still forked — the arms will "
            "overlap and adopt each other's values")
        # ONE combined surface: no two ramp pieces may overlap.
        for i, a in enumerate(ramps):
            for b in ramps[i + 1:]:
                assert a.polygon.intersection(b.polygon).area \
                    == pytest.approx(0.0, abs=1e-6), (
                        "two ramp pieces of one combined surface overlap")
        # and it is still ONE value at every shared cross-edge node.
        n_shared, worst = _shared_corner_spread(ramps)
        assert worst <= 0.01

    def test_the_sustain_fraction_is_the_spec_literal(self) -> None:
        """1.0 = "remains above it through the end of the probe window".
        A value below 1.0 admits a fork whose divergence lapses."""
        assert bridges.TUNNEL_FORK_SUSTAIN_FRACTION == 1.0
