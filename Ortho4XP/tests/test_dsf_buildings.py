"""DSF building-facade reading + term_bridge grouping (20260614-02).

Covers:
* ``_building_role_for_def`` — terminal / hangar / bridge / None.
* the depth-5 facade bezier parse fix: a curved ``term_building_*.fac``
  is authored as ``(lon, lat, wall_param, ctrl_lon, ctrl_lat)`` per
  point; reading a fixed ``tok[3],tok[4]`` grabbed the wall param as the
  control lon (≈ a small integer), exploding the ring to continental
  scale.  The fix reads the LAST TWO planes, keeping the ring local.
* ``_cluster_dsf_building_facades`` connectors: a term_bridge joining two
  building footprints unions them into ONE pad; a bridge linking nothing
  is dropped; the no-connector path is unchanged.
* ``_combine_building_sources`` — OSM TERMINAL-WAY AUTHORITY (owner
  2026-08-09, docs/specs/osm-terminal-way-authority-spec.md): the OSM way
  is the building's identity and the DSF clusters majority-inside it are
  absorbed; the retired rule dropped the way instead.
"""
import os

from shapely.geometry import Polygon

import auto_patch.dsf_reader as D
from auto_patch.dsf_reader import _building_role_for_def
from auto_patch.terminals import (
    _cluster_dsf_building_facades,
    _combine_building_sources,
    building_pad_accounting,
    clip_pads_by_water,
    repunch_kept_ways_from_pads,
)
from auto_patch.config import (
    DSF_CLUSTER_OSM_ABSORB_FRAC,
    DSF_MIN_BUILDING_AREA_M2,
)


def test_building_role_for_def():
    base = "lib/airport/Modern_Airports/Terminal_kit/"
    assert _building_role_for_def(base + "term_building_Ground_01.fac") \
        == "terminal"
    assert _building_role_for_def(base + "term_bridge_01.fac") == "bridge"
    assert _building_role_for_def(base + "term_roof_level_01.fac") is None
    assert _building_role_for_def(
        "lib/airport/Common_Elements/Hangars/Blue_Hangar.fac") == "hangar"
    # Non-facade resources never classify, even with a matching substring.
    assert _building_role_for_def("foo/term_building_Ground.pol") is None
    assert _building_role_for_def("foo/term_bridge_thing.obj") is None


def test_building_role_for_stock_generic_buildings():
    """The stock generic-building families classify as "building" —
    the SPJC field case (2026-07-24): 47 Misc_Buildings placements
    (cargo terminals, warehouses, an office) were dropped and the
    cargo apron got no building pads."""
    misc = "lib/airport/Common_Elements/Misc_Buildings/"
    for name in ("Cargo_Terminal.fac", "Blue_Warehouse.fac",
                 "White_Warehouse.fac", "White_Office.fac"):
        assert _building_role_for_def(misc + name) == "building"
    assert _building_role_for_def(
        "lib/airport/buildings/offices/office_building_01.fac") \
        == "building"
    assert _building_role_for_def(
        "lib/airport/buildings/warehouses/cargo/blue.fac") == "building"
    assert _building_role_for_def(
        "lib/airport/buildings/utility/garage/6m/gray_1.fac") == "building"
    # Recognition is BY LIBRARY FOLDER: generic words alone never
    # classify, so third-party facades cannot false-positive.
    assert _building_role_for_def("MyPack/cargo_ramp.fac") is None
    assert _building_role_for_def("MyPack/warehouse_tarp.fac") is None
    assert _building_role_for_def("MyPack/office_fence.fac") is None
    # Non-facade resources under the recognized folders still refuse.
    assert _building_role_for_def(misc + "Cargo_Terminal.pol") is None


def _write_fake_dsf(tmp_path, body):
    """Create a fake .dsf + a fresh .dsf.text cache so ``_read_dsf_polys``
    parses our synthetic text without invoking DSFTool."""
    dsf = tmp_path / "fake.dsf"
    dsf.write_text("binary-placeholder")
    txt = tmp_path / "fake.dsf.text"
    txt.write_text(body)
    # Ensure the cache is NEWER than the dsf so no re-conversion is tried.
    now = os.path.getmtime(txt)
    os.utime(dsf, (now - 10, now - 10))
    return str(dsf)


