# `why` — WHAT BINDS THIS SHAPE: CYXY apron 156 and service road 153

Lane `v2why`, 2026-09-04. Owner question (sim read, app 1.0.280, v2 patch
`/Users/noah/XPTerrainBuilderData/Patches/+60-140/+60-136/CYXY_auto.patch.osm`):
the "Apron off E at G" complex (pav17: apron 156, junctions 155/161/103,
buildings 165/166, cross connector 160) solves 3.4–4.7 m BELOW the
production DEM while the runways sit on it — *"what is preventing 156 from
being higher — the taxiways that serve it should be able to support an
elevation closer to DEM"*.

Instrument: `python -m auto_patch_v2 why CYXY --shape 156` (`solve/why.py`,
read-only over the pipeline's own LP; INDEX row on the `auto_patch_v2`
entry). Face ids in the lane's build equal the shipped patch's `shapeID`s
(centroids of 103/153/155/156/160/161/167 identical), so `--shape` is a
direct face lookup here. Build: deb25119 + this lane, production DEM frame
N60W136, ruleset ICAO, 4,545 vertices, 192,839 + 213 LP rows, solve 0.6 s.

## 1. Apron 156 — the answer

```
== face 156: role=apron ref=pav17 letter=- side=airside vertices=83
   z 698.22..699.37  DEM 702.47..703.42  z−dem median -4.38 (min -4.73, max -3.28)
-- binding rows on the shape's vertices, by family (rows, Σ|dual|):
   pads                     49    145247.61     (building 165/166 frontage / weld — internal to the complex)
   no_step_pairs            33     17308.16
   apron_within_shape       24      6029.68
   (transverse: 0 rows binding; taxi_within_shape: 0 rows ON the apron's own vertices)
-- chain trace (binding rows from the shape to the nearest hard terminal):
   start v3139[apron#156,junction#155,parking_lot#154] z 698.217
   terminal v471[primary_parallel#6,runway#11,runway#8] z 694.334
       [PIN: RULINGS :511-516 CIFP threshold rwy 02/20 end 02]
   4 hops; Σ dz +3.883 m = z[start] − z[terminal] +3.883 m
   by family along the chain: no_step_pairs +2.005, taxi_within_shape +1.876, runway_crown +0.001
     1. v3139[apron#156,junction#155]  698.217 -> v2350[graded_strip#159,junction#103] 696.719
                                       dz +1.499  no_step_pairs cap 1.00% × 149.9 m   dual -6279
     2. v2350[junction#103]            696.719 -> v451[graded_strip#122,primary_parallel#6] 696.212
                                       dz +0.507  no_step_pairs cap 1.50% × 33.8 m    dual -4321
     3. v451[primary_parallel#6]       696.212 -> v469[primary_parallel#6,runway#8] 694.336
                                       dz +1.876  taxi_within_shape cap 1.50% × 125.1 m dual -4312
     4. v469[runway#8]                 694.336 -> v471[runway#8,runway#11] 694.334
                                       dz +0.001  runway_crown (transect)              dual -4346
-- relax one family (full re-solve each; the shape's rise):
   pads                 −    14 rows  dz median +0.412  max +0.834  z−dem after -3.931
   no_step_pairs        − 22610 rows  dz median +2.777  min +1.162  max +4.390  z−dem after -1.706
   apron_within_shape   −  9681 rows  dz median +0.000  max +0.000  z−dem after -4.381
   taxi_within_shape    − 38146 rows  dz median +0.000  max +0.047  z−dem after -4.381
   runway_crown         −   500 rows  dz median +0.059  max +0.066  z−dem after -4.322
-- taxi centrelines touching the shape (code-letter evidence):
   centreline 20 ref='taxi17' (62 m): apt.dat 1202 name/letters G ['A'];
       faces 160:cross_connector/A@3.0%, 156:apron/-@1.0%, 103:junction/-@1.5%
```

