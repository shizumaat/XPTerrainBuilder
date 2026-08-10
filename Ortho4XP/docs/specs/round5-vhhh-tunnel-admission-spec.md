# Round 5 — Feature-A tunnel admission guards (2026-08-10, FROZEN; pre-ship)

Author: lead (Fable). Charter: owner in-sim at VHHH on 1.0.230 —
island-wide trench in the water + −21.38 m canyons through
taxiways/flat fill. Recon: ONE classifier record (T1 =
`tunnel/sea.obj` + `tunnel/sea_X.obj`, a 21,495,901 m² submerged
sea-bed shell; `sea_X` max_y −3.129 — no geometry above grade;
`solid_minimum_y_m` −28.200 overrides `body_depth_m` 4.133 via the
`min()` at object_terrain_assembly.py:~1947; floor = 7.32 − 28.2 −
0.5 = −21.38) emits one 21.6 km² `object_tunnel_trench` way claiming
all unowned ground. The five real road tunnels (T0, T2–T5, floors
+0.81…−2.19) map to OSM's mapped service tunnels and must survive.
PRE-SHIP MODE applies.

## The law — two admission guards on feature-A tunnel records
(object_terrain_features.py; both refusals log at verbosity 1 with
resource names and the measured number)

1. **A tunnel has grade-level structure.** A candidate structure
   whose maximum solid effective height is BELOW
   `TUNNEL_MIN_ABOVE_GRADE_TOP_M` (−0.5 — i.e., nothing reaches
   within half a metre of grade) is not a tunnel: it is submerged
   scenery (sea bed, wrecks). Refused before pooling can attach it
   to a sibling. (`sea_X.obj`: max_y −3.129 — the type specimen.)
2. **A tunnel is not an island.** A record whose deck footprint
   exceeds `TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2` (150,000 — generous
   for any real cut-and-cover complex; T1 is 21.5 km², 770× the
   largest real record's 27,807 m²) is refused. Minima exist
   (`TUNNEL_MIN_BELOW_GRADE_DECK_AREA_M2`); this is the missing
   maximum.

Both constants env-overridable, comments citing the VHHH numbers.
The `min(deck, solid_minimum)` arithmetic itself is UNCHANGED — it is
correct for real shells (EGLL walls); the guards keep garbage out of
it. Exclusion-set note: a refused record's resources leave the
rebake-exclusion set (they are ordinary scenery again); confirm the
pack's sea still renders (exclusions never suppressed rendering —
assert nothing else keys on them).

## Tests (run once)
Synthetic twins: submerged-shell structure (max_y < −0.5) → refused,
logged; island-scale footprint → refused; a real-shell twin (roof at
grade, 5 m deep, 3,000 m²) → admitted unchanged; the T1 arithmetic
as a regression pin (the numbers above, asserting the floor NEVER
emits). VHHH census from the cache (no build): exactly T1 refused,
T0/T2–T5 survive with their floors unchanged.

## Acceptance
Unit tests once; the cached-census check; the owner sims VHHH after
the next +22+113 rebuild (expected: flat island at Z0 except the
five real tunnels). Cache version bump so the stale classification
re-derives. One deferred-verification line.
