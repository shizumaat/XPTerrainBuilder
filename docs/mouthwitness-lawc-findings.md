# Scout `mouthwitness` — Law C general witness (RULINGS 2026-10-05f, issue #396)

## VERDICT (first)

**The owner's witness, taken literally ("an object stands across the mouth between the arms"), does NOT separate the cases — but a COMPOSED general rule, every clause of which is already law or is the owner's witness read against the whole pack, reads OTHH 9 / everywhere-else 0 on the entire registered capture corpus with no airport key.**

Three facts the brief's framing did not have (all MEASURED on the registered captures, arm `scratchpad/mouthwitness/mw.py`, affordance forced on in-process, no law-file edit, no build):

1. **The OTHH-43 vs LEMD-cargo-57 conflict of 09-10ap no longer exists.** Owner RULINGS 2026-09-27a (3) ratified the kerb test (d) `[cutout.wall_corridor] max_wall_height_m = 3.0` (`wall_corridors.py:836-844`). Under today's law with the key forced on, LEMD's cargo docks — CGVRW, NEWCO, FLEDI, EAT/EATzwei, GAVIA 0/3 and 1/3, LEMD64, LEMD70/73/79 — are ALL refused by (d): 43 candidates, own-wall height 4.55–31.65 m. OTHH's accepted set today is 9 corridors (DutyFree_003 ×3, Terminal_Base_2_5 underpass, Terminal_Base_2_1 bays ×5; own 0.40–1.40 m), exactly the brief's "9 corridors (bay 7, level 4)".
2. **The literal mouth witness reads the cargo docks as OPEN.** Of the 43 (d)-refused LEMD cargo candidates, 39 have NOTHING across at least one mouth (floor to grade+4 m, any placement, within 2 m) — e.g. NEWCO 35/38/39/40/41/43/44/47: 0.00 cover at both ends; CGVRW 18/19/22: 0.00 both ends. Aerosoft models them as two parallel foundation sheets with open ends, not as a closed dock. The witness as pictured is not in the geometry; (d) is what separates them, and (d) is already ratified law.
3. **The LIVE residue with the key forced on everywhere is 61 false corridors at three airports**, none of them a cargo dock: LEMD 33 (31 `grass_FSX-LEMDgrass` buried grass-billboard lattices, 1 `Cargo-GAVIA` 0/0, 1 `Sim-wings-SWbaume`), KASE 26 (one UUID-named city-block object `b56dfde4-…-359f7b320fda_{1,2,3,4}` in downtown Aspen, 3.9–4.4 km from the field), TFFJ 2 (`industrial_1_1`, 560–594 m off the field). Every other registered capture yields zero live candidates.

### Confusion table — population A: today's law, key forced ON everywhere (positives = OTHH's 9, negatives = the 61 live candidates at LEMD/KASE/TFFJ)

| clause | OTHH kept (of 9) | LEMD kept (of 33) | KASE kept (of 26) | TFFJ kept (of 2) | TP / FN / FP / TN |
|---|---|---|---|---|---|
| **W1** owner's witness, literal: some end has nothing across it BELOW grade (floor+ε .. ground−ε), any placement, ≥ 50 % of the mouth clear | 9 | 32 | 23 | 2 | 9 / 0 / **57** / 4 |
| **W1s** W1 AND nothing across that end AT grade (ground+ε .. ground+4 m), horizontal slabs included | 9 | 31 | 5 | 0 | 9 / 0 / 36 / 25 |
| **W3** the arms run out from a BUILT structure: a deck plate over the trench (the existing headroom witness) OR an above-grade wall ≥ 1 m over ground closing an end | 9 | 2 | 24 | 2 | 9 / 0 / 28 / 33 |
| **FIELD** the open mouth stands on the field: within `[tunnel] mouth_standoff_m` 150 of the classified cover (the mapped-tunnel law, spec §29 (1), RULINGS 12r/12t/12aa) | 9 (0.0–9.6 m) | 33 (0–135.5 m) | 0 (3,900–4,370 m) | 0 (560–594 m) | 9 / 0 / 33 / 28 |
| W1s ∧ W3 | 9 | 0 | 3 | 0 | 9 / 0 / 3 / 58 |
| **R = (d) ∧ W1s ∧ W3 ∧ FIELD** | **9** | **0** | **0** | **0** | **9 / 0 / 0 / 61** |

