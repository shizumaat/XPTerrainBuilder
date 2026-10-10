# weldverify notes — measuring PR #504 (`claude/cloudweldfix` b8c8e988) on the corpus; §63 acceptance

Lane `weldverify` (Opus). Worktree `.claude/worktrees/weldverify`, branch `claude/weldverify` = `origin/claude/cloudweldfix`
b8c8e988 + `origin/main` 469d18ea0 (merge b57214e32; main since the base adds two log/sidecar-sum commits, no patch change).
Scratch `<scratch>/weldverify/` (`.progress`, `pair.sh` / `acc.sh` / `cmp.py` / `cencmp.py` copied from `<scratch>/weld63/`,
bases `b0` / `kb0` and weld63's `w1` / `kw1` symlinked — controls shared, not rebuilt). Frozen replay tree `weld63frz`.

## RESUME HERE

* HEAD 1e6ab88d (pushed) = PR #504 + main + (a) 63341a37 the rim strip out of the zone claim, (b) 75cdfb3e LP twins for
  10a (2), (c) 1e6ab88d a groundside cap half a tier above its tier's rows. Non-Qt suite at 1e6ab88d: 9,199 passed,
  19 skipped, 1 xfailed, 1 xpassed (`<scratch>/weldverify/suite.txt`).
* Arms in `<scratch>/weldverify/`: `v1` / `kv1` (b57214e3), `x1` / `kx1` (44f9955b), `s1` (23ad159e), `v2` / `kv2`
  (63341a37). RUNNING: `chain3.sh` = `v3` / `kv3` at 1e6ab88d; then `chain4.sh` = bases `sb0` / `cb0` / `ob0` (SPJC, CYXY,
  OTHH at ded211fb). THEN: arms `sv` / `cv` / `ov` at the final head, the sites, the closing build `weldverify_HECA`,
  Qt suite + the four named tests, ratchets.
* `v2` (strip fix alone) at HECA: airside nodes 0 removed / 2 added (both at the `objpav366` apron contact 30.11721, 31.38160);
  movers runway 0, strip 4, taxi 10, apron 39, worst 0.05 m, all 53 within 200 m of that one site; structure 0;
  `--null-change` 5/0/0.249, 8/0/0.137, 8/0/0.137 (inside bar); conflicts 349 / 19 / 2; adjudicated airside 12,022 → 11,867.
* `s1` (S + T): airside nodes 0 / 0, movers 0, conflicts 254 / 104 / 64 unchanged, TOUCH-OFF 15 / 565 → 13 / 597.
  `kx1` = `kw1` on every line (B′ moves nothing measurable at KCLT either: TOUCH-OFF 1 / 0, 267 / 53 / 48).
* FOUND on `v1`, fixed 1e6ab88d, `v3` measures it: cloud (2) put a lot's / road's own grade cap in the groundside tier at
  the SAME price as the road's ramp ceiling and cross-section it had been senior to → `dsf:objpav405` at 30.1390670,
  31.4100643 (no pad near) went 5.90 m over 55.8 m (`pavement_over_road_cap` HECA 23 → 48 rows, KCLT 16 → 38).

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
