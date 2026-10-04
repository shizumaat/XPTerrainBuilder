"""SERVICE-ROAD APRON SPINES — owner ruling RULINGS 2026-08-25h.

Spec: ``docs/specs/service-road-apron-spine-spec.md``.  The owner's model,
verbatim: *a truck route along/through an apron is a SPINE at the apron's
cap — like a taxiway, but 1 %.*

THE GAP THIS CLOSES, and why it is a gap and not a cap change.  Free-road
scoping (owner 2026-07-27 + R7a 2026-08-15) cuts a service centerline at
the stations where it stops being a free road and feeds only the FREE
stretches to the slice; the ruling says the rest "grades with the apron".
It did not — the contact stretches were DROPPED, so those roads reached
the grade graph with **no centerline at all**.  With nothing anchoring
them, the apron chain and the road family solved the same welded stations
independently, which is the alternating apron-vs-service sawtooth at the
owner's two back-edge ripple sites.

The five twins the spec names:
  (a) a through road inside an apron gets a 1 % profile and the apron
      chords to it;
  (b) the same road OUTSIDE the apron is unchanged (8 % / free road);
  (c) the reachability band's service exclusion is byte-identical — the
      airside-contamination regression class;
  (d) a shared apron/road edge emits one value series (no sawtooth);
  (e) the flag is default ON and OFF is byte-identical.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch import config as C                          # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# §1 RECOGNITION — the free-road predicate's own complement
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# §2 THE SPINE — (a) and (b)
# ══════════════════════════════════════════════════════════════════════

class _Shape:
    def __init__(self, role, polygon=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.node_altitudes = node_altitudes


class _Layout:
    canonical_points = None
    apt_taxi_centerlines: list = []

    def __init__(self, shapes=(), apron_spines=(), free=()):
        self.shapes = list(shapes)
        self._apron_spine_subsegments = list(apron_spines)
        self._slice_service_subsegments = list(free)


# ══════════════════════════════════════════════════════════════════════
# §3 NO ALTERNATION — (d)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# §e THE FLAG
# ══════════════════════════════════════════════════════════════════════

def test_e_the_flag_is_default_on():
    assert C.SERVICE_APRON_SPINE is True
    assert C.EDGE_ALTERNATION_TOL_M == 0.25


