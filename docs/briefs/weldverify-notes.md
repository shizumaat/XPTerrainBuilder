# weldverify notes — measuring PR #504 (`claude/cloudweldfix` b8c8e988) on the corpus; §63 acceptance

Lane `weldverify` (Opus). Worktree `.claude/worktrees/weldverify`, branch `claude/weldverify` = `origin/claude/cloudweldfix`
b8c8e988 + `origin/main` 469d18ea0 (merge b57214e32; main since the base adds two log/sidecar-sum commits, no patch change).
Scratch `<scratch>/weldverify/` (`.progress`, `pair.sh` / `acc.sh` / `cmp.py` / `cencmp.py` copied from `<scratch>/weld63/`,
bases `b0` / `kb0` and weld63's `w1` / `kw1` symlinked — controls shared, not rebuilt). Frozen replay tree `weld63frz`.

## RESUME HERE (lane complete; nothing running)

* HEAD = this commit on `claude/weldverify` (code ea519891). Suites at ea519891: non-Qt 9,200 passed / 19 skipped / 1 xfailed /
  1 xpassed; Qt 311; the four named files 204; ratchets PASS (WARN `classify/roles.py` 1,444 → 1,504, `constraints/pads.py`
  1,061 → 1,180).
* The closing build `weldverify_HECA` is of 1e6ab88d (before the strip tie); NOT re-run at ea519891 — replay `v6` is its measure.

## THE STRIP IS PART OF THE WELD (master's ruling from 09j / 08c (4) / 09d (1)) — `v6` HECA, `kv6` KCLT, `ov6` OTHH at ea519891

`constraints/pads.rim_strip_ties`: every vertex of a groundside value face that shares a rigid face's rim (outer ring or a
HOLE), stands off the rim and within the knife (+ grid) of the pad it touches, is tied to its nearest rim vertex in
`pad_slope_ceiling` (the pad's hard 1 % tilt, pad tier) and joins `pad_welded_vertices` (B′ withdraws the ramp target /
ceiling / join pin there). An airside vertex is never tied; a mapped-road ribbon and a late piece are not read. HECA 155 ties.
Two identification bugs on the way (c2df3b49 whole-face test, 704d091c one-ref / outer-ring rim): a strip part runs past
the pad's end, a pad is several faces, and a strip that runs round a pad piece carries that rim as a hole.

CORRECTION of "THE STRIP'S LIP" below: `lip.py` read the rim on the face's OUTER ring only. Read with holes and against the
nearest rim vertex, the 1e6ab88d lips were `building59` | `objpav7` 0.52 m (4 of 5), `building12` | `route3` 0.15 m (12 of 12,
not 0.78), `building207` | `objpav405` 0.11 (21 of 35) — 70 vertices > 0.05 m in 20 pairs; KCLT 14 in 7 (`building46` |
`pol28` 0.55); W whole-clip 11 in 9 (≤ 0.11) / 4 in 4 (0.30).

