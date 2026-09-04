# auto-patch-v2 — M4d report: below-grade cutouts admitted by the object's own geometry (RULINGS 2026-09-04i, 04f-2/3)

Lane `v2cutouts` (Fable, owner 2026-09-04i / 03h), branch `lane/v2cutouts`
off main `9af3ea54`. Files: `airport/obj8.py` (743 lines),
`planar/basins.py` (419), `constraints/structures.py` (413),
`law/structures.toml` + schema `law/model.py`, `model/structures.py`
(two additive `Basin` fields), one call-site line in `planar/build.py`
(passes the object report into the basin pass). No environment reads,
every law value from the TOML, nothing imports v1; the law twin
cross-checks the new constant against v1. Commits in §8, on the branch,
not merged.

## 0. Site first — what emits now, per airport (closing builds through `build_airport.py ICAO --engine v2`, ledgered)

**OTHH — ten cutouts** (was two): the six Drainage bowls as eight pits
(Drainage_06 is three shells, three pits) and the two Dewatering pits.
Floor = deepest genuine solid − (0.5 + 1.0) margins (08-26), R_est 3.96
everywhere (the flat inset). The owner sim-checks each row (lat,lon):

| basin | objects | floor | rim (R_est / wall crest) | area m² | floor plate m² | covered | rim open | site |
|---|---|---|---|---|---|---|---|---|
| basin:0 | Drainage_06 (000+001) | **−1.74** | 3.96 | 4,130 | 644 | 0 % | 0 / 79 st. | 25.252755,51.626279 |
| basin:1 | Drainage_03 | **−1.35** | 3.96 | 3,592 | 782 | 0 % | 0 / 55 | 25.291944,51.605865 |
| basin:2 | Drainage_01 | **−1.35** | 3.96 | 3,469 | 740 | 0 % | 0 / 40 | 25.295672,51.604575 |
| basin:3 | Drainage_02 | **−1.35** | 3.96 | 2,623 | 560 | 0 % | 0 / 34 | 25.296327,51.606389 |
| basin:4 | Dewatering_01 (002) | **−10.68** | 3.96 | 6,216 | 1,283 | 2 % | 2 / 46 (20 m) | 25.295698,51.603557 |
| basin:5 | Drainage_04 | **−1.35** | 3.96 | 2,062 | 275 | 0 % | 0 / 26 | 25.253708,51.622961 |
| basin:6 | Dewatering_02 (002) | **−10.68** | 3.96 | 4,325 | 1,145 | 2 % | 2 / 46 (20 m) | 25.252080,51.624597 |
| basin:7 | Drainage_06 (piece 2) | **−1.74** | 3.96 | 1,436 | 455 | 0 % | 0 / 18 | 25.253662,51.624418 |
| basin:8 | Drainage_05 | **−1.35** | 3.96 | 514 (under the 1,000 diagnostic) | 66 | 0 % | 0 / 10 | 25.253917,51.622124 |
| basin:9 | Drainage_06 (piece 3, 001 only) | **−1.74** | 3.96 | 155 (diagnostic) | 85 | 0 % | 0 / 6 | 25.253509,51.623991 |

