"""Unit tests for auto_patch.elevation_per_surface.node_space.

The store is the U1 transport refactor's single keyed-artifact home: an
artifact is minted ONCE per build against canonical-point keys and
resolved into a pass's index space through the ``view_*`` resolvers.
These tests pin the two things a transport refactor can silently break:

* the **single-construction audit trail** (``mint`` / ``mint_count`` and
  the incremental-writer ``open_map`` identity contract), and
* **per-site alias-collision + coverage semantics** — the seat-box
  ``intersect`` rule is checked against a literal replay of the OLD
  resolve loop from ``route_profile/solve.py`` (the bounded-yield seat
  box mapping, ~line 1367) on the same synthetic payload, so the view
  is proven to reproduce values AND coverage, not merely to look right.

Pure in-memory: no DEM, no layout build, no X-Plane install.
"""
from __future__ import annotations

import types

import pytest

from auto_patch.elevation_per_surface.node_space import (
    NodeSpaceStore,
    store_of,
)


# ── the pre-migration resolve loop, replayed verbatim ──────────────────
def _legacy_seat_box_idx(payload, b2i, n):
    """The OLD bounded-yield seat-box mapping from ``solve.py``.

    Transcribed from the pre-U1 loop (``_seat_boxes`` is canonical-key
    keyed; map into THIS solve's index space, intersecting keys that
    alias one node — tightest per side).  Kept structurally identical to
    the original so the comparison in
    :meth:`TestViewIntervalIntersect.test_matches_legacy_seat_box_loop`
    is a real replay and not a paraphrase.
    """
    out = {}
    for key, box in payload.items():
        i = b2i.get(key)
        if i is None or i >= n:
            continue
        prev = out.get(i)
        out[i] = (box if prev is None
                  else (max(prev[0], box[0]), min(prev[1], box[1])))
    return out


# A payload exercising every branch of the loop above:
#   "a"/"b" alias index 0 (collision), "c" resolves alone,
#   "d" is absent from b2i (i is None -> skip),
#   "e" resolves to an index >= n (out-of-range -> skip).
_SEAT_PAYLOAD = {
    "a": (10.0, 20.0),
    "b": (12.0, 18.0),
    "c": (5.0, 6.0),
    "d": (0.0, 100.0),
    "e": (-1.0, 1.0),
}
_SEAT_B2I = {"a": 0, "b": 0, "c": 1, "e": 7}
_SEAT_N = 3


class TestMint:
    """Single-construction contract and kind validation."""

    def test_returns_payload_and_stores_it(self):
        store = NodeSpaceStore()
        payload = {"k": (1.0, 2.0)}
        assert store.mint("seat_boxes", "interval", payload) is payload
        assert store.has("seat_boxes")
        assert store.raw("seat_boxes") is payload
        assert store.mint_count("seat_boxes") == 1

    def test_double_mint_raises(self):
        store = NodeSpaceStore()
        store.mint("seat_boxes", "interval", {"k": (1.0, 2.0)})
        with pytest.raises(ValueError):
            store.mint("seat_boxes", "interval", {"k": (3.0, 4.0)})
        # The failed mint left the first payload (and its count) intact.
        assert store.raw("seat_boxes") == {"k": (1.0, 2.0)}
        assert store.mint_count("seat_boxes") == 1

    def test_replace_succeeds_and_bumps_mint_count(self):
        store = NodeSpaceStore()
        store.mint("seat_boxes", "interval", {"k": (1.0, 2.0)})
        second = {"k": (3.0, 4.0)}
        assert store.mint(
            "seat_boxes", "interval", second, replace=True) is second
        assert store.raw("seat_boxes") is second
        assert store.mint_count("seat_boxes") == 2

    def test_kind_mismatch_raises_even_with_replace(self):
        store = NodeSpaceStore()
        store.mint("seat_boxes", "interval", {"k": (1.0, 2.0)})
        with pytest.raises(ValueError):
            store.mint("seat_boxes", "scalar", {"k": 1.0}, replace=True)
        assert store.mint_count("seat_boxes") == 1
        assert store.raw("seat_boxes") == {"k": (1.0, 2.0)}

    def test_unknown_kind_raises(self):
        store = NodeSpaceStore()
        with pytest.raises(ValueError):
            store.mint("whatever", "vector", {"k": 1.0})
        assert not store.has("whatever")
        assert store.mint_count("whatever") == 0

    @pytest.mark.parametrize(
        "kind,payload",
        [("scalar", {"k": 1.0}),
         ("interval", {"k": (1.0, 2.0)}),
         ("keyset", {"k"}),
         ("relation", {"k": "j"})],
    )
    def test_every_declared_kind_is_accepted(self, kind, payload):
        store = NodeSpaceStore()
        assert store.mint("art", kind, payload) is payload

    def test_absent_name_reads_as_missing(self):
        store = NodeSpaceStore()
        assert not store.has("nope")
        assert store.raw("nope") is None
        assert store.mint_count("nope") == 0


