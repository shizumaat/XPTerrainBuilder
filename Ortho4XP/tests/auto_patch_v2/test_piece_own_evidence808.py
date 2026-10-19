"""Issue #808 (owner 2026-10-19): the pavement beyond a §43 neck, and a
route-territory junction part no taxi centreline runs on, stand on their
OWN evidence — never the source polygon's stands, centrelines or name.

Synthetic, headless."""
from __future__ import annotations

from shapely.geometry import LineString, Polygon, box

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.evidence import Chain
from auto_patch_v2.classify.open_default import apron_evidence
from auto_patch_v2.classify.roles import _centreline_on
from auto_patch_v2.classify.sources import SourceRecord


def _src(**kw):
    base = dict(id="pav1", description="Apron", area_m2=1e5, width_m=100.0, road_m=0.0,
                osm_road_m=0.0, through_m=0.0, dead_ends=0, road_pieces=0, road_reach=0,
                aisle_m=0.0, taxi_m=500.0, startups=8, parking_cover=0.0,
                apron_cover=1.0, cls="open", reason="")
    base.update(kw)
    return SourceRecord(**base)


def test_the_source_evidence_never_reaches_past_a_neck():
    rules = load_rules()
    face: Polygon = box(0, 0, 100, 100)
    assert apron_evidence(face, _src(), {"n_taxi": 0}, None, rules) is not None
    assert apron_evidence(face, _src(), {"n_taxi": 0, "neck_new_apron": 1.0},
                          None, rules) is None
    # the piece's own centreline still counts
    assert apron_evidence(face, _src(), {"n_taxi": 1, "neck_new_apron": 1.0},
                          None, rules) is not None


def _chain(pts):
    return Chain(1, LineString(pts), ("A",), frozenset({"A"}), (False, False), False)


def test_a_centreline_on_the_part_or_beside_it():
    rules = load_rules()
    part = box(0, 0, 100, 20)
    assert _centreline_on(part, [_chain([(0, 10), (100, 10)])], rules)
    assert not _centreline_on(part, [_chain([(0, 40), (100, 40)])], rules)
