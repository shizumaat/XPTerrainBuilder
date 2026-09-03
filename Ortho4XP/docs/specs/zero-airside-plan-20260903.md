# Zero airside law violations — the plan (2026-09-03)

Goal (owner, 2026-09-03): complete the deferred work and reach ZERO
airside law violations on the five battery airports (SPJC / SPLP / CYXY /
HECA / KCLT), with LEMD / OTHH adjudicated in sim. Absolute-zero
acceptance (RULINGS, `absolute-zero-acceptance`) is the bar; "airside"
is the acceptance-airside census scope (`row_side`, `run_checks_law_true`).

Sources: STATUS 20260902a; RULINGS 2026-09-01a..w + 02a; DEFERRED_
VERIFICATION 2026-09-01..03; `fgp-single-authority-spec.md`;
`fgpall-round-ledger.md`; `fgp-s1-round-ledger.md`; `beta-hardening-
plan.md`; the three parked lanes' branch-local RULINGS/DV entries.

## 0. Where the airside count stands (last recorded, corrected instrument)

| airport | census total | acceptance-airside | note |
|---|---|---|---|
| HECA | 2,838 | **1,075** | FGP closes 641 / mints 432 (01t); combined S1+S2+S3 arm 1,063 |
| CYXY | 153 (adjudicated 179) | 100 | air2 arm alone: 74 → 63 |
| SPJC | 686 | (not split) | 683 EXACT rows after re-clip |
| KCLT | 2,174 | (not split) | zero KCLT-specific work yet |
| SPLP | 35 | (not split) | |

Runway profile: 0 on all five (H7 `7786ff0e`, `test_runway_longitudinal_
grade` green). Airside feasibility holds at the solve exit (ONE both-hard
over-cap pair, 0.003 m, 01r). Emit is innocent (zero groundside wins).

First action of Round 1 is therefore a KCLT / SPJC / SPLP airside split
from the existing censuses (no build: `census.py` on the sidecars) so
every airport has a number to drive to zero, not only HECA.

## 1. The root, and the ordering it forces

Four lanes converged (01t/01u/01v): **final_grade_projection (FGP)
re-authors values the solve made lawful** — because *the solve's exit does
not satisfy the law the configuration imposes* (membrane + no-step pairs
are stated but never driven to feasibility, 01n). Every downstream airside
mechanism (air2, air3, apron second wave, pad law) measured against a
surface FGP then moves; that is why three of them are parked "blocked on
FGP". The ordering is not negotiable: **the solve round first**, everything
airside re-measured on its exit.

S1 (`O4_FGP_SOLVE_LAW` + `_MEMBRANE`), S2 (`_CLAMP`), S3 (`_CARRIERS`)
are MERGED default-OFF and byte-inert (`e916085b677a`), so the round
starts from main, not a branch.

## 2. Owner decisions the plan hinges on (asked, not assumed)

| id | decision | data | plan consequence |
|---|---|---|---|
| OD-3 | Post-beta FGP round scope: the solve round as §3 R1 (solve publishes a surface lawful under its own membrane/no-step law; FGP becomes pure projection) | control cert 2,167 residuals; combined arm entry both-hard 1,602→97, lattice 108→23, unauthored (827-class) 896 | R1 charter as written, or narrower |
| OD-1 | air3 sign-off: accept HECA −31 net with 21 NEW rows (`63e14774`, `O4_PASS2_CONFORM_EXT`) | 52 GONE / 21 NEW; over-cap edges 651→0; 127 of 161 rows floored by own-law ceilings | if NO: air3 stays parked and R1 must close the same 52 (its charter already does); if YES: merge now, re-measure after R1 |
| OD-2 | Split-level-seat un-hold for the flat-pad-spans-relief subset (b168: 4.03 m over 397 m = 1.01 %) | 70 no-free-end rows: 29 partners-contradict, 12 outside band, 20 tier 1↔2; seat clamp arms 1,176 / 1,154 vs 1,073 control (refuted) | governs `no_step apron\|building` (01p) and R4 |
| OD-8 | Full pad law bar: accept HECA −242 with LEMD +1,346 / SPJC +229 booked to the 08-08 apron-relief class? | `apron\|apron` +136 at LEMD with no building in the pair | if NO: R4 needs a RELIEF charter first (recommended) |

