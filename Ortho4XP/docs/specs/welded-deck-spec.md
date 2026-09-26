# The welded deck — a hard deck inside a building unit is a DECK, and the ground under it is not the building's pad

Issue #14 (OTHH-3), site 25.2599127, 51.6149444. Fable 2026-09-25, lane `deckspec`. Law it amends:
object-placement-spec §16g (10) (2)/(4)/(7) (RULINGS 14x/14ah/14aj/17t), §6/§13/§16a (11a, 11r/s), §16e/§16g (7) deck
guard (14c); design §30 (4); RULINGS 23a (apron welds to the pad edge). Measurements: the registered OTHH frame
(`frames.py list OTHH`: capture `othhjunction/OTHH.pkl`, closing plan `/tmp/harness/othhjunction.v2/OTHH.rebake.json`
+ `OTHH.graded.json`, base 059a1f18), HECA `/tmp/harness/hecabase_main.v2` (main), LEMD `XPTerrainBuilderData/Patches/
+40-010/+40-004/o4_v2_rebake_LEMD.json` (09-17). Dry reads only; nothing built.

## 0. Attribution — the mechanism is NOT the pier test, and NOT the deck's own ring

`Buildings/Terminal/OTHH_TerminalRoads_01_001.obj` (plan `unit:85`, `deck_kind=flag`, ring 10,980 m², `deck_top_y` 12.64,
`deck_datum_z` 3.99) is a 1.9 m slab authored entirely at y 10.75–12.64 with NO column, wall or foot of its own: one part,
`base_y` 10.746. `deck_signature.elevated_deck` reads it "no near-horizontal face 2 m above its own floor" — the resource's
floor IS the slab's underside — so `elevated_deck=False`. That flag is read by nothing on the pad path (scout census, §3).
The member is already a LEAF (`member_is_deck` → `walled=False`, `leaf_dropped`), so its own ring mints nothing.

What mints the pad under it is §16g (10) (2)'s outline rule: the cluster outline is the union of EVERY part ring of every
WALLED body, elevated parts included. Under the deck ring D: `OTHH_TerminalRoads_01_003.obj` (32 parts; 30 ground columns
`base_y` −2.2 with 1,151 m² of ground trace inside D, two elevated beam parts at 8.0/11.8 m shading 6,164 m²) and
`OTHH_TerminalRoads_01_004.obj` (13 parts, all `base_y` ≥ 9.55, h 4.87 → "walled", 3,716 m²). The deck's shade is minted
by its neighbours' upper storeys. Emitted pads over D: `building7` 5,659 of 6,042 m² and `building4` 4,921 m²; of that
9,454 m² only 1,151 m² has anything standing on the ground.

**The obvious fix is REFUTED by measurement.** "A walled body's ring mints ground only from parts standing on the ground"
(part `base_y` ≤ T) was swept T = 0.5 … 8 m through the exact derivation (`plan_clusters` + `cluster_outlines`): at T = 0.5
OTHH loses 402,562 of 469,125 m² of emitted pad (85.8 %; the terminal `building4` 91 %), HECA 18.0 % (`building14` 37 %),
LEMD 7.5 %; at T = 8 still 64.9 / 10.1 / 5.7 %. Packs author terminals as walls + roofs: OTHH's terminal ground floor is
`Terminal_Base_2_2` (182 of 1,221 parts at ground, wall slivers), the plan is carried by roof parts at 18–30 m. The pad
IS the walled cluster's shade, as 14x ruled; the deck must be told apart by WHAT STANDS UNDER ITS PLATE, not by the base
height of the rings that shade the ground.

## 1. THE DISCRIMINATOR — the pier reading in the UNIT frame

For a `flag` (ATTR_hard_deck) member m of plan unit U (the anchor family), with D its `deck_ring`:

1. **The plate** is the dominant near-horizontal bin of m's hard-deck faces (`deck_plane_bin_m`, `deck_plane_area_tie`,
   the tie to the higher bin — `elevated_deck`'s own bin rule), `y_plate`, measured from the UNIT'S ZERO PLANE (y = 0,
   §16g (2)) — never from the resource's own lowest vertex. H = `[structures.bridge] deck_min_elevation_m` (2.0 m): a plate
   under H is a slab on the ground and the rule does not apply. No new number: the corpus population (every ATTR_hard_deck
   member; LEMD has none) is OTHH 01_001 **12.50**, 03_000 8.00, 02_000 6.50, Parking 6.90, Bridge_02 9.02, _06 7.99,
   _03 2.37, Bridge_01/04/05 3.2–4.6 (thin slabs over water; no plate in the resource frame, their slab IS the plate in
   the unit frame); HECA `T3_road.obj` **3.50** (`deck_top_y` 16.83 is the MAX of its hard faces — the ramps — not the plate).
   Minimum 2.37 ≥ H: every hard deck in the corpus is a candidate; the section decides.
