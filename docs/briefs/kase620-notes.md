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

## RESUME HERE
