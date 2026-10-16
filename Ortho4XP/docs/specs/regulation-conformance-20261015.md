# Regulation conformance — spec and consumer census (RULINGS 2026-10-15k/l, #776)

Lane `regconf`, 2026-10-15. Spec only: no engine code (RULINGS 2026-08-30l).
Source audit: `docs/findings/law-table-audit-20261015.md` (rows 1–13, §4).
Standards read: FAA AC 150/5300-13B Chg 1 with errata (`regs/`, text
extraction in the session scratchpad); ICAO Annex 14 Vol I 8th ed. as cited by
the audit, cross-read against EASA CS-ADR-DSN Issue 7 (`regs/`); TP 312 not
available (as in the audit).

**Base.** main `78b88ca71` + PR #763 (`claude/rwyzone15c-p2` `c184723a6`,
phase 5 included) + PR #768 (`claude/trendcap` `6dda1a8ed`). PR #766
(`claude/tri752`) touches `solve/rows.py` and `geom/triangulate.py`, and only
`solve/rows.py` overlaps this spec (A-9 below). Line numbers are from that
merged tree, which is a scratch merge (`#768` conflicts with `#763` only in
`docs/frames.jsonl`).

**What #763 already does (not re-specced here).** It measures the runway zone
from the centreline (`tables.runway_zone_edge_offset_m`). It sets the RSA
length from the end (`rsa_length_m`, `runway_safety_area_length_m`) and stops
the end area at the top of a drop (`model/end_area`). It adds
`Runway.instrument`, true when the CIFP has an approach to either end
(`airport/cifp.read_cifp_approach_runways`). It reads the strip end length and
the RESA by code and instrument status (`end_length_instrument_m`,
`corridor_length_instrument_m`; this covers audit row 6 and row 12's strip-end
half). It reads the take-off climb surface by code (`[icao.eat]` by_code). Its
interim `band_max_down_faa = 0.05` (15c (4)) is replaced here by 15l (2).

**Owner direction (2026-10-15, relayed).** Most of this round is table work:
change a value, or key it by code, letter or instrument status. Only two rows
need geometry or consumer work: the taxiway strip re-base (row 3) and the FAA
approach-surface rise (row 5). Most of the cost is in verifying the airports
(§6). The owner re-reads every approved airport once, after #763, #768, #766
and this round have all landed.

---

## 1. The audit rows and the missing laws

Key types: **code** is the ICAO code number, from the runway's physical length
(§3.2). **rwy-letter** is the runway width letter (§3.1); under FAA it is the
proxy for the AAC/ADG. **twy-letter** is the 1202 width class of the
taxiway's chain (§3.3). **inst** is the runway instrument flag from #763.
**app-class** is the approach class of each END, from CIFP (§3.4, new):
`visual` / `npa` / `apv` / `pa`.

