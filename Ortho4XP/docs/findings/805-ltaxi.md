# #805 — an end-around taxiway recognised by its shape (lane ltaxi, 2026-10-26)

Law: owner RULINGS 2026-10-16d (amends 2026-10-15e). Code: `src/auto_patch_v2/constraints/eat.py`.

## Attribution (dry recognition reads off captures, current main a6258a190)

`eat._recognise` read straight off the captures (no solve). KCLT is
`/Users/noah/XPTerrainBuilderData/.harness/frames/ltaxi/KCLT.pkl` (fresh). KDEN and
KATL are the registered `m5/KDEN.pkl` and `l1140/KATL.pkl`.

| airport / end | taxiway | route crossing | rect D | value | verdict today |
|---|---|---|---|---|---|
| KCLT 18C | T | 448.4 m | 426.7–469.8 m | 217.31 (end 226.20) | refused_near_crossing (< 457.2) |
| KDEN 34R | WB | 418.8 m | 392.0–418.9 m | 1621.94 (end 1631.91) | refused_near_crossing |
| KDEN 17R | ED | 414.8 m | 392.6–436.7 m | 1629.49 (end 1639.22) | refused_near_crossing |
| KATL 09L | M | 454.0 m | 454.4–479.4 m | 302.16 (end 310.59) | refused_near_crossing |
| KATL 08R | V (Victor) | 461.7 m | 430.5–482.5 m | 303.43 (end 312.12) | report-only (lidar) |

On all four airports, both endpoints of every one of these crossings reach the runway's
flank on their own side of the extended centreline (s ≤ 0) by taxi routes alone. In
other words, every one of these crossings wraps the end (scratch walk, same rule as below).

### Clause (2), the lidar witness, at KCLT

The KCLT inset is USGS 3DEP 1 m, project `NC_Phase_4_CentralWestNC_GEIGER_A16`,
publication date 2024-06-10. The metadata (`KCLT_usgs3dep.json`) carries **no acquisition
date**. The apt.dat carries no survey date either.

Along the 18C extended centreline the lidar reads:

| s from the 18C end | 0 | 320 | 400–500 (T) | 560 | 620 |
|---|---|---|---|---|---|
| lidar | 226.2 | 222.1 | 228.3–229.5 | 223.2 | 216.4 |

So T sits on a **ridge** in the lidar. It is not in a cut. The lidar along T's own route
falls 230.92 → 225.00 m over 245 m (node 8 → node 4), which is 2.4 %, above the 1.5 %
taxiway cap. The lidar does not show the excavation in the owner's photos, so it
predates it. Neither machine witness that 16d (2) names exists in the data for KCLT, so
(2b) is an owner question (`taxiways-ltaxi.md` Q805-1).

The same read at the other three sites (flanks at s = d_lo − 75 m and d_hi + 75 m):
- KDEN 34R: ridge (1631.3 vs 1628 / 1623).
- KDEN 17R: no cut (1639.5 vs 1638.2 / 1639.6).
- KATL 09L: flat (301.4 vs 301.4 / 300.8).
- KATL 08R Victor: 302.6–303.4 between 301 (runway side) and 306 (far side). That is one
  side lower, so it is not a cut.

## The rule as implemented

1. **THE WRAP (16d (1)).** A route crossing joins both sides when the following holds.
   From each endpoint of the crossing row-1202 edge, a walk over non-runway taxi routes
   that never leaves that endpoint's side of the extended centreline (strict sign of q)
   reaches a node with s ≤ 0, which is a node abeam the runway. Such a crossing is an
   end-around taxiway whatever its distance past the `min_crossing_m` gate, with two
   bounds:
   - it must lie beyond the runway's own safety area,
     `tables.runway_safety_area_length_m` (owner 15c (2); FAA 304.8 m at C–F). Inside the
     RSA the end-profile law governs the ground, and recognition must under-claim. A
     taxiway crossing at the end itself, like KCLT 18L D9 at 0.1 m, is not a wrap. This
     bound is law since owner RULINGS 2026-10-27x (Q805-2 ruled (a));
   - the existing far bound, `min(D_clear, max_crossing_m)`, still applies.

   A crossing at 1,500 ft or beyond stays an EAT as before (15e (1)). The value is the
   same law: `end_z + max(0, D − setback)·slope − tail`. For D < `D_clear` that gives the
   required depth max(0, tail − 0.025·D) under the 40:1 surface.