2. **The section at y_mid = y_plate / 2**, over EVERY member of U (and any member of another unit whose part box touches D —
   the welded neighbour): the solid faces whose plan centroid lies in D and which cross y_mid. Each member's own trace is
   rasterised and hole-filled ALONE (`deck_signature._raster`, cell `deck_pier_close_m` — a building's OWN walls close its
   own ring), the filled cells are unioned inside D, NEVER filled across members: `ratio = filled ∩ D / D`. Filling the
   joint trace is refuted: at HECA the deck's parapet and the terminal façade together close a loop and the joint fill
   reads 0.683 against 0.093 per member; the unfilled buffered trace cannot tell walls from piers (0.037 vs 0.146).
3. **DECK iff ratio ≤ `deck_pier_footprint_max` (0.20).** Measured, per-member fill: OTHH 01_001 **0.033 → DECK**;
   02_000 0.277 and 03_000 0.249 → WALLED (the two lower-road boxes: their own walls 0.181/0.068 plus the terminal's — a
   road inside walls under a deck is a walled solid and Law C's corridor already owns the road: `wall_corridor_ramp`
   683 m² under 02_000); HECA `T3_road` **0.093 → DECK** (self 0.062, largest other 0.025).
4. **Publication.** `Member.deck_shade_ring` (lat/lon ring(s), None when not a deck by 1–3) and `Member.deck_pier_ratio`,
   plan version 9 → 10 (`from_dict` defaults None/None so a v9 plan loads and mints as today); the partition cache keys on
   the code digest and self-invalidates. `elevated_deck` (resource frame) is NOT changed — it stays what `planar/group`
   is gated on; nothing else reads it. `SHADE = D − (filled section ∩ D)`: the ground the piers/walls do occupy stays
   pad-eligible (OTHH: 3.3 % of D in column blobs, under `[building_pad] min_area_m2`).

## 2. THE REGION RULE — the ground under a deck is never the building's pad

1. **Outline (the ONE derivation, `geom/cluster_outline.cluster_outlines`, new rule 6).** Every cluster outline has every
   deck shade of the plan SUBTRACTED, after rule 2's close (so the dilate/erode does not refill it) and before rule 3
   (over-another) and rule 4/5. Both readers — the mint `classify/evidence._cluster_pads` and the census
   `constraints/cluster_pad.cluster_polys` — pass the same `shades` from one helper `planar/cluster.deck_shades(airport)`
   (read off `airport.partition` members), so mint and `pad_cluster_mismatch` cannot disagree.
2. **Fallback footprints** (`_pads` :583-591, OSM / `dsf:fac` / `dsf:object`): a footprint is trimmed by the shades before
   the 50 % cover test. A deck never re-enters as a v1 footprint or an OSM `building=roof`.
3. **The ground keeps the role of what surrounds it.** No new role, no new shape class: the cells under the shade are
   whatever the classifier scores there once the pad no longer subtracts them — the OSM road corridors and 1206 route
   (`roles.py:544` no longer minus `pad_union` there → `service_road`, groundside, §2 road clamp), apron cells extend
   under it where apt.dat pavement runs there (`apron_cut_to_pads` no longer cuts, 23a's weld moves to the new pad edge),
   and open ground between is the §23 groundside terrace ground. The deck's `deck_datum_z` (median solved z inside D,
   `deck_datum_from_surface`) then reads the ground under the deck instead of the pad plane.
4. **The deck body rides.** 01_001 is ELEVATED (§13: `y_zero` 10.75 > `elevated_base_m`) and CARRIED (§16a) by the ground
   body of its placement with the largest plan overlap, at its authored offset — unchanged. It is never emitted as
   pavement: `emit_decks` keeps object decks "recorded, never severing"; `bridge_deck:*` faces stay §49's mapped-way class.