class TestOpenMap:
    """The incremental-writer identity contract."""

    def test_first_call_creates_empty_dict(self):
        store = NodeSpaceStore()
        payload = store.open_map("seat_boxes", "interval")
        assert payload == {}
        assert store.raw("seat_boxes") is payload
        assert store.mint_count("seat_boxes") == 1

    def test_second_call_without_reset_is_the_same_object(self):
        store = NodeSpaceStore()
        first = store.open_map("seat_boxes", "interval")
        first["k"] = (1.0, 2.0)
        second = store.open_map("seat_boxes", "interval")
        # Later producers of the same solve MERGE into the live payload:
        # object identity, not just equality, is the contract.
        assert second is first
        assert second["k"] == (1.0, 2.0)
        second["j"] = (3.0, 4.0)
        assert first == {"k": (1.0, 2.0), "j": (3.0, 4.0)}
        # Get-or-create must not count as a re-mint.
        assert store.mint_count("seat_boxes") == 1

    def test_reset_returns_a_fresh_empty_dict_and_bumps_count(self):
        store = NodeSpaceStore()
        first = store.open_map("seat_boxes", "interval")
        first["k"] = (1.0, 2.0)
        second = store.open_map("seat_boxes", "interval", reset=True)
        assert second is not first
        assert second == {}
        assert store.raw("seat_boxes") is second
        assert store.mint_count("seat_boxes") == 2
        # The old payload is detached, not aliased.
        second["j"] = (3.0, 4.0)
        assert first == {"k": (1.0, 2.0)}

    def test_non_dict_payload_raises(self):
        store = NodeSpaceStore()
        store.mint("spine_keys", "keyset", {"a", "b"})
        with pytest.raises(ValueError):
            store.open_map("spine_keys", "keyset")

    def test_reset_recovers_a_non_dict_payload(self):
        # reset short-circuits before the isinstance guard, so a solve
        # whose first producer resets is never blocked by a stale kind.
        store = NodeSpaceStore()
        store.mint("spine_keys", "keyset", {"a", "b"})
        fresh = store.open_map("spine_keys", "keyset", reset=True)
        assert fresh == {}
        assert store.mint_count("spine_keys") == 2


