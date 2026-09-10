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
