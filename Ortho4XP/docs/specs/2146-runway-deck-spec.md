# Spec 2146-3 — the generated ELEVATED deck: a runway or taxiway that stands on a bridge deck for a whole end

Issue #2146 item 3. Owner RULINGS 2026-11-17n (with 16y, 17 "the pack always wins"). Draft by scout spec2146, 2026-11-17, on `origin/claude/ldeck3` 389d7fde2 (line numbers are that tree's). Extends spec `2123.md` Part A; nothing here names an airport — LPMA is where it was found and the closing test. Needs owner answers Q1–Q6 (§9) and prototype P0 (§8) before round 1.

Conventions: station `s` in metres from the 05 end along the apt.dat axis (length 2,784 m); lateral `t` > 0 = left of 05→23 = inland (NW).

## 0. Ground truth (measured by the scout from the corpus files unless marked)

- **OSM** (`OSM_data/+30-020/+32-017/+32-017_airports.osm.bz2`): runway −28 818 m `bridge=yes layer=2` (s 1,817–2,635); runway −101 148 m `bridge=yes`, NO `layer` (s 2,635–2,783); taxiway bridges −94 (179 m), −11 (158 m), −27 (270 m), all `layer=2`; −28, −101, −94, −11 share node 32.705852, −16.7651445.
- **Roads beneath**: service −238 564 m, −239 343 m, −195 281 m, −207 209 m, −249 133 m and 14 more, all `covered=yes layer=-2`; trunk −23 320 m, −1397 116 m, −44 91 m `covered=yes`; trunk −2549 / −2548 `bridge=yes covered=yes layer=1`. None is `tunnel=yes`.
- **DEM.** FABDEM inset (30 m): centreline 57.1 (s 1,800), 56.4 (2,100), 56.3 (2,200), 56.9 (2,400), 56.8 (2,780); nodata (sea) from t ≈ −30…−60 at s ≥ 2,100; inland t = +90…+150 reads 39–64. Base SRTM3: a 58 m plateau from t ≈ 0 to −120…−150, 0 beyond, 56–100 inland. Neither raster shows ground under the deck: "the terrain would have to rise" has no DEM witness here.
- **Coastline** (ways −38 / −50): t = −121…−135 at s 1,900–2,800. The platform lies seaward of the runway; inland it meets ground at about its own level.
- **Gateway apt.dat** (Global Airports, LPMA): the 23 end, its 151 m displaced threshold, one row-21 PAPI (32.70324, −16.76742, s ≈ 2,230) and one windsock lie on the deck. `gui_label 2D`, 8 rows 110.
- **Installed pack** (lane ldeck3, not re-measured): `runway23_area.obj` is a hard deck beside the runway (lateral −180…−30); the runway is drawn on the mesh.
- **Code today.** `structure_underpass.aeroway_decks` (:143-169) admits a taxied aeroway bridge only with its own `layer >= underpass_min_layer` (=1), so −101 is dropped. `underpass_bores` (:186) bores every road under the ribbon. `deck_generated` drops a road covered over `max_cover_m` 100 as a tunnel (:388-393, :212-216) and refuses a piece with no end PAIR (:469-472). `deck_pack_cover` (c) refuses beside a pack hard deck (:243-269). `_pack_refusal` refuses a Global-Airports-only airport (:338-346). `deck_runway_marks` draws no designator, displaced-threshold arrow or chevron (:13-14).
- **Corpus census** (121 airport extracts): 57 taxied aeroway bridge ways in 23 extracts; runway bridges only in +32−017; other chains ≥ 150 m: +35+139 two taxiway bridges of 625 m, +29−096 one of 161 m.

## 1. The witness (WHERE) — every number a `[deck_gen]` key (§7)

- **W1 CHAIN.** Taxied aeroway bridge ways (`is_aeroway_bridge`) that touch, grouped by `deck_generated._connected`'s union-find (shared, not copied). The chain's layer is its members' highest; a member with no `layer` takes it. Admitted at `>= [tunnel] underpass_min_layer`.
- **W2 RING.** `R` = the airport pavement inside each member's deck-cell ribbon (`_deck_cell`), grown `edge_margin_m`, one ring per connected piece. An END LINE is where pavement runs onto `R`. A route that ENDS inside `R` (a runway end on the deck) gives a FREE END: one end line is lawful. Airside pavement in the chain's window not in `R` is listed in the note (a finding, not a switch).
- **W3 HEIGHT.** Every `[bridge] abutment_sample_step_m` (5 m) along the chain, `H = T − G`. ELEVATED when `H >= elevated_min_m` over a run `>= elevated_min_run_m` and over `>= elevated_min_share` of its length; else it stays 2123's crossing deck.
- **W4 THE PACK ALWAYS WINS** (17n). The WHOLE chain is refused, by name, when `deck_pack_cover.pack_decks_near` reads a pack hard deck (flag or signature), a pack structure, or an elevated pack top within `elevated_pack_beside_m` of `R`. Global Airports alone is refused with the 16y (2) offer note. LPMA with the installed pack: refused; the patch equals the control (bar E-7).
- **W5 PRECEDENCE.** Elevated rings are derived first and handed to `generated_decks` as `taken`; a 2123 piece on one is refused by name.

