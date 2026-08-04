# Split-level building seats: sectioned pads, loud polytopes

Fable spec, 2026-08-04 (lead-reviewed, approved). Implements the owner's split-level ruling
(RULINGS, landed 170d4e3): a building whose footprint relief exceeds a
threshold gets SECTIONED seats — each section level, steps at section
joints; the seat coupler couples sections; an empty coupling polytope
is LOUD attribution, never a silent ship. Threshold is an
owner-adjustable constant, provisional default from the coupler's own
gap data. Lines against 399c24d. BINDING: docs/RULINGS.md
(feasibility-is-guaranteed; band-lawful displacement / ONE band;
grade-law completeness; convergence guards).

## Mechanism (carrier_attrib/DOSSIER.md §§5–6; dossier_fixes/)

One flat seat is forced onto relieved footprints:

- **building181 (HECA)** — 12 ring nodes, DEM 101.72–105.54 (3.81 m
  relief), seated flat at 105.772, ABOVE the whole footprint and
  1.858 m above its own node-band ceiling at 2 nodes. Carried 16 000
  stall sweeps (50.5 % of HECA's budget) and survives as a gate-on
  carrier ×6 in the spine-freeze round (spine_freeze/RESULTS.md #3).
  The band clamp (`O4_SEAT_BAND_CONSISTENT`, anchors.py:247, landed
  c5d39f8 default OFF) removes the over-ceiling arithmetic but cannot
  make one level fit 3.81 m of ground — that needs sections.
- **building197 ↔ building201 (HECA)** — touching (gap 0.0 m), ring
  relief 13.75 m (40 nodes), coupling polytope EMPTY, shipped 5.9 m
  apart by the silent fallback (now loud per c5d39f8 §4). building188:
  10.99 m over 43 nodes. Production census (dossier_fixes logs, every
  HECA arm): `EMPTY POLYTOPE: 76 pad(s) / 126 coupled pair(s) admit NO
  jointly-feasible seat set; 105 pair(s) SHIP violating their own
  coupling limit` (152/130 with `O4_SEAT_COUPLE_SHARED_SURFACE` on).
  The polytope is empty for a REAL reason — genuine relief — so per
  feasibility-is-guaranteed the LAW changes (sections), the solver is
  not tortured into a fiction.

## The design

1. **Trigger.** Footprint ring-DEM relief (max−min over ring nodes —
   the same frame the coupler's gap data uses) >
   `SPLIT_LEVEL_RELIEF_M`, an owner-adjustable constant in config.py.
   Provisional default **2.0 m**, derived from the coupler's own data:
   it must sit BELOW 3.81 m (building181 — the smallest measured relief
   that produced an unlawful seat) and ABOVE the small-pad population
   (the centroid-DEM path, `level = min(de, hi)` at anchors.py:~357,
   deliberately untouched — the dossier-fixes round's deviation-2
   population); 2.0 m also bounds a level section's worst seat-vs-DEM
   offset at ±1.0 m. HONEST LIMIT: the evidence brackets the threshold
   (0 < T < 3.81) but does not measure a boundary inside that bracket;
   the trigger census below is the data the owner re-derives it from.
2. **Section derivation.** Cut the footprint along DEM iso-lines
   quantized at `SPLIT_LEVEL_RELIEF_M`: contiguous sections, each
   section's DEM relief ≤ the constant, joints snapped to footprint
   geometry with a min-section-width guard (no slivers). Geometry-phase
   work: sections are born as `building`-role shapes with their law
   attached (single-solve: shapes born with role/caps/law).
3. **Per-section seats.** Each section runs the EXISTING seat law
   independently: the frontage/band-consistency law (dossier-fixes §2)
   applies per section — seat clamps into `_frontage_band` ∩ the
   node-band at the section's own contact nodes (ONE band,
   `reach_band_unified` — LEAD ANNOTATION 2026-08-04: this band is
   under owner challenge (1-cm HEAZ intervals are an attribution case);
   §3 pins to WHATEVER band the seed attribution certifies — implement
   against the current band, expect a re-pin. RESOLVED 2026-08-04: the
   band is certified TRUTHFUL given complete seeds — §3's clamp is
   lawful once seed-fix §2 (`O4_BAND_SEED_COMPLETE`) lands; before
   that it inherits the 2-node floor-above-own-hard defect (HECA
   4818/2863) and merge adjudication checks §3 rows against that
   list); a section below the small-pad size cut takes
   the small-pad path. No new seat mathematics.
4. **Section joints.** building|building steps at the joints — already
   step-exempt (the `_both_buildings` exemption, owner 2026-06-20);
   declared in the sidecar (`section_joints`) so the validator SEES
   them (visibility, per grade-law completeness). Intra-building
   section pairs are NOT grade-coupled (the joint is the declared
   step); only INTER-building pairs enter the coupling law — this is
   what makes gap-0 neighbours feasible: building197's low section can
   meet building201's low section at the touching edge.
5. **Coupler.** Sections are the coupling unit: each enters
   `build_building_seats`' pair graph (anchors.py:192) with its own
   ring; pair gaps are section-to-section. The empty-polytope report
   (c5d39f8 §4) is UNCHANGED and stays loud — it is this round's
   instrument, expected to fall, never silenced.

Gate: `O4_SPLIT_LEVEL_SEATS`, default "0". Arms may combine with
`O4_SEAT_BAND_CONSISTENT` / `O4_SEAT_COUPLE_SHARED_SURFACE`; every
arm's `env | grep O4_` is logged.

## Pre-registered outcomes (bands)

1. HECA empty-polytope line: "pairs shipping in violation of their own
   limit" 105 → −60 % success / −30 % partial; 0 movement ⇒
   STOP-with-attribution. Sectioned-unit and pad counts quoted.
2. building197↔201: the shipped 5.9 m gap-0 step → adjacent-section
   seats within their coupling limit at the touching edge (≤0.5 m
   step-cap scale) or a declared section joint.
3. Deep-pocket carriers: the seat-over-own-ceiling class (5 seats, max
   +1.858) → 0; carriers (1020,4970)/(1021,1742x) lose their ~1.9 m
   seat component (the dossier's quantified split). PRE-REGISTERED
   NON-GOAL: the pocket fraction does NOT clear from this round alone
   (DOSSIER §6: the ~11 m remainder is steep truth — the terrace law's
   arm owns it; do not iterate on the pocket here).
4. Trigger census per airport: sectioned buildings quoted; expected
   concentrated at HECA's terminal pad family; SPLP/CYXY/KCLT
   few-to-0. Sectioning >25 % of any airport's seated buildings ⇒
   over-fire STOP (return the census, re-derive the constant with the
   owner).
5. Small-pad fence: every pad below threshold seats byte-identically in
   the A/B (the deviation-2 population untouched — asserted, not
   assumed).
6. Census both frames, all five airports:
   `within_pair.ground.micro/slope` building|building rows (352+115 at
   HECA in the drain frame) fall 20–60 %; mixed apron|building step
   rows do not rise beyond declared-joint accounting.

## Acceptance

Gate-off byte identity (body hashes, 2×): SPLP 1531e6d0 / CYXY
5b7a1912 / HEAZ 5854d6e7 / HECA 2a28d01b / KCLT 74c4731f. Suite: same
23 reds; new tests (synthetic-relief section derivation, intra-vs-inter
coupling membership, per-section band clamp, loud report unchanged,
sidecar round-trip, small-pad fence). Runway vertices byte-identical.
Only `check_build_time --run` timings quotable; no timing claim this
round; ≥1 %-budget cost ⇒ Fable-5 optimization review per hard law.
Build budget: identity 2×5 + HEAZ probe + HECA arms ≈ 1.5–2 h honest
wall total, foreground, WORKTREE (venv/OSM_data symlinked), no commit.
Convergence guards: 0.01 m materiality, 2 attempts, `.progress`.

## STOP rules

Over-fire (band 4); any section seat outside its own node band; the
empty-polytope pair count RISES; band-1 no-movement; second miss on any
target.

## Out of scope

The apron terrace law (own spec — including the pocket clearance); the
consensus retirement; flipping any seat-gate default (needs a battery);
groundside lots; changes to the small-pad path.
