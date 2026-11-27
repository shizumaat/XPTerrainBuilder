# The building envelope — spec for the owner law of 2026-11-27 (pack objects)

Fable scout `lenvelope`, 2026-11-27, design only, read-only. Destination `docs/specs/building-envelope-20261127.md` (the master commits). Code read at `0979b3c8a` (`origin/claude/project-thread-ddpu46` as briefed; the branch tip has since moved to `7323a7052`, which touches only `planar/short_bore.py` and `planar/structures.py`). All `file:line` below are `Ortho4XP/src/auto_patch_v2/…` at `0979b3c8a`. Starts from the census `XPTerrainBuilderData/.harness/findings/lobjcensus-20261127-findings.md` (rows P1–P16) and builds on lane `lfilecache` (per-file readings store, kinds `skirt`, `base`, `deck`, `terrain_shape`, `outline`: `airport/file_readings_code.py` in that lane's worktree); nothing here re-does that lane's work.

## 0. The law and the design in ten lines

OWNER LAW (text for the master to record; proposed id 2026-11-27h, the next free id at `7323a7052`). Owner 2026-11-27, as relayed by the master, verbatim: 21:07Z/21:11Z "we should only be identifying separate buildings that need to be split so they can be seated, we don't want to spend any time analyzing small components inside a group that all moves together"; 22:07Z "objects inside another object should always move with the containing object"; 22:34Z "I can't think of a case where even a tunnel or door well would move independently of a building it was placed with."

1. A BUILDING is found once, at load, from WALL PIECES only: the plan cover of every solid piece standing `[placement] chain_min_height_m` (2.5 m) or more, connected on a `footprint_touch_m` (0.5 m) lattice, its roofed enclosures filled (§2).
2. A piece lying `contents_min_fraction` (0.95) or more inside one building's plan is INTERIOR, whatever file, placement or anchor it belongs to, and WHATEVER IT IS: a chair, a floor, a basement, a tunnel, a door well, a wall, a jetway root. It is never analysed alone: no contact test, no body, group, cluster, connector, underside map, skirt reading, foot row, relief offset or seat of its own. MOTION HAS NO EXCEPTION: a building has ONE vertical shift and every contained piece takes it, at its authored offset (§5).
3. The pieces of one placement in one building are ONE body by membership (a "slice"); the slices of one building are ONE group and ONE footprint unit; per anchor they are ONE cluster with ONE envelope (§3: the 25m underside map of the whole building, plus outline, feet and skirt).
4. Everything OUTSIDE every building keeps today's law unchanged (bodies by contact, leaves on their own ground or carrier, decks, lines, scatter).
5. The only thing that still looks under a building is OUR TERRAIN: where a building holds a below-grade opening (a road under it, a door well, a pit, a wall corridor) the ground must be cut for it. That is a reading of the envelope's LOW layer (§6), never a seat. Where the terrain was cut for a contained piece, the building keeps the zero that cut was made for (today's `adapted_riders` rule): the datum ties seat and terrain together, the pieces never move apart.
6. Nothing here is new machinery in kind: the walled chain (14ah), the spanning sheet (27a), contents (18q/18t S6, `airport/contents.py`), "the perimeter/wall objects determine the seat, everything else moves with it" (22b), "everything inside a building moves with the building" (19f) and the underside map (25m/25n) already say it piecewise. The change is that the building is decided FIRST and cheaply, and that the per-piece work it makes unnecessary is not done.

Measured on seven captures (§1): the split classes 72 % / 83 % / 64 % of the solid pieces as wall or interior at KMCI / KATL / RJTT, skips 69 % / 77 % / 46 % of the contact pairs, and folds 53 % / 62 % / 46 % of today's clusters and 70 % / 78 % / 57 % of today's groups into buildings.

## 1. What the captures say (measured, read-only)

Scripts `scratchpad/envspec/scripts/{envcensus,envregions,envroof,table,rooftable}.py`, outputs `scratchpad/envspec/out/*.json`. They load a `v2_solve_replay --capture` pickle and rasterise `Part.rings` (else `Part.box`) at 0.5 m; no build, no replay. Captures: `frames/lpackobj/{KMCI,RJTT}.pkl`, `frames/lvec/KATL.pkl`, `frames/lkege3/KEGE.pkl`, `frames/l2203/{BIKF,OMDB,LGAV}.pkl`, read under the session worktree `84d554495`. APPROXIMATIONS: outlines are today's outward-simplified rings, not triangles; wall = piece-level `height_m >= 2.5` and not `member_is_deck`; the sheet merge (B5) and the same-placement join (B7) are NOT applied in these counts, only counted; pairs are box pairs (as the census's `pairs.py`); the table still applies S6's two refusals (a deck; a body below −2.5 m), which §5 repeals — the contained ones then move from EXTERIOR to INTERIOR: KMCI 3,117 pieces, RJTT 519, CYYZ 27, OMDB 15, LEMD 7 (`*.contained.json`).

| | KMCI | KATL | RJTT | KEGE | BIKF | OMDB | LGAV |
|---|---:|---:|---:|---:|---:|---:|---:|
| pieces | 81,226 | 124,467 | 27,884 | 2,809 | 7,241 | 8,844 | 14,353 |
| line / scatter (already out) | 11,124 / 9,821 | 5,057 / 41,643 | 118 / 0 | 2 / 283 | 1 / 2,930 | 880 / 337 | 290 / 2,897 |
| WALL pieces (seeds) | 11,142 | 22,862 | 5,096 | 399 | 625 | 4,705 | 1,851 |
| INTERIOR pieces | 32,300 | 41,351 | 12,661 | 1,905 | 3,104 | 2,181 | 1,475 |
| EXTERIOR pieces | 16,839 | 13,554 | 10,009 | 220 | 581 | 741 | 7,840 |
| — of which partly inside (< 0.95) | 5,264 | 4,686 | 997 | 92 | 262 | 420 | 1,385 |
| — refused: deck member / authored below −2.5 m | 57 / 3,719 | 1,166 / 261 | 4,501 / 12 | 0 / 0 | 0 / 0 | 40 / 2 | 479 / 116 |
| triangles wall / interior / exterior (k) | 1,015 / 1,469 / 647 | 1,524 / 2,264 / 1,179 | 2,959 / 4,075 / 4,314 | n/m | n/m | n/m | n/m |
| lattice regions (all / ≥ 100 m² / ≥ 5,000 m²) | 1,866 / 108 / 17 | 1,367 / 148 / 30 | 430 / 186 / 25 | 61 / 28 / 4 | 124 / 62 / 6 | 1,275 / 211 / 39 | 863 / 79 / 10 |
| today's walled clusters with rings / any / ≥ 5,000 m² | 432 / 848 / 43 | 347 / 709 / 47 | 316 / 448 / 51 | 38 / 55 / 6 | 74 / 105 / 8 | 723 / 780 / 115 | 440 / 750 / 37 |
| today's walled clusters whose pieces fall in 2+ regions | 94 | 90 | 10 | 0 | 1 | 119 | 19 |
| regions holding 2+ of today's walled clusters | 19 | 21 | 17 | 0 | 3 | 45 | 34 |
| same-placement bodies bridging 2 regions (B7 would join) | 153 | 114 | 16 | 3 | 6 | 66 | 21 |
| bodies with pieces inside and outside / exterior pieces they attach | 694 / 4,329 | 789 / 3,038 | 140 / 1,482 | 22 / 183 | 60 / 500 | 196 / 278 | 532 / 1,353 |
| placements cut by building (in 2+ regions) / solid placements | 178 / 384 | 261 / 2,012 | 48 / 1,057 | 5 / 67 | 25 / 78 | 71 / 157 | 83 / 154 |
| interior pieces of another anchor / regions spanning anchors | 177 / 4 | 155 / 6 | 10 / 6 | 0 / 2 | 0 / 1 | 0 / 4 | 11 / 1 |
| bodies today → folded into buildings | 46,534 → 21,525 | 58,960 → 30,740 | 8,009 → 4,306 | 296 → 74 | 563 → 344 | 4,930 → 3,343 | 4,360 → 1,047 |
| groups today → folded | 29,690 → 20,932 | 38,858 → 30,239 | 7,560 → 4,302 | 118 → 72 | 457 → 344 | 3,780 → 3,176 | 3,011 → 1,034 |
| clusters today → folded | 17,662 → 9,331 | 22,244 → 13,685 | 6,585 → 3,020 | 88 → 0 (*) | 290 → 185 | 1,349 → 826 | 2,690 → 564 |
| box pairs inside one building (same / other placement) | 106,958 / 324,514 | 75,836 / 178,768 | 39,698 / 25,160 | 5,243 / 2,646 | 9,823 / 9,246 | 7,649 / 12,272 | 2,742 / 1,433 |
| box pairs between two buildings / with an exterior piece | 21,793 / 175,995 | 2,823 / 72,146 | 4,445 / 70,673 | 41 / 806 | 10 / 2,521 | 1,814 / 9,904 | 920 / 31,823 |
| share of pairs never tested | 69 % | 77 % | 46 % | 90 % | 88 % | 63 % | 11 % |
| foot rows / of them from folded groups | 13 / 12 | 219 / 27 | 336 / 0 | 2 / 2 | 0 / 0 | 3 / 3 | 0 / 0 |
| pad-relief offsets / from folded groups (largest, m) | 418 / 233 (2.38) | 177 / 120 (1.33) | 228 / 157 (2.0) | 10 / 9 (0.02) | 0 / 0 | 32 / 16 (2.56) | 60 / 22 (0.43) |

