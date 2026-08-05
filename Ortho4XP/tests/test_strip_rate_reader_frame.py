"""check_grade STRIP-family reader frame — two BROKEN-INSTRUMENT fixes.

Both were measured on the composed KCLT patch, 2026-08-05.

1. DOUBLE COUNT.  Adjacent ``graded_strip`` band pieces share their whole
   common boundary chain, so every consecutive vertex pair on that chain
   belongs to BOTH rings and the per-way readers counted the same physical
   station once per way: strip_abeam 847 rows over 433 distinct sites (414
   carried by >1 way) = x1.96; strip_arc 985 over 517 = x1.91.  The
   no-stacked-nodes invariant makes the shared vertices ONE node with ONE
   value, so the second reading is arithmetically identical — never
   independent evidence.

2. RATE BLIND SPOT AT THE WRONG SPACING.  ``_RATE_READER_BLIND_SPOT`` was
   the constant ``0.1 / 30.0`` — an emit quantum over an ASSUMED 30 m
   station spacing — while the emitted strip rings station 2-5 m apart
   (585 of 985 KCLT arc rows).  A grade-change reading is a
   second difference, so its rounding envelope is
   ``q * (1/dp + 1/dn)``: at 3 m spacing that is twenty times the old
   constant, and the reader was judging pure emit rounding as curvature.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def _cg():
    spec = importlib.util.spec_from_file_location(
        "cg_frame_test", REPO / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cg_frame_test"] = mod
    spec.loader.exec_module(mod)
    return mod


CG = _cg()


class _Way:
    """Minimal stand-in for check_grade's Way (only what the readers use)."""

    def __init__(self, tags=None):
        self.tags = tags or {"role": "graded_strip"}
        self.wid = "-1"
        self.role = "graded_strip"


# ── 1. the physical-site key ──────────────────────────────────────────

def test_site_key_is_order_independent():
    a, b = (10.0, 20.0), (13.0, 20.5)
    assert CG._site_key(a, b) == CG._site_key(b, a)


def test_site_key_separates_genuinely_different_sites():
    assert CG._site_key((0.0, 0.0), (3.0, 0.0)) != \
        CG._site_key((0.0, 0.0), (3.0, 1.0))


def test_site_key_matches_the_same_station_read_from_two_bands():
    """Two adjacent bands carry the SAME two nodes; the reader must see
    one site, whichever way it walks the chain."""
    p, q, r = (0.0, 0.0), (3.0, 0.1), (6.0, 0.2)
    assert CG._site_key(p, q, r) == CG._site_key(r, q, p)


# ── 2. the rate blind spot ────────────────────────────────────────────

def test_blind_spot_scales_with_the_actual_station_spacing():
    w = _Way()
    wide = CG._rate_reader_blind_spot(w, 30.0, 30.0)
    tight = CG._rate_reader_blind_spot(w, 3.0, 3.0)
    assert tight > wide
    assert tight == 10.0 * wide, (
        "a ten-times-tighter station spacing must give a ten-times-wider "
        "grade-change blind spot — the second difference divides by the "
        "spacing twice")


def test_blind_spot_is_the_quantum_over_the_two_spacings():
    """ONE derivation: q * (1/dp + 1/dn), q from _pair_quant_noise_m
    floored at the coarse emit envelope (no second constant)."""
    w = _Way()
    q = max(CG._pair_quant_noise_m(w), CG.SLOPED_QUAD_ROUNDING_NOISE_M)
    for dp, dn in ((3.0, 3.0), (2.0, 8.0), (30.5, 30.5)):
        assert CG._rate_reader_blind_spot(w, dp, dn) == \
            q * (1.0 / dp + 1.0 / dn)


def test_blind_spot_at_30_m_is_no_tighter_than_the_retired_constant():
    """The retired constant claimed to be the 30 m envelope; the honest
    second-difference envelope at 30 m is WIDER, never tighter — so the
    fix cannot have made the reader more permissive by accident at the
    spacing the old constant was written for."""
    w = _Way()
    assert CG._rate_reader_blind_spot(w, 30.0, 30.0) >= 0.1 / 30.0


def test_degenerate_spacing_is_never_read():
    w = _Way()
    assert CG._rate_reader_blind_spot(w, 0.0, 5.0) == float("inf")
