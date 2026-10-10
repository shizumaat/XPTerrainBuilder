# padreview2 summary — second review of §56 on PR #463 (Fable `padreview2`, 2026-10-08)

Spec: §56 (11) (`tools/docq.py spec '§56'`), appended in place. Read on the lane builds `/tmp/harness/p60_*`
(frames `frames/pads60/`) against main's `swg_*` (main `5fbef58a` = `29133c54` in engine code), and on SEVEN
INTERVENTION REPLAYS of the main-era captures `<scratch>/sweepwalls/base/{KCLT,KASE}.pkl` (`--from classify`,
lane code `0a4b93db`, ONE law group disarmed per arm; scripts and outputs in
`docs/briefs/padspec-scratch/padreview2/`, arm patches registered `frames.py list KCLT|KASE` lane `padreview2`).
The frame is exact both ways: main's replay of the capture == `swg_*` (0 movers, sweepwalls `arm_Z2`) and the
lane's full arm `F` == `p60_*` (0 movers at 0.02 m, KCLT and KASE). Instrument: `airside_value_delta --tol 0.02`,
SOLVE-OWNED frame (the lane's "3,044" counted strip/junction roles in another frame; this table is one frame).

## A. Airside movers vs main — the channel ladder (intervention, not correlation)

| arm (what is ON) | KCLT movers | taxi / worst | apron / worst | strip / worst | runway | > 0.3 m (far-field) | taxi-tier `hard_conflict` | pad-tier |
|---|---|---|---|---|---|---|---|---|
| main `swg` | — | | | | | | **19** | 4 |
| `OA0` collar deletion + 4F + F1b + F2 + hygiene (outline and absorb keys 0) | **1,531** | 261 / 0.61 | 810 / 0.23 | 460 / 0.58 | 0 | 16 (16) | **19** | 28 |
| `O0` = `OA0` + absorb key on | 1,531 (0 vs `OA0`: with the close at 0 NOTHING is absorbed) | | | | | | 19 | 28 |
| `A0` outline on, absorb off | 2,399 | 439 / 0.67 | 1,398 / 0.87 | 560 / 0.96 | **2 / 0.05** | 220 (155) | 59 | 101 |
| `C0` close + holes on, chord off, absorb on | 3,015 | 514 / 0.53 | 1,782 / 1.15 | 719 / 0.93 | 0 | 223 (171) | 56 | 499 |
| `F` everything (= `p60_KCLT`) | **2,643** | 527 / 0.67 | 1,466 / 0.92 | 650 / 0.98 | 0 | **226 (162)** | **57** | 102 |
| 4F alone (lane's pre-F4 → F4, `pads60/kclt_*`) | 456 | 14 / 0.55 | 48 / 0.29 | 394 / 0.58 | 0 | 19 (19) | 57 = 57 | |

KASE: `OA0` = `O0` **107** (apron 52 / 0.34, taxi 36 / 0.33, strip 19 / 0.23, runway 0; pad-tier 59, main 68);
`F` = `A0` **103** (apron 45 / 0.40, taxi 33 / 0.31, strip 24 / 0.25, **runway 1 at 0.03 m** at 39.22186,
−106.86917 — runway 15/33's edge vertex shared with its strip zone and `small_roads:-420`; 2363.68 → 2363.65;
pad-tier 12); `C0` 129 (worst 0.32, runway **0**, pad-tier 45). HECA build vs main (no ladder): 4,507 (taxi
1,943 / 0.40, strip 1,030 / 1.05, apron 1,534 / 1.05), taxi-tier 72 → 73, pad-tier 27 → 121. OTHH: 0.

**The rows.** The channel that moves airside is the OUTLINE (rule 2b), and it moves it through the pads' WELD
ROW POPULATION — `platforms[].welded` (the hard two-way hold rows, 02ah) — not through area: KCLT total welded
`O0` 1,437 → `F` 1,220 → `C0` 3,678; KASE `building2` 33 → **9** (`F`) / 48 (`C0`) on a 72 m² footprint change
(outline 73 → 26 vertices, chord residue 44.8 m²), `building1` 7 → 6 / 28. The datum is the median of those
contacts, so it re-chooses (KASE `building2` 2363.141 → 2362.906, `building1` −0.139; KCLT `building15`
−0.946 with welded 15 → 3, `building83` +0.294 with 13 → 145), the apron body planes conform (30f) and the
strips, connectors and road ribbons follow — `pav118` −0.67 m 90 m from any pad; `small_roads:-30712` −1.69 m
at 35.22546, −80.93240 taking its bordering strip's level (10-03b). The 38 new taxi-tier rows (0 gone) are all
`rulesets.common.pavement_max_grade ceiling` (+3 `road_max_grade` fallbacks) between a road ribbon / pol and
a taxi strip zone at four sites: `small_roads:-30712` / `face:1450` 1.67 m (35.22547, −80.93251); `dsf:pol35` /
`face:955` 1.05 m (35.20423, −80.94002, beside a tunnel ramp; the road rose 2.0 m); `small_roads:-7017`
(35.20903, −80.93103); `building16`/`17` plateau (35.20740, −80.94260). The same 38 stand in `C0` (chord off),
NONE in `OA0`/`O0`; so at KCLT the CLOSE + holes are the driver (welded triples, pad-tier 499), at KASE the
CHORD is (welded thirds, the runway vertex) — one mechanism, two faces.

**Verdicts.** (1) Collar deletion + 4F + F1b + F2 (`OA0`): **(ii)** — the measured floor class: far-field
junction / stub / strip vertices ≤ 0.61 m (KCLT) / 0.34 (KASE), 16 and 2 over 0.3 m, NO new taxi-tier row,
runway 0; the HECA null change (231–262 vertices to 0.57 m) is the same class. Pad-tier 4 → 28 is lawful: the
released welds sit on the pad tier. (2) Absorption: **(i)**, and zero on its own — with the outline off it
absorbs nothing at all (finding: `outline_close_m = 0` disarms `absorb_near_roads` too, an unstated coupling);
with the outline on, `A0` ↔ `F` differ by 1,582 vertices through the same datum path (the 21 KCLT roads into 9
pads). (3) Outline: **(i) in kind, (iii) in effect** — it is 30f's own picture (the pad leads, the apron
conforms) but it re-populates the frontage weld rows and breaks 30f's two letters: "taxiway and apron caps are
never exceeded" (38 taxi-tier hard rows relaxed to 1.67 m at KCLT; 19 → 57 is **(iii)**) and "the runway never
moves" (KASE 0.03 m). §56 (2) 1's "AIRSIDE: unchanged — the apron's own rim vertices become the pad's" does
not hold as a row population. RULE (§56 (11) R-W): the FRONTAGE IS NOT SIMPLIFIED — a rule-2 outline vertex
within the identity spacing of an airside cell's rim is PINNED through rule 2b (the closing fills no
re-entrant whose mouth lies on the frontage, the straightening drops no pinned vertex); the owner's straight
chords are the groundside and road sides, as (2) 8 already says. Acceptance: per pad `welded` = the `OA0`
arm's; taxi-tier `hard_conflict` = main's ± 3; runway 0 at every airport; KASE `building2` datum within 0.05 m
of `OA0`'s.

