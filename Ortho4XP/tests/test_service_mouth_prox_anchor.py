"""PROXIMITY MOUTH ANCHORS — the twins.

OWNER LAW 2026-08-15: *a service road meeting a taxiway (or any airside
pavement) must arrive AT that pavement's elevation — exactly like roads
meeting runways.*  AIRSIDE IS KING: the road conforms; the airside value is
read-only.

THE MEASURED DEFECT (HECA, 187 road<->airside contact sites): the DEM-follow
anchor set in ``apply_service_road_dem_follow`` held only service nodes that
are an EXACT canonical vertex of a non-service ring.  All 127 WELDED sites
step 0.000 m; 34 of the 60 UNWELDED ones step > 0.3 m (max 9.135 m), because
the corridor minter cuts the road body back from aircraft pavement by
``_PAV_CLEAR_TOL_M`` = 1.0 m while conformance welds only within
``SHARED_VERTEX_TOL_M`` = 0.5 m — the abutting road node is anchor-less BY
CONSTRUCTION and grades from whatever anchor it can reach instead of from
the pavement it touches.

The fix anchors any service node within ``_PAV_CLEAR_TOL_M +
SHARED_VERTEX_TOL_M`` (1.5 m, derived — no new number) of an AIRCRAFT-
PAVEMENT ring EDGE, at that edge's INTERPOLATED already-solved elevation at
the node's perpendicular foot, and HOLDS that seat through the projections.

Two clauses come from the attempt-1 measurement (adjudicated 2026-08-15):

* THE CARRIER IS AIRCRAFT PAVEMENT ONLY (``ENCLAVE_AIRSIDE_ROLES``).
  Indexing every non-service ring minted 52 of 141 HECA seats from a
  ``graded_strip`` — the road's own grading product, riding at the road's
  own level, so the seat PINNED the road at the value the law wants
  replaced — and 42 from ``building`` rings, against only 35 from real
  pavement.
* THE SEAT IS HELD.  Soft, it was written over: 35 of 141 survived to emit
  within 0.01 m; 96 were moved (worst 9.069 m) — the free-end tie's own
  measured failure, cured here with the free-end tie's own spelling
  (a ``svc_mouth`` keyset, membership only).

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters (auto_patch/CLAUDE.md, "Import cycle").
import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch import config as CFG                          # noqa: E402
from auto_patch.canonical_points import (                     # noqa: E402
    CanonicalPointRegistry)
from auto_patch.elevation_per_surface.node_space import (     # noqa: E402
    store_of)
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    anchors as ANCH)
from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES         # noqa: E402
from auto_patch.layout import (                               # noqa: E402
    BuiltShape, SHARED_VERTEX_TOL_M)
from auto_patch.pavement.service_roads import (               # noqa: E402
    _PAV_CLEAR_TOL_M)

CAP = CFG.SERVICE_ROAD_MAX_GRADE

# The taxiway's east edge runs y = -10 -> y = +20, rising 0.6 m over its
# 30 m (2 %), so an INTERPOLATED read is distinguishable from a
# nearest-vertex one at every station.
TAXI_Z0, TAXI_Z1 = 100.0, 100.6
TAXI_Y0, TAXI_Y1 = -10.0, 20.0


def _edge_z(y: float) -> float:
    """The taxi edge's own value at station ``y`` — the law's answer."""
    t = (y - TAXI_Y0) / (TAXI_Y1 - TAXI_Y0)
    return TAXI_Z0 + t * (TAXI_Z1 - TAXI_Z0)


class _Layout:
    def __init__(self, shapes):
        self.icao = "TEST"
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = []
        self._slice_service_subsegments = []

    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)


def _abutting_layout(gap_m: float, dem_far: float = 90.0, welded=False,
                     taxi_role: str = "primary_parallel"):
    """A taxiway at x <= 0 and a 200 m service road standing ``gap_m`` clear
    of its east edge — the corridor cut-back's geometry in miniature.

    ``welded=True`` instead splices the road's mouth vertices INTO the taxi
    ring (the state the mouth-join minter reaches), which is the control:
    those nodes are exact-vertex anchors and must be untouched by this fix.
    """
    taxi_ring = [(-30.0, TAXI_Y0), (0.0, TAXI_Y0),
                 (0.0, TAXI_Y1), (-30.0, TAXI_Y1)]
    if welded:
        gap_m = 0.0
        taxi_ring = [(-30.0, TAXI_Y0), (0.0, TAXI_Y0), (0.0, -3.0),
                     (0.0, 3.0), (0.0, TAXI_Y1), (-30.0, TAXI_Y1)]
    taxi = BuiltShape(polygon=Polygon(taxi_ring), role=taxi_role)
    xs = [gap_m + d for d in (0.0, 50.0, 100.0, 150.0, 200.0)]
    road_ring = ([(x, -3.0) for x in xs]
                 + [(x, 3.0) for x in reversed(xs)])
    road = BuiltShape(polygon=Polygon(road_ring), role="service_road")
    road.lateral_cap = None
    layout = _Layout([taxi, road])

    b2i, nodes = {}, []
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            key = layout.canonical_points.get_or_add(float(x), float(y))
            if key not in b2i:
                b2i[key] = len(nodes)
                nodes.append((float(x), float(y)))
    elev = [0.0] * len(nodes)
    dem = [dem_far] * len(nodes)

    def _idx(x, y):
        return b2i[layout.canonical_points.get_or_add(float(x), float(y))]

    # The airside is ALREADY SOLVED — its edge carries the 2 % profile.
    for (x, y) in taxi_ring:
        elev[_idx(x, y)] = _edge_z(y)
    mouth = [_idx(xs[0], -3.0), _idx(xs[0], 3.0)]
    return layout, b2i, elev, dem, nodes, mouth, _idx


def _run(layout, b2i, elev, dem):
    return ANCH.apply_service_road_dem_follow(layout, b2i, elev, dem, CAP)


class TestTheMouthArrivesAtThePavement:
    def test_an_unwelded_mouth_seats_at_the_edges_interpolated_value(self):
        """0.6 m clear of the taxi edge, no shared vertex: the road node
        takes the EDGE's value at its own perpendicular foot — 100.14 /
        100.26, not the ring vertex's 100.0 or 100.6."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        assert elev[mouth[0]] == pytest.approx(_edge_z(-3.0), abs=1e-9)
        assert elev[mouth[1]] == pytest.approx(_edge_z(3.0), abs=1e-9)
        assert set(mouth) <= set(layout._svc_mouth_prox_idx)

    def test_the_step_across_the_seam_is_zero(self):
        """The census's own metric: |road node − interpolated airside| at
        the contact.  It was 8.246 m at the owner's HECA site."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        for i, y in zip(mouth, (-3.0, 3.0)):
            assert abs(elev[i] - _edge_z(y)) < 0.01     # materiality floor

    def test_the_road_ramps_away_within_its_own_cap(self):
        """The anchor feeds the EXISTING reach band: the interior descends
        toward terrain at <= the road cap, never as a cliff."""
        layout, b2i, elev, dem, nodes, _mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        for y in (-3.0, 3.0):
            profile = sorted((nodes[i][0], elev[i])
                             for i in range(len(nodes))
                             if nodes[i][1] == y and nodes[i][0] > 0.0)
            assert len(profile) == 5
            for (xa, za), (xb, zb) in zip(profile, profile[1:]):
                assert abs(zb - za) / (xb - xa) <= CAP + 1e-9
            assert profile[-1][1] < profile[0][1]       # it did descend

    def test_the_airside_value_is_read_only(self):
        """AIRSIDE IS KING: not one taxi node moves."""
        layout, b2i, elev, dem, _n, _m, _idx = _abutting_layout(0.6)
        before = [elev[_idx(x, y)] for (x, y) in
                  ((-30.0, TAXI_Y0), (0.0, TAXI_Y0),
                   (0.0, TAXI_Y1), (-30.0, TAXI_Y1))]
        moved = _run(layout, b2i, elev, dem)
        after = [elev[_idx(x, y)] for (x, y) in
                 ((-30.0, TAXI_Y0), (0.0, TAXI_Y0),
                  (0.0, TAXI_Y1), (-30.0, TAXI_Y1))]
        assert before == after
        assert all(nid not in moved for nid in
                   (_idx(0.0, TAXI_Y0), _idx(0.0, TAXI_Y1)))

    def test_the_mouth_seats_are_reported_as_moved(self):
        moved = None
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        moved = _run(layout, b2i, elev, dem)
        assert set(mouth) <= set(moved)


class TestTheGateAndTheControls:
    def test_a_welded_road_is_byte_identical_to_today(self):
        """The exact-vertex anchor keeps precedence — a road that already
        welds must not shift by a millimetre under the new pass."""
        on = _abutting_layout(0.0, welded=True)
        _run(*on[:4])
        CFG_ON = list(on[2])
        off = _abutting_layout(0.0, welded=True)
        import auto_patch.config as _C
        _prev = _C.SVC_MOUTH_PROX_ANCHOR
        try:
            _C.SVC_MOUTH_PROX_ANCHOR = False
            _run(*off[:4])
        finally:
            _C.SVC_MOUTH_PROX_ANCHOR = _prev
        assert CFG_ON == list(off[2])
        assert not on[0]._svc_mouth_prox_idx

    def test_a_road_beyond_the_tolerance_gets_no_anchor(self):
        """> ``_PAV_CLEAR_TOL_M + SHARED_VERTEX_TOL_M`` is not a contact:
        nothing is anchored and the arm is byte-identical to gate-off."""
        far = _PAV_CLEAR_TOL_M + SHARED_VERTEX_TOL_M + 0.5   # 2.0 m
        on = _abutting_layout(far)
        _run(*on[:4])
        off = _abutting_layout(far)
        import auto_patch.config as _C
        _prev = _C.SVC_MOUTH_PROX_ANCHOR
        try:
            _C.SVC_MOUTH_PROX_ANCHOR = False
            _run(*off[:4])
        finally:
            _C.SVC_MOUTH_PROX_ANCHOR = _prev
        assert not on[0]._svc_mouth_prox_idx
        assert list(on[2]) == list(off[2])

    def test_the_gate_off_restores_the_exact_vertex_only_anchor_set(self):
        on = _abutting_layout(0.6)
        _run(*on[:4])
        off = _abutting_layout(0.6)
        import auto_patch.config as _C
        _prev = _C.SVC_MOUTH_PROX_ANCHOR
        try:
            _C.SVC_MOUTH_PROX_ANCHOR = False
            _run(*off[:4])
        finally:
            _C.SVC_MOUTH_PROX_ANCHOR = _prev
        assert not off[0]._svc_mouth_prox_idx
        # …and gate-off is the MEASURED DEFECT: the mouth is nowhere near
        # the pavement it touches.
        assert abs(off[2][off[5][0]] - _edge_z(-3.0)) > 1.0

    def test_the_tolerance_is_derived_from_the_two_gap_constants(self):
        """No new number: the cut-back that opens the gap plus the weld
        tolerance that fails to close it."""
        assert _PAV_CLEAR_TOL_M + SHARED_VERTEX_TOL_M == pytest.approx(1.5)


class TestTheCarrierIsAircraftPavementOnly:
    """Adjudication 2026-08-15 clause 1 — the seat's authority is the
    owner's law, so only the surfaces that law names may mint one."""

    @pytest.mark.parametrize("role", ("graded_strip", "building",
                                      "boundary", "object_pad", "ols_cut"))
    def test_a_non_pavement_ring_mints_no_seat(self, role):
        """THE MEASURED DEFECT of attempt 1: a ``graded_strip`` is the
        road's OWN grading product at the road's own level, so seating
        the road on it pins the value the law wants replaced (HECA: 52
        of 141 seats, one at d = 0.00 m from strip -13003 facing an
        apron 9 m below).  A building is a stage-B seat, not a surface a
        truck arrives at."""
        assert role not in ENCLAVE_AIRSIDE_ROLES
        on = _abutting_layout(0.6, taxi_role=role)
        _run(*on[:4])
        assert not on[0]._svc_mouth_prox_idx
        off = _abutting_layout(0.6, taxi_role=role)
        import auto_patch.config as _C
        _prev = _C.SVC_MOUTH_PROX_ANCHOR
        try:
            _C.SVC_MOUTH_PROX_ANCHOR = False
            _run(*off[:4])
        finally:
            _C.SVC_MOUTH_PROX_ANCHOR = _prev
        assert list(on[2]) == list(off[2])

    @pytest.mark.parametrize("role", sorted(ENCLAVE_AIRSIDE_ROLES))
    def test_every_aircraft_pavement_role_mints_a_seat(self, role):
        """…and all eight of them do: the road arrives at a runway the
        same way it arrives at a taxiway (the owner's own comparison)."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(
            0.6, taxi_role=role)
        _run(layout, b2i, elev, dem)
        assert set(mouth) <= set(layout._svc_mouth_prox_idx)
        assert elev[mouth[0]] == pytest.approx(_edge_z(-3.0), abs=1e-9)

    def test_the_role_set_is_the_canonical_one(self):
        """Imported, never re-spelled — blast.py's role-literal hazard."""
        from auto_patch import enclaves as ENC
        assert ANCH.__dict__ is not None            # module under test
        assert ENC.ENCLAVE_AIRSIDE_ROLES == ENCLAVE_AIRSIDE_ROLES
        assert "graded_strip" not in ENCLAVE_AIRSIDE_ROLES
        assert "building" not in ENCLAVE_AIRSIDE_ROLES


