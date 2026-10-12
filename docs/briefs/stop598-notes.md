# stop598 — lane notes (issue #598, RULINGS 2026-10-12h (3))

## RESUME HERE

* Branch `claude/stop598` ON TOP of `origin/claude/inactive585` (PR #590, itself on #584);
  worktree `.claude/worktrees/stop598`.
* Census below (as measured on `inactive585` @ 772c403bb, BEFORE any edit). Design and as-built
  state follow it.

## CENSUS — what the imagery/DSF step (`O4_Tile_Utils.build_tile`) writes IN PLACE, in order

"Old DSF" = the `<dsf>` of the previous completed build, the file X-Plane reads. A Stop is the red
flag polled at the step's checkpoints; in a parallel run a child that does not answer within the
grace period is SIGTERM'd then SIGKILL'd (`o4_engine/parallel.py`), so EVERY row below is a state a
Stop can leave, not only the polled ones.

| # | When | Site | What is written / removed in the live tile folder | State if the build ends here | Old DSF still loads? |
|---|------|------|---|---|---|
| 1 | step start | `build_tile` L399 | `cleaning_level > 1`, not grouped: every `textures/*.png` DELETED (sea / inland masks, airport fade masks, `water_transition.png`) | old `.ter` files' `BORDER_TEX` point at nothing | not measured in the sim (missing border texture); default `cleaning_level` is 1, so off by default |
| 2 | step start | `build_tile` L409 | not grouped: `shutil.rmtree(terrain/)` — EVERY `.ter` deleted | old DSF present, 0 of its `terrain/*.ter` on disk | **NO** — every terrain definition of the old DSF is missing, from the first second of the step |
| 3 | encoder, per texture | `DSF.create_terrain_file` | `terrain/<tex>[_water\|_sea][_overlay].ter` rewritten one by one | a growing subset of the NEW set | **NO** until the set is whole, and then only if old ⊆ new (see the measurement) |
| 4 | encoder, per texture | `build_dsf` L1381 / L1434 | `textures/<mask>.png`: removed when the texture needs no mask any more; re-saved (same name) when it does | old overlay `.ter` may name a removed or changed mask | loads; a removed mask = missing border texture (not measured) |
| 5 | encoder | `airport_geometry.write_fade_mask`, `water_transition.png` copy | written only when absent | additive | yes |
| 6 | encoder, after the triangle walk | `build_dsf` L1836 | `<dsf>` MOVED to `<dsf>.bak` | **no scenery file at all** | n/a — X-Plane shows default scenery for the tile, for the whole encode + download time |
| 7 | encoder | `build_dsf` L1893… | `<dsf>.tmp` written, MD5 appended last | truncated `.tmp` until the last write | n/a (row 6) |
| 8 | downloads (parallel with 3–7) | `IMG.build_jpeg_ortho` | JPEGs into the shared `Orthophotos/` corpus — NOT the tile folder | arrived JPEGs stay | yes; reused by the next build |
| 9 | converts (parallel) | `IMG.convert_texture` | `textures/<tex>.dds` written by the external converter straight onto its final name; only for a texture that is absent or needs the other DXT format / is older than its mask; with imprinted masks the `textures/<mask>.png` is removed | new `.dds` added; a `.dds` of the other format REPLACED in place; a converter killed mid-write (SIGTERM path) leaves a short `.dds` under its final name | yes (a `.dds` is self-describing) — except a short `.dds` |
| 10 | after joins | `activate_dsf` | `<dsf>.tmp` → `<dsf>` — run BEFORE the red-flag check | Stop during downloads: the NEW DSF is active with whatever textures arrived (#598) | the old DSF is `.bak` |
| 11 | after activation | cleaning | `.bak` removed (`cleaning_level > 1`); `.alt` / `.node` / `.poly` / mesh / apt removed (X-Plane reads none); `remove_unwanted_textures`: `.dds` no `.ter` names are deleted (`> 1`, not grouped); DSFTool dump leftovers | — | — |
| 12 | last | `_write_imagery_manifest` | `<tile>/…imagery manifest` (`.tmp` + replace) — a record; X-Plane does not read it | absent/older manifest ⇒ `is_cached` False ⇒ the next build runs the step | — |

Not in this step: overlays (`build_overlay`, its own step, staged install since #590, into
`yOrtho4XP_Overlays`), the Masks corpus (`build_masks`, outside the tile folder), the mesh file
(`.tmp` + replace; X-Plane does not read it). The vector step's auto-patch rewrites scenery PACK
files (re-seating; RULINGS 12d) before this step — a Stop after it leaves re-seated packs under the
previous tile; outside #598, listed for the master.

## MEASUREMENT — is a rewritten `terrain/` compatible with the previous DSF?

Real pairs: 80 tiles under `X-Plane 12/Custom Scenery/zOrtho4XP_*` hold both `<dsf>.bak` (previous
generation) and `<dsf>` (current), with the `terrain/` folder the CURRENT build wrote. `terrain/…ter`
names read from both files' definition tables and checked against the folder (read-only):

* current DSF: 0 references missing on all 80 (the instrument reads true);
* previous DSF: **19 of 80 tiles have references missing** — 9 of them 100 % (706/706, 850/850,
  645/645, 614/614, 479/479, 427/427, 394/394, 285/285, 264/264; provider or zoom changed, so every
  texture name changed), the rest partial (503/831, 71/71, 52/52, 38/93, 24/51, 23/815, 4/92, 2/104,
  2/30, 1/1157);
* 61 of 80: previous ⊆ current (same imagery settings).

So a rewritten terrain folder is NOT additive in general: putting the old DSF back (or leaving it)
over the new folder is unloadable on 19/80 real pairs AFTER a whole build, and on 80/80 DURING one
(row 2 deletes the folder first). `.ter` files must be staged; the names cannot be relied on.
