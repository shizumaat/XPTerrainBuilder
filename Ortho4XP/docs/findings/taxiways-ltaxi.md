# Taxiway lane ltaxi, 2026-10-26: #517 SPJC, #883 KBOI, #805 KCLT

Captures (current main a6258a190, all registered in `frames.py`):
- `ltaxi/SPJC.pkl`
- `ltaxi/KBOI.pkl`
- `ltaxi/KCLT.pkl`

Replays: `v2_solve_replay.py --replay … --from constraints --solved-out … --emit …`.
Profiles were read off the solved surface along the apt.dat 1201/1202 taxi routes (scratch
reader, not a tool).

## #517 SPJC: the dip and climb on taxiway L (needs a ruling: Q517-1)

**Site.** Taxiway L runs alongside 16L/34R. The site is about 190 m west of that runway's
centreline and 400–550 m north of the 34R threshold. The dip is the L / M4 junction
(-12.031527, -77.111309). The climb back peaks 120 m north of it (-12.0305733, -77.1117774).

**Profile on main, taxiway L from A (-12.0324445, -77.1108544) to B (-12.0291405, -77.11248):**

| station from A | 0 | 120 (L/M4 junction) | 180 (low) | 240 (crest) | 300 | 420 (L/M3 junction) |
|---|---|---|---|---|---|---|
| z | 25.23 | 23.37 | 23.16 | 23.65 | 23.18 | 21.17 |
| grade into it | −2.0 % | −1.0 % | −0.1 % | **+1.1 %** | −1.2 % | −1.5 % |
| DEM | 26.87 | 25.37 | 25.08 | 24.58 | 24.48 | 24.05 |
| taxi trend target | | 25.24 | 25.02 | 24.80 | 24.67 | 24.06 |

**What holds the low point.** The chain of holds runs from the terminal to taxiway L:
- The terminal pad `building5` is seated at 19.05 (3.4–3.9 m under the DEM). Its apron
  plateau `pav49#plateau:building5` holds the parallel taxiway M at about 20.0.
- From M, the connectors M4 and M3 climb to L at their cap. M3 is +1.50 % over 76 m;
  M4 is 1.3–1.7 % over 75 m.
- So L can stand at most about 1.1 m above M at its two junctions: about 23.37 at the
  L/M4 junction and about 21.2 at the L/M3 junction. Both sit 2 m and 2.9 m under the
  DEM trend.

**What makes the climb back.** `--why-vertex` on the crest (v3328) and on the low point
(v3330) reads "no row binds — the objective holds it". Between the two junction holds,
taxiway L is pulled by two terms:
- the taxi trend (`[design] taxi_trend` 30), priced on every vertex of the taxi face
  (spec §8.6.1). It pulls L toward the DEM trend, 1.1–1.9 m above it;
- the chain's curvature row (`taxi_profile` 300, the second difference along the
  centreline only).

Summed over the face, the trend outweighs the curvature row. The free span therefore
bulges up toward the trend and comes back down to the next hold. That bulge is the
0.5 m climb.

**What a smoother lawful profile moves.** Both arms are replays, measured, with no code
change:

| arm | climb at the crest | L/M4 junction | L/M3 junction | airside vertices moved > 0.05 m (max) |
|---|---|---|---|---|
| main | +1.10 % | 23.38 | 21.17 | — |
| `taxi_profile` 300 → 3000 | +0.11 % | 23.41 | 21.14 | parallel 443, stub 206, junction 278, apron 82 (0.65 m) |
| `taxi_trend` 30 → 3 | +0.25 % | 23.22 | 21.17 | parallel 577, stub 286, junction 539, apron 250 (0.75 m) |

Either arm removes the climb, and the holds do not move (±0.16 m). Both are airport-wide
weight changes: they move every taxiway of every airport. A third option, not measured:
shift the taxi trend linearly through the chain's stage-1 junction levels, the same way
§21 shifts the runway trend through its thresholds and 15i (3) shifts it through
stage-1 apron levels. That gives a straight line between the two junction holds
(about −0.72 % here) and changes only chains held off their trend.

**Q517-1 (owner).** For a smoother taxiway grade between two held junctions, which of
these is ruled?
- (a) a stiffer taxi curvature row (`taxi_profile` 3000);
- (b) a weaker taxi trend (`taxi_trend` 3);
- (c) the trend shifted through the chain's held junction levels.

The lane recommends (c). It is the narrowest, and it is the form the runway law already
has. (a) puts the curvature row above the law's own one-sided weight (300) and could
trade law rows for smoothness. (b) re-opens the 10o / 10t lag the trend was ruled to fix.

