# Below-grade cutouts and deck-flush grading — implementation plan

**Status:** REVISED after Fable design review (2026-07-31). Owner rulings 2026-07-30/31.
**Owner:** Opus implements. Fable reviewed this document only.

> **Review outcome: the first draft was NOT implementable.** Five blocking findings, all verified
> against the source before accepting them. They are folded in below; the draft's claims that were
> wrong are struck and corrected in place rather than deleted, so the error is not re-made.
>
> | # | draft claimed | verified reality |
> |---|---|---|
> | 1 | Bridge_04 routes to `insert_bridge_deck_end_pins` | pins only reach the `corridor` partition (`bridges.py:6543-6548`); Bridge_04's crest +1.91 < `BRIDGE_DECK_CARRIED_MIN_HEIGHT_M` = 2.0 (`object_terrain_features.py:214`) ⇒ AMBIGUOUS/`road_carried`, **zero pins**. A new partition outcome is required. |
> | 2 | discriminator at 1 m is safe | flips the EGLL tunnel-10 fixture (`tests/test_object_terrain_features.py:751-769`: deck at effective −0.5 m, AGL −1.0, asserts one tunnel). Must be **hardness-qualified** and use its own constant, not R14's 1 m. |
> | 3 | W4c's discriminator "already computed" as `excluded` | `excluded` is `_depressed_way_ids` and `EMIT_DEPRESSED_ROADS = False` (`config.py:456`) ⇒ **empty in every default build**, and it means "ways *we* depressed", not "the pack models the crossing". |
> | 4 | (not mentioned) | `_CLASSIFICATION_CACHE_VERSION = 11` (`object_terrain_assembly.py:419`) must bump with any classifier change, or a warm build serves old records and reads as "no change". |
> | 5 | "floor plates that step down" | `born_flat_solver_plate` is flat-only (`bridges.py:6428`); a sloped floor is ONE plate with per-vertex `node_altitudes`, the `ROLE_BRIDGE_TRENCH` idiom. |
>
> Also corrected: §2's mechanism attribution. Bridge_01 **cannot** have entered via the AGL limb —
> `_agl_tunnel_seed_resources` caps the highest face at `TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M`
> (`object_terrain_features.py:1976-1979`) and Bridge_01 crests at +10.25 m. It seeds via the
> hard-below-grade limb; only **Bridge_04** is an AGL-limb case. W1 must intervene in both limbs.

---

## 0. What the owner ruled

1. **R14 (2026-07-31).** *"For any object that extends more than 1 m below grade, I want cutouts so
   the whole below grade portion is visible."*
2. **Bridges are above-ground.** *"All the bridges you highlighted, including the green one, are
   above ground bridges… they just need to be set so their top edge (the road deck) at either end is
   flush with grade."*
3. **Deck flush is at the ENDS only** — pin the two deck ends, let the solver run between them.
4. **Bridge_01 (the green one)** is connected to the main terminal and *"our current cutout is just
   leaving the ramp above grade"* — terrain must be graded **up** to it.
5. **The 8th tunnel** should be *"one cutout that exposes the whole below grade area, might be two
   objects, but the road crossing is modeled… so should just be an extended trench at the bottom of
   the ramp."*

---

## 1. The measurement law that everything else depends on

An object drapes at `terrain(anchor)`, so authored `y = 0` is the ground at **one point**. Reading
negative authored y as "below grade" counts every pier and foundation stub of a perfectly
above-ground structure. This is the error that produced the wrong bridge inventory.

Measured on the six OTHH bridges (deck faces separated from the rest):

