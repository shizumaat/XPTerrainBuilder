"""Twins for THE FABRIC MODEL Phase-A gate (``O4_FABRIC_SPARSE``).

Charter: owner RULINGS 2026-08-08 "THE FABRIC MODEL";
``docs/specs/fabric-model-spec.md`` Phase A.

Two things must be true and are asserted here:

1. **INERTNESS** — with the gate off (the default) nothing arms, every
   predicate is False, the thinning pass is a no-op, and every hook the
   gate touches behaves exactly as before.  This is the twin the spec's
   "Phase A is gated and in-lane; production emission is untouched"
   guard rests on; the byte-identity of a whole battery patch is proven
   separately by the lane's control build.
2. **THE MECHANISM** — with the gate on inside a declared cluster, a
   ring keeps its LAW vertices (welds, direction changes, spine
   stations) and loses the rest, and the emit decimator's own chord/curve
   tolerances are the ones used.
"""

import math
import os

import pytest
from shapely.geometry import Polygon

from auto_patch import fabric_sparse as FS
from auto_patch import emit_decimate as ED
from auto_patch.layout import BuiltShape, PavementLayout, SHARED_VERTEX_TOL_M


# ── helpers ─────────────────────────────────────────────────────────────
def _layout(shapes, anchor=(30.1089375, 31.434664815)):
    lay = PavementLayout(icao="TEST", anchor=anchor)
    lay.shapes = list(shapes)
    return lay


def _rect(x0, y0, x1, y1, role="apron", stations=0):
    """Axis-aligned rect, optionally with ``stations`` collinear vertices
    inserted along the bottom edge (the generic stationing this model
    retires — every one of them is exactly on the chord)."""
    bottom = [(x0, y0)]
    for k in range(1, stations + 1):
        bottom.append((x0 + (x1 - x0) * k / (stations + 1), y0))
    ring = bottom + [(x1, y0), (x1, y1), (x0, y1)]
    return BuiltShape(polygon=Polygon(ring), role=role)


@pytest.fixture(autouse=True)
def _inert_between_tests():
    FS.disarm()
    yield
    FS.disarm()


# ── 1. INERTNESS ────────────────────────────────────────────────────────
def test_gate_off_arms_nothing(monkeypatch):
    monkeypatch.delenv("O4_FABRIC_SPARSE", raising=False)
    s = _rect(-100.0, -100.0, 100.0, 100.0, stations=9)
    lay = _layout([s])
    assert FS.arm(lay, "HECA") == 0
    assert FS.is_sparse(s) is False
    assert FS.sparse_shapes(lay) == []
    before = list(s.polygon.exterior.coords)
    assert FS.thin_rings(lay, "HECA") == 0
    assert list(s.polygon.exterior.coords) == before
    assert FS.report() == {}


def test_gate_off_explicit_zero_is_also_inert(monkeypatch):
    monkeypatch.setenv("O4_FABRIC_SPARSE", "0")
    s = _rect(-100.0, -100.0, 100.0, 100.0, stations=9)
    lay = _layout([s])
    assert FS.arm(lay, "HECA") == 0
    assert FS.is_sparse(s) is False


def test_gate_on_but_no_declared_cluster_is_inert(monkeypatch):
    """An airport with no Phase-A cluster is untouched even gate-on —
    the proof pair is the whole scope of Phase A."""
    monkeypatch.setenv("O4_FABRIC_SPARSE", "1")
    s = _rect(-100.0, -100.0, 100.0, 100.0, stations=9)
    lay = _layout([s])
    assert FS.arm(lay, "SPJC") == 0
    assert FS.is_sparse(s) is False
    assert FS.thin_rings(lay, "SPJC") == 0


def test_densify_long_edges_untouched_when_inert(monkeypatch):
    """The 60 m stationing pass keeps stationing when the gate is off."""
    monkeypatch.delenv("O4_FABRIC_SPARSE", raising=False)
    from auto_patch.conformance import densify_long_edges
    s = _rect(0.0, 0.0, 500.0, 100.0)
    lay = _layout([s])
    n = densify_long_edges(lay, {"apron"}, 60.0)
    assert n > 0, "gate-off densify must still station over-long edges"


def test_span_ok_default_is_the_house_cap():
    """``max_chord=None`` IS ``MAX_CHORD_M`` — every pre-existing caller
    of the extended helper is unchanged."""
    ring = [(0.0, 0.0), (ED.MAX_CHORD_M / 2.0, 0.0),
            (ED.MAX_CHORD_M * 2.0, 0.0), (ED.MAX_CHORD_M * 2.0, 50.0),
            (0.0, 50.0)]
    n = len(ring)
    assert ED._span_ok(ring, None, 0, 2, n, 1.0) is False          # capped
    assert ED._span_ok(ring, None, 0, 2, n, 1.0,
                       max_chord=ED.MAX_CHORD_M) is False
    assert ED._span_ok(ring, None, 0, 2, n, 1.0,
                       max_chord=float("inf")) is True


