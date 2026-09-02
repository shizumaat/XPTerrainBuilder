# FGP S1 round ledger — PARKED (attempt cap reached; pre-beta merge declined)

Lane fgp1, 2026-09-01/02.  Spec `fgp-single-authority-spec.md` §S1;
census `fgp-s1-consumer-census.md` (committed f6c9a941 before any
edit).  Verdict: **PARK** — the entry-contradiction acceptance passes
decisively, the census / senior-movement bars do not, and both misses
are measured to be the S3 coupling the spec pre-names.  Per the spec's
own scheduling clause this becomes the first post-beta round.

## The change (all behind `O4_FGP_SOLVE_LAW`, default OFF)

`src/auto_patch/elevation_per_surface/route_profile/solve.py`, inside
`final_grade_projection` (commits 9557d997 + 20995a01 + 604d7ab9):

* `_solve_law_hold_filter` (module level, ~8348): a re-derived hard
  hold stands down where the seed contradicts the solve-stated value.
* JOIN block (~8727): the solve's published IMPOSED no-step pairs join
  the main joint (`airside_no_step` entry, STAGE A); the membrane join
  rides sub-gate `O4_FGP_SOLVE_LAW_MEMBRANE` (default OFF, S3-gated).
* Hold releases: `svc_free_end` (~8838), `svc_profile` (~8895) via the
  filter; groundside-family feature welds released as torn at the weld
  scan (~9145).  `svc_mouth` untouched (owner law 2026-08-15); store
  registers untouched.
* Late block after `_stage("hard")` (~9595): carrier seeding
  (S3-sub-gated with the membrane join), all-hard transect-row drop,
  all-hard joined-pair drop, the `[fgp-solve-law]` report line.

Tests: `tests/test_fgp_solve_law.py` (7 tests, headless).

## The arms (HECA, shared corpus, run + artifact ledgers)

Control = current-main HECA control, body `e916085b677a…8954408f`
(air7ctl, artifact ledger).  Census control: airside_for_acceptance
**1,075**, total 2,838; solve exit both-hard over-cap **759**; FGP
entry both-hard over-cap **1,602** (air6 dump, reproduced).

| Arm | Tree | Config | Body sha | Entry BH over-cap | Census airside | Cert final1_exit residuals | Solve-owned moved (vs OFF) |
|---|---|---|---|---|---|---|---|
| fgp1_off | 9557d997 | gate OFF | `e916085b…` = control | 1,602 (control) | — | — | — |
| fgp1_off2 | 20995a01 | gate OFF | `e916085b…` = control (ledger-STORED) | 1,602 | 1,075 | 2,167 (worst 7.002) | 0 (identical bytes) |
| fgp1_on (attempt 1) | 20995a01 | gate ON + membrane ON | `31e2adbd…` | **97** | 1,362 (**+287 FAIL**) | 2,263 (**FAIL**), worst 6.398 | 3,463, worst 4.34 (**FAIL**) |
| fgp1_on2 (attempt 2) | 604d7ab9 | gate ON, membrane dark (merge-candidate config) | `7fd2bb57…` | **97** | 1,247 (**+172 FAIL**) | 2,202 (**FAIL**, worst 6.398) | 3,071, worst 4.41 (**FAIL**) |

Acceptance items that PASS on the merge-candidate arm (fgp1_on2):

* Entry both-hard over-cap **1,602 → 97** (bar ≤ 759, the solve exit's
  own count; solve exit unchanged at 759).  Anatomy: 83
  unified:service_junction + 12 other service rows (all in solve-exit
  families) + the 2 known 0.003 m apron rows also present in the
  control entry; p50 excess 0.0036 m.  The FGP-only `transverse`
  both-hard class (control 300) is GONE; holds stood down:
  svc_free_end 790, svc_profile 1,114, gs_weld 999.
* Gate OFF byte-identity: three OFF builds across the three trees all
  emit body `e916085b…` = the standing control (fgp1_off3 at the final
  tree recorded in the run ledger).
* Basin/tunnel invariants: ZERO moved nodes on any tunnel/basin role
  (airside_value_delta per-role); tunnel bores REFUSED 3 and
  basin_facilities 0 in both arms.
* Runway: runway-family census rows unchanged (runway_crown 3 = 3,
  skirt 0); the 822 s runway-longitudinal pytest was NOT run for the
  parked outcome — it is owed on the post-beta round's green arm.

Acceptance items that FAIL (both attempts):

* HECA airside census worsened; the mint is apron-ring movement:
  within_shape +189/+207 NEW apron|apron rows, apron_lattice_membrane
  +101/+192 NEW `?|apron` rows.
* Airside certificate final1_exit residuals +35/+96 (worst improves
  7.002 → 6.398; both-hard 3 → 0).
* Solve-owned airside movement ~3.1–3.5 k nodes (bar: zero).

## THE FINDING (spec-author information — the S3 coupling, both ends)

S1's law-join half cannot land while the emitted membrane carriers
stay frozen at solve values (RULINGS 2026-09-01q), and the coupling
has TWO ends, split cleanly by the two arms:

1. **Ring side** (attempt 1): joining the membrane family moves apron
   rings toward the solve's membrane state, and ANY ring movement
   prices `apron_lattice_membrane` against the stale carriers —
   108 → 245 census rows.  Even with the join dark (attempt 2), the
   no-step-driven ring movement alone minted 108 → 169.
2. **Interior side** (attempt 2): with carrier seeding dark, the
   joined no-step pairs price the DEM-garbage station/lattice
   interiors — entry airside-cert `airside_no_step` 499 rows, worst
   **29.272 m** (vs 8.023 m with seeding lit) — and the projection
   then drags emitted juniors toward those garbage seniors.

So: the no-step join NEEDS the carrier-value seeding (a read of S3's
surface), and any airside improvement FGP makes mints membrane rows
until the carriers refresh — which 01q showed cannot happen before
S1/S2 hold.  The dependency is circular at the CENSUS instrument, not
in the law: the ordering that closes it is S1 (this branch, armed) +
S2 (clamp yields) + S3 (carriers refresh) measured as ONE
configuration, with the membrane sub-gate flipped by S3.

Unmeasured single arms (attempt cap reached, deliberately not built):
hold-release-only (no join), and no-step join + seeding with membrane
join dark.  Either is a cheap first arm for the post-beta round.

## Artifacts

Arms + dumps + censuses + value deltas under
`/tmp/harness/fgp1_*` and the lane scratchpad `fgp1_*` files
(`fgp1_on{,2}.final1_entry.json`, `fgp1_on{,2}.solve_exit.json`,
`fgp1_*_census.txt`, `fgp1_avd{1,2}.{txt,json}`, build logs); run
ledger `tools/run_ledger.jsonl` (this worktree); artifact ledger
entries for fgp1_off2/off3 (control-identical) and both ON arms.
