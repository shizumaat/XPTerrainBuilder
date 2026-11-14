# #1884 round 2 — terrain-carried base + routing safety (Fable review of lows1884 ceebe3e55, 2026-11-13)

Read-only review; nothing built. Evidence: owner's installed rebake plan (`/Users/noah/XPTerrainBuilderData/Patches/+40+010/+47+012/o4_v2_rebake_LOWS.json`, 11-10) replayed through the branch with `tools/v2_rebake_replay.py plan` on the owner's two meshes (`/Volumes/ThunderBlade/Custom Scenery Library/Ortho4XP/zOrtho4XP_+47+01{2,3}/Data+47+01{2,3}.mesh`). Replay reproduces the lane: Terminal_LOWS_38 b1 +1.45 (lane +1.46), _36 +18.19 (+18.2), _15 b0 −0.04 (0.00), domiki_lows_37 roof 6.46 over its carrier's zero (+6.77). Scratch: `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-frosty-jemison-49af9b/cefbef3f-64e7-4c8d-9220-de7d4ea95540/scratchpad/rev1884/`.

## 1. Verdict
- The deviation (split decided once by the tile whose DSF holds the row; bodies routed) is RIGHT: `tile_rows.for_tile` partitions by row tile, two independent splits cannot agree.
- The "49 regressions" are mostly a METRIC ARTEFACT: the lane's `compare2.py` judged roof components as footed; their houses were buried 4–21 m rigidly so the roofs sat at ground level; now the house is seated and the roof stands at eave height.
- The +32 m body is a real defect — one building; narrow witness-gated rule (A).
- Not landable as is: record-ownership and atomicity hazards (B) can leave objects drawn by neither tile or by both.
- The four "unchanged" terminals are the 22o connected-group zero — out of scope.

