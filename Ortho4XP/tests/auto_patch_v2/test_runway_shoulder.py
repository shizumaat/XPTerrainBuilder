"""§40 A PAVEMENT ALONG A RUNWAY IS THE RUNWAY'S; APRON EVIDENCE REFUSES
THE CORRIDOR KIND (owner RULINGS 2026-09-13co items 1 and 6, 2026-09-13cs
items 1 and 6; Fable 2026-09-13) as synthetic twins over the M1 synthetic
airport (``test_classify._synthetic``):

1. a page whose boundary runs ``corridor.runway_shoulder_shared_m`` or
   more along a runway ring is that runway's SHOULDER — role ``runway``
   at the RUNWAY's ref, code number and code letter, ``kind =
   runway_shoulder`` with the shared length as its evidence — and it
   carries no taxi-family face, so no adjacent-ground zone strip is
   manufactured around it (§40 (3));
2. the same page 10 m SHORTER than the floor is not a shoulder: the
   ladder's own verdict stands;
3. the STRIP FOOTPRINT is the RUNWAY's own geometry, not a fit to
   whatever carries the runway role — a shoulder does not move it
   (``constraints.strips.runway_groups``,
   ``model.airport.Runway.slab_corners``);
4. OSM ``aeroway=apron`` cover at or above ``lot.apron_cover_fraction``
   REFUSES the corridor kind: the cell is apron, and the route-proximity
   cut does not re-mint it as a junction;
5. THE CROWN STOPS AT THE RUNWAY EDGE (``constraints/runway_chord.py``):
   a shoulder vertex's chord target is the runway EDGE's value, not the
   crown continued to the shoulder's own lateral offset — which sits
   exactly ON the transverse cap, so the built surface reads over it.
   Its twin is the CYXY census
   (``test_constraints.test_cyxy_verify_matches_v1_census``, which
   requires ``runway_transverse`` 0): with the three CYXY shoulders and
   no clamp that family reads 4 DEFECT rows, 1.56-1.93 m, each 0.03 pp
   over the 1.5 % cap.  The synthetic airport carries no ``runway_
   profile`` breakline, so it cannot state the target at all.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.classify import classify, load_rules  # noqa: E402
from auto_patch_v2.classify.explain import role_census  # noqa: E402
from auto_patch_v2.classify.roles import TAXI_FAMILY  # noqa: E402
from auto_patch_v2.constraints.precedence import view  # noqa: E402
from auto_patch_v2.constraints.strips import runway_groups  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import OsmWay, Pavement, Surface  # noqa: E402
from auto_patch_v2.planar.build import build as planar_build  # noqa: E402
from test_classify import _rect, _synthetic  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _shoulder_airport(length_m: float, depth_m: float = 40.0):
    """A ``length_m`` x ``depth_m`` page on the runway's SOUTH edge (the
    slab is y = -15..15, x = 0..1060), welded to it over ``length_m`` of
    boundary.  40 m deep by default: a RIBBON, under
    ``corridor.runway_shoulder_max_depth_m``."""
    a = _synthetic(gate=True, island=False)
    page = Pavement("page", Surface.ASPHALT,
                    _rect(300.0, -15.0 - depth_m, 300.0 + length_m, -15.0), ())
    return _dc.replace(a, pavements=a.pavements + (page,))


def _page_cells(cl):
    return [c for c in cl.cells if c.ref.split("#")[0] == "page"]


# ── 1. the shoulder joins the runway body ────────────────────────────────

def _band_off(rules):
    """§40 (5)'s own disarm clause: §40 (1)'s whole-cell admission."""
    return _dc.replace(rules, corridor=_dc.replace(rules.corridor,
                                                   runway_shoulder_band=False))


def test_a_page_running_along_the_runway_is_its_shoulder(law, rules):
    """§40 (1) with §40 (5) DISARMED: the whole page joins the runway body."""
    need = rules.corridor.runway_shoulder_shared_m
    cl = classify(_shoulder_airport(2 * need), law, _band_off(rules))
    # the page is no longer a page: it is the runway, at the RUNWAY's ref
    assert not _page_cells(cl)
    sh = [c for c in cl.cells if c.kind == "runway_shoulder"]
    assert len(sh) == 1, [(c.role, c.ref, c.kind) for c in cl.cells]
    c = sh[0]
    assert c.role == "runway" and c.ref == "09/27" and c.side == "airside"
    assert (c.code_number, c.code_letter) == (2, "C")     # the runway's own class
    assert c.evidence["shoulder_of"] == "09/27"
    assert c.evidence["shoulder_shared_m"] == pytest.approx(2 * need, rel=0.02)
    assert Polygon(c.ring, c.holes).area == pytest.approx(2 * need * 40.0, rel=0.05)


def test_the_shoulder_is_a_band_the_runway_role_ends_at_the_strip(law, rules):
    """§40 (5) (1)/(2) (Fable 2026-09-15; owner RULINGS 2026-09-15az).

    The runway is code 2, so its graded strip half width is 40 m
    (``zones.toml`` ``adjacent_ground.runway.half_width_m``) and the page
    runs 15–55 m off the centreline: 25 m of it is the runway's, 15 m of
    it is not.  ONE variable against the twin above — the law key."""
    from auto_patch_v2.law.tables import zone2_half_width_m
    hw = zone2_half_width_m(law, "runway", 2, "C")
    assert hw == 40.0, hw
    need = rules.corridor.runway_shoulder_shared_m
    cl = classify(_shoulder_airport(2 * need), law, rules)
    sh = [c for c in cl.cells if c.kind == "runway_shoulder"]
    assert len(sh) == 1, [(c.role, c.ref, c.kind) for c in cl.cells]
    c = sh[0]
    # (1) the band part is STILL the runway's, at the runway's own class
    assert c.role == "runway" and c.ref == "09/27" and c.side == "airside"
    assert (c.code_number, c.code_letter) == (2, "C")
    assert Polygon(c.ring, c.holes).area == pytest.approx(2 * need * 25.0, rel=0.05)
    # NO runway-family vertex beyond the strip half width
    assert max(abs(y) for _x, y in c.ring) == pytest.approx(hw, abs=0.01)
    # (2) the remainder is NOT runway family, and the runway's ref is gone
    rest = _page_cells(cl)
    assert rest, [(x.role, x.ref, x.kind) for x in cl.cells]
    assert all(x.role not in ("runway", "runway_crossing") for x in rest)
    assert all(x.ref.split("#")[0] == "page" for x in rest)
    assert sum(Polygon(x.ring, x.holes).area for x in rest) == \
        pytest.approx(2 * need * 15.0, rel=0.05)
    # ...and it earned its role on its own evidence, marked as the remainder
    assert any(x.evidence.get("shoulder_beyond_band") for x in rest), \
        [dict(x.evidence) for x in rest]
    assert cl.stats["shoulder_band_cuts"] == 1
    # §40 (3): no taxi-family face on that ground, so no zone strip is
    # manufactured around it
    ring = Polygon(_rect(300.0, -55.0, 300.0 + 2 * need, -15.0))
    assert not [x for x in cl.cells if x.role in TAXI_FAMILY
                and Polygon(x.ring, x.holes).intersection(ring).area > 1.0]
    # the census names it with its evidence (the dry before/after read)
    text = "\n".join(role_census(cl))
    assert "runway shoulder (§40 (1)): 1 cell(s)" in text
    assert "shoulder_shared_m" in text and "kind=runway_shoulder" in text


def test_a_page_short_of_the_floor_is_not_a_shoulder(law, rules):
    need = rules.corridor.runway_shoulder_shared_m
    cl = classify(_shoulder_airport(need - 10.0), law, rules)
    assert not [c for c in cl.cells if c.kind == "runway_shoulder"]
    cells = _page_cells(cl)
    assert cells and all(c.role != "runway" for c in cells), \
        [(c.role, c.ref) for c in cells]


def test_a_page_deeper_than_the_ribbon_cap_is_not_a_shoulder(law, rules):
    """THE SHOULDER IS A RIBBON: the same 300 m of runway edge under a page
    deep enough that its mean depth (area / shared length) passes
    ``corridor.runway_shoulder_max_depth_m`` is a page, not a shoulder —
    the lane deviation §40 (1) is implemented under, measured at OTHH
    (runway role 619,131 -> 3,832,917 m2 without it)."""
    deep = rules.corridor.runway_shoulder_max_depth_m + 25.0
    cl = classify(_shoulder_airport(300.0, depth_m=deep), law, rules)
    assert not [c for c in cl.cells if c.kind == "runway_shoulder"]
    assert _page_cells(cl)
    # ...and one metre under the cap it is
    thin = rules.corridor.runway_shoulder_max_depth_m - 1.0
    cl2 = classify(_shoulder_airport(300.0, depth_m=thin), law, rules)
    assert [c for c in cl2.cells if c.kind == "runway_shoulder"]


def test_the_shoulder_never_reaches_the_open_default_or_the_demotion(law, rules):
    """A shoulder is decided BEFORE every other rung: it carries none of
    the ladder's marks (no open default, no demotion, no §27 flip)."""
    cl = classify(_shoulder_airport(300.0), law, rules)
    c = [x for x in cl.cells if x.kind == "runway_shoulder"][0]
    for mark in ("open_default", "demoted", "airside_edge_flip", "near_route"):
        assert mark not in c.evidence, (mark, c.evidence)


