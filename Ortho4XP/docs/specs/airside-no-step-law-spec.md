# Airside no-step law — grade + rate-of-change over DIRECT distance
# (Fable spec, 2026-08-27; owner ruling RULINGS 2026-08-27 "NO STEPS IN
# AIRSIDE PAVEMENT", refined: magnitude spread smoothly is fine — the
# law is the runway-style grade + curvature pair, applied to ALL
# airside pavement)

## §0 Measured frame (round3-integration branch, combined patch
## `/tmp/harness/HECA_20260827T021457.osm`, census ledgered)

The accumulation gap the ruling closes, measured twice:

- Dip site `30.1290177,31.4055841`: junction pieces 73.88–74.33 beside
  membrane 72.62–73.62; nearest-pair reads (junction/station → nearest
  lattice node): max +0.60 m at ≤30 m pair distance (≈2 %+ direct),
  +1.07 m at ≤50–75 m — every pointwise NEIGHBOUR pair within budget,
  the direct-distance grade over cap. The low membrane nodes sit
  130–137 m from the nearest station, coupled only through chained
  50 m × cap budgets that accumulate.
- Item-2 site `30.104671,31.3973462`: apron −10258 at 103.2 vs
  junction −10250 at 108.9, ~35 m apart — ~16 % between two airside
  surfaces. The road (round: crossing conformance) now descends at its
  cap ceiling; the airside spread itself is the offender.
- Both surfaces are pointwise-lawful under the pre-ruling law: no
  family prices a NON-neighbour airside pair against direct distance.

## §1 THE LAW

1. **LOCAL DIRECT-DISTANCE GRADE.** For airside pavement nodes (the
   `enclaves.ENCLAVE_AIRSIDE_ROLES` register — one register, never a
   hand list) within a local window `AIRSIDE_NO_STEP_WINDOW_M`
   (default 150 m, config constant with a STANDARDS.md note), the
   bound is |Δz| ≤ cap × DIRECT (euclidean) distance — within one
   shape AND across airside shape boundaries. The cap is the pair's
   own from the existing chain (`classify_pair` semantics: corridor
   region 1.5 %, stand chords 1 %, back-edge 5 % — reuse, never a new
   cap value).
2. **RATE-OF-CHANGE.** Along the membrane's own polylines (lattice
   rows/columns, spine-station runs, ring sequences) grade CHANGE per
   unit length is bounded by the existing vertical-curve machinery's
   analogue for the surface's family (the `strip_arc` / runway
   K-factor pattern — extend that machinery, never fork it). A 1.5 m
   bowl spread over 200 m with lawful curvature is LAWFUL; the same
   1.5 m concentrated over 30 m is not — the owner's refinement
   verbatim.
3. **SOLVER SIDE.** The §1.1 pairs enter the one-solve graph as law
   edges: per airside node, its k-nearest airside neighbours within
   the window (k bounded, default 16, spatially spread — a config
   constant), budgets cap × direct distance. SENIORITY LADDER (the
   adoption principle, now explicit): runway profile > taxi centerline
   profile (spine stations included, per round-3 Amendment 2 they are
   constants) > seated pads > membrane free nodes. An edge between
   tiers constrains the LOWER tier only (one-sided); an edge within
   the free tier is symmetric. The item-2 apron therefore RISES toward
   the junction within its own caps; the junction (centerline-valued)
   does not move.
4. **DEM DEMOTION (DEM-LAST applied to the membrane).** Airside
   membrane interior free nodes carry NO DEM-proximity objective term:
   seeded by the taut scaffold, they settle by curvature-minimisation
   subject to the law edges. The sag that produced the dip was DEM
   preference inside the lawful range — RULINGS 2026-08-25 already
   demoted that to last; this enforces it for the membrane class.
5. Flag `O4_AIRSIDE_NO_STEP`, default ON; OFF byte-identical.
6. **CENSUS.** A registered family `airside_no_step` prices exactly
   the sidecar-published §1.3 edge enumeration (the
   `apron_lattice_membrane` precedent: solver publishes, census prices
   the same list — one law, one population); the §1.2 rate term
   extends the existing arc-family publication for the new polyline
   classes. `LAW_FAMILIES` registration with the register/parity
   twins, so omission is structurally impossible.

## §2 Twins

- Synthetic apron, two anchors 1.5 m apart in z at 40 m spacing →
  §1.1 edge over cap → solve pulls the free side within law; same
  anchors 200 m apart → lawful, untouched.
- Cross-shape: junction ring at +1.5 m beside an apron membrane 20 m
  away → membrane rises, junction byte-identical (seniority).
- Rate: bowl of fixed depth at two widths — narrow violates the arc
  term, wide passes.
- Flag OFF byte-identical; empty airside → vacuous.

## §3 Acceptance (ONE HECA build on round3-integration + census A/B
## vs `HECA_20260827T021457`)

- Dip site: nearest-pair table (30/50/75 m) — every pair within
  cap × direct distance; junction pieces byte-identical (seniority);
  report the surface delta honestly.
- Item-2 site: the apron −10258 ↔ junction −10250 spread lawful over
  direct distance (apron risen, junction unmoved); re-read the
  crossing line — expect the road's adopted descent to now start from
  a lawful airside surface.
- T site / line T: unchanged or better vs the combined frame.
- Census: A/B with the new family reported separately (its rows are
  un-blinding); other airside families not regressed row-for-row at
  the named sites; SPJC/CYXY non-regression arms.
