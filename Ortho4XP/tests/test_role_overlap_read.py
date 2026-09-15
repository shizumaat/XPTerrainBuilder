"""ROLE OVERLAP READ — twins for ``tools/role_overlap_read.py``
(promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its
second use, RULINGS ``7e90032``).

The tool answers the question a ruling of the form "the spine must stop
at groundside pavement" is adjudicated on: the SQUARE METRES one emitted
role/ref class stands on another's footprint.  A census cannot — a face
lying flat on a lot breaks no grade law and prices zero rows.

These twins pin what makes it trustworthy:
  * the area it reports is the real intersection area, in the metre
    frame the SIDECAR declares;
  * the ROLE:REF selector is exact — a way of the right role and the
    wrong ref is not in the population;
  * a stack under the floor is not a stack;
  * it prices nothing and counts no defects — the report carries areas
    and populations only;
  * a patch with no sidecar is REFUSED (no frame declared);
  * a v2 sidecar — no top-level ``anchor`` by design — reads in v2's own
    node-mean frame instead of raising (RULINGS 2026-09-13cs chip);
  * this index row exists.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import role_overlap_read as ROR                           # noqa: E402

ANCHOR = (30.12, 31.40)


def _ll(x, y):
    lat = ANCHOR[0] + y / 111320.0
    lon = ANCHOR[1] + x / (111320.0 * math.cos(math.radians(ANCHOR[0])))
    return lat, lon


def _patch(tmp_path, name, rings, *, sidecar=True):
    """One emitted patch from ``(tags, ring_in_metres)`` pairs."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    nid = [-1]
    ways = []
    for tags, pts in rings:
        nids = []
        for (x, y) in pts:
            lat, lon = _ll(x, y)
            out.append(f"  <node id='{nid[0]}' lat='{lat:.11f}' "
                       f"lon='{lon:.11f}'>\n"
                       f"    <tag k='alt_abs' v='100.00' />\n  </node>\n")
            nids.append(nid[0])
            nid[0] -= 1
        nids.append(nids[0])
        ways.append((nids, tags))
    wid = -900
    for nids, tags in ways:
        out.append(f"  <way id='{wid}'>\n")
        for n in nids:
            out.append(f"    <nd ref='{n}' />\n")
        for k, v in sorted(tags.items()):
            out.append(f"    <tag k='{k}' v='{v}' />\n")
        out.append("  </way>\n")
        wid -= 1
    out.append("</osm>\n")
    p = tmp_path / name
    p.write_text("".join(out))
    if sidecar:
        (tmp_path / (name + ".axes.json")).write_text(json.dumps(
            {"anchor": list(ANCHOR), "ruleset": "icao"}))
    return p


def _square(half, cx=0.0, cy=0.0):
    return [(cx - half, cy - half), (cx + half, cy - half),
            (cx + half, cy + half), (cx - half, cy + half)]


_STRIP = ({"role": "graded_strip", "ref": "gap_fill_spine",
           "shapeID": "3190"}, _square(50.0))          # 100 x 100 m
_LOT = ({"role": "groundside_pavement", "ref": "groundside",
         "shapeID": "2813"}, _square(20.0))            # 40 x 40 m, inside


def test_the_area_reported_is_the_real_overlap(tmp_path):
    """HECA 3190-over-2813 in miniature: the lot stands wholly inside
    the strip, so the strip covers ALL of it — 1,600 m², 16 % of its
    own 10,000 m²."""
    p = _patch(tmp_path, "a.osm", [_STRIP, _LOT])
    r = ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert r["over_ways"] == 1 and r["on_ways"] == 1
    assert r["stacked"] == 1
    assert 1590.0 < r["area_m2"] < 1610.0
    row = r["rows"][0]
    assert row["shapeID"] == "3190"
    assert 9950.0 < row["own_area_m2"] < 10050.0
    assert 0.155 < row["over_frac"] < 0.165
    assert row["on"][0]["shapeID"] == "2813"


