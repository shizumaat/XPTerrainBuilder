"""§16g (10) (12) — v1's TWO PAD-ADMISSION GATES, PORTED TO v2
(issue #101, lane ``padgates101``; owner RULINGS 2026-10-02v (3), verbatim:
*"We definitely don't want a flat pad under the whole train at HECA"*).

v1 refused HECA's 31,220 m2 elevated-train footprint as "a slab/mast weld,
not a building" (``src/auto_patch/object_footprints.py::structure_ring``,
``DSF_OBJECT_MIN_TALL_BASE_FILL`` ``src/auto_patch/config.py`` :3755) and
refused 446 structure rings for want of BUILDING EVIDENCE (R18-2, owner
ruling 2026-08-11b); v2 admitted both as pads.  Both gates now live at v2's
ONE pad admission site, ``geom.cluster_outlines`` rules 9 and 10, measured
once at ``placement_family.plan_clusters`` (``geom.pad_evidence``).

THE FLOOR IS DELIBERATELY LOW (v1's calibration, measured HECA 2026-07-27):
the weld class reads < 0.002 and THIN-WALL terminal shells ~0.002-0.01, so
0.002 sits between two real populations and raising it toward 0.05 culled
~140 real shells.  Twins 1 and 2 are one on each side of it.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import box

from auto_patch_v2.airport.placement_contact import m_per_deg_exact
from auto_patch_v2.airport.placement_family import plan_clusters
from auto_patch_v2.geom import cluster_outlines, osm_building_evidence
from auto_patch_v2.geom.pad_evidence import (PadEvidence,
                                             has_vertical_structure_evidence,
                                             member_row, tall_base_fill)
from auto_patch_v2.law.tables import PadAdmission, load_default, pad_admission

LAT0, LON0 = 41.0, -3.0
ML, MO = m_per_deg_exact(LAT0)

#: the shipped law, so the twins are judged at the values that ship
LAW = load_default()
ADMISSION = pad_admission(LAW)
#: ``(tall_member_min_extent_m, evidence_min_height_m, evidence_min_coverage)``
EVIDENCE_LAW = (
    float(LAW.tables.structures.placement.tall_member_min_extent_m),
    float(LAW.tables.structures.placement.evidence_min_height_m),
    float(LAW.tables.structures.placement.evidence_min_coverage))


def test_the_ported_values_are_v1s():
    """The law table carries v1's numbers, value for value — the floor is
    LOW on purpose and this twin is what fails if someone raises it."""
    pl = LAW.tables.structures.placement
    assert pl.min_tall_base_fill == 0.002          # DSF_OBJECT_MIN_TALL_BASE_FILL
    assert pl.tall_member_min_extent_m == 2.5      # ..TALL_MEMBER_MIN_EXTENT_M
    assert pl.building_evidence is True            # ..BUILDING_EVIDENCE
    assert pl.evidence_min_height_m == 6.0         # ..EVIDENCE_MIN_HEIGHT_M
    assert pl.evidence_min_coverage == 0.0         # ..EVIDENCE_MIN_COVERAGE
    # ...and the tall floor is its OWN key, as in v1 — never an alias of
    # ``chain_min_height_m``, which tests and users legitimately zero
    names = {f.name for f in _dc.fields(type(pl))}
    assert {"tall_member_min_extent_m", "chain_min_height_m"} <= names


# ── the plan shims (the ``test_unitplatform_connector`` idiom, with the
#    footprint RINGS and the per-component heights this law reads) ──────

def _lat(north_m: float) -> float:
    return LAT0 + north_m / ML


def _lon(east_m: float) -> float:
    return LON0 + east_m / MO


class _Part:
    """One welded component: a plan rectangle in metres, its own SOLID
    height (``Part.height_m`` — what the tall-base accumulator reads) and
    its own authored base (``base_y`` — what the above-grade clamp reads)."""

    def __init__(self, pid, x0, y0, x1, y1, height, base_y=0.0):
        self.pid = pid
        self.comp = 0
        self.box = (_lat(y0), _lon(x0), _lat(y1), _lon(x1))
        self.rings = (((_lat(y0), _lon(x0)), (_lat(y0), _lon(x1)),
                       (_lat(y1), _lon(x1)), (_lat(y1), _lon(x0))),)
        self.lat = 0.5 * (self.box[0] + self.box[2])
        self.lon = 0.5 * (self.box[1] + self.box[3])
        self.base_y = float(base_y)
        self.height_m = float(height)
        self.feet = ((self.lat, self.lon, self.base_y),)
        self.area_m2 = 1.0            # 3-D surface area; NOT a plan area
        self.line = False
        self.scatter = False


class _Member:
    def __init__(self, resource, parts):
        self.id = resource
        self.resource = resource
        self.parts = tuple(parts)
        self.heading_deg = 0.0
        self.deck_kind = ""
        self.deck_ring = None
        self.deck_shade_ring = None
        self.deck_datum_z = None
        self.elevated_deck = False


class _Unit:
    def __init__(self, members, uid="unit:0"):
        self.id = uid
        self.anchor = (LAT0, LON0)
        self.members = tuple(members)


@_dc.dataclass
class _Plan:
    units: tuple
    contacts: tuple = ()
    connectors: "tuple | None" = None


def _to_xy(lon: float, lat: float) -> tuple[float, float]:
    """``cluster_outlines`` calls the frame as ``to_xy(lon, lat)``; metres
    east / north of the twin's origin."""
    return ((lon - LON0) * MO, (lat - LAT0) * ML)


