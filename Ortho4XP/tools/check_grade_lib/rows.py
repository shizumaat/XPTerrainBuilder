"""The records every law family emits: ``Way`` (a parsed patch way) and
``Violation`` (one law row) — moved verbatim from ``check_grade.py``
(issue #857), which re-exports both."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple


@dataclass
class Way:
    wid: str
    role: str
    ref: str
    aeroway: str
    nids: List[str]               # closed ring (first repeats at end)
    elevs: List[Optional[float]]  # one per nid (closed-ring length)
    tags: Dict[str, str]
    #: CAP BY EDGE PORTION (owner RULINGS 2026-09-04t-2): for a way stamped
    #: ``o4_grade_law='apron'`` the LONG runs of its ring shared with an
    #: apron ring (``mark_apron_edge_portions``), each a frozenset of node
    #: ids; ``None`` until the marker runs (the whole-body 07-06 reading).
    apron_portion_runs: Optional[Tuple[FrozenSet[str], ...]] = None


@dataclass
class Violation:
    grade_pct: float       # %
    excess_pct: float      # %
    distance_m: float
    de_m: float
    way_a: Way
    way_b: Way
    pt_a: Tuple[float, float]
    pt_b: Tuple[float, float]
    elev_a: float
    elev_b: float
    # Geographic location of the violation (lat, lon), filled in by
    # run_checks so callers can point a user at the spot.  None until set.
    lat: Optional[float] = None
    lon: Optional[float] = None
    #: Set to the NAME of the adjudication that takes this row out of the
    #: acceptance count (currently only ``"disconnected_ring"``).  The row
    #: is still measured, still counted in its family and still printed —
    #: instruments report, the law adjudicates.
    out_of_scope: Optional[str] = None
    #: THE CAP THAT PRICED THIS ROW, in percent (owner ruling RULINGS
    #: 2026-08-21c, spec A1 §2a).  With the apron interior at 5 % and its
    #: movement surfaces at the strict cap, "how bad is this row" is not
    #: answerable from ``grade_pct`` alone — two rows at 3 % are a PASS and a
    #: FAIL depending on which law priced them.  Set by every within-shape
    #: row; ``None`` on families that carry no per-pair cap.
    cap_pct: Optional[float] = None
    #: WHICH READING PRICED IT when the family has more than one:
    #: ``"taxi_box"`` for a within-shape row priced as the short-chord
    #: BOX (RULINGS 2026-09-06q (1)); ``None`` for the family's default.
    reading: Optional[str] = None
    #: THE FACES ON EACH SIDE OF THE PAIR (owner RULINGS 2026-09-12aj (c)):
    #: the SENIOR role of every face carrying this endpoint's node, which
    #: for a vertex shared by an apron and a pad is the APRON — the face
    #: the law says owns the shared value.  Stamped by ``run_checks``;
    #: ``row_roles`` prefers them over the row's own two ways, which name
    #: the RING a pair was walked on and not what meets there.
    role_a: Optional[str] = None
    role_b: Optional[str] = None
    #: ``pt_a``/``pt_b`` are LAT/LON, not metres (the published-edge
    #: family): ``run_checks`` maps every other row's points from the
    #: engine metric back to the census frame and leaves these (#772)
    points_ll: bool = field(default=False, repr=False, compare=False)
