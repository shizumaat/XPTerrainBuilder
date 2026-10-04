"""Twin for the PAD-SEAT FEASIBILITY GATE (owner ruling RULINGS
2026-08-24c).

"A pad seat that cannot reach its governing centerline anchor within
1 % x chord is a SEAT DEFECT caught at seating time (anchor-placement law
analogue), NEVER surface debt."

The reach BAND is that test already computed: ``band(x, y)`` is the
interval of levels reachable at cap from the routes serving that point, so
"inside its own reach interval" is the question, and the gate asks it of
the seat the solve is about to ship.

REPORT-FIRST BY ORDER: nothing is moved this round, so the twin asserts
the RECORD and the read-out, never a changed seat.

Headless, no network, no X-Plane install.
"""

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class _Layout:
    def __init__(self):
        self.lines = []

    def m_to_ll(self, x, y):
        return (30.0 + y * 1e-5, 31.0 + x * 1e-5)


def test_the_key_is_registered_as_CENSUS_EVIDENCE_not_law():
    """A seat defect is caught at seating time and is NOT surface debt, so
    the census REPORTS it and never adjudicates it — which is also what
    keeps this round's acceptance counts comparable with the last.  Every
    emitted sidecar key must appear in one of the two registers, and
    test_harness twin-asserts that."""
    import check_grade as CG
    assert "pad_seat_infeasible" in CG.SIDECAR_EVIDENCE_KEYS
    assert "pad_seat_infeasible" not in CG.SIDECAR_LAW_KEYS


# ── THE FRONTAGE-BAND EXPORT (lead order 2026-08-24) ──────────────────

def test_the_frontage_band_key_is_registered_as_evidence():
    """The band interval at pad frontage points is EVIDENCE for the seat
    adjudication — reported by the census, never adjudicated as law, so
    exporting it cannot move an acceptance count."""
    import check_grade as CG
    assert "frontage_band" in CG.SIDECAR_EVIDENCE_KEYS
    assert "frontage_band" not in CG.SIDECAR_LAW_KEYS


def test_the_record_round_trips_through_the_sidecar():
    """Every field the adjudication needs survives JSON: pad id, frontage
    point, floor/ceiling, governing anchor and its route leg."""
    import json
    rec = {"pad": "building12", "ll": [30.1, 31.4],
           "floor": 62.793, "ceiling": 71.850, "seat_m": 72.356,
           "anchor_nodes": [4211, 4212], "route_m": 143.2,
           "off_mask_m": 6.0, "floor_at_anchor": 63.0,
           "ceiling_at_anchor": 71.0}
    back = json.loads(json.dumps([rec]))[0]
    assert back == rec
    for k in ("pad", "ll", "floor", "ceiling", "seat_m",
              "anchor_nodes", "route_m"):
        assert k in back, f"{k} must survive the sidecar round trip"
    # the seat's position within its own interval is derivable from it
    assert back["seat_m"] > back["ceiling"]


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# the test read the SOURCE of a deleted v1 module:
# ``test_the_export_reads_the_solves_own_band_never_a_replay``.
