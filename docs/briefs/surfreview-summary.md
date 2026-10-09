# surfreview — spec §60 (#337 through the gap stage) as BUILT: review, two blockers attributed, rulings, fix list

Lane `surfreview` (Fable, spec author / reviewer; NO engine code), 2026-10-09.
Branch `claude/surfreview` off `claude/surf337` 64945f43 (main e2eec15c).
Spec: `Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md` **§60 (9) AS BUILT / REVIEW**
(the rulings R1, R2, (a)–(d), the fix list, the owner question). Probes
`docs/briefs/surfreview/`; frames `frames.py list OTHH` (lane surfreview: the two
P3 patches copied, the base pickle by path).

## Probes

| # | what | cost | result |
|---|---|---|---|
| P1 | B1 geometry read on the lane's build patch vs main's `sw6_OTHH.osm` | s | `basin_wall:4` rim gains 3 nodes at −9.52 / −8.25 / −8.04 shared with `gap:1/s3`; `:0` 9 nodes (1.97..3.96) with `gap:2/s1`, `:3` 10 (2.14..4.03) with `gap:1/s4`; floors `basin_floor:4/0/3` (`tunnel_trench`) at −9.68 / −0.74 / −0.35, unchanged |
| P2 | code read: `planar/basins.build_basins` knife loop (flush cut of every non-structure cell, `gap:` included) vs `structure_approach.cut_gap_cells` (stood off); `gap_follow._OWN_RIM_M` 0.3 m skip; floor cells as ordinary neighbours | — | the mechanism, three parts |
| P3 | A0 gap-free base `--solved-out` (8 min) → A1 control `--late-from` (identity: 1,072 / 1,072 way groups = the lane's build body `b58e5698e7c5`) → A2 `arm_rimfollow.py` (below-grade family excluded as follow neighbours + 26 rim pins) | 8 + 8 + 7 min | three parts flat at their rims (3.96); relaxed 7 → 0; `hard_conflict` 7 → 0, `mid_edge_step` 24 → 0, `vertex_to_edge_step` 3 → 0, `within_shape` 528 → 374 (= main), rows ≥ 0.5 m 500 → 308 (main 287); CRITICAL visual 2,111 → 2,084 (approach 21 → 3, runway 9 → 0); 1,061 / 1,072 way groups identical, 0 non-gap groups changed; SEAT table identical |
| P4 | B2 offline: `deck_datum_from_surface` re-run on the lane's graded surface, all vertices / gap-owned excluded / main's surface | s | gap excluded ⇒ every one of the 8 differing members reads main's value (`None` ×6 bridges, Emiri 4.0, TerminalRoads 4.61); the arm's datums are medians of 1–4 gap-piece vertices (`gap:13`, `:41`, `:2/s0`, `:37`, `:10`, `:3`) |
| P5 | HECA way-group read, main `swga_HECA` vs `surf337_HECA` | s | 222 / 1,311 groups differ, 13 gap; `gapapron:1/:2` 42/35 nodes, 11/14 moved ≤ 0.06 m; `gap:8/s0/lot` 88 → 88 nodes, 3 moved (2.37 m); runway groups identical |
| P6 | the spec's `admit_probe.py` on the 2026-10-04 capture under this tree | s | its "SURFACE-only" class is empty now (the tree's gate agrees): the 122-vs-131 split cannot be re-measured on the old capture |

## Rulings (full text in §60 (9))

* **R1 (B1)** — the cells behind a declared step (`emit/graded.FLOOR_ROLES` + the wall void `retaining_wall`) are never follow neighbours; a part follows the structure's RIM at ground; no part re-nodes a rim with a non-rim level (`authored_seats` hard bar). R1a = the family exclusion in `gap_follow`; R1b = the basin cut through `cut_gap_cells`' stood-off blade (Q1), else the pin.
* **R2 (B2)** — an object-stage datum read off the solved surface reads STANDING cells only (§53 (18) reaches the object stage); an after-mesh abutment walk sees everything. Six-unit table in metres in §60 (9): Bridge_01 −0.33 m and TerminalRoads_Parking −0.39 m WORSE, Bridge_06 −0.12, Bridge_04 −0.08, the rest same level by the wrong reader.
* **(a)** HECA airside movers are the §59 pull (lawful, 08g/08c (1)/09b); the 2.37 m lot is the §55 cut's discreteness, not §61's non-uniqueness. **(b)** D1–D5 ACCEPTED (D1 and D4 correct the spec's own text; D3 replaces `gap_sheet_admission.py`; D5 a one-off). **(c)** the §59 D1 closure slivers are lawful; (2)'s bar re-spelled. **(d)** the intake is as estimated (FREE within 0.2 %); the +9 pieces are this tree's standing cells.

## Fix list (implementer; each a commit; replays off `frames/surf337/OTHH.pkl` + `surfreview/base/solved.pkl`)

1. F1 R1a `constraints/gap_follow`: skip `FLOOR_ROLES` ∪ {`WALL_ROLE`} faces as neighbours (+ twin) — 1 h; bars: the three parts within 0.02 m of 3.96, relaxed 0, `within_shape` 374, rows ≥ 0.5 m ≤ 308, no non-gap group moved.
2. F2 R1b `planar/basins`: a `gap:` cell is cut by the rim ⊕ `standoff_m` via `cut_gap_cells` — 1 h + a `--from classify` replay; bars: rim node counts = main's, `groundside_pavement|tunnel_trench` rows 0, cliff 18. After Q1.
3. F3 R2 `pipeline/build._rebake_inputs` / `emit/rebake.deck_datum_from_surface`: gap-owned vertices excluded (+ synthetic twin) — 1 h; bar: the plan from the screen sidecar sha-identical to `sw6_OTHH.v2/OTHH.rebake.json`.
4. F4 closing build OTHH (body = the F1+F2 replay's, plan = main's, ≤ 660 s), then the master's sweep.

## Owner question

Q1 — a basin rim gets the 1.45 m ground collar every tunnel wall has (pavement stops short of the pit lip; rim never re-noded) rather than pavement welded flush to the lip at the rim's level? RECOMMENDATION: YES.

## Not done

* No engine code (by brief). No `v2_late_read` on the arm (the census and the way-group read carried the bars). No OTHH build.
* The +222 `hairline_pair` rows (the pieces' own knife / stand-off pairs) read, not ruled — the master's, with the lane's census.
* The split of the +9 pieces between the walls-era cells and §59's trims (P6: not measurable on the old capture under this tree).
