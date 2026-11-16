# #2091 round 3 spec (Fable review of l2091b 095dd05cf, 2026-11-15; owner chose "new spec round" 02:42Z)

Lines are on origin/claude/l2091b under `Ortho4XP/src/auto_patch_v2/`. Fresh Opus lane, medium, base origin/claude/l2091b. Keep all of rounds 1 and 2. No new module, no new law key, no `PLAN_VERSION` bump, nothing names an airport. Register the patch, sidecar, solved pickle (`--solved-out`), rebake plan and drawn JSONs with `tools/harness/frames.py` before the worktree goes. Never raise the lane cap; delete your scratch builds when you report.

## Findings
- **F1.** OTHH Bridge_03 end a (stack `stack:free:dsf:obj36723`, zero 6.124; end a of `dsf:obj36745` graded, top 2.475 → single top 8.599; plate 8.38 at corner a → 8.60 at corner b): eight end-road vertices on sheet `gap:16` held at band [8.559, 8.599] (`model/deck_ends.py:65-76`, `constraints/deck_stack.py:213-215`). Two inside the ring (0.08 / 0.76 m) have R3 ceiling 8.349/8.346 → R1 dropped (`constraints/deck_stack.py:276`), drawn 7.86/7.81. Two 3.95/4.39 m outside held at 8.56, 0.17 ABOVE the plate at a. With the plate's own height the eight would be 8.346–8.606, within 0.045 of the plate plane. The road ramp reads the same dict (`airport/deck_ends.py:40`, `airport/road_ramp.py:922-923`).
- **F2.** OTHH front garage: partition `unit:24`, 42 members at one origin (25.258626, 51.614551), heading 338.33. `OTHH_Terminal_Parking_003.obj` (`dsf:obj8778`, hard-deck flag) has two base planes y 4.089 and y 1.143, each 42,333 m² in two 21,166 m² halves. `welded_deck` reads it as a deck on piers (ratio 0.0105 < 0.2) and takes only the LARGEST piece of the two-piece ring (`airport/deck_signature.py:981-984`) → stamped shade 20,946 m² = exactly the south half; the shade leaves every pad outline via `geom/base_slab.pad_shades` (`:341-360`). r2 sidecar: north half 100 % on `building10` (pad z 4.35/4.54/4.68); south half 29.9 % on faces, 70.1 % on no face (raw DEM p50 9.03) → slab buried 53.8 %. Simulated trim: 64 pads either way; pad area 1,010,016 → 1,031,111 m²; south slab on pad 0.3 % → 100 %; garage pad 33,599 → 54,694 m²; only one 21,095 m² piece at 25.25812, 51.61348 differs. Across 12 captures the trim touches only this member (20,945 of 20,946 m²); 29 other deck shades (HECA, KIAH, KDEN, KLAX, EGLL, KBNA, ELLX) lose 0 m². The STAMP must not change: `footprint_unit._deck_lending` (`:565-570`) uses it as the "welded deck lends no datum" guard; this member gets a `deck_datum_z` (`airport/rebake_plan.py:353-368`).
- **F3.** Parking_006 base +4.99 is an instrument read of a 13.8 m² thin wall's cap (z 1.77–9.29 at 25.258244, 51.615276; `tools/drawn_site.py:461,495`, `tools/drawn_site_bars.py:144-165`); its foot is 2.53 m under the patch ground as authored. Parking_003's four "deck ends −2.6" are the edges of a 620 m² plate at y −1.713 (25.257725, 51.615039) under `gap:48`, which read −3.2…−4.5 on the control. Neither is new; neither in scope.
- **F4.** s1 road step 0.55: way −1564 has no ribbon; it leaves ribbons −2684/−2690 (z 4.3–4.4) onto raw DEM 6.2–6.6, 30 m outside the slab plan. Not in scope.

