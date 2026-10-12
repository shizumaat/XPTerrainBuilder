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

## DESIGN (as built)

Smallest change that makes the ruling true for the scenery file and its terrain files:

1. **Terrain files are staged.** New module `Ortho4XP/src/O4_Tile_Staging.py`. `build_tile` no longer
   deletes `terrain/`; it starts an empty `terrain_staged_<tile>/` beside it (`begin`) and
   `DSF.create_terrain_file` writes there (`terrain_dir`; a direct caller with no build in progress
   still writes the live folder).
2. **The previous scenery file is not moved by the encoder.** The move to `.bak` left `build_dsf` and
   is the first half of `activate_dsf`.
3. **Activation is the last act of a completed build** (`O4_Tile_Utils.activate_tile`), after the
   encoder, the downloads and the conversions, and after the Stop check:
   `install` staged `.ter` into `terrain/` (adds / replaces same names, removes nothing) →
   `<dsf>` → `.bak`, `<dsf>.tmp` → `<dsf>` → `prune` the `.ter` the new file does not name (not for a
   grouped folder, as before). At every instant the `<dsf>` in place has every `.ter` it names.
4. **A Stop activates nothing** — inside the encoder or during textures, one branch:
   `if UI.red_flag or not any(dsf_built)`. It is a cancel: no failure is named; the step says one
   line through `UI.loud_warning` (the existing `Log(level="warning")` event, so both apps' logs show
   it): "Build stopped before it completed: the new scenery was not activated. The scenery built
   before is still in place, unchanged; build the tile again to finish — the textures already
   downloaded are kept." (or "…this tile has no scenery yet…" when there is no `<dsf>`).
5. A refused activation (#585) now leaves the PREVIOUS `<dsf>` active (never moved, or put back from
   `.bak`); same codes (`scenery_file_locked` / `scenery_file_not_activated` / `disk_full`). A refused
   terrain install is the same named failure. This supersedes "State after a refusal" rows 1–2 of
   `inactive585-notes.md` ("no `<dsf>`").

No wire change, protocol stays 1.10, no catalogue code added, no app code touched.

## STATE A STOP LEAVES (stopped by the flag, or killed, at ANY moment before the swap)

* `<dsf>`: the previous file, byte-identical. `terrain/`: untouched (names and text). No `.bak`.
* Leftovers X-Plane does not read: `terrain_staged_<tile>/`, `<dsf>.tmp` (whole or truncated), the
  `.dds` that arrived. The next build empties the staging folder, rewrites `.tmp`, queues only the
  textures not on disk, and activates — nothing by hand.
* Killed INSIDE the swap (a few renames, no Stop checkpoint there): after the install and before
  the move — previous `<dsf>` with old ∪ new `.ter` (same-named ones in the new text): loadable.
  Between the two `<dsf>` moves — no `<dsf>`, `.bak` + `.tmp` beside it: default scenery until the
  next build, which repairs it.

## WHAT A STOP CAN STILL CHANGE UNDER THE PREVIOUS SCENERY (NOT fixed — `textures/` is still written in place)

* Row 4 / 9: a mask `.png` the new build no longer needs is removed, or re-saved under the same
  name; a `.dds` whose DXT format must change (mask imprint setting changed, or mask newer than the
  texture) is replaced in place. The old `.ter` then reads a changed or missing border texture.
  Only when masks or the imprint setting changed between the two builds.
* Row 1: with `cleaning_level > 1` (not the default) every `textures/*.png` is deleted at step start.
* Row 9: a converter KILLED mid-write (SIGTERM escalation) can leave a short `.dds` under its final
  name; the next build takes it as present. Older than this lane.
* What X-Plane does with a missing border texture was not measured.
* Outside this step: packs re-seated by the vector step of the stopped build (RULINGS 12d covers a
  FAILED airport, not a stopped tile).

## APPS / WIRE TODAY

A stopped tile is `TileState(state="queued", label="stopped")`; both apps set their row to
"stopped" locally at the click and match the literal `"stopped"`, so the label cannot carry more
text without app changes. The row therefore says "stopped"; the sentence above is in the log. After
the next scan the tile reads as built (its previous `<dsf>` is there) — now true.

## TWINS

`Ortho4XP/tests/test_stopped_build.py` (9): Stop during textures / inside the encoder → 0
activations, previous `<dsf>` byte-identical, `terrain/` identical in names and text, no failure,
the stopped line said; the next build asks only for the texture that had not arrived and activates
once; a completed build activates exactly once; at the swap both generations' `.ter` are present;
grouped folder not pruned; refused terrain install keeps the previous scenery; the encoder writes to
staging. `test_dsf_activation.py` (15, 4 rewritten to the new state, 2 added).
