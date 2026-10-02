"""THE BUILDING BASE PROFILE — §1's READ, on synthetic OBJ8 twins
(``docs/specs/building-base-profile-spec.md`` §5 A1; owner RULINGS
2026-10-01f, answers 10-01k).

A1's fixture set, verbatim: a STEPPED fixture (two slabs 0 / +3.0 with a
riser face) -> 2 base planes and one riser declared 3.0; a SLOPED fixture
(one slab at 2 %) -> the SLOPED verdict carrying 2.0 %; a FLAT fixture ->
one plane, unchanged; a ROOF fixture (a slab at +4 over column feet at 0)
-> 0 upper planes; a sub-floor riser (0.8 m) -> welded to ONE plane; and
the #162 FEET case (posts, no floor) -> no plane at all, whose seating is
the object stage's TILT (``test_placement_tilt.py``).

Hermetic and synthetic: every fixture is written into ``tmp_path`` with an
explicit ``encoding=``/``newline=`` (the Windows text-IO law) and read
back through the engine's OWN reader (``airport/obj8.parse_obj8``),
because "the read is right" means the readers downstream accept it.  No
network, no data corpus, no pack.
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_grade as BP


# ── the fixtures ─────────────────────────────────────────────────────────

def _slab(x0, z0, w, d, y, *, base=0.0):
    """A SLAB as a pack really authors a floor plate or a terrace lot: an
    OPEN SHELL — the horizontal top face at ``y`` and the vertical skirt
    walls down to ``base``, with NO underside.  KASE's own terrain sheet
    is this shape (``FireStation_7.obj``: 239 vertices, 354 tris, 11,820
    of 12,335 m² horizontal — §0 fact 5).

    The bottom ring vertices are the FEET.  Returns ``(vertices,
    triangles)``, the top face FIRST so a reader can name it.

    WHY NO UNDERSIDE, AND WHY THAT IS A FIXTURE CHOICE AND NOT A
    CONVENIENCE: §1 (1) defines a horizontal face by ``|n_y|``, which
    admits a DOWN-facing one, so a CLOSED box's flat underside reads as a
    base plane of its own.  That is an open question for the spec author,
    recorded as its own twin
    (:func:`test_a_flat_underside_also_reads_as_a_base_plane`); an open
    shell keeps every other twin measuring the base its fixture states."""
    v = [(x0, y, z0), (x0 + w, y, z0), (x0 + w, y, z0 + d), (x0, y, z0 + d),
         (x0, base, z0), (x0 + w, base, z0), (x0 + w, base, z0 + d),
         (x0, base, z0 + d)]
    t = [(0, 1, 2), (0, 2, 3),                        # the top (horizontal)
         (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),  # the skirt (vertical)
         (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _closed_slab(x0, z0, w, d, y, *, base=0.0):
    """:func:`_slab` CLOSED with a flat underside.  Only the underside
    twin uses it."""
    v, t = _slab(x0, z0, w, d, y, base=base)
    return v, t + [(4, 6, 5), (4, 7, 6)]


def _tilted_slab(x0, z0, w, d, y0, grade, *, skirt=3.0):
    """An open-shell slab whose top face RISES at ``grade`` (m/m) along
    +x — the SLOPED base of §1 (2).  Its four BOTTOM-ring vertices carry
    the same gradient, which is what the contact-set fit reads.

    ``skirt`` is deliberately deeper than ``contact_band_m``: §17 (B)
    defines the feet as the vertices within the band of the member's
    LOWEST, so a shallow skirt would pull the top face's low corner into
    the foot set and the fit would not be a plane at all."""
    y1 = y0 + grade * w
    v = [(x0, y0, z0), (x0 + w, y1, z0), (x0 + w, y1, z0 + d), (x0, y0, z0 + d),
         (x0, y0 - skirt, z0), (x0 + w, y1 - skirt, z0),
         (x0 + w, y1 - skirt, z0 + d), (x0, y0 - skirt, z0 + d)]
    t = [(0, 1, 2), (0, 2, 3),
         (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
         (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _post(x0, z0, side, h):
    """A COLUMN: a thin CLOSED box.  Its top and bottom faces are
    horizontal but ~1 m² each — far under the 250 m² area floor, so they
    are FURNITURE; its bottom four vertices are FEET."""
    return _closed_slab(x0, z0, side, side, h, base=0.0)


def _write(path, groups):
    """Write one OBJ8 from ``[(vertices, triangles)]``, offsetting each
    group's indices.  The Windows text-IO law: an explicit ``encoding``
    and ``newline`` on every write (``tests/test_windows_text_io.py``)."""
    verts: list = []
    idx: list[int] = []
    for v, t in groups:
        off = len(verts)
        verts.extend(v)
        for a, b, c in t:
            idx.extend((a + off, b + off, c + off))
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    for x, y, z in verts:
        out.append(f"VT\t{x:.4f} {y:.4f} {z:.4f}\t0.0 1.0 0.0\t0.0 0.0")
    out.append("")
    for i in range(0, len(idx) - len(idx) % 10, 10):
        out.append("IDX10\t" + " ".join(str(x) for x in idx[i:i + 10]))
    for x in idx[len(idx) - len(idx) % 10:]:
        out.append(f"IDX\t{x}")
    out += ["", "ATTR_hard", f"TRIS\t0 {len(idx)}"]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    return path


#: THE LAW THE TWINS READ, each key at the value the shipped law carries
#: (asserted against the real tables by :func:`test_law_is_the_shipped_law`,
#: so a law change cannot leave these twins measuring a fiction).
LAW = dict(horizontal_ny=0.95, roof_support_fraction=0.25,
           sloped_min_extent_m=20.0, sloped_max=0.08,
           min_area_m2=250.0, split_tol_m=0.3, contact_band_m=1.0,
           pad_terrace_floor_m=1.0, pad_frontage_m=3.0,
           min_distinct_spacing_m=0.5, pad_slope_max=0.01)


def _profile(tmp_path, name, groups, **over):
    g = obj8.parse_obj8(str(_write(tmp_path / name, groups)))
    comps = obj8.solid_components(g)
    return BP.base_profile(g, comps, **{**LAW, **over})


def test_law_is_the_shipped_law():
    """THE TWINS MEASURE THE SHIPPED LAW, not a copy of it (the
    census-wrapper defect class, RULINGS 2026-08-30l): every number in
    :data:`LAW` is the value the law tables actually carry, read at the
    SAME key ``ResourceCache.base_profile`` reads it at."""
    import os

    import auto_patch_v2.law as _law
    from auto_patch_v2.law.model import load_tables
    t = load_tables(os.path.dirname(_law.__file__))
    bp, st, em = t.structures.base_profile, t.structures, t.emit
    assert LAW["horizontal_ny"] == bp.horizontal_ny
    assert LAW["roof_support_fraction"] == bp.roof_support_fraction
    assert LAW["sloped_min_extent_m"] == bp.sloped_min_extent_m
    assert LAW["sloped_max"] == bp.sloped_max
    assert LAW["min_area_m2"] == st.building_pad.min_area_m2
    assert LAW["split_tol_m"] == st.placement.split_tol_m
    assert LAW["contact_band_m"] == st.basin.contact_band_m
    assert LAW["pad_terrace_floor_m"] == em.terrace.pad_terrace_floor_m
    assert LAW["pad_frontage_m"] == em.design.pad_frontage_m
    assert LAW["min_distinct_spacing_m"] == em.identity.min_distinct_spacing_m
    assert LAW["pad_slope_max"] == em.within_shape.pad_slope_max


# ── A1: the STEPPED fixture ──────────────────────────────────────────────

def test_stepped_reads_two_planes_and_one_riser(tmp_path):
    """§5 A1 row 1: two 400 m² slabs at 0 and +3.0, adjacent -> TWO base
    planes and ONE riser declared 3.0.  This is the owner's own sentence
    (10-01f): "part of it is at one level and another part is at a higher
    level ... create two pads with a cliff to match them"."""
    lower = _slab(0.0, 0.0, 20.0, 20.0, 0.0, base=-1.0)
    upper = _slab(21.0, 0.0, 20.0, 20.0, 3.0, base=-1.0)   # 1 m gap < pad_frontage_m
    prof = _profile(tmp_path, "stepped.obj", [lower, upper])
    assert prof.verdict == BP.STEPPED, prof.line()
    assert len(prof.planes) == 2, prof.line()
    assert sorted(round(p.y, 3) for p in prof.planes) == [0.0, 3.0], prof.line()
    assert len(prof.risers) == 1, prof.line()
    assert abs(abs(prof.risers[0].dy) - 3.0) < 1e-6
    # the polygons are the FACE UNION, never a bbox or a hull: each slab
    # is 400 m² and the two together never claim the 20 m² gap
    assert all(abs(p.area_m2 - 400.0) < 1.0 for p in prof.planes), \
        [p.area_m2 for p in prof.planes]
    assert all(abs(p.polygon.area - 400.0) < 1.0 for p in prof.planes)
    # §1 (3): the offsets are read against p0
    assert sorted(round(d, 3) for d in prof.offsets) in ([-3.0, 0.0], [0.0, 3.0])


