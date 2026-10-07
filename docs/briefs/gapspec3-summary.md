# gapspec3 summary — §55 (15): the shape of a part (Fable, 2026-10-07)

Design and review only; no engine code touched. The record is
`design-surface-spec.md` §55 (15) (`tools/docq.py spec '§55'`), founded on
gaps7's build (`gaps7_HECA`, body `54c274700a00`, `docs/briefs/gaps7-notes.md`)
and its three found-not-fixed items A, B, C.

THE LOOP: read-only probes on the build's own artefacts — `gaps7/ARM2/solved.pkl`
(the build's map + solve), the build patch + sidecar, the census rows — with
`<scratch>/gapspec3/probeA.py`, `probe2.py` (seconds) and the offline re-solve
`resolve4.py` (29 s) + `tools/v2_late_read.py` (90 s). Four probes, no replay.

ONE MECHANISM UNDER A AND C: `planar/shapes._label_pavement` labels a gap part
as 08k labels a standing apron — into the pavement union, eroded by half the
mouth, each vertex to the nearest body. So two parts across a 0.75 m knife
welded to one apron carry ONE label (668 of 760 knife step rows: same label
both rims; 51 two labels but no lens pair; 41 on a joint) and a part narrower
than 12 m at a neck is split into two bodies, a contour cut through its one
face (112 of 132), every row across it withdrawn (0 straddling Diff rows
survive inside a part), the surface steps (14 contours beyond cap·d + floor).
Residual 5's DEM hypothesis is refuted and deleted.

RULE A+C — a gap part is ONE SHAPE BY KIND; its knives are its only joints:
(1) parts out of the pavement union (standing labels = the no-part map's);
(2) one label per STEP PART (lot + ramp one), welded rim vertices keep the
standing label; `shape_of_face` by kind; (3) NEW `model.planar.shares_gap_part`
read by `straddles` AND `declarable_pairs` (the #253 pattern) — no contour, no
row withdrawn inside a part. PROBED: gap joints 48 → 79 covering 2,514 m of
2,027 m facing rim (one 9 m stub short); 749 of 760 knife rows within 1 m of a
joint declaring ≥ their step (7 under-declared, 4 uncovered at building6's
foot); contours 132 → 16 (14 ribbon, 2 standing). RE-SOLVED with the withdrawn
rows re-added (1.58 M, solve 19 s): the four cliffs 4.95 → 0.76 m over 8.9 m,
4.53 → 0.64, 4.23 → 1.16, ramp1 0.52 → 0.28; in-part pairs beyond the floor
14 → 2 (+0.09 / +0.03); relaxed 89 → 93; movers 0; own-group 46; stepping
85/68; sites 97.46 / 97.56 / 90.24 unchanged — P12 within ±5 %.

RULE B — the census learns the floor THROUGH THE SIDECAR: new law-input key
`late_stage` {floor_m, followers} published by the stage; the census builds
`late_stage_unknown_nodes` (a node on gap-part / published follower ways only)
and adds `floor_m` in `within_shape`, `pavement_over_road_cap`, `cross_shape`
for unknown–unknown pairs; `cross_shape` also reads the declared-step
allowance (it reads no joint today). Frame twin: the node set = the stage's
unknowns by the 11-dp join. The 352 beyond-floor rows: 327 are C, 9 merged
station (residual 1), 7 constant-end at gap:15 (residual 3, lawful), 2 at
`gap:1` unattributed.

hard_conflict siding: one line (role `groundside_pavement` when the record's
tier is groundside).

PREDICTED CENSUS vs BASE after A+B+C (from +3,885): within_shape ≈ −150…−250,
pavement_over_road_cap ≈ +5, mid_edge_step ≈ +10, vertex_to_edge ≈ +2,
cross_shape 0, terrace_actual_step +11, road_cross_section +79 (untouched; the
S0 read still owed), hard_conflict +89 now groundside; total ≈ −50…+50,
airside ≈ +10. ±25 % per family = STOP.

CONSUMER TABLE (16 rows in (15)): three CHANGE sites (`_label_pavement`; the
predicate via `straddles`/`declarable_pairs`; the three census families), two
NEW records (sidecar key; `ShapeStats.part_contours_undeclared`), one line
(`hard_conflict`); every other reader none, two to be read at the replay
(`_shape_bodies` datum — P8 refuted it as a lever; the LP-size line).

STEP PLAN: S-A1 predicate (0.5 h); S-A2 labels + twins (2 h); S-B sidecar +
census (2–3 h); S-D siding (0.3 h); S-E ONE replay + reader + census (0.5 h +
15 min); S-F suites, `rows_class.py` promoted as a `census.py --class` bucket
(1 h); S-G ONE HECA build + `--workers 1` (20 min). ≈ 7–9 h wall; build time
predicted ±10 s (≈ 460–480 s cold).

RESIDUALS for the sim read (coordinates in (15)): the gap:8 interleave (11.18
m, 30.1151145, 31.4106671); merged-sliver steps at five pads (Q6); ribbons
that step where a knife crosses them (`small_roads:-18752` 5.11 m at
30.1156804, 31.4079978) and the ribbon terrain floors; gap:34 / gap:37; the
floor welds (Q4: 8.1 %, 9.9 %, 8.2 %); the 7 + 4 under-declared knife rows,
`gap:1`, j103; the follow-miss bar (46 own-group) still not met.

NEW OWNER QUESTIONS: none; Q1–Q6 stand. Q4 now also decides B through the one
published number.