_DEF = ("POLYGON_DEF lib/airport/Modern_Airports/Terminal_kit/"
        "term_building_Ground_01.fac\n")


def test_depth5_facade_ring_stays_local(tmp_path, monkeypatch):
    # Pretend DSFTool exists (we pre-seed the .text cache, so it is never
    # actually run).
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
    # A small square facade authored at depth 5: each point is
    # (lon, lat, wall_param, ctrl_lon, ctrl_lat).  All corners here are
    # plain (ctrl == anchor), wall_param = 3.  The buggy reader would
    # treat (3.0, lon) as the bezier handle and blow the ring up to
    # lon ≈ 3.
    pts = [(31.4000, 30.1000), (31.4010, 30.1000),
           (31.4010, 30.1010), (31.4000, 30.1010)]
    lines = ["BEGIN_POLYGON 0 6 5", "BEGIN_WINDING"]
    for lon, lat in pts:
        lines.append(
            f"POLYGON_POINT {lon:.6f} {lat:.6f} 3.000000 "
            f"{lon:.6f} {lat:.6f}")
    lines += ["END_WINDING", "END_POLYGON"]
    body = _DEF + "\n".join(lines) + "\n"
    dsf = _write_fake_dsf(tmp_path, body)

    polys = D._read_dsf_polys(
        dsf, lambda p: p.lower().endswith(".fac"), cache_dir=str(tmp_path))
    assert len(polys) == 1
    outer, holes, path = polys[0]
    lons = [lon for lon, _ in outer]
    lats = [lat for _, lat in outer]
    # The ring must stay inside the authored ~0.001° box — NOT explode to
    # lon ≈ 3 (the wall param) as the pre-fix reader did.
    assert min(lons) >= 31.39 and max(lons) <= 31.41
    assert min(lats) >= 30.09 and max(lats) <= 30.11


def test_depth5_facade_bezier_is_curved(tmp_path, monkeypatch):
    # A depth-5 point whose ctrl differs from the anchor is a real bezier
    # handle (cols 4-5) and must produce extra interpolated vertices.
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
    pts = [
        # (lon, lat, param, ctrl_lon, ctrl_lat)
        (31.4000, 30.1000, 0.0, 31.4000, 30.1000),   # corner
        (31.4010, 30.1000, 0.0, 31.4014, 30.1004),   # handle near anchor
        (31.4010, 30.1010, 0.0, 31.4010, 30.1010),   # corner
        (31.4000, 30.1010, 0.0, 31.4000, 30.1010),   # corner
    ]
    lines = ["BEGIN_POLYGON 0 6 5", "BEGIN_WINDING"]
    for lon, lat, p, cl, ca in pts:
        lines.append(
            f"POLYGON_POINT {lon:.6f} {lat:.6f} {p:.6f} {cl:.6f} {ca:.6f}")
    lines += ["END_WINDING", "END_POLYGON"]
    body = _DEF + "\n".join(lines) + "\n"
    dsf = _write_fake_dsf(tmp_path, body)
    outer, _, _ = D._read_dsf_polys(
        dsf, lambda p: p.lower().endswith(".fac"),
        cache_dir=str(tmp_path))[0]
    # More than the 4 raw corners (the curved edge was tessellated), and
    # still local.
    assert len(outer) > 4
    lons = [lon for lon, _ in outer]
    assert min(lons) >= 31.39 and max(lons) <= 31.41


def _sq(x0, y0, w, h):
    return Polygon([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h),
                    (x0, y0 + h)])


