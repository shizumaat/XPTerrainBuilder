"""THE APRON INTERIOR LATTICE — twins for §1b of
docs/specs/heca-apron-round2-spec.md (Amendment 1; legs pinned to their
precedents by Amendment 2).

§1's route-synthesis premise was REFUTED at HECA by measurement: apt.dat
nodes 462/470 are CONNECTED (560.6 m network path against 252.7 m
straight, a 2.2x detour) and neither is a leaf.  The routes go AROUND
the apron, so there is no feed gap — but the VOID is real: 10 nodeless
interiors, worst 175.4 m empty radius, and 247 m of the owner's cliff
line with no emitted station at all, dropping 6.06 m at ZERO census
rows.  That ground needs ANCHORS, not invented taxi geometry.

These twins pin the four legs:
  * the TRIGGER is the §2 measurement itself (one implementation);
  * the GEOMETRY is deterministic from the shape's own frame, clipped,
    and held off the ring so no lattice point interns into a ring bucket;
  * the LAW is the apron's own — edges priced through
    ``_grade_graph_edges``/``classify_pair``, never a private cap;
  * the CENSUS family prices the emitted membrane against the budget the
    SOLVE published, and an unmatched edge is a LOST MEASUREMENT.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


ANCHOR = (30.12, 31.40)


class _Shape:
    def __init__(self, polygon, role="apron", ref=""):
        self.polygon = polygon
        self.role = role
        self.ref = ref
        self.fan_ramp_zone = False
        self.lateral_cap = None


def _square(side):
    h = side / 2.0
    return Polygon([(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)])


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.anchor = ANCHOR

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


# ═════════════════════════════════════════════════════════════════════
# GEOMETRY: deterministic, clipped, off the ring
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# ROUND-3 §2: A LATTICE SEGMENT CLIPS TO ITS OWN APRON
#
# RULINGS 2026-08-26b item 1 (owner sim read): the lattice OVERLAPS
# other shapes.  Measured on /tmp/harness/HECA_20260826T213425.osm — 7
# of 970 segments leave the apron footprint, 89.5 m: 28.1 m through
# building shapeID 157, 23.5 + 8.2 m through junctions 2775/2776, the
# rest through graded strips.  ``_rows_and_columns`` joins consecutive
# grid POINTS with only per-POINT containment, so a segment between two
# lawful points bridges a hole or a concavity.
# ═════════════════════════════════════════════════════════════════════


def inspect_source(fn):
    import inspect
    return inspect.getsource(fn)


# ═════════════════════════════════════════════════════════════════════
# TRIGGER: the §2 measurement, not a second notion
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# THE FLAG
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# SOLVER ADMISSION (Amendment 2 clause 1)
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# THE LAW IS THE APRON'S OWN (Amendment 2 clause 1)
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# CENSUS FAMILY (Amendment 2 clause 3)
# ═════════════════════════════════════════════════════════════════════

def test_the_family_is_registered():
    """A check in ``run_checks`` that is not in ``LAW_FAMILIES`` fails
    ``test_harness``; registration is what makes omission impossible."""
    import check_grade as CG
    keys = [k for k, _t, _b in CG.LAW_FAMILIES]
    assert "apron_lattice_membrane" in keys
    bucket = {k: b for k, _t, b in CG.LAW_FAMILIES}
    assert bucket["apron_lattice_membrane"] == "within"


def test_the_sidecar_key_is_registered_as_LAW_input():
    import check_grade as CG
    assert CG.SIDECAR_LAW_KEYS["apron_lattice_edges"] == \
        "apron_lattice_edges_ll"
    assert "apron_lattice_edges" not in CG.SIDECAR_EVIDENCE_KEYS


def _parse_with_features(path):
    """``(nodes, ways, lattice_ways)`` — the lattice is an OPEN
    constrained breakline, so ``_parse_osm`` routes it to
    ``feature_out`` and never into ``ways``.  A ring-only population
    would find none of it."""
    import check_grade as CG
    feats: dict = {}
    nodes, ways = CG._parse_osm(Path(path), feature_out=feats)
    return nodes, ways, feats.get("apron_lattice", [])


def test_the_lattice_is_a_registered_open_feature_class():
    """Without this the emitted polylines are dropped by the ring filter
    and every lattice edge silently becomes a LOST MEASUREMENT."""
    import check_grade as CG
    assert "apron_lattice" in CG.ROLE_LESS_FEATURE_CLASSES


def _membrane_patch(tmp_path, name, alt_b, *, budget=0.50):
    """An emitted lattice polyline whose first two stations are 50 m
    apart, with a declared budget for that pair.  THREE nodes, because
    ``_parse_osm`` drops a way with fewer (its open-feature route is
    reached after that filter) — which is itself why a 2-station run
    lands in the LOST-MEASUREMENT count rather than passing silently."""
    lat0, lon0 = ANCHOR
    dlon = 50.0 / (111320.0 * math.cos(math.radians(lat0)))
    txt = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n",
           f"  <node id='-1' lat='{lat0:.9f}' lon='{lon0:.9f}'>\n"
           f"    <tag k='alt_abs' v='100.0'/>\n  </node>\n",
           f"  <node id='-2' lat='{lat0:.9f}' lon='{lon0 + dlon:.9f}'>\n"
           f"    <tag k='alt_abs' v='{alt_b}'/>\n  </node>\n",
           f"  <node id='-3' lat='{lat0:.9f}' lon='{lon0 + 2 * dlon:.9f}'>\n"
           f"    <tag k='alt_abs' v='{alt_b}'/>\n  </node>\n",
           "  <way id='-900'>\n    <nd ref='-1'/>\n    <nd ref='-2'/>\n"
           "    <nd ref='-3'/>\n"
           "    <tag k='o4_feature' v='apron_lattice'/>\n"
           "    <tag k='aeroway' v='apron'/>\n  </way>\n",
           "</osm>\n"]
    p = tmp_path / name
    p.write_text("".join(txt), encoding="utf-8", newline="")
    edges = [{"a": [lat0, lon0], "b": [lat0, lon0 + dlon],
              "budget_m": budget, "shapeID": 7}]
    (tmp_path / (name + ".axes.json")).write_text(json.dumps(
        {"anchor": list(ANCHOR), "ruleset": "icao",
         "apron_lattice_edges": edges}), encoding="utf-8", newline="")
    return p, edges


def test_a_membrane_pair_over_its_budget_is_a_row(tmp_path):
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "over.osm", 101.2, budget=0.50)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    rows, n_checked, n_unmatched = CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)
    assert n_checked == 1 and n_unmatched == 0
    assert len(rows) == 1
    assert rows[0].de_m == pytest.approx(1.2, abs=1e-6)


def test_a_membrane_pair_inside_its_budget_is_not(tmp_path):
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "under.osm", 100.4, budget=0.50)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    rows, n_checked, _u = CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)
    assert n_checked == 1 and rows == []


def test_the_budget_is_the_solvers_own_not_re_derived(tmp_path):
    """The same geometry judged against two declared budgets gives two
    answers — proof the family reads the published number."""
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "b1.osm", 100.8, budget=0.50)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    assert CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)[0]
    edges[0]["budget_m"] = 1.5
    assert CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)[0] == []


def test_an_unmatched_edge_is_a_LOST_MEASUREMENT_not_a_pass(tmp_path):
    """The emit decimators can remove a lattice vertex.  A published
    edge with no emitted endpoint must be COUNTED, never silently
    dropped into a clean report."""
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "gone.osm", 100.1)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    edges[0]["b"] = [ANCHOR[0] + 0.01, ANCHOR[1] + 0.01]   # far away
    rows, n_checked, n_unmatched = CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)
    assert (rows, n_checked, n_unmatched) == ([], 0, 1)


def test_no_published_edges_means_no_rows_and_no_claim(tmp_path):
    import check_grade as CG
    p, _e = _membrane_patch(tmp_path, "none.osm", 100.1)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    assert CG._check_apron_lattice_membrane(
        None, lat_ways, ways, nodes, to_m) == ([], 0, 0)


# ═════════════════════════════════════════════════════════════════════
# EMISSION (Amendment 2 clause 2)
# ═════════════════════════════════════════════════════════════════════


