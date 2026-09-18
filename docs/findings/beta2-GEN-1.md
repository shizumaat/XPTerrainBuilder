# GEN-1: "[v2 rebake]" prints with "Modify custom airports" UNCHECKED

STATUS: in progress

## 1. Where "[v2 rebake]" is printed, and what it writes

All ten prints live in one function, `rebake_after_mesh()`:
`Ortho4XP/src/auto_patch/engine_v2.py:791-925` (prints at :818, :821, :826,
:849, :857, :868, :874, :917, :921, :924). It is the post-mesh PLACEMENT
stage: for every `o4_v2_rebake_<ICAO>.json` plan the tile build wrote into
its own `Patches/<tile>/` dir, it samples the built mesh, cuts each pack
object into bodies and re-anchors the DSF placements.

Write surfaces:
- the PLAN/measure half writes nothing into the pack —
  `obj8_split.split_obj8()` is explicitly read-only
  (`Ortho4XP/src/auto_patch_v2/airport/obj8_split.py:317-320` "Reads the
  file and returns text; writes nothing").
- the WRITE half is `placement_write.apply_plan(...)` at
  `engine_v2.py:763-767` — that rewrites the pack's DSF (backup
  `.anchor_bak`) and writes new body `.obj` files into the Custom Scenery
  pack; also restores `.anchor_bak` objects.
- reads always resolve through `pristine_dsf_path()`
  (`auto_patch_v2/airport/dsf_write.py:130-147`) = the pack's
  `.anchor_bak` if present, else the live DSF.
- a DSF text dump is materialised via `_DSFR.ensure_dsf_text_path()`
  (`engine_v2.py:655`) into `FNAMES.airport_mod_cache_root()`
  (`engine_v2.py:651`) — our own cache root, NOT the pack.

## 2. The gate inside the rebake path

`engine_v2.py:824`: `measure_only = not getattr(tile, "modify_custom_airports", True)`
— printed at :826. Also `O4_PACK_WRITES=measure_only` (lane builds, :848)
and `config.DSF_OBJECT_REANCHOR` (:855-859).
`measure_only` is passed into `_place_objects(...)` (`engine_v2.py:894`),
which passes `write_cuts=bool(write_enabled and not measure_only)` into
`build_plan` (`engine_v2.py:754`) and RETURNS BEFORE `apply_plan`:
`engine_v2.py:757-762` — "MEASURE ONLY ... nothing written".
So: when the flag is genuinely False on the tile object, the pack is not
touched; only the plan is computed and logged.

## 3. How the Swift toggle travels to the engine

- UI: `Sources/XPTerrainBuilder/BuildPane.swift:355-357` Toggle "Modify
  custom airports" -> `buildModel.modifyCustomAirports` /
  `setModifyCustomAirports`.
- `Sources/XPTerrainBuilder/BuildModel.swift:1654-1664`: it is NOT a
  per-run JSONL argument. `setConfigValue("modify_custom_airports", ...)`
  writes the key into the GLOBAL `Ortho4XP.cfg` on disk
  (`BuildModel.swift:1666-1680`), and the comment says so explicitly.
- Engine: `modify_custom_airports` is a registry var
  (`Ortho4XP/src/O4_Cfg_Vars.py:265-277`) listed in `list_vector_vars`
  (`O4_Cfg_Vars.py:763`), hence in `list_tile_vars` (`O4_Cfg_Vars.py:844`).
  `CFG.Tile.__init__` seeds every tile var from the module globals
  (`O4_Config_Utils.py:172-173`) and the build then calls
  `tile.read_from_config()` (`o4_engine/session.py:1006-1007`,
  `o4_engine/parallel.py:1142-1143`, `:1859-1861`), which LAYERS global
  cfg then the TILE cfg (`O4_Config_Utils.py:228-280`).
- The rebake path DOES read it: `engine_v2.py:824`.
  The mesh hook passes the real Tile (`O4_Mesh_Utils.py:2556-2571`).

## 4. Verdict

LOGGING (plus wasted work), not a pack-modification bug — with one
checkable escape hatch.

- When the tile resolves `modify_custom_airports` False, `rebake_after_mesh`
  still RUNS: it loads the plans, dumps the pack DSF into our own mod
  cache (`engine_v2.py:651-659`), computes the whole placement plan and
  prints `[v2 rebake]` / `[v2 placement]` lines, then returns at
  `engine_v2.py:757-762` before `apply_plan`. No file inside the Custom
  Scenery pack (DSF, .obj, .anchor_bak) and no apt.dat is written on that
  path — the only writers are `apply_plan` (`engine_v2.py:763-767`) and
  `restore_pack_objects` (`placement_write.py:242`), both downstream of
  the early return. `split_obj8` is read-only (`obj8_split.py:317-320`).
- So the owner's console lines are the measure-only announcement plus the
  measurement itself. The design intent is deliberate ("the measurement is
  the product", `engine_v2.py:833-838`), but it reads to a user as "it is
  modifying my airport" and it costs the full placement stage per build.
- THE ONE REAL GATING RISK (same class as the color_harmonization stale-
  tile-cfg trap): the setting is ALSO exposed at TILE scope
  (`Sources/XPTerrainBuilder/SettingsLayout.swift:97`, scope `.tile`),
  while the BuildPane toggle writes only the GLOBAL cfg
  (`BuildModel.swift:1659-1664`). A tile cfg that carries
  `modify_custom_airports=True` wins over the global by the layering rule
  (`O4_Config_Utils.py:232-243`), and the BuildPane checkbox would then be
  unchecked while the engine writes the pack. CHECK BEFORE FIXING: grep
  `modify_custom_airports` in the owner's `Ortho4XP_+XX+YYY.cfg` for the
  built tiles; if it is absent, this is purely the logging/work issue. If
  it is present as True, GEN-1 is a genuine gating bug.
- Note of scope: the flag only ever covered INSTALLED CUSTOM SCENERY packs
  (`O4_Cfg_Vars.py:268-276`). Our own tile products (mesh, DSF, Patches,
  the auto_patch apt.dat patch) are governed by `auto_patch`, not by this
  switch — if the owner meant "do not touch the airport at all", that is a
  different switch.

## 5. Minimal fix shape (not implemented)

Make the OFF state silent and cheap rather than loud and busy: in
`rebake_after_mesh` (`engine_v2.py:824-828`), when `measure_only` comes
from the user's `modify_custom_airports` (as opposed to the lane's
`O4_PACK_WRITES` or `DSF_OBJECT_REANCHOR`, which exist precisely to keep
the measurement), emit ONE line at vprint(1) naming the switch and return
`counts` immediately, before the plan loop — no DSF dump, no placement
plan, no `[v2 placement]` output; keep the measure-only plan path alive
for the lane/env arms and for the tests that drive it. If the tile-cfg
check above shows a stale True, the second half is to have the BuildPane
toggle clear any TILE override for the key (a `write_tile`-style removal
for the selected tiles) instead of writing the global alone, so the
visible checkbox is the value the engine resolves.

## 6. Tile-cfg check (PM, 2026-09-18)

`grep modify_custom_airports "~/X-Plane 12/Custom Scenery"/zOrtho4XP_*/Ortho4XP_*.cfg`:
23 tile cfgs carry the key, ALL `=True` (incl. +25+051, +30+031, +60-136,
+61-133, -13-078, -13-077, +40-004). With tile-beats-global precedence the
unchecked checkbox never reaches the engine on a re-built tile: GEN-1 is a
real gating bug of the color_harmonization class, not logging only.
