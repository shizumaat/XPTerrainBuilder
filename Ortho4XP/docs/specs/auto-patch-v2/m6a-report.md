# auto-patch-v2 — M6a report: restore before read, re-bake after the mesh (RULINGS 2026-09-04i 04f-1)

Lane `v2rebake` (Fable, owner 2026-09-03h), branch `lane/v2rebake` off main
`9af3ea54`. Every v2 file ≤ 1,000 lines (new: `model/rebake.py` 214,
`airport/rebake_plan.py` 207, `emit/rebake.py` 217); no environment reads
in v2; nothing under `auto_patch_v2` imports v1 (the model twins enforce
both and the dependency direction: model ← airport ← emit ← pipeline). The
driver hook lives in v1's `auto_patch/engine_v2.py` and imports both.
Commits in §9, on the branch, not merged.

## 0. Site first — OTHH, tile +25+051, `--engine v2`, closing build `OTHH_tile_v2_rebake`

| | value |
|---|---|
| restored-for-read (placements whose geometry was read from `.anchor_bak`) | **1,229** of 11,902 placements (OTBD 0, OTBH 0: all-stock packs) |
| re-seat plan | 93 units (anchor spellings) / 1,083 members / 146,960 witnesses; 283 resources skipped at plan time: 1,901 stock `lib/` placements, 84 resources at 2–7 anchors (I-4), 177 resolving outside the pack (A15), 33 with below-grade solids (08-26), 158 with no genuine solid |
| post-mesh seat (the NEW mesh of this build) | 93 units: **13 seated** (537 resources), **79 below the 1.0 m threshold** (stay, terrain adapts), **1 held** (Bridge_05: every founding foot on the canal's water triangles — current bytes kept), 0 unseatable, 26 findings |
| objects re-seated / written | **0 written** — the closing build ran under v1's kill switch `O4_DSF_OBJECT_REANCHOR=0` (recorded in the env snapshot): seats measured and recorded in `Patches/+20+050/+25+051/o4_v2_rebake_result_OTHH.json`, no pack file written or reverted. WHY in §5. |
| `.anchor_bak` count before → after | 1,229 → 1,229 (no write); live ≠ backup 63 → 63 |
| ledger | `tools/run_ledger.jsonl` tree `020d02c9696b`, tag `OTHH_tile_v2_rebake`, exit 1 (the masks step's bathymetry-band stamp refused by the shared-repo guard — PRE-EXISTING: the 06:28 `OTHH_tile_v2` run of lane v2app stopped at the same "step 3 masks START"; the re-seat runs at the end of step 2 and completed) |

**Owner-site datum reads, before → after** (before = the pack on disk,
v1's owner-accepted R12 bakes, `tools/v2_rebake_replay.py disk`; after = the
v2 seat this build measured on its own mesh):

| family (one anchor spelling) | v1 on disk (accepted in sim 2026-08-11) | v2 seat | note |
|---|---|---|---|
| Bridge_01 (8 members) | **+4.1589** (`bridge_abutment_seat`) | **+3.887** | founded by `Bridge_01_LOD0_000` (64 land feet); 2 CLUTTER members all-water |
| Bridge_04 (2) | **+2.5672** | **+4.397** | founded by `_002` (20 land / 12 water feet); 4 witnesses > 0.75 m off |
| Bridge_05 (3) | **+1.6450** | **HELD** (kept) | 150 founding feet, all on water |
| Bridge_02/03/06 (25) | **+0.9576** (coalition, memory R12) | **+5.585** | coalition 3/6 founding members within 0.25 m; 3 outliers |
| BusStation (12) | authored (v1: max structure delta 0.046 m) | −0.102 → **stays** (below threshold) | coalition 10/11 members |

The bridge deltas are NOT the accepted ones (§5). Everything else the v2
seat would move (13 units) is in §4.

## 1. What 04f-1 asked, and what v1 actually does (attribution before fix)

The brief assumed v1 rewrites DSF object placements through DSFTool. It
does not: v1's post-mesh (`post_mesh.py` → `object_anchor.py` →
`object_rebake.py`) rewrites the **OBJ8 vertex `y` tokens** of the pack's
own `.obj` files in place (`_rewrite_y_tokens`, one offset per rigid
structure), keeps the authored file as `<name>.anchor_bak` (created once
from the authored bytes, never overwritten with a bake — invariant I-14's
three-way hash), records `.o4_reanchor_provenance.json` per pack, and on
every run puts back any resource its current decision excludes (the
reversion pass). The DSF is never written; DSFTool is only read (the
dump cache). So there is no DSF round-trip to reuse, and `.anchor_bak` is
the one file format both engines share.

Which state v2 read before this lane: the LIVE files — m4b-report §9 Q1
(LEMD T4S +3.42 m, OTHH 1,229 backups). Measured here: OTHH's pack holds
1,229 backups, 63 live files differ from their backup, 265 provenance
entries (206 generic y-bake, 53 `bridge_abutment_seat`, 6
`basin_group_seat`), written by lane v2app's 06:28 tile build through
v1's hook — a v2 tile build was already re-baking through v1's law.

## 2. Restore before read (`airport/pack.py`, `airport/load.py`)

`pack.authored_source(path) -> (path_to_read, restored)`: the
`.anchor_bak` beside a resolved `.obj` when one exists, else the path.
The loader maps every resolved placement through it when
`[rebake] restore_before_read = true`, records `resolved_path` as the
authored file (the structure/basin passes read from it unchanged) and
counts `objects_restored_for_read` (the pipeline's `objects:` line prints
it). READ-side only: the patch build never writes the pack. Twins: the
backup is preferred over the live file; the planar object read sees the
authored box (top 0) where the live file is +3 m; through
`airport.load` on the CYXY fixture a pack-relative placement with a
backup resolves to it and is counted.

## 3. Re-bake after the mesh — design and where it runs

Three pure v2 halves plus one v1 hook:

* `model/rebake.py` — data: `RebakePlan{units[Unit{anchor, agl, members[Member{resource, authored_path, live_path, feet[Foot{lat, lon, y}], deck_ring, deck_top_y, deck_datum_z}]}], skipped, counts}`, `SeatResult{UnitSeat{delta_m, datum, seat_datum_m, members[MemberSeat], skip_reason, held, findings}}`, JSON round-trip.
* `airport/rebake_plan.py::plan` — at PATCH time in the pipeline (after emit, before verify), over the planar pass's placed objects (read once: `planar.build(objects_out=…)`): **units** = every placement sharing one anchor spelling `(lat, lon, AGL)` (memory `shared-datum-pack-authoring`: one anchor for all objects of a family — canonical identity, never proximity); per member the **feet** = the object's own lowest band (`foot_band_m` over its genuine solid components, thinned to `foot_samples_per_component` / `_per_member`) in world position with authored `y`; for a hard-deck object the deck ring, `deck_top_y` and the SOLVED surface's median value inside the ring (`emit.rebake.deck_datum_from_surface`, bound by the pipeline). Skips: stock `lib/`, outside-pack resolution (A15 guard 2), `OBJECT_MSL`, multi-anchor resources (I-4), basin-facility ids (`pm.basins`, v1 R4) and any object with below-grade solids (08-26: the terrain adapts to it). Written as `<out>/<ICAO>.rebake.json`; the driver copies it beside the patch as `Patches/<tile>/o4_v2_rebake_<ICAO>.json`.
* `emit/rebake.py::seat(plan, sampler, law)` — AFTER the mesh: `sampler(lat, lon) -> (z, is_water) | None`. Per unit: anchor ground = mesh(anchor); founding members = those whose feet reach the UNIT's lowest band (+`foot_band_m`) or carry a deck; per founding member the seat = median over land feet of `mesh(foot) − (anchor_ground + agl) − y` (a foot on a water triangle never founds, `water_founds_seat = false`); the unit's ONE delta = the deck members' median if any (deck top → solved value, R12), else the agreeing coalition of founding-member seats within `agreement_window_m` (R12 amendments 3/4), else the median with a finding; `|delta| < min_delta_m` → stays; no founding witness on land → **HELD** (current bytes kept, finding). Feet further than `residual_report_m` off the mesh under the rigid seat are counted as findings, never a split seat.
* `auto_patch/engine_v2.py::rebake_after_mesh(tile)` — dispatched from `O4_Mesh_Utils._auto_patch_post_mesh_rebake` when `auto_patch_engine = v2` (one baker per pack per build; v1's `rebake_dsf_objects` otherwise). Reuses v1's `_mesh_is_newer_than_alt` ordering guard, `_is_protected_scenery_root`, `MeshElevationSampler` (elevation + water bit in one point-in-triangle), and — THE writer — `object_rebake.apply` fed a `RebakeDecision` with one `Structure` per resource over all its solid triangles, every vertex the unit's delta, `decision_kind = v2_feet|v2_deck_top`, `seat_datum_m` (so provenance records `delta_m`). `modify_custom_airports` OFF = v1's measure-only: nothing baked, an earlier bake put back (twinned both ways). `DSF_OBJECT_REANCHOR = 0` (v1's engine-wide kill switch) = seats measured and recorded, nothing written or reverted. Held units are unknown to the decision, so the reversion pass leaves them alone. Result sidecar `o4_v2_rebake_result_<ICAO>.json` (every unit, member seat, findings, what `apply` did); one summary line per airport; the "restart X-Plane" reminder per modified pack.

Law added: `structures.toml [rebake]` (11 keys, each citing its v1
constant or ruling); `law/model.py::Rebake`. Idempotency is v1's: `apply`
always reads from the backup, so a second run over the same mesh writes
identical bytes and creates no new backup (twinned: hashes and backup
count unchanged); `object_rebake.restore` returns the authored bytes
byte-exact (twinned).

## 4. What the v2 seat would move at OTHH (measured, not written)

13 units: Dewatering_01_000 +15.1 (a basin family member without its own
below-grade solid — the basin exclusion should cover the whole family,
§6), Qatar_DutyFree +12.2 (15 members founded by one 16-witness piece),
TerminalRoads_03 +6.35 (**400 members** founded by ONE 4-witness piece),
PowerStation +5.9 (8 witnesses), Bridge_02/03/06 +5.58, Bridge_04 +4.40,
Bridge_01 +3.89, FuelFarm_03 +3.8 (7 witnesses), GA_Hangar9 +2.0, Fuel_02
+1.9, Terminal_Parking +1.7 (coalition 14/16), HangarC +1.6, FuelFarm_01
+1.3. 79 units stay (within 1 m: the flat 3.96 m apron).

Attempt history (cap two, both on the witness definition, the seat law
unchanged): attempt 1 read per-COMPONENT contact bands — a roof piece that
is its own component has "feet" 8 m up (AuxBuilding_02: 162 components,
20 roof parts), so 57 units moved, median −0.55 m, worst −33.5 m; the fix
(the object's own lowest band; a unit founded by the members reaching ITS
band, the rest inherit — v1 I-8) brought it to the table above.

## 5. Why the closing build did not write the pack — the open ruling

The remaining wrong seats share one mechanism: **a shared-anchor family
founded by one small piece whose authored floor is far below the rest**
(TerminalRoads_03_004: 4 witnesses lift 400 objects 6.3 m) — v1's rigid
unit is the contact-graph STRUCTURE (welded parts), not the anchor family,
and v1's bridge seat is founded on the DECK-FACE end lines by a classifier
(`bridges.py`, TERRAIN_CARRIED via height fallback) that v2 does not have:
OTHH's `Bridge_0x` carry no `ATTR_hard_deck` (m4b), so v2's deck law has
nothing to govern and the feet law seats them on the canal bank (+5.58
where the owner accepted +0.96). Writing that into the owner's live OTHH
pack — a state accepted in sim — would be a known regression; measuring
it is the product this round can deliver honestly. The seat and the
write path are exercised end to end (8 hook twins, 10 v2 twins; the tile
build ran the hook on its own mesh), the pack write is one env variable
away, and the ruling below decides what the family/deck law is.

## 6. Open questions (≤ 3)

1. **The bridge datum without `ATTR_hard_deck`.** v2 law-from-tables has no bridge classifier. Options: (a) a table-declared deck signature (e.g. a resource-path token `Bridge` + "the family's highest large flat component is the deck top"), (b) v2 keeps v1's post-mesh for bridge families only, (c) accept the feet seat / hold. Until ruled, v2 tile builds should run the re-seat with `O4_DSF_OBJECT_REANCHOR=0` or hold bridge families.
2. **Rigid unit = anchor family or welded structure?** The shared-anchor unit is the pack-authoring truth (one datum), but a family founded by a below-datum utility piece moves everything. A `[rebake]` rule "a founding member must carry ≥ N witnesses / ≥ p % of the family's feet" or v1's contact-graph structures inside a family — owner's call (it changes seats, not just witnesses).
3. **Basin families.** The basin exclusion keys on `pm.basins[].objects` (the below-grade members); the rim pieces sharing the anchor (Dewatering_01_000, +15.1) should be excluded with them (one-line: exclude the whole unit when any member is a basin object). Ruled trivial; not done under the cap.

## 7. Build-time impact

Plan stage at OTHH 16.7 s in the per-airport wall (of which ~19 s of a
26 s profile was `obj8.solid_components` over the 1,234 resources the
basin pass never decomposed; witnesses are thinned to ≤ 64/component and
≤ 256/member); OTBD/OTBH 0.01 s (stock-only packs). Over the 1 % line —
the Fable-5 optimisation review is owed (`docs/DEFERRED_VERIFICATION.md`).
Post-mesh seat ~1 s (sampler over 147k witnesses). Mesh step of the
closing build 30.6 s.

## 8. Reuse vs rewrite

Reused from v1 (imported by the hook, never copied): `object_rebake.apply`
(477 lines: backup discipline, y-token rewrite, provenance, reversion),
`object_rebake.restore`, `object_anchor.RebakeDecision/Structure`,
`obj8_reader.load_object_file`, `mesh_sampler.MeshElevationSampler`,
`post_mesh._mesh_is_newer_than_alt / _is_protected_scenery_root /
object_anchor_worklist_path`, `config.DSF_OBJECT_REANCHOR`. Written: v2
model 214 + plan 207 + seat 217 lines, hook +214 lines in `engine_v2.py`,
`pack.py` +34, `load.py` +8, law +11 keys, pipeline +25, planar +4, mesh
dispatch +9, tool 150, twins 10 + 8.

## 9. Commits

On `lane/v2rebake` (see the lane report for the sha).
