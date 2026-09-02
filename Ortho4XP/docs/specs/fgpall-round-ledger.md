# FGP COMBINED round ledger (S1+S2+S3 as ONE configuration) — PARKED

Lane fgpall, 2026-09-01/02.  Spec `fgp-single-authority-spec.md`
§S1-S3; RULINGS 2026-09-01u (S1 parked; the three land as one
configuration); S1 work merged from lane/fgp1 (f6c9a941..afedefa6),
NOT redone.  Verdict: **PARK** (attempt 1 of the cap of 2; attempt 2
deliberately not spent — see THE FINDING).  The configuration is the
first FGP arm to IMPROVE the census, and both failing bars trace to
one root the elimination experiment already priced: the residual work
that must move INTO the solve.

## The change (gate family, all default OFF)

S1 (merged): `O4_FGP_SOLVE_LAW` + membrane sub-gate
`O4_FGP_SOLVE_LAW_MEMBRANE` — see `fgp-s1-round-ledger.md`.

S2 (`O4_FGP_SOLVE_LAW_CLAMP`, ANDed with the parent): the band clamp —
one implementation `_clamp_corner_elevs_to_band`, three sites (both
`_writeback` passes + `seal_pavement_to_band`) — resolves the
solve-stated value (`solved_values` store, emitted space) at every
point it would move.  Solve-stated within
`POST_SOLVE_IDEMPOTENCE_TOL_M` ⇒ the clamp STANDS DOWN (counted, sited
yield on `layout.band_clamp_yields`); a genuine violation ⇒ clamped as
before WITH the authority record (solve-stated value, finding field
10).  `solver_primitives.py`: `_solve_stated_closure`,
`_record_band_clamp_yields`.

S3 (`O4_FGP_SOLVE_LAW_CARRIERS`, ANDed with the parent):
`apron_lattice_emit` / `apron_spine_station_emit` refresh IN PLACE
after pass 2 (`membrane_conform`), before FGP's writeback, in emitted
space — values only, topology stays the mint's; unresolved points keep
the minted value, counted.  `solve.py`: `_refresh_membrane_carriers`.

Tests: `tests/test_fgp_solve_law.py` 7 → 12.

## The arms (HECA, shared corpus, run + artifact ledgers)

Configuration env (ONE arm lights everything):
`O4_FGP_SOLVE_LAW=1 O4_FGP_SOLVE_LAW_MEMBRANE=1 O4_FGP_SOLVE_LAW_CLAMP=1
O4_FGP_SOLVE_LAW_CARRIERS=1`.

Control = standing HECA control, body `e916085b677a…8954408f`; census
airside_for_acceptance **1,075**, total 2,838; cert final1_exit
residuals **2,167** (worst 7.002); solve exit both-hard over-cap
**759**; FGP entry both-hard over-cap **1,602**; who_wrote
`--author final_grade_projection` untouched class **827** (air5_who2).

| Arm | Tree | Config | Body sha | Entry BH over-cap | Census airside | Cert final1_exit residuals | Solve-owned moved (vs OFF) |
|---|---|---|---|---|---|---|---|
| fgpall_off | fcaea2be | gate OFF | `e916085b…` = control (**identity PASS**) | 1,602 (control) | 1,075 | 2,167 (worst 7.002, BH 3) | — |
| fgpall_on | fcaea2be | S1+S2+S3 ON | `5a11b1b1…` | **97** (bar ≤759 PASS) | **1,063 (−12, IMPROVED — first FGP arm ever)** | 2,263 (count +96 FAIL; worst 6.398 IMPROVED; both-hard 3 → 0) | 3,470, worst 4.34 |

## Acceptance readings (attempt 1 of the configuration)

* **(a) Gate-OFF byte-identity: PASS.**  Body `e916085b677a…8954408f`
  = the standing control, zero guard blocks; OFF census reproduces the
  control exactly (airside 1,075, total 2,838, cert 2,167/7.002).
* **Census: PASS.**  airside_for_acceptance 1,075 → **1,063**; total
  2,838 → **2,696** (−142).  Row anatomy (airside): GONE 343 / NEW 332.
  `apron_lattice_membrane` **108 → 23** (worst 3.98 → 1.45) — the
  stale-carrier class S3 exists for, closed in configuration (the same
  refresh ALONE was the 01q 1,075→2,120 explosion).  `airside_no_step`
  468 → 390 with the 4–5.8 m DEM-garbage station rows GONE (the 01u
  interior side, closed by seeding+refresh together).  transverse
  637 → 592.  The mint: `within_shape` 1,034 → 1,121 (airside
  apron|apron +207 NEW / −65 GONE), worst family value IMPROVES
  11.54 → 9.75.
