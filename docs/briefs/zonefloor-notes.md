# zonefloor — notes (the zone-part WIDTH floor; spec §59 (4) row 10, review `gapreview` D5)

Branch `claude/zonefloor` (base = main `e2eec15c`, merged in), worktree
`.claude/worktrees/zonefloor`. Scratch `<scratch>/zonefloor/`. Frames
`<frames>/zonefloor/`. Probes: `docs/briefs/zonefloor/zone_probe.py` (planar
stage only: zone parts, runway-ring vertices, map digest, per arm),
`zone_args.py` (pickles `overlay`'s own arguments to `zone_regions`).

## State: BUILT AS RULED, NOT READY — one ruling owed (bottom)

## 1. The fix (as D5 ruled it)

`Ortho4XP/src/auto_patch_v2/planar/zones.py`: `_unmeshable(g, spacing_m)` and
its one call at the part floor's line (`g.area < 1.0 or _unmeshable(g, ident)`,
`ident = law.tables.emit.identity.min_distinct_spacing_m`). The predicate is the
erosion `g.buffer(-spacing / 2).is_empty` — the inline width test of
`classify/gap_mint`, `classify/gap_terrace._under_floor` and
`overlay.dissolve_degenerate_holes` (no shared function exists; `blast.py --find`
thin / sliver / hairline / erod / width) — behind `merge_slivers`' own gate (mean
width `2A/P` under twice the bound; the inradius is never under `A/P`).
`overlay.inscribed_width_m` is the same reading but `overlay` imports `zones`.

## 2. THE FRAME TWIN FAILS ITS BAR: the floor does not make the trim redundant

`frames/gapapron3/HECA.pkl`, planar stage, runway-ring vertices vs the tree's 2,610
(`zone_probe.py`; `<scratch>/zonefloor/heca.log`, `heca2.log`):

| arm | zone parts | runway vertices +/− |
|---|---|---|
| tree (trim, floor) vs base (trim, no floor) | 354 vs 358 (4 dropped) | 0 / 0 |
| 11 cells IN the claim, no floor | 358 | +143 / −3 |
| 11 cells IN the claim, floor (attempt 1 = the ruling) | 353 | **+77 / −3** |
| + slit opening (attempt 2, NOT built) | 354 | **+2 / −1** |

