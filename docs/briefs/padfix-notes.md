# Lane `padfix` — notes (branch `claude/padfix`, base `origin/claude/padsweep` 090f28244, code head c1a26f166)

Scratch `<scratch>/padfix/` (`.progress`, drivers `rows_at.py` / `near.py` / `framed.py` / `pad36.py` / `arm_rimpin.py`,
copies in `docs/briefs/padfix-scratch/`). Captures: the registered `frames/pads67/<ICAO>.pkl`. Sweep artefacts read:
`/tmp/harness/sw10_<ICAO>.*` (main) and `sw11_<ICAO>.*` (merged).

## RESUME HERE

See the last section of this file for what is done and what is running.

## Item 1 — KCLT, 11 structure-frame nodes 1.41–1.43 m at 35.22182657, −80.94183645: ATTRIBUTED, NOT FIXED (a question)

SITE NUMBERS (sw10 main → sw11 merged; `near.py` on the two graded surfaces):

| vertex | main | merged |
|---|---|---|
| the 8 rim vertices of the well (apron `pav14` hole-ring vertices on the `retaining_wall` void) | 220.94–221.02 | 222.34–222.44 (+1.41..+1.43) |
| the 3 ramp-top vertices (apron `pav14` + `door_ramp`) | 220.94–220.96 | 222.35–222.38 (+1.41..+1.42) |
| the well's own pinned floor (4 `door_ramp` vertices: sill 220.09, plane 220.11 / 220.83 / 220.93) | same | **unmoved (0.00)** |
| `building75` (the pad whose face the well is cut at; rim vertices 3 m away) | 221.02 | 222.44 |

