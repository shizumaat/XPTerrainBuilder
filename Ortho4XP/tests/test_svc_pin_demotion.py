"""AIRSIDE ZERO air6 — the service-pin mutual-consistency demotion.

A law edge both of whose endpoints are held by the service pin registers
(``svc_free_end`` / ``svc_profile`` / ``svc_mouth``) and whose HELD
values already violate the edge is a contradiction minted into the hard
set: nothing downstream may move either endpoint, so the projections
tally it forever (the both-hard residue the 2026-09-01 HECA anatomy
measured at 759 solve-exit rows, every material one service-held).

The demotion releases the JUNIOR endpoint's membership (mouth > profile
> free-end; equal rank demotes the higher index), values untouched, at
the single derivation seam both consumers resolve through (layout attrs
for the solve's ``yield_hard``, store keysets for the final pass).
"""
import os

import pytest

from auto_patch.elevation_per_surface.route_profile.solve import (
    _demote_contradicted_service_pins)
from auto_patch.elevation_per_surface.node_space import store_of


class _FakeLayout:
    pass


def _mk(free_end=(), mouth=(), profile=(), keysets=None):
    lay = _FakeLayout()
    lay._svc_free_end_idx = set(free_end)
    lay._svc_mouth_prox_idx = set(mouth)
    lay._svc_profile_idx = set(profile)
    st = store_of(lay)
    for name, keys in (keysets or {}).items():
        st.mint(name, "keyset", set(keys))
    return lay


def test_junior_free_end_demoted_against_profile():
    # profile node 1 @110.8, free-end tie node 2 @104.3, budget 0.32 —
    # the measured HECA worst site's shape.
    b2i = {"k1": 1, "k2": 2}
    lay = _mk(free_end=[2], profile=[1],
              keysets={"svc_free_end": {"k2"}, "svc_profile": {"k1"}})
    elev = [0.0, 110.8, 104.3]
    joint = [{"edges": [(1, 2, 0.32)]}]
    rep = _demote_contradicted_service_pins(lay, "TEST", elev, 3, joint, b2i)
    assert rep["pairs"] == 1
    assert rep["demoted"] == {"svc_free_end": 1, "svc_mouth": 0,
                              "svc_profile": 0}
    assert rep["worst_excess_m"] == pytest.approx(6.18, abs=0.01)
    # membership released at BOTH seams; the value is untouched.
    assert lay._svc_free_end_idx == set()
    assert lay._svc_profile_idx == {1}
    assert store_of(lay).raw("svc_free_end") == set()
    assert store_of(lay).raw("svc_profile") == {"k1"}
    assert elev[2] == 104.3


def test_equal_rank_demotes_higher_index_only():
    b2i = {"a": 4, "b": 7}
    lay = _mk(free_end=[4, 7], keysets={"svc_free_end": {"a", "b"}})
    elev = [0.0] * 8
    elev[4], elev[7] = 100.0, 101.0
    joint = [{"edges": [(4, 7, 0.10)]}]
    rep = _demote_contradicted_service_pins(lay, "TEST", elev, 8, joint, b2i)
    assert rep["demoted"]["svc_free_end"] == 1
    assert lay._svc_free_end_idx == {4}
    assert store_of(lay).raw("svc_free_end") == {"a"}


def test_lawful_and_submaterial_pairs_keep_their_pins():
    b2i = {}
    lay = _mk(free_end=[1, 2], profile=[3])
    elev = [0.0, 100.0, 100.05, 100.055]
    joint = [{"edges": [(1, 2, 0.10),          # lawful
                        (2, 3, 0.005)]}]       # 0.005 excess < materiality
    rep = _demote_contradicted_service_pins(lay, "TEST", elev, 4, joint, b2i)
    assert rep["pairs"] == 0
    assert lay._svc_free_end_idx == {1, 2}
    assert lay._svc_profile_idx == {3}


def test_interval_edges_and_non_register_nodes_ignored():
    b2i = {}
    lay = _mk(profile=[1, 2])
    elev = [0.0, 100.0, 108.0, 90.0]
    joint = [{"edges": [(1, 2, -0.5, 0.5),     # interval, violated
                        (1, 3, 0.10)]}]        # 3 not register-held
    rep = _demote_contradicted_service_pins(lay, "TEST", elev, 4, joint, b2i)
    # interval pair demotes (equal rank -> higher index); the pair to a
    # non-held node never counts.
    assert rep["pairs"] == 1
    assert lay._svc_profile_idx == {1}


def test_gate_off_is_a_noop(monkeypatch):
    monkeypatch.setenv("O4_SVC_PIN_DEMOTION", "0")
    b2i = {}
    lay = _mk(free_end=[1], profile=[2])
    elev = [0.0, 100.0, 110.0]
    joint = [{"edges": [(1, 2, 0.10)]}]
    rep = _demote_contradicted_service_pins(lay, "TEST", elev, 3, joint, b2i)
    assert rep.get("gated_off") is True
    assert lay._svc_free_end_idx == {1}
    assert lay._svc_profile_idx == {2}


def test_mouth_seat_is_senior_to_profile_and_free_end():
    b2i = {}
    lay = _mk(mouth=[1], profile=[2], free_end=[3])
    elev = [0.0, 100.0, 105.0, 111.0]
    joint = [{"edges": [(1, 2, 0.10), (2, 3, 0.10)]}]
    rep = _demote_contradicted_service_pins(lay, "TEST", elev, 4, joint, b2i)
    assert lay._svc_mouth_prox_idx == {1}
    # profile 2 demoted against the mouth; free-end 3 demoted against the
    # (still-ranked-at-entry) profile — rank is taken once, at entry.
    assert rep["demoted"]["svc_profile"] == 1
    assert rep["demoted"]["svc_free_end"] == 1