(*) KEGE's capture is `011e3cc55` (11-17); its cluster `pids` did not map onto the partition under today's code, so the cluster rows for KEGE are not usable.

Five readings that shape the design:

- F1. Today a material-split terminal is not one building, it is a STACK of clusters: one KMCI lattice region holds 27 of today's walled clusters whose floors run −14.06…+19.51 m, another 20 (−9.37…+12.0); KATL's largest region (271,840 m²) holds 25 (−4.66…+29.52). That is 14x's floor split (`placement_family._floor_split` :529) applied to walled bodies that are single material sheets. In plan they are one footprint (13bo: "always keep objects covering the same footprint together").
- F2. The walls alone already cover the interiors: filling only ROOFED holes instead of every covered hole changes the interior count by 340 of 34,700 at KMCI and 26 of 39,086 at KATL (`*.roof.json`). The fill matters for safety, not for reach: KMCI has three unroofed enclosures of 41,541 / 38,919 / 19,485 m² (cover 0.00–0.01) and KATL one of 46,745 m² (0.22) that an unconditional fill would turn into "buildings".
- F3. Seeding from wall PIECES splits what a placement's own touching pieces hold together (153 / 114 / 16 bridging bodies; 4,329 / 3,038 / 1,482 exterior pieces attached through a body). 10i (1) must survive at the building's edge: B7.
- F4. Placements ARE cut by building: 178 of 384 solid placements at KMCI lie in two or more regions (material sheets), 261 of 2,012 at KATL. The file cut cannot go away; its unit becomes (placement × building) instead of (placement × contact body).
- F5. Certified airports: the pieces that fold feed 2 of 2 foot rows at KEGE and 3 of 3 at OMDB, and 9 of 10 / 16 of 32 / 22 of 60 pad-relief offsets at KEGE / OMDB / LGAV, the largest 0.02 / 2.56 / 0.43 m. OMDB is where the 0.5 m bar is at risk; BIKF has none.

## 2. Finding the separately seated buildings (`airport/building_split.py`, new; lattice helpers in `geom/`)

One pass, plan-wide, at load, between `contact.placed_parts` (:611) and the weld loop of `contact.partition` (:1313). Inputs it already has: every placed piece's points and triangles, its solid height (`contact.solid_height` :523), whether it has ground feet, and its member's line / scatter / deck verdicts (`pack_partition._build_member` :500–:528). It reads no DEM and no planar product, so it is cached with the partition.

Classes of a solid piece (line and scatter pieces are out, as today):

- WALL piece: `solid_h >= [placement] chain_min_height_m`, its member not a deck of a BRIDGE frame (22b (2): `placement_family.member_is_bridge_deck` :378 — the object stage's reading, now the one reading; see Q4).
- every other solid piece is a CANDIDATE, classed below as INTERIOR, ATTACHED or EXTERIOR.

Steps (each is one vectorised numpy / `scipy.ndimage` operation; no shapely union, no per-piece Python work beyond bookkeeping):

- B1 THE LATTICE. Cells of `footprint_touch_m` (0.5 m), aligned to multiples of the cell in the airport's entry frame (the alignment `geom/underside_map._grid` :168 uses), so the same pack on the same frame gives the same cells on every machine and in every process. Dense grids are per BOX GROUP (wall pieces whose plan boxes come within three cells, by union-find), never the whole airport.
- B2 THE WALL RASTER `W`: every cell a wall piece's plan projection touches. Triangles with plan area are filled by SUPERCOVER (a cell is marked when the triangle meets it, not only when it holds the cell centre — `rasterise_layers` :180 samples centres and misses thin walls); a triangle with no plan area marks the cells its longest edge crosses (`contact.plan_hull` :366's reading of a wall seen from above).
- B3 THE COVER RASTERS, same pass over every solid piece: `C` (any solid) and `R` (a solid whose top stands `chain_min_height_m` or more over the lowest wall foot of its box group: a roof or an upper floor). The per-piece cell sets are kept as (piece, cell) pairs for B6.
- B4 ROOFED ENCLOSURES. A hole of `W` (a 4-connected background component that does not reach the grid edge) joins the building when `R` covers `[basin] basement_cover_min` (0.9) of it — 19f's ROOFED measure. An unroofed enclosure (a walled yard, a fenced apron, a pit ring) is NOT a building's inside (F2).
- B5 BUILDINGS = the 8-connected components of `W ∪ roofed holes`. Guarantee: two wall footprints less than 0.5 m apart are ALWAYS one building (today's `footprint_touch_m`, in 14j's safe direction: never split what touches); more than 1.41 m apart they are ALWAYS two; in between the lattice decides, the same way on every run. (A 0.25 m cell with a two-cell link narrows that band to 0.5–1.06 m at four times the cells; the lane measures both at stop 0 and the master picks.)
- B6 SHEETS (27a (1), `sheet_chain.sheet_links` :139 restated on the lattice): a candidate that is no deck, has no ground feet and is not authored wholly below `contents.CONTENTS_BELOW_M` (2.5 m), and whose cells overlap two or more buildings by `sheet_chain_min_fraction` (0.5) of the SMALLER of (sheet, building), joins those buildings into one and becomes interior. Over one building it links nothing.
- B7 INTERIOR (S6, `contents.attach_contents` :100 restated): a candidate with `contents_min_fraction` (0.95) of its cells in ONE building. NO REFUSAL (owner 22:07Z / 22:34Z): S6 today refuses a deck (`contents.py:162`, :185) and a body whose lowest piece is authored below `-CONTENTS_BELOW_M` (:165; the body's base is its lowest piece, `footprint_unit.py:710`) — both refusals are REPEALED for motion. Such a piece still never SEEDS or JOINS buildings (it is no wall piece and no B6 sheet), and what it means for the ground is §6's question. The test is plan-only, as S6 is (F.9: "anything that intersects the building … moves with it"); across anchors it is the same test (KMCI 177 pieces, KATL 155).
- B8 ONE PLACEMENT'S TOUCHING PIECES (10i (1) at the edge). After the narrow pass (§4.1 says which pairs it still tests): an exterior piece in ε-contact, inside its own placement, with a piece of building `k` is ATTACHED to `k`; a same-placement contact component that reaches two buildings joins them. This is the only contact reading the split needs, and it is over pairs that involve an exterior piece.
- B9 IDS AND ORDER. A building's id is the smallest part id among its wall pieces; buildings are listed in id order. Joins (B6, B8) keep the smaller id. Nothing depends on dict order, pool size or worker count: B1–B7 run in the parent on the placed arrays; the pool's order-free narrow verdicts (`contact.narrow_ahead` :1208) feed B8 through the existing replay.

The record on the partition (`PackPartition.buildings`, new field beside `contacts` :146): `{part id: building id}` for wall, interior and attached pieces, and per building its anchors, wall part ids and lattice outline. Everything else is derived from it.

What a split is, after this: a placement is cut where it crosses a building's edge (F4), where its exterior pieces do not touch (today's law), and where a pad is cut into flat blocks under a building (30r C16, `pad_block_seat.sever` :197, by block membership). Never by which interior pieces happen to touch.