## #883 KBOI: the airside rows on current main (attribution; no fix)

The replay census (`census.py` on the replay patch at a6258a190) reads: adjudicated 105,
airside 28 (acceptance count 30), groundside the rest, 670 drainage version-deferred.

| row(s) | m | where (landmark) | attribution |
|---|---|---|---|
| strip_seam_tear ×2 1.20, adjacent_ground_step ×2 0.78, pad_frontage_infeasible building56 0.127, pad_airside_weld 0.048, hard_conflict pad_slope_max ×2 0.023 | — | The hangar corner by taxiway B / A7, 530–560 m east of the 10L threshold (43.5709, -116.2300) | **The kept step** (owner 2026-10-20 answer 44). The pad `building55` stands at 865.92, level with taxiway B (`pol7`). Next to it are `pol92` and `gap:7`, at 863.8–864.9. The gap joint is declared (1.036 m, kind `apron_terrace`, gap). The taxiway B zone-1/zone-2 graded strip between them carries the step. The strip families read only `wall_terrace` joints (15b), so they report the declared gap step again. See Q883-1. |
| pad_frontage_infeasible building41 0.348 (WARNED) | 0.35 | The hangar 176 m south of taxiway F, 510 m from the 10R threshold (43.5657, -116.2448) | The pad is seated flat at 857.74 (4,084 m²). Over its frontage, the apron cannot meet a flat pad within its caps, so 7 of 8 contacts are released (the flat-pad spec v2 release, WARNED at build). This is lawful by the release rule. |
| frontage_near_miss building43 0.12 | 0.12 | The terminal-area pad 150 m south of taxiway A, 1.2 km from the 10L threshold (43.5680, -116.2224) | The apron plateau `pol30#plateau:building43` meets the pad at 4.79 % over 2.5 m. This is the "building36 frontage 0.12" of the 10-20 comment (renumbered). |
| plane_gradient pol30 0.21 | 0.012 excess | The apron 220 m south of taxiway D (43.5674, -116.2180) | A 13.2 m triangle at 1.591 % against the apron cap. The census magnitude is the whole rise; the excess over the cap is about 0.012 m, under the 0.05 m pavement bar. |
| pad_frontage_infeasible building21 0.085, frontage_near_miss building32 0.05 | ≤ 0.09 | The pads by taxiway K and the west apron | At or under the bar. |
| strip_transverse ×2 0.28 / 0.20 | ground | The 10L/28R and 10R/28L edge strips | Ground, under the 0.5 m bar. |
| pad_airside_renode ×11, airside_no_step ×1, hard_conflict 0.024 | 0.00–0.02 | various | Bookkeeping rows of 0 m. |

The "building36 coverage join 0.72 m" of the 10-20 comment no longer appears on main.

**Q883-1 (owner).** At the kept hangar step, should the two strip families forgive the
declared gap step the way `frontage_near_miss` does since #1084? The pairs here sit
beside the joint line, not across it, so a crossing test alone would not forgive them.
Answer 44 kept the step, but the census still counts it as 4 ground rows at 0.78–1.20 m.

## #805 KCLT: questions the implementation leaves open

The part of 16d that can be read from the data shipped as `claude/ltaxi-805`; see
`805-ltaxi.md`. Two items need the owner.

**Q805-1, the survey date.** Ruling 16d (2b) says lidar is no witness where the survey
predates the airport data. Nothing in the data states a survey date:
- the KCLT inset is USGS 3DEP 1 m, project `NC_Phase_4_CentralWestNC_GEIGER_A16`. Its
  metadata carries a publication date (2024-06-10) but no acquisition date;
- the apt.dat carries no date.

The lidar reads taxiway T **on a ridge**: 228.3–229.5 between 222.1 at 320 m and 216.4 at
620 m along the 18C extended centreline. Along T's own route it falls 2.4 % (node 8 →
node 4), above the 1.5 % taxiway cap. So it does not show the excavation in the owner's
photos.

A witness the data can read: the lidar along the end-around taxiway's own route breaks
the taxiway grade law, which means the survey does not show this pavement. Is that
accepted as the "predates" witness? If not, should a date come from somewhere else?
Until this is answered, T stays at the lidar level, reported (not pinned) as an EAT.

**Q805-2, the near bound.** The ruling says "whatever its distance". The lane reads the
wrap only beyond the runway's own safety area (`runway_safety_area_length_m`; FAA
304.8 m, ICAO strip end + RESA). The reason is LEMD 36L. Its taxi route wraps the end at
70.8 m, inside the strip/RESA, and without the bound it would be pinned 23.4 m under the
runway end (581.63 vs 605.03, coarse DEM). Is the safety-area bound accepted?
