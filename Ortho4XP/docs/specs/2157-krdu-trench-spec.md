# #2157 KRDU taxiway E: the trench under the cut deck (TWO-ROUND-CAP review of lkrdu3)

Review of `claude/lkrdu3` 1362aa781 (on lkrdu2 71512d05d). Spec only; nothing here is implemented.
Law: RULINGS 2026-11-18i (cut to spans, choice (b)), 10-30a / 30b / 30f (flush decks, banks, walls
set the cut), 18f (the pack is a witness), 08-30l (consumer census). Owner additions relayed
2026-11-18T20:48Z / 20:49Z, verbatim: "The taxiway E is on a large embankment with roads and lots
well below it on either side…" / "Except where they cross under the three bridges".

All numbers below are from ONE replay of `frames/lkrdu/KRDU.pkl` at 1362aa781 (`--from planar`,
NCPHASE3 lidar), read off the solved pickle. Stations `s` run along the deck's own axis
(`DeckBridge.span_cut` a = (-1213.8, -551.3) to b = (-731.0, -1079.1), 715 m); `off` is across it
(+ = NE). Nothing was built.

## 1. Attribution: what the "corridor" is

It is NOT a road corridor and NOT an approach ramp. The four structures at the W bridge are short:
`tunnel:-17014@0` axis 72 m, `@1` 120 m, `tunnel:-2422@0/@1` 96 / 60 m, all `top_pinned`, floor
109.94. The 21,800 m2 pit is the WALLED-DECK FLOOR of the W span:

- `planar/deck_bridge._walled_trench` (deck_bridge.py:866-893) builds the floor as
  `wall_strip(r, n, ua, ub, s_lo, s_hi)` between the frame's two "inner" wall faces. Only the RIM is
  intersected with the deck ring (line 884); the FLOOR never is. `deck_cut` then unions that floor
  into `ramp` and `outer` (deck_bridge.py:713-720) and clips only to the midline half-plane
  (`_keep`, :751).
- `DeckBridge.walls` is read from the WHOLE frame (`wall_faces(cache, frame, ...)`,
  deck_bridge.py:383), so both spans of obj140 carry all six wall lines of the 711 m object, at
  s = 155, 206, 591, 615, 661, 674 (frame u = -275, -224, +161, +185, +231, +244).
- `geom/wall_lines.inner_faces` (wall_lines.py:38-50) takes the nearest line each side of the ring's
  middle that covers `_COVER_MIN` = 0.5 of the ring's width along the road, lines binned at
  `_LINE_BIN_M` = 0.5 m. The W span ring is 68.9 m wide along the road (the whole deck plan, slopes
  included); its own east wall (s 206) is 40.1 m long and 0.3 m out of straight, so it falls in two
  bins and its larger bin covers 31.8 / 68.9 = 46 % -- REFUSED. The next line east is the E
  bridge's west wall at s 591.
- Result (measured by calling `_walled_trench` on the replay's deck): W span inner faces
  ua = -274.9, ub = +161.2 -> a floor strip 436.1 m long, 30,034 m2 (its rim 3,227 m2). The E span
  the same way skips its own wall at s 615 and takes s 661: 70.2 m, 4,395 m2.
- In the solved map this is faces 443 (`tunnel_ramp`, 21,905 m2, s 181-591, off -39..+66, z
  106.63..120.53) and 303 (8,284 m2, s 183-543, off -127..-6), meeting along the W span's midline
  extended 405 m at z 106.6. Face 443 runs from that line up to the taxiway's NE edge strip
  (116-120.5): the taxiway crest itself is the pit's wall. The at-grade cell between the spans is
  left as one 508 m2 edge strip (`deck_at_grade:dsf:obj140#0`, off +27..+33) of the 33,358 m2 plan.
- `tunnel:-17013@0` ("its corridor overlaps tunnel:-17014@0") is refused by this floor reaching the
  E bridge, not by any road geometry.

Before the cut the same strip stood under ONE 711 m deck ring, which hid it. lkrdu3's two refuted
arms both treated it as a corridor: pairing spans changes `other`, not `ua/ub`; adding the at-grade
cells to `uncut` (deck_bridge.py:728-733) subtracts the pavement from a floor that is still 436 m
long, so the 106.6 floor stood `rim_off` from the taxiway's edge along its whole length and the
span/pol59 rows followed it down to 111.96.

## 2. Is the road in a cut there? The lidar says no -- it is an embankment

Transects across the axis (lidar, m):

| s | off -90 | -45 | -30 | 0 | +15 | +30 | +45 | +90 |
|---|---|---|---|---|---|---|---|---|
| 200 (W opening) | 106.9 | 107.6 | 107.8 | 108.9 | 108.7 | 108.6 | 108.8 | 109.4 |
| 250 | 108.8 | 113.4 | 116.7 | 117.0 | 116.7 | 114.2 | 110.2 | 112.8 |
| 350 | 110.9 | 112.5 | 117.7 | 118.6 | 118.3 | 115.4 | 113.6 | 113.6 |
| 450 | 113.6 | 113.7 | 118.3 | 120.1 | 119.9 | 118.6 | 117.1 | 117.2 |
| 550 | 117.5 | 117.8 | 119.4 | 121.6 | 121.5 | 120.8 | 117.4 | 116.3 |
| 600 (E opening) | 115.5 | 115.1 | 115.0 | 115.6 | 115.4 | 115.3 | 115.4 | 115.7 |
| 650 | 114.4 | 114.5 | 118.3 | 122.9 | 122.9 | 122.5 | 118.5 | 116.5 |

The owner's statement holds: a crest about 50 m wide (off -33..+17, centred ~8 m SW of the pack
axis) stands 4-9 m over roads and lots on both sides; the low ground beside it is real and already
in the lidar. The roads rise with it (108 under W, 115 under E). No floor is owed anywhere between
the openings. The defect is a floor claimed UNDER the pavement plan.

