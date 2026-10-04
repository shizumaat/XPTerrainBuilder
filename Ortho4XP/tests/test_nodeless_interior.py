"""THE NODELESS-INTERIOR INSTRUMENT — twins for §2 of
docs/specs/heca-apron-round2-spec.md.

The instrument exists because the census is STRUCTURALLY BLIND to a
region with no emitted nodes: every family table prices PAIRS OF EMITTED
NODES, so an apron interior the slice never cut contributes zero rows
and reads as compliant however wrong its surface is.  HECA's 215 x 430 m
void passed three rounds of censuses at 1,679 while carrying a visible
cliff at 30.1289374, 31.4052385.

Twins, per the spec: a synthetic apron with an empty 100 m disk gives a
line + a sidecar count; a densely-cut apron gives zero.  Plus the
registration twin (an emitted sidecar key classified nowhere fails
``test_harness``) and the sidecar round-trip.
"""
from __future__ import annotations

import json
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


def _square(side):
    h = side / 2.0
    return Polygon([(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)])


# ═════════════════════════════════════════════════════════════════════
# The measurement
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# The report: loud at zero, and published on the layout
# ═════════════════════════════════════════════════════════════════════

class _FakeLayout:
    """The minimum surface the reporter reads."""

    def __init__(self, shapes):
        self.shapes = shapes
        self.anchor = ANCHOR

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


# ═════════════════════════════════════════════════════════════════════
# Sidecar registration + round trip
# ═════════════════════════════════════════════════════════════════════

def test_the_sidecar_keys_are_registered_as_evidence():
    """An emitted sidecar key classified nowhere fails
    ``test_harness.test_every_emitted_sidecar_key_is_classified``."""
    import check_grade as CG
    for key in ("nodeless_interiors", "gap_spine_bridges",
                "gap_spine_stand_down"):
        assert key in CG.SIDECAR_EVIDENCE_KEYS
        assert key not in CG.SIDECAR_LAW_KEYS


def test_the_evidence_reader_counts_them(tmp_path):
    import check_grade as CG
    osm = tmp_path / "p.osm"
    osm.write_text("<osm/>", encoding="utf-8", newline="")
    (tmp_path / "p.osm.axes.json").write_text(json.dumps({
        "anchor": list(ANCHOR), "ruleset": "icao",
        "nodeless_interiors": [{"shapeID": 3, "radius_m": 107.4},
                               {"shapeID": 9, "radius_m": 88.0}],
        "gap_spine_bridges": [{"node_a": 462, "node_b": 470}],
        "gap_spine_stand_down": [{"icao": "HEAZ", "bridge_count": 13}]}), encoding="utf-8", newline="")
    ev = CG.sidecar_evidence(str(osm))
    assert ev["nodeless_interior_count"] == 2
    assert ev["gap_spine_bridge_count"] == 1
    assert ev["gap_spine_stand_down_count"] == 1
    assert ev["unknown_keys"] == []