def test_cluster_bridge_merges_two_buildings():
    # Two 20x20 buildings, 10 m apart — comfortably past the proximity-merge
    # reach (2 × DSF_FACADE_MERGE_GAP_M = 4 m; the old 4 m gap sat EXACTLY on
    # that threshold and flapped with the buffer arithmetic).  A bridge slab
    # spanning the gap is admitted into the SAME facade pool (the caller's
    # gate decides) and unions the run into one flat group.
    a = _sq(0, 0, 20, 20)
    b = _sq(30, 0, 20, 20)
    bridge = _sq(19, 8, 12, 4)   # spans the 10 m gap, overlaps both
    assert len(_cluster_dsf_building_facades([a, b])) == 2     # gap → 2
    assert len(_cluster_dsf_building_facades([a, b, bridge])) == 1


def test_cluster_freestanding_bridge_slab_is_a_pad():
    # A term_bridge slab that IS the concourse floor (no abutting
    # term_building) is still a real building component → its own pad
    # (≥ min_area).  Complex buildings union ALL their facade classes.
    a = _sq(0, 0, 20, 20)
    slab = _sq(200, 200, 40, 40)   # 1600 m², free-standing
    out = _cluster_dsf_building_facades([a, slab])
    assert len(out) == 2


def test_cluster_separate_buildings_unchanged():
    a = _sq(0, 0, 20, 20)
    b = _sq(100, 0, 20, 20)
    assert len(_cluster_dsf_building_facades([a, b])) == 2


# ──────────────────────────────────────────────────────────────────
# OSM terminal-way authority over DSF cluster swarms (owner 2026-08-09,
# docs/specs/osm-terminal-way-authority-spec.md).  An OSM terminal way IS
# the identity of its building: the way is kept whole and the DSF clusters
# majority-inside it are ABSORBED.  The retired rule
# (DSF_BUILDING_OSM_OVERLAP_FRAC 0.2) did the reverse — it deleted the way.
# v2 (2026-08-09, spec §2.3b): a SURVIVING cluster that still overlaps a
# kept way is CLIPPED by it — no emitted pad overlaps a kept way.
# ──────────────────────────────────────────────────────────────────


def _assert_no_pad_overlaps_way(out, ways):
    """Spec §2.3b's invariant: pairwise pad ∩ way is empty (area 0) for
    every emitted polygon that is not itself one of the kept ways."""
    for poly in out:
        if any(poly.equals(w) for w in ways):
            continue
        for w in ways:
            assert poly.intersection(w).area == 0.0


def test_combine_absorbs_interior_cluster_swarm():
    # One OSM way + a swarm of clusters entirely inside it → exactly one
    # combined polygon, the WAY.  (OTHH Concourse C: 153 structure hulls
    # inside a 162-node way that used to be deleted for them.)
    way = _sq(0, 0, 300, 100)
    swarm = [_sq(10 + 20 * k, 20, 15, 60) for k in range(10)]
    out = _combine_building_sources(
        swarm, [way], DSF_CLUSTER_OSM_ABSORB_FRAC)
    assert len(out) == 1
    assert out[0].equals(way)


def test_combine_keeps_cluster_mostly_outside_clipped():
    # A jet bridge / canopy hanging off the facade: 40 % inside the way,
    # 60 % outside → NOT absorbed, it survives as its own pad — CLIPPED
    # by the way (spec §2.3b, v2): the way owns its footprint, so the
    # pad keeps exactly the 60 % that lies outside.
    way = _sq(0, 0, 200, 100)
    hanging = _sq(180, 30, 50, 40)      # 20 m of 50 m inside → 0.4
    out = _combine_building_sources(
        [hanging], [way], DSF_CLUSTER_OSM_ABSORB_FRAC)
    assert len(out) == 2                       # survivors + osm
    assert abs(out[0].area - 0.6 * hanging.area) < 1e-6
    assert out[0].equals(hanging.difference(way))
    assert out[1].equals(way)
    _assert_no_pad_overlaps_way(out, [way])


def test_combine_absorbs_at_exact_boundary_fraction():
    # Exactly at the absorb fraction → ABSORBED (the test is >=, not >).
    way = _sq(0, 0, 200, 100)
    half_in = _sq(180, 30, 40, 40)     # 20 m of 40 m inside → exactly 0.5
    assert DSF_CLUSTER_OSM_ABSORB_FRAC == 0.5   # shipped default pin
    out = _combine_building_sources([half_in], [way], 0.5)
    assert len(out) == 1 and out[0].equals(way)
    # A hair above the achieved fraction and the cluster stands — proving
    # the boundary case above is decided by ">=", not by rounding.
    assert len(_combine_building_sources(
        [half_in], [way], 0.5 + 1e-9)) == 2


