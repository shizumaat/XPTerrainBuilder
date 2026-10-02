"""§2 THE PLANE-PAD MINT — the twins (``docs/specs/building-base-profile-
spec.md`` §2 (1)/(2)/(3), §3 C1/C2/C7/C13/C15, §4, §5 A1; owner RULINGS
2026-10-01f and 10-01k Q2/Q3/Q4/Q5).  Lane ``basepads3``.

PR #174 landed the composed-unit read (§1 (3)) and withheld the MINT, for
the reason it reported as its finding 3: *a plane pad minted without its
hard pin is two independently frontage-held pads at two FREE datums — an
uncontrolled cliff, worse than today's single pad.*  So the three things
these twins hold are one thing:

1. **The regions** (``geom.base_planes``) — one pad per base plane,
   clipped to the unit's pad, with the ``min_distinct_spacing_m`` RISER
   STRIP cut out of BOTH neighbours so no two rims share an XY (§4, the
   identity law).  The strip claims no pad: it is the wall GAP (RULINGS
   2026-09-01c), and the mesher's triangles across it are the steep ones.
2. **The mint** (``planar.plane_pads``) — the refs ``<unit>/p<k>``, the
   registries, and the DECLARED ``base_step`` riser; and byte-for-byte
   NOTHING for a unit reading FLAT / ROOF / FEET (§1 (3), §5 A5's control
   counts).
3. **The pin** (``constraints.platform.plane_offset_rows``) — one hard
   row ``z[D_k] − z[D_0] = Δy_k`` per non-origin plane pad, at the
   object's own authored riser, ranked WITH the pad hold (C13).

THE SHAPE EVERY GEOMETRY TWIN USES is KASE site 2, the fire station the
owner read (#163, §0 facts 5–7): a floor plane at 0 and a LOT at **+3.9**
beside it, the lot 6,394 m² in TWO PIECES (§4).  The numbers are the
spec's own, so a twin that passes here is measuring the site the ruling
was written for.

Hermetic: no corpus, no network, no pack, no OBJ on disk.  Every fixture
write goes through an explicit ``encoding=`` / ``newline=`` (the Windows
text-IO law, ``tests/test_windows_text_io.py``).
"""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from auto_patch_v2.airport import obj8_grade as BG
from auto_patch_v2.airport.placement_contact import m_per_deg_exact
from auto_patch_v2.constraints import platform as CP
from auto_patch_v2.geom import base_planes as BPG
from auto_patch_v2.law import Law
from auto_patch_v2.model import base_step as BS
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.model.planar import plane_of, plane_ref, unit_ref_of
from auto_patch_v2.planar import plane_pads as PP
from auto_patch_v2.planar.overlay import Region

#: §0 fact 5: the lot stands +3.9 m over the station floor.
LOT_DY = 3.9
#: §1 (1) / §4: the riser strip is ``[identity] min_distinct_spacing_m``.
STRIP_M = 0.5
#: §1 (1): two planes are ADJACENT within ``[seam] pad_frontage_m``.
FRONTAGE_M = 3.0
#: §1 (1): the smallest plane the mint keeps, ``[building_pad] min_area_m2``.
MIN_AREA_M2 = 250.0
#: a plain mid-latitude anchor; nothing in the mint depends on WHERE.
ANCHOR = (39.2213, -106.8704)


def _sq(x0, y0, w, d) -> Polygon:
    return Polygon([(x0, y0), (x0 + w, y0), (x0 + w, y0 + d), (x0, y0 + d)])


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ══════════════════════════════════════════════════════════════════════
# 1  THE REGIONS (geom.base_planes)
# ══════════════════════════════════════════════════════════════════════

#: THE FIRE-STATION SHAPE in the composed frame (metres east/north of the
#: unit anchor): the station FLOOR 40 x 30 at y 0, and the LOT at +3.9
#: beside it in two pieces — 60 x 60 TOUCHING the floor's east edge, and a
#: 20 x 20 outlier 20 m further east (§4's "6,394 m² in two pieces").
FLOOR = _sq(0.0, 0.0, 40.0, 30.0)
LOT = MultiPolygon([_sq(40.0, 0.0, 60.0, 60.0), _sq(120.0, 0.0, 20.0, 20.0)])
#: the unit's pad: the footprint union the 23a cut and the 28b terrace left
PAD = _sq(-5.0, -5.0, 150.0, 70.0)


def _regions(planes=(FLOOR, LOT), ys=(0.0, LOT_DY), risers=((0, 1, LOT_DY),),
             pad=PAD, **over):
    kw = dict(strip_m=STRIP_M, frontage_m=FRONTAGE_M,
              min_area_m2=MIN_AREA_M2)
    kw.update(over)
    counts: dict = {}
    regs, strips = BPG.plane_regions(list(planes), list(ys), list(risers),
                                    pad, counts=counts, **kw)
    return regs, strips, counts