def test_the_ref_selector_is_exact(tmp_path):
    """A graded_strip of the WRONG ref (an adjacent_ground band) is not
    the population the ruling is about, whatever it covers."""
    band = ({"role": "graded_strip", "ref": "adjacent_ground",
             "shapeID": "9001"}, _square(50.0))
    p = _patch(tmp_path, "b.osm", [band, _LOT])
    r = ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert r["over_ways"] == 0
    assert r["stacked"] == 0 and r["area_m2"] == 0.0
    # ... and the same patch read for the band's own ref DOES see it.
    r2 = ROR.read(p, over="graded_strip:adjacent_ground",
                  on="groundside_pavement")
    assert r2["stacked"] == 1


def test_a_stack_under_the_floor_is_not_a_stack(tmp_path):
    """The floor is the emit rounding, not a law threshold: a 9 m²
    corner clip is not a face standing on a lot."""
    lot = ({"role": "groundside_pavement", "ref": "groundside",
            "shapeID": "2814"}, _square(2.0, cx=49.0, cy=49.0))
    p = _patch(tmp_path, "c.osm", [_STRIP, lot])
    assert ROR.read(p, over="graded_strip:gap_fill_spine",
                    on="groundside_pavement")["stacked"] == 1
    assert ROR.read(p, over="graded_strip:gap_fill_spine",
                    on="groundside_pavement",
                    min_area_m2=10.0)["stacked"] == 0


def test_it_prices_no_law(tmp_path):
    """MEASUREMENT ONLY: the report carries populations and areas — no
    row count, no violation, no grade.  Defect counts come from
    ``harness/census.py`` and nowhere else."""
    p = _patch(tmp_path, "d.osm", [_STRIP, _LOT])
    r = ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert set(r) == {"patch", "anchor", "frame", "over", "on", "min_area_m2",
                      "pad_m", "over_ways", "on_ways", "over_area_m2",
                      "stacked", "area_m2", "beyond", "beyond_ways",
                      "beyond_area_m2", "beyond_by_ref", "beyond_rows",
                      "sites", "rows"}
    for k in ("rows", "violations", "families", "grade"):
        assert k not in set(r) - {"rows"}


def test_a_patch_with_no_sidecar_is_refused(tmp_path):
    p = _patch(tmp_path, "e.osm", [_STRIP, _LOT], sidecar=False)
    with pytest.raises(SystemExit) as ei:
        ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert "sidecar" in str(ei.value)


def test_a_v2_sidecar_with_no_anchor_reads_in_the_node_mean_frame(tmp_path):
    """RULINGS 2026-09-13cs chip: every CURRENT sidecar is v2's, whose
    register carries NO top-level ``anchor`` by design (``emit/osm_adapter
    .SIDECAR_KEYS``; ``build_airport.py`` records ``anchor: None``), and
    the reader raised ``KeyError: 'anchor'`` on all of them.  v2's own
    frame is the mean of the vertices (``verify/frame.Patch.of``) — the
    same anchor-less frame ``_ll_to_m_factory`` builds — so the read goes
    through, names the frame, and the area is the v1 area to the metre
    (both frames are equirectangular about a point ~100 m apart; the
    ``cos(lat0)`` difference is parts per million on this fixture)."""
    p = _patch(tmp_path, "v2.osm", [_STRIP, _LOT])
    side = tmp_path / "v2.osm.axes.json"
    side.write_text(json.dumps({          # the v2 register, no anchor
        "ruleset": "icao", "axes": [], "stretches": [], "crown_drops": [],
        "terrace_joints": [], "basin_facilities": [], "road_bridge_decks": [],
        "design": {"rounds": 1}, "design_target": []}))
    assert "anchor" not in json.loads(side.read_text())
    r = ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert r["anchor"] is None
    assert r["frame"] == "mean-of-nodes"   # the string v2zonehole shipped (14bh)
    assert r["stacked"] == 1 and r["rows"][0]["shapeID"] == "3190"
    assert 1590.0 < r["area_m2"] < 1610.0
    # ... and a v1 sidecar still reads about ITS anchor.
    v1 = _patch(tmp_path, "v1.osm", [_STRIP, _LOT])
    r1 = ROR.read(v1, over="graded_strip:gap_fill_spine",
                  on="groundside_pavement")
    assert r1["frame"] == "sidecar anchor" and r1["anchor"] == list(ANCHOR)
    assert abs(r1["area_m2"] - r["area_m2"]) < 1.0