**Instrument.** Mover counts at 0.02 m are not an acceptance instrument for a pad-shape change: the floor
(`OA0`) is 1,531 at KCLT and the ±0.5 m null class is diffuse. Read instead, per airport: (a) runway movers
(bar 0, exact); (b) taxi-tier `hard_conflict` count vs main (30f's "caps never exceeded"; sidecar
`hard_conflict[].tier`); (c) movers over 0.3 m and their far-field share (the visual bar); (d) the adjudicated
airside census by family under each tree's own tool. (d) read: KCLT adjudicated airside 3,372 (main tool) →
3,750 (lane tool): `hard_conflict` airside 23 → 159, `pad_airside_weld` 5 → 14 (worst 0.64 → 0.71),
`jetway_strip` 0 → 6, `strip_seam_tear` 0 → 2 (1.31 m), `drainage_minimum` (deferred) 1,802 → 1,880,
`platform_rim_relief` 53 → 0, `platform_refused` 11 → 0, `mid_edge_step` 13 → 0; CRITICAL motion 5 → 8
(+`pavement_over_road_cap` 2, `road_cross_section` 1, `within_shape` 1); critical visual 1,966 → 1,726. KASE
2,658 → 2,541; CRITICAL 1 = 1; `hard_conflict` 68 → 12; `airside_no_step` worst 3.98 → 6.12.