## 2. The deck line and the ground under it

**2.1 DECK LINE `T`**: one plane, level across the route. End line A pinned on the window-blind chord (`constraints/deck_anchor`). Two end lines: the chord between them. A free end takes, in order: the CIFP threshold on the deck; under G2, the median DEM over the last `level_probe_m` of `R`; level. Rise clamped as `_tilt`. A chain whose anchors do not fit one plane inside the family cap is REFUSED by name.

**2.2 GROUND `G`**, a two-rung ladder.
- **G1 SURVEY.** The DEM under `R` already stands `>= elevated_min_m` under `T`: `G` = DEM, nothing edited.
- **G2 PLATEAU.** The DEM under `R` is within `plateau_tol_m` of `T`. Per DEM cell row across the route, in the chain's window: (1) walk each side through plateau cells out to `plateau_reach_m`; (2) a FOOT is the first cell that is water (`airport.dem.water_many`) or stands `>= elevated_min_m` under `T`; (3) the EDIT REGION `E` runs to the foot on a side that has one, and one DEM cell past `R` on a side that has none — ground is never lowered toward a side with no witness; (4) `E` never enters a standing cell, its zones, or water; (5) `G` on `E` is the Laplace membrane of its boundary, never above the DEM; (6) where a mapped road passes under `R` at `H < thickness_m + [tunnel] clearance_m`, `G` is lowered to that floor over carriageway + `shoulder_m`, banks at `[channel] bank_slope`; (7) W3 is asked of this `G`. No foot on either side: REFUSED, "no ground witness under the deck".
- **LPMA estimate** (FABDEM inset alone): `E` 24–31 ha, `G` under the centreline 7.7–32.9 m. The lane's FIRST output is this table on the Gateway capture.

## 3. The record and the derivation sites (one each)

- **New `planar/deck_elevated.py`**: `elevated_decks(airport, classification, law, objects, cache) -> (records, notes)`, called once at the top of `planar/build`, before `channels_after_basins`. Each record a `DeckBridge` with `witness="generated"`, `walls=()`, `floor_min_m=0`, `cut="none"`, one or two seat lines, plus `E`, `G`, free-end level.
- **SITE 1 — deck read.** `aeroway_decks` returns no way of an elevated chain (removes underpass bores, mouths, ramps, §45 (1) (a) channels in one place).
- **SITE 2 — ground.** `Airport.dem` wrapped once so `z` / `z_many` return `G` inside `E` (look for an existing overlay first). `E` less standing cells tiled into `graded_strip` cells `deck_under:<id>`, each vertex pinned at `G` by new `constraints/deck_under.py`. The corpus raster is never edited.
- **SITE 3 — pavement.** `carried_off` cuts the airside cells under `R` (unchanged).
- **SITE 4 — zones.** `classification.keepouts` gains `K` = `R` ∪ the axis over the chain's window ± the zone-2 half-width; `airport/end_area` reads length 0 for a runway end inside `R`.
- Build time: milliseconds.

## 4. Consumer census (RULINGS 2026-08-30l; "lane confirms" = on the capture, before editing that consumer)

