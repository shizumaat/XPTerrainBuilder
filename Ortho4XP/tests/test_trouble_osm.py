"""THE TROUBLE MAP twin — ``tools/trouble_osm.py``.

It measures nothing, so what the twin protects is FIDELITY: the values it
writes are the census's own, the coordinates round-trip through the metre
frame exactly, the classes follow the documented precedence, and the file is
well-formed OSM with negative ids and a bounds JOSM can open.
"""
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_grade as cg
import trouble_osm as TO

from auto_patch.config import BUILDING_REACH_CORRIDOR_M
from auto_patch.grade_law import APRON_BODY_CHORD_MAX_M, APRON_INTERIOR_CAP

ANCHOR = (30.1089375, 31.434664815)


def _row(**kw):
    base = dict(family="within_shape", roles="apron|apron", side="airside",
                magnitude_m=1.0, grade_pct=1.2, cap_pct=1.0,
                distance_m=100.0, site_m=[[0.0, 0.0], [100.0, 0.0]],
                lat=30.11, lon=31.41, way_a="-10612", way_b="-10612")
    base.update(kw)
    return base


# ── the frame round-trips exactly ────────────────────────────────────

def test_the_metre_frame_is_the_censuss_own_inverse():
    """``m_to_ll_factory`` is the analytic inverse of
    ``check_grade._ll_to_m_factory`` about the same anchor — not an
    approximation, and not a proximity join."""
    fwd = cg._ll_to_m_factory({}, anchor=ANCHOR)
    inv = TO.m_to_ll_factory(ANCHOR)
    for lat, lon in ((30.118135, 31.410568), (30.09, 31.45), ANCHOR):
        x, y = fwd(lat, lon)
        la, lo = inv(x, y)
        assert abs(la - lat) < 1e-11 and abs(lo - lon) < 1e-11


def test_the_anchor_comes_from_the_sidecar_when_there_is_one():
    assert TO.sidecar_anchor({"anchor": list(ANCHOR)}, {}) == ANCHOR
    # and falls back to the node mean exactly as check_grade does
    got = TO.sidecar_anchor(None, {"a": (10.0, 20.0), "b": (12.0, 22.0)})
    assert got == pytest.approx((11.0, 21.0))


# ── classification: documented precedence, row fields only ───────────

def test_transverse_wins_over_everything():
    r = _row(family="transverse", distance_m=1.0)
    assert TO.classify(r, None, (30.11, 31.41)) == "transverse"


def test_a_long_chord_with_a_spine_baked_family_is_the_spine_door():
    r = _row(distance_m=APRON_BODY_CHORD_MAX_M + 1.0)
    assert TO.classify(r, "unified:apron:spine", None) == "long_spine_chord"
    assert TO.classify(r, "unified:apron", None) == "long_ring_edge"
    # absence of a baked family is never read as "not a spine"
    assert TO.classify(r, None, None) == "long_ring_edge"


def test_the_body_gate_is_the_laws_own_constant():
    assert TO.classify(_row(distance_m=APRON_BODY_CHORD_MAX_M),
                       None, None) != "long_ring_edge"
    assert TO.classify(_row(distance_m=APRON_BODY_CHORD_MAX_M + 0.01),
                       None, None) == "long_ring_edge"


def test_an_apron_row_over_five_percent_is_the_seat_docket():
    assert TO.classify(_row(distance_m=20.0, grade_pct=7.5),
                       None, None) == "frontage_gt5pct"


def test_a_short_strict_apron_row_is_a_frontage_chord():
    assert TO.classify(_row(distance_m=20.0), None, None) == "frontage_chord"
    # ...and a non-apron one is short_strict
    assert TO.classify(_row(distance_m=20.0, roles="junction|junction"),
                       None, None) == "short_strict"


def test_a_row_at_the_interior_cap_is_not_strict():
    r = _row(distance_m=20.0, roles="junction|junction",
             cap_pct=APRON_INTERIOR_CAP * 100.0, grade_pct=6.0)
    assert TO.classify(r, None, None) == "other"