class TestViewIntervalIntersect:
    """Seat-box semantics: tightest per side, with the legacy replay."""

    def test_matches_legacy_seat_box_loop(self):
        store = NodeSpaceStore()
        store.mint("seat_boxes", "interval", dict(_SEAT_PAYLOAD))
        view = store.view_interval(
            "seat_boxes", _SEAT_B2I, _SEAT_N, combine="intersect")
        legacy = _legacy_seat_box_idx(_SEAT_PAYLOAD, _SEAT_B2I, _SEAT_N)
        assert view == legacy
        # Pin the expected values too, so a regression in BOTH the view
        # and the replay cannot pass silently.
        assert view == {0: (12.0, 18.0), 1: (5.0, 6.0)}

    def test_skips_unresolved_and_out_of_range_keys(self):
        store = NodeSpaceStore()
        store.mint("seat_boxes", "interval", dict(_SEAT_PAYLOAD))
        view = store.view_interval(
            "seat_boxes", _SEAT_B2I, _SEAT_N, combine="intersect")
        # "d" has no b2i entry; "e" resolves to 7 >= n=3.
        assert set(view) == {0, 1}
        assert 7 not in view
        assert all(i < _SEAT_N for i in view)

    def test_intersect_is_order_independent(self):
        store_a = NodeSpaceStore()
        store_b = NodeSpaceStore()
        store_a.mint("seat_boxes", "interval",
                     {"a": (10.0, 20.0), "b": (12.0, 18.0)})
        store_b.mint("seat_boxes", "interval",
                     {"b": (12.0, 18.0), "a": (10.0, 20.0)})
        b2i, n = {"a": 0, "b": 0}, 1
        assert (store_a.view_interval("seat_boxes", b2i, n,
                                      combine="intersect")
                == store_b.view_interval("seat_boxes", b2i, n,
                                         combine="intersect")
                == {0: (12.0, 18.0)})

    def test_absent_artifact_is_empty_dict(self):
        store = NodeSpaceStore()
        assert store.view_interval("nope", _SEAT_B2I, _SEAT_N,
                                   combine="intersect") == {}

    def test_unknown_combine_mode_raises(self):
        store = NodeSpaceStore()
        store.mint("seat_boxes", "interval", dict(_SEAT_PAYLOAD))
        with pytest.raises(ValueError):
            store.view_interval("seat_boxes", _SEAT_B2I, _SEAT_N,
                                combine="union")


class TestViewIntervalLast:
    """Band semantics: last-write-wins in mint insertion order."""

    # Boxes chosen so "last" and "intersect" DISAGREE on the collision
    # (last -> (12, 25); intersect -> (12, 20)); a payload whose last
    # box happens to be the tightest one cannot tell the modes apart.
    _PAYLOAD = {"a": (10.0, 20.0), "b": (12.0, 25.0)}

    def test_collision_keeps_the_last_minted_key(self):
        store = NodeSpaceStore()
        # Insertion order chosen deliberately: "b" is minted last.
        store.mint("env_band", "interval", dict(self._PAYLOAD))
        b2i, n = {"a": 0, "b": 0}, 1
        assert store.view_interval(
            "env_band", b2i, n, combine="last") == {0: (12.0, 25.0)}
        assert store.view_interval(
            "env_band", b2i, n, combine="intersect") == {0: (12.0, 20.0)}

    def test_result_is_order_dependent(self):
        forward = NodeSpaceStore()
        reverse = NodeSpaceStore()
        forward.mint("env_band", "interval",
                     {"a": (10.0, 20.0), "b": (12.0, 25.0)})
        reverse.mint("env_band", "interval",
                     {"b": (12.0, 25.0), "a": (10.0, 20.0)})
        b2i, n = {"a": 0, "b": 0}, 1
        fwd = forward.view_interval("env_band", b2i, n, combine="last")
        rev = reverse.view_interval("env_band", b2i, n, combine="last")
        assert fwd == {0: (12.0, 25.0)}   # "b" last
        assert rev == {0: (10.0, 20.0)}   # "a" last
        assert fwd != rev                 # order-dependence, explicitly

    def test_last_is_the_default_combine(self):
        store = NodeSpaceStore()
        store.mint("env_band", "interval", dict(self._PAYLOAD))
        b2i, n = {"a": 0, "b": 0}, 1
        default = store.view_interval("env_band", b2i, n)
        assert default == store.view_interval(
            "env_band", b2i, n, combine="last")
        assert default != store.view_interval(
            "env_band", b2i, n, combine="intersect")