def _clusters(plan, **kw):
    return plan_clusters(plan, 0.5, chain_min_height_m=2.5,
                         evidence_law=EVIDENCE_LAW, **kw)


def _outlines(cl, admission=ADMISSION, osm=None, refused=None, **kw):
    """The pad mint's own call, with rules 6 (thin pieces) and 4 (the
    airside clip) left disarmed so a twin measures the gate under test and
    nothing else — a thin-wall shell's outline IS thin by rule 6."""
    kw.setdefault("thin_m", 0.0)
    return cluster_outlines(cl, _to_xy, 0.5, admission=admission,
                            osm_evidence=osm, refused=refused, **kw)


# ── TWIN 1: the SLAB + MAST WELD is refused (v1's own class) ───────────

def _weld_plan():
    """v1's plate+mast weld: a solid 100 x 100 m ground plate 0.3 m tall
    welded to a 4 x 4 m mast 28 m tall.  The mast makes the body WALLED
    (so rule 5/7 does not take it first) and supplies the vertical extent,
    the plate supplies the dense base — and NO tall member covers the
    footprint: 16 / 10,000 = 0.0016, under v1's 0.002 floor."""
    plate = _Part(1, 0, 0, 100, 100, 0.3)
    mast = _Part(2, 48, 48, 52, 52, 28.0)
    return _Plan((_Unit([_Member("objects/light_mast.obj", [plate, mast])]),),
                 ((1, 2),))


def test_twin1_slab_and_mast_weld_mints_no_pad():
    cl = _clusters(_weld_plan())
    assert len(cl) == 1 and cl[0].walled
    ev = cl[0].evidence
    assert ev is not None
    assert ev.hull_area_m2 == pytest.approx(10_000.0, rel=2e-3)
    assert ev.tall_base_fill == pytest.approx(0.0016, rel=5e-2)
    assert ev.tall_base_fill < ADMISSION.min_tall_base_fill
    refused: list[dict] = []
    pads, counts = _outlines(cl, refused=refused)
    assert pads == []
    assert counts["no_tall_base"] == 1
    assert counts["no_building_evidence"] == 0      # rule 9 closed first
    # the refusal is RECORDED with its ref, its gate and its measured value
    assert len(refused) == 1
    row = refused[0]
    assert row["id"] == cl[0].id
    assert row["gate"] == "min_tall_base_fill"
    assert row["value"] == pytest.approx(0.0016, rel=5e-2)
    # ...and the footprint's length / width, which issue #229 reads
    assert row["length_m"] == pytest.approx(100.0, rel=2e-3)
    assert row["width_m"] == pytest.approx(100.0, rel=2e-3)


def test_twin1_control_the_gate_disarmed_mints_the_pad():
    """``min_tall_base_fill = 0`` is the matched base arm: the same weld
    takes a pad, which is what v2 did before #101."""
    cl = _clusters(_weld_plan())
    pads, counts = _outlines(cl, admission=_dc.replace(
        ADMISSION, min_tall_base_fill=0.0, building_evidence=False))
    assert len(pads) == 1 and counts["no_tall_base"] == 0