## B. OTHH `within_shape` 366 → 1,095 — INSTRUMENT, two parts; reader named

Reader: `tools/check_grade._check_within_shape` → `iter_shape_grade_constraints(pad_relief_by_nid=…)` (:9293),
`de = |(ea − eb) − offset|` (:9295) with `offset` = the sidecar `pad_relief` target per node (`_pad_relief_by_nid`
:1021, RULINGS 11j). (i) The 9.02 m rows are NOT a surface: within 130 m of 25.25795, 51.61436 the lane patch
holds no node over 4.29 m (`alt_abs` 3.49–4.29, 312 nodes; main 3.66–4.41) — the pair is two vertices of the
one terminal way `-10873` 73 m apart whose RELIEF TARGETS differ by ≈ 9 m: six lane targets of 5.416 m at
25.25766, 51.61449 (main: max 0.979 there) that the surface does NOT carry (z ≈ 4.18 = the level). (ii) The pair
population scales with the ring: 813 of 1,104 `building|building` rows stand on way `-10873` (the one 1,111-vertex
outline), 1,028 of them over 0.2 m, median pair distance 36 m. The per-VERTEX reader of the same offsets, the
in-build `verify/pads.pad_flat` (`report.json verify.by_family`), reads **56 on the lane vs 77 on main** — the
pad is FLATTER. Airport-wide the relief class is the same in kind: targets over 5 m 89 (lane) vs 83 (main),
max 5.467 both. RULE (§56 (11) R-C): `within_shape` pairs on a `building` way are read ONE PER VERTEX against
the level plane (what `pad_flat` already does) — a relief vertex counted once, not against every ring partner;
until then the master reads `pad_flat` for pad flatness, not `within_shape`. OWED (not §56's): which body
authored the +5.4 m feet at the terminal rim and why the solve did not carry them (the relief rows lost to the
hard welds — the reported residual of §11a (2), "pavement is senior").

## C. F1b — ACCEPTED, with the general reading and a named follow-up

Reading: a landing is where a deck's surface MEETS ITS UNIT'S LEVEL — `y_land ∈ [−BAND_M, +BAND_M]`; below the
band is a footing under the ground (R-L), above it an elevated end that joins another object (F1b); neither is
a ramp foot and neither grades the ground. HECA: the five T3 landings stand on `p60_HECA` (`landing0..4`
−0.005..−0.234, levels 101.66–101.87, + `landing5` minted bodiless as before). The seven captures
(`decks.py`): deck members exist ONLY at HECA (1: `T3_road.obj`, foot) and OTHH (13); KASE, KCLT, SPJC, CYXY,
NLWF carry none, so nothing can be lost there. OTHH under F1 + F1b: foot 3 (`Bridge_02/_03` −0.18, `Emiri_17_03`
+0.37 — not on held units, no landing minted, as on main), below 6, above 4; `p60_OTHH` landings 0 = main's 0.
FINDING (follow-up `landing-foot-at-level`, not Beta 2): `bridge_family.landing_pieces` reads the band from the
OBJECT'S LOWEST y, so a ramp object that also carries a footing (`TerminalRoads_02` −1.75..+10.77, `_03`,
`_Parking`, `Bridge_06`, `Terminal_Parking_003`) is refused as "below" although its deck crosses the unit level
(`decks0.py`: triangles crossing [−0.5, +0.5] 856 / 721 / 1,188 m²; `_Parking` 441 m² flat at the level in 6
pieces). The band should be taken about the unit's zero, with a rule that tells a deck lip from a pier
cross-section — a design, not a call site.

## D. F2 — ACCEPT 4 faces; the 0.08 m is acceptable

