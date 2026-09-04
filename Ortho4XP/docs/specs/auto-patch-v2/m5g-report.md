# auto-patch-v2 — M5g report: post-merge integration (lane v2integ, 2026-09-05)

Lane `lane/v2integ` off main `7ddf3f5b` (the seven-airport re-census after
six merges: LEMD rc 1, KCLT 27/24, HECA 67/60). Every law value from the
TOML tables (no new key); no env reads; no v1 imports in v2 (the oracle
edit is `tools/check_grade.py`, twinned in `tests/test_harness.py`);
every touched v2 file ≤ 1,000 lines. Attempt cap: two per class, one
self-inflicted regression repaired (§3, KCLT) and one class STOPPED at the
cap and reported (§4, HECA).

## 0. Site first — the seven-airport table (this branch, `77595da9`)

All seven built through `build_airport.py ICAO --engine v2`, ledgered,
CONCURRENTLY (seven builds at once: the wall times are correctness-run
times, not timing-grade; the 04g/04l/05a columns were single builds).

| airport | tag / artifact key | build s | hard set | census adj / airside | before (main 7ddf3f5b) | 04g/04l/05a |
|---|---|---|---|---|---|---|
| CYXY | `CYXY_20260904T143940` / `b941733a7f28` | 5.5 | feasible | **0 / 0** | 0 / 0 | 0 / 0 |
| SPLP | `SPLP_20260904T143940` / `102573c064ec` | 9.1 | feasible | **0 / 0** | 0 / 0 | 0 / 0 |
| SPJC | `SPJC_20260904T143940` / `e36459427963` | 65.1 | feasible | **0 / 0** | 0 / 0 | 0 / 0 |
| OTHH | `OTHH_20260904T143940` / `6c90360b5d70` | 80.1 | feasible | **0 / 0** | 0 / 0 | 0 / 0 |
| LEMD | `LEMD_20260904T143940` / `3ec19f0f4b13`* | 187.6 | INFEASIBLE → tier 8 (structures) | **5 / 3** (mid_edge_step 2 + vertex_to_edge_step 1 on cross_connector; 2 groundside) | rc 1 (KeyError); stored patch 45/43 under the fixed reader → 5/3 | 0 / 0 (04l) |
| KCLT | `KCLT_20260904T143940` / `9cdcda3b702d`* | 204.0 | INFEASIBLE (IIS budget) → tier 8, 1 row | **3 / 0** (cross_shape service_road, groundside — the m5c lot residual) | 27 / 24 | 27 / 0 (05a) |
| HECA | `HECA_20260904T143940` / `8d09faabc4fa`* | 368.2 | INFEASIBLE (IIS budget) → tier 3 (apron) | **61 / 54** (within_shape 14, airside_no_step 20, mid_edge_step 11+6, cross_shape 3, frontage 3, vertex_to_edge 4) | 67 / 60 | 52 / 52 (04x, stored) |

\* the artifact-ledger keys of the FIRST closing round (`…T143118`); the
`…T143940` round's keys are in `tools/run_ledger.jsonl` on the branch.
CYXY/SPLP/SPJC/OTHH: 0/0 both rounds' code except the middle commit (§3).

## 1. LEMD — the crash (fixed) and the reader disagreement (fixed)

* **Cause of rc 1.** `verify/within.py` built its vertex map from face
  OUTER rings only, while stretches join through `Patch.ll` (every
  vertex) and the generator prices through `pm.vertices`. LEMD face 145
  (`cross_connector` pav84) has a gap-interior hole; taxi centreline
  `taxi660` enters it, so the stretch's endpoint 8521 is a HOLE-ring
  vertex → `KeyError`. Fix: the reader uses the frame's whole map
  (`Patch.xy`, `within.py:185`). Twin: `test_v2integ.py::
  test_a_stretch_ending_on_a_hole_ring_vertex_prices_without_a_key_error`.
