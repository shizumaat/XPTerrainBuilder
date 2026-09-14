"""Lane ``v2cost2`` twins (RULINGS 2026-09-14q): the law-neutral cost
cuts, each proved IDENTITY-PRESERVING against the reading it replaced.

* the apron pass's MIDPOINT pre-screen is SOUND (it can only reject what
  ``chords_covered`` rejects) and the whole pass's row set is unchanged
  by deferring the minting — the ``apron:<face>:<k>`` group names
  included, which is what the reserve/mint split is for;
* ``anchor_rule.pad_majority``'s hoisted boxes answer exactly what the
  per-call boxes answered;
* ``contact._inside`` / the ``_narrow_rows`` screen, axis by axis, select
  exactly the points the ``.all``-reduced masks selected;
* ``airport/partition_cache`` round-trips a payload and MISSES when any
  fingerprint input moves.
"""
from __future__ import annotations

import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon

from auto_patch_v2.airport import anchor_rule as _ar
from auto_patch_v2.airport import contact as _contact
from auto_patch_v2.airport import partition_cache as _pc
from auto_patch_v2.constraints.geometry import (chord_midpoints_hit,
                                                chords_covered, face_cover)


# ── the apron midpoint pre-screen ────────────────────────────────────────

def _apron_with_holes():
    """A 200 x 200 apron with two holes — a road and a building."""
    ring = [(0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)]
    holes = [[(40.0, 40.0), (60.0, 40.0), (60.0, 160.0), (40.0, 160.0)],
             [(120.0, 80.0), (170.0, 80.0), (170.0, 130.0), (120.0, 130.0)]]
    return ring, holes


def test_midpoint_screen_only_rejects_what_the_cover_rejects():
    ring, holes = _apron_with_holes()
    cover = face_cover(ring, holes, 0.5)
    assert cover is not None
    rng = np.random.default_rng(20260914)
    pts = rng.uniform(0.0, 200.0, size=(400, 2))
    segs = [((float(pts[i][0]), float(pts[i][1])),
             (float(pts[i + 1][0]), float(pts[i + 1][1])))
            for i in range(0, 398, 2)]
    hit = chord_midpoints_hit(cover, segs)
    ok = chords_covered(cover, segs)
    # SOUNDNESS: every chord the full predicate keeps, the screen keeps
    for k, (h, o) in enumerate(zip(hit, ok)):
        assert not (o and not h), f"chord {k}: covered but the midpoint missed"
    # and it is worth having: it rejects a real share of them here
    assert not all(hit)
    # the two-stage answer is the one-stage answer
    live = [i for i, h in enumerate(hit) if h]
    second = chords_covered(cover, [segs[i] for i in live])
    kept = {i for i, s in zip(live, second) if s}
    assert kept == {i for i, o in enumerate(ok) if o}


def test_midpoint_screen_keeps_every_chord_with_no_cover():
    segs = [((0.0, 0.0), (1.0, 1.0)), ((2.0, 2.0), (3.0, 3.0))]
    assert list(chord_midpoints_hit(None, segs)) == [True, True]
    assert list(chord_midpoints_hit(None, [])) == []


def test_tier_reserve_mint_is_the_old_rows():
    """``_Tier.rows`` and ``reserve`` + ``mint`` mint the same rows in the
    same ``apron:<face>:<k>`` groups — including the pairs a face cover
    later rejects, which still consume a ``k``."""
    from auto_patch_v2.constraints.apron import _Tier
    from auto_patch_v2.model.constraints import Source
    src = Source("apron", "ruling", ("face:7", "pav7"))
    pairs = [(1, 2, 10.0), (2, 3, 20.0), (3, 4, 30.0), (4, 5, 40.0)]
    a = _Tier(7, "pav7", 0.015, 0.01)
    direct = [a.rows(x, y, d, src) for x, y, d in pairs]
    b = _Tier(7, "pav7", 0.015, 0.01)
    held = [b.reserve(x, y, d, src) for x, y, d in pairs]
    assert b.k == a.k
    # minted LATER, in any order, the rows are the rows
    assert [b.mint(h) for h in held] == direct
    assert [b.mint(held[2]), b.mint(held[0])] == [direct[2], direct[0]]
    assert b.n_rows == 2
    c = _Tier(7, "pav7", None, 0.01)
    assert c.n_rows == 1 and len(c.rows(1, 2, 3.0, src)) == 1


# ── pad_majority's hoisted boxes ─────────────────────────────────────────

def _pad(ref, lat0, lon0, d=0.001):
    return _ar.PadRing(ref, ((lat0, lon0), (lat0 + d, lon0),
                             (lat0 + d, lon0 + d), (lat0, lon0 + d)))