2. **THE CUT WITNESS (16d (2a)).** On a credible lidar inset, a recognised rect stays
   report-only (15e (2)) unless the lidar reads the rect's pavement **in a cut**.
   - **Pavement level:** the median production DEM over the rect's governed vertices.
   - **Flanks:** the DEM on the extended centreline at `d_lo − segment_gap_m` (toward
     the runway) and `d_hi + segment_gap_m` (past it).
   - **Cut:** both flanks stand above the pavement by more than `[cockpit] visual_m`
     (0.5 m, the depth a pilot can see).

   Where it reads a cut, the lidar is not a witness against the law, and the rect is
   judged as on a coarse DEM (clause 3, cut-only, then pinned).
3. **(2b) "the survey predates the airport data"** is NOT implemented. No date is
   readable (above).

Every verdict stays named in `RECTS`:
- new row keys `wraps` and `recognised_by` (`"distance"` / `"shape"`);
- new STATS `recognised_by_shape` and `lidar_cut_witness`;
- the near-crossing refusal reason now says whether the route wraps.

## Acceptance bar

- **Twins** (`tests/auto_patch_v2/test_v2eat.py`):
  - a 450 m crossing whose route joins both flanks is pinned on a coarse DEM;
  - the same crossing without the flank routes is refused (the existing twin stands);
  - a wrap inside the RSA is refused;
  - on lidar, a recognised wrap is report-only on flat ground and pinned where the
    lidar reads a cut.
- **Dry reads at KCLT / KDEN / KATL:** the four near crossings above become recognised.
  All four are on credible lidar with no cut, so they are report-only. There is no
  geometry change at any of the four, and KCLT T keeps the lidar level until Q805-1 is
  answered.
- **Closing build KCLT:** the patch body is unchanged against the control, and the
  census gains the report-only `eat_ceiling` rows at T.

## Measured (claude/ltaxi-805 on main bfca74e15)

- **Dry reads after the change:**
  - KCLT 18C T: recognised_by `shape`, report-only (lidar).
  - KDEN 34R WB and 17R ED: `shape`, report-only.
  - KATL 09L M: `shape`, report-only.
  - KATL 08R Victor: `distance`, report-only (unchanged).
  - LEMD 36L wraps at 70.8 m inside the safety area and stays refused. Without the
    safety-area bound it would be accepted and pinned at 581.63 against an end of 605.03
    (7 pins, coarse DEM).
  - HECA, OTHH, CYXY, SPLP, SPJC, KBOI, KMCI, KASE, LFPG, EGLL: no rect changes verdict.
  - Pins are unchanged at every airport read: 0 new.
- **Closing build:** `ltaxi805_KCLT`, harness, patch-only, 1172 s on a loaded machine,
  body_sha 8f662d4a31c4, solve optimal.
  - Census: law-true 12,681; adjudicated 4,929 (airside 3,149, groundside 1,762, mixed 18).
  - The `eat_ceiling` family carries 4 airside rows, 9.15–9.59 m, at taxiway T beyond the
    18C end (35.2315, -80.9533). These are the report-only rect: T stands about 9.6 m
    above its tail-clearance ceiling 217.31.
  - No pin is minted, so the surface is the one main builds. Body identity follows by
    construction (the constraint set is unchanged); no control build was paid.

## Round 2 — RULINGS 2026-10-27w (Q805-1 ruled (a)) and 2026-10-27x (Q805-2 ruled (a))

**The rule (27w).** On credible lidar, a recognised rect is pinned, not report-only,
where the survey breaks the taxiway grade law along the EAT's own route. The reading is
`eat._route_grade`: the steepest DEM grade between the ends of the crossing 1202 edges.
It is compared with `ruleset.taxi.longitudinal` for the edge's width class and adds no
new number. A grade over the cap means the survey predates the taxiway.

The cut witness (16d (2a)) stays; `eat._lidar_overruled` reads both. The road beside a
lowered EAT keeps its level, and the edge takes the existing bank and wall law.

**Dry reads (route grade):**
- KCLT 18C T: **2.42 %**, which is over 1.50 %, so T is **pinned at 217.31**;
- KDEN 34R: 1.45 % and 17R: 0.28 %, both report-only;
- KATL 09L: 0.92 % and 08R Victor: 0.55 %, both report-only.

**Replay, KCLT capture, same tree.** Control is round 1 (report-only); the arm is 27w.
- **T:** the 4 pinned vertices sit at **217.31**, the ceiling. The cross_connector
  between the runway end and T falls from 222.6–228.6 to 217.3–220.7.
  `eat_ceiling` goes 4 → 0.
- **The road:** the 49 service_road vertices within 250 m of T are unchanged
  (max |dz| 0.00), so the embankment road keeps its level.
- **The edge:** the graded strip between road and taxiway falls to 216.85–223.70.
  No new census row lies at T's edge.
