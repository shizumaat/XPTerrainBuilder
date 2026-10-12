# connect549 — notes (implementation of RULINGS 2026-10-10n/10o at the KCLT garage group; supersedes §64 as written by level549)

## RESUME HERE (2026-10-12, session 2; branch `claude/connect549` on main 1ff5a912a)
* DONE: step 2 arm A2 attribution (below), step 3 = the object cut at a pad level (`pad_block_seat.split_units`
  second pass, commit c5f26c3ae), step 4 = three dry-run arms of `obj8_split_report` on the kclt546 build's plan
  (numbers below). Scratch this session: `<scratchpad 466e18b3…>/connect549/` (p1_rows.py … p5_sites.py, osr_*.json).
* RUNNING / NEXT: closing harness build `connect549_KCLT` (`/private/tmp/harness/connect549_KCLT.*`), then
  `obj8_split_report` on its `.v2/KCLT.rebake.json` + `KCLT.graded.json` (site rows via p5_sites.py), `census.py`
  + `airside_value_delta.py` vs `frames/kclt546/kclt546_KCLT.osm`, register the frame, final report.
* Full non-Qt suite running in the background (`suite_nonqt.log` in the scratch dir); ratchets PASS.


Scratch `<scratchpad>/connect549/` (c1..c5). Branch `claude/connect549` off main b7505552d.

## Step 1 — THE CONNECTION AT KCLT (c1/c2/c3/c5 on plan sw11 v13 + owner's 1.0.387 graded + capture valley2)
* building88 (hourly deck) <-> terminal pads: **125.9 m gap, NOTHING spans it** (no part of any unit within 8 m of both;
  nearest part 22 m from the terminal / 8 m from the deck is an 89 m2 canopy). The terminal's own elevated roadway
  decks (`paredes_8` 19,324 m2 base 6.9, `suelos_interiores` 9,182 m2 base 7.8, `paredes_5` 7,147 m2 base 11.3)
  join building75 / 81 / 83 / the plateau pieces — component 0 — and stop short of the deck. OWNER'S PREMISE
  "the large garage connected to the terminal" is NOT in the pack geometry — FINDING for the master.