def test_beyond_reports_the_complement_at_arms_length(tmp_path):
    """``--pad``/``--beyond`` (Batch 4a): the OWNERSHIP read — how much
    of the OVER class lies FURTHER than M metres from the ON class.  The
    near ring reaches the padded union and is not far; the far one is,
    and its area is totalled under its own ref."""
    near = ({"role": "service_junction", "ref": "", "shapeID": "10"},
            _square(10.0, cx=70.0))              # 20 x 20 m, 10 m away
    far = ({"role": "service_junction", "ref": "", "shapeID": "11"},
           _square(10.0, cx=600.0))              # 570 m away
    p = _patch(tmp_path, "f.osm", [_STRIP, near, far])
    res = ROR.read(p, over="service_junction", on="graded_strip",
                   pad_m=25.0, beyond=True)
    assert res["over_ways"] == 2
    assert res["beyond_ways"] == 1
    assert res["beyond_rows"][0]["shapeID"] == "11"
    assert res["beyond_by_ref"]["(none)"]["ways"] == 1
    assert res["beyond_area_m2"] == pytest.approx(400.0, rel=0.02)
    # the SAME read with no pad puts both beyond (nothing overlaps)
    res0 = ROR.read(p, over="service_junction", on="graded_strip",
                    beyond=True)
    assert res0["beyond_ways"] == 2


def test_a_site_is_answered_in_the_over_classs_own_terms(tmp_path):
    """``--site LAT,LON``: which OVER way covers the named place, and how
    far that place is from the ON class — the acceptance read for a
    ruling stated at a coordinate."""
    far = ({"role": "service_junction", "ref": "", "shapeID": "11"},
           _square(10.0, cx=600.0))
    p = _patch(tmp_path, "g.osm", [_STRIP, far])
    res = ROR.read(p, over="service_junction", on="graded_strip",
                   pad_m=25.0, beyond=True, sites=[_ll(600.0, 0.0)])
    site = res["sites"][0]
    assert site["in_over_class"] is True
    assert site["shapeID"] == "11"
    assert site["dist_to_on_m"] == pytest.approx(550.0, rel=0.02)
    # a place in NO over way says so rather than guessing a nearest one
    res2 = ROR.read(p, over="service_junction", on="graded_strip",
                    pad_m=25.0, beyond=True, sites=[_ll(0.0, 0.0)])
    assert res2["sites"][0]["in_over_class"] is False


def test_the_tool_is_in_the_index():
    """RULINGS ``7e90032``: a tool absent from ``tools/INDEX.md`` is
    treated as absent, and every new tool lands with its index entry in
    the same commit."""
    index = _ROOT.parent / "tools" / "INDEX.md"
    if not index.exists():                      # a lane worktree mirror
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    assert "role_overlap_read.py" in index.read_text()


# ── --slivers and --hole-rings (RULINGS 2026-09-14g items 4/5, lane
#    ``v2slivers``): the two reads §41 (4) and the hole-suppression rule
#    are accepted on — which zone strips are too small or too thin to
#    carry a transition, and which emitted hole rings the faces inside
#    them already cover.

def test_the_inscribed_width_is_the_widest_place(tmp_path):
    """RULINGS 2026-09-14g item 4: ``2 A / P`` is a MEAN-width proxy that
    over-counted HECA's narrow zone faces 42 -> 153, so the read uses the
    MAXIMUM INSCRIBED CIRCLE's diameter — and it is the ENGINE's own
    number (``planar.overlay.inscribed_width_m``), never a second one."""
    from shapely.geometry import Polygon
    from auto_patch_v2.planar.overlay import inscribed_width_m as engine_w
    p = Polygon(_square(3.0)).union(Polygon([(3.0, -0.1), (15.0, -0.1),
                                             (15.0, 0.1), (3.0, 0.1)]))
    assert ROR.inscribed_width_m(p) == pytest.approx(engine_w(p), abs=1e-6)
    assert ROR.inscribed_width_m(p) == pytest.approx(6.0, abs=0.05)
    assert 2.0 * p.area / p.length < 3.0


def test_the_tool_constants_are_the_laws(tmp_path):
    """The three §41 (4) / item-5 numbers have ONE authority — the law
    table — and the tool's defaults mirror it (the ``ENCLOSED_MIN_FRAC``
    precedent, RULINGS 2026-09-13cs)."""
    from auto_patch_v2.law import Law
    t = Law.for_airport("CYXY").tables.emit.terrace
    assert ROR.STRIP_MIN_M2 == t.strip_min_m2
    assert ROR.STRIP_MIN_WIDTH_M == t.strip_min_width_m
    assert ROR.HOLE_COVER_EPS == t.hole_cover_eps