def test_a_stepped_unit_yields_one_region_per_base_plane():
    """§2 (1): "where today the unit mints ONE ``building`` pad over its
    footprint union, it mints one pad REGION per base plane"."""
    regs, strips, counts = _regions()
    assert counts == {}, counts
    assert sorted({r.k for r in regs}) == [0, 1]
    assert len(strips) == 1
    # the LOT came in two pieces and stays two pieces (§1 (1) forbids the
    # hull exactly so the gap between them is not claimed)
    assert len([r for r in regs if r.k == 1]) == 2
    assert [r.dy for r in regs if r.k == 1] == [pytest.approx(LOT_DY)] * 2
    assert all(r.dy == 0.0 for r in regs if r.k == 0)


def test_the_riser_strip_is_cut_out_of_BOTH_planes_at_the_identity_spacing():
    """§2 (3) / §4: the two rims are two vertex rows
    ``min_distinct_spacing_m`` apart, never coincident XY.  Half the
    spacing comes off each side, so the gap between the pads is exactly
    the spacing and NEITHER pad claims it."""
    regs, strips, _c = _regions()
    lo = [r.polygon for r in regs if r.k == 0]
    hi = [r.polygon for r in regs if r.k == 1]
    assert len(strips) == 1 and strips[0].a == 0 and strips[0].b == 1
    assert strips[0].dy == pytest.approx(LOT_DY)
    # RE-FOUNDED (owner RULINGS 2026-10-02m (C)/(D), lane basepads4):
    # ``p0`` is now THE PAD LESS the other planes less the strips, so it
    # wraps the upper plane and the reading that states the law is the
    # strip itself -- its interior is claimed by NOTHING, and the upper
    # plane's rim stands the strip's half-width off the riser line.
    mid = Point(40.0, 15.0)                     # on the shared edge x = 40
    assert not any(q.covers(mid) for q in lo + hi)
    assert strips[0].strip.covers(mid)
    
    # the upper plane gave up half the spacing along the riser line
    assert min(q.distance(Point(40.0, 15.0)) for q in hi) >= 0.5 * STRIP_M - 0.02
    # the regions PARTITION the pad: disjoint, and their union is the
    # pad less the strips (10-02m (D), the SPJC overlap STOP)
    from shapely.ops import unary_union
    allr = lo + hi
    for i in range(len(allr)):
        for j in range(i + 1, len(allr)):
            assert allr[i].intersection(allr[j]).area < 1e-6
    left = PAD.difference(unary_union([s.strip for s in strips]))
    assert unary_union(allr).area == pytest.approx(left.area, rel=1e-6)


def test_a_sub_floor_riser_never_reaches_the_mint():
    """§1 (1): "a riser under ``pad_terrace_floor_m`` WELDS (the two
    planes are one plane at the area-weighted height — a kerb is not a
    terrace)".  The WELD is the base read's; what this twin holds is that
    the mint refuses a pair the read did not hand it a riser for, rather
    than inventing one."""
    regs, strips, counts = _regions(risers=())
    assert (regs, strips) == ([], [])
    assert counts.get("no_riser") == 1


def test_one_plane_mints_nothing_so_a_FLAT_unit_is_byte_identical():
    """§1 (3) / §5 A1: "a unit with no base plane keeps today's law
    exactly".  One plane is today's pad; the mint must hand back nothing
    at all rather than one pad renamed ``/p0`` — a rename is not
    byte-identical."""
    regs, strips, counts = _regions(planes=(FLOOR,), ys=(0.0,), risers=())
    assert (regs, strips) == ([], [])
    assert counts.get("one_plane") == 1       # and it SAYS which gate closed
    # ... and so does a profile with no plane at all (ROOF / FEET)
    assert _regions(planes=(), ys=(), risers=())[:2] == ([], [])


def test_a_plane_outside_the_unit_pad_is_clipped_not_widened():
    """§2 (1) "clipped to the unit footprint union": a lot the pack
    authored wider than the bodies standing on it never widens the unit's
    claim on the apron."""
    wide = _sq(40.0, 0.0, 400.0, 60.0)          # runs 300 m past the pad
    regs, strips, _c = _regions(planes=(FLOOR, wide), risers=((0, 1, LOT_DY),))
    assert strips and regs
    hi = [r.polygon for r in regs if r.k == 1]
    assert hi and all(PAD.buffer(1e-9).covers(p) for p in hi)
    assert sum(p.area for p in hi) < wide.area