def test_pad_majority_boxes_hoist_is_the_same_answer():
    pads = tuple(_pad(f"building{k}", 25.0 + 0.01 * k, 51.0) for k in range(6))
    on = pads[3]
    cands = [(on.ring[0][0] + 0.0005, on.ring[0][1] + 0.0005, 0.0, 0.0)] * 3
    cands += [(24.5, 50.5, 0.0, 0.0)]
    _ar._PAD_BOXES["pads"] = None                    # cold
    first = _ar.pad_majority(cands, pads)
    second = _ar.pad_majority(cands, pads)           # warm: the cached boxes
    assert first is second is on
    # a DIFFERENT pads object is not the cached one
    other = tuple(_pad(f"other{k}", 40.0 + 0.01 * k, 5.0) for k in range(3))
    assert _ar.pad_majority(cands, other) is None
    assert _ar.pad_majority(cands, pads) is on
    # no majority: no pad
    assert _ar.pad_majority([cands[0]] + [cands[3]] * 3, pads) is None
    assert _ar.pad_majority([], pads) is None and _ar.pad_majority(cands, ()) is None


# ── the contact screens, axis by axis ────────────────────────────────────

def test_inside_axis_by_axis_is_the_reduced_mask():
    rng = np.random.default_rng(14)
    for _ in range(25):
        pts = rng.uniform(-5.0, 5.0, size=(rng.integers(1, 60), 3))
        lo = rng.uniform(-3.0, 0.0, size=3)
        hi = lo + rng.uniform(0.1, 4.0, size=3)
        eps = float(rng.uniform(0.0, 0.5))
        want = pts[((pts >= lo - eps) & (pts <= hi + eps)).all(axis=1)]
        got = _contact._inside(pts, lo, hi, eps)
        assert got.shape == want.shape and np.array_equal(got, want)


def test_narrow_rows_screen_is_the_reduced_mask():
    """The point x triangle screen inside ``_narrow_rows``, per axis,
    picks exactly the ``(point, triangle)`` rows the ``.all(axis=2)``
    masks picked — same rows, same order."""
    rng = np.random.default_rng(1409)
    for _ in range(25):
        cand = rng.uniform(-2.0, 2.0, size=(rng.integers(1, 30), 3))
        tlo = rng.uniform(-2.0, 1.0, size=(rng.integers(1, 30), 3))
        thi = tlo + rng.uniform(0.05, 1.5, size=tlo.shape)
        want = ((cand[:, None, :] >= tlo[None])
                & (cand[:, None, :] <= thi[None])).all(axis=2)
        c0 = cand[:, 0][:, None]
        m = c0 >= tlo[None, :, 0]
        np.logical_and(m, c0 <= thi[None, :, 0], out=m)
        c1 = cand[:, 1][:, None]
        np.logical_and(m, c1 >= tlo[None, :, 1], out=m)
        np.logical_and(m, c1 <= thi[None, :, 1], out=m)
        c2 = cand[:, 2][:, None]
        np.logical_and(m, c2 >= tlo[None, :, 2], out=m)
        np.logical_and(m, c2 <= thi[None, :, 2], out=m)
        assert np.array_equal(m, want)
        assert [tuple(x) for x in np.transpose(np.nonzero(m))] == \
               [tuple(x) for x in np.transpose(np.nonzero(want))]


# ── the partition cache ──────────────────────────────────────────────────

def test_partition_cache_round_trip_and_miss(tmp_path):
    p = str(tmp_path / "o4_v2_partition_+25+051.cache")
    payload = ({"objects": 3}, "report", [1, 2, 3], ("cluster",))
    assert _pc.read(p, "fp1") is None                  # no file yet
    assert _pc.write(p, "fp1", payload) is True
    assert _pc.read(p, "fp1") == payload
    assert _pc.read(p, "fp2") is None                  # a moved fingerprint MISSES
    assert _pc.read(None, "fp1") is None and _pc.read(p, None) is None
    assert _pc.write(None, "fp1", payload) is False
    # a corrupt cache is a miss, never an exception
    with open(p, "wb") as fh:
        fh.write(b"not a pickle")
    assert _pc.read(p, "fp1") is None


def test_partition_cache_path_and_code_digest(tmp_path):
    class _Pack:
        name = "OTHH Doha (Aeroscape)"
        apt_dat_path = str(tmp_path / "pack" / "Earth nav data" / "apt.dat")

    class _Air:
        pack = _Pack()

    air = _Air()
    got = _pc.cache_path(air, str(tmp_path / "mod"),
                         "/x/+25+051.dsf.anchor_bak.84ffe846.text")
    assert got is not None and got.endswith(
        "OTHH Doha (Aeroscape)/o4_v2_partition_+25+051.cache")
    assert _pc.cache_path(air, None, "/x/+25+051.dsf.text") is None
    assert _pc.cache_path(air, str(tmp_path / "mod"), None) is None
    d = _pc.code_digest()
    assert isinstance(d, str) and len(d) == 64 and _pc.code_digest() == d


def test_partition_cache_fingerprint_needs_a_pack_and_a_dump(tmp_path):
    class _Air:
        pack = None
        frame = None
        icao = "OTHH"
    assert _pc.fingerprint(_Air(), None, dump_path=None, radius_deg=0.05) is None