### The three bridges

The pack's own walls state three openings: s 155-206 (51 m; ways -17014 secondary 5 lanes and -2422
service, both `tunnel=yes layer=-1`; lidar open 160-210 at 108.5), s 591-615 (24 m; way -17013;
lidar open at 115.8), and **s 661-674 (13 m; way -454 service, `tunnel=yes layer=-1`, 68 m long,
crossing at s 668)**. The third is invisible to `geom/deck_spans.span_cut`: the bare-earth lidar is
continuous there (crest 123.1-123.2), with the flanks at 114.4 / 116.5. The replay refuses it twice:
"generated deck at (-758, -1040) 2,325 m2 over -454 service 68.0 m: REFUSED -- the pack's hard deck
dsf:obj140 stands on it"; `tunnel:-454@0` builds a 24 m stub (floor 114.33) against the plan.
NOT VERIFIED: that this is the owner's third bridge (not read in the pack mesh or the sim); the
other candidate is that the 51 m W opening is two bridges (no pier ground in the lidar).

## 3. The rule

**R1 (embankment).** Airside pavement holds its own graded level across its width and shoulders.
Lower roads and lots beside it are met by a bank at the bank law. No road floor, deck floor, lot
floor or ramp may claim ground under airside pavement, except inside a bridge span's opening.

