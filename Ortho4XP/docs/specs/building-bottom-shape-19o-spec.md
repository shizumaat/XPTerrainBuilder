# THE GROUND UNDER A BUILDING FOLLOWS ITS AUTHORED BOTTOM — what landed (sloped) and the spec for the rest (stepped, posts)

Lane `lpadshape`, 2026-11-19, on `claude/test-565` (8d141e68f). Owner law: **RULINGS 2026-11-19o** (amends 09c; reads with 19l), issue **#2184** (KASE covered aircraft parking, 39.226775, -106.868670). Consumer census per 08-30l: the twin `tests/auto_patch_v2/test_pad_base_slope.py` (`CENSUS`). Builds on `building-base-profile-spec.md` (the FLAT / STEPPED / SLOPED / FEET read, §1) and its owner rulings 10-01k.

## §0 Facts (KASE capture at 8d141e68f, `--replay --from classify`)

| # | fact |
|---|---|
| 1 | `Objects/test.obj` (OBJECT at 39.227247849, -106.868720916, hdg 249.39): 248 x 48 m roof on columns; 258 of 274 lowest-per-metre cells on ONE plane `y = -0.097 - 0.01900 x + 0.00014 z` (rms 0.001 m); feet fall 4.7 m toward bearing 339 deg. `base_profile`: **SLOPED 1.90 %**, floor fraction 0.0014 (posts). |
| 2 | Its §16g clusters `unit:7#0..#5` carry an EMPTY composed profile (`cluster_profile.profile_job` exits on a member with no base PLANES), so `pad_blocks.unit_base` reads `""` for it — the SLOPED verdict reached no pad. |
| 3 | Its pads `building8..12` (3,803 / 1,200 / 595 / 774 / 779 m2) were §4 CONFORMING held flat; `building8` was also a #798 DOOR PAD (one `Flat`). Built: all five at 0.000 % except `building11` (1.01 %, the warned release); terrain minus authored feet spread **4.39 m** under `building8`. |
| 4 | Apron within 40 m of the canopy: 26 of 43 edges under 0.3 % ("too flat"), 3 over 1.5 % to **5.67 %** ("too steep") — the owner's read. |
| 5 | KASE's eleven other SLOPED members fit at rms 0.10-0.28 m (uneven contact sets, not planes). Certified airports: KEGE 1 / BIKF 3 / LGAV 6 / OMDB 8 SLOPED members, **0** clusters with an admissible plane (LGAV `Trench_03` fits at 0.001 m but is no pad cluster). |

## §1 What landed (19o (1), the planar sloped base)

* ONE derivation `planar/pad_base_slope.sloped_pads`: a pad whose covering cluster (>= half the pad) is made of SLOPED members fitting within `[base_profile] sloped_pad_rms_m` (0.05 m, the 12y pavement bar), all placements agreeing, takes the member's gradient rotated by the heading (`obj8_grade._place_matrix`), magnitude capped at `[common] pavement_max_grade` (5 %).
* `constraints/pad_relief.pad_slope_offsets`: the plane per pad vertex, merged into `pad_relief_offsets` (so the plate target, the sidecar `pad_relief`, `verify/pads` and the census read it).
* `planar/platform.platform_split`: a sloped pad is never HELD flat (no unit plan, no §4 conforming hold) — the hold machinery (`hold_sets`, `no_step.hold_interval`, `platform_records`, the frontage warning) is untouched.
* `constraints/pads`: the plate's cap-0 pairs carry the plane and LEAD the rim two-sided (a Diff prices differences, so the apron's level wins and its tilt is drawn to the plane); the 1 % ceiling is measured from the plane under its own head `structures.building_pad authored base plane ceiling` — hard, pad tier, NOT in `conforming_hard_rulings`, so stage 1 grades the apron rim into it; hard one-plane rows (`platform.coplanar_rows`, head `platform plane`).
* `constraints/door_pad`: a sloped-base pad is not a #798 door pad.
* `tools/check_grade._check_pad_airside_weld`: reads a pad whose every node carries a PLANAR relief on that plane (`_planar_relief`); per-foot relief stays raw (12u).

## §2 STEPPED (19o (1) second sentence) — NOT built; spec

The base-profile spec §2 (1)/(3) (one pad per base plane, `<ref>/p<k>`, a hard plane-offset `Diff` between datum columns, a 0.5 m `base_step` riser strip; owner 10-01k Q2-Q4) is the design and stays it. What exists today: `planar/low_level` mints a LOWER LEVEL only for a held pad whose storey edge meets a lot (#809/#1101); LGAV carries 160 STEPPED clusters and BIKF 33 with **0** `/p<k>` plane pads. Work list (one lane, effort high): (a) `cluster_profile` publishes the composed profile (it does for planes); (b) mint plane pads per §2 (1) in `planar/platform` beside the sloped exclusion of §1; (c) C8/C10/C11/C13/C15/C17 of the base-profile census; witness KASE site 2 (`FireStation_7.obj`, lot +3.9 m over 6,394 m2, today floating 2.7 m) — the hillside stepped case; HECA T3 is the risk control (must stay ROOF after composition).

## §3 POSTS (19o (2), with 19l) — NOT built; spec

A FEET-verdict body (columns, no floor: floor fraction < `roof_support_fraction`) gets NO SLAB: its cluster pad is not minted (19l's ground plan already excludes lifted parts; the posts case is the at-grade column body), the apron/ground runs under it at its own law, and the terrain follows the FEET: the existing per-foot relief (`pad_relief._foot_offsets`, nearest foot) becomes a per-foot GROUND target on the faces under the footprint (not a pad's), within the visibility bar, and 10-01k Q1's body tilt (`placement_seat_tilt`) absorbs the rest. Where the feet lie on one plane (KASE `test.obj`) §1 already gives the same surface; that is why this lane took the pad route for it. Census to run first: `geom/cluster_outline` rule 7b (19w slope pads — the KASE canopy pads exist through it; COUPLING: lane lk1fix is editing the K1 refusal in the same function), `classify/evidence._pads`, `pad_relief._foot_offsets` (seniority rules 12u/#1855/#1905), `object_stage` seat tilt.

## §4 Owner question (INTENT)

The canopy stands inside an apron whose hard cap is 1.5 %; its authored base is 1.90 %. Today the pad meets the apron at 1.34-1.50 % along the canopy (within 19o's 1 % allowance; terrain under the feet spread 1.30 m over 230 m). Should the apron under and around an object authored on a slope yield its 1.5 % cap to the object's own grade (up to 19o's 5 %), so the feet meet exactly?