# ── TWIN 2: the THIN-WALL TERMINAL SHELL is ADMITTED ──────────────────

def _shell_plan(wall_m: float = 0.125, height: float = 10.0):
    """A material-split terminal shell: four 100 m wall strips around a
    100 x 100 m footprint, each 0.125 m thick.  Tall base = 4 x 12.5 =
    50 m2 over a 10,000 m2 hull = 0.005 — ABOVE v1's 0.002 floor and
    exactly the population v1 refused to raise the floor past."""
    w = wall_m
    parts = [_Part(1, 0, 0, 100, w, height),
             _Part(2, 0, 100 - w, 100, 100, height),
             _Part(3, 0, 0, w, 100, height),
             _Part(4, 100 - w, 0, 100, 100, height)]
    return _Plan((_Unit([_Member("objects/T3_shell.obj", parts)]),),
                 ((1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)))


def test_twin2_thin_wall_terminal_shell_keeps_its_pad():
    cl = _clusters(_shell_plan())
    assert len(cl) == 1
    ev = cl[0].evidence
    assert ev.tall_base_fill == pytest.approx(0.005, rel=5e-2)
    assert ev.tall_base_fill > ADMISSION.min_tall_base_fill
    refused: list[dict] = []
    pads, counts = _outlines(cl, refused=refused)
    assert counts["no_tall_base"] == 0
    assert counts["no_building_evidence"] == 0      # 10 m of wall is evidence
    assert refused == []
    assert pads, "a thin-wall shell is a REAL building and needs its pad"


def test_twin2_the_floor_sits_between_the_two_populations():
    """The one assertion the floor exists for: the weld is below it and the
    shell above it, so no single raise can refuse one without the other."""
    weld = _clusters(_weld_plan())[0].evidence.tall_base_fill
    shell = _clusters(_shell_plan())[0].evidence.tall_base_fill
    assert weld < ADMISSION.min_tall_base_fill < shell


# ── TWINS 3 / 4: BUILDING EVIDENCE (R18-2), both halves ───────────────

def _slab_plan():
    """An apron slab: ONE 60 x 40 m component 3.0 m tall.  It is WALLED
    (3.0 >= chain_min_height_m) and its tall base covers its own footprint
    (fill 1.0), so rule 9 passes it — but 3.0 m is under v1's 6.0 m
    vertical-evidence height, which is v1's phantom class exactly (the
    four HECA rings top out at 2.85-5.36 m)."""
    return _Plan((_Unit([_Member("objects/concrete_3.obj",
                                 [_Part(1, 0, 0, 60, 40, 3.0)])]),))


def test_twin3_no_osm_building_and_no_vertical_structure_mints_no_pad():
    cl = _clusters(_slab_plan())
    ev = cl[0].evidence
    assert ev.tall_base_fill == pytest.approx(1.0, rel=1e-3)   # rule 9 passes
    assert ev.tallest_extent_m == pytest.approx(3.0)
    assert not has_vertical_structure_evidence(
        ev.rows, ev.hull_area_m2, *EVIDENCE_LAW[1:])[0]
    refused: list[dict] = []
    pads, counts = _outlines(cl, osm=None, refused=refused)
    assert pads == []
    assert counts["no_building_evidence"] == 1 and counts["no_tall_base"] == 0
    assert refused[0]["gate"] == "building_evidence"
    assert refused[0]["value"] == pytest.approx(3.0)
    # the refused OUTLINE's own length / width (issue #229)
    assert refused[0]["length_m"] == pytest.approx(60.0, rel=2e-3)
    assert refused[0]["width_m"] == pytest.approx(40.0, rel=2e-3)


class _B:
    """A ``model.airport.Building`` as ``geom.osm_building_evidence`` reads
    it — rings ALREADY in the planar frame (``airport/load.py`` projects
    them at load)."""

    def __init__(self, source, poly):
        self.source = source
        self.outer = tuple(poly.exterior.coords)[:-1]
        self.holes = ()


