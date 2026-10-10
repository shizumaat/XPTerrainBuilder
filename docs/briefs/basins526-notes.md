# basins526 — pit/basin objects: the gap (G), #526 (B1), #527 (B2), #528 (B3)

Lane branch `claude/basins526`, base main `f5f11c81f`. Reference: `/tmp/harness/othh513_OTHH.*`
(body eb7565539e36, plan sha 8e24e55b3f68), `docs/briefs/othh513-notes.md`.

## Step 0 — instruments

* `tools/obj8_split_report.py --units-with SUBSTR` (NEW parameter; `airport/placement_read.plan_units_with`):
  the plan trimmed to the units holding a matching resource BEFORE the plan stage — the two
  pit units of OTHH read in 2.3 s instead of the pack's ~600 s. Every plan-wide count is then
  partial and the tool says so.
* Base partial read (`Dewatering Drainage`, main code): `Drainage_06_000` b0 `skirted` on the
  trench floor (z −0.74, y0 −2.51), b1 basin:7; `Drainage_06_001` b0 basin:0, b1/b2 basin:7
  (3 bodies in the PARTIAL plan; the as-built 1.0.385 plan has a 4th, b3 basin:9 — the full-plan
  base is being read to settle whether the partial plan or the tree differs);
  `Dewatering_02_LOD0_002` b1..b10 `plate_only` / `footless_own_ground` at z −9.68.

## Step 1 — attribution and probes (othh513 frame `/tmp/harness/othh513_OTHH.v2`, main f5f11c81f)

* The `4 -> 3 bodies` of othh513's B1 intervention is a CROSS-TREE read: on one tree and
  one frame `Drainage_06_001` forms 3 bodies (b0 = comps [0,1,4] basin:0; b1 = [2], b2 = [3]
  basin:7) on main's code AND with the feet rule, full plan and partial plan alike; the 4th
  body (comp 4 alone on basin:9) exists only in the as-built 1.0.385 plan (engine 616e5d58a),
  and the same as-built plan + graded read through this tree gives 3. Not the rule's doing.
* B1 probe (`<scratch>/b1_probe.py`): `Drainage_06_000` comp 1 (4,858 m², base y −2.51):
  centroid in NO ring, all 4 feet in `basin_wall:0`; comp 3: centroid and feet basin:7.
  `Drainage_06_001` comps 0,1 basin:0; 2,3 basin:7; 4 basin:9 (feet and centroid agree).
  `Dewatering_02_LOD0_002` comps 52–61: base y +3.18, area 0, FEET 0, centroid inside basin:6.
* B3 mechanism: the 12 fittings are §14a (2) FLOOR MEMBERS (`basin_floor_members` 12 →
  `basin_floor_own_ground` 12): a floor member "takes no carrier" and seats on its own
  ground = the pit floor −9.68. With the feet guard the carrier search names the shell
  (basin b0) but issue #10's `contents_seat` reroutes to the unit datum (median ground under
  the shell's contacts = the floor, "carrier stands +13.64 m off its datum") — the basin
  exemption of §16a (2) (`_ok`) was missing there.