Population B (the 10ap framing, kerb test (d) neutralised in-process — OTHH 44 corridors vs LEMD 76): W1 keeps OTHH 44 / LEMD 75; W1s 40 / 69; W3 39 / 26; W1s∧W3 35 / 19. No mouth clause reads 43/0 there either — the cargo docks are open-mouthed sheets. (d) is the clause that reads them, and 27a (3) already made it law.

Also measured: the mouth witness alone would ADMIT the OTHH corridors the owner's #12 read rejected (site a 25.2575296, 51.6120308 = `TerminalRoads_03_004` candidates 11–14 at ~30 m: 0.02/0.02 cover both ends, walls 9.78 m; site b VCN_004: 0.00–0.15 below). So W1/W1s cannot REPLACE (d); it composes with it.

---

## 1. THE WITNESS, AS GEOMETRY (what the engine already has)

Everything below is read in `read_wall_corridors` (`Ortho4XP/src/auto_patch_v2/airport/wall_corridors.py:565-1015`) on a CANDIDATE PAIR after rule 4 (`:846-886`), from objects the pair loop already holds; nothing is re-derived downstream (RULINGS 2026-08-30l: one derivation site, no consumer vetoes).

* **ARM** = one `WallBand` of the pair (`wall_geometry.py:41-60`): a genuine component of vertical faces authored ≥ `min_wall_depth_m` 1.0 under the object's zero, reaching within `basin.contact_band_m` of it, plan length ≥ `min_wall_length_m` 5. The pair's inner faces are `tunnel_walls.read_wall_lines` kind "II"; the stations `stations_along` (`:708-709`). Arms of unequal length: the corridor is the OVERLAP window along the axis (`_overlap_along`, `:653`); the longer arm's excess is not part of the corridor and never was.
* **MOUTH SEGMENT** = `end_line(k)` (`:847-855`): the segment across the trench at the last station of end k, from the left inner face to the right inner face (W = `half_l + half_r`, 6.1–19.4 m measured). This is the segment the existing end-cap test already reads (`_end_cover`, `:359-394`). Its window along the axis is the flat buffer of `tunnel.object.end_cap_open_m` 2.0 (existing).
* **"AN OBJECT ACROSS THE MOUTH"** (the new reading): ANY triangle of ANY placement of the pack (every family, stock-library resources excluded as the reader already excludes them, `:609`) whose plan (vertical face → its plan segment; other faces → their plan polygon) intersects the mouth window, projected onto the mouth segment; CLOSED when the union of projections covers ≥ `end_cap_cover_min` 0.5 of W (existing value). Two height bands, in the SEATED frame (`_seat_base`, RULINGS 10ad):
  * BELOW-GRADE band: `floor_z(k) + ε .. ground_z(k) − ε` — the trench opening a vehicle would drive through. Family geometry here is what the existing rule 4 reads; OTHER placements here are the owner's "object across the mouth".
  * AT-GRADE band: `ground_z(k) + ε .. ground_z(k) + min_headroom_m` (3.5; my arm used 4.0 — results identical) — a wall, door, fence or GROUND SLAB standing across the mouth at grade. Above `min_headroom_m` is a canopy/deck: open.
  * ε = `[rebake] plate_seat_min_delta_m` 0.05 (the smallest step the engine treats as visible, 08u (1)); my arm used 0.10. SENSITIVITY (measured): LEMD GAVIA 24's closer is the apron slab object `Cargo-LEMD63` whose top stands 0.10–0.13 m over the DEM at the mouth; ε must stay ≤ 0.1 or that mouth reads open and GAVIA 24 becomes a false corridor. Do not use `min_distinct_spacing_m` 0.5 here.
