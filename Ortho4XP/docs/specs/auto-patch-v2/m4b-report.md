# auto-patch-v2 — M4b report: basins / pits and hard-deck OBJECT bridges from the pack's own OBJ8 geometry, at OTHH and LEMD

Lane `v2basins` (Fable, owner 2026-09-03h), branch `lane/v2basins` off main
`136f03a2`. Every file ≤ 1,000 lines (largest `planar/structures.py` 923);
no environment reads; every law value from the TOML tables (twelve new
keys in `structures.toml [basin]`, §6); nothing imports v1 (the law twin
cross-checks eight of the new constants against v1). Commits in §9, on
the branch, not merged.

Build: `PYTHONPATH=src venv/bin/python -m auto_patch_v2 build ICAO --out DIR`
(production DEM frame, guard armed, 0 blocked writes). Oracles:
`tools/harness/census.py`, `tools/tunnel_portal_acceptance.py`.

## 0. Site first — what the pack's objects say, and what was emitted

| | **OTHH** | **LEMD** |
|---|---|---|
| placements / resolved / unresolved / stock `lib/` | 11,902 / 11,902 / 0 / 1,901 | 2,498 / 2,497 / 1 (`AS_LEMD/Objects/…OldTerminal_FSX-LEMD83.obj`, absent from the pack and the library index) / 634 |
| resources parsed (OBJ8 files), object read wall | 1,366, 11.3 s | 400, 4.3 s |
| placements with genuine below-grade solids (local grade) | 44 | 76 |
| hard-deck (`ATTR_hard_deck`) objects | **0** | **0** |
| below-grade regions / ≥ `min_area_m2` / basins emitted / refused | 122 / 2 / **2** / 0 | 290 / 1 / **0** / 1 |
| **basin:0** | Dewatering_02 (2 objects): floor **−10.74**, R_est 3.96, deepest genuine solid −13.20 rel. (rendered −9.24), 4,321 m², covered 2 %, at 25.252116,51.624580 | — |
| **basin:1** | Dewatering_01 (2 objects): floor **−9.06**, R_est 3.96, deepest −11.52 rel. (rendered −7.56), 5,108 m², covered 19 %, at 25.295715,51.603583 | — |
| refused | — | basin:0 32,542 m² at 40.453750,−3.575457 (the old T1–T3 terminal level, 8 objects): **51 % covered** by the pack's own geometry above the contact band (> `max_covered_fraction` 50 %) |
| Drainage_01–06 (v1's six BOWL facilities) | under `min_area_m2`: the clipped-below-2.5 m footprints are 641/134, 479/100, 725/81, 310/91, 19/48, 938/333 m² per member pair (closed regions 544, 394, 230, 197 … m²) — listed, not emitted (§5) | — |
| emitted faces | floor `tunnel_trench` `basin_floor:0/1` (24 / 21 nodes, every node at the floor), wall band `retaining_wall` `basin_wall:0/1` (26 / 23 nodes, crest 3.96 = the DEM all round) | none |

OTHH object bridges: none — the pack's `Bridge_0x` objects carry no
`ATTR_hard*` at all (measured: 0 files under `Buildings/Bridges Bus/`
mention it), so the object-bridge law had nothing to govern at either
airport; it is twinned synthetically (§8).

## 1. The two findings that shaped the law (attribution before fix)

**A. The LEMD pack on disk is v1-rebaked.** `.anchor_bak` backups sit
beside 1,517 objects across the two packs (`.o4_reanchor_provenance.json`:
LEMD 281 entries, OTHH 265). The T4S family was lifted **+3.4227 m**
(`basin_group_seat`, seat datum 600.51, anchor ground 597.09): the
witness `Ground-FSX-LEMD36.obj` reads min y −7.03 in the backup and
**−3.61 on disk**. Other clusters were re-seated by v1's generic
per-structure y-bake with deltas to **−35 m** (`Munoza-LEMD70` −1.75 →
−35.84; `LEMDgrass` −1.84 → −31.50; `Munoza-TEJ1` +12.30 → −18.61).
v2 reads the pack as X-Plane renders it — the files on disk.

**B. Authored y is not depth.** X-Plane drapes a placement at ITS ANCHOR
(`z = DEM(anchor) + agl + y`); LEMD is one flat-plane family on 30 m of
real relief (Muñoza 565.7 m vs the anchor 596.0 m — both DEM frames
agree). Under 08-26's letter (clip below the authored −2.5 m plane) the
on-disk pack minted **75 regions ≥ 1,000 m² at LEMD** — 60 of them grass
clumps at −31.5 m (thickness 0.8 m, past the decal gate), a 73,588 m²
"pit" 35 m deep under the old-terminal apron (100 % pavement overlap),
and a 27k m² T4S ring with a −3.63 witness. The mechanism is measured
(§7), so the reading was changed, not the constants:

1. **Depth is LOCAL** (`obj8.py`): every genuine solid component is
   judged against the DEM under it — plane
   `DEM(component) − DEM(anchor) − agl − admission_depth_m` in the
   authored frame; on flat ground (OTHH, DEM 3.96 everywhere) this is
   exactly the authored reading.
2. **A shell reaches grade** (`[basin] shell_reaches_grade`): a component
   whose rendered TOP lies more than `contact_band_m` under the ground is
   buried geometry, not a pit (v1's pit seed reads the same
   ground-contact band). This alone removed the 12 grass "pits" that
   survived reading 1 (they render 20–44 m underground).
3. **Openness** (founding spec §2.1 item 2, `max_covered_fraction`): the
   old-terminal level is 51 % covered by its own buildings → refused.

Result: LEMD 0 basins, OTHH the two Dewatering pits — the two facilities
v1 also cut at OTHH (its `TRENCH_SPINE` records, above-grade fraction
0.24–0.36 on v1's own reading).

## 2. Per-airport, end to end (single runs, production frame; the two closing builds ran concurrently)

| | control `136f03a2` OTHH | **OTHH M4b** | control LEMD | **LEMD M4b** |
|---|---|---|---|---|
| load / classify / planar | 6.1 / 2.4 / 2.1 s | 6.1 / 2.4 / **14.3 s** (object read 11.3, basins 0.9) | 4.7 / 2.2 / 2.0 s | 4.7 / 2.2 / **9.6 s** (object read 4.3) |
| constraints (basin rows) | 4.1 s | 4.0 s (172: 45 floor pins, wall flats/pins) | 3.9 s | 3.9 s (0) |
| solve (HiGHS OPTIMAL) | 5.4 s | 5.4 s | 7.3 s | 7.4 s |
| **total** | 28.4 s | **36.1 s** | 26.4 s | **32.6 s** |
| planar faces / T-vertices | 952 / 0 | **956** / 0 (+2 floors, +2 walls) | 971 / 0 | 971 / 0 |
| patch sha (attempt 1 == attempt 2) | | `2467399d…` | | `efbf6b7e…` |

Build-time impact statement: the OBJ8 read is the whole cost (OTHH +7.7 s
wall: 1.58 GB of OBJ8 text, 17 M vertices parsed in numpy; every
placement's plan extent is pre-screened against the DEM before any
component work, so components run for 44 + a few placements, not 1,366
resources). Both airports stay under the 60 s gate; a per-resource parse
cache for the pipeline stage cache is the lever if HECA's Taimodels pack
is heavier (`DEFERRED_VERIFICATION.md`).

## 3. Census by family — v1 oracle on v2's patch, before → after (same base `136f03a2`, same frame)

| family | OTHH control | **OTHH M4b** | LEMD control | **LEMD M4b** |
|---|---|---|---|---|
| plane_gradient | 1 (1 airside) | 1 (1) | 12 (11) | 12 (11) |
| strip_seam_tear | 1 | 1 | 1 | 1 |
| runway_crown | 0 | 0 | 2,185 | 2,185 (the crown lane's class; unchanged here — main has since merged its fix, `eaac452d`: main LEMD reads 14 / 13) |
| basin_floor_declaration | 0 | **0** (2 facilities declared) | 0 | 0 |
| every other family | 0 | 0 | 0 | 0 |
| **adjudicated / airside** | 2 / 2 | **2 / 2** | 2,198 / 2,197 | **2,198 / 2,197** |

**Airside rows added: 0 at both airports** — the basin faces (floor
`tunnel_trench`, wall `retaining_wall` with the 0.6 m gap) price nothing
in the oracle: `retaining_wall` has no cap (step readers skip it), the
floor is flat and shares no vertex with anything, the wall's outer edge
would share the cut pavement's vertices (none at OTHH: both pits lie on
bare ground). The v2 verify agrees row for row (`basin_floor_declaration`
0, `basin_floor_at_declaration` 0, `basin_wall_gap` 0, tunnel acceptance
keys unchanged from M4).

Tunnel acceptance (`tunnel_portal_acceptance.py`): OTHH 8/8 canonical,
`ramp_wall_gap` 0, `covered_span_clean` FAIL 1 (M4's pre-existing zone
row); LEMD 19 sites / 4 not canonical, `ramp_wall_gap` 0 — identical to
M4. The object-deck bands and the basin rows enter the same LP; residual
certificate 0.0000 m on every kind at both airports.

## 4. The LEMD basin invariant (floor 587.75, G 596.682) — quoted, not reproduced

The invariant belongs to the ORIGINAL objects and the 2026-08-27 DEV
surface: R_est along the T4S ring on today's production frame reads
**596.29** (v1's 596.30); the backup `LEMD36.obj.anchor_bak` witness is
**−7.03** (v1 −7.048); 596.29 − 7.03 − 1.5 = **587.76** — the historical
587.75 to the R_est rounding. G = 596.682 is superseded by the owner's
accepted 600.51 seat datum (memory `lemd-aerosoft-patch-ground-truth`;
`.o4_reanchor_provenance.json` `seat_datum_m`). On the pack AS IT IS ON
DISK v2 measures: witness −3.61 (rebaked +3.42), rendered floor 592.39 =
DEM(anchor) 596.0 − 3.61, and the production DEM at the pit centre is
**593.0** (the pack's own mesh pit rides in as the `LEMD Madrid - 2 -
Mesh` inset, smoothed) — 0.6 m of depth at the centre, under the 2.5 m
admission; the region's largest part is 98 m² (`small_regions` in the
report JSON). A pit emitted here would be cut to 590.9 from the rebaked
witness — 3 m shallower than v1's, because v1 lifted the objects. Which
state of the pack v2 should read is open question 1.

## 5. Refusals and residuals (attempt cap: 2 builds per airport — attempt 1 refused twice (GEOS side-location conflict in an above-grade clip at OTHH; a LEMD grass "basin" pinning a tunnel-wall vertex), attempt 2 identical products)

* **OTHH Drainage_01–06 not emitted** — v1's six BOWL facilities (floors
  keyed on −3.82 / −4.20 m solids). Under 08-26's region recipe the part
  of each bowl below the 2.5 m admission plane is 19–938 m² per member,
  the closed regions 54–544 m², all under `min_area_m2` 1,000 (v1 admitted
  them structure-level, through its bowl classifier, not through this
  recipe). Listed with their areas; open question 2.
* **LEMD old-terminal level refused at 51 % covered** vs the 50 % table
  value — the number is stated for ratification (§6, open question 3);
  the region is a building's lower level (8 objects, 9 m under R_est
  603.47, 1 % pavement overlap), and refusing it is the intended outcome.
* **Overlapping a tunnel** refuses the basin, never cuts the structure
  (kind `structure` cells are never cut; the wall band's outer edge is
  the test). No instance survived at either airport after the
  reaches-grade gate; the attempt-1 LEMD IIS was exactly this class.
* `anchor` absent from the v2 sidecar — the oracle's site coordinates
  print 0,0 (M4's note; `SIDECAR_KEYS` closed).
* Object bridges: no instance at OTHH/LEMD; twinned (§8). KCLT/EGLL-class
  packs (`ATTR_hard_deck` decks) are M5's first real arm.

## 6. Law tables and model extended (03e; additive)

`structures.toml [basin]` (schema `Basin` + 12 fields): `floor =
"deepest_solid"` (was `"declared"`), `seat_margin_m` 1.0,
`min_solid_thickness_m` 0.3, `admission_depth_m` 2.5, `contact_band_m`
1.0, `footprint_close_m` 2.0, `min_area_m2` 1000, `rim_sample_step_m` 10,
`floor_disagreement_m` 2.0 (all eight equal v1's constants — the law
twin asserts it), `rim = "ground"`, `shell_reaches_grade = true`,
`cuts_pads = true`, `cuts_runway_family = false`, and
**`max_covered_fraction = 0.5`** — v1's founding constant is 0.02
(`BOWL_MAX_ABOVE_GRADE_AREA_FRACTION`) but was never exercised on a real
record (LEMD/OTHH founded 0 in v1); OTHH's owner-accepted pits read
2.5 % / 19.4 % here (24–36 % on v1's own pooled records), the LEMD
basements 51 % and ~100 %. Recorded as a RULED deviation in the law twin
pending the owner (open question 3). `model/structures.py`: `Basin`
carries the ring, wall path, R_est, the deepest solid (rendered and
relative), coverage, area, anchor; `Deck.datum == "deck_top"` is the
object bridge; `PlanarMap.basins`; `DsfObject.resolved_path` / `kind`;
`DsfPlacement.kind`.

## 7. What the measurements named on the way (each deleted or ruled)

1. authored-plane admission → 75 LEMD regions (§1); 2. `np.unique(axis=0)`
   components over every resource → 211 s of OTHH planar (pre-screen by
   plan extent: 14.3 s); 3. an above-grade clip's invalid sliver refusing
   the whole union (GEOS side-location conflict) → repair at the
   contribution, snapped union fallback; 4. a grass "basin" welded to a
   tunnel wall (two senior pins on one vertex, the IIS named both) →
   structure cells are never cut, overlap refuses; 5. the per-line Python
   OBJ8 parse (19.8 s at OTHH) → numpy tables; 6. openness computed for
   all 12k placements → on demand, near candidate rings only; 7. the
   IIS twin's "low deck" was absorbed by the apron sharing the mouth cap
   under the ground rule — the twin now states a deck the apron cannot
   absorb, which is the class the IIS must name.

## 8. Twins and commits

`tests/auto_patch_v2/test_m4b.py` (9): OBJ8 parse (arrays, hardness
state, IDX10), welded components and the thickness gate (a −50 m decal
quad never witnesses), the heading transform (x east / z south), local
grade reading (a pit 60 × 40 on a sloped plane: area, rendered floor,
AGL folded into a deck top), the basin pass (one basin, the small one
under `min_area_m2`, floor = rendered deepest − margins = R_est + rel −
margins, floor / wall cells with the gap, the pad inside cut and the pad
beside untouched, the apron cut, the keep-out, 0 T-vertices), the
covered pit refused, rows → solve → emit → verify (floor pins on every
floor vertex, wall crest by station / ground, OPTIMAL, the sidecar
record's arithmetic, `basin_*` families 0, no `tunnel_trench` step or
cross-shape row), the readers firing (a lifted floor vertex; a
disagreeing declaration), the object bridge (the object law governs — no
terrain deck for the mapped bridge way over it — `deck_top` band rows,
the cut held at datum under it, OPTIMAL) and a deck too low for the
apron to absorb as an IIS naming the deck-top row. `test_law_tables`
cross-checks the eight v1 constants and records the ruled deviation.
The v2 suite: 98 pass. Commits on `lane/v2basins`: §9.

## 9. Open questions (≤ 3)

1. **Which pack state does v2 read?** The LEMD pack on disk is
   v1-rebaked (T4S +3.42 m, other clusters to −35 m). v2 reads the files
   as shipped (X-Plane's truth); the T4S pit then reads 0.6 m deep against
   a production DEM that already carries the pack's own mesh pit, and no
   basin is cut. Reading the `.anchor_bak` originals instead reproduces
   587.75 — but v2 has no bake, so the objects would render 3.4 m lower
   than v1 seats them. Owner: pack-on-disk (this lane), or a
   restore-before-read rule?
2. **OTHH Drainage_01–06**: emit v1's six bowls? They need a
   structure-level admission (a bowl whose below-plane part is under
   1,000 m² but whose shell is a closed pit) — a second recipe beside
   08-26's region recipe, or a smaller `min_area_m2` for closed bowls.
3. **`max_covered_fraction` 0.5** (v1 0.02, never exercised): ratify, or
   name the fraction from OTHH's accepted pits (≤ 0.36) and LEMD's
   refused basements (≥ 0.51)?

NOT done: the OTHH basin mesh apply (not required); CYXY / SPLP / SPJC
re-census (no below-grade geometry there by construction); `--runs 3`
timing; a per-resource parse cache; the five-airport sweep
(orchestrator); a KCLT/EGLL object-bridge arm (M5).
