# v2 — OTHH seat artefacts: the flat-site datum reaches the seat (spec, 2026-09-08)

RULINGS 2026-09-08a (owner: "OTHH should not require any object
modifications") and 2026-09-08d (the attribution: 77 of the 95 objects the
owner's 1.0.293 tile build wrote are SEAT-LAW artefacts). Author: lane
`v2othhseat` (Fable 5.1). Law: `structures.toml [rebake]` (keys stated in
§3). Instrument before any edit: `tools/v2_rebake_replay.py seat` over the
owner's plan `Patches/+20+050/+25+051/o4_v2_rebake_OTHH.json` and the
owner's mesh (`Custom Scenery/zOrtho4XP_+25+051/Data+25+051.mesh`, read
only) reproduces the 1.0.293 result exactly: 24 units bake, 96 resources
(95 files; `tunnel1` is one file at two anchors).

## 1. What was measured (the owner's mesh, the owner's plan)

OTHH is `flat_candidate`, Z0 = 3.96 (05l: 15,428/15,437 rows at Z0).

| family | files | unit / datum | anchor mesh | mechanism (08d) | delta today |
|---|---|---|---|---|---|
| Bridges Bus 02/03/06 | 27 | unit:6 cluster | 0.00 **water** | base = 0 + 0 → every ground part at 3.96 reads +3.96 | +3.35 … +3.96 (bank parts +1.0 … +2.9) |
| Bridges Bus 05 / 04 / 01 | 18 | unit:0/3/17 deck_top | 0.00 **water** | base = 0 + agl (−3.5/−3.8/−3.5); flag deck ring (land only) median 2.81 / 3.28 / 2.11 vs deck top 1.11 / 0.85 / 0.08 | deck +1.70 / +2.42 / +2.04; family parts +4.6 … +7.8 |
| Terminal (TerminalRoads decks + clutter) | 20 | unit:28 deck_top | 3.96 | ring samples FLAT (spread 0.00 / 0.00 / 0.28 / 0.89 m): the deck TOP (10.8 / 11.0 above the plane) is seated at ground | −10.87; cluster members −1.05 … −4.7; interior clutter +2.27 |
| Terminal_Parking_VCN | 2 | unit:23 cluster | 3.96 | parts read the canal-bank cut (2.0–2.8) | −1.89 |
| Emiri | 4 | unit:15 cluster | 3.96 | parts read the raw inset DEM outside the patch (2.6–3.2) | −1.07 … −2.09 |
| tunnels middle-west / -east | 2 | unit:44/65 plate | 2.88 / 2.67 | the plate stations (the rim ring) sample the trench drop: 1.19 … 3.95, median 2.58 | −2.30 / −2.09 |
| tunnels (7 others) | 6 files | plate | −3.43 … 0.62 | the anchor sits ON THE TRENCH FLOOR the mesh cut: the sim's probe reads the floor, the plate seat lifts the plate to the rim (05n-4) | +1.35 … +5.40 (cut compensations) |
| Dewatering 01/02, Drainage 01–05 | 16 | plate | −9.18 / −4.13 / 0.15 | the anchor sits on the pit floor: the floor plate seat compensates the cut | +3.82 / +8.09 / +13.14 (needed) |
| Drainage_06 | 2 | unit:10 plate | 3.96 | delta 0.0013: a no-op write passed by the threshold exemption | +0.001 |

## 2. The rules (08d) as implemented

(a) THE ANCHOR. The anchor's ground is the sim's placement probe — what
X-Plane adds `agl` to. On a flat-candidate site (a `substitutes`
verdict) the datum reaches the anchor: a WATER sample inside the datum
region takes Z0 (`anchor_water_founds_seat = false`; without a datum a
water anchor is HELD, no write); a LAND sample inside the region within
`basin.contact_band_m` of Z0 takes Z0 (`flat_site_anchor_datum = true`:
the plane's own sub-band residual is the datum's). A land sample deeper
than the band below Z0 is a CUT the mesh made (a trench floor, a pit
floor: Dewatering_01 at −9.18, tunnel west 1 at −1.04) and STAYS the
anchor's ground — the sim will probe that floor, and the plate seat's
delta is the cut compensation the owner's 1.0.293 needed. (The brief's
literal "any anchor on a flat-candidate site takes Z0" would zero every
Dewatering / Drainage / tunnel compensation: Dewatering_01's +13.14
becomes 0 and the pit shell renders 13 m under the floor; reported as
the deviation it is, §5.)

(b) THE DECK RING. A flag deck's ring reading requires ABUTMENT RELIEF:
the ring has water samples, or its land samples spread ≥
`basin.contact_band_m`. A ring that samples flat is not a bridge over a
cut (the TerminalRoads decks: an elevated kerb road on columns over the
plane) — the deck seat stands down with a finding and the cluster law
governs the unit's parts (the same form as the mid-span clearance
refusal, `deck_min_clearance_under_m`); on a flat site the cluster law
under (e) keeps the authored y.

(c) THE PLATE STATIONS. A tunnel wall object's plate stations stand at
the wall's OUTER FACE + `emit.identity.min_distinct_spacing_m`, outward,
every `bridge.abutment_sample_step_m` along it — built from the corridor's
own FOOTPRINT (`Tunnel.footprint`, the walls' plan union), never from the
rim ring, so the rule holds whether the rim stands outside the outer face
(main, `rim_gap_m`) or inside the wall (lane `v2trenchgap`,
`rim_inset_fraction`). Basin members keep their floor stations (the
floor plate seats on the floor).

(d) THE THRESHOLD. `structure_seat_threshold_exempt = false`: a
structure seat whose |delta| < `min_delta_m` STAYS (skip
`below_threshold`, members fixed at their authored y, never handed to the
cluster law); the earlier bake, if any, is reverted by v1's reversion
pass as for any skipped resource. 05n-4's exemption (v1's +0.9576
precedent) is withdrawn by 08d; the key keeps `true` as a lawful value.

(e) THE GROUND. On a flat-candidate site the datum extends under every
object footprint (`flat_site_ground_datum = true`) and the pack's seat is
AUTHORITATIVE there: a CLUSTER ground part of an object ANCHORED inside
the datum region — its WHOLE footprint, the parts beyond the region's
edge included (the closing build's first arm: Terminal_Parking_VCN's two
ground parts on the canal bank, 2,077 of the unit's 21,215 parts outside
the region, read the bank's cut at 2.07 and wrote −1.89; instance 2's one
fix) — and any part standing inside the region reads its object's
authored `y = 0` plane as its ground (delta 0 — never the canal bank, never the raw inset DEM outside
the patch, and never `−agl`: a literal "ground = Z0" wrote Bridge_05's
three AGL −3.5 members +3.50 in the replay), and a DECK unit anchored
inside the region keeps its authored deck (the ring / abutment reads
found −2.26 / −1.54 / −1.93 m against a Z0 base on the canal bridges).
Plate stations read the RAW mesh (they stand on a floor or a rim by
construction: the cut compensations).

The datum region is `FlatVerdict.region` (pavement ∪ boundary ⊕
`detector.margin_m`: the extent the datum is priced over), carried into
the plan as `RebakePlan.flat` (PLAN_VERSION 5) in lat/lon.

## 3. Law keys (`structures.toml [rebake]`)

