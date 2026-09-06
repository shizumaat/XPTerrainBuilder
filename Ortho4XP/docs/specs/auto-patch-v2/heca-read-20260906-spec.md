# v2 — HECA read on 1.0.288: three unpriced laws (spec, 2026-09-06)

Owner: runway 05C/23C "flexed more than it should", edges "banking
steeply", building seats "deeply sunken or floating"; v1's HECA was
"very close to certified" in the sim. Measured on the tile patch
(engine 1.50.1730, 07:27) and v1's 2026-09-02 surface (RULINGS
2026-09-06b). Author: session (Fable). Implementer: lane `v2heca3`.

## 1. Measured

| | v2 1.0.288 | v1 |
|---|---|---|
| 05C/23C ridge max grade | 1.50 % | 0.81 % |
| max grade CHANGE per 100 m | **2.32 pp** | 0.71 pp |
| bow below the threshold line | 8.2 m | 9.3 m |
| graded strip 31–90 m off the ridge | ridge − z from +1.6 to **−5.6 m** (strip 5.6 m ABOVE the edge) | follows |
| runway halves' cross-fall | ≤ 1.53 % | ≤ 0.86 % |
| objects | 41 families seated as rigid units, deltas −35.6 … +0.4 m (133- and 199-member families) | untouched |

## 2. Law 1 — the runway VERTICAL CURVE is hard (§3.1.15/16)

`rulesets.toml [*.runway] max_grade_change` and `vertical_curve_k_m` are
declared and read by no generator. `constraints/runway_profile.py`
gains `runway_vertical_curve`: along each ridge chain, for consecutive
stations (i−1, i, i+1) with spacings d₁, d₂, the grade change
`|(z_{i+1} − z_i)/d₂ − (z_i − z_{i−1})/d₁| ≤ min(max_grade_change,
(d₁ + d₂)/2 / K)` — expressed as two `Linear` rows per interior station
(hard, runway tier). Stations are the ridge chain vertices (≈ 12 m at
HECA); the K bound per 12 m is 0.04 pp, which is the law's own
smoothness. `verify/runway.py` reads the same quantity as a DEFECT
(`runway_vertical_curve`). Twins: a synthetic ridge with a 1.5 % up /
1.5 % down zigzag → rows refuse it, a K-curve passes.

## 3. Law 2 — the graded strip is TIED to the runway edge

The strip's zone rows (`constraints/zones.py::zone_bands`) are DEM
corridors ("no deeper than"); nothing bounds a strip vertex ABOVE the
runway edge. `zones.toml` already carries the zone classes' transverse
caps (`[zone…] max_grade_change`/slopes — the lane states the exact
key; ICAO §3.4.15: graded portion of the strip transverse ≤ 2.5 %, code
3/4). New rows in `zones.py`: for every graded-strip vertex abeam a
runway-family edge (the existing `_nearest_edge` foot at lateral
distance d from the edge), `|z_v − z_foot| ≤ zone_transverse_cap × d`
BOTH directions (the strip may neither rise nor fall from the edge
faster than its cap), in the strip's tier (junior to the runway, senior
to the DEM band). Twin: a strip vertex 40 m off the edge can sit at
most 1.0 m above/below it; the reader in `verify/strips.py` reads the
same (`strip_transverse`).

## 4. Law 3 — a shared-anchor family seats as ONE unit only when its
members AGREE

`emit/rebake.py`: the family's members' deltas form coalitions within
`agreement_window_m`; today the largest coalition's median moves EVERY
member (133 members −35.6 m). RULED: members OUTSIDE the winning
coalition are seated by their OWN resource delta (one file, one delta —
I-4 holds per resource; a resource placed at several anchors takes its
own median) when their feet are witnessed on land, and reported per
member as `seated_apart`; a member whose own delta is under
`min_delta_m` stays. A family whose members all agree is unchanged
(OTHH). Twin: a family of three at one delta and one member 30 m off →
three move together, the fourth by its own delta. Provenance records
`seated_apart` with the coalition delta and the member's own.

## 5. Acceptance (ONE airport = HECA, on a branch from main a80f3875)

HECA `build_airport.py HECA --engine v2 --tile 30 31` ONCE (the seat is
post-mesh): 05C/23C grade change per 100 m ≤ K (quote max), bow, six
halves ≤ 1.53 %; strip vertices 31–90 m off each ridge within the zone
cap of the edge (quote max above/below); seat result: families split,
per-member deltas' spread, objects written; v2-verify by family (new
readers 0 rows), oracle adjudicated (withdrawn apart, bar 40); solve
wall. CYXY/OTHH `--base-arm` (v2-verify 0 must hold; OTHH's families
must still seat as one — quote unit:21). Build-time statement.
