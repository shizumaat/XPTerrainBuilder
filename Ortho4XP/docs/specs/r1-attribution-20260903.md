# R1.1 — attribution of the HECA control's airside residuals (2026-09-03)

Lane `r1attrib`, zero-airside plan R1 step 1 (`zero-airside-plan-20260903.md`
§3 R1.1).  ATTRIBUTION ONLY — no mechanism changed; every edit on this
branch is instrumentation (`O4_AIRSIDE_CERT_DUMP`, `who_wrote --vertex-dump`)
or this document.

## Pre-registered predictions (written BEFORE the instrumented build)

Baseline read from the STANDING CONTROL's own sidecar (artifact ledger
entry `air7_HECA_arm`, tree `13902ca6`, body `e916085b677a`, served with
`artifact_ledger.serve` — no build): `airside_certificate.readings`.

| reading | n_edges_scoped | n_over | mixed | both-hard | worst m |
|---|---|---|---|---|---|
| solve_exit | 718,567 | 3,054 | 2,181 | 0 | 4.58 |
| final1_entry | 249,767 | 3,291 | 1,731 | 3 | 8.02 |
| final1_exit (verdict) | 253,108 | **2,167** | 1,184 | 3 | 7.00 |

final1_exit by family group (sum 2,167): service_junction 1,061
(`service_junction:-` 740, `unified:service_junction` 295, `:spine` 21,
`:service` 5; both-hard 3), apron 690 (351 + 321 + `:spine` 18),
transverse 148, junction 133 (47 + 45 + `junction:transverse_no_step`
36 + `:spine` 5), service_road 123 (102 + 19 + 2), rod_interval 10,
unified_graph 2.

Predictions, by family, of what an R1.2 feasibility drive (S1 law-join +
S2 clamp yield + the solve driving its own membrane / no-step law to
certification) closes:

| P | family (count) | predicted last writer of the endpoints | predicted disposition | predicted count closed by R1.2 |
|---|---|---|---|---|
| P1 | service_junction + service_road, the MIXED rows (1,184 of 2,167) | one endpoint airside (solve writeback / FGP), the other a groundside service node last written by `seat_service_pavement_on_law` / `seat_groundside_on_law` (pipeline 7012/7047) or an FGP hold | the 01r groundside-service-pin class; hold-release-only (S1 `_solve_law_hold_filter`) closes the rows whose hard endpoint is a `svc_free_end` / `svc_profile` pin; the rest is R6 (cap-consistent-at-mint) — NOT airside solve work | ≈ 450 close (hold release), ≈ 730 remain |
| P2 | apron 690 | ≥ 70 % of rows have an endpoint whose last change is FGP's writeback (`solve.py:10859`) with a move ≥ 0.1 m (01p: 71–94 %); the solve-exit apron residue (512 rows, worst 0.39 m) is the undriven membrane / no-step law (01n) | closes: the 512 under the solve-side drive (membrane join certifying), the FGP-added ≈ 180 under S1 + S2 | ≈ 650 of 690 |
| P3 | transverse 148 + `junction:transverse_no_step` 36 = 184 | FGP-only families (ABSENT at solve_exit); endpoints last written by the solve writeback | closes under S1 (the solve's no-step pairs replace FGP's own transect / no-step mint; fgp1 measured the transverse both-hard class 300 → 0) | ≥ 160 of 184 |
| P4 | junction 97 (47 + 45 + 5) | solve exit carried 181 and FGP closed 84; the rest sit on runway-adjacent nodes | ≥ 50 % have a hard endpoint pinned `runway_node` / `pad` → senior-protected (R5); the rest closes under the drive | ≈ 45 of 97 |
| P5 | rod_interval 10 + unified_graph 2 | — | sub-0.15 m; quant-floor noise or S2 | 12 |
| **total** | 2,167 | | | **≈ 1,320 close / ≈ 850 remain** (≈ 730 service pins, ≈ 50 senior, rest mixed) |

The 827-class (control `who_wrote --author final_grade_projection`
untouched moves; 896 on the ON configuration, fgpall ledger: building 537
p50 0.63, apron 140, service_road 137, service_junction 72, junction 10):

| P | subset | predicted last writer before FGP | predicted disposition |
|---|---|---|---|
| P6a | building (≈ 60 %) | solve writeback (`solve.py:6246`) carrying the pad seat | `no_step apron\|building` partner drag — OD-2 (split-level un-hold) territory; NOT closable by a feasibility drive on the current law |
| P6b | apron + junction (≈ 20 %) | solve writeback | closes under S2 (clamp yields) + the drive |
| P6c | service_road + service_junction (≈ 20 %) | `seat_*_on_law` or solve writeback | R6 pin class |