The four: the pad (194,424 m²); the §20 stand-zone plateau part (4,060 m², inherent, §56 (8) 1); `building6#3`
(105 m², mean width 3.42 m > rule 6's 2.0 m floor, 17.3 m of run on the OPEN apron `pav4` — re-roling it would
hand the apron 105 m² of pad at the pad's value along an edge that is not the plateau's, a geometry change);
`building6#4` (102 m², width 3.42 m, plateau-bordered only but over the floor). A rule to reach 2 needs a
second floor (area, not width) and a level argument for a scrap the open apron borders; not for Beta 2. The
six vertices over 0.02 m (worst −0.08 m at 25.26455, 51.61256) are the terminal's four relaxed
`pad_slope_max ceiling` rows re-choosing (0.42 / 0.08 / 0.04 / 0.05 → 0.42 / 0.11 / 0.04 / 0.06): pad-tier,
under the 0.3 m visual bar, airside 0 — accepted; "byte-identical" is withdrawn as the bar for a re-role that
changes the ring a priced row stands on.

## E. F3 — LEAVE for Beta 2, recorded; the pit is not what the owner sees

`building5` is T3's OWN unit (`unit:43#6330`, base `flat` by 10-02aj (2)), two bodiless walled-ramp pieces of
`T3_road.obj` that main seated as two §20 plates at their own ground (92.03 / 100.38) and rule 2b joined. The
owner's instrument at #112 (`obj8_split_report --feet-in`, 60 m of 30.1125123, 31.3961245): feet within 0.3 m
11 → 14 of 156, buried 3 → 0, worst −10.31 → −9.39, cross-body contact pairs over 0.5 m 9 (worst 8.08 m) → 0.
142 of 156 feet FLOAT ON BOTH TREES: the unit is one level (101.87) and every ramp wall is rigid with it while
the ground under the viaduct stands at 92–100 — no pad level under the ramp changes that; the ground inside
the walled ramp is covered by the ramp object. So 93.04 is DIFFERENT, not measurably worse by the owner's
instrument. RULE (§56 (11) R-J2, replacing R-J's "always planned"): a join of pieces whose §20 ground levels
differ by more than `pad_slope_max × the joined span` is REFUSED at rule 2b (the pieces stay separate plates,
as on main) — the smallest rule at the single derivation site; it needs each piece's ground read at classify
(the DEM median the §20 plate seats at), so it is a design for the next round with the twin R-J named. Per-piece
seating with a strip is NOT recommended (new machinery for an invisible surface). OWNER QUESTION (sim read, not
§56): T3's one level (10-02aj (2)) vs `T3_road.obj`'s authored ground — 142 floating feet on both trees.

## Fix list (ordered, each its own commit) and the subset options

| # | what | wall | acceptance |
|---|---|---|---|
| 1 | R-W frontage pinned through rule 2b (`geom.cluster_outline.simplified_outline` takes the pinned vertex set; `_cluster_pads` passes the airside rims) | 2 h | KASE: runway 0, `building2` welded 33 ± joins, datum within 0.05 of `OA0`; KCLT: taxi-tier 19 ± 3, welded 1,437 ± joins; replay from `sweepwalls/base/*.pkl` against the registered `OA0` arms |
| 2 | R-C `within_shape` one row per building vertex (`check_grade` + `verify/within`), `test_harness` twin | 1 h | OTHH `within_shape` ≈ main's order; `pad_flat` unchanged |
| 3 | the outline-disarm coupling: `absorb_near_roads` with `outline_close_m = 0` absorbs nothing — state it or decouple | 0.5 h | `OA0` ≠ `O0` or the docstring says why |
| 4 | R-J2 refused join across a level step (design + twin; next round) | 3 h | #112 site 100.38 / 92.03 as on main |

Subsets: **(S1) ship `OA0`'s content** (collar deletion + warning + 4F + F1b + F2 + hygiene; outline and
absorb keys set to 0 for the release, R-W landed later) — airside: KCLT taxi-tier = main, runway 0, movers ≤
0.61 m far-field; KASE runway 0; OTHH 0; HECA un-laddered (one 10-min replay owed). **(S2) ship all after fix 1**
— re-measure with the same ladder; expected `F` ≈ `OA0` in the airside frame. **(S3) hold the whole change**
— no airside case for it: `OA0` is within the floor. Recommend S2 if fix 1 lands today, else S1.

## Not settled

HECA's channel ladder (replays at 10 min each; the build's 4,507 movers and 73 taxi-tier rows are consistent with
the KCLT pattern, unmeasured); which body authored the +5.4 m relief at the OTHH terminal rim; the stage-1
`--stage1-dump` row diff (the `welded` record was the witness instead); the F2 second-floor rule.