The Drainage floors: shells to −3.82 / −4.20 (rendered 0.15 / −0.24),
minus the margins. The Dewatering floors: M4b read Dewatering_02 −10.74
and Dewatering_01 −9.06; both now read −10.68 — the floor keys on the
pit's own deep shell (`_LOD0_002`, −13.14 m, top +0.06) in both; M4b's
2.5 m-clip region at Dewatering_01 missed the −13.14 sump, and the
`_LOD0_001` structures (−13.20, tops +2.84 — pillars standing in the
pit) are no longer floor witnesses (rule 1: their shell rises through
the ground) and so no longer key the floor (6 cm at Dewatering_02;
"err deep" both ways is lawful under 08-26, and the residual is the
owner's sim read).

**LEMD — zero cutouts** (unchanged from M4b): every candidate refused with
its reason (§3). The pack on disk is v1-rebaked (04f-1 territory — lane
`v2rebake`); §6 shows what the RESTORED pack reads under this rule.

Census / acceptance: §4.

## 1. The admission rule (replaces `min_area_m2` and `max_covered_fraction` as refusals)

Law `structures.toml [basin]`; `planar/basins.py` docstring is the
normative text. A region is a CUTOUT when:

1. **FLOOR WITNESS** — a genuine solid component (thickness ≥
   `min_solid_thickness_m`, §2.1) carries a FLOOR PLATE: near-horizontal
   solid faces (`floor_plate_normal_y_min` = v1's
   `NEAR_HORIZONTAL_NORMAL_Y_MIN` 0.7) lying `admission_depth_m` (2.5)
   or more under the LOCAL ground (rendered at `DEM(anchor) + agl + y`
   against the DEM under the component), and its shell **tops out within
   `contact_band_m` of the ground** — neither buried under it
   (`shell_reaches_grade`, M4b) nor passing through it
   (`rim_reaches_grade`, v1's pit seed `PIT_SEED_MAX_ABOVE_GRADE_Y_M`).
   Walls without a floor witness nothing — refused by resource ("a skirt,
   not a pit"); a floor whose shell rises through the ground is a
   building standing on the pack's flat plane over real relief, or a
   structure standing inside a pit — refused by resource with its height.
2. **REGION** — the union of the witnesses' footprints **below the
   ground** (not below the 2.5 m admission plane: the cut must reach the
   shell's rim — under the 2.5 m clip Drainage_06 split into three
   pieces with its −2.51 m floor between them left uncut, and Drainage_05
   was 68 m²), closed at `footprint_close_m`, one region per connected
   part. **No area gate.**
3. **RIM DIAGNOSTIC** — ring stations (`rim_sample_step_m`) farther than
   `footprint_close_m` from the member objects' at-grade geometry (every
   component, from `contact_band_m` under the ground upward, as
   linework — a vertical wall is a line) are reported per basin, never a
   refusal: the owner-accepted Dewatering pits read 2 of 46 stations
   open (3.6 m / 2.5 m) where a buried culvert leaves the shell.
4. **COVER** — the pack's geometry above the contact band over the region
   (every solid component of every object; a roof sheet is cover — the
   thickness gate is a floor-witness gate) is reported against
   `max_covered_fraction` (diagnostic). A covered region is a **covered
   pit** (the cover is the object; the terrain still needs the cutout)
   UNLESS it is a **basement**: the floor lies wholly (a
   `footprint_close_m / 2` sliver allowed) under solid geometry the
   floor-owning objects THEMSELVES hold at or above the ground (a roof, a
   lid flush with the ground) — then no pit; the terrain there is the
   building's pad under the pad law; refused naming the pad cells.
5. **KEPT** — never the runway family; never a tunnel structure; the ring
   must have a DEM, survive the identity grid and clear its wall band by
   the gap.

Walls: crest = the ground (DEM where bare, 09-03b/04d), and where a wall
station shares a vertex with governed pavement the station's `Flat` row
is sourced as the RIM TIE (28c item 3: rim LEVEL with the apron) — the
hard row binding the whole band station to the pavement vertex it
shares (`constraints/structures.py::_wall_rows(src_tie=…)`). At OTHH no
basin wall touches pavement (all ten lie on bare inset ground), so every
crest is a DEM pin at 3.96.

## 2. Attribution before fix — the four findings that shaped the rule

1. **Bowls are shallow-sided.** Drainage_0x `_000` shells reach −2.51 /
   −2.94 with sloped sides; only 19–938 m² per member lay under the 2.5 m
   plane (regions 54–544 m²) while the shells' below-ground footprints
   are 2,062–4,130 m². The plane was the reason for the area refusal.
2. **A pit's wall and floor are separate components** (LEMD CNTRL: the
   floor slab alone read 26 of 34 rim stations open at 42–66 m). Rim and
   own-cover evidence therefore read the whole OBJECT, not the witness
   component.
3. **A building on the pack's flat plane reads as a below-grade floor.**
   LEMD's cargo terminal (NEWCO/TEJ1/LEMD64, one anchor at 596 m, local
   ground 599–600): slab 5.8 m under the local ground, walls 6–15 m above
   it, 11,684 m² of "floor plate". Under a cover-only rule it was a
   covered pit at 92 % (own cover 0 % — the roof belongs to sibling
   objects) and would have cut a 7.3 m pit under a terminal standing on
   the ground. The discriminator is v1's own pit seed: a pit's shell tops
   out within the ground band. This also retires OTHH's
   TerminalRoads_Parking ramp (top +7.96) and a LEMD radar (+36 m).
