"""OLS ROAD REGRADE — ``auto_patch.ols._emit_road_regrades``.

The corridor mask leaves a surface road on its own DEM embankment; across
an ADMITTED penetration island that preserves the very hill the cut law
removes, as a road-width causeway proud of the fan at grades far beyond
``SERVICE_ROAD_MAX_GRADE`` (measured SPJC 16R: 12.8 % / 13.2 %).  With
``config.OLS_ROAD_REGRADE_ENABLED`` such a road is regraded: a
grade-capped, cut-only profile along the mapped way, bounded by the
composed ceiling over admitted cells, blending back into the DEM on both
sides, emitted as corridor deck strips (ref ``ols.REF_ROAD``).

Headless and fixture-free, on the ``test_ols`` synthetic harness: one
runway, a knoll penetrating the north approach fan, and a monkeypatched
road network (``bridges._load_tunnel_road_network`` — the same seam the
skirt tests use, and the one both the corridor mask and the regrade read).

Pinned here:

* a road crossing the admitted island grows a deck; every deck edge obeys
  the service-road grade cap; along the spine the deck never rides above
  the DEM (cut-only) and its ends blend into the DEM;
* the deck never overlaps the banded cut pieces (mask/deck disjointness);
* the sub-gate off restores the embankment (no decks, bands unchanged);
* a REFUSED island (depth guard) grades no road;
* BLEND refusal: a way that ends mid-hill emits no deck;
* railways are out of scope.
"""
import math

import pytest

from auto_patch import config as apc
from auto_patch.config import SERVICE_ROAD_MAX_GRADE

RUNWAY_LEN_M = 3000.0            # code 4
BASE_TERRAIN_M = 5.0
LAT0, LON0 = -12.5, -77.5
TILE_LAT, TILE_LON = -13, -78
COS0 = math.cos(math.radians(LAT0))

#: The knoll in the north approach fan: centred on the extended
#: centreline, 300 m beyond the end (240 m past the 60 m setback, well
#: inside the fan), penetrating the ~11 m ceiling there by ~5 m.
KNOLL_X, KNOLL_Y = 0.0, RUNWAY_LEN_M + 300.0


class FakeDEM:
    """The read surface of ``O4_DEM_Utils.DEM`` the module uses."""


    def alt(self, node):
        x, y = node
        nmax = self.nxdem - 1
        x = min(max(float(x), self.x0), self.x1)
        y = min(max(float(y), self.y0), self.y1)
        j = int(round(x * nmax))
        i = int(round((1.0 - y) * nmax))
        return float(self.alt_dem[i, j])


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)
    monkeypatch.setattr(apc, "OLS_ROAD_REGRADE_ENABLED", True)


def _ring(shape):
    coords = list(shape.polygon.exterior.coords)[:-1]
    alts = shape.node_altitudes[:len(coords)]
    return coords, alts


# ══════════════════════════════════════════════════════════════════════
# HECA ROUND 5 ITEM 1 — THE DECK STANDS DOWN OVER THE RUNWAY STRIP
# (owner sim read of 1.0.265, spec
#  docs/specs/heca-round5-drainage-and-ramps-spec.md §Item 1:
#  "the runway family is aircraft-transit — NOTHING crosses it carrying
#   its own elevation authority … at a runway crossing the ols_road /
#   drainage corridor takes the RUNWAY's surface exactly … or STANDS
#   DOWN OVER THE STRIP.")
#
# The measured defect this twin encodes (HECA, arms r5base vs r5armB):
# the deck's profile bound is min(DEM, composed ceiling) and consults NO
# pavement, so beside runway 05C/23C the two ols_road halves rode
# 116.4-118.85 m over a runway surface at 109.3-111.2 — INSIDE the strip,
# where the adjacent_ground bands weld to them and tear (5.10 m over
# 0.19 m).  With O4_OLS_ROAD_REGRADE=0 both decks vanished and the strip
# beside them fell 115.90 -> 110.88: the deck is the author.
# ══════════════════════════════════════════════════════════════════════


class TestRunwayStripStandDown:

    def test_the_gate_is_default_on(self):
        assert apc.OLS_ROAD_RUNWAY_STANDDOWN is True