OD-4 (+60-136 cold-cache write) and OD-5 (300 s tile budget vs LEMD
574 s) are perf/process, not airside law; they sit in the final
profiling round (§5).

## 3. Rounds (each: one spec, one gate default-OFF, pre-registered
outcomes, attribution before fix, synthetic-first then ONE airport)

Representative airport per round: HECA (815 s/build today; the only
airport with the full population). Cheap control: CYXY (41 s). Strict
merge rule stands: gate-OFF byte-identical AND gate-ON improves every
axis, else park. Wall-clock per round below counts HECA builds ×
~14 min + CYXY controls.

### R1 — THE SOLVE ROUND (C-1; spec `fgp-single-authority-spec.md` §S1–S4)
Charter: the solve's exit surface satisfies its own published membrane
(`_apron_lattice_edges_ll`) and imposed no-step pairs
(`_airside_no_step_pairs_m`); FGP then projects and authors nothing.
1. **Attribution first (no fix).** Family-attribute the control's 2,167
   `final1_exit` residuals and the 896 unauthored (827-class) moves by
   solver stage that last wrote each vertex (`who_wrote`). One HECA
   instrumented build + the existing scratch anatomy. Output: one table,
   pre-registered predictions for which families a feasibility drive
   closes. (~1 HECA build)
2. **Drive imposed law to feasibility inside the solve** (01n's named
   gap): the pass-2 `membrane_conform` / phase-A joint projection must
   certify at HECA instead of exiting on the stall guard (sweep 1,392/
   250,000). Cheap arms banked in FGP1:97 first: hold-release-only (no
   join); no-step join + seeding with membrane join dark. Senior
   invariants byte-held: runway profile 0, no senior movement, basin /
   tunnel byte-identical. (2–3 HECA arms + CYXY controls ≈ 1 h)
3. **Flip S1+S2+S3 ON** on the certified exit. Acceptance = the spec's:
   S1 entry both-hard ≤ solve exit; S2 zero unauthored moves; S3 carrier
   refresh byte-neutral; S4 air7 certificate CERTIFIED at HECA / CYXY /
   SPJC. (1 HECA + CYXY + SPJC ≈ 20 min per configuration)
4. **Full-suite gate:** the 822 s `test_runway_longitudinal_grade` on
   the green arm (C-2), `test_fgp_solve_law` (12), no-step twins (57).
Exit: HECA airside well below 1,075 with 0 NEW airside rows; every
remaining row attributed to a family with a named next round.

### R2 — RE-LAND THE PARKED AIRSIDE LANES ON THE CERTIFIED EXIT
- air2 profile-law ingestion (`ad20ca42`): rebase, gate-OFF byte-identical,
  gate-ON at CYXY (74→63 expected to hold) and HECA now certifies (C-4).
- air3 (`63e14774`): per OD-1. If merged pre-R1, re-measure; the stale
  breakline emit docket (01q a) is expected closed by S3 (662 refreshed /
  0 unresolved) — verify, don't assume.
- weldov closing arms KCLT + HECA (`test_no_self_overlap`, census A/B)
  and air7 full suite (C-9, C-10) ride this round's sweep.
(≈ 3 HECA + 2 CYXY + 1 KCLT ≈ 1 h)

### R3 — APRON SECOND WAVE (C-7, 01p)
Classes routed to certification: `within_shape a|a` 266, `no_step a|a`
142, `no_step a|b` 96, lattice (108→23 already on the combined arm).
Predicted to fall with R1; whatever survives gets attributed per class
(71–94 % had an FGP-moved endpoint — re-attribute on the R1 exit before
touching a mechanism). One HECA build per surviving class.