* **OPEN corridor (needs a ramp)** = at least one end whose BELOW and AT-GRADE cover are both < 0.5 (W1s). A level corridor needs one open end per half as today; a bay one.
* **W3 — "walls running OUT FROM the building"**: the corridor touches a built structure: the existing headroom witness returns a plate (`_headroom`, `:483-562`, `plate_plan is not None`) OR an above-grade face (z_max ≥ ground + 1.0 m, ≥ 50 % of W) closes an end. Both are already computed for the candidate; W3 adds no geometry. (Equivalent formulation with an existing accessor: the trench ⊕ `end_cap_open_m` intersects the family's `obj8.above_grade_footprint` — not measured in this form.)
* **FIELD**: the open mouth point lies within `[tunnel] mouth_standoff_m` 150 of the classified cover — the identical test §29 (1) applies to mapped-tunnel mouths (`planar/structures.py:187`, `structure_approach.py:415-544`). Reuses the cover polygon; no new value.

**Degenerate cases (ruled by the reading above):**
| case | reading |
|---|---|
| one arm only | no pair (rule 2 unchanged) — nothing. |
| arms of unequal length | mouth at the overlap window's end; the longer arm's run-on is ignored (as today). |
| roll-up door mesh / fence / kerb / step across the mouth | a face in the AT-GRADE or BELOW band → CLOSED if it covers ≥ 50 % of W. A kerb 0.15 m high at grade covers the band (its z-range crosses ground+ε) → CLOSED; if that is not wanted, raise the at-grade band's floor to the kerb height — an owner value, not measured here. |
| jet-bridge across the mouth | its underside is above `min_headroom_m` → open; its supports (legs) cover < 50 % → open. |
| canopy / deck overhead, open at grade | OPEN (W1s reads only up to `min_headroom_m`). Measured at OTHH `TerminalRoads_Parking_004` 7–10 and `VCN_004` 28/30: below 0.00–0.15, above 1.00 (decks at ground+2..+4.4 m) → open at grade; these are (d)-refused anyway. |
| ground slab object at grade across the mouth | CLOSED (the pack says ground is there). This is exactly LEMD GAVIA 24 (`Cargo-LEMD63`, 0.82 of W) and SWbaume 117 (`Ground-FSX-LEMD85` fills the trench 1.00 and crosses both mouths). |
| corridor open at both ends | a level corridor (two halves) as today, provided W3 (a deck over it — OTHH's underpass `Terminal_Base_2_5`, headroom 4.31) — two bare walls under open sky with open ends are a ditch/fence line → refused by W3 (LEMDgrass, 31 of 31). |
| closed at both ends | refused by rule 4 as today ("sunken yard"; NLWF's 14 house foundations, KASE 2,073 pairs). |
| garage ramps | §4 below. |

Values table (all existing except none new): `end_cap_open_m` 2.0, `end_cap_cover_min` 0.5, `min_headroom_m` 3.5, `plate_seat_min_delta_m` 0.05, `mouth_standoff_m` 150, `max_wall_height_m` 3.0, the wall-at-end bar 1.0 m = `basin.contact_band_m` (a face reaching a full contact band over ground is a wall, not a kerb cap). NO new law value is required; a lane may want a named alias key per value for readability (the spec author's call).

---

## 2. THE MEASUREMENT

**Instrument.** `scratchpad/mouthwitness/mw.py` (replay arm off a capture; loads the pickle, `Law.for_airport(icao)` with `tables.airports[icao]` replaced in-process so `kerb_wall_corridors=True`, `max_wall_height_m` set to 1e9 in-process so every candidate reaches rule 4 while its measured own-height still states the (d) verdict; wraps the module's own `_floor_profile/_seat_base/_end_cover/_trench/_headroom` to capture each candidate's mouth segments, seated floors and trench; then reads every placement's triangles around each mouth). `conf.py` (confusion counts), `field.py` (distance of live mouths to `cap["cl"]` cells), `tab.py`. Per-candidate JSON per airport beside them. Second use → promote to `tools/` with an INDEX row (the `wc_arm.py` precedent).

**Captures used (all registered, all EXISTING):** OTHH `frames/perfB362/OTHH.pkl` (base 56e67443, 2026-10-04); LEMD `frames/sheetchain/LEMD.pkl` (base 098743cd, 2026-09-28 — the newest LEMD capture; 7 days older than main); KASE/NLWF/KCLT/CYXY `conc333/*_main28500ecf.pkl` (2026-10-04); TFFJ/GEML `surfacesettle2` (be2dfd43); HECA `rebake362`; SPJC `fac334/SPJC_r4`; SPLP `splp144`; KGRK/KRDU `tx154`; KHDN `cwcb154`; VMMC `shoredecide`. NOT measured: TNCM and TFFG (the registry's newest entries are a `.tgz`/`.prof`, no pickle), VHHH, HEAZ, KMCI (no capture registered).

**Reader totals (measured, (d) neutralised / today's law):** OTHH 36,019 objects read 189 s, 139 families, 399 bands, 69 pairs, 66 candidates, 44 corridors (14 bay, 60 level halves) / **9**; LEMD 2,498 objects, 3 families, 7,174 bands, 132 pairs, 122 candidates, 76 / **33 live**; KASE 4,610 objects, 2,140 families, 11,772 bands, 3,695 pairs, 964 corridors / **26 live** (2,073 pairs closed both ends, 938 (d)-refused at 3.61–10.6 m); TFFJ 5,411 objects, 4 families, 41 pairs, 17 / **2 live**; GEML 2 candidates / 0 (one garage-class, refused "shallow end 3.18 m under ground"); NLWF 14 / 0 (all closed both ends); HECA 4 bands, 0 pairs; KRDU 51 bands, 0 pairs; CYXY, KCLT, SPJC, SPLP, VMMC, KGRK, KHDN: 0 bands.

### 2a OTHH — the 9 corridors admitted today (ground truth = accepted; RULINGS 27a (3) + #12 read on the new pack)

| id | resource / bands | site | arm overlap L × W (m) | depth (m) | own wall (m) | headroom plate | end 0: below / at-grade cover (closer) | end 1: below / at-grade (closer) | verdict | field dist |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Qatar_DutyFree_003 3/5 (bay) | 25.283218, 51.604172 | 7.3 × 12.17 | 1.37 | 1.40 | 5.28 | 1.00 / 1.00 (DutyFree_003 z 2.6–4.4; _004/_005 above) | **0.00 / 0.00** | OPEN | 3.3 m |
| 1 | Qatar_DutyFree_003 8/7 (level) | 25.283203, 51.603764 | 19.7 × 12.79 | 12.21 (pit) | 1.30 | 12.21 | **0.00 / 0.00** | **0.00 / 0.00** | OPEN | 0–6.3 |
| 2 | Qatar_DutyFree_003 5/7 (bay) | 25.283230, 51.604033 | 20.0 × 12.17 | 1.37 | 0.40 | 5.12 | **0.00 / 0.03** | 1.00 / 1.00 (DutyFree_003) | OPEN | 9.6 |
| 20 | Terminal_Base_2_5 432/433 (level, the 08u underpass) | 25.266210, 51.611335 | 77.8 × 9.85 | 1.89 | 0.59 | 4.31 | **0.00 / 0.00** | **0.00 / 0.00** | OPEN | 0.0 |
| 21–23 | Terminal_Base_2_1 2044/2056, 2143/2161, 2256/2257 (bays) | 25.262927, 51.612381 · 25.263446, 51.612201 · 25.264815, 51.611645 | 6.0 × 9.86 | 1.39 | 0.59 | 5.27 | **0.00 / 0.00** | 1.00 / 1.00 (Terminal_Base_4 wall z 2.61–6.16, i.e. 2.2 m over ground) | OPEN | 0.0 |
| 24–25 | Terminal_Base_2_1 2729/2732, 2760/2812 (bays) | 25.264478, 51.612396 · 25.263927, 51.612659 | 6.0 × 9.86 | 1.35 | 0.63 | 5.23 | 1.00 / 1.00 (Terminal_Base_4) | **0.00 / 0.00** | OPEN | 0.0 |

Void occupancy (solid between the arms, floor+0.3 .. ground−0.2, trench shrunk 0.3 m): 0.00–0.10 at all 9. All 9: W1 ✓ W1s ✓ W3 ✓ FIELD ✓ → kept; records untouched.

The other 52 OTHH candidates reaching rule 4: 35 (d)-refused (TerminalRoads_02/03/Parking_004 5.91–9.78 m, Terminal_Parking_VCN_004/006 3.52–9.82, Bridge_02/04/06 4.52–9.48) — of these the mouth reading is OPEN at 30 (e.g. TerminalRoads_03_004 11–14 at site a: 0.02/0.02 both ends; Bridge_06 ×16: floor 2.5–2.9 m ABOVE the DEM in the seated frame, nothing across); Bridge_04_LOD0_003 ×4 closed both ends; 5 Bridge_03_LOD0_003 own 2.56 refused on headroom 0.12–1.37; 12 refused by rule 4/5 as today. Nothing changes for them under R.

### 2b LEMD — key forced on (ground truth: all refused by the owner's read; today 0 by the key)

Live under today's law (33):
| group | n | sites (first/last) | arm overlap / W / depth | own wall | headroom | mouths | W1s | W3 | FIELD | R |
|---|---|---|---|---|---|---|---|---|---|---|
| `grass_FSX-LEMDgrass` buried grass-billboard lattice (vertical quads ~1 m tall, components wholly at/under the object's zero: own −0.60..+0.04; a 10.2 × 6.1 m grid repeats — idx 78/80/82/84/97/98 read identical 0.96/0.15 covers) | 31 | 40.532111, −3.577619 … 40.456397, −3.561072 (grass belt N of 18R/36L and SE cargo kerbs) | 4.9–103.8 / 6.1–19.4 / 0.27–2.24 | −0.60..0.04 | none (open sky) | open: family quads cross 0–0.96 below, 0.00 at grade | 31 OPEN | 0 (no deck, no wall) | 17–136 m (inside 150) | refused by W3 |
| `Airport_Cargo-GAVIA` 0/0 bay (24) | 1 | 40.458445, −3.577556 | 15.9 / 11.7 / 1.18–1.37 | 2.29 | 3.73 | end 0 closed by GAVIA wall; end 1 below 0.00 / **at grade 0.82 by apron slab `Cargo-LEMD63` (top 0.10–0.13 m over DEM)** | CLOSED | ✓ | 0–1.8 m | refused by W1s |
| `Sim-wings-SWbaume` 135/163 (117) | 1 | 40.491095, −3.568335 | 5.5 / 8.1 / 6.7–8.0 | 2.36 | none | both mouths crossed by `Ground-FSX-LEMD85` ground slab (1.00) + `LEMD03` 0.78 at grade; void occupancy **1.00** | CLOSED | ✓ (wall at end) | 0 m | refused by W1s |

(d)-refused but otherwise admitted (43 — the owner's cargo docks): CGVRW ×17 (own 4.60–31.65; mouths 0.00/0.00 at 11 of 17 at both ends, the rest one end closed by the shed's own 6–10 m wall), NEWCO ×9 (6.63–10.45; 7 of 9 open BOTH ends), FLEDI ×2 (11.2; bays, open end 0.00), EAT/EATzwei (17.5/18.6; bays), GAVIA 0/3 and 1/3 (9.41/10.83; 23's open end is closed at grade by `LEMD63` 1.00, 26 open 0.00/0.62), LEMD64 (10.46; open both), LEMD70 ×2, LEMD73, LEMD79 ×5 (4.55–24.0), LEMDzaun ×2 (3.78; fence, void 0.98 / mouths 0.95). W1 OPEN at 39 of 43. Void occupancy 0.00–0.02 at every cargo dock: no dock body between the arms in Aerosoft's geometry either.

Refusals with (d) neutralised (56): 39 closed both ends, 9 not two readable bands, 3 authored above zero, 2 headroom, 1 max_authored_grade 328.6 %, 1 garage "shallow end 1.3 m under ground".

### 2c KASE and TFFJ (nobody tuned anything here)

KASE 26 live (`b56dfde4-95de-48c2-afa2-359f7b320fda_1/_2/_3/_4`, with `_5`/`_7` as closers — a multi-storey city-block object at 39.1889–39.1919, −106.8184–−106.8234, i.e. downtown Aspen; walls 1.7–10.3 m under zero, own 0.00–3.00 exactly at the (d) bar, decks over 24 of 26 at 3.7–10 m). W1s keeps 5, W1s∧W3 keeps 3: **3105** (39.191344, −106.819583; 19.5 × 10.3 m, 9.9 m deep, one end wholly open, other closed by `_2` wall z 2395–2405), **3131** (39.189304, −106.819453; 10.3 × 8.9, 3.1 m, bay under a 7.2 m deck), **3161** (39.190352, −106.819609; 22.2 × 10.7, 7.0 m, bay). All 26 mouths stand 3,900–4,370 m from the classified cover → FIELD refuses every one. These three are the residue the owner should look at in the sim if FIELD is not adopted.

TFFJ 2 live (`industrial_1_1` 14/14 at 17.902721, −62.852342 and 30/30 at 17.903018, −62.852148; 6.8 × 7.8 m, 2.5–7.1 m deep, own 2.04, decks 5.6/8.95): open below at one end but a 6.3 m facade crosses it at grade (above 1.00) → W1s CLOSED; mouths 560–594 m from the cover → FIELD refuses too. (15 more `industrial_1_1`/`airport.obj` pairs are (d)-refused at 4.03–6.3 m.)

Zero-candidate airports with a registered capture: CYXY, HECA, KCLT, SPJC, SPLP, VMMC, KGRK, KHDN, KRDU (0 pairs), NLWF (14 pairs, all closed both ends), GEML (2 pairs: one garage-class refused, one closed both ends 82 %/81 %).

---

## 3. THE RULE, ITS SITE, THE CENSUS, THE DELETION LIST

**Rule R** (admission, after rule 5, one site: the pair loop of `read_wall_corridors`, `wall_corridors.py:920-939`, replacing the affordance gate at `:693-697`): a Law C candidate is ADMITTED iff (a) authored depth [existing], (d) kerb test [existing, 27a (3)], rule 4 has ≥ 1 open end [existing], rule 5 headroom [existing], **and** W1s: that open end has no pack geometry of ANY placement across the mouth segment in the below-grade or at-grade band (≥ 50 % of W within `end_cap_open_m`), **and** W3: the headroom witness returned a plate OR an above-grade wall closes an end, **and** FIELD: the open mouth lies within `mouth_standoff_m` of the classified cover. `stats.admission` prints each clause with its closer (resource, placement, cover fraction, z band) per candidate — the same line format as today.

Implementation note (not built): W1s needs the whole pack near a mouth — an STRtree over `PlacedObject.plan_bbox` (exists) then `cache.component_bounds` per hit, as `_headroom` already walks members. My unindexed arm read 61 OTHH candidates × 5 queries over 36k placements in 17 s; indexed, for 9 candidates, estimated < 0.5 s (ESTIMATE; the lane measures per `ab-time`). FIELD needs the classification at structure time: `read_wall_corridors(…, classification=…)` already takes it (`:566`) and `planar/build.py:223` has it; the cover polygon is the one `structure_approach.py:504` grows for §29 (1) — reuse it, do not rebuild it. HARD LAW §6 statement: expected under 1 % of the 60 s budget; must be measured, not claimed.

**Consumer census (RULINGS 2026-08-30l)** — R only REFUSES candidates; an admitted record's fields are built by unchanged code, so every consumer sees the same records at OTHH:
| # | consumer | reads | under R |
|---|---|---|---|
| 1 | `planar/pack_reads.wall_corridor_reads` (:126-137) | the records + stats | unchanged shape; 9 records at OTHH (identical), 0 elsewhere |
| 2 | `planar/build.py:223-227` → `wall_corridor_ramps.wall_corridor_groups` (:77) | records → `Group` | same 9 groups at OTHH; none elsewhere |
| 3 | `planar/structures.build_structures` (:133), `structure_geometry.covered_start`, `structure_deck.py:186` | groups, `plate_plan` | unchanged (plate_plan is read, not re-derived) |
| 4 | `constraints/structures.py:114-115, 277, 303` (`WALL_CORRIDOR_SOURCE/ROLES`) | emitted ramp rows | unchanged |
| 5 | `pipeline/build.py:293` (seat exclusion), `:785` (report line) | `tn.source` | unchanged; LEMD/KASE/TFFJ report 0 as today |
| 6 | `airport/rebake_plan` facility members | the kerb walls as members | unchanged |
| 7 | `pipeline/publication.py:168 RAMP_ROLES`, `verify/structures`, `verify/keepout.py:104`, `verify/channel.py:178`, `emit/graded.py:28 FLOOR_ROLES`, `constraints/foot_rows.py:77`, `classify/airside_edge.py:58` | role literals | unchanged (count effect only) |
| 8 | `tools/check_grade.LAW_FAMILIES`, `harness/census.py`, `precedence.toml` `oracle_role = tunnel_ramp` | the role | unchanged |
| 9 | `planar/__main__ --stage structures` / `--kml` | `wall_corridor_admission` | gains the three clauses' witnesses per candidate |
| 10 | door wells / sunken roads / basins / tunnel objects | their own laws | untouched |

**What changes:** OTHH — nothing: the 9 records are kept with every field computed by unchanged code → patch body and rebake plan expected BYTE-IDENTICAL (CLAIM; proof = the lane's replay `--from planar --emit` body sha against today's, then ONE OTHH build). LEMD — nothing visible: 0 corridors today by the key, 0 under R (the 21 OSM road bores untouched, Law A/B unchanged). KASE, TFFJ, GEML, NLWF, HECA, KCLT, SPJC, CYXY, SPLP, VMMC, KGRK, KHDN, KRDU — 0 corridors, identical to today. Sim: no change anywhere on the corpus.

**Deletion list:** `law/airports.toml` `[OTHH]` table (the `kerb_wall_corridors` key; the file and `airports_schema.load_airports` stay only if `Affordances.group_span_max_m` (RULINGS 2026-09-11i, unnamed for every airport today) is kept — that is a second per-airport affordance 05e did not record; flag for the owner); `Affordances.kerb_wall_corridors` (`law/airports_schema.py:47`); `law/tables.affordances()` (`:74-79`) if no other reader; the gate `wall_corridors.py:673-697` and docstring `:5-14`; the VHHH refutation note `airport/object_cut.py:605-623` (rewrite as history); `tests/test_no_airport_specific_code.py:44-46` RECORDED → `set()`; `test_v2corridor.py` twins asserting "law off for"; `Ortho4XP.spec` law-table count guard and `test_auto_patch_engine_dispatch.py:429-432` if the file goes; spec §12g superseded by a new §12h (Fable). `Law.icao` stays (other readers).

**Residue for the owner (nothing misclassified under R on the corpus, but three refusals rest on ONE clause each):** KASE 3105 / 3131 / 3161 above (refused by FIELD alone); LEMD GAVIA 24 (40.458445, −3.577556 — a 1.2–1.4 m cargo kerb pit under a 3.7 m deck whose mouth is paved over by the pack's apron slab) and SWbaume 117 (40.491095, −3.568335 — a 7 m pit at the T4S tower filled by the pack's ground slab) refused by W1s alone. If the owner wants pictures, those five sites. UNMEASURED and owed before the key is deleted: **VHHH** — `object_cut.py:612-623` records `CITY2.obj` 0 → 116 corridors with the key on (2026-09-15, BEFORE (d) existed); a city block off the field is expected to fall to (d) and FIELD, but no VHHH capture exists. Cheapest: one `tools/v2_solve_replay.py --capture VHHH` (minutes to ~15 min, ONE light process) then `mw.py` + `field.py` (~1 min). Not taken.

**Next witness if R is refused:** the crest test — the band's own top ≥ 0.2 m over the object's zero (visible kerb): OTHH 9 at 0.40–1.40, LEMDgrass 31 at ≤ 0.04, GAVIA/SWbaume 2.3 (needs W1s still), KASE 21/26 pass (needs FIELD still). Weaker than W3 (a 0.36 m margin vs a presence test), listed for completeness.

---

## 4. GARAGE RAMPS

Same witness, one mouth: for the descending class the mouth is the SHALLOW end only (`:874-876`), and the existing "no mouth at grade" refusal (`shallow_depth > contact_band_m`, `:957-964`) IS already a mouth test. R applies unchanged: W1s at the shallow end, W3 trivially true (the deep end is closed by the garage, a built structure, and the garage deck is the headroom plate), FIELD as for a level corridor. **No admitted garage ramp exists anywhere on the corpus** (08u (3) still stands): GEML `GEHM_01` 180/236 at 35.301954, −2.943986 (descends 1.21 m, shallow end 3.18 m under ground — refused), one LEMD candidate (descends 3.35 m, shallow end 1.3 m under), OTHH `Terminal_Parking_VCN_004` (348.5 % step), GEML `GEML_BT1` (39.3 %). The class stays unexercised; it needs no different witness, only the one mouth.

---

## What I could not verify / did not do
* No build, no capture taken, no repo or data-repo write; everything above is a replay arm on registered captures (one process at a time, nice 5).
* Byte-identity at OTHH and the build-time cost are claims to be proven by the implementing lane (replay body sha; `ab-time`).
* VHHH, HEAZ, KMCI, TNCM, TFFG: no usable capture; VHHH is the one that matters (see residue).
* The LEMD capture is 7 days older than main (098743cd); the reader code is main's (43d3fea1).
* The sim appearance of the five single-clause sites.
* `Affordances.group_span_max_m` is a second per-airport affordance not in the RECORDED set — owner/master to rule whether 05e covers it.

Artefacts: `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/mouthwitness/{mw.py,conf.py,field.py,tab.py,OTHH.json,LEMD.json,KASE.json,TFFJ.json,…,field.json,*.log}`.