def test_ring_keep_set_default_matches_explicit_house_cap():
    ring = [(0.0, 0.0)]
    for k in range(1, 40):
        ring.append((k * 10.0, 0.0))
    ring += [(400.0, 60.0), (200.0, 60.0), (0.0, 60.0)]
    a = ED._ring_keep_set(ring, None, 1.0)
    b = ED._ring_keep_set(ring, None, 1.0, max_chord=ED.MAX_CHORD_M)
    assert a == b
    c = ED._ring_keep_set(ring, None, 1.0, max_chord=float("inf"))
    assert len(c) < len(a), ("lifting the chord cap must drop the "
                             "stationing the cap was holding")


# ── 2. THE MECHANISM ────────────────────────────────────────────────────
def _armed_heca_layout(monkeypatch, extra=()):
    """A layout whose apron CONTAINS the declared HECA seed point."""
    monkeypatch.setenv("O4_FABRIC_SPARSE", "1")
    anchor = (30.1089375, 31.434664815)
    lay = PavementLayout(icao="HECA", anchor=anchor)
    seed_lat, seed_lon = FS._PHASE_A_SEEDS["HECA"]["points"][0]
    sx, sy = lay.ll_to_m(seed_lat, seed_lon)
    apron = _rect(sx - 400.0, sy - 400.0, sx + 400.0, sy + 400.0,
                  stations=19)
    lay.shapes = [apron] + list(extra)
    return lay, apron, (sx, sy)


def test_arm_selects_the_seeded_apron(monkeypatch):
    lay, apron, _ = _armed_heca_layout(monkeypatch)
    assert FS.arm(lay, "HECA") == 1
    assert FS.is_sparse(apron) is True
    assert FS.report()["cluster_shapes"] == 1


def test_arm_takes_one_hop_of_welded_neighbours(monkeypatch):
    """"the apron + its welded neighbors + fronting pads" — a shape
    sharing a vertex joins; a shape sharing none does not."""
    lay, apron, (sx, sy) = _armed_heca_layout(monkeypatch)
    corner = (sx + 400.0, sy - 400.0)
    welded = BuiltShape(
        polygon=Polygon([corner, (corner[0] + 50.0, corner[1]),
                         (corner[0] + 50.0, corner[1] + 50.0),
                         (corner[0], corner[1] + 50.0)]),
        role="building")
    far = BuiltShape(
        polygon=Polygon([(sx + 5000.0, sy), (sx + 5050.0, sy),
                         (sx + 5050.0, sy + 50.0), (sx + 5000.0, sy + 50.0)]),
        role="apron")
    lay.shapes = [apron, welded, far]
    assert FS.arm(lay, "HECA") == 2
    assert FS.is_sparse(apron) is True
    assert FS.is_sparse(welded) is True
    assert FS.is_sparse(far) is False


def test_thin_drops_stationing_and_keeps_law_vertices(monkeypatch):
    """The proof-pair mechanism on a hand-built scene: collinear
    stationing goes, corners stay, and a welded neighbour's vertex is
    held even though it sits exactly on the chord."""
    lay, apron, (sx, sy) = _armed_heca_layout(monkeypatch)
    # a pad welded to a STATIONING vertex on the apron's bottom edge
    ring = list(apron.polygon.exterior.coords)[:-1]
    weld_xy = ring[3]
    assert abs(weld_xy[1] - (sy - 400.0)) < 1e-9        # on the bottom edge
    pad = BuiltShape(
        polygon=Polygon([weld_xy, (weld_xy[0] + 30.0, weld_xy[1]),
                         (weld_xy[0] + 30.0, weld_xy[1] - 30.0),
                         (weld_xy[0], weld_xy[1] - 30.0)]),
        role="building")
    lay.shapes = [apron, pad]
    assert FS.arm(lay, "HECA") >= 1
    before = len(list(apron.polygon.exterior.coords)) - 1
    removed = FS.thin_rings(lay, "HECA")
    after_ring = list(apron.polygon.exterior.coords)[:-1]
    assert removed > 0
    assert len(after_ring) == before - removed
    # the four true corners survive
    for c in [(sx - 400.0, sy - 400.0), (sx + 400.0, sy - 400.0),
              (sx + 400.0, sy + 400.0), (sx - 400.0, sy + 400.0)]:
        assert any(math.hypot(p[0] - c[0], p[1] - c[1]) < 1e-6
                   for p in after_ring), f"corner {c} was dropped"
    # the WELD survives, though it is collinear
    assert any(math.hypot(p[0] - weld_xy[0], p[1] - weld_xy[1]) < 1e-6
               for p in after_ring), "a welded vertex was dropped"
    # …and the pad is untouched (buildings are never thinned)
    assert len(list(pad.polygon.exterior.coords)) == 5