def test_sub_floor_riser_welds_to_one_plane(tmp_path):
    """§5 A1 last row / §1 (1): a riser UNDER ``pad_terrace_floor_m``
    (0.8 m < 1.0) WELDS — a kerb is not a terrace.  The two slabs become
    ONE plane at the AREA-WEIGHTED height, and the verdict is FLAT."""
    lower = _slab(0.0, 0.0, 20.0, 20.0, 0.0, base=-1.0)
    upper = _slab(21.0, 0.0, 20.0, 20.0, 0.8, base=-1.0)
    prof = _profile(tmp_path, "kerb.obj", [lower, upper])
    assert prof.verdict == BP.FLAT, prof.line()
    assert len(prof.planes) == 1, prof.line()
    assert not prof.risers
    assert abs(prof.planes[0].y - 0.4) < 0.02, prof.line()   # equal areas
    assert abs(prof.planes[0].area_m2 - 800.0) < 2.0


def test_riser_at_the_floor_does_not_weld(tmp_path):
    """The weld floor is a FLOOR, not a rounding: a 1.0 m riser is a
    terrace and stays two planes (``pad_terrace_floor_m`` is 1.0 and the
    comparison is ``>=``, owner RULINGS 2026-09-30i)."""
    prof = _profile(tmp_path, "floor.obj",
                    [_slab(0.0, 0.0, 20.0, 20.0, 0.0, base=-2.0),
                     _slab(21.0, 0.0, 20.0, 20.0, 1.0, base=-2.0)])
    assert prof.verdict == BP.STEPPED, prof.line()
    assert len(prof.planes) == 2


# ── A1: the SLOPED fixture ───────────────────────────────────────────────

