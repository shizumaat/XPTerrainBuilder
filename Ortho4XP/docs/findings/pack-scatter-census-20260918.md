# THE SCATTER CENSUS — nine airports, dry (slice S5a)

Lane `packscatter-census`, base main `c0912e54`, 2026-09-18.  Spec
`docs/specs/pack-read-once-fast-spec.md` §B.2, slice **S5a: the predicate +
the dry census, NO BEHAVIOUR CHANGE**.  Nothing in the build consults the
predicate; the wiring is S5b, after the owner answers the spec's Q1 (may
scatter shape the terrain?) and Q2 (what is a piece's seat?).

Instrument: `tools/pack_scatter_census.py` (INDEX row in the same commit,
twin `tests/auto_patch_v2/test_v2packscatter.py`).  Predicate:
`src/auto_patch_v2/airport/scatter.py`.  Thresholds: `structures.toml`
`[scatter] components_min = 64`, `component_diag_max_m = 10.0` — named law
values, no literal in the module.

**Build-time impact: NONE.**  No consumer reads the predicate; the law table
gains two keys nothing asks for.

---

## 1. THE TABLE

Every row is the airport's own pack, the DSF text dump a build would read
today, and the loader's own ±0.05° window.  "comps" are GENUINE
(thickness-gated) components — the population every consumer reads — counted
PER PLACEMENT.

| airport | pack | placements | resources | scatter res | scatter comps / all | share | rows ≤ (a) | pad boxes touching (b) | pads' placements touched | structure-read screen (c) | near-threshold (d) |
|---|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|
| **TNCM** | c_NLD TNCM_1_Apt | 10,024 | 367 | 34 | 87,285 / 157,403 | **55.5 %** | 349,140 | 73,976 / 87,285 (1.154 of 1.192 M m²) | 821 / 9,837 | 1 | 49 |
| **TFFG** | c_NLD TNCM_1_Apt | 6,750 | 182 | 11 | 81,525 / 123,524 | **66.0 %** | 326,100 | 76,958 / 81,525 (66,456 of 82,028 m²) | 22 / 6,663 | 10 | 20 |
| **LEMD** | Aerosoft LEMD | 4,883 | 2,470 | 41 | 10,502 / 60,916 | 17.2 % | 42,008 | 10,496 / 10,502 (36,691 m²) | 432 / 4,302 | 2 | 139 |
| **HECA** | Tai Models HECA | 10,281 | 4,779 | 57 | 10,695 / 102,047 | 10.5 % | 42,780 | 10,695 / 10,695 (104,354 m²) | 893 / 7,380 | 1 | 311 |
| **OTHH** | Aeroscape OTHH | 15,555 | 1,988 | 170 | 88,684 / 285,484 | 31.1 % | 354,736 | 80,266 / 88,684 (3.693 of 3.706 M m²) | 1,894 / 5,934 | 9 | 300 |
| **VHHH** | Tai Models VHHH | 6,240 | 763 | 5 | 1,917 / 54,928 | 3.5 % | 7,668 | 1,917 / 1,917 (34,391 m²) | 127 / 2,954 | 0 | 106 |
| **CYXY** | CYXY Whitehorse | 498 | 66 | 4 | 498 / 5,073 | 9.8 % | 1,992 | 0 / 498 (0 m²) | 0 / 431 | 0 | 8 |
| **GEML** | Aerosoft GEML | 1,458 | 78 | 4 | 1,592 / 34,063 | 4.7 % | 6,368 | 1,566 / 1,592 (785 m²) | 27 / 1,419 | 2 | 9 |
| **TFFJ** | c_FRA TFFJ_1_Apt | 5,411 | 202 | 11 | 2,717 / 49,195 | 5.5 % | 10,868 | 1,614 / 2,717 (2,776 m²) | 123 / 5,190 | 5 | 13 |

Nine of nine airports censused; none skipped.  Whole run 614 s wall, peak RSS
3.09 GB, no build, no capture, no stage, no write.

**The owner's islands are the class's customers, and the big airports are
not**: TNCM 55.5 % and TFFG 66.0 % of every placed genuine component, against
LEMD 17.2 %, HECA 10.5 %, VHHH 3.5 %.  OTHH's 31.1 % is a surprise the spec
did not have (§E: "HECA, OTHH, VHHH are S5a's") — 170 resources, 88,684
components, mostly terminal interior clutter and GSE.

### Why these counts differ from the spec's [M-new]

The spec's `attach.py` read ALL solid components and dropped every `__b`
split file; this tool reads GENUINE components (the `[basin]
min_solid_thickness_m = 0.3` gate that `ResourceCache.genuine` and
`pack_partition._build_member` apply) of the resources the CURRENT DSF
actually places, split files included, resolved through
`pack.authored_source`.  Neither LEMD nor TNCM nor HECA has a `.anchor_bak`
DSF, so the live DSF **is** what a build reads today — at LEMD that DSF
places the object-split products (`…__b0_…obj`), which is why its resource
count is 2,470 and its component count 60,916 rather than the spec's 495,439.
The share, not the absolute count, is the comparable number.

### The class, by resource (largest first)

* **TNCM** — `Objects/Flora/HillBush.obj` 41,217 (one placement),
  `Objects/Autogen/AG2_palms.obj` 24,089, `Ground/Roads/ParkingBushes.obj`
  6,869, `AG1_Palms2` 3,449, `Objects/Airport/AirportFence.obj` 1,890 (the
  LINE CLAUSE: posts small, wire runs line-shaped — the file is not a line
  object because its posts are not), palms, ferns, baggage carts, catering
  trucks, road signs, `Airport/TerminalGlass.obj` 214 (4.49 m panes — the
  named false-positive class), `Maho_Girl3.obj` 166 people.
* **TFFG** — `Tree1Foliage.obj` 60,888, `Tree2Branch.obj` 8,072,
  `Objects/Flora/HillTree.obj` 373 × 15 placements = 5,595, `ApronTrees.obj`
  3,492, `Terminal/AirEdge.obj` 1,366, bushes, cars.
* **LEMD** — the T4 struts / glass exactly as the spec named them:
  `Terminal4_green-LEMD23__b0` 1,032, `Terminal4_yellow-LEMD11__b1` 1,013,
  `Terminal4SAT_Yellow-LEMD23__b0` 838, … 41 resources, every one a terminal
  sub-file.  **At LEMD the class is entirely false positives** under §B.2 (3)'s
  meaning — it is the T4 population, not vegetation.
* **OTHH** — `Terminal_Interior_Clutter_15__b0` 4,992 and its siblings, GSE,
  jetways (`OTHH_Jetway_Type4.obj` 247 comps × 18 placements).
* **CYXY** — 4 STOCK LIBRARY resources only (`leg_lugg_cart_group`,
  `leg_lugg_train_group`, `fuel_truck_large`, and a 16 m European tower at 73
  components / 8.67 m: a false positive, and the only building-shaped one).

## 2. (a) THE LP FOOT-ROW EXPOSURE — an UPPER BOUND, stated as one

The census reports `scatter parts × [rebake] foot_samples_max` (4).  Today
every non-line scatter member is an eligible group whose ground parts state
target rows priced at `pad_flat` (the 11q law) — so the bound is the number
of rows that CANNOT survive Q1 = "no", and the measured number is somewhere
under it.  TNCM ≤ 349,140 rows, TFFG ≤ 326,100, OTHH ≤ 354,736, LEMD ≤ 42,008,
HECA ≤ 42,780, VHHH ≤ 7,668, TFFJ ≤ 10,868, GEML ≤ 6,368, CYXY ≤ 1,992.

**NOT the measured count.**  The measured count is
`planar/group.derive` → `constraints/foot_rows` per airport (bodies ×
feasible × on-sheet), and that is a stage run this slice did not make (§5).

## 3. (b) THE CLUSTER-PAD EXPOSURE — a named BOX PROXY

Per airport: the placed plan-BOX of every scatter component against the
placed plan-BOXES of every non-scatter COMPONENT (not placement bounds — a
terminal's bound swallows its apron and every bush on it would read
"touching"), `[placement] footprint_touch_m = 0.5`.

What it says: at TNCM 73,976 of 87,285 scatter boxes (1.154 M of 1.192 M m²
of box area) come within 0.5 m of a non-scatter component, and they reach
**821 of 9,837** other placements; at OTHH 1,894 of 5,934; at HECA 893 of
7,380; at LEMD 432 of 4,302; at CYXY **none at all** (its four stock clutter
files stand clear of everything).  Those placement counts are the upper bound
on "pad outlines that would change".

It is a PROXY in both directions: a component's box contains its ring (so a
box touch may not be a ring touch — over-reports), and the cluster chains
transitively through bodies (so one lost bush can move a pad whose own box
the bush never touched — under-reports).  The measured delta is the cluster
pass's, i.e. S5b's.

