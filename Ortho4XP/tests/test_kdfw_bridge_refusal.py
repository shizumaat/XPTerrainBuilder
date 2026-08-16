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
from shapely.geometry import Polygon

import auto_patch.config as cfg
import auto_patch.object_terrain_features as otf
from auto_patch.elevation_per_surface.route_profile import solve as SV
from auto_patch.elevation_per_surface.route_profile.law_graph_budget \
    import build_anchor_envelope
from auto_patch.layout import PavementLayout
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


def test_the_classification_cache_version_retires_v17_records():
    """A v17 pickle for an unedited pack still carries the KDFW record —
    the fingerprint covers the PACK and cannot see a classifier rule
    change (the round-5 island-tunnel precedent, version 15)."""
    from auto_patch import object_terrain_assembly as ota
    assert ota._CLASSIFICATION_CACHE_VERSION >= 18


# ══════════════════════════════════════════════════════════════════════
# CLAUSE 2 — the deck-pin contradiction guard
# ══════════════════════════════════════════════════════════════════════
# The KDFW shape: a deck pin 8 m above the ground it stands on, a senior
# runway anchor a short taxi route away.
_ANCHOR = 100               # a senior hard runway/seam anchor
_ANCHOR_V = 175.29          # KDFW's own corridor floor / terrain level
_PIN_V = 183.29             # the deck-end pin value the pack authored
_SEED = 175.30              # the DEM seed the seeder found at the pins
#: 100 --0.9-- 201 --0.3-- 200, plus a sibling pair the anchors cannot
#: reach (no bound ⇒ its pin stands: refusal is PER NODE).
_ADJ = {
    _ANCHOR: [(201, 0.9)],
    201: [(_ANCHOR, 0.9), (200, 0.3)],
    200: [(201, 0.3)],
    300: [(301, 0.4)],
    301: [(300, 0.4)],
}


def _pins():
    return {200: _PIN_V, 201: _PIN_V, 300: _PIN_V}


def _guard_layout(prev_is_hard=False):
    layout = PavementLayout(icao="KDFW", anchor=(32.90, -97.04))
    layout._object_bridge_pin_prev = {
        i: (_SEED, True, prev_is_hard) for i in _pins()}
    layout._object_bridge_pin_idx = _pins()
    layout._seam_pin_idx = set(_pins())
    return layout


class TestTheDeckPinGuard:
    def test_the_pins_that_contradict_the_runway_anchor_are_refused(self):
        refused = SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {**_pins(), _ANCHOR: _ANCHOR_V})
        assert set(refused) == {200, 201}, (
            "the two nodes inside the anchor's reach are refused; the "
            "sibling the anchors cannot reach keeps its pin")
        for i in (200, 201):
            assert refused[i]["side"] == "ceiling"
            assert refused[i]["witness"] == _ANCHOR
        # 175.29 + 0.9 = 176.19 ceiling at 201 ⇒ 7.10 m past it;
        # 175.29 + 1.2 = 176.49 ceiling at 200 ⇒ 6.80 m past it.
        assert refused[201]["excess_m"] == pytest.approx(7.10, abs=1e-4)
        assert refused[200]["excess_m"] == pytest.approx(6.80, abs=1e-4)

    def test_the_predicate_is_the_eat_guards_own_implementation(self):
        """THE SAME PREDICATE THROUGH THE SAME IMPLEMENTATION: exactly
        ``AnchorEnvelope.violation`` on the law-graph budget oracle.  A
        second spelling of "pin + cap·route < anchor" is the
        census-wrapper defect class."""
        env = build_anchor_envelope(_ADJ, {_ANCHOR: _ANCHOR_V})
        refused = SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {_ANCHOR: _ANCHOR_V})
        for i, row in refused.items():
            assert row == env.violation(i, _PIN_V, tol=0.01)
        assert SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {_ANCHOR: _ANCHOR_V}) == \
            SV.eat_pin_contradiction_refusals(
                _pins(), _ADJ, {_ANCHOR: _ANCHOR_V})

    def test_a_deck_pin_never_bounds_itself_or_its_sibling(self):
        assert SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, dict(_pins())) == {}

    def test_a_junior_eat_pin_never_bounds_a_senior_deck_pin(self):
        """Deck pins are seeded BEFORE the EAT rect and outrank it, so an
        EAT pin is passed as ``junior`` and is removed from the anchor set
        exactly as the deck pins themselves are."""
        eat = {_ANCHOR: 240.0}         # a wild EAT pin on the same node
        assert SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {**_pins(), **eat}, junior=eat) == {}
        assert set(SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {**_pins(), **eat})) == {200, 201}, (
            "without the demotion the junior pin would author the bound")

    def test_no_graph_and_no_pins_refuse_nothing(self):
        assert SV.deck_pin_contradiction_refusals(
            {}, _ADJ, {_ANCHOR: _ANCHOR_V}) == {}
        assert SV.deck_pin_contradiction_refusals(
            _pins(), {}, {_ANCHOR: _ANCHOR_V}) == {}
        assert SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {}) == {}


