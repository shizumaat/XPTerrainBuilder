"""A TUNNEL RAMP SURFACE'S AUTHORED FIELDS SURVIVE TO EMIT.

RULINGS 2026-08-31b; ``docs/specs/linear-transport-redesign-spec.md`` §5.2
(REWIRE BY ROLE/GEOMETRY, not ref) and
``docs/specs/linear-transport-consumer-census.md`` rows #33/#34.

WHAT CHANGED.  This file used to pin R14-1's CLAIM CLASS: the predicate
was ``groundside.claimed_tunnel_corridor`` and it asked whether a shape
carried the ``tunnel_road`` ref that ``bridges._claim_road_pavement``
stamped on mapped road pavement over an open cut.  That class is RETIRED
(31a judged it the defect, 31b retired it); mapped road pavement is never
re-profiled in place any more.  The predicate is now
``groundside.is_tunnel_ramp_surface`` and its population is the portal
walk's OWN below-grade geometry — ramp / mouth / corridor, the canonical
mouth of RULINGS 2026-08-30.

WHAT DID NOT CHANGE — the law under test, which is why the file survives.
MEASURED (lane/tunnelmerge, OTHH mouth D): the corridor under the mouth's
approach was authored at −0.92 m and shipped as way ``-12170`` — 19,325 m²,
``role=groundside_pavement ref=groundside``, FLAT at ``altitude=3.96`` —
so the mouth emitted no below-grade geometry at all.

THE PASSES THAT TOOK IT, each measured on a synthetic scene rather than
guessed: ``_merge_touching_groundside`` (a ring merged with its touching
neighbours is re-minted through ``_dem_follow_polygon`` with
``ref="groundside"`` — the profile gone), the post-solve law seats
(``seat_groundside_on_law`` / ``seat_service_pavement_on_law``), the
clearance clip (``_separate_groundside_from_airside``) and the service
lens clip (``_clip_shape_yielding_to`` /
``_deconflict_service_overlaps``).  None of them is wrong in general: the
merge is a geometry repair for pieces split upstream, and the seats exist
to rescue rings still carrying their pre-solve DEM seed.  A TUNNEL RAMP
SURFACE IS NEITHER: it has internal structure (a bore profile) and it is
not on a seed — its field is authored by the portal walk, which outranks
both.

WHY THE FIXTURES CARRY A GROUNDSIDE / SERVICE ROLE WITH A TUNNEL REF.
Every one of the six readers is inside a loop already gated on
``ROLE_GROUNDSIDE_PAVEMENT`` or the service roles, so a shape whose ROLE
is ``ROLE_TUNNEL_RAMP`` never reaches the guard at all — the guard exists
for the shape that arrives wearing a groundside/service role while
carrying the portal walk's ref, which is EXACTLY the measured mouth-D
class above (a bore surface shipping as ``groundside_pavement``).  That
is the predicate's ref arm; its role arm is asserted directly in
:class:`TestThePredicateKeysOnRoleAndGeometry`.

THE FIX IS AT SOURCE: the verdict RIDES THE SHAPE and every downstream
re-derivation recognises it and leaves the field alone.  There is no
re-stamping pass and none may be added — a field restored after the fact
is a field that was already lost.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import groundside as gs
from auto_patch.layout import (BuiltShape, PavementLayout, ROLE_APRON,
                               ROLE_GROUNDSIDE_PAVEMENT,
                               ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD,
                               ROLE_TUNNEL_RAMP)

#: The ref the portal walk stamps on its own ramp geometry.  One
#: spelling, shared with ``bridges._TUNNEL_PAVEMENT_REFS``.
RAMP_REF = "tunnel_ramp"

BORE_Z = -0.92
GRADE_Z = 3.96


class _DEM:
    """A flat DEM at grade — so any re-derivation shows up as the
    ramp surface coming back to ``GRADE_Z``."""

    def alt(self, *a, **k):
        return GRADE_Z

    def alt_vec(self, *a, **k):
        return None


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    lay = PavementLayout(icao="KFAKE", anchor=(25.0, 51.0))
    lay.shapes.extend(shapes)
    return lay


def _ramp_surface(role=ROLE_GROUNDSIDE_PAVEMENT):
    """The portal walk's own below-grade surface as the downstream
    passes meet it: the walk's ref, a bore profile, and the role the
    upstream re-derivation left on it (see the module docstring)."""
    return BuiltShape(polygon=_rect(0, 0, 40, 10), role=role,
                      ref=RAMP_REF, node_altitudes=[BORE_Z] * 5)


def _neighbour(x0=40, x1=90):
    return BuiltShape(polygon=_rect(x0, 0, x1, 10),
                      role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
                      node_altitudes=[GRADE_Z] * 5)


def _alts(shape):
    return [round(float(a), 2) for a in (shape.node_altitudes or ())]


class TestThePredicateKeysOnRoleAndGeometry:
    """Spec §5.2: the axis is ROLE/GEOMETRY, not a claim ref.  A ref can
    be dropped by a rebuild; ``ROLE_TUNNEL_RAMP`` is what every other
    tunnel consumer keys on, so BOTH arms are law."""

    def test_the_role_arm_admits_the_portal_walks_own_shapes(self):
        assert gs.is_tunnel_ramp_surface(
            BuiltShape(polygon=_rect(0, 0, 40, 10), role=ROLE_TUNNEL_RAMP,
                       ref="", node_altitudes=[BORE_Z] * 5))

    def test_the_ref_arm_admits_ramp_mouth_and_corridor(self):
        for ref in ("tunnel_ramp", "tunnel_mouth", "tunnel_corridor"):
            assert gs.is_tunnel_ramp_surface(
                BuiltShape(polygon=_rect(0, 0, 40, 10),
                           role=ROLE_GROUNDSIDE_PAVEMENT, ref=ref,
                           node_altitudes=[BORE_Z] * 5)), ref

    def test_an_ordinary_lot_is_not_a_ramp_surface(self):
        assert not gs.is_tunnel_ramp_surface(_neighbour())

    def test_the_retired_claim_ref_carries_no_meaning_any_more(self):
        """RULINGS 2026-08-31b: ``tunnel_road`` is no longer a class.  A
        shape wearing that ref is ordinary road pavement — core road
        ground above a covered stretch, or severed by the cut."""
        assert not gs.is_tunnel_ramp_surface(
            BuiltShape(polygon=_rect(0, 0, 40, 10),
                       role=ROLE_SERVICE_JUNCTION, ref="tunnel_road",
                       node_altitudes=[BORE_Z] * 5))
        assert "tunnel_road" not in gs.BELOW_GRADE_REFS
        assert not hasattr(gs, "claimed_tunnel_corridor")

    def test_the_ref_set_has_ONE_spelling_shared_with_bridges(self):
        """``groundside`` must recognise the portal walk's geometry
        without importing the module that imports it — so the two lists
        are asserted equal rather than kept in step by hand."""
        from auto_patch import bridges
        assert (tuple(gs._TUNNEL_RAMP_REFS)
                == tuple(bridges._TUNNEL_PAVEMENT_REFS))


class TestTheMergeLeavesARampSurfaceAlone:
    """The measured eater: a ramp ring merged with its neighbours is
    re-minted with ``ref="groundside"`` and a DEM-followed field."""

    def test_the_ramp_ring_survives_with_ref_and_altitudes(self):
        ramp, near = _ramp_surface(), _neighbour()
        lay = _layout([ramp, near])
        gs._merge_touching_groundside(lay, _DEM(), 25, 51)
        assert ramp in lay.shapes, (
            "the ramp surface was consumed by the groundside merge")
        assert ramp.ref == RAMP_REF
        assert _alts(ramp) == [BORE_Z] * 5, (
            "the merge re-derived the ramp's authored profile")

    def test_ordinary_neighbours_still_merge_around_it(self):
        """The merge's own purpose is untouched: two ordinary pieces
        sharing a seam are still one surface afterwards."""
        a, b = _neighbour(40, 90), _neighbour(90, 140)
        lay = _layout([_ramp_surface(), a, b])
        n = gs._merge_touching_groundside(lay, _DEM(), 25, 51)
        assert n >= 1, "the merge stopped merging ordinary groundside"
        assert a not in lay.shapes and b not in lay.shapes
        merged = [s for s in lay.shapes
                  if s.role == ROLE_GROUNDSIDE_PAVEMENT
                  and s.ref == "groundside"]
        assert len(merged) == 1
        assert merged[0].polygon.area == pytest.approx(100 * 10, rel=1e-3)


class TestThePostSolveSeatsLeaveARampSurfaceAlone:
    """``seat_groundside_on_law`` / ``seat_service_pavement_on_law`` are
    the rescue for rings still on their pre-solve DEM seed.  A tunnel
    ramp surface is not on a seed."""

    def test_the_groundside_seat_skips_it_and_says_so(self):
        ramp = _ramp_surface()
        lay = _layout([ramp, _neighbour()])
        gs.seat_groundside_on_law(lay, _DEM(), 25, 51)
        assert _alts(ramp) == [BORE_Z] * 5, (
            "the post-solve groundside seat re-seated the ramp onto "
            "the surrounding law — the measured mouth-D burial")
        assert ramp.ref == RAMP_REF
        # counted where the condition is known, never inferred later
        _book = (getattr(lay, "_gs_law_seat", None) or {})
        _bucket = ((_book.get("post_solve_groundside_law_seat") or {})
                   .get("skipped") or {})
        assert _bucket.get("tunnel_ramp_surface", 0) >= 1

    def test_the_service_seat_skips_it_too(self):
        ramp = _ramp_surface(role=ROLE_SERVICE_JUNCTION)
        lay = _layout([ramp])
        gs.seat_service_pavement_on_law(lay, _DEM(), 25, 51)
        assert _alts(ramp) == [BORE_Z] * 5
        assert ramp.ref == RAMP_REF

    def test_an_ordinary_ring_is_still_seated_normally(self):
        """The seats keep their population: only the ramp is exempt."""
        plain = _neighbour(0, 40)
        lay = _layout([plain])
        gs.seat_groundside_on_law(lay, _DEM(), 25, 51)
        _book = (getattr(lay, "_gs_law_seat", None) or {})
        _gs = _book.get("post_solve_groundside_law_seat") or {}
        assert _gs.get("candidates", 0) >= 1, (
            "an ordinary groundside ring stopped being a candidate — the "
            "exemption leaked past the ramp")


class TestTheSeparationClipCarriesTheRampProfile:
    """THE PASS THE FIRST PROBE MISSED, and why: a scene with no AIRSIDE
    in it makes ``_separate_groundside_from_airside`` a no-op, so the
    probe read "harmless" — while at OTHH the surface is a 19,461 m² ring
    ADJACENT to apron, gets clipped to the clearance gap, and is re-minted
    with ``ref="groundside"`` and a DEM re-follow.

    The clearance invariant is real (groundside shares no node or edge
    with airside), so the ramp surface IS clipped.  What must not happen
    is the rebuild forgetting whose surface it is.
    """

    def _scene(self):
        ramp = _ramp_surface()                    # x 0..40
        apron = BuiltShape(polygon=_rect(30, 0, 120, 10), role=ROLE_APRON,
                           ref="apron", node_altitudes=[GRADE_Z] * 5)
        lay = _layout([ramp, apron])
        return lay, ramp, apron

    def test_the_clipped_piece_keeps_the_ref_and_the_profile(self):
        lay, ramp, apron = self._scene()
        n = gs._separate_groundside_from_airside(lay, _DEM(), 25, 51,
                                                 preserve_field=True)
        assert n >= 1, "the clearance clip did not fire — inert scene"
        corridor = [s for s in lay.shapes
                    if gs.is_tunnel_ramp_surface(s)]
        assert corridor, (
            "the clipped ramp lost its ref — the measured mouth-D burial "
            "(shipped ref=groundside, flat at grade)")
        piece = corridor[0]
        # the carrier is the module's own edge-interpolating resampler,
        # so a rebuilt vertex lands within its 2-dp step of the authored
        # value — what must never happen is the DEM's 3.96 coming back
        assert max(_alts(piece)) <= BORE_Z + 0.05, (
            f"the ramp came back at {max(_alts(piece))} m — the "
            f"rebuild re-followed the DEM instead of carrying the "
            f"authored bore profile")

    def test_an_ordinary_lot_is_clipped_exactly_as_before(self):
        """The pass keeps its own behaviour everywhere else: an ordinary
        lot is still clipped and still re-derived."""
        plain = BuiltShape(polygon=_rect(0, 0, 40, 10),
                           role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
                           node_altitudes=[GRADE_Z] * 5)
        apron = BuiltShape(polygon=_rect(30, 0, 120, 10), role=ROLE_APRON,
                           ref="apron", node_altitudes=[GRADE_Z] * 5)
        lay = _layout([plain, apron])
        n = gs._separate_groundside_from_airside(lay, _DEM(), 25, 51,
                                                 preserve_field=True)
        assert n >= 1
        assert not [s for s in lay.shapes if gs.is_tunnel_ramp_surface(s)]
        lots = [s for s in lay.shapes
                if s.role == ROLE_GROUNDSIDE_PAVEMENT]
        assert lots and lots[0].ref == "groundside"


class TestNoReStampingPass:
    """The structural assertion, unchanged in force and re-keyed in name:
    the fix is a predicate consulted where the field would be re-derived,
    never a pass that puts the fields back afterwards."""

    def test_the_fix_is_a_predicate_at_the_consumers(self):
        import inspect
        src = inspect.getsource(gs)
        assert src.count("is_tunnel_ramp_surface(") >= 5, (
            "the ramp predicate is not consulted at every re-derivation")
        for banned in ("re_stamp", "restamp", "reapply_claim"):
            assert banned not in src


# ═════════════════════════════════════════════════════════════════════
# THE SERVICE CHAIN — the same rule, the same carrier
# ═════════════════════════════════════════════════════════════════════

class TestTheServiceChainCarriesTheRampProfile:
    """MEASURED (OTHH, 2026-08-25): on the service side the REF rides
    fine — every surviving piece kept it — and the DEPTH did not:
    surfaces authored at −1.14 m came back at 1.50/1.60/4.00 m on the
    pieces a clip re-shaped, while pieces the clip never touched kept
    −1.00.

    The carrier was the difference.  ``_clip_shape_yielding_to`` takes
    each new vertex's altitude from the NEAREST ORIGINAL VERTEX — right
    for a flat-ish service ring welded along its contact, wrong for a
    corridor whose ring runs from bore depth to ambient, because a clip
    near the shallow end snaps the deep end's vertices to a shallow
    corner.  A tunnel ramp surface is carried by the module's own
    EDGE-INTERPOLATING resampler instead: one carrier, not two.
    """

    def _service_ramp(self):
        """A corridor ring GRADED along its run — bore depth at one end,
        ambient at the other.  A flat test ring cannot tell the two
        carriers apart, which is how this survived a round."""
        return BuiltShape(
            polygon=_rect(0, 0, 100, 10), role=ROLE_SERVICE_JUNCTION,
            ref=RAMP_REF,
            node_altitudes=[-1.14, GRADE_Z, GRADE_Z, -1.14, -1.14])

    def test_a_clipped_ramp_ring_keeps_its_PROFILE(self):
        ramp = self._service_ramp()
        # a larger partner overlapping the ring's SHALLOW end only
        partner = BuiltShape(polygon=_rect(80, -5, 300, 15),
                             role=ROLE_SERVICE_ROAD, ref="service",
                             node_altitudes=[GRADE_Z] * 5)
        lay = _layout([ramp, partner])
        n = gs._deconflict_service_overlaps(lay)
        assert n >= 1, "the lens clip did not fire — inert scene"
        assert ramp in lay.shapes and ramp.ref == RAMP_REF
        assert min(_alts(ramp)) <= -1.10, (
            f"the clipped corridor's deep end came back at "
            f"{min(_alts(ramp))} m — the nearest-vertex carry lifted "
            f"it (the measured service-side loss)")

    def test_a_ramp_ring_wholly_inside_another_is_NOT_dropped(self):
        """The drop path: "the kept shape already covers its footprint at
        the same role" is true of the FOOTPRINT and false of the
        SURFACE — the corridor carries bore depth and the cover does
        not."""
        ramp = BuiltShape(polygon=_rect(10, 2, 30, 8),
                          role=ROLE_SERVICE_JUNCTION,
                          ref=RAMP_REF,
                          node_altitudes=[-1.14] * 5)
        cover = BuiltShape(polygon=_rect(0, 0, 200, 10),
                           role=ROLE_SERVICE_ROAD, ref="service",
                           node_altitudes=[GRADE_Z] * 5)
        lay = _layout([ramp, cover])
        gs._deconflict_service_overlaps(lay)
        assert ramp in lay.shapes, (
            "a tunnel ramp surface wholly inside a service shape was "
            "dropped — that deletes the bore and leaves the mouth at "
            "grade")

    def test_an_ordinary_service_ring_still_yields_and_still_drops(self):
        """The pass keeps its own behaviour everywhere else."""
        plain = BuiltShape(polygon=_rect(10, 2, 30, 8),
                           role=ROLE_SERVICE_JUNCTION, ref="service",
                           node_altitudes=[GRADE_Z] * 5)
        cover = BuiltShape(polygon=_rect(0, 0, 200, 10),
                           role=ROLE_SERVICE_ROAD, ref="service",
                           node_altitudes=[GRADE_Z] * 5)
        lay = _layout([plain, cover])
        gs._deconflict_service_overlaps(lay)
        assert plain not in lay.shapes


class TestTheCarrierRebuildsThePiece:
    """``_carry_tunnel_ramp_profile`` is the ONE carrier every clip uses.
    The retired claim stamped a ``_tunnel_claim_depth`` attribute for the
    claim-drift audit to read back; that audit retired with the class
    (census #32), so the carrier now carries geometry and field only —
    there is nothing else to keep in step."""

    def test_a_carried_piece_keeps_the_ref_and_the_authored_field(self):
        from shapely.geometry import Polygon as _P
        source = BuiltShape(
            polygon=_rect(0, 0, 40, 10), role=ROLE_GROUNDSIDE_PAVEMENT,
            ref=RAMP_REF,
            node_altitudes=[BORE_Z, BORE_Z, GRADE_Z, GRADE_Z, BORE_Z])
        part = _P([(0, 0), (20, 0), (20, 10), (0, 10)])
        piece = gs._carry_tunnel_ramp_profile(source, part)
        assert piece is not None
        assert piece.ref == RAMP_REF
        assert piece.role == ROLE_GROUNDSIDE_PAVEMENT
        assert piece.node_altitudes and min(piece.node_altitudes) <= \
            BORE_Z + 0.05, (
            "the carrier re-derived the field instead of carrying it")

    def test_the_retired_claim_depth_attribute_is_not_stamped(self):
        from shapely.geometry import Polygon as _P
        source = _ramp_surface()
        part = _P([(0, 0), (20, 0), (20, 10), (0, 10)])
        piece = gs._carry_tunnel_ramp_profile(source, part)
        assert piece is not None
        assert not hasattr(piece, "_tunnel_claim_depth")