| key | value | rule |
|---|---|---|
| `anchor_water_founds_seat` | `false` | (a): a water anchor takes Z0 where a datum exists, else HELD; `true` = the water surface founds the base (1.0.293's law, v1's) |
| `flat_site_anchor_datum` | `true` | (a): a land anchor within `basin.contact_band_m` of Z0 inside the region takes Z0 |
| `flat_site_ground_datum` | `true` | (e): inside the region a cluster ground part's ground is its object's authored plane and a deck unit keeps its authored deck (the pack's seat) |
| `structure_seat_threshold_exempt` | `false` (was `true`) | (d): a structure seat under `min_delta_m` stays |
| existing `basin.contact_band_m` | 1.0 | (a) the datum band, (b) the ring relief floor |
| existing `emit.identity.min_distinct_spacing_m`, `bridge.abutment_sample_step_m` | 0.5, 5.0 | (c) the station stand-off and step |

No new numeric literal; no `law/*.py` numeric.

## 4. Consumer census (owner ruling 30l): every reader of the anchor ground and the cluster ground

| reader | reads | ruling |
|---|---|---|
| `emit/rebake.seat` line 313 (`sampler(u.anchor)`) → `base` | the anchor ground | (a): water → Z0 / HELD; land within the band → Z0; a cut → the mesh |
| `emit/rebake._deck_reading` flag-ring path (`sampler` over `deck_ring`) | ground at the ring | (e) not reached for a deck unit anchored inside the region (authored deck); elsewhere the raw mesh with (b)'s relief test |
| `emit/rebake._abutment_grade` (signature decks, end lines) | ground at the abutments | (e) as above; no flat-site signature deck in the corpus (LEMD is not flat: unchanged) |
| `emit/rebake._mid_span` (`deck_stations`) | ground under the deck | (e) as above |
| `emit/rebake._plate_reading` (`plate_stations`) | the trench floor / the rim | RAW mesh (a structure read); (c) moves the tunnel stations off the drop |
| `emit/clusters.seat_clusters` line 213 (ground parts' centroids) | the cluster ground | (e) `authored[pid]` = the object's authored plane for a part inside the region; the raw mesh outside |
| `emit/clusters` `_P.base` (from `base_by_member`) | the anchor ground + agl | inherits (a) |
| `engine_v2._decision_from_seats` → `anchor_ground_by_resource`, `seat_datum_by_resource` | provenance | records the (a) ground; reversion keys on resource, not on the value |
| `object_rebake.apply` provenance (`anchor_ground_m`) | provenance | as above; a value change is not a decision change |
| `tools/v2_rebake_replay.py` (`--filter`, the 06g residual metric) | `UnitSeat.anchor_ground_m` | reports the (a) ground; residual metric reads the RAW mesh (unchanged: it measures what the sim renders) |
| `tools/object_seating_report.py` | v1 decision `anchor_ground_by_resource` | v1 path; the v2 hook hands it the (a) ground — report only |
| `airport/flat_site.seat_consensus` (S4) | the objects' authored seats | pre-mesh; not a reader of either |
| `pipeline/build.py` flat verdict lines 304–314 | `airport.flat_site` | the SOURCE; `rebake_plan.plan` now carries it into the plan |

Region containment (shapely, lon/lat) lives in `emit/rebake.py` (already
a numpy/shapely module); `model/rebake.py` stays data-only.

## 5. Replay on the owner's plan + mesh (`tools/v2_rebake_replay.py seat … --flat 3.96`)

Before: 24 units bake, 96 resources (95 files). After the rules (a, d, e
— (c) needs a fresh plan): 16 units bake, 24 files in 2 families —
Dewatering / Drainage 16 (+3.816 … +13.142) and tunnels 8 (−2.299 …
+5.397, the two middle corridors still on the old rim stations).
Bridges Bus 45 → 0, Terminal 20 → 0, Emiri 4 → 0, Drainage_06 → 0. The
closing build was predicted to add (c): middle-west/-east read the
at-grade ground → −0.92 / −0.71 → stay (d) → 22 files. The brief's target
"≤ 18, the Dewatering cut compensations" does not count the six tunnel
files, which are the same class (the anchor on the cut floor the mesh
made); they are quoted, not suppressed.

## 6. The closing builds (`OTHH_v2othhseat` 732 s, `OTHH_v2othhseat2` 745 s; verify 0 both, flat_candidate Z0 3.962, 16,221/16,221 datum rows at Z0)

| family | 1.0.293 | arm 1 (rules a–e as §2) | arm 2 (+ the (e) footprint fix) | rule |
|---|---|---|---|---|
| Bridges Bus | 45 | 0 (4 units HELD: water anchor, `anchor_water_founds_seat = false` — the units lie OUTSIDE the datum region, so Z0 does not found them; held = no write, the pack's bytes) | 0 | (a) |
| Terminal (TerminalRoads decks + clutter) | 20 | 0 (unit:28 deck_top: "flat site — the authored deck seat is the seat") | 0 | (e)/(b) |
| Terminal_Parking_VCN | 2 | 2 (cluster 70, −1.891: two bank parts outside the region) | 0 | (e) footprint |
| Emiri | 4 | 0 (below_threshold) | 0 | (e) |
| Drainage_06 | 2 | 0 ("plate seat \|−0.001\| < 1.0 m — stays") | 0 | (d) |
| tunnels middle-west / -east | 2 | 2 (−2.745 / −2.326) | 2 | (c) REFUTED at this site, see below |
| tunnels (others: south west 2, tunnel1 ×2 anchors, west 1) | 6 files | 3 files / 4 resources (+1.47 … +3.59) | same | cut compensations (a) |
| Dewatering 01/02, Drainage 01–05 | 16 | 16 (+3.816 … +13.142) | 16 | cut compensations (a) |
| **total files** | **95** | **23** | **21** | |

(c) at middle-west / -east, MEASURED on the closing mesh: the new
stations (90 / 64, every 5 m round the footprint at the outer face +
0.5 m, the mitred ring 192 × 60 m / 80 × 119 m) read 0.06 … 3.96, median
2.14 / 2.39 — and probes 1, 2, 3, 5, 8 m further out read medians 2.33 /
2.45 / 2.61 / 2.88 / 3.14. The transect across middle-west at mid-length
is a BOWL 63 m wide (4.0 at −39 m, 1.4 from −24 to −9 m, 4.0 at +24 m)
and along its axis a RAMP (3.0 at +60 m to −0.1 at −60 m): the object
stands ON the corridor ramp of the bore pair −8272/−8271 (both mouths
inside `tunnel middle - west` and `tunnel1@1`, replaced by the objects),
not beside a rim drop. No station placement outside the outer face reads
at-grade ground here, because the corridor cut is wider than the wall
object and descends along it — the (c) mechanism the 08d attribution
named (the rim ring's vertices on the drop) is not what founds these two
deltas on this tree; a rigid plate crest cannot be flush with ground that
falls 4 m along the object. Not fixed (attribution cap); owed to the
corridor geometry (`v2trenchgap`, the rim inside the wall; 08c's sunken
road law) and reported for the owner's sim read: the delta −2.75 / −2.33
lowers the crest to the median ground beside it.

Deviations for the spawner / owner: (i) rule (a) narrowed to the datum
band (§2a); (ii) rule (e) read as "the pack's seat is authoritative"
(the authored plane, the authored deck) rather than "ground = Z0" — the
literal form wrote −agl on AGL-offset objects (Bridge_05 +3.50 × 3) and
the deck reads wrote the canal bridges −1.5 … −2.3 m against a
Z0-founded base (ring medians 2.1–3.3 vs deck tops 4.0–5.1); (iii) v1's
owner-accepted OTHH DID write the bridges (+1.6450 Bridge_05, +2.5672
Bridge_04, +4.1589 Bridge_01, +0.9576 Bridge_02/03/06 — `tools/INDEX.md`),
i.e. v1 founded the base on the water probe exactly as 1.0.293 did; if
X-Plane's placement probe returns the water surface at 0.00, `anchor_water_founds_seat = false`
renders the 45 bridge objects 3.96 m under the banks — the owner's sim
read decides, the key flips it back; (iv) (d) also stops LEMD's two basin
plate seats at +0.425 / +0.426 m (units 24/26: cargo terminal, old
terminal) — bridges/decks there are unaffected.

## 7. The stranded flat planes (owner read 2026-09-09b (5)) — the read

The owner sees "flat floor or ceiling planes floating and separated from
their objects — extensive at HECA, mostly around bridges at OTHH".

Read against the owner's own rebake results (`o4_v2_rebake_result_HECA.json`
of the +30+031 tile, `o4_v2_rebake_result_OTHH.json` of the +25+051 tile),
replaying `engine_v2._decision`'s per-vertex map exactly and grouping by
the CONNECTED COMPONENTS of the OBJ8 solid mesh:

* HECA — 391 members write a delta; **190 of them leave 15,729 components
  with no delta at all, 15,716 of those FLAT** (authored y-extent under
  `min_solid_thickness_m` 0.3 m; most are exactly 0.000 — a pure plane).
  The object around them moves by up to −45 m, so the plane hangs 45 m
  above its walls. The stranded component is typically 0.03–0.17 m from
  the nearest moved component in the authored frame: it is the floor or
  the ceiling slab of the very room whose walls moved.
* OTHH — 23 members write; **11 leave 44 stranded components, all flat**,
  separation +3.816 … +13.142 m, nearest carrier 0.03–0.8 m away. All 11
  are the Dewatering / Drainage basins of the interchange (anchors
  25.2957/51.6036, 25.2521/51.6247, 25.2537/51.6230, 25.2920/51.6059,
  25.2958/51.6048) — the owner's "around bridges".
* The direction is always the same: **the walls move, the horizontal
  plane stays at its authored y.** Never the reverse.

Mechanism, two lines:

1. `airport/rebake_plan.py:194` — `comps = [(i, c) for i, c in
   enumerate(cache.components(o.resolved)) if c.max_y - c.min_y >=
   cache.thickness_m]`. Only THICKNESS-GATED components become `Part`s
   (`[structures.basin] min_solid_thickness_m = 0.3`). A horizontal
   plane has a y-extent of 0.0, so it is never a part, never in a
   cluster, and `clusters.seat_clusters` never mints a delta for it.
   The gate is a WITNESS gate (a decal must not found a seat, 08-26
   §2.1) being used as a WRITE gate.
2. `auto_patch/engine_v2.py:449–459` (`_decision`) — `comps =
   _obj8.solid_components(geom)` enumerates ALL components so the
   indices line up, but `per_vertex` is filled ONLY from
   `ms.part_deltas`. A component absent from that list gets no entry,
   and `object_rebake.apply` always rewrites from `.anchor_bak`, so its
   vertices keep their authored y while the rest of the file moves.

`Part.comp` is 1:1 with a `solid_components` component (`contact.py:118`),
and `clusters` gives one delta per part, so the ruling's first half —
one delta per connected component — already holds; what was missing is
COMPLETENESS: a component with no delta of its own.

### The rule (09b (5))

Every solid component of a written resource follows a CARRIER: the
component the seat considered that is nearest to it (minimum 3-D
distance between their authored vertex sets; ties by lowest component
index) — "the walls that carry it". It takes that carrier's delta, or
STAYS when the carrier stays: a component the seat RULED to stay (a
facility cluster 05p, a cluster under `min_delta_m` 08d (d), an A3
refusal, a structure seat that stays) is never given a delta and carries
its own planes with it, so 08f's rules and the facility rule are
untouched. Only a component the seat never CONSIDERED follows at all.

Replayed on the owner's own results (`tools/v2_rebake_replay.py bodies`):
HECA 15,716 stranded → **2** (both planes whose nearest carrier is a held
component — lawfully staying with their walls), OTHH 44 → **0**.
Implemented once, as pure geometry,
in `airport/rigid.complete_component_deltas` (a new 91-line module: `obj8.py` is at the 1,000-line ceiling); the seat, the
witness gate and 08f's rules are untouched.

## 8. Consumer census (owner ruling 30l): every reader of the per-vertex deltas

| reader | reads | ruling under 09b (5) |
|---|---|---|
| `object_rebake.apply` VT rewrite (`elevation_delta_by_vertex.get(i)`, line 1481) | delta per vertex index | the point of the change: the plane's VT lines now move with their carrier. Backup-sourced rewrite is unchanged, so it stays byte-idempotent |
| `object_rebake._positional_command_rewrite_plan` (lights, smoke, magnets; I-10) | the deltas THROUGH `_structure_boxes_and_deltas` over `decision.structures` | `Structure.triangles_by_resource` already listed EVERY component's triangles (`engine_v2` line 465), so a command's box already covered the plane; its delta was the median over box vertices — now complete, so a command over a stranded plane stops taking a mixed value. No interface change |
| `object_rebake._reconcile_animation_blocks` (I-11) | the same per-vertex map | unchanged shape; more vertices carry a delta, which is what an ANIM subtree needs to stay rigid |
| `object_rebake.apply` provenance `delta_m` / `delta_range_m` (lines 1542–1550) | `set(deltas.values())` | a file whose planes previously stayed at 0 recorded a spurious two-value range; now it records the carriers' range only. Report-only key |
| `emit/rebake.seat` notes + the `n_multi` finding (lines 526–549) | `MemberParts.part_deltas` | UNCHANGED — the completion is a WRITE-side rule over components the plan never made parts of; the seat's own record still describes the parts it seated |
| the plan / result JSON (`o4_v2_rebake_*.json`, `part_deltas`) | as above | unchanged; the follower is derived from the authored OBJ8 at write time, so no new field crosses the plan |
| the app's JSONL (`o4_engine/events.py` → `OrthoEngineClient.swift`) | rebake COUNTS and the summary text only — no per-vertex delta crosses the wire | no wire change; the seat note gains a trailing clause |
| `tools/v2_rebake_replay.py`, `tools/object_seating_report.py` | `UnitSeat` / v1 decision fields | unchanged (neither reads the per-vertex map) |
| `emit/clusters.seat_clusters`, `airport/contact.partition`, the witness gate | genuine parts only | UNCHANGED by ruling: a thin plane still never votes, never founds a seat, never joins a cluster |

## 9. RULINGS 2026-09-09q (1): the exclusion is the MEMBER, never the anchor family

The law: a structure the terrain adapted to (a wall-corridor / basin /
tunnel member) excludes **that member** from the re-seat; every other
member of its anchor family seats per body as 09d does.
`airport/rebake_plan.py`'s family expansion and its key
`[rebake] structure_family_excluded` are DELETED (not gated — the
refutation record is this section and git).

Measured at LEMD (app 1.0.297): the 28 wall-corridor members' ids
expanded to the pack's TWO origin anchors and took **300** placements out
of the re-seat — 188 of the 195 placements off by > 1 m, worst
`OldTerminal_FSX-LEMD38.obj` **+36.4 m** sunk, `Munoza-elect.obj`
**−31.8 m** floating.

### Consumer census (owner ruling 30l): every reader of `excluded` and of the family key

| reader | reads | ruling |
|---|---|---|
| `pipeline/build.py:596-605` (the `excluded` set: basin objects when `basin.seat != "floor_plate"`, plus every `door` / `sunken_road` / `wall_corridor` structure's `tn.objects`) | the SOURCE | UNCHANGED — the set still names exactly the members the terrain adapted to. Only its expansion is deleted, so `seat = "none"` now means "this member is not re-seated", which is what 08b/08c/08m say |
| `airport/rebake_plan.plan` line 82 (`excluded` by id **or** path) | the member spelling | UNCHANGED — both spellings still match, and still only the member (twin `test_basin_exclusion_matches_paths_too`) |
| `airport/rebake_plan.plan` line 93 (the family expansion) | `deck_signature.family_key` | **DELETED** — the point of the ruling |
| `airport/rebake_plan.plan` line ~123 (`o.id in excluded` → `counts["terrain_adapted"]`, `skipped[path]`) | the member set | text amended ("adapted to THIS member … never its anchor family"); the `basin facility` prefix is KEPT so `tools/`-side and scout classifiers that key on it still bucket the class |
| `airport/deck_signature.family_key` | the anchor spelling | UNCHANGED and still used by the three family rules that are NOT the exclusion: `plate_keys` (tunnel wall plates, 05n-4), `deck_keys` (`deck_family_seats_rigid`, R12-2), and the unit key itself (one unit per anchor spelling). Only the exclusion stops reading it |
| `law/rebake_schema.py` `RebakeTable` | the law key | field **DELETED**; `structures.toml:306` deleted with it. `tests/auto_patch_v2/test_law_tables.py` asserts the attribute is gone, so nothing can re-introduce the expansion silently |
| `emit/rebake.seat` (units, clusters, plates, decks) | the PLAN's units — never `excluded` | UNCHANGED code; more units reach it. The readmitted members are held at 0 by the rules that already exist: 08f (a) `flat_site_anchor_datum` / (e) `flat_site_ground_datum` on a flat-candidate site, (b) the deck-abutment relief gate, `min_delta_m` 1.0, and 05p's facility clusters — see the replay below |
| `engine_v2._decision_from_seats`, `object_rebake.apply` | seats by resource | UNCHANGED — a resource that never seats is never written; the exclusion never crossed into the write half |
| `tools/v2_rebake_replay.py`, `tools/object_seating_report.py` | plan / seat records | UNCHANGED (neither reads the law key) |
| `docs/specs/auto-patch-v2/tunnel-wall-objects-spec.md` §89, `othh-terminal-ramps-spec.md` §156 | prose naming the key | historical record of the withdrawn reading; superseded by this section |

### The proof that OTHH's terminal families do not move (no tile build)

`build_airport.py OTHH --engine v2 --patch-only` (tag `v2lemdseats_OTHH`,
400 s), then `tools/v2_rebake_replay.py seat … Data+25+051.mesh` against
the owner's mesh, versus the same replay on the `OTHH_20260909T141611`
plan (the family expansion still on):

| | expansion ON | expansion OFF (this ruling) |
|---|---|---|
| `terrain_adapted` (placements excluded) | 287 | **13** |
| plan units / members | 107 / 680 | 111 / 947 |
| **resources written** | **24** files in 2 families | **24** files in 2 families |
| the families written | Dewatering Drainage 16 (+3.816 … +13.142), tunnels 8 (−2.944 … +3.094) | identical, same deltas |

The 274 readmitted placements add **zero** writes. What holds them is not
the family exclusion:

* the OTHH terminal deck family — `unit:28`, **193** members, previously
  excluded whole — seats `deck_top` and writes 0: *"below_threshold: flat
  site — the authored deck seat is the seat"* = **08f (e)/(b)** with the
  flat-site datum Z0 3.962;
* `unit:23` (Terminal, 31 members) writes 0 as a **05p facility cluster**;
* the units the brief names, PowerStation-Hangar (11 members) and the GSE
  van, were never family-excluded and are unchanged: `unit:22`/`unit:26`
  before → `unit:24`/`unit:29` after, both *"below_threshold: every
  cluster moves less than 1.0 m — stays"* (`min_delta_m`), the van with
  the 08f (a) finding *"anchor within 1.0 m of Z0: the datum 3.96 founds
  it"*.

### §9.1 THE BAR IS MISSED AT LEMD — the exclusion was not the only anchor-family rule

LEMD tile `v2lemdseats_LEMD` (`--tile 40 -4`, 425 s wall, step 2 mesh
41.7 s; rebake plan 30 units / 311 members / 8 terrain-adapted), measured
with the scout's `measure5.py` / `analyze5.py` on the built mesh and the
re-baked pack:

| |Δ| at the worst foot, 870 measured `.obj` placements | 1.0.297 (expansion ON) | this branch (expansion OFF) |
|---|---|---|
| > 3 m | 184 | **185** |
| > 1 m | 195 | 194 |
| < 0.3 m | — | 502 (57.7 %) |
| objects written | 26 | **303** |
| worst placement | `OldTerminal_FSX-LEMD38.obj` +36.4 m | `OldTerminal_FSX-LEMD38.obj` **+36.2 m** |
| worst-30 relief-dominated | 30/30 | 30/30 (|relief| mean 27.45, authored |y| mean 0.61) |
| stranded components (`v2_rebake_replay bodies`) | — | 27,571 → **3** after the 09d completion (bar ≤ 2) |
| multi-anchor class (1,562) | max 1.15 m | max 1.15 m (unchanged) |

The 300 are no longer excluded — they are now `SEATED (unit)`, in
`unit:24` (184 resources) and `unit:26` (95), **`datum = "plate"`**, one
rigid delta each: **+0.6235 m** and **+0.6010 m**. They did not "seat per
body": they were caught by the SECOND anchor-family expansion,
`plate_keys` (`rebake_plan.py:98`, `in_plate_family` at :130/:232 — the
tunnel wall plate family of RULINGS 2026-09-05n-4, *"their whole anchor
family with them"*), which keys on the same `deck_signature.family_key`
anchor position. LEMD's wall-corridor objects sit on the pack's two
origin anchors, so the plate family is again all 300.

ARM 2 (measured, NOT landed — `plate_keys = set()`, LEMD `--patch-only`
287 s, seat replayed on the same mesh): writes drop 303 → 195, but the
survivors keep the SAME deltas (Terminal4 +0.623) and the 108 that leave
are not seated per body — they fall out as `below_grade` 4 → 105 /
`no_parts` 12 → 25 skips. The bar is not reached by that either.

THE RESIDUAL MECHANISM (attributed, needs a ruling — not this lane's to
decide): the re-seat's unit is a RIGID body with one delta, and at LEMD
only **113 of 29,076 parts** are ground parts, all near one elevation, so
the cluster's seat is +0.62 m while the objects themselves span 10.5 km
and 32 m of relief (`LEMD_OBJ-grass_FSX-LEMDgrass.obj` span 10,493 m,
−28.2 m; `Munoza-LEMD78.obj` span 3,241 m, −31.4 m). No rigid delta can
seat those; they are scatter files, not bodies. The candidates are 09q's
owed item (2) (per-placement resources) or a per-COMPONENT ground follow
(09d's `complete_component_deltas` currently gives every component its
nearest CARRIER's delta — the same +0.62 — rather than the ground under
itself). Both are owner/spawner intent.

## 10. RULINGS 2026-09-09s: the plate FAMILY expansion withdrawn; PER-COMPONENT GROUND SEATING (lane `v2lemdseats` round 2)

Two rules land together.

**(1) The plate family expansion is withdrawn (05n-4's "their whole
anchor family with them").** A tunnel-wall / basin plate seats **its own
object**: `plate_keys` (`rebake_plan.py:98`) covers the plate's own
placement ids only, and `emit/rebake.seat`'s `DATUM_PLATE` branch fixes
the members that CARRY a plate, never every member of the anchor
spelling. LEMD's pack anchors 300 placements at two origin points, so
the expansion re-made exactly the body 09q had just broken: two plate
units of 184 / 95 members, one rigid `+0.6235` / `+0.6010` m each over
32 m of relief. Deck families (`deck_family_seats_rigid`, R12-2) are
UNCHANGED — the withdrawal is the plate rule only.

**(2) Per-component ground seating.** The seat's ground reading moves
from ONE mesh sample under a part's plan centroid to the part's own
FEET — its lowest solid vertices within `[basin] contact_band_m` of the
component's own minimum, at most `[rebake] foot_samples_max`, spread by
farthest-point over the plan. A part's SEAT TARGET (the world elevation
of its object's `y = 0` plane that lands it on the mesh) becomes
`median over its feet of (mesh z at the foot − the foot's authored y)`;
with one foot at the centroid carrying `base_y` this is literally
today's `z − base_y`, so the CUT law, the facility rule, the A3 guard
and the pads keep their shape. GROUND is unchanged (`base_y ≤ elevated_base_m`);
the plan carries the verdict by carrying the feet only for the ground
parts, so the seat reads it straight off the plan and a 152 k-part plan
does not grow by an elevated part's feet.

REFUTED AND DELETED in the lane (the record, per BUILD ECONOMY): a
STRUCTURE-relative ground test — `base_y` within `elevated_base_m` of the
lowest `base_y` of the part's contact structure — was written to rescue
an Aerosoft terminal authored wholly at `y = 5.21`
(`LEMD_OBJ-Airport_Terminal4SAT_Yellow-LEMD23.obj`, 2,346 thick
components, 927 m span, ZERO ground parts today). It makes a FLOATING
disconnected part its own structure and therefore a ground part: the
twin `test_elevated_parts_inherit_the_supporter`'s sign, hanging over
nothing, seated itself on the ground instead of re-homing to the nearest
cluster (v1 I-8, spec §4.2b). Whole-file-elevated packs stay inheritors;
the scout's instrument excludes them too ("elevated base", 406 LEMD
placements), so the bar does not measure them. RESIDUAL, reported.

A cluster still seats as ONE (05q "a structure sunk uniformly lifts as
one", twin `test_a_structure_sunk_uniformly_lifts_as_one`) — the ruling's
own gloss is v1's `ground_under(structure) − ground_under(anchor)` **per
structure**, and a scatter file's buildings are each their own contact
structure, so each now lands on its own ground. The cut tolerance
(`cluster_seat_tolerance_m` 0.5 m) bounds what a shared cluster costs a
member's feet.

### Consumer census (owner ruling 30l): every reader of the part's ground reading, of `plate_keys` and of the plan's `Part`

| reader | reads | ruling under 09s |
|---|---|---|
| `airport/contact.placed_parts` | the placed component | GAINS `feet` — the component's lowest vertices in the frame with their AUTHORED y. Pure addition; `base_y`, centroid, boxes, areas unchanged, so the contact graph, the weld pass and the narrow phase are bit-identical |
| `airport/contact.partition` | the parts + the union-find | GAINS the ground-candidate cull: a part whose `base_y` exceeds its STRUCTURE's minimum by more than `elevated_base_m` carries no feet (the plan stays small: LEMD 9.1 k of 29.1 k parts, OTHH's 152 k parts likewise culled). The structure roots are already computed there — no second pass |
| `model.rebake.Part` / the plan JSON | the witness set | GAINS field 10, `feet` = `[[lat, lon, y], …]` (mm-rounded). `PLAN_VERSION` 5 → 6. A version-5 plan read through `--flat`-style promotion has no feet: every part then falls back to ONE foot at its centroid with `base_y`, which IS the pre-09s reading, so an old plan replays unchanged |
| `emit/clusters.seat_clusters` — `_P.z` | one mesh sample | REPLACED by `_P.target` over the feet. `target`, `lift`, the cut, `lifts[k]`, `grounds_of[k]`, the A3 guard and the pad residuals are all expressed in the same quantity, so their law text is unchanged. `ClusterSeat.ground_m` keeps its meaning (the median seat target = the median `y = 0` plane) — it is what `delta = ground_m − base` already subtracted |
| `emit/clusters` — the GROUND test | `base_y ≤ elevated_base_m` | REPLACED by "this part carries feet" (the plan's structure-relative verdict), with the flat rule as the fallback for a feet-less plan. Elevated parts still never vote and still inherit (v1 I-8) |
| `emit/clusters` — the flat-site `authored` override (08f (e)) | part id → the authored `y = 0` plane | UNCHANGED and takes precedence over the feet: an authored part's target IS its base, delta 0. Measured OTHH is the airport this protects |
| `emit/rebake.seat` `DATUM_PLATE` branch (line 478) | the unit's members | NARROWED to the members carrying `plate_y` (ruling (1)). Every other member of the unit falls to the cluster law, which is where 09q sent it |
| `emit/rebake._plate_reading` / `_deck_reading` / `_structure_seat` | member plates and deck rings | UNCHANGED — the plate and the deck seats stay PER OBJECT and rigid (ruling (3)); the per-component law is the cluster half only |
| `airport/rebake_plan.plan` `in_plate_family` (:130, :232) | `plate_keys` | NARROWED to `o.id in plates`: the `below_grade` and `no_parts` skips no longer spare a plate's anchor siblings. `counts["plate_families"]` is retired in favour of `counts["plate_members"]` (already present) |
| `airport/rigid.complete_component_deltas` (09d) | the seat's per-component deltas + `held` | UNCHANGED — a component the seat never considered (a thin plane, an elevated part in no cluster) still follows its NEAREST carrier. More components now carry a delta of their own, which is the point |
| `engine_v2._decision_from_seats` / `object_rebake.apply` | `MemberSeat.part_deltas` | UNCHANGED shape. A member whose parts fall in several clusters already wrote per-vertex deltas (06g); more of them now do |
| `tools/v2_rebake_replay.py` (`seat`, `bodies`) | the plan + the result | UNCHANGED code; `seat` promotes a version-4 plan already — a version-5 plan replays through the feet fallback |
| `tools/object_seating_report.py`, the app JSONL (`o4_engine/events.py`) | counts and v1 decision fields | UNCHANGED — no per-part field crosses either boundary |
| the census / `check_grade` / the oracle | the PATCH, never the pack | UNCHANGED — the re-seat writes OBJ8 vertex `y`, never a patch row |

### The twins re-scoped, with the reason

* `tests/auto_patch_v2/test_seat_clusters.py::test_plate_seat_holds_at_cluster_level`
  pinned "a tunnel wall object's plate seats its FAMILY on the ground at
  the band" — the anchor sibling `kerb` was asserted rigid with the
  plate at `−1.5`. RE-SCOPED by ruling (1): the plate member alone takes
  the plate delta and the kerb falls to the cluster law. The rest of the
  twin (the plate's own datum, the neighbour never founded by it, the
  distinct cluster ids) is unchanged and still asserted.

### §10.1 What it measured — and the two bars it does not reach

LEMD tile `v2lemdseats_LEMD3` (`--tile 40 -4`, 427 s wall, mesh 51.7 s;
the branch's earlier arm `v2lemdseats_LEMD2` at 531 s carried rule (1) +
the feet without the per-component delta), measured with the scout's
`measure5.py` / `analyze5.py` on the built mesh and the re-baked pack:

| |Δ| at the worst foot, measured `.obj` placements | 1.0.297 | 09q only (round 1) | this branch |
|---|---|---|---|
| placements measured | 870 | 870 | 805 |
| > 3 m | 184 | 185 | **122** |
| > 1 m | 195 | 194 | 126 |
| < 0.3 m | — | 502 (57.7 %) | 504 (62.6 %) |
| worst placement | `OldTerminal_FSX-LEMD38` +36.4 | +36.2 | +36.2 (now a plan SKIP, not a seat) |
| objects written | 26 | 303 | **196** |
| stranded components (`v2_rebake_replay bodies`) | — | 27,571 → 3 | 27,135 → **24** |
| LEMD v2 verify rows / census adjudicated | — | — | 496 / 338 (patch-side, untouched by the seat) |

BARS MISSED, with the residual attributed. `> 3 m → 0`: 122 stand.
`the worst 30 within 0.5 m at their feet`: 30/30 still over 10 m. By
mechanism, and NONE of them is the cluster seat:

* **76 — the MEMBER-level below-grade skip** (`rebake_plan.py:137`,
  `o.solid_min_depth_m ≤ −[basin] admission_depth_m` 2.5 m). 09s
  predicted this ("`below_grade` 4 → 105"): with the plate family gone,
  105 members are skipped whole because SOME component of the file lies
  ≥ 2.5 m under the local terrain — which is what a pack's flat authored
  plane does over 32 m of relief. This is 04i / 08-26's facility rule
  reading a SCATTER FILE as one body: the same error 09s (2) corrects
  inside the cluster seat, one pass earlier. It is not ruled, so the lane
  did not touch it. **Owner/spawner item: should the below-grade facility
  test be per COMPONENT (a clump 10 m under is a facility, its 1,500
  at-grade siblings are not)?** The cluster-level facility rule (05p) is
  already per-cluster and would carry it.
* **14 — wall-corridor members excluded by 09q (1)**: the terrain
  adapted to them; lawful, not a defect.
* **~6 — PLATE-datum members**: they seat their PLATE on the ground at
  the wall band (05n-4), so a foot instrument mis-reads them by
  construction. But LEMD's tunnel-object reader claims 13 plate members
  that are plainly not tunnel walls — `Terminal4_green-CNTRL.obj`
  (`plate_y` +9.27), `-Bus.obj` (−0.22), `Ground-FSX-LEMD36/37/85`
  (−7.05), `OldTerminal_FSX-P2CNX` (+5.21) — and the plate seat then
  stands them 12–17 m off their own feet. **Second owner/spawner item,
  upstream of the seat: the LEMD `tunnel_objects` reading.**
* **1 — `Munoza-LEMD64.obj`**, baked per component (−21.19 m on disk)
  with a foot still −22.4 m out: its remaining feet sit in clusters that
  STAYED.

OTHH plan replay (`build_airport.py OTHH --engine v2 --patch-only`, tag
`v2lemdseats_OTHH2`, 600 s; `v2_rebake_replay.py seat` on the owner's
`tile_OTHH_20260908T121758/Data+25+051.mesh`), against 09q's table:

| | 09q (round 1) | round-1 plan under this code (the feet FALLBACK) | this branch |
|---|---|---|---|
| resources written | **24** in 2 families | 22 in 2 | **23** in 3 |
| Dewatering Drainage | 16, +3.816 … +13.142 | 14, same range | 12, same range |
| tunnels | 8, −2.944 … +3.094 | 8, −2.283 … +5.392 | 8, −2.283 … +5.392 |
| Fire Fuel | — | — | 3, −1.130 |
| unit:28 (terminal deck, 193 members) | 0 (08f b/e) | 0 | 0 |

BAR MISSED (24, same deltas). Both moves are the ruling working: the
plate no longer carries its anchor siblings (Dewatering 16 → 12), and one
Fuel cluster's single measured ground part now reads its FEET, so its
lift is −1.130 m and crosses `min_delta_m` where the centroid reading
left it under. Nothing new is HELD and no family is newly written.

HECA offline replay (`v2_rebake_replay.py bodies` on the owner's plan and
rebake result in the shared repo): **15,716 stranded → 2** after the 09d
completion (bar ≤ 2, unchanged — the completion is a write-side rule this
ruling does not touch); top-5 spread −45.4 … −30.3 m, all
`Airport/Private_hall/*` at 30.11212, 31.41203.

Suite: 750 passed, 1 skipped (`tests/auto_patch_v2 tests/test_harness.py
tests/test_engine_v2_rebake.py`; 745 on the branch + the five 09s twins).

BUILD-TIME IMPACT: the seat's post-mesh half reads up to
`foot_samples_max` 4 mesh samples per GROUND part instead of 1 (LEMD
7,685 ground parts of 25,484; OTHH 15,802 of 139,065) and the plan grows
by their feet. Measured at the tile level: LEMD3 427 s vs LEMD2 531 s and
09q's 425 s — inside the ±25 % single-run noise floor, no phase attributed.

## 11. RULINGS 2026-09-09w: the below-grade test per COMPONENT, the tunnel object's WALL signature, the engine's own rebake glob (lane `v2lemdseats` round 3)

### 11.1 The three mechanisms

1. **THE BELOW-GRADE TEST IS PER COMPONENT** (09w (1)).
   `airport/obj8.read_placed_objects` records, per placement,
   `below_grade_comps` — the indices (into `ResourceCache.components`,
   the same deterministic partition `rebake_plan` enumerates) of the
   genuine solid components whose OWN rendered minimum stands
   `[basin] admission_depth_m` (2.5 m) or more under the ground at that
   component.  `solid_min_depth_m` (the deepest of them over the whole
   file) is no longer a skip on its own.  `airport/rebake_plan.plan`
   then: skips the placement whole only when EVERY genuine component is
   below grade (`counts["below_grade"]`, message unchanged), and
   otherwise drops just those components from the member's `comps`
   before the partition (`counts["below_grade_parts"]`) — their at-grade
   siblings seat normally.  The deck-family (`deck_family_seats_rigid`)
   and plate (05n-4) exemptions are unchanged and skip the filter
   entirely (a tunnel wall's skirt IS the tunnel).
2. **A CREST PLATE NEEDS A WALL UNDER IT** (09w (2)).
   `airport/tunnel_objects.signature` measures
   `_skirt_perimeter_fraction`: the share of the crest plate's PERIMETER
   — every ring of every plate polygon, sampled every `wall_sample_m`
   (2.0) — with a near-vertical solid face within
   `wall_face_max_thickness_m` (2.0) in plan whose top lies in the
   crest's band (`plate_bin_m`) and which descends by the depth that
   admitted the reading: `skirt_min_depth_m` under the SEAT for a full
   wall, `edge_wall_min_skirt_m` under the CREST for a shallow-seat edge
   wall (06f — the seat is the author's handle there).  Under
   `skirt_perimeter_min_fraction` (0.5, new law value) the reading is
   refused: `"roof, not a crest: skirt under {frac:.0%} of the
   perimeter …"`.
3. **THE ENGINE LOADS ITS OWN PLANS ONLY** (09w (3)).
   `auto_patch/engine_v2` globbed `o4_v2_rebake_*.json` in the patch
   directory and tried to read `tools/v2_rebake_replay.py`'s own
   `o4_v2_rebake_<ICAO>.seat.json` as a plan; the glob is now filtered
   by `_PLAN_NAME_RE` = `^o4_v2_rebake_(?!result_)[A-Za-z0-9]{2,8}\.json$`
   (`model.rebake.PLAN_FILENAME`'s shape).

### 11.2 Consumer census (owner ruling 30l): every reader of the below-grade reading, of the signature and of the plan glob

| Reader | What it reads | Ruled interaction |
|---|---|---|
| `airport/rebake_plan.plan:137` | `solid_min_depth_m`, `below_grade` | REPLACED by `below_grade_comps`: whole-placement skip only when every genuine component is deep; otherwise a per-component filter |
| `airport/rebake_plan.plan` (member loop) | `cache.components` | the same enumeration, minus `below_comps[o.id]`; `Part.comp` keeps the ORIGINAL index, so `emit/rebake`'s writer maps back unchanged |
| `airport/contact.partition` | the `(index, Component)` list | receives fewer components; contacts / pools / structures are computed over the at-grade parts only — which is the intent (a pit is not a contact of the building beside it) |
| `planar/basins.read_objects` → `pipeline/build` | `PlacedObject.below_grade`, `witnesses` | UNTOUCHED: the below-grade REGION (08-26's derived cut) is still the union of every witness footprint; only the re-seat's skip changed |
| `airport/deck_signature.promote/classify` | `below_grade`, `deck_kind` | untouched (the promote path runs before the skip and is exempt from it) |
| `airport/obj8.ObjReport` (`no_floor`, `through_grade`, `rim_protrusions`, `buried_components`) | the same loop | unchanged: `below_grade_comps` is recorded BEFORE the existing `continue`s, and no existing counter moved |
| `airport/tunnel_objects.read_corridors` | `signature()` | the only consumer; a refused resource is reported by name in `TunnelObjectStats.refused` (the new message does not match the four suppressed prefixes) |
| `planar/sunken_roads`, `planar/door_ramps` | their own readers | never call `signature()`; unaffected |
| `pipeline/build._plate_seats` | `pm.structures` (`source == "object"`) and `pm.basins` | unchanged — and see §11.4: at LEMD 12 of the 13 plate members come from the BASIN half, not from `signature()` |
| `auto_patch/engine_v2._run_rebake` | the patch dir's plan files | narrowed; `REBAKE_RESULT_FILENAME` and `tools/v2_rebake_replay.py` outputs are excluded by name |

### 11.3 Twins (`tests/auto_patch_v2/test_v2lemdseats.py`)

* `test_the_below_grade_skip_is_per_component` — one resource with a
  6 m-deep clump and two buildings 500 m away: `below_grade` 0,
  `below_grade_parts` 1, two parts planned, the two buildings seated on
  their own ground (+5 / +10 m on the 1 % sampler).
* `test_a_placement_below_grade_THROUGHOUT_is_still_skipped_whole` —
  every genuine component deep ⇒ the 08-26 facility rule as before.
* `test_a_crest_plate_needs_a_wall_under_its_perimeter` — a box wall
  reads 100 % and is admitted; the same tessellated plate over a skirt
  under a fifth of its ring is refused by name; the same plate with the
  skirt all the way round is admitted again.
* `test_the_perimeter_fraction_is_a_law_value`,
  `test_the_engine_loads_only_its_own_rebake_plans`.

### 11.4 THE 13 LEMD PLATE MEMBERS ARE NOT THE TUNNEL READER'S (attribution correction to §10.1)

Round 2 attributed ~6 of the 122 to "LEMD's `tunnel_objects` reader
claims 13 plate members that are not tunnel walls".  Measured on the
round-2 build's own artefacts (`Patches/+40-010/+40-004/
o4_v2_rebake_LEMD.json` and `LEMD_auto.patch.osm.axes.json`):

* the patch sidecar's `tunnel_objects` list holds **17** records, of
  which exactly **one** is a wall object — `tunnel-object:Bridge4.obj@0`
  (the 06f edge wall on LEMD's real bore, `plate_y_m` 2.016); the other
  16 are `wall_corridor` records (`plate_y_m` 0.0);
* the other **12** plate members reach `rebake_plan` through
  `pipeline/build._plate_seats`'s BASIN half (`[basin] seat =
  "floor_plate"`, RULINGS 06b (3)): every one of their `plate_y` values
  is a basin's `plate_y_m` verbatim — `Ground-FSX-LEMD36/37/85` −7.048
  (the T4S basin, floor 588.95), `OldTerminal_FSX-P2CNX` +5.206,
  `-DCNEUN` +4.336, `Cargo-CNTRL` −1.666, `Terminal4_green-LEMD02`
  −0.497, `-LEMD41` −0.470, `-LEMD54` −0.671.

So mechanism (2) cannot refuse them: they never pass through
`signature()`.  Measured directly on the authored files (the pack's
`.anchor_bak`, restore-before-read), with the law as shipped:

| resource | before 09w (2) | skirt under the perimeter | after |
|---|---|---|---|
| OTHH `tunnel*` ×8 | admitted | **100 %** (3.0 m under the seat) | admitted |
| LEMD `Bridge4.obj` | admitted (edge wall) | **100 %** (1.5 m under the crest) | admitted |
| LEMD `Ground-FSX-LEMD37` | admitted (full skirt 7.05) | **0 %** | REFUSED |
| LEMD `Ground-FSX-LEMD85` | admitted (edge, floor −7.03) | **0 %** | REFUSED |
| LEMD `OldTerminal_FSX-LEMD54` | admitted (edge, crest +18.22) | **0 %** | REFUSED |
| LEMD `Terminal4_green-CNTRL` | admitted (edge, crest +13.70) | 100 % | admitted |
| LEMD `OldTerminal_FSX-LEMD41` | admitted (edge, crest +18.96) | 100 % | admitted |
| LEMD `OldTerminal_FSX-LEMD43` | admitted (edge, crest +4.19) | 65 % | admitted |
| LEMD `Cargo-CNTRL`, `-Bus`, `LEMD02`, `Ground-FSX-LEMD36`, `P2CNX` | already refused (no skirt / a stub / roofed along the axis) | — | refused |

DEVIATION, reported not decided.  The three survivors are shallow-seat
EDGE WALLS (06f) whose facades genuinely descend `edge_wall_min_skirt_m`
under their own roof, so no perimeter fraction separates them from
`Bridge4`.  What separates them is the CREST HEIGHT: 06c caps a full
wall's edge-wall crest at `edge_wall_max_plate_m` (2.0 m) but 06f's
shallow-skirt branch has NO cap at all, which is how a roof at +18.96 m
reads as an edge wall.  A cap cannot simply be extended: `Bridge4`'s
crest is +2.016 m, over `edge_wall_max_plate_m` itself.  Left for the
owner/spawner with the second item: **should the PLATE SEAT of a BASIN
member be the target instead** (that is where the 12 came from, and the
seat then stands them 12–17 m off their own feet)?

### §11.5 What round 3 measured — and why the below-grade test needed a WITNESS

THE LEMD TILE COULD NOT BE BUILT AT THIS HEAD.  `build_airport.py LEMD
--engine v2 --tile 40 -4` (tag `v2lemdseats_LEMD4`) reached step 2 and
Triangle4XP failed at every angle constraint —
`segmentintersection(): Topological inconsistency after splitting a
segment`, the subsegment at (0.2651, 0.2869) of tile +40−004, i.e. at
**LEGT** (Getafe), 20 km from LEMD.  Not this lane's geometry: LEGT
carries 0 tunnel objects, 0 basins and 365 placements, ALL stock — its
re-seat plan is empty, so none of the three mechanisms can change a byte
of its patch.  It is the 09t/09u bank-and-water emit that lane
`v2bankblend` holds.  Everything below is therefore measured OFFLINE:
one patch-only build per airport for the plan, and round 2's own tile
mesh (`/tmp/harness/tile_v2lemdseats_LEMD3/Data+40-004.mesh`, 18:30) for
every seat — the same terrain under every arm, so the seat is the only
variable.

THE INSTRUMENT (`scratchpad/lemdseats/r3/measure6.py`, a promotion
candidate — see the owed list): the residual at every placement's feet
computed from the AUTHORED pack + a seat result's per-component deltas +
one mesh, so two arms compare without writing a pack.  It reads 873
placements where the scout's `measure5` (the live baked pack) read
805–873; the round-2 column below is that instrument's reading of round
2's own result, NOT §10.1's 122.

| LEMD, one mesh, one instrument | round 2 (`…result_LEMD.json`) | ARM A (09w (1) as ruled) | ARM B (shipped) |
|---|---|---|---|
| \|Δ\| > 3 m | 106 | **148** | **34** |
| \|Δ\| < 0.3 m | 62.2 % | 59.9 % | **66.0 %** |
| worst | 36.84 | 36.24 | 19.15 |
| plan `below_grade` (files skipped whole) | 105 | 94 | **0** |
| plan `below_grade_parts` | — | 2,935 | **55** |
| plan `parts` | 25,484 | 14,655 | 29,344 |
| resources written | 196 | 200 | **290** |
| stranded after the rigid completion (`bodies`) | 24 | **952** | 111 |

ARM A is the ruling applied literally, and it makes LEMD worse.  The
attribution, measured on the round-3 plan against the patch sidecar:
**of the 91 resources the depth test skipped, 91 carry NO floor witness
at all** (the sidecar records 12 resources with a real basin, and not one
of them is in the skipped set).  They are under the local DEM because
Aerosoft authored the whole pack on ONE flat plane over 32 m of relief —
the `deep` test is reading the PACK'S DATUM, not a basement.  Per
component that gets worse, not better: the deep components are dropped
from the plan, so the file is baked with some components moved and the
rest left where they were — 952 stranded components, a sheared model.

ARM B keeps 09w (1) exactly — the test is per component, the siblings
seat — and adds the qualifier the ruling's own parenthesis states, "(a
basin/tunnel witness)": the test applies only inside a placement that
carries a FLOOR WITNESS.  With no witness anywhere the placement is not a
facility and nothing of it is dropped.  08-26's facility rule is
untouched where it applies (a pit, OTHH's Drainage bowls, OTHH's
`TerminalRoads_03_005` with its 84 witnesses).  **This is a DEVIATION
from the ruled wording and is reported, not decided** — it deletes the
witness-less `deep` skip that 04i added.

CONTROLS (both arms identical unless stated):

* OTHH (`v2lemdseats_OTHH3` arm A 490 s, `v2lemdseats_OTHH4` arm B
  489 s; seat replayed on the owner's `Data+25+051.mesh`): **25 resources
  written in 3 families** — Dewatering Drainage 14 (+3.816 … +13.142),
  tunnels 8 (−2.944 … +3.094), Fire Fuel 3 (−1.130) — identical under
  both arms.  Round 2 read 23 (Dewatering 12); the +2 is NOT separable
  from main's `v2water` merge (09u changed OTHH's flat-site datum and
  water) without an arm this lane did not spend.  Verify rows 45 both.
* HECA (`v2lemdseats_HECA1`, 195 s; owner's `Data+30+031.mesh`):
  stranded 15,716 → **2** after the completion (bar ≤ 2, unchanged), 392
  resources in 8 families.
* LEMD census (`v2lemdseats_LEMD5.osm`, `--no-cache`): law-true 12,357,
  of which 12,048 are the 05aa withdrawn-law taxi chord rows; v2 verify
  400 rows (round 2: 496 / 338 — the patch side is main's, not the
  seat's).

BARS: `> 3 m ≤ 14` MISSED (34 on this instrument); `stranded ≤ 2` MISSED
at LEMD (111 — all of them FLAT components of the 94 newly-written files,
the 09b (5) class) and MET at HECA (2).  The worst 30 are no longer a
single mechanism: 14 are `Terminal4_*` / `Cargo-*` members whose plate or
cluster seat stands them 4–19 m off the feet the instrument reads, 2 are
09q's lawful terrain-adapted members, and 3 are the `Bridge1/2/3` decks
(seated at their deck top by construction).

BUILD-TIME IMPACT: the plan grows (LEMD parts 25,484 → 29,344, members
208 → 300) because 91 files re-enter the seat; LEMD patch-only 421 s and
OTHH patch-only 489/490 s are both inside the ±25 % single-run noise
floor against round 2's 425–531 s LEMD tiles and 600 s OTHH.  No phase
attributed.

## 12. RULINGS 2026-09-09z (4) + 2026-09-09ac (2)/(3): the carrier by CONTACT, the basin plate seat SCOPED, the census promoted (lane `v2planes`)

### 12.1 The two mechanisms

**(1) THE CARRIER IS THE COMPONENT THE PLANE TOUCHES.** §7's rule gave a
free component the NEAREST considered component's delta. The owner's
read (09z (4)) is that a plane always follows ITS OWN walls, held or
not — never "a panel at a different height from the walls that carry
it". So the carrier is now the considered component the free geometry
is IN CONTACT with, and, where several touch, the one it touches MOST:

* THE CONTACT TEST, and its cost. Contact = a carrier vertex within
  `emit.identity.min_distinct_spacing_m` (0.5 m — the identity spacing:
  two points closer than it are the SAME point to every emit law) of
  one of the free component's own vertices. `solid_components` welds by
  ROUNDED POSITION, so a genuinely SHARED vertex is contact at distance
  0 and needs no separate test — and two distinct components can never
  share one (they would be one component), which is why the pair list
  stays short. The measure of "most" is the number of the free
  component's OWN vertices in contact with that carrier; ties by lowest
  component index, so the write stays deterministic. Cost: one extra
  `cKDTree.sparse_distance_matrix` over the free vertices already
  gathered for the k=1 query, plus an `np.unique` per component — one
  C-level call for the whole file (measured with the k=1 query it sits
  beside: 0.2 s over HECA's 15.7 k free components; the pair pass adds
  under 0.1 s of that order). A per-component `query_ball_point` loop
  was rejected for the same reason §7 rejected per-component queries.
* Bounding-box contact was NOT used, though 09z (4) admits it: inside a
  dense placement the walls' boxes enclose the plane's box, so a box
  test makes everything touch everything and the "most contact" ranking
  becomes meaningless. Vertex proximity within the identity spacing is
  the strictly narrower reading of the same ruling and subsumes shared
  vertices.
* HELD CARRIERS ARE UNCHANGED and now bind harder: a plane whose
  TOUCHING carrier is held is held with it (§7's rule already did this
  for the nearest carrier; the contact test makes it the RIGHT carrier).
* The law value is the CALLER's: `airport/rigid.py` takes
  `contact_tol_m` and holds no number (twin
  `test_the_contact_tolerance_is_the_identity_spacing`);
  `contact_tol_m = 0.0` is the pre-09z pure-nearest rule.

**(2) THE BASIN PLATE SEAT IS THE BASIN'S OWN WITNESS RESOURCE'S.**
§11.4 attributed 12 of LEMD's 13 "plate" members to `_plate_seats`'
BASIN half: `[basin] seat = "floor_plate"` handed EVERY `member_ids`
entry the DEEPEST member's `plate_y_m`, so a terminal slab that merely
shares that plate y was seated onto a floor it never had (12–17 m off
its own feet). 09ac (2): only the object whose floor plate the basin
CUT takes the plate seat. `planar/basins.build_basins` already computes
that object — `deepest`, the member with the minimum `solid_min_z`,
the one `plate_y_m`, `anchor_inside_floor` and `seat_expect_m` are all
read from — but recorded only its PATH set; it now records its
placement id in the new field **`Basin.witness_id`**, at the same site
`plate_y_m` is computed, so the two can never name different objects
(twin `test_the_witness_is_the_deepest_member_the_plate_y_was_read_from`).
Every other member seats by its FEET like any other resource.

**(3) `tools/seat_feet_census.py`** — the `v2lemdseats` lane's
`measure6.py` promoted on its third use, with an index row and twins.

### 12.2 Consumer census (owner ruling 30l): every reader of the carrier rule and of the basin's members

| Reader | What it reads | Ruled interaction |
|---|---|---|
| `airport/rigid.complete_component_deltas` | the components + the seat's deltas | THE CHANGE. New optional `contact_tol_m`; the return shape (`{component: delta}`, held components absent) is unchanged, so every downstream reader in §8 is unchanged |
| `auto_patch/engine_v2._decision_from_seats` (the WRITE half) | the completed map → the per-vertex map | passes `law.tables.emit.identity.min_distinct_spacing_m` (twin `test_the_engine_passes_the_identity_spacing_as_the_contact_tolerance`: no literal, no reliance on the default). Its seat NOTE is amended ("follow the carrier they touch") |
| `object_rebake.apply` VT rewrite / `_positional_command_rewrite_plan` / `_reconcile_animation_blocks` / the provenance range | the per-vertex map | UNCHANGED in shape and in coverage — the same components get a delta, some get a DIFFERENT one. §8's rows stand |
| `tools/v2_rebake_replay.py bodies` | the same function | gains `--contact` (default 0.5 = the identity spacing; `0` replays the pre-09z rule), so the two arms are comparable offline without a build |
| `emit/rebake.seat`, `emit/clusters.seat_clusters`, `airport/contact.partition`, the witness gate | genuine PARTS only | UNCHANGED by ruling: a thin plane still never votes, never founds a seat, never joins a cluster. The completion is a WRITE-side rule over components the plan never made parts of |
| the plan / result JSON, the app's JSONL (`o4_engine/events.py` → `OrthoEngineClient.swift`) | counts and part deltas | no new field crosses either — the follower is derived from the authored OBJ8 at write time |
| `pipeline/build._plate_seats` (BASIN half) | `pm.basins` | THE CHANGE: `b.witness_id` instead of `b.member_ids`. The TUNNEL half (`tn.objects`, 05n-4/06c) is untouched — `Bridge4` and OTHH's 8 tunnels still plate-seat |
| `airport/rebake_plan.plan` (`tunnel_objects` → `plates`, `in_plate_family`, `plate_paths`, `counts["plate_members"]`) | the plate MAP by id | UNCHANGED code; the map is smaller. A member no longer in it is no longer exempt from the multi-anchor / thickness rules — which is the point: it seats by its feet, per body, like its neighbours |
| `emit/rebake._plate_reading` | a member's `plate_y` / `plate_stations` | UNCHANGED — it reads whatever the plan carries |
| `pipeline/build`'s `excluded` set and `below_grade=[(region, b.objects)]` | `b.objects` (PATHS) | UNCHANGED — the basin's below-grade REGION and the `seat = "floor_plate"` non-exclusion still cover EVERY member. Only the plate SEAT narrowed; nothing is newly excluded or newly cut |
| `pipeline/publication.py` (the sidecar's `basins` records) | `member_ids`, `plate_y_m` | `witness_id` ADDED beside them (additive key; every existing reader keyed by name is unaffected), so an offline read can tell the witness from the other members |
| `pipeline/build.py:385` (the basin report line) | `plate_y_m`, `anchor_ll` | UNCHANGED text; the value it prints is still the witness's |
| `model/structures.Basin` positional construction | field ORDER | the only constructor is `planar/basins.build_basins` (grepped): `witness_id` inserted after `plate_y_m` and the call updated in the same commit. No pickled/serialised Basin exists — the sidecar is written by name |
| `tests/auto_patch_v2/test_v2othh3.py::test_basin_family_seats_its_floor_plate_on_the_trench_floor` | `for oid in b.member_ids: assert oid in seats` | RE-SCOPED to `b.witness_id` — the assertion was the family-wide rule 09ac (2) withdraws |
| `airport/door_wells.py`, `planar/structures.py` (`plate_y_min/max`, `TunnelStructure.plate_y_m`) | their OWN plate fields | unrelated names; never read `Basin` |

### 12.3 Twins (`tests/auto_patch_v2/test_v2planes.py`, 16)

* `test_a_plane_follows_the_wall_it_shares_more_vertices_with` — a
  tessellated floor plane between a full-length wall 0.10 m off its
  near edge (5 contacts) and a stub 0.05 m off its far edge (1): the
  pre-09z rule returns the STUB's delta, the contact rule the wall's.
* `test_a_canopy_that_touches_nothing_falls_back_to_the_nearest` — a
  plane 30 m from one wall and 60 m from another takes the nearest, and
  agrees with the pre-09z answer.
* `test_a_plane_over_held_walls_stays_with_them` — the plane touches
  only the HELD wall while a moving wall stands 20 m away: no delta.
* `test_the_contact_winner_is_deterministic_on_a_tie`,
  `test_contact_zero_keeps_the_pre_09z_rule`,
  `test_the_contact_tolerance_is_the_identity_spacing`,
  `test_the_engine_passes_the_identity_spacing_as_the_contact_tolerance`.
* `test_only_the_basins_own_witness_takes_the_plate_seat` — two members
  at one `plate_y`, one of them the witness: only it is in the plate
  map, and the other is still a MEMBER of the region.
* `test_a_basin_with_no_witness_plate_seats_nothing`,
  `test_the_witness_is_the_deepest_member_the_plate_y_was_read_from`,
  `test_the_witness_reaches_the_sidecar`.
* Five for the promoted census: the arithmetic at the feet (a 4 m wall
  on flat ground reads 0; +2 m of delta reads −2), restore-before-read
  (`.anchor_bak` wins over a baked live file), both spellings of the
  seat record (a `None` part delta is not a delta; a plate unit's delta
  stands in), that DSFTool is never RUN, and the index row.

### 12.4 What it measured

**THE OWNER'S SITE FIRST — LEMD, one tile build**
(`build_airport.py LEMD --engine v2 --tile 40 -4`, tag `v2planes_LEMD1`,
**rc 0**, wall 529.5 s, step 2 mesh 51.7 s): the 09ac §11.5 Triangle
failure at LEGT is GONE at this head (the `v2bankblend` round-3 merge,
09ab) — the tile that could not be built in round 3 builds, so every
number below is this build's own plan, result and mesh, not a replay of
an older one. The re-seat wrote 289 objects (2,311,616 vertices, 193
with several deltas, 2 reverted).

`tools/seat_feet_census.py` on that mesh (873 measured placements of
3,021 OBJ placements):

| |Δ| | n | % |
|---|---|---|
| < 0.3 m | 568 | 65.1 % |
| 0.3–1 m | 233 | 26.7 % |
| 1–3 m | 41 | 4.7 % |
| **> 3 m** | **31** | 3.6 % |

By class: SEATED n=204 (29 over 3 m, max 19.26), terrain-adapted n=2
(both over 3 m, 09q's lawful members), multi-anchor n=666 (**0** over
3 m, max 1.35), not in plan n=1.

**BAR `> 3 m ≤ 14`: MISSED at 31** (round 3 read 34 on its own mesh —
the two are not the same measurement frame, so read 31 as this build's
number, not as a −3). Of the 31: **8 are PLATE-seated members**, 21 are
other seated members whose CLUSTER seat stands them off the feet the
instrument reads, and 2 are 09q's terrain-adapted members. The three
`Bridge2/3/4` rows (3.9–4.3 m) are deck-top seats by construction.

**BAR `stranded ≤ 2`: MISSED at LEMD (167), MET at HECA (2).** And the
count is now, by construction, the count of planes LAWFULLY HELD: a free
component is absent from the completion's output only when the carrier
it touches (or, failing contact, its nearest) is a HELD component — 09z
(4)'s "if the carrier is held the plane is held with it". All 167 are
that class; the contact rule cannot reduce them, because reducing them
would mean moving a plane off the wall that carries it. `bodies` at
`--contact 0` and `--contact 0.5` return the same 167 (and the same
2 at HECA): the stranded count is INSENSITIVE to this ruling, so it is
no longer the instrument for it.

**The interventional measurement of the carrier rule** (the same plan
and result, `contact_tol_m` 0.0 vs 0.5 — the only thing that changes):

| airport | free components | take a DIFFERENT carrier | files | worst change |
|---|---|---|---|---|
| LEMD (`v2planes_LEMD1`) | 27,759 | **424** | 10 | 9.36 m (`Terminal4SAT_Yellow-LEMD11`, 175 components) |
| HECA (round-3 arm, replayed) | 15,716 | **327** | 27 | 8.46 m (`T23/Plastic.obj`, 7 components) |

So the ruling moves 424 LEMD and 327 HECA panels onto the walls that
actually carry them, by up to 9 m — the class the owner read at HECA's
Private Hall.

**OTHH is UNCHANGED** (`v2_rebake_replay.py seat` on the round-3 plan
and the owner's own `zOrtho4XP_+25+051/Data+25+051.mesh`): 25 resources
written in 3 families, `Dewatering Drainage` 14 files +3.816 … +13.142,
`tunnels` 8 files −2.944 … +3.094, `Fire Fuel` 3 files −1.130 — byte
for byte the §11.5 reading.

**THE BASIN SCOPE REMOVED TWO OF THE TWELVE — the other ten ARE their
basins' witnesses** (measured deviation, reported not decided). LEMD's
plate members go 13 → **11**: `Ground-FSX-LEMD36` and `Ground-FSX-LEMD85`
lose the plate seat (they shared another basin's `plate_y_m`), and
`Bridge4` plus **10 basin witnesses** keep it — `Terminal4_green-CNTRL`
+9.266, `-Bus` −0.218, `-LEMD02` −0.497, `Cargo-CNTRL` −1.666,
`OldTerminal_FSX-P2CNX` +5.206, `-DCNEUN` +4.336, `-LEMD41` −0.470,
`-LEMD43` −0.661, `-LEMD54` −0.671, `Ground-FSX-LEMD37` −7.048. Five of
those ten are still in the worst 30 (16.71, 16.65, 16.08, 13.21,
11.68 m). §11.4's attribution said the basin reader "admits terminal
geometry at LEMD as basin floors" — 09ac (2) rules the SEAT's scope, and
this measurement shows the residual is upstream of it: those slabs are
each the DEEPEST genuine solid of their own admitted basin region, so
scoping the seat to the witness cannot reach them. What would is the
basin ADMISSION test (does a terminal slab over 32 m of Aerosoft datum
relief found a basin at all?). OWED, for the owner/spawner.

BUILD-TIME: the tile is 529.5 s wall against round 2's 425–531 s LEMD
tiles — inside the ±25 % single-run noise floor, and not a timing run
(a `--base-arm` LEMD patch-only build was running concurrently). Neither
mechanism adds a pass: the contact test is one extra C-level pair query
per written OBJ8 inside the post-mesh re-seat, and the plate map is
SMALLER.

## 13. RULINGS 2026-09-09ag: the basin ADMISSION test — an authored sunken solid, never a datum sitting under the terrain (lane `v2basin`)

### 13.1 Attribution: which admission clause let a terminal slab in

Measured OFFLINE on the LEMD and OTHH structure stages at main `858a6836`
(`auto_patch_v2.planar` reader + `build_basins`, shared corpus, production
DEM frame; LEMD cross-checked against `v2planes_LEMD1`'s 33
`basin_facilities`): LEMD admits **34** basins from **11** witness
resources, OTHH **10** from its Drainage / Dewatering shells.

THE CLAUSE IS RULE 1's LOCAL GROUND. `obj8.read_placed_objects` takes a
component's ground as `dem_z` at its plan CENTROID and gates the floor at
`plate ≤ local − admission_depth_m` (2.5 m). Aerosoft authored LEMD as
ONE flat plane; where the terrain stands above it an ordinary ground-floor
slab — own authored `y` **−0.5 m** — reads 15 m "under the local ground"
and witnesses a pit. Nothing downstream refuses it: the plate is genuine,
the shell tops out in the band, and the region is the slab's own
footprint, whose boundary is where the slab meets the ground — so the rim
diagnostic reads CLOSED.

`D_ground` = R_est − floor (depth under grade); `D_datum` = −`plate_y`
(depth the object AUTHORED under its own render datum); the balance is the
datum lying under the terrain.

| witness | basins | D_ground | D_datum | datum under grade | ring relief | rim open |
|---|---|---|---|---|---|---|
| OTHH `Drainage_01..06` | 8 | 3.81–4.20 | 3.82–4.20 | **0.00** | 0.00 | 0 of 6–79 |
| OTHH `Dewatering_01/02` | 2 | 13.14 | 13.14 | **0.00** | 0.00 | 2 of 46 |
| LEMD `Ground-FSX-LEMD37` | 1 | 7.07 | 7.05 | **0.02** | 7.10 | 57 of 69 |
| LEMD `OldTerminal-LEMD54` | 2 | 4.24 | 0.67 | 3.57 | 0.66–1.02 | 1 of 4 |
| LEMD `OldTerminal-LEMD41` | 1 | 6.47 | 0.47 | 6.00 | 0.98 | 27 of 61 |
| LEMD `OldTerminal-LEMD43` | 9 | 6.66 | 0.66 | 6.00 | 0.00 | 1–2 of 4 |
| LEMD `Cargo-CNTRL` | 1 | 11.67 | 1.67 | 10.00 | 1.31 | 26 of 34 |
| LEMD `OldTerminal-STRT1` | 1 | 11.44 | 1.44 | 10.00 | 3.96 | 25 of 36 |
| LEMD `OldTerminal-P2CNX` | 1 | 4.79 | **−5.21** | 10.00 | 0.00 | 0 of 7 |
| LEMD `OldTerminal-DCNEUN` | 1 | 5.98 | **−4.34** | 10.32 | 2.34 | 6 of 7 |
| LEMD `Terminal4_green-LEMD02` | 9 | 15.50 | 0.50 | 15.00 | 0.00–0.24 | 1 of 4 |
| LEMD `Terminal4_green-CNTRL` | 7 | 5.73 | **−9.27** | 15.00 | 0.00 | 0 of 4 |
| LEMD `Terminal4_green-Bus` | 1 | 16.30 | 0.22 | 16.08 | 0.15 | 0 of 4 |

* The separation is TOTAL and it is the DATUM, not the shape: every OTHH
  pit authors its floor the full depth (ratio 1.00); every LEMD slab but
  `LEMD37` authors 0.2–1.7 m and borrows 3.6–16.1 m from a datum under the
  terrain. Four author their "floor" ABOVE their own datum (`plate_y`
  +4.34 … +9.27) and still found a pit.
* ENCLOSURE IS REFUTED as the discriminator: it refuses LEMD's genuine
  `LEMD37` (57 of 69 open, the most open region at either airport) and
  admits every `LEMD02` / `CNTRL` sliver (0–2 of 4).
* RELIEF-vs-THICKNESS (the brief's first reading) is refuted as
  sufficient: it refuses 7 of 11 and admits `LEMD02`, `Cargo-CNTRL`,
  `DCNEUN`, `Bus`, whose regions sit on plateaus with 0.0–2.0 m of relief.
  The relief is under the OBJECT; the region is where the test must bite.

`LEMD37` STAYS ADMITTED: the Aerosoft ground truth of record (floor 588.95
against G = 596.02), an authored 7 m basin.

### 13.2 The test

A basin is a SUNKEN SOLID: its depth is AUTHORED. A component witnesses
only when its floor stands `[basin] authored_depth_min_m` under the
placement's OWN render datum (`anchor_z + agl`) as well as
`admission_depth_m` under the local ground. Applied at rule 1's SINGLE
DERIVATION SITE — the witness, in `airport/obj8.read_placed_objects`,
where the component's ground and the placement's datum are both in hand —
so a datum-relief slab never founds a region, never becomes a
`below_grade_comps` part for the seat skip to read, and never takes a
plate seat: it seats by its feet like its neighbours (09ag "object to the
terrain"). Refused by resource with its authored depth. `authored_depth_
min_m = 2.5` = `admission_depth_m`: rule 1's own floor gate, measured
against the object's datum instead of the terrain.

REFUTED, measured, on the way here: an ABSOLUTE cap on how far the datum
may stand under the ground (`datum_drop_max_m = 1.0 = contact_band_m`).
It separates LEMD's slabs from OTHH's pits perfectly at the BASIN level,
but at the witness it refuses OTHH's 8 tunnel objects — whose datum
stands 3.00–8.00 m under the ground and whose floors are authored 15.0 m
down. The authored depth is the invariant; the datum's drop is not.

Also refuted, at the basin level (the first arm, spec commit `645dfdde`):
refusing the REGION instead of the witness. LEMD 34 → 1 as intended, but
the 33 objects then fell into the per-component below-grade seat SKIP
(09w (1)) — plan `below_grade` 3 → 8 — and kept their authored y instead
of seating: census > 3 m 11 → 22, five ex-basin resources at 10.7–16.5 m
(`LEMD02` 16.46, `Bus` 15.63, `Terminal4_green-CNTRL` 15.41,
`Cargo-CNTRL` 10.66 ×2). A skip is the opposite of "object to the
terrain", which is why 5b belongs at the witness.

### 13.3 What it measured

**THE INTERVENTIONAL ARM, on the real packs** (one airport load,
`authored_depth_min_m` 0.0 vs 2.5 the ONLY thing that changes —
`scratchpad/v2basin/witdiff.py`):

| airport | below-grade objects | placements that LOSE a witness |
|---|---|---|
| **OTHH** | 15 → **15** | **0** |
| LEMD | 11 → 5 | 6 (`Cargo-CNTRL` ×2, `OldTerminal-LEMD43`, `-STRT1`, `Terminal4_green-Bus`, `-LEMD02`) |

OTHH cannot change: no placement loses a witness, so no below-grade part,
no region, no plate member and no plan row differs — the `Dewatering
Drainage` 14 / `tunnels` 8 / `Fire Fuel` 3 families are untouched by
construction, which is a stronger reading than a replay against a stale
plan. Its 10 basins are byte-identical (same floors, witnesses, areas).

**LEMD** (patch-only builds, `v2basin_LEMDbase` → `v2basin_LEMD3`):
basins **34 → 1** (`Ground-FSX-LEMD37`'s 27,657 m² Aerosoft basin, the
ground truth of record); rebake plan `plate_members` **11 → 2**
(`Bridge4` + that basin's witness), `below_grade` 3 → 2.

`tools/seat_feet_census.py`, both arms on ONE fixed terrain
(`Tiles/zOrtho4XP_+40-004/Data+40-004.mesh`, the main tree's; the tool's
own frame for comparing two seat arms without a build between them):

| arm | < 0.3 m | 0.3–1 | 1–3 | **> 3 m** | plate members | below-grade skips |
|---|---|---|---|---|---|---|
| base `v2basin_LEMDbase` | 623 | 212 | 27 | 11 | 11 | 0 |
| region-refusal (refuted) | 616 | 207 | 28 | **22** | 2 | 5 (10.7–16.5 m) |
| **`v2basin_LEMD3`** | 621 | 208 | 30 | **14** | **2** | **0** |

**BAR `> 3 m ≤ 14`: MET at 14.** No plate-seated terminal slab and no
below-grade skip remains in the worst 30; the worst rows are the two
`LEMDzaun` fence files (17.02 / 12.23), `Bridge1/2/3/4` deck-top seats by
construction (3.80–10.37), 09q's two terrain-adapted members (7.40 /
7.19) and three Cargo files at 3.75–4.03 that were previously
basin-excluded and now seat by their feet.

FRAME, reported not decided: this mesh was built on 2026-08-27 and is
NOT either arm's own terrain, so the absolute counts are not comparable
with `v2planes_LEMD1`'s 31 (measured on its own tile mesh). What the
table reads is the A/B of the seat on one terrain — which is what the
instrument is for — and the base arm's 11 flatters it, because a plate
seat's residual is measured against a trench this mesh does not contain.
The acceptance reading needs a LEMD TILE build, which this lane's brief
excluded.

Patch body `2813025073b8` for all three post-fix arms (the geometry is
identical; only the rebake plan moves). Build 332.4 s.

## 14. RULINGS 2026-09-10i: ONE TOUCHING BODY, ONE DELTA — no cut inside a placement, feet across the body (lane `v2rigid`)

Measured on the owner's 1.0.300 LEMD (plan `o4_v2_rebake_LEMD.json`, result
`o4_v2_rebake_result_LEMD.json`, mesh `Data+40-004.mesh`): 23,371 contact edges,
**13,979 of them INSIDE one authored placement**; 929 cut; 200 of 288 written
members carry several deltas; 12,057 pairs of one OBJ8 within 2 m with different
deltas, 85 sites over 2 m; 86 of the 185 clusters wider than 200 m decided by ONE
measured foot (k1: 4,202 parts, ⌀982 m, −6.507 against neighbours +2.8).

### 14.1 The four rules

1. **NO CUT INSIDE A PLACEMENT.** The `cluster_seat_tolerance_m` cut applies only
   to a ground-to-ground contact edge whose two parts belong to DIFFERENT members
   (`(unit, member)` — one authored placement). An intra-placement edge is never
   cut: two components of one placement that touch are ONE BODY with ONE delta.
   The knob is KEPT (it still governs the across-placement cut) — not deleted.
   A placement carries several deltas only across a physical separation: two of
   its components with no contact edge (parts further apart than
   `contact_epsilon_m`, i.e. beyond `identity.min_distinct_spacing_m`).
2. **FEET ACROSS THE BODY.** Every ground-contact part of a body contributes its
   feet-founded seat target; the body's ground is their MEDIAN and EVERY part of
   the body takes that one delta (`ground_m − base(member)`) — the per-part
   "own target" of 09s (2) is WITHDRAWN, it was the second source of the tear.
   The per-foot residual (`target − ground_m`, one per measured ground part) is
   reported in `ClusterSeat.foot_residuals` with its max. A body wider than
   `[rebake] body_feet_span_m` (100 m) carrying fewer than
   `ceil(diameter / body_feet_span_m)` measured feet SAMPLES the design surface —
   the same mesh reader the seat and `tools/seat_feet_census.py` use, one sample
   per ground-contact part at its footprint centroid `(lat, lon)` with its
   `base_y` as the authored y — and those samples join the median as additional
   feet (counted in `ClusterSeat.feet_sampled`).
3. **PLATES FOLLOW THE BODY THEY TOUCH.** Ground bodies are formed FIRST (rule 1);
   every elevated / non-founding part is then assigned by multi-source BFS over
   the contact graph FROM the bodies' ground parts — the body it touches,
   transitively, never a contact-count vote. A tie at equal hop distance resolves
   to the body containing a ground part of the SAME placement, then to the lowest
   body id. An elevated part never bridges two bodies (it joins one; it does not
   merge them). A part reaching no ground part joins the NEAREST body only when
   its plan box lies within `identity.min_distinct_spacing_m × 4` (2.0 m) of that
   body's parts; otherwise it is HELD, with the distance in the skip reason.
4. **OTHH IS EXEMPT BY CONSTRUCTION.** The interchange basin plates, the tunnel /
   bridge decks and every `plate_units` member are `fixed` MEMBERS: their parts
   carry `fixed`/`family`, are excluded from the ground vote and the cut, and
   their separation from the walls is a structure-seat rule, untouched by 1–3.
   No special case is added. PROOF PLAN: `tools/v2_rebake_replay.py seat` on the
   owner's OTHH plan + mesh, both arms, `Dewatering Drainage` 14 / `tunnels` 8 /
   `Fire Fuel` 3 written deltas within 0.05 m of 1.0.300's. Any family that moves
   is a STOP-and-report, not a special case.

### 14.2 Consumer census (owner ruling 2026-08-30l): every reader of a cluster id,
a part delta, `plate_units` and the basin plates

| # | Consumer | Reads | Ruling |
|---|---|---|---|
| C1 | `emit/clusters.py::seat_clusters` | the contact graph, `Part.feet`, `fixed`/`family` | THE SITE OF THE CHANGE (rules 1–3) |
| C2 | `emit/rebake.py` `_plate_seats` / deck seats | builds `fixed`, `family`, `stay` per MEMBER | unchanged — rule 4's exemption lives here |
| C3 | `emit/rebake.py` member note / `one_delta` | `MemberParts.part_deltas` | unchanged; "several per-vertex deltas" now fires only across a separation |
| C4 | `emit/rebake.py::_one_file_one_delta` | effective deltas per resource | unchanged (a resource at several anchors still needs agreement) |
| C5 | `model/rebake.py::SeatResult.counts` | `multi_delta`, `plate_units` | unchanged; `multi_delta` becomes the separation count |
| C6 | `model/rebake.py::ClusterSeat` | the seat record | EXTENDED: `foot_residuals`, `foot_residual_max_m`, `feet_sampled` (appended, defaulted — old JSON still round-trips) |
| C7 | `auto_patch/engine_v2.py::_decision` | `ms.part_deltas` → `by_comp`, `held` | unchanged |
| C8 | `airport/rigid.py::complete_component_deltas` | per-file free components, carrier by contact | unchanged: once one placement is one body its touching carriers share one delta, so the count vote is moot — VERIFIED by the pair census, not asserted |
| C9 | `airport/rebake_plan.py` | writes `Part.feet`, the witness gate | unchanged; `PLAN_VERSION` stays 6 (no plan format change) |
| C10 | `airport/contact.py::partition` | ε-contact edges, the elevated cull | unchanged |
| C11 | `tools/seat_feet_census.py` | `part_deltas` of a result | unchanged (the acceptance instrument) |
| C12 | `tools/v2_rebake_replay.py` `seat`/`bodies` | plan + result | EXTENDED: `bodies --pairs` is the tear census (pairs of one OBJ8 within 2 m with different deltas) |
| C13 | basin plate seat (`Basin.witness_id`, 09ac (2)) | the witness resource only | unchanged — a basin plate is a `fixed` member (rule 4) |

### 14.3 Law key

`structures.toml [rebake] body_feet_span_m = 100.0` — a body wider than this
needs at least one measured foot per that span; short of it the seat samples the
design surface under every ground-contact part (rule 2). `0` disables the
sampling (the pre-10i reading).

### 14.4 What was measured (lane `v2rigid`, LEMD patch build 351 s + offline replay
on the owner's 1.0.300 mesh `Data+40-004.mesh`)

`tools/v2_rebake_replay.py pairs` (new): pairs of one OBJ8 within 2 m whose applied
deltas differ by more than 0.05 m — **21,769 → 10,026**; over 2 m **12,057 → 505**,
in **25 → 14** resources. The T4 car park (`Terminal4_yellow-LEMD13`), the old
terminal (`OldTerminal_FSX-ZNTWR` / `LEMD54` / `tej2` / `LEMD03`) and the T4S k1
mega-cluster are GONE from the census. `seat_feet_census.py` `> 3 m` **20 → 22**
(the same instrument on both arms; 09ak's "14" is a different reading).
`cut_edges` 929 → 318, all across placements; `intra_placement_kept` 672;
`held_parts` 5; the T4S k1 body 4,202 parts / ⌀982 m / 1 foot → 43 parts / ⌀43 m,
the satellite now seated +2.83 on 14 feet. OTHH: **byte-for-byte the same 20
written resources** (Dewatering 9, tunnels 8, Fire Fuel 3), max delta difference
0.000 m — the exemption held by construction, no special case.

Two findings for the spawner:

* **The partition hid the touch.** `airport/contact.py` records a connectivity-
  equivalent SPANNING subset, so two components of ONE placement 16 mm apart
  (`ZNTWR` c0/c4) carried NO edge and the across-placement cut ran along the path
  between them. Fixed at the derivation site: an intra-placement pair is tested and
  RECORDED even when already joined transitively (LEMD contacts 23,371 → 34,113,
  rebake plan 27.0 s, build 351 s).
* **10i (2)'s sampling cannot manufacture feet.** It reads the surface under the
  parts that TOUCH the ground; LEMD's T4 complex (5,255 parts, 30 resources,
  ⌀1,204 m) is authored with its floor 5.36 m above the pack's `y = 0`, so ONE
  265 m² slab is its only ground-contact part and the rule adds one foot.
  Widening "ground-contact" to each placement's own lowest stratum was tried and
  **REFUTED** (pairs over 2 m 505 → 15,763, worst 46 m) and deleted. The residual
  505 pairs are dominated by one 43-part T4S body whose single foot stands on a
  design-surface plateau at 588.95 (40.49186, −3.56815) while its neighbours read
  598.3 — a 9.35 m step in the SURFACE under one welded structure, not a seat law.
  STOP-and-report under the attempt cap.

## 15. RULINGS 2026-09-10u: THE PLATE FOLLOWS THE WALL IT TOUCHES, AND THE WALL UNDER ITS EAVE (lane `v2roofs`)

Measured on the owner's 1.0.306 LEMD (plan + result in the data repo, mesh
`Data+40-004.mesh`): 440 plate-above-wall pairs over 0.5 m, 257 plates, 16
resources. **2,345 contact edges INSIDE one placement still carry different
deltas** — and the split is **1,679 elevated×elevated against 666 ground×
elevated**, so 10u's stated site (`clusters.py:331` `elif pa.ground or
pb.ground: continue`) is the SMALLER half. The worst site, `Terminal4SAT_
Yellow-LEMD11.obj` (plate c5153 at +3.550, 0.089 m from wall c3104 at
−5.621), is elevated×elevated: BOTH ends are elevated (`base_y` 14.984 and
8.112, no feet), each is assigned INDEPENDENTLY by the multi-source BFS in
the same round, and neither ever sees the other. DEVIATION REPORTED: rule 1
below is 10u (1) widened to every intra-placement contact edge — the narrow
reading fixes 666 of 2,345 and leaves the ruling's own named bar unmet.

### 15.1 The two rules

1. **A TOUCHING SET OF ONE PLACEMENT IS ONE BODY, ELEVATED INCLUDED** (10u (1)
   under 10i (1)/(3), 09z (4)). Elevated parts of one placement joined by
   intra-placement contact edges form a COHESION GROUP; the BFS assigns the
   GROUP, never a part, so two touching elevated components of one file can
   never land in different bodies. Where a group touches several bodies it
   joins ONE (it never bridges them): the body whose touched part has the
   largest PLAN-FOOTPRINT OVERLAP with the group — the wall it rests on —
   then a body holding a ground part of the same placement, and only then the
   lowest body id. No number in code.
2. **THE EAVE GAP** (10u (2)). In `rigid.complete_component_deltas`, a free
   component with NO carrier within `contact_tol_m` no longer falls straight
   to nearest: a carrier whose plan footprint OVERLAPS the free component's,
   whose top is not above the free component's top, and whose top lies within
   `[rebake] plate_gap_max_m` of the free component's bottom, is taken as if
   touching (highest such top first, then largest plan overlap, then lowest
   index). Beyond `plate_gap_max_m`, nearest exactly as today, and the count
   that fell through is REPORTED.

### 15.2 Consumer census (owner ruling 2026-08-30l): every reader of a contact edge, a body assignment and a plate seat

| # | Consumer | Reads | Ruling |
|---|---|---|---|
| C1 | `emit/clusters.py::seat_clusters` cut loop | `plan.contacts`, `Part.feet`, `key` | THE SITE of rule 1 (`ecoh` groups; the ground×ground cut untouched) |
| C2 | `emit/clusters.py` elevated BFS + nearest fallback | `adj`, `cluster_of`, `Part.box` | REWRITTEN per group; the `euf` "touched nothing" fallback and the `min_distinct_spacing_m × 4` reach unchanged |
| C3 | `emit/clusters.py` seat / feet-across-body (10i (2)) | a body's GROUND parts only | unchanged — elevated parts still never vote |
| C4 | `emit/rebake.py` `_plate_seats` / deck seats / `stay` | `fixed`, `family` per MEMBER | unchanged: a fixed part is never in a cohesion group (OTHH's exemption, 14.1 rule 4) |
| C5 | `emit/rebake.py::_one_file_one_delta`, member notes | effective deltas per resource | unchanged |
| C6 | `model/rebake.py::ClusterSeat` / `SeatResult.counts` | the seat record | EXTENDED by counters only (`elevated_groups`, `group_ties`) |
| C7 | `airport/rigid.py::complete_component_deltas` | free components, carrier by contact | THE SITE of rule 2 (new `plate_gap_max_m` argument, default `0.0` = today) |
| C8 | `auto_patch/engine_v2.py::_decision` | `ms.part_deltas`, `held` | passes the new law value; no other change |
| C9 | `airport/contact.py::partition` | ε-contact edges, the elevated cull | UNCHANGED — the contact graph stays PHYSICAL. Rule 2's 4 m reach is a CARRIER rule, never a contact edge: widening ε would merge structures, pools and the facility rule with it |
| C10 | `airport/rebake_plan.py` | the witness gate, `Part.box` | unchanged; `PLAN_VERSION` stays 6 (no plan format change — so the OTHH proof replays the owner's own plan) |
| C11 | `tools/seat_feet_census.py` | `part_deltas` of a result | unchanged (acceptance instrument) |
| C12 | `tools/v2_rebake_replay.py pairs` | plan + result | EXTENDED: `--class plate-vs-wall` (15.4) |
| C13 | basin plate seat, `plate_units`, `Basin.witness_id` | the witness resource | unchanged — a basin plate is a `fixed` member |

### 15.3 Law key

`structures.toml [rebake] plate_gap_max_m = 4.0` — a roof over a wall top with
an eave or parapet gap up to this joins that wall's body as if touching. `0`
disables rule 2 (the pre-10u pure-nearest fallback).

### 15.4 OTHH's exemption proof plan

No special case is added. OTHH's tunnel/bridge decks, interchange basin plates
and every `plate_units` member are `fixed` MEMBERS: their parts are excluded
from the cohesion groups (C4) and from rule 2 (they are never free), and the
interchange's deliberately separate datums are ACROSS placements, which rule 1
does not touch. PROOF: `tools/v2_rebake_replay.py seat` on the owner's OTHH
plan + mesh, both arms — the same 20 written resources (Dewatering 9, tunnels
8, Fire Fuel 3), max delta difference 0.000 m. Any family that moves is a
STOP-and-report.

### 15.5 The instrument

`tools/v2_rebake_replay.py pairs --class plate-vs-wall`: PLATE = a component of
y-extent under `--plate-thickness` with ≥3 vertices, WALL = y-extent at or over
it; a pair is counted when a wall vertex lies within `--near` in PLAN and the
plate's applied delta exceeds the wall's by more than `--floor`. Bucketed by
the AUTHORED vertical gap (plate bottom − wall top): `contact` (≤
`contact_epsilon_m`), `gap` (≤ `--gap`, the `plate_gap_max_m` class) and `far`.