## 2. Mechanism
a. `build_plan` output identical on base and branch (165 splits, 3,955 bodies); the round only stops `split_guard.off_tile_splits` undoing 81 placements, so every new seat is the standing law on formerly-rigid placements. 3,717 footed non-elevated bodies: within 0.5 m of own ground 221 → 3,303; within 0.3 m 149 → 2,881. Newly worse > 0.3 and off > 0.5: 23 (20 buried 0.5–0.92 m: 14 under 22o group zero, 4 §16g unit median, 2 low-side foot; 1 real float Terminal_LOWS_77 b0 +0.97 §16c-bound to Terminal_LOWS_48 b4; 2 Terminal_LOWS_25 fence segments, probably metric).
b. Two datums: Terminal/Veh at 47.79329, 12.99657 (ground 432.17); all 48 domiki at 47.790277621, 12.99384918 (ground 435.51). At 47.7997, 12.9836 `domiki_lows_14` = walls (y −0.13..6.47), `domiki_lows_37` = roof (6.47..7.21); ground 442.95; rigid put wall base at 435.4 (7.5 m buried), roof bottom 441.97 (lane's −0.72); now walls on ground, roof carried at 6.46. Of 179 elevated bodies that went "seated/buried → float": 125 ride a carrier seated within 0.5 m; 42 ride a carrier off > 0.5 m (22o groups, low-side-foot houses); 12 no carrier row. Terminal_LOWS_23/_37 roof floats are roofs on walls (_37 part 7.52 on Terminal_15 walls to 10.17; _23 part 9.23 on Terminal_22 walls to 11.92).
c. The +32 m body: hilltop building at 47.74974, 13.00860, `domiki_lows_14` part 30184 (base y 33.593, 1,861 m², 17.83 m tall; b349 replay / b352 lane), companions domiki_07/_12/_13/_37 (bases 33.62–40.64), unit `fu:1:263`; ground there 34–40 m above the domiki datum ground (author raised it to his terrain); rigid left it 1.9–6.7 m buried. Floats because `contact.partition` (contact.py:1333-1341, 1557-1560) strips feet when `base_y > elevated_base_m` (0.5) in the FRAME (not relative to its structure as `Part` doc says, model/rebake.py:94-97); `placement_carrier.is_elevated` (line 107) likewise absolute → whole structure elevated, no carrier → `placement_file._own_ground_file` (y_zero 0, authored y kept) +33.6. Unit path: `footprint_unit._wall_base` footless branch (1073-1088) fires only when `lift != 0.0` → unit zero = ground − 0 = 474.86. Only structure of this class at LOWS (of 97 own-ground bodies with base > 0.5 m, 3 have ground rise matching base; others −8..+0.8, genuinely elevated, e.g. Terminal_LOWS_46 12.4 m).
d. Terminals _37 b1–b4, _38 b0/b1, _33, _23 b2, _35, _36 are in "one connected group fu:2:10895 at 432.22" (22o/q): 151 bodies over 47.7892–47.7993, 12.995–13.0078 (6 east of 13.0), zero ≈ old datum plane, over pads 429.58–431.37 → +0.85..+1.45 W, +2.6 E; _36 = +2.69 + authored base 15.49. Fence parts don't chain units; what links E to W unidentified.

## 3. Ordered changes (two lanes, disjoint files: A+D, B; one closing build after both). Base: claude/lows1884 + claude/lentc1908 (its `free_column.py` is the sibling mast rule touching `placement_file`, `placement_plan`, `anchor_rule`).

### A. Terrain-carried base — new `auto_patch_v2/airport/terrain_base.py` (beside `free_column.py`), one witness, two sites
Witness (all, else nothing changes — 13r): (1) every walled part (non-line, not deck/plate, `height_m >= [placement] chain_min_height_m`) is in the air: lowest plane b of their `base_y` (reuse `PLANE_SHARE`, `AUTHOR_GROUND_M`) > `[rebake] elevated_base_m`; (2) frame has no authored lift; (3) authored base does not clear our ground: `frame_zero + b − G <= elevated_base_m` (`frame_zero` from `adapted_riders.frame_zero(surface, anchor, lift, authored)`; G = median design surface under the walled parts; LOWS: 435.51 + 33.6 − ~474.5 = −5.4; Terminal_46 lights +13.7 refused); (4) no carrier.
Site 1 `footprint_unit._wall_base` footless branch: when `lift == 0.0` and witness holds, `memo[root] = b` (pass `surface`, `frame_of` from `plan_unit_datums`); unit zero = ground − b; unit carry and `group_zero` seat `fu:1:263` unchanged.
Site 2 `placement_file._own_ground_file`: lowest walled part satisfies witness → `y_zero = b`; anchor at the base-ring vertex with the lowest design surface when ring spread > `split_tol_m` (use `anchor_rule`'s low-side rule); keep the `OWN_GROUND` stem (as lentc1908); reason "base is the author's terrain: frame zero + b stands X m under this ground"; counts `terrain_carried_units`, `terrain_carried_bodies`, `terrain_carried_refused_over_ground`. No new constants (else `[placement]` TOML). Do NOT relax the feet strip in `contact.partition`. 13r census: `v2_rebake_replay plan` over the frames corpus, list every unit/body whose seat changes; master reads before landing.

### B. Routing safety — `tile_route.py`, `placement_write.py`, `unpatched_pack.py`, `dsf_write.py`, `object_stage.py`
1. Guest rows belong to the tile that wrote them. Today `_sibling_plans` drops `LOWS@+47+012` whenever `LOWS` is in `drop` (dsf_write.py:1169); `unpatched_pack.seated_airports` folds guests into the owner (unpatched_pack.py:86-88). Failures: (i) a +47+013 build that can't patch LOWS runs `restore_airport`, `kept` empty, copies backup over the DSF, removes cut files → 2,928 routed bodies drawn by neither tile; (ii) unpatching +47+012 returns its DSF to whole objects while +47+013 keeps guests → drawn by both; `remove_cut_files(written_body_files(...))` may orphan +47+013's names. Fix: `restore_airport` treats `ICAO@other` as another airport (kept, recomposed); unpatching tile A rewrites every neighbour DSF of the pack without `ICAO@A`; a guest row that can't be re-applied (stale `row_is_current`, garbled) takes its home DSF back to the original in the same write and says so at verbosity 0 (rigid as authored, never missing).
2. One function, one transaction (e.g. `placement_write.apply_routed`): today `object_stage.py:694-770` = guest write, own write, then an unjournalled unlocked second `write_files`. Own write failing (`BackupUnproven` → `{}`, or a raise rolling back only the own tile) leaves guests (drawn by both); between own restore and the second `write_files` the neighbour DSF names missing bodies (a concurrent `torn_pack.repair` would revert it). Fix: classify own + each neighbour DSF before writing; one `pack_journal` transaction over own DSF, neighbour DSFs and all bodies; a raise restores all; drop the post-hoc `write_files`; `object_stage` and `v2_rebake_replay plan --write-pack` call this one function.
3. Lock: `apply_plan` locks the record beside one DSF (placement_write.py:635); steps lock separately; tiles in different 10° folders lock different files while sharing `objects/`; `dsf_write.write_pack` callers outside `apply_plan` take no lock (object_stage.py:367, pack_rewrite.py:52, unpatched_pack.py:151); `hold_file_lock` yields False after 900 s and `apply_plan` ignores it. Fix: one lock per PACK at the outermost entry of every writer, non-reentrant; False refuses the write.

### C. Guest seat source — measure only
Guest bodies planned on the airport DEM, drawn on the neighbour mesh; at 2,656 guest anchors mesh − DEM p5 −1.55, p50 −0.02, p95 +3.65, max +10.27; 935 off > 0.5 m. Own-base bodies unaffected (plain OBJECT). Units/groups straddling the edge: `fu:2:10895` (6 east), `fu:1:136`, `fu:3:13725`, `fu:1:191`. Report per-unit drawn-zero spread for guest units; > 0.3 m → follow-up, not a retry.

### D. Metric — extend `Ortho4XP/tools/drawn_site.py` with a plan-reading compare mode (carried/elevated bodies judged rider-to-carrier offset vs authored + the carrier's seat; only footed bodies judged foot-to-mesh); INDEX row + twin; register the closing plan and drawn JSON in frames.

## 4. Consumer census (lane confirms "not read" rows by grepping `_wall_base`, `OWN_GROUND`, `guest`)
| Consumer | Reads | Ruling |
|---|---|---|
| `footprint_unit._wall_base` → `plan_unit_datums` | unit wall base | edited (A site 1) |
| `footprint_seats.plan_wide_seats` → `open_frame_seat.root_zeros`/`group_zero` | unit zero | no edit |
| `footprint_carry` (`footless_carried_by_unit`) | unit zero | no edit |
| `one_building.one_building_groups`/`pavement_top` | unit zero | no edit (not read) |
| `placement_file._own_ground_file` | y_zero 0 | edited (A site 2) |
| `free_column` (lentc1908) | own-ground stem | runs after; confirm no double seat |
| `open_frame_seat` own-ground (~601), `adapted_riders`, `placement_targets` | own-ground bodies | stem kept (not read) |
| `placement_census`/`seat_feet_census`/`contents_census` | `y0 > elevated_base_m` = float | must read the new reason (not read) |
| `placement_carrier.is_elevated`, `contact.partition` feet strip | absolute base | unchanged by design |
| `dsf_write._guest_row` | `msl_z`, `lift_m` | own-base body is plain OBJECT |
| `dsf_write._sibling_plans`, `unpatched_pack.restore_airport`/`seated_airports` | guest key | edited (B1) |
| `sibling_stage` | record | under the pack lock; confirm owner-folding hides no sibling |
| `pack_rewrite`, `object_stage.py:367`, forest/drape/optimise/user-seat rewrites | record + DSF | pack lock; must re-apply guests |
| `torn_pack.repair`, `pack_journal` | DSF vs body files | one transaction (B2) |

## 5. Bars at LOWS (drawn: build mesh +47+012, owner's World mesh +47+013)
1. Terminal_LOWS_15 wall feet within 0.10 m; its Terminal_37 hall part rides it.
2. Hill building (`domiki_lows_14` main body 47.74974, 13.00860): no base edge > 0.5 m above ground, low side within 0.3 m; `fu:1:263` one zero within 0.05 m (was +31.95).
3. The 49 regenerated with tool D: zero footed floats; each a rider on a carrier seated within 0.5 m with authored offset within 0.05 m, or named with its law.
4. No footed body floats > 0.3 m above its figure under the owner's installed products; Terminal_LOWS_77 b0 (+0.97) fixed or attributed; Terminal_LOWS_25 fence segments near 47.7949, 12.9982 checked drawn.
5. ≥ 3,300 of 3,717 footed bodies of the 81 placements within 0.5 m.
6. Terminal_LOWS_23/_35/_36/_38 not worse than installed by > 0.1 m.
7. Every body of the 81 placements drawn exactly once across both DSFs (row census on the pack copy).
8. Guest-unit drawn-zero spread reported (C).

## 6. Closing build
One: `tools/harness/build_airport.py LOWS --tile 47 12 --pack-copy DIR` (lows1884c took 2,101 s, vector step 1,661 s). +47+013 verified offline on the same pack copy: `tools/v2_rebake_replay.py plan <owner's +47+013 plan> <owner's +47+013 mesh> --tile 47 13 --write-pack DIR`; assert guest rows present exactly once and every named body file exists.

## 7. Tests
A: walled in-air no-lift structure with base at/under ground seats by its base at both sites; same with base clearing ground > 0.5 m unchanged; non-walled in-air body unchanged; lifted frame takes existing branch; own-ground body on a slope anchors low side.
B: neighbour unpatched → guests kept; home unpatched → guests dropped from neighbour, no orphaned body file; stale guest row → home DSF back to original with a note; own write raises after guest write → both DSFs byte-identical to before; lock timeout → write refused; a `write_pack` rewrite (drapes/forests) re-applies guests.
Gates: `test_no_airport_specific_code`, `O4_Object_Stage_Code.CODE_MODULES`, `windows_text_io`, `patch_env_classification`, `tile_failures`, `console_encoding`.

## 8. Risks
Witness 3 is one-sided (a building authored for higher terrain keeps own ground + authored y; counted). Off-tile witness reads the DEM, which differs from the drawn mesh by metres on hills (LOWS margin −4..−5 m). B changes restore semantics for every multi-tile pack (needs the #25 sibling corpus twin TNCM/TFFG). The lock file lives in the pack's `Earth nav data` (inside the X-Plane install for live packs) — check against the pack-copy write guard.

## 9. Owner-intent questions
1. Walled building authored in the air whose base ends up ABOVE our ground: sit on our ground, or stay? (Recommend stay until a case appears.)
2. In-air body with no carrier and no witness: 13r literally = the author's rigid height (datum ground + y), not §16 (3) "own ground + authored y". Should §16 (3) stand?
3. Connected group `fu:2:10895` (1.1 km; terminal +0.85..1.45, east hangars +2.6 over pads): one zero intended (22o) or its own issue?
4. 20 footed bodies now buried 0.5–0.92 m under group/unit zeros: accepted under 22o?

## 10. Not verified
Lane's 49 not matched row by row (plans/JSON deleted); "258 neither / 438 both" not re-run (`consist.py` in scratchpad `lows/`); what chains `fu:2:10895`; Terminal_LOWS_36's carrier; per-body base from sampled points (unreliable for line/multi-level bodies); mesh − DEM figures from replay anchors on possibly older owner meshes; lock/journal behaviour read not exercised; lentc1908 read at doc level.
