"""A TRUE FORK IS WALLED PER ARM, AND THE PINCH IS SHARED.

Spec ``docs/specs/linear-transport-redesign-spec.md`` §5-SUPPLEMENT-2
(Batch 3f):

    A TRUE fork (31h divergence test) is walled PER ARM: downstream of
    the divergence point each arm is its own corridor for the wall
    machinery — the existing band emitter runs on the arm's own body,
    yielding inner AND outer faces per arm naturally (no special
    inner-face path).  Where the two arms' INNER bands overlap near the
    throat (the V's pinch, the 31g class), they collapse to ONE SHARED
    wall along the bisector — a shared structure is the physical answer
    in a gap narrower than two bands.  (RULINGS 2026-09-01a A then stood
    the pinch wall DOWN at the seed, and 2026-09-01c retired the §T5
    foot: the band is one ref, standing off the road.)

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
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from auto_patch import bridges
from auto_patch.layout import (BuiltShape, PavementLayout,
                               ROLE_RETAINING_WALL, ROLE_TUNNEL_RAMP)

APT = 4.0
G0, G1 = 0.6, 1.0          # wall gap (2026-09-01e), wall width


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
        assert face is not None
        # both sides: the band reaches ground on the -x and +x flanks
        assert face.intersects(Polygon([(-2, 10), (0, 10), (0, 50),
                                        (-2, 50)]))
        assert face.intersects(Polygon([(8, 10), (10, 10), (10, 50),
                                        (8, 50)]))

    def test_the_band_is_complete_on_a_clean_body(self):
        """The band occupies its whole ``G0``..``G0+G1`` annulus (the
        0.02 m slit kerf is the only allowance) — and NOT the gap
        inboard of it, which the mesher triangulates (2026-09-01c)."""
        lay = _layout()
        arm = Polygon([(0, 0), (8, 0), (8, 60), (0, 60)])
        s = _ramp(arm)
        lay.shapes.append(s)
        bridges.emit_wall_band(lay, [], [arm], [s], [], G0, G1,
                               _dem, APT)
        inner = arm.buffer(G0, join_style=2, mitre_limit=2.0)
        want = arm.buffer(G0 + G1, join_style=2,
                          mitre_limit=2.0).difference(inner)
        got = _wall(lay, "tunnel_wall")
        assert got.area == pytest.approx(want.area, rel=0.02)
        assert got.intersection(inner.difference(arm)).area \
            == pytest.approx(0.0, abs=0.01), (
            "the band reaches into the gap the mesher must triangulate")


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
        """RULINGS 31g's answer: ONE shared wall in the pinch."""
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

    def test_a_multi_body_cluster_walls_per_body_and_a_single_one_does_not(
            self):
        """RULINGS 2026-09-01j: EVERY ramp body of a multi-body cluster
        is walled as its own corridor; the union band is kept for the
        SINGLE-body cluster only (a 31h-merged dual carriageway is one
        body and still takes it)."""
        src = inspect.getsource(bridges._emit_portal_cluster)
        assert "_cluster_ramps = [" in src, "no per-body register"
        assert "if len(_cluster_polys) >= 2 and _plan:" in src, (
            "the per-body path is not gated on a MULTI-body cluster")
        assert "for _bods, _srcs, _aends in _plan:" in src
        # …and the single-union path survives for the single-body case
        assert "_ru_polys" in src.split(
            "if len(_cluster_polys) >= 2 and _plan:")[1]

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