* G probe (`<scratch>/g_probe.py`, Basin records: `wall_path` = rim, `ring` = floor,
  `region` = the object's outline): on main every no-face pit's rim stands +0.72…0.85 m
  (median; max 1.1–1.4) OUTSIDE the outline, the floor ring ON it (0.00–0.20 m in): a slot
  0.65–0.76 m wide (slot m² / perimeter). OTHH has 45 basins: 8 drainage/dewatering pits,
  1 walled sump (basin:9, shell 0.78), 30 jetway rotunda wells (22–84 m² rims, shell 0.00)
  and 6 more. No other sweep airport has a basin (sw11_* / sw12_HECA: 0).
* First G arm (band inside for every no-face shell): the 8 pits' rims land on the outline
  (median +0.01…0.10, ±0.3 lattice snap), slot 0.01–0.12 m; but 20 jetway wells went
  BAND-IN with 0–3 m² floors of 32 m² plates (a well ~1.5 m wide cannot hold two bands) →
  the DEGENERATE RULE as a law key `[basin] bank_band_plate_min = 0.5` (the floor inside
  must keep that share of the witnessed plate; else the outward yield). A mean-bank-width
  witness was tried and refuted: the Dewatering bowls' shallow banks read as PLATE
  (|n_y| ≥ 0.7), so basin:6 measured 0.66 m of "bank" and fell back wrongly.
* B2: the quantum constants `TOL_DEG` / `POOL_QUANTA` move to `model/placement` (the writer
  `dsf_write` imports them back by name); `anchor_rule.rim_anchor_point` pushes the nearest
  rim vertex TOL_DEG along the outward bisector (one site; `basin_ring.arc_anchor` reads it).
* Other airports (base = `git archive f5f11c81f`, arm = this tree, full `obj8_split_report
  --json`): KCLT 573 bodies, HECA 3,039 bodies — 0 changed (class, anchor, components).

## Step 2 — what landed (branch `claude/basins526`)

| commit | fix | rule in one sentence | twin |
|---|---|---|---|
| e99636db3 | G (§47 (3) AMENDED) | a pit shell with no wall face (shell < `min_solid_thickness_m`) keeps its rim ON the object's outline and takes the `max(t, F)` band INSIDE it, under the banks; a well whose floor inside keeps under `[basin] bank_band_plate_min` (0.5) of its plate keeps the outward yield, named DEGENERATE | `test_basins526.py` (bowl with an outlet; 1.6 m well) |
| 9e075489e | B2 #527 | the basin rim anchor is the nearest rim vertex pushed `model.placement.TOL_DEG` (the writer's pinned round-trip tolerance) along the ring's outward bisector — one site `anchor_rule.rim_anchor_point`, read by `_basin_rim_anchor` and `basin_ring.arc_anchor` | `test_basins526.py` (B2), `test_v2objsplit` rim twin amended |
| 952171199 + 83f51b834 | B1 #526 | a component belongs to the ring its centroid is in; a component whose centroid is in no ring belongs to the ring more than half its feet stand in (plurality) — ONE function `anchor_rule.ring_of_part` at the three sites; feet-first REFUTED on the closing build (feet on the rim ring of a sump whose plate reaches the outline) | `test_basins526.py` (B1) |
| 952171199 + e137608f3 | B3 #528 | §14a (2)'s floor-member test is asked only of a group with feet; a piece carried by a BASIN body keeps that carrier in `contents_seat` (the basin's zero is the rim, its unit datum the floor — the §16a (2) exemption, counted `contents_seat_kept_basin_rider`) | `test_basins526.py` (B3) |

Per-pit, othh513 frame → closing build frame (`obj8_split_report --units-with "Dewatering Drainage" --dsf-dump`):

| body | before | after |
|---|---|---|
| `Drainage_06_000` b0 (the L trench shell) | `skirted`, low-side foot z −0.74, y0 −2.51 → rim 2.68 m under grade | `basin` on `basin_wall:0@1052`, z 3.96, y0 0 → rim at grade |
| `Drainage_06_000` b1, `Drainage_06_001` b0/b1/b2 | basin rim VERTICES (3.733 / 3.810 as written) | rim vertex + TOL_DEG outward, surface 3.96 |
| `Dewatering_02_LOD0_002` b1..b10, `_001` b1/b2 (the fittings) | 12 bodies `footless_own_ground` z −9.68 (13.64 m low) | 2 bodies carried by the shell, z 3.96 y0 0, authored +3.18 kept |
| 22 authored rows (13 pit, 9 wall) | kept as authored | kept as authored (22) |

Closing build `basins526_OTHH`: rc 0, patch clock 532.1 s (bar 660), wall 727.9 s, body 87f9d2f94d71
(main eb7565539e36), rebake plan 4eaa5364f8a0 (15 authored seats identical; only the `plate_stations`
of the two plain-row pit members differ — they follow the moved rims). Movers vs othh513 by 11-dp
identity: runway/taxi 0; apron 2 nodes (4.31 m, ON the pit rings: the floor→rim role swap of G);
structure_rim 27 (the basin rings themselves, max 13.64); groundside_pavement 133 ≤ 0.05 m;
service_road 3 ≤ 0.02 m. The per-pit ring table is in design spec §47 (3) AMENDED.
Frame registered (`frames.py list OTHH`, lane basins526).

Suites: non-Qt `-n auto` 9,230 passed / 1 failed → `test_v2basinedge` rim twin amended for §47 (3)
(9 passed); Qt `-n0` 311 passed; the four named files 204 passed; `tools/ratchets.py` duplicate +
layer PASS; size WARN anchor_rule.py 1024 → 1111 (+87, this lane).
