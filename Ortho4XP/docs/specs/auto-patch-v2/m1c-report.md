# auto-patch-v2 M1c — CYXY sim read round 3 (RULINGS 2026-09-04u)

Lane `v2round3`, branch `lane/v2round3` off main `40a3ca3f`
(9781e9f1 + STATUS), app 1.0.281 patch read by the owner. Three items,
all attributed by the spawner in 04u; each fixed synthetic-first (the v2
CLI on CYXY is the fixture — 5 s a build) and closed with ONE ledgered
harness build.

## Site numbers first (closing build, `build_airport.py CYXY --engine v2`)

Tag `CYXY_20260904T132056`, artifact ledger `46b61609f57a`, tree
`1289c45b`, body `a0b366da17d2`, 306 ways / 4,442 nodes, solve optimal,
v2 verify 0 rows; **oracle census 0/0** (LAW-TRUE TOTAL 0, PASS).
Control at the base sha `40a3ca3f`: tag `CYXY_20260904T131541`, ledger
`10f7fdbd7b16`, census 0/0.

| item | coordinate | before (owner's patch) | after |
|---|---|---|---|
| 1 sliver weld | 60.7081013, −135.0771456 | node −2366 (703.12) on cross_connector 101 (pav18) + 208 (pav5) only; junction 211 passes 0.47 m off it, no shared edge; the 0.47 m notch between 101's boundary and 211's cut edge is an UNOWNED face (dropped at overlay — the DEM drapes it) | the node (702.87–702.88) is shared by cross_connector 101, cross_connector 156 and **junction 215** (4 nodes): the notch is the junction's own face, every vertex shared, 0 T-vertices |
| 2 shape 106 | 60.7125394, −135.0752877 | one 12,466 m² face `dsf:pol17`+`pol20`+`pol123`, role **apron, airside** ("no road; or taxi/startup/apron evidence", explain read "road 0 m" while 1206 route 50 was in its centrelines) | `dsf:pol123` **parking_lot, groundside** (`source_class=lot`, "1 road(s) reach it (04u)"), `pol17` 6,581 m² and `pol20` 796 m² parking lots; at the apron mouth 60.7122971, −135.0745001 apron pav9 (87) meets lot pol123 (106) |
| 3 lot 87 | 60.714258, −135.0766894 | lot pav4 node WELDED to building9's pad at 694.77 (lot 694.77–702.17) | building9 flat at 694.26 holds no lot node; the lot's nearest node is 1.58 m away at 697.65 (lot 697.65–702.20): the set-back terrace, the lot on its own level |

## Mechanisms and fixes

### 1. Sliver weld — `src/auto_patch_v2/planar/weld.py` (new), called from `planar/overlay.py:89`

Mechanism: two sources (pav18 / pav5) whose boundaries nearly coincide
leave a face narrower than the identity spacing that no region claims
(≥ 0.5 × its area under any region fails) → dropped → DEM-draped cliff.
Fix: `weld_cells` runs on the classified cells BEFORE the zones are
derived and the rings are noded. Same-side, value-carrying, non-rigid
cells, in seniority order (`precedence.authority.order`, larger first):
a junior cell's vertices within `emit.identity.weld_spacing_m` of a
senior boundary move onto it (to the senior's vertex when one is within
the tolerance, else the nearest edge point); senior vertices within the
tolerance of a junior segment (and not already on it) are inserted into
the ring. A vertex already shared with ANY other cell (a pad, a
neighbour) is frozen. Law value `emit.toml [identity] weld_spacing_m =
1.0` (`law/model.py Identity.weld_spacing_m`): read pre-snap, so
identity spacing + the snap's half-diagonal, which also covers HECA's
post-snap 0.554 m rim (04s). CYXY: 52 cells welded, 137 vertices moved,
37 inserted, 8 refusals (sub-metre slice-noise cells that would collapse;
kept as they were), 0 T-vertices, min spacing 0.50 m, dropped faces
41 → 38. `BuildStats.weld` / `report.json planar.weld` record it.

### 2. Shape 106 — `classify/sources.py` (`road_reach`), `classify/open_default.py` (new), `classify/roles.py:256`, `classify/rules.toml [groundside] default_open_role`

Mechanism: the source reader counted only road length INSIDE a page;
route 50 ended at pol17's boundary (0 m inside) so the page read "open"
and the slice's apron default kept the merged face airside (its chain
to the runway runs through the apron and the lot pages). Fix (a):
`SourceRecord.road_reach` — 1206 routes / OSM roads that enter the page
or end within `cells.on_tol_m` of its boundary; an open page with no
taxi centreline, no startup, no apron name/cover that a road reaches is
a `lot` (cut at its own boundary). Fix (b): a face the slice scored
apron keeps `apron` only on evidence (`open_default.apron_evidence`:
taxi centreline on the face or its source, a startup, an apron name,
`aeroway=apron` cover); otherwise `parking_lot` when `_road_evidence`
reaches it, else `rules.groundside.default_open_role`
(`groundside_pavement`), gated by `requires_terminal` like the demotion.
At CYXY / SPLP / SPJC the page-level rule (a) did all the work
(`open_defaulted` 0); (b) is the twin-covered backstop.

### 3. Lot 87 — `classify/roles.py::_cut_back_groundside`, `law/tables.py::snap_margin_m` (new), `planar/zones.py:57`

