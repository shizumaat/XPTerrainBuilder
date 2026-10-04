"""THE GAP-BRIDGING SPINE — twins for §1 of
docs/specs/heca-apron-round2-spec.md.

The motivating measurement: HECA's apt.dat taxi-route graph has a FEED
GAP — taxiway J ends at node 462, the next route starts at node 470
254 m north, no 1202 edge between them and no OSM way there.  Both ends
sit on ONE continuous piece of apron pavement, but the global slice cuts
along CENTERLINES, so the emitted apron carries a 215 x 430 m region
with ZERO interior vertices.

Spec §1.4's twin, verbatim: a synthetic two-route apron with a 250 m gap
gives one bridge, slice vertices in the void and priced chords; a gap
over 300 m gives no bridge; non-apron pavement between gives no bridge.

Headless, no network, no X-Plane install.
"""
from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import LineString, Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.apt_dat_reader import TaxiCenterline    # noqa: E402


def _cl(pts, size="C", service=False):
    return TaxiCenterline(line=LineString(pts),
                          seg_sizes=[size] * (len(pts) - 1),
                          is_service=service, name="route")


def _apron(width=400.0, y0=-200.0, y1=400.0):
    """One continuous rectangle of apron pavement spanning both routes
    and the gap between them."""
    h = width / 2.0
    return Polygon([(-h, y0), (h, y0), (h, y1), (-h, y1), (-h, y0)])


# ═════════════════════════════════════════════════════════════════════
# §1.4 twin 1 — a 250 m gap gives ONE bridge
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# Determinism: the tie rule is the spec's (lower node id)
# ═════════════════════════════════════════════════════════════════════


class _Airport:
    def __init__(self, nodes):
        self.taxi_nodes = nodes


# ═════════════════════════════════════════════════════════════════════
# The bridge is a FIRST-CLASS centerline (§1.2), and the flag (§1.3)
# ═════════════════════════════════════════════════════════════════════

class _Layout:
    def __init__(self, centerlines):
        self.apt_taxi_centerlines = list(centerlines)

    def m_to_ll(self, x, y):
        return (30.12 + y / 111_320.0, 31.40 + x / 96_000.0)


# ══════════════════════════════════════════════════════════════════════
# THE STAND-DOWN — twins for gap-spine-bridge-stand-down-spec
# Amendment 1 (owner ruling 2026-08-27 "2").
#
# The adjudication is INTERVENTIONAL: the post-solve band law refusing a
# build in which bridges were minted triggers ONE re-run with them stood
# down, and the two outcomes rule.  These drive
# ``pipeline.gap_spine_stand_down_solve`` directly — it takes its two
# expensive halves as callables precisely so the law is testable without
# a build, and it is the ONE implementation the pipeline calls.
# ══════════════════════════════════════════════════════════════════════


def test_the_stand_down_key_is_a_registered_evidence_key():
    """A stand-down is EVIDENCE, counted by the census and re-judged by
    nobody — and the sidecar contract requires it to be classified."""
    import check_grade as cg
    assert "gap_spine_stand_down" in cg.SIDECAR_EVIDENCE_KEYS
    assert "gap_spine_stand_down" not in cg.SIDECAR_LAW_KEYS