def test_a_plane_under_the_area_floor_is_dropped_and_counted():
    """§1 (1): under ``min_area_m2`` a plane is FURNITURE.  A 40 m² pad
    with its own datum column and hold set is a solver liability, not a
    terrace."""
    small = _sq(40.0, 0.0, 8.0, 5.0)            # 40 m²
    regs, strips, counts = _regions(planes=(FLOOR, small),
                                    risers=((0, 1, LOT_DY),))
    assert (regs, strips) == ([], [])
    assert counts.get("plane_under_min") == 1
    assert counts.get("one_plane_after_cut") == 1


def test_the_ORIGIN_plane_is_THE_PAD_LESS_THE_OTHERS():
    """RE-FOUNDED (owner RULINGS 2026-10-02m (C)/(D), lane basepads4).

    This twin asserted that a unit whose ``p0`` FACE UNION fell under the
    area floor minted nothing.  ``p0`` is no longer its face union: it is
    THE PAD LESS the other planes less the strips (10-02m (C)), because
    #196 replaced the unit's pad region with the planes' own unions and
    left whatever they did not cover UNCLAIMED -- a hole where a building
    pad had been -- while SPJC's p0/p1 came out as the SAME polygon
    (10-02m (D)).  So a tiny ``p0`` face union still mints: the ground
    the lot does not take is ``p0``'s, which is exactly today's law for
    it, and ``p0``'s outer ring stays the PAD'S own so no airside vertex
    can move.  ``origin_under_min`` now fires only where the PAD itself
    has nothing left."""
    tiny = _sq(32.0, 0.0, 8.0, 5.0)          # ADJACENT to the lot's west rim
    regs, strips, counts = _regions(planes=(tiny, LOT), ys=(0.0, LOT_DY))
    assert strips and {r.k for r in regs} == {0, 1}
    z = [r.polygon for r in regs if r.k == 0]
    hi = [r.polygon for r in regs if r.k == 1]
    # p0 is the pad's remainder, not the 40 m2 face union
    assert sum(q.area for q in z) > sum(q.area for q in hi)
    # and its outer ring is the PAD'S own, coordinate for coordinate
    big = max(z, key=lambda q: q.area)
    assert set(big.exterior.coords) == set(PAD.exterior.coords)


def test_planes_that_face_each_other_nowhere_mint_nothing():
    """§1 (1): a riser exists only between planes whose polygons are within
    ``pad_frontage_m``.  A pair the read listed but that the CLIP pulled
    apart is not a terrace — and must not come out as two unpinned pads."""
    far = _sq(100.0, 0.0, 40.0, 40.0)           # 60 m from the floor
    regs, strips, counts = _regions(planes=(FLOOR, far),
                                    risers=((0, 1, LOT_DY),))
    assert (regs, strips) == ([], [])
    assert counts.get("riser_no_facing_rim") == 1


def test_the_declared_riser_is_the_objects_own_height_not_a_measurement():
    """§2 (3): ``declared_step_m = Δy``.  The pair arrives in either order
    and the riser is read LOW-to-HIGH, so the declaration carries the
    object's authored sign."""
    _r, strips, _c = _regions(risers=((1, 0, -LOT_DY),))
    assert len(strips) == 1
    assert (strips[0].a, strips[0].b) == (0, 1)
    assert strips[0].dy == pytest.approx(LOT_DY)


# ── the frame conversion (the composed frame -> the planar frame) ─────────

def _frame():
    """A planar frame about :data:`ANCHOR`: ``entry(lon, lat) -> (x, y)``
    metres east/north, and its inverse.  The mint's own conversion is the
    only thing under test, so the frame is the simplest exact one."""
    ml, mo = m_per_deg_exact(ANCHOR[0])

    def entry(lon, lat):
        return ((float(lon) - ANCHOR[1]) * mo, (float(lat) - ANCHOR[0]) * ml)

    def to_ll(x, y):
        return (ANCHOR[0] + float(y) / ml, ANCHOR[1] + float(x) / mo)
    return entry, to_ll


def test_place_round_trips_the_composition_frame_to_the_planar_frame():
    """``geom.base_planes.place``: the composed polygons are metres
    east/north of the unit anchor; the planar map's frame is the
    airport's.  The conversion is the composition's own two steps in
    reverse, so with a frame centred on that anchor it is the IDENTITY —
    and a twin that did not assert it would let a silently mirrored or
    scaled placement put a pad somewhere plausible."""
    entry, _to_ll = _frame()
    got = BPG.place([FLOOR, LOT], ANCHOR, entry, m_per_deg_exact(ANCHOR[0]))
    assert len(got) == 2 and all(g is not None for g in got)
    assert got[0].area == pytest.approx(FLOOR.area, rel=1e-9)
    assert got[1].area == pytest.approx(LOT.area, rel=1e-9)
    for (ax, ay), (bx, by) in zip(FLOOR.exterior.coords,
                                  got[0].exterior.coords):
        assert math.hypot(ax - bx, ay - by) < 1e-6
    assert BPG.place([None], ANCHOR, entry, m_per_deg_exact(ANCHOR[0])) == [None]