| # | Law | Standard (section) | Target key(s) and keying | Witness | Kind |
|---|---|---|---|---|---|
| 1 | ICAO runway band max fall | Annex 14 §3.4.15: 2.5 % at code 3/4, 3 % at code 1/2 | `zones.toml [adjacent_ground.runway] band_max_down` by_code {1: 0.03, 2: 0.03, 3: 0.025, 4: 0.025} | code | value |
| 2 | Airside grade-change rate (taxiway rings) | Annex 14 §3.9.9 (audit citation): 1 % per 30 m (C–F), 1 % per 25 m (A/B). FAA §4.14.1 (3)(b): 100 ft (30.5 m) of curve per 1 % change, maximum change 3 % | new `[icao.taxi] curve_rate` by_letter {A, B: {0.01, 25}; C–F: {0.01, 30}}; `[faa.taxi] curve_rate` {0.01, 30.5} at every letter. `no_step_rate` reads the FACE's family: the taxi family uses `taxi.curve_rate` by the face letter; runway and apron rings keep `strip.arc_rate` (the apron rate is engine-invented, audit §3) | twy-letter (face `code_letter`, `roles._junction_letter` at junctions) | value + re-key |
| 3 | Taxiway graded strip / TSA width | Annex 14 §3.11.4: graded portion from the CENTRELINE, A 10.25 … F 22 m. FAA §4.5.3: TSA width = ADG wingspan, half 7.5/12.0/18.0/26.0/32.6/39.9 m | `[adjacent_ground.taxi] half_width_m` re-read as a centreline figure; new `half_width_faa_m` by_letter {A 7.5, B 12.0, C 18.0, D 26.0, E 32.6, F 39.9}. Edge offset = max(lip, half − `<ruleset>.taxi.width_m`(letter)/2), in ONE accessor (§2.A) | twy-letter | **geometry** (census §2.A) |
| 4 | FAA runway band max fall | AC Table 3-6 S-3: 1.5–3.0 % at AAC C–E, 1.5–5 % at A/B (15l (2)) | delete #763's `band_max_down_faa`; `zone_bounds` under FAA reads `[faa.resa] transverse_near_max` by_letter (A/B 0.05, C–F 0.03). That table is already Table 3-6 S-3, so this is one key, not a copy | rwy-letter as the AAC proxy | value |
| 5 | FAA rise beyond the runway end | AC §3.16.5 (3): no part of the RSA may penetrate an applicable approach surface or clearway plane. Tables 3-2 to 3-4: visual 20:1 from the threshold; NPA 20:1 (≥ ¾ sm) or 34:1 (< ¾ sm) from 61 m beyond the threshold; APV/PA also Surface 6, 30:1 from the threshold | new `[faa.end_skirt] approach_surface` by app-class: {visual: {slope 0.05, from_threshold_m 0}, npa: {0.05, 61}, apv: {0.05, 61, also 1/30 from 0}, pa: {1/34, 61, also 1/30 from 0}}. `EndProfile.rise_m` = the lowest applicable surface, measured from the THRESHOLD (displaced length included) against the CIFP threshold elevation. `[faa.eat]` 40:1 stays for the EAT (§4.12 std 3) — owner Q1 asks whether it also stays in the end profile | app-class per end, `RunwayEnd.displaced_m`, `threshold_elev_m` | **row shape** (census §2.C) |
| 6 | ICAO RESA | §3.5.3: ≥ 90 m (240 m recommended) at code 3/4 and code 1/2 instrument; 30 m recommended at code 1/2 non-instrument | DONE by #763 phase 5 (`corridor_length_m` 30/30/90/240, instrument 90/90/90/240) | code, inst | — |
| 7 | FAA RSA by ADG and visibility | App. G: A/B-III and lower-visibility A/B-I/II are 300 × 600 ft | `rsa_length_m` and `half_width_faa_m` gain a `_lowvis` variant for letters A/B (91.4 m half × 182.9 m). It is read when the end's app-class is `pa`. A/B-III cannot be reached through the width proxy, because 100 ft reads AAC C (§3.1), and that is stated, not invented | rwy-letter, app-class | value |
| 8 | RAOA | §3.8.1: precision approach runways only | `constraints/strips.raoa` and both readers build the rectangle only before an end whose app-class is `pa` | app-class per end | **region trim** (census §2.B) |
| 9 | Zone-1 lip | FAA runway: Fig. 3-33 note 2, 3–5 % over 10 ft (= today). FAA taxiway: §4.14.2 (4), 5 ± 0.5 % over 10 ft. ICAO §3.4.15: negative, up to 5 % (the 3 % minimum is engine-invented, audit §3) | new `[adjacent_ground.taxi] lip_min_down_faa = 0.045`, `lip_max_down_faa = 0.055`, read by `zone_bounds` for the taxi family under FAA | authority + family | value |
| 10 | Apron at stands | ICAO §3.13.5: ≤ 1 % at a stand. FAA §5.9.2: 1 % at parking positions, 1.5 % on apron taxilanes (15l (3) supersedes 06w) | `[common.roles] apron_stand = {max = {0.010, 0.010}}`. An apron face that contains a 1300 startup of kind `gate` or `tie_down` takes the stand cap HARD on its rows (the same heads as `apron_hard_rulings` / `common.roles.apron …`). Every other apron face keeps 1.5 % hard and 1 % preferred | `Airport.startups` inside the face ring (point-in-polygon, one predicate published in the sidecar as `stand_faces`) | value keyed by a witness |
| 11 | FAA runway shoulder transverse | AC Table 3-6 S-2: 1.5–5.0 % (15l (3) supersedes 13dd) | `[faa.runway] shoulder_transverse_max = 0.05`; new `shoulder_transverse_min = 0.015` (mandatory fall). ICAO keeps 2.5 % | authority | value |
| 12 | Code-1 instrument strip | §3.4.2 end 60 m (DONE #763); §3.4.8 graded half-width 40 m | `[adjacent_ground.runway] half_width_instrument_m` by_code {1: 40, 2: 40, 3: 75, 4: 75}, read through #763's `_by_status` | code, inst | value |
| 13 | Code-3 end zone | §3.1.14: 0.8 % in the end quarters at code 3, Cat II/III only | `end_zone_precision_only_codes = [3]` binds when an end's app-class is `pa` (Cat unknown, so the strict reading; owner Q2) | app-class | value |
| M1 | ICAO mean runway slope (missing) | §3.1.13: (max − min)/L ≤ 1 % at code 3/4, 2 % at code 1/2. `rulesets.toml:88` carries §3.1.14's values but cites §3.1.13 | new `[icao.runway] mean_slope_max` by_code; one generator row family `runway_mean_slope` over each runway's centreline vertices (§4). Its census twin family has the same name | code | **grading law, in scope** |
| M2 | FAA C–E no grade change in the end zones (missing) | AC §3.16.1 C/D/E std 2: no grade change within the lesser of the end quarter and 762 m | new `[faa.runway] end_zone_no_change` by_letter {C–F: true}: the existing `runway_vertical_curve` rows inside `runway_end_zone_length_m` get an allowed change of 0 | rwy-letter (AAC) | **grading law, in scope** |
| M3 | Minimum distance between grade changes (missing) | ICAO §3.1.19: D ≥ K(\|x−y\|+\|y−z\|), K = 30,000/15,000/5,000 m. FAA §3.16.1: 1,000 ft (C–E) or 250 ft (A/B) × Σ\|Δg\|; FAA taxiway §4.14.1 (3)(c): 100 ft × Σ | **no generator** (owner Q3). A vertex surface has no PVI. The existing curve rows (`vertical_curve_k_m`) already bound Σ\|Δg\| over any window W by W/K (the same K), which is the standard to within a factor of two (curves may abut) | — | grading law, NOT emittable exactly |
| M4 | ICAO ungraded strip beyond the graded portion (§3.4.16/17), taxiway strip beyond graded (§3.11.6) | "should not exceed an upward 5 %" — a cap on RAW terrain beyond zone 2 | **out of scope**: zone 3 IS the DEM (08-01; 15g (B) "straight to DEM"). `ungraded_max_up` stays unread by the engine. The census zone-3 reading (`grade_law.adjacent_ground_envelope` `up_slope`) is unchanged | — | not a grading law here (master to rule) |
| M5 | FAA ROFA (Table 3-7 S-4/S-5/D-1) | OFA side slope ≤ 0 %, back slope 8:1–16:1 | **out of scope**: object-free area beyond the RSA = zone 3 = DEM. The census already has a ROFA back-slope zone-3 override (`grade_law.rofa_back_slope_ceiling`), unchanged | — | not a grading law here |
| M6 | FAA taxiway max grade change 3 % | §4.14.1 (3)(a) | no row: implied by the 1.5 % longitudinal cap (a change cannot exceed 3 %) | — | implied |

The FAA ≤ 30,000 lb taxiway case (2 %) and the clearway plane have no witness
and are not built (audit §4). The edge drop of 1.5 in is a pavement detail,
not a grading law.

**Twin values.** The census prices against v1 `auto_patch/config.py`
`Ruleset`s (`grade_law`). `tests/auto_patch_v2/test_law_tables.py` holds the
TOML against config. Every value row above changes in BOTH places, in the same
commit, or the census should import the v2 accessor instead. Where §2 names
an accessor, the census imports it, as `check_grade` already does with
`_V2_STRIP_T` at `check_grade.py:8400`.

---

## 2. Consumer census (one table, three regions plus the band values)

Rule: trim at the single derivation site. A consumer changes only when it reads
the changed QUANTITY itself; a consumer that reads the region inherits.

### 2.A Taxiway graded strip, re-based on the centreline (row 3)

One accessor, extended rather than forked. #763's
`tables.runway_zone_edge_offset_m(law, cn, cl, runway_half_m)` becomes the
runway branch of `tables.zone_edge_offset_m(law, role, cn, cl,
pavement_half_m=None)`. For the taxi family it returns `max(lip, half(ruleset,
letter) − taxi.width_m(letter)/2)`. `zone2_half_width_m` keeps its meaning (the
CENTRELINE table value).

Static result (edge offset in m, today → new). ICAO: A 10.25 → 6.5, B 11 →
5.75, C 12.5 → 5.0, D 18.5 → 9.5, E 19 → 7.5, F 22 → 9.5. FAA (TSA): A → 3.75,
B → 6.75, C → 10.5, D → 14.5, E 19 → 21.1, F 22 → 24.9. ICAO bands narrow
everywhere; FAA bands narrow at A–C and widen at D–F (KATL E, KCLT F, KDEN
E/F).

| C | Pass | file:line | Reads | Ruling |
|---|---|---|---|---|
| A-1 | planar | `planar/zones.py:362-366` | `zone2_half_width_m(law,"junction",…)` buffered from the taxi union | **THE DERIVATION SITE**: buffer by `zone_edge_offset_m` |
| A-2 | planar | `planar/zones.py:329-332` `rank` | hw orders the groups (wider first) | read the offset (ordering only) |
| A-3 | planar | `planar/overlay.py`, `planar/strip_keepout.py`, `planar/terrain_edge` clip | the zone REGIONS | inherit (strip_keepout is runway only) |
| A-4 | planar | `planar/structure_underpass.py:83` | taxi hw as the strip a structure declares | → offset |
| A-5 | classify | `classify/ribbon_mint.py:65` | taxi cell buffered by hw — "the regions `zone_regions` draws" | → offset (its docstring requires equality with A-1) |
| A-6 | load | `airport/road_ramp.py:938,943` | taxi hw as a road contact's reach, default letter | → offset |
| A-7 | constraints | `constraints/zones.py:291-296` `half_of` | taxi edge corridor reach (fed to `zone_bounds(…, half_m)` at :574/:579) | → offset; pass `half_m` for taxi too |
| A-8 | constraints | `constraints/zones.py:618,699` | `strip_transverse_bound` (runway family) | unaffected |
| A-9 | solve | `solve/rows.py:283` | zone width per pavement vertex (whether a sheet is anchored) | → offset; #766 edits this file elsewhere — land after #766 |
| A-10 | solve | `solve/project.py` zone projection (12ag) | rows from A-7 | inherit |
| A-11 | emit | `emit/osm_adapter.py` (zone tags `adjacent_ground:taxi:<L>:zone<k>`) | region and letter | inherit |
| A-12 | verify | `verify/keepout.py:132-138` | taxi hw as the strip of a ramp-in-strip | → offset |
| A-13 | census | `tools/check_grade.py:8403-8412` `_strip_half_width_m` | v2 `zone2_half_width_m` | → v2 `zone_edge_offset_m` |
| A-14 | census | `tools/harness/law_support/grade_law.py:740-750` taxi envelope | config `taxiway_strip_graded_half_width_m` (ICAO table under both rulesets) | → v2 `zone_edge_offset_m`; drops the FAA-gets-ICAO defect |
| A-15 | census | `adjacent_ground_step` / `_tear`, `strip_seam_tear` | zone faces by tag | inherit |
| A-16 | harness | `tools/v2_solve_replay.py:1200` | runway only | unaffected |
| A-17 | twin | `tests/auto_patch_v2/test_law_tables.py` | config vs toml | update |

Probe: no seam probe was needed. Every reader goes through one of two
accessors, and reading them statically settles it.

### 2.B RAOA restricted to precision ends (row 8)

The RAOA has no planar region: the rectangle exists only inside its row
generator and its two readers. The trim is the END FILTER, at one predicate
`law.tables.raoa_applies(end)` = app-class `pa`, read from `RunwayEnd` in the
engine and from the sidecar in the census.

| C | Pass | file:line | Reads | Ruling |
|---|---|---|---|---|
| B-1 | constraints | `constraints/strips.py:822-850` `raoa` | both ends of every `runway_groups` group | filter ends by `raoa_applies` |
| B-2 | verify | `verify/strips.py:702-725` `raoa` | both ends, from `groups(p)` | same filter, from the sidecar `runway_ends` (B-5) |
| B-3 | census | `tools/check_grade.py:4555-4592` `_check_raoa_rate` | both ends, unconditional — it never calls `raoa_applies` | call `grade_law.raoa_applies` with the sidecar class |
| B-4 | census | `grade_law.py:2203-2217` `raoa_applies` | v1 `config.runway_end_approach_class` (apt.dat markings and lights) | witness → the CIFP app-class (15k (3)); the v1 classifier is no longer read here |
| B-5 | publication | `pipeline/publication.py` | — | NEW key `runway_ends: [{ref, end, approach_class, displaced_m, threshold_elev_m}]` (also feeds 2.C) |
| B-6 | planar, solve, emit | — | nothing reads the RAOA rectangle | unaffected |

### 2.C FAA end rise on the approach surface (row 5)

Single derivation: `tables.runway_end_profile(law, cn, cl, instrument,
approach_class=None, displaced_m=0.0)`. Under FAA, `rise_m(d)` = min over the
applicable surfaces of `(d + displaced_m − from_threshold_m)·slope`, plus a
datum term `z_thr − z_end` (the CIFP threshold elevation where pinned, the end
foot otherwise). The 61 m hold (§3.16.5 (2)) is unchanged. ICAO is unchanged:
its approach surface (Table 4-1) never lies below the take-off climb surface
over the RESA.

| C | Pass | file:line | Reads | Ruling |
|---|---|---|---|---|
| C-1 | law | `law/tables.py:623-650` `runway_end_profile` | `[faa.eat]` slope/setback | **THE DERIVATION SITE**: approach surface by class |
| C-2 | constraints | `constraints/strips.py:523` (end rows), `:385` (pairs/transects), `:723` (rate rows z_v − z_foot) | `prof.rise_m(d)` | pass the end's class and displacement; the row's datum is a constant (CIFP) — still a `Band`/`Linear` |
| C-3 | constraints | `constraints/strips.py:766` `runway_end_profile(law)` (rate only) | `prof.rate` | unaffected |
| C-4 | constraints | `constraints/eat.py` | `[faa.eat]` directly | unaffected (the EAT keeps 40:1, §4.12 std 3) |
| C-5 | planar | `planar/zones.py:181` `runway_end_breaks` | `break_m` (fall side) | unaffected |
| C-6 | model | `model/end_area.py:48` drop test | `fall_m` | unaffected |
| C-7 | verify | `verify/strips.py:580` | `rise_m` | pass the class from the sidecar `runway_ends` (B-5) |
| C-8 | census | `tools/check_grade.py:2997, 4045` `_runway_end_profile_law` | the v2 profile | same |
| C-9 | tool | `tools/runway_end_ground.py:307-339` | `rise_m` | same (diagnostic) |

### 2.D Band-fall values (rows 1, 4) — values only, no region change

`tables.zone_bounds` (`law/tables.py:483-505`) is the ONE derivation. Its
readers inherit: `constraints/zones.py:574,579,618,699`,
`verify/strips.py:182,188`, `solve/project.py` (12ag), and
`tools/harness/runway_edge_tie.py`. The one census twin that does NOT inherit
is `grade_law.ruleset_strip_band_max_down_slope(code_number, rs)`
(`grade_law.py:731` via config). It keys by code only, so under FAA it must
take the letter. Change it to read the v2 accessor.

---

## 3. Witnesses

**3.1 The runway letter (AAC/ADG proxy).** There are two classifiers today,
and they disagree.

| Classifier | Location | Rule |
|---|---|---|
| engine | `airport/load.py:51-53,233-237` | `width ≤ lim`: 18 A, 23 B, 30 C, 45 D, 60 E, else F |
| census | `auto_patch/config.py:3308-3333` (via `check_grade.py:241`, `grade_law`) | `≥`: 15 B, 21 C, 28 D, 42 E, 55 F |

Measured on the registered captures, the engine and the census disagree at
CYXY 02/20 (B / C), NLWF 07/25 (C / D), SPJC both runways (D / E), OTHH both
(E / F), and KBJC 12R/30L and 03/21 (B / C). At KBJC that means the census
judges a 75 ft runway at 1.5 % while the engine builds it at 2 %.

The audit's shift is real. AC App. G gives runway widths by RDC: A/B-I 60 ft,
A/B-II 75 ft, A/B-III and C/D-I…III 100 ft, C/D-IV and D-V 150 ft, VI 200 ft.
The engine's exclusive bounds sit at the ICAO metric minimums, so 60 ft (18.29
m) reads B where AAC A/B-I is right. 100 ft (30.48 m) reads D where C is right;
this has no AAC effect, since both are C–E. 150 ft → E is the documented
conservative ADG-V tail (`config.py:3316-3320`) and stays.

