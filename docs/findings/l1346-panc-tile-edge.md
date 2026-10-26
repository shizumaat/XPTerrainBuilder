# l1346 — PANC runway 15/33 at the lon −150 tile seam (#1346, #1347, #1348)

Lane `l1346`, base `dae8b1b09`. PHASE 1 (attribution) only. The fix needs an
owner ruling on law, so phase 2 was not started (see "Why this stops").

## The site, numbers first

The built ridge of runway 15/33 steps **1.006 m over 11.9 m (−8.47 %)** between
v2894 (61.17338754, −149.99983297) and v2895 (61.17328434, −149.99977721), about
9 m east of the meridian. This is the capture's numbering; the same vertices are
v2732 → v2733 in the `+61-150` build. Stage 1 AIRSIDE is hard-infeasible:
33 / 170,055 hard rows are violated in the replay, the worst 0.714 m
(`runway_profile` end_zone, row 2405). That matches the `+61-151` build's report
row for row.

Capture: `/Users/noah/XPTerrainBuilderData/.harness/frames/l1346/PANC.pkl`
(`frames.py list PANC`). Replay: `--from constraints --why-hard 40 --why-hard-stage 1`.

| station from the RWY 15 end | vertex | holder | z (base) | DEM |
|---|---|---|---|---|
| 2988.8 | v2416 (61.17376894, −150.00004671) | §38 seam pin, west band edge | 36.192 | 36.192 |
| 3007.4 | v2891 (61.17360741, −149.99995378) | §38 seam pin, east band edge | 36.262 | 36.262 |
| 3008.5 | v2892 | free | 36.248 | 36.268 |
| 3020.9 | v2893 | free | 36.629 | 36.291 |
| 3032.8 | **v2894** | **CIFP threshold pin, RWY 33 (displaced 270 m)** | **36.881** | 36.335 |
| 3044.7 | v2895 | free | 35.875 | 36.373 |
| 3056.7 | v2896 | free | 35.985 | 36.412 |

## The hard rows that hold v2894 / v2895

These are not an edge weld, a crossing anchor (15/33 crosses no runway here), or
a disagreement between the two tiles. Two HARD DATUMS meet inside the runway
family's reach:

1. **The RWY 33 CIFP threshold pin**, 36.881 m on v2894. The DEM under it is
   36.335 m, so the pin stands **+0.546 m** above the lidar.
2. **The §38 tile-seam DEM pins** on the runway's band edges (± 2.5 m of lon −150):

   | pin | lat, lon | value | `+61-150` raster | `+61-151` raster |
   |---|---|---|---|---|
   | v2891 | 61.17360741, −149.99995378 | 36.262 | 36.262 | 36.262 |
   | v2979 | 61.17352215, −149.99995377 | 36.263 | 36.263 | 36.263 |
   | v2980 | 61.17333370, −149.99995375 | 36.270 | 36.270 | 36.270 |
   | v2981 | 61.17314524, −149.99995374 | 36.311 | 36.311 | 36.311 |
   | v3002 | 61.17352215, −150.00004669 | 36.212 | 36.212 | 36.212 |
   | v3001 | 61.17333369, −150.00004667 | 36.214 | 36.214 | 36.214 |
   | v3000 | 61.17314524, −150.00004666 | 36.225 | 36.225 | 36.225 |

   The two tiles' baked rasters agree to the millimetre at every pin
   (`seam_harmonized_ballot_insets`). **The "neighbour tile's edge value"
   hypothesis is refuted.**

The families between the two datums cannot be met:

- **Longitudinal.** v2891 (seam, 36.262) to v2894 (CIFP, 36.881) is +0.619 m
  over 25.4 m, 2.44 %. §50 already yields the cap uniformly ("RUNWAY OVER GRADE
  15/33 … built to 2.458 %"), so this row is lawful.
- **Vertical curve (K / max_grade_change).** The ridge has to turn from the
  0.37 % seam-to-seam grade (v2416 → v2891, both DEM pins) to 2.44 % at v2891.
  The allowance is 0.0004 per 11.9 m station. Rows 414990, 414991 and 415434
  demand 0.106 and 0.094.
- **Transverse (`transverse_max`).** At the threshold station the band-edge pin
  v2980 (36.270) is 8.8 m across the runway from v2894 (36.881): 0.611 m, or
  6.9 %. Rows 413393, 413427 and 413391 demand 0.26, 0.42 and 0.24 against 0.12,
  0.19 and 0.04. These rows are pin against pin through one interpolated free
  vertex. **No placement of the free vertices satisfies them.** The solver's
  compromise is the 1 m step.

Why PANC, and why here: runway 15/33 runs about 15° off the meridian, so the
seam band lies along about 170 m of runway (runway seam pins from lat 61.1727 to
61.1741). The 33 displaced threshold sits 9 m from the band edge. CIFP stands
above the lidar DEM at all six PANC thresholds: 07R +0.21, 25L +0.29, 07L +0.30,
25R +0.38, 15 +0.38 and 33 +0.52 m. Runways 07L/25R and 07R/25L also cross lon
−150, but far from their thresholds (07L is about 450 m away), so they have room
to turn and are lawful. SPLP #145 is the same class at 0.06 m. It was closed
below the bar.

Diagnostic arm `--drop-generator seams`: the replay is not clean, because
`runway_chord._with_seam_knots` still reads `pm.seam_vertices`. With it, stage 1
SETTLED and the verify DEFECT families are all zero. But `seam_residual` rose to
439 rows, and the ridge south of the threshold kept 2.46 % to 39.79 m at
s = 3152, which is +3.1 m over the DEM. Dropping the pins alone is not a fix.

## PAAQ (#1348) is a different class

PAAQ sits wholly inside `+61-150`. It has no seam vertices (`seam: null`), and
its stage-1 hard set is empty. Its verify DEFECT is `runway_transverse` 2: face
10, 5.03 % over 22.0 m and 5.02 % over 21.5 m (frame x 178–201 m, y +293.5 and
−182.0). Its `within_shape` runway|runway rows (5–7.7 %) sit on the same face at
61.5939, −149.0876. It needs its own issue and attribution. This lane does not
fix it, so the PR may not say `Fixes #1348`.

## A production fact the fix must face

§38 (4) reads "one airport, one solve, per-tile pieces". Production builds PANC
once PER TILE, and each build reads its own tile's pack DSF dump:

| | `+61-150` | `+61-151` |
|---|---|---|
| `dsf:object` buildings | 38 | 0 |
| dsf pavements | 314 | 133 |
| planar vertices | 18,390 | 18,239 |
| seam vertices | 475 | 468 |
| stage-1 rows violated | 26 | 18 |

Today the two pieces agree at the seam only because both pin it to one DEM. A
runway that "both tiles consume" needs a single cross-tile solve first.

## Why this stops (the ruling the owner owes)

The law as written makes this case infeasible, and it says to NAME it rather
than move a pin:

- §38 (1): "every seam-band vertex of every role, the runway included".
- 13ah: "never a moved pin".
- §38 (4) as amended (13am): "the band is draped DEM".
- §50: "THRESHOLDS ARE TRUTH", and the CIFP pin outranks the seam only on a
  shared vertex.

The brief's rule, that the seam pin yields to the runway family, amends §38 (1)
and (4). On its own it leaves a 0.5–0.6 m step at each band edge, where the
runway meets the draped DEM strip. `seam_residual` is not a gating family, so
that step would PASS verify and ship. The owner has three options:

- **(A)** The runway is ONE profile across the meridian. On runway faces the
  band is not cut, and the per-tile pieces share meridian vertices at the
  runway's z. This needs a cross-tile solve, since today there are two solves,
  and a mesh-side proof that the two DSFs meet at those z on the tile edge.
- **(B)** The seam is senior on a runway it crosses near a threshold. The CIFP
  threshold yields up to about 0.5 m. This reverses §50's "thresholds are truth"
  for this case.
- **(C)** A datum read. The systematic +0.2…+0.5 m CIFP-over-lidar offset
  (geoid or realisation) is corrected before the solve. That would shrink but
  not remove the 33 conflict: about 0.17 m over 8.8 m is 1.9 %, still over the
  transverse cap.
