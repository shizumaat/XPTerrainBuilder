# kase620 — finishing PR #629 (#620; RULINGS 2026-10-12q (1))

Branch `claude/kase620` (from `origin/claude/rwyend620` 820143f01 — that name is held by the old
worktree `.claude/worktrees/rwyend620`; the master re-points the PR). Worktree `.claude/worktrees/kase620`.
Scratch `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/466e18b3-e03c-471f-b042-c64d8df4e04d/scratchpad/kase620`
(`rp.sh ARM ICAO PKL` = replay from planar + emit + verify + profile; `rows.py PKL V...` = every row on a vertex;
`faces.py PKL END FACE...` = faces / vertices near an end in the runway frame).

## Item 1 — KASE 15: MECHANISM (by intervention, capture `frames/pads67/KASE.pkl`)
Rows on the two centre-line vertices (v1584 break 61.1 m, v1589 outer ring 76.6 m; arm a0 = 820143f01):
* v1584: 2 × resa_transverse (slack 2.0 / 1.4 m), 2 × end-profile CHORD (lo −1.968 hi +0.14, act −0.621), 2 × FAA end-edge rate
  (±1.307, act +0.585).  v1589: 2 × resa_transverse, 1 chord (lo −2.741, act −2.050), 1 rate.  All priced (300), none hard, none binding.
* NO transect PAIR row between them.  `constraints/strips.end_corridor_longitudinal` ran the transect block OUTSIDE its
  `for ring_idx in (1, 2)` loop, so it read the leaked index (2) — transect pairs were minted at the FAR end of every runway only.
  KASE 15 is end 1.  Nothing "outside the strip rows" holds the ground: the row was never stated (which is why every drop arm
  left it unchanged).  INTERVENTION: loop the block over both ends -> −9.23 % becomes −5.94 % (= 5 % + q/15.5 m), dz at band end −2.05 -> −1.56.
* SECOND cause, the 15 census rows: both READERS (`verify/strips.groups`, `check_grade._runway_strip_groups`) fit the runway axis
  to every runway-role ring.  KASE 15 has a 60.2 m x 42 m paved pad beyond the end (face 1, role runway, the runway's ref — a §40
  shoulder; apt.dat row 100 declares no overrun at 15), so the fit ran 60 m long (L 2566.7 vs slab 2500.7), width 152 m
  (end rect half 152 vs 96): every 15-end station read 60 m short (the 61 -> 76.6 m pairs judged at the 3 % near cap), and at
  the 33 end vertices 96-152 m lateral were read as end band.  The generator / break / --profile use the SLAB (§40 (1)/(4)).
  FIX: `runway_axes` sidecar rows gain the two overruns; `verify.strips.published_slabs` / `end_groups` and the harness reader
  frame the end family on the slab.  KASE runway_end_skirt 15 -> 0.
* THIRD, what the breakline made: the break at 61.0 m lands 0.85 m behind the pad's far edge (60.2 m) and no row tied the
  ground to that edge (the transect pairs pair VERTICES on one line; the pad corners stand at t = +/-21) — pad 2340.66,
  break vertex 2340.22: 0.44 m in 0.85 m.  FIX: the TRANSECT FOOT (`end_transect_foot`): an end-band vertex follows the nearest
  crossing inward of its own line with runway-role pavement of the runway's ref beyond the end, by the profile's increment,
  one-way (chord head -> also post-solve clamped).  KASE 15 now: pad 2340.66 -> 2340.50 -> 2339.72 (−5.03 %), band end +0.88 m fill.

## Item 2 — tolerance: ONE key
`emit.instrument.strip_edge_noise_m` (0.15, unchanged) through `law.tables.end_profile_noise_m(law, reader=)`: generator = key −
materiality (floor 0); readers = key (floor `rounding_noise_m`).  0 = the cap exactly.  Tables below.