class TestTheGuardIsWiredWhereItCanBePriced:
    """THE WIRING, which no unit call can show."""

    def test_it_sits_after_the_graph_and_before_every_authority(self):
        """The predicate is priced on the graph phase A projects on, and
        a refused pin that reached the flex pass, the runway-class anchor
        registration or the hard-truth publication would already have
        authored a band.  ABOVE the EAT guard, too: deck pins outrank EAT
        pins, so a discredited deck value must be out of ``base_hard``
        before the EAT guard reads it as a senior anchor."""
        import inspect
        src = inspect.getsource(SV.solve_route_profile)
        at_graph = src.index("u_spine_adj_airside = adj_without_pairs")
        at_deck = src.index("deck_pin_contradiction_refusals(")
        at_eat = src.index("eat_pin_contradiction_refusals(")
        at_flex = src.index("_apply_runway_flex_hook(")
        at_truth = src.index("layout._seed_hard_truth_values")
        assert at_graph < at_deck < at_eat < at_flex < at_truth

    def test_every_helper_the_block_calls_exists(self):
        for name in ("deck_pin_contradiction_refusals",
                     "release_refused_deck_pins",
                     "publish_deck_refusal_keys",
                     "format_deck_guard_line"):
            assert callable(getattr(SV, name))

    def test_the_guard_needs_no_env_flag(self):
        """No new switch: the object-bridge feature's own gate is the
        only one, and the guard is part of the feature."""
        import inspect
        assert "environ" not in inspect.getsource(
            SV.deck_pin_contradiction_refusals)
        assert "environ" not in inspect.getsource(
            SV.pin_contradiction_refusals)

    def test_the_line_carries_count_worst_shortfall_and_anchor(self):
        refused = SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {_ANCHOR: _ANCHOR_V})
        worst_node, worst = max(refused.items(),
                                key=lambda r: r[1]["excess_m"])
        worst = dict(worst, pin_m=_PIN_V)
        line = SV.format_deck_guard_line(
            "KDFW", 2, 3, worst_node, worst, _ANCHOR_V)
        assert line.count("\n") == 0, "ONE loud line, not a report"
        assert line.lstrip().startswith("[object-bridge] KDFW:")
        assert "2 of 3 deck-end pin(s) REFUSED" in line
        assert "node 201" in line
        assert "183.290" in line
        assert "7.100 m past its ceiling 176.190" in line
        assert "witness anchor 100 = 175.290" in line
        assert "route budget 0.9000 m" in line


