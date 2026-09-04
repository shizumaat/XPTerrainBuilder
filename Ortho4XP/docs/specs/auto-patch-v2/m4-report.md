# auto-patch-v2 — M4 report: structures (tunnels, road bridge decks) at OTHH and LEMD, prototyped on SPJC

Lane `v2m4` (Fable, owner 2026-09-03h), branch `lane/v2m4` off main
`e4b9b7d0`. Every file ≤ 1,000 lines (largest `planar/structures.py`
859); no environment reads; every law value from the TOML tables (five
new keys in `structures.toml [tunnel]`, §6); nothing imports v1. Commits
in §9, on the branch, not merged.

Build: `cd Ortho4XP && PYTHONPATH=src venv/bin/python -m auto_patch_v2 build ICAO --out DIR`
(production DEM frame, guard armed, read-only). The oracle census is
`tools/harness/census.py`, the tunnel oracle
`tools/tunnel_portal_acceptance.py --profile OTHH|LEMD`.

## 0. Site first — the owner's four OTHH coordinates (v1 1.0.275 → v2 M4)

| site | v1 (09-03b closing build) | **v2 M4** |
|---|---|---|
| wall node 25.2715296,51.6022683 | `tunnel_wall` 4.00 (ramp −1.12 beside it) | `tunnel_wall` **3.96**, ramp −1.14 beside it (5.10 m) |
| ramp mouth node 25.2715366,51.6022718 | `tunnel_ramp` −1.12 | `tunnel_ramp` **−1.14** |
| 25.2556192,51.6080938 | `tunnel_ramp` −1.10 | `tunnel_ramp` **−1.14** |
| 25.2556004,51.6080853 | `tunnel_wall` (unvalued node) | `tunnel_wall` **3.96** |

OTHH's DEM is the production frame's constant inset at 3.96 m (v1's
4.00 was its own crown-frame value). No road shape exists outside the
wall: v2 emits no OSM roads at all, and the pavement the structure
cuts stops at the wall's outer edge (its vertices there ARE the crest).

## 1. The 08-30l consumer table, RULED (v2's consumers of the new shape class)