def test_sloped_carries_the_base_gradient(tmp_path):
    """§5 A1 row 2 + 10-01k Q5: one 40 × 20 m slab at 2 % -> the SLOPED
    verdict carrying 2.0 % ± 0.05, with NO 1.5 % clamp (the owner: "the
    object was built for it").  There is no horizontal face over the area
    floor, so no plane is minted — the contact set is the base."""
    prof = _profile(tmp_path, "sloped.obj",
                    [_tilted_slab(0.0, 0.0, 40.0, 20.0, 0.0, 0.02)])
    assert prof.verdict == BP.SLOPED, prof.line()
    assert not prof.planes, prof.line()
    grade = math.hypot(*prof.slope)
    assert abs(grade - 0.02) < 0.0005, f"{grade!r} {prof.line()}"
    assert prof.residual_rms_m < 1e-6, prof.line()


def test_sloped_past_the_hard_ceiling_is_not_a_base(tmp_path):
    """§1 (2): geometry steeper than ``sloped_max`` (8 %) is RISER
    geometry, not a plane — KASE's 17 % cut-slope staircase.  The verdict
    falls back to FEET and the lane never mints a 17 % pad."""
    prof = _profile(tmp_path, "cliffy.obj",
                    [_tilted_slab(0.0, 0.0, 40.0, 20.0, 0.0, 0.17)])
    assert prof.verdict == BP.FEET, prof.line()
    assert not prof.planes, prof.line()
    # ... and the 17 % faces never became a plane: a face cluster whose
    # own vertices span more than ``split_tol_m`` is not LEVEL
    assert not prof.risers, prof.line()


def test_short_slope_is_feet_not_sloped(tmp_path):
    """§1 (2): a contact set shorter than ``sloped_min_extent_m`` (20 m)
    is FEET — a column-only shelter is not a ramp."""
    prof = _profile(tmp_path, "short.obj",
                    [_tilted_slab(0.0, 0.0, 10.0, 6.0, 0.0, 0.04)])
    assert prof.verdict == BP.FEET, prof.line()


# ── A1: the FLAT fixture ─────────────────────────────────────────────────

def test_flat_reads_one_plane_and_no_riser(tmp_path):
    """§5 A1 row 3: a FLAT base reads ONE plane and no riser — the pad
    count and the rows are what they are today, which is what "a FLAT
    fixture -> byte-identical patch" means at this layer."""
    prof = _profile(tmp_path, "flat.obj", [_slab(0.0, 0.0, 30.0, 20.0, 0.0, base=-1.0)])
    assert prof.verdict == BP.FLAT, prof.line()
    assert len(prof.planes) == 1 and not prof.risers
    assert prof.offsets == (0.0,)


def test_furniture_under_the_area_floor_is_not_a_plane(tmp_path):
    """§1 (1): a horizontal cluster under ``[building_pad] min_area_m2``
    (250 m²) is FURNITURE.  A 5 × 5 m plinth beside a floor never becomes
    a second pad."""
    prof = _profile(tmp_path, "furniture.obj",
                    [_slab(0.0, 0.0, 30.0, 20.0, 0.0, base=-1.0),
                     _slab(31.0, 0.0, 5.0, 5.0, 2.0, base=-1.0)])
    assert prof.verdict == BP.FLAT, prof.line()
    assert len(prof.planes) == 1, prof.line()
    assert abs(prof.planes[0].y) < 1e-6


# ── A1: the ROOF fixture (the §6 STOP, and the HECA T3 risk) ─────────────

def test_roof_over_column_feet_is_not_a_base_plane(tmp_path):
    """§5 A1 row 4 + §6's first STOP: a slab at +4 over COLUMN FEET at 0
    reads ROOF, not a base — its support hull covers the polygon.  This
    is #162's ``Shelters.OBJ`` in miniature (1,752 column feet under
    6,149 m² of roof, hull 156 %) and the HECA T3 halls' upper floors."""
    posts = [_post(x, z, 1.0, 4.0)
             for x in (1.0, 10.0, 19.0, 28.0) for z in (1.0, 10.0, 18.0)]
    roof = _slab(0.0, 0.0, 30.0, 20.0, 4.0, base=3.8)
    prof = _profile(tmp_path, "roof.obj", posts + [roof])
    assert not prof.planes, prof.line()         # ZERO upper planes
    assert prof.verdict == BP.FEET, prof.line()
    assert prof.feet >= 4 * 12, prof.line()


def test_roof_support_hull_fraction_is_the_discriminator(tmp_path):
    """§1 (1): the test is the support hull's SHARE, so a plane with a few
    lower vertices CLUSTERED at one threshold is a BASE (KASE's garage
    threshold: 157 vertices, hull 0.2 % of a 6,394 m² lot) while the same
    count DISTRIBUTED is a roof.  One number, two answers."""
    clustered = [_post(x, z, 1.0, 4.0) for x in (1.0, 3.0) for z in (1.0, 3.0)]
    lot = _slab(0.0, 0.0, 30.0, 20.0, 4.0, base=3.8)
    prof = _profile(tmp_path, "lot.obj", clustered + [lot])
    assert len(prof.planes) == 1, prof.line()
    p = prof.planes[0]
    assert p.support_fraction < LAW["roof_support_fraction"], p.support_fraction
    # ... and §1 (1)'s TRIM took the threshold cells off it
    assert p.trimmed_m2 > 0.0, p
    assert p.polygon.area < 600.0


# ── the #162 FEET verdict (10-01k Q1) ────────────────────────────────────

def test_feet_only_object_mints_no_plane(tmp_path):
    """§5 A3 + 10-01k Q1: ``Shelters.OBJ``'s class — POSTS, no floor plane
    — reads FEET and mints NO pad.  The terrain stays at the apron grade;
    the OBJECT stage seats it (``airport/placement_tilt.py``), which is
    the other half of this twin set."""
    posts = [_post(x, 1.0, 1.0, 4.0) for x in range(0, 60, 6)]
    prof = _profile(tmp_path, "shelter.obj", posts)
    assert prof.verdict == BP.FEET, prof.line()
    assert not prof.planes and not prof.risers
    assert prof.feet == 4 * len(posts), prof.line()