Against Annex 14 Table 3-1, letter F needs 60 m, so OTHH's 60 m runways read E
where F is right. RIGHT: ONE classifier, `law/tables.runway_code_letter(law,
width_m)`, read from a TOML table with a 0.5 m unit tolerance: A ≤ 18.8, B ≤
23.4, C ≤ 31.0, D ≤ 45.0, E ≤ 46.3, F above. `load.py` stamps
`Runway.code_letter` once. The sidecar `runway_caps` already carries
`code_letter`; the census reads it from there, and both config functions and
`load.runway_code_letter` are deleted.

Engine movers: CYXY 14L/32R D→C, KBJC 12L/30R D→C, OTHH E→F. C and D are
identical in every by_letter table except the EAT tail height, which only
reaches code ≥ 3 runways with a recognised EAT (≥ 457.2 m, 15e). OTHH F raises
the tail from 20.1 to 24.4 m wherever OTHH has a recognised EAT; the lane
reports any.

**3.2 Code number: physical length versus field length.** The code number is
by aeroplane reference field length (Annex 14 Table 1-1), which belongs to the
aircraft and has no witness. The engine uses runway length, which is right as
a proxy. A runway is at least as long as its critical aircraft's field length,
so the proxy reads the same class or one higher; at high or hot fields it
reads higher. The duplicate classifiers are `airport/load.py:47,226-230`
(apt.dat end-to-end length) and `constraints/strips.py:105-116` (the SLAB
length, overruns included: `strips.py:152`). A fourth sits in config
(`config.py:3714`, census). ONE site: `load.py` stamps `Runway.code_number`;
`strips.runway_groups` reads `rw.code_number`; the census reads `runway_caps`.

