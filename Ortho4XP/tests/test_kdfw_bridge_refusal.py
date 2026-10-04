"""KDFW — refuse implausible deck contracts + the deck-pin contradiction
guard (docs/specs/kdfw-bridge-refusal-spec.md).

THE MECHANISM, proven interventionally (KDFW +32-098, 2026-08-15/16): the
Aerosoft KDFW pavement inset mesh — 5 objects on ONE shared DSF anchor —
pools into a 2,849.6 x 820.6 m / 263,160 m² "deck" with no pavement
evidence to read (``contract_evidence=deck_profile_fallback``), so the
crest test alone called it DECK_CARRIED; its girder clearance measured
2.01 m under the 4.2 m bound and was WARNed-and-emitted anyway; and the
193 hard deck-end pins it produced at one DEM sample + 8 m (183.29 m)
inverted the final band at 650 nodes / 43 pairs, worst 1.996 m.  The
bridge-feature-off arm built clean.

Clause 1 refuses the contract AT CLASSIFICATION (a refused contract emits
nothing — no trench, no corridor, no pins).  Clause 2 is the backstop for
every bad pack datum clause 1 cannot see at classification time: a
deck-end pin is priced against the senior hard anchors on the graph phase
A projects on, through the EAT guard's own predicate and implementation.

Hermetic: synthetic OBJ8 geometry and hand-built graphs; no fixtures, no
DEM files, no X-Plane, no network.
"""
import pytest

import auto_patch.config as cfg
import auto_patch.object_terrain_features as otf
from test_object_terrain_features import (
    _GeometryBuilder, _hard_deck_bridge_geometry, _placement,
)


# ══════════════════════════════════════════════════════════════════════
# CLAUSE 1 — the contract refusal
# ══════════════════════════════════════════════════════════════════════
# The KDFW record's own measurements, read from the pack classification
# sidecar (``o4_object_terrain_classification_+32-098.cache``).
_KDFW_LENGTH_M = 2849.6
_KDFW_WIDTH_M = 820.6
_KDFW_AREA_M2 = 263160.0
_KDFW_CLEARANCE_M = 2.01

# The largest REAL deck anywhere in the corpus sweep (KMCI, 2026-08-16):
# 217.8 x 49.3 m over 1,773 m².  Every bound has orders of margin.
_REAL_LENGTH_M = 217.8
_REAL_WIDTH_M = 49.3
_REAL_AREA_M2 = 1773.0


def _reason(**overrides):
    kwargs = dict(
        contract=otf.DECK_CARRIED,
        contract_evidence=otf.CONTRACT_EVIDENCE_DECK_PROFILE,
        deck_hardness=otf.DECK_HARDNESS_HARD_DECK,
        deck_length_m=_REAL_LENGTH_M,
        deck_width_m=_REAL_WIDTH_M,
        deck_area_m2=_REAL_AREA_M2,
        girder_clearance_m=None,
    )
    kwargs.update(overrides)
    return otf.contract_refusal_reason(**kwargs)


class TestTheKdfwSlabIsRefused:
    def test_the_kdfw_measurements_are_refused(self):
        reason = _reason(deck_length_m=_KDFW_LENGTH_M,
                         deck_width_m=_KDFW_WIDTH_M,
                         deck_area_m2=_KDFW_AREA_M2)
        assert reason is not None
        assert reason.startswith(otf.BRIDGE_REFUSAL_IMPLAUSIBLE_DECK)

    def test_the_reason_carries_its_measurements(self):
        """"Logs the refusal with its measurements" (spec): all three
        bounds are exceeded at KDFW and all three are named, so the
        reader never has to go back to the pack to find out what fired."""
        reason = _reason(deck_length_m=_KDFW_LENGTH_M,
                         deck_width_m=_KDFW_WIDTH_M,
                         deck_area_m2=_KDFW_AREA_M2)
        assert "2,849.6 m" in reason
        assert "820.6 m" in reason
        assert "263,160 m²" in reason

    def test_each_bound_refuses_on_its_own(self):
        """OR, not AND — one implausible dimension is enough."""
        assert _reason(deck_length_m=_KDFW_LENGTH_M) is not None
        assert _reason(deck_width_m=_KDFW_WIDTH_M) is not None
        assert _reason(deck_area_m2=_KDFW_AREA_M2) is not None

    def test_the_bounds_clear_the_largest_real_deck_in_the_corpus(self):
        assert _reason() is None
        assert _REAL_LENGTH_M < otf.BRIDGE_FALLBACK_MAX_DECK_LENGTH_M
        assert _REAL_WIDTH_M < otf.BRIDGE_FALLBACK_MAX_DECK_WIDTH_M
        assert _REAL_AREA_M2 < otf.BRIDGE_FALLBACK_MAX_DECK_AREA_M2


