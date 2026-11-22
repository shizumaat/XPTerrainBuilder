# Walled multi-bridge frames: one rule set (#2157 KRDU north; KORD I-190) — ONE-MISS review of lkrdu6

Review of `claude/lkrdu6` 6915736ac. Spec only; nothing here is implemented, built or replayed.
Law: RULINGS 2026-10-30a (flush 0.04 m, road passes under), 10-30b (banks; walls bound the cut),
2026-11-18i (1)-(8) (cut to spans, graded spans, the cap is the pavement's grade, wall-pair
spans), 2026-11-19a (a walled deck is still a bridge; per-piece depth; one bore), 10-22m/22n
(class A airside decks), 10-27c (pavement runs ACROSS), 11-06 #1903 (a trench object's own
floor is the cut), 08-30l (consumer census), 05e/05g (no airport-specific code).

Sources read: the code at 6915736ac (cited `file:line`, under `Ortho4XP/src/auto_patch_v2/`),
the KORD 1.0.561 debug log `/Users/noah/XPTerrainBuilderData/Patches/+40-090/+41-088/
auto_patch_verify_debug.log` :4926-5263 and `o4_v2_rebake_KORD.json` beside it, RULINGS 19a's
NOT MET text. KRDU numbers are the lkrdu6 report's (via the brief and 19a), not re-measured.

## 1. The family

A pack TRENCH with WALLS, in one object or one co-placed frame, that carries SEVERAL hard-deck
pieces: taxiway (and road) bridges over the road in the trench, often on more than one axis,
with open walled trench between and beyond them.

| | KRDU CTR_TML obj143 / NTH_TML obj137-139 | KORD `tunel_solido.obj` dsf:obj14271 |
|---|---|---|
| Pieces | D 3,077 m2 (over -254), C 2,736 (over -255), groundside 832 (over service -461), slivers 109 / 135; NTH: twy over tunnel -1744 and road -239 | W x[-57,-20.8], E x[28.1,64.3], both y = 0, each across the 109 m width of a 470 m trench (floor y -5.05) |
| Walls | a co-placed signature-B trench object (to -13.57 m at its far ramp) | in the SAME file; signature-B refuses it (below) |
| Axes | several (D, C and the 832 piece do not band along one axis) | one (W and E in order along the trench) |

## 2. Attribution: why each site misses (code-level; M = measured in a log, C = read in code)

**KORD.**
1. (M, log :4980) `airport/object_cut.py:575-600` refuses obj14271 as signature B: "a SHELL
   (floor plate 1115 m2 at -5.00 m, trench 8317 m2) with no flush HARD_DECK cover at the same
   placement". The self-cover form is excluded on purpose (:575-584, a sea barrier covering its
   own floor). So obj14271 is never in `tstats.trench_objects`, and `deck_bridge._bottom_y`
   (`planar/deck_bridge.py:233-238`) reads `walled = False`: lkrdu6's whole 19a path (per-piece
   depth :399, the bore join `planar/structures.py:284-293`) is keyed on signature-B admission
   and cannot reach a one-file walled frame.
2. (M, log :4948) structures: `decks 0`. WHY `deck_bridges` returned no `DeckBridge` is NOT
   VERIFIED: the debug log does not carry `sstats.hard_decks`. Candidates in code order
   (`deck_bridge.py:354-394`): `deck_top_z is None`; "no pavement runs across it" (the stations
   one step outside a ring that ends ON the rim, section 3 W3); `_elevated` (road family; the
   rebake plan has `elevated_deck: true`). First lane step reads the note (section 8).
3. (M, log :5263) `planar/basins` then claims the frame as `basin:0`, "covered pit; 2
   object(s)", floor 187.83 = R_est 197.82 - deepest solid 9.99 (the trench floor is y -5.05:
   the pit stands ~4.9 m too deep), floor area 44,748 m2. The six "deck candidates ... refused
   (does not span the pit)" are NOT the hard decks: they are `basin_witness.ramp_decks`
   (`airport/basin_witness.py:181-296`), RAMP candidates whose test is a vertical CLIMB from the
   floor to the rim (:271 `spans = hi >= rim - band and lo <= floor + band`). A flat deck at rim
   level can never pass it. The brief's reading ("tested along the 470 m length, not across") is
   corrected here: the basin pass has no hard-deck span test at all. Do not edit `ramp_decks`.
