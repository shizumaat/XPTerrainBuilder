"""THE TUNNEL-CORRIDOR EXCLUSION from the unified node book.

Spec: ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md``
(owner-ordered fix, 2026-08-25).  Owner law it rests on:
``docs/RULINGS.md`` 2026-08-11 "Roads serve tunnels — the paved area IS
the corridor" (R14-1, the claim these twins reuse) and 2026-08-07's
tunnel-portal fidelity rulings.

WHAT WENT WRONG, and why the fix is SCOPE not REVERT.  ``cce9da6f`` put
``service_road`` + ``service_junction`` into ``_CHORD_LIMIT_ROLES``, so
the road family shares ONE node key space with ``groundside_pavement``
in the finalize-stage Lipschitz clamp — and at a weld the road's value
wins (authority precedence).  At OTHH's site-1 bore the descending
tunnel FLOOR is a ``groundside_pavement`` ring: it gained 17 shared
nodes across six road rings, took ``tunnel_road`` bench values
(+2.28/+2.96 against a −1.1 m floor — a 3.3 m mid-ramp step), and 9 of
the bore's 10 ``authority_retreat_wall`` faces stopped being emitted.
The limiter joined the roles for a reason, so the exemption axis moves
from ROLE (``tunnel_ramp``, which this bore's floor is not) to
AUTHORITY: a ring inside R14-1's OWN open-cut claim belongs to the
portal walk, whatever its role.

The four twins the spec names:

(a) a groundside ring inside a tunnel claim welded to a road ring —
    exclusion ON, the ring's below-grade values survive the clamp and no
    shared key is minted; OFF reproduces the capture;
(b) a road ring OUTSIDE any claim still takes the limiter's precedence
    (the ``cce9da6f`` purpose, unregressed);
(c) retreat-wall derivation: with the restored ramp the retreat faces
    emit — and with the capture they do not (spec §3);
(d) flag off → the pre-fix result, exactly.
"""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Polygon

from auto_patch import config as cfg
from auto_patch import groundside as gs
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import (BuiltShape, PavementLayout,
                               ROLE_GROUNDSIDE_PAVEMENT,
                               ROLE_SERVICE_JUNCTION, ROLE_TUNNEL_RAMP,
                               SHARED_VERTEX_TOL_M)

FLAG = "O4_TUNNEL_CORRIDOR_NODE_BOOK_EXCLUSION"

#: The bore floor's own solved value — the OTHH site-1 number.
FLOOR_Z = -1.1
#: The surrounding road's at-grade bench — the value that captured it.
BENCH_Z = 2.3


# ═════════════════════════════════════════════════════════════════════
# helpers — synthetic, headless, no DEM, no X-Plane install
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _shape(poly, role, z):
    return BuiltShape(polygon=poly, role=role,
                      node_altitudes=[z] * len(poly.exterior.coords))


def _layout(shapes, claim_polys=None):
    """A minimal layout carrying R14-1's PUBLISHED claim set.

    ``tunnel_open_cut_claim_polys`` is exactly what
    ``bridges.publish_tunnel_open_cut_claim_set`` writes — the claimed
    road surfaces themselves.  Nothing here re-derives a cut zone; a
    second geometric notion of "inside the cut" is what the spec
    forbids.
    """
    lay = types.SimpleNamespace(shapes=list(shapes), anchor=(0.0, 0.0))
    if claim_polys:
        lay.tunnel_open_cut_claim_polys = list(claim_polys)
    return lay


def _alts(shape):
    return [round(float(a), 2) for a in shape.node_altitudes]


def _bore_scene(claimed=True):
    """The site-1 shape of the defect, at unit scale.

    ``floor`` is the bore's descending floor — a ``groundside_pavement``
    ring at −1.1 m.  ``road`` is the at-grade ``service_junction`` beside
    it, sharing the two vertices on their common edge (the weld the node
    book unified).  R14-1 claimed the FLOOR as the tunnel corridor, so
    the claim set is the floor's own polygon.
    """
    floor = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
    road = _shape(_rect(40, 0, 60, 10), ROLE_SERVICE_JUNCTION, BENCH_Z)
    lay = _layout([floor, road],
                  claim_polys=[floor.polygon] if claimed else None)
    return lay, floor, road


# ═════════════════════════════════════════════════════════════════════
# (a) the exclusion itself
# ═════════════════════════════════════════════════════════════════════

