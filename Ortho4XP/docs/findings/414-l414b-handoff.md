# #414 lane l414b — handoff (paused 2026-10-27 for shutdown)

Branch `claude/l414b-ramp-orient` (PR #1567, already merged into batch AK
`claude/batch-ak-beta5` / PR #1568; the master pulls new commits).

## State
- DONE and pushed before this pause: RULINGS 2026-10-28h (1)(2)(3) + the
  `headroom_cover_min` key (confirmed by 2026-10-28l (1)), #1463 reapplied.
  Closing build `l414b3_OTHH` + matched control `l414bctl_OTHH` are
  registered (frames lane `l414b`).
- IN PROGRESS (this WIP commit): RULINGS 2026-10-28l (2), "a step between
  neighbouring bays under a shared wall that reaches below both floors is
  lawful".
  - Committed earlier (`064ed7f3f`): `WallCorridorRecord.wall_bands` and
    `Tunnel.wall_bands` (each wall: plan ring, lowest rendered z), set in
    `wall_family` / `planar/structures._wall_bands`; new
    `pipeline/shared_wall_steps.py` publishes one `wall_terrace` joint per
    shared wall (shape label `shared_bay_wall`), hooked into
    `publication.terrace_joints_ll`; code-digest lists keyed; twins in
    `tests/auto_patch_v2/test_docklanes414.py` (deep wall -> declared,
    shallow -> nothing).
  - Measured on build `l414b4_OTHH` (HEAD `064ed7f3f`, /tmp/harness, NOT
    registered): census law-true 1133 (control 1117, l414b3 1139). The joint
    line was the AUTHORED band axis, which sits ~0.1-0.5 m beside both
    emitted ramp rings (rings snap to the 0.5 m identity lattice; the dock
    wall is 0.3 m), so the largest rows (0.85 m mid_edge / vertex_to_edge at
    25.28320-25.28321, 51.60404-51.60405) did not cross it and stayed.
    Only 8 of 18 step rows were forgiven. Also found: the two halves of a
    LEVEL corridor (Terminal_Base_2_5 @0/a, @0/b) were declared as
    neighbours — must be excluded.
  - UNCOMMITTED-then-WIP (this commit): `shared_wall_steps.py` rewritten so
    (a) a pair sharing BOTH walls (halves of one corridor) is skipped and
    (b) the line is the MIDLINE BETWEEN THE TWO EMITTED RAMP REGIONS
    (`_between`, samples of the band axis moved to the midpoint of the
    nearest points on each corridor's ramp faces, `_ramp_faces`).
    The twin `test_a_deep_shared_wall_declares_the_step_between_two_bays`
    now FAILS: its stub planar has no `faces` (the `_ramp_faces` lookup
    needs `planar.faces` / `ring_vertices`). Fix the stub (give it
    `faces={}` so `_between` falls back to the axis) or make `_ramp_faces`
    tolerate a planar without faces.

## Exact next step
1. Make the twin pass (above); add a twin where the two ramp regions are
   offset from the authored band (midline used, chord between rings
   crosses it).
2. Run `tests/auto_patch_v2/test_docklanes414.py`, the closure twins
   (`test_stage_code_closure`, `test_step_code_closure`,
   `test_patch_code_closure`) and `tools/ratchets.py`.
3. ONE OTHH closing build (`build_airport.py OTHH --patch-only --tag
   l414b5_OTHH`), census with `--rows-json`, diff against the registered
   control `/Users/noah/XPTerrainBuilderData/.harness/frames/l414b/l414bctl_OTHH.osm`
   (scratch diff script: `Ortho4XP/tmp/l414b/rowdiff.py` in the lane tree,
   gitignored). Bar: the 26 step rows at 25.28318-25.28321,
   51.60404-51.60406 gone; hairline_pair (7) and the 0.11 m within_shape
   building|tunnel_ramp row are NOT steps under the wall and may remain —
   report them. Note main moved (merged 5211b698f) since the control.
4. Register the build, push, report the census delta.

## Captures / frames
- OTHH capture `frames/m12/OTHH.pkl` (synthetic reads); control patch
  `frames/l414b/l414bctl_OTHH.osm`; prior lane build `frames/l414b/l414b3_OTHH.osm`.

## Cloud container?
Steps 1-2 yes (pure Python twins, ratchets). Step 3 (OTHH build/census) NO:
needs the Mac corpus (`/Users/noah/XPTerrainBuilderData`) and the
Aeroscape OTHH pack in the X-Plane install.