def test_the_weld_cluster_needs_both_a_short_chord_and_the_disc():
    c = (-12.021394, -77.110990)
    near = _row(distance_m=1.3, lat=c[0], lon=c[1])
    assert TO.classify(near, None, c) == "weld_cluster"
    # a long chord in the same disc is NOT the cluster class
    assert TO.classify(_row(distance_m=800.0, lat=c[0], lon=c[1]),
                       None, c) == "long_ring_edge"
    # and no declared cluster means no cluster class anywhere
    assert TO.classify(near, None, None) != "weld_cluster"


def test_a_frontage_chord_beyond_the_building_reach_is_not_one():
    d = BUILDING_REACH_CORRIDOR_M + 1.0
    assert d > BUILDING_REACH_CORRIDOR_M
    # (still inside the body gate only if the gate is larger; guard the
    # intent rather than the arithmetic of two independent constants)
    if d <= APRON_BODY_CHORD_MAX_M:
        assert TO.classify(_row(distance_m=d), None, None) == "short_strict"


# ── the file ─────────────────────────────────────────────────────────

def _mini(tmp_path):
    """A two-way patch and a rows dump over it, in the sidecar's frame."""
    fwd = cg._ll_to_m_factory({}, anchor=ANCHOR)
    ring = [(30.1100, 31.4100), (30.1105, 31.4100),
            (30.1105, 31.4110), (30.1100, 31.4110)]
    nd = "".join(
        f"  <node id='-{i+1}' lat='{la}' lon='{lo}' alt_abs='10.0' />\n"
        for i, (la, lo) in enumerate(ring))
    refs = "".join(f"    <nd ref='-{i+1}' />\n" for i in range(len(ring)))
    patch = tmp_path / "MINI_auto.patch.osm"
    patch.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
        + nd +
        f"  <way id='-900'>\n{refs}    <nd ref='-1' />\n"
        "    <tag k='role' v='apron' />\n  </way>\n</osm>\n")
    a = fwd(*ring[0])
    b = fwd(*ring[2])
    rows = {"rows": [
        {"family": "within_shape", "roles": "apron|apron", "side": "airside",
         "magnitude_m": 9.59, "grade_pct": 1.13, "cap_pct": 1.0,
         "distance_m": 846.676, "site_m": [list(a), list(b)],
         "lat": ring[0][0], "lon": ring[0][1], "way_a": "-900",
         "way_b": "-900"},
        {"family": "within_shape", "roles": "apron|apron", "side": "groundside",
         "magnitude_m": 0.5, "grade_pct": 3.0, "cap_pct": None,
         "distance_m": 12.0, "site_m": [list(a), list(b)],
         "lat": ring[0][0], "lon": ring[0][1], "way_a": "-900",
         "way_b": "-900"},
    ]}
    rj = tmp_path / "rows.json"
    rj.write_text(json.dumps(rows))
    sc = tmp_path / "MINI_auto.patch.osm.axes.json"
    sc.write_text(json.dumps({
        "anchor": list(ANCHOR),
        "pair_caps": [[list(ring[0]), list(ring[2]), 8.4,
                       "unified:apron:spine"]],
        "apron_seniority": [[ring[0][0], ring[0][1], "senior"],
                            [ring[1][0], ring[1][1], "interior"]],
    }))
    return patch, rj


def test_the_file_is_well_formed_josm_osm(tmp_path):
    patch, rows = _mini(tmp_path)
    rep = TO.build(patch, rows, tmp_path / "out", icao="MINI")
    root = ET.parse(rep["path"]).getroot()
    assert root.tag == "osm" and root.get("version") == "0.6"
    assert root.find("bounds") is not None, "JOSM needs a <bounds> to zoom"
    node_ids = [int(e.get("id")) for e in root.findall("node")]
    way_ids = [int(e.get("id")) for e in root.findall("way")]
    assert node_ids and way_ids
    assert all(i < 0 for i in node_ids + way_ids), "JOSM wants negative ids"
    # OSM ids are PER TYPE, so uniqueness is asserted per type — a node -1
    # and a way -1 are different objects and JOSM reads them as such.
    assert len(set(node_ids)) == len(node_ids)
    assert len(set(way_ids)) == len(way_ids)
    for w in root.findall("way"):
        for nd in w.findall("nd"):
            assert int(nd.get("ref")) in node_ids, "dangling nd ref"