WHAT THE STRUCTURE IS. Not a tunnel: a pack DOOR WELL (`door:paredes_11_charlotte.obj@0`, `source = door`, object-framed,
`pinched` = "framed by the pack's own objects: no grade cap (07e)", sill 220.09, `top_ground_z` 221.50, DEM on the rim
221.50–221.59) cut into apron `pav14` at the face of `building75`. The 11 "structure" nodes are APRON vertices: the
`airside_value_delta` structure frame includes the `structure_rim` breakline, whose vertices here are all shared with
`pav14`. Rows on them (`rows_at.py`, the replay's own constraint set): `common.roles.apron` ring edge / preferred tier /
body chord, `pavement_max_grade ceiling`, `airside_no_step`, `structures.building_pad frontage_level` and the ONE-SIDED
`structures.structure_rim frontage_level` (10an). NO ROW of the structure generator states a level on them:
`constraints/structures._rim_rows` skips a rim vertex the governed ground shares ("the ground's value carries the rim",
the M4 ground rule + owner 2026-09-10an "the rim is flush with the pavement it sits in"), and the framed ramp's top vertex
the ground shares "keeps the ground's own value". No road, no weld partner, no rim-strip tie and no pad row is on them.

WHICH PARENT, WHICH CHANGE (by intervention, existing one-variable pairs — nothing rebuilt):

| pair (A → B) | structure frame |
|---|---|
| seatspec base → seatspec ARM E (`frames/seatspec/KCLT_auto.patch.osm` → `KCLT_armE.patch.osm`: R-E's cross-ring apron chords the ONE variable, one tree, one capture) | **the same 11 nodes, 1.41–1.42 m** |
| main sw10 → `frames/pass2/KCLT_auto.patch.osm` (parent `claude/pass2`) | the same 11, 1.42–1.43 m |
| weldverify `kb0` → `kv6` (parent `claude/weldverify`, its own notes) | 0 of 363 |

So: parent `claude/pass2`, change class spec §62 (4) R-E ("an apron sheet is one body across its holes"). Not the
touch-weld, not a rim-strip tie, not the linear fix.

WHAT HELD THE RIM ON MAIN, WHAT REPLACED IT. Nothing held it on main either. The well's rim is part of the hole ring of
`pav14` that carries `building75`; on main that hole ring was "seated alone" (R-E's own attribution: no within-shape row
between a hole ring and the rest of the sheet), the held pad stood at its contacts' level 221.02 and the rim, 0–3 m from
the pad's rim under the apron's 1.5 % ring edges, stood at 220.94–221.02. R-E put the hole ring on the sheet: the sheet
and `building75` / `building83` went to 222.44 (`pav14#plateau:building75` 220.30..221.73 → 221.57..222.44, 521 nodes),
and the rim went with the apron it is a vertex of. The AUTHORED part of the structure — the sill and the framed plane —
did not move.

WHAT IS WRONG AT THE SITE (a defect, but not "a structure was moved"): the framed plane is pinned as ONE line from the
sill (220.09) to `top_ground_z` (221.50, the DEM), while its top vertices carry the apron's SOLVED value. main: the apron
stood 0.55 m UNDER the plane's design top (220.95 vs 221.50) and happened to meet the plane's last interior station
(220.93) within 0.02 m. Merged: the apron stands 0.86 m OVER it (222.36), so the last pinned station (220.93) is 1.43 m
under the ramp-top vertex about 1 m away — a cliff at the top of the door ramp, and a well 2.3 m deep where the frame
gives 1.4 m. The latent mismatch (plane derived against the DEM, top carried by the solve) is on main too.

INTERVENTION ARM, measured and NOT landed (`arm_rimpin.py`: every shared rim / ramp-top vertex of an object-framed door
well PINNED at the well's own `top_ground_z`; replay of `frames/pads67/KCLT.pkl --from classify --emit`, 12 vertices
pinned at 221.50):

| read vs main sw10 | merged sw11 | arm |
|---|---|---|
| structure frame | 11 nodes, 1.41–1.43 | 11 nodes, **0.48–0.57** (the rim at the frame's own ground 221.50) |
| `building75` / `83` datum (main 221.02) | 222.44 | 221.59 |
| `building81` (main: refused) / `building84` (main 222.63) | 221.75 / 222.70 | 220.90 / 222.20 |
| solve-owned movers > 0.02 m | 3,869: apron 2,384 ≤ 1.44, taxi 732 ≤ 1.35, strip 753 ≤ 1.00 | 3,781: apron 2,354 ≤ 1.08, taxi 677 ≤ 0.72, strip 750 ≤ 0.57 |
| runway | 0 | 0 |
| stage-1 §5a LP | 0 relaxed | **6 relaxed, tier pad (`frontage_hold` of `building75` against the pins)** |
| stage-2 §5a | 309 (gs 276, pad 33) | 301 (gs 268, pad 33) |
| `hard_conflict` by tier | gs 276, pad 33 | gs 268, pad 39 |

READ: no principled level gives "0 vs main" — main's rim value was the apron's solve (0.55 m under the frame's ground),
not an authored quantity; the only way back to main's numbers is main's apron level at `building75`, i.e. R-E off on
that sheet. The arm (the structure as a fixed contact of the apron) brings the whole sheet 0.85 m back toward main and
halves the taxi / strip worst movers, but it leaves the structure frame at 0.5 m against main and relaxes 6 pad holds
in stage 1. Not landed: attempt cap respected, and it is a law choice (below), not a plain defect.

QUESTION (yes / no): "Where a pack's own objects frame a well in an apron (door well, wall corridor), is the apron at
the well's rim HELD at the ground level the frame was authored against, the sheet and the pads on it grading from
there — rather than the rim following wherever the apron's solve puts it (10an)?" RECOMMENDATION: YES (07b / 07c (3) /
07f: authored structures are not re-seated and the engine cuts the terrain the author's elevations expect; 10a (2):
a pad is held by what it touches that cannot move — an authored well in the pad's face cannot). If NO, the general fix
is the opposite one: the framed plane tops at the SOLVED ground (a `Linear` from the sill to the top vertex's column,
07c (1) "exempt cap, no step at the door"), which removes the cliff but lets structure vertices move with the apron by
design — and then the structure-frame bar must exclude rim vertices the pavement shares (as pads65 read SPJC's 19
`channel_wall` rim nodes: "solve-owned movers seen through the rim"). Either is its own change with its own sweep
(OTHH's door wells are read by the same rule).

## Item 2 — OTHH, one `structure_rim:tunnel_wall` node 0.04 m and one `basin_wall` rim node re-sited: ATTRIBUTED, lawful

SITE NUMBERS (`near.py`, sw10 → sw11): 25.26473780, 51.61171830 — 3.92 → 3.96; its two neighbours on the same ring
3.96 = 3.96 and the wall-corridor ramp vertex 0.7 m away 2.57 = 2.57. 25.26436318, 51.61131128 (A-only) 3.96;
25.26501762, 51.61258695 (B-only) 3.96; every ring neighbour of both 3.96 = 3.96.

All three are vertices of the ONE pad `building6` (main: face `building6#collar`; merged: face `building6`), standing
on a wall-corridor rim / the basin wall's rim breakline. Neither parent brought them: the IDENTICAL delta — the same
mover, the same A-only and the same B-only node, 2,546 nodes, 1 / 1 / 1 — is in `frames/pads67/sw8_OTHH.osm` (PR #480,
the collar deletion alone, before `pass2` and `weldverify` existed), read here with `airside_value_delta sw10_OTHH
sw8_OTHH`; lane pads65 recorded the mover when it landed (`docs/briefs/pads65-notes.md`, arm `f2` c35bed63: "main 3.92 →
3.96, the pad's own level; on main that rim vertex sat 0.04 under it in the collar's bank"). weldverify's own pair
(`ob0` → `ov6`) reads 0 of 2,546 and reverify's OTHH pair is byte-identical.

- The 0.04 m: with the collar gone (§56 (3)) the rim vertex is a point of the pad's plane (10an: a void wall's rim is
  flush with the surface it sits in; `model.platform.structure_vertices` keeps only value-carrying ramp vertices out of
  the flat set). It now stands AT the pad's level with every other vertex of the pad; on main it was 0.04 m low in the
  collar's bank. No wall, ramp or floor pin moved (ramp vertex 2.57 = 2.57).
- The re-sited node: the pad's outline is the §56 simplified outline (straight chords), not the collar's ring: one
  chord station fewer at 25.26436318, 51.61131128 and one more at 25.26501762, 51.61258695, both on a flat run of the
  pad at 3.96 between unmoved neighbours. No rim level changed; the rebake plan sha is identical to main (8e24e55b3f68).

VERDICT: lawful, no fix. The structure bar of 0 is met for every value a structure states; the three nodes are the
pad's own, changed by the ruled collar deletion (07b (4) / 07c (6)).