Measured on captures: the slab code equals the load code at every sweep
airport, so there are no movers. A runway near 800, 1200 or 1800 m with blast
pads would differ.

**3.3 Taxiway letter.** The witness exists: the apt.dat 1202 `width_class` is
threaded per chain (`classify/evidence.py:280` → `Breakline.code_letter` →
the cell `code_letter`, `roles._junction_letter` at junctions). Captures:
CYXY {D 42, A 22, B 19, C 3, E 1}, HECA {E 297, F 5, C 2}, OTHH {F 433, E 17,
C 3}, KATL {E 2150}, KCLT {F 364, E 11}, KDEN {E 535, F 226, …}, KBJC {C 62,
E 56, A 39, B 36}, KASE {C 171, A 18, B 3}, SPJC {F 96, E 89, C 45, D 22, B 7},
NLWF {B 3}. Rows 2, 3 and 9 key by it; no new witness is needed.

**3.4 Approach class per end (new, extends #763).** #763's
`read_cifp_approach_runways` returns designators. Extend it, without forking,
to return `{designator: class}` from the APPCH procedure ident's first letter
(ARINC 424 route type):
- `pa`: I (ILS), J (GLS), M/W/Y (MLS). These are Annex 14 precision approaches
  and FAA Table 3-4.
- `apv`: R and H (RNAV/RNP). They may carry LPV or LNAV/VNAV, which is FAA
  Table 3-4; for Annex 14 they are non-precision.
- `npa`: every other ident.
- `visual`: no procedure.

The strongest class per end wins. `Runway.instrument` stays as "any end ≠
visual". Visibility minimums have no witness. Owner Q2 proposes `pa` → < ¾ sm
(34:1), `npa` and `apv` → ≥ ¾ sm (20:1).

CIFP at the sweep airports (X-Plane 12 `Custom Data/CIFP`, read only):
- CYXY: `pa` 32L; `apv` 14L 14R 32R; 02/20 visual.
- NLWF: `npa` 25, `apv` 07.
- SPJC: `pa` 16L 16R; `npa` 34R; 34L visual.
- HECA: `pa` 05C 05R 23C 23L; `npa`/`apv` 05L 23R.
- OTHH: `pa` all four ends.
- KASE: `npa` 15; `apv` 33.
- KBJC: `pa` 30R; `npa`/`apv` 30L 12L.
- KDEN and KATL: `pa` at every end.
- **KCLT: the CIFP idents (01L/01R/19L/19R/18L/36R) do not match its apt.dat
  runways (18L/36R, 18C/36C, 18R/36L) one for one.** The lane must log the
  join. An unmatched end reads `visual`, which also affects #763's
  `instrument` flag.

---

## 4. Emittability (heightfield mesh)

Every changed law is a bound on vertex heights or on linear combinations of
them, so all are emittable except M3:

| Law | Form | Notes |
|---|---|---|
| Rows 1, 4, 9, 11, 12 | `zone_bounds` / transverse bands | Rows 1 and 4 narrow the band window to 1.5–2.5 % or 1.5–3 %; row 9 narrows FAA taxi lips to 4.5–5.5 %; row 11's minimum makes the shoulder a mandatory fall |
| Row 2 | the same three-term rows at a different rate | |
| Row 3 | the same rows over a different buffer | |
| Row 5 | a Band per end-area vertex against a constant (CIFP datum) | or a Linear against the end foot |
| Row 8 | fewer rows | |
| Row 10 | the existing hard apron rows at a lower cap on the faces that hold a stand | |
| M1 | all-pairs rows `z_i − z_j ≤ m·L` over a runway's centreline vertices (n ≤ ~300; ≤ 45k Diff rows at HECA's longest), or two auxiliary columns `zmax`/`zmin` if the solver admits them | lane's choice, stated in its report |
| M2 | the curve rows at 0 change | |