## S0. Base reads (replay only, before any edit)
`tools/v2_solve_replay.py --replay /Users/noah/XPTerrainBuilderData/.harness/frames/l2091b/OTHH.pkl --from classify --solved-out BASE.pkl` at the branch head. Record: (1) cluster pads count, area, cover of each slab half's plan (the y 1.143 base plane of `dsf:obj8778` placed with `airport/slab_plates._placed`; halves centred 25.259006, 51.615846 and 25.258124, 51.613484) — expect 64, north 100 %, south 0.3 %; (2) for the eight end-road vertices of `dsf:obj36745` end a within 6 m of edge a→b: R1 row, R3 ceiling, solved z, dropped/relaxed; (3) `hard_conflict` count; (4) z of every vertex inside the south half's plan, by ref.
Reusable reads (run from the lane's Ortho4XP/): /private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-vigilant-lederberg-4eb8b5/36801969-f4c8-4829-9e02-0dc8b5704d14/scratchpad/r3/q.py (end vertices), .../scratchpad/r3/sim.py (pad mint with the trim), .../scratchpad/r3/census.py (blast radius). Promote one only on a second use.

## S1. A road meets a deck's end edge at the plate's own height there
Single site: `model/deck_ends.end_road_vertices` (`:30-83`), branch for a free or kept stack (`st.kind != TRENCH`, `:63-68`).
- For each claimed vertex the returned height is `zero + y_v`, less `deck_flush_m` where the vertex lies inside that deck's ring.
- `y_v = geom/lowest_face.floor_z_at(d.plate, x, y, edge_m=H)` (the reading the slab block uses, `constraints/deck_stack.py:247-249`); `nan` → fall back to the end's top.
- The "two end lines more than `deck_flush_m` apart → left out" test (`:78-81`) stays on the ends' single tops.
- Trench stacks unchanged (`constraints/deck_stack.py:126-137`).
- No consumer edited: `constraints/deck_stack._bridge_rows` (`:213-215`) and `airport/deck_ends.deck_end_seeds` (`:40` → `airport/road_ramp.py:919-926`) read the selection, so R1 and the ramp seed stay one number.
- Update docstrings of `end_road_vertices` and the R1 paragraph of `constraints/deck_stack`.
Twins in `tests/auto_patch_v2/test_bridge_stack2065.py`: cross-fall end → road vertices at both corners carry R1 at the plate's height (minus flush inside the ring), none dropped under R3, `deck_end_seeds` returns the same heights; level end → outside vertices unchanged, inside-ring one flush lower; `test_deck_stack1971.py` (trench) green untouched.

## S2. The ground under a deck that has its own ground slab is the building's pad
Rule: a welded deck's shade leaves every pad outline, EXCEPT where the deck's own file carries a base plane within `[bridge] deck_min_elevation_m` of the objects' zero beneath it ("a slab on the ground"); that plan is the building's floor and stays in the outline.
1. `airport/slab_plates.py`: add `deck_floors(u, m, to_xy, lw, q=0.0) -> list` — for a member carrying a `deck_shade_ring`, every `base_profile["planes"]` plane with `abs(y) < lw.deck_elev_m` and `area_m2 >= lw.min_m2`, placed through `_placed` (`:52-57`); `[]` otherwise; only the member's own profile.
2. `airport/slab_faces.py:155`: `faces.deck_floors = deck_floors` beside `faces.plates`.
3. `geom/cluster_outline.deck_shades` (`:118`): optional `floors=None` callable `(u, m) -> polygons`; each member's shade loses its own floors; remainder opened at the touch tolerance, pieces < 1 m² dropped; `floors=None` byte-identical to today.
4. `geom/base_slab.pad_shades` (`:351`): pass `floors` when the face reader has `deck_floors` and `lw.deck_elev_m > 0`.
5. `classify/evidence.py`: add `CLUSTER_PADS["deck_floor_m2"]`.
Do not touch `welded_deck`, `_stamp_deck_shades`, `Member.deck_shade_ring` or `model/rebake.py`.

Consumer census (RULINGS 2026-08-30l):
| Reader | Reads | Effect |
|---|---|---|
| `classify/evidence.py:618` (pad mint) | `pad_shades` | outline gains the floor's plan |
| `classify/evidence.py:773` (fallback trim) | `pad_shades` | a fallback footprint over the floor is no longer trimmed; the cluster covers it |
| `constraints/cluster_pad.py:167` (census) | `pad_shades` | same shade as the mint, no `pad_cluster_mismatch` |
| `planar/apron_shelf.py:99` | `pad_shades` | same |
| `airport/footprint_unit.py:496,565` (lender guard) | stamped `deck_shade_ring` | UNCHANGED; must stay |
| `planar/cluster.py:296-302`, `pipeline/build.py:447`, `publication.py:625` (reports) | stamped shade | unchanged |
| `model/rebake.py` (serialisation) | stamped shade | unchanged |
Slab shades and the airport's extra shades (sunken ramps, walls, entrances, stacks) are never reduced. No airside, lot or road row is added.
Twins in `tests/auto_patch_v2/test_welded_deck.py`: deck with a base plane at y 1.1 under its whole shade → `pad_shades` no shade for it, stamp unchanged, `_deck_lending` still refuses it; plane at y 2.5 or under `min_m2` → shade unchanged; no base profile → unchanged.

## S3. Report only
Parking_006 base and Parking_003 deck ends at the garage site (expect ~+5.0 wall cap, −1.7…−2.6 sunken plate); the s1 road step and its way; z of the six road refs inside the south half (−5926, −5925, −2683, −2686, −2691, −5928) before/after; max grade of `gap:26`, `gap:140`, `gap:48` before/after.

## Bars
Replay (same capture, `--from classify`, with S1+S2):
- Pads: same count as S0; the garage pad covers ≥ 99 % of both slab halves; pad area +21,095 ± 200 m²; cluster pads differ from S0 by ≤ 50 m² outside the south half.
- End: all eight end-road vertices carry R1 at the plate's own height (8.35/8.35/8.39/8.38 at a; 8.56/8.61/8.60/8.60 at b; ± 0.01); none dropped or relaxed; solved z within 0.045 under the plate plane.
- South half: every solved vertex inside the plan within +0.30 / −0.50 of the north half's pad p50.
- Whole solve: no new `hard_conflict`; no airside-face vertex moves > 0.05 m vs S0.
- Tests/ratchets: touched tests, `test_no_airport_specific_code`, `ratchets.py dupes --near` and `unused` not rising, CI registry twins (`windows_text_io`, `patch_env_classification`, `tile_failures`, `console_encoding`).
Closing build (one): `build_airport.py OTHH --tile 25 51 --pack-copy <dir> --texture-mode default_xplane --refresh-data dem --tag l2091r3_OTHH` (df ≥ 30 GB; ≤ 4 builds machine-wide). Then `drawn_gate.py OTHH --tag l2091r3_OTHH` with the 13 sites in /tmp/claude-501/l2091/sites.txt plus `--site garage=25.2586,51.6146,120`, `--against /Users/noah/XPTerrainBuilderData/.harness/frames/l2091/ctl528.drawn.json`.
- s3: `drawn_site.py` mesh_z at five points 1.0 m outside the edge at 0.5, 3.0, 6.25, 9.5, 12.0 m from corner a, recomputed from the build's deck ring (r2 points: (25.251539927, 51.617019089), (25.25155975, 51.617030949), (25.25158552, 51.617046368), (25.251611291, 51.617061787), (25.251631114, 51.617073648); plate 8.391/8.437/8.497/8.556/8.602). Each plate − ground in [−0.05, +0.15]; first and last differ ≤ 0.10.
- Garage: `drawn_site.py --object Terminal_Parking`: the two 21,170 m² plates of Parking_003 at authored y 1.143 — `bottom_minus_mesh` p50 in [−0.15, +0.30], buried ≤ 5 %, both halves. Site `garage`: patch→drawn 0 over bars, road step ≤ 0.5.
- s1/s2: as round 2 (s1 drawn 3.96 ± 0.10, no `/p` level; s2 PASS). s1 road step reported, not judged.
- R2 nine sites: PASS, no MOVED.
- Protected airports (master rule 11-15): replay or plan-diff KIAH, KDEN (frames/l2090d), KMCI, LEMG, KBNA, LICJ (certified) for S1 — list any end-road vertex or seat moving > 0.1 m.
Build-time impact: < 0.1 s.

## Stop rules (report; no second attempt)
- South half not ≥ 99 % pad in the replay → name what cut it.
- Any cluster pad changes outside the south half's plan.
- The lender-guard twin fails.
- South-half z bar misses because mapped roads inside the pad keep their own levels → report refs and z; do not write a road rule; still run the closing build for s3.
- An end-road R1 row is relaxed → report the opposing family.
- s3 or the garage slab bar misses on the closing build → goes to the owner (RULINGS 2026-11-03d).

## Ruling text for the master to record
A road meets a bridge's end edge at the plate's own height along that edge, never at one level for the whole end. The ground under a deck whose own file carries a ground slab beneath it is the building's pad.

## Follow-ups recorded, not in this round
- `welded_deck` reads only the largest piece of a multi-piece hard-deck ring (`airport/deck_signature.py:981-984`).
- The drawn base bar reads a thin wall component at its cap (`tools/drawn_site_bars.py:144-165`); excluding thin components changes verdicts tile-wide — needs its own control.
- The deck-end judge treats an upper deck's free edges as ends.
- The 620 m² plate at y −1.713 in Parking_003 (sunken floor shallower than a storey) needs the owner's sim read.
- A trench end with a cross-fall keeps the uniform top (not measured).