def test_the_sliver_read_names_the_strips_and_their_host(tmp_path):
    """HECA shape 1035 in miniature: a 2 m-wide zone face against a
    taxiway, with the pavement it borders longest named as its host — and
    a full-size band beside it that is NOT a sliver."""
    pav = ({"role": "cross_connector", "ref": "pav115", "shapeID": "221"},
           _square(50.0))
    sliver = ({"role": "graded_strip", "ref": "adjacent_ground:taxi:E:zone1#38",
               "shapeID": "1035"},
              [(50.0, -4.0), (58.0, -4.0), (58.0, -2.0), (50.0, -2.0)])
    band = ({"role": "graded_strip", "ref": "adjacent_ground:taxi:E:zone2#1",
             "shapeID": "1036"},
            [(50.0, 0.0), (70.0, 0.0), (70.0, 40.0), (50.0, 40.0)])
    p = _patch(tmp_path, "s.osm", [pav, sliver, band])
    r = ROR.strip_slivers(p)
    assert r["strip_ways"] == 2 and r["slivers"] == 1
    row = r["rows"][0]
    assert row["shapeID"] == "1035"
    assert row["area_m2"] == pytest.approx(16.0, rel=0.05)
    assert row["width_m"] == pytest.approx(2.0, abs=0.05)
    assert row["below_area"] and row["below_width"]
    assert row["host"] == "cross_connector:pav115"
    assert row["shared_edge_m"] == pytest.approx(2.0, rel=0.05)
    # the thresholds are the read's, both ways
    assert ROR.strip_slivers(p, area_min_m2=0.0, width_min_m=0.0)["slivers"] == 0


def test_the_hole_read_gives_the_cover_fraction_and_the_width(tmp_path):
    """RULINGS 2026-09-14g item 5: way -10231 shipped because the ring
    EDGES were not a superset though the inner faces covered 92 % of the
    area.  The read reports that fraction, the inscribed width, and the
    verdict each ring falls under."""
    host = ({"role": "cross_connector", "ref": "pav115", "shapeID": "221"},
            _square(50.0))
    inner = ({"role": "service_road", "ref": "route4", "shapeID": "222"},
             [(-9.0, -1.0), (9.0, -1.0), (9.0, 1.0), (-9.0, 1.0)])
    ring = ({"o4_feature": "gap_interior_ring", "shapeID": "221"},
            [(-10.0, -1.0), (10.0, -1.0), (10.0, 1.0), (-10.0, 1.0)])
    p = _patch(tmp_path, "h.osm", [host, inner, ring])
    r = ROR.hole_rings(p)
    assert r["rings"] == 1
    row = r["rows"][0]
    assert row["host"] == "cross_connector:pav115"
    assert row["cover_frac"] == pytest.approx(0.9, rel=0.05)
    assert row["width_m"] == pytest.approx(2.0, abs=0.05)
    assert row["verdict"] == "hairline"       # 2 m < strip_min_width_m
    assert r["hairline"] == 1 and r["covered"] == 0 and r["void"] == 0
    # a WIDE ring the inner face does not cover is a real void
    r2 = ROR.hole_rings(p, width_min_m=0.0)
    assert r2["rows"][0]["verdict"] == "void"
    # ... and at the cover the inner face actually gives, covered
    r3 = ROR.hole_rings(p, width_min_m=0.0, eps=0.2)
    assert r3["rows"][0]["verdict"] == "covered"


def test_the_three_reads_are_three_reads(tmp_path):
    """``--contains``, ``--slivers`` and ``--hole-rings`` are different
    questions in different frames: never two at once, never with
    ``--over`` / ``--on``."""
    p = _patch(tmp_path, "m.osm", [_STRIP, _LOT])
    assert ROR.main([str(p), "--slivers", "--hole-rings"]) == 2
    assert ROR.main([str(p), "--slivers", "--over", "graded_strip",
                     "--on", "groundside_pavement"]) == 2
    assert ROR.main([str(p), "--slivers"]) == 0
    assert ROR.main([str(p), "--hole-rings"]) == 0