* **The 40 within_shape rows the oracle then read (45/43).** Every one a
  pair of two vertices on a B-letter (3 %) stretch crossing an E/F
  (1.5 %) cross_connector (faces 9, 603, 604, 620, 992, 993). The v2
  generator and reader price them at 3 % (04t-3 / 04y: "a pair on one
  stretch holds that stretch's cap"); the oracle's PLANE-shape path
  passes `spine_caps=()` (grade_graph.py:3523) and reads the face cap.
  Fix in the oracle only: `check_grade._common_stretch_cap` — a body-cap
  pair whose two nodes both lie on one published stretch reads the
  looser common stretch's cap, never below the face's (`compose_pairs`'
  rule). Stored LEMD 45/43 → 5/3. Twin: `test_harness.py::
  test_a_rect_pair_on_a_looser_stretch_reads_that_stretchs_cap`.
* **Residual 5/3**: three `cross_connector|cross_connector` micro-steps
  (0.51–0.61 m over 0.05 m, two sites) + two groundside — present in the
  stored 04l-era patch too (the round-3 weld class, not this lane's).
  LEMD's hard set is INFEASIBLE on two `structures` pins (tunnel crest =
  DEM at `tunnel:-5938` vs basin rim = DEM at basin 22, Terminal 4
  green) → tier 8 soft, 62 rows, max 5.99 m. Not attributed (main's LEMD
  run crashed before its tier line; the class is not one of this lane's).

## 2. KCLT 24 airside — attribution and fix

Bisected with offline planar replays (no builds): the 24 rows are ONE
site, 35.20826/−80.93022, `strip_seam_tear` 2.02–2.17 m across 2.5–3.9 m
around pad `building26` (airside, inside taxiway F's zone 2, touching no
airside pavement). Caps-lane control `e5c4db91e012`: pad at 216.97, rim
shared with `service_road dsf:pol50`; main: pad at 214.83 (its DEM), rim
shared with strips only. `why KCLT --at 35.208548,-80.930355`: only the
pad's FLAT rows bind (dual 1.0 = the DEM preference). **Merge: round 3
(`57e1a854`, 04u "groundside never welds to a pad")** cut the road back;
the pad had been held at the lip only by that accidental weld. Two
defects in `constraints/zones.py` then let it float: (a) zone membership
read outer rings only — a pad inside the strip is a HOLE of the zone face,
so its rim was never a member; (b) `own_law` exempted every airside
value face, pads included. Fix: holes are members; a RIGID pad's rim is
banded — and because a pad is ONE level, only its rim vertex nearest a
lip carries the full band, every other rim vertex the floor (§3 for what
the first cut of this did). KCLT: 27/24 → **3/0** (the 24 gone; the 3
groundside are m5c's lot residual). Twins: `test_v2integ.py` (banded
rim; one ceiling per pad; hard set feasible on the fixture).

## 3. The self-inflicted regression (repaired)

The first cut (`5e32edc7`) banded EVERY pad's strip-side rim: a pad that
touches airside pavement sits at that level (03h/04r) and the band then
demanded the mandatory-down below the very lip — CYXY / SPLP / SPJC /
OTHH went hard-infeasible and RELAXED (27 / 2 / 53 / 57 rows; census
3/0/4/5). `77595da9`: only a DETACHED pad (no rim vertex on an airside
value face or a road) is levelled by the strip. All four back to
hard-feasible 0/0 (table). KCLT's hard set is still infeasible under the
final law (IIS budget-bound at 2.5 M rows, tier 8 demoted 1 row
≤ 0.2 m) where main's was feasible — the cost of the KCLT fix, reported,
not hidden: +120 s IIS budget in its build.

## 4. HECA +8 — attribution (confirmed) and the fix (mechanism in, STOPPED at the cap)

Offline replays in three throwaway worktrees (relax merge `31e5d126`,
caps merge `598a50d7`, HEAD) — no builds. The IIS on main is 4 rows:
`runway_profile` crown-transverse on face 39 (05L/23R) + reach bands at
vertices 3337/3338 (from the 05L pin 3339, 60.655) and 3692 (floor
61.49). The 3692 floor comes from the **23C threshold pin (114.3) over
the min-BUDGET route** — 1,175 m + 1,306 m of junction pav132's edge
along apron pav132 priced at **1 % (04t-2 portion caps)**: budget 52.8
vs ≥ 58.1 at the relax merge (floor 56.2, core FEASIBLE there). **Merge:
caps `598a50d7`.** The core is truly infeasible (53.6 m of drop over a
52.8 m budget); the last resort should relax the apron-portion pairs
("a slightly over-cap apron") but (i) the IIS named the reach BANDS
(the envelope) instead of the path rows, and (ii) the portion rows are
taxi-tier by FACE and never admitted. Fixes (`solve/relax.py`,
`solve/iis.py`): `envelope_free` sets the reach bands aside for the whole
last resort (diagnosis, spread, re-solve — the demotion pattern);
`_law_tier` owns a row by the tier of the LAW it states (an apron row on a
junction relaxes at the apron tier); `diagnose(minimal=False)` hands the
last resort the Farkas support (QuickXplain's O(k·log n) probes on a
2,500-row chain blow the budget). Twins: `test_v2integ.py` (three) +
`test_relax.py` unchanged. **Measured at HECA: the mechanism now finds
candidates in round 1 but the second certificate LP over 1.34 M rows
does not fit the remaining `[relaxation] iis_time_budget_s = 120`** —
offline: "round 2: the certificate LP hit the time limit"; in the
concurrent closing build even round 1. Result 61/54 (main 67/60; the
20 no-step + 14 apron rows are the tier-3 demotion). STOPPED at the
attempt cap; the next step is a spawner/owner call (§6).

## 5. Not done

* 04x-1 (QP size gate): not the cause anywhere this round (HECA's QP
  never ran; SPJC/OTHH fell to the PWL under the 20 s budget) — skipped.
* 04x-2 (oracle prices `relaxed_rows`): not needed for this table (no
  airport in the final round is in relaxed mode); the hook is the
  oracle's `out_of_scope` class mechanism — one afternoon, when a
  relaxed airport exists to measure it on.
* The five-airport sweep: not run (orchestrator's).
* Build-time impact: not timed (concurrent builds); the KCLT/HECA
  +120 s IIS budget burns are stated in §3/§4.

## 6. Open questions (≤ 3)

1. HECA: raise `[relaxation] iis_time_budget_s` (two certificate LPs at
   1.34 M rows ≈ 60–120 s each under load), or cache the certificate
   between rounds? Either is a table/mechanism call, not this lane's.
2. KCLT: the hard set is now infeasible under the detached-pad band
   (IIS budget-bound) — accept the tier-8 yield (1 row ≤ 0.2 m) or scope
   the band to the pad's nearest rim only when the pad is the ONLY
   strip occupant?
3. LEMD: two `structures` pins contradict (tunnel crest vs basin rim, one
   vertex) → tier 8 yields 5.99 m; whose is it (M4d/M6 structures)?