def test_twin4_the_same_ring_with_an_osm_building_under_it_is_admitted():
    """v1's EVIDENCE SOURCE (a): an intersecting OSM building footprint is
    evidence on its own, whatever the object's own geometry says."""
    cl = _clusters(_slab_plan())
    osm = osm_building_evidence([_B("osm", box(10, 10, 50, 30))])
    refused: list[dict] = []
    pads, counts = _outlines(cl, osm=osm, refused=refused)
    assert len(pads) == 1 and refused == []
    assert counts["no_building_evidence"] == 0
    assert counts["osm_vouched"] == 1, "the OSM half is what carried it"


def test_twin4_only_an_osm_source_is_evidence():
    """A ``dsf:*`` footprint is the PACK's own geometry, so it is not
    independent evidence of a building — the predicate ignores it, and a
    pack-only airport gets ``None`` (v1: no OSM in hand is NOT evidence of
    absence, and the gate rests on the vertical test alone)."""
    assert osm_building_evidence(
        [_B("dsf:fac:building", box(0, 0, 60, 40)),
         _B("dsf:object:object", box(0, 0, 60, 40))]) is None
    cl = _clusters(_slab_plan())
    pads, counts = _outlines(cl, osm=osm_building_evidence(
        [_B("dsf:object:object", box(0, 0, 60, 40))]))
    assert pads == [] and counts["no_building_evidence"] == 1


def test_a_building_tall_structure_needs_no_osm_at_all():
    """The vertical half on its own: the same slab at 6.1 m — every real
    terminal shell reaches 6.1 m or more (v1's calibration)."""
    plan = _Plan((_Unit([_Member("objects/concrete_3.obj",
                                 [_Part(1, 0, 0, 60, 40, 6.1)])]),))
    pads, counts = _outlines(_clusters(plan), osm=None)
    assert len(pads) == 1 and counts["no_building_evidence"] == 0
    assert counts["osm_vouched"] == 0


# ── TWIN 5: a refused footprint leaves the rest of the map UNTOUCHED ──

def _neighbour_plan(with_weld: bool):
    """A real 120 x 80 m building 12 m tall, 100 m away from the weld of
    twin 1 — with the weld in the pack and without it."""
    good = _Member("objects/office_a.obj",
                   [_Part(9, 200, 0, 320, 80, 12.0)])
    members = [good]
    if with_weld:
        members.append(_Member(
            "objects/light_mast.obj",
            [_Part(1, 0, 0, 100, 100, 0.3), _Part(2, 48, 48, 52, 52, 28.0)]))
    return _Plan((_Unit(members),), ((1, 2),) if with_weld else ())


def test_twin5_a_refused_footprint_leaves_the_pad_set_identical():
    """The refused footprint mints NO pad, NO plateau, NO collar and NO
    frontage hold, and its ground is ordinary terrain: every one of those
    is derived from a pad REF (the 30l consumer census), so the proof is
    that the surviving pad set is IDENTICAL to the arm with no object
    there at all — same ids, same rings, to the millimetre."""
    on, c_on = _outlines(_clusters(_neighbour_plan(True)), refused=[])
    off, c_off = _outlines(_clusters(_neighbour_plan(False)))
    assert c_on["no_tall_base"] == 1 and c_off["no_tall_base"] == 0
    assert [i for i, _c, _g in on] == [i for i, _c, _g in off]
    assert len(on) == 1
    for (_i, _c, a), (_j, _d, b) in zip(on, off):
        assert a.equals(b)
        assert a.area == pytest.approx(b.area, abs=1e-9)
    # ...and the weld's own ground is in NEITHER pad set
    weld = box(0, 0, 100, 100).centroid
    assert not any(g.contains(weld) for _i, _c, g in on)


# ── the discipline rails ──────────────────────────────────────────────

def test_an_unmeasured_cluster_is_refused_by_neither_rule():
    """NOT MEASURED is not REFUSED (the ``cluster_no_height`` discipline):
    a cluster from a plan read before the field — or a twin that does not
    ask — keeps the pre-#101 reading and the population SAYS SO."""
    cl = plan_clusters(_weld_plan(), 0.5, chain_min_height_m=2.5)
    assert cl[0].evidence is None
    pads, counts = _outlines(cl)
    assert len(pads) == 1
    assert counts["unmeasured"] == 1
    assert counts["no_tall_base"] == 0 and counts["no_building_evidence"] == 0