Mechanism: the cut-back applied only to MIXED pads (touching airside
AND groundside); building9 touches groundside only, so lot pav4 shared
its ring and the pad's `Flat` group carried the lot node down. Second
mechanism found on the way: a 0.6 m pre-snap gap is narrower than the
0.5 m lattice's diagonal (0.707 m) and the noding merged the two rings
into one vertex again. Fix: every pad within the set-back of groundside
pavement cuts it back; the knife is the pad read on the identity grid
(precision model stripped again — `build._snapped`) buffered by
`groundside_cutback_m + snap_margin_m(law)` (the grid's half-diagonal),
so the 0.6 m holds AFTER the snap. The zone bands' groundside cut-back
(`zones.toml groundside_cutback_m`) carries the same margin — without it
a 0.35 m zone sliver opened between the pad knife and the zone band
(CYXY building1 / pav29 / cross_connector pav3) and its noding minted a
cross_shape pair (0.499 m, 0.04 m, 8 %); with it CYXY is 0/0.

## Censuses (v1 oracle `census.py`; SPLP/SPJC/HECA through the v2 CLI, not ledgered)

| airport | base 40a3ca3f | lane 1289c45b | note |
|---|---|---|---|
| CYXY (harness, ledgered) | 0/0 | **0/0** | closing build above |
| SPLP | 0/0 (M4c) | **0/0** | classification unchanged (0 lots flipped) |
| SPJC | 8/8 (CLI control at base) | **4/4** | all `junction|junction` at the apron cap — the 04s reader disagreement 04t-2 rules (cap by edge portion, v2caps); none at the reclassified pages |
| HECA | 04s: census 84/84, `mid_edge_step` 23 | see below | v2relax owns HECA's solve; report only |

HECA (v2 CLI, hard set infeasible → tier-3 apron yields as at 04s,
175 rows ≤ 0.443 m): WIP-tree arm (weld v1 + reach + every-pad knife,
zone bands NOT yet margined): census 58 (airside 53), `mid_edge_step`
**23 → 5** (all groundside), `vertex_to_edge_step` 0. FINAL-tree arm
(`1289c45b`: weld with frozen identities + explicit insertion, zone
margin): census **75** (airside 70), `mid_edge_step` **16** (11 airside,
5 groundside), `vertex_to_edge_step` **3**, worst 1.05 m, all
`cross_connector|junction` at 30.1373–30.1381 N / 31.4053–31.4058 E —
the north end of the hangar row whose hard set is infeasible. Two
changes sit between the arms (weld rewrite, zone margin). WELD-OFF arm
at the final tree (`--law-dir` with `weld_spacing_m = 0`, everything
else as shipped): census **89** (airside 89), `mid_edge_step` **29**
(all airside), `vertex_to_edge_step` **4**, same sites — the weld
removes 13 of HECA's mid-edge steps at the final tree; the rise from
the WIP arm's 5 is the zone margin's effect on the relaxed (tier-3)
HECA solve, which reshuffles the yielded rows at the infeasible hangar
row. HECA is v2relax's (04t-1 least-variance relaxation, merged on main
after this lane branched); reported, not iterated (attempt cap).

## Classification flips (role diff, base vs lane, `(role, ref, area)`)

* CYXY: `dsf:pol17` 12,466 apron → `pol17` 6,581 / `pol20` 796 /
  `pol123` 5,089 parking_lot (the item); `pav2` "New Taxiway 2"
  (1,284 m², 17 m wide, 1206 route 47 through it 40 m, no 1202
  centreline, no startup) apron → parking_lot; `pav1` "New Taxiway 3"
  (lost its touch-chain through pav2) apron 1,501 → parking_lot,
  junction 383 → groundside_pavement; `dsf:pol126` (1,517 m²) → lot
  with a 2 m² remainder piece (the pre-existing cut-remainder class);
  `pav29` service road split 13,983 → 13,946 + 37.
* SPJC: `pav3` "Aeronaval" (24,294 m², 63 m wide, route 137 through it
  33 m, no taxi, no startup) apron → parking_lot; `dsf:pol64`
  (15,417 m², route 135 inside 24 m) apron → parking_lot; the
  neighbouring pav35 / pav40 apron faces shrink by exactly those areas.
* SPLP: none.

## Twins

`tests/auto_patch_v2/test_round3.py` (4): two airside pavements 0.47 m
apart weld (shared edge ≥ 59 m, no face in the old gap, 0 T-vertices;
the tol-0 arm keeps the gap); an open page a route ENDS at is a lot
(`road_reach` 1, 0 m inside); a runway-touching page with nothing is
`groundside_pavement` beyond the proximity band (`open_default` 1,
`open_defaulted` ≥ 1) and a lot once a route reaches it; a rotated pad
touching only the landside island: cut back ≥ 0.6 m, no shared planar
vertex after the snap, no `Flat` group member in the lot, no frontage
row on it. `test_m3b.py` updated (knife = set-back + snap margin).
`tests/auto_patch_v2`: 179 passed.

## Not done / open

* `pav1`/`pav2` at CYXY and `pav3` "Aeronaval" / `pol64` at SPJC flip
  apron → lot by the letter of 04u (no listed evidence; a 1206 route
  reaches them). They may be aircraft pavement without 1202/1300 data;
  the taxiway name in an apt.dat description is not on the evidence
  list. Owner question.
* The face-level default is gated by `groundside.requires_terminal`
  (06-11: no terminal → every island is aircraft parking); 04u does not
  say whether it overrides that. Kept the gate.
* The weld is same-side only; an airside/groundside pair within the
  tolerance still terraces (groundside terrace law). Not ruled.
* The `mid_edge_step` re-census of HECA is a v2-CLI arm, not a harness
  control pair; HECA's solve is v2relax's.
* The scratch probes (`weld_probe.py`, `pair_probe.py`, `xy_probe.py`,
  `role_table.py`) were used more than once and not promoted to `tools/`.