def test_thin_preserves_conformance_by_construction(monkeypatch):
    """Nothing a NEIGHBOUR references may be removed — that is what
    makes the thinning T-vertex-free without a repair pass."""
    lay, apron, (sx, sy) = _armed_heca_layout(monkeypatch)
    ring = list(apron.polygon.exterior.coords)[:-1]
    neighbours = []
    for p in ring[1:5]:
        neighbours.append(BuiltShape(
            polygon=Polygon([p, (p[0] + 5.0, p[1]),
                             (p[0] + 5.0, p[1] - 5.0), (p[0], p[1] - 5.0)]),
            role="building"))
    lay.shapes = [apron] + neighbours
    FS.arm(lay, "HECA")
    FS.thin_rings(lay, "HECA")
    kept = {(round(x, 6), round(y, 6))
            for (x, y) in list(apron.polygon.exterior.coords)}
    for nb in neighbours:
        for (x, y) in nb.polygon.exterior.coords:
            k = (round(x, 6), round(y, 6))
            if k in {(round(p[0], 6), round(p[1], 6)) for p in ring}:
                assert k in kept, "a shared vertex was thinned away"


def test_thin_holds_the_degeneracy_floor(monkeypatch):
    """A ring may never fall below four open vertices."""
    lay, apron, (sx, sy) = _armed_heca_layout(monkeypatch)
    lay.shapes = [apron]
    FS.arm(lay, "HECA")
    FS.thin_rings(lay, "HECA")
    assert len(list(apron.polygon.exterior.coords)) - 1 >= 4


def test_thin_carries_node_altitudes_by_index(monkeypatch):
    lay, apron, (sx, sy) = _armed_heca_layout(monkeypatch)
    ring = list(apron.polygon.exterior.coords)[:-1]
    apron.node_altitudes = [100.0 + i for i in range(len(ring))] + [100.0]
    lay.shapes = [apron]
    FS.arm(lay, "HECA")
    FS.thin_rings(lay, "HECA")
    out_ring = list(apron.polygon.exterior.coords)[:-1]
    assert apron.node_altitudes is not None
    assert len(apron.node_altitudes) == len(out_ring) + 1
    # every surviving vertex kept ITS OWN altitude
    for i, p in enumerate(out_ring):
        j = next(k for k, q in enumerate(ring)
                 if math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-9)
        assert apron.node_altitudes[i] == pytest.approx(100.0 + j)


def test_adjacent_ground_declines_cluster_hosts(monkeypatch):
    """"Unregulated ground: NOTHING — the drape is the feather."  The
    band emitter must not see a cluster shape as a host."""
    monkeypatch.setenv("O4_FABRIC_SPARSE", "1")
    lay, apron, _ = _armed_heca_layout(monkeypatch)
    lay.shapes = [apron]
    FS.arm(lay, "HECA")
    from auto_patch import adjacent_ground as AG
    n = AG.emit_adjacent_ground_bands(lay, None, 30, 31)
    assert n == 0
    assert getattr(lay, "adjacent_ground_presolve", None) in (None, [])


def test_spine_stations_are_force_kept(monkeypatch):
    """The owner's rider — "as long as we keep adequate nodes on spines
    and at curves" — is a FORCED keep, taken from the published axis
    export, not a new spacing constant."""
    lay, apron, (sx, sy) = _armed_heca_layout(monkeypatch)
    lay.shapes = [apron]
    FS.arm(lay, "HECA")
    ring = list(apron.polygon.exterior.coords)[:-1]
    station = ring[5]
    fake_line = [(station[0] - 1.0, station[1]),
                 (station[0] + 1.0, station[1])]
    monkeypatch.setattr(FS, "_spine_lines",
                        lambda _lay: __import__("shapely.geometry",
                                                fromlist=["LineString"])
                        .LineString(fake_line))
    FS.thin_rings(lay, "HECA")
    kept = list(apron.polygon.exterior.coords)
    assert any(math.hypot(p[0] - station[0], p[1] - station[1]) < 1e-6
               for p in kept), "a spine station was thinned away"
    assert SHARED_VERTEX_TOL_M == 0.5     # the tolerance used, unchanged