4. (C + M) With no deck plate the object stage falls to `airside_deck_seat.airside_zero`'s
   unplated path (`airport/airside_deck_seat.py:399-411`): `airside_end_ground(ring, surface,
   step_m, outside=False)` reads the surface ON the ring edge (:170), i.e. on the trench rim,
   where the map holds rim (197.5) and pit floor together. Brief: zero 191.72, decks 4.6-6.3 m
   under the taxiway. The plan confirms the inputs: `deck_datum_z 197.33`, `deck_end_stations
   []`, no `plate_kind`.
5. (C + M) `airport/rebake_plan.py:149-154` `_deck_ring_xy` publishes "its largest polygon's
   exterior": `Member.deck_ring` in the KORD plan is W's four corners only. E has no ring, no
   end lines, no seat.
6. (brief, not re-read) the pit's faces keep the taxiway centreline vertices (197.28): a tent.

**KRDU north** (lkrdu6 report; C where cited).
1. `deck_bridge.py:408-410`: "ONE zero per object" for every piece without a `span_cut`. Only a
   piece cut out of an at-grade deck is graded (18i (5)); NTH's piece keeps one flat zero across
   end lines 1.6 m apart on the lidar (+1.4..+2.9).
2. The joined bore -254/-233/-255 (`planar/bore_continuation.py:158-188`) ends under the 832 m2
   piece, which has no witness (`facing_contacts` asks for ROLLED-ON airside pavement,
   `airside_deck_seat.py:251`; the piece stands in groundside pavement). The mouth therefore
   seats at bridge C and road -469 climbs at the ramp cap INSIDE the trench walls (walls to
   -13.57 at 35.879782, -78.789194): a 4.6-6.6 m hard row; D and C yield 1.4-2.5 m.
3. `deck_gap_ways` retags the gap way `tunnel=yes` (:184). `o4_deck_gap` has NO reader (grep:
   one hit, its writer), so the gap is a ROOFED bore. That is what flipped KBNA -3438 / -4945,
   and why lkrdu6 had to key the join on signature B (which KORD then cannot enter).
4. Object stage: `pipeline/rebake_inputs.py:285` takes the FIRST deck's `span_cut` for the whole
   object; `airport/deck_plates.py:221-253` `_span_plates` bands along one `a -> b` axis;
   `geom/plate_bands.py:22-46` `Plates` is one axis + cut stations, and plates that do not band
   along one axis are "left whole and counted" (`deck_plates.py:17-19`). A multi-axis frame
   loses bodies or seats whole.

## 3. The rule set (general; no airport, pack, resource or coordinate named)

**W1 — Classification: a walled bridge frame, before any pit.** A FRAME (`deck_bridge._frames`:
the co-placed set, or one placement) is a WALLED BRIDGE FRAME when it holds a hard-deck piece
that (a) SPANS its own walls: `geom/wall_lines.inner_faces` finds a facing wall pair of the
frame's own solids within the piece's reach across the road (the `_walled_trench` test,
`deck_bridge.py:931-936`) and the piece covers the pair wall to wall — the span test is taken
ACROSS the trench, on the piece's short crossing, never along the trench; and (b) is WITNESSED
(W2). `walled` in `deck_bridges` becomes that geometric reading OR signature-B admission (today
only the latter, :233-236). Precedence, one reader per frame: an `ObjectFloor` frame
(`planar/build.py:314`, `floor_frame`; LGAV, OMDB) stays the floor's, unchanged; else a walled
bridge frame is `deck_bridges`'; only then may the basin, split-level, sunken-road and
wall-corridor passes see what is left. Every placement of a walled bridge frame is passed as
`taken` to those passes (they run after `deck_bridges`: `planar/build.py:372` vs :405 / :460).
A frame with walls and NO witnessed spanning piece is untouched by this spec.