class TestTheRefusedPinIsReleasedToItsSeed:
    def _arm(self, prev_is_hard=False):
        n = 302
        elev = [0.0] * n
        base_hard = [False] * n
        have_initial = [False] * n
        layout = _guard_layout(prev_is_hard)
        for i, v in _pins().items():
            elev[i] = v
            base_hard[i] = True
            have_initial[i] = True
        return layout, elev, base_hard, have_initial

    def test_the_released_node_no_longer_inverts_the_band(self):
        """The pre-registered outcome: after the refusal the node's own
        value sits INSIDE the senior envelope — the inversion the pin
        authored is gone, and it is gone because the pin is, not because
        anything moved a runway."""
        env = build_anchor_envelope(_ADJ, {_ANCHOR: _ANCHOR_V})
        layout, elev, base_hard, have_initial = self._arm()
        refused = SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {_ANCHOR: _ANCHOR_V})
        assert SV.release_refused_deck_pins(
            layout, refused, elev, base_hard, have_initial) == 2
        for i in (200, 201):
            assert elev[i] == pytest.approx(_SEED)
            assert not base_hard[i], "a refused pin is not a truth anchor"
            assert i not in layout._object_bridge_pin_idx
            assert i not in layout._seam_pin_idx
            assert env.violation(i, elev[i], tol=0.01) is None
        # the sibling the guard did not refuse is untouched
        assert elev[300] == pytest.approx(_PIN_V)
        assert base_hard[300]
        assert layout._object_bridge_pin_idx == {300: _PIN_V}
        assert 300 in layout._seam_pin_idx

    def test_a_node_that_arrived_hard_is_handed_back_hard(self):
        """Where the EAT release may assume the node was soft (its pin
        builder skips every already-hard node), a deck pin deliberately
        OVERWRITES a coinciding seam vertex — "pavement value always
        wins" — so the release restores ``is_hard`` and the seam-pin
        protection it found, never a blanket False."""
        layout, elev, base_hard, have_initial = self._arm(prev_is_hard=True)
        refused = SV.deck_pin_contradiction_refusals(
            _pins(), _ADJ, {_ANCHOR: _ANCHOR_V})
        assert SV.release_refused_deck_pins(
            layout, refused, elev, base_hard, have_initial) == 2
        for i in (200, 201):
            assert elev[i] == pytest.approx(_SEED)
            assert base_hard[i], "the senior family's hard value returns"
            assert i in layout._seam_pin_idx

    def test_a_node_with_no_snapshot_is_left_alone(self):
        """Inventing a seed for a node the seeder did not record would be
        the same class of defect the pin itself committed."""
        layout = PavementLayout(icao="KDFW", anchor=(32.90, -97.04))
        layout._object_bridge_pin_prev = {}
        layout._object_bridge_pin_idx = {200: _PIN_V}
        elev = [0.0] * 201
        elev[200] = _PIN_V
        base_hard = [False] * 201
        base_hard[200] = True
        assert SV.release_refused_deck_pins(
            layout, {200: {}}, elev, base_hard, None) == 0
        assert elev[200] == pytest.approx(_PIN_V)
        assert base_hard[200]


class TestTheVerdictIsCarriedByCanonicalPoint:
    """``_seed_elevations`` runs again at every later pass on a GROWN
    layout, from a BUCKET dict that never heard about the refusal.  The
    carried key set is the only thing standing between a refused pin and
    its own resurrection."""

    def test_the_keys_are_points_never_node_indices(self):
        from auto_patch.canonical_points import CanonicalPointRegistry
        layout = PavementLayout(icao="KDFW", anchor=(32.90, -97.04))
        layout.canonical_points = CanonicalPointRegistry()
        nodes = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
        for (x, y) in nodes:
            layout.canonical_points.get_or_add(x, y)
        keys = SV.publish_deck_refusal_keys(layout, {0: {}, 2: {}}, nodes)
        assert keys == layout._object_bridge_pin_refused_keys
        for i in (0, 2):
            assert layout.canonical_points.get(*nodes[i]) in keys
        assert layout.canonical_points.get(*nodes[1]) not in keys

    def test_the_two_pin_families_carry_on_separate_attributes(self):
        """One mechanism, two registers: refusing a deck pin must never
        silence an EAT pin or the reverse."""
        from auto_patch.canonical_points import CanonicalPointRegistry
        layout = PavementLayout(icao="KDFW", anchor=(32.90, -97.04))
        layout.canonical_points = CanonicalPointRegistry()
        nodes = [(0.0, 0.0), (10.0, 0.0)]
        for (x, y) in nodes:
            layout.canonical_points.get_or_add(x, y)
        SV.publish_deck_refusal_keys(layout, {0: {}}, nodes)
        SV.publish_eat_refusal_keys(layout, {1: {}}, nodes)
        assert layout._object_bridge_pin_refused_keys == {
            layout.canonical_points.get(*nodes[0])}
        assert layout._eat_pin_refused_keys == {
            layout.canonical_points.get(*nodes[1])}