# ── §1 (3) the composed UNIT profile ─────────────────────────────────────

def test_composition_folds_a_sibling_members_supports_into_a_roof(tmp_path):
    """§1 (3) + §5 A5's PRE-REGISTERED RISK: a member's own read cannot
    see supports living in a SIBLING member, so a hall's upper floor reads
    STEPPED per member (the §0 fact 10 UPPER BOUND) and must read ROOF
    once composed.  HECA T3 gaining a plane pad is a §6 STOP, and this is
    the twin that holds the line."""
    import numpy as np
    a = _profile(tmp_path, "hall.obj",
                 [_slab(0.0, 0.0, 30.0, 20.0, 0.0, base=-1.0),
                  _slab(0.0, 0.0, 30.0, 20.0, 4.0, base=3.8)])
    # RE-FOUNDED (owner RULINGS 2026-10-02m (B), lane basepads4): the
    # MEMBER read already folds this, because ``_storeys`` reads the
    # PLANES against each other and these two slabs share a footprint.
    # The composed roof test below still covers the case the twin was
    # written for -- supports in a SIBLING member, which no vertex
    # reading inside one member can reach.
    assert a.verdict == BP.FLAT and len(a.planes) == 1, a.line()
    assert abs(a.planes[0].y) < 1e-9, a.line()
    # the COLUMNS under that upper slab, as a sibling member would carry them
    lower = np.array([(x, 1.0, z)
                      for x in (2.0, 11.0, 20.0, 28.0) for z in (2.0, 10.0, 18.0)],
                     dtype=float)
    unit = BP.compose_profiles(
        [(a, (0.0, 0.0, 0.0))], seat_xz=(15.0, 10.0),
        pad_terrace_floor_m=LAW["pad_terrace_floor_m"],
        pad_frontage_m=LAW["pad_frontage_m"],
        roof_support_fraction=LAW["roof_support_fraction"],
        lower_pts=lower, contact_band_m=LAW["contact_band_m"],
        min_distinct_spacing_m=LAW["min_distinct_spacing_m"])
    assert unit.verdict == BP.FLAT, unit.line()
    assert len(unit.planes) == 1 and abs(unit.planes[0].y) < 1e-6, unit.line()


def test_composition_picks_the_seat_plane_as_the_origin(tmp_path):
    """§1 (3): ``p0`` is the base plane whose polygon CONTAINS the unit's
    seat point — not the largest.  Every other plane's offset is read
    against it, which is what the §2 (1) plane-offset row pins."""
    big = _slab(0.0, 0.0, 40.0, 30.0, 0.0, base=-2.0)        # 1,200 m2
    small = _slab(41.0, 0.0, 20.0, 20.0, 3.0, base=-2.0)     #   400 m2
    prof = _profile(tmp_path, "two.obj", [big, small])
    assert prof.verdict == BP.STEPPED
    # with no seat the LARGEST is p0
    bare = BP.compose_profiles([(prof, (0.0, 0.0, 0.0))],
                               pad_terrace_floor_m=1.0, pad_frontage_m=3.0)
    assert abs(bare.planes[0].y) < 1e-6, bare.line()
    # with the seat INSIDE the small plane, that one is p0 and the big
    # plane carries the offset
    seated = BP.compose_profiles([(prof, (0.0, 0.0, 0.0))], seat_xz=(51.0, 10.0),
                                 pad_terrace_floor_m=1.0, pad_frontage_m=3.0)
    assert abs(seated.planes[0].y - 3.0) < 1e-6, seated.line()
    assert seated.offsets[0] == 0.0
    assert abs(seated.offsets[1] + 3.0) < 1e-6, seated.offsets


def test_composition_translates_a_members_planes_by_its_offset(tmp_path):
    """§1 (3): the §16c contact graph gives the members' relative offset
    EXACTLY, so composition TRANSLATES; nothing is fitted."""
    a = _profile(tmp_path, "a.obj", [_slab(0.0, 0.0, 30.0, 20.0, 0.0, base=-1.0)])
    b = _profile(tmp_path, "b.obj", [_slab(0.0, 0.0, 20.0, 20.0, 0.0, base=-1.0)])
    unit = BP.compose_profiles([(a, (0.0, 0.0, 0.0)), (b, (0.0, 3.5, 60.0))],
                               pad_terrace_floor_m=1.0, pad_frontage_m=3.0)
    assert unit.verdict == BP.STEPPED, unit.line()
    assert sorted(round(p.y, 3) for p in unit.planes) == [0.0, 3.5], unit.line()
    # ... and they are FAR apart in plan, so there is no riser between them
    assert not unit.risers, unit.line()


def test_a_unit_with_no_base_plane_keeps_todays_law(tmp_path):
    """§1 (3) last sentence: a unit with no base plane keeps today's law
    exactly — the composed verdict is the member's, and no pad changes."""
    posts = [_post(x, 1.0, 1.0, 4.0) for x in range(0, 60, 6)]
    feet = _profile(tmp_path, "posts.obj", posts)
    unit = BP.compose_profiles([(feet, (0.0, 0.0, 0.0))],
                               pad_terrace_floor_m=1.0, pad_frontage_m=3.0)
    assert unit.verdict == BP.FEET, unit.line()
    assert not unit.planes