class TestCrownLift:
    """z' = z + crown is applied once, in the resolver, per index."""

    def test_crown_adds_to_both_sides(self):
        store = NodeSpaceStore()
        store.mint("env_band", "interval", {"a": (10.0, 20.0)})
        assert store.view_interval(
            "env_band", {"a": 0}, 1,
            crown_of={0: 3.5}) == {0: (13.5, 23.5)}

    def test_missing_crown_entry_is_zero_lift(self):
        store = NodeSpaceStore()
        store.mint("env_band", "interval", {"a": (10.0, 20.0),
                                            "c": (5.0, 6.0)})
        view = store.view_interval("env_band", {"a": 0, "c": 1}, 2,
                                   crown_of={0: 3.5})
        assert view == {0: (13.5, 23.5), 1: (5.0, 6.0)}

    def test_lift_then_intersect_equals_intersect_then_lift(self):
        # Aliased keys sharing ONE index share ONE crown, so the lift
        # commutes with max/min: this is what lets the resolver lift
        # before combining without changing any call site's values.
        store = NodeSpaceStore()
        store.mint("seat_boxes", "interval",
                   {"a": (10.0, 20.0), "b": (12.0, 18.0)})
        b2i, n, crown = {"a": 0, "b": 0}, 1, {0: 3.5}
        lift_then_intersect = store.view_interval(
            "seat_boxes", b2i, n, crown_of=crown, combine="intersect")
        intersect_then_lift = {
            i: (lo + crown[i], hi + crown[i])
            for i, (lo, hi) in store.view_interval(
                "seat_boxes", b2i, n, combine="intersect").items()}
        assert lift_then_intersect == intersect_then_lift == {0: (15.5, 21.5)}

    def test_crown_commutes_with_last_write_wins(self):
        store = NodeSpaceStore()
        # "b" is last but NOT the tightest box, so this also pins that
        # the lift did not quietly turn the band view into an intersect.
        store.mint("env_band", "interval",
                   {"a": (10.0, 20.0), "b": (12.0, 25.0)})
        b2i, n, crown = {"a": 0, "b": 0}, 1, {0: -2.0}
        lifted = store.view_interval("env_band", b2i, n, crown_of=crown)
        plain = {i: (lo + crown[i], hi + crown[i])
                 for i, (lo, hi) in store.view_interval(
                     "env_band", b2i, n).items()}
        assert lifted == plain == {0: (10.0, 23.0)}


class TestViewPositionalInterval:
    """The envelope's shape: a length-n list, None where unresolved."""

    def test_absent_artifact_is_none(self):
        store = NodeSpaceStore()
        assert store.view_positional_interval("nope", {"a": 0}, 3) is None

    def test_empty_payload_is_none(self):
        # Load-bearing: "no carry => pair closure" at the envelope call
        # site keys on None, NOT on an all-None list.
        store = NodeSpaceStore()
        store.mint("rod_carry", "interval", {})
        assert store.has("rod_carry")
        assert store.view_positional_interval("rod_carry", {"a": 0}, 3) is None
        # An open_map'd but never-written payload must read the same way.
        store2 = NodeSpaceStore()
        store2.open_map("rod_carry", "interval")
        assert store2.view_positional_interval(
            "rod_carry", {"a": 0}, 3) is None

    def test_length_is_n_with_none_for_unresolved(self):
        store = NodeSpaceStore()
        store.mint("rod_carry", "interval", dict(_SEAT_PAYLOAD))
        out = store.view_positional_interval(
            "rod_carry", _SEAT_B2I, _SEAT_N)
        assert isinstance(out, list)
        assert len(out) == _SEAT_N
        # index 2 was never keyed; "d"/"e" were skipped entirely.
        assert out[2] is None
        assert out[1] == (5.0, 6.0)
        assert out[0] is not None

    def test_alias_collision_is_last_write_wins(self):
        store = NodeSpaceStore()
        # (12, 25) is the LAST box, not the tightest — so a positional
        # view that quietly intersected would read (12, 20) and fail.
        store.mint("rod_carry", "interval",
                   {"a": (10.0, 20.0), "b": (12.0, 25.0)})
        assert store.view_positional_interval(
            "rod_carry", {"a": 0, "b": 0}, 1) == [(12.0, 25.0)]

    def test_crown_is_applied(self):
        store = NodeSpaceStore()
        store.mint("rod_carry", "interval", {"a": (10.0, 20.0),
                                             "c": (5.0, 6.0)})
        assert store.view_positional_interval(
            "rod_carry", {"a": 0, "c": 1}, 3,
            crown_of={0: 3.5}) == [(13.5, 23.5), (5.0, 6.0), None]