* The deck IS connected to the two outer garages: covered walkways `paredes_12` comps 296–303 (5.3 x 68 m), 663–666
  (9.5 x 37 m), 679–682 (4.5 x 36 m), 924 (7.9 x 29 m): h 1.86 m, one per storey at base 2.38 / 5.70 / 9.03 / 12.34 m,
  footless; plus their ground columns (`paredes_12` 203/218: 1.0 x 2.3 m, h 6.0, footed). Component 7 =
  {building86, building90, building88} (c3). Today's design cluster `unit:31#1117` (5 members, 141 bodies, footed 63)
  already chains all three garages (through the columns) but its outline is in 10 pieces (gaps 0.50–1.12 m between
  the column pieces, 4–35 m otherwise) because the walkways are THIN (h 1.86 < chain_min_height_m 2.5) -> leaves
  (§16g (10) (4)), not in the cluster, their rings not in the union; each piece is then its own pad and plane
  (§16g (10) (5)) and seats alone: /2 (deck) 223.21 by a soft term, /0 /4 at their DEM. 09-11i ("one pad across the
  footprint union") is the law that fails here; 08-27's split never fired (no pavement touches: no grade violation).
* (B) base plates (10o) in unit:31: 18 plates / 61,026 m2 — `suelos_interiores` comp 45 (36,377 m2, 238 x 515 m,
  h 0.95, 37 % inside the pads) and `techos_1` comp 8 (23,162 m2, 63 % inside building75): the terminal's forecourt
  slab = object-drawn roads/lots where the toll plaza stands (+4.5 m float). BETWEEN the outer garages: no base
  plate (the only candidates are 1.6–3.5 m kerb strips and an 89 m2 canopy) -> the outer garages are served by no
  pavement in the pack; their seat is their own ground (10n (2)).
* Population (c3, 7 airports; connectors = elevated parts chaining pads): HECA unit:42 component 0 links pads 147/133/
  31/38/13/33 (71–93 m) via `concrete_3` 88.7 x 1160 m plates (h 1.37, base 8.3) and `metal_blue` roofs 69 x 120 m;
  unit:43 component 829 = T3 building4 (101.79) + building6 (92.03) + building7 via 148 x 256 m plates — the 14ah
  precedent (floor plates between buildings) — a connector rule MUST exclude plates: KCLT's walkways are 4.5–9.5 m
  wide, HECA's linking plates 69–148 m: a natural gap [9.5, 69] m. OTHH: unit components all within 0.06 m (flat).
  SPJC 1 unit, CYXY 0, KASE 0.

## Step 2 — the repair site and arm A (branch baf681d99, merged with origin/claude/kclt546 a143765ba -> 6b34588af)
* Site: `constraints/cluster_pad._plane_groups` read each outline PIECE `<cid>/<k>` of one cluster as its own plane
  (§16g (10) (5)); 09-11i says the welded group takes ONE pad across its footprint union. Fix: pieces of one cluster
  are re-united into one plane entry unless a piece is pinned (fronts airside — `pads.pad_fronts_airside` — or is a
  HELD block). Twin `tests/auto_patch_v2/test_connect549.py` (4 tests); the four covering files 62 passed.
* ARM A (KCLT valley2 capture, --from classify --emit --verify): the three garages are now ONE plane — but at
  **223.0–223.4 m**, not their ground: building86 222.99–223.37 (rim z-DEM +4.6..+5.3), building88 223.09–223.14
  (+3.8..+5.1), building90 222.99–223.45 (+0.9..+5.1). Airside movers vs base 0 / 14,894; the terminal pads
  unchanged (building75 222.44, 84 222.70, 92 223.67). So the soft term that held piece /2 at 223.21 now holds the
  merged group there; it is NOT the §9b DEM datum (the group's rim DEM means 218.2–219.5) and NOT a HELD block
  (the capture's 73 HELD refs do not include the garages). Attribution arm A2 (`--solved-out` + `--why-at`
  building86 / building88) running. Until it is named, the fix is NOT the owner's outcome for the outer garages
  ("seated lower"): STOP point if A2 does not name it.
* #547 (kclt546 Finding 2): c3 COMPONENT 0 of unit:31 = {building75 (541 bodies), building81 (89), building83 (3)}
  joined by 829 elevated parts — the terminal's road decks (`paredes_8` comp 23: 106 x 312 m, base 6.93, h 1.07;
  comp 115 52 x 263 m; `suelos_interiores` comp 1 48 x 301 m base 7.8) = class (A) connectors. Connected, and BOTH
  pieces are held by airside at different levels (222.44 / 221.75, 36.6 m of apron between): the 09-11i
  "infeasible -> long-span exception" / 08-27 split case — the group keeps its two held levels with the 0.69 m
  step AT the link, and the object side must seat per piece (`plan_unit_datums` one-zero is the site). Not
  implemented here (design in §64 (3) (e)).

## Step 2 arm A2 — NAMED (session 2; `armA2/KCLT.solved.pkl` read by p3.py)
* The merged garage plane (108 rim vertices, 222.99–223.45) is held by ONE soft row family: `pad_level`
  "structures.building_pad frontage_level (apron; FACING ACROSS BARE GROUND; owner 2026-09-27a (9) Q-11 A)" on
  `face:974` (building86's face) against apron `pav14` / `pav14#plateau:building92` leaders at 222.1–223.7
  (`pavement:apron:facing`). 27a (9): "a pad FRONTS every apron within 50 m across bare ground and takes that
  edge's level; the ground between grades as a terrace" (spec-author decision, "owner may veto"). No pin, no
  HELD block, no §9b datum: the deck piece /2 sat at 223.21 for the same reason before the merge. The "bare
  ground" between the garages and `pav14` is the terminal forecourt — the object-drawn road slab of 10o / #229
  (not pavement in the map), so the facing read is lawful today and would stop once #229 admits the slab.
* So under 10n (1) + 27a (9) the three garages are ONE pad at the deck's level (223.0–223.4), the terminal's
  level in effect (its pads 222.44 / 222.70 / 223.67); the fill at the outer garages' rims is +0.9..+5.3 m
  over the DEM (building86 DEM mean 219.1, building90 219.6, building88 219.4) — "the fill that requires is
  accepted" (10n (1)). The owner's stated KCLT expectation (outer garages "seated lower") is 10n (2), which
  presumes they stand on their own; the pack joins them to the deck with 4 covered walkways per storey
  (4.5–9.5 m wide, 29–68 m long, h 1.86) and their columns. INTENT QUESTION for the owner (report).

## Step 3 — the object cut at a pad level (10n (3); #547) — commit c5f26c3ae
* `airport/pad_block_seat.split_units` gained a FIRST pass (`_split_by_level`): a §16g unit standing on two or
  more plain pads whose medians (`fold_pad_ref`, the one pad datum rule 17t) differ by more than
  `[placement] split_tol_m` (0.3 m — the existing seat materiality, no new key) is one unit per LEVEL
  (`<id>/p<k>`, lowest first; `level_groups`); bodies on no pad resolve by welds then feet exactly as the block
  cut's (the common `_cut_unit`; the block cut is byte-for-byte the same behaviour through it, its 28 tests
  pass). Block pads stay the block cut's (`level_pad_rings` skips them). Contacts are NOT severed at a level
  boundary. Wired: `footprint_seats.plan_wide_seats(level_tol_m=)` ← `placement_plan` passes `split_tol_m`.
* Twin: `tests/auto_patch_v2/test_connect549.py` (+3 tests, 7 total).

## Step 4 — dry-run arms (`obj8_split_report` on `/private/tmp/harness/kclt546_KCLT.v2/KCLT.rebake.json`)
base = kclt546 worktree src (main + #546) on the kclt546 graded surface; fix = this branch, same surface
(object cut alone); fixA = this branch on arm A's graded surface (`armA/KCLT.graded.json`: the garages one plane).
* Site A 35.2224352,-80.9472186 `paredes_5 b0` (19 feet): base y_zero −0.69 on `fu:6:960` "pad building75
  222.44" → fix / fixA 0.00 on `fu:6:960/p0` pad building81 221.75 (own ground +0.00); its 4 carried riders
  follow. Site B 35.2203395,-80.9466805 `paredes_1 b1`: base −0.99 (worst foot 1.22) → fix −0.30 (0.53) →
  fixA −0.15 (0.24); `paredes_1 b2`: −0.86 → −0.17.
* Garages (`fu:31:2809`): base = one zero at building88 223.21, 10 bodies at −2.2..−4.86 (floats 2.2–5.3 m)
  on pads building86 218.14 / building90 218.99. fix (object cut alone): /p0 building86 (+0.07), /p1
  building90 (+0.03), /p2 building88 — but the 7 bodies BETWEEN the garages (on no pad, welded to the deck
  chain) stay on /p2 and still float 3–5 m: the object cut alone is not the fix. fixA (both): one unit on one
  plane at 223.11, every body within 0.48 m (own ground −0.48..+0.00), 2 feet > 3 m airport-wide (the
  forecourt slab `techos_1 b0` 3.86 m — the 10o/#229 base plate — and the 69.8°-tilted `paredes_4 b1`).
* §7 census, feet of all bodies: base <0.3 6360 / 0.3–1 2331 / 1–3 310 / >3 82 (building >3 39, buried 779,
  floating 1944) → fix 7038 / 1694 / 300 / 51 (building >3 1; buried 539, floating 1506) → fixA 7621 / 1747 /
  244 / 2 (buried 487, floating 1506). Bodies 615 → 624 → 587, files 538 → 539 → 507.