**W2 — Witness.** (a) Airside: 27c unchanged, pavement runs across, stations per W3. (b) NEW, a
road deck inside groundside pavement: a piece of a walled bridge frame with no airside facing
pair is a ROAD span when it spans its walls (W1 a), a mapped way passes under it between that
wall pair (the 18i (8) reading, `planar/deck_span_cut.py:78-104`), and a facing pair exists
under the widened `carried` predicate — road roles or groundside pavement (the precedent:
`planar/floor_decks.py:94-97`, `cut_deck_seat.py:263-265`). Family `road`; `_elevated` still
judges it. Its end-line rows live in the GROUNDSIDE tier: they may never appear as a hard row
against an airside row (airside is king). (c) A piece that is neither (the 109 / 135 m2
slivers) is no deck: it RIDES the nearest span's cell (W6), and is still published (W9).

**W3 — End lines one step outside the rim, per span.** For every piece of a walled bridge
frame the end-line stations stand one sample step outside the LARGER of the piece's ring and
the trench rim (wall inner face + `[tunnel] wall_gap_m`), on the carried surface: the planar
seats on the map's nearest vertices OFF the cut (`constraints/deck_lines.floor_end_lines`, as
`floor_decks` does), the object stage with `outside=True`. The object stage never seats a
walled bridge frame from the unplated ring path: a witnessed piece without `plate_stations` is
counted `walled_frame_unplated` and listed, never read on the rim.

**W4 — Each span seats on its own axis, graded (18i (5)/(6)/(7)).** Every witnessed piece of a
walled bridge frame with TWO OR MORE witnessed pieces not banding along one axis, or whose
frame is already cut to spans (18i), carries its own `span_cut = (a, b, ((0, L),), cap)` with
`a`, `b` the middles of ITS two end lines: one level per end line (`DeckAnchor.graded`), the
two-sided row `|mean z[S_B] - mean z[S_A]| <= cap * L` (`constraints/edge_deck._graded_rows`),
the cap the PAVEMENT's grade (18i (7)), over-cap listed (`deck_span_over_cap`). The "one zero
per object" estimate (`deck_bridge.py:408-410`) no longer joins such pieces. A frame whose
pieces band along one axis and is all bridge (18i (4), #2112: KBNA taxiway L; KORD's W / E)
keeps one zero per plate band, unchanged. NTH's single piece is graded because its frame
(obj137-139) is cut per W6; if it turns out to be one piece in a one-axis frame, 18i (5) is
extended to it only on the owner's word (stop condition 6).

**W5 — The floor per piece.** Under each span the floor is that span's zero less its OWN bottom
(`_piece_bottom`, `deck_bridge.py:241-272`), for every walled bridge frame (W1), not only
signature-B ones. Along an open stretch the floor is the frame's lowest solid standing in that
stretch, read the same way per station (W7), never one depth for the whole object and never
`R_est - deepest solid`.

**W6 — The object stage cuts on every span's axis.** `Plates` (one axis, cut stations) becomes
CELLS: each cell an intersection of half-planes `(nx, nz, c)` in the authored frame; a band is
the two-half-plane case, so #2112 and 18i frames produce the same cells as today. For a
multi-axis frame the cells are: per span, its ring grown `SPAN_SEAT_M` along its own axis and
bounded across it by its wall pair; the REST (trench walls, floor, riders outside every span)
is cut between neighbouring spans at the middle line of the gap between them and each rest
cell takes its nearest span's end-line reading — a rigid translate (no tilt), anchored as
`_band_seats` anchors a band. `obj8_split.BodyCut.band` (`airport/obj8_split.py:277-280`)
clips to a cell instead of `(ux, uz, lo, hi)`. `rebake_inputs.py:285` publishes EVERY piece's
`span_cut`, keyed by piece, and `_span_plates` builds one cell set from all of them. At-grade
bands are dropped only where 18i (3) drops them (mapped airside); a trench cell is never
dropped. Steps between neighbouring rest cells over `deck_flush_m` are listed, not chased.

**W7 — One cut, open sky between spans; the road climbs out where the walls say.** (a) A short
open way joining two bores under spans of one walled bridge frame joins the CUT only: the floor
may not come up between them, and the stretch stays OPEN SKY between the frame's walls (the
existing `_walled_trench(other)` stretch, `deck_bridge.py:938-945`). `o4_deck_gap` gets its
reader: no roof, cover or ground face over a gap way. With that, the population is W1's and
the signature-B key (`structures.py:288-290`) goes. (b) Beyond the last span the approach's
floor follows the frame: at each station along the road, floor = the seat there + the frame's
lowest solid between its wall pair (W5), for as long as the frame has a facing wall pair at
that station; the MOUTH (where the road is free to meet grade under the ramp law) is the
station where the wall pair ends or the walls' height falls under `[tunnel] object.cover_flush_m`.
No ramp-cap row is written inside the walls. This is 11-06 #1903's rule ("a simple continuous
trench tracing the whole object") applied to the open stretches of a walled bridge frame.