| bridge | deck **ends** | crest | lowest face | >1 m below datum | of which deck |
|---|---|---|---|---|---|
| Bridge_01 | −1.22 / −1.28 | +10.25 | −5.84 | 1,174 m² (17.1 %) | **1,113 m²** |
| Bridge_02 | +0.77 / −0.55 | +19.87 | −7.60 | 1,289 m² (5.5 %) | 841 m² |
| Bridge_03 | +1.90 / −0.39 | +12.63 | −6.66 | 780 m² (6.0 %) | 166 m² |
| Bridge_04 | +0.23 / +0.24 | +1.91 | −3.35 | 107 m² (3.1 %) | 8 m² |
| Bridge_05 | +1.08 / +1.09 | +2.16 | −1.72 | 19 m² (0.5 %) | 0 m² |
| Bridge_06 | +0.78 / −0.70 | +18.20 | −1.81 | 853 m² (4.4 %) | 782 m² |

Every deck **end** is within ±1.9 m of the datum. The −9.67 / −8.72 m figures previously reported
are foundations: Bridge_02's −8..−2 m bands hold 305 m² of face with **zero** deck area, Bridge_03's
328 m² likewise.

**Law:** R14's 1 m test applies to **deck/floor surfaces that are below the LOCAL ground**, never to
authored y and never to non-deck stubs. Anything else carves a pit under every bridge pier.

---

## 2. Why Bridge_01 and Bridge_04 are currently cut as tunnels

Both are `OBJECT_AGL` placements with **negative AGL** (−3.50 m and −3.80 m). Negative OBJECT_AGL is
a deliberate tunnel signature (spec: EGLL tunnels 6/7/10 at −1.0/−7.0/−7.5 m). Their records:

    Bridge_01  kind=OBJECT_AGL agl=-3.50  body_depth=1.67  solid_min=-5.838  roof=True deck=True
    Bridge_04  kind=OBJECT_AGL agl=-3.80  body_depth=1.23  solid_min=-5.413  roof=True deck=True

The trench floor law then takes `min(-body_depth, solid_minimum_y)` = −5.84 and cuts to
−6.34 m across the **whole** footprint. But Bridge_01's deck area sits like this:

    -6..-5 m   541 m2 deck      <- the descending ramp
    -5..-4 m   234 m2 deck
    -2..-1 m   330 m2 deck
    -1..+0 m 3,039 m2 deck      <- the bulk, AT GRADE
    +0..+1 m 2,099 m2 deck
    +6..+10 m   ~40 m2          <- a short flyover

So a **flat pan at the deepest solid** is wrong twice over: it digs 6 m under 5,138 m² of deck that
belongs at grade (leaving the deck floating — exactly the reported defect), and it does not follow
the ramp that genuinely descends.

---

## 3. Work items

### W0 — Cache version bump (prerequisite for W1/W2/W3)

`_CLASSIFICATION_CACHE_VERSION` 11 → 12 the moment classifier output changes, and any new
`TunnelStructure` field gets a dataclass default so old pickles still unpickle (the
`above_grade_area_fraction` precedent). Without it a warm OTHH build serves pre-change records and
shows "no change" — the trap that already cost an hour this session (STATUS `20260730b`, cache-root
note). **Do not make the classifier DEM-dependent**: the sidecar fingerprint covers pack inputs
only, so ground-aware classification would be silently wrong on a cache hit. Keep the classifier on
the anchor plane and do local-ground work in the emitters, where `_sample_dem` is already the idiom.

### W1 — Deck-end flush contract for bridges (owner rulings 2 and 3)

An above-ground bridge gets **no trench**. Its two deck ends are pinned to grade and the solver runs
between them; terrain under the span is left alone.