4. **The 2 m station test refuses real pits.** Both Dewatering shells
   have a 10–20 m stretch where geometry leaves the shell below grade (a
   culvert); as a refusal it killed both owner-accepted pits, so it is a
   reported diagnostic and rule 1 carries "the rim reaches grade".

Measured on the way and deleted: an object-level `at_grade` per witness
(finding 2); cover under the thickness gate (LEMD cargo sheds' single-
sheet roofs read 0 % own cover); the −2.5 m clip as the cut outline
(finding 1).

## 3. Refusals, every one with its reason (closing builds)

OTHH (23): 19 resources "genuine solids reach −2.97…−12.21 m under the
local ground but carry NO floor plate — a skirt" (DutyFree, Bridge_0x
clutter, TerminalRoads, PowerStation, Fuel, Emiri — the flat-plane
skirts of tall objects); 3 resources "shell rises through the ground"
(TerminalRoads_Parking_002 +7.96 m over a −3.18 m landing;
Dewatering_01/02_LOD0_001 +2.84 m over −12.86 m — the pillars standing
inside the two pits, whose floors the `_002` shells carry); 1 basement
(PowerStation_Clutter_000, 0 m² sliver wholly under its own solid →
pad `building4`).

LEMD (67): 60 resources with no floor plate (Cargo, OldTerminal_FSX,
Munoza, Terminal4 families: flat-plane skirts 2.5–10.7 m under the local
ground); 4 through grade (Munoza-rada +36 m, Cargo-NEWCO +6.1 m over
−3.97 m, Cargo-CNTRL +2.4 m over −12.64 m, OldTerminal LEMD43 +1.2 m);
3 basements (OldTerminal_FSX-TECH, 4 m² each, wholly under their own
solid; no pad cell).

## 4. Census and acceptance — unchanged

| | control (M4c, main) | **M4d (this lane, ledgered)** |
|---|---|---|
| OTHH oracle census (`census.py`, adjudicated / airside) | 0 / 0 (`42a253005ec9`) | **0 / 0**, all 27 families 0, `basin_floor_declaration` 0 (ten facilities declared); v2 verify 0 rows incl. `basin_floor_at_declaration` / `basin_wall_gap` 0 — artifact key `03926fc8eaa3`, body `886ec52e3af5`, 40.8 s |
| LEMD oracle census | 0 / 0 (`4d96b4d41c41`) | **0 / 0**, all 27 families 0; v2 verify 71 (`tunnel_wall_top_flat` 63, `tunnel_mouth_canonical` 8 — M4-owned, unchanged) — key `80a880945b5d`, body `0a558c92464b`, 41.6 s |
| `tunnel_portal_acceptance.py --profile OTHH` | 8 / 8 canonical, `ramp_wall_gap` 0 | **8 PASS / 0 FAIL / 12 SKIP**: 8 mouth sites all CANONICAL, `ramp_wall_gap` 0, `no_low_connector` 0, `pad_flat` 0, bore corridor walls median 96 % |

Airside rows added by ten basin faces: 0 — every basin lies on bare
inset ground (3.96), the wall crests are DEM pins, no pavement is cut
(`cells cut 0`).

## 5. Twins (`tests/auto_patch_v2/test_m4b.py`, 13; v2 suite 110 pass)