| read | HECA base → 1e6ab88d → ea519891 | KCLT | OTHH |
|---|---|---|---|
| knife-line vertices > 0.05 m off the rim | — → 70 in 20 pairs → **4 in 3**, all mapped-road ribbons (`small_roads:-18809` 0.10, `-20325` 0.07, `-20639` 0.06: the engine's own ribbon class, not strips) | 14 in 7 → **0** | 0 → 0 |
| TOUCH-OFF runs / m | 15 / 565 → 3 / 49 → 3 / 49 | 8 / 62 → 1 / 0 → **0 / 0** | 0 |
| airside nodes removed / added | 0 / 2 → 0 / 2 | 2 / 2 → 2 / 2 | 5 / 4 |
| airside movers runway / strip / taxi / apron, worst | 0 / 4 / 10 / 39, 0.05 (unchanged) | 0 / 4 / 5 / 31, 0.45 (unchanged) | 0 |
| structure frame | 0 of 245 | 0 of 363 | 0 of 2,546 (held 18, plateaus 7 equal) |
| `hard_conflict` gs / pad / taxi | 340 / 19 / 2 → 358 / 19 / 2 | 370 / 33 / 0 → 351 / 33 / 0 | none |
| `--null-change` | 5/0/0.249, 8/0/0.137, 8/0/0.137 | 5/0/0.139, 0, 0 | — |
| CRITICAL visual | 1,962 → 1,992 → **2,008** | 1,996 → 2,038 → 2,038 | 1,932 → 2,054 → 2,054 |
| `hairline_pair` vs base | +30 → +30 | +43 → +43 | +122 → +122 |

THE ONE 10a (2) (b) SITE: HECA `building36` | `dsf:objpav366` at 30.11685, 31.38175. The pad is held by airside (2
`frontage_hold` rows; its plane at 63.26); the road is welded to the apron a few metres on. The knife line now stands at
63.26–63.29 and the road climbs 63.26 → 63.65 → 63.96 in 3 m, its own rows relaxed (`road_cross_section` 15 ≤ 0.59 m,
`pavement_max_grade ceiling` 10 ≤ 0.55 m, tier groundside) against the pad's ceiling. The census reads it as 18 new step rows
(`mid_edge_step` +13 CRITICAL visual, `vertex_to_edge_step` +3), all `service_road|service_road` 0.51–0.68 m over 0.65–0.98 m,
all here: the whole CRITICAL visual rise 1,992 → 2,008. No exemption exists for it (10a (2) (b) names none in the census).

HAIRLINE READ (`hair.py` on `--rows-json`, HECA base → 1e6ab88d): 96 rows added, 66 dropped, net +30; a coplanar strip
changes none of them (the family is a PLAN-distance read; +30 / +43 / +122 identical before and after the tie). Of the 96
added, 73 stand within 2 m of a pad rim: `ring` rows `building|groundside_pavement` 17, `building|service_road` 15,
`service_road|service_road` 11, and `short` rows (a segment under the 0.5 m spacing) `service_road|service_road` 10,
`groundside_pavement|groundside_pavement` 7 — the strips' own geometry (their ends, and rim vertices a grid cell off the
knife line), not the zone band (0 `graded_strip` rows). Distances 0.097 / 0.496 / 0.499 m (min / median / max): one
identity-grid cell, not millimetres. A mesh gets constrained edges 0.35–0.5 m apart there: a few sub-metre triangles per
strip end, coplanar now, no sliver explosion (the family's alarm class is the 0.01–0.06 mm pair).

## FINAL — head 1e6ab88d (`v3` HECA vs `b0`, `kv3` KCLT vs `kb0`; base ded211fb; each tree's own census)

| read | HECA base → W (`w1`) → head | KCLT base → W (`kw1`) → head | bar | verdict |
|---|---|---|---|---|
| TOUCH-OFF runs / m | 15 / 565 → 8 / 68 → **3 / 49** | 8 / 62 → 1 / 0 → **1 / 0** | toward 0 | MET (HECA's 49 m is `building15` \| `objpav394`: 3 + 7 shared rim vertices at the pad's 97.7, the lot falling at 4.3–4.9 % inside its 5 % cap — welded, read as off by the 10 m window) |
| GAPPED (listed) | 2 / 66 → 5 / 86 → 5 / 86 | 3 / 24 → 4 / 24 → 4 / 24 | — | `building164` \| `objpav405` +2.70 over 65.8 m, gap 1.31 m, unchanged |
| ENGINE | 18 / 156 → 22 / 302 → 23 / 302 | 2 / 0 → 0 → 1 / 16 | — | `building131` \| `gap:0/s2/lot` 110 m as W |
| airside nodes removed / added | 9 / 2 → **0 / 2** | 6 / 3 → **2 / 2** | 0 / 0 | NEAR: HECA's 2 are both at the `objpav366` apron contact 30.11721, 31.38160 |
| airside movers > 0.02 m runway / strip / taxi / apron, worst | 0 / 14 / 20 / 98, 0.14 → **0 / 4 / 10 / 39, 0.05** | 0 / 4 / 5 / 6, 0.45 → **0 / 4 / 5 / 31, 0.45** | runway 0, others ~0 | runway MET; HECA all 53 within 200 m of `objpav366`; KCLT 26 ≤ 0.04 at one welded road (35.2094, −80.9415), 8 ≤ 0.05 at 35.2070, −80.9321, and 5 isolated apron nodes 0.25–0.45 (35.21569, −80.94399; 35.20810, −80.95938; 35.20849, −80.93090) that moved the same under W's one-pad probe |
| structure frame | 0 of 245 | 0 of 363 | 0 | MET |
| `hard_conflict` gs / pad / taxi | 254 / 104 / 64 → 266 / 124 / 70 → **340 / 19 / 2** | 277 / 33 / 50 → 267 / 53 / 48 → **370 / 33 / 0** | pad ≤ base; taxi ± 3 | pad MET; taxi is the RECLASSIFICATION (below) |
| `--null-change` | 9/0/0.119, 8/0/0.091, 8/0/0.091 → 5/0/0.249, 8/0/0.137, 8/0/0.137 | — → 5/0/0.139, 0, 0 | ≤ 20 / 0 | MET |
| pad datums moved > 0.02 m | 9 of 120 | 5 of 83 | airside-seated 0 | MISSED, attributed: `building75` 100.69 → 100.85, `building59` 85.47 → 85.76, `building36` 63.31 → 63.54, `building96` 63.60 → 63.40 are pads whose PLANE was relaxed in the base (`building75` alone 84 of the 104 pad rows: rim 99.75–100.85) and holds now (rim 100.85 flat) — the published level is the plane's, the lot yields |
| CRITICAL motion / visual | 3 / 1,962 → 3 / 1,973 → 3 / **1,992** | 0 / 1,996 → 0 / **2,038** | not rising | MISSED by `hairline_pair` alone (+30 / +43 unmeshable pairs: the 0.95 m strips' own thin faces); every other family equal to base |
| adjudicated airside | 12,022 → 12,043 → 11,861 | 2,971 → 2,985 → 2,915 | — | `hard_conflict` airside 168 → 21 / 83 → 33 carries it |
| `road_cross_section` | 501 → 617 → 586 | 769 → 898 → 870 | — | groundside REPORT rows on welded roads; not attributed row by row |
| `pavement_over_road_cap` | 23 → 22 → 24 | 16 → 19 → 20 | — | (48 / 38 at b57214e3 before the cap-seniority fix) |

Other airports at the head: SPJC (`sv` vs `sb0`) runway 0, nodes 5 / 7, movers strip 8 / taxi 8 / apron 15 ≤ 0.08 m, structure 0 of 377,
conflicts 3 / 1 / 7 → 9 / 1 / 0, TOUCH-OFF 2 / 0 → 0, HELD 2. CYXY (`cv` vs `cb0`) runway 0, nodes 3 / 0, movers strip 4 / apron 21
≤ 0.12 m (60.70495, −135.06923), structure 0 of 94, conflicts 4 = 4, TOUCH-OFF 2 / 157 → HELD 2 / 157 (13o's terraces).

### THE STRIP'S LIP (found, attributed, NOT fixed — a design question on cloud commit (3))

`<scratch>/weldverify/lip.py`: a welded cell's vertices within 1.2 m of the rim against the nearest rim vertex. W whole-clip
(`w1`): 2 vertices > 0.3 m in 21 pairs. Head (`v3`): 14 in 31 pairs — `building12` \| `route3` 11 of 15 knife-line vertices
0.3–0.78 m above the rim (95.6 vs 94.6–94.9) across the 0.95 m strip; `building36` \| `objpav366` 0.58; `building59` \|
`objpav7` 0.52. KCLT `kv3`: `building56` \| `pol48` / `pol22` 0.70 / 0.65, `building46` \| `pol28` 0.55 (`kw1` 0.47 / — / 0.30).
Mechanism: the BODY is the knifed cell and no weld partner, so its knife-line vertices keep the road's own law (ramp target,
ceiling, join pin — B′ releases only vertices SHARED with a pad), and the strip between has no rim → knife-line ring edge
except at its two ends, so no cap row crosses it (`pavement_cap` R-F skips a pad vertex). Under 1 m everywhere read, so
08d (2)'s class, and the edge read (threshold 1 m) does not see it.
## Step 1 — `v1` (HECA) / `kv1` (KCLT) at b57214e3, before any fix here

| read | HECA `b0` → `w1` (weld63) → `v1` | KCLT `kb0` → `kw1` → `kv1` |
|---|---|---|
| TOUCH-OFF runs / m | 15 / 565 → 8 / 68 → **3 / 0** | 8 / 62 → 1 / 0 → 3 / 4 (`building26` \| `pol50#1` 3.5 m −1.82: a strip part) |
| GAPPED | 2 / 66 → 5 / 86 → 5 / 86 | 3 / 24 → 4 / 24 → 4 / 24 |
| ENGINE | 18 / 156 → 22 / 302 → 22 / 311 | 2 / 0 → 0 → 0 |
| `hard_conflict` gs / pad / taxi | 254 / 104 / 64 → 266 / 124 / 70 → **349 / 19 / 2** | 277 / 33 / 50 → 267 / 53 / 48 → **303 / 33 / 0** |
| airside nodes removed / added (solve-owned) | 9 / 2 → **5 / 163** | 6 / 3 → **31 / 30** |
| airside movers > 0.02 (runway / strip / taxi / apron), worst | 0 / 14 / 20 / 98, 0.14 → **11 / 67 / 76 / 43, 0.10** | 0 / 4 / 5 / 6, 0.45 → 4 / 6 / 5 / 31, 0.45 |
| structure frame | 0 of 245 → 0 of 245 | 0 of 363 → 0 of 363 |
| `--null-change` | 9/0/0.119, 8/0/0.091, 8/0/0.091 → 3/0/0.092, **76/4/0.343, 98/4/0.343 MISSED** | — → 2/0/0.117, 0, 0 |
| CRITICAL motion / visual | 3 / 1,962 → 3 / 1,973 → 3 / **2,015** | 0 / 1,996 → … → 0 / 2,036 |
| adjudicated airside | 12,022 → 12,043 (`x1`) → 12,122 | 2,971 → 3,031 |
| `road_cross_section` | 501 → 617 → 559 | 769 → 898 → 809 |

`x1` (W + B′ + P, 44f9955b) reads the same as `w1` on every line at HECA: B′ changes nothing measurable there.

### The node miss is a ZONE-CLAIM HAIRLINE, not the weld (attributed by intervention, fixed 63341a37)

`v1`'s 163 added airside nodes are RUNWAY nodes of 05C/23C (121 `runway|runway`, 14 `junction|runway`, 11 `runway|stub`, …),
1.6 km from the nearest pad. Chain: cloudweldfix (3) adds 27 rim-strip cells (HECA 1,531 → 1,558) → `planar/zones.zone_regions`
unions every cell into its claim → the union re-nodes and leaves a new band part `adjacent_ground:runway:4:zone1#5`,
**1.31 m², 3,378 m of ring (1,689 m × 0.8 mm)** beside 05C/23C, over the 1 m² floor → its ring's 60 m chord stations
land on the runway edge. The same class, the same hairline, as spec §59's gap apron (the comment in `zones.py`).
Reads: `<scratch>/weldverify/{lines_drv,reg_drv,zone_drv}.py` on trees 44f9955b (3 thin parts) and b57214e3 (4: the new one).
FIX (63341a37): the strip carries `pad_touch.STRIP_KEY`; `zones._unclaimed` leaves it out of the claim exactly as a gap
apron (cut out of a band it reaches). After it the head reads the 3 thin parts of the base. Twins in `test_pad_touch`.
NOT DONE, measured: a WIDTH floor on zone parts (drop a part nowhere wider than the 0.5 m identity grid) would be the
general cure for the class but drops 3 parts at HECA, 137 of 606 at KCLT, 4 at SPJC, 2 at CYXY — real narrow bands, not
only float slivers; not landed (a law question: is a band under 0.5 m wide a band?).

### Step 2 — the census reclassification of cloud commit (2)

`hard_conflict` rows of the two `SIDE_RANKED_HEADS` standing on a groundside vertex now carry tier `groundside`, and
`check_grade` sides them groundside: HECA `v1` 159 `pavement_max_grade ceiling` + 10 `road_max_grade pavement fallback`
= **169 rows** (KCLT 113 + 11 = **124**) that the old ranking would have reported in the taxi tier (airside). Census
`hard_conflict` airside / groundside: HECA 168 / 254 → 21 / 349, KCLT 83 / 277 → 33 / 303. The family is REPORT rows; the
adjudicated-airside figure above moves for other families (`within_shape` airside +355 at HECA `v1`, the hairline's nodes).

### RULINGS 2026-10-10a (2) at HECA `building12` (30.11524973490, 31.40942194421) — what holds the pad

Nothing holds it. weld63's `--why-at` on the one-pad probe `ph` (`<scratch>/weld63/ph/why12.txt`): the vertex binds on 18
rows of its OWN plane (`pads`), chained through the shared `route3` vertex → `road_cross_section` → `road_within_shape`
→ the apron contact v8305 at 92.24, 40 m off; no airside contact of the pad, no datum, no hold, no object seat.
On `v1` the pad stands at **94.42–95.52 (median 95.05)** — DEM 104–106 — and `route3` shares its rim at 94.4–94.9:
10a (2) (a) is what the engine does today (the pad MOVED to where the road grades inside its caps). The spec's "104 with
a 29 % road" never existed on this tree (weld63 notes D1). LP twins added (75cdfb3e, `test_ceiling_side_rank`): (i) a
landside pad + welded road tied to a fixed lower contact → 0 relaxed rows; (ii) the same pad held by an apron vertex →
the relaxed rows are `road_cross_section` / `ramp ceiling` / the fallback cap, tier groundside; the pad's plane holds.
