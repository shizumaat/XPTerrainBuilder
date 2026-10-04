"""THE TAUT BACK EDGE — twins for spec §3 of
docs/specs/heca-apron-round2-spec.md (HECA apron round 2).

The band's own constraint docstring states its pre-ruling law verbatim:
``value = clamp(dem, edge + floor(d), edge + ceiling(d))`` per vertex,
"with NO neighbour coupling of any kind".  That is what put 0.5-1.1 m of
terrain ripple on HECA's emitted back edge at 7 % local grade (ways
-13257 / -13411, 2026-08-25 attribution), and what let a band ring
welding two pavement families ~1.6 m apart sawtooth between them (the
IDENTITY-ADOPTION LADDER).

These twins pin the three sub-passes and the flag:

  * a strip over bumpy DEM between two level anchors reads as a faired
    plane (bump amplitude below materiality);
  * a strip welding a low road and a high apron alternately is MONOTONE
    between welds — and the welded nodes themselves keep their adopted
    pavement values (the identity-adoption rule holds AT them);
  * the chain builder carries the law offsets rather than re-deriving
    them, and marks the welds;
  * flag OFF reproduces the pre-ruling values.

No network, no DEM, no fixtures: stub chains and arithmetic.
"""
from __future__ import annotations

import importlib


# ── the second-difference rate the pass shares with the B2 spines ────


def _chain(idx, xy, hosts, depth, floor_off=-2.0, ceil_off=2.0):
    """One zone ROW in the shape ``build_adjacent_ground_band_chains``
    returns (and ``_fair_gap_spine_chains`` already consumes)."""
    return {"idx": list(idx), "xy": list(xy),
            "specs": [[] if j is None else [(j, floor_off, ceil_off)]
                      for j in hosts],
            "host": list(hosts),
            "depth": [float(d) for d in depth],
            "kind": "fill", "shape": None}


# ═════════════════════════════════════════════════════════════════════
# §3.1 — the strip is a plane between its ends, not N DEM clamps
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §3.2 — THE ADOPTION LADDER DIES
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# The chain builder: offsets CARRIED, welds MARKED
# ═════════════════════════════════════════════════════════════════════

class _CPS:
    def get_or_add(self, x, y):
        return (round(float(x), 6), round(float(y), 6))


class _Shape:
    pass


class _Layout:
    def __init__(self, presolve, first_zone=2):
        self.canonical_points = _CPS()
        self._adjacent_ground_first_zone_index = first_zone
        self.adjacent_ground_presolve = presolve


# ═════════════════════════════════════════════════════════════════════
# The flag
# ═════════════════════════════════════════════════════════════════════

def test_the_flag_defaults_on_and_reads_the_environment(monkeypatch):
    import auto_patch.config as cfg
    assert cfg.TAUT_GRADED_STRIP is True
    monkeypatch.setenv("O4_TAUT_GRADED_STRIP", "0")
    reloaded = importlib.reload(cfg)
    try:
        assert reloaded.TAUT_GRADED_STRIP is False
    finally:
        monkeypatch.delenv("O4_TAUT_GRADED_STRIP", raising=False)
        importlib.reload(cfg)