**W8 — Clean cut: nothing of the pavement inside a span cut.** Inside each span's cut polygon
(the rim ring, W3) no pavement cell, at-grade cell, apron gap-fill, zone ground or centreline /
edge breakline vertex survives: cells are knifed out (the `carried_off` knife,
`planar/deck_generated.py:686-712`, for pack decks of walled bridge frames too) and breaklines
are clipped at the end lines. The faces under a span are the trench's only (floor, wall
stand-off, 30b bank where a side has no wall). Verify: no vertex with a pavement or centreline
ref inside any span cut (a new `LAW_FAMILIES` check, `walled_span_clean`).

**W9 — Every piece is published.** `Member` carries every hard-deck piece's ring (`deck_rings`,
with `deck_ring` kept as the largest for old readers), each tagged `span` (airside / road) or
`rider`, with its own end stations, tops and `span_cut`. `_deck_ring_xy` stops being the only
ring a consumer can reach.

## 4. Consumer census (08-30l): every pass reading the changed regions

By grep at 6915736ac; the lane confirms each row with `tools/blast.py` before editing.

| Pass (`file:line`) | Reads | Rule | Effect |
|---|---|---|---|
| `planar/deck_bridge.deck_bridges` :333-425, `_bottom_y` :219 | `trenches` -> `walled` | W1, W5 | walled by geometry; per-piece bottom for all |
| `deck_bridge.py:408-410` `_deck_z` | one zero per object | W4 | not for multi-axis walled pieces |
| `deck_bridge._walled_trench` :913, `deck_cut` :724, `deck_banks` :814, `deck_ground` :950 | walls, `other` | W7a, W8 | open stretch stays; ground minted only outside span cuts |
| `planar/deck_span_cut.span_split` :46, `_wall_spans` :78 | wall pairs, mapped ways | W2b, W4 | road-span witness; identity `span_cut` |
| `airport/airside_deck_seat.facing_contacts` :212, `airside_end_ground` :139 | roles one step outside the ring | W2b, W3 | `carried` widened; rim-aware stations |
| `airside_deck_seat.airside_zero` :371 | unplated ring path | W3 | refused + counted for walled frames |
| `planar/bore_continuation.deck_gap_ways` :158; `planar/structures.py:284-293` | deck rings, `trenches` | W7a | W1 population; gap not roofed |
| `planar/structure_approach.chains` :175, ramp :1097-1130; `structure_mouth` | bore ends, `ramp_max_grade` | W7b | mouth at the walls' end; no cap row inside walls |
| `planar/build.py:311-460` (floors -> decks -> structures -> basins) | `floor_frame`, `taken` | W1 | walled frame ids taken from later passes |
| `planar/basins.build_basins`, `read_objects`; `split_level_pit` :185; sunken road; wall corridor (W1s) | candidate placements | W1 | KORD `basin:0` not built; `ramp_decks` untouched |
| `airport/object_cut.py:575-600` | signature B | none | unchanged (the refusal stays; W1 does not need it) |
| `airport/object_floor.py`, `planar/floor_decks.py`, `airport/cut_deck_seat.py` | `ObjectFloor` frames | none | precedence keeps them; LGAV / OMDB identical |
| `planar/deck_generated.carried_off` :686, `generated_decks` | deck rings, cells | W8 | knife also under walled pack spans |
| `constraints/edge_deck` (`_graded_rows`, :168 / :590), `deck_lines`, `deck_anchor.settle` | `span_cut`, end lines | W3, W4 | more graded spans; groundside tier for road spans |
| `pipeline/rebake_inputs.py:262-296` | first `span_cut`, stations | W6, W9 | per-piece cuts and stations |
| `airport/rebake_plan.py:149-171, 384-460`; `model/rebake.py:175, 456, 492, 607` | `deck_ring` | W9 | `deck_rings` added, serialised both ways |
| `airport/deck_plates.py:181-253`, `geom/plate_bands.py:22-46`, `airport/obj8_split.py:277`, `obj8_band` | bands | W6 | cells; bands are the special case |
| `deck_ring` readers: `planar/{channel,channel_geometry,group,free_bridge,structures}`, `airport/{placement_coherence,bridge_stack,written_seat_census,bridge_family,free_bridge_seat,deck_end_read,deck_routes,pack_partition,footprint_unit,placement_family}` | largest ring | W9 | unchanged value; audit each for "one ring = the deck" |
| `verify/deck_flush`, census `deck_end_flush`, `tools/check_grade.py` `LAW_FAMILIES` | per-end levels | W3, W8 | per-piece end lines; new `walled_span_clean` |
| `auto_patch/object_terrain_features`, `object_stage` (pack journal, apt.dat hole) | structures, deck plan | W8, W9 | hole per span ring |