class TestTheSeatIsHeld:
    """Adjudication 2026-08-15 clause 2 — the free-end tie's spelling,
    for the free-end tie's own measured reason."""

    def test_the_seat_is_minted_as_a_keyset(self):
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        held = store_of(layout).view_keyset("svc_mouth", b2i, len(elev))
        assert held == set(mouth)

    def test_the_seat_survives_a_node_list_rebuild(self):
        """SURVIVING PROJECTION is a node-space property: minted by
        CANONICAL KEY, so the final projection — which rebuilds the node
        list — resolves the same nodes."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        rebuilt = {k: i for i, k in enumerate(sorted(b2i, key=str))}
        held = store_of(layout).view_keyset("svc_mouth", rebuilt,
                                            len(rebuilt))
        assert len(held) == len(mouth)
        assert held == {rebuilt[k] for k in
                        (layout.canonical_points.get_or_add(0.6, y)
                         for y in (-3.0, 3.0))}

    def test_a_projection_holding_the_seat_leaves_it_at_the_pavement(self):
        """…and with that membership the projection cannot write over it
        — the 9.069 m the SOFT seat lost at HECA."""
        from auto_patch.elevation_per_surface.route_profile.one_solve import (
            feasibility_project)
        layout, b2i, elev, dem, nodes, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        edges = []
        for a in range(len(nodes)):
            for b in range(a + 1, len(nodes)):
                d = ((nodes[a][0] - nodes[b][0]) ** 2
                     + (nodes[a][1] - nodes[b][1]) ** 2) ** 0.5
                if 0.0 < d <= 55.0:
                    edges.append((a, b, CAP * d))
        hard = set(layout._svc_mouth_prox_idx)
        feasibility_project(elev, [{"edges": edges}], hard)
        for i, y in zip(mouth, (-3.0, 3.0)):
            assert elev[i] == pytest.approx(_edge_z(y), abs=1e-6)

    def test_no_seats_no_keyset(self):
        """A road clear of pavement mints nothing at all."""
        layout, b2i, elev, dem, _n, _m, _idx = _abutting_layout(2.0)
        _run(layout, b2i, elev, dem)
        assert not store_of(layout).view_keyset("svc_mouth", b2i, len(elev))


class TestTheSeatIsReDerivedAtTheAirsideFinalMoment:
    """The timing adjudication.  The seat was never wrong; WHEN it was
    taken was — the DEM-follow pass runs while the airside surface is
    still moving, and at every failing HECA site the apron travelled
    5-9 m AFTER the seat was taken (which the hold then froze perfectly).
    """

    def test_the_reseat_follows_the_pavement_that_moved(self):
        """THE TWIN THE ROUND TURNS ON: move the airside edge between
        DEM-follow and the final projection, and the seat moves with
        it."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        assert elev[mouth[0]] == pytest.approx(_edge_z(-3.0), abs=1e-9)
        # …every prior projection now runs, and the apron sinks 9 m —
        # the HECA -12519 magnitude exactly.
        for (x, y) in ((0.0, TAXI_Y0), (0.0, TAXI_Y1)):
            elev[_idx(x, y)] -= 9.0
        moved, worst = ANCH.reseat_service_mouths(layout, b2i, elev,
                                                  len(elev))
        assert moved == len(mouth)
        assert worst == pytest.approx(9.0, abs=1e-6)
        for i, y in zip(mouth, (-3.0, 3.0)):
            assert elev[i] == pytest.approx(_edge_z(y) - 9.0, abs=1e-9)

    def test_it_is_the_INTERPOLATED_current_value_not_the_old_one(self):
        """The recipe is the foot, not the value: tilt the edge and the
        seat takes the new value AT ITS OWN STATION."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        elev[_idx(0.0, TAXI_Y1)] += 3.0            # steepen the edge
        ANCH.reseat_service_mouths(layout, b2i, elev, len(elev))
        for y, i in zip((-3.0, 3.0), mouth):
            t = (y - TAXI_Y0) / (TAXI_Y1 - TAXI_Y0)
            assert elev[i] == pytest.approx(_edge_z(y) + 3.0 * t, abs=1e-9)

    def test_a_stationary_pavement_reseats_nothing(self):
        """No move, no write — the pass is a lookup, not a re-solve."""
        layout, b2i, elev, dem, _n, _m, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        before = list(elev)
        moved, worst = ANCH.reseat_service_mouths(layout, b2i, elev,
                                                  len(elev))
        assert (moved, worst) == (0, 0.0)
        assert list(elev) == before

    def test_it_reads_the_endpoints_UNCROWNED(self):
        """A runway partner's crown is a designed sub-cap offset, not
        part of the value a truck arrives at — the ``elev - crown`` /
        ``+ crown`` spelling the final projection already uses."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(
            0.6, taxi_role="runway")
        _run(layout, b2i, elev, dem)
        crown = {_idx(0.0, TAXI_Y0): 0.4, _idx(0.0, TAXI_Y1): 0.4}
        for i, c in crown.items():
            elev[i] += c                            # into the z' frame
        moved, _w = ANCH.reseat_service_mouths(layout, b2i, elev,
                                               len(elev), crown_of=crown)
        assert moved == 0                           # the crown moved nothing
        for i, y in zip(mouth, (-3.0, 3.0)):
            assert elev[i] == pytest.approx(_edge_z(y), abs=1e-9)

    def test_the_recipe_survives_a_node_list_rebuild(self):
        """The final projection rebuilds the node list, so the recipe —
        like the keyset beside it — is carried by CANONICAL KEY."""
        layout, b2i, elev, dem, _n, mouth, _idx = _abutting_layout(0.6)
        _run(layout, b2i, elev, dem)
        order = sorted(b2i, key=str)
        rebuilt = {k: i for i, k in enumerate(order)}
        re_elev = [0.0] * len(order)
        for k, i in b2i.items():
            re_elev[rebuilt[k]] = elev[i]
        for (x, y) in ((0.0, TAXI_Y0), (0.0, TAXI_Y1)):
            re_elev[rebuilt[layout.canonical_points.get_or_add(x, y)]] -= 5.0
        moved, worst = ANCH.reseat_service_mouths(layout, rebuilt, re_elev,
                                                  len(re_elev))
        assert moved == len(mouth)
        for y in (-3.0, 3.0):
            j = rebuilt[layout.canonical_points.get_or_add(0.6, y)]
            assert re_elev[j] == pytest.approx(_edge_z(y) - 5.0, abs=1e-9)

    def test_no_seats_is_a_no_op(self):
        layout, b2i, elev, dem, _n, _m, _idx = _abutting_layout(2.0)
        _run(layout, b2i, elev, dem)
        assert ANCH.reseat_service_mouths(layout, b2i, elev,
                                          len(elev)) == (0, 0.0)