Synthetic OBJ8 fixtures: the big pit AND the small bowl (400 m², under
v1's 1,000 m² floor) both admitted, the small one noted; a pit under a
separate object's roof admitted as a covered pit (fraction reported over
the diagnostic, no refusal); a BASEMENT (pit shell + an unwelded roofed
box from +0.5 to +8 in the SAME object) refused naming the pad cell; a
BUILDING (one welded shell +8 → −5) refused "rises 8.0 m above the
ground"; a SKIRT (four walls to −6, no floor, two placements) refused by
resource "x2 … NO floor plate"; an OPEN pit (three walls) admitted with
its open length noted, the closed pit noted 0 open. Rows → solve → emit →
verify unchanged (floor pins, crest by station, OPTIMAL, sidecar
arithmetic, `basin_*` readers 0). `test_law_tables` cross-checks
`floor_plate_normal_y_min` = v1 `NEAR_HORIZONTAL_NORMAL_Y_MIN` and
records `max_covered_fraction` as a diagnostic since 04i.

## 6. The RESTORED LEMD pack under this rule (04f-1 preview, offline replay, no build)

Read through the `.anchor_bak` files (the authored state): 123
placements with below-grade solids, 355 closed regions under the old
recipe. Under this rule the flat-plane skirts are refused by resource
(no floor plate) and the terminal families by rule 1 (through grade);
the T4S ring (Ground-FSX-LEMD36 witness −7.03, rendered 588.97 against
a production DEM of 593.0 at the pit centre) is a floor witness whose
shell tops out at grade — it will emit as the LEMD basin once `v2rebake`
lands (floor ≈ 587.5, the 08-27 invariant 587.75 to the margins). Not
measured end-to-end here: the restore is `v2rebake`'s.

## 7. Build-time impact statement

OTHH v2 total 42.5 s (M4b 36.1; v2resid 28.9): the object read is
unchanged (11.4–11.8 s), the basin pass grew by the whole-object at-grade
clip of the members (≈ 1 s) and ten basins instead of two (arrangement
+0.5 s). LEMD 42.5 s in the offline replay (solve 12.8 s — the same LP
as M4c, a slower run) with 0 basins. Both under the 60 s gate; the OBJ8
parse cache stays owed.

## 8. Commits, ledger keys, not done

Branch `lane/v2cutouts`: `9ee79382` (the admission rewrite, law, twins),
plus this report. Run ledger: `tools/run_ledger.jsonl` (tree
`6149c55212a0`); artifact ledger keys `03926fc8eaa3` (OTHH_m4d),
`80a880945b5d` (LEMD_m4d); census JSON / acceptance JSON beside the
patches in the lane scratchpad.

NOT done: the restore-before-read (04f-1 — `v2rebake`; §6 is an offline
preview on the `.anchor_bak` files, not a build); a verify reader for
the rim tie (the tie is a `Flat` on a shared vertex, vacuous to read
back from the patch — no reader added); the OTHH tile mesh apply; the
five-airport sweep (orchestrator); `--runs 3` timing; the OBJ8 parse
cache; the `pipeline/build.py` log label "under min area N" (now counts
ADMITTED basins under the diagnostic — not my file, one word).

## 9. Open questions (≤ 3)

1. **Dewatering floors −10.68 (both)** vs M4b's −10.74 / −9.06: the
   floor now keys on each pit's own `_LOD0_002` shell (−13.14, top at
   grade) rather than the `_LOD0_001` pillars (−13.20, top +2.84) —
   owner sim read of the two pits decides whether the 6 cm / 1.6 m
   deepening is visible (it should not be: occluded by the shell).
2. **Drainage_06 emits as three pits** (4,130 / 1,436 / 155 m²) because
   its shells are three below-ground pieces; the 155 m² piece (001 only)
   is a sump. Merge pieces of one object family into one facility, or
   keep the object's own partition? (Kept — the object's own geometry.)
3. **Basement rule ownership**: "the same object" — LEMD authoring splits
   one terminal across sibling objects sharing an anchor; rule 1 (shell
   through grade) caught every such case at OTHH/LEMD, so rule 4 was not
   widened to sibling objects. Widen if a pack shows a pit-shaped shell
   under a sibling's roof.