Falsifiers: (i) if < 50 % of apron rows have an FGP-moved endpoint, 01p's
re-authoring mechanism does not own the apron residue; (ii) if the
transverse / transverse_no_step rows DO appear at solve_exit under their
own family, P3's "FGP-only" premise is wrong; (iii) if the mixed rows'
groundside endpoints are NOT hard-pinned (pins null), P1's pin class is
not the mechanism and hold release cannot be the arm.

## Second build (justified in one line)

The 896-class exists only under the ON configuration (`O4_FGP_SOLVE_LAW`
+ `_MEMBRANE` + `_CLAMP` + `_CARRIERS`), which is the configuration R1.3
flips; the charter names that population explicitly, so ONE more HECA
build, same instruments, that configuration.  No sweep, no third arm.

(Measured results follow below once the builds land.)

## Measured (2026-09-03, two instrumented HECA builds)

Instruments (this branch): `O4_AIRSIDE_CERT_DUMP=<prefix>` in
`src/auto_patch/elevation_per_surface/route_profile/solve.py`
(`_dump_airside_certificate`, every residual row of every certificate
reading with endpoint xy / ll / z / hard flag / pin source) and
`tools/harness/who_wrote.py --vertex-dump` (every value-changing write per
vertex, keyed by role + ref + plan coordinate) + `--cert-attrib` (the
NO-BUILD join that makes the tables below; twin
`tests/test_who_wrote_attrib.py`).  Tables:
`docs/specs/r1-attribution-tables/{r1ctl,r1on}.final1_exit.md` (+ `.groups.json`).

Builds (worktree `.claude/worktrees/r1attrib`, main `3f9e008f` + this
branch's instrumentation; shared corpus, lane-local products; both through
`who_wrote.py` → `build_airport.build_patch`, run ledger + shared-repo
guard armed, zero guard blocks):

| arm | config | build_patch wall | shapes | body sha | cert solve_exit / final1_entry / final1_exit | both-hard over-cap solve / entry | untouched-class FGP moves | census airside_for_acceptance (total) |
|---|---|---|---|---|---|---|---|---|
| r1ctl | gates OFF (control) | 837.6 s (14:41:42–14:55:49, two builds in parallel, not a timing) | 3,721 | `134e5eadc7b0` | 3,054 / 3,291 / **2,167** (worst 7.002) | 759 / 1,602 | **827** (max 3.66) | 1,094 (2,866) |
| r1on | S1+S2+S3 ON | 844.7 s (14:41:50–14:56:03) | 3,727 | `25656b5f2d7d` | 3,054 / 3,780 / **2,263** (worst 6.398) | 759 / 97 | **896** (max 2.97) | 1,070 (2,714) |

Every solve / FGP number reproduces the standing control and the fgpall ledger
EXACTLY (2,167 / 3,054 / 3,291 / 759 / 1,602 / 827 / 896 / 2,263 / 97), so the
population the charter names is the one measured.  The emitted census is
+19 airside on both arms against the ledgers (1,075 → 1,094; 1,063 → 1,070):
`census_rows_diff --side airside` of the served control (`ctl.osm`, body
`e916085b`) vs r1ctl = 1,073 EXACT / 0 GONE / **19 NEW, all
`strip_seam_tear graded_strip|graded_strip` at one site 30.113483,31.414089
(ways -13585/-13589/-13593)** — post-projection emit drift of the tree since
the 09-02 control (weldov `b1b11d31` / ovfix `02aa437c` are the emit-side
commits in `fa5d6af5..HEAD`), not this instrumentation and not the
certificate population.  Owed: one plain `build_airport.py HECA` on main
to confirm the 19 are the tree's (see "not done").

### Predictions vs measured (control, final1_exit 2,167)

