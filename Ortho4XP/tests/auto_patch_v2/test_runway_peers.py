"""RUNWAY PEERS (owner RULINGS 2026-11-10b (2), (3), (4); issues #1912,
#1945, #1928; ``airport/runway_peers``, ``airport/end_pins.verify``,
``constraints/runway_profile.end_pin_cases``).

Synthetic, on the one-runway fixture plus a second runway built beside it.
LSZI (an apt.dat-only runway beside a CIFP one), KCRS (two CIFP ends 6 m
apart) and LTFM (a parallel pair the DEM refused) are where the rulings
were found and their closing measurements, never their scope (RULINGS
2026-10-05e).
"""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest
from auto_patch_v2.airport import end_pins as EP
from auto_patch_v2.airport import runway_peers as RP
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.runway_profile import CASE_LIDAR, CASE_TOUCHING, end_pin_cases
from auto_patch_v2.geom import runway_contact as RC
from auto_patch_v2.law import Law
from tests.auto_patch_v2.test_runway_end_pins import _Classed, _Lidar, _site


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _beside(rw, rid, gap, thresholds, along=0.0, names=("09L", "27R")):
    """A copy of ``rw`` moved sideways so its slab lies ``gap`` metres from
    ``rw``'s, and ``along`` metres down its axis, with CIFP ``thresholds``."""
    (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    off = rw.width_m + gap
    dx, dy = -uy * off + ux * along, ux * off + uy * along
    ends = tuple(_dc.replace(e, name=n, xy=(e.xy[0] + dx, e.xy[1] + dy), threshold_elev_m=z,
                             pin_source="cifp" if z is not None else "")
                 for e, n, z in zip(rw.ends, names, thresholds, strict=True))
    return _dc.replace(rw, id=f"{names[0]}/{names[1]}", ends=ends)


def _with(airport, *more):
    return _dc.replace(airport, runways=tuple(airport.runways) + tuple(more))


def _cifp(airport):
    rw = airport.runways[0]
    ends = tuple(_dc.replace(e, pin_source="cifp" if e.threshold_elev_m is not None else "")
                 for e in rw.ends)
    return _dc.replace(airport, runways=(_dc.replace(rw, ends=ends),) + airport.runways[1:])


# ── the witness: slabs that touch ────────────────────────────────────────

def test_slabs_touch_within_the_gap_only(law):
    airport, _pm = _site(law, _Lidar(0.0), (None, None))
    rw = airport.runways[0]
    gap = float(law.tables.runway_ends.peer_touch_m)
    assert RC.slabs_touch(rw, _beside(rw, "x", 0.3, (None, None)), gap)
    assert not RC.slabs_touch(rw, _beside(rw, "x", 30.0, (None, None)), gap)


# ── (2) an apt.dat-only runway takes its touching survey's level ─────────

def test_an_apt_dat_only_runway_beside_a_cifp_one_takes_its_level(law):
    """LSZI's class: the lidar puts the apt.dat-only runway 2 m under its
    neighbour's level CIFP pins — touching, it takes their level; apart,
    26e's lidar stands."""
    dem = _Lidar(0.0)                                    # 700 m everywhere
    airport, pm = _site(law, dem, (None, None), elev=702.0)
    rw = airport.runways[0]
    vw = view(pm, law)
    for gap, case in ((0.3, CASE_TOUCHING), (200.0, CASE_LIDAR)):
        site = _with(airport, _beside(rw, "x", gap, (702.0, 702.0)))
        cases = end_pin_cases(pm, law, site)
        assert {p.case for p in cases.values()} == {case}, gap
        want = 702.0 if case == CASE_TOUCHING else 700.0
        for v, p in cases.items():
            assert p.z == pytest.approx(want, abs=0.02), (gap, vw.xy[v], p)


def test_the_pull_reaches_only_as_far_as_the_cap_along_the_axis(law):
    """22a's reach: a touching survey 300 m down the axis pulls each end
    no further than the runway's cap over its distance along the axis."""
    dem = _Lidar(0.0)
    airport, pm = _site(law, dem, (None, None), elev=720.0)
    rw = airport.runways[0]
    site = _with(airport, _beside(rw, "x", 0.3, (720.0, None), along=300.0))
    cases = end_pin_cases(pm, law, site)
    assert {p.case for p in cases.values()} == {CASE_TOUCHING}
    zs = sorted(p.z for p in cases.values())
    assert 700.0 < zs[0] < zs[1] < 720.0, zs


# ── (3) two close pinned ends split the difference ──────────────────────

def _crossing_at(rw, k, along, deg, thresholds):
    """A runway turned ``deg`` from ``rw`` whose end 0 sits on ``rw``'s
    centreline ``along`` metres in from ``rw``'s end ``k``."""
    (ax, ay), (bx, by) = rw.ends[k].xy, rw.ends[1 - k].xy
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    c, sn = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    vx, vy = ux * c - uy * sn, ux * sn + uy * c
    p0 = (ax + ux * along, ay + uy * along)
    p1 = (p0[0] + vx * 900.0, p0[1] + vy * 900.0)
    ends = tuple(_dc.replace(e, name=n, xy=p, threshold_elev_m=z, pin_source="cifp")
                 for e, n, p, z in zip(rw.ends, ("20", "02"), (p0, p1), thresholds, strict=True))
    return _dc.replace(rw, id="02/20", ends=ends)


def test_two_close_ends_yield_equally_until_the_pavement_complies(law):
    """KCRS's class: a crossing runway's CIFP end sits on this runway's
    ridge 6 m in from its CIFP end, 0.31 m under it.  The pavement between
    them is this runway's profile: its pin-line grade over 6 m, give or
    take the vertical-curve bound.  Each end yields the SAME share, just
    to that range's edge; a pair already inside it is untouched."""
    airport, _pm = _site(law, _Lidar(0.0), (700.0, 694.0))
    airport = _cifp(airport)
    rw = airport.runways[0]
    site = _with(airport, _crossing_at(rw, 0, 6.0, 30.0, (699.69, 697.0)))
    out, lines = RP.split_close_ends(site, law)
    a, b = out.runways[0].ends[0], out.runways[1].ends[0]
    lo, hi = RP._band(law, list(site.runways), (0, 0), (1, 0), 6.0, 1.0)
    g = (694.0 - 700.0) / rw.length_m
    assert len(lines) == 1 and lo < g * 6.0 < hi and hi - lo < 0.31
    assert b.threshold_elev_m - a.threshold_elev_m == pytest.approx(lo, abs=1e-9)
    assert (b.threshold_elev_m - 699.69) == pytest.approx(700.0 - a.threshold_elev_m, abs=1e-9)
    assert a.cifp_elev_m == 700.0 and RP.SPLIT in b.pin_flags
    assert out.runways[0].ends[1].threshold_elev_m == 694.0
    calm = _with(airport, _crossing_at(rw, 0, 6.0, 30.0, (700.0 + g * 6.0, 697.0)))
    assert RP.split_close_ends(calm, law) == (calm, [])


def test_ends_farther_apart_than_the_ruling_hold(law):
    airport, _pm = _site(law, _Lidar(0.0), (700.0, 690.0))
    airport = _cifp(airport)
    rw = airport.runways[0]
    far = _with(airport, _beside(rw, "x", -rw.width_m + 6.0, (705.0, 690.0), along=15.0))
    assert RP.split_close_ends(far, law)[1] == []


# ── (4) a parallel runway whose CIFP stood corroborates a (b) refusal ────

def test_a_parallel_standing_pair_corroborates_a_b_refusal(law):
    """LTFM's class: on a coarse DEM falling 10 m along the runways, the
    parallel runway's CIFP (695 -> 705) stands; this runway's (700 -> 697)
    disagrees with the DEM by 13 m (> 12 m, rule (b)) but agrees with its
    neighbour end for end within 12 m — it STANDS.  Alone, it is refused."""
    slope = 10.0 / 1200.0
    dem = _Classed(slope, None)
    airport, _pm = _site(law, dem, (700.0, 697.0), elev=750.0)      # no field vouching
    airport = _cifp(airport)
    rw = airport.runways[0]
    alone, _r, lines = EP.verify(airport, law)
    assert alone.runways[0].ends[0].pin_source == "dem" and "rule (b)" in lines[0]
    site = _with(airport, _beside(rw, "x", 200.0, (695.0, 705.0)))
    out, recs, lines = EP.verify(site, law)
    assert [e.threshold_elev_m for e in out.runways[0].ends] == [700.0, 697.0]
    assert [e.pin_source for e in out.runways[0].ends] == ["cifp", "cifp"]
    assert any("RULINGS 2026-11-10b (4)" in ln for ln in lines), lines
    # a neighbour that disagrees beyond the tolerance corroborates nothing
    site = _with(airport, _beside(rw, "x", 200.0, (685.0, 695.0)))
    out, _r, _l = EP.verify(site, law)
    assert out.runways[0].ends[0].pin_source == "dem"


def test_a_crossing_runway_is_no_parallel_peer(law):
    airport, _pm = _site(law, _Lidar(0.0), (700.0, 697.0))
    rw = airport.runways[0]
    (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
    cx, cy = (ax + bx) / 2, (ay + by) / 2
    turned = _dc.replace(rw, id="18/36", ends=(
        _dc.replace(rw.ends[0], xy=(cx - (by - ay) / 2, cy + (bx - ax) / 2)),
        _dc.replace(rw.ends[1], xy=(cx + (by - ay) / 2, cy - (bx - ax) / 2))))
    stood = {"18/36": (turned, {0: 700.0, 1: 697.0})}
    assert RP.parallel_peer(rw, {0: 700.0, 1: 697.0}, stood, 12.0, 5.0) is None
    stood = {"p": (_beside(rw, "p", 200.0, (700.0, 697.0)), {0: 700.0, 1: 697.0})}
    assert RP.parallel_peer(rw, {0: 700.0, 1: 697.0}, stood, 12.0, 5.0) == "p"