# ── 3. the strip footprint is the runway's, not the shoulder's ───────────

def test_the_strip_footprint_does_not_move_with_a_shoulder(law, rules):
    """``runway_groups`` reads ``Runway.slab_corners``: the same axis,
    width and rings with and without a 75 m-wide shoulder on the ref."""
    def groups(a):
        cl = classify(a, law, rules)
        pm, _stats = planar_build(a, cl, law)
        return {g.ref: g for g in runway_groups(view(pm, law), a)}

    base = groups(_synthetic(gate=True, island=False))
    with_sh = groups(_shoulder_airport(300.0))
    assert set(base) == set(with_sh) == {"09/27"}
    b, s = base["09/27"], with_sh["09/27"]
    assert s.width_m == pytest.approx(b.width_m, abs=1e-6)
    assert s.axis_a == pytest.approx(b.axis_a) and s.axis_b == pytest.approx(b.axis_b)
    assert s.rings == b.rings
    # ...and it really is the runway's own slab: 30 m wide, 1060 m long
    assert b.width_m == pytest.approx(30.0, abs=0.01)
    assert b.length_m == pytest.approx(1060.0, abs=0.01)


# ── 4. apron cover refuses the corridor ──────────────────────────────────

def _apron_over_the_parallel(x0: float, x1: float):
    """The synthetic parallel taxiway page (x 100..900, y 100..125) with an
    OSM ``aeroway=apron`` way drawn over ``x0..x1`` of it.  The page is cut
    into a WEST and an EAST corridor cell by the taxiway at x = 500, so one
    way can cover one cell and leave the other bare — which is the whole
    point of reading the cover PER CELL."""
    a = _synthetic(gate=True, island=False)
    w = OsmWay(90001, "airport", _rect(x0, 95.0, x1, 130.0), True,
               {"aeroway": "apron"})
    return _dc.replace(a, osm_ways=a.osm_ways + (w,))