> **W1a LANDED, and the review's own premise was wrong — measured.** Fable proposed a
> *hardness-qualified* discriminator, reasoning that the EGLL AGL shells carry no hard triangles and
> are therefore safe. Measurement: **none of the six OTHH bridges has ANY hard triangle either**
> (0 m² hard near-horizontal, above or below grade), so a hard-area test can never fire on them and
> Bridge_01/04 would have stayed tunnels. Fable also held that Bridge_01 could not seed via the AGL
> limb because its crest (+10.25 m) exceeds `TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M` = 2.0 — but that
> cap is applied **per resource**, and `_agl_tunnel_seed_resources` returns exactly one seeding
> object for each of Bridge_01 and Bridge_04 (`*_LOD0_002.obj`). Both bridges seed via the AGL limb.
>
> **The landed fix is therefore simpler than either draft:** judge the AGL limb's above-grade cap and
> below-grade deck floor on the **whole structure**, not on the seeding resource. A single-placement
> structure is unaffected by construction (pool == resource), so every one-object AGL tunnel — the
> EGLL 6/7/10 shells and the fixtures pinning them — reads exactly as before.
>
> Verified on OTHH: Bridge_01's wrong trench is **gone** (object-tunnel floors 12 → 11, rims 84 →
> 74), the basin table is byte-identical, 399 tests pass across the ten-file blast radius.
> `_CLASSIFICATION_CACHE_VERSION` 11 → 12 (W0) so warm packs re-classify.
>
> ~~**Bridge_04 still trenches**~~ **W1a-part2 LANDED (2026-07-31) — and the candidate fix in this
> paragraph was measured and REJECTED.** Bridge_04's crest is +1.91 m (under the 2.0 m cap) and its
> below-grade near-horizontal area clears the 25 m² floor, because `below_grade_mask` keys on
> `TUNNEL_ROOF_TOP_TOLERANCE_M` — a shallow tolerance that catches the **underside of an at-grade
> deck** (Bridge_04's deck dips to −1.23 m with ends at +0.23/+0.24). ~~The candidate fix is to
> measure that floor at `TUNNEL_MIN_BODY_DEPTH_M` instead~~ — measured on the installed EGLL pack,
> that drops Tunnel/7's below-grade deck from 52.8 m² to **19.4 m²**, under the 25 m² gate, and
> un-classifies a real tunnel. It would also have flipped two synthetic fixtures.
>
> **What landed instead: a second above-grade gate, `TUNNEL_AGL_MAX_ABOVE_GRADE_DECK_AREA_M2`** —
> the AGL limb refuses a structure carrying ≥ 200 m² (`BRIDGE_MIN_DECK_AREA_M2`, one number, not
> two) of near-horizontal area standing clear above grade (≥ `+TUNNEL_ROOF_TOP_TOLERANCE_M`). The
> height cap catches structures that TOWER over grade; this catches the LOW bridge it cannot see.
>
> | structure | area ≥ +0.5 | area ≤ −1.0 | outcome |
> |---|---|---|---|
> | OTHH Bridge_04 | **1 650.6** | 8.4 | refused — 8× over the floor |
> | EGLL Tunnel/7 | **0.0** | 52.8 | still a tunnel (the only real AGL case) |
> | EGLL Tunnel/6 | 0.0 | 50.0 | unchanged |
> | EGLL Tunnel/10 | 128.7 | 55.1 | kept, 1.55× under the floor |
>
> Tunnel/10's 128.7 m² is exactly the figure `TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M`'s comment cites
> when warning that "an above-grade AREA test cannot do this job". That warning is about a FRACTION
> test and it stands; an ABSOLUTE floor is a different test.
>
> Verified: OTHH object-tunnels 1 → **0** (Bridge_04's trench gone), EGLL **unchanged** (8 tunnels,
> same list, 1 bridge). 315 passed / 11 skipped across the six-file blast radius; three new fixtures,
> including a guard on the rejected alternative. `_CLASSIFICATION_CACHE_VERSION` 12 → 13 (W0).
> Build-time: no measurable cost (classify best-of-3, gate ON vs OFF: OTHH −0.28 s, EGLL +0.16 s —
> opposite signs, both inside run-to-run noise on a 5–10 s call that is pack-sidecar cached).

* **W1a (superseded draft) — the discriminator, HARDNESS-QUALIFIED.** ~~deck-face fraction more than 1 m below local
  ground~~ *(flips EGLL tunnel 10 — review finding 2)*. Instead: a structure is bridge-family when
  its **hard** deck area at or above the at-grade band is both ≥ `BRIDGE_MIN_DECK_AREA_M2` (200 m²,
  absolute) and ≥ ~0.5 of its hard deck area, using a NEW constant for the band edge — never R14's
  1 m visibility threshold. The hardness qualifier is what protects the EGLL AGL shells, which carry
  **no hard triangles at all** (spec §2.1/A6) and so can never be caught. Bridge_01 (5,138 m² of
  at-grade deck) and Bridge_04 clear it easily.
  Intervene in **both** tunnel-seed limbs: the AGL limb (`_agl_tunnel_seed_resources`, Bridge_04)
  and the hard-below-grade limb of `_is_tunnel_signature` (Bridge_01). Confirm the firing limb per
  bridge with a cache-only probe first — mechanism before fix.
> **⚠ W1b IS BLOCKED ON A RULING — its premise was measured 2026-07-31 and does not hold at OTHH.**
> A partition outcome only helps a structure that reaches the partition. **None of the six OTHH
> bridges ever becomes a `BridgeStructure`**: all six carry ZERO hard triangles (hardness codes all
> 0), so `_hard_face_components` seeds nothing and only the whole-pool COSMETIC limb can fire. Three
> different gates stop them:
>
> | bridge | pool | n | gate |
> |---|---|---|---|
> | Bridge_01 | #1 | 2 251 | building gate — 57 299 wall columns ≥ `BUILDING_MIN_WALL_COLUMN_COUNT` (500); `_classify_bridge` is never called |
> | Bridge_02 / _03 / _06 | #65 | 239 | pooled into ONE candidate; refused *"piered viaduct: no solid geometry reaches effective grade within 35 m of the deck end(s)"* (the min-rotated-rect of three merged bridges ends in mid-air) |
> | Bridge_04 | #5495 | 5 | cosmetic limb needs ≥ `BRIDGE_MIN_DECK_AREA_M2` (200 m²) of deck at or above `BRIDGE_DECK_CARRIED_MIN_HEIGHT_M` (+2.0 m); it has **0.0 m²** |
> | Bridge_05 | #5494 | 5 | same floor; it has 45.7 m² |
>
> Built as specified, W1b is an **EGLL-only** change (4.obj: `DECK_CARRIED`, hard_deck, crest +7.84,
> ends 7.84/7.84, 52 m long, zero deck-end pins today — the STATUS-flagged gap). That is real, but
> it is not the owner's case. Reaching the owner's bridges needs a prior ruling on **which of the
> three gates yields**, each with its own cross-pack blast radius:
>   1. relax the cosmetic limb's +2 m elevated-deck floor (reaches Bridge_04/05; every low soft deck
>      in every pack becomes a bridge candidate);
>   2. exempt bridge-name-hinted members from the mega-pool building gate (reaches Bridge_01);
>   3. split pool #65 so Bridge_02/03/06 are three candidates (reaches them; the abutment refusal is
>      an artefact of the merge, not of the geometry).
>
> **UPDATE — OWNER RULED (2026-07-31): use the `bridge` name hint for now** ("great, but not always
> guaranteed"). Two of the three gates are now OPEN, and the ruling's scoping is what bounds them —
> `COSMETIC_BRIDGE_NAME_HINT`'s own standing law already restricts the hint to structures with ZERO
> hard triangles, so nothing that reaches the geometric deck path can be diverted.
>
> * **Gate A + B — `_cosmetic_bridge_components` (LANDED).** Cosmetic bridges are classified per
>   COMPONENT, the third instance of the lesson feature A learned in round 5 and feature C on
>   2026-07-30. Bridge_01's component is 11 resources with **85** wall columns instead of the pool's
>   57 299, so `_classify_bridge` is called on it at last. **Gate B is NOT fixed by this**:
>   Bridge_02/_03/_06 sit within `BRIDGE_COMPONENT_JOIN_BUFFER_M` (10 m) of each other, so they are
>   genuinely one component (31 seeds, 495 wall columns) and still refuse as a piered viaduct. Their
>   adjacency is physical, not a pooling artefact — the merge hypothesis is FALSIFIED.
> * **Gate C — the low-bridge limb (LANDED).** The cosmetic limb's +2 m floor asks "is there a deck
>   well ABOVE grade?", the wrong question for a road bridge crossing at grade. When the +2 m set
>   fails, the deck is re-measured against the AT-GRADE band. Strictly additive: the retry runs only
>   after the old test has already failed.
>
> **Result at OTHH: 0 bridges → 3** (Bridge_01, _04, _05, all `hardness=cosmetic`). **Every other
> installed pack is byte-identical** — KBNA (4 bridges, both Murfreesboro cosmetic decks included),
> KMCO, EGLL, EGGW, ELLX, LFPG all unchanged, verified by a forced-off/on diff.
>
> **Where they land, and why W1b is now the live piece.** `_partition_bridges_for_corridors` tests
> `is_cosmetic` BEFORE the contract, so a cosmetic bridge never reaches the `suppress` branch
> whatever its contract says — it goes to `corridor` or, with no taxi/truck route on the deck,
> `road_carried`. A landside road bridge is the second. `road_carried` takes **zero pins**, which is
> exactly review finding 1. W1b's deck-flush outcome is therefore `road_carried` **plus deck-end
> pins**, and nothing else changes.
>
> **The false-causeway hazard is already excluded upstream** — no ruling needed. Amendment A4's
> abutment test refuses any structure without solid geometry reaching grade within
> `ABUTMENT_GRADE_SEARCH_RADIUS_M` (35 m) of BOTH deck ends, so every surviving `BridgeStructure` has
> grounded abutments by construction. Pinning its deck ends cannot build a causeway over thin air.
>
> **What is still open:** whether deck-end pins go to EVERY `road_carried` bridge or only cosmetic
> ones. That cannot be measured offline — `_bridge_is_road_carried` needs a layout — so it is the one
> item a build has to settle.

* **W1b — a NEW partition outcome, because none of the existing three fits.** `corridor` drags a
  causeway, an under-deck trench, the R8 pavement cut and building-pad removal
  (`build_bridge_layout_shapes`); `road_carried` takes no pins at all; AMBIGUOUS is refused. Add a
  **deck-flush** outcome: pin the two deck ends, no causeway, no corridor, no trench. Decide
  explicitly whether the pinnable role set includes `ROLE_GROUNDSIDE_PAVEMENT` — Bridge_01 abuts the
  terminal's groundside pavement, which `_BRIDGE_PIN_ROLES` cannot pin today; the R13
  `pavement_cut_roles(include_groundside=…)` split is the precedent to copy.
* **W1c — reuse the existing deck-axis machinery** (`_deck_axis` min-rotated-rect and
  `_deck_top_profile` end bins, giving `deck_end_elevations_y_m`) rather than inventing a first/last
  10 % variant. The ends are already computed there.
* **W1d — R4 bookkeeping.** A structure that stops being a tunnel leaves the Phase-2 y-bake
  exclusion list, and refused bridges add none. Bridge_01/04 would newly become y-bake candidates —
  a vertical move of the OBJECTS. State and test the intended exclusion status per bridge.

**Verification:** Bridge_04 loses its trench and gains two end pins ~~(assumed)~~ — measure the
terrain-vs-deck-end delta on the built layout for **all twelve** bridge ends and show flush within
tolerance, so "Bridge_02/03/05/06 unchanged" is demonstrated rather than assumed. Run the classifier
unit suite before any build; it is the real net for the fixtures.

### W2 — Deck-following floors for genuine below-grade ramps (owner ruling 4)

Where the deck **is** below local ground (Bridge_01's descending section; the terminal ramps), the
cutout must **follow the deck profile**, not sit flat at the deepest point.

* **W2a — ONE sloped plate, not stepped pans.** ~~floor plates that step down~~ *(review finding
  5)*: `born_flat_solver_plate` is flat-only, and stepped pans at profile bins mint 0.3–0.8 m
  mini-cliffs whose shared boundaries recreate the one-node-two-altitudes glitch the wall-gap
  machinery exists to prevent. The established idiom is a **single plate carrying per-vertex
  `node_altitudes`** at law values — what `ROLE_BRIDGE_TRENCH` already does (densified ≈5 m) and
  what ruling R12 prescribes. `grade_law.tunnel_trench_floor_elevation_m(datum, deck_level)` takes
  per-bin calls unchanged.
* **W2b.** The cut extent is the part of the deck actually below local ground, not the whole
  footprint. For Bridge_01 that is the 775 m² at −6..−4 m plus its transition, not the 5,138 m² at
  grade. **Scope this to ramp-class records only** — EGLL's mouth ramps rise above −1 m, and
  applying W2b to them would drop their cut and break byte-identity.
* **W2c.** Terrain **grades up** to the at-grade portion — which is what W1's end pins already do
  once the body is no longer trenched flat.
* **W2d — the discriminator is an explicit RECORD MARKER, not a slope heuristic.** ~~"does the deck
  slope more than X % along its axis"~~ reads EGLL's mouth ramps and flips every EGLL tunnel; an
  end-to-end variant reads ≈0 on a U-profile and misses Bridge_01. Instead the classifier stamps
  ramp-class records (a populated `deck_depth_profile` field, or the `terrain_feature` tag), and
  `build_tunnel_layout_shapes` branches on the marker. Byte-identity for EGLL/EGKR/KBNA/EGGW then
  holds **by construction** — legacy records never carry the marker — instead of hanging on a
  heuristic. The branch must key on the marker and never on inferred depth-field shape, because
  `basin_trench_structures` *mints* `body_depth_m`/`solid_minimum_y_m` and basins must never take
  the profiled path.
* **W2e — pavement posture must be decided, not defaulted.** Tunnel-family records carry
  `cuts_pavement=False`, so R2 subtracts pavement from the body before birth. If Bridge_01's
  descending ramp lies under pack-faithful pavement (the `ASPH3.pol` situation that buried
  Drainage_04/05), the profiled floor yields to the last square metre, nothing is born, and the ramp
  stays buried — a guaranteed wasted build. Decide whether ramp cuts extend R13 (cut,
  groundside-inclusive) and record it as a ruling amendment.
* **W2f — anchor-seat interaction.** The facility anchor seat pins terrain(anchor) = datum. If
  Bridge_01's anchor sits inside the below-grade ramp extent, that 3×3 m plate stands as a pillar in
  the profiled cut. Probe the anchor position offline before building.

**Risk, stated plainly:** this is the largest item and it changes an emitter that four other
airports exercise (EGLL, EGKR, KBNA, EGGW tunnel fixtures). Gate it
(`O4_OBJECT_RAMP_PROFILE_FLOOR`, default ON per the ruling); a true cut-and-cover tunnel has a flat
floor and must keep one. `tools/attic/tunnel_trench_audit.py` assumes the flat-pan law — annotate it
or its deltas will read as defects.

### W3 — Terminal ramps (owner question, 2026-07-31)

The big terminal's small ramps connecting below-grade points to apron level get **no cutout today**.
Candidates from the sweep, with the datum caveat of §1 — these are drape-datum depths and must be
re-measured against local ground before any of them is carved:

    TerminalRoads_Parking_005  -9.09      TerminalRoads_03_005  -4.73
    TerminalRoads_02_004       -6.55      TerminalRoads_03_002  -3.76
    TerminalRoads_03_004       -6.35      TerminalRoads_02_002  -3.76
                                          TerminalRoads_Parking_002  -3.18

* **W3a — DONE.** Re-measured per structure against local ground, near-horizontal (deck/floor) faces
  separated from wall stubs. The method validates itself: every basin we already carve shows large
  sunken deck area, and every structure the owner calls above-ground shows ~zero.

  | structure | deck >1 m below LOCAL ground | deepest | verdict |
  |---|---|---|---|
  | **AuxBuilding_09 pool** (TerminalRoads / Parking) | **66,837 m²** | 7.79 m | **CARVE — the terminal ramps** |
  | AuxBuilding_17 (Dewatering_02) | 5,183 m² | 13.32 m | carved today |
  | AuxBuilding_13 (Dewatering_01) | 7,275 m² | 13.07 m | carved today |
  | Drainage_01…06 | 204–2,772 m² each | 3.8–4.0 m | carved today |
  | AuxBuilding_15 (Qatar Duty Free) | 252 m² | 2.62 m | carve — modest |
  | ControlPost_07 / 08, CorpOffice_01, CabinBase | 0–16 m² | 1.0–4.1 m | **no — stubs only** |
  | **Bridge_05** | **5 m² of 3,144** | 1.72 m | **no — above-ground, as the owner said** |

  This retires the drape-datum inventory outright. Qatar Duty Free is 252 m², not the −12.21 m the
  old method implied; Bridge_05's −5.32 m was a stub. **The real prize is the AuxBuilding_09 pool at
  66,837 m²** — the terminal ramps and underground parking, and much the largest uncarved
  below-grade area on the field.
* **W3b.** That pool is the mega-pool (2.5 M m² of face across 589 resources), so it cannot be
  carved as one body: it needs component extraction first, analogous to `_open_pit_components`.
  Per-component, the enclosure test then decides open trench (W2) versus R10 interior cutout (W6).

### W4 — The 8th tunnel: one merged trench instead of a system veto (owner ruling 5)

`bridges.py:1507` vetoes a whole tunnel system when it runs under/alongside another road
(`system_veto`, the LMML/CYUL "dense interchange, overlapping ramps" case). At OTHH this fires once:
the build logs *"skipped 1 tunnel(s) with an adjacent/crossing road (ramps not modelled)"* against 7
emitted clusters.

* **W4a.** First, **name it**: log the vetoed system's OSM way id(s), centroid lat/lon and extent at
  verbosity 1. We cannot fix what the log does not identify, and this is a one-line diagnostic.
  *(Note: `_n_adj_skip` counts WAYS, not systems or clusters — `bridges.py:1507`.)*
* **W4b.** Replace the veto for the *crossing-road-is-modelled* case with a single merged trench:
  union the system's bore corridors, take the below-grade extent, and emit ONE trench spanning it —
  "an extended trench at the bottom of the ramp" — instead of per-portal ramps that overlap. Reuse
  the low-connector open-trench idiom (`_synthesize_implied_crossing_bores`,
  `low_connector_max_gap_m`) rather than a new corridor-union emitter, and deconflict against
  `_classifier_owned_crossing_union` — the owner's "might be two objects" is a double-cut hazard.
* **W4c — the discriminator is UNDECIDED and must stay so until W4a reports.** ~~`excluded` at line
  1499 already computes it~~ is **wrong** (review finding 3): `excluded` is `_depressed_way_ids`
  from the through-airport depressed-road emit, `EMIT_DEPRESSED_ROADS = False` by default, so the
  set is empty in every default build — and it means "ways *our* emitter depressed", not "the pack
  models the crossing", which is what the owner means. Real candidates:
  `_classifier_owned_crossing_union(layout)` (pack-object-owned crossings, available pre-veto since
  the layout is in hand), the crossing OSM way's own `bridge=yes`/`layer` tags, or the pack DSF road
  network sidecar. Pick after W4a names the system.
* **W4d — add a synthetic unit test for the veto FIRST.** There is no test anywhere for
  `system_veto`; "LMML/CYUL fixtures" are 7-minute airport builds. A unit test is the cheap evidence
  the budget law wants before touching it.

**Verification:** ~~OTHH emits 8 clusters, not 7~~ — the veto counts ways, and a vetoed way's portals
may cluster as one, two, or merge. Better acceptance: **the vetoed way's below-grade extent is
trenched, and no emitted ramp overlaps the crossing road.** LMML/CYUL unchanged.

### W6 — R10 interior cutouts (R14's largest consequence — do not silently drop)

Spec R14 states plainly that it "makes ruling R10's interior cutout a requirement rather than a
design note… R14 is the instruction to build it." The measured set at OTHH is bucket B — 59
resources across 6 pools (Qatar Duty Free, TerminalRoads_Parking, Fuel_02, FuelFarm_01, GA_Hangar9,
HangarC). After W1–W4 those are still invisible. The input R14 was waiting on (the bridge ruling) is
now in hand, so the deferral needs to be either lifted or stated for owner sign-off.

Note the coupling to W3: the TerminalRoads pools are bucket-B members pooled with terminal
buildings, and whether a given ramp takes W2's **open** trench or R10's **interior** cutout (which
forbids carving pavement) is decided by the enclosure test
(`INTERIOR_CUTOUT_ENCLOSURE_MIN_FRACTION`). W3b's "they are ramps" hides a component-extraction
workstream analogous to `_open_pit_components`.

### W5 — Docs

R14 in `object_terrain_features_spec.md` §10 already carries the measurement law and the deck-end
corollary. Add: the W1 discriminator, the W2 profiled floor, and W4's narrowed veto once each lands.

---

## 4. Sequencing and budget

Ordered so each step is verifiable alone, cheapest evidence first:

1. ~~**W4a**~~ **DONE** — the 8th tunnel is service way `F|-172`, 10 nodes, 74 m end-to-end, centre
   25.254287,51.620925.
2. ~~**W3a**~~ **DONE** — terminal-ramp table published (§W3a above); the drape-datum inventory is
   retired and the prize is the AuxBuilding_09 pool at 66,837 m².
3. **W1** — **W0 + W1a + W1a-part2 DONE** (both wrong trenches retired, zero builds needed: every
   verdict was measured offline through the classifier). **W1b BLOCKED on a ruling** (see the boxed
   finding above). W1c/W1d fold into whatever W1b becomes.
4. ~~**W4d**~~ **DONE** — `tests/test_tunnel_system_veto.py`, 9 synthetic cases, 0.13 s. The veto
   now has a net, so W4b/c can be attempted without a 7-minute LMML/CYUL build per iteration.
5. **W4b/c** — contained in the portal walk. W4c's discriminator is now decidable (W4a has
   reported) but still UNDECIDED. One OTHH build + the LMML/CYUL fixtures.
6. **W2** — largest, gated, needs the tunnel fixtures byte-identical. One OTHH build + the four
   tunnel-fixture airports.

**Budget actually spent so far: ZERO airport builds.** Every W1 verdict came from instrumenting the
classifier on the installed packs (`tools/probes_bridge04_20260731/`, ~27 s per run). The plan
allowed one OTHH build for W1; it was not needed, and the probes stay as the cheap net.

**Budget:** OTHH full build ≈ 7 min each; `tests/test_object_*.py` + the bridges blast radius
(9 files) ≈ 3.5 min; full suite ≈ 8.5 min. Baseline to beat: 24F/3849P/18S, failure set unchanged.
Build-time law: time the changed function paired ON/OFF (2 pairs), never a whole-build A/B; the
0.6 s review line applies.

---

## 5. Open questions for the reviewer

1. ~~Is the W1 discriminator ("deck predominantly at or above local ground ⇒ bridge") the right
   shape, or should it key on the pack's own signal (deck hardness, `ATTR_hard_deck`) instead of
   geometry?~~ **ANSWERED BY MEASUREMENT, 2026-07-31.** Neither, as posed. *Hardness cannot be the
   key*: all six OTHH bridges carry zero hard triangles, so any hardness-keyed test is silent on
   exactly the structures the ruling is about. *"Predominantly" cannot be the key* either — a
   fraction test calls EGLL Tunnel/10 a bridge (128.7 m² above grade against 55.1 below). What works
   is an **absolute** floor on the near-horizontal area standing clear above grade, which is
   geometry, hardness-free, and separates the measured cases by 8× and 1.55×.
2. W2 changes a shared emitter. Is a separate ramp emitter safer than profiling the existing one?
3. Bridge_01 is *both* — an at-grade deck, a flyover, and a descending ramp in one object. Should it
   be split by the emitter, or should W1 and W2 both apply to different parts of the same body?
4. Does anything else consume `TunnelStructure.body_depth_m` / `solid_minimum_y_m` in a way that a
   profiled floor would break?
