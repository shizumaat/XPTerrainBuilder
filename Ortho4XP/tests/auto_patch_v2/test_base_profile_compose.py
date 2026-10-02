"""§1 (3) THE COMPOSED-UNIT ROOF TEST — the twin that holds the §6 STOP
(``docs/specs/building-base-profile-spec.md`` §1 (3), §5 A5, §6; owner
RULINGS 2026-10-01f).

THE MEASURED FACT THESE TWINS DESIGN AGAINST (RULINGS 2026-10-02d, the
session's five-airport control read): HECA ``unit:43`` — the T3 complex —
reads **STEPPED with 113 planes** at the PER-MEMBER UPPER BOUND, because
a member's own base read cannot see the walls and columns that hold its
floor up when those live in a SIBLING member.  §5 A5 pre-registers that
as THE RISK and §6 lists "HECA T3 gaining any plane pad" as a STOP.  §1
(3) is the answer: compose the members of one §16g unit into ONE frame —
each member's base polygons rotated by its own DSF heading and translated
to its own placement origin — and RE-RUN the roof test there, against the
composed unit's lower geometry.

Two levels, both here:

* :func:`test_a_rotated_members_plane_lands_where_the_placement_affine_puts_it`
  and its neighbours — the geometry of the composition itself
  (``obj8_grade.compose_profiles``).
* the T3-SHAPED UNIT — a synthetic ``RebakePlan`` unit of six hall
  members whose per-member planes are all roof-class, composed through
  ``placement_family.cluster_base_profile`` exactly as the planar stage
  composes it.  It must read ROOF/FEET with ZERO plane pads, and the same
  unit with the origins withheld must still read the upper bound — so the
  twin measures that the COMPOSITION is what resolves the STOP, not a
  threshold that happened to fall the right way.

Hermetic: fixtures are written into ``tmp_path`` with an explicit
``encoding=``/``newline=`` (the Windows text-IO law) and read back through
the engine's own ``obj8`` reader.  No network, no corpus, no pack.
"""
from __future__ import annotations

import math

import numpy as np

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_grade as BP
from auto_patch_v2.airport import placement_family as PF
from auto_patch_v2.airport.placement_contact import m_per_deg_exact
from auto_patch_v2.model import rebake as RB

from test_base_profile import LAW, _post, _slab, _write

#: The unit's anchor — a plain mid-latitude point; nothing in the read
#: depends on WHERE, only on the metres between the members.
ANCHOR = (40.0, -75.0)
#: The KASE fire station's own heading (§0 fact 5), used so the twins
#: exercise a rotation that is neither 0 nor a right angle.
HEADING = 69.97

#: §1 (3) the five law numbers the composed read takes, at the values
#: ``tests/auto_patch_v2/test_base_profile.LAW`` pins against the shipped
#: tables (so these twins cannot drift from the law either).
PROFILE_LAW = PF.ProfileLaw(
    pad_terrace_floor_m=LAW["pad_terrace_floor_m"],
    pad_frontage_m=LAW["pad_frontage_m"],
    roof_support_fraction=LAW["roof_support_fraction"],
    contact_band_m=LAW["contact_band_m"],
    min_distinct_spacing_m=LAW["min_distinct_spacing_m"])


def _profile(tmp_path, name, groups, **over):
    g = obj8.parse_obj8(str(_write(tmp_path / name, groups)))
    return BP.base_profile(g, obj8.solid_components(g), **{**LAW, **over})


def _ll(origin_ll, heading_deg: float, x: float, z: float) -> tuple[float, float]:
    """One authored ``(x, z)`` of a member placed at ``origin_ll`` with
    ``heading_deg``, as ``(lat, lon)``.

    THE FIXTURE USES THE ENGINE'S OWN AFFINE (``obj8._to_frame``, the one
    spelling ``placement_affine`` is built from): a second hand-written
    rotation here is the census-wrapper defect in a fixture — it would
    agree with a wrong composition and disagree with a right one.  Only
    the metres-per-degree scaling is applied on top, the same
    ``m_per_deg_exact`` the composition uses.
    """
    ml, mo = m_per_deg_exact(ANCHOR[0])
    dE = (float(origin_ll[1]) - ANCHOR[1]) * mo
    dN = (float(origin_ll[0]) - ANCHOR[0]) * ml
    east, north = obj8._to_frame((dE, dN), heading_deg, x, z)
    return (ANCHOR[0] + north / ml, ANCHOR[1] + east / mo)


def _origin(east_m: float, north_m: float) -> tuple[float, float]:
    """A placement origin ``east_m`` / ``north_m`` from :data:`ANCHOR`."""
    ml, mo = m_per_deg_exact(ANCHOR[0])
    return (ANCHOR[0] + north_m / ml, ANCHOR[1] + east_m / mo)