Mechanism (by intervention, `<scratch>/zonefloor/explore*.py`): the re-noded claim
leaves the slits between cells that run edge to edge OPEN. One becomes a part of
its own (`runway:4:zone1#5`, 1.31 m², 1,689 m; widest place 4.1 mm, mean 0.77 mm) —
the floor drops it. The others are LIMBS of real parts: `runway:4:zone1#0` 405.72 m²
with a 1,399 m limb 0.01 mm wide (perimeter 3,075 m against 276.5 m), `zone1#1`
309.90 m² (= the tree's 130.05 + 179.85 joined by 860 m of slit), `zone1#8`,
`zone2#15`, `zone2#26` (27 / 30 / 7 m). No part floor reads a limb.
Attempt 2: every part opened (mitre) at the entry lattice's half-diagonal
(0.71 mm), replaced only where it loses more than 2 × 0.5 m of ring, simplified at
the same radius: the 5 parts lose their limbs and regain the tree's perimeters, no
part of the tree is touched (map digest = the floor-only tree's), and the runway
still takes +2 / −1 — 14 parts of the re-noded claim differ from the tree's by a
vertex. Attempt cap reached; attempt 2 deleted from the tree.

DECISION: **the §59 claim trim STAYS.** The frame twin proves it is NOT redundant.
What is chaotic is the claim's `unary_union`, not a class of part; the protection
is keeping a new stage-1 class out of the claim. (A re-derived classify without
the capture state pops NO hairline with the same 11 cells in — which is why the
twin reads the pickled arguments, `frames/zonefloor/HECA_zone_args.pkl`.)

## 3. What the floor changes on main (base `e2eec15c`)

Planar stage, floor off → on (captures on this tree; `<scratch>/zonefloor/<ICAO>.json`):

| airport | parts | dropped | m² | by band | largest (m², length, where) | runway ring | map |
|---|---|---|---|---|---|---|---|
| NLWF | 8 | 0 | 0 | — | — | 0 / 0 | = |
| KASE | 30 | 0 | 0 | — | — | 0 / 0 | = |
| CYXY | 132 → 130 | 2 | 3.4 | taxi z2 2 | 2.10, 6 m, 60.7060015, −135.0761961 | 0 / 0 | differs |
| SPJC | 167 → 164 | 3 | 15.4 | taxi z2 3 | 10.72, 64 m, −12.0244982, −77.1226243 | 0 / 0 | differs |
| HECA | 358 → 354 | 4 | 9.5 | taxi z1 1, z2 3 | 3.24, 14 m, 30.1172471, 31.3817986 | 0 / 0 | differs |
| OTHH | 485 → 465 | 20 | 103.2 | runway z2 4, taxi z1 11, z2 5 | 27.25, 139 m, 25.2907099, 51.5873126 | 0 / 0 | differs |
| KCLT | 605 → 468 | 137 | 598.3 | runway z1 1, z2 28, taxi z1 91, z2 17 | 30.99, 314 m, 35.2116103, −80.9440890 | 0 / 0 | differs |

No runway vertex is added or removed anywhere. Every dropped part is REAL ground
(mean width 11–400 mm), until now handed to §41 (4)'s sliver dissolve.

Full replays `--from classify --emit --verify` (HECA: `--gap-free --solved-out`
then `--late-from`), `frames/zonefloor/<ICAO>/`, against main's sweep patches
(`/tmp/harness/sw6_*`, `swga_HECA`), `airside_value_delta --tol 0.01`, census:

| airport | body (main) | solve-owned movers / worst | runway | by family | relaxed by tier (main → tree) | CRITICAL motion | CRITICAL visual |
|---|---|---|---|---|---|---|---|
| NLWF | `45ec40e74dcb` (= `45ec40e74dcb`) | — | — | — | — | — | — |
| CYXY | `904925e0eb63` (`cf8e9e89ec62`) | 45 / 0.09 m | 0 | apron 15 / 0.09, strip 25 / 0.03, taxi 5 / 0.02 | groundside 5 = 5, pad 2 → 3, taxi 0 = 0 | 0 = 0 | 52 → **53** |
| SPJC | `77b4054ab8ca` (`61f66f149737`) | 266 / 0.19 m | 0 | strip 125 / 0.19, taxi 38 / 0.12, apron 103 / 0.04 | taxi 6 = 6, pad 1 = 1, groundside 1 = 1 | 0 = 0 | 507 → 501 |
| KCLT | `2904c4157e4a` (`0b1566de77d5`) | 977 / 0.61 m | 0 | taxi 88 / 0.61, strip 615 / 0.60, apron 274 / 0.47 | taxi 51 = 51, pad 4 = 4, groundside 291 → 289 | 5 → **8** | 1,974 → 1,970 |
| OTHH | `927a20beb051` (`73676fda6914`) | 0 | 0 | — (3 nodes removed, 1 added) | 0 = 0 | 0 = 0 | 1,846 → 1,845 |
| HECA | `76b790056234` (`ad4ef9685c5f`) | 20 / 0.01 m | 0 | apron 15, strip 3, taxi 2 (centimetre flips) | pad 17; taxi 63 / 61; groundside 50 — all equal | 2 = 2 | 1,910 = 1,910 |

Bars: runway 0 at 0.01 m — MET everywhere; taxi-tier `hard_conflict` ± 3 — MET
(equal); identity where nothing dropped — MET (NLWF); **CRITICAL rows not rising —
MISSED at KCLT (motion +3) and CYXY (visual +1).** KCLT's three rows: `apron|apron`
0.646 m over 0.95 m at 35.2066181, −80.9462290 (`vertex_to_edge_step`), 0.565 m
over 0.83 m and 0.538 m over 0.79 m beside it (`mid_edge_step`); 30 m from the
dropped `taxi:F:zone2#42` (1.72 m², 16 m). Candidate mechanism, NOT intervened: the
strip between two aprons is no longer there for §41 (4) to dissolve into its host,
so the two rims stand unwelded. KCLT's worst mover 0.61 m `junction|stub` at
35.2051691, −80.9358419.

## 4. The #337 pre-read (OTHH, `frames/zonefloor/OTHH.pkl`)

The 122 pieces of `origin/claude/surfspec:docs/briefs/surfspec/out/OTHH_pieces.json`
(the gap mint's output over the SURFACE-admitted sheets; 30 apron-class by its
estimate) added as cells `gapapron:<k>`; runway ring 1,870 vertices
(`zone_probe.py --bodies`, `<scratch>/zonefloor/probe_OTHH337.log`):

| arm | no floor | floor |
|---|---|---|
| 122 as `gapapron:` cells, trim ON | 0 / 0 | 0 / 0 |
| 122 IN the claim (trim off) | +2 / −4 | +2 / −4 |

No hairline PART pops at OTHH with the bodies in the claim (the thin parts are
main's own 20), so the floor changes nothing there; the ring still moves +2 / −4.
Under §59 the pieces never enter the claim: apron-class ones are trimmed, road-class
ones are late (`overlay` hands `zone_regions` no late cell). With the trim, two
zone parts yield ground where a piece reaches a band (the trim's own guard) —
#337 should confirm its mint's band knife on its own capture.

## 5. Owed: ONE ruling (spec author)

Is the part width floor kept at 0.5 m? YES means a companion rule for the real
strips it drops is owed before merge (KCLT CRITICAL motion 5 → 8; 977 airside
nodes up to 0.61 m). NO means the floor is withdrawn and the trim alone stands.
RECOMMENDATION: **NO — withdraw it.** It reaches no 0 / 0 without the trim, the
trim already keeps the hairline class out (HECA and the OTHH pre-read: 0 / 0), and
no law number separates the noder's hairline (4.1 mm at its widest) from main's
thinnest real part (22 mm at HECA; mean ≥ 16 mm elsewhere): the entry lattice's
diagonal (1.4 mm) does not drop the hairline, and anything between is tuned.
Withdrawing = delete `_unmeshable` and its call; the twins' synthetic half goes
with it, the frame twin's "why the trim stays" half is worth keeping.

## Found, not fixed

* The claim's `unary_union` is input-chaotic for ANY standing cell a later change
  adds (not only §59's): nothing gates "runway ring unchanged" at planar. A
  deterministic claim (bands differenced against cells without one global union)
  is the real general cure; not attempted.
* KCLT carries 137 zone parts under 0.5 m wide (598 m²), OTHH 20, from the terrain
  -edge clip and the stand-offs; §41 (4) dissolves them after their rings have
  noded their neighbours.
* `zone_probe.py`'s first HECA run printed `at` as lon, lat (fixed; the tables
  above are lat, lon).
