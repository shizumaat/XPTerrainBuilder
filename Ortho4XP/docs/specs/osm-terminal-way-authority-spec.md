# OSM terminal-way authority over DSF cluster swarms — spec (2026-08-09, FROZEN)

Author: lead session (Fable). Status: **FROZEN for implementation.**
Charter: owner 2026-08-09 (OTHH bug report) — "It appears the large
central terminal, including building128 is being broken up into a bunch
of small buildings, why is this not a single large building? Compare
with the aeroway=terminal, building=airport_terminal way in the OSM
data." Rulings canon: `docs/RULINGS.md` (a brief violating a listed
ruling is invalid).

## 1. Diagnosis (recon 2026-08-09; cite, don't re-derive)

* OTHH's central complex is six OSM ways, all `aeroway=terminal`
  (verified in the raw extract): `-874` Main Terminal (92,530 m²),
  `-203` Concourse C (151,543 m²), `-870`/`-871`/`-872`/`-873`
  Concourses D/E/A/B, `-77` Emiri Terminal. All are read by
  `terminals.py:646 _extract_osm_terminals` (selector matches
  `aeroway=terminal`; no selector change is needed).
* The loss is `terminals.py:927 _combine_building_sources`, called at
  `pipeline.py:2825-2830`: an OSM way whose intersection with the
  DSF-object cluster union is ≥ `DSF_BUILDING_OSM_OVERLAP_FRAC` (0.2,
  `config.py:569`) of the way's area is DROPPED, and the cluster swarm
  (per-OBJ8-structure hulls from `_cluster_dsf_building_facades`,
  `terminals.py:850`) becomes the representation. Concourse C: 51 %
  covered by 153 tiny structure hulls → the 162-node way is deleted and
  32 flat pads (altitudes 3.00→5.12 m) replace it. Five of the six
  central ways are dropped this way; only `-874` (3 % covered — the
  pack models no solid ground band there) survives, as pad
  `building128`.
* In the 2026-08-08 20:02 OTHH patch: 125 `role=building` pads; the
  central complex is 81 pads / 281,310 m² against OSM's 362,906 m².
  The uncovered remainder of each dropped way grades as apron/ground.

## 2. The law (this spec's change)

**An OSM terminal way is the identity of its building.** Where OSM and
the DSF describe the same building, the OSM way wins the FOOTPRINT and
the DSF clusters under it are absorbed — the exact reversal of today's
rule. Precisely, in `_combine_building_sources` (signature unchanged;
semantics replaced):

1. Every OSM terminal way admitted by `_extract_osm_terminals` (and the
   existing ≥ 100 m² filter) is KEPT as one building polygon.
2. A DSF cluster polygon is ABSORBED (not emitted as its own pad) when
   `cluster.intersection(osm_way).area / cluster.area ≥
   DSF_CLUSTER_OSM_ABSORB_FRAC` for any kept OSM terminal way. New
   constant, `config.py`, default **0.5**, env
   `O4_DSF_CLUSTER_OSM_ABSORB_FRAC`. Majority-inside means the OSM way
   already represents it; a cluster mostly outside (jet bridge, fixed
   link, canopy hanging off the facade) stays a separate pad, whole —
   never clipped.
3. DSF clusters overlapping no kept OSM way behave exactly as today.
   An airport with zero OSM terminal ways is bit-for-bit unchanged —
   this is the degeneracy gate (§5.2).
4. `DSF_BUILDING_OSM_OVERLAP_FRAC` is RETIRED with the old rule.
   Verify `config.py:569` has no other consumer before deleting; if one
   exists, STOP and report.

Ordering stays `combined = dsf_survivors + osm_kept` (deterministic;
refs renumber — refs are per-build, not stable identifiers).

## 3. Constraints (standing law; violations are STOP-and-report)

1. Airside-is-king: zero airside effect. Building pads are groundside;
   the census gate in §5 adjudicates it.
2. Building pads remain rigid flat bodies under the existing seat law
   (`building_feasibility.building_feasible_levels`, cap 0,
   full-frontage at ≥ `BUILDING_FULL_FRONTAGE_AREA_M2`). No seat-law
   change in this spec: one way → one pad → one seated level.
3. No new role literals; the pads emit as `ROLE_BUILDING` with
   `ref=f"building{i+1}"` exactly as today (`pipeline.py:2935-2940`).
4. Downstream gates (`_close_building_outline`, boundary-centroid gate,
   `simplify(TERMINAL_SIMPLIFY_TOL_M)`) are untouched. If any of them
   silently drops a ≥ 100,000 m² way (Concourse C is 151k m² — larger
   than any pad emitted before), that is a finding to report, never to
   patch around ad hoc.

## 4. Tests (twins first; headless, tmp_path, no network)

In the file that already covers this seam (`tests/test_dsf_buildings.py`
or a sibling; consult `tools/INDEX.md` before adding any new tool):

* one OSM way + interior cluster swarm → exactly one combined polygon,
  the way; swarm absorbed;
* a cluster 60 % outside the way → survives whole;
* a cluster at exactly the absorb fraction boundary (0.5) → absorbed
  (≥, not >);
* zero OSM ways → output identical to input clusters (degeneracy);
* the old-rule case (way 51 % covered) → way kept (regression pin
  against reintroduction of the drop).

## 5. Acceptance — ONE OTHH build + matched census

1. Unit tests above green; blast-radius suite for `terminals.py` +
   `pipeline.py` via `tools/run_with_ledger.py`.
2. OTHH patch build through the harness (`tools/harness/build_airport.py
   OTHH`, lane worktree, shared data repo per the mount ritual): each of
   the six central ways emits exactly ONE `role=building` pad whose
   outline IoU-matches its OSM way ≥ 0.9 (after simplify); the ~81-pad
   swarm inside them is gone; report the pad count delta (125 → expected
   ≈ 50) and each kept way's single `altitude`.
3. Degeneracy: a battery airport WITHOUT OSM terminal ways in its
   extract builds byte-identical (body hash, `tail -n +3`). Battery
   airports WITH OSM terminal ways: enumerate which ways change
   representation, report pad-count/area deltas per airport — expected
   and wanted, but named, never silent.
4. Census (`tools/harness/census.py`, law-true frame) OTHH vs the
   2026-08-08 control: zero NEW adjudicated airside rows; groundside
   deltas attributed (fewer pad↔pad steps expected — the interior
   fragment edges stop existing).
5. Build-time impact statement (tripwire): expected reduction (fewer
   pads downstream); one line in the report.

## 6. Convergence guards (mandatory)

Materiality floor 0.01 m / 0.01 pp; attempt cap 2 then STOP-and-report;
`.progress` heartbeat in the lane scratch dir. Honest budget: 1 OTHH
patch build + 1 control-comparison census + ledger suite; hard cap 2
OTHH builds. Timing runs: none (no timed claim in this spec).