def _member(mid: str, prof, origin, heading_deg: float, parts=()) -> RB.Member:
    return RB.Member(id=mid, resource=f"objects/{mid}.obj",
                     authored_path=f"/pack/objects/{mid}.obj",
                     live_path=f"/pack/objects/{mid}.obj",
                     heading_deg=heading_deg, parts=tuple(parts),
                     base_profile=BP.profile_to_json(prof), origin=origin)


def _part(pid: int, lat: float, lon: float, base_y: float, feet=()) -> RB.Part:
    return RB.Part(pid=pid, comp=0, lat=lat, lon=lon, base_y=base_y,
                   area_m2=100.0, box=(lat, lon, lat, lon), feet=tuple(feet))


# ── the composition's own geometry ────────────────────────────────────────

def test_a_rotated_members_plane_lands_where_the_placement_affine_puts_it(tmp_path):
    """§1 (2): "orientation is carried by the polygons".  A member's base
    polygon is AUTHORED ``(x, z)``; composed into the unit frame it must
    sit exactly where ``obj8.placement_affine`` would put the same
    vertices — that is what makes a pad's edges follow the base polygon
    and a sibling's feet land under the right plane."""
    prof = _profile(tmp_path, "slab.obj",
                    [_slab(0.0, 0.0, 40.0, 20.0, 0.0, base=-2.0)])
    assert prof.verdict == BP.FLAT and len(prof.planes) == 1
    unit = BP.compose_profiles(
        [(prof, (100.0, 0.0, -50.0), HEADING)],
        pad_terrace_floor_m=LAW["pad_terrace_floor_m"],
        pad_frontage_m=LAW["pad_frontage_m"])
    got = unit.planes[0].polygon
    want = [obj8._to_frame((100.0, -50.0), HEADING, x, z)
            for x, z in ((0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0))]
    for wx, wy in want:
        assert got.exterior.distance(
            __import__("shapely").geometry.Point(wx, wy)) < 1e-6, (wx, wy)
    assert abs(got.area - 800.0) < 1e-6, got.area


def test_no_heading_translates_and_is_not_the_zero_heading_affine(tmp_path):
    """``_part_row``: a 2-tuple row carries NO heading and translates;
    heading 0.0 goes through the affine, whose ``z`` axis runs SOUTH
    (``placement_affine`` = ``[1, 0, 0, −1, …]``).  The two must differ,
    or a 0°-authored member would compose MIRRORED against a 0.001°
    neighbour and the roof test would look under the wrong floor."""
    prof = _profile(tmp_path, "slab.obj",
                    [_slab(0.0, 10.0, 40.0, 20.0, 0.0, base=-2.0)])
    kw = dict(pad_terrace_floor_m=LAW["pad_terrace_floor_m"],
              pad_frontage_m=LAW["pad_frontage_m"])
    dry = BP.compose_profiles([(prof, (0.0, 0.0, 0.0))], **kw)
    placed = BP.compose_profiles([(prof, (0.0, 0.0, 0.0), 0.0)], **kw)
    ymid_dry = dry.planes[0].polygon.centroid.y
    ymid_placed = placed.planes[0].polygon.centroid.y
    assert abs(ymid_dry - 20.0) < 1e-6, ymid_dry
    assert abs(ymid_placed + 20.0) < 1e-6, ymid_placed


def test_a_siblings_feet_under_a_floor_make_it_a_roof_only_once_composed(tmp_path):
    """§1 (3) in miniature: the hall floor is a member of its own and
    reads a BASE PLANE alone (nothing of its own lies a metre below it);
    the columns holding it up are a SIBLING member.  Composed, the floor
    is a ROOF."""
    hall = _profile(tmp_path, "hall.obj",
                    [_slab(0.0, 0.0, 40.0, 30.0, 8.2, base=8.0)])
    assert hall.verdict == BP.FLAT and len(hall.planes) == 1, hall.line()
    kw = dict(pad_terrace_floor_m=LAW["pad_terrace_floor_m"],
              pad_frontage_m=LAW["pad_frontage_m"])
    lower = np.array([(x, 0.0, z) for x in (3.0, 14.0, 26.0, 37.0)
                      for z in (3.0, 15.0, 27.0)], dtype=float)
    alone = BP.compose_profiles([(hall, (0.0, 0.0, 0.0))], **kw)
    assert alone.verdict == BP.FLAT and len(alone.planes) == 1, alone.line()
    composed = BP.compose_profiles(
        [(hall, (0.0, 0.0, 0.0))],
        roof_support_fraction=LAW["roof_support_fraction"], lower_pts=lower,
        contact_band_m=LAW["contact_band_m"],
        min_distinct_spacing_m=LAW["min_distinct_spacing_m"], **kw)
    assert composed.verdict == BP.FEET, composed.line()
    assert not composed.planes, composed.line()
    assert "read as a roof" in composed.why, composed.why


