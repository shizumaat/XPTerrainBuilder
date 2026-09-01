"""A TRUE FORK IS WALLED PER ARM, AND THE PINCH IS SHARED.

Spec ``docs/specs/linear-transport-redesign-spec.md`` §5-SUPPLEMENT-2
(Batch 3f):

    A TRUE fork (31h divergence test) is walled PER ARM: downstream of
    the divergence point each arm is its own corridor for the wall
    machinery — the existing band emitter runs on the arm's own body,
    yielding inner AND outer faces per arm naturally (no special
    inner-face path).  Where the two arms' INNER bands overlap near the
    throat (the V's pinch, the 31g class), they collapse to ONE SHARED
    wall+foot along the bisector — a shared structure is the physical
    answer in a gap narrower than two bands.

WHY IT COULD NOT WORK BEFORE.  The cluster band was emitted ONCE on the
UNION of every ramp in the cluster.  A union's outward offset traces its
OUTER hull only: the V between two arms is a concave notch, so the inner
faces were never geometry the emitter could produce.  Measured at the
confirmed fork 25.2537652,51.6032373 — inner side 0.08 of its length
retained by a wall against 0.98 for the foot.

THE PINCH RULE IS THE ``exclude`` SEED, not a second emitter: each arm
subtracts the bands its siblings already occupy, so where two inner
bands would overlap exactly one survives — along the bisector, because
that is where the overlap lies.
"""
from __future__ import annotations

import inspect

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from auto_patch import bridges
from auto_patch.layout import (BuiltShape, PavementLayout,
                               ROLE_RETAINING_WALL, ROLE_TUNNEL_RAMP)

APT = 4.0
G0, G1 = 0.6, 1.0          # wall gap, wall width


def _dem(x, y):
    return APT


def _layout():
    return PavementLayout("OTHH", anchor=(25.0, 51.0))


def _ramp(poly, z=-1.0):
    return BuiltShape(polygon=poly, role=ROLE_TUNNEL_RAMP,
                      ref="tunnel_ramp",
                      node_altitudes=[z] * (len(poly.exterior.coords) - 1))


def _band(lay):
    return [s for s in lay.shapes if s.role == ROLE_RETAINING_WALL]


def _wall(lay, ref):
    ps = [s.polygon for s in lay.shapes if s.ref == ref]
    return unary_union(ps) if ps else None


class TestAnArmWalledOnItsOwnBodyGetsBothFaces:

    def test_a_single_arm_band_wraps_the_whole_arm(self):
        """An arm IS its own corridor: the band emitter run on the arm's
        own body produces faces on BOTH of its sides — which is the
        whole of the mechanism the spec asks for."""
        lay = _layout()
        arm = Polygon([(0, 0), (8, 0), (8, 60), (0, 60)])
        s = _ramp(arm)
        lay.shapes.append(s)
        bridges.emit_wall_band(lay, [], [arm], [s], [], G0, G1,
                               _dem, APT)
        face = _wall(lay, "tunnel_wall")
        foot = _wall(lay, "tunnel_wall_foot")
        assert face is not None and foot is not None
        # both sides: the band reaches ground on the -x and +x flanks
        assert face.intersects(Polygon([(-2, 10), (0, 10), (0, 50),
                                        (-2, 50)]))
        assert face.intersects(Polygon([(8, 10), (10, 10), (10, 50),
                                        (8, 50)]))

    def test_the_foot_annulus_is_complete_on_a_clean_body(self):
        lay = _layout()
        arm = Polygon([(0, 0), (8, 0), (8, 60), (0, 60)])
        s = _ramp(arm)
        lay.shapes.append(s)
        bridges.emit_wall_band(lay, [], [arm], [s], [], G0, G1,
                               _dem, APT)
        want = arm.buffer(G0, join_style=2, mitre_limit=2.0).difference(arm)
        got = _wall(lay, "tunnel_wall_foot")
        assert got.area == pytest.approx(want.area, rel=0.02)