- Convergence guards: materiality 0.01 m, attempt cap 2, STOP on
  second miss, heartbeat. No shared-repo writes, no timing claims;
  build-time impact statement (k-nearest edge build cost included).
- Supersedes the round-3 "dip residual accepted" line: that residual
  is now the offender this law exists to price.

## Amendment 1 (Fable, 2026-08-27 — rulings on the lane's two STOP
## questions; attempt cap RESETS, cap 2)

Measured (lane/nostep 89617e69): membrane direction correct (dip
over-cap pairs 344 → 212 at 75 m, other airside families −116, line-T
membrane rose toward the spine), but 4,474 of 6,072 junction nodes
moved (worst 1.64 m) and the item-2 spread survived behind the lane's
visibility gate. Rulings:

1. **TIER 2 IS THE WHOLE TAXIWAY-FAMILY SURFACE, AND A NODE'S TIER IS
   THE MAX OVER ITS CARRYING SHAPES.** "Taxi centerline profile" in
   §1.3 was under-read as spine-adjacent nodes only. The ruling: every
   node of taxiway-family pavement (taxiway, junction, stub,
   primary_parallel — ring or interior) is tier 2: that surface is the
   centerline profile's transverse writeback, and letting the no-step
   edges renegotiate it re-creates the round-3 anchored-side disease.
   A node shared between shapes takes the SENIOR tier (closes the 5
   runway+road carve-corner movers: runway-shared ⇒ tier 1, frozen).
   Tier2↔tier2 no-step pairs are CENSUS-PRICED but NOT solver-imposed
   this round (report-first): a violating pair there is a
   profile-law docket, never a solver tug-of-war between two
   authorities.
2. **THE VISIBILITY GATE IS RATIFIED — §1.1 BINDS WITHIN CONTIGUOUS
   AIRSIDE PAVEMENT ONLY.** The lane's deviation was correct and the
   spec's §0 framing of the item-2 pair was wrong: RULINGS 2026-08-24b
   stands ("a step is lawful only across a pavement gap"), and the
   2026-08-27 ruling's own basis is aircraft traversal — no aircraft
   crosses unpaved ground between two disjoint pavements. The chord
   must lie inside the airside pavement union (the gate as built).
3. **ITEM-2 EXITS THIS LAW AND BECOMES AN ATTRIBUTION DOCKET.** The
   real defect there is ROAD INFEASIBILITY between two authorities:
   the road is welded to apron −10258 (≈102–105) and asked to meet
   junction −10250 (≈107–109) across ~49 m — 8.04 m of spread against
   a 3.9 m cap allowance. Under feasibility-is-guaranteed one of the
   two authorities is mis-valued at the site; attribute WHO authors
   apron −10258's values (ring welds? pads? DEM sag?) before any fix.
   Separate follow-up, not this lane's attempt.
4. **Acceptance restated:** dip-site (and whole-patch) taxiway-family
   byte-identity is now STRUCTURAL via tier 2 — assert it; nearest-
   pair tables over contiguous-pavement pairs only; runway-family
   moved nodes 0 by the max-tier rule; SPJC/CYXY re-run with matched
   controls (expect the §1.1 residual to shrink under the gate +
   tier-2 freeze; report honestly). The two lane scratch readers
   (nearest-pair table, family term-split) are on their second use —
   PROMOTE both into tools/ with INDEX rows and twins per RULINGS
   7e90032.

## Amendment 2 (Fable, 2026-08-27 — TWO-PASS CONFORM: senior
## byte-identity becomes structural; attempt cap resets, cap 2)

Measured (lane/nostep 459415a5, A1): tier-2 widening + max-tier cut
taxiway-family movers 4,473 → 3,342 (HECA) but cannot reach zero —
the one-solve graph expresses one-sidedness only against a CONSTANT,
and a junction ring vertex is a free variable of its own within-shape
law, so an imposed tier2↔tier4 edge still moves it. Freezing tier 2 at
phase-A values would differ from the flag-off arm in the OTHER
direction; making tier2↔tier4 report-first deletes the coupling that
lifts the membrane. The staged principle (round-3 Amendment 1) is the
answer:

1. **TWO-PASS CONFORM.** Pass 1: the solve WITHOUT any imposed no-step
   edges — byte-identical to the flag-off arm by construction (assert
   it, don't argue it). Pass 2 (the MEMBRANE CONFORM pass): every
   tier-1/2/3 node is a CONSTANT at its pass-1 value; only tier-4
   membrane nodes are free; impose the no-step edges (senior↔4
   one-sided against the constants, 4↔4 symmetric) TOGETHER WITH the
   tier-4 nodes' own existing laws (within-shape, lattice, station
   edges) and the §1.4 DEM demotion, and re-project. Emit pass-2
   values for tier 4, pass-1 values for everything else.
2. Consequences, all structural: senior byte-identity vs the flag-off
   arm needs no gate — non-tier-4 values ARE the flag-off values; the
   runway carve-corner movers (5 HECA / 2 SPJC) vanish (shared nodes
   are max-tier constants, the emit author cannot flip); tier2↔tier2
   stays report-first exactly as ruled.
3. **Acceptance restated:** assert zero non-tier-4 value deltas vs the
   matched flag-off arm (whole patch, all airports); dip-site table
   expected at-or-better than A0 (the membrane now conforms to
   unmoved seniors — report honestly); line T, overlap read, census
   A/B as before; SPJC/CYXY matched controls; build-time statement
   (pass 2 is one extra projection over the tier-4 subset — quote its
   phase cost).