def _par_cells(cl):
    out = {}
    for c in cl.cells:
        if c.ref != "parallel":
            continue
        out[round(Polygon(c.ring, c.holes).centroid.x)] = c
    return out


def test_apron_cover_refuses_the_corridor_cell_it_covers(law, rules):
    """The parallel taxiway's page is a CORRIDOR (`primary_parallel`).  An
    `aeroway=apron` drawn over its WEST half makes the west cell APRON —
    and the proximity cut does not re-mint it a junction — while the EAST
    cell, with no apron over it, keeps the corridor.  The cover is the
    CELL's, never the page's."""
    assert rules.lot.apron_cover_fraction <= 0.5
    base = _par_cells(classify(_synthetic(gate=True, island=False), law, rules))
    assert base and all(c.role == "primary_parallel" for c in base.values())

    cl = classify(_apron_over_the_parallel(100.0, 500.0), law, rules)
    cells = _par_cells(cl)
    assert set(cells) == set(base), (sorted(cells), sorted(base))
    west = min(cells)
    for x, c in cells.items():
        if x == west:
            assert c.role == "apron" and c.kind == "apron", (x, c.role)
            assert c.evidence["apron_cover_refused_corridor"] == 1.0
            assert c.evidence["cell_apron_cover"] >= 0.85
            assert c.evidence.get("near_route") is None    # no proximity re-mint
        else:
            assert c.role == "primary_parallel", (x, c.role, c.evidence)
    assert "apron cover refused the corridor (§40 (2))" in "\n".join(role_census(cl))


