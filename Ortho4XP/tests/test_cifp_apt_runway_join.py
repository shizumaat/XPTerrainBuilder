"""CIFP → apt.dat runway join (``elevation._build_apt_runway_join``).

apt.dat owns runway footprint geometry; the CIFP owns the thresholds the
segmenter iterates.  Joining them is a naming problem, and the two files
disagree in two independent ways — zero-padding (apt.dat ``9`` vs CIFP
``RW09``) and magnetic renumbering (the same strip labelled ``18R/36L`` in
one and ``RW19R/RW01L`` in the other).

A missed join is SILENT: ``runway_segments._runway_physical_extent`` sets
``have_apt_geom`` False and the runway quietly falls back to coarse CIFP
geometry, never segmenting at its apt.dat pavement joins.  Nothing raises,
so these tests are the only guard.

The renumbered fixture is KCLT with Navigraph 2607 — coordinates below are
the real values parsed from
``Custom Data/CIFP/KCLT.dat`` and ``Global Airports/.../apt.dat``.  Two of
its three strips are renumbered (+1 heading with a 36→01 wrap, and the
centre strip additionally moves C→L/R), while the third keeps its name —
so one fixture covers the renumbered and non-renumbered paths at once.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch.apt_dat_reader import Runway
from auto_patch.elevation import _build_apt_runway_join
from auto_patch.pavement.runway_segments import canonical_runway_desig


# ──────────────────────────────────────────────────────────────────────
# Fixtures — real KCLT geometry
# ──────────────────────────────────────────────────────────────────────
def _rwy(desig_a, desig_b, lat_a, lon_a, lat_b, lon_b, width_m=46.02,
         blast_a_m=0.0, blast_b_m=0.0):
    return Runway(
        desig_a=desig_a, desig_b=desig_b,
        lat_a=lat_a, lon_a=lon_a, lat_b=lat_b, lon_b=lon_b,
        width_m=width_m, surface_code=1,
        displaced_a_m=0.0, displaced_b_m=0.0,
        blast_a_m=blast_a_m, blast_b_m=blast_b_m)


# apt.dat row-100 records (X-Plane 12 Global Airports).
KCLT_APT = [
    _rwy("18L", "36R", 35.2247475, -80.9361671, 35.2009447, -80.9341243,
         blast_a_m=140.0, blast_b_m=61.0),
    _rwy("18R", "36L", 35.2253311, -80.9673938, 35.2006672, -80.9652720,
         blast_a_m=130.0, blast_b_m=122.0),
    _rwy("18C", "36C", 35.2274452, -80.9531448, 35.2000402, -80.9507868,
         blast_a_m=61.0, blast_b_m=61.0),
]

# CIFP thresholds (Navigraph 2607).  RW01L/RW01R/RW19L/RW19R are the
# renumbered spellings; RW18L/RW36R still agrees with apt.dat.
KCLT_CIFP = {
    "RW01L": (35.20061944444445, -80.96529722222222),
    "RW01R": (35.19999166666666, -80.95081111111111),
    "RW18L": (35.22473333333333, -80.93615833333334),
    "RW19L": (35.22739722222222, -80.95316944444444),
    "RW19R": (35.22528333333334, -80.96741944444445),
    "RW36R": (35.20095555555556, -80.93411666666667),
}


def _apt_geom(geom, desig):
    """The consumer's lookup, verbatim from
    ``runway_segments._runway_physical_extent`` (lines 124-127).  Tests
    must ask the question production asks — a designator can resolve via
    the canonical fallback here without ever being a key in ``geom``."""
    return geom.get(desig) or geom.get(canonical_runway_desig(desig))


def _apt_width(widths, desig_a, desig_b):
    """The consumer's width lookup, verbatim from
    ``runway_segments`` lines 1123-1126."""
    return (widths.get(desig_a)
            or widths.get(canonical_runway_desig(desig_a))
            or widths.get(desig_b)
            or widths.get(canonical_runway_desig(desig_b)))


def _pair(desig_a, desig_b, thresholds=KCLT_CIFP):
    """One ``pair_runways``-shaped tuple."""
    def data(d):
        lat, lon = thresholds[d]
        return {"lat": lat, "lon": lon, "elevation_m": 0.0,
                "displaced_m": 0.0}
    return (desig_a, data(desig_a), desig_b, data(desig_b))


# ``pair_runways`` output for KCLT: get_reciprocal swaps the L/R suffix,
# so RW01L pairs with RW19R (not RW19L) — opposite ends of ONE strip.
KCLT_PAIRS = [
    _pair("RW01L", "RW19R"),
    _pair("RW01R", "RW19L"),
    _pair("RW18L", "RW36R"),
]


# ──────────────────────────────────────────────────────────────────────
# The premise: name matching genuinely fails for the renumbered ends
# ──────────────────────────────────────────────────────────────────────
def test_renumbered_designators_do_not_reconcile_by_name():
    """Guards the tests below from passing for the wrong reason.

    If ``canonical_runway_desig`` ever grew renumbering awareness these
    tests would still pass while measuring nothing, so assert up front
    that the renumbered CIFP spellings really are absent from apt.dat.
    """
    apt_spellings = set()
    for r in KCLT_APT:
        for d in (r.desig_a, r.desig_b):
            apt_spellings |= {d, "RW" + d.lstrip("RW"),
                              canonical_runway_desig(d)}
    for renumbered in ("RW01L", "RW01R", "RW19L", "RW19R"):
        assert renumbered not in apt_spellings
        assert canonical_runway_desig(renumbered) not in apt_spellings
    # ...while the strip that was NOT renumbered does match by name.
    assert "RW18L" in apt_spellings


# ──────────────────────────────────────────────────────────────────────
# Renumbered airport: every end still resolves
# ──────────────────────────────────────────────────────────────────────
def test_renumbered_runways_all_resolve_to_apt_geometry():
    """No CIFP end falls back to CIFP geometry (``have_apt_geom`` True).

    Mirrors ``runway_segments._runway_physical_extent``'s lookup exactly.
    """
    geom, _widths, _c2a = _build_apt_runway_join(KCLT_APT, KCLT_PAIRS)
    for desig_a, _da, desig_b, _db in KCLT_PAIRS:
        assert _apt_geom(geom, desig_a) is not None, \
            f"{desig_a} fell back to CIFP geometry"
        assert _apt_geom(geom, desig_b) is not None, \
            f"{desig_b} fell back to CIFP geometry"


def test_renumbered_runways_map_to_the_correct_apt_runway():
    """Position matching picks the right strip, not merely *a* strip.

    Ground truth is the ILS ident each threshold carries in the stock
    CIFP: IXUU = apt 36L = Navigraph RW01L, IPEP = apt 18C = RW19L, etc.
    """
    _geom, _widths, cifp_to_apt = _build_apt_runway_join(KCLT_APT, KCLT_PAIRS)
    assert cifp_to_apt[("RW01L", "RW19R")] == ("36L", "18R")
    assert cifp_to_apt[("RW01R", "RW19L")] == ("36C", "18C")
    # The non-renumbered strip reconciles to itself.
    assert cifp_to_apt[("RW18L", "RW36R")] == ("18L", "36R")


def test_renumbered_end_takes_its_own_threshold_not_the_reciprocal():
    """Orientation must survive the join: a CIFP end must receive the
    apt.dat geometry of the SAME physical end.  Getting this backwards
    would silently invert every runway profile."""
    geom, _widths, _c2a = _build_apt_runway_join(KCLT_APT, KCLT_PAIRS)
    # apt 18R/36L: end-a is the north (18R) threshold, end-b the south
    # (36L).  CIFP RW01L is the south end, RW19R the north.
    g_01l = _apt_geom(geom, "RW01L")
    g_19r = _apt_geom(geom, "RW19R")
    assert g_01l is not None and g_19r is not None
    assert g_01l[:2] == (35.2006672, -80.9652720)   # apt end-b
    assert g_19r[:2] == (35.2253311, -80.9673938)   # apt end-a
    # Per-end blast values follow the same end (index 4 = blast_m).
    assert g_01l[4] == 122.0    # blast_b_m
    assert g_19r[4] == 130.0    # blast_a_m


def test_renumbered_runways_get_apt_width():
    """Width is registered under the CIFP spelling too — otherwise the
    segmenter widens a renumbered runway to a default."""
    _geom, widths, _c2a = _build_apt_runway_join(KCLT_APT, KCLT_PAIRS)
    assert _apt_width(widths, "RW01L", "RW19R") == pytest.approx(46.02)
    assert _apt_width(widths, "RW01R", "RW19L") == pytest.approx(46.02)
    # ...and under the RAW CIFP spelling: runway_segments line 1747 reads
    # ``runway_widths.get(desig_a, DEFAULT_RUNWAY_WIDTH)`` with no
    # canonical fallback, so a renumbered end missing here silently gets
    # the default width instead of apt.dat's.
    for desig in ("RW01L", "RW01R", "RW19L", "RW19R"):
        assert widths[desig] == pytest.approx(46.02)


# ──────────────────────────────────────────────────────────────────────
# Zero-padding (the other naming disagreement)
# ──────────────────────────────────────────────────────────────────────
def test_single_digit_apt_designator_resolves_from_padded_cifp():
    """TBPB-style: apt.dat writes ``9``/``27``, the CIFP ``RW09``/``RW27``.

    This path is resolved by NAME — ``canonical_runway_desig("RW09")`` is
    ``"9"`` — at the *lookup* site, so ``"RW09"`` is deliberately not a key
    in ``geom``.  Asserting ``geom["RW09"]`` would pass only because
    position matching also registers that spelling, i.e. it would measure
    the wrong mechanism.
    """
    apt = [_rwy("9", "27", 13.0800, -59.4900, 13.0700, -59.4800, width_m=45.0)]
    pairs = [("RW09", {"lat": 13.0800, "lon": -59.4900}, "RW27",
              {"lat": 13.0700, "lon": -59.4800})]
    geom, widths, _c2a = _build_apt_runway_join(apt, pairs)
    assert _apt_geom(geom, "RW09")[:2] == (13.0800, -59.4900)
    assert _apt_geom(geom, "RW27")[:2] == (13.0700, -59.4800)
    assert _apt_width(widths, "RW09", "RW27") == pytest.approx(45.0)


# ──────────────────────────────────────────────────────────────────────
# Precedence and boundaries
# ──────────────────────────────────────────────────────────────────────
def test_exact_name_match_is_never_overridden_by_position():
    """Position matching fills gaps only.  A designator that matched
    apt.dat by name keeps its by-name geometry even when a (closer)
    neighbouring strip would win the position match."""
    geom, _widths, _c2a = _build_apt_runway_join(KCLT_APT, KCLT_PAIRS)
    # RW18L matched by name → apt 18L end-a, not 18C or 18R.
    assert geom["RW18L"][:2] == (35.2247475, -80.9361671)
    assert geom["RW36R"][:2] == (35.2009447, -80.9341243)


def test_unpaired_cifp_end_is_skipped_without_error():
    """A CIFP end with no reciprocal in the file gets no position
    reconciliation (it has no pair centre to match on).  Documented
    limitation — it must degrade quietly, not raise."""
    pairs = [("RW01L", {"lat": 35.20061944, "lon": -80.96529722}, None, None)]
    geom, _widths, cifp_to_apt = _build_apt_runway_join(KCLT_APT, pairs)
    assert cifp_to_apt == {}
    assert "RW01L" not in geom          # still falls back
    assert "18L" in geom                # apt.dat entries unaffected


def test_no_nearby_apt_runway_leaves_the_cifp_designator_unresolved():
    """Position matching must not reach across the airport: a CIFP pair
    with no apt.dat strip near it stays unmatched rather than binding to
    an unrelated runway."""
    pairs = [_pair("RW01L", "RW19R")]
    far_apt = [_rwy("09", "27", 0.0, 0.0, 0.0, 0.027)]   # different hemisphere
    geom, _widths, cifp_to_apt = _build_apt_runway_join(far_apt, pairs)
    assert cifp_to_apt == {}
    assert "RW01L" not in geom


def test_empty_apt_runways_is_safe():
    """No apt.dat runways at all → empty maps, no exception."""
    geom, widths, cifp_to_apt = _build_apt_runway_join([], KCLT_PAIRS)
    assert (geom, widths, cifp_to_apt) == ({}, {}, {})