def test_disarming_the_read_is_todays_law(tmp_path):
    """``horizontal_ny`` 0 disarms the base read: every member reads FEET
    and no plane pad is ever minted (the law file's own off switch)."""
    prof = _profile(tmp_path, "off.obj",
                    [_slab(0.0, 0.0, 30.0, 20.0, 0.0, base=-1.0)],
                    horizontal_ny=0.0)
    assert prof.verdict == BP.FEET and not prof.planes, prof.line()


# ── THE TWO OPEN SPEC QUESTIONS, RECORDED AS TWINS ───────────────────────
# Reported, never decided (``Ortho4XP/CLAUDE.md``: a mid-implementation
# deviation is ruled by the spec's Fable author).  Each twin asserts what
# the code does TODAY so the ruling cannot land silently.

def test_a_T3_SHAPED_unit_with_perimeter_only_storeys_reads_no_base_plane(
        tmp_path):
    """§6's STANDING STOP, MADE REAL (owner RULINGS 2026-10-02m (B), the
    measured reason PR #196 was reverted; lane basepads4).

    ``road_train/T3_concrete_Yellow.obj`` on the real HECA v12 plan: 5
    slabs of 16,756 m2 at ONE footprint, stacked, their support carried
    by walls running around the perimeter -- **26 lower vertices ON the
    polygon, 0 strictly inside it**.  #196's ``_roof_test`` counted
    support strictly inside the ERODED polygon, which is the one place a
    stacked storey has none: all five read BASE, unit:43 read STEPPED
    with 89 planes and ``building4`` took 12 plane pads up to +25.6 m
    (HECA pads 432 -> 529).

    The bar: ONE base plane, the lowest, and therefore NO plane pad.
    This test FAILS on #196's code."""
    S = 129.4                                   # 16,756 m2, T3's own
    parts = []
    for k in range(5):
        y = k * 6.4
        parts.append(_slab(0.0, 0.0, S, S, y, base=(y - 6.4 if k else -0.5)))
    prof = _profile(tmp_path, "T3_concrete_Yellow.obj", parts)
    assert prof.verdict == BP.FLAT, prof.line()
    assert len(prof.planes) == 1, prof.line()
    assert abs(prof.planes[0].y) < 1e-6, prof.line()
    assert not prof.risers, prof.line()


def test_the_FIRE_STATION_lot_and_floor_mint_and_the_staircase_does_not(
        tmp_path):
    """§5 A2 / 10-02m (A) MADE REAL (lane basepads4): KASE's
    ``FireStation_7.obj`` -- the floor at 0, the +3.9 m upper lot, and
    the BANK STAIRCASE behind it at +4.1, +4.4, +4.6, +5.1, +5.6, +5.9,
    +6.1, +6.6 m (47-210 m2 each, the cut slope).

    #196 chained every one of those 0.25 m bins (each gap 0.25 <=
    ``split_tol_m`` 0.3, and the bin is NARROWER than the tolerance, so
    the chain never breaks) into ONE cluster with the lot -- y +3.79,
    9,375 m2, vertex deviation 4.59 m -- which the LEVEL test then
    DROPPED, so FS_7 read ``sloped`` with 0 planes and the site #163 is
    about minted nothing at all.

    The bar: exactly TWO base planes (the floor and the lot) and ONE
    riser between them; the staircase sheets stay out, each being under
    ``min_area_m2`` (10-01k Q4: "every plane >= 250 m2").  This test
    FAILS on #196's code."""
    parts = [_slab(-30.0, -30.0, 30.0, 30.0, 0.0, base=-0.5),
             _slab(0.0, 0.0, 80.0, 80.0, 3.9, base=-0.5)]
    for i, y in enumerate([4.1, 4.4, 4.6, 5.1, 5.6, 5.9, 6.1, 6.6]):
        parts.append(_slab(0.0, 80.0 + i * 0.9, 80.0, 0.9, y, base=y - 0.4))
    prof = _profile(tmp_path, "FireStation_7.obj", parts)
    assert prof.verdict == BP.STEPPED, prof.line()
    assert len(prof.planes) == 2, prof.line()
    ys = sorted(float(q.y) for q in prof.planes)
    assert abs(ys[0]) < 1e-9, prof.line()
    # §5 A2's bar on the lot: within 0.3 m of the authored +3.9 (the
    # +4.1 m first bank tread welds in under ``pad_terrace_floor_m``,
    # which is the law, and moves it by 2 mm)
    assert abs(ys[1] - 3.9) <= 0.3, prof.line()
    assert len(prof.risers) == 1, prof.line()
    # ``Riser.dy`` is the record's own 4-dp rounding
    assert abs(abs(prof.risers[0].dy) - (ys[1] - ys[0])) < 1e-4, prof.line()


def test_an_OPEN_shell_still_reads_its_top_as_the_base_plane(tmp_path):
    """THE MEASUREMENT THAT KEEPS 10-02m (B) OFF THE PERIMETER BAND
    (lane basepads4, reported not decided).  The brief asks the roof
    test to count support "on or within the perimeter band".  A slab on
    a vertical SKIRT has its own foot ring directly below its own
    boundary, so ANY outward band reads a 100 % support hull there and
    calls it a roof -- and that is the shape a pack authors a terrace
    lot in, KASE's own terrain sheet among them (11,820 of 12,335 m2
    horizontal, spec §0 fact 5).  It is a BASE plane.  What carries
    10-02m (B) instead is ``_storeys``, which asks whether there is a
    PLANE under this plane."""
    prof = _profile(tmp_path, "shell.obj",
                    [_slab(0.0, 0.0, 30.0, 20.0, 0.0, base=-1.0)])
    assert prof.verdict == BP.FLAT and len(prof.planes) == 1, prof.line()
    assert abs(prof.planes[0].y) < 1e-9, prof.line()


