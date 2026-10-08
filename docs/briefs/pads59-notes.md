# pads59 notes — 4B's copy, 4C, 4D, 4E built; bar 3 (c)/(d) MISSED and attributed (Opus implementer, 2026-10-08)

Branch `claude/pads56` (PR #463). Spec `tools/docq.py spec '§56'`. Continues `pads58-notes.md`.
Scratch: `<scratch>/pads59/` (`cmp.py A.axes.json B.axes.json` = bar 3 (a)–(e); `movers.py A.graded.json
B.graded.json TOL`; `notrend_patch.py TREE` = the scratch arm below; `s1_4a.json.gz`, `s1_4c.json.gz`,
`s1_diff.txt` = the stage-1 population diff). All HECA arms: `tools/v2_solve_replay.py --replay
gaps3/HECA.pkl --from classify --emit DIR --verify --workers 6` (8–10 min each on a quiet machine).

## Commits (each revertable alone)

| sha | what |
|---|---|
| `d0c6dfc7` | R1 + R2: the warning copy without the Why sentence; spec §56 (3) copy and bar 3 (d) amended, marked pending spec-author review |
| `faa2789a` | R3 (4): `placement_read._banks_as_platform` — the fold narrowed to banks (a landing's `#collar`, a block's `#strip`) |
| `055e08f1` | step 4C — the deletion core |
| `c9dcc09e` | R3 (3): `pad_block_seat._platform_polys` keeps every ring of a block |
| `66ddcf7b` | R3 (6): `check_grade._check_platform_rim_relief` skips a record with no `rim_relief_max_m` |
| `90bc0e27` | step 4D — the `platform_collar` knob deleted; R3 (1) `platform_collar_max_m` kept and re-commented as the landing bank's width |
| `b63cce36` | step 4E — family texts, the allow-list note |

R3 (2) (`coverage_edge_collar_vertices` stays) and R3 (5) (`pads.py:605` / `:970` stay true for a landing)
needed no code: both readers are untouched (`:605` also reads the flat-held unit refs).

## What 4C is

- `planar/platform.platform_split` is the block planner: no erosion, no `#collar` region, no
  `under_min_area` / `eroded_away`. One block → the region WHOLE under its ref + `HELD[ref]` with the
  plan's record; several → `_mint_blocks` (block faces `<unit>/b<k>`, the strip half `#strip`). A unit
  with no plan, a draped facade and every §20 pad over `min_area_m2` are conforming-held as before.
- `model/platform.datum_vertices`: ONE rule — an own (non-airside) vertex farthest from the weld.
  `datum_vertex_of`, `held_platform_vertices` deleted. `Platform` = `ref, pad_m2, welded_samples,
  relief_m, refused`.
- `constraints/platform`: `unit_pad_faces`, `_contact_sets` / `platform_contacts` (contacts = the face's
  airside vertices; flat = the rest but a vertex another PAD carries — a bank face is no floor),
  `flat_held_refs`; the flat rows over the flat set; `hold_sets` over the contacts (ramp mask, plateau
  as before); a near-miss endpoint joins when its pad vertex is flat; `platform_records` (no collar key)
  + `_landing_records` (the landing's old record). The landing's `#collar` pair keeps `collar_faces`,
  `_bank_rows`, the basis plane and the contact-led level rows exactly as they were.
- `constraints/pads`: `platformed` (no §30 (6) relief on the plate) also for a flat-held unit ref.

## Bar 3 on the HECA gaps3 replay, 4C vs the 4A/4B arm (`<scratch>/pads58/heca_4b`, reproduced
byte-identically by a fresh run of `d0c6dfc7`)

| bar | result |
|---|---|
| (a) released set | **MET** — `building101, 132, 141, 150, 158, 186` in both; the 3 erosion-refused pads are held with 0 released: `building96` 0/12 (datum 101.263), `100` 0/32 (92.438), `162` 0/13 (74.651) |
| (b) no release grows > 0.05 | **MET** — `101` 0.328 → 0.328, `141` 0.260 → 0.261 (6/33 → 5/34), `132` / `158` / `150` 0.043 / 0.043 / 0.042 unchanged, `186` 0.021 |
| (c) tiers | **MISSED** — pad 14 → 133, groundside 168 → 178, **taxi 70 → 73** (3 new stage-2 `pavement_max_grade ceiling` rows, 0.038–0.153 m, at `gap:15` 30.10462, 31.39655 ×2 and `dsf:objpav3` 30.12166, 31.42041) |
| (d) `|datum(4C) − datum(4A)| ≤ 0.05` | **MISSED on 10 of 45** — `building101` −0.108, `51` −0.105, `61` −0.105, `62` −0.106, `63` −0.106, `64` −0.106, `88` −0.106, `90` −0.106, `81` −0.092, `82` −0.092 (one welded cluster at 30.119–30.122, 31.406–31.409); every other pad ≤ 0.012 |
| (e) WARNED ≤ 3 | **MET** — 1, `building101` (line in the lane report) |

The pad tier's 133 = 98 `pad_slope_max ceiling` (87 of them one cluster, `unit:41#103` face 963) + 25
`platform plane` + 10 `frontage_hold`, all stage 2: the unit pad's rim against rows that hold a rim vertex
elsewhere — the "ladder demotes the pad's flat" class the spec predicts (§56 (6)).

## Attribution of (c)/(d) — measured, three arms

1. **The stage-1 population diff** (`--stage1-dump` on both arms' `--solved-out`, `--stage1-diff`):
   columns 19,335 = 19,335 with **9 swapped** (the nine unit pads' datum columns: the interior platform
   vertex is gone, the column is a rim vertex); least-squares rows: `apron_trend` **8 removed / 8 added /
   47 retargeted**, `detached` 9 / 9; one-sided: `platform_collar` 1,116 removed / 1,126 added / 60
   retargeted (the hold rows re-keyed on the new column, +10 = near-miss joins), `pavement_ceiling` +44,
   `proximity` +2, `runway_flex` 968 retargeted; triangles and sheet faces identical. Pass 1a did not
   move (`datum_median` ±0.002 on the ten pads).
   The `apron_trend` row is the one with a level in it: `solve/design_assemble` step 9a gives every
   vertex of `planar.apron_trend_z` a trend row unless it is `pad_follow` (a `pad_level_rulings`
   vertex); a held pad mints no level row (30bb F4), so its DATUM COLUMN takes a trend row at the
   point where the column's vertex stands. Moving the column moves that target by metres (T3
   `building3`: 99.97 → 92.90 m; a cluster pad 88.66 → 90.32 m).
2. **Control arm** (4A code, datum = the HIGHEST-id platform vertex instead of the lowest — a pure
   relabel inside the interior): pad datums ≤ 0.001 m, apron movers 0, hard_conflict 252 → 253
   (groundside 168 → 169) — but junction 231 movers to +0.57 m, graded_strip 427, secondary_parallel
   27 to +0.32 at 30.1017–30.1066, 31.3967–31.3990. That SW taxi-family region moves under a null
   change: it is this frame's noise floor for taxi-family movers and for ±1 conflict rows.
3. **Intervention** (`notrend_patch.py`: the datum columns take NO `apron_trend` row), in the 4A code
   and in the 4C code: in 4A alone it moves 10 of 39 datums by > 0.05 (worst `building51` −0.119 — the
   same cluster, the same size as the 4C shift); 4C-without vs 4A-without then differ on ONE pad over
   0.05 (`building141` −0.078; `101` +0.044 with 4 released of 16 instead of 3), apron movers 1,158 →
   865 (median −0.08 → +0.04), taxi tier 71 → 73.

So: most of (d)'s miss is the datum column's trend row moving with the column; a residual stays
(`building141`, the elastic LP's choice at `101`), and (c)'s three taxi rows are stage-2 consequences
inside the frame's noise. NO FIX WAS IMPROVISED: there is no interior vertex to keep the column on, and
taking the trend row off datum columns changes main's levels at 10 HECA pads.

QUESTION for the spec author (yes / no): may the datum column of a held pad take no `apron_trend` row
(add it to `pad_follow` in `design_assemble` 9a — "a pad following its frontage takes no trend row",
10l, read for the hold)? RECOMMEND YES, as its own step with its own sweep: it removes the only level
term that depends on WHERE the column's vertex stands, which 4C necessarily moves; it costs ≤ 0.12 m at
10 HECA pads on main's own frame. Either way bar 3 (d) at 0.05 is not reachable for `building141` and
(c) "count-identical" is tighter than the frame's own noise (control arm) — the bars need restating.

R4 (the datum below `datum_median` on 33 of 39 pads, worst −4.65 m `building85`) is NOT this: with the
trend row off the datum columns the gap reads the same (median −0.68, worst −4.66). Still unattributed.

## LANDINGS APPEAR (a reader the census does not rule — reported, not decided)

4A arm and main's sweep (`swg_HECA`): 0 landings. 4C: **5 at T3** (`building3/landing0..4`, 6 minted).
`planar/landing._key` finds a viaduct's block by a point-in-polygon over the held blocks' regions; for a
one-block unit that was the ERODED platform (the collar had another ref), so a viaduct standing in the
15 m annulus found no block and minted nothing. With the pad whole it is found — which is what a cut
unit's block polygon (never eroded) always did. Consequences on the replay: lots cut around five
landings, service_road / parking_lot movers to +7.44 m at 30.11408, 31.39756, groundside conflicts
168 → 178 (in part), T3's west rim on the plane (+8.83 m at 30.11141, 31.39239 where the collar banked
to ground). `landing._unit_collar` (the landing may take ground from its unit's COLLAR) now matches
nothing, so a landing takes nothing from its unit's pad. NOT changed: keeping "0 landings" would need
the erosion back. The owner ruled the landings (2026-10-03e, #290); whether their return belongs in
this PR is the master's.

## Found, not fixed

- R4, verbatim from the brief: the pad `datum` is lower than `datum_median` on 35 of 39 HECA pads, worst
  4.65 m at `building85` — unattributed; and it is NOT the datum column's trend row (above).
- The datum column of a held pad carries an `apron_trend` row (above).
- `constraints/platform.py` is 1,194 lines (was 1,113): the landing's pair path and the unit pad's path
  now stand side by side. A split (`constraints/landing_bank.py`) is the next reader's first move.
- `Platform.relief_m` / `planar/platform.rim_relief_m` (the DEM relief read at the mint) is now only a
  record field; no reader decides anything from it.
- `landing._unit_collar` matches nothing (above); `platform_level_rows` / `contact_led_refs` /
  `refused_plates` now serve only a landing pair and a draped facade with the hold off.
- The generator name `platform_collar` and the ruling heads `… platform_collar bank / rim / terrace`
  are kept (they are row identities in `emit.toml` registers and in every sidecar).
