# lfloat handoff: #1344 (KBUF), #1301 and #1279 (LFPG) floating buildings

Paused 2026-10-27T17:43Z on the owner's shutdown order. Nothing is edited in
`src/` yet; this note is the whole state of the lane.

## Measured: two mechanisms, not one

### A. KBUF terminal (#1344, 42.934592627, -78.732335196): the floor plane picks a sub-storey feet plane

Inputs: the owner's 2026-10-25 14:37 build (engine 1.50.1874):
`/Users/noah/XPTerrainBuilderData/Patches/+40-080/+42-079/{o4_v2_rebake_KBUF.json,KBUF.graded.json,o4_v2_placement_KBUF.json}`,
the mesh `~/X-Plane 12/Custom Scenery/zOrtho4XP_+42-079/Data+42-079.mesh`, and the pack DSF
plus its `.anchor_bak` (KBUF pack `Earth nav data/+40-080/+42-079.dsf`).

- `seat_feet_census.py --rebake-plan … --dsf-dump WRITTEN --rows-dump PRISTINE --mesh … --pack … --graded …`
  (the written-DSF mode), AIRSIDE GROUPS: unit:21 (the terminal frame, 10 airside members). The
  airside-contact feet float a median of **+0.92 m** above the written mesh (8 of 10 members are
  more than 0.3 m off). Complex_11/7/5/14 sit at +0.84 to +0.92. Complex_26 sits at +10.5 and
  Complex_18 at +6.8: these are upper parts and are not yet read.
- Design surface at the site: the building4/building2 pads and the `pav30#plateau:building2` apron are
  flat at **211.16** (site_read faces). Group zero `fu:21:592` = **212.07** (plan reason "one connected group
  … at 212.07"). The body file `KBUF_Terminal_Complex_11__b0_*.obj` runs y 0.812..4.780, while the authored file runs -0.10..3.87,
  so the file is lifted 0.91 m.
- WHY 212.07: I instrumented `airside_group_seat.airside_zeros` in a replay
  (`tools/v2_rebake_replay.py plan <rebake> <mesh> --graded … --tile 42 -79 --runs 1`, about 35 s/run).
  It read 107 stand-side feet. 68 are authored at y = -0.10 on the 211.16 pad, which gives candidates of 211.26.
  39 are authored at y = **-1.20**: these are the east end of the same frame
  (Complex_5 obj7304, Complex_10 obj7323, Complex_15 obj7318, Complex_7 obj7302, Complex_23 obj7312,
  around 42.93460, -78.73110), and they give candidates of 211.65..212.36. `geom/foot_planes.floor_plane` takes the HIGHEST dense
  band, which here is the y -1.2 feet, so its median is 212.07. The author's ground falls 1.1 m to the east; the patch made ONE flat
  pad (correctly: 1.1 m < `[building_pad] low_level_min_step_m` 3.0, so `planar/low_level` mints no second level).
  The object stage then seats the frame as if y -1.2 were a lower storey, and the whole west half floats about 0.9 m.
- Proposed general fix (not yet written): in `floor_plane`, candidate planes less than one storey
  (`low_level_min_step_m`) below the top dense band are the SAME level. The zero of that level is its
  LOWEST substantial band (ground_plane semantics: nothing floats, and parts may sink, as RULINGS 22c allows).
  A plane a full storey apart keeps today's choice: KMCI's curb y -5.8 vs concourse y -1.1 is 4.7 m apart, which is unchanged.
  `planar/group_low.py` (lines 99-114) and `planar/low_level.py:186` also call `floor_plane`. They inherit
  the change, so the patch and the object stage stay coherent; check both.
  Expected at KBUF: zero about 211.26. The west sits on the pad and the east sinks at most 1.1 m.
  MUST re-verify by replay that KMCI (#1214) and LFPG T2 (2A_*, fu:2:46 at 105.19) keep their zeros.

### B. LFPG (#1301 49.012943414, 2.558167642; #1279 49.012480321, 2.558229061): a companion pack that is never rebaked

- No DSF row, plan body or graded object of the selected pack (`2_LFPG_PARIS_TAIMODELS_XP12`)
  stands at either site. The floating building is **`1_LFPG_PARIS_T1_2_3_XP12`**: `AIRPORT/KHU9/K9_8,
  K9_11, K9_10…` share ONE anchor at 49.0138733, 2.5628672, **358–372 m away**. That pack has no
  apt.dat, so `airport/pack.select_pack` (one pack: the one whose apt.dat serves the ICAO) never
  reads it. Its plain OBJECT rows drape y=0 at the mesh at the anchor: **109.79 m** against the ground at the
  sites of about **106.8–107.1 m** (building73 pad 106.78). The K9_* ground floors float **+2.6 to +2.8 m**.
  Over the whole pack, 45 of 149 objects have a median low-foot gap > 1 m (owner mesh 2026-10-27 07:28).
- This is the shared-datum class (memory "shared-datum pack authoring") in a SECOND pack. Fixing it means
  the engine adopts objects-only companion packs. That is an architecture and scope choice, so it is an OWNER QUESTION:
  **Q (lfloat-B): LFPG's terminals T1/T2/T3 come from a second pack (`1_LFPG_PARIS_T1_2_3_XP12`)
  that has no apt.dat. The engine re-seats only the pack carrying the apt.dat, so those buildings drape
  at an anchor 360 m away and float up to 2.8 m. (A) Adopt a companion pack: a Custom Scenery pack with
  no apt.dat whose DSF places pack-local objects inside the airport boundary is re-seated with the main pack
  (pads, plan, DSF write). The witness must exclude overlay packs (AEP Overlays, simHeaven also place objects at
  LFPG). (B) Leave companion packs as authored and only report them. (C) Seat only the anchor: write one
  OBJECT_MSL per companion row at the footprint ground, with no split. Recommendation: A, specced first
  (consumer census of every pass that reads the pack; it is not a lane fix).**

## Exact next step
1. Implement A's fix in `src/auto_patch_v2/geom/foot_planes.py` (`floor_plane`), reading the storey
   from law (`structures.placement`/`building_pad.low_level_min_step_m`). Add a twin under `tests/auto_patch_v2`:
   one frame whose feet span 1.1 m on a flat pad seats at the pad (nothing floats); two planes 4.7 m apart keep the lower
   feet plane.
2. Replay KBUF as above, plus KMCI and LFPG from the owner's Patches plans, to compare zeros. Then run ONE KBUF closing build
   with `tools/harness/build_airport.py KBUF` and `census.py`, and `seat_feet_census` written-DSF mode
   before and after (before = +0.92 m median).
3. Raise B with the master as an owner question. Do not touch `planar/structures.py` (lane llfpgcut).

## Notes
- The harness guard reported Airport_mod_cache writes (KATL, KHMP) by concurrent processes during my
  read-only replays (CONTAMINATED from outside; this lane wrote nothing to the corpus).
- Scratch probes were in `/private/tmp/claude-501/lfloat/bin/` and may not survive the reboot. Their method: a
  `floor_plane` wrapper logging candidates; an `airside_zeros` copy logging (key, member, lat, lon, y, z) per stand-side foot;
  a DSF-text scan for OBJECT rows whose authored vertices cover a site; a drape-float scan, which is the mesh at the anchor + y_foot −
  the mesh under the foot.
- Cloud container: step 1's code and twin can run there (pure Python), but the replays, the closing build and the
  measurements need the Mac corpus, the owner's Patches and the X-Plane install. Run steps 2–3 locally.
