# Lane `padfix` — notes (branch `claude/padfix`, base `origin/claude/padsweep` 090f28244, code head c1a26f166)

Scratch `<scratch>/padfix/` (`.progress`, drivers `rows_at.py` / `near.py` / `framed.py` / `pad36.py` / `arm_rimpin.py`,
copies in `docs/briefs/padfix-scratch/`). Captures: the registered `frames/pads67/<ICAO>.pkl`. Sweep artefacts read:
`/tmp/harness/sw10_<ICAO>.*` (main) and `sw11_<ICAO>.*` (merged).

## RESUME HERE

Code head 9cb3819d1 (ONE code change: `solve/feasibility.row_tiers`, item 3). Items 1, 2, 4, 5, 6 attributed; item 3
fixed; item 7 not implemented (the read below refutes half (i)'s premise; half (ii) not started). Closing section at
the end of the file: suites, replay pairs, the `sw12_HECA` row. Only HECA's body changes.

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

## Item 3 — HECA `building36` | `dsf:objpav366` 30.11685, 31.38175: ATTRIBUTED BY INTERVENTION, FIXED (9cb3819d1)

SITE NUMBERS (replay pair on `frames/pads67/HECA.pkl --from classify --gap-free --emit`: `h0` = control tree
`padfixctl` at c1a26f166, `h1` = the fix; `h0` reproduces sw11's record exactly):

| | main sw10 | merged (sw11 = `h0`) | fix `h1` |
|---|---|---|---|
| `building36` record | held, datum 63.319, tilt 0.0, welded 13 | RESIDUAL, datum 63.544, tilt 0.321, released 13 of 13 (worst 0.281) | **held, datum 63.267, tilt 0.002, welded 13, released 0** |
| the pad's 13 emitted vertices | 63.32 all | 63.26 × 11, **63.51 and 63.54** at the road weld | 63.26–63.27 all |
| §5a stage 2 at the site | — | 2 `frontage_hold` relaxed 0.245 / 0.250 m (tier pad) against 1 `pavement_max_grade ceiling` | 0 pad rows; the road's own rows relaxed (`road_cross_section` 16, ceiling 11, tier groundside) |
| HECA §5a stage 2 (final) | — | 302: gs 269, pad 32, taxi 1 | 299: gs 270, **pad 28**, taxi 1 |
| hold verdicts | held 32 | held 37, residual 2 | **held 38, residual 1** |

PARENT: `claude/weldverify` (the touch-weld). `frames/pass2/HECA_auto.patch.osm` and `pads67/sw8_HECA` read held
63.306 / 14 vertices; `weldverify_HECA.osm` reads residual 63.543 / 15 vertices.

MECHANISM. The pad was never released by the airside: its 10 airside rim vertices and 3 near-miss contacts stand at
the pad's level in both arms. What moved is ONE CORNER of the pad — the vertex the touch-weld shares with the rim strip
`dsf:objpav366#2` and the road `small_roads:-3884` (30.11669816, 31.38145248) and its neighbour 0.5 m away — which the
record reads as "the datum" (`pad36.py`: with the weld EVERY vertex of the pad is a weld, 10 airside + 5 groundside, and
`model.platform.datum_vertices` takes a groundside weld as the datum column), so all 13 contacts read "off the datum".
The corner was lifted because the §5a LP relaxed the PAD's two hold rows instead of the ROAD's cap:
`solve.feasibility.row_tiers` ranked a `pavement_max_grade ceiling` row groundside only when one of its vertices was
touched by NO airside pavement. The road's ceiling between the pad's corner (roles building + service_road) and the
apron contact 4.0 m on (`dsf:objpav114` + the road, 63.75) has two "airside-touched" vertices, kept the TAXI rank and
outranked the pad tier — 09j (1) / 10a (2) (b) inverted at exactly the place the weld creates.

FIX (general, one derivation site): a two-vertex side-ranked row whose vertices share pavement faces, NONE of them
airside, ranks in the groundside tier — it is that road's or lot's own cap between two welds. Twins in
`tests/auto_patch_v2/test_ceiling_side_rank.py` (rank; and the LP: the pad's plane holds, the road's ceiling relaxes
0.3 m) — both fail on c1a26f166.

WHAT THE FIX MOVED (`airside_value_delta h0 h1`, 0.02 m): row-side 2 nodes (the pad's corner −0.27 / −0.25 m), 6
`service_road` nodes ≤ 0.28 m (`dsf:objpav366#2` 4, `small_roads:-3884` 2); solve-owned airside 0; runway 0;
structure 0.

THE ROAD'S RESIDUAL CLIMB IS THE MAP, not a row that should have yielded elsewhere. `small_roads:-3884` lies along
the edge of apron `dsf:objpav114` — its end vertices ARE that apron's (63.75 at 30.11666659, 31.38147325; 64.06 at
30.11685612, 31.38183117) and it stands at 63.86–64.03 between them — 3–4 m outside the pad's SE rim, which junction
`dsf:objpav365` and the same apron's far corner hold at 63.26 (10 airside rim vertices). Two senior airside levels
0.5–0.8 m apart, 3–4 m apart in plan (main: 63.32 vs 63.80–64.11, the same 0.5–0.8 m, read then as a TOUCH-OFF step
of 0.72 m). The weld puts the whole difference across the 0.95 m rim strip (knife line tied to the rim at 63.26–63.29,
the road's own edge at 63.86–64.0): the census's 15 `mid_edge_step` `service_road|service_road` rows of 0.51–0.68 m
over 0.65–0.98 m. They stand after the fix (the road did not move); 10a (2) (b) is what the surface does there.

## Item 4 — HECA `mid_edge_step` +9 CRITICAL visual: what it is

16 new rows, 13 gone (`<scratch>/padsweep/m/HECA_{base,arm}.rows.json`). 15 of the 16 new are item 3's site
(`service_road|service_road`, ways −11662 | −11663, 0.51–0.68 m). The 13 gone: 7 `apron|building` (the collar's rim
rows, to 1.54 m) and 6 groundside.

The 16th, 4.69 m `groundside_pavement|groundside_pavement` at 30.11594978, 31.40754772 (ways −12145 | −12016):
the wall of a DECLARED GAP TERRACE between two late-stage parts of one gap piece — `gap:0/s5` (sidecar `gap_pieces`
kind `step`) against `gap:0/s0/lot` (kind `lot`), whose edges run 0.5 m apart between `building10` (103.2) and
`building26` (90.2). `osmnear.py` on the two patches, the node pairs along the seam: main 97.46 | 95.09 (2.37 m),
98.87 | 93.43 (5.44 m); merged 98.78 | 94.72 (4.06 m), 100.88 | 93.06 (7.82 m). The step part was re-cut (4,312 m² on
main, with `s9` / `s15` beside it → 6,660 m² merged) and the lot fell ~0.37 m with `building26` (90.56 → 90.20). The
wall is on main too; `terrace_actual_step` groundside went 29 → 15 in the same build — the one row is the stretch of
the wall where a vertex of the step part faces the lot's edge mid-span with no declared joint point beside it (joint
points within 45 m: 222 → 202). Groundside, a terrace wall (09f), reported under a different family: not a new step.

## Item 5 — `hairline_pair` against the parents' expectation: every count is a sum of recorded pairs

The parents' "+30 / +43 / +122" are weldverify's figures against ITS base (the collar-less tree), not against main.
main → merged also crosses the collar deletion (PR #480, the common ancestor), whose own pair is `pads67-notes.md`
(main → sw8):

| | collar deletion (main → sw8) | R-D (seat2 notes) | R-E (reverify m → c2) | weld strips (weldverify) | sum | observed sw10 → sw11 |
|---|---|---|---|---|---|---|
| HECA | 1,851 → 1,896 (+45) | +7 | +7 | +30 | +89 | +91 (main itself 1,851 → 1,853 between the two sweeps) |
| KCLT | 1,969 → 1,993 (+24) | 0 | 0 (CRITICAL visual 1,996 = 1,996) | +43 | +67 | **+67** |
| OTHH | 2,040 → 1,923 (**−117**) | 0 | 0 (byte-identical) | +122 | +5 | +4 |

So: the surplus over the weld's own count at HECA and KCLT is the collar deletion's (the pads' simplified outlines'
own sub-spacing pairs), in both parents. The OTHH "drop" is not a drop of the weld's rows: the +122 is real (merged
CRITICAL visual 2,054 = weldverify's `ov6` 2,054 exactly) and the collar deletion had removed 117 collar hairlines
first.

## Item 6 — KCLT families rising airside on the merged head, one line each

| family | which change (the recorded pair) | read |
|---|---|---|
| `taxi_box` +3 (13 new / 8 gone; worst 0.70 m at 35.22399174, −80.9375963) | pass2's linear-solve fix (pass2 census m / c2 / f: 224 / 224 / **227**; weldverify 224 → 223) — the worst two are R-E's junction below read by the box family | DEFECT-class rows (an airside junction over its cap), pass2's found-not-fixed; not minted by the merge |
| `transverse` +4 (6 new, 0.49–0.70 m over 25 m, all on junction way −10177 at 35.2240, −80.9376) | R-E (reverify m → c2: 4 → 8; weldverify 4 = 4): the junction sinks 0.30–0.47 m against a runway-side edge that does not move | DEFECT (a junction 2.8 % across), R-E's, not fixed here |
| `pad_airside_renode` +6 (7 new / 1 gone, magnitude 0) | the collar deletion (sidecar key: main 47, `pads67/sw8` 53, pass2 53, merged 53) | REPORT rows (where the pad cut re-noded an airside ring); lawful |
| `pad_airside_weld` +2 (0.64 m over 92 m at 35.21610606, −80.92907988; 0.16; 0.14) | the common ancestor (weldverify's base `kb0` 7 = `kv6` 7 = merged 7; main 5) — neither parent | DEFECT of item 7 (ii)'s class: a pad with no vertex of its own on an apron sheet is not one level |
| `strip_arc` +1 (0.39 m over 40 m at 35.22118171, −80.93695414) | R-E (reverify m → c2: 11 → 12; weldverify 11 = 11): one graded-strip vertex 224.65 → 224.71 against 225.10 unmoved | lawful movement, a row at its threshold (CRITICAL `strip_arc` 4 = 4) |

## Item 7 — the all-welded pad: NOT IMPLEMENTED; half (i)'s premise is refuted by the population, half (ii) not started

READ (`padrelief.py` on the sw11 graded surfaces + sidecars: every pad by base ref, its vertices classed OWN / welded
to AIRSIDE pavement / welded to GROUNDSIDE pavement only; relief = max − min over its ring):

| class (pads / with relief > 0.05 m) | HECA | KCLT |
|---|---|---|
| every vertex welded, all to airside pavement (`building99`'s class) | 17 / **16** (to 1.42 m `building150`; `building99` 1.05) | 20 / **19** (to 1.63 m `building68`) |
| every vertex welded, groundside only (`building12`'s class) | 3 / 2 (`building12` 1.17 m over 175 m = 0.67 %; `building23` 0.09) | 2 / 1 (`building59` 0.57 m over 108 m = 0.53 %) |
| every vertex welded, both sides | 1 / 1 (`building36` 0.28 — item 3; 0.01 after the fix) | 0 |
| OWN vertices + an airside frontage (the held pads) | 37 / 10 (the held ones ≤ 0.55 m: relaxed planes) | 53 / 4 |
| **OWN vertices, landside (no airside vertex)** | **154 / 48** (`building120` 3.13 m over 237 m = 1.32 %, 57 of 57 vertices its own; `building86` 1.27 m, 40 of 40 own; `building5` 1.01; `building44` 0.83; `building59` 0.75) | **23 / 8** (`building26` 0.55, `building56` 0.49, `building90` 0.45 with 52 of 52 own) |
| landings | 6 / 6 | — |

HALF (i) — STOPPED AT THE READ. The brief's class for `building12` ("no own vertex → no datum column → nothing holds
it flat; the same class as `building99`") does not survive the table: a landside pad is not one level today WHETHER OR
NOT it has vertices of its own — 48 of HECA's 154 landside pads with own vertices have relief (the worst, all 57
vertices its own, 3.13 m), 8 of KCLT's 23. `pad36.py` on `building12`: its rows are `structures.building_pad flat`
(cap 0, the PRICED zero-tilt target of `pad_flat_rulings`) and the hard `pad_slope_max ceiling` (1 %), exactly a
landside pad's with own vertices; it is not in `HELD` (a hold is an airside frontage's), and its 0.67 % is inside the
1 % ceiling. So the rule as briefed ("a pad whose every vertex is welded takes a datum column") would level 2 of
HECA's 50 tilted landside pads and 1 of KCLT's 9 and leave the other 48 / 8 tilted by the same mechanism: not a
general rule, and not the cause. The general statement would be "every pad without an airside hold is ONE hard level
(the 1 % `pad_slope_max` allowance no longer applies to it)" — a change of `emit.toml [within_shape] pad_slope_max`'s
meaning for ~200 pads per large airport, groundside only (no airside vertex can move: they are all stage-2 columns).
QUESTION (yes / no): "Is a landside pad one hard level, the lots and roads welded to it taking the grade (10a (2)),
instead of a plane that may tilt up to 1 %?" RECOMMENDATION: yes for a pad with a building on it (09-09c "a building
pad is ONE PLANE"; the 1 % was the allowance for the frontage fit, and 10a (2) now says which side yields) — as its
own change and sweep, with the landings excluded (their relief is the viaduct's).

HALF (ii) — NOT STARTED (budget: it needs stage-1 follower rows, two replay pairs each at HECA and KCLT, and
`--null-change`; padsweep's arm stands as the only measurement: 16 pads take a rim datum, `building99` 1.05 → 0.02 m,
2,879 solve-owned airside vertices moved up to 1.72 m, stage-1 LP relaxing 2 pad rows). Facts gathered for whoever
takes it: the class is 16 pads at HECA and 19 at KCLT, 0.41–1.63 m of relief, tilts 0.84–1.74 % over the pad's extent
(up to 4.99 % across `building99`'s short side); KCLT's two new `pad_airside_weld` rows (item 6) and HECA's are this
class read by the census; the pad's own `pad_slope_max ceiling` rows already exist over those apron vertices but are
stage-2 rows over constants (their violations are the pad-tier `hard_conflict` rows: HECA 20 `pad_slope_max ceiling`
after item 3's fix, KCLT 15).

## Closing — suites, replay pairs, the one rebuilt airport

SUITES at 9cb3819d1: non-Qt split 9,220 passed / 19 skipped / 1 xfailed / 1 xpassed, 0 failed (142.9 s); Qt 311
passed; the four named files 204 passed; `tools/ratchets.py` DUPLICATE RATCHET PASS, LAYER RATCHET PASS (no size
WARN line names `solve/feasibility.py`; the WARN lines are the parents').

REPLAY PAIRS, fix tree against the control tree `padfixctl` at c1a26f166 (`rep.sh`: `frames/pads67/<ICAO>.pkl
--from classify [--gap-free] --workers 9 --emit`; the emitted patch hashed):

| airport | control → fix | what moved |
|---|---|---|
| HECA (`h0` → `h1`) | patches differ | 2 `building36` nodes −0.27 / −0.25 m, 6 `service_road` nodes ≤ 0.28 m; solve-owned 0; runway 0; structure 0; §5a stage 2 pad 32 → 28; held 37 → 38 |
| KCLT (`k0` → `k2`) | e622670f7b40 = e622670f7b40, **byte-identical** | nothing (§5a 309 = 309: gs 276, pad 33) |
| NLWF / CYXY / KASE / SPJC (`s0_*` → `s1_*`) | 4dde63cc7243 / 74bea73af5f1 / e07070eabaa6 / e05b2a22d77d, each **byte-identical** | nothing |
| OTHH (`o0` → `o1`) | see the last line of this file | the §5a LP relaxes 0 rows at OTHH in every solve (`lp relaxed 0=0`), and `row_tiers` is read by that LP only |

REBUILT: HECA only — `tools/harness/build_airport.py HECA --tag sw12_HECA` on this tree, rc 0, status optimal,
668.5 s (a single correctness run beside nothing else; not a timing), body `9a8766eac4a3` (sw11 `645b3b7f49f3`, main
sw10 `5fce51e016a0`). Frame registered (`frames/padfix/sw12_HECA.osm`).

`sw12_HECA` against `sw11_HECA` (`airside_value_delta`, 27,973 = 27,973 nodes, none added or removed): row-side 2
movers (the pad's corner, 0.27 m), `service_road` 6 nodes ≤ 0.28 m; solve-owned 0 of 17,430; structure 0 of 245.
Census rows sw11 → sw12: `pad_frontage_infeasible` 5 → 4 (the 0.281 m row at 30.11721238, 31.38159758 gone),
`hard_conflict` airside 33 → 29, pad tier 32 → 28, hold verdicts held 37 → 38 / residual 2 → 1; and — the cost, all
at the one road beside `building36` — `mid_edge_step` groundside 55 → 60 and `vertex_to_edge_step` 16 → 17 (five
0.51–0.63 m rows and one 0.58 m row over 0.47–0.61 m at 30.11672..30.11679, 31.38151..31.38163): the pad's corner no
longer rises 0.27 m to meet the road, so the road's step off the knife line runs on to the corner. CRITICAL visual
2,032 → **2,038** (+6, these rows); CRITICAL motion 3 = 3. `road_cross_section` 555 → 567 is REPORT rows (the LP's
relaxed set, groundside 359 → 360), no node moved with them.

The per-airport row, sw10 (main) → sw12 (`<scratch>/padfix/m/HECA_row.txt`, the same reader as padsweep's table):

```
=== HECA: body 5fce51e016a0 -> 9a8766eac4a3; status optimal; patch wall 569.2 -> 668.5 s; rebake plan sha 1956d7537290 -> 75018e8013b8
  MOVERS row-side: 10445 > 0.02 m, worst 9.48; A-only 375 B-only 294; {'other': (2306, 9.48), 'apron': (2236, 5.19), 'taxi': (2339, 1.16), 'strip': (3453, 0.73), 'runway': (111, 0.13)}
  MOVERS solve-owned: 5893 > 0.02 m, worst 2.19; A-only 0 B-only 8; {'apron': (2136, 2.19), 'taxi': (2339, 1.16), 'strip': (1307, 0.59), 'runway': (111, 0.13)}
  MOVERS structure: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  RUNWAY nodes moved > 0.02 m: 111, worst 0.13 @ 30.13223500946, 31.39747096527
    runway way 05C/23C: 1154 joined, worst |dz| 0.03 m, worst shape 0.038 pp / 30 m, sites > 0.1 pp: 0 []
    runway way 05L/23R: 686 joined, worst |dz| 0.13 m, worst shape 0.24 pp / 30 m, sites > 0.1 pp: 10 [(0.24, '30.12694322, 31.39039445'), (0.159, '30.13852330, 31.40588179'), (0.151, '30.13935325, 31.40651482')]
  PAD EDGES (runs / m) base -> arm: AIRSIDE 31/556 -> 3/46; BARE 297/14831 -> 326/17058; ENGINE 41/331 -> 22/302; GAPPED 2/66 -> 5/86; HELD 4/165 -> 1/2; TOUCH-OFF 13/446 -> 3/49; cls:M 243/7872 -> 258/10569; cls:S 1/0 -> 1/0
  PLATFORMS 42 -> 47; hold verdicts {'held': 32, None: 8, 'residual': 2} -> {None: 8, 'held': 38, 'residual': 1}; datums moved > 0.02 m: 26
    held pads 38: datum off its held contact > 0.02 m: 3 [('building165', 0.105), ('building157', 0.075), ('building169', 0.059)]; tilted (tilt_pct > 0.05): base 3 -> arm [('building100', 93.4), ('building169', 0.08), ('building5', 0.212), ('building59', 0.319), ('building101', 0.513), ('building178', 0.603), ('building93', 0.06)]
  HARD_CONFLICT by tier: {'groundside': 209, 'pad': 24, 'taxi': 63} -> {'groundside': 360, 'pad': 28, 'taxi': 1}
  CENSUS law-true total 56069 -> 56282; ADJUDICATED airside-for-acceptance 12176 -> 11929; by side airside 12167 -> 11920, groundside 2234 -> 2692, mixed 9 -> 9
    rising airside as in sw11 (adjacent_ground_step +3, airside_no_step +26, pad_airside_weld +2, pavement_over_road_cap mixed +2, strip_seam_tear +14, taxi_box +1, transverse +22) but pad_frontage_infeasible 0 -> 4 (sw11: 5); hard_conflict air 87 -> 29 (sw11: 33)
    mid_edge_step air/mixed/gs 6/0/46 -> 0/0/60 (sw11: 0/0/55); vertex_to_edge_step 2/0/13 -> 1/0/17 (sw11: 1/0/16); road_cross_section gs 518 -> 567 (sw11: 555)
  CRITICAL_MOTION: 3 -> 3; CRITICAL_VISUAL: 1913 -> 2038; without hairline_pair 60 -> 94; hairline_pair 1853 -> 1944 (+91)
  QP exits arm: every solve optimal (15)
```

NOT RE-RUN on this head: `--null-change` (the fix touches only the §5a LP's row ranks; HECA's line on the merged
head stands in padsweep-notes §5); KCLT / OTHH / SPJC / CYXY / KASE / NLWF builds (bodies unchanged: replay patches
byte-identical, or — OTHH — see the last line).

## Found, not fixed

1. KCLT `door:paredes_11_charlotte.obj@0` (35.22182657, −80.94183645): the cliff at the top of the door ramp — the
   framed plane's last pinned station 220.93 against the apron's top vertex 222.36, 1 m apart; the well 2.3 m deep
   (item 1: a question, both answers measured or described).
2. The framed plane of a door well is derived against the DEM (`top_ground_z`) while its top vertices carry the
   apron's solved value: on main the apron stood 0.55 m under the plane's design top at that well.
3. `airside_value_delta`'s structure frame counts a `structure_rim` vertex the pavement shares as a structure node:
   it reads an apron mover as a structure mover (KCLT 11; SPJC 19 in pads65's notes).
4. HECA `building36`: 15 + 6 CRITICAL visual step rows on the road between the pad's rim and apron `dsf:objpav114`'s
   edge 3–4 m away (0.5–0.8 m apart in level) — 10a (2) (b) as the census reads it; no family exempts it.
5. `model.platform.datum_vertices` takes a GROUNDSIDE weld as a held pad's datum column when the pad has no vertex of
   its own off the airside (HECA `building36`: 10 airside + 5 groundside welds). With item 3's fix the column holds
   (63.267, tilt 0.002); the docstring's "never a weld" is no longer true of it.
6. The landside pads: 48 of HECA's 154 and 8 of KCLT's 23 landside pads WITH vertices of their own have relief
   (to 3.13 m, 1.32 %) — item 7's question.
7. The 16 / 19 pads on an apron sheet with no vertex of their own (HECA / KCLT) are not one level (item 7 (ii), not
   started); KCLT's `pad_airside_weld` +2 is that class.
8. KCLT junction way −10177 at 35.2240, −80.9376 sinks 0.30–0.47 m under R-E against a runway-side edge that does not
   move: `transverse` 6 rows to 0.70 m / 25 m, 2 `taxi_box` rows (item 6; pass2's found-not-fixed).
9. HECA 4.69 m `mid_edge_step` at 30.11594978, 31.40754772: a declared gap terrace's wall reported under the step
   family along the stretch with no joint point (item 4).

OTHH replay pair (`o0` control → `o1` fix): 8bfbeeeb5e8b = 8bfbeeeb5e8b, **byte-identical** — nothing moved; the structure frame at OTHH is the merged head's (item 2).
