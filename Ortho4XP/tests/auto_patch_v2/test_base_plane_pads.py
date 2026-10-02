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
    # the two pads do not touch, and the gap IS the spacing (to the
    # buffer's own flat-cap precision)
    gap = min(a.distance(b) for a in lo for b in hi)
    assert gap == pytest.approx(STRIP_M, abs=0.02), gap
    # nothing claims the strip: its interior is outside every region
    mid = Point(40.0, 15.0)                     # on the shared edge x = 40
    assert not any(p.covers(mid) for p in lo + hi)
    # and the floor really did give up ground (it was 40 x 30 = 1,200)
    assert sum(p.area for p in lo) < 1200.0
    assert sum(p.area for p in lo) > 1200.0 - 0.6 * 30.0


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


def test_the_ORIGIN_plane_is_never_half_minted():
    """§2 (1): ``p0`` carries today's datum law.  A unit whose ``p0`` falls
    under the area floor mints NOTHING — never the upper plane alone,
    which would be a pad with no datum to be pinned to."""
    tiny = _sq(32.0, 0.0, 8.0, 5.0)          # ADJACENT to the lot's west rim
    regs, strips, counts = _regions(planes=(tiny, LOT), ys=(0.0, LOT_DY))
    assert (regs, strips) == ([], [])
    assert counts.get("origin_under_min") == 1


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


def test_the_mint_replaces_the_unit_pad_with_one_pad_per_plane(law, monkeypatch):
    """§2 (1) + C7: the refs are ``<unit>/p<k>``, ``p0`` is the origin
    plane, and ``unit_ref_of`` folds them back to ONE unit so every
    reader keyed on the unit ref — ``pad_cluster_mismatch`` among them,
    C25 — sees one cluster."""
    got, counts = _mint(law, _profile(), monkeypatch=monkeypatch)
    refs = sorted(str(r.ref) for r in got)
    assert refs == [plane_ref("building2", 0), plane_ref("building2", 1),
                    plane_ref("building2", 1)]
    assert "building2" not in refs           # the unit pad itself is gone
    assert {unit_ref_of(r) for r in refs} == {"building2"}
    assert {plane_of(r)[1] for r in refs} == {0, 1}
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
    assert BS.origin_ref_of("building2") == plane_ref("building2", 0)
    assert len(BS.BASE_STEPS) == 1
    st = BS.BASE_STEPS[0]
    assert st.declared_step_m == pytest.approx(LOT_DY)
    assert (st.lower_ref, st.upper_ref) == (plane_ref("building2", 0),
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
    assert plane_of(moved[0].ref) == ("building2", 1)


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
        ref = plane_ref(unit, k)
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
                     {plane_ref("building2", 0): 7, plane_ref("building2", 1): 11})
    assert len(rows) == 1                     # p0 keeps today's datum law
    r = rows[0]
    assert isinstance(r, Diff)
    assert (r.a, r.b) == (11, 7)              # p1 against p0, in that order
    assert r.cap == 0.0 and r.bound_m == 0.0
    assert r.rel == pytest.approx(LOT_DY)
    assert r.soft is None and r.follows is None      # HARD, two-way
    assert r.source.ruling.startswith(CP.PLANE_OFFSET_RULING)
    assert CP.STATS["plane_offset_rows"] == {"pins": 1, "no_datum_column": 0,
                                             "no_origin_pad": 0}


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


def test_a_plane_pad_with_no_datum_column_is_reported_never_pinned_to_nothing(
        law, monkeypatch):
    """A plane that touches no apron has no stage-1 datum column of its
    own (Q3's case); a pin onto a column that is not an unknown is a row
    on a constant.  It is COUNTED, so the unit's fallback is readable."""
    _pads_registered()
    rows = _pin_rows(law, monkeypatch, {plane_ref("building2", 0): 7})
    assert rows == []
    assert CP.STATS["plane_offset_rows"]["no_datum_column"] == 1


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