### R4 — APRON RELIEF CHARTER + PAD LAW (OD-2, OD-8; lane/bldround)
The 2026-08-08 apron-relief class is the blocker for the full pad law:
rows whose two endpoints are both apron cannot be closed by any pad-side
mechanism. Sequence: (a) owner charter for apron relief (what a lawful
apron surface over real relief is — HECA's ~85 m is real); (b) split-level
un-hold per OD-2 on the flat-pad-spans-relief subset; (c) rebase
lane/bldround (`f89cc09d`: fill-R 15, frontage cutback 0.6 m, contact
weld) and re-measure HECA / LEMD / SPJC against THAT bar. LEMD +1,346 is
the tripwire: any LEMD growth led by `apron|apron` means the charter,
not the pad, is the work.

### R5 — RUNWAY-ADJACENT RESIDUAL (C-6, 01l)
The junction/apron sharing the two runway nodes cannot reach the runway's
law line under their own caps: HECA +12 / CYXY +3 adjudicated rows. Own
round: name the CIFP-vs-taxi-network tension (2026-08-15 band findings)
and rule it; then rebuild SPJC / SPLP / KCLT / OTHH / LEMD under
`O4_RUNWAY_WRITEBACK_PRESERVE` (never done).

### R6 — GROUNDSIDE PINS THAT LEAK (OD-7, 01r/01s)
Groundside service pins carry the only material solve-exit contradictions
(384 + 266 + 106 pairs, worst 6.17 m over 0.32 m). Groundside is not in the
airside count, but the channel to airside is FGP's rebuilt-graph writeback
(01s). After R1 this leak must measure ZERO (airside-is-king); if not, the
cap-consistent-at-mint ruling for free-end DEM ties is the fix.

### R7 — EMIT HYGIENE (C-8, 02a)
Retire the two registry-pollution channels (`_build_node_list` zone
attractors 9/15; `_vertex_elev_anchored` `get_or_add`-as-query 3–4/15)
behind a 30l consumer census of registry writers; `reclip_emit_frame_
overlaps` then has nothing to clip. Spec-author docket; byte-identity is
the acceptance (emit is innocent today).

## 4. The five-airport gate (after each merged round, at each app build)
`build_airport.py` ×5 (HECA 815 s, KCLT 500 s, SPJC 167 s, CYXY 41 s,
SPLP 10 s ≈ 26 min serial; parallel when not timing) + `census.py` with
the sidecar frame, airside split quoted per airport, then STATUS twin and
the owner's sim read (31a sim gate). Zero = zero adjudicated airside rows
on all five; LEMD/OTHH sim-adjudicated.

## 5. Parked outside the airside path (not forgotten)
- Perf: HEAZ unmeasured since 08-13; LEMD emit bisect (+25.7 s wk); tile
  budget adjudication (OD-5); `--runs N` on the foot retirement — all in
  the FINAL profiling round, after the last airside merge.
- OD-4 `+60-136` cold-cache write: bless or remove (owner).
- Tunnel residuals: `wall_top_flat` 5.1 m pre-existing; LEMD no-band
  site 40.4896687,-3.5494150; `test_tunnel_portal_fidelity` ×5 reds.
- Housekeeping: tile-store CLI writer; 231 lane branches + worktrees;
  phantom specs 25f/g/h; lane/bldround's leftover SPJC clip `.tmp`.
- Chips: road-band-seal restore — SUPERSEDED on main (`9ac3441c`,
  `184ee9b4`); step-loop rc=0 — merged this session (see STATUS).

## 6. Order of operations, wall-clock
1. Owner sim read of 1.0.275 (today) → decisions OD-1/2/3/8.
2. R1 attribution build while decisions are pending (no fix depends on
   them): 1 HECA build.
3. R1 mechanism: ~1 day of lanes (Fable 5.1 medium), ≤ 6 HECA builds.
4. R2 + five-airport gate: ~half a day.
5. R3–R7 sequential, each ≤ 1 day, each gated by its own sweep.
Attempt cap per round: 3 arms; a third failed arm parks the round and
routes the premise to the owner (29e/29f).