# ══════════════════════════════════════════════════════════════════════
# 2  THE MINT (planar.plane_pads)
# ══════════════════════════════════════════════════════════════════════

class _Frame:
    def __init__(self):
        self._entry, self._to_ll = _frame()

    def entry(self):
        return self._entry

    def transformers(self):
        return self._entry, self._to_ll


class _Airport:
    frame = None

    def __init__(self):
        self.frame = _Frame()


class _Cluster:
    """The two fields the mint reads off a ``PlanCluster`` (§1 (4) /
    C1) — the composed profile and the frame it is in."""

    def __init__(self, cid: str, prof: BG.BaseProfile):
        self.id = cid
        self.base_profile = BG.profile_to_json(prof)
        self.profile_anchor = ANCHOR


def _profile(verdict=BG.STEPPED, planes=((0.0, FLOOR), (LOT_DY, LOT)),
             risers=((0, 1, LOT_DY),), slope=(0.0, 0.0)) -> BG.BaseProfile:
    return BG.BaseProfile(
        verdict=verdict,
        planes=tuple(BG.BasePlane(y=y, area_m2=float(p.area), polygon=p)
                     for y, p in planes),
        risers=tuple(BG.Riser(a, b, dy) for a, b, dy in risers),
        slope=slope, feet=1041, feet_y=-0.2)


def _pad(ref="building2", poly=PAD):
    return Region("building", ref, poly, None, None, "airside", "cell")


def _mint(law, prof, pads=None, monkeypatch=None, cid="unit:108#0"):
    """``plane_pad_split`` over ONE cluster, with the cluster DERIVATION
    stubbed (it is #174's own twins' subject — ``test_base_profile_
    compose.py``) so this twin measures the MINT."""
    pads = list(pads if pads is not None else [_pad()])
    cl = _Cluster(cid, prof)
    monkeypatch.setattr(PP, "_cluster_pieces",
                        lambda airport, law_: [(cl, PAD)])
    return PP.plane_pad_split(pads, law, 0.5, _Airport())


#: RE-FOUNDED (owner RULINGS 2026-10-02m (C), lane basepads4): ``p0``'s
#: ref IS the unit's own, because the mint now runs AFTER
#: ``platform_split`` and ``p0`` is the region the split already minted
#: -- with its platform record, its collar, its hold and its datum
#: column all keyed on that ref (``planar/plane_pads._ref_of``).
_P0 = "building2"


def test_the_mint_replaces_the_unit_pad_with_one_pad_per_plane(law, monkeypatch):
    """§2 (1) + C7, RE-FOUNDED (owner RULINGS 2026-10-02m (C), lane
    basepads4): a non-origin plane takes ``<unit>/p<k>`` and ``p0``
    KEEPS THE UNIT'S OWN REF.

    #196 renamed every plane including ``p0`` to ``<unit>/p0``, and the
    mint ran BEFORE ``platform_split``.  The mint now runs LAST (after
    ``plateau_cut``, so nothing downstream of it reads the airside --
    10-02m (C)'s 214 runway movers), which means ``p0`` IS the region
    the split already minted: its platform record, its collar, its hold
    and its datum column are all keyed on the unit ref, and renaming it
    would orphan every one of them.  Keeping the ref is §2 (1)'s "p0
    takes the unit's datum exactly as today", literally.
    ``unit_ref_of`` still folds the lot back to ONE unit, so every
    reader keyed on it -- ``pad_cluster_mismatch`` among them, C25 --
    sees one cluster."""
    got, counts = _mint(law, _profile(), monkeypatch=monkeypatch)
    refs = sorted(str(r.ref) for r in got)
    assert refs == ["building2", plane_ref("building2", 1),
                    plane_ref("building2", 1)]
    assert {unit_ref_of(r) for r in refs} == {"building2"}
    assert {(plane_of(r) or ("building2", 0))[1] for r in refs} == {0, 1}
    assert counts["plane_units"] == 1 and counts["base_steps"] == 1
    assert counts["plane_pads"] == 2
    # every minted region keeps the pad's ROLE: a plane pad is a pad
    assert {r.role for r in got} == {"building"}


