# #1300 / #1324 lane lverify — handoff (paused 2026-10-27T17:43Z)

## State
- Branch `claude/lverify-coast-buffer` from origin/main 096ab9dbe.
- FIX (uncommitted work now in this WIP commit): `src/O4_Coastline_Vetting.py`
  `_witness_reads_sea` sampled `buffer(...).exterior`; GEOS returns a small
  closed coastline ring's 150 m buffer as a MultiPolygon (polygon + two
  ~1e-11 deg^2 slivers), so vetting raised `AttributeError: 'MultiPolygon'
  object has no attribute 'exterior'` (regression from #1354, 1519a09eb).
  Now every buffer part's exterior is sampled. Twin added in
  `tests/test_coastline_vetting.py` (real 53-vertex ring, tile-relative);
  that file passes 14/14.

## Measured
- KPIE (+27-083) on main, `build_airport.py KPIE --patch-only
  --allow-degraded-dem --tag lverify-kpie-main-degraded` (degraded: 25
  approach-ring cells unanswered; `--refresh-data rings` was denied by the
  permission classifier — owner must run it): verify passes, NO ring_fold,
  rows 184 — BUT the log shows `[dem] shore witness N27W083 UNAVAILABLE
  (AttributeError ...)` and `0 foreign water edges`: the shore weld never
  ran, so the original ring_fold (zone2 face 417 at 27.91218,-82.67950, next
  to the 10-24 weld's worst_at 27.91136,-82.68059: 69 snapped / 5 dropped /
  16 projected, fold_refused 0) is masked, not fixed. On main the same
  exception also hits the tile build's include_sea (O4_Vector_Map ~3127):
  +27-083 tile builds likely fail outright.
- YMML (-38+144): harness refuses (15 AUSTRALIA5M inset negatives re-asked per
  engine version: needs owner `--refresh-data dem`). Evidence instead: the
  owner's app solve of 2026-10-26 22:38 local
  (`XPTerrainBuilderData/tmp/auto_patch_v2/-38+144/YMML/YMML.report.json`)
  has `verify.defects == {}`, runway_transverse 0, runway_vertical_curve 0 —
  #1324 looks fixed (triage named #1340/#1364).

## Exact next step
1. Run the gates: `tests/auto_patch_v2`, windows_text_io,
   patch_env_classification, tile_failures, console_encoding twins,
   `tools/ratchets.py`, `test_no_airport_specific_code`.
2. Rebuild KPIE patch-only on this branch (degraded frame acceptable, or
   owner runs `--refresh-data rings` first) — confirm the shore witness now
   reads chains and check `report['ring_folds']`. If the fold returns, it is
   a weld_to_shore snap/drop/project fold (the #1275 guard covers only
   merge_sub_spacing): extend the `_fold_culprits` refusal to the weld's
   moves, general rule, twin on the face.
3. Census + matched control (`census.py`), PR "Fixes #1300" (if verify
   clean) and "Fixes #1324" only with a harness verify line after the owner's
   dem refresh.

## Captures / frames
None registered for KPIE or YMML (`frames.py list` empty). Needs the Mac
corpus (OSM_data +27-083 coastline cache, DEM). Step 1 (unit gates) can run
in a cloud container; steps 2-3 cannot (Mac corpus).