class TestTheScaleLawIsScopedToTheFallback:
    def test_measured_pavement_evidence_is_never_judged_on_size(self):
        """A span whose contract came from MEASURED coverage has real
        evidence; the scale bounds exist to stand in for evidence that is
        missing, so they do not apply where it is present."""
        assert _reason(
            contract_evidence=otf.CONTRACT_EVIDENCE_PAVEMENT_COVERAGE,
            deck_length_m=_KDFW_LENGTH_M, deck_width_m=_KDFW_WIDTH_M,
            deck_area_m2=_KDFW_AREA_M2) is None

    @pytest.mark.parametrize("contract", [otf.TERRAIN_CARRIED,
                                          otf.PROFILE_CARRIED,
                                          otf.AMBIGUOUS])
    def test_only_a_deck_carried_verdict_is_judged(self, contract):
        """The defect is a DECK_CARRIED verdict reached on the crest test
        alone.  A terrain- or profile-carried span pins nothing at a
        pack-authored deck value."""
        assert _reason(contract=contract, deck_length_m=_KDFW_LENGTH_M,
                       deck_width_m=_KDFW_WIDTH_M,
                       deck_area_m2=_KDFW_AREA_M2) is None


class TestTheClearanceGate:
    def test_the_kdfw_clearance_refuses(self):
        reason = _reason(girder_clearance_m=_KDFW_CLEARANCE_M)
        assert reason is not None
        assert reason.startswith(otf.BRIDGE_REFUSAL_CLEARANCE_UNDER_MINIMUM)
        assert "2.01 m" in reason

    def test_clearance_at_the_minimum_is_lawful(self):
        assert _reason(
            girder_clearance_m=float(cfg.BRIDGE_ROAD_CLEARANCE_MINIMUM_M)
        ) is None

    def test_no_underside_plane_refuses_nothing(self):
        """A missing measurement is honest — and the emit-time WARN this
        gate replaces was likewise skipped when no underside plane
        existed."""
        assert _reason(girder_clearance_m=None) is None

    def test_the_caller_passes_the_girder_line_never_the_slab_fallback(
            self):
        """A GIRDER LINE, NOT ANY UNDERSIDE.  The emit-time A10 check
        falls back to the largest-area underside (``ceiling_y_m``) when
        no girder line was found; a REFUSAL may not.  On the cosmetic
        road-bridge class that fallback is soft geometry AT or BELOW
        grade — measured over the whole cached corpus (2026-08-16), all
        three OTHH viaduct records and one KMCI record expose no girder
        line and carry ceilings of −5.84 / −0.93 / −0.49 / −0.92 m, so a
        fallback reading would refuse the bridge FIXTURE airport's REAL
        viaducts on a number that is not a clearance at all."""
        builder = _GeometryBuilder()
        builder.add_horizontal_rectangle(
            -20, 20, -5, 5, 6.0, hardness="hard_deck", segments=8)
        # a below-grade slab underside: a ``ceiling_y_m``, never a girder
        builder.add_horizontal_rectangle(
            -20, 20, -5, 5, -1.0, hardness="", segments=8)
        builder.add_vertical_wall(-20, -5, 5, 0.0, 6.0)
        builder.add_vertical_wall(20, -5, 5, 0.0, 6.0)
        result = otf.classify_object_terrain_features(
            [_placement("bridge/lowslab.obj")],
            {"bridge/lowslab.obj": builder.build()}, pack_root="PACK")
        assert len(result.bridges) == 1, (
            "a deck with no measured girder line is not judged on the "
            "slab underside")
        assert result.bridges[0].clearance_underside_y_m is None
        assert result.bridges[0].ceiling_y_m is not None
        assert result.bridges[0].ceiling_y_m < float(
            cfg.BRIDGE_ROAD_CLEARANCE_MINIMUM_M)

    def test_the_gate_scope_is_the_corridor_set(self):
        """Amendment A10's warning could only ever fire where a corridor
        is dug: DECK_CARRIED spans plus every cosmetic deck
        (``bridges._partition_bridges_for_corridors``).  A span with
        pavement draping across it has no corridor beneath, so its
        underside height limits nothing."""
        low = 1.0
        assert _reason(girder_clearance_m=low) is not None
        assert _reason(contract=otf.TERRAIN_CARRIED,
                       girder_clearance_m=low) is None
        assert _reason(contract=otf.PROFILE_CARRIED,
                       girder_clearance_m=low) is None
        assert _reason(contract=otf.TERRAIN_CARRIED,
                       deck_hardness=otf.DECK_HARDNESS_COSMETIC,
                       girder_clearance_m=low) is not None