class TestViewKeyset:
    """Spine-crossing identity: keys in, resolved indices out."""

    def test_absent_artifact_is_empty_set(self):
        store = NodeSpaceStore()
        assert store.view_keyset("nope", {"a": 0}, 3) == set()

    def test_empty_payload_is_empty_set(self):
        store = NodeSpaceStore()
        store.mint("spine_keys", "keyset", set())
        assert store.view_keyset("spine_keys", {"a": 0}, 3) == set()

    def test_resolves_only_present_and_in_range_keys(self):
        store = NodeSpaceStore()
        store.mint("spine_keys", "keyset", {"a", "b", "c", "d", "e"})
        # "d" is absent from b2i; "e" resolves to 7 >= n=3.
        assert store.view_keyset("spine_keys", _SEAT_B2I, _SEAT_N) == {0, 1}

    def test_aliased_keys_collapse_to_one_index(self):
        store = NodeSpaceStore()
        store.mint("spine_keys", "keyset", {"a", "b"})
        assert store.view_keyset("spine_keys", {"a": 0, "b": 0}, 1) == {0}


class TestViewRelation:
    """Pad-face weld contact -> pad node, with per-side guards."""

    def test_absent_artifact_is_empty_dict(self):
        store = NodeSpaceStore()
        assert store.view_relation("nope", {"a": 0}, 3) == {}

    def test_left_must_resolve_and_be_in_range(self):
        store = NodeSpaceStore()
        store.mint("pad_weld", "relation",
                   {"a": "c",      # left 0, right 1     -> kept
                    "d": "c",      # left absent          -> dropped
                    "e": "c"})     # left 7 >= n=3        -> dropped
        assert store.view_relation("pad_weld", _SEAT_B2I, _SEAT_N) == {0: 1}

    def test_unresolved_right_side_is_none(self):
        store = NodeSpaceStore()
        store.mint("pad_weld", "relation",
                   {"a": "d",      # right absent from b2i
                    "c": "e"})     # right resolves to 7 >= n=3
        assert store.view_relation(
            "pad_weld", _SEAT_B2I, _SEAT_N) == {0: None, 1: None}

    def test_both_sides_resolve_to_indices(self):
        store = NodeSpaceStore()
        store.mint("pad_weld", "relation", {"a": "c", "c": "a"})
        assert store.view_relation(
            "pad_weld", _SEAT_B2I, _SEAT_N) == {0: 1, 1: 0}

    def test_index_zero_right_side_is_not_confused_with_none(self):
        store = NodeSpaceStore()
        store.mint("pad_weld", "relation", {"c": "a"})
        view = store.view_relation("pad_weld", _SEAT_B2I, _SEAT_N)
        assert view == {1: 0}
        assert view[1] is not None


class TestStoreOf:
    """One store per build object, created on first use."""

    def test_same_object_gets_the_same_store(self):
        layout = types.SimpleNamespace()
        first = store_of(layout)
        assert isinstance(first, NodeSpaceStore)
        assert store_of(layout) is first

    def test_payloads_survive_across_store_of_calls(self):
        layout = types.SimpleNamespace()
        store_of(layout).mint("env_band", "interval", {"a": (1.0, 2.0)})
        assert store_of(layout).raw("env_band") == {"a": (1.0, 2.0)}

    def test_fresh_object_gets_a_fresh_store(self):
        a = types.SimpleNamespace()
        b = types.SimpleNamespace()
        store_a = store_of(a)
        store_a.mint("env_band", "interval", {"a": (1.0, 2.0)})
        store_b = store_of(b)
        assert store_b is not store_a
        assert not store_b.has("env_band")

    def test_store_is_attached_to_the_object(self):
        layout = types.SimpleNamespace()
        assert getattr(layout, "_node_space", None) is None
        store = store_of(layout)
        assert layout._node_space is store


