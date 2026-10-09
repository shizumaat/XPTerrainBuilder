# gapapron — spec §59: an apron-touching gap piece is a road by road evidence, else the apron (2026-10-08)

Lane `gapapron` (Fable, design only), branch `claude/gapapron` off main `3f9a349d`.
Deliverable: `Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md` §59 (new;
§55 (3) 6 and §55 (12) Q3 carry one-line supersessions). Probes in
`docs/briefs/gapapron/` (`evidence_read.py`, `neck_read.py`, `arm_driver.py`,
`evidence.json`); frames under
`/Users/noah/XPTerrainBuilderData/.harness/frames/gapapron/` (`ARMBASE/`,
`ARM/`: patch + sidecar + `solved.pkl` + log; the reads `arm.txt`,
`arm.site.txt`, `main.site.txt`, the two `delta_*.txt`), registered in
`docs/frames.jsonl`. Capture: `frames/gaps3/HECA.pkl`; classification
`<scratch>/gaps5/cl.pkl` (the mint is unchanged since it was written).

## The existing road-evidence rules (found, reused — no second rule)

* `classify/roles._road_evidence`: a 1206 route or OSM `highway` chain within
  `cells.on_tol_m` (1 m), or a `service_road` / `parking_lot` face touching
  within `groundside.touch_tol_m`. Blind to a piece on two PARAMETERS
  (`ev.road_chains` is clipped to the pavement union; a piece stands 1.45 m
  off road faces) — §59 adds `touch_tol_m=` / `touch_roles=` with today's
  defaults and calls `evidence._osm_roads` once more over the sheet union.
* `classify/airside_edge.airside_edge_flip` (§27 12c/12f + §37 (2) 13q-7):
  ≥ 10 m lateral airside edge flips a groundside face to apron unless the
  contact is a MOUTH; a road-by-evidence face flips only at ≥ 20 % of its
  perimeter (the free-road ruling). The gap mint runs AFTER it (`roles.py`
  :634 / :670), so no piece was ever judged — §59 adds `road_class=` and the
  mint calls it on the apron-touching parts.
* `classify/neck` (§43): probed as a local witness — 0 necks on 17 of 19
  pieces; the class is per piece.

## The class table, HECA (20 touching pieces, 831,854 m²)

| class | pieces | m² |
|---|---|---|
| ROAD (late §55 piece, unchanged) | gap:0, 2, 4, **7** (#430/#292), 11, 12, 28, 29, 34 | 819,950 |
| APRON — no road evidence | gap:22 (573), gap:24 (549), gap:36 (249) | 1,371 |
| APRON — road evidence, lateral share ≥ 20 % (§37 (2)) | gap:13, 15, 16, 17, 20, 30, 33, 37 | 10,533 |

Owner sites: all in ROAD pieces; 06d's lot + ramp unchanged
(97.47 / 97.57 / 90.25 vs 97.46 / 97.56 / 90.24).

## "Graded with the whole apron" — the probe (ARMBASE vs main's `sww_HECA`, same tree)

11,904 m² of apron class moved standing apron 102 refs / 2,692 nodes worst
2.47 m (`pav6` 100.80..101.97 → 102.18..103.27; `objpav106#2` 1.68 m),
junction 131 / 2,471 / 1.38 m, cross_connector 24 / 971 / 1.38 m (`pav111`),
graded_strip 1.79 m, pads 0.34 m (= drift), runway 2 refs / 29 nodes /
0.02 m (`05L/23R` 24 nodes — the bar is 0; S0 attributes). Tree-drift
control (gaps6 BASE vs sww): apron 0.04, junction 0.40, runway 0.
Stage-1: +154 unknowns, +4,221 hard rows (+0.8 %), taxi-tier relaxations
66/64 vs 63/61 (heads unread), base shapes 53 vs 52, 2 contour joints (10 m)
vs 0. Late stage after it: 28 pieces → 80 parts, 48 knives, movers 0 of
34,705, follow misses 69 = DECLARED 38 + OWN-GROUP 31 (worst 2.06 m),
stepping pairs 65 / 59 / 18, knives 46 worst 7.94 m, ribbons grown 9; one new
conflict `gapapron:7` 72.77 vs `pav39` 71.97 (0.77 m) at gap:34. Part levels
today → apron: gap:22 −0.87, gap:30 −0.56, gap:37 +0.60, gap:16 −0.33,
gap:33 +0.27, others ≤ 0.15 m.

## Census (`census.py sww_HECA.osm ARM --class`)

19 min. ADJUDICATED 14,901 → 14,436 (airside +27, groundside −489);
hard_conflict 309 → 347 (+38, standing|standing; late stage 91 → 77 by head,
so the base's +52); airside_no_step +9; CRITICAL motion 3 → 4: a NEW
`mid_edge_step apron|apron` 0.616 m over 0.99 m at 30.1278259, 31.4046286 —
`gapapron:7` (gap:30) beside `pav39`, rims within the weld spacing but not
coincident, no follow row any more → §59 (2) 4 closes an apron part's rim
onto its apron rings at the mint. NOT the arm: transverse +521,
pavement_over_road_cap −182, within_shape −771 move on rows the arm never
touched (route3|route3, gap:7/ramp1) — build-vs-replay instrument; S6 reads
replay vs replay.

## Owner questions (§59 (7))

Q7 the pull accepted (recommend YES, runway held at 0); Q8 the §37 (2) share
makes a road-evidenced strip along an apron APRON (recommend YES); Q9 the
06d lot keeps its terrace beside a sloping apron (recommend YES; no code
depends on it).

## Not settled

The runway 0.02 m; the +3 taxi-tier heads; the 2 base contour joints; a
same-tree build-time pair; the census as a bar line; gap:15's point reads no
level on either arm.
