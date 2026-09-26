# Beta 2 blockers — the beta 1 (build 1.0.350) feedback list

> **MIGRATED 2026-09-18:** every OPEN / DIAGNOSED row below is now a GitHub issue (#1–#20, milestone *Beta 2*, label `blocker`). Track status THERE; this file is kept as the owner-text record.


Source: owner test results on build 350, 2026-09-18. **Every row must be
`CLOSED` or `WAIVED` before any beta ≥ 2 tag.** The gate is mechanical:
`scripts/check_beta_blockers.sh` (called by `scripts/check_tag_version.sh`,
the first step of every release job) parses the table below and refuses a
`-beta.N` (N ≥ 2) tag while any row is in another state. Run it by hand
before tagging: `bash scripts/check_beta_blockers.sh`.

Status vocabulary (the gate reads column 2 literally):

- `OPEN` — reported, not attributed.
- `DIAGNOSED` — mechanism measured (findings file cited in Notes).
- `FIXED` — fix merged (sha in Notes); owner sim read still owed.
- `CLOSED` — owner confirmed in the sim / app (RULINGS key in Notes).
- `WAIVED` — owner ruled it out of beta 2 (RULINGS key in Notes). Only the
  owner waives.

Rules: never delete a row; new beta 1 reports append with the next ID;
a status change cites its evidence in Notes in the same commit. Owner text
is quoted verbatim in the detail section — the table is a summary.

| ID | Status | Airport | Summary | Notes |
|----|--------|---------|---------|-------|
| GEN-1 | FIXED | all | `[v2 rebake]` console messages with "Modify custom airports" UNCHECKED — nothing in the airport should be modified | `docs/findings/beta2-GEN-1.md`: flag off ⇒ rebake still MEASURES + prints, returns before the only pack writers (engine_v2.py:757-762) — logging + wasted work, no pack write. CHECK DONE 2026-09-18: all 23 owner tile cfgs carrying the key (incl. +25+051 OTHH, +30+031 HECA, +60-136 CYXY, -13-078 SPJC) say `modify_custom_airports=True`, and a tile cfg beats the global (O4_Config_Utils.py:232-243) ⇒ REAL GATING BUG: the unchecked box is overridden by the stale tile value, which each build re-writes. Whether 350 actually wrote the packs: unverified. MECHANISM (findings §7): `write_to_config` dumps ALL tile vars, freezing every setting per tile — class bug shared with color_harmonization. RULED RULINGS 2026-09-18a: option A sparse tile cfgs + UI change/reset writes through to the selected tiles (set if differs, REMOVE if equal to global) + early-return rebake. Lane `b2sparsecfg` branch `claude/b2sparsecfg` (f978cdf0 P1 early return, 8a40b115 P2 sparse `write_to_config` sharing `O4_Settings_Model.sparse_tile_values` with `write_tile` + consumer census, f29c2c98 P3 one-time migration on read — an UNMARKED legacy full dump carries NO overrides except provenance, see the commit for the owner flag, 2c9a3d11 P4 write-through: engine command `tile_settings_write` + Qt + Swift toggle). Tests only, no airport build; `swift build` green. SUPERSEDED 2026-09-18c (2) by lane `b2cfgstamp` branch `claude/b2cfgstamp` (be3332f2): P3's 80 %-dump heuristic is DELETED and Q 18b-1 is moot -- every tile cfg the engine or the app writes now carries a `cfg_written_by` stamp (`O4_Cfg_Vars.cfg_stamp_key`, not a setting: skipped by `_apply_config_file`, stripped from `read_tile_raw`, survives the retired-key cleanup), and an UNSTAMPED (pre-1.0.352) tile cfg is MOVED on first touch to `Ortho4XP_+XX+YYY.cfg.pre352.bak` (never overwriting an existing backup) at every census reader -- build read, `read_tile_raw`, `O4_Tile_Info` scan, `write_tile` -- after which the tile resolves wholly from the global. LOUD: a legacy cfg's `zone_list` and imagery provenance go to the backup too (owner said ANY config file). The harness stamps its canonical per-tile cfg source so a frame does not lose provider/ZL mid-build. OWED: Swift converge onto the engine command; `O4_Tile_Info` global fallback. |
| GEN-2 | OPEN | all | Harmonizer rework: exclude water from stats; casts from seam-edge strips, not whole-texture medians; interpolate shift across texture centres (no edge step) | Fable spec, then Opus lane. Memory: color-harmonization-mints-seams. Beta 1 known issue. 2026-09-25 closing arms (PR 56, frames harmonizerv2/hv2_arms_20260925): v2 ON vs OFF control on +25+051, 359 land seams judged — introduced step p50 0.05 / max harmonizer-attributable 1.68 (cross-ZL); site chain 27968_42128→42144 −0.06, 28000|28016_42144 −0.05 (v1: +26/+28, −28); max texture shift 4, 0 at the ±20 cap (v1: 50); drift +0.18 max; 1 seam over 2 counts in BOTH arms (2 land rows, OFF 6.16 / ON 5.12, DXT). §4 bar 3 (p90 DDS step ≤ 0.6× source) MISSED 5.41 vs 5.39 — a continuous field cannot move a seam step; needs a spec ruling |
| CYXY-1 | OPEN | CYXY | 60.7125349, -135.0753244 should be GROUNDSIDE with a service road from the apron (was before); now two road slivers, rest apron — regression | ATTRIBUTION ONLY, no interventional measurement (`docs/findings/beta2-CYXY-SPJC-regressions.md`): `dsf:pol123` is apron via §27's fixpoint cascade (`05ea3bbf`, `a1daa7d5`) through `pav9` / `dsf:pol20` / `pol17`, overriding ruling 04u which names these pages; slivers = §37 (2) sparing the roads |
| CYXY-2 | FIXED | CYXY | Groundside 60.7141907, -135.0766528 pulled nearly flat with the apron; DEM ~2 m higher | FIXED by owner RULINGS 2026-09-18c (1) option C, lane `b2frontagedatum` (`docs/findings/beta2-CYXY-2-3-optionC.md`): §28 (6)'s `pair_dem_step_m` now subtracts the pad's AIRSIDE-FRONTAGE median `dem_z` (§20's own contacts, the seat the pad is levelled to) instead of the arranged pad-RIM median `dba32406` trims; `frontage_step_max_m` re-centred 3.2 -> 2.4 on the measured population of THREE airports (CYXY 4 pairs / LEMD 1 / HECA 16; TERRACE +4.192, -4.006, +3.283 | ARMED +1.599 .. 0.007, a 1.68 m gap). CLOSING BUILD `CYXY_20260918T171219` rc 0, body_sha 74a61fd896b3, shared repo UNCHANGED: `pairs_held_as_terrace` 0 -> 2; the site reads 698.42 against DEM 698.35 (**+0.07 m**, was ~2 m below) and `pav4` stands +2.99 m above `building9`'s pad. Census law-true 1,378 adjudicated 373 (frame value, no base arm). Owner sim read owed |
| CYXY-3 | FIXED | CYXY | Same pattern at 60.7155636, -135.0792452 | Same fix as CYXY-2 (`b2frontagedatum`): `dsf:pol129 <- building10` step +0.915 -> +3.283 under the airside-frontage datum, held as a terrace at 2.4. On the closing build the face sits at median 700.19 against DEM median 700.47 (-0.28 m) and +2.70 m above `building10`'s pad; the probe point itself (that face's lowest corner) reads 698.73 vs DEM 699.99. Owner sim read owed |
| SPJC-1 | OPEN | SPJC | building13 (-12.0256285, -77.1076771) is one tiny end of a terminal, sunk; whole building needs one pad, leveled (was built before) — regression | ATTRIBUTION ONLY, no interventional measurement (`docs/findings/beta2-CYXY-SPJC-regressions.md`): code-reading only — every SPJC patch on the machine is one v1 body from 2026-07-25 (one 48,488 m² `building32`); suspect pad-is-the-cluster / leaves get no pad (`f71fca86`, `ad8b5120`); same family as SPJC-2. Needs a v2 SPJC build |
| SPJC-2 | OPEN | SPJC | Central new terminal (-12.0284806, -77.1162727): no pad; components seated at different levels, float | |
| SPJC-3 | OPEN | SPJC | Tunnel mouths gone at -12.0326702, -77.115129 and -12.0325443, -77.1148715 (were emitted) — regression | ATTRIBUTION ONLY, no interventional measurement (`docs/findings/beta2-CYXY-SPJC-regressions.md`): v1 patch has tunnel_ramp+tunnel_wall at both mouths; suspect §34 (12) (5) `terrain_tunnel_witness` (`eab1a904`) + Law C sibling refusal (both mouths die together). Needs a v2 SPJC build |
| HECA-1 | OPEN | HECA | Nested building shapes: two building20's, one inside the other; only the larger footprint matters | |
| HECA-2 | OPEN | HECA | building13 ends at 30.112611, 31.4058943; the part south/east at 30.1125298, 31.4064909 is not it and must be free to terrace | |
| HECA-3 | OPEN | HECA | Service road should extend to 30.1122535, 31.4062746; object wall on the road edge is a RETAINING wall — road level at wall top, ground beyond at wall bottom | |
| HECA-4 | OPEN | HECA | Terminal floating roof elements + roof-mounted light posts at 30.1110619, 31.4041921 | |
| HECA-5 | OPEN | HECA | Many buildings / larger terminals missing interiors or windows, or levels separated | §48 interiors (lane v2interiors checkpointed) |
| HECA-6 | OPEN | HECA | Cargo complex 30.1194398, 31.4077874 → 30.1161247, 31.4087786 must not be sunken; weld to the apron (30.1172704, 31.4094737) along the whole east edge | |
| OTHH-1 | OPEN | OTHH | No tunnel exists at 25.2575296, 51.6120308; extra tunnels emitted around the groundside in front of the terminal (25.2584256, 51.6142851) | |
| OTHH-2 | DIAGNOSED | OTHH | Build insanely slow, mainly "triangulating"; last message before the slowest step: `[v2 placement] OTHH: design surface 67 object pad(s), 84 structure rim(s), 866 graded face(s) for the §17 motion rule` | `docs/findings/beta2-OTHH-2-4-6.md` (counts from the 2026-08-14 patch — NO build-350 OTHH patch existed; re-count on a fresh one): tile mesh 448.61 / 272.08 s vs HECA 76.69 / 110.31 s; constraint density — 53,904 segments, median edge 5.35 m (HECA 11.73), junction+service_junction = 1,521 of 2,535 ways (HECA 70); retry ladder O4_Mesh_Utils.py:2891-2917. ALSO UNATTRIBUTED: auto_patch total 449.8 s (09-03) → 1,575.3 s (09-09), 'Assembling pavement & runway shoulders' 1.5 → 536.7 s |
| OTHH-3 | OPEN | OTHH | 25.2599127, 51.6149444 is NOT apron — groundside or terminal building (elevated road deck area) | |
| OTHH-4 | DIAGNOSED | OTHH | Clouds of detached nodes (e.g. 25.2546269, 51.6204583) everywhere, at slightly different elevations from surroundings; extraneous | `docs/findings/beta2-OTHH-2-4-6.md` (counts from the 2026-08-14 patch — NO build-350 OTHH patch existed; re-count on a fresh one): no detached nodes in the patch; 15,775 of 33,109 nodes (47.6%) carry NO `alt_abs` (~89% of service_junction vertices) and take raw DEM beside pinned neighbours. Same root as OTHH-2 (junction faces); 854 service_junction classifications (classify/roles.py:434-437) unattributed |
| OTHH-5 | OPEN | OTHH | Tunnel wall 25.2639569, 51.6126961 broken: should be a straight rectangle matching the pack's object wall, at TERRAIN height not below grade; ramp a simple sloping rectangle, not wiggling | |
| OTHH-6 | OPEN | OTHH | DESIGN QUESTION: on a truly flat airport the inset pre-flattens the whole airport — can almost all patch work be skipped, keeping only below-grade trenches/tunnels/ramps and adjacent-ground / gap-fill drainage slopes? Owner: "Am I missing something?" | Closes on a written answer the owner accepts (+ a plan if yes). Interacts with OTHH-2/-4. `docs/findings/beta2-OTHH-2-4-6.md` (counts from the 2026-08-14 patch — NO build-350 OTHH patch existed; re-count on a fresh one): draft answer PARTLY — premise inverted (the inset sharpens, O4_Cfg_Vars.py:305-313; OTHH is flat because Doha is); constrained edges, pads/rims, §17 roles, crown, retaining walls have no DEM substitute; the 1,521 junction faces ARE skippable. Owner has not read/accepted it |
| NLWF-1 | OPEN | NLWF | Runway broken and unusable | NLWF not a battery airport — needs a first build |
| NLWF-2 | OPEN | NLWF | Texture tearing at one runway end | |
| NLWF-3 | OPEN | NLWF | Tiny apron and buildings too elevated to be reachable from the runway | #20. Attributed (lane nlwf): the pack's apron is a HARD solid Y = 0 OBJ (`pavement/vele_apron.obj`, 1,499 m², no draped layer group) that §42 refused, so the ground under it followed the DEM 5.7 → 12.8 m. §42 (1b) hard-ground-plane admission landed DEFAULT OFF (branch claude/nlwf): ON arm apron 5.3–7.6 m, terminal pad 15.9 → 7.5 m, v2 gate ALL ZERO but census 9/0 PASS → 181/78 FAIL + 94 hairlines; owner Q-20 on #20. |

## Owner text, verbatim (2026-09-18, build 350)

> If "Modify custom airports" is NOT checked, why would I see any "[v2 rebake]..." messages in the console? We shouldn't be modifying anything in the airport...
>
> Rework the harmonizer (a Fable spec, then an Opus lane): exclude water from the statistics, measure casts from seam-edge strips instead of whole-texture medians, and interpolate the shift across texture centres so there is no step at an edge.
>
> **CYXY** good, but a few regressions
> 1. This apron (60.7125349, -135.0753244) should be groundside, and was previously, with a service road running up to it from the apron. Now there's two little service road slivers and everything else is apron (wrong)
> 2. What is pulling this groundside area (60.7141907, -135.0766528) down to nearly flat with the apron? It should be closer to 2m higher in the DEM I believe.
> 3. Same pattern here: 60.7155636, -135.0792452
>
> **SPJC**
> 1. building13 (-12.0256285, -77.1076771) is one tiny end of one of the terminals, and that end of the building is sunk into the ground. There should be a pad for the whole building, and we were building them before and leveling it so the whole building was visible.
> 2. Central new terminal (-12.0284806, -77.1162727) appears to have no pad, and the building is being seated at different levels so various components float
> 3. We were emitting tunnel mouths here: -12.0326702, -77.115129 and -12.0325443, -77.1148715, why are they gone?
>
> **HECA**
> 1. You can't have more than one building shape nested. There's two building20's, one inside the other. The larger footprint would be all that mattered.
> 2. building13 ends here: 30.112611, 31.4058943, the portion extending south and east here 30.1125298, 31.4064909 are not part of it, and should be free to terrace
> 3. service road should extend out to here: 30.1122535, 31.4062746, there's an object wall along the edge of the road that is a retaining wall: the road sits level at the top of the wall, and then the ground on the other side is at the level of the bottom of the wall.
> 4. Terminal has some floating roof elements and roof mounted light posts here: 30.1110619, 31.4041921
> 5. Many buildings, and larger terminals missing interiors or windows, or levels separated.
> 6. The complex of cargo buildings between 30.1194398, 31.4077874 and 30.1161247, 31.4087786 should not be sunken, and should generally weld to the apron (30.1172704, 31.4094737) all along their east edge
>
> **OTHH**
> 1. There's no tunnel here: 25.2575296, 51.6120308, and a number of additional tunnels are being emitted around the groundside area in front of the terminal: 25.2584256, 51.6142851
> 2. Something is still causing the build to take an insanely long time, primarily in the "triangulating" phase, with the last console message before the slowest step being "[+25+051]   [v2 placement] OTHH: design surface 67 object pad(s), 84 structure rim(s), 866 graded face(s) for the §17 motion rule"
> 3. 25.2599127, 51.6149444 is not apron, it's either groundside or part of the terminal building, this is the elevated road deck area.
> 4. Clouds of detached nodes like this: 25.2546269, 51.6204583 all over the place, at slightly different elevations from the surrounding area for no apparent reason. They seem extraneous.
> 5. This tunnel wall 25.2639569, 51.6126961 is completely broken, it's shape should be a simple straight rectangle matching the object wall from the scenery package, and it should be at terrain height not below grade. The ramp then is also a simple rectangle sloping down, not wiggling all over the place.
> 6. On a truly flat airport like OTHH, we are pre-setting the entire airport area to a flat elevation in the inset, so wouldn't that mean we could skip almost all the patch work entirely since all buildings and pavement would already be flat, the only shapes we would need are for below grade trenches, tunnels, ramps, and adjacent ground or gap fill to add slopes for drainage areas. Am I missing something?
>
> **NLWF**
> 1. Runway broken and unusable
> 2. Texture tearing at one runway end
> 3. Tiny apron and buildings are too elevated to be accessible from Runway

## Tooling defects found while working the list (not owner rows; fix before relying on them)

- `tools/v2_solve_replay.py --capture` cannot pickle at main `23556c2a`:
  `PicklingError: Can't pickle local object <function Frame.entry.<locals>.enter>`
  on `ProductionDem._enter`; every registered CYXY capture is `[MISSING]`.
  Found by lane b2cyxyhill 2026-09-18 (worked around in process). Blocks
  synthetic-first iteration for EVERY lane — repair first next session.