# ── the T3-SHAPED UNIT, off a synthetic plan ──────────────────────────────

def _t3_unit(tmp_path, halls: int = 6, *, placed: bool = True) -> RB.Unit:
    """A unit shaped like HECA's T3 complex (§0 fact 10): ``halls`` hall
    members side by side, each carrying ONE upper-floor plane (1,200 m²
    at +8.2 on a 0.2 m skirt, so per member nothing of its own lies a
    metre below it and the plane reads a BASE), and beside each a COLUMN
    member standing on the ground whose feet are the floor's supports.

    ``placed=False`` withholds every ``Member.origin``, which is a plan
    written before version 12 — the composition must then fall back to
    the vertical-only UPPER BOUND and say so.
    """
    floor = _profile(tmp_path, "hall.obj",
                     [_slab(0.0, 0.0, 40.0, 30.0, 8.2, base=8.0)])
    assert floor.verdict == BP.FLAT and len(floor.planes) == 1, floor.line()
    cols = _profile(tmp_path, "cols.obj",
                    [_post(x, z, 1.0, 8.0)
                     for x in (3.0, 14.0, 26.0, 37.0) for z in (3.0, 15.0, 27.0)])
    assert cols.verdict == BP.FEET and not cols.planes, cols.line()
    members: list[RB.Member] = []
    pid = 0
    for i in range(halls):
        org = _origin(i * 60.0, 0.0)
        members.append(_member(f"hall{i}", floor, org if placed else None,
                               HEADING, parts=[_part(pid, *_ll(org, HEADING, 20.0, 15.0),
                                                     8.0)]))
        pid += 1
        feet = [(*_ll(org, HEADING, x, z), 0.0)
                for x in (3.0, 14.0, 26.0, 37.0) for z in (3.0, 15.0, 27.0)]
        members.append(_member(f"cols{i}", cols, org if placed else None,
                               HEADING,
                               parts=[_part(pid, *_ll(org, HEADING, 20.0, 15.0),
                                            0.0, feet=feet)]))
        pid += 1
    return RB.Unit(id="unit:43", anchor=ANCHOR, agl_m=0.0,
                   members=tuple(members))


def test_the_t3_shaped_unit_reads_roof_and_mints_no_plane_pad(tmp_path):
    """§5 A5 / §6: the pre-registered RISK, held.  Every hall floor of the
    T3-shaped unit is roof-class once its SIBLING columns are composed
    under it, so the composed unit carries ZERO base planes — no plane
    pad is minted and §6's "HECA T3 gaining any plane pad" cannot
    happen.  The composition is read exactly as the planar stage reads
    it (``cluster_base_profile``), through the plan's own origins,
    headings and part feet."""
    unit = _t3_unit(tmp_path)
    rec, how = PF.cluster_base_profile(
        unit, range(len(unit.members)), PROFILE_LAW)
    assert how == "composed", how
    prof = BP.profile_from_json(rec)
    assert prof.verdict == BP.FEET, prof.line()
    assert not prof.planes, prof.line()
    assert "read as a roof" in prof.why, prof.why


def test_the_same_unit_reads_the_upper_bound_per_member(tmp_path):
    """The CONTROL for the twin above: the per-member read of the SAME
    unit is the upper bound §0 fact 10 measured — one base plane per hall
    — so what the composition changed is the composition, not a
    threshold.  (6 halls here; HECA's real T3 read 113.)"""
    unit = _t3_unit(tmp_path)
    planes = sum(len(BP.profile_from_json(m.base_profile).planes)
                 for m in unit.members)
    assert planes == 6, planes


def test_a_plan_without_origins_falls_back_to_the_upper_bound_and_says_so(tmp_path):
    """§1 (3) / version 12: a plan written before ``Member.origin`` cannot
    be composed, and the read must be the labelled UPPER BOUND rather than
    a composed answer from a half-placed set.

    What the bound reads here is the bound's own shape: with no origins
    the six halls translate onto ONE another and weld into a single
    7,200 m² plane at +8.2 — a plane pad WOULD be minted for a floor
    eight metres up.  That is the §6 STOP, and it is what the composed
    read above removes."""
    unit = _t3_unit(tmp_path, placed=False)
    rec, how = PF.cluster_base_profile(
        unit, range(len(unit.members)), PROFILE_LAW)
    assert how == "vertical_only", how
    prof = BP.profile_from_json(rec)
    assert prof.verdict != BP.FEET, prof.line()
    assert prof.planes and abs(prof.planes[0].y - 8.2) < 1e-6, prof.line()