class TestEveryBodyOfAMultiBodyClusterIsWalled:
    """RULINGS 2026-09-01j — PER-BODY WALLING.

    The measured defect: only divergence ARMS entered the walling
    register, so any other ramp body of a multi-body cluster got just
    the union band, whose outward offset traces the OUTER HULL and can
    never produce a concave inner face.  At the OTHH fork the log read
    "2 arm(s)" at a site with FOUR ramp bodies, and the 142.8 m body was
    left 66.7 m unanswered — 51.4 m of it on FREE GROUND — while the
    same emitter, called on that same body offline, returned a complete
    band.  The geometry was always emittable; the body never got a call.
    """

    def test_a_non_arm_body_gets_its_own_inner_faces(self):
        """A body walled as its own corridor is retained on BOTH sides —
        the union band's hull cannot do this for a concave side."""
        body = Polygon([(0, 0), (8, 0), (8, 60), (0, 60)])
        lay = _layout()
        s = _ramp(body)
        lay.shapes.append(s)
        n0 = len(lay.shapes)
        bridges.emit_wall_band(lay, [], [body], [s], [], G0, G1,
                               _dem, APT)
        band = unary_union([p.polygon for p in lay.shapes[n0:]
                            if p.role == ROLE_RETAINING_WALL])
        for flank in (Polygon([(-2, 10), (0, 10), (0, 50), (-2, 50)]),
                      Polygon([(8, 10), (10, 10), (10, 50), (8, 50)])):
            assert band.intersects(flank), (
                "a body walled as its own corridor must be retained on "
                "both of its sides")

    # NO SYNTHETIC HULL-vs-PER-BODY TWIN, AND THAT IS DELIBERATE.
    # One was written and DELETED: on a synthetic Y the union band
    # already answers 0.958 of an arm's ring under the acceptance
    # instrument's own 2.5 m reach, because the arms sit close enough
    # that the band on the far side of the V still counts.  The scene
    # did not reproduce the defect, and reshaping it until the
    # assertion held would be fitting a scene to a bar — the class this
    # batch has refused throughout.  The hull's inability to produce a
    # concave inner face is evidenced where it was MEASURED: the OTHH
    # fork's 142.8 m body, 51.4 m of free-ground side under the union
    # band against a complete band when the body gets its own call
    # (docs/DEFERRED_VERIFICATION.md, round 3k).