| P | predicted | measured | verdict |
|---|---|---|---|
| P1 service mixed 1,184: ≈450 close under hold release, ≈730 remain | hard endpoints: service_ring 523, gs_weld 125+9, feature_weld 4, terrain_pin 48 → disposition `closes:S1-hold-release` **646**, `senior (terrain_pin)` 48, `both-hard` 3; **480 of 1,061 service_junction rows have NO hard endpoint** (falsifier iii fires for 41 %); ON arm: service_junction 1,061 → 588, service_road 123 → 87 (**−509**) | count HELD (≈450 vs −509); mechanism HALF-RIGHT: the pin class is 55 %, the other 45 % is FGP projecting un-pinned service junctions that a pre-FGP pass re-seeded (957 of 1,061 rows have an endpoint moved ≥0.1 m off the solve value before FGP) |
| P2 apron 690: ≥70 % FGP-moved endpoint; ≈650 close (512 solve-exit residue under the drive, ≈180 under S1+S2) | FGP-moved endpoint **537 / 690 = 78 %** (01p confirmed); inherited from solve exit 179, minted by the rebuilt graph 29, **minted by the projection 482**; ON arm: apron 690 → **1,073 (+383; 879 projection-minted, worst 2.48)** | mechanism CONFIRMED, disposition REFUTED: S1+S2+S3 do not close apron, they mint it — the apron law FGP prices is not satisfied by the solve exit, and the projection's own exit is not a fixpoint |
| P3 transverse + transverse_no_step 184: ≥160 close under S1 | FGP-only confirmed (0 at solve_exit; 127 + 20 minted at entry, 21 + 15 by the projection); ON arm **184 → 158 (−26)** | premise CONFIRMED, closure REFUTED: the S1 join does not retire FGP's transect / no-step mint |
| P4 junction 97: ≈45 close, ≥50 % senior | hard `runway_node` endpoints **8** (senior 9 rows), 89 rows no hard endpoint; inherited 55, projection-minted 40; ON arm **97 → 167 (+70, 107 projection-minted, p50 0.05)** | REFUTED both ways: not senior-bound, and the arms mint |
| P5 rod/graph 12 | 0.03–0.14 m, 9 no hard endpoint | as predicted |
| P6 827-class | last pre-FGP writer `solve@6246` for 718 / 827 (building 461, apron 109, service_road 97, service_junction 44); the rest `decimate_emit_nodes` (7127) 59, `emit_terrain_transition_features` 24, `_grade_limit_groundside_chords` (7062) 13, `_quant_pre` (7241) 9; **≥0.1 m: 316 of 827** (building 125, apron 85, service_road 75, service_junction 27, junction 4); 78 of the 461 building moves sit on a residual row; ON arm 896: 569 ≥ 0.1 m (building 363 p50 0.63) | P6a confirmed (building carries the solve writeback value; FGP moves it under `no_step apron\|building`); materiality: 62 % of the control class is sub-0.1 m |

### The three-way split of the 2,167 (instrument: `--cert-attrib --cert-base solve=… --cert-base entry=…`, endpoint-pair join)

| origin | rows | by family |
|---|---|---|
| **inherited from the SOLVE's own exit** (row present at solve_exit) | **803** (37 %) | service_junction 458, apron 179, service_road 108, junction 55, rod 2, tns 1 |
| **minted by FGP's REBUILT GRAPH at entry** (absent at solve_exit, present at final1_entry) | **716** (33 %) | service_junction 527, transverse 127, apron 29, tns 20, service_road 10, junction 2, graph 1 |
| **minted by FGP's PROJECTION** (absent at both; born inside the pass) | **648** (30 %) | apron 482, service_junction 76, junction 40, transverse 21, tns 15, rod 8, service_road 5, graph 1 |

The SEEDING axis (vertex history, `--vertex-dump`): **1,361 of 2,167 rows
have an endpoint whose value at FGP entry is ≥ 0.1 m off the solve's
writeback value** — service_junction 957 / 1,061, transverse 117 / 148,
service_road 102 / 123, apron 185 / 690, junction 0 / 97.  Re-seeding
writers (endpoint counts): `decimate_emit_nodes` (pipeline 7127) 1,205,
`_quant_pre` (7241) 316, `emit_terrain_transition_features` 300,
`_grade_limit_groundside_chords` (7062) 205, `_enf_pre` weld (7270) 101.
So the "solve's own exit" share (803) overstates what the solve authored:
FGP never sees the solve's surface on the service families — five
pre-projection passes rewrite it first.  Endpoint last-writer overall:
7127 3,000 endpoints, `solve@6246` 482, 7241 384, emit_terrain 307, 7270
215, 7062 198.

ON-arm split (2,263): inherited 671 (service_junction 369, apron 165,
service_road 75, junction 58), rebuilt-graph 333 (service_junction 99,
airside_no_step 90, transverse 83, apron 29), **projection 1,259 (apron
879, service_junction 120, junction 107, airside_no_step 79)**; reseeded
943 / 2,263 (apron 287).  Under the joined law the population moves from
"FGP's graph disagrees with the solve" to "FGP's projection cannot
satisfy the solve's own law" — which is the R1.2 charter, measured.

