# Lane `walls3` — notes (2026-10-07; continues `cloudwalls` PR #460, implements object-placement spec §18)

Branch `claude/walls3` = `origin/claude/cloudwalls` 1ba381b5 + main 318efe5b + `origin/claude/authspec` c108304c.
Scratch: `<scratchpad>/walls3/` (`pd2.py` planar dump off the capture with seat records / basin refusals / deck
intervals; `pd1.pkl`, `pd3.pkl`, `pd3.log`; `pits.py` the intake read of every pit placement; `step1.txt`).
Capture: `/Users/noah/XPTerrainBuilderData/.harness/frames/perfB362/OTHH.pkl` (`--from planar`).

## Task 1 — D's red twins: DONE (7371f213, f3223f8a)
25 twins read the road cap from the law; fixtures whose meaning needed the number are re-derived from it.
Two things for the master:
- `test_v2doorramp::test_law_register` asserted door_ramp cap > tunnel_ramp / service_road cap. All three are 10 %
  now (07d + 17h Q1), so "strictly steeper" no longer holds — asserted as "never below". QUESTION: is that the meaning
  wanted, or should door / wall-corridor ramps stay strictly steeper than the road?
- A 26th twin CI never sees (it needs the mounted frames): `test_gap_terrace::test_the_rule_read_on_a_real_map…`
  (HECA, frames gaps3). D changes it: parts 93 -> 84, knives 48 -> 34, merged 66, dropped 6 -> 9 m2, and the owner's
  pavement-gap site 30.1159784, 31.4106264 reads `gap:7/lot` where it read `gap:7/ramp0`. Re-recorded; the HECA
  pavement-gap geometry DOES move with the 10 % cap.

## Task 2 — §18: step 1 measured, rule implemented (88bb16fb)
### Step 1 (the replay §18 (8) asks for first) — `h_cut` per wall on A+B+C+D
| wall | h_cut (m) | §18 expected | h_uncut |
|---|---|---|---|
| tunnel south west 2 | 2.15 | 2.04 | 4.50 |
| tunnel1 (x2) | 1.98 / 1.98 | 2.00 / 1.99 | 4.55 |
| tunnel middle - west | 2.00 | 2.00 | 2.00 |
| tunnel middle - east | 2.00 | 2.00 | 2.00 |
| tunnel_sw (#453) | 1.58 | 2.21 | 5.00 |
| tunnel west 2 (#455) | 1.59 | 2.07 | 5.00 |
| tunnel west 3 (#454) | 2.59 | 2.62 | 6.00 |
| tunnel west 1 | 2.40 | 2.4 (flat portal) / 4.95 (ramp) | 7.50 |
- `tunnel west 1` is a FLAT PORTAL (bores at both ends, grade 0) — §18's second reading.
- All nine read in band (0 … 3.0): nine kept, none re-seated; median stated height 2.00 m.
- `tunnel_sw` / `west 2` read 1.58 / 1.59, not 2.21 / 2.07: the full-length ramp (07b (2)) is shallower under the
  anchor than the OSM ramp §18 (2) sampled. §18 (8) step 6's acceptance "crest 2.0 ± 0.3" at #453 misses by 0.12 m.
- The two `middle` walls' anchors stand BESIDE their trench. §18 (3) (a)'s formula text says "the ramp profile at the
  anchor's station", which reads 0.19 / −0.41 there; §18 (2)'s own table reads them on uncut ground (2.00). The code
  follows the table: the floor where the anchor stands inside `Corridor.trench`, the ground where it does not.

### The pits — §18 (5)'s expectation FAILS (STOP, reported)
Expected basins by resource 2 -> 8. MEASURED 2 -> 4: `Drainage_01` (basin:1, rim −0.02 m) and `Dewatering_01`
(basin:2, rim −0.14 m) are cut and kept; `Drainage_02..05` are REFUSED as basements (04i rule 4).
Mechanism: each pit is two placements at one anchor with one lift (+4.2985): `_001` (floor plate −3.816, lift − depth
0.48: in band, read ground-seated, 1–3 floor witnesses) and `_000` (deepest solid −2.943 for 02..05, lift − depth 1.36:
OUT of the 1.0 band, left lifted). The lifted `_000` then stands over the floor and the region reads 100 % under its
own object's solids at or above the ground. `Drainage_01_000` is −3.609 (0.69: in band), which is why 01 works.
Not fixed (spec frozen; a wider band would be a number tuned to one pack). Candidate rule for the spec author: the
lift is one decision per ANCHOR FAMILY (same anchor, same lift) — if one member reads lifted-by-its-own-depth, its
siblings are read ground-seated with it.
- Rim: the floor row cuts `floor_clearance_m` (0.5) UNDER the floor plate, so the rim of a kept pit lands −0.02 /
  −0.14 m (at grade), not §18's +0.48 / +0.36 (07c (5) says "about 0.4 m over grade").

### Deviations from §18's text (all reported, none decided silently)
1. Kept members are EXCLUDED (the existing "terrain adapted" skip), so they are in no unit; the record is plan-level
   `RebakePlan.authored_seats` (id, resource, datum, seat, h_cut_m, h_uncut_m, proud_m / agl_authored_m), not three new
   `Member` fields.
2. The proud height rides the existing plate CLEARANCE (`Datum(plate_y − clear)`), no new `plate_proud_m` field.
3. Re-seat target = the pack's MEDIAN stated height (07c (4)), not §18 (3) (b)'s per-wall `h_uncut`.
4. `PlacedObject.agl_m` stays the AUTHORED lift; the new flag is `ground_seated` (+ `base_z`), where §18 (5) names
   `agl_read` / `agl_authored`. Forty readers of `agl_m` need the authored value.
5. The lift is measured against the deepest GENUINE solid (a decal under a shell is not its depth), and only for a
   shell at least `admission_depth_m` deep; a lift that founds no pit is read as it was. (262 placements — people 4 cm
   off the ground — passed §18 (5)'s bare test.)
6. A plain pit whose anchor stands OUTSIDE its floor (rim at grade) is now "authored (cut)": no plate entry. Its plate
   delta was ~0 before, so nothing visible changes; `test_v2othh3` re-stated.
7. Plan version 13 with the read window widened to five (v9 still loads — `test_welded_deck` twins it).
8. NOT DONE: the `seat` column in `v2_solve_replay --emit/--verify` and `obj8_split_report.py` (§18 (6) last row);
   LEMD read (§18 (8) step 7).

## Task 4 — #450: attributed and fixed (986a1ef9)
`tunnel:-1355@0`: mouth at 25.2542625, 51.6212946 (the owner's true mouth). `climb_from` 260.3 = far edge + gap of
OBJECT deck `dsf:obj11305` (deck top 10.03 m) crossing the approach at s 152.3..259.7. The free ramp reaches the
ground ~51 m out, so the bridge stands 100 m beyond the ramp; the owner's "no tunnel here" site is ~82 m out, under
260 m of flat trench. The object branch already drops such a deck; the mapped-bore branch did not.
`structure_deck.decks_over_climb` (new) is that rule. Reaches every airport with a mapped bore and a bridge / object
deck beyond its free ramp top.

## Task 3 / 5 — see the final report (replay chain, closing build, reach).