**NOT emittable exactly: M3** (distance between PVIs). A vertex profile has no
PVI, and the windowed form (Σ|Δg| over W ≤ W/K) is already implied by the
curve rows. Recommendation: no generator (owner Q3).

Feasibility risks: rows 2 and 10 tighten HARD or senior rows on pavement (§6
probe), and M2 forces the FAA C–E end zones straight against the CIFP pins.
That is the same yield class as §50.1 (3): where pins in an end zone demand a
bend, the end zone yields with the pins and the yield is reported, never
silently relaxed.

---

## 5. Lane plan (3 lanes) and landing order

| Lane | Rows | Files (own) |
|---|---|---|
| **L1 `regwit` — witnesses** (small; first) | §3.1, §3.2, §3.4; row 8 (RAOA filter); row 13; row 7; publication `runway_ends` | `airport/cifp.py`, `airport/load.py`, `model/airport.py`, `law/tables.py` (classifier + `raoa_applies` only), `rulesets.toml` letter table, `constraints/strips.py` (`raoa`, `runway_code_number` deletion), `verify/strips.py` (`raoa`), `pipeline/publication.py`, `check_grade.py` (`_check_raoa_rate`, the classifier imports), `grade_law.raoa_applies`, `config.py` (classifier deletion) |
| **L2 `regval` — values** (after L1) | rows 1, 2, 4, 5, 9, 10, 11, 12; M1, M2 | `law/zones.toml`, `law/rulesets.toml` (value keys), `law/model.py`, `law/tables.py` (`zone_bounds`, `runway_end_profile`), `constraints/no_step.py`, `verify/no_step.py`, `constraints/apron.py`, `constraints/strips.py` end rows, new `constraints/runway_mean_slope.py`, `verify/` twin, `config.py` value twins, `grade_law` value readers, `test_law_tables.py` |
| **L3 `regtsa` — taxiway strip re-base** (parallel with L2; lands after it) | row 3 | `planar/zones.py`, `planar/structure_underpass.py`, `classify/ribbon_mint.py`, `airport/road_ramp.py`, `constraints/zones.py`, `solve/rows.py`, `verify/keepout.py`, `check_grade._strip_half_width_m`, `grade_law` taxi envelope, `law/tables.zone_edge_offset_m` |