Heightfield emittability: W7b replaces a 4.6-6.6 m violated row by a floor that follows the
object, W1 removes a 44,748 m2 pit 4.9 m too deep; walls remain vertical faces at the rim as
today (`_walled_trench` rim). No new face kind, role or ref prefix.

## 5. Bars (replay; drawn at integration per 17r)

At KRDU (D, C, the 832 piece, NTH) and KORD (W, E):
1. Every span end line flush <= 0.04 m (`deck_end_flush`), each within 0.5 m of the lidar read
   one step outside the rim; each span's pavement grade <= the cap, bends listed (18i (7)).
2. Taxiways within 0.5 m of the lidar along the apt.dat centrelines through and 150 m either
   side of each span (KRDU d, c, j; KORD the two taxiways over I-190). Today: d -3.01, c -2.31,
   j +2.58; KORD decks 4.6-6.3 m low.
3. Clean cut: `walled_span_clean` 0; no pavement / tent vertex under a span; no hard row
   violated > 0.05 m at the bore mouths (today 4.6-6.6 m at -469).
4. KRDU: the 832 piece witnessed as a road span, the joined cut's south mouth beyond it at the
   walls' end; -233's gap open sky. KORD: `basin:0` absent, 2 `DeckBridge` pieces, the trench
   floor within 0.5 m of zero - 5.05 under each span.