5. **A welded deck lends no datum.** §16g (2)'s first priority (a DECK member's abutment datum) and the §16g (7) deck guard
   (`_deck_lending`, touching bodies take the deck's `deck_datum_z`) are confined to units whose walled members are the
   deck family's own (bridges). A deck by §1 inside a unit holding walled non-deck bodies is a rider: `deck_datum_lent_to`
   0 for it, the unit datum stays the pad plurality (17t median). Without this, unit:85's touching kerb bodies would
   re-seat to the road under the deck the day the pad leaves.

## 3. CONSUMER CENSUS (RULINGS 2026-08-30l; scout census over the current tree, rows with a Δ; the rest read a face)

| reader (`auto_patch_v2/…`) | reads | Δ under §1–§2 | ruling |
|---|---|---|---|
| `geom/cluster_outline.cluster_outlines` :47-136 | cluster rings, walled, min_m2 | **EDITED**: rule 6 subtracts shades | the ONE site |
| `classify/evidence._cluster_pads` :452-521, `constraints/cluster_pad.cluster_polys` :120-172 | `cluster_outlines` | **EDITED**: both pass `shades` | one helper, two callers |
| `classify/evidence._pads` :583-591 (fallback) | OSM/fac/obj footprints vs cluster cover | **EDITED**: trim by shades first | §2 (2) |
| `planar/cluster.clusters` :90-137 | partition units | **EDITED**: `deck_shades()` beside it, memoised | derivation site |
| `airport/deck_signature` :625-816 | resource geometry | **EDITED**: `welded_deck(cache, members, m, law)` reusing `_raster`/`_footprint_m2`; `elevated_deck` untouched | §1 |
| `airport/rebake_plan._with_deck` :247-302, `model/rebake.Member` :144-207/:325-395 | ring, top, datum | **EDITED**: stamp `deck_shade_ring`, `deck_pier_ratio`; version 10 | §1 (4) |
| `airport/footprint_unit._deck_lending` :348-405, datum priority :86/:535 | `deck_datum_z` of unit members | **EDITED**: a shaded deck in a walled non-deck unit lends nothing | §2 (5) |
| `classify/roles.classify` :544-545, :589-590; `_cut_back_groundside` :726-760 | road corridors − `pad_union`; pads → building cells | UNTOUCHED — roads survive under the shade; smaller pad | seam-probe: the site's cell role |
| `planar/overlay.apron_cut_to_pads` :168-296 (23a) | apron − pads | UNTOUCHED — apron extends under the shade where pavement runs | seam-probe: `building7`/apron shared edge |
| `constraints/pads.*`, `pad_relief`, `pad_frontage_gs`, `foot_rows` | rigid faces, frontage vertices | UNTOUCHED — face-driven; new frontage along the shade edge | census `pad_airside_weld` |
| `constraints/cluster_pad.pad_cluster_mismatch` :230-398; `check_grade` :6290/:6393 | clusters vs building refs | UNTOUCHED — same shade on both sides | bar: 0 new rows |
| `emit/rebake.deck_datum_from_surface` :33-55 → `rebake_plan` :278 | median z inside D | UNTOUCHED — now reads the ground under the deck | consumed only via §2 (5) |
| `airport/anchor_rule` `_pad_of`/`pad_majority` :351-462, `footprint_unit.plan_unit_datums` :528-597 | PadRing contacts | UNTOUCHED — unit:85's contacts under the deck (1,151 m² of columns) leave the pad; median over `building4` moves < 0.02 m expected | bar |
| `airport/placement_carrier.is_elevated` :73-106, `merge_rides` | `base_y` > 0.5, overlaps | UNTOUCHED — 01_001 rides 01_003 as today | seam-probe: carrier named |
| `planar/group` :334-351/:444/:459 | `elevated_deck` (flag decks refused at :342) | UNTOUCHED — flag unchanged | none |
| `planar/structures` :284-288/:576/:882 (pads as ramp stops), `wall_corridor_ramps.airside_stops` :126-131 | building faces | UNTOUCHED — a corridor that stopped at the shaded pad edge may run on under the deck | seam-probe: corridor count 73 |
| `planar/basins` :924-933, `channel` :843, `structure_deck.emit_decks` :618+ | `hard_deck`, `deck_top_z` | UNTOUCHED — recorded, never a face | none |
| `pipeline/publication` :252-300 (sidecar `cluster_pads`), `pack_partition` :389/:439 counts | — | additive: `deck_shades` count, area | say-line |
| `law/structures.toml:632 abutment_deck_share_min` | — | DEAD KEY (no reader) — delete in the same commit | scout finding |

## 4. ACCEPTANCE

**OTHH, the owner's site 25.2599127, 51.6149444** (numbers first, today → bar): containing face shape 925 `building7`, role
`building`, side airside, `aeroway=apron`, z 3.15–4.71 (med 4.30) → **no `building` face contains the site**; the face
there is a road/ground face (`service_road` or the §23 ground), z within `visual_m` of the roads' §2 profile.
`building7` 5,972 m² (census; 6,042 in the local metric) → ≤ 600 m² or absent (< `min_area_m2` 250 after the 5,469 m² of
shade leaves). `building4` 395,514 → ≈ 391,500 m² (−3,985 of shade, −1.0 %); its pad datum (17t median) within 0.02 m of
today; `pad_cluster_mismatch` and `pad_airside_weld` no new rows; airside vertices moved > 0.02 m = 0 (the runway/taxi
family untouched); `OTHH_TerminalRoads_01_001` still carried (§13/§16a) at its authored offset — `zero − zero_beneath`
≤ 0.3, carrier named; 02_000/03_000 WALLED (ratio 0.277/0.249), their ground unchanged; the bus bridges 01/04/05 and the
02/03/06 interchange stand over no pad — no face moves there. v2 verify DEFECT families empty (146 rows today).
**HECA control:** `T3_road.obj` reads DECK (0.093); its shade leaves `building14` 209,347 → ≈ 190,700, `building15` 3,276 →
≈ 860, `building16` 256 → absent; the terminal at 30.1279552, 31.403143 stays on its pad within 0.02 m (the §16g (7) (2)
connector already lends nothing); every other HECA pad byte-identical in ring; airside moved 0. **LEMD control:** no
ATTR_hard_deck member — design surface `body_sha` unchanged (dry). Suite once on the touched files; plan stage ≤ +1 s
(≤ 11 hard decks × ≤ 40 members read through the memoised cache, measured 1–2 s per deck in the dry read).

## 5. OWNER QUESTIONS (defaults in force unless ruled)

- **Q1** The ground under a welded deck keeps the role of what surrounds it (roads → groundside road law, apron → apron,
  else terrace ground). Default YES; the alternative (a dedicated `deck_underpass` role) is a new shape class and a
  second census — not proposed.
- **Q2** HECA's T3 departures deck shade (22,137 m², 21,280 of it pad today) leaves the terminal pads by the same law.
  Default YES (one law, no airport clause); the sim read decides — the kerb road under it today sits on the pad plane.
- **Q3** A WALLED hard-deck box (02_000/03_000: a road inside walls under a deck) keeps its ground in the pad; Law C's
  corridor owns the road. Default YES.
- **Q4** The lesser #14 question — `building` pads written `aeroway=apron` (`precedence.toml:74`): unchanged here; an
  emit-vocabulary question for its own spec. Default UNCHANGED.

## 6. OPUS BRIEF (lane, after the owner's Q defaults or rulings; model opus; this spec is the frozen interface)

Files: `airport/deck_signature.py` (`welded_deck`), `airport/rebake_plan.py`, `model/rebake.py` (v10),
`planar/cluster.py` (`deck_shades`), `geom/cluster_outline.py` (rule 6, `shades=`), `classify/evidence.py` (both sites),
`constraints/cluster_pad.py`, `airport/footprint_unit.py` (§2 (5)), `law/structures.toml` (delete the dead key; NO new
numbers — H and the gate are the existing bridge keys), `pipeline/publication.py` (say-line). Twins
`tests/auto_patch_v2/test_welded_deck.py`: (a) a box building + a slab on four columns welded to its wall → shade =
slab ring − column blobs, ratio < 0.2; (b) the same slab on a walled box → no shade; (c) two members whose walls only
JOINTLY enclose the section → per-member fill, still a deck; (d) a plate under H → no shade; (e) `cluster_outlines` with a
shade excludes it after the close and a fallback footprint over it is trimmed; (f) a v9 plan loads with shade None and
mints as today; (g) a shaded deck lends no datum (`deck_datum_lent_to` 0) while a bridge unit still takes its deck's.
Blast: `tools/blast.py` on each file first; run only its named tests once. Convergence guards: materiality 0.01 m /
1 m² per bar; attempt cap 2 per bar then STOP-and-report; `.progress` START/step/EXIT stamps. Build-time statement
in the report (plan stage before/after, 3 runs of the dry `plan`). Closing test, in order: (1) HECA dry — `v2_solve_replay
--capture HECA` (~140 s) then `--replay --from classify --emit --verify --pad-read --site 30.1279552,31.403143`; (2) OTHH:
the shade is stamped at partition time, upstream of every `--from` stage, so RE-CAPTURE on the branch (`--capture OTHH`,
~36 min / 25 GB, lane-local overlays as the `othhjunction` frames row says) then `--replay --from classify --emit --verify
--pad-read --site 25.2599127,51.6149444`, quote §4's numbers against the registered `othhjunction` emission; (3) ONE
`build_airport.py OTHH --tag deckspec` (rc, census LAW-TRUE / ADJUDICATED / CRITICAL beside 1,196 / 494 / 0, `body_sha`,
shared repo UNCHANGED); (4) LEMD dry `body_sha` identical. Register every product (`frames.py register`). Report the site
numbers first, then the tables of §4, every deviation from this spec STOPPED and reported to its Fable author, never
decided. Never the five-airport sweep; the spawner merges; commit `Fixes #14` only if §4's site bar is met.