def test_a_name_vouched_weld_is_exempt_as_in_v1():
    """v1's shipped WIDE path vouch (owner CYXY 2026-07-28): an arched-shell
    hangar's footings project ~0.001 of its hull, below the 0.002 floor, so
    a resource whose path NAMES it a building yields the tall-base gate."""
    plan = _Plan((_Unit([_Member(
        "Airport/Hangar_Tower/hangar_7.obj",
        [_Part(1, 0, 0, 100, 100, 0.3), _Part(2, 48, 48, 52, 52, 28.0)])]),),
        ((1, 2),))
    cl = _clusters(plan)
    assert cl[0].evidence.name_vouched
    pads, counts = _outlines(cl)
    assert len(pads) == 1 and counts["no_tall_base"] == 0


def test_the_mint_and_the_census_read_one_admission():
    """§16g (10) (12): the MINT and the CENSUS must be judging a cluster at
    the SAME thresholds, or ``pad_cluster_mismatch`` ends up measuring the
    drift.  Both call ``law.tables.pad_admission`` and
    ``geom.osm_building_evidence`` — asserted structurally, because a
    second reading is exactly what no number can catch."""
    import inspect

    from auto_patch_v2.classify import evidence as mint
    from auto_patch_v2.constraints import cluster_pad as census
    for src in (inspect.getsource(mint._cluster_pads),
                inspect.getsource(census.cluster_polys)):
        assert "osm_evidence=osm_building_evidence(" in src
    assert "pad_admission(law)" in inspect.getsource(mint._cluster_pads)
    assert "pad_admission(law)" in inspect.getsource(census._face_map)


def test_the_measurement_has_one_implementation():
    """``geom.pad_evidence`` is THE definition of "is this a building" —
    a second spelling is the census-wrapper defect in geometry (RULINGS
    2026-08-30l).  The gate re-runs that function; it does not re-derive
    the comparison."""
    import inspect

    from auto_patch_v2.geom import cluster_outline as co
    assert "has_vertical_structure_evidence(" in inspect.getsource(
        co._vertical_evidence)


def test_the_fill_is_frame_free():
    """v1's claim: both areas are read in ONE frame, so the ratio is the
    same number whatever the projection — the lat/lon anisotropy cancels."""
    rows = (("a", 0.3, 0.3, 10_000.0), ("b", 28.0, 28.0, 16.0))
    assert tall_base_fill(rows, 10_000.0, 2.5) == pytest.approx(0.0016)
    scaled = tuple((r[0], r[1], r[2], r[3] * 4.0) for r in rows)
    assert tall_base_fill(scaled, 40_000.0, 2.5) == pytest.approx(0.0016)


def test_the_above_grade_clamp_is_v1s():
    """v1's A11 amendment (owner defect 2026-07-30, OTHH drainage basins):
    a pit authored -3.82 .. +0.06 is a 3.87 m HOLE, not a 3.87 m building,
    so BOTH ends are clamped at grade before the evidence test."""
    pit = _Part(1, 0, 0, 50, 50, 3.88, base_y=-3.82)
    _res, extent, above, _area = member_row(pit, "objects/drainage_04.obj",
                                            ML, MO)
    assert extent == pytest.approx(3.88)
    assert above == pytest.approx(0.06, abs=1e-9)
    wall = _Part(2, 0, 0, 50, 50, 13.5, base_y=6.5)
    assert member_row(wall, "w", ML, MO)[2] == pytest.approx(13.5)


def test_a_degenerate_footprint_is_unmeasured_not_refused():
    """A hull of zero area cannot be divided, so rule 9 refuses nothing —
    v1's ``hull_area > 0.0`` guard, ported."""
    ev = PadEvidence(0.0, 0.0, 0.0, 0.0, False, False, 0.0, 0.0, 0, ())
    pads, counts = _outlines(
        [_dc.replace(_clusters(_slab_plan())[0], evidence=ev)],
        admission=PadAdmission(0.002, False, 6.0, 0.0))
    assert len(pads) == 1 and counts["no_tall_base"] == 0
