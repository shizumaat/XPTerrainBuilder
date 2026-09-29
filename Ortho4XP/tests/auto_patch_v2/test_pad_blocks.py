"""Flat-pad spec §2 twins (issue #111, RULINGS 2026-09-30f): the hold
interval, the chain propagation and the greedy block partition on a
synthetic frontage."""
from __future__ import annotations

import numpy as np

from auto_patch_v2.planar.pad_blocks import (chain_propagate, greedy_blocks,
                                             hold_interval)

A = 0.015            # the apron hard cap
GRADE = 0.01         # a 1 % frontage


def _frontage_case(depth_m: float, span_m: float = 600.0, atom_m: float = 50.0):
    """A straight frontage rising at 1 %; one taxi edge vertex ``q`` in front
    of every metre of it at ``depth_m``, whose ground is the frontage's.
    Atoms of ``atom_m`` each, ordered along the frontage."""
    xs = np.arange(0.0, span_m, 5.0)
    contacts = np.c_[xs, np.zeros_like(xs)]
    Q = np.c_[xs, np.full_like(xs, depth_m)]
    Tq = GRADE * xs
    own = (xs // atom_m).astype(int)
    tau = np.zeros(len(xs))

    def iv(atoms):
        m = np.isin(own, atoms)
        C = contacts[m]
        d = np.min(np.hypot(Q[:, None, 0] - C[None, :, 0], Q[:, None, 1] - C[None, :, 1]),
                   axis=1)
        return hold_interval(Tq, d, tau, A)
    return sorted(set(own.tolist())), iv


def test_hold_interval_is_the_intersection():
    lo, hi = hold_interval(np.array([10.0, 12.0]), np.array([100.0, 100.0]),
                           np.array([0.0, 0.0]), A)
    assert (lo, hi) == (12.0 - 1.5, 10.0 + 1.5)
    assert hold_interval(np.array([]), np.array([]), np.array([]), A)[0] == -np.inf


def test_deep_apron_one_block_shallow_apron_splits():
    # 600 m at 1 % = 6 m of relief.  With a q in front of every metre the
    # q set beyond a block's ends binds too (the cone): ℓ_max =
    # 2·d·sqrt(a² − g²) / g, i.e. 2.236·d here (the spec's 2·a·d/g = 3·d
    # is the bound with q only in front of the block)
    order, iv = _frontage_case(depth_m=300.0)        # ℓ_max 671 m > 600 m
    lo, hi = iv(order)
    assert lo <= hi
    assert greedy_blocks(order, iv) == [order]
    order, iv = _frontage_case(depth_m=100.0)        # ℓ_max 224 m -> 3 x 200 m
    blocks = greedy_blocks(order, iv)
    assert len(blocks) == 3
    # every block is feasible alone, and no atom is split
    assert all(iv(b)[0] <= iv(b)[1] for b in blocks)
    assert sorted(a for b in blocks for a in b) == order


def test_chain_bounds_consecutive_datums():
    iv = [(0.0, 1.0), (3.0, 4.0)]
    # a 100 m gap carries 1.5 m: block 0 is pushed to [1.5, 1.0] = empty
    got = chain_propagate(iv, [100.0], A)
    assert got[0][0] > got[0][1]
    # a 200 m gap carries 3 m: both stay feasible
    got = chain_propagate(iv, [200.0], A)
    assert all(lo <= hi for lo, hi in got)
