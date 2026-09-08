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
object footprint inside the datum region (`flat_site_ground_datum =
true`) and the pack's seat is AUTHORITATIVE there: a CLUSTER ground part
inside the region reads its object's authored `y = 0` plane as its
ground (delta 0 — never the canal bank, never the raw inset DEM outside
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
closing build adds (c): middle-west/-east read the at-grade ground →
−0.92 / −0.71 → stay (d) → 22 files. The brief's target "≤ 18, the
Dewatering cut compensations" does not count the six tunnel files, which
are the same class (the anchor on the cut floor the mesh made); they are
quoted, not suppressed.

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