class TestAClaimedBoreFloorIsExcludedFromTheNodeBook:
    """Spec §2 — the ring keeps its own solved values and contributes NO
    key to the shared space."""

    def test_off_reproduces_the_capture(self, monkeypatch):
        """The pre-fix world, on purpose: the road's bench value wins at
        the weld and drags the bore floor up out of its cut."""
        monkeypatch.setenv(FLAG, "0")
        lay, floor, road = self._scene()
        gs._grade_limit_groundside_chords(lay)
        after = _alts(floor)
        assert max(after) > FLOOR_Z + 0.5, (
            f"the capture did not reproduce: floor {after} — this twin's "
            f"OFF arm must show the defect the fix removes")

    def test_on_the_below_grade_values_survive(self, monkeypatch):
        """The ruled behaviour: the portal walk owns the bore floor, so
        the clamp may not touch a single one of its vertices."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = self._scene()
        before = _alts(floor)
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == before == [FLOOR_Z] * len(before), (
            "the bore floor moved — its authority is the portal walk")

    def test_on_the_excluded_ring_mints_no_shared_key(self, monkeypatch):
        """"…and contributes no keys to the shared space" — the second
        half of §2, and the half that stops a partner way importing a
        value ACROSS the cut boundary."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = self._scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["nodes"] == 0, (
            f"the excluded rings still minted {stats['nodes']} node "
            f"key(s) in the unified book")
        assert ROLE_GROUNDSIDE_PAVEMENT not in (stats["rings"] or {})

    def test_the_partner_road_ring_is_excluded_too(self, monkeypatch):
        """Membership is ANY node inside the claim, and exclusion is per
        RING — so the road welded to the cut boundary leaves the book as
        well.  That is the mechanism: a shared key is exactly how a value
        crosses the boundary, so neither side may mint one."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = self._scene()
        before = _alts(road)
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["tunnel_corridor_excluded_rings"] == 2
        assert stats["tunnel_corridor_excluded_by_role"] == {
            ROLE_GROUNDSIDE_PAVEMENT: 1, ROLE_SERVICE_JUNCTION: 1}
        assert _alts(road) == before

    def test_no_claim_means_no_exclusion(self, monkeypatch):
        """No second notion of "inside the cut": with nothing published
        by R14-1 the pass is exactly the pre-fix pass."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = self._scene(claimed=False)
        gs._grade_limit_groundside_chords(lay)
        assert lay._chord_limit_stats["tunnel_corridor_excluded_rings"] == 0
        assert max(_alts(floor)) > FLOOR_Z + 0.5

    @staticmethod
    def _scene(claimed=True):
        return _bore_scene(claimed=claimed)


# ═════════════════════════════════════════════════════════════════════
# (b) the road chord limiter's own purpose, unregressed
# ═════════════════════════════════════════════════════════════════════

class TestARoadOutsideAnyClaimKeepsTheLimiter:
    """Spec §4 — "the limiter keeps its full role set everywhere else"."""

    def _scene(self):
        """A road/lot weld 500 m from the bore, and a claim that covers
        only the bore."""
        bore = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
        road = BuiltShape(polygon=_rect(500, 0, 540, 20),
                          role=ROLE_SERVICE_JUNCTION,
                          node_altitudes=[10.0, 14.0, 14.0, 10.0, 10.0])
        lot = _shape(_rect(500, 20, 540, 60), ROLE_GROUNDSIDE_PAVEMENT, 10.0)
        return _layout([bore, road, lot],
                       claim_polys=[bore.polygon]), bore, road, lot

    def test_the_far_road_is_still_clamped(self, monkeypatch):
        """A road ring over its own cap is still pulled inside it — the
        exclusion is scoped to the claim, never to the family."""
        monkeypatch.setenv(FLAG, "1")
        lay, bore, road, lot = self._scene()
        n = gs._grade_limit_groundside_chords(lay)
        assert n >= 1
        after = _alts(road)
        assert after[1] < 14.0, "the over-cap road vertex was not CUT"
        cap = cfg.ROLE_GRADE_LIMITS[ROLE_SERVICE_JUNCTION]
        worst = max(abs(after[i] - after[j])
                    / max(1e-9, _dist(road, i, j))
                    for i in range(4) for j in range(i + 1, 4))
        assert worst <= cap + 5e-3

    def test_the_road_still_wins_the_weld(self, monkeypatch):
        """Authority precedence across roles — the ``cce9da6f`` rule the
        node book exists for — is untouched outside the claim."""
        monkeypatch.setenv(FLAG, "1")
        lay, bore, road, lot = self._scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["shared_road_lot_nodes"] == 2, (
            "the road↔lot weld left the unified book")
        assert stats["tunnel_corridor_excluded_rings"] == 1
        # one value per shared node, both rings
        shared = {}
        for shape in (road, lot):
            ring = list(shape.polygon.exterior.coords)[:-1]
            for (x, y), v in zip(ring, _alts(shape)):
                k = (round(x, 2), round(y, 2))
                if k in shared:
                    assert shared[k] == pytest.approx(v, abs=1e-9)
                shared[k] = v


def _dist(shape, i, j):
    ring = list(shape.polygon.exterior.coords)
    ax, ay = ring[i]
    bx, by = ring[j]
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


# ═════════════════════════════════════════════════════════════════════
# (c) the retreat faces come back (spec §3)
# ═════════════════════════════════════════════════════════════════════