def test_apron_cover_below_the_floor_leaves_the_corridor(law, rules):
    """5 % of the west cell under apron — half `lot.apron_cover_fraction`:
    every cell keeps its corridor."""
    cl = classify(_apron_over_the_parallel(100.0, 120.0), law, rules)
    cells = _par_cells(cl)
    assert cells and all(c.role == "primary_parallel" for c in cells.values()), \
        [(x, c.role, c.evidence.get("cell_apron_cover")) for x, c in cells.items()]


# ── 5. the shoulder keeps the datum and takes its own cross-slope ────────

def test_the_shoulder_cap_is_one_reading(law):
    """§40 (2) as amended (owner RULINGS 2026-09-13dd): inside the
    runway's own half width the law is the RUNWAY's transverse maximum;
    beyond it, the SHOULDER's.  One accessor
    (``law.tables.runway_transverse_cap``) — the generator, the v2 verify
    reader and the v1 census all price through it, so the three cannot
    disagree about where the runway ends."""
    from auto_patch_v2.law.tables import (runway_transverse_cap,
                                          runway_transverse_max)
    rwy = runway_transverse_max(law, "F", 4)
    shoulder = law.ruleset.runway.shoulder_transverse_max
    assert shoulder == 0.025 and rwy == 0.015
    assert runway_transverse_cap(law, 0.0, 30.0, "F", 4) == rwy
    assert runway_transverse_cap(law, 30.0, 30.0, "F", 4) == rwy   # ON the edge
    assert runway_transverse_cap(law, 30.01, 30.0, "F", 4) == shoulder
    assert runway_transverse_cap(law, 204.9, 30.0, "F", 4) == shoulder
    # HECA's two round-1 rows pass at the shoulder cap and failed at the
    # runway's: 1.5287 % at 108.665 m and 1.5233 % at 204.872 m
    for grade, d in ((0.015287, 108.665), (0.015233, 204.872)):
        assert grade > runway_transverse_cap(law, d, 30.0, "F", 4) * 0 + rwy
        assert grade <= runway_transverse_cap(law, d, 30.0, "F", 4)
    # no geometry (a patch that published no half width) keeps the runway
    assert runway_transverse_cap(law, 500.0, 0.0, "F", 4) == rwy


def test_the_census_reads_the_shoulder_line_from_the_sidecar(tmp_path):
    """The v1 census marks a SHOULDER vertex off the sidecar's
    ``runway_axes`` — the solve's own line — and never re-derives the
    width from the runway RINGS, which a shoulder fattens
    (``check_grade.shoulder_nids``)."""
    sys.path.insert(0, str(ROOT / "tools"))
    import check_grade as cg

    class _W:
        def __init__(self, tags, nids):
            self.tags, self.nids = tags, nids

    # a 60 m-wide runway along the equator-ish axis: half width 30 m
    nodes = {"1": (0.0, 0.0), "2": (0.0, 0.001), "3": (0.0002, 0.0),
             "4": (0.002, 0.0)}
    m_per_deg = 111_320.0

    def ll_to_m(lat, lon):
        return (lon * m_per_deg, lat * m_per_deg)

    ways = [_W({"role": "runway", "ref": "09/27"}, ["1", "2", "3", "4"])]
    axes = [["09/27", 0.0, 0.0, 0.0, 0.01, 30.0]]
    got = cg.shoulder_nids(ways, nodes, ll_to_m, axes)
    # node 3 is 22 m off the axis (inside), node 4 is 223 m off (shoulder)
    assert got == {"4"}, got
    # no published axes: nothing is a shoulder, the runway cap stands
    assert cg.shoulder_nids(ways, nodes, ll_to_m, None) == set()
    assert cg.shoulder_nids(ways, nodes, ll_to_m, []) == set()
    # the sidecar keys are the ones the solve publishes
    from auto_patch_v2.emit.osm_adapter import SIDECAR_KEYS
    assert "runway_axes" in SIDECAR_KEYS
    assert "shoulder_transverse_max" in SIDECAR_KEYS
    assert cg.SIDECAR_LAW_KEYS["runway_axes"] == "runway_axes_ll"
    assert cg.SIDECAR_LAW_KEYS["shoulder_transverse_max"] == \
        "shoulder_transverse_max"


# ── 6. a shoulder manufactures no REGION (§40 (4)) ───────────────────────