class TestSingleConstructionAudit:
    """``mint_count`` is the audit trail a build-level test asserts on."""

    def test_two_replace_mints_count_two(self):
        store = NodeSpaceStore()
        store.mint("env_band", "interval", {"a": (1.0, 2.0)}, replace=True)
        store.mint("env_band", "interval", {"a": (3.0, 4.0)}, replace=True)
        assert store.mint_count("env_band") == 2

    def test_single_construction_counts_one(self):
        store = NodeSpaceStore()
        store.mint("env_band", "interval", {"a": (1.0, 2.0)})
        assert store.mint_count("env_band") == 1

    def test_counts_are_per_name(self):
        store = NodeSpaceStore()
        store.mint("env_band", "interval", {"a": (1.0, 2.0)}, replace=True)
        store.mint("env_band", "interval", {"a": (3.0, 4.0)}, replace=True)
        store.mint("seat_boxes", "interval", {"a": (5.0, 6.0)})
        assert store.mint_count("env_band") == 2
        assert store.mint_count("seat_boxes") == 1

    def test_incremental_writers_count_once_per_reset(self):
        # A whole solve's worth of producers merging into one map is
        # still ONE construction; only a reset re-mints.
        store = NodeSpaceStore()
        for _ in range(5):
            store.open_map("seat_boxes", "interval")["k"] = (1.0, 2.0)
        assert store.mint_count("seat_boxes") == 1
        store.open_map("seat_boxes", "interval", reset=True)
        assert store.mint_count("seat_boxes") == 2


# ── view_scalar (R1 reference field's resolver) ────────────────────────
# Added for step R1/P2: the field is a scalar artifact minted once by
# canonical key and resolved through this view.  Semantics are pinned to
# match ``view_interval`` exactly, since both feed the same passes.
def test_view_scalar_round_trip() -> None:
    """A minted scalar resolves key -> index with values intact."""
    st = NodeSpaceStore()
    st.mint("reference_field", "scalar", {"ka": 10.0, "kb": 20.5})
    assert st.view_scalar("reference_field", {"ka": 0, "kb": 1}, 2) == {
        0: 10.0, 1: 20.5}


def test_view_scalar_absent_artifact_is_empty() -> None:
    """An unminted name resolves to {} rather than raising."""
    assert NodeSpaceStore().view_scalar("nope", {"ka": 0}, 1) == {}


def test_view_scalar_skips_unknown_and_out_of_range_keys() -> None:
    """Keys absent from b2i, or resolving to >= n, are dropped."""
    st = NodeSpaceStore()
    st.mint("f", "scalar", {"ka": 1.0, "unknown": 2.0, "far": 3.0})
    assert st.view_scalar("f", {"ka": 0, "far": 7}, 2) == {0: 1.0}


def test_view_scalar_crown_lift_matches_hand_lift() -> None:
    """crown_of lifts into z' = z + crown, per index, like view_interval."""
    st = NodeSpaceStore()
    st.mint("f", "scalar", {"ka": 100.0, "kb": 200.0})
    b2i = {"ka": 0, "kb": 1}
    got = st.view_scalar("f", b2i, 2, crown_of={0: 0.25})
    assert got == {0: 100.25, 1: 200.0}
    # identical to lifting the unlifted view by hand
    plain = st.view_scalar("f", b2i, 2)
    assert got == {i: v + {0: 0.25}.get(i, 0.0) for i, v in plain.items()}


def test_view_scalar_coerces_to_float() -> None:
    """Integer payloads resolve as floats (the field is float-valued)."""
    st = NodeSpaceStore()
    st.mint("f", "scalar", {"ka": 7})
    out = st.view_scalar("f", {"ka": 0}, 1)
    assert out == {0: 7.0} and isinstance(out[0], float)


def test_view_scalar_empty_payload_reads_as_absent() -> None:
    """Minted-empty reads as absent through the view (pinned U1 behavior;
    ``has``/``mint_count`` still distinguish it)."""
    st = NodeSpaceStore()
    st.mint("f", "scalar", {})
    assert st.view_scalar("f", {"ka": 0}, 1) == {}
    assert st.has("f") and st.mint_count("f") == 1