def _slab_geometry(half_length_m, half_width_m, deck_y_m,
                   underside_y_m=None):
    """A flat hard deck with walls reaching grade at both ends — the
    minimum shape that survives amendment A4's abutment test, so the
    contract refusal is what fires and not the viaduct guard."""
    builder = _GeometryBuilder()
    builder.add_horizontal_rectangle(
        -half_length_m, half_length_m, -half_width_m, half_width_m,
        deck_y_m, hardness="hard_deck", segments=8,
    )
    if underside_y_m is not None:
        builder.add_horizontal_rectangle(
            -half_length_m, half_length_m, -half_width_m, half_width_m,
            underside_y_m, hardness="", segments=8,
        )
    # The abutment test looks for a grounded vertex within
    # ABUTMENT_GRADE_SEARCH_RADIUS_M of each deck-profile END, which sits
    # on the axis: a wall quad spanning the full width grounds only at
    # its corners, so a wide slab needs a wall reaching the axis too or
    # amendment A4's viaduct guard fires first and the contract refusal
    # is never reached.
    wall_half = min(half_width_m, 20.0)
    for end_x in (-half_length_m, half_length_m):
        builder.add_vertical_wall(
            end_x, -half_width_m, half_width_m, 0.0, deck_y_m)
        builder.add_vertical_wall(
            end_x, -wall_half, wall_half, 0.0, deck_y_m)
    return builder.build()


class TestARefusedContractEmitsNothing:
    """End to end through the classifier: a refused contract produces NO
    bridge record at all, which is the only spelling of "no trench, no
    corridor, no pins" that every downstream emitter obeys — each of them
    reads the classification, and none of them can un-emit."""

    def _classify(self, geometry, resource="bridge/slab.obj"):
        return otf.classify_object_terrain_features(
            [_placement(resource)], {resource: geometry}, pack_root="PACK",
        )

    def test_the_kdfw_shaped_slab_produces_no_bridge_record(self):
        result = self._classify(
            _slab_geometry(1424.8, 410.3, 8.0), "KDFW/inset_slab.obj")
        assert result.bridges == []
        assert len(result.refusals) == 1
        assert result.refusals[0].reason.startswith(
            otf.BRIDGE_REFUSAL_IMPLAUSIBLE_DECK)

    def test_a_scale_refusal_carries_no_deck_to_seat_from(self):
        """The refusal's premise is that this union is NOT a deck, so
        feeding its axis and crest to the post-mesh rigid seat would hand
        the seat the very measurement the refusal rejects.  R12-2's
        ``has_measurable_deck`` then routes the family to the generic
        y-bake — where an unrecognized structure belongs."""
        result = self._classify(
            _slab_geometry(1424.8, 410.3, 8.0), "KDFW/inset_slab.obj")
        assert result.refusals[0].has_measurable_deck is False

    def test_a_clearance_refusal_keeps_its_rigid_seat(self):
        """A clearance refusal is still a bridge — a real deck whose
        modelled crossing is too tight — so the family keeps the R12-2
        rigid deck-top seat, exactly as a refused piered viaduct does.
        Refusing a terrain FEATURE and refusing to know where the deck is
        are two different acts."""
        result = self._classify(_slab_geometry(20.0, 5.0, 6.0,
                                               underside_y_m=3.0))
        assert result.bridges == []
        assert len(result.refusals) == 1
        assert result.refusals[0].reason.startswith(
            otf.BRIDGE_REFUSAL_CLEARANCE_UNDER_MINIMUM)
        assert result.refusals[0].has_measurable_deck is True

    def test_a_refused_structure_takes_no_exclusion(self):
        """Ruling R4 excludes structures whose terrain was ADAPTED to
        them; none was."""
        result = self._classify(
            _slab_geometry(1424.8, 410.3, 8.0), "KDFW/inset_slab.obj")
        assert result.exclusions == []

    def test_the_plausible_evidenced_deck_still_classifies(self):
        """THE TWIN the spec names: OTHH's / KMCI's REAL viaducts keep
        their decks.  A plausible-scale deck whose girder line clears the
        minimum classifies exactly as before — the refusal is a guard on
        the pathological, never a new bar for bridges."""
        result = self._classify(_hard_deck_bridge_geometry(),
                                "bridge/hard.obj")
        assert result.refusals == []
        assert len(result.bridges) == 1
        bridge = result.bridges[0]
        assert bridge.contract == otf.DECK_CARRIED
        assert bridge.deck_length_m == pytest.approx(40.0, abs=1.0)
        assert bridge.clearance_underside_y_m == pytest.approx(4.2, abs=0.2)


# ══════════════════════════════════════════════════════════════════════
# CLAUSE 2 — the deck-pin contradiction guard
# ══════════════════════════════════════════════════════════════════════
# The KDFW shape: a deck pin 8 m above the ground it stands on, a senior
# runway anchor a short taxi route away.
_ANCHOR = 100               # a senior hard runway/seam anchor
#: 100 --0.9-- 201 --0.3-- 200, plus a sibling pair the anchors cannot
#: reach (no bound ⇒ its pin stands: refusal is PER NODE).
_ADJ = {
    _ANCHOR: [(201, 0.9)],
    201: [(_ANCHOR, 0.9), (200, 0.3)],
    200: [(201, 0.3)],
    300: [(301, 0.4)],
    301: [(300, 0.4)],
}