def test_the_registries_carry_the_offsets_and_the_declared_riser(law, monkeypatch):
    """§2 (1)/(3) + C15: ``PLANE_PADS`` carries Δy per plane (``p0`` 0),
    ``BASE_STEPS`` the DECLARED riser, the strip's width and its area."""
    _got, _c = _mint(law, _profile(), monkeypatch=monkeypatch)
    pads = BS.plane_pads_of_unit("building2")
    assert [p.k for p in pads] == [0, 1]
    assert pads[0].dy_m == 0.0 and pads[0].y_m == 0.0
    assert pads[1].dy_m == pytest.approx(LOT_DY)
    assert pads[1].y_m == pytest.approx(LOT_DY)
    assert all(p.verdict == BG.STEPPED and p.gradient is None for p in pads)
    assert BS.origin_ref_of("building2") == _P0
    assert len(BS.BASE_STEPS) == 1
    st = BS.BASE_STEPS[0]
    assert st.declared_step_m == pytest.approx(LOT_DY)
    assert (st.lower_ref, st.upper_ref) == (_P0,
                                            plane_ref("building2", 1))
    assert st.strip_width_m == pytest.approx(STRIP_M)
    assert st.strip_m2 > 0.0
    # Q2: the riser is the strip, never a 1:3 bank — a 3.9 m riser over a
    # 1:3 bank would need 11.7 m of ground, and the strip is 0.5 m
    assert st.strip_m2 < 11.7 * 70.0
    # the line is lat/lon (the sidecar's own coordinates)
    assert st.line and all(abs(la - ANCHOR[0]) < 0.01 and abs(lo - ANCHOR[1]) < 0.01
                           for part in st.line for la, lo in part)


@pytest.mark.parametrize("verdict", [BG.FLAT, BG.FEET])
def test_a_FLAT_or_FEET_unit_mints_nothing_and_the_layout_is_identical(
        law, monkeypatch, verdict):
    """§1 (3) / §5 A5: a unit reading FLAT or FEET (KASE site 1's
    shelters) keeps today's law exactly — the SAME region objects come
    back and both registries stay empty, so no control pad count can
    move."""
    pads = [_pad(), _pad("building9", _sq(500.0, 0.0, 40.0, 40.0))]
    prof = _profile(verdict=verdict, planes=((0.0, FLOOR),), risers=())
    got, counts = _mint(law, prof, pads=pads, monkeypatch=monkeypatch)
    assert [str(r.ref) for r in got] == ["building2", "building9"]
    assert all(a is b for a, b in zip(got, pads))      # the same objects
    assert not BS.PLANE_PADS and not BS.BASE_STEPS
    assert counts["plane_pads"] == 0 and counts["base_steps"] == 0


def test_a_ROOF_read_mints_nothing_which_is_the_HECA_T3_stop(law, monkeypatch):
    """§6's STOP: "HECA T3 gaining any plane pad".  §1 (3)'s composed read
    returns FEET with NO plane for a unit whose planes all read as roofs
    (#174's own twin measures that); what this one holds is the mint's
    side — a profile with no plane pair mints nothing, so the STOP cannot
    be crossed here even if a composed read regressed to one plane."""
    prof = BG.BaseProfile(BG.FEET, why="every composed plane read as a roof")
    got, counts = _mint(law, prof, monkeypatch=monkeypatch)
    assert [str(r.ref) for r in got] == ["building2"]
    assert not BS.PLANE_PADS and not BS.BASE_STEPS and counts["plane_pads"] == 0


def test_a_SLOPED_unit_keeps_ONE_pad_and_carries_the_base_gradient(
        law, monkeypatch):
    """§2 (2) + 10-01k Q5: a SLOPED base carries the OBJECT'S OWN gradient
    with no 1.5 % clamp, and its airside frontage WELDS as it does today
    — so the LAYOUT is untouched (one pad, its own ref) and only the
    pad's plane rows change."""
    prof = _profile(verdict=BG.SLOPED, planes=((0.0, FLOOR),), risers=(),
                    slope=(0.0102, -0.004))
    got, counts = _mint(law, prof, monkeypatch=monkeypatch)
    assert [str(r.ref) for r in got] == ["building2"]       # no /p0 rename
    assert counts["sloped_units"] == 1 and counts["base_steps"] == 0
    pad = BS.PLANE_PADS["building2"]
    assert pad.k == 0 and pad.dy_m == 0.0 and pad.verdict == BG.SLOPED
    assert pad.gradient == pytest.approx((0.0102, -0.004))
    # Q5's "no 1.5 % clamp": the carried gradient is the object's, and
    # 1.02 % is KASE unit:82's own live reading (§0 fact 10)
    assert math.hypot(*pad.gradient) > float(
        law.tables.emit.within_shape.pad_slope_max)
    assert not BS.BASE_STEPS