| # | Consumer | Ruling |
|---|---|---|
| 1 | `aeroway_decks` → `underpass_bores`, `channel._aeroway_bridges`, `deck_generated._covered_roads`, `deck_bores` | TRIM at SITE 1; roads under the deck are open roads on `G` |
| 2 | road cells/rows under `E` (`road_yield`, `fill_road`, `lidar_road`, ramps) | read `G` via SITE 2; lane confirms no road above the soffit |
| 3 | `viaduct_road` R6, `reach_under_covers` | SAME (an aeroway bridge is no cover) |
| 4 | `covered_ground` (#714) | SAME for `covered=yes`; a mapped tunnel under an elevated ring stands down inside `E`; lane confirms |
| 5 | `deck_generated.generated_decks` (2123) | W5 |
| 6 | `deck_pack_cover` | REUSED for W4 |
| 7 | `carried_off` / `cell_knife` | SAME |
| 8 | `zones.zone_regions`, overlay holes | SITE 4 `K` |
| 9 | `airport/end_area`, `zones._runway_band`, `runway_axes` | SITE 4: length 0 for an end on the deck |
| 10 | `runway_chord`, `overlay._ridges_off_cuts`, `deck_anchor.deck_holes` / `blind` | SAME; lane confirms end-A chord moves < 0.05 m |
| 11 | `constraints/deck_anchor` | SAME at end A; EXTEND: a free end published, never pinned |
| 12 | `constraints/edge_deck` | rigid row only between two end lines; `deck_floor` skips `floor_min_m = 0`; lane confirms |
| 13 | `threshold_seam`, CIFP pins, `runway_profile`, `runway_step`, `transverse`, `strips`, `runway_mean_slope`, `runway_end_report` | act on the land part; `runway_mean_slope` counts the deck line; lane confirms or extends |
| 14 | `verify/runway`, `transverse`, `strips`, `deck_flush`; census families | no runway face in `R`; end A at `deck_flush_m` 0.04 |
| 15 | `constraints/water`, `planar/shore`, masks | SAME; `E` excludes water |
| 16 | `road_bridge_gen` / `_clear` / `_pack` | read `G`; 4.2 m under the soffit else refused; LPMA trunk −2549/−2548 lane reports |
| 17 | `planar/structures`, `deck_bridge.deck_ground` | `cut="none"`; lane confirms no mouth adopts it |
| 18 | `generated_publication`, `publication.deck_anchors`, `planar_report` | publish ring, zero, tops, free end, `E`, `G` |
| 19 | `rebake_inputs._deck_plate`; `airport/deck_riders` | EXTEND riders: pack object inside `R` seats on the deck top; inside `E` reads `G` |
| 20 | object stage (`generated_pack.recipe`, `deck_objects`, `deck_obj8`, `deck_structure`, `deck_runway_marks`, `apt_flatten`, `dsf_poly_clip`, `dsf_write`) | EXTEND per §6; row 100 never edited |
| 21 | `drawn_site` / `drawn_gate` | EXTEND with bars E-1…E-4; objects layer must measure the deck |
| 22 | reachability (`routes`, `reach_after_pads`) | route runs through the deck; lane confirms no flip to groundside at end A |
| 23 | `front_cache`, provenance, law digest | new keys/modules enter the digests |
| 24 | `tile_bundle`, `patch_library` | NOT VERIFIED (open since 2123 §10) |
| 25 | Mac app and Qt window | no control added |

## 5. Is it emittable?

- **Mesh: yes.** `G` single-valued; the deck an `ATTR_hard_deck` OBJ8 over it (2123 A3's model, drawn at ESSA).
- **X-Plane: NOT PROVEN at this scale.** X-Plane drapes row 100 (runway, markings, lights) and rows 19/20/21 on the mesh: under an elevated deck they draw on the ground below (at LPMA the last 966 m, the 23 threshold, a PAPI). Row 100 cannot be shortened. So the deck redraws its own surface, markings and lights (§6); rows 19/20/21 in `R` move onto the deck as objects and leave the pack copy's apt.dat (Q5); X-Plane's draped copy stays under the deck (Q2).
- **P0 must show**: an aircraft starts and lands on the deck at a runway end; Laminar light objects light as runway lights; the PAPI reads right; the draped copy below is acceptable. If P0 fails, stop and report.

## 6. The object (2f478ce3d's structure, 82e8407f9's markings; Laminar-first)

- Slab, beams, edge beam, kerbs, joints, two LODs: `deck_structure.structure_parts` unchanged. A free end is a side edge.
- **Segments**: one plane, written as objects ≤ `segment_m`, each its own `OBJECT_MSL` row.
- **Supports**: a bent every `bent_span_m` (cap beam 1.5 × 1.2 m); octagonal columns ≤ `bent_col_gap_m` apart, each to its own `G(x, y) − pier_foot_m` (or water level − `pier_foot_m`); width `max(pier_col_m, height / pier_slender)`; none on a mapped carriageway + `shoulder_m`.
- **Surface**: unchanged (`deck_pavement`, `deck_skin`, rubber strip, taxi lights).
- **Runway markings**: `deck_runway_marks` per segment; NEW for a runway end in `R`: designator, displaced-threshold arrows and bar from the same atlas.
- **Runway lights** (new `airport/deck_runway_lights.py`): from row-100 codes, X-Plane's own `lib/airport/lights/slow/` exports (`MIRL_*`, `RCLS_*`, `thr_*`, `TDZL`, `REIL_*`, `PAPI`) on the deck top. Approach lights beyond the deck out of scope.

## 7. Law keys (`structures.toml [deck_gen]`; all proposed)

| Key | Default | Meaning |
|---|---|---|
| `elevated_min_m` | 6.0 | W3: `thickness_m` 1.0 + `[tunnel] clearance_m` 5.0 |
| `elevated_min_run_m` | 100.0 | W3: = `max_cover_m` |
| `elevated_min_share` | 0.5 | W3 |
| `elevated_pack_beside_m` | 30.0 | W4 (Q4) |
| `plateau_tol_m` | 1.5 | G2 |
| `plateau_reach_m` | 200.0 | G2 |
| `segment_m` | 120.0 | §6 |
| `bent_span_m` | 30.0 | §6: = `pier_min_span_m` |
| `bent_col_gap_m` | 12.0 | §6 |
| `pier_slender` | 15.0 | §6 |

Grade caps for decks per owner 2026-11-17T20:43Z (#2144): rail 3.5 %, road 10 %; pier foot stretch ≤ 3 m.

## 8. Tests and plan (synthetic first; one closing build)

- **P0 — X-Plane prototype** (Opus, low, no engine change, no tile build): with the existing writers, a ~300 m hard-deck slab 10 m over one runway end in a COPY of an installed Gateway pack, with lights and a PAPI. Owner checks §5's four items in 5 minutes.
- **H1 — harness arm** (Opus, low; beside P0): `build_airport.py` and `v2_solve_replay.py --capture` gain `--without-pack NAME` (declared and recorded like `--data-overlay`); `tools/INDEX.md` row and twin. The arm also needs the airport's Gateway pack in the pack copy (#1989 install, or the 16y (2) offer extended).
- **R1 — planar and solve** (Opus, high): twins in `tests/auto_patch_v2/test_deck_elevated.py` (chain/layer inheritance, jet_bridge refused; G1 valley 20 m elevated / 3 m not; G2 plateau with sea one side, no foot REFUSED; W4; free end; W5; SITES 1 and 4). Replays: ldeck3/LPMA.pkl `--from planar --emit --verify` refused by W4 and equal to control; ESSA and the +29−096 / +35+139 captures no mover > 0.1 m; Gateway capture: §2.2 table first, then emit/verify clean.
- **R2 — object stage and gate** (Opus, medium): twins for bents, segments (shared plane within 1 mm), lights table, designator/arrows, apt.dat row filter (rows 19/20/21 in `R` dropped and recorded; row 100 byte-identical). ONE closing build: `build_airport.py LPMA --tile 32 -17 --pack-copy DIR --without-pack "<custom pack>"`, then `drawn_gate.py` at abut=32.700608,-16.771266, mid=32.7040,-16.7670, end23=32.7068045,-16.7640141 `--against <control>`. Bars: E-1 end A flush ≤ 0.04 m; E-2 drawn mesh under `R` ≥ 6.0 m under the top at ≥ 50 % of stations and never above; E-3 every column foot at or below the drawn mesh by ≤ `pier_foot_m` + 0.5 m; E-4 gate PASS, no MOVED outside `E` ⊕ 50 m; E-5 110 area inside `R` ≤ 1 m², row 100 unchanged; E-6 Log.txt clean; E-7 the pack arm generates nothing and equals its control; E-8 owner sim read.
- Briefs say: never raise the lane cap; delete your scratch builds when you report.

## 9. Owner questions (recommended default first)

- **Q1** Ground under a deck the elevation data reads as ground: (a) infer it from the plateau's foot (sea or lower ground) and lower the mesh (G2) — recommended; (b) generate only where the survey already shows low ground (LPMA then generates nothing).
- **Q2** X-Plane still draws its runway and lights on the ground under the deck, hidden from above: accept, with the deck redrawing surface, markings and lights (recommended; decide at P0), or keep a terrain core under the pavement and dress deck edges and supports around it.
- **Q3** Deck width: pavement + 1.5 m (recommended) or the whole structure the data shows (~150 m at LPMA).
- **Q4** A pack hard deck or structure within 30 m beside the elevated pavement refuses the whole chain: yes (recommended).
- **Q5** PAPI, windsock, signs on the deck: move onto the deck as objects and drop their rows from the pack copy's apt.dat (recommended), or leave them at ground level below.
- **Q6** Testing the Gateway half: harness `--without-pack` + #1989 Gateway install in the pack copy (recommended), or the owner builds in the app with the pack disabled.

## 10. Not verified

X-Plane behaviour (draped runway and lights under a deck, light/PAPI objects as placed objects, start position on a hard deck, AI traffic — P0 settles these); ldeck3's pack measurements (not re-read); the production DEM composite at LPMA (estimate is FABDEM inset alone); every "lane confirms" census row; zone-2 half-width and RSA numbers for LPMA's code; whether `--pack-copy` can receive a #1989 Gateway install; `tile_bundle` / `patch_library`; Q3's wide option has no general witness (hull of the `covered=yes` ways is an unmeasured candidate).

Found in passing: runway way −101 is `bridge=yes` with no `layer`, so `aeroway_decks` drops it today; a deck with one end line is refused today (`deck_generated.py:469-472`); `deck_runway_marks` draws no designator or displaced-threshold arrows.