The new faces are `tunnel_ramp` (role registered, groundside, 4 %
longitudinal / 2 % transverse), `retaining_wall` (ref exactly
`tunnel_wall` — the oracle's population key; non-value, airside) and the
terrain deck (`service_road`, ref `bridge_deck:<way>`). The gap between
ramp and wall is NO face (the arrangement drops it; the mesh
triangulates it — 09-01c).

| consumer | reads | ruling for tunnel faces | where |
|---|---|---|---|
| `planar/overlay` + `zones.zone_regions` | cells, keep-outs | the ramp / wall / deck are cells that CUT every pavement they run through except the runway family and pads; the structure footprint (ramp + gaps + bands) is a KEEP-OUT the zone regions subtract — **zones stop at the wall** | `classify.Classification.keepouts`, `planar/structures.build_structures` |
| `constraints/precedence.view` | caps | ramp = governed (4 %); wall = ungoverned; deck = governed (road 8 %) | tables only |
| `constraints/zones.zone_bands` | strip vertices | a strip vertex on a wall edge carries the crest and gets NO band (measured IIS: two crest pins vs one mandatory-down row) | `zones.py` (one line) |
| `constraints/no_step` | airside value roles | ramp is groundside → excluded; wall non-value → excluded; deck groundside → excluded | tables only |
| `constraints/transverse.axes` | centrelines | none in a structure (OSM ways are not breaklines in v2) | — |
| `constraints/contiguity` / `roads` | `families.road_cross_section.roles` | the ramp is its own class (not in the road family): the walk does not bind it; the deck IS a road and is walked | tables only |
| `constraints/apron` / `taxi` | ring pairs | the cut pavement's ring runs along the wall's outer edge; those shared vertices carry the crest under the ground rule (§3) | shared vertices, no edit |
| `constraints/strips` | runway groups | a wall inside the runway strip keep-out is REFUSED at planar build (`retaining_wall.in_runway_strip = false`); the ramp never crosses the runway family (`ramp_cuts_runway_family = false`, refused) | `planar/structures` |
| `constraints/pads` | pads | a pad across the approach CLIPS the ramp at the pad edge with the gap in between (08-07 r3); a mouth against a pad refuses | `planar/structures` |
| `verify/steps` | ring pairs | ramp ↔ wall = groundside ↔ airside (designed separation, skipped); the 0.6 m gap clears the 0.5 m proximity knob; wall ↔ pavement share vertices (no step) | no edit |
| `verify/strips` seam tear | wall-straddle | v2 emits walls now; the oracle's straddle exemption reads role `retaining_wall` (unchanged) | — |
| `emit/osm_adapter` | roles → aeroway | `tunnel_ramp`/`retaining_wall` from the register (`taxiway`/`apron`); the mesh reads altitudes only | no edit |
| seam band | graticule | a mouth on a tile line is cut by the band like any face (untested: no M4 airport crosses one) | — |

## 2. Per-airport, end to end (single runs, production frame)

| | SPJC (prototype) | **OTHH** | **LEMD** |
|---|---|---|---|
| bores (uncovered) / mouths / duals merged | 10 (8) / 4 / 2 | 22 (13) / 18 / 8 | 91 (62) / 58 / 11 |
| tunnels emitted / decks / refused | 2 / 0 / 0 | 8 / 0 / 2 | 19 / 1 / 22 |
| load / classify / planar | 3.7 / 0.4 / 0.8 s | 10.2 / 2.3 / 2.1 s | 5.7 / 2.1 / 2.0 s |
| constraints (structure rows) | 1.2 s (1,246) | 3.9 s (4,135) | 3.7 s (19,826) |
| solve (HiGHS, OPTIMAL) | 4.9 s | 5.4 s | 7.3 s |
| LP | 826,708 ≤ + 1,810 = rows, 20,511 cols (9,332 z) | 2,481,962 + 5,996, 50,307 cols (23,399 z) | 2,277,721 + 4,036, 48,323 cols (22,396 z) |
| emit / verify | 0.4 / 1.0 s | 1.0 / 2.8 s | 0.8 / 3.9 s |
| **total** | **12.2 s** | **27.7 s** (v1 434 s) | **25.4 s** (v1 574 s) |
| planar | 411 faces, 0 T-vertices | 952 faces, 0 T-vertices | 1,257 faces, 0 T-vertices |

## 3. Census by family — v1 oracle on v2's patch, and the v2 verify

| family | SPJC v2 (M3b: 1) | OTHH v2 | OTHH no-structure control arm | LEMD v2 | LEMD no-structure control arm |
|---|---|---|---|---|---|
| plane_gradient | 1 (gs, M3b's sliver) | 1 (stub) | 1 | 12 (10 airside) | 12 |
| strip_seam_tear | 0 | 1 | 1 | 1 | 1 |
| runway_crown | 0 | 0 | 0 | 2,185 | 2,193 |
| every other family incl. `wall_in_runway_strip` | 0 | 0 | 0 | 0 | 0 |
| **adjudicated / airside** | **1 / 0** | **2 / 2** | 2 / 2 | **2,197 / 2,196** | 2,206 / 2,205 |
| v1's own patch (control) | 686 / 596 | 1,528 / 1,202 | | 1,180 / 617 | |

The v2 verify agrees with the oracle row for row on every family it
reads. **M4-attributable census rows: 0 at all three airports** — the
control arm (same tree, `build_structures` stubbed) reads the same rows
at the same sites: OTHH's tear at 25.26772,51.60090 and stub plane
row are pre-existing v2 classes; LEMD's `runway_crown` 2,185 is a v2
runway-family class at LEMD (its four runways' declared drops; not a
structure; not a milestone airport before M4 — **the LEMD airside bar
is NOT met and the class is M5's / a runway lane's, not M4's**).

## 4. Tunnel acceptance (`tunnel_portal_acceptance.py`, v1 control → v2)

| check | OTHH v1 | **OTHH v2** | LEMD v1 | **LEMD v2** | SPJC v2 |
|---|---|---|---|---|---|
| mouth sites / canonical | 10 / 9 | **8 / 8** | 16 / 13 | 17 / 13 | 2 / 2 |
| ramp_wall_gap (shared ids, bar 0) | FAIL 23 | **PASS 0** | FAIL 14 | **PASS 0** | PASS 0 |
| wall_top_flat (worst, report) | 3.45 m | **0.00 m** | 3.07 m | 1.42 m | 0.01 m |
| over_cap_ramp_rows | 136 | **0** | — | 0 | 0 |
| covered_span_clean | PASS | FAIL 1 (§5) | SKIP | SKIP | SKIP |
| site_reach / mouth_vertex_reach | 7.0 / 9.0 | 6.4 / 8.6 | 1.6 / 1.6 | 1.9 / 2.0 | 0.3 / 3.1 |

v2's own readers (`verify/structures.py`): `tunnel_ramp_wall_gap` 0
everywhere; `tunnel_wall_top_flat` 0 at OTHH/SPJC, 63 pairs over the
0.1 m quantum at LEMD (worst 1.42 m, §5); `tunnel_mouth_canonical` 0
at OTHH/SPJC, 8 at LEMD (§5); `tunnel_deck_clearance` 0;
`wall_in_runway_strip` 0.

## 5. Residuals (attempt cap: per family two; LEMD feasibility took seven
distinct IIS-named mechanisms, each a different row class — listed in §7)

* **OTHH `covered_span_clean` 1** — a runway zone-2 `graded_strip` vertex
  at 25.27689,51.59481 sits at 2.79 m (DEM 3.96) 23 m off the D bore;
  identical on the no-structure control arm: a v2 zone class, not M4.
* **OTHH `-8342` refused at both mouths** ("the mouth stands against
  building pad building2"): a 3.5 m service bore whose mapped ends sit
  against a terminal pad; v1 emitted two canonical sites there
  (25.2548815,51.6201318 / 25.2538750,51.6215682). 08-07 ruling 3 makes
  the pad the portal; a ramp shorter than one station is not emitted.
* **LEMD 22 refusals** of 58 mouths: 11 mouths against pads (building13
  / 15 / 16 — the terminal shells), 4 approaches bending tighter than
  the corridor half width (self-intersecting rings; a buffer repair would
  mint off-grid vertices, the merge class), 5 overlapping corridors at
  the T4 portal complex (2+2 carriageways plus service lanes whose
  separation diverges beyond 31h's test — the narrower is refused), 2
  where the 4 % climb does not meet the DEM within 600 m (real relief).
* **LEMD `wall_top_flat` 1.42 m** — under the ground rule (§3 of the
  generator's docstring; open question 1) a band station shared with a
  road that solved below the DEM carries the road's value while the next
  bare station is the DEM; the oracle REPORTS this (no bar); v1 read
  3.07 m.
* **LEMD `tunnel_mouth_canonical` 8** — 2 "2 wall pieces at the mouth"
  at the deck-severed tunnel (`-17295+-7905@1`, deck `-11828`: the deck
  cuts the U into pieces), 3 mouth walls 0.11–0.38 m off the 5.1 m
  relation where the cap is shared with ground that is not the DEM, and
  3 sites (2.6 / 4.7 / 5.1 m) where the reader's mouth end is not the
  cap end (ramps that DESCEND outward under the ±4 % cone, or a
  pad-clipped stub) — a reader residual, not adjudicated by the oracle,
  which reads those sites canonical.
* **LEMD 4 non-canonical oracle sites**: 2 redundant band pieces (the
  deck site), one unwrapped end (open 0.13 > 0.10: a corridor whose
  cut pavement ring runs across part of the cap), one "unmerged" pair
  (two collinear ramp pieces of one clipped run).
* **`anchor` absent from v2's sidecar** — the oracle prints site
  coordinates as 0,0 (report only); `SIDECAR_KEYS` is closed by design.

## 6. Law tables and model extended (03e; additive)

`structures.toml [tunnel]`: `wall_band_width_m` = 1.0 (M0 Q2, stated
from the §F1 "band is ~1 m wide" read), `lane_width_m` 3.5,
`default_lanes` 2, `dual_carriageway_max_separation_m` 40 (31h),
`max_ramp_length_m` 600. Schema `Tunnel` + 5 fields. `model/structures.py`
(`Tunnel`, `Deck`, `Basin` records), `PlanarMap.structures`,
`Classification.keepouts`, `zone_regions(…, keepouts)`.

## 7. What the IIS named on the way (each a mechanism, each deleted)

1. identity snap merging a ramp corner with the cap corner (0.85 m →
   one 0.5 m grid point) → structure vertices born ON the grid, the
   band snapped AWAY from the ramp; 2. a strip vertex on the wall banded
   toward the taxiway lip → zones stop at the wall; 3. the ramp's
   within-shape law over the chord of a curved corridor (6.9 %) → all
   ring pairs at the cap over the direct distance, the ramp planned for
   the chord; 4. crest = DEM pins at 1.07 % along an apron edge (1 %
   cap) → the ground rule; 5. deck DEM pins at 11 % across a 5 m deck
   edge → the deck is road, solved; 6. a clipped stub ramp's top edge
   shared with the apron → the portal-face gap; 7. the mouth datum from
   the axis point sample in a cutting (cap 2 m higher) → the datum is
   the cap centre's DEM.  Plus the lever: tying the mouth to the cap's
   solved crest let the ramp's DEM pull lift an apron 0.49 m — the
   ramp's objective target is now its own design profile
   (`planar.structures.ramp_targets`).

## 8. Mesh bar (`tools/run_tile_mesh_only.py 25 51 --patches-as-is`, 3 runs per arm, foreground, nice 0, medians)

| arm | input segments | constrained edges | triangles | step 1 median | step 2 median |
|---|---|---|---|---|---|
| v1 (data-repo OTHH patch) | 228,476 | 284,467 | 753,661 | 23.69 s (23.29 / 23.69 / 23.71) | 162 s (161 / 162 / 162) |
| **v2 M4** | **222,042** (−6,434, −2.8 %) | **270,024** (−14,443) | 727,321 | 24.16 s (24.11 / 24.16 / 24.38; +2 %, inside the ±25 % floor) | **147 s** (159 / 146 / 147) |

Both arms: the guard reports the same single blocked warm-pass
`N25E051` inset-manifest rewrite (identical frame both sides, not a
patch effect — the M3b precedent).

## 9. Twins and commits

`tests/auto_patch_v2/test_m4.py` (5): tag widths; the dual bore as one
ramp per mouth with gap, wall and cap, the apron cut, 0 T-vertices; the
deck severing the ramp and the pad clipping it clear of the pad;
generator rows (all-pairs 4 % Diffs, clearance Offsets, one pin per
vertex, crest by ground) with a solve → emit → verify round trip
reading 0 on every acceptance key; the readers firing on a bent crest.
The 67 existing v2 twins pass. Commits on `lane/v2m4`: `bbfef674`
(code, tables, twins) · this report.

## 10. M5 brief skeleton — HECA / KCLT: scale and relief (03k-dependent)

| item | what M4 leaves | M5 |
|---|---|---|
| scale | OTHH 23.4k z / 2.48 M rows solves in 5.4 s; HECA ≈ 4–6× OTHH's vertices; `apron_within_shape` (528 k rows at OTHH) and `no_step_pairs` (143 k) are the two all-pairs families | thin to K-nearest per the tables' own `no_step.k`; apron all-pairs → spine-chord pairs only (the census's "nearest-spine chord only") |
| relief | LEMD's 85 m-class DEM produced every M4 IIS; the ground rule (open Q1) | HECA's 85 m across the runways: the runway profile + zone bands under relief; the pad class (03k) |
| runway_crown at LEMD | 2,185 rows, pre-existing | attribute (declared drops vs the built crown at 4 runways) before HECA |
| tunnels at HECA/KCLT | KCLT's tunnel (memory `kclt-tunnel-attribution-r10`) | the same generator; the deck law with an object (`hard_deck` + footprint from the OBJ8 — not loaded in v2's `dsf.py`) |
| basins | not generated (§11 Q4) | LEMD T4S + OTHH drainage need OBJ8 solid-depth reading (`airport/obj8.py`) |

## 11. Open questions (≤ 5)

1. **The ground rule** (generator docstring): a wall vertex the governed
   ground shares takes the ground's value (03i), a bare one the DEM
   (09-03b). Ratify, or is the crest the DEM even against an apron at
   its cap (the IIS then refuses the tunnel)?
2. **Mouth datum = cap-centre DEM − 5.1 tied to the cap's solved crest**
   (exact where bare; where the cap is shared, the mouth follows the
   ground). Is the covering SURFACE's value the datum (this reading), or
   the DEM point sample?
3. **Dual carriageways transitively** (a 2+2 with service lanes = one
   ramp) and the overlap refusal of the narrower corridor — ratify 31h's
   extension, or emit a fork?
4. **Basins**: v2's DSF loader reads no OBJ8 geometry, so no floor can be
   declared from the pack (08-26 keys the floor on the deepest solid).
   Add an OBJ8 reader (M5), or take the declared floors from another
   source?
5. **LEMD `runway_crown` 2,185** — a runway-family class at a 4-runway
   airport; which lane owns it before M5 builds HECA?

NOT done: basins/pits (Q4); hard-deck OBJECT decks (no footprint / deck
top in v2's `DsfObject`); CYXY / SPLP re-census after the zone keep-out
(`DEFERRED_VERIFICATION.md`); the five-airport sweep (orchestrator);
solve `--runs 3` (single-run walls only; the LP solve is 5–7 s of a 25–28
s build).
