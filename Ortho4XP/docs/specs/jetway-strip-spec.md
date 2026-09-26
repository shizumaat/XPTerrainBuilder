# THE JETWAY STRIP — the apron under the jetways is LEVEL with the terminal (issues #32, #31)

Fable 2026-09-25, lane `jetwayspec`. Law: owner RULINGS 2026-09-18t Q3 (verbatim: "UNDER THE
JETWAYS THE APRON STRIP IS LEVEL WITH THE TERMINAL — a NEW AIRSIDE LAW, solved airside-first;
nothing groundside pulls it"), 18t (2) "units by intersection, NO jetway recognition", 23a
(apron does not extend under a pad; pad = footprint; apron welds to the pad edge), 18m, F.9.
Standing law this sits on: §16g (13bo units), §20 (pad takes the pavement's edge level), §28,
§30 (4) (the cluster pad and its collar), §16 / §32 (post-solve projections), §37, §38,
pack-read spec §F (S6, S7, F.5, F.9). Consumer census per RULINGS 2026-08-30l (§3).
**PREREQUISITE**: 23a's implementation (`claude/spjcpads` beb5ba4d / 7c470a6a, `planar/overlay.py`)
is NOT on main today; this law reads the 23a pad (= the unit footprint) and lands after it.

## 1. THE REGION — recognised without recognition

**Measured** (scratchpad `jetway_reach3.py`, to be promoted on its second use; pristine
`*.anchor_bak.*` dumps + the shipped `Patches/<tile>/<ICAO>.graded.json`; names picked the
MEASUREMENT population only). Hosts = every placed resource ≥ 2.5 m tall, ≥ 10 m across, plan
raster ≥ 100 m² (F.2's closure test DROPPED for the instrument: HECA's T23 shells are
material-sliced walls, closure 0.56); 1 m raster, EDT distance from each jetway DSF anchor.

| | LEMD (121 `.agp` + 1 A380 `.agp`) | HECA (48 `.agp` + 3 `EGCC_Jetway_metal_03.obj`) | SPJC |
|---|---|---|---|
| anchor → nearest host outline | 121/122 ≤ 0.5 m, 122/122 ≤ 1.0 m | 7/51 ≤ 0.5 m, 46/51 ≤ 2.0 m, 51/51 ≤ 5.0 m (p50 1.4) | 0 jetway placements (Autogate DGS/marshaller only; the OSM `jet_bridge` ways are §34 (5)'s, refused as decks) |
| `.agp` TILE (its own declared plan footprint) | ±10 m | ±5 m | — |
| SAM reach (`sam.xml`, rotunda → cabin end) | cabinPos 15.9–17.2 + maxExtent 10–25 = **26–42.2 m** (130 rows; 11 at 42.2) | 17.5 + 18 = **35.5 m** (48), 33.2 (3) | — |
| static OBJ forward extent (retracted) | 13.6 m | 13.4–14.0 m | — |
| anchors standing on an apron face | 122/122 | 60/60 | — |

Two findings decide the shape: (i) a jetway's anchor IS at the terminal wall — S7's 0.5 m anchor
rule (F.5 (1)) catches LEMD whole and HECA 7 of 51; HECA's rotundas stand 1–2 m off the wall
with the `.agp` TILE (±5 m) and the object's own back end (6.5 m behind the origin) reaching it.
(ii) the wheels and cabin stand 26–42 m out; the owner's "30–60 m" is the stand, the jetway is
the first 40.

1. **THE RIDER** (S7, F.5 (1) as amended). A placement the plan holds no geometry for
   (`.agp`, multi-anchor, `lib/`) is a RIDER of the unit whose outline it stands within
   `rider_reach` of: `rider_reach = max([placement] footprint_touch_m 0.5, its declared
   plan half-extent)`, the half-extent being the `.agp` `TILE` (read once per resource, a
   number in the file) or the OBJ8 plan box for a parsed multi-anchor, capped at
   `[placement] rider_reach_max_m` (10 m). Name-free; the marshaller 40 m out never rides.
   Host: the nearest outline; ties → larger area, lower placement id (F.5).
2. **THE STRIP**. For each 23a pad (= the unit footprint), the pad-edge segments that carry a
   rider anchor within `rider_reach` are the RIDER EDGES. The strip is the apron within
   `[design] jetway_strip_m` (**D = 40 m**, plan distance from a rider edge, measured along the
   edge's outward normal and capped at the edge's ends + D) — apron faces only, and never a
   vertex the taxi / runway family carries, never a zone-band vertex, never an apron vertex a
   taxi-family no-step row couples (the §30 (4) `cluster_apron_faces` strike set, 13cc (i) —
   reused as THE ONE derivation of "apron a pad may move", never re-spelt). A pad with no rider
   mints no strip. D = 40 covers every HECA gate and 119/130 LEMD gates; the 11 A380 gates
   overrun 2.2 m at ≤ 1.5 % = 3 cm, under the 0.05 m visual floor (§31).
3. Riders are NOT bodies: never in the contact graph, the groups, the clusters or the plan's
   `bodies_of_plan` (F.2); a rider record only (§4).

## 2. THE LAW

Owner 18t Q3 chose (b): the strip is level at the terminal's level, an AIRSIDE law.

1. **ONE LEVEL PER STRIP.** Every strip vertex takes ONE value `L_strip`; the strip's own slope
   cap is 0 within D (the apron's `preferred` 1.0 % / `max` 1.5 % → 0). `L_strip` is AIRSIDE-
   DERIVED: the median of the stage-1 airside solve's z over the strip's vertices — the apron's
   own value where the jetways stand, nothing groundside in it.
2. **THE PAD TAKES THE STRIP.** §20 already makes the pad's level the senior frontage's edge
   mean and 23a welds the apron to the pad edge (`pad_airside_weld` 0.00); with the strip level
   the pad's frontage IS `L_strip`, so the pad datum = `L_strip` with no new pad row. A rider-
   carrying pad keeps §20's one plane; its tilt ceiling stays 1 % hard (a level strip along
   the whole rider edge makes it level in fact; a pad whose rider edges disagree is §6 Q1).
3. **THE TRANSITION.** Beyond D the apron returns to its own law: from the strip's outer line
   the surface grades to the stage-1 value over `L_t = |fall| / rulesets.apron.max.longitudinal`
   (1.5 %; never over the 5 % ceiling), along the rider edge's outward normal — the §13.9
   field construction, the annulus being the band D … D + L_t. A taxi / runway / zone / seam
   (§38) vertex inside the band is NEVER moved: the field is clamped there and the clamp is a
   REPORTED residual (family `jetway_strip`, per gate: rider, strip, clamp vertex, metres).
4. **A PROJECTION, NOT A ROW SET.** The strip is applied like §16 / §32: after the stage-1
   airside solve and before stage 2 (the pads read the projected apron as their constants).
   WHY (the precedent that decides it): §30 (4)'s collar — a cap-0 plane over the apron within
   40 m of a cluster, minted as stage-1 rows — is BUILT and DISARMED (`emit.toml
   cluster_apron_reach_m = 0.0`, RULINGS 14bk): on matched HECA pairs 11,363 airside vertices
   moved, 2,211 of them > 500 m away, the runway 849 worst 1.62 m — "a FIELD-WIDE shift of an
   UNSETTLED stage-1 optimum (14as (ii)) … cannot be met by ANY row added to stage 1 until the
   airside solve settles". A projection moves only what it names; "airside moved outside the
   strips + transitions ≤ hard_tol_m" becomes satisfiable by construction and IS the bar.
5. **Drainage.** `rulesets.toml apron_min_grade = 0.005` has NO reader (`law/model.py:148` only);
   a level strip breaks no law. Stated, not changed.
6. **Verify.** `jetway_strip` family: (a) a strip vertex off `L_strip` by > 0.05 m; (b) a
   transition pair over the apron `max`; (c) each clamp residual. Registered in `LAW_FAMILIES`
   (the `test_harness` twin) and in `families.toml`; the sidecar publishes `jetway_strips_ll`
   (polygon + level + rider count) so the census reads it law-true, like `terrace_joints_ll`.

## 3. CONSUMER CENSUS (RULINGS 2026-08-30l) — every pass reading apron faces or pad edges near a pad

| # | consumer | reads | ruling |
|---|---|---|---|
| C1 | `planar/overlay.py` 23a apron cut (pad = footprint, apron cut back to the pad edge) | pad outline vs airside faces | UNAFFECTED — the strip is a REGION over apron vertices, not a face, hole or shape class; it is derived AFTER the cut from the 23a pad edge + rider anchors. |
| C2 | `constraints/pads.pad_frontage_level` / `_airside_only` / `pad_frontage_leaders` (10–50 m band) | the pad's airside frontage as leaders | UNAFFECTED in code; in VALUE the leaders inside a strip read `L_strip` (stage-2 constants), which is §2 (2). |
| C3 | `pads.pad_flats` / `pad_slope_ceiling` / `cluster_pad.plane_groups` | the rim pairs | UNCHANGED (one plane, 1 % hard). |
| C4 | `constraints/apron.py` within_shape + frontage chords; `apron_trend` / `surface_trend` | apron ring edges, pad→apron chords | UNAFFECTED — they price the stage-1 solve; the projection runs after it. The `within_shape` VERIFY family reads the emitted rings: strip pairs (grade 0) pass; transition pairs are held ≤ `max` by L_t (§2 (3)). |
| C5 | `constraints/cluster_pad.cluster_apron_faces` / `cluster_apron_plane` / `cluster_pad_takes_collar` | apron within reach of a cluster; the strike set | EDITED: `cluster_apron_faces`'s strike logic becomes the shared derivation the strip calls (one derivation, two readers). The two disarmed collar generators are REFUTED-AND-DELETED with their `[design]` heads (§6 Q3, default delete). |
| C6 | `constraints/no_step.py` (`no_step_edges`) | airside pairs by route | UNAFFECTED as rows; its COUPLING set is what strikes strip vertices (C5). The verify family `airside_no_step` over the emitted rings is met by L_t at the apron cap, or the clamp is reported. |
| C7 | `constraints/ceiling.py` 5 % hard | every pavement pair | UNAFFECTED — L_t is priced at 1.5 % < 5 %. |
| C8 | `constraints/zones.py`, `strips.py`, `transverse.py`, `runway_*` | zone bands, runway family | UNAFFECTED: struck from every strip and clamped in every transition; taxi/runway family byte-identical is a bar. |
| C9 | `constraints/roads.py` §37 (free-road ruling; §37 (6) groundside ramp from its airside contact) | roads welded into apron; airside contacts | UNAFFECTED in kind: a road welded into the strip IS apron and takes `L_strip`; a groundside ramp's contact now sits at `L_strip` and ramps from there. |
| C10 | `constraints/groundside.groundside_ramps`, `pad_frontage_gs.py` §28 | the apron↔groundside stand-off; groundside frontages of the pad | UNAFFECTED — followers of the pad / apron; never pull (§28 (2), 08d (4b)). |
| C11 | `constraints/seams.py` §38 | the seam band's DEM pin | UNAFFECTED, senior: a seam vertex is a clamp (§2 (3)). |
| C12 | `solve/design.py` (§20b stage split, §9b datum, §16/§32 projections) | stage order | EDITED: the projection is inserted between stage 1 and stage 2; the datum rows are untouched (a strip vertex keeps its body; the projection overrides its value). |
| C13 | `verify/pads.pad_flat`, `verify/census.DEFECT_KEYS`, `families.toml [pad_airside_weld]`, `harness/census.py`, `tools/check_grade.py` | emitted rings, sidecar keys | EDITED: NEW family `jetway_strip` + NEW sidecar key `jetway_strips_ll` — twins in `test_harness.py` refuse a census that omits either. |
| C14 | `emit/*`, `pipeline/publication` | solved z, faces | UNAFFECTED in geometry (no vertex added or removed); publication writes the new sidecar key. |
| C15 | `airport/footprint_unit.plan_unit_datums` / `plan_wide_seats` (unit datum = the cluster pad plane, median since 17t) | the pad plane | UNAFFECTED in code; in value the unit datum = `L_strip` through the pad. |
| C16 | `airport/pack_partition` (`drop_now` multi-anchor), `placement_plan`, `contact.partition` | plan bodies | UNAFFECTED — a rider never becomes a body (F.2). |
| C17 | `airport/dsf_write.edit_dump` / `footprint_unit.msl_seats_for_dump` (§16g (5), 13by "on ground suffices") | rows to rewrite | EDITED: a rider row is left ON GROUND where the terrain at its anchor equals its unit datum within `hard_tol_m` (after this law, the normal case); `OBJECT_MSL` = unit datum + authored offset only on a residual. |
| C18 | `law/rebake_schema.py`, placement JSON (`o4_v2_placement_<ICAO>.json`: `msl_seats`, `kept`, `splits`) | the plan record | EDITED: NEW `riders` list + `jetway_strips` (§4). |
| C19 | `planar/structure_underpass.py` §34 (5); `planar/channel.py` §45 (1)(c) | OSM `jet_bridge` ways; pack witnesses beside a road | UNAFFECTED (jetway ways stay refused as decks; point objects beside a road are no witness). |
| C20 | Swift `SceneryKit` | JSONL event names | UNTOUCHED. |

## 4. #31 — RIDERS: no body, a SEAT RECORD on the carrier, re-seated on write

Today (F.5): LEMD's 121 `.agp`, HECA's 48 `.agp` and OTHH's multi-anchor jetways never reach
the plan; X-Plane drapes each at its anchor on whatever the apron does there.

1. `airport/riders.py`: `riders_for_dump(dump, units, pads, law) -> list[Rider]`;
   `Rider(index, resource, lon, lat, heading, kind_before, host_unit, host_pid, anchor_gap_m,
   reach_m, strip_id | None, seat_z, seat_why)`. `seat_z` = the host unit's datum + the
   authored offset (`footprint_unit.authored_offset`, the 11b conversion). `seat_why ∈
   {on_ground, msl_written, no_host}`.
2. The plan JSON carries `riders` and `jetway_strips: [{pad_ref, level, rider_count,
   polygon_ll, clamps: [...]}]`; the DSF write reads `riders` (C17). The census counts per
   airport: riders / in a strip / on ground / MSL written / no host.
3. STEP 0 (F.5 (3), F.8): whether X-Plane 12 honours `OBJECT_MSL` for an `.agp` and SAM follows
   it is UNVERIFIED — one owner sim read of a hand-edited row. If it does not, the strip law
   (§2) is the ONLY seat a `.agp` jetway can have, and `msl_written` is refused for `.agp`.

## 5. ACCEPTANCE — the owner's sites (RULINGS 17p–17ab), numbers first

Shipped products (pre-23a pads, the strip absent). Apron z interpolated in the containing
face at each rider anchor, grouped by nearest pad:

| site | pad | riders | apron at the anchors: min … max (spread) | pad plane | pad − apron median |
|---|---|---|---|---|---|
| HECA T3 30.1080544,31.3958302 (17p (2), 17s, 17z) | `building9` | 29 | 99.13 … 103.12 (**3.99 m**) | 99.37 | −2.12 |
| HECA T3 | `building6` | 12 | 97.77 … 100.46 (2.70) | 95.89 | −3.66 |
| HECA T3 | `building13` | 10 | 102.61 … 104.24 (1.63) | 100.51 | −3.62 |
| LEMD T4 40.4967429,−3.5912949 / 40.4967396,−3.5899271 / 40.4964709,−3.5910008 (17p LEMD 4, 17u, 17x) | `building49` | 12 | 616.13 … 616.49 (0.36) | 615.70 | −0.60 |
| LEMD T4 | `building45` / `47` / `44` / `43` | 15 / 5 / 5 / 2 | 615.90 … 616.59 (≤ 0.69) | 615.17–615.82 | −0.95 … −0.50 |
| LEMD T1–T3 | `building26` / `25` / `48` / `52` | 34 / 6 / 37 / 6 | spreads 3.89 / 1.65 / 1.41 / 0.92 | | +1.08 / +1.73 / +0.20 / −4.14 |

17x (fix B, OFF): the worst buried T4 unit foot +1.73 → +0.43 m; HECA T3's shells stand on
`pav1`, which falls 5.4 m across the district (17z). The owner's nearest riders: 49–62 m
from the three LEMD points (`building49`, pad 615.67 vs apron 616.60); 34 m from the HECA point.

BARS (materiality 0.05 m = the §31 visual floor; attempt cap 2):
1. HECA T3 (the closing build): every rider of `building9` / `6` / `13` stands on apron within
   0.05 m of its unit datum, OR its gate is in the `jetway_strip` clamp list with metres.
2. LEMD (offline replay on a registered capture, no build): `pav12` at the T4 riders' anchors
   = the pad datum ± 0.05 (today 0.36–0.69 m spread, pad 0.5–0.95 m under); every T4 unit
   member's buried foot ≤ 0.20 m (17x's bar; 0.43 with fix B) with fix B still OFF.
3. `pad_airside_weld` 0.00 at every rider-carrying pad; taxi / runway family z byte-identical
   to the base arm; airside moved outside strips + transitions ≤ `hard_tol_m` (14bk's bar).
4. #31 census: HECA 51 riders / LEMD 122, `no_host` 0 at both; `on_ground` = all where bar 1
   holds; `msl_written` only on clamped gates.
5. Plan stage + solve wall not worse than +1 % of the 60 s budget (0.6 s): the region is an
   STRtree query over ≤ 200 anchors × pad edges and the projection one linear pass — expected
   < 0.2 s; measured with the ledger's phase times, never a single run.

## 6. OWNER QUESTIONS (recommended defaults in bold)

- **Q1 — the long terminal.** HECA `building9` carries 29 riders over an apron falling 3.99 m
  along the jetway line (LEMD `building26` 3.89 m over 34). One level per strip absorbs that
  beyond D over L_t = 266 m at 1.5 % (80 m at the 5 % ceiling) — into the T3 taxilane, which
  is never moved, so the strip is clamped and the residual reported. Alternatives: (a) one
  level per pad, transition at 1.5 %, clamps reported per gate — the ruling read literally;
  (b) the strip levels PER SEGMENT (riders within `jetway_strip_gap_m` 60 m along the edge
  form a segment; segments differ in level by ≤ the apron's fall over the gap), and the
  terminal is then the 17x reserve shape (unit partitioned by reach); (c) the transition at
  the 5 % ceiling. **Default (a); (b) needs your T3 read since 17z refused fix B there.**
- **Q2 — D.** Fixed 40 m from the population, or per gate from `sam.xml` (cabinPos +
  maxExtent) where a SAM row stands within 1 m of the anchor — reading SAM is recognition by
  data, not by name. **Default: fixed 40 m; SAM as a later refinement if a gate misses.**
- **Q3 — the collar.** `cluster_apron_plane` / `cluster_pad_takes_collar` are disarmed
  (reach 0) and refuted as stage-1 rows (14bk). **Default: delete them with this lane** (BUILD
  ECONOMY: refuted mechanisms are deleted); the strip is their successor.
- **Q4 — the stand.** The aircraft's nose gear stands 10–20 m beyond the jetway cabin. Include
  the stand (D ≈ 60)? **Default no: your words were "the jetways"; the stand slopes ≤ 1.5 %.**
- **Q5 — rider reach.** `max(0.5 m, the .agp TILE / OBJ8 plan box half-extent)` capped 10 m
  (HECA's rotundas 1–2 m off the wall). **Default as stated; an anchor beyond it is reported
  `no_host`, never guessed.**
- **Q6 — `.agp` MSL rows** (§4 (3)). One sim read of a hand-edited LEMD row decides whether
  `msl_written` exists for `.agp` at all. **Default: assume not; the strip is the seat.**

## 7. THE OPUS IMPLEMENTATION BRIEF (lane `jetwaystrip`, after `claude/spjcpads` lands)

Files: NEW `src/auto_patch_v2/planar/jetway_strip.py` (rider edges, strip polygons, the
strike set moved from `cluster_pad.cluster_apron_faces` into one shared derivation), NEW
`src/auto_patch_v2/solve/project_strip.py` (`L_strip` median, the D…D+L_t field along the
edge normal via the §13.9 construction, clamps), NEW `src/auto_patch_v2/airport/riders.py`
(§4), EDIT `solve/design.py` (stage order, C12), `airport/dsf_write.py` (C17),
`law/rebake_schema.py` + `airport/placement_record.py` (C18), `law/emit.toml [design]
jetway_strip_m = 40.0`, `jetway_strip_gap_m = 60.0` (Q1 (b) only if ruled),
`law/structures.toml [placement] rider_reach_max_m = 10.0`, `law/families.toml
[jetway_strip]`, `verify/census.py`, `tools/check_grade.py LAW_FAMILIES`,
`pipeline/publication.py` (`jetway_strips_ll`), `law/design_schema.py`. DELETE the collar
generators + `cluster_apron_reach_m` (Q3 default). Promote the measurement script as
`tools/jetway_rider_census.py` with its `tools/INDEX.md` row (second use; `--strip` prints §5's
table per pad). Run `tools/blast.py` on each file before editing.

Twins (`tests/auto_patch_v2/test_v2jetwaystrip.py`): a `.agp` anchor 1.4 m off the wall inside
its TILE rides, one 40 m out does not, a marshaller never; strip vertices = the apron within D
of a rider edge minus the strike set (a taxi-welded vertex absent); `L_strip` = the stage-1
median; L_t = fall / 1.5 % and every transition pair ≤ `max`; a taxi vertex in the band is
byte-identical and appears as a clamp; a seam vertex likewise; the pad's weld 0.00 and its
datum = `L_strip`; a rider row left on ground when the terrain equals the datum, MSL only on
a clamp; `riders` / `jetway_strips` round-trip through the schema; `test_harness.py` refuses a
census missing the family or the key. Suite: the test files covering the change, once.

Synthetic-first: register a HECA capture on the merged base (`v2_solve_replay.py --capture
HECA --placement` — no registered HECA capture exists, `frames.py list HECA` all MISSING),
iterate `--replay --from planar` + `--probe-site 30.1080544,31.3958302`; LEMD offline on its
own capture for bar 2. Closing test: ONE `build_airport.py HECA` (the owner's site), control
via `--base-arm`; no sweep. Build-time statement in the report (bar 5). Deviations from this
spec stop and report (CLAUDE.md 1a); the spec author rules them. Heartbeat + `.progress`.

NOT DONE HERE: no code; no capture taken; SPJC has no riders to measure; OTHH's 14 multi-anchor
jetway types not measured (same rule, S7's customer); the `.agp` MSL sim check (Q6) is the
owner's; the collar deletion waits on Q3.