Cost: my census script rasterised the wall rings in 4.3 s and classified 60,281 pieces in 9.9 s at KMCI in per-piece Python with shapely; `unit_underside` rasterises all 3.0 M static triangles of KMCI's 10,061 maps in 10.4 s serial-profiled (census P13). Estimate for B1–B7 from triangles: 5–10 s serial at KMCI and KATL, less at RJTT's 27,884 pieces but 11.4 M triangles (≈ 15 s). Memory: one bool and one int32 grid per box group; KMCI's whole plan is 13,935 × 7,798 cells (109 M) and the script held it in under 1 GB; per box group it is tens of MB.

## 3. The envelope record

One per building per anchor that holds wall pieces of it, and — unchanged — one per exterior cluster with a grounded part. It IS `geom/underside_map.UndersideMap` (:130), population changed in `unit_underside.unit_population` (:64) and `_derive` (:297), with four additions. Nothing is duplicated: the layers come from the rasteriser that exists.

| part of the record | what it is | where it comes from |
|---|---|---|
| PERIMETER | `outline` (new): the building's plan rings, the lattice region polygonised and simplified OUTWARD (`contact._outward` :260, 14j); the stations `e, n, lo, hi, h, kind, levels_k, airside` on the boundary of the ground-contact plan `P` | B5 region; `underside_map._stations` :358 |
| UNDERSIDE / FEET | layers `foot`, `tread`, `floor`; scalar `t` (the floor its airside contacts stand at, 25n (2)), `base`, `relief`, `flat`; `feet` (new): the perimeter stations' contacts thinned to one per 2 m of perimeter (a law key, `[envelope] foot_spacing_m`; no number in code), as `(lat, lon, y)` rows | `rasterise_layers` :180 over EVERY piece of the building (wall, interior, attached); feet from WALL pieces only (22b; F.4) |
| TOP | layer `top` | same pass |
| LOW (below grade) | layer `low`; `interiors` (open / roofed, floor, cover, cells); `low_min` (new): the lowest solid under `t` | same pass; `underside_map._interiors` :424 |
| SKIRT (new) | `skirt_fraction` = share of the perimeter length whose stations are kind `skirt`; `skirt_depth` = the smallest `hi − lo` over them | stations (`SKIRT_M` 0.3) |
| LEVELS (stop 4 only) | `plates`: per decimetre level, the plan cells of near-horizontal up-facing surfaces | same pass, one more histogram |

Passes that read ONLY the envelope for a building (never its pieces):

- the seat: `underside_seat.seat_records` (:296), `footprint_unit.plan_unit_datums` (:866) / `_wall_base` (:1108) — one zero per building (25m (4), 22b);
- perimeter grading and cut-outs: `unit_perimeter.perimeters` (:214), `perimeter_grade` (:52), `unit_storey._contact_level` (:472) — as 25n step 2/3 built them;
- the cluster and its pad: `placement_family.plan_clusters` (:560) takes `rings` from `outline`; `geom/cluster_outline.cluster_outlines` (:372), `classify/evidence._cluster_pads` (:584), `constraints/cluster_pad.cluster_polys` (:119) read the cluster as today;
- the group: `planar/group.derive` (:360) takes the building's `feet` and `t`; `constraints/foot_rows.foot_targets` (:263) and `constraints/pad_relief._foot_offsets` (:231) read the group as today;
- the skirt: `Member.skirted` per slice (`pack_partition.py:528`), `classify/evidence._drop_skirted` (:1215);
- the sidecar: `pipeline/underside_publication` (:59).

## 4. How each ruling changes, exactly

Scope word for every row: "inside a building" = wall, interior and attached pieces of one building (§2). Outside it, each ruling stands as written.