def test_every_value_written_is_the_censuss_own(tmp_path):
    patch, rows = _mini(tmp_path)
    rep = TO.build(patch, rows, tmp_path / "out", icao="MINI")
    root = ET.parse(rep["path"]).getroot()
    row_ways = [w for w in root.findall("way")
                if any(t.get("k") == "trouble" for t in w.findall("tag"))]
    tags = {t.get("k"): t.get("v")
            for t in row_ways[0].findall("tag")}
    src = json.loads(rows.read_text())["rows"][0]
    assert tags["family"] == src["family"]
    assert tags["roles"] == src["roles"]
    assert tags["side"] == src["side"]
    assert float(tags["de_m"]) == pytest.approx(src["magnitude_m"])
    assert float(tags["grade_pct"]) == pytest.approx(src["grade_pct"])
    assert float(tags["chord_m"]) == pytest.approx(src["distance_m"])
    assert tags["way_ref"] == src["way_a"]


def test_the_row_chord_lands_back_on_its_own_coordinates(tmp_path):
    """The whole point of the inverse: a row's ``site_m`` returns to the
    lat/lon it was projected from, so the chord sits on its pavement."""
    patch, rows = _mini(tmp_path)
    rep = TO.build(patch, rows, tmp_path / "out", icao="MINI")
    root = ET.parse(rep["path"]).getroot()
    by_id = {e.get("id"): e for e in root.findall("node")}
    w = [w for w in root.findall("way")
         if any(t.get("k") == "trouble" for t in w.findall("tag"))][0]
    a = by_id[w.findall("nd")[0].get("ref")]
    src = json.loads(rows.read_text())["rows"][0]
    inv = TO.m_to_ll_factory(ANCHOR)
    want = inv(*src["site_m"][0])
    assert float(a.get("lat")) == pytest.approx(want[0], abs=1e-9)
    assert float(a.get("lon")) == pytest.approx(want[1], abs=1e-9)


def test_the_baked_family_join_is_exact_and_reaches_the_tag(tmp_path):
    patch, rows = _mini(tmp_path)
    rep = TO.build(patch, rows, tmp_path / "out", icao="MINI")
    root = ET.parse(rep["path"]).getroot()
    got = [{t.get("k"): t.get("v") for t in w.findall("tag")}
           for w in root.findall("way")]
    row = [g for g in got if g.get("trouble") == "row"
           and g.get("side") == "airside"][0]
    assert row["baked_family"] == "unified:apron:spine"
    assert row["class"] == "long_spine_chord", (
        "an 846 m chord with a spine baked family is the SPINE door")


def test_context_rings_and_seniority_nodes_are_written(tmp_path):
    patch, rows = _mini(tmp_path)
    rep = TO.build(patch, rows, tmp_path / "out", icao="MINI")
    root = ET.parse(rep["path"]).getroot()
    ctx = [w for w in root.findall("way")
           if any(t.get("k") == "context" for t in w.findall("tag"))]
    assert ctx and len(ctx[0].findall("nd")) >= 4, "the apron ring is context"
    assert not any(t.get("k") in ("family", "class")
                   for t in ctx[0].findall("tag")), "context carries NO law"
    sen = [n for n in root.findall("node")
           if any(t.get("k") == "apron_seniority" for t in n.findall("tag"))]
    assert {t.get("v") for n in sen for t in n.findall("tag")
            if t.get("k") == "apron_seniority"} == {"senior", "interior"}
    assert rep["seniority_nodes"] == 2


def test_seniority_can_be_switched_off(tmp_path):
    patch, rows = _mini(tmp_path)
    rep = TO.build(patch, rows, tmp_path / "out", icao="MINI",
                   seniority=False)
    assert rep["seniority_nodes"] == 0


def test_groundside_rows_are_kept_only_for_airside_families(tmp_path):
    """The brief's own scoping — airside rows plus the groundside rows of the
    SAME families, so the file stays readable."""
    patch, rows = _mini(tmp_path)
    d = json.loads(rows.read_text())
    d["rows"].append({
        "family": "lateral_contiguity", "roles": "service_road|service_road",
        "side": "groundside", "magnitude_m": 0.1, "grade_pct": 9.0,
        "cap_pct": 8.0, "distance_m": 3.0,
        "site_m": [[0.0, 0.0], [3.0, 0.0]], "lat": 30.11, "lon": 31.41,
        "way_a": "-901", "way_b": "-901"})
    rows.write_text(json.dumps(d))
    rep = TO.build(patch, rows, tmp_path / "out", icao="MINI")
    assert rep["rows"] == 2, (
        "a groundside-only family must not reach the file")