class TestTheSeederHonoursTheCarriedVerdict:
    """The seeder side of clause 2 — the snapshot it must publish and the
    refusal it must obey — exercised on the real ``_seed_elevations``."""

    def _layout_with_deck_pins(self, refused_keys=None):
        from auto_patch.canonical_points import CanonicalPointRegistry
        from auto_patch.layout import BuiltShape, ROLE_APRON
        from auto_patch.layout import SHARED_VERTEX_TOL_M
        layout = PavementLayout(icao="KDFW", anchor=(32.90, -97.04))
        layout.canonical_points = CanonicalPointRegistry()
        ring = [(0.0, 0.0), (60.0, 0.0), (60.0, 40.0), (0.0, 40.0)]
        layout.shapes = [BuiltShape(
            polygon=Polygon(ring), role=ROLE_APRON, ref="apron1")]
        scale = 1.0 / SHARED_VERTEX_TOL_M
        layout._object_bridge_pin_values = {
            (int(round(x * scale)), int(round(y * scale))): _PIN_V
            for (x, y) in ring[:2]
        }
        if refused_keys is not None:
            layout._object_bridge_pin_refused_keys = refused_keys
        return layout, ring

    def _seed(self, layout):
        from auto_patch.elevation_per_surface import solver_primitives as SP
        nodes, bucket_to_idx = SP._build_node_list(layout)
        elev, is_hard, have_initial = SP._seed_elevations(
            layout, nodes, bucket_to_idx)
        return nodes, bucket_to_idx, elev, is_hard

    def test_the_seeder_publishes_the_pin_map_and_the_snapshot(self):
        layout, ring = self._layout_with_deck_pins()
        _nodes, b2i, elev, is_hard = self._seed(layout)
        idx = {b2i[layout.canonical_points.get(x, y)] for (x, y) in ring[:2]}
        assert set(layout._object_bridge_pin_idx) == idx
        assert set(layout._object_bridge_pin_prev) == idx
        for i in idx:
            assert elev[i] == pytest.approx(_PIN_V)
            assert is_hard[i]
            assert len(layout._object_bridge_pin_prev[i]) == 3, (
                "elev, have_initial AND is_hard — a deck pin may land on "
                "a node an earlier family already hardened")

    def test_a_carried_verdict_makes_the_seeder_skip_the_node(self):
        layout, ring = self._layout_with_deck_pins()
        # price the verdict on the first pass, then re-seed with it
        self._seed(layout)
        key = layout.canonical_points.get(*ring[0])
        layout2, ring2 = self._layout_with_deck_pins(refused_keys={key})
        layout2.canonical_points = layout.canonical_points
        _nodes2, b2i2, _elev2, hard2 = self._seed(layout2)
        skipped = b2i2[layout2.canonical_points.get(*ring2[0])]
        kept = b2i2[layout2.canonical_points.get(*ring2[1])]
        assert not hard2[skipped], (
            "a node the guard refused must never be re-pinned by a later "
            "pass — the writeback clamp rescuing it is not the law "
            "holding")
        assert skipped not in layout2._object_bridge_pin_idx
        assert hard2[kept]
        assert kept in layout2._object_bridge_pin_idx

    def test_no_verdict_carries_nothing(self):
        layout, ring = self._layout_with_deck_pins()
        _nodes, b2i, _elev, hard = self._seed(layout)
        assert not hasattr(layout, "_object_bridge_pin_refused_keys")
        for (x, y) in ring[:2]:
            assert hard[b2i[layout.canonical_points.get(x, y)]]
