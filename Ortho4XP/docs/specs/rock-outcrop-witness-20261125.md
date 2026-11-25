# Rock outcrops (RULINGS 2026-11-25j): the natural-shape witness, the fallback switch, the plan

Status: SPEC (Fable scout lrockspec, 2026-11-25; one-miss review of lane lrocks `origin/claude/lrocks` 1ee43e6b2). Design only; no build run. Owner guidance 2026-11-25T23:09Z: built objects have right angles and flat planes; rocks and terrain have none, small facets at different angles, almost no vertical planes.

## 0. Result

- A geometric witness admits 4 of the 5 named rocks (EBBR hill_03, LGSR Colina, CYAZ Rock_1, BGGH Rocks3) and catches no built object in the 651 others past lrocks' loose gates (90 packs of the 164 scanned). Two others pass and look natural: LICR `SAT/Circo.obj` (345 m plan, 46 m relief, outside the boundary) and TNCS `TidalPools-merged`.
- All 57 earlier false positives refused, including KEGE_Terminal_Part1 and OMDB H2/H4; certified packs' 20 objects refused; the three 25j exclusions (EDDH logo, CYQB APTjunk, KTPA Fedex_Blast) refused.
- KSRQ mesh_hill cannot be admitted by shape: a composite (45 % tall wall/card, largest top sheet 48 %, 33 lights, 33 animations; its sibling srq_rwy14_wall has near-identical numbers). Loosening to admit it admits 13 built objects → user switch (§4).

## 1. Why lrocks missed

Whole-object area shares fail: rocks are low-poly or carry built parts (EBBR 37 triangles; BGGH boulders on a flat base plate, 13.6 % vertical; KSRQ composite); look-alikes are single curved roof pieces (LIMC, OMAA, OTHH, EDDL, EDDS); base rate ≈ 5 in 650. The owner's seven ideas measured on rocks vs 651 built (coplanar region size, dihedral histogram, perpendicular normal clusters, axis alignment, vertical area, rectangular footprint, triangle-size Gini, UV tiling): none separates alone; 2, 3, 4 work only as one-sided guards once KSRQ is out. What separates: the top surface is ONE connected sheet, and the object stands on its own ground zero.

## 2. The witness (non-`OBJECT_MSL` rows only; MSL rows keep `terrain_shell.small_shape`/`small_match`, so TFFJ/TNCS do not move)

Candidate gates (lrocks `rock_shape`, unchanged): plan 50 m to < 500 m; top relief p5–p95 ≥ 5 m; hillside steep ≥ `relief_skin.MIN_STEEP`; big pieces ≥ `relief_skin.MIN_SHARE`.

| Gate | Definition | Constant | 4 rocks | Nearest built |
|---|---|---|---|---|
| ONE SHEET | upward faces (not walls), welded at 1 cm, joined across shared edges: largest component's area share | `ROCK_MIN_SHEET` 0.9 | 0.966–1.0 | 0.885 (arched hangar, also over the wall limit); a 747 0.35 |
| ON THE GROUND | lowest plan-grid surface (+ `OBJECT_AGL` lift) ≤ `ROCK_BASE_M` above the object's zero, top p95 ≥ 5 m above zero | `ROCK_BASE_M` 1.0 | −2.21..+0.02 m | 5.29 m; curved roofs 7.8–70.9 m |
| NO STOREY WALLS | area share of walls (`WALL_NY` 0.1) ≥ `STOREY_M` 3 m tall | 0.05 | 0–0.037 | built median 0.31 |
| NO RIGHT-ANGLE CREASES | shared-edge length share bent ≥ 80° | `ROCK_MAX_RIGHT` 0.1 | 0–0.077 | built median 0.19 |
| NOT AXIS-ALIGNED | sloped upward faces, azimuth mod 90° in 5° bins: best two adjacent bins | `ROCK_MAX_AXIS` 0.5 | 0.14–0.40 | built median 0.95 |

Stability (one threshold at a time): sheet 0.5–0.95, axis 0.4–0.8, base 0.1–5.0 m, wall 0.05–0.2, right 0.08–0.3 all give 4 rocks / 2 others. Thin margins: wall (BGGH 0.037 vs 0.05) and right (BGGH 0.077 vs 0.1). Never relax constants to chase a rock. All 29 known shells (TFFJ 16, TNCS 9, SBRJ, KHAF, LOWS, …) pass the frame-free gates (sheet 1.000, walls ≤ 0.016, axis ≤ 0.29). Optional tripwire for an unseen dome/arch on the ground: best mirror symmetry of the top grid `ROCK_MAX_MIRROR` 0.85 (rocks/shells ≤ 0.833; Doha arch 0.886, OMAA 0.989, 747 0.990).

Match: lrocks' `rock_match` unchanged (base rim within `SHELL_LEVEL_M` of our ground at the row datum, no correlation); hide offer `terrain_model.quality()` unchanged.

## 3. Texture content and placement context — not witnesses

Texture: sand roofs, grass logos and sports fields are earth-hued (earth ≥ 0.45 & no LIT & hue spread ≤ 35: 5/5 rocks but 43 built). Placement: rocks sit inside boundaries with vegetation and neighbours; custom packs barely use apt.dat pavement (off-pavement & isolated & ≥ 300 m from runway: 2/5 rocks, 68 built). Neither is needed.