class TestTheWallingOrderIsTheMechanism:
    """THE ORDER WAS A SYMPTOM; THE ARC-DROP WAS THE MECHANISM.

    Batch 3f read walling order as the cause: walling the throat first
    let ITS band claim the ground each arm's INNER band needed, and the
    arms — which subtract what is already emitted — came up short
    (throat-first 0.52/0.52 against arms-first 0.92/0.92 on the §T5
    foot, matching the field fork at 25.2537652,51.6032373).

    RE-MEASURED under the retired foot (RULINGS 2026-09-01c), the real
    mechanism showed itself one layer down: the sibling subtraction cuts
    a later arm's already-slit C-ring into TWO arcs and the emitter kept
    only the larger, deleting 62.0 m² of a 128.8 m² band ON FREE GROUND
    with no log line naming the remover.  Keeping every surviving arc —
    what the R10-2 clip beside it always did — puts BOTH orders at
    0.91/0.91 and leaves a shortfall that is entirely sibling pavement.
    The emitter still walls arms before the throat (it is the shape it
    ships and the twin below pins it), but the ordering no longer
    carries the result.
    """

    THROAT = Polygon([(0, 0), (20, 0), (20, 30), (0, 30)])
    ARM_A = Polygon([(0, 30), (9, 30), (-6, 80), (-16, 76)])
    ARM_B = Polygon([(11, 30), (20, 30), (36, 76), (26, 80)])

    def _walled(self, order):
        lay = _layout()
        bodies = {"throat": self.THROAT, "A": self.ARM_A, "B": self.ARM_B}
        shapes = {k: _ramp(v) for k, v in bodies.items()}
        for s in shapes.values():
            lay.shapes.append(s)
        done = []
        for key in order:
            n0 = len(lay.shapes)
            bridges.emit_wall_band(lay, [], [bodies[key]], [shapes[key]],
                                   [], G0, G1, _dem, APT,
                                   exclude=list(done))
            done.extend(s.polygon for s in lay.shapes[n0:]
                        if s.role == ROLE_RETAINING_WALL)
        return lay

    def _wall(self, order):
        lay = self._walled(order)
        bodies = {"throat": self.THROAT, "A": self.ARM_A, "B": self.ARM_B}
        band = [s.polygon for s in lay.shapes
                if s.ref == "tunnel_wall"]
        out = []
        for k in ("A", "B"):
            inner = bodies[k].buffer(G0, join_style=2, mitre_limit=2.0)
            want = bodies[k].buffer(G0 + G1, join_style=2,
                                    mitre_limit=2.0).difference(inner)
            got = unary_union(band).intersection(want) if band else None
            out.append((got.area / want.area) if got else 0.0)
        return out

    def test_every_arm_is_retained_whatever_the_order(self):
        """THE ORDERING WAS A SYMPTOM, AND THE CAUSE IS FIXED.

        The sibling subtraction (``exclude``) cuts a later arm's
        already-slit C-ring into two arcs, and it used to keep only
        ``max(geoms, key=area)`` — deleting the other arc in silence.
        MEASURED here before the fix: arm B kept 65.8 of a 128.8 m²
        band and lost 62.0 m² on FREE GROUND, which is the fork's
        missing inner face.  Keeping EVERY surviving arc (what the
        R10-2 clip beside it already did) takes both arms to 0.91 in
        BOTH orders, and the whole remaining shortfall — 11.4 of
        11.4 m² — lies on sibling PAVEMENT, where R10-2 forbids a band.
        """
        for order in (["A", "B", "throat"], ["throat", "A", "B"]):
            a, b = self._wall(order)
            assert min(a, b) >= 0.9, (
                f"{order}: arm band {a:.2f}/{b:.2f} — an arm lost band "
                f"on free ground")

    def test_no_arc_crumb_ships_and_none_nests(self):
        """THE ARC FIX MUST NOT SHIP MITRE RESIDUE *AT THE EMITTER*.

        Keeping every surviving arc is what recovered the fork's inner
        face, but a difference at a sharp mitred corner also leaves
        crumbs, so the arc list is floored at
        ``_TUNNEL_COVER_MIN_PIECE_M2`` — the constant the R10-2 clip
        already uses for the same question, so the two paths hold ONE
        opinion of what a piece is.

        SCOPE, MEASURED (2026-09-01): this twin governs the EMITTER's
        own output and nothing downstream.  The OTHH fork still ships
        0.23-0.73 m² crumbs and two nested pairs AFTER this floor, so
        those are made by a later, unattributed pass — this twin must
        not be read as covering them.
        """
        lay = self._walled(["A", "B", "throat"])
        band = [s.polygon for s in lay.shapes if s.ref == "tunnel_wall"]
        assert band
        floor = bridges._TUNNEL_COVER_MIN_PIECE_M2
        assert min(p.area for p in band) >= floor, (
            f"a crumb below {floor} m2 shipped: "
            f"{sorted(round(p.area, 2) for p in band)}")
        for i, a in enumerate(band):
            for j, b in enumerate(band):
                if i != j:
                    assert not b.covers(a), (
                        f"band piece {i} ({a.area:.2f} m2) is nested "
                        f"inside piece {j} ({b.area:.2f} m2)")

    def test_the_shortfall_that_remains_is_sibling_pavement(self):
        """What a band may NOT stand on: R10-2 keeps full force, and
        ruling 2026-09-01a A leaves the fork's V unwalled at the pinch.
        Every square metre an arm lacks must be on a sibling."""
        lay = self._walled(["A", "B", "throat"])
        band = unary_union([s.polygon for s in lay.shapes
                            if s.ref == "tunnel_wall"])
        bodies = {"throat": self.THROAT, "A": self.ARM_A, "B": self.ARM_B}
        for k in ("A", "B"):
            inner = bodies[k].buffer(G0, join_style=2, mitre_limit=2.0)
            want = bodies[k].buffer(G0 + G1, join_style=2,
                                    mitre_limit=2.0).difference(inner)
            miss = want.difference(band)
            sib = unary_union([bodies[o] for o in bodies if o != k])
            assert miss.difference(sib).area <= 0.5, (
                f"arm {k} lacks {miss.difference(sib).area:.1f} m² of "
                f"band on ground no sibling occupies")

    def test_the_emitter_walls_arms_before_the_other_bodies(self):
        """Arms first, every other body after — the order IS a
        mechanism (throat-first starves the arms' inner bands: measured
        0.52/0.52 against 0.92/0.92 on the synthetic Y).  Under
        2026-09-01j the plan is SEEDED from the arm register and the
        remaining cluster bodies are appended to it, which is that
        ordering expressed as one list."""
        src = inspect.getsource(bridges._emit_portal_cluster)
        i_seed = src.index("_plan = [(_bods, _srcs, _aends)")
        i_rest = src.index("_plan.append(([_s.polygon], _cluster_ramps, []))")
        i_run = src.index("for _bods, _srcs, _aends in _plan:")
        assert i_seed < i_rest < i_run, (
            "the arms must seed the plan before the other bodies are "
            "appended, and the plan must be built before it is walked")