def test_combine_zero_osm_ways_is_identity():
    # Degeneracy gate: an airport with no OSM terminal ways gets the
    # cluster list back UNCHANGED — same objects, same order (§2.3, the
    # bit-for-bit guarantee).
    clusters = [_sq(0, 0, 20, 20), _sq(100, 0, 30, 30)]
    out = _combine_building_sources(
        clusters, [], DSF_CLUSTER_OSM_ABSORB_FRAC)
    assert [id(g) for g in out] == [id(g) for g in clusters]


def test_combine_keeps_way_covered_by_swarm_old_rule_pin():
    # REGRESSION PIN against reintroducing the retired drop rule: a way
    # 51 % covered by a swarm of tiny hulls (the OTHH Concourse C ratio)
    # used to be DELETED (coverage >= 0.2 of the WAY's area).  Under the
    # new law the way is kept and every hull inside it is absorbed.
    way = _sq(0, 0, 100, 100)                     # 10,000 m²
    swarm = [_sq(10 * (k % 10), 10 * (k // 10), 10, 10)
             for k in range(51)]                  # 51 % of the way's area
    covered = _uunion(swarm).intersection(way).area / way.area
    assert abs(covered - 0.51) < 1e-9             # the old rule's trigger
    out = _combine_building_sources(
        swarm, [way], DSF_CLUSTER_OSM_ABSORB_FRAC)
    assert len(out) == 1 and out[0].equals(way)


def test_combine_clips_cluster_that_contains_the_way():
    # THE CONTAINMENT CASE (v2, spec §2.3b) — measured as the dominant
    # battery pattern: a DSF cluster several times LARGER than the way,
    # containing it whole.  cluster ∩ way / cluster.area = 1/9 < 0.5, so
    # the cluster is NOT absorbed; under v1 it survived whole and made
    # two overlapping pads at two altitudes.  Now it is clipped: the way
    # is kept, its footprint is cut out of the cluster, and the genuine
    # outside extent survives.
    way = _sq(100, 100, 100, 100)          # 10,000 m²
    cluster = _sq(0, 0, 300, 300)          # 90,000 m², contains the way
    out = _combine_building_sources(
        [cluster], [way], DSF_CLUSTER_OSM_ABSORB_FRAC)
    assert len(out) == 2
    remainder, kept = out
    assert kept.equals(way)                              # way kept whole
    assert abs(remainder.area - (cluster.area - way.area)) < 1e-6
    assert len(remainder.interiors) == 1                 # the way's hole
    _assert_no_pad_overlaps_way(out, [way])


def test_combine_drops_sub_min_area_clip_remainder():
    # A clip remainder under DSF_MIN_BUILDING_AREA_M2 (20 m²) is DROPPED
    # — a sliver of facade sticking out past the way is not a building.
    # 6x5 = 30 m² cluster with 2.4 m of its width inside: 12 m² inside
    # (frac 0.4 < 0.5, so it survives the absorb test) and an 18 m²
    # remainder, under the floor.
    way = _sq(0, 0, 100, 100)
    sliver = _sq(97.6, 40, 6, 5)
    assert abs(sliver.intersection(way).area / sliver.area - 0.4) < 1e-9
    assert sliver.difference(way).area < DSF_MIN_BUILDING_AREA_M2
    out = _combine_building_sources(
        [sliver], [way], DSF_CLUSTER_OSM_ABSORB_FRAC)
    assert len(out) == 1 and out[0].equals(way)


def test_combine_clip_emits_multipolygon_parts_separately():
    # A cluster the way cuts IN TWO emits each surviving part as its own
    # pad (MultiPolygon remainder → parts), and no part overlaps the way.
    way = _sq(100, 0, 40, 200)                  # a vertical band
    straddler = _sq(0, 60, 300, 50)             # crossed by the band
    frac = straddler.intersection(way).area / straddler.area
    assert frac < DSF_CLUSTER_OSM_ABSORB_FRAC   # survives the absorb test
    out = _combine_building_sources(
        [straddler], [way], DSF_CLUSTER_OSM_ABSORB_FRAC)
    assert len(out) == 3                        # 2 parts + the way
    assert out[-1].equals(way)
    assert all(p.geom_type == "Polygon" for p in out)
    assert abs(sum(p.area for p in out[:2])
               - straddler.difference(way).area) < 1e-6
    _assert_no_pad_overlaps_way(out, [way])


def _pipeline_pad_stage(cluster_seeds, way_seeds, absorb_frac=None):
    """Replay pipeline.py's building-pad stage on synthetic seeds:
    merge -> _close_building_outline + simplify -> §2.6 RE-PUNCH.
    Returns ``(cluster_pads, way_pads)`` in emission order."""
    from auto_patch.terminals import _close_building_outline as _close
    from auto_patch.config import TERMINAL_SIMPLIFY_TOL_M as _TOL
    frac = (DSF_CLUSTER_OSM_ABSORB_FRAC if absorb_frac is None
            else absorb_frac)
    kept: list = []
    combined = _combine_building_sources(
        cluster_seeds, way_seeds, frac, kept_osm_out=kept)
    way_ids = {id(w) for w in kept}
    cluster_pads, way_pads = [], []
    for seed in combined:
        sink = way_pads if id(seed) in way_ids else cluster_pads
        for pad in _close(seed):
            simp = pad.simplify(_TOL, preserve_topology=True)
            if (simp.geom_type == "Polygon" and not simp.is_empty
                    and simp.area >= 100.0):
                pad = simp
            sink.append(pad)
    if way_pads and cluster_pads:
        cluster_pads = repunch_kept_ways_from_pads(cluster_pads, way_pads)
    return cluster_pads, way_pads


def test_repunch_survives_the_close_refill_emiri_class():
    # REGRESSION PIN for the v3 finding (integration build, OTHH): the
    # merge-time clip is UNDONE by _close_building_outline whenever the
    # clip hole is narrower than BUILDING_OUTLINE_FILL_GATE_M — the close
    # swallows it (fill radius 110 m) and the reopen test at 55 m returns
    # EMPTY.  The way then sat inside the refilled cluster pad and was
    # deleted downstream as an "OSM relation duplicate".  With the §2.6
    # re-punch the hole is restored AFTER the close, so the pair reaches
    # emission as donut + way.
    from auto_patch.config import BUILDING_OUTLINE_FILL_GATE_M as _GATE_M
    cluster = _sq(0, 0, 400, 400)
    way = _sq(150, 150, 80, 80)          # inradius 40 m < 55 m gate
    assert way.area / cluster.area < DSF_CLUSTER_OSM_ABSORB_FRAC
    assert 40.0 < _GATE_M                # the refill condition holds
    # Without the re-punch the close refills the hole (the bug):
    refilled = _close_building_outline(
        _combine_building_sources(
            [cluster], [way], DSF_CLUSTER_OSM_ABSORB_FRAC)[0])
    assert len(refilled) == 1 and not refilled[0].interiors
    # With the pipeline stage (re-punch included) the hole is back:
    cluster_pads, way_pads = _pipeline_pad_stage([cluster], [way])
    assert len(way_pads) == 1 and len(cluster_pads) == 1
    donut = cluster_pads[0]
    assert len(donut.interiors) == 1
    assert donut.intersection(way_pads[0]).area < 1.0
    # ...and the duplicate-drop's containment test can no longer fire:
    # neither pad is >= 80 % inside the other (elevation.DUPLICATE_FRAC).
    for a, b in ((donut, way_pads[0]), (way_pads[0], donut)):
        assert a.intersection(b).area / a.area < 0.80


def test_repunch_drops_sub_min_remainder_and_splits_parts():
    # §2.3b remainder rules apply to the re-punch too: a sub-20 m²
    # remainder drops, and a pad the way cuts in two emits both parts.
    way = _sq(0, 0, 100, 100)
    sliver = _sq(97.6, 40, 6, 5)                 # 18 m² outside → drops
    assert repunch_kept_ways_from_pads([sliver], [way]) == []
    straddler = _sq(-50, 40, 200, 20)            # cut in two by the way
    parts = repunch_kept_ways_from_pads([straddler], [way])
    assert len(parts) == 2
    assert all(p.geom_type == "Polygon" for p in parts)
    assert abs(sum(p.area for p in parts)
               - straddler.difference(way).area) < 1e-6
    # An EDGE-ONLY touch is left untouched (no ring churn).
    toucher = _sq(100, 0, 40, 40)
    out = repunch_kept_ways_from_pads([toucher], [way])
    assert len(out) == 1 and out[0].equals(toucher)
    # No kept ways at all → the pads come back unchanged.
    assert repunch_kept_ways_from_pads([toucher], []) == [toucher]


def test_building_pad_accounting_exposes_missing_refs():
    # The acceptance check reads constructed-vs-emitted from the refs:
    # refs are building{i+1} over the CONSTRUCTED list, so the highest
    # ref is the constructed count and the gaps are the pads a
    # downstream stage dropped (OTHH new arm: 103 constructed, 77
    # emitted, 26 missing; control 128/125/3).
    acc = building_pad_accounting(
        ["building1", "building2", "building4", "building7"])
    assert acc == {"constructed": 7, "emitted": 4,
                   "missing": [3, 5, 6], "missing_count": 3}
    assert building_pad_accounting([])["constructed"] == 0
    # Non-building refs are ignored, order does not matter.
    acc2 = building_pad_accounting(
        ["building3", "apron", "building1", "runway16L"])
    assert acc2["constructed"] == 3 and acc2["missing"] == [2]


from shapely.ops import unary_union as _uunion

from auto_patch.terminals import _close_building_outline
from auto_patch.config import BUILDING_OUTLINE_FILL_GATE_M as _GATE


def _fill_ratio(p):
    return p.area / p.convex_hull.area


def _comb(gap, depth=240, n=4, tooth=30):
    # Spine + ``n`` deep fingers separated by ``gap`` m — a stylised
    # finger-pier terminal with a low (deeply-concave) fill-ratio.
    spine = _sq(0, 0, (n - 1) * gap + n * tooth, 20)
    parts = [spine]
    x = 0
    for _ in range(n):
        parts.append(_sq(x, 20, tooth, depth))
        x += tooth + gap
    return _uunion(parts)


def test_close_absorbs_narrow_stands():
    # A deep comb (gaps 80 m < 2×GATE) is narrow-filled: the stands fill in
    # out to the tooth tips → one simpler, more solid pad.
    comb = _comb(80)
    out = _close_building_outline(comb)
    assert len(out) == 1
    closed = out[0]
    assert closed.area > comb.area
    assert _fill_ratio(closed) > _fill_ratio(comb)


def test_close_noop_on_convex():
    sq = _sq(0, 0, 200, 200)
    out = _close_building_outline(sq)
    assert len(out) == 1 and abs(out[0].area - sq.area) < 1.0


def test_close_preserves_wide_concavity():
    # A wide U (opening WIDER than 2×GATE) keeps its concavity — narrow-fill
    # bridges only the narrow stands, never the genuine reentrant shape.
    wide = 4 * _GATE + 60                 # > 2×GATE
    u = _sq(0, 0, wide + 100, 300).difference(_sq(50, 90, wide, 300))
    out = _close_building_outline(u)
    assert len(out) == 1
    assert _fill_ratio(out[0]) < 0.95


def test_close_fills_teeth_but_not_wide_centre():
    # The HECA case: a finger comb whose tooth gaps are NARROW (absorbed)
    # but whose open centre is WIDE (preserved).  Two outer-toothed piers
    # joined by a spine, with a wide gap between them.  Narrow-fill must
    # grow the area (teeth absorbed) yet stay well below the convex hull
    # (the wide centre is NOT bridged).
    centre_gap = 6 * _GATE                # >> 2×GATE → stays open
    pier_w, pier_h, tooth = 30.0, 240.0, 25.0
    left = _comb(40, depth=pier_h, n=1, tooth=pier_w)   # toothless pier core
    # left pier with outer teeth
    parts = [_sq(0, 0, pier_w, pier_h)]
    for k in range(4):
        parts.append(_sq(-tooth, 10 + k * 60, tooth, 25))   # teeth to the left
    rx = pier_w + centre_gap
    parts.append(_sq(rx, 0, pier_w, pier_h))
    for k in range(4):
        parts.append(_sq(rx + pier_w, 10 + k * 60, tooth, 25))  # teeth right
    parts.append(_sq(0, pier_h, rx + pier_w, 20))           # top spine
    comb = _uunion(parts)
    out = _close_building_outline(comb)
    merged = _uunion(out)
    assert merged.area > comb.area                  # teeth absorbed
    assert merged.area < 0.85 * comb.convex_hull.area   # centre NOT filled


# ──────────────────────────────────────────────────────────────────
# R6-1 — a DSF building pad never spans water
# (docs/specs/round6-othh-residuals-spec.md, owner in-sim residual)
# ──────────────────────────────────────────────────────────────────
def test_water_clip_removes_the_over_water_lobe():
    # THE OTHH SHAPE: the DSF cluster's footprint ring is a CONVEX HULL,
    # so building1 (19,466 m²) bridged a lagoon and its shore and carried
    # 2,055 m² — 10.6 % — of open water.  The clip takes the water back.
    pad = _sq(0, 0, 200, 100)                    # 20,000 m² hull
    lagoon = _sq(150, 0, 60, 40)                 # 2,000 m² inside the pad
    out = clip_pads_by_water([pad], lagoon)
    assert len(out) == 1
    assert abs(out[0].area - (pad.area - 2000.0)) < 1e-6
    # Nothing of the pad is left standing over water.
    assert out[0].intersection(lagoon).area < 1e-9


def test_water_clip_remainder_rules_match_2_3b():
    # ONE remainder law for the kept-way punch and the water clip:
    # sub-DSF_MIN_BUILDING_AREA_M2 drops, MultiPolygon parts emit
    # separately, an EDGE-ONLY touch leaves the pad untouched, and a
    # missing/empty union never deletes a building.
    water = _sq(0, 0, 100, 100)
    sliver = _sq(97.6, 40, 6, 5)                 # 18 m² outside → drops
    assert sliver.difference(water).area < DSF_MIN_BUILDING_AREA_M2
    assert clip_pads_by_water([sliver], water) == []
    straddler = _sq(-50, 40, 200, 20)            # cut in two by the water
    parts = clip_pads_by_water([straddler], water)
    assert len(parts) == 2
    assert all(p.geom_type == "Polygon" for p in parts)
    assert abs(sum(p.area for p in parts)
               - straddler.difference(water).area) < 1e-6
    toucher = _sq(100, 0, 40, 40)                # shares an edge only
    out = clip_pads_by_water([toucher], water)
    assert len(out) == 1 and out[0].equals(toucher)
    for empty_union in (None, Polygon()):
        assert clip_pads_by_water([toucher], empty_union) == [toucher]


def test_water_clip_is_cluster_pads_only_ways_untouched():
    # THE MAPPER OWNS THE FOOTPRINT THEY DREW.  The pipeline hands only
    # the DSF-CLUSTER pads to the clip; the kept OSM-way pads go straight
    # to the emitted list (OTHH's Emiri way -77 is 27 m inland and clean).
    # Pinned at the seam the clip sits on: cluster in, way out.
    import inspect

    import auto_patch.pipeline as P

    source = inspect.getsource(P.build_airport_pavement)
    assert "clip_pads_by_water(_cluster_pads, _water_u)" in source
    assert "clip_pads_by_water(_way_pads" not in source
    # ...and the helper does not care which is which — it clips whatever
    # it is given, so the CALLER is the whole of the way exemption.
    way_pad = _sq(0, 0, 50, 50)
    assert clip_pads_by_water([way_pad], _sq(0, 0, 25, 50))[0].area == 1250.0


def test_water_sea_union_reads_water_and_coastline_layers(monkeypatch):
    # The union's two limbs, over a synthetic tile cache: closed
    # ``natural=water`` ways, and the SEA derived from ``natural=coastline``
    # under the OSM orientation convention (LAND ON THE LEFT).
    from shapely.geometry import Point

    import auto_patch.osm_load as OL

    # A metre-frame projection anchored at the equator/prime meridian
    # keeps the arithmetic readable; to_m takes (lon, lat).
    from auto_patch.layout import _projection
    to_m = _projection((0.0, 0.0))

    def _ll(x_m, y_m):
        """(lat, lon) of a local metre offset — the loader's node shape."""
        import math
        from auto_patch.layout import R_EARTH
        return (math.degrees(y_m / R_EARTH), math.degrees(x_m / R_EARTH))

    # A 200 m lagoon east of the origin, and a coastline running NORTH
    # at x = 500: land on the left is WEST, so the sea is EAST.
    layers = {
        "water": (
            {"w1": _ll(1000, 0), "w2": _ll(1200, 0),
             "w3": _ll(1200, 200), "w4": _ll(1000, 200)},
            [("lagoon", ["w1", "w2", "w3", "w4", "w1"],
              {"natural": "water"})],
            {},
        ),
        "coastline": (
            {"c1": _ll(500, -3000), "c2": _ll(500, 3000)},
            [("shore", ["c1", "c2"], {"natural": "coastline"})],
            {},
        ),
    }
    monkeypatch.setattr(
        OL, "_load_osm_road_layer",
        lambda layer, lat, lon, radius=0.05: layers.get(layer, ({}, [], {})))

    union = OL._load_osm_water_sea_union(
        0.0, 0.0, to_m, (-400.0, -400.0, 1400.0, 400.0), sea_band_m=2000.0)
    assert union is not None and not union.is_empty
    # WEST of the shore is land; EAST of it is sea.
    assert not union.contains(Point(to_m(*reversed(_ll(400, 0)))))
    assert union.contains(Point(to_m(*reversed(_ll(600, 0)))))
    # The lagoon limb stands on its own (it is east of the shore too, so
    # assert it explicitly through a run with no coastline at all).
    layers.pop("coastline")
    water_only = OL._load_osm_water_sea_union(
        0.0, 0.0, to_m, (-400.0, -400.0, 1400.0, 400.0))
    assert water_only.contains(Point(to_m(*reversed(_ll(1100, 100)))))
    assert not water_only.contains(Point(to_m(*reversed(_ll(600, 0)))))


def test_water_sea_union_reads_coastline_ring_orientation(monkeypatch):
    # A CLOSED coastline ring: counter-clockwise encloses LAND (an
    # island), clockwise encloses WATER (an interior sea).  The reading
    # is O4_Vector_Utils.coastline_to_MultiPolygon's, not a new one.
    import math

    from shapely.geometry import Point

    import auto_patch.osm_load as OL
    from auto_patch.layout import R_EARTH, _projection

    to_m = _projection((0.0, 0.0))

    def _ll(x_m, y_m):
        return (math.degrees(y_m / R_EARTH), math.degrees(x_m / R_EARTH))

    corners = {"r1": _ll(-100, -100), "r2": _ll(100, -100),
               "r3": _ll(100, 100), "r4": _ll(-100, 100)}
    ccw = ["r1", "r2", "r3", "r4", "r1"]          # island (land inside)
    cw = list(reversed(ccw))                      # interior sea

    def _run(order):
        monkeypatch.setattr(
            OL, "_load_osm_road_layer",
            lambda layer, lat, lon, radius=0.05: (
                (corners, [("ring", order, {"natural": "coastline"})], {})
                if layer == "coastline" else ({}, [], {})))
        return OL._load_osm_water_sea_union(0.0, 0.0, to_m, None)

    centre = Point(to_m(0.0, 0.0))
    assert _run(cw).contains(centre)              # clockwise → water
    assert _run(ccw) is None                      # counter-clockwise → land