## 4. Fallback: per-object "Seat as terrain" (default off)

- `pack_terrain.py` answers gain `TERRAIN` (seat as terrain) and `OBJECT` (never terrain — vetoes any family's recognition), same `TERRAIN_OBJECTS` store; new `TERRAIN_CANDIDATES` store (objects passing candidate gates but not the witness, ≈ 4 per airport pack); `object_rows` adds `candidate`/`terrain`; `adjust_edit.change` takes declared ticks; the declared set joins `_tile_state`, patch provenance and the partition cache key (25d lesson).
- Wire: capability `pack_terrain_declare` beside `pack_terrain_objects` (`o4_engine/events.py`, `EngineCapabilities.swift`); no event renamed. Mac `PackAdjustSheet.swift` "Seat as terrain (rocks, hills):" list under the terrain row; Qt `O4_Qt_Pack_Adjust.py` mirrors in the same PR (`tests/test_qt_layout_parity.py`).
- Declared: `rock_shape(..., declared=True)` skips §2's gates (keeps plan < `MIN_PLAN_M` and a non-empty grid), then the lrocks path (one rigid frame, `row_datum`, `rock_match`, skirt seat, hide by `quality()`).
- No feather exists in code (#2272 round 3 removed `edge_feather`); rocks get the skirt seat. BGGH Rocks3 (flat base plate on slope) runs out of skirt (3.12 m gap, 61 m²): the seat stops at skirt depth; when the DEM-predicted worst gap exceeds the depth by > `terrain_fill.SERVED_M` 0.5 m the record carries `fill_z0 = datum − depth` and `terrain_cut_stage` runs `terrain_fill.rim_fill` (raise only, shoulder then 1:1 talus within `REACH_M` 60 m, never a patch or tile-edge posting). Inside the patch: reported unserved (25k frontage L4).
- KSRQ caution: raw-DEM replay sinks mesh_hill 3.77 m of 5.69 m relief; ground then shows through its whole body. Judge on the integration build before handover.

## 5. Owner questions

1. Is an unticked "Seat as terrain" box per object in Adjust acceptable for composites like KSRQ's mesh_hill?
2. LICR's Circo hillside (345 m, 46 m relief) would be recognised and seated like the rocks — agreed?
3. BGGH's rock (flat base on slope): after sinking to its skirt depth 3.1 m still floats — may our ground be raised to its low edge outside airside (as 25k at ELLX)?

## 6. Plan

- Step 1 — lane lrocks2 (Opus, high) on `origin/claude/lrocks`: replace `terrain_rock._witness`/`capped_wall_share` with §2's five gates (reference implementation: lrockspec scratch `geo2.py` `feats()`), `fill_z0` + `terrain_cut_stage` rim fill, census tool gate values, replay tool, tests. Acceptance: census over all installed packs via the machine ledger — `rock` rows exactly EBBR hill_03, LGSR Colina, CYAZ Rock_1, BGGH Rocks3, LICR Circo in the 164 airport packs, every other `rock` row listed with gate values (one built object = a miss); KEGE, BIKF, OMDB, LGAV, TFFJ, TNCS, SBRJ, KHAF, LOWS identical (0 movers); `shell_seat_replay --dem`: EBBR, CYAZ, LGSR gap 0.00 and fixed; BGGH rim floating ≤ 0.5 m after fill or in-patch stations counted; EDDH logo, CYQB APTjunk, KTPA Fedex_Blast, KEGE_Terminal_Part1, OMDB H2/H4 refused with their failing gate. Integration: one tile build each at EBBR, LGSR, CYAZ, BGGH with drawn gate, no MOVED.
- Step 2 — lane lrockdecl (Opus, medium): §4's switch (engine store, rows, JSONL capability, Mac sheet, Qt mirror, parity test, cache keys). Acceptance: KSRQ declared → one `rock` record, never split, seat reported; undeclare restores the plan byte-identical; `OBJECT` on EBBR removes its record; a pack with no answers is identical.

## 7. Proposed RULINGS line

2026-11-25l — ROCK OUTCROPS: THE WITNESS IS ONE TOP SHEET STANDING ON THE GROUND; COMPOSITES ARE DECLARED (refines 25j). (1) An object on a plain or AGL row, 50 to < 500 m plan with ≥ 5 m hillside relief, is a rock when its upward faces form one connected sheet (≥ 0.9), its lowest surface is within 1 m of its zero and it rises ≥ 5 m above it, ≥ 3 m walls are ≤ 0.05 of its area, ≥ 80° creases ≤ 0.1 of shared edge length, and its slopes are not axis-aligned (≤ 0.5); no name, texture or placement is read. (2) It is then a terrain shell: one rigid frame, seated by its skirt, hidden only on a fine match. (3) Where the skirt runs out our ground is raised to the rim outside the patch (25k); inside it is reported. (4) An object the witness refuses is seated as terrain only when the user ticks it in Adjust (off by default; "not terrain" vetoes); both apps.

## 8. Not verified

No tile build or seat replay with the new witness; ~930 installed packs outside the 164 not scanned (step 1's holdout); stored vertex normals assumed up; LICR Circo and TNCS TidalPools not viewed (TidalPools' row kind unconfirmed); OSM-building and fine-DEM context reasoned, not computed.