Disjoint except for `law/tables.py`, `check_grade.py`, `grade_law.py`,
`config.py` and `rulesets.toml`. In those files the lanes touch disjoint
functions or keys, named above; the merges are textual.

**Order:** #763 → #768 → #766 → L1 → L2 → L3. L1 first because L2 (row 5, the
app-class) and the census readers consume its sidecar key. L3 last because it
moves the planar mesh, so its re-read must include L2's band values. If L2 and
L3 are ready together, they merge as one batch with one sweep.

Each lane builds ONE closing airport: L1 CYXY (the cheap control: RAOA and the
letter); L2 HECA (rows 1, 2 and 10 all bind); L3 KCLT (FAA F widening plus
row 2's interplay). The master's sweep after the batch is the verification
(§6).

**Build time:** M1 adds ≤ 45k rows at HECA (<1 % of the 60 s budget expected;
the lane measures it on a replay). Everything else is equal or fewer rows.

---

## 6. Verification plan (the bigger work — per airport)

Read against the sweep reference **of main with #763+#768+#766 merged** (the
master's next sweep), not against `sw24`. #763's interim FAA 5 % would
otherwise show as a regression it is not. Compare with
`tools/airside_value_delta.py --tol 0.02 --by-ref 8` plus `cmp` of the rebake
plans. Read with the law-true census (`tools/harness/census.py`).

Expected direction:
- ↓ = rows falling, or fewer rows.
- ↑ = rows rising where the solve cannot hold the stricter law (each one
  attributed, never accepted silently).
- ⇄ = vertices move, but the census has no reason to change.

### Seam probe

Two seam probes, both through `tools/v2_solve_replay.py --replay … --from
planar --verify --z-out`, run on registered captures in scratch trees with
one TOML value edited (never committed). Both arms are supersets of the real
change, so they are upper bounds:
- RATE: ICAO `strip.arc_rate` at 1 %/30 m. This also tightens `strip_arc`,
  which row 2 does not touch.
- APRON: `common.roles.apron` max at 1 % on every apron face, not only the
  faces with stands.

Base: `c184723a6` (#763 phase 5). Movers are vertices that moved more than
0.02 m, by senior face role.

| Probe | Census rows (verify) | Hard set | Movers (> 0.02 m) |
|---|---|---|---|
| CYXY RATE | `airside_no_step` 22 → 43, `strip_arc` 6 → 15 | feasible, 0 hard rows violated | graded_strip 22 (worst 0.24 m), junction 10 (0.03), primary_parallel 1 (0.24 m at 60.71194, −135.07141), cross_connector 1, apron 1 |
| CYXY APRON | `within_shape` 234 → 232, `transverse` 28 → 26 | feasible (63,671 → 65,039 hard rows, 0 violated) | apron 229 (worst 0.35 m at 60.70554, −135.07662), junction 76 (0.17), graded_strip 76, service_road 58, cross_connector 21, parking_lot 18 |
| HECA RATE (base #763 + #768) | `airside_no_step` 3,723 → 4,089, `strip_arc` 1 → 2 | 103 hard rows violated in both arms | graded_strip 7 (0.06), apron 4 (0.11 m at 30.10320, 31.39623), secondary_parallel 3, junction 2, primary_parallel 1 |
| HECA APRON | 21,379 → 25,721 rows: `airside_no_step` 4,049 → 4,978, `taxi_box` 2,867 → 3,537, `strip_seam_tear` 37 → 51, **`runway_transverse` 0 → 1 (a DEFECT family)** | hard rows violated 102 → 141 | not vertex-comparable: the planar map changed (44,626 → 44,641 vertices) |

Reading the probes:
- The rate rows are SOFT (a `law` penalty), so a stricter rate shows up as
  census rows, never as infeasibility. It moves little pavement: CYXY 35
  vertices, worst 0.24 m; HECA 17, worst 0.11 m. It adds `airside_no_step`
  rows that L2 must attribute.
- The apron rows are HARD. CYXY's superset arm stays feasible. **HECA's does
  not stay clean**: a 1 % hard cap on every apron face adds 39 violated hard
  rows and a runway DEFECT row. Row 10 must therefore be scoped to stand faces
  (owner Q4), and L2 closes it on HECA.
- The HECA capture replays with a large standing count on BOTH arms (21k
  rows; the capture predates the current engine, see memory "replays must use
  the app mesh", #737). Only the deltas are evidence; the absolute counts are
  not.

### Per airport

| Airport | Changed laws that can bind | Families to read (expected) | Airside? | Owner sites to re-check |
|---|---|---|---|---|
| **NLWF** (ICAO) | Row 1: code 2, 5 → 3 %. Row 8: RAOA removed at both ends (no `pa`). Row 2: B-taxi rate. Row 3: B strip 11 → 5.75 m. Row 10: 2 tie-downs | `strip_transverse` ⇄/↑ at the band, `raoa` ↓ (to 0), `airside_no_step` ↑, `adjacent_ground_step` ⇄ | taxi rings (row 2) | seawall shore, 29a (4) |
| **CYXY** (ICAO) | Row 1: 14R/32L and 14L/32R 3 → 2.5 %, 02/20 5 → 3 %. Row 8: RAOA kept at 32L only. Row 2: A/B/C/D rates. Row 3: D 18.5 → 9.5 m, B 11 → 5.75 m. Row 10: 7 gates + 13 tie-downs. Letter: 14L/32R D→C (no table effect) | `raoa` ↓, `strip_transverse` ⇄/↑, `airside_no_step` ↑ (probe 7 → 26), `runway_end_skirt` ⇄ at the escarpment ends (15h), `plane_gradient`/`within` ⇄ on stand aprons | taxi rings, stand aprons | 15j v2132 (60.71132797, −135.07199978); 15i strip_arc site (60.715966, −135.066514); escarpment ends 14R/32L, 14L/32R, 02/20 (15h (1)) |
| **KASE** (FAA) | Row 4: D (40 m), 3 % — the same as main, a change only against #763's 5 %. Row 5: 15 `npa`, 33 `apv` (33 displaced 314 m: the threshold datum matters here). Row 2: C rate 1 %/30.5 m. Row 3: C 12.5 → 10.5 m. Row 9: FAA taxi lip 4.5–5.5 %. Row 11: shoulders if §40 built. M2: end zones straight (C–E) | `runway_end_skirt` ↑/⇄ where ground rises beyond 61 m, `runway_vertical_curve` (M2) ⇄ on the runway, `airside_no_step` ↑, `adjacent_ground_step` ⇄ | runway end zones (M2), taxi rings | the KASE "mostly approved" items; city X-Obj placements (15a (4)) |
| **SPJC** (ICAO) | Row 1: 3 → 2.5 %. Row 8: RAOA removed at 34L, 34R. Row 2: B–F rates. Row 3: F 22 → 9.5, E 19 → 7.5, C 12.5 → 5 m. Row 10: 94 gates + 92 tie-downs (the widest stand set after OTHH) | `strip_transverse`, `raoa` ↓, `airside_no_step` ↑, `plane_gradient` / `within` on aprons ⇄ (row 10 HARD 1 % — read every relaxed row in the §5a report) | aprons (row 10), taxi rings | SPJC is gentle (memory): any large count is bug/instrument first |
| **KCLT** (FAA) | Row 4: E, 3 % (= main). Row 5: depends on the CIFP join (§3.4 flag). Row 3: F 22 → 24.9 m (WIDER). Row 2: F rate. Row 9: taxi lip. Row 11: shoulders. M2. Row 10: 112 gates + 60 tie-downs | `adjacent_ground_step` and `strip_seam_tear` ⇄/↑ (wider bands meet more roads and lots; groundside cut-back 0.6 m holds), `airside_no_step` ↑, `runway_end_skirt` | taxi rings, aprons, runway end zones | 15i loop (35.2302, −80.9553); 18C taxiway T (15e, not an EAT) |
| **HECA** (ICAO) | Row 1: 3 → 2.5 %. Row 8: RAOA removed at 05L, 23R. Row 2: E/F rate. Row 3: E 19 → 7.5, F 22 → 9.5 m. Row 10: 43 gates + 172 tie-downs over 297 apron faces. M1: non-binding (end-to-end ≤ 0.14 %, captures) | `strip_transverse` ⇄/↑, `airside_no_step` ↑, apron `plane_gradient` ↑ risk, `raoa` ↓, `strip_seam_tear` (15g baseline 37) | aprons, taxi rings | 15i apron/junction 0.511 m (30.109008, 31.403958); Seasonal Terminal walls (15a (4)); dip/sag sites (memories heca-dip/sag) |
| **OTHH** (ICAO) | Row 1: 3 → 2.5 %. Row 8: kept at all 4 ends. Row 2: F rate. Row 3: F 22 → 9.5 m. Row 10: 345 gates (the largest). Letter E→F: EAT tail +4.3 m only if a recognised EAT exists | apron `plane_gradient` / `within` (row 10 is the main risk), `airside_no_step` ↑, `strip_transverse` | aprons (row 10), taxi rings | bridge deck / tunnel sites (memories othh-*) |
| **KDEN** (FAA) | Row 4: E/F, 3 % (= main). Row 5: `pa` everywhere → 34:1 from 61 m. Row 3: E 19 → 21.1, F 22 → 24.9 m (wider). Row 2: rates. Rows 9, 11. M2 | `runway_end_skirt` (17R/34R end bands, 15c site), `adjacent_ground_step` ⇄, `airside_no_step` ↑ | taxi rings, end zones | 15c KDEN shape 1306 zone2#74; 15e 17R / 34R EAT-returned taxiways |
| **KBJC** (FAA) | Row 4: 12L/30R C (letter fix), 3 %; 12R/30L and 03/21 B, 5 % (the ONE place the band LOOSENS against main: code-4 B 3 → 5 %). Row 5: 30R `pa`, 12L/30L `npa`/`apv`. Rows 2, 3 (C 10.5, A 3.75, B 6.75 m), 9. M2 on 12L/30R. Census letter now = engine's (75 ft B: 2 % not 1.5 %) | `strip_transverse` ↓ on the B runways, `runway_end_skirt` at the 12L end, `transverse`/`strip_longitudinal` census rows on 12R/30L ↓ (census now judges B) | taxi rings, end zones | 15c KBJC 12L end ground truth (39.9162644, −105.1319067; 39.917411, −105.1308332) |
| **KATL** (FAA) | Row 4: E, 3 % (= main). Row 5: `pa` everywhere. Row 3: E 19 → 21.1 m (wider — check the I-285 mouths and walls). Row 2: E rate on 2150 edges. Row 10: 190 gates. Rows 9, 11. M2 | `adjacent_ground_step` (15b baseline 64), `strip_seam_tear` (15b 10), `terrace_joint_strip` (15b 1), `airside_no_step` ↑, `runway_end_skirt` | taxi rings, aprons, end zones | 15a I-285 (33.6200754, −84.4307614); `muro_concreto5` wall (33.6412038, −84.4211416); Victor EAT (15e) |

Every approved airport (HECA, OTHH, SPJC, CYXY, NLWF, KPDX, and most of KASE)
moves under row 2 and row 3; the owner re-reads all of them once (15l (4)).
The sweep report lists, for each airport, the movers by role (runway / taxi /
apron / ground) with the worst vertex and its coordinates, so the owner reads
sites, not totals.

---

## 7. Owner questions (intent the standards leave open)

1. **FAA end rise: the approach surface alone, or the approach surface and the
   40:1 departure surface, whichever is lower?** §3.16.5 (3) names only
   approach and clearway; the engine reads 40:1 today. Recommend the lower of
   the two: no FAA end area gets looser than today, and the EAT keeps 40:1
   either way.
2. **Approach class from the CIFP ident when the category and visibility
   minimums are not witnessed.** Recommend: ILS/GLS/MLS = precision (RAOA,
   34:1 from 61 m, and the code-3 end zone, read as Cat II/III, the strict
   reading). RNAV/RNP = APV (20:1 from 61 m plus 30:1; not precision for
   Annex 14). Everything else = NPA at ≥ ¾ sm (20:1).
3. **Minimum distance between grade changes (ICAO §3.1.19, FAA §3.16.1).** It
   cannot be stated exactly on a vertex surface, and the existing K-curve rows
   already hold it to within a factor of two. Recommend no generator; record it
   as implied.
4. **Stand cap witness.** Recommend: an apron FACE containing a 1300 gate or
   tie-down takes 1 % hard. The alternative, an aircraft-size disc around each
   stand, needs a new planar region and its own census; it is not recommended
   for Beta 2. A cap of 1 % on EVERY apron face (the plain table edit) is
   ruled out by the probe: at HECA it adds 39 violated hard rows and a
   `runway_transverse` DEFECT row.

(Out of scope by existing law, no question: the ungraded strip and ROFA beyond
zone 2 are raw DEM (08-01, 15g (B)).)

## 8. Not done in this round

- No engine code, no builds.
- No per-airport row counts, except the seam probes in §6 (CYXY and HECA, rows 2 and 10).
- TP 312 and Annex 14 amendments after the 8th edition were not read.
- The KCLT CIFP join was not verified.
- Whether OTHH has a recognised EAT (for the letter E→F tail) was not checked.
