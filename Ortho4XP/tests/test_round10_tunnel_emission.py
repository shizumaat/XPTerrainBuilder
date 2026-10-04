"""Round 10 — tunnel emission: evidence before depth, walls never cover ramps.

Spec: ``docs/specs/round10-tunnel-emission-spec.md`` including its
2026-08-11 AMENDMENTS (A1-A8), which supersede several lines of the
frozen text after the implementer measured them against the code:

R10-1/A1/A6  NO PHYSICAL EVIDENCE, NO DEPTH — and THE COVER IS THE DECK.
          Per mapped way, below-grade geometry is emitted iff the DEM
          probe MEASURED a cut, OR (``layer < 0`` AND the probe could not
          measure at all), OR (tag evidence AND the way is NOT mostly
          under a building AND it IS meaningfully under airside
          pavement).  A1's first two disjuncts alone refused KCLT area
          1's four building-passthroughs (right) and all 8 of OTHH's
          mapped bores (wrong): a bare-earth DEM carries no cut under a
          man-made bore, so WHAT COVERS THE BORE is the discriminator —
          a building is a deck the road passes under at grade, an apron
          is a deck the road passes under in a bore.
          ``tunnel=building_passage`` never seeds SYNTHETIC depth.  Every
          refusal mints a ``tunnel_passthrough_findings`` record carrying
          both cover fractions, the layer value and the deciding reason.
R10-2/A4/A7(c)  A wall/roof/cap NEVER covers tunnel pavement, and ALL
          surviving pieces >= 0.5 m2 are kept — the largest-piece rule
          was a silent deletion of the other arcs.
          ``tunnel_unwalled_mouth`` is the reported backstop, EXEMPTING
          light-touch clusters (cap + roof, no side walls, by owner
          ruling 2026-07-17).
R10-3/A3/A5/A7(b)/A8  Facing portals across an open gap are DISTINCT
          entrances.  Dedup separates the three populations that share
          "two coincident walks" by station distance and outward walk
          direction: combined-entrance SIBLINGS (within
          portal_cluster_dist_m) and FACING pairs (opposing directions)
          are never dropped; only the LMML MERGE class (aligned, far
          apart, overlapping) is.
          A same-road facing pair is ONE lowered stretch — the gap emits
          a single roofless walled corridor at the pair's JOINT depth,
          and neither portal ramps to grade inside it.  Mouth depth is
          floored by ``BRIDGE_ROAD_CLEARANCE_M`` below the measured deck.
A2 struck the stationing bullet: mouths already anchor at mapped end
nodes, so there is no stationing test here — the 10 m acceptance is
carried by the dedup law and pinned by ``TestFacingBoresBothEmit``.
A7(a) ratified the ``_cut_measured`` / ``cut_detected`` evidence-vs-mode
split, pinned by ``tests/test_tunnel_dem_cut_portals.py``'s gate-off test
passing unmodified.

All fixtures are synthetic and headless (local-metre geometry built in
code, monkeypatched road loader + DEM sampler; no network, no X-Plane
install, nothing written) — the idiom of
``tests/test_tunnel_dem_cut_portals.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from auto_patch import config as _CFG  # noqa: E402

ANCHOR_LATITUDE = 35.2202
ANCHOR_LONGITUDE = -80.9459
ANCHOR = (ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
TILE_LATITUDE = 35
TILE_LONGITUDE = -81

AIRPORT_SURFACE_M = 100.0
#                                    crossing needs 5.1 m of clearance


def _flat_dem(_x, _y):
    return AIRPORT_SURFACE_M


def _refs(layout, *names) -> list:
    return [s for s in layout.shapes
            if getattr(s, "ref", "") in names]


# ══════════════════════════════════════════════════════════════════
# 4. R10-3 / A5 — mouth depth from clearance
# ══════════════════════════════════════════════════════════════════
class TestMouthDepthFromClearance:
    """A 1-arcsec DEM under-resolves a narrow cut; it may report DEEPER
    than the clearance the crossing requires, never shallower."""


    def test_the_clearance_constant_is_the_deck_one(self):
        # A5: the deck-clearance constant, never the 4.2 m acceptance
        # minimum and never a new knob.
        assert float(_CFG.BRIDGE_ROAD_CLEARANCE_M) == pytest.approx(5.1)