**R2 (a deck's floor is under the deck).** A walled deck's floor is the strip between the wall
pair bracketing ITS OWN opening, and never leaves its ring except along an open stretch to a deck it
runs through to (`other`, unchanged). A wall line outside the ring's reach is not this deck's wall.

**R3 (the opening is the walls').** Where a frame's walls face each other across the carried
pavement with a mapped road passing between them, that pair is a SPAN whether or not the survey
shows the void (18f: the pack is a witness; 10-30f: walls set the cut).

**R4 (the pavement is the taxiway, not the object's plan).** The at-grade part of a cut deck
becomes pavement only where the mapped airside stands (width + shoulder); the rest of the object's
plan is the embankment's bank.

## 4. Changes (general; no airport, pack or resource named)

**F1 -- `geom/wall_lines.inner_faces` + `planar/deck_bridge._walled_trench` (R2).**
(a) `_walled_trench` passes the ring's own reach: an inner face is admitted on a side only when it
stands within `[u_lo - inset, u_hi + inset]`; else that side is `None` and the 30b bank stands, as
the docstring already says. (b) The cover test measures against the stretch of `[s_lo, s_hi]` that
the frame's wall faces inside that u-reach occupy (the walls' own length), not the ring's whole
width, and a line is the faces within the bin of its neighbours (merge adjacent 0.5 m bins) -- so a
40 m wall under a 69 m plan is a wall. (c) The floor strip is intersected with the ring (the `other`
stretch excepted). Expected at KRDU: W floor u -274.9..-223.8 (51 m), E +161.2..+184.8 (24 m).
(a)+(c) are no-ops wherever the inner faces already stand inside the ring; (b) can only ADD a wall.

**F2 -- `geom/deck_spans.span_cut` / `planar/deck_span_cut.span_split` (R3).** After the survey
spans, add a span for each facing wall pair of the frame (`deck_walls.wall_faces`, the same faces)
that (i) lies in a stretch the survey read as at grade, (ii) has a mapped road way crossing the
deck between the two lines, and (iii) has ground more than a storey
(`[building_pad] low_level_min_step_m`) under the crest on BOTH flanks at the crossing. Its
abutments are the two wall lines. It then takes 18i (5)/(6) unchanged: graded end lines, a
`Member.deck_spans` band kept and warped, the road under it a deck corridor like -17013's.

**F3 -- `planar/deck_span_cut.at_grade_cells` (R1, R4).** The at-grade plan made pavement is the
deck plan ∩ the mapped airside (`_mapped_airside`, widened by the taxiway shoulder from the law
tables; apt.dat pavement and runways as they are). The remainder of the plan is minted as ordinary
ground beside the taxiway (the existing `adjacent_ground` graded strip), free to bank to the lidar.
Evidence: `deck_at_grade:dsf:obj140#2` (s 630-715, no trench near it) spans off -39..+50 over lidar
114.8-123.8 and solves 120.4-122.3, 1.3-2.2 m under the crest.

Order: F1, replay; F3, replay; F2, replay. One variable per replay.

## 5. Are the low span ends a consequence? Yes, of F1 and F3 together

W span 114.80 -> 115.88 against lidar 115.6 -> 116.7; E span 120.49 / 120.45 against 122.0 / 122.7.
18i (5) seats each end line at "the level the airside solve builds there". With the crest between
the spans replaced by face 443, the only pavement the solve holds at the E span's west line is the
508 m2 shoulder strip on lidar 120.8; east of it cell #2 is dragged by its own slope overhang (F3).
The span mechanism needs no change. If an end is still more than 0.04 m off after F1+F3, read
`deck_anchor.settle`'s per-end level against the adjoining cell's centreline before touching it.

Not in scope, noted: the W floor is deck - 8.70 (the frame's roof top) = 106.6 against a lidar road
of 108.0-108.9. Q344 a keeps lidar unread under a deck; raise it with the master only if the drawn
road shows a step at the mouths.

## 6. Consumer census (08-30l): every pass reading the changed regions

Compiled by grep at 1362aa781; the lane confirms each row with `tools/blast.py` before editing.

| Pass | Reads | Effect of the change |
|---|---|---|
| `planar/deck_bridge.deck_cut` :677 | `_walled_trench` floor/rim -> `ramp`, `outer` | F1: floor shrinks to the opening |
| `deck_bridge.deck_banks` :767, `is_walled` :796 | `_walled_trench is not None` | F1 (b) keeps W/E walled; a side with no wall falls to the 30b bank |
| `planar/deck_bores` :128, `survey_deck_cut` :197 | `is_walled` | unchanged verdict expected; check LGAV / LFPG notes |
| `planar/structures` :1420-1426 | `d_uncut`, `deck_cut`, banks | none; lkrdu3's `uncut` arm stays removed |
| `planar/structures` emit_decks :1477, `structure_deck` :690 | `outer` ∩ object deck plan -> `Deck` rings | rings fall from 12,783 / 8,525 m2 to the opening |
| `structure_overlap` (overlap refusal) | corridor footprints | -17013@0 should admit; assert it |
| `deck_bridge.deck_ground` :896 | cells unowned under a deck ring | banks minted only inside each span |
| `deck_bridge.with_cuts` :109, `planar/cut_frame`, `wing_cut`, `object_floor_cells`, `basins` | tunnels' footprints | smaller footprint; no new reader |
| `planar/build` :290 `at_grade_cells` | deck plan - spans | F2 removes the third span's band; F3 trims to the airside |
| `constraints/structures`, `edge_floor`, `viaduct_floor` | ramp faces, `edge_floor_s`, floor pins | fewer floor vertices; no rule change |
| `constraints/edge_deck` :168 / :590, `deck_anchor` :306 | `DeckBridge.span_cut` | F2: a third graded span, two more end lines |
| `pipeline/rebake_inputs` :285, `airport/rebake_plan` :446, `airport/deck_plates` | `span_cut` spans -> object bands | F2: a third kept band 661-674; diff the rebake PLAN (#625), not body hashes |
| `verify/deck_flush`, census `deck_end_flush` | per-end-line levels | six end lines |
| `auto_patch/object_terrain_features` | `pm.structures` | footprint only |

Heightfield emittability: F1 removes a 15 m step along 405 m of taxiway edge; F3 adds bank ground
with ordinary slopes. No new face kind, role or ref prefix; `MARK` cells keep `deck_at_grade:`.

## 7. Bars (replay; drawn at integration per 17r)

Lidar crest along the axis (max over off ±10): s 0 114.4, 100 114.8, 150 115.6, 220 116.7, 300
117.8, 400 119.3, 500 120.8, 580 122.0, 630 122.7, 660 123.1, 680 123.3, 715 123.7, 760 123.9.

1. Taxiway E centreline within 0.5 m of that profile, s 0 to the twy-A end, outside the openings.
2. Twy-A end within 0.5 m.
3. All SIX span end lines flush within 0.04 m (`deck_end_flush`), each span's grade <= 1.5 %.
4. No `tunnel_ramp`, `retaining_wall` or deck-floor vertex under the at-grade pavement plan; no
   floor face reaching outside s 150-220, 582-630, 655-680 along the taxiway. Report the W / E floor
   areas (expect ~51 x road cut and ~24 x road cut, not 30,034 / 4,395 m2).
5. `tunnel:-17013@0` admitted; `-454` crosses under a span, no stub against pavement.
6. Rebake plan: three kept bands, at-grade bands dropped, nothing else moved.
7. `tests/auto_patch_v2/test_deck_spans.py`, `test_deck_trench2072.py`, `test_deck_cut_cover.py`,
   `test_survey_deck_cut2128.py` green; new synthetic tests: a two-span frame whose walls are
   shorter than its plan (F1), a wall-pair span the survey does not see (F2), a plan wider than its
   taxiway (F3). Ratchets, `test_no_airport_specific_code`, the CI registry gates.

## 8. Replay commands (from `Ortho4XP/`)

    venv/bin/python tools/v2_solve_replay.py --replay /Users/noah/XPTerrainBuilderData/.harness/frames/lkrdu/KRDU.pkl \
        --from planar --json OUT/krdu.json --solved-out OUT/krdu.pkl
    venv/bin/python ../tools/harness/frames.py latest ICAO --kind capture     # each protected airport

`--allow-degraded-dem` is refused at replay (#2038): leave it off. One KRDU replay ran in about
3 minutes here (solve 64 s). Read faces off `--solved-out` (`pm.faces`, `pm.ring_vertices`,
`pm.decks`, `pm.structures`); the object stage through `tools/v2_rebake_replay.py plan`.

Protected airports -- replay `--from planar` before and after on the same capture, one pair each:
KBNA taxiway-L deck 172.0 ± 0.1 and its walled floor polygon IDENTICAL; KEGE, BIKF, OMDB, LGAV,
OTHH, LOWS, NZWN: no vertex moves more than 0.1 m, `is_walled` verdict and floor area per deck
unchanged, no deck newly cut to spans. F2 is the one that can reach them (any frame with facing
walls over a mapped road in an at-grade stretch): list every span it adds anywhere.

## 9. Stop conditions

- Any protected mover > 0.1 m, or a KBNA / LGAV / OTHH walled floor that changes shape: stop, report.
- F1 lands and the pit is still there (bar 4 fails): stop -- the attribution here is wrong.
- F1+F3 land, bar 4 passes, and the centreline is still more than 0.5 m off: stop and report the
  profile; do not tune weights or caps.
- F2 adds a span at any protected airport, or the third opening cannot be confirmed as a bridge in
  the pack mesh: ship F1+F3, hand F2 to the master as an owner question.
- No closing tile build (17r). Never raise the lane cap; delete scratch builds on report.

## 10. Estimate

One Opus lane, effort high (geometry). F1 ~40 lines in two files, F3 ~25, F2 ~60 plus tests;
no new public symbol expected beyond one helper in `geom/wall_lines`. About 6 KRDU replays (~20 min)
and 16 protected replays, run in parallel: 2.5-3.5 h wall. Integration then builds KRDU once and
runs `drawn_gate.py KRDU` at the three bridges, mid-embankment and the twy-A end.

## 11. Not verified

- The third bridge's identity (section 2) and the owner's intended count.
- The pack patch witness levels (road 114, airfield 119): taken from the brief, not re-read.
- lkrdu3's `uncut` arm (111.96): explained from the code, not re-run.
- That F3 alone accounts for cell #2's 1.3-2.2 m: inferred from one replay, no arm isolates it.
- Protected airports: predicted unaffected by F1/F3, not measured.
- The census table is by grep; line numbers are at 1362aa781.