### Specimens (top families, control final1_exit)

* service_junction, worst 7.00 m: 30.114101,31.399259 ↔ 30.114157,31.399186
  (idx per dump; endpoints last written by `emit_terrain_transition_features`
  / `_grade_limit_groundside_chords`; hard pin `service_ring`);
  6.24 m: 30.114134,31.399335 ↔ 30.114407,31.399416 (terrain_pin, senior);
  5.48 m: 30.110610,31.395121 ↔ 30.110587,31.395115 (no hard endpoint,
  reseeded by 7127).
* apron, worst 2.04 m: 30.110534,31.395371 ↔ 30.110507,31.395253
  (projection-minted, FGP moved both endpoints, last pre-FGP writer 7127);
  1.17 m: 30.110612,31.395640 ↔ 30.110595,31.395631; inherited class
  0.35 m: 30.135851,31.410713 ↔ 30.135866,31.410777 (solve@6246 both ends,
  FGP did not move them).
* transverse, worst 5.77 m (entry-minted, service_ring / gs_weld hubs; see
  table); junction 0.53 m: 30.135729,31.410555 ↔ 30.135575,31.410810
  (inherited, `runway_node` hard on 4 rows).

### Recommended R1.2 arms (priority order), with the counts this table predicts

1. **Hold-release-only (S1 filter, no join)** — closes the 646
   `closes:S1-hold-release` rows (service_ring 520, gs_weld 122,
   feature_weld 4) IF the released endpoint can move to the airside
   value; the ON arm measured service families −509, consistent.  Cannot
   touch: 487 un-pinned service rows (FGP's own projection of reseeded
   junctions), 48 terrain_pin, 3 both-hard.  Predicted exit ≈ 1,500.
2. **No-step join + carrier seeding, membrane dark** — the `airside_no_step`
   family joins (ON arm: 169 rows appear, 90 at entry / 79 projection);
   predicted to close the 36 `junction:transverse_no_step` + part of the
   482 projection-minted apron rows ONLY IF the solve's exit already
   satisfies its no-step pairs — it does not (01n) — so this arm is a
   MEASUREMENT of the no-step residue (predict +100…+170 apron rows, as
   fgp1_on2 read +172 census), not a closer.  Run it to size the solve-
   side drive, not to merge.
3. **Membrane join (S1 full + S3)** — the ON arm IS this configuration:
   apron +383, junction +70, transverse −26, service −509, net +96.  The
   only arm that closes apron is the SOLVE-SIDE one: `membrane_conform` /
   phase-A joint projection certifying at the solve exit (the 179
   inherited + the law the 482/879 projection-minted rows price).  Do
   not spend a FGP-side arm on it.

Net: FGP-side arms are worth ≈ 650 service rows; the remaining ≈ 1,500
(apron 690 → 1,073 under the joined law, transverse 184, junction 97 →
167, un-pinned service 487) need the solve to publish a surface lawful
under its own membrane / no-step law AND the five pre-FGP re-seeding
passes (7127 / 7241 / 7062 / 7270 / emit_terrain) to stop moving solve
values before the projection reads them — 1,361 of 2,167 rows carry such a
re-seed; that channel is not in the plan and needs its own row.

### What the instruments could not answer

* Whether a released hold actually CLOSES a row (disposition is a
  mechanical prediction; only the arm says).
* `decimate_emit_nodes` (7127) reads as the last pre-FGP writer of 3,000
  endpoints: the vertex history sees a value change at the coordinate,
  but cannot tell a real re-authoring from a ring rebuild that re-maps a
  coordinate to an interpolated value — a `--at` trace at two specimens
  (e.g. 30.110610,31.395121) would decide it.
* In-place list mutation (`node_altitudes[k] = v`) is invisible to the
  probe (property setter only); no such writer is known, unverified.
* The +19 census rows vs the standing control (strip_seam_tear, one site)
  — tree drift vs probe effect — needs one un-instrumented HECA build on
  main (not run: budget).
* solve_exit rows whose nodes were later rebuilt join at 98 % (54 of 264
  CYXY endpoints unjoined at solve_exit; HECA final readings 0 / 42
  unjoined), so the "inherited" class is a lower bound by ≤ 2 %.