* **Certificate: FAIL on the count, split verdict honestly.**
  final1_exit residuals 2,167 → 2,263 (+96) — but worst 7.002 → 6.398,
  both-hard 3 → 0, and the scoped edge population GREW 253,108 →
  257,204 (the joined solve-law families are now priced at the
  certificate; rate 0.856 % → 0.880 %).  Entry both-hard over-cap
  1,602 → **97** (solve exit unchanged 759).
* **Runway: PASS.**  runway_crown 3 = 3 (worst 0.270), skirt 0; ZERO
  runway-role movers in the value delta; runway flex / preserve /
  crown-rail log lines byte-identical between arms.
* **Senior movement: PASS on seniors, quoted honestly on the rest.**
  ZERO movers on any runway/tunnel/basin/bridge role.  The
  configuration's own class: 4,365 row-side movers (worst 4.34 m,
  apron/graded_strip/junction field), 3,470 of them solve-owned — this
  IS FGP's re-projection under the joined law, reported not hidden.
* **Basin/tunnel invariants: PASS** (census `basin_facilities=0` both
  arms; tunnel/bridge/bore log lines byte-identical; zero movers).
* **S2 second-author class:** FGP-writeback clamp 69 clamps worst
  **+8.05 m** (OFF — air5's exact headline mover) → 38 clamps worst
  **+0.80 m** (ON); 5+11 clamp YIELDS recorded (solve-stated values the
  band disagreed with, declined).  The solve's own writeback clamp (82,
  worst +7.07) is byte-identical both arms — untouched by design.
* **who_wrote 827-class: FAIL** (`who_wrote HECA --author
  final_grade_projection`, gates lit, /tmp/harness/fgpall_who):
  untouched-class total **896** vs control 827 (bar: 0), worst falls
  3.66 → 2.97; by role building 537 (p50 0.63), apron 140, service_road
  137, service_junction 72, junction 10.  Under the joined law FGP now
  moves MORE solve-stated values, not fewer — lawfully and reportedly,
  but still a second author by the strict bar.
* **S3 refresh magnitude:** 662 altitudes updated, 0 unresolved.  The
  spec's S3 acceptance ("refresh byte-neutral where S1/S2 hold") is NOT
  met literally — the projection still moves membrane interiors after
  the solve mint; 662 is the honest measure of that residue.
* Not run (owed only on a green arm per the S1 ledger): the 822 s
  runway-longitudinal pytest.

## THE FINDING (why PARK, and why attempt 2 was not spent)

Both failing bars have ONE root, and it is not a defect in S1, S2 or
S3 — each mechanism did exactly its specified job on the log evidence
(law joined + holds stood down; clamp yields recorded and the +8.05
class gone; carriers truthful and the membrane family closed).  The
root: **the solve's exit surface does not satisfy the law the
configuration now imposes** (final1_exit 2,167 residuals on the
control; the joined membrane/no-step families included).  So FGP,
pricing the solve's own law, must still MOVE solve-stated values into
it — 896 untouched-class moves, the within_shape apron mint, and a
cert count that grows with the newly-scoped families.  That is 01t's
"residual ~209 is real work to move into the solve", measured again
from inside the configuration.  No arm variation available to this
round changes that; the next work is IN THE SOLVE (make the solve
publish a surface lawful under its own published membrane/no-step law
— then S3's refresh becomes byte-neutral and the untouched class can
actually reach 0), which is post-beta work per the spec's scheduling
clause.  Attempt 2 is banked, not burned.

## What S2/S3 required beyond the spec

Nothing outside the spec's named surfaces.  Two implementation choices
worth recording: (1) S2 lives in the ONE clamp implementation
(`_clamp_corner_elevs_to_band`), so it covers both writeback passes
AND `seal_pavement_to_band` — the solve's own writeback is naturally
exempt because `solved_values` is minted after it; (2) S3 refreshes
values IN PLACE on the minted polylines (topology untouched) so no
consumer sees a geometry change; unresolvable points keep the minted
value, counted (HECA: 0).

## Artifacts

Arms + dumps under `/tmp/harness/fgpall_*`; scratchpad `fgpall_*`
files; run ledger `tools/run_ledger.jsonl` (this worktree).
