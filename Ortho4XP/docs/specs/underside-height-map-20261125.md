# The underside height map — spec for RULINGS 2026-11-25m

Fable scout `lunderside`, 2026-11-25, design only (base 236b6d838). Committed by the master; the full scout report (consumer census U1–U28 with file:line, §5 timing, §10 not-verified) is reproduced in condensed form here.

## 0. Findings

- F1. A unit's vertical reference is read three ways today: `unit_storey.unit_floor` (:128, mode of grounded parts' base near airside), `footprint_unit._wall_base` (:1108, median authored y of walled feet; the seat uses `zero = median(pad.z) − base`), `airside_floor.floor_lifts` (:122, only when airside is a storey ABOVE the zero). A building whose airside floor is a storey BELOW its zero is covered by none.
- F2. ELLX firestation is that case (2026-11-19 plan): 82 bodies, 55 at 366.34 (unit on building21), 27 at 371.41–375.07; one zero ≈ 374 fits all. 53 of 161 ELLX multi-body placements have bodies > 0.5 m apart, 12 > 3 m.
- F3. With `t` read at the airside contact, `z0 = D − t` is known when stage 1 ends (round 3's "no pre-mesh zero" was F1).
- F4. A pre-mesh one-piece seat exists: `storey_seat.seat_records` → `RebakePlan.authored_seats` + `exclude`.
- F5. The clamp exists: `geom/terrain_deck.target_at`.
- F6. Pins inside the patch are refuted; D-relative one-way rows after stage 1 (25i) and weak z = DEM follower rows (25e) work.
- F7. 18h (1): nothing that reads fine today moves.

## 1. The record

One `UndersideMap` per §16g footprint unit, derived once at the pack stage (`geom/underside_map.py`, `airport/unit_underside.py`), cached with the partition, on `Airport.undersides`, keyed by sorted placement row ids. 1 m grid in the airport metric frame (coarsened over 1e6 cells). Static solids only (no lines/scatter/contents/lights/animation/hidden terrain; fences never join). Layers: `top`, `low`, `floor` (lowest up-facing near-horizontal), `foot` (ground contact). Ground-contact plan `P` = foot cells + skin cells joined to them; overhangs (roofs, canopies, decks, jetways, spans) set no perimeter. Perimeter stations on P's boundary (and holes) carry `lo_k` (lowest outer edge), `hi_k` (floor behind it within 3 m), kind (sheet / wall / skirt / open) and `levels_k`. Below-grade interiors: P cells whose floor lies ≥ `floor_sunken_min_m` under the interpolated contact surface — OPEN (< 0.9 covered) or ROOFED; kept and cut out. Scalars: `t` (floor plane of contact heights within 3 m of apt.dat airside; else all stations), levels, relief, flat flag. Split-level: `UnitLevels` gains rung L0 (contact heights along `face`); L4 from sheet stations; L3 pier feet. Composites (25l) join their sheet members. Long connectors, free bridges, deck families, viaducts: ends/feet are stations of their units. No contact → `footless`, today's carriers.

## 2. Seating

- S1 admitted unit written whole: rows `OBJECT_MSL` at `z0 + lift`, `z0 = D − t`, D = median solved level of its pad block (stage 1, as today); via `authored_seats`/`exclude`; no body split, no post-mesh re-seat. S2 riders ≥ half inside ride it.
- S3 admission: on a pad, no exception member, and (a) coherent (|t − today's base| < 0.05 m, bodies share the zero — identity), or (b) mis-zeroed (≥ 0.5 m, ground confirms: L1 misfit of credible DEM to non-airside stations falls ≥ 0.5 m), or (c) a recognised partial shell/composite. Doubt keeps today's seat.
- S4 far (25f): a piece of P a storey or more off credible ground keeps today's seat, reported.
- S5 exceptions (today's behaviour): long connectors, free bridges/deck families/viaducts/portals, basin-rim/pile/walled-plate units, kept-as-authored sunk rows, terrain models/shells/rocks, isolated objects, lines/scatter/AGP/facades/stock library, no-pad units (Q1), tile-straddling units, 16v separate-pad touch groups.

## 3. Perimeter grading

`G'(p) = g(p) + w(d)·(clamp(g(p), z0 + lo_k, z0 + hi_k − UNDER_M) − g(p))`, w = 1 within the shoulder, linear to 0 at REACH_M 60; raised or lowered (25k). G0 level choice by ground confirmation. G1 airside never pulled (stage 1 unchanged; airside station > 0.5 m off reported, Q2). G2 inside the patch: targets, never pins — the frontage band keeps C12's D-relative row; other groundside vertices within REACH_M take G' as the value their own ground-follow reads (25e follower, strip datum, road terrain-follow) after stage 1; caps hard; unserved reported. G3 outside the patch: tile raster takes G' at the terrain-cut stage (`rim_grade` generalised to interval targets from one `perimeter` plan record per unit); never edge/patch/water postings or another unit's Owned ground. G4 stations judged on the drawn surface (patch inside, raster outside); boundary stations counted apart. G5 cut-outs: inside P the ground never stands over `z0 + floor − UNDER_M` (cut only; `terrain_cut._cut_grid` fed `floor`; in-patch interiors handed to the existing ObjectFloor/walled_pit/pit_bank consumers). G6 emittable (declared walls, pit grammar; sub-posting steps outside the patch become banks, Q3).

## 4. Consumer census (condensed)

Derivation U1 (new). Unchanged: plan_clusters/cluster_profile (twin), pad_evidence, platform_split/pad_blocks, platform rows/pads (stage 1 identical), landing/strip/riser, plan_low & siblings (twin vs held L0), Vertex.dem_z substitutions, seam pins/coverage join (senior), storey_seat (twin), shell/terrain_model/rim_fill (S5), object_floor/walled_pit/pit_bank (receive G5), Triangle4XP/edge/water/masks (13k). EDIT: U7 unit_storey (L0, air_y twin), U9 frontage reads rise from L0, U10 follower/strip/road read G', U13 rebake_inputs (unit seat records), U15–U17 footprint/pad_block/touch/carry (admitted rows bypass; z0 fixed vote), U19 ground_rim (map replaces _RimSet zero/stations), U21 terrain_cut_stage (perimeter records), U24 object stage (authored_seats; reuse input), U25 sidecar keys `unit_undersides`, `perimeter_unserved`, U26 LAW_FAMILIES `perimeter_gap`, U27 code keys. No UI/wire change.

## 5. Time

Certain: object stage (admitted rows skip body cut, seat passes, OBJ writes; ELLX 710 placements → 1,431 files, the four sets 444 bodies). Possible: solve (fewer conflicts; ELLX hard_conflict 1,285, LDSP 133). Later: retire witness readers to views of the record (classify 28.6 % of ledger time). Added: rasterising on a partition-cache MISS — bar ≤ 1 % of the 60 s budget at median, reported at HECA and OTHH.

## 6. Population / identity / gate

Tool `tools/underside_census.py` (+ INDEX row) over the 29 live captures (CYYZ, EKVG, ELLX, ESSA, GCLA, KASE, KBIL, KBNA, KBUF, KEGE, KIAH, KJFK, KLAX, KMCO, KMSY, KORD, KPHX, KRDU, KSDL, LDSP, LFPG, LPHR, LPMA, MMUN, NZWN, PHLI, RJTT, TFFJ, TNCS) + BIKF/OMDB/LGAV from pack + last plan. Certified: 0 (b)/(c) admissions or each listed. Step 1 byte-identical everywhere; steps 2–3: airports with no (b)/(c) unit byte-identical bodies, coherent units within 0.01 m. Drawn gate at integration: ELLX (49.6350,6.2168; 49.6341,6.2208; 49.6262,6.2009; 49.6186,6.1859), PHLI 21.97850,−159.34935, LDSP 43.5366,16.2990, LPHR; census every crossing.

## 7. Plan

- Step 1 (medium, no behaviour change): U1, U2 twin, U25, U27, the tool. Acceptance: bodies byte-identical on all 29; ELLX 4 composites recognised, firestation t ≈ −7 reported with predicted z0 within 0.5 m of 374.06, Terminal-A within 0.05 m of 375.86, pool_5 within 0.05 m of 344.28; S3 table for all; derivation cost per airport.
- Step 2 (high): seat and levels (U7, U13, U15–U17, U19 zero). Acceptance: ELLX firestation one zero (spread 8.73 → ≤ 0.05 m, lower storey within 0.5 m of building21), Lux one zero within 0.5 m of its pad, Terminal-A/pool_5 ≤ 0.01 m; ELLX files written −400 or more; L0 = today's levels (PHLI 4.1, LPHR 6.0, LDSP −5.6..−6.0, ELLX building42 4.8); PHLI kerb band unchanged; 0 airside movers > 0.01 m; (b) movers listed.
- Step 3 (high): grade and cut-outs (U10, U21, U22, U23, U26, rest of U19). Acceptance: ELLX free stations over 0.5 m → 0 (pool_5 135, Lux 60, firestation 374, Terminal-A 230 free); in-patch groundside over 0.5 m: firestation lot 132 → ≤ 13, Terminal-A lot 189 → ≤ 19, pool_5 road 101 → ≤ 10 (rest named with the binding cap); 0 airside movers; PHLI/LPHR/LDSP frontage unchanged; every OPEN interior cut; identity per §6.

## 8. Owner questions

- Q1. Groups with no airside pad (landside hotels, car parks, off-apron hangars): grade their perimeters too where the gap > 0.5 m and seat once? Recommended: yes, problem spots only, after step 1's count.
- Q2. A group's own edge meeting airside > 0.5 m off: leave and list for a sim read, or shift within its skirt depth (25a)? Recommended: leave and list.
- Q3. A wall-like perimeter step outside the patch can't be drawn by the ~10 m terrain grid → bank, or extend the patch around such groups? Recommended: bank first, judge in the sim.

## 9. Proposed RULINGS line

2026-11-25n — THE UNDERSIDE HEIGHT MAP, SPEC RULES (implements 25m): (1) every §16g unit carries one underside map (top, low, floor, contacts; 1 m; cached with the partition); perimeter stations carry the lowest outer edge and the floor behind it; overhangs set no perimeter; a recognised composite's sheet joins its unit. (2) `t` is the floor its airside-contact stations stand at; replaces the wall-base median for admitted units. (3) Admitted units (on a pad; coherent, mis-zeroed with ground confirming, or composite) are written whole at z0 = D − t before the mesh; exceptions and doubt keep today's seat. (4) Our ground is graded to the perimeter interval by one field (shoulder, feather 60 m): in-patch as the value groundside follow rows read (never a pin), outside as tile postings; airside never moved. (5) Inside the plan the ground never stands over the lowest floor; open below-grade interiors are cut out. (6) A perimeter a storey or more from credible ground is left as authored (25f).