def test_a_unit_with_no_base_plane_publishes_nothing(tmp_path):
    """§1 (3) last sentence, at the plan level: a group whose members
    carry no base plane keeps today's law exactly — nothing is composed
    and nothing is published, which is also the cheap exit the 2,677
    HECA clusters take."""
    cols = _profile(tmp_path, "cols.obj",
                    [_post(x, 1.0, 1.0, 4.0) for x in range(0, 60, 6)])
    unit = RB.Unit(id="unit:9", anchor=ANCHOR, agl_m=0.0, members=(
        _member("a", cols, _origin(0.0, 0.0), HEADING),
        _member("b", cols, _origin(40.0, 0.0), HEADING)))
    rec, how = PF.cluster_base_profile(unit, (0, 1), PROFILE_LAW)
    assert rec == {} and how == "", (rec, how)


def test_the_composition_is_published_on_the_cluster(tmp_path):
    """§1 (4) / C1: ``plan_clusters`` publishes the composed record on
    ``PlanCluster.base_profile`` with its ``composition`` label, and
    publishes NEITHER when no ``ProfileLaw`` is passed — so a reader that
    does not ask pays nothing and sees nothing."""
    unit = _t3_unit(tmp_path, halls=2)
    plan = RB.RebakePlan(icao="TEST", pack_name="p", pack_root="/pack",
                         units=(unit,), skipped=(), counts={})
    bare = PF.plan_clusters(plan, 0.5)
    assert bare and all(c.base_profile == {} and c.composition == ""
                        for c in bare)
    got = PF.plan_clusters(plan, 0.5, profile_law=PROFILE_LAW)
    assert got, "the T3-shaped plan derived no cluster"
    for c in got:
        assert c.composition in ("composed", ""), c.composition
        assert not (c.base_profile.get("planes") or ()), c.base_profile


def test_the_rotation_is_what_puts_the_columns_under_the_floor(tmp_path):
    """The twin that would fail if the composition translated without
    rotating (or rotated the wrong way): the hall is authored 40 × 30 and
    the columns sit inside it, so at the RIGHT heading the support hull
    covers the floor and the plane is a roof — and at a heading 90° out
    of step it does not, and the plane survives.  The rotation is load-
    bearing law, not decoration."""
    unit = _t3_unit(tmp_path, halls=1)
    wrong = RB.Unit(id=unit.id, anchor=unit.anchor, agl_m=unit.agl_m,
                    members=tuple(m if m.id.startswith("cols")
                                  else __import__("dataclasses").replace(
                                      m, heading_deg=HEADING + 90.0)
                                  for m in unit.members))
    right, _ = PF.cluster_base_profile(unit, (0, 1), PROFILE_LAW)
    off, _ = PF.cluster_base_profile(wrong, (0, 1), PROFILE_LAW)
    assert not (BP.profile_from_json(right).planes), right
    assert BP.profile_from_json(off).planes, off


def test_the_affine_matches_the_engines_own_spelling():
    """``obj8_grade._place_matrix`` must BE ``obj8.placement_affine`` — one
    spelling of the authored -> frame affine.  Measured directly rather
    than by inspection: two readings of one law drifting apart is the
    defect class §6 names."""
    from shapely.geometry import Polygon
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)]
    assert list(BP._place_matrix(7.0, -3.0, HEADING)) == \
        obj8.placement_affine((7.0, -3.0), HEADING)
    got = BP._place_all([Polygon(ring)], 7.0, -3.0, HEADING, 0.0)[0]
    want = Polygon([obj8._to_frame((7.0, -3.0), HEADING, x, z) for x, z in ring])
    assert got.equals_exact(want, 1e-9), (list(got.exterior.coords),
                                          list(want.exterior.coords))
    assert abs(math.hypot(*(np.array(got.centroid.coords[0])
                            - np.array(want.centroid.coords[0])))) < 1e-9


def test_the_placement_goes_through_frame_entry():
    """§51 (2) (``tests/auto_patch_v2/test_v2witnessvalid.py`` G1): the
    composition's affine is applied by ``frame_entry.enter`` and nowhere
    else — rotating a face-union polygon rounds micron slivers into
    self-touching rings, and the first union that reads one (the riser
    WELD, one step later) refuses it.  So ``enter`` must REPAIR here, not
    merely transform."""
    import inspect

    from shapely.geometry import Polygon
    assert "frame_entry" in inspect.getsource(BP._place_all)
    # a bow-tie enters as a VALID polygonal geometry, never as itself
    bow = Polygon([(0.0, 0.0), (4.0, 4.0), (4.0, 0.0), (0.0, 4.0)])
    assert not bow.is_valid
    got = BP._place_all([bow], 0.0, 0.0, HEADING, 0.0)[0]
    assert got is not None and got.is_valid, got
    # ... and a polygon that repairs to nothing comes back None
    sliver = Polygon([(0.0, 0.0), (1e-9, 0.0), (1e-9, 1e-9)])
    assert BP._place_all([sliver], 0.0, 0.0, HEADING, 0.0)[0] is None