| ruling | says today | after |
|---|---|---|
| 2026-09-10i (1) | a contact edge inside one authored placement is never cut: one touching body, one delta; several deltas only across a physical separation | a placement's pieces in one building are one body BY MEMBERSHIP: no touch is tested between them, and pieces of it that do not touch are still that one body. A placement has several deltas only (a) across buildings, (b) between a building and exterior pieces of the placement that touch none of its pieces there, (c) among its exterior pieces, by today's test, (d) at a pad-block line (30r). An exterior piece touching a building piece of its own placement stays in that body — (1) is KEPT at the building's edge (B8). |
| 2026-09-10i (2) | a body's delta is founded on feet across it, every ground-contact component contributing, the median taken; a wide body with too few feet samples the surface under every ground-contact component | a building's delta is founded on its WALL pieces' contacts alone, read as the envelope's `t` at its perimeter stations (22b: "we only need to check the perimeter/wall objects"; 25n (2)). Interior pieces found nothing and report no residual. Exterior bodies unchanged. (3) and (4) unchanged: decks and plates of deck families are never interior. |
| 2026-09-11a (2nd bullet) / 10i "buildings never group with buildings across placements; each seats on its own feet" | every body is its own group unless it is an elevated deck abutting a kerb (`group.py:446`, `refused_building` 8,557 at KMCI) | the slices of ONE building are ONE group, whatever placements they come from (the contained objects the brief names). Between two buildings, and between a building and an exterior body, 11a stands: never grouped, except the elevated-deck junior, whose senior is now the whole building. 11a's first bullet (multi-anchor rows seated by DSF elevation) is untouched. |
| 2026-09-14ah (4) | a thin body is a LEAF: seated on its own ground or its carrier, never a link between two walled bodies | "never a link" STANDS and is now the definition of a building (only wall pieces seed and connect; 27a's spanning elevated sheet is the one exception, B6). "Seated on its own ground or its carrier" stands only for a leaf OUTSIDE every building. A thin piece inside one is interior: no cluster, no seat, no ground of its own. (S6 already said this in the object stage; it now holds at load and on the design surface, where `plan_clusters` stops minting leaf clusters inside buildings: 9,331 / 13,685 / 3,020 at KMCI / KATL / RJTT.) 14ah (5) (a derived pad never takes airside ground) is untouched. |
| 2026-09-10af | foundation vs corridor is a property of the OBJECT'S below-zero geometry: skirt when the below-zero perimeter is at least `corridor_skirt_fraction` of the footprint's perimeter, read per FILE (`skirt.is_skirt` :278) | read per BUILDING from the envelope: skirt when `skirt_fraction >= corridor_skirt_fraction`. A material sheet is not a building and is no longer asked (KMCI: 67.3 s serial for 19 skirted members). A placement with no piece in any building keeps the per-file reading (cached by `lfilecache`). An exterior body of a placement that also has slices is never skirted. Law C's narrow-cut clause (d)(ii) reads the building's fraction. |
| 2026-09-10ag | a skirted building needs no pad while the relief across its footprint ≤ s; the rebake seats a skirted body at its low-side foot | the same two rules, asked of the building: `_drop_skirted` reads `outline` and `skirt_depth`; every slice of a skirted building seats at the building's low-side contact. A basin member is never skirted (10ax (2)), unchanged. |
| 2026-09-11j | the unit of the relief target is the BODY: `surface(foot) = level + (y_foot − y_zero)` per foot | inside a building the unit is the BUILDING: its feet are the envelope's perimeter `feet`, its zero is `t`. An interior piece founds no relief target (17h (1) "objects inside a building never pull terrain up", now for pads too). Exterior bodies unchanged. |
| 2026-09-11x (1)–(3) | foot rows fire all-or-nothing per body; feasibility is the fit's own residual between neighbouring feet; basin bodies are out | the same three rules with the building as the body: its rows fire only if every perimeter foot is on-sheet and the fit over them is feasible. Interior pieces issue no row. |

Also changed, NOT in the brief's list — the master should record or refuse them (Q1–Q4):

- 14x §16g (10) (1), the FLOOR SPLIT: retired inside a building. One plan footprint is one building (13bo); a split-level building's levels are its envelope's levels and its pad blocks (30r), never separate clusters stacked in plan (F1).
- §16g (9) ONE POPULATION becomes true: `plan_clusters` chains per anchor (`placement_family.py:645`), `plan_units_and_connectors` plan-wide (`footprint_unit.py:598`). After: one building (plan-wide) is the object stage's unit; its per-anchor part is the design surface's cluster. A touching building at another anchor does NOT merge clusters on the design surface by this spec (no pad merges at KATL's 548 anchors); pieces of another anchor that lie INSIDE a building ride it and mint nothing.
- 27a (1) and S6 (18q/18t F.2) are restated on the lattice (B6, B7) with their numbers unchanged; 22b (2)'s bridge-frame deck test becomes the one deck test for the wall chain on both sides.
- S6's two refusals (a deck; a body authored below −2.5 m) are repealed for motion (B7, §5). 13r (the free rider) is the one owner-ruled independent seat of a contained piece; 22:07Z "always" reads as repealing it — Q1.

## 5. Motion: every contained piece moves with its building — the proof asked for at 22:34Z

THE RULE. A building has ONE vertical shift δ. Every piece contained in it — interior, wall, attached; a tunnel, a door well, a retaining wall, a jetway root, a basement; in the building's own file or another placement's, at its anchor or another's — is written at its own rendered zero plus δ. No contained piece has a shift of its own, and no reader in §6 may give it one.

WHICH δ (the datum; unchanged law, stated once): (i) where our terrain was cut for a piece of the building (a terrain-adapted member, `pack_partition.Screen.excluded` :103; a pit group, 27f; a structure-seated plate), δ is the one that cut was made for — for a terrain-adapted member δ = 0, the rendered zero (`airport/adapted_riders.py` module doc: owner sim read KMCI 1.0.480, 2026-11-10T15:47Z, "the art is at the right spot, and the terminal is too low"); (ii) else the building's own datum by 13bo (2) — deck, pad, ground — read at the envelope's `t` (25n (2)). The cut and the seat are tied by the datum. They are never reconciled by moving a piece apart from its building.

CAN A CONTAINED TUNNEL OR DOOR WELL RIGHTLY MOVE ON ITS OWN? I found no case. Every on-screen instance on record of a contained piece moving apart from its building was read as a defect and fixed:

| where | what moved apart | how far | record |
|---|---|---|---|
| KMCI terminal, 39.2979, −94.7188 | the terminal frame against the sunken road and wall corridors cut for it | 308.76 vs 310.73 (1.97 m) | owner 2026-11-10T15:47Z; `adapted_riders.py` module doc |
| KBWI | interior and skylights over the terrain-adapted shell | 0.41 m | #1726, owner sim read 2026-11-03 |
| KATL | roofs (`techo1.obj`) into the hall whose walls (`pared1.obj`) the terrain adapted to | 3.45 m | #1599, app 1.0.441 |
| HECA | 3,091 leaves inside a walled host seated apart (2,573 over 0.5 m, 994 over 2 m) | to > 2 m | `contents.py` module doc (S6) |
| LEMD T4 / old terminal | pieces of one placement on several deltas (12,057 pairs, 85 sites over 2 m) | to 9.3 m | RULINGS 2026-09-10i |
| RJTT T3 | interior decks seated as decks inside `T3MIN2.obj` | stall, 38.8 GB | RULINGS 2026-11-19f |
| CYYZ tunnel mouths | wing walls on the ground at their own anchors, on top of the cut | 2.4–94 m from the box | #2099, `mouth_group.py` module doc |

The one case where the datum, not the motion, was wrong: KDAL's drainage cap became the CONTENTS of its sunken channel, the unit took a viaduct datum and the channel walls went 3–10 m under the ground (`contents.attach_contents` docstring, RULINGS 2026-10-22b). Cap and channel still belong together; the zero had to be the channel's. That is rule (i).

TODAY'S CODE CAN STILL SEAT A CONTAINED PIECE ON ITS OWN, by six paths. These are what this spec closes. Counts are pieces at least 0.95 inside a lattice building, from `scratchpad/envspec/out/*.contained.json` (script `contained.py`); whether each one stands apart ON SCREEN today is not measured (no current placement plan is on disk for these builds; `tools/obj8_split_report.py PLAN --json` → `tools/contents_census.py`, or `tools/seat_feet_census.py --placement-plan … --rebake-plan …`, would say).

| path today | file:function | evidence in the captures |
|---|---|---|
| S6 refuses a body whose lowest piece is authored below −2.5 m: it seats as a leaf (own ground or carrier) | `contents.attach_contents` :165; `footprint_unit.py:710` | KMCI 3,117 pieces (`Airport/Terminal/metal_dark.obj` dsf:obj10494, 387 pieces down to −9.2 m, 39.29891112, −94.71665339); CYYZ 20 (`CA_CYYZ-Terminal1_Parte48.obj` dsf:obj6089, −6.0 m, 43.68468589, −79.6156966); RJTT 8 (`T1INTER.obj` dsf:obj2191, −6.5 m, 35.5478802, 139.7851896); LEMD 7 (`Ground-FSX-LEMD36.obj` dsf:obj10, −7.01 m, 40.49157677, −3.56847271); OMDB 1 |
| S6 refuses a deck member; on the design surface a deck member is always a leaf | `contents.attach_contents` :162, :185; `placement_family.plan_clusters` :671 | RJTT 511 pieces (`T3ROOF.obj` dsf:obj2238 252, `T2ROOF.obj` dsf:obj2215 122); OMDB 14; CYYZ 7 |
| a structure-seated plate takes the structure's datum and is left out of the units | `rebake_plan._with_deck` :407; `footprint_unit.plan_units_and_connectors` :690 | RJTT `T3GND.obj` dsf:obj2227, `plate_kind` overpass, origin 35.54484197, 139.768742373, 18 of 22 pieces inside T3 (`frames/l2225/o4_v2_rebake_RJTT.json`) |
| a terrain-adapted member keeps its row; only pieces of the SAME frame that ε-TOUCH it take its zero | `pack_partition.partition_pack` (`ADAPTED_SKIP` :82); `adapted_riders.touching_adapted` :88 | the KMCI, KBWI and KATL rows above |
| the free rider (13r) | `rider_floor.free_rider_witness` :114; `contents._free_riders` :203 | SBRJ `policeman4` in `Guarita_Mil.obj` dsf:obj2507 (ruling text; no capture read) — owner-ruled, Q1 |
| a building cut at its pad's block lines (30r C16) | `pad_block_seat.sever` :197 | not counted — a split BY SEAT, kept (Q2) |

A seventh population is outside the partition altogether: placements that are never members (stock library, multi-anchor drop) whose anchor stands inside a building of 100 m² or more — KMCI 907 stock + 195 pack, CYYZ 338 + 515, RJTT 50 + 344, LEMD 0 + 287, OMDB 14 + 93. X-Plane seats them on our ground at their own anchor unless a rider law carries them (`airport/riders.py`, `frame_riders.py`, `underside_seat._riders` :271; NOT traced by me). The law's "always" covers them: stop 2 counts how many the rider laws leave behind.

## 6. What OUR TERRAIN must read at a building (never a seat)

The readers below exist because the ground must be CUT or OPENED where a building goes below grade or where a structure crosses it. Each already screens on below-zero geometry of the FILE (`ResourceCache.y_range`, `obj8.py:748`); after this spec each screens a building on its envelope's LOW layer and reads only the pieces standing over the cells that pass. None of them seats anything.

| reader | pre-screen today (file:line) | what the ground needs from it | pre-screen on the envelope |
|---|---|---|---|
| sunken roads `sunken_roads.read_sunken_roads` :373 | file `vmin > -min_descent_m` skips (:342–:345) | the roofed floor of a road under the building: a cut and its ramps | `interiors` kind roofed with floor ≤ −`min_descent_m`; only pieces over those cells |
| door wells `door_wells.read_door_wells` :352 | file `vmin` against `sill_min_depth_m` and the ground (:143–:152); per component `min_y` (:190) | a below-grade floor plate reaching the exterior face: a door ramp | `low` ≤ −`sill_min_depth_m` within `BEHIND_M` of a perimeter station |
| wall corridors `wall_family.read_wall_corridors` :648 | file `vmin > -min_wall_depth_m` skips (:138–:139); per component (`wall_corridors.py:308`) | thin tall kerb walls under the object's zero: a corridor cut (Law C) | `low` ≤ −`min_wall_depth_m` at the perimeter; the Law C gate first |
| tunnels and trenches `tunnel_objects.read_corridors` :918, `trench_objects.read_trench_objects` :91, `portal_objects.read_portals` :699 | `vmax − vmin < least_skirt` skips (`tunnel_objects.py:1013–:1015`); `vmin > -shell_floor_min_m` (`trench_objects.py:114–:115`) | walls and floor of a bore or trench, its mouths | unchanged for a shell that is its own building; inside a building: `low` ≤ −`admission_depth_m` AND a mapped way crossing `outline` |
| pits, basins, object floors `obj8.read_placed_objects` :1379 (`:1092–:1105`), `walled_pit.read_walled_pit` :269, `object_floor.read_object_floors` :481 | deepest vertex under the highest ground by `admission_depth_m` | the floor our ground follows (27f), the open cut-out (25m (3)) | `interiors` kind open, floor ≤ −`admission_depth_m` |
| retaining walls `wall_class._derive` :181, `classify/retaining_wall.retaining_pieces` :92, `planar/shore.pack_shore_walls` :152, `road_ramp.wall_pieces` :1952 | thin, long, `retaining_wall_min_height_m` tall, with an outline | the step in the ground the wall holds | none needed: a retaining wall is a WALL piece (a seed), its outline is kept |
| decks, abutments, bridges, jetways `deck_signature.classify` :350, `elevated_deck` :741; `contact._abutment_pairs` :1232; `planar/free_bridge`, `deck_bridge`; `jetways.declared_jetways` :99 | deck plates per component; part boxes | the deck's ring, its ends, the ground under it | unchanged: these are their own objects; contained, they move with the building and are read the same way |
| the interior-deck test (19f) `interior_deck.mark` :61 | roofed and floored inside a building of its own frame family | nothing — it only withdraws a deck verdict | later: the envelope's `top` / `low` answer it |

Thin plates (`thin_plates.read_plates` :186) and terrain models (`terrain_model.placement_models` :551) are not partition members and are untouched.

FIVE PLACES, what the terrain reads there (captures as §1 plus `frames/lcyyz/CYYZ.pkl` and `frames/l588fix/LEMD.pkl`; `pm.structures`, `pm.decks`, `Airport.undersides`):

1. KMCI terminal, 39.296825, −94.718003 — a SUNKEN ROAD read out of the terminal's own material sheets (`sunken-road:KCMO-Trimsheet-16.obj@0`; objects dsf:obj10494 with 990 of 1,982 pieces inside the 38,758 m² building, dsf:obj10520 1,188 of 1,486, dsf:obj10567 427 of 427): a cut mouth, floor 0.87 m under, mouth at 305.66 m; a second at 39.294776, −94.718109 (1.32 m, 305.87 m); and a WALL CORRIDOR from `Airport/Terminal/stoneblock.obj` dsf:obj10469, 4.51 m deep, mouth at 298.01 m. The map carries 3 `tunnel_ramp`, 4 `wall_corridor_ramp`, 1 `garage_ramp` and 2 `tunnel_trench` faces. Seat: one zero for the terminal and all of it — the 310.73 m those cuts were made for.
2. CYYZ Terminal 1, 43.686593, −79.616045 and 43.685432, −79.60666 — two SUNKEN ROADS under the terminal, read from `CA_CYYZ-Terminal1_Parte47.obj` (dsf:obj6088, 13 of 14 pieces inside the 465,270 m² building; 3.06 m deep, mouth 168.93 m) and `Parte49` with `Parte44` (dsf:obj6090, dsf:obj6085; 4.0 m, 168.56 m). The terrain reads a roofed road floor; nothing about the terminal's seat.
3. CYYZ taxiway bridges (not contained: each is a building of its own) — FA `CA_CYYZ_Ponte_FA.obj` dsf:obj10883, deck at 167.79 m, cut `walls`, members dsf:obj10881/10882/10883; taxiway T mouths 43.66996, −79.62652 and 43.66975, −79.62559 (27c). The terrain reads the shell's floor, its wall lines and the mouth zone; the wing walls seat WITH their mouth (#2099).
4. LEMD T4S, 40.491656, −3.56866 — today's underside map `unit:24#3636` already reads ONE OPEN below-grade interior there: 345 cells, floor −5.2 m, cover 0.0, `t` −6.54. The pit group (`Ground-FSX-LEMD36` dsf:obj10, −7.01 m; `LEMD37` dsf:obj7) lies inside the 91,223 m² T4S building. The terrain reads the pit's floor (object floors: 7 at LEMD) and follows the group's authored base (27f); the group keeps its seat with the terminal.
5. RJTT — `objects/BaR/bridge2.obj` dsf:obj2178 (0 of 703 pieces in any building: its own structure) gives two sunken-road cuts, 35.542287, 139.789647 (1.88 m, mouth 3.10 m) and 35.540405, 139.790983 (0.93 m); inside buildings the maps read ROOFED interiors at 35.541927, 139.791813 (`unit:127#0`, floor −11.14, `t` −6.12) and 35.544133, 139.766455 (`unit:264#1587`, floor −1.0), and T1's `T1INTER.obj` reaches −6.5 m at 35.5478802, 139.7851896.

No DOOR WELL example: none of the seven captures carries a door-ramp face, and OTHH (the door-well airport, 371 screened placements) has no capture on disk. KMCI's wall corridor is the nearest kind.

## 7. Consumer census (RULINGS 2026-08-30l): every pass that reads pack geometry or a pack-stage product

"Stop" names the stop of §10 at which the row changes; "—" = never changes. Heightfield emittability: this spec adds no region to the planar map and no posting class; building pads are today's cluster pads from a different outline, and the perimeter grade is 25n's.

A. Derivation sites

| # | pass (file:function:line) | reads now | reads after | stop |
|---|---|---|---|---|
| A1 | `airport/basin_witness.read_objects` :63 → `obj8.read_placed_objects` :1379 | every placement's file, per-placement witnesses | same | — |
| A2 | `pack_partition._build_member` :441 (`elevated_deck` :500, line :505, scatter :515, skirt :528, base profile :552) | per-file verdicts (cached by `lfilecache`) | same, except skirt: asked only of a placement with no piece in a building | 3 |
| A3 | `contact.placed_parts` :611 / `part_attrs` :691 (`_feet` :155, `plan_hull` :340, `solid_height` :523) | every piece: feet, outline, solid height | same through stop 3 (outlines from the `outline` file reading); stop 4: no outline for an interior piece | 4 |
| A4 | NEW `airport/building_split` (§2) | — | every solid piece's placed triangles once (lattice), `solid_h`, feet flag, member verdicts | 1 |
| A5 | `contact.partition`: weld :1313, pending pairs :1322, narrow pass :1327 (`_narrow_pass` :976, `narrow_ahead` :1208) | every candidate pair not yet joined, and every same-placement pair | a building's part ids are joined before the weld; a pair with both parts in one building is never tested; each slice is stated as a spanning chain in id order, as `_piece_edges` :725 states a scatter piece (:1335) | 2 |
| A6 | `contact._abutment_pairs` :1232 (called :1340) | part boxes inside one anchor plane | same code; a pair inside one building falls to its own "already one component" skip | 2 |
| A7 | `pack_partition.PackPartition.filtered` :182, `extend_partition` :1048 | drops screened parts and their edges; adds plates | also re-states each slice's chain over its surviving parts | 2 |
| A8 | `planar/group.derive` :360 (`refused_building` :448, zeros :482 / :528) | bodies, abutments, every part's feet | the slices of one building are one group; its feet and zero are the envelope's `feet` and `t` | 3 |
| A9 | `footprint_connector.solid_connectors` :703 (runs `plan_units_and_connectors` at :735; `cluster_topology` :326) | every long body of every unit | long EXTERIOR bodies and whole buildings; a slice is never a candidate | 2 |
| A10 | `placement_family.plan_clusters` :560 (walled :671, chain :715, sheets :728, floor split :777, profiles :823) | bodies' rings, heights, floors, per unit | chain = building per anchor; leaves = exterior bodies; no floor split and no leaf cluster inside a building; `rings` from the envelope `outline` | 2 |
| A11 | `footprint_unit.plan_units_and_connectors` :598 (chain :726, sheets :737, contents :772) | bodies' rings plan-wide; S6 contents | units = buildings; contents and sheets already decided (B6, B7); the plate skip at :690 stays for the DATUM only, the plate still moves with its building | 2 |
| A12 | `unit_underside.unit_population` :64 / `_derive` :297 (`_Placer` :84) | every static triangle of every footed cluster (10,061 maps at KMCI) | one map per building and anchor from all its pieces, plus exterior footed clusters; record gains `outline`, `feet`, `skirt_*`, `low_min` | 2 |

B. Readers of bodies and contacts

| # | pass | reads now | after | stop |
|---|---|---|---|---|
| B1 | `placement_family.bodies_of_plan` :135 → `placement_cut._bodies_of` :826 | same-placement contact edges | same code; a slice reads as one body through its stated chain | 2 |
| B2 | `placement_plan.build_splits` :211 (`intra` / `unit_pairs` :373–:391, carriers `unit_edges` :883) | contacts and abutments per unit | same code, fewer bodies; an exterior body touching a building still has its tested edge | 2 |
| B3 | `pad_block_seat.sever` :197, `neighbours` :353 | drops contact pairs that straddle two blocks | re-states a slice's chain per block (the building is cut at the block line, 30r) | 2 |
| B4 | `mouth_group.mouth_groups` :195 | cross-owner contact edges | same: a wing wall is its own building, its edge to the mouth box is building-to-exterior and is tested | — |
| B5 | `rebake_plan.plan` :280 (`screen_of` :219, `_with_deck` :407), `placement_read` :61, `model/rebake` JSON | the filtered partition | same, plus `buildings` | 2 |
| B6 | `rider_floor.free_rider_witness` :114 | a walled singleton host's surfaces under a rider's feet | Q1 | — |

C. Readers of groups, clusters, undersides

| # | pass | reads now | after | stop |
|---|---|---|---|---|
| C1 | `constraints/foot_rows.foot_targets` :263 | every group's feet (KMCI 29,690 groups → 13 rows) | same code, building groups | 3 |
| C2 | `constraints/pad_relief._foot_offsets` :231 | every feasible group's feet (KMCI 51,432 candidate feet → 418 offsets) | same code, building groups | 3 |
| C3 | `geom/cluster_outline.cluster_outlines` :372, `classify/evidence._cluster_pads` :584, `constraints/cluster_pad.cluster_polys` :119, `planar/pad_blocks._cluster_index` :473, `airport/sunken_ramp._cluster_shades` :220, `constraints/jetway_strip`, `airport/cluster_profile` | every cluster's rings, evidence, base profile | same code, fewer clusters | 2 |
| C4 | `classify/evidence._drop_skirted` :1215 (`skirt.skirted_placements` :304) | per-placement file footprint and skirt depth | the building's `outline` and `skirt_depth`; per file only outside buildings | 3 |
| C5 | `underside_seat.seat_records` :296, `unit_perimeter.perimeters` :214, `perimeter_grade.perimeter_grade` :52, `unit_storey._contact_level` :472, `pipeline/underside_publication` :59, `pipeline/rebake_inputs` :629 | per-cluster maps | per-building maps | 2 |
| C6 | `pipeline/xplat` stage digests, `publication` cluster report, the `[clusters]` say-line | counts | counts change (report) | 2 |

D. Readers of a piece's own fields off the partition

| # | pass | reads now | after | stop |
|---|---|---|---|---|
| D1 | `unit_storey._unit_plans` :437 through `part_footprint` :131 (the one polygon choke point), `unit_floor` :145, `upper_storeys` :193, `unit_levels` :744; `classify/storey_edge.storey_height` :141; `classify/floor_yard._floor_pads` :178 | every solid part's rings and base | for a building: the envelope's `plates` (one row per level) and its wall pieces; exterior parts as today | 4 |
| D2 | `planar/low_level` (`_derive_points` :105, `walled_feet` :202, `plan_low` :296, `top_level` :383), `planar/level_regions.level_seeds` :142, `planar/level_depth.airport_level_b` :56, `planar/group_low.group_floor` :73 | part centre, base, feet, height | same (these fields stay on every piece) | — |
| D3 | `planar/low_extent` (:381–:485), `planar/covered_cut` (:173–:214), `planar/apron_shelf._part_prints` :157, `planar/structure_fence` :172, `geom/base_slab.base_slabs` :229, `planar/pad_blocks._part_index` :438, `airport/ramp_feet._member_feet` :136, `airport/frontage_face.face_clues` :96, `airport/walled_plate.body_plan` :345 | rings of the parts each selects | same through stop 3; stop 4: each is checked for whether it selects interior pieces, and reads the envelope where it does | 4 |
| D4 | `planar/structure_service._Index` :366, `airport/wall_class._derive` :181, `classify/retaining_wall.retaining_pieces` :92, `planar/shore.pack_shore_walls` :152, `airport/road_ramp.wall_pieces` :1952, `airport/hung_wall_seat._witness` :116, `airport/wall_sides` | rings and height of TALL parts | same: wall pieces keep outline and height | — |
| D5 | `airport/flat_pack._grounded_feet` :78, `airport/unit_fence._member_lines` :79, `airport/underside_composite.join` :142, `underside_seat._clusters_of_rows` :170 | feet, lines, part ids | same | — |

E. Readers of raw file geometry (`ResourceCache.geometry` / `components`; 95 modules by grep, read by family, not one by one)

| family | modules | after |
|---|---|---|
| per-file verdicts | `skirt`, `obj8.base_profile` :695, `deck_signature`, `line_object.is_line_object` :153, `scatter.is_scatter` :182, `terrain_model.shape_of` :376, `file_verdict` | per file, cached by `lfilecache`; skirt as A2 |
| structure readers | the §6 table | §6 |
| object-stage cutters and seats | `placement_cut`, `obj8_split`, `placement_body._raw_bodies` :44, `deck_*`, `*_seat`, `riders`, `frame_riders`, `hanging_objects` | same code; bodies fall by the folded share (§1) |
| the envelope's own read | `unit_underside._Placer` :84 | A12 |
| outside the partition | `pack_optimise/*`, `pack_overlap*`, `pack_trees`, `pack_ground`, `terrain_*`, `bridged_ground`, `cover_rim` | untouched |

## 8. Seconds and memory

Basis: the census's ONE-run serial cProfile of the pack stage (KMCI 459.8 s, KATL 373.4 s; pooled 102.8 / 147.1 s on 16 workers) and my pair and piece shares (§1). Estimates, not A/B numbers. "Warm" = `lfilecache`'s readings on file (its work, not counted here); "cold" = the first build of a pack or after a reader's code changed.

| pack-stage item | KMCI serial-prof s | KATL | basis |
|---|---:|---:|---|
| narrow pass, pairs inside one building never tested | −41 of 59.4 | −17 of 22.0 | 69 % / 77 % of box pairs |
| abutments | −3 of 4.2 | −1 of 2.0 | same-building pairs skip |
| connectors (no slice is a candidate) | −30 of 35.1 | −10 of 15.7 | ASSUMES the long material sheets are what `cluster_topology` runs on; not profiled per body |
| clusters (profiles, evidence per cluster) | −8 of 21.7 | −8 of 16.5 | 53 % / 62 % of clusters fold |
| groups, underside maps | −4 of 13.5 | −3 of 12.0 | 70 % / 78 % of groups fold; same triangles rasterised |
| the split itself (B1–B8) | +8 | +8 | §2 |
| WARM total | ≈ −78 | ≈ −31 | of ≈ 212 / ≈ 190 left after `lfilecache` |
| skirt per building, not per file (cold only) | −60 of 67.3 | −3 of 4.9 | 19 skirted members at KMCI |
| no outline for interior pieces (cold only, stop 4) | −54 of 114.0 | −45 of 99.5 | interior = 47 % / 46 % of solid triangles |
| COLD total | ≈ −190 | ≈ −80 | of 459.8 / 373.4 |

Pooled, divide by about four: KMCI ≈ −20 s warm / ≈ −45 s cold of 102.8 s; KATL ≈ −8 / ≈ −20 of 147.1 s. RJTT has no pack-stage profile; its shares are smaller (46 % of pairs, 36 % of triangles interior, 4,501 deck pieces untouched) and its known sinks are the §6 readers in the planar stage, which this spec leaves alone until stop 5.

After the pack stage (KMCI replay profile, 923 s): `platform_split` 59.2 s and `unit_storey.unit_levels` 41.3 s read every solid part of every unit through D1; reading plates and wall pieces instead should take most of that (estimate −40 to −60 s at stop 4; NOT measured). Foot rows and pad relief: −3 s. The OBJECT STAGE is the largest unmeasured gain: bodies fall 46,534 → about 25,000 + 3,015 slices at KMCI and 58,960 → about 31,000 at KATL, with as many fewer body files to cut and write; `tools/v2_rebake_replay.py plan PLAN.json MESH --graded G.json` times it and nobody has run it for this question.

Memory. The split adds two rasters per box group (tens of MB). Through stop 3 the placed pack is held as today (KMCI peak 8.93 GB serial, 5.81 GB pooled): no saving. From stop 4 an interior piece carries no outline and need not be held with per-triangle boxes for the contact pass: about 120 bytes per triangle over 1.47 M / 2.26 M / 4.08 M interior triangles = roughly 0.2 / 0.3 / 0.5 GB at KMCI / KATL / RJTT. Object-stage memory falls with the body count; not measured.

## 9. Bars

- Identity per stop (§10): stated at each stop.
- CERTIFIED AIRPORTS KEGE, BIKF, OMDB, LGAV (captures `frames/lkege3/KEGE.pkl`, `frames/l2203/{BIKF,OMDB,LGAV}.pkl` as controls; the lane takes a new `v2_solve_replay --capture` on its own code at each): patch movers by `tools/airside_value_delta.py BASE.osm LANE.osm --by-ref` — airside 0 over 0.05 m, ground and pads none over the owner's 0.5 m (12y), every mover over 0.1 m listed for the master; law-true grade defects through `tools/harness/census.py` not above the control in any family; object stage `tools/rebake_plan_diff.py zeros` — no body's zero moves over 0.5 m except a contained piece that today sits apart from its building (listed with coordinates: those are the law working). Known exposure: OMDB (16 of 32 relief offsets to 2.56 m, 3 of 3 foot rows, 119 of 723 walled clusters meeting more than one lattice region), LGAV (22 of 60 offsets to 0.43 m), KEGE (2 of 2 rows, offsets ≤ 0.02 m), BIKF (none).
- KMCI, KATL, RJTT: replay off a new capture per stop; time by `tools/pack_stage_profile.py ICAO --one --cache off` (and `--workers 1` under cProfile for the serial table), three runs where a number is quoted.
- DRAWN GATE (integration, 17r; one build per touched airport, `drawn_gate.py --against` the control, no MOVED): KMCI 39.2979,−94.7188 (terminal) and 39.296825,−94.718003 (sunken road mouth); CYYZ 43.686593,−79.616045 and 43.685432,−79.60666 (T1 sunken roads) and the T mouths 43.66996,−79.62652 / 43.66975,−79.62559; LEMD 40.491656,−3.56866 (T4S pit); RJTT 35.54484197,139.768742373 (T3GND) and 35.542489,139.771442 (19f's cart); KATL — the three largest buildings whose cluster set changed, coordinates printed by stop 0; OMDB and LGAV at the sites their accepted reads used (`lomdb3_drawn_sites.json`, `llgav3b.drawn.json`). Integration censuses every crossing at each (owner 11-20).

## 10. Implementation order — one Opus lane, effort high, six stops

Before coding: `tools/blast.py` on each file; `tools/blast.py --find raster lattice supercover` (extend `geom/underside_map.rasterise_layers` and `geom/shape_class.rasterise`, never a third rasteriser); the census is an extension of `tools/underside_census.py` (`--buildings`), not a new tool; new modules are named in `pipeline/stage_code.py`'s lists, `airport/partition_code.py` and, if a per-file kind is added, `file_readings_code.READER_MODULES`; `scipy.ndimage` is already a frozen import. Never raise the lane cap; delete scratch builds on report.

- STOP 0 — MEASURE, no behaviour. `building_split` as a library plus `underside_census.py --buildings` over the registered captures: B1–B7 from TRIANGLES, with B6 and the B8 count (same-placement contacts from the capture's `contacts`). Prints §1's table for every capture, both cell choices (0.5 m; 0.25 m with a two-cell link), and for each certified airport every today's walled cluster that does not map one-to-one onto a building, with coordinates. STOP and report if any certified airport's buildings differ from today's units in a way the lane cannot name; the master picks the cell.
- STOP 1 — THE RECORD, nothing reads it. `PackPartition.buildings`, derived in `partition_pack` after `placed_parts`, cached with the partition; a `buildings` sidecar key. Bar: patch, sidecar (but the new key), rebake plan and placement plan byte-identical on KMCI, KATL, RJTT and the four certified; the split's seconds reported.
- STOP 2 — ONE BODY, ONE UNIT, ONE CLUSTER, ONE MAP, ONE SHIFT (A5–A7, A9–A12, B1–B5, C3, C5; 10i (1), 11a, 14ah (4), floor split, S6 without refusals, 27a on the lattice; §5's rule with δ from rule (i)/(ii)). Outlines still come from the file readings for every piece, so D1–D5 are untouched. Bars: §9; contacts fall by the §1 share; no placement written with more deltas than buildings it crosses plus its exterior bodies; every contained piece of §5's second table shares its building's δ (`seat_feet_census.py` coherence bars), and the non-member placements inside buildings are counted with the rider law's verdict. STOP: report movers, the object-stage diff and the pack-stage times.
- STOP 3 — GROUPS, FEET, SKIRT FROM THE ENVELOPE (A2, A8, C1, C2, C4; 10i (2), 10af/10ag, 11j/11x). Order in `pipeline/build.pack_stage` (:140) becomes partition → envelopes → groups → connectors → clusters. Bars: §9; the rows and offsets that leave are listed against §1's last two rows; `skirted_members` before and after by name.
- STOP 4 — LEVELS FROM THE ENVELOPE; NO OUTLINE FOR INTERIOR PIECES (A3, D1, D3). A design note first (which D3 readers select interior pieces, measured on the captures), reviewed by the master before code. Bars: storey and level products (`tools/unit_levels_census.py`) unchanged at PHLI, LPHR, LDSP, ELLX and the certified four within 0.1 m, else STOP.
- STOP 5 — THE §6 READERS SCREEN ON THE LOW LAYER (optional; worth it only where the planar pack reads dominate — RJTT, OTHH). Bar: every reader's records identical on the captures (`tests/auto_patch_v2/test_once362.py`'s machinery); seconds by reader.

One-miss cap as CLAUDE.md (RULINGS 2026-11-11c): a stop that misses its bar is stopped and reported to the master, not iterated.

## 11. Questions for the owner (through the master) and the ruling line

- Q1. 13r (2026-11-13) seats a footed rider on its own ground when it certainly stands on no surface of its host (SBRJ policeman in a floorless booth). 22:07Z says "always". Recommended: 13r is repealed — the booth's own zero was the defect (walls authored to −0.69 m lifting the unit), and the envelope's `t` reads the floor the contacts stand at, not the skirt. If kept, it is the one exception to §5 and needs the host's inner floor read.
- Q2. A building standing on a pad cut into flat blocks is cut at the block lines (30r C16). 25m (4) says "seated as one piece". Recommended: keep the block cut — it is a split by seat, the kind the 21:07Z sentence allows — and count how many buildings it cuts at stop 2.
- Q3. The floor split (14x) goes: stacked storeys of one footprint are one building (F1). Confirm.
- Q4. A deck member contained in a building moves with it (no exception), also on the design surface, where today it is always a leaf; a bridge frame never seeds or joins a building. RJTT `T3GND.obj` (35.54484197, 139.768742373) is the case to look at: today an overpass plate with its own datum, 18 of 22 pieces inside T3.
- Q5. Between 0.5 m and 1.41 m of clear space (or 1.06 m at the finer cell) the lattice decides whether two wall groups are one building. Acceptable, or must the tie be the exact 0.5 m polygon distance (costs the outlines of the wall pieces in that band)?

PROPOSED RULINGS LINE — 2026-11-27h (id provisional: the next free 2026-11-27 id at merge) — OWNER: ONLY SEPARATE BUILDINGS ARE SPLIT; EVERYTHING INSIDE AN OBJECT MOVES WITH IT, NO EXCEPTION. Owner 2026-11-27, as relayed by the master, verbatim: 21:07Z/21:11Z "we should only be identifying separate buildings that need to be split so they can be seated, we don't want to spend any time analyzing small components inside a group that all moves together"; 22:07Z "objects inside another object should always move with the containing object"; 22:34Z "I can't think of a case where even a tunnel or door well would move independently of a building it was placed with." RULED (spec `docs/specs/building-envelope-20261127.md`): (1) a BUILDING is the pack's wall pieces (solid height at least `chain_min_height_m`; never a line, scatter or bridge-frame deck) connected in plan on the `footprint_touch_m` lattice, its roofed enclosures filled, joined by a spanning sheet (27a) or by one placement's touching pieces (10i (1)); found once at load. (2) A piece `contents_min_fraction` inside a building's plan is INTERIOR whatever it is and whatever file or anchor it is in: never analysed alone (no outline, contact test, body, group, cluster, connector, underside map, skirt reading, foot row, relief offset), and it takes its building's one vertical shift — tunnels, door wells, walls, basements and jetway roots included; S6's deck and below-grade refusals are repealed for motion. (3) The building is one body per placement, one group, one footprint unit, one cluster per anchor, with one envelope (25m's map of the whole building: perimeter, feet, top, low, skirt); seat, pad, levels, grade and skirt read the envelope. (4) Our terrain reads what is below grade at a building through the envelope's low layer (sunken roads, door wells, wall corridors, pits, tunnels); where the ground was cut for a contained piece the building keeps the zero that cut was made for; no reader seats a piece. (5) REPLACES, inside a building: 09-10i (1) touch test (membership instead; kept at the building's edge) and (2) feet across the body (wall contacts only, 22b); 09-11a/10i "buildings never group with buildings" for the placements of one building; 09-14ah (4) "a leaf seats on its own ground"; 14x floor split; 09-10af/10ag read per file (per building); 09-11j/11x per-body relief targets and rows (the building's perimeter feet). Outside every building each stands.

## 12. Not verified

- No build, no replay, no closing evidence: every count is a read of capture pickles through outward-simplified rings at 0.5 m, not triangles; B6 (sheets) and B8 (same-placement joins) are counted, not applied, so "today's clusters split over regions" (KMCI 94, KATL 90, OMDB 119) overstates what the full rule leaves. Stop 0 is the measurement.
- Captures are of different code (KATL `ac5ddd50a`, KMCI/RJTT `bc393a0c4`, KEGE `011e3cc55`, BIKF/OMDB/LGAV `777232700`, CYYZ `9acc3df90`, LEMD `l588fix`), read under `84d554495`; KEGE's cluster rows are unusable (§1 note).
- Every second in §8 derives from the census's single profiled runs and my shares. The connector saving assumes which bodies `cluster_topology` runs on. Stop-4 and object-stage savings are unmeasured.
- Whether each contained piece of §5's second table stands apart on screen today is not measured (no current placement plan on disk for KMCI, CYYZ, LEMD; the LEMD plan in `Patches/` is 2026-10-22). The KMCI, KBWI, KATL, HECA, LEMD, RJTT, CYYZ and KDAL rows of the first table are quoted from module docs and rulings, not re-measured.
- The rider laws for non-member placements (`riders.py`, `frame_riders.py`, `sibling_riders.py`, `ground_frame_riders.py`) were not read; §5's seventh population is a count by anchor only.
- The 95 raw-geometry readers of §7 E were classed by family from grep, not opened one by one; D3's readers were not each checked for which pieces they select (stop 4's design note).
- `lfilecache` was read only as its one uncommitted file (`airport/file_readings_code.py`, kinds `skirt`, `base`, `deck`, `terrain_shape`, `outline`); whether its `outline` reading is per file or per component decides how stop 4 asks it. Not known.
- SBRJ (13r), KDAL, KBWI, HECA, OTHH: no capture read. No door-well site in any capture read.
- The pad-block cut's reach (how many buildings 30r cuts) and the count of buildings holding terrain-adapted pieces (rule (i)) need a rebake plan per airport; only RJTT's (`frames/l2225/o4_v2_rebake_RJTT.json`) was read.
- The thread branch tip moved from `0979b3c8a` to `7323a7052` during this work (RULINGS 2026-11-27g added; `planar/short_bore.py`, `planar/structures.py` changed); line numbers were not re-checked there.