- **Movement:** 103 vertices within 250 m and 220 within 250–600 m move more than
  0.05 m. Beyond 600 m, 22 vertices move, at most 0.08 m. Beyond 1.5 km nothing moves.
- **Census:** adjudicated 4,910 → 5,026:
  - `within_shape` airside +123;
  - `eat_ceiling` −4, `strip_longitudinal` −2, `airside_no_step` −1.

  All 123 new rows are at 35.2294, −80.953. They pair the EAT's own approach connector
  (`pav11` cross_connector / stub, about 220 m past the 18C end) with the runway end
  region 430–450 m away, at 1.92–2.02 % against the 1.5 % cap: 8.66 m over about 450 m.

  This is a law collision, not a solve residual. The EAT depth at D ≈ 450 m is 8.9 m,
  and a straight direct-distance pair inside one source polygon can lose only
  0.015 × 450 = 6.75 m. Every EAT nearer than depth / 0.015 (about 590 m here) collides
  with the within-shape reading wherever one source polygon spans the runway end and
  the EAT. The question goes to the master: exempt the ramp's direct pairs, or read
  them on the route the way the route-grade chord caps do.

**Closing build (round 2).** Build `ltaxi805b_KCLT`, made by the harness from ca9f11843, patch-only, 919 s. body_sha be9828f5b1dc, solve optimal. Frame registered as `ltaxi/ltaxi805b_KCLT.osm`.

Census against the round-1 build `ltaxi805_KCLT`: adjudicated 4,929 → 5,045.

| family (airside) | change |
|---|---|
| `within_shape` | +123 |
| `eat_ceiling` | −4 |
| `strip_longitudinal` | −2 |
| `airside_no_step` | −1 |

This is the replay's diff exactly. All 123 new rows sit at the EAT's approach connector, 35.2294, −80.953. No row changed anywhere else.

## Round 3 — RULINGS 2026-10-28f (owner Q210 (a)): taxiway slope along the route (lane l805r)

**Readers audited.**
- **Solver:** the taxi family has no pair rows. The chain (`constraints/taxi.taxi_chain`: centreline edges, lateral hops, crossings) implies every route budget. Nothing judges T's connector straight across.
- **Verify:** `verify/within.within_shape` reads every pair of a taxi-family ring on its published `taxi_route_pairs` budget (05ab). This already obeys 28f.
- **Census:** this was the straight-across reader. `harness/census.stamp_withdrawn_taxi_chords` withdrew a taxi chord only when the SENIOR face at both ends was taxi-family (`row_roles`, 12aj (c)). T's approach connector `pav11` ends on vertices the runway owns, so its chords read `cross_connector|runway` and stayed adjudicated. These are the 123 rows: 8.66 m over a 450 m chord (1.92 %) against a published route of about 903 m with a 13.5 m budget.

**Change.** `census.read_taxi_ring_route` handles a chord of 30 m or more on a taxi-family RING that has a non-taxi face at an end. It reads the chord on the published route budget, joining the pair by identity key through `Violation.ll_a/ll_b`, which `_check_within_shape` now stamps. This is verify's reading of the same pair:
- **within the budget, or a null route:** stamped `withdrawn_law_05aa`;
- **over the budget:** the row stays and is restated on the route (`reading = taxi_route`);
- **unpublished** (the route equals the chord): the chord row stays.

The both-taxi population keeps its 05aa blanket stamp, unchanged.

**KCLT census, same patches, old census → 28f census:**
- **round-1 build** `ltaxi805_KCLT`: adjudicated 4,929 → 3,123;
- **round-2 build** `ltaxi805b_KCLT`: adjudicated 5,045 → 3,116.

Every change is `within_shape` on taxi rings that end on the runway:
- round 1: 976 `primary_parallel|runway`, 447 `cross_connector|runway` and 383 `runway|stub` rows withdrawn;
- 282 rows stay, over their route and restated on it (185 / 24 / 73).

Under the 28f census, round 1 → round 2 is `eat_ceiling` −4, `strip_longitudinal` −2, `airside_no_step` −1 and `drainage_minimum` −7. **`within_shape` +0:** the 123 rows at T are gone.

**Closing build** `l805r_KCLT` (merge of origin/main 478b4489a): harness, patch-only, 1,828 s, solve optimal. Its body be9828f5b1dc is identical to `ltaxi805b_KCLT`, so the census change is the only difference. Census: adjudicated 3,116, airside for acceptance 1,354, `pav11` `within_shape` 0.

**Not done (finding).** The both-taxi population is still withdrawn wholesale. On the round-2 build, about 80 of those chords are over even their published route, or unpublished and over their chord. The verify reports them; the census does not. Unifying the two populations is a census-count change for the master to schedule.