class TestThePinchCollapsesToOneSharedStructure:

    def _two_arms(self, gap):
        """Two parallel arms ``gap`` apart — the V's pinch in the small."""
        a = Polygon([(0, 0), (8, 0), (8, 60), (0, 60)])
        b = Polygon([(8 + gap, 0), (16 + gap, 0),
                     (16 + gap, 60), (8 + gap, 60)])
        return a, b

    def _wall_pair(self, gap, use_exclude):
        lay = _layout()
        a, b = self._two_arms(gap)
        sa, sb = _ramp(a), _ramp(b)
        lay.shapes.extend([sa, sb])
        done = []
        n0 = len(lay.shapes)
        bridges.emit_wall_band(lay, [], [a], [sa], [], G0, G1, _dem, APT)
        done.extend(s.polygon for s in lay.shapes[n0:]
                    if s.role == ROLE_RETAINING_WALL)
        bridges.emit_wall_band(lay, [], [b], [sb], [], G0, G1, _dem, APT,
                               exclude=list(done) if use_exclude else None)
        return lay

    def test_without_the_exclude_the_two_bands_OVERLAP(self):
        """The defect the rule exists for: in a gap narrower than two
        bands, walling each arm independently doubles the structure."""
        lay = self._wall_pair(gap=1.0, use_exclude=False)
        pieces = [s.polygon for s in _band(lay)]
        overlap = 0.0
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                overlap += pieces[i].intersection(pieces[j]).area
        assert overlap > 0.5, (
            "the fixture must actually pinch, or it tests nothing")

    def test_with_the_exclude_exactly_one_structure_survives(self):
        """RULINGS 31g's answer: ONE shared wall+foot in the pinch."""
        lay = self._wall_pair(gap=1.0, use_exclude=True)
        pieces = [s.polygon for s in _band(lay)]
        overlap = 0.0
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                overlap += pieces[i].intersection(pieces[j]).area
        assert overlap == pytest.approx(0.0, abs=0.05), (
            f"{overlap:.2f} m2 of band overlaps itself — the pinch did "
            f"not collapse to one shared structure")

    def test_a_WIDE_gap_keeps_both_arms_their_own_walls(self):
        """The pinch rule is scoped to the pinch: arms far enough apart
        each keep their own inner face, which is what "inner AND outer
        faces per arm" means away from the V."""
        lay = self._wall_pair(gap=12.0, use_exclude=True)
        face = _wall(lay, "tunnel_wall")
        # ground strictly between the two arms carries wall on both sides
        assert face.intersects(Polygon([(8, 20), (10, 20), (10, 40),
                                        (8, 40)]))
        assert face.intersects(Polygon([(18, 20), (20, 20), (20, 40),
                                        (18, 40)]))


class TestTheWiring:

    def test_exclude_seeds_the_emitted_set(self):
        """The mechanism is the seed, not a second emitter."""
        src = inspect.getsource(bridges.emit_wall_band)
        assert "exclude" in src
        assert "_emitted_band: list = [g for g in (exclude or ())" in src

    def test_a_fork_walls_per_arm_and_a_merged_run_does_not(self):
        """Two paths, and the fork one is taken only when arms exist."""
        src = inspect.getsource(bridges._emit_portal_cluster)
        assert "if _arm_bodies:" in src, "no per-arm branch"
        assert "for _bods, _srcs, _aends in _arm_bodies:" in src
        # …and the single-union path survives for the merged case
        assert "else:" in src.split("if _arm_bodies:")[1][:4000]
        assert "_ru_polys" in src.split("if _arm_bodies:")[1]

    def test_arm_bodies_is_empty_when_the_cluster_does_not_fork(self):
        """A dual carriageway merged by 31h is UNTOUCHED: it never
        populates the per-arm register, so it takes the union path."""
        src = inspect.getsource(bridges._emit_portal_cluster)
        i_decl = src.index("_arm_bodies: list = []")
        i_fill = src.index("_arm_bodies.append(")
        i_else = src.index("if s_div is None:")
        assert i_decl < i_else < i_fill, (
            "the register must be declared before the no-fork branch and "
            "filled only in the fork branch")
