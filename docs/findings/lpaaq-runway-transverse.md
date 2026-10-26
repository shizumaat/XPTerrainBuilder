# #1363 — PAAQ `runway_transverse` 2 on face 10 with an empty hard set

Lane `lpaaq`, 2026-10-26, base `origin/main` c95b84fb6. Capture
`PAAQ.pkl` (tile +61-150, 4422 vertices, 317 faces), replayed with
`tools/v2_solve_replay.py --replay … --from constraints --verify`.

## Site numbers

| reading | before | after |
|---|---|---|
| `runway_transverse` DEFECT rows | 2 (5.03 % over 22.0 m, 5.02 % over 21.5 m, face 10) | **0** |
| verify rows, all families | 317 | 315 (only the 2 false rows go) |
| stage 1 / stage 2 hard set | 0 violated (max 0.0139 m) | unchanged (verify-only change: the solved surface is the same) |

The two rows are vertices **v363** (61.598113, −149.087873; the north-east
corner of 16S/34S, 1.11 m) and **v311** (south-east corner of 16S/34S, near
61.5939, −149.0876; 1.08 m).

## Attribution

Not a post-solve step. The replay's `--verify` reads the solved surface
straight from `graded_surface` with no emit, projection or decimation step
in between, and it reproduces both rows. The solve is right by its own
hard set. The census and the generator disagree on **who owns a vertex**.

- PAAQ has the gravel strip 16S/34S (half width 9.1 m) parallel to 16/34
  (half width 15.2 m), 30 m between crowns. Face 10 is 16/34's west shoulder
  band, x = 44.5…52.5 m: its west edge IS 16S/34S's east edge, so v311…v363
  sit on face 10 (ref 16/34) and face 51 (ref 16S/34S).
- #1149 (EDTK) ruled that such a vertex takes the transverse law of the
  runway whose own edge it is, the least `d − half`. For v311 that is
  16S/34S (−0.16 m) against 16/34 (+6.2 m).
- The generator (`constraints/runway_profile._transverse_owners`) measures
  `d` with `_foot` = `geometry.project_to_chain`, which clamps at the chain
  ends. v311 and v363 lie at the stations where 16S/34S's ridge chain ends
  (t = 1.000 and t = 0, d = 8.98 m), so both go to 16S/34S. The generator
  states their row against 16S/34S, and the solve holds it.
- The verify's copy (`verify/runway._transverse_owners`) measured `d` with
  `_nearest_ridge`, which keeps **interior** feet only (the SPLP guard,
  RULINGS 2026-09-10au, which belongs to the *reading*, not the ownership).
  The end corners have no interior foot on 16S/34S, so 16S/34S never
  entered their owner set. The corners defaulted to face 10's ref and were
  read against 16/34's crown 21.4 m away, which is a row the generator never
  states. That makes it a DEFECT with an empty hard set.

The two instruments were not twins at chain ends. The class is any
runway-end corner of a parallel runway that shares a neighbouring runway's
shoulder face.

## Fix (single source)

`verify/runway._transverse_owners` measures ownership with the generator's
own primitive (`project_to_chain`, clamped). The reading itself keeps
`_nearest_ridge`: a corner owned by its own runway and lacking an interior
foot is still skipped there, because it is the longitudinal and end-zone
readers' business. Twin:
`tests/auto_patch_v2/test_runway_transverse_owner.py::test_a_runway_end_corner_stays_its_own_runways`
fails on the old verify and passes with the fix.

## Observed, not changed (follow-up for the master)

The real surface does carry a level difference across face 10. 16S/34S
sits **0.9–1.7 m below its DEM** along its whole ridge (−1.69 m at 16S,
−1.71 m at 34S). The reason is that its ends are pinned to the apt.dat
datum (RULINGS 2026-09-30z (2); no CIFP for 16S/34S): 34S at 68.66 m and
16S at 70.95 m, against DEM 70.38 m and 72.65 m. 16/34's west edge stays
near its DEM, so face 10 steps about 1.1 m over 6.5 m. The census already
reports this as 31 `within_shape` rows on face 10, up to 17.9 %. That
family is not a DEFECT family. Whether a gravel strip's apt.dat datum should
yield to a lidar DEM 1.7 m above it is an owner question (law 30z (2)) and
out of this lane's scope.

Latent, same file: the verify keeps only the FIRST `crown_spine` per runway
ref, while the generator reads all of a runway's chains. That gives a false
negative, not a false positive (a vertex near a second chain has no interior
foot on the first and is skipped). It does not bite at PAAQ, where each
runway has one chain.