5. Rebake plan (diff the PLAN, #625): every piece's ring published; KORD W and E each seated on
   its own end lines; KRDU obj143 cut into cells with no body lost (body count in = out + the
   18i-dropped at-grade bands, listed).
6. Tests: synthetic fixtures for a one-file walled frame with two spans (W1/W3/W5), an L of
   three spans with a rest cell (W6), a road span inside groundside pavement (W2b), a gap way
   between two spans (W7a), a walled approach (W7b), a centreline through a span (W8).
   `test_deck_bridge1671.py`, `test_deck_spans.py`, `test_deck_trench2072.py`,
   `test_deck_cut_cover.py`, `test_survey_deck_cut2128.py`, the #2112 plate tests green;
   ratchets, `test_no_airport_specific_code`, `test_v1_retired`, the CI registry gates.

## 6. Protection

Replay `--from planar` before / after on the same capture, and the rebake plan diff:
KBNA taxiway L 172.0 +- 0.1, its walled floor polygon and the open stretch -3438 / -4945 OPEN
SKY (#1718), identical; KEGE, BIKF, OMDB, LGAV, OTHH, LOWS, NZWN identical (no vertex > 0.1 m,
no frame newly classified W1, no basin lost, plan unchanged). WILL FLIP, list with numbers:
EDDF `Bridge_3` + `Tunnel_3` (co-placed signature-B trench: a bridge since 19a, now also
per-span floor and rim-outside end lines). List every other frame W1 newly claims anywhere and
every basin W1 removes.

## 7. Replay commands (from `Ortho4XP/`)

    venv/bin/python tools/v2_solve_replay.py --replay /Users/noah/XPTerrainBuilderData/.harness/frames/lkrdu/KRDU.pkl \
        --from planar --json OUT/krdu.json --solved-out OUT/krdu.pkl
    venv/bin/python tools/v2_rebake_replay.py plan ...            # the object stage, KRDU and KORD
    venv/bin/python ../tools/harness/frames.py latest ICAO --kind capture   # each protected airport

KORD has no capture (`frames.py list KORD`: none). Take ONE, on the base sha before any edit:

    venv/bin/python tools/v2_solve_replay.py --capture KORD --out OUT/KORD.pkl
    venv/bin/python ../tools/harness/frames.py register --icao KORD --kind capture \
        --path OUT/KORD.pkl --base <sha> --lane <lane> --copy --note 'walled frames control'

KORD's planar stage took 274 s and its pack partition 333 s in 1.0.561 (log :4897, :4911): a
KORD replay is ~10 min; budget for it. Captures in use: KBNA `lkbna16`, KEGE `lkege3`, BIKF
`lkbna14`, OMDB `lomdb`, LGAV `llgav3`, OTHH `lkbna2`, LOWS `lowspad`, NZWN `lnzwn4`, EDDF
`deckB`. `--allow-degraded-dem` is refused at replay.

## 8. Order of work and stop conditions

Order, one variable per replay: (0) KORD capture; print `sstats.hard_decks` for obj14271 and
record why no deck was read. (1) W1 + W3 + W5 + W9 -> KORD. (2) W2b + W7 -> KRDU CTR. (3) W4 +
W6 -> KRDU CTR / NTH, object stage. (4) W8 at both. Protection after (1), (2) and (3).

Stop and report (no tuning of weights, caps or thresholds):
1. Step 0 shows a cause outside section 2's candidates.
2. Any protected mover > 0.1 m, KBNA's open stretch roofed, or a LGAV / OMDB `ObjectFloor`
   frame reclassified.
3. W7a without the signature-B key changes KBNA: restore the key, report, and W7a waits.
4. After (2) the -469 row is still violated > 0.5 m: the walls-end mouth is wrong; report the
   wall profile along -469.
5. After (1) KORD's end lines are flush but the taxiways are > 0.5 m off the lidar: report the
   profiles (the lidar under a deck is never read, Q344 a).
6. NTH is a single piece in a one-axis frame (W4): owner question, do not grade it.
7. W6 loses or duplicates a body in any plan diff.
8. A second miss goes to the owner (11-11c). No closing tile build (17r); never raise the lane
   cap; delete scratch builds on report.

## 9. Estimate

Two Opus lanes, effort high, disjoint files: lane A planar (W1, W2b, W3 planar half, W5, W7,
W8: `deck_bridge`, `deck_span_cut`, `bore_continuation`, `structures`, `structure_approach`,
`build`, basins' `taken`), ~250 lines + tests; lane B object stage (W3 object half, W4 plates,
W6, W9: `plate_bands`, `deck_plates`, `obj8_split` / `obj8_band`, `rebake_inputs`,
`rebake_plan`, `model/rebake`), ~300 lines + tests. New public symbols expected: `Plates`
cells accessor, `Member.deck_rings`, one check name. Replays: KRDU ~3 min x ~8, KORD ~10 min x
~4, 9 protected x 3 passes in parallel: 4-6 h wall per lane, lanes in parallel. Integration
builds KRDU and KORD once each and runs `drawn_gate.py` at D, C, the 832 piece, NTH (KRDU) and
at W and E over I-190 (KORD).

## 10. Not verified

- Why `deck_bridges` read no deck at KORD (section 2, KORD 2).
- KORD's 191.72 zero, the 4.6-6.3 m and the centreline tent: from the brief; the plan and log
  confirm only the inputs (no plate, one ring, `deck_datum_z 197.33`, `basin:0` floor 187.83).
- Whether obj14405 / obj14272 are co-placed with obj14271 (the basin lists "2 object(s)").
- Every KRDU number (lkrdu6's replay was not re-run); NTH's piece count and axes.
- That the roofed gap is the whole KBNA flip (read from code: `o4_deck_gap` has no reader).
- KORD's OSM under the decks (whether I-190 is tunnel-tagged there) and its lidar floor.
- Protected airports and EDDF: predicted, not measured. Census rows are by grep.