def test_a_rim_sliver_of_a_replaced_pad_joins_its_nearest_plane_pad(
        law, monkeypatch):
    """ONE REF, ONE PAD (the ``platform_split`` ``_to_block`` rule): a 23a
    rim sliver still carrying the unit's ref would otherwise name a pad
    that no longer exists.  It joins the plane pad it stands nearest."""
    sliver = _pad("building2", _sq(145.1, 0.0, 2.0, 2.0))   # east, by the lot
    got, _c = _mint(law, _profile(), pads=[_pad(), sliver],
                    monkeypatch=monkeypatch)
    moved = [r for r in got if r.polygon is sliver.polygon]
    assert len(moved) == 1
    # RE-FOUNDED (owner RULINGS 2026-10-02m (C)/(D), lane basepads4):
    # ``p0`` is now THE PAD LESS the other planes (not its own 40 m2
    # face union), so it reaches the pad's east rim and IS the nearest
    # region to a sliver standing just outside it -- the sliver joins
    # ``p0``, which keeps the unit's own ref.  Either way the law the
    # twin states holds: no region is left naming a pad that does not
    # exist.
    assert unit_ref_of(moved[0].ref) == "building2"
    assert str(moved[0].ref) in {_P0, plane_ref("building2", 1)}


def test_a_cluster_carrying_NO_PROFILE_AT_ALL_mints_nothing_and_never_raises(
        law, monkeypatch):
    """§1 (3) "a unit with no base plane keeps today's law exactly", at the
    channel (lane basepads4).

    The mint reads ``Airport.clusters`` now -- the stamped derivation,
    not a re-run of it (10-02m (F): the ``id(airport)`` memo missed and
    cost 36 of 37.7 s at HECA).  That channel is PUBLIC, and a cluster on
    it may carry no ``base_profile`` attribute at all: a plan before
    version 12, or a cluster-shaped fixture.  Reading it as an attribute
    took **17 tests red** across ``test_v2clusterpad.py`` and
    ``test_v2jetwaystrip.py`` in the full suite, which is this twin's
    measurement.  No profile means NO MINT, not an AttributeError."""
    class _Bare:
        id = "unit:0#0"                         # no base_profile at all

    airport = _Airport()
    airport.clusters = (_Bare(),)
    pads = [_pad()]
    got, counts = PP.plane_pad_split(pads, law, 0.5, airport)
    assert got == pads
    assert counts["plane_pads"] == 0 and counts["plane_units"] == 0
    assert not BS.PLANE_PADS and not BS.BASE_STEPS
    assert "no cluster reads STEPPED or SLOPED" in str(PP.WHY.get("gate"))


def test_the_mint_is_a_no_op_with_the_base_read_disarmed(law, monkeypatch):
    """§1 (1): ``[base_profile] horizontal_ny`` 0 disarms the read, so
    there is no profile to mint from — ONE gate, the read's own."""
    import copy
    off = copy.deepcopy(law)
    object.__setattr__(off.tables.structures.base_profile, "horizontal_ny", 0.0)
    pads = [_pad()]
    monkeypatch.setattr(PP, "_cluster_pieces",
                        lambda a, l: [(_Cluster("u", _profile()), PAD)])
    got, counts = PP.plane_pad_split(pads, off, 0.5, _Airport())
    assert got == pads and counts["plane_pads"] == 0
    assert "disarmed" in str(PP.WHY.get("gate"))


# ══════════════════════════════════════════════════════════════════════
# 3  THE PIN (constraints.platform.plane_offset_rows)
# ══════════════════════════════════════════════════════════════════════

def _pin_rows(law, monkeypatch, cols):
    monkeypatch.setattr(CP, "datum_vertices", lambda planar, law_: dict(cols))
    return CP.plane_offset_rows(object(), law)


def _pads_registered(unit="building2", dys=(0.0, LOT_DY)):
    BS.PLANE_PADS.clear()
    for k, dy in enumerate(dys):
        # the mint's OWN ref rule (10-02m (C)): ``p0`` keeps the unit ref
        ref = PP._ref_of(unit, k)
        BS.PLANE_PADS[ref] = BS.PlanePad(ref=ref, unit=unit, k=k, dy_m=dy,
                                         y_m=dy, area_m2=1000.0,
                                         verdict=BG.STEPPED)