## Item 4 — NLWF 25 (and what the same reads found elsewhere)
* The 2.8 % pair (v329-v328, 37 m, over by 0.16 m) stands on a mapped service road crossing the end band: the road's
  `road_ramp` equality to the DEM + its own caps hold it.  ROAD CAP GOVERNS (RULINGS 2026-10-02ag (2)): the end family
  (pairs, transects, feet — the chords already did) and `resa_transverse` no longer state or read a row on a
  `road_cap_governs` vertex.  NLWF harness census: runway_end_skirt 3 -> 0, resa_transverse 0, LAW-TRUE 81 -> 78.
  (The replay's own `--verify` does not carry `road_cap_governs` — it is added in `pipeline/build.py` — so it still prints
  those rows; the harness census on the emitted patch is the reading.)
* KBFI (new capture `frames/kase620/KBFI.pkl`): the end rows bound an APRON edge two-way (ring pairs of two apron-edge
  vertices; FAA three-station rate rows over them) — the tolerance arm moved 11 apron vertices <= 0.20 m.  Fixed: a pair of
  two pavement vertices is not stated, a mixed pair is one-way (ground follows), a rate triple with a pavement station is
  not stated; readers the same.  Tolerance arm now moves 0 airside vertices.  Base -> arm still moves 6 apron-edge
  vertices <= 0.07 m: with BOTH end generators dropped the same 6 move 0.07 m — the breakline re-nodes the apron's ring
  (8 new vertices on it), no row.

## Measured (matched replays from planar: base = origin/main 89693e99d in worktree kase620base, arm = this branch)
See `table_final.txt` in the scratch dir; the final report carries it.

## Closing builds (harness, this tree)
* KASE `kase620_KASE` 37.7 s body b6d21d6dffda: runway_end_skirt 0, LAW-TRUE 3493; 15 end −0.59 % then −5.03 %.
* SPJC `kase620_SPJC` 83.4 s body c24798c27bf5 (= the rwyend620 build's body): runway_end_skirt 0, LAW-TRUE 3439.
* CYCG REFUSED by the harness: the merged engine is 1.50.1836 and the tile's HRDEM no-coverage negative was recorded by
  1.50.1835 — it wants `--refresh-data dem` (a shared-corpus event; the master's call, not a lane's).  CYCG stands on the
  matched replay pair.

## Final per-end table (matched replays; census = harness census on the emitted patch; q0 = the tolerance key at 0)
Columns: first-segment grade to the break, then the following segments | dz at the break, dz at the band's end @ its distance.

Residuals named: CYXY keeps 6 runway_end_skirt rows (4 lip vertices at two ends where the zone-band row and the end chord
both price one vertex and split 0.24-0.26 m; 2 where a taxiway (pav9) stands 0.4 m above a code-1 runway's end inside its
band and its adjacent ground follows the taxiway), +2 resa_transverse at that taxiway, +24 within_shape rows on the
role-less  feature way (the census reads that way all-pairs at 1.5 %: 14 rows on it at base) where the
band's rim at the bluff is lifted <= 0.95 m.  KASE +3 resa_transverse (6.4-7.2 % over 48 m): the breakline's own lateral
pairs on the valley side.  HECA 05R: the band's end cut 2.04 m / 1.75 m (rising ground, the climb surface).
HECA base -> arm: 375 apron vertices <= 0.05 m (runway 0, taxi 1 @ 0.03); arm -> q0: 0 — see the drop-arm intervention.

## Suites
Full non-Qt on the final code: 9,651 passed, 19 skipped, 1 xfailed, 1 xpassed (169 s; includes tests/auto_patch_v2).
ratchets: DUPLICATE PASS, LAYER PASS; size WARN check_grade.py 13,793 -> 14,326, publication.py 1,171 -> 1,282 (main's
growth + 9), project.py 1,039, run_checks 1,194 lines.

## RESUME HERE
* Nothing open in code.  Not done: the CYCG harness build (corpus refresh needed, above); no push (local branch
  ); the CYXY lip / taxiway-zone conflicts and the terrain_edge census reading are findings for the master.