## 4. (c) THE STRUCTURE-READ SCREEN — 30 named resources in nine airports

For every would-be-scatter resource the census runs the per-RESOURCE gates
each structure reader passes through: authored depth below the object's own
zero against `[basin] admission_depth_m` (2.5 m — the floor-witness / shell /
door-well / sunken-road / wall-corridor population), `skirt.is_skirt`,
`deck_signature.elevated_deck`, HARD / HARD_DECK triangles (the predicate
already refuses those), and `line_object.is_line_object`.  A hit is a
CANDIDATE, not a proven consumer: the readers also test the geometry against
the DEM, the plate normal, the roof fraction and the run length, none of
which a parse can answer.

| airport | hits | what they are |
|---|---:|---|
| TNCM | 1 | `Objects/Flora/HillBush.obj` (41,217) — authored below −2.5 m |
| TFFG | 10 | all flora + `Terminal/AirEdge.obj` (1,366, also `skirt`), `Vehicles/Car3.obj` (`skirt`) |
| LEMD | 2 | `OldTerminal_FSX-AES_SAFE09__b4` (65, `skirt`), `T4STower…SWbaume__b0` (179, deep) |
| HECA | 1 | `Airport/Hangar_Tower/metal_blue__b0` (89, `skirt`) |
| OTHH | 9 | **6 read `elevated_deck`** — incl. `Terminal_Parking_Parking-Left/Right_000` at 6,735 components each — plus `Jetway_Type4` (247 × 18) deep, 2 ILS docks |
| VHHH / CYXY | 0 | — |
| GEML | 2 | `GEML_3dPlants.obj` (1,221), `GEML_Clutter.obj` (96) — both deep |
| TFFJ | 5 | `buoy_net` (deep + skirt), `fences1`, `lot_palms`, `terminal3`, `terminal_details` |