def test_one_hard_row_per_non_origin_plane_at_the_authored_riser(
        law, monkeypatch):
    """§2 (1): ONE hard row ``z[D_k] − z[D_0] = Δy_k`` between the two
    DATUM COLUMNS — no new column class and no new row generator.  Stated
    as a ``Diff`` at cap 0 against a relief target, which reads
    ``-0 <= (z[a] − rel) − z[b] <= 0``: the equality, exactly."""
    _pads_registered()
    rows = _pin_rows(law, monkeypatch,
                     {_P0: 7, plane_ref("building2", 1): 11})
    assert len(rows) == 1                     # p0 keeps today's datum law
    r = rows[0]
    assert isinstance(r, Diff)
    assert (r.a, r.b) == (11, 7)              # p1 against p0, in that order
    assert r.cap == 0.0 and r.bound_m == 0.0
    assert r.rel == pytest.approx(LOT_DY)
    assert r.soft is None and r.follows is None      # HARD, two-way
    assert r.source.ruling.startswith(CP.PLANE_OFFSET_RULING)
    assert CP.STATS["plane_offset_rows"] == {"pins": 1, "no_datum_column": 0,
                                             "no_origin_pad": 0,
                                       "ghost_dropped": 0, "ghosts": ""}


def test_the_pin_head_is_hard_law_ranked_WITH_the_pad_hold(law):
    """§2 (1) + C13: the head stands in ``[design] hard_rulings`` and in
    EXACTLY ONE §5a tier — the PAD tier, the lowest law rank, so an IIS
    naming it relaxes it and the unit falls back towards one pad instead
    of moving a runway (§6's STOP)."""
    d = law.tables.emit.design
    assert CP.PLANE_OFFSET_RULING in d.hard_rulings
    tiers = [i for i, t in enumerate(d.hard_conflict_ranks)
             if CP.PLANE_OFFSET_RULING in t]
    assert len(tiers) == 1
    assert d.hard_conflict_tiers[tiers[0]] == "pad"
    # and it ranks WITH the hold, not above or below it
    assert CP.HOLD_RULING in d.hard_conflict_ranks[tiers[0]]


class _FacePlanar:
    """The least planar map that answers "does this ref own a face?" --
    what :func:`constraints.platform._has_no_face` reads to tell a pad
    PRESENT but columnless from the registry GHOST."""

    class _F:
        def __init__(self, ref):
            self.ref = ref
            self.ring = 0
            self.holes = ()

    def __init__(self, refs):
        self.faces = {i: self._F(r) for i, r in enumerate(refs)}
        self.vertices = {}

    def ring_vertices(self, _ring):
        return ()


def test_a_plane_pad_PRESENT_but_columnless_is_reported_never_pinned(
        law, monkeypatch):
    """A plane that touches no apron has no stage-1 datum column of its
    own (Q3's case); a pin onto a column that is not an unknown is a row
    on a constant.  It is COUNTED, so the unit's fallback is readable.

    RE-FOUNDED (PR #220 item 5/6, lane basepads4read): this now needs a
    pad that OWNS A FACE, because a columnless pad with no face at all is
    the registry GHOST and is counted apart -- see the twin below."""
    _pads_registered()
    ref = plane_ref("building2", 1)
    monkeypatch.setattr(CP, "datum_vertices", lambda planar, law_: {_P0: 7})
    rows = CP.plane_offset_rows(_FacePlanar([_P0, ref]), law)
    assert rows == []
    st = CP.STATS["plane_offset_rows"]
    assert st["no_datum_column"] == 1, st
    assert st["ghost_dropped"] == 0, st
    assert ref in BS.PLANE_PADS                 # present: NOT evicted


def test_the_REGISTRY_GHOST_is_named_apart_and_EVICTED(law, monkeypatch):
    """PR #220 items 5/6, measured by lane basepads4read: SPJC
    ``building21/p3`` (1,316 m2, +3.94 m) sat in ``PLANE_PADS`` and
    ``BASE_STEPS`` with **no region in the patch** -- the mint gave it a
    region and the arrangement later dropped it (``merge_slivers``, §41
    absorption) -- and it read as the one ``no_datum_column``, pointing
    at the pin instead of at the ghost.

    A pad with NO FACE AT ALL is not a pin failure: it is a pad the
    layout does not contain.  It is counted apart and EVICTED, so the
    publication cannot list a pad the patch has not got."""
    _pads_registered()
    ref = plane_ref("building2", 1)
    BS.BASE_STEPS.append(BS.BaseStep(
        unit="building2", lower_ref=_P0, upper_ref=ref, lower_k=0,
        upper_k=1, declared_step_m=LOT_DY, strip_m2=10.0,
        strip_width_m=0.5))
    monkeypatch.setattr(CP, "datum_vertices", lambda planar, law_: {_P0: 7})
    rows = CP.plane_offset_rows(_FacePlanar([_P0]), law)   # p1 owns NO face
    assert rows == []
    st = CP.STATS["plane_offset_rows"]
    assert st["ghost_dropped"] == 1, st
    assert st["no_datum_column"] == 0, st
    assert ref in st["ghosts"]
    # EVICTED from both registries, so nothing downstream publishes it
    assert ref not in BS.PLANE_PADS
    assert not any(b.upper_ref == ref for b in BS.BASE_STEPS)