class TestTheRetreatWallsFollowTheRestoredRamp:
    """Spec §3 — ``authority_retreat_wall`` emission is VERIFIED
    downstream of the exclusion.

    The faces are derived from the below-grade geometry retreating from
    a higher-precedence claimant: they exist only while the two
    claimants DISAGREE at the shared node.  The capture erased the
    disagreement (the clamp wrote one value into both rings), which is
    why 9 of OTHH site-1's 10 faces stopped being emitted.  Walls are
    lawful here because this is a CARVE STRUCTURE (owner 2026-08-07:
    "walls are lawful ONLY at tunnel/bridge carve structures").
    """

    def _bore_layout(self, claimed=True):
        lay = PavementLayout(icao="KFAKE", anchor=(25.27, 51.60))
        lay.canonical_points = CanonicalPointRegistry(
            tol_m=SHARED_VERTEX_TOL_M)
        # the at-grade road, welded to the middle of the floor's top edge
        # (a mid-ring contested vertex — a ring CORNER can only retreat
        # along its diagonal, which the emitter refuses)
        lay.shapes.append(_shape(_rect(100, 0, 140, 40),
                                 ROLE_SERVICE_JUNCTION, BENCH_Z))
        floor = BuiltShape(
            polygon=Polygon([(0, 0), (0, -200), (400, -200), (400, 0),
                             (140, 0), (100, 0)]),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="bore_floor",
            node_altitudes=[FLOOR_Z] * 7)
        lay.shapes.append(floor)
        # THE CARVE STRUCTURE — the portal the wall is lawful at.
        lay.shapes.append(_shape(_rect(110, 2, 130, 12),
                                 ROLE_TUNNEL_RAMP, BENCH_Z - 6.0))
        if claimed:
            lay.tunnel_open_cut_claim_polys = [floor.polygon]
        return lay, floor

    @staticmethod
    def _walls(lay):
        return [s for s in lay.shapes
                if (getattr(s, "ref", "") or "") == "authority_retreat_wall"]

    def test_on_the_faces_emit(self, monkeypatch):
        from auto_patch import adjacent_ground as AG
        monkeypatch.setenv(FLAG, "1")
        lay, floor = self._bore_layout()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 7
        assert AG.emit_authority_retreat_walls(lay) > 0
        assert self._walls(lay), (
            "the bore's retreat faces did not emit even though the ramp "
            "values survived — spec §3 is not satisfied")

    def test_off_the_faces_vanish_exactly_as_measured_at_othh(
            self, monkeypatch):
        """The defect's other half, pinned so it cannot come back
        silently: with the capture the two claimants AGREE at the weld,
        so there is nothing to retreat from and no face is minted."""
        from auto_patch import adjacent_ground as AG
        monkeypatch.setenv(FLAG, "0")
        lay, floor = self._bore_layout()
        gs._grade_limit_groundside_chords(lay)
        assert max(_alts(floor)) > FLOOR_Z + 0.5
        AG.emit_authority_retreat_walls(lay)
        assert not self._walls(lay)


# ═════════════════════════════════════════════════════════════════════
# (d) the kill switch
# ═════════════════════════════════════════════════════════════════════

class TestTheFlagOffIsTodaysBehaviour:
    """Spec §5 — OFF is the pre-fix pass, bit for bit, for attribution
    arms."""

    def test_off_equals_a_layout_with_no_claim_published(self, monkeypatch):
        """The only thing the fix adds to the pass is the claim read; with
        the flag off, a layout CARRYING a claim and one carrying none must
        produce the same altitudes, the same return value and the same
        census."""
        monkeypatch.setenv(FLAG, "0")
        with_claim, floor_a, road_a = _bore_scene(claimed=True)
        without, floor_b, road_b = _bore_scene(claimed=False)
        n_a = gs._grade_limit_groundside_chords(with_claim)
        n_b = gs._grade_limit_groundside_chords(without)
        assert n_a == n_b
        assert _alts(floor_a) == _alts(floor_b)
        assert _alts(road_a) == _alts(road_b)
        assert (with_claim._chord_limit_stats
                == without._chord_limit_stats)
        assert (with_claim._chord_limit_stats[
            "tunnel_corridor_excluded_rings"] == 0)

    def test_the_flag_defaults_ON(self, monkeypatch):
        """Default ON (spec §5): the production build carries the fix."""
        monkeypatch.delenv(FLAG, raising=False)
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 5

    def test_the_claim_set_is_published_by_r14_1_not_re_derived(self):
        """ONE AUTHORITY (spec §2): the publisher hands the claim list
        through verbatim — the same polygons
        ``_stand_down_synthetic_over_claimed`` consumes."""
        from auto_patch import bridges
        lay = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        a, b = _rect(0, 0, 10, 10), _rect(20, 20, 30, 30)
        assert bridges.publish_tunnel_open_cut_claim_set(
            lay, [a, None, b]) == 2
        assert lay.tunnel_open_cut_claim_polys == [a, b]
        # a second system's claim ACCUMULATES, never replaces
        c = _rect(40, 40, 50, 50)
        assert bridges.publish_tunnel_open_cut_claim_set(lay, [c]) == 1
        assert lay.tunnel_open_cut_claim_polys == [a, b, c]
        # nothing claimed ⇒ nothing published ⇒ nothing excluded
        empty = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        assert bridges.publish_tunnel_open_cut_claim_set(empty, []) == 0
        assert not hasattr(empty, "tunnel_open_cut_claim_polys")
