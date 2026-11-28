# Late derive (#2206, lane llate): RESUME note, 2026-11-27 (paused by the owner)

Base `claude/project-thread-ddpu46` cac5a41a0.  Branch `claude/llate`, WIP: NOTHING HERE IS
IDENTITY-VERIFIED.  Do not merge before the bar below is run.

## Measured (current code, loaded machine, replays)

- KATL `--prefix-twice` (frames/lvec/KATL.pkl), the build's order in one process: base derive 265 s,
  late derive 181 s (planar 98 of which arrangement 68.5, structures 11; constraints 48.7; channels
  22.3; road profile 6.9; jetway 4.0).  Main-thread wall sampler (cProfile under 3.14 attributes the
  machine-memory watcher thread's waits to random frames: not usable).  Late hot spots:
  platform_split 34 s (read_levels -> unit_levels 16, low_level_split 8.8, landing_regions 4.6,
  plan_blocks 2.8), pass C 12.9, with_road_ramp 10.8, road_within_shape 9.5 (station_caps 7.5),
  build_basins 6.0, map stats (_t_vertices + _spacing) 5.7, zone_bands 5.4, shelf 5.1,
  zone_regions 5.0, plateau_cut 4.5.
- RJTT `--late-from` (cold memos, base pickle from `--gap-free --solved-out`): late wall_s cut 12.9,
  derive 524 (heavily loaded), solve 2.2.  CYYZ late planar 119 s in the cold `--late-from`.
- WHY NO "RE-DERIVE ONLY WHAT IS TOUCHED" (census, base vs late classification, non-late cells: the
  arrangement front's inputs): KATL 2 cells re-cut (objpav360#9, objpav233#wall1: the late cut's
  second `cut_roads_at_walls` moves them) + 4 ramp run-out cells; RJTT 14 run-out cells; CYYZ 1
  re-cut (pol73) + 4 run-outs.  The front differs by those, and its passes are global (one
  snap-rounding noding, polygonize order = face ids), so no front/pass reuse is exact (lmemo's
  front memo, refuted, was this).  Exact reuse is item-level only.
- Unchanged rebuild: the late derive's records ARE keyed and hit already
  (`tests/auto_patch_v2/test_backhalf_end_to_end.py::...second_build...hits_every_record_of_both_late_passes`
  passes); the app ledger's CYYZ late_derive 103-115 s are cold (new code each build).

## In this WIP commit (unverified)

1. `airport/dem_memo.asked`: an `ItemMemo` for a function that READS THE DEM -- kept with its DEM
   record, served only when `dem_record.holds`, questions replayed into a listening recorder (tested:
   `tests/auto_patch_v2/test_dem_memo2206.py`).  `ItemMemo.peek/put`, `DemRecorder.listening`.
2. `planar/unit_levels_read.read_levels` through it (key: airside/groundside WKB, shells pickle, law
   and every loaded airport field by identity, flat-site by what `ground_class` reads, deck stacks by
   value).  Hit count at KATL NOT yet read (the sampled run was stopped).  ~16 s a late derive.
3. `planar/build._t_vertices/_spacing` bulk (equal on KATL/RJTT/CYYZ base maps: 4.0 -> 1.2 s;
   t-vertex count is 0 there, the T case needs a unit test against the loop).
4. `constraints/contiguity.station_caps` probes in bulk (`_cross_sections`, `_run_at`): written,
   NOT run -- needs a test against the old loop (copy it from cac5a41a0) before anything.
5. `tools/v2_solve_replay.py --late-warm` (the base derive first, as the build orders them, so the
   late derive reads the main pass's memos) and a `LAST STAGES wall_s` line.  Needs its
   `tools/INDEX.md` note and a `test_v2_solve_replay_arms` check if the twin asks.

## Next step

1. Unit tests for 3 (a T-vertex map) and 4 (random polygons vs the old loop).
2. Frozen code snapshots per arm (`git archive` of src + this tools dir beside symlinks to the lane's
   mounts: editing src under a running replay contaminates it, lazy imports).
3. Base pickles (`--gap-free --solved-out`, base snapshot) for KATL RJTT CYYZ KDFW BIKF OMDB LGAV
   KDEN KEGE (KATL/RJTT/CYYZ exist only in the removed lane tmp: recapture).  Then per airport, base
   and arm CONCURRENTLY: `--replay CAP --from classify --late-from BASE.pkl --late-warm --emit DIR
   --rebake-plan`; sha256 every emitted file; seconds from `LAST STAGES wall_s` derive.
4. Then the next items by the list above (low_level_split/extend_levels, landing _fills,
   with_road_ramp, split_level_pits) -- exact speedups or item memos only.