def test_a_flat_underside_also_reads_as_a_base_plane(tmp_path):
    """OPEN QUESTION 1 — is ``horizontal_ny`` SIGNED?

    §1 (1) defines a HORIZONTAL FACE by ``|n_y| >= horizontal_ny``, which
    admits a DOWN-facing face.  So a floor plate authored as a CLOSED box
    mints TWO base planes: its top (the floor the terrain must meet) and
    its underside (geometry no terrain ever touches), with a riser between
    them that is the plate's own thickness.

    The KASE pack's own sheets are open shells (``FireStation_7.obj``:
    354 tris over 12,335 m², §0 fact 5), so the measured sites do not show
    it — but a pack that closes its plates would get a phantom lower pad.

    This twin states the behaviour; the spec author rules whether the test
    should become ``n_y >= horizontal_ny`` (up-facing only)."""
    prof = _profile(tmp_path, "closed.obj",
                    [_closed_slab(0.0, 0.0, 30.0, 20.0, 0.0, base=-2.0)])
    assert prof.verdict == BP.FLAT, prof.line()
    assert len(prof.planes) == 1, prof.line()
    # RE-FOUNDED (owner RULINGS 2026-10-02m (B), lane basepads4): the
    # PHANTOM LOWER PAD this twin warned about is GONE.  The box's TOP
    # overlaps its own underside in plan by 100 %, and a terrain surface
    # is single-valued in plan, so §1 (1)'s storey reading
    # (``obj8_grade._storeys``) folds the top away and ONE plane is left
    # -- the UNDERSIDE, which is where a closed box standing on the
    # ground actually meets it.  The spec author's open question ("up-
    # facing only?") no longer changes the pad COUNT, only which of the
    # two heights the one plane reads at.
    assert abs(prof.planes[0].y + 2.0) < 1e-6, prof.line()
    assert not prof.risers, prof.line()