# ── the VISUAL layer (--visual, 2026-08-24) ──────────────────────────

def _findings(tmp_path):
    """A findings file exercising every kind and one geometry-less row."""
    p = tmp_path / "F_visual_findings.json"
    p.write_text(json.dumps({
        "icao": "MINI",
        "generator": "twin",
        "arms": {"wk": "week-ago arm", "a5": "merged arm"},
        "findings": [
            {"cls": "owner_site", "kind": "node", "lat": 30.11, "lon": 31.41,
             "tags": {"owner": "NAMED IN SIM", "step_m": 2.56,
                      "changed": "this-round"}},
            {"cls": "interior_bump", "kind": "node", "lat": 30.12,
             "lon": 31.42, "tags": {"amp50_m": 2.1, "way_ref": "-10555"}},
            {"cls": "cliff_step", "kind": "edge", "lat": 30.13, "lon": 31.43,
             "lat2": 30.1301, "lon2": 31.4301, "tags": {"step_m": 9.13}},
            {"cls": "context_apron", "kind": "ring", "ll": [
                [30.14, 31.44], [30.1401, 31.44], [30.1401, 31.4401]],
             "tags": {"way_ref": "-10555", "role": "apron"}},
            {"cls": "road_break", "kind": "node", "tags": {"way_ref": "-1"}},
        ]}))
    return p


def test_visual_writes_every_kind_and_reports_the_geometryless(tmp_path):
    rep = TO.build_visual(_findings(tmp_path), tmp_path / "out")
    assert rep["icao"] == "MINI"
    assert rep["path"].endswith("MINI_visual.osm")
    assert rep["written"] == 4 and rep["skipped"] == 1, (
        "a finding with no geometry is REPORTED, never silently dropped")
    root = ET.parse(rep["path"]).getroot()
    assert root.find("bounds") is not None
    ways = root.findall("way")
    assert len(ways) == 2, "one edge + one ring"
    assert sorted(len(w.findall("nd")) for w in ways) == [2, 3]
    nid = {n.get("id") for n in root.findall("node")}
    assert all(d.get("ref") in nid for w in ways for d in w.findall("nd"))
    assert len({n.get("id") for n in root.findall("node")}) == \
        len(root.findall("node"))


def test_visual_writes_values_verbatim_and_stamps_the_arms(tmp_path):
    """It MEASURES NOTHING: every tag is the producer's own value, and the
    arms the numbers came from ride on every element."""
    rep = TO.build_visual(_findings(tmp_path), tmp_path / "out", icao="ZZZZ")
    assert rep["icao"] == "ZZZZ"
    root = ET.parse(rep["path"]).getroot()
    site = [n for n in root.findall("node")
            if any(t.get("k") == "owner" for t in n.findall("tag"))]
    assert len(site) == 1
    tags = {t.get("k"): t.get("v") for t in site[0].findall("tag")}
    assert tags["step_m"] == "2.56", "verbatim — never re-formatted"
    assert tags["class"] == "owner_site" and tags["trouble"] == "visual"
    assert tags["arm_wk"] == "week-ago arm" and tags["arm_a5"] == "merged arm"
    assert float(site[0].get("lat")) == 30.11
    for el in list(root.findall("node")) + list(root.findall("way")):
        kk = {t.get("k") for t in el.findall("tag")}
        if kk:
            assert "arm_wk" in kk and "source" in kk, (
                "no element may lose which arms its numbers came from")


def test_visual_classes_are_declared(tmp_path):
    rep = TO.build_visual(_findings(tmp_path), tmp_path / "out")
    assert set(rep["classes"]) <= set(TO.VISUAL_CLASSES)


def test_visual_cli_refuses_a_missing_findings_file(tmp_path):
    assert TO.main(["--visual", str(tmp_path / "nope.json"),
                    "--out", str(tmp_path / "out")]) == 2
    assert TO.main(["--out", str(tmp_path / "out")]) == 2, (
        "without --visual the row-map inputs are required")