def test_a_shoulder_manufactures_no_region(law, rules):
    """§40 (4) (owner RULINGS 2026-09-14s): a shoulder carries the runway's
    datum but NO region — it is excluded where the strip keep-out and the
    zone bands are derived, and inherits its host runway's.

    The VHHH defect: three shoulder cells beside 07R/25L buffered by the
    75 m strip half width refused the `tunnel1_done.obj` road tunnel and
    minted 587,849 m² of zone-2 band.  Read here on the derivations
    themselves: the same airport with and without a shoulder yields the
    SAME strip keep-out and the same runway zone-band sources."""
    from auto_patch_v2.classify.roles import is_runway_shoulder
    from auto_patch_v2.planar.shapes import strip_keepout

    base = classify(_synthetic(gate=True, island=False), law, rules)
    withs = classify(_shoulder_airport(300.0), law, rules)
    sh = [c for c in withs.cells if is_runway_shoulder(c)]
    assert len(sh) == 1 and sh[0].role == "runway"
    # the predicate is exact: nothing else in either classification is one
    assert not [c for c in base.cells if is_runway_shoulder(c)]
    assert not [c for c in withs.cells
                if is_runway_shoulder(c) and c.kind != "runway_shoulder"]

    # (a) the joint keep-out: the shoulder adds no polygon of its own
    a = strip_keepout(base, law)
    b = strip_keepout(withs, law)
    ua = unary_union(a) if a else Polygon()
    ub = unary_union(b) if b else Polygon()
    assert ua.symmetric_difference(ub).area < 1.0, (ua.area, ub.area)

    # (b) the zone bands: the runway group's sources are the SLAB cells
    # only, so the band population does not grow with the shoulder
    from auto_patch_v2.planar.zones import RUNWAY_FAMILY as ZRF

    def band_sources(cl):
        return sorted(round(Polygon(c.ring, c.holes).area, 3)
                      for c in cl.cells
                      if c.role in ZRF and not is_runway_shoulder(c))
    assert band_sources(base) == band_sources(withs)
    # ...and the shoulder really is in the runway family, so only the
    # predicate — not the role — keeps it out
    assert sh[0].role in ZRF


# ── 7. a shoulder runs ALONG a runway, it does not enclose one ───────────

def _wrapping_airport():
    """The synthetic runway (y = -15..15, x = 0..1060) inside ONE paved
    area that surrounds it — LERM's class: at a small aerodrome the whole
    apron/hangar pavement wraps the strip."""
    a = _synthetic(gate=True, island=False)
    page = Pavement("wrap", Surface.ASPHALT,
                    _rect(-40.0, -60.0, 1100.0, 60.0), ())
    return _dc.replace(a, pavements=a.pavements + (page,))


def test_a_page_that_wraps_the_runway_is_not_its_shoulder(law, rules):
    """§40 (1) (owner RULINGS 2026-09-14ba, the +40-004 tile abort): a
    cell sharing more than `corridor.runway_shoulder_max_wrap` of the
    RUNWAY RING's own length encloses the runway — it is the ground the
    strip sits in, not a shoulder — however narrow its mean depth.

    MEASURED at LERM: the 65,655 m2 cell at 40.8665330,-3.2447104 shares
    2,135 m of a 2,135 m ring (wrap 1.00) at 30.7 m mean depth, passed
    both other tests, took the runway's datum while its own ground falls
    7.5 %, and minted 43 `runway_transverse` DEFECT rows that ABORTED the
    owner's tile.  Real shoulders wrap 0.01-0.55 (HECA 32 cells, VHHH
    23)."""
    cl = classify(_wrapping_airport(), law, rules)
    sh = [c for c in cl.cells if c.kind == "runway_shoulder"]
    assert not sh, [(c.ref, c.evidence) for c in sh]
    # the wrapping page is still classified, just not as the runway
    assert [c for c in cl.cells if c.ref.split("#")[0] == "wrap"]
    # ...and the plain ribbon beside the same runway still is a shoulder,
    # so it is the WRAP that refused, not the geometry in general
    cl2 = classify(_shoulder_airport(300.0), law, rules)
    keep = [c for c in cl2.cells if c.kind == "runway_shoulder"]
    assert len(keep) == 1
    assert keep[0].evidence["shoulder_wrap"] < rules.corridor.runway_shoulder_max_wrap