def test_a_level_cluster_is_required_for_a_plane(tmp_path):
    """OPEN QUESTION 2 — must a PLANE be LEVEL?

    §1 (1) makes any ``|n_y| >= 0.95`` cluster over 250 m² a plane, and
    §1 (2) reads SLOPED only when there is NO such plane.  A 2 % slab 40 m
    long is such a face, so under the literal wording the SLOPED verdict
    is unreachable by the geometry it describes.  ``base_profile``
    therefore requires a cluster's own VERTICES to fit one level height
    within ``split_tol_m`` — the spec's own "is this one plane" tolerance,
    so no new number is introduced.

    Here: a 0.2 m-deep dish over 30 m (within the tolerance) IS one plane;
    the 2 % slab of :func:`test_sloped_carries_the_base_gradient` is not.
    The spec author rules whether this is the intended reading."""
    v = [(0.0, 0.0, 0.0), (30.0, 0.2, 0.0), (30.0, 0.2, 20.0), (0.0, 0.0, 20.0),
         (0.0, -3.0, 0.0), (30.0, -2.8, 0.0), (30.0, -2.8, 20.0), (0.0, -3.0, 20.0)]
    t = [(0, 1, 2), (0, 2, 3),
         (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
         (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    prof = _profile(tmp_path, "dish.obj", [(v, t)])
    assert prof.verdict == BP.FLAT, prof.line()
    assert len(prof.planes) == 1, prof.line()


# ── §2 (1) THE PLANE-PAD REF GRAMMAR (§3 C7) ─────────────────────────────

def test_plane_pad_ref_grammar_folds_to_its_unit():
    """§2 (1) / §3 C7: a plane pad carries ``<unit>/p<k>`` at the ONE
    grammar site, and ``unit_ref_of`` folds it exactly as it folds a
    block's ``/b<k>`` — so every reader keyed on the unit ref still sees
    ONE unit (C25: ``pad_cluster_mismatch`` cannot report a cluster
    spanning its own plane pads)."""
    from auto_patch_v2.model.planar import (COLLAR_SUFFIX, block_ref,
                                            plane_of, plane_ref, unit_ref_of)
    r = plane_ref("building2", 1)
    assert r == "building2/p1"
    assert plane_of(r) == ("building2", 1)
    assert unit_ref_of(r) == "building2"
    # the collar of a plane pad, and a BLOCK inside one (§2 (1): blocks run
    # INSIDE a plane pad, never across a riser)
    assert plane_of(r + COLLAR_SUFFIX) == ("building2", 1)
    assert unit_ref_of(r + COLLAR_SUFFIX) == "building2"
    inner = block_ref(r, 2)
    assert inner == "building2/p1/b2"
    assert plane_of(inner) == ("building2", 1)
    assert unit_ref_of(inner) == "building2"
    # p0 is the ORIGIN PLANE and is a plane pad like any other
    assert plane_of(plane_ref("building2", 0)) == ("building2", 0)
    # and nothing else parses as one
    for other in ("building2", "building2#collar", "building2/b3", "pav7",
                  "building2/pX", "/p1"):
        assert plane_of(other) is None, other


# ── §2 (3) / §3 C17 THE DECLARED RISER AND ITS CENSUS EXEMPTION ──────────

def test_base_plane_step_is_a_registered_step_exemption():
    """§2 (3) / §3 C17 (owner RULINGS 2026-10-01f): the riser between two
    plane pads of ONE unit is LAWFUL geometry, registered under its own
    name so a report says which law applied — and so
    ``terrace_actual_step`` prices the EMITTED step against the DECLARED
    riser rather than forgiving it blind."""
    import tools.check_grade as cg

    class _W:
        def __init__(self, ref, role="building"):
            self.tags = {"role": role, "ref": ref}

    # two planes of ONE unit -> the NAMED base-plane exemption
    assert cg._step_exemption_for(_W("building2/p0"), _W("building2/p1")) \
        == "base_plane_step"
    # a block inside one plane against a block inside the other, likewise
    assert cg._step_exemption_for(_W("building2/p0/b1"), _W("building2/p1/b0")) \
        == "base_plane_step"
    # TWO INDEPENDENT pads keep the 06-20 exemption — the base-profile
    # ruling adds a name, it does not widen what is forgiven
    assert cg._step_exemption_for(_W("building16"), _W("building30")) \
        == "building_to_building"
    # ... and so do two BLOCKS of one unit (that is 30r's law, not this one)
    assert cg._step_exemption_for(_W("building2/b0"), _W("building2/b1")) \
        == "building_to_building"
    # two faces of the SAME plane are not a step pair at all
    assert cg._step_exemption_for(_W("building2/p1"), _W("building2/p1")) \
        == "building_to_building"
    # a pad against PAVEMENT is still gated (the 06-20 sentence's own tail)
    assert cg._step_exemption_for(_W("building2/p0"), _W("pav7", "apron")) is None
    # the exemption is REGISTERED with its ruling (one authority, read by
    # both the harness census and the acceptance gate)
    assert "base_plane_step" in cg.STEP_EXEMPTIONS
    assert "2026-10-01f" in cg.STEP_EXEMPTIONS["base_plane_step"]


def test_the_plane_pad_separator_is_one_spelling():
    """§2 (1): the validator may not import solver state, so it quotes the
    separator — and the two spellings must agree or the census would read
    a plane pad the emitter wrote as an ordinary pad (the cross-language
    wire-protocol hazard, in one language)."""
    import tools.check_grade as cg
    from auto_patch_v2.model import planar
    assert cg.PLANE_PAD_SEP == planar.PLANE_SEP
    assert cg.BASE_STEP_JOINT_KIND == "base_step"


def test_terrace_actual_step_prices_a_base_step_joint_as_declared():
    """§2 (3) / §3 C17: the riser is published as a ``terrace_joints``
    record of kind ``base_step`` carrying ``declared_step_m = Δy``, and the
    census reads it through the family it already has —
    ``terrace_actual_step`` (``families.toml:103``) — pricing the EMITTED
    step against the DECLARED one.  "One family extended, never a parallel
    rule."

    The fixture is §4's own emittable form: two plane pads of ONE unit
    whose rims are the two vertex rows of the 0.5 m identity strip
    (``min_distinct_spacing_m``), with the declared riser between them.

    Three readings, because "forgiven" and "priced as declared" are not
    the same thing and only the second is the law:

    * the EMITTED step equal to the declared riser -> no row;
    * an emitted step PAST it -> a row, with the excess measured;
    * the joints read KIND-BLIND, so a ``base_step`` record is not
      silently dropped the way a private census once dropped
      ``terrace_joints_ll`` whole (RULINGS 2026-08-30l).
    """
    import math

    import tools.check_grade as cg

    lat0, lon0 = 39.2215, -106.8701
    cos0 = math.cos(math.radians(lat0))

    def ll(x, y):
        return (lat0 + math.degrees(y / cg.R_EARTH),
                lon0 + math.degrees(x / (cg.R_EARTH * cos0)))

    #: the identity strip's half width — the two rims are one
    #: ``min_distinct_spacing_m`` apart across the riser, never coincident
    half = 0.5 * LAW["min_distinct_spacing_m"]
    declared = 3.0

    def _pads(dy: float):
        """``(nodes, ways)``: ``p0`` at z 100 south of the joint, ``p1`` at
        ``100 + dy`` north of it, both ``building`` faces of one unit."""
        lo = [(-20.0, -half), (20.0, -half), (20.0, -20.0), (-20.0, -20.0)]
        hi = [(-20.0, half), (20.0, half), (20.0, 20.0), (-20.0, 20.0)]
        nodes, ways = {}, []
        for k, (ring, z, ref) in enumerate(((lo, 100.0, "building2/p0"),
                                            (hi, 100.0 + dy, "building2/p1"))):
            nids = []
            for j, (x, y) in enumerate(ring):
                nid = f"n{k}{j}"
                nodes[nid] = ll(x, y)
                nids.append(nid)
            ways.append(cg.Way(f"w{k}", "building", ref, "", nids + [nids[0]],
                               [z] * (len(nids) + 1),
                               {"role": "building", "ref": ref}))
        return nodes, ways

    nodes, ways = _pads(declared)
    ll_to_m = cg._ll_to_m_factory(nodes)
    # the DECLARED riser, as §2 (3) publishes it
    joint_rows = [{"points": [ll(-20.0, 0.0), ll(20.0, 0.0)],
                   "step_m": declared, "kind": cg.BASE_STEP_JOINT_KIND,
                   "declared_step_m": declared}]
    joints = cg._terrace_joints_to_m(joint_rows, ll_to_m)
    assert joints and joints[0][1] == declared, joints
    rows = cg._check_terrace_actual_step(joints, ways, nodes, ll_to_m, 0.015)
    assert not rows, [(v.de_m, v.distance_m) for v in rows]

    # the emitted step PAST the declared riser is priced
    nodes2, ways2 = _pads(declared + 1.5)
    ll_to_m2 = cg._ll_to_m_factory(nodes2)
    joints2 = cg._terrace_joints_to_m(
        [{"points": [ll(-20.0, 0.0), ll(20.0, 0.0)], "step_m": declared,
          "kind": cg.BASE_STEP_JOINT_KIND, "declared_step_m": declared}],
        ll_to_m2)
    rows2 = cg._check_terrace_actual_step(joints2, ways2, nodes2, ll_to_m2, 0.015)
    assert rows2, "an emitted step past the declared riser must be priced"
    assert max(v.de_m for v in rows2) > declared, [v.de_m for v in rows2]

    # UNDECLARED, the same geometry is the whole step: the declaration is
    # what the family prices against, not a blanket forgiveness
    bare = cg._check_terrace_actual_step(
        cg._terrace_joints_to_m(
            [{"points": [ll(-20.0, 0.0), ll(20.0, 0.0)], "step_m": 0.0,
              "kind": cg.BASE_STEP_JOINT_KIND}], ll_to_m),
        ways, nodes, ll_to_m, 0.015)
    assert bare and max(v.de_m for v in bare) >= declared - 1e-9, \
        [v.de_m for v in bare]


# ══════════════════════════════════════════════════════════════════════
# WHAT lane basepads4read MEASURED ON THE REAL CAPTURES (PR #220)
#
# Both of these are STRICT XFAILs: pre-registered bars, failing for the
# reason recorded, which go XPASS -- and so FAIL -- the moment the
# mechanism lands.  That is what forces the marker off rather than
# letting a measured STOP be forgotten.  Each needs a ruling, not a
# guess, so neither is "fixed" here.
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.xfail(strict=True, reason=(
    "PR #220 item 3, a STOP, measured by lane basepads4read on the real "
    "HECA v12 plan: `_storeys` cannot see a T3 roof because the T3 ground "
    "floor is NOT a horizontal plane in the composed unit, so no lower "
    "PLANE exists for the roof to overlap. Cover of building157's "
    "+18.90 m plane by ALL lower planes combined is 0.13; building4/b1's "
    "+12.58 m is 0.29; building168's +12.30 m is 0.00. building157 mints "
    "that +18.90 m roof as its ORIGIN plane p0 (12,951 m2) with p4 at "
    "-0.63 m. A plan-overlap discriminator is necessary but NOT "
    "sufficient: what is missing is a rule that a base plane must be "
    "GROUND -- either a height ceiling over the unit's feet (a NEW LAW "
    "NUMBER, the owner's: somewhere between KASE's +3.9 m lot and T3's "
    "+12.58 m roof) or p0 forced to the LOWEST plane rather than the "
    "largest. Spec author rules."))
def test_a_roof_over_a_unit_with_NO_horizontal_ground_floor_is_not_a_base(
        tmp_path):
    """A T3 hall as the real plan has it: a big roof slab high above, and
    a ground floor that is NOT horizontal, so no lower plane exists for
    the roof to stand on.  The roof must not read as a base plane, and
    above all must never become the ORIGIN plane."""
    S = 113.8                                   # 12,951 m2, building157's
    V, T = _slab(0.0, 0.0, S, S, 18.90, base=0.0)
    V, T = list(V), list(T)
    k = len(V)
    # the GROUND: a RAMPED floor (|n_y| < 0.95 -> not a horizontal face)
    V += [(0.0, -0.63, 0.0), (S, 2.5, 0.0), (S, 2.5, S), (0.0, -0.63, S)]
    T += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    prof = _profile(tmp_path, "T3_hall.obj", [(V, T)])
    high = [q for q in prof.planes if q.y > 5.0]
    assert not high, prof.line()


@pytest.mark.xfail(strict=True, reason=(
    "PR #220 item 4, measured by lane basepads4read: KASE still mints 0 "
    "plane pads. FireStation_7's +3.90 m lot is 6,398 m2 over 209 faces "
    "whose vertices span +2.96..+4.44 m -- a ~2 % TILTED surface inside "
    "ONE 0.25 m bin. The deviation split this PR added splits BETWEEN "
    "bins and cannot split within one, so the LEVEL test still drops the "
    "cluster and FS_7 reads `sloped` with 0 planes; unit:108 then "
    "composes to `feet` because it has TWO sloped members (FS_2 and "
    "FS_7) while the single-sloped branch needs exactly one. The lot is "
    "genuinely sloped, so the answer is 10-01k Q5's own gradient -- but "
    "spec §1 (2) has SLOPED only as a WHOLE-MEMBER verdict with no base "
    "plane, not as one sloped plane among others, so admitting it is a "
    "SPEC EXTENSION. Spec author rules."))
def test_a_TILTED_lot_inside_one_bin_still_reaches_a_pad(tmp_path):
    """The fire-station lot as the pack really authors it: one surface at
    ~+3.9 m tilted ~2 %, so its own vertices span 1.48 m -- five times
    ``split_tol_m`` -- inside a single height bin.  It is the ground the
    station's upper lot stands on and must reach a pad, by whatever
    verdict the spec author rules."""
    V, T = _slab(-30.0, -30.0, 30.0, 30.0, 0.0, base=-0.5)
    V, T = list(V), list(T)
    k = len(V)
    # the LOT: 80 x 80 m rising +2.96 -> +4.44 (1.85 %), one bin
    V += [(0.0, 2.96, 0.0), (80.0, 4.44, 0.0), (80.0, 4.44, 80.0),
          (0.0, 2.96, 80.0)]
    T += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    prof = _profile(tmp_path, "FireStation_7_tilted.obj", [(V, T)])
    lot = [q for q in prof.planes if 2.5 <= q.y <= 4.6]
    assert lot, prof.line()
    assert prof.verdict == BP.STEPPED, prof.line()