**The limiter is the airside no-step direct-distance law (hypothesis b).**
The apron's lowest vertex v3139 is exactly 1 % × 149.9 m = 1.499 m above a
junction-103 vertex 149.9 m away (the pair sits at the 150 m window's edge
and is priced at the APRON's 1 % — "the strictest governed cap at either
endpoint"), that junction vertex is 1.5 % × 33.8 m above the parallel
taxiway, and the taxiway is 1.5 % × 125.1 m above the runway edge at the
02-end CIFP pin (694.33). Every metre of the 3.88 m from the pin to the
apron is spent at a cap; the DEM at the apron is 8.7 m above the pin.
Relaxing `no_step_pairs` alone lifts 156 by +2.78 m (median; −4.38 → −1.71
z−dem). Relaxing the taxi or apron within-shape families alone lifts it by
0.00 m: the no-step pairs price the same taxiway vertices at direct
distance, so the longitudinal caps are redundant with them here.

## 2. Second level — with no-step relaxed (`--drop no_step_pairs`, an ARM)

```
== face 156: z 700.51..703.07  DEM 702.47..703.42  z−dem median -1.71 (min -2.18, max +0.10)
-- binding families: apron_within_shape 32 (Σ|dual| 445), taxi_within_shape 7 (390), no_step_rate 1 (234), pads 49 (200)
-- chain trace: 3 hops, Σ dz +6.207 m to the same CIFP pin
     1. v2366[apron#156,cross_connector#160,junction#103] 700.541 -> v477[junction#103,primary_parallel#6] 697.211
                                       dz +3.330  taxi_within_shape cap 1.50% × 222.0 m
     2. v477[junction#103]            697.211 -> v469[primary_parallel#6,runway#8] 694.221
                                       dz +2.990  taxi_within_shape cap 1.50% × 199.3 m
     3. v469 -> v471 runway crown     dz −0.113
-- relax one family:
   apron_within_shape   dz median +0.414  max +1.877  z−dem after -0.037
   taxi_within_shape    dz median +1.719  max +2.177  z−dem after +0.000
   no_step_rate         dz median +0.000
   pads                 dz median +0.000  max +0.453
   runway_crown         dz median +0.213
```

Without the no-step pairs the apron is held by the taxi-family WITHIN-SHAPE
all-pairs cap on junction 103 (letter None → default 1.5 %) over its 222 m
diagonal and on primary_parallel 6 over 199 m; relaxing `taxi_within_shape`
then puts the apron ON the DEM (z−dem +0.00).

## 3. Service road 153 (groundside, dsf:pol120, 33 vertices)

```
   z 696.92..702.55  DEM 696.92..703.65  z−dem median +0.00 (min -1.58, max +0.12)
-- binding families: road_cross_section 15 (Σ|dual| 45), transverse 2 (1.3)
-- chain trace: 12 hops from v3064 (702.108) to the same runway pin (694.334), Σ dz +7.774
   by family: no_step_pairs +2.476, road_within_shape +2.024 (5 % × 40.5 m, the parking_lot 154 edge),
              taxi_within_shape +1.876, road_cross_section +1.304 (2 % × 42.6 + 22.6 m), apron +0.092
-- relax one family: every arm dz median +0.000 (road_cross_section max +1.197, road_within_shape max +1.386)
```

153 follows the DEM (median z−dem 0.00) — the owner's "2.6 % down" is the
DEM's own fall. Its one below-DEM end (−1.58 m) is where it meets lot 154
/ apron 156: the road's 2 % cross-section rows and the lot's 5 % cap carry
the apron's deficit outward. Nothing binds 153 in its own right.

## 4. Hypotheses (a)–(e), verdicts

| | hypothesis | verdict | numbers |
|---|---|---|---|
| a | taxi longitudinal 1.5 % along G/E from the runway contact | **co-binding, redundant** | step 3 of the chain is `taxi_within_shape` 1.5 % × 125.1 m (+1.876 of 3.883 m), but relaxing the family alone lifts 156 by 0.000 m — no-step pairs price the same vertices |
| b | airside no-step, 150 m window, K=16, direct distance at the apron cap | **BINDS (the limiter)** | pair v3139↔v2350 at 1.00 % × 149.9 m = 1.499 m; family Σ dz +2.005 on the chain; relax alone → +2.777 m median (−4.38 → −1.71); after it, taxi within-shape on junction 103 (222 m at 1.5 %) binds next |
| c | transverse across pav17's faces | **refuted** | 0 transverse rows binding on 156; relaxing not even a candidate |
| d | code letter: taxiway width → letter, G at 3 % | **does not hold for 156** | G is already apt.dat 1202 letter **A**: face 160 (cross_connector) solves at 3.0 %; the binding step is at the APRON's 1 % on a no-step pair, where the taxi letter never enters; junction 103 is letter None (the route-proximity cut mints junctions with no letter, `classify/roles.py` ~l.222) and would govern only at the second level. No law-table change made |
| e | apron 1 % within-shape over the apron's own span | **refuted** | 24 rows binding (internal 1 % ties) but relax alone → +0.000 m; second level +0.414 m |

Per the brief, (b) is intent and the no-step law is untouched: the numbers
above are for the owner. v1 held the same apron at 702.8–703.5 by breaking
exactly these rows (its census: airside_no_step 24, transverse 72).

## 5. What the owner can read from this

The apron cannot be closer to the DEM under the current no-step law
because a direct-distance pair to a junction vertex 150 m away is priced
at the apron's 1 % (1.5 m per 150 m) although the travel path between
them is a taxiway at 1.5 % (G's own class, letter A, would be 3 %). If the
owner rules that a no-step pair between an apron vertex and a
taxi-family vertex should be priced at the TAXI endpoint's cap (or along
the route rather than the chord), `--drop no_step_pairs` shows the next
ceiling: junction 103's within-shape all-pairs cap over a 222 m shape.

## 6. Not done

- No law-table change ((d) does not hold at 156); no classify edit for the
  letter-less proximity-cut junction (reported, open question).
- No repro_cut / solve_cut iteration: the v2 `why` IS the offline replay
  (whole airport in 7 s); no five-airport sweep.
- Closing test: one `build_airport.py CYXY --engine v2` (see the lane report).