def test_no_plane_pad_means_no_row_at_all(law, monkeypatch):
    """§5 A6: "stage 1 rows grow by ONE Diff per non-origin plane pad" —
    and by none at an airport with no stepped building, which is every
    control (§5 A5)."""
    BS.PLANE_PADS.clear()
    assert CP.plane_offset_rows(object(), law) == []


def test_a_sloped_pad_is_never_pinned(law, monkeypatch):
    """§2 (2): a SLOPED unit has ONE pad at its own datum.  ``k`` 0 is the
    origin plane, so the pin skips it — a sloped pad pinned to itself
    would be a degenerate row."""
    BS.PLANE_PADS.clear()
    BS.PLANE_PADS["building2"] = BS.PlanePad(
        ref="building2", unit="building2", k=0, dy_m=0.0, y_m=0.0,
        area_m2=1000.0, gradient=(0.0102, -0.004), verdict=BG.SLOPED)
    assert _pin_rows(law, monkeypatch, {"building2": 7}) == []


@pytest.fixture(autouse=True)
def _clean():
    """Both registries are arrangement-scoped (``model.base_step``): a twin
    that left one filled would hand the next the previous mint."""
    BS.PLANE_PADS.clear()
    BS.BASE_STEPS.clear()
    yield
    BS.PLANE_PADS.clear()
    BS.BASE_STEPS.clear()


# ══════════════════════════════════════════════════════════════════════
# 5  WHAT lane basepads4read MEASURED ON THE REAL CAPTURES (PR #220)
#
# A reader lane re-captured KASE / SPJC / HECA / KCLT / CYXY and replayed
# this mint against a matched no-mint arm.  Three of its findings are
# STOPs.  Each one below is the measurement turned into a twin, so the
# next round verifies instead of re-discovering.  The two that need a
# spec-author ruling are STRICT XFAILs: pre-registered, failing for the
# reason recorded, and they will go XPASS -- and so FAIL -- the moment
# the mechanism lands, which is what forces the marker off.
# ══════════════════════════════════════════════════════════════════════

def test_the_partition_holds_under_a_FIXED_PRECISION_pad(law, monkeypatch):
    """PR #220 item 5, the 10-02m (D) STOP, root-caused by basepads4read.

    The pad arrives carrying the arrangement's identity grid as a GEOS
    FIXED-PRECISION MODEL (``shapely.get_precision(pad) == 0.5``), and
    under a precision model every overlay snap-rounds its OWN output
    independently -- so the chain of overlays this partition is made of
    can disagree by up to half a cell.  Measured on the real HECA plan:
    ``building257`` p0 n p3 **2.625 m2**, ``building168`` p0 n p2 0.5 m2,
    ``building308`` p0 n p3 1.0 m2, every one a multiple of the 0.5 m
    cell, and the same calls with the model stripped gave 0.0.

    The bar: a precision-carrying pad mints a partition that is still
    disjoint, and the regions come back WITHOUT a per-geometry precision
    model (the arrangement applies the grid once, globally, in pass B)."""
    import shapely
    pr = _pad("building2", shapely.set_precision(PAD, 0.5))
    assert shapely.get_precision(pr.polygon) == 0.5     # the fixture is the case
    got, counts = _mint(law, _profile(), pads=[pr], monkeypatch=monkeypatch)
    regs = [r for r in got if str(r.ref).startswith("building2")]
    assert len(regs) >= 2, counts
    for i in range(len(regs)):
        for j in range(i + 1, len(regs)):
            ov = regs[i].polygon.intersection(regs[j].polygon).area
            assert ov <= 1e-6, (regs[i].ref, regs[j].ref, ov)
    assert "regions_overlapped_m2" not in counts, counts


def test_an_OVERLAPPING_partition_REFUSES_the_unit_rather_than_emitting_it():
    """The GUARD behind the fix above (10-02m (D) is a STOP, so an
    overlap must be structurally unable to reach the patch however it
    arose).  Driving ``plane_regions`` with two planes whose polygons
    genuinely coincide must mint NOTHING and say so -- never one pad of
    the pair vanishing in the patch while the registry lists it."""
    from auto_patch_v2.geom.base_planes import plane_regions
    same = _sq(10.0, 10.0, 60.0, 40.0)
    counts: dict = {}
    regs, strips = plane_regions(
        [same, same], [0.0, LOT_DY], [(0, 1, LOT_DY)], PAD,
        strip_m=0.0, frontage_m=3.0, min_area_m2=250.0, counts=counts,
        hold_m=0.0)
    assert (regs, strips) == ([], [])
    # it is REPORTED, by whichever gate caught it -- never silent
    assert counts, counts