**Two findings S5b must carry:**

1. **`below_admission_depth` is the flora signature, not a structure
   signature.**  Trees and bushes are authored with their root ball metres
   under y = 0 so they sit into the ground.  A depth gate alone therefore
   does NOT separate a bush from a basement, and S5b must not try: the
   readers' own DEM-relative tests do.  This is why the census reports the
   screen and not a verdict.
2. **OTHH has six resources that read SCATTER *and* `elevated_deck`**, two of
   them 6,735 components.  §B.2 (2)'s exemption ("…the placement is not
   deck-family, plate-seated, structure-seated or a basin member") is the
   caller's, applied in `_build_member` — and `_build_member` reads
   `elevated_deck` BEFORE the line verdict today.  S5b must order the scatter
   test the same way or OTHH's car-park decks change class.  This is the one
   place the census found where the predicate alone would be wrong.

## 5. (d) NEAR-THRESHOLD — the numbers the thresholds should be judged on

Resources with components in [48, 96] (0.75–1.5 × `components_min`) or a
component diagonal in [8, 12] m (0.8–1.2 × `component_diag_max_m`): TNCM 49,
TFFG 20, LEMD 139, HECA 311, OTHH 300, VHHH 106, CYXY 8, GEML 9, TFFJ 13.

What moving a threshold would do, from the rows:

* **`components_min` 64 → higher** loses almost nothing that matters and
  drops the small false positives: CYXY's 73-component tower, TFFJ's
  `buoy_net` (69), GEML's `GEML_Clutter` (96), OTHH's GSE stairs (69).  The
  heavy files are 1,000–61,000 components; nothing between 64 and ~200 is
  worth having in the class.
* **`component_diag_max_m` 10 → lower** is where the false positives live.
  The LEMD T4 population sits at **8.3–9.4 m**, OTHH's jetways at 9.89 m,
  TFFG's `ApronTrees` at 9.85 m, TNCM's palms at 7.4–8.8 m.  A 10 → 8 m move
  would take out LEMD's whole class and OTHH's jetways AND TFFG's apron trees
  — the discriminator is not size.  A 10 → 12 m move admits HECA's
  `Jetway_metal_03` (11.49 m), VHHH's jetway frames (10.88 m) and TNCM's
  `new_BoatBar1` (11.36 m).
* Nothing in the corpus sits ON either threshold; the nearest are HECA's
  `apron_T1` at 9.99 m (18 components, not scatter on count) and TFFG's
  `ApronTrees` at 9.85 m.  **(64, 10 m) is a stable plateau** — the
  population does not change under ±20 % of either number except as listed
  above.

## 6. WHAT THIS SLICE DID NOT MEASURE

* **The `structures.json` DRY PAIR** (gate skipping scatter vs not, LEMD /
  HECA).  It needs the S5b wiring — which is a behaviour change this slice is
  forbidden to make — and a `planar --stage structures` run per airport
  (LEMD 378 s / 4.8 GB).  §4's screen is the static half of the same
  question.
* **The MEASURED foot-row count and the MEASURED pad-outline delta** (§2,
  §3): both need the planar group / cluster stage.
* **TNCM and TFFG have no registered capture** (spec §C: the capture dies at
  `wall_corridors.py:289` until §51 merges), and every frame in
  `frames.py list` for LEMD / HECA is `[MISSING]` (purged scratchpads), so
  there was nothing to replay from either.
* The `[scatter]` thresholds were judged against the corpus (§5), never
  FITTED to it.
