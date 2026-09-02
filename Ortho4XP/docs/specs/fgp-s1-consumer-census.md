# FGP S1 consumer census (RULINGS 2026-08-30l discipline)

Lane fgp1, 2026-09-01.  Spec: `fgp-single-authority-spec.md` §S1 — FGP
consumes the solve's law.  Committed BEFORE any consumer is edited.

## The affected region

S1 changes three things, all inside `final_grade_projection`
(`src/auto_patch/elevation_per_surface/route_profile/solve.py`), all
behind `O4_FGP_SOLVE_LAW=1` (default OFF, byte-inert):

* **R1 — the joint constraint set** gains the solve's published law:
  the apron membrane (lattice + spine-station) pairs re-resolved from
  `layout._apron_lattice_edges_ll` and the IMPOSED airside no-step
  pairs from `layout._airside_no_step_pairs_m` — the same two
  publications pass 2 (`membrane_conform`) already resolves, now joined
  into the MAIN projection's law; and its transect hyper rows drop the
  all-endpoints-hard subset (unimposable rows that can only mint
  contradictions against solve-stated values — FGP-only law pricing a
  field it cannot move).
* **R2 — the hard set**: the `svc_free_end` / `svc_profile` keyset
  holds and the GROUNDSIDE-family feature-weld hardenings join `hard`
  only where the node's seed AGREES with the solve-stated value
  (`solved_values` carry, tol = `POST_SOLVE_IDEMPOTENCE_TOL_M`); a
  contradicted hold stands down (seed kept, membership released,
  counted and reported).  `svc_mouth` is untouched (owner law
  2026-08-15: the mouth seat is re-derived at the airside-final moment
  and held — that re-derivation is downstream-of-movers BY RULING).
* **R3 — membrane interior seeds**: free lattice/station nodes seed
  from the solve's emitted carriers (`apron_lattice_emit` /
  `apron_spine_station_emit`, values READ ONLY — the carriers are S3's
  surface and are NOT refreshed) instead of raw DEM, so R1's joined
  membrane law prices the solve's own state at entry rather than DEM
  garbage.

## The consumer table

| # | Consumer (reader of the affected geometry) | Interaction under the gate | Ruling |
|---|---|---|---|
| 1 | `feasibility_project_partitioned` (the main projection) | Reads joint+hard+elev.  Gains solve-law families; loses contradicted holds; released nodes projected under law from their warm seeds | INTENDED CONSUMER — the change's whole point |
| 2 | Entry/exit `projection_law_certificate`, `_publish_airside_certificate`, `_dump_both_hard` | Reads joint+hard+elev.  Entry counts fall (acceptance instrument) | OBSERVE — report-only |
| 3 | Torn-datum release scan (joint iteration for `_releasable`) | Sees the joined entries; releasable set unchanged in kind | OBSERVE — measured via closing arm |
| 4 | Bounded-yield seat boxes / pad handling | Reads `hard` (hard nodes dropped inside the clamp).  Released svc nodes were never pad nodes | UNCHANGED BY DESIGN |
| 5 | Band clamp (env-band / reach-band inside the projection) — **S2 surface** | Code untouched; released nodes become clampable where held nodes were not.  If the clamp lifts a freed node to a contradicted profile that is the S2 coupling | OBSERVE — if material, STOP-and-report the coupling (spec order) |
| 6 | `membrane_conform` (pass 2, FGP tail) | Reads its OWN resolutions of the same two publications; now runs after a main projection that already enforced them → smaller residual.  Restated-pair overlap is the same law at the same budget | UNCHANGED — no edit; residual reported |
| 7 | `_writeback` + runway-profile snapshot restore | Runway byte-held by the existing snapshot (acceptance: runway profile check 0) | UNCHANGED BY DESIGN |
| 8 | Emit: `to_osm` consensus, `emit_snap`, `emit_decimate` | Read final values; airside-first `AUTHORITY_PRECEDENCE` (01s: zero groundside wins) unchanged | MEASURED AT ACCEPTANCE (census, body hash OFF) |
| 9 | Carriers `apron_lattice_emit` / `apron_spine_station_emit` — **S3 surface** | READ for R3 seeding only; never refreshed.  Membrane node movement still does not reach emit (the 01q stale-emit masking stands — S3's docket) | UNCHANGED — read-only use |
| 10 | Later pipeline passes between mid-FGP and late-FGP (groundside reach, road family, clearance, bridges) | Read pavement values the mid call writes; gate-ON changes those values on released/lawfully-moved nodes | MEASURED AT ACCEPTANCE (census + basin/tunnel invariants byte-held) |
| 11 | W3 hard census (`classify_projection_hard`, `_fgp_hard_census`) | Smaller hard set appears in the census | OBSERVE — instrument |
| 12 | gs-witness horizon (`_fp_witness_limited`) + route-metric witness admission | `_gs_weld_idx` shrinks by the released welds; admission logic unchanged | OBSERVE |
| 13 | Break forensics / `_fcat_fp` / both-hard label sets | Labels reflect the reduced sets | OBSERVE — instrument |
| 14 | The svc store registers (`svc_free_end`/`svc_mouth`/`svc_profile` keysets), `gs_witness`, `solved_values` | NOT mutated — release is FGP-local `hard` membership only; every other reader sees identical registers (contrast air6's demotion, which edited the registers at their mint and is OFF) | UNCHANGED BY DESIGN |
| 15 | `law_band` store + its solve-side consumers (reach band, `building_feasibility`) | Publication untouched; S1 adds a read-only resolution at FGP (memo lands on FGP's own graph object) | UNCHANGED BY DESIGN |
| 16 | `check_grade` / harness census / oracle / sidecar readers | Acceptance instruments; no law family added to `run_checks` (twins unaffected) | OBSERVE — acceptance |
| 17 | Scoped-projection lazy stubs (`_scoped_projection_defer_ids`) | Joined law edges may move a deferred shape's node → stub expands (designed behavior) | UNCHANGED BY DESIGN |
| 18 | Sweep-budget derivation (`derive_sweep_budget`) | Slightly larger edge population → derived budget grows accordingly | OBSERVE — build-time statement in the report |
| 19 | `tools/airside_value_delta.py` / `who_wrote` | Senior-movement acceptance instruments | OBSERVE — acceptance |
| 20 | `_reseat_service_mouths` + `svc_mouth` hold | Explicitly out of scope (owner law 2026-08-15) | UNCHANGED — excluded from R2 |

Single-derivation-site preference (30l corollary a): R2 edits the four
FGP mint/join sites of the affected hard memberships — the only places
those memberships exist (the store registers themselves are not
touched, so no per-consumer veto exists anywhere else).

Emittability (30l corollary b): no new shape class or region enters
the layout; every value remains an ordinary heightfield node value —
trivially emittable.

## Seam-probe note

Static reading was decisive for every row above except #5 (the band
clamp on released nodes), which cannot be judged statically and is the
S2 coupling the spec pre-names; the closing arm's certificate + census
+ airside_value_delta are the probe for it, and a material finding is
a STOP-and-report, not a widened edit.
