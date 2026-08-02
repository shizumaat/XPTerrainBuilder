# Owner rulings — canonical, agent-visible

Standing rulings from the owner that gate design and implementation. This file
exists because subagents never see the lead session's memory: **every
delegation brief must link this file**, and a brief that would violate a
listed ruling is invalid — the implementer stops and reports rather than
deciding. Only the owner revises a ruling; the lead session updates this file
in the same session a ruling lands. Entries marked PROVISIONAL are live law
until the owner revisits them.

Process law (delegation model, Fable-vs-Opus roles, build-time budgets, run
ledger) is canonical in `Ortho4XP/CLAUDE.md` and is not duplicated here.

## Surface law (airside / groundside / solver)

- **Airside is king** (standing). Groundside must have ZERO effect or pull on
  airside; airside solves first, groundside conforms. Groundside witnesses,
  anchors, or mouth-pull on airside are defects, not inputs.
- **Feasibility is guaranteed** (standing; ESCALATED 2026-08-01). A real
  airport with real thresholds ⇒ a lawful surface EXISTS. Break regions and
  quarantine are law defects to attribute (metric, anchor value, role/cap, or
  false topology) — never a legitimate answer. Quarantine is UNAUTHORIZED;
  zero breaks in paved areas; all counts are full-census, never
  quarantine-excluded.
- **Groundside terrace law** (2026-07-30). Only pavement and ROADS inside
  groundside are graded; the ground between them may terrace freely
  (retaining walls). Groundside is never a feasibility witness for airside.
- **Free-road ruling** (2026-07-27). Roads inside or edge-sharing an apron
  ARE the apron (never carve); only completely free road-width pavement
  grades as a road. Canonical text: `groundside.free_road_subsegments`.
- **Reach follows centerlines** (2026-07-30). Feasibility/reach follows TAXI
  CENTERLINES only; buildings and empty aprons are endpoints on frontage
  chords, not envelope walks over the pavement pair graph.
- **Anchor placement law** (2026-08-01). NO hard anchors mid-taxiway;
  interior corridor nodes are free. A misplaced anchor is itself the defect —
  a sharp local pit/spike in a smooth field means test anchor legitimacy
  before any two-authority story.
- **Adjacent-ground zone law** (2026-08-01, PROVISIONAL). Only zones 1–2 are
  graded; beyond them, raw DEM. Steps at the graded/DEM boundary are lawful
  terraces and validator tear checks must exempt them.
- **Band-lawful displacement trumps DEM** (2026-08-01). Metres moved is NOT a
  defect metric. Lawfulness conditions: endpoint band membership, law-true
  spines, edge-follow. ONE band (`reach_band_unified`); seats and endpoints
  both consume it.
- **String purpose statement** (2026-08-01). Strings exist ONLY to prevent
  unnecessary hills/valleys in otherwise correctly graded taxiways — a
  smoothing refinement, never a surface authority. Default scope is taxiway
  corridors; aprons excluded unless the owner says otherwise. The strings-off
  arm is the visual-quality reference; refinement is measured as "same
  surface, fewer hills/valleys", NOT as chord-target attainment.
- **Cut-piece floor: accept-the-drape** (2026-08-01, PROVISIONAL, option c).
  Do not fix the missing cut floor. Probe builds inflate the count
  (303-vs-36).

## Acceptance and measurement

- **Absolute-zero acceptance** (2026-08-01). App builds require ZERO
  actionable law-true defects on battery airports, pre-existing included. No
  sim testing with known issues.
- **Builds parallel when not timing** (2026-07-31). Correctness builds may
  run concurrently (extra Ortho4XP instances). Only runs whose OUTPUT IS A
  TIME (`check_build_time --run`, profilers) are exclusive.
- **Build budget discipline** (standing). Escalate cost only as needed:
  reuse existing artefacts → offline replay → unit tests → ONE test airport →
  full battery at final acceptance only. Every brief states a build budget
  and quotes the honest total.
- **Single-pass principle** (standing). Never do a task twice — prefer
  reorder/identity-preservation over re-derive/transport; build once, filter
  per consumer.

## Facts the owner has corrected repeatedly

- **HECA is not flat.** ~85 m relief across HECA's runways is REAL (DEM and
  CIFP agree). Never infer flatness from field elevation.
- **Scenery signature is apt.dat + DSF only.** Deep pack walks stay out.

## Process

- **Intent questions route to the owner.** Mechanisms get measured; INTENT
  gets asked. Ask for artifacts (KML/OSM/counts) — they're usually offered.
  One owner sentence has repeatedly replaced a build and several analysis
  rounds.

- **Runway-edge terrain law** (2026-08-01, owner verbatim class): retaining
  walls are NEVER lawful at a runway edge — runway surroundings must grade
  away smoothly. Further: "there's very specific requirements for the
  terrain all around runways that should all be part of our grade law.
  Review the [FAA/EASA] docs, and determine what's missing from our grade
  law so we are following the regs." The standards-gap review is a
  standing work item until closed; runway↔retaining_wall pairs must be
  visible to the validator.
- **Band-shaped baseline accepted** (2026-08-01). The route-metric
  envelope's two-sided tightening toward the band (measured: 47.7% of
  HECA vertices moved, balanced up/down, dip sag 5.81→4.79 m) is the
  accepted baseline surface character going forward.

- **Region-specific rulesets** (2026-08-02, owner verbatim class): "FAA
  applies within the USA, and ICAO everywhere else. So we should support
  region specific regulations and provide the code structure to allow
  the possibility to choose and/or support multiple rulesets in the
  future." Grade-law/standards constants become RULESET-keyed (FAA /
  ICAO-EASA to start), selected per airport by region (default: ICAO
  code prefix), with a first-class ruleset structure — never hardcoded
  branches. Each ruleset carries its own authority's PRIMARY-VERIFIED
  values (standards-gap review 2026-08-02); "take the stricter" is
  superseded by jurisdictional fidelity. Emitters and validators read
  the SAME ruleset (lockstep).

- **Service-road absorption rule** (2026-08-02, DRAFT from owner field
  report — pending his confirmation of this canonical text): pavement
  that shares substantial edge with a service-road spine AND has
  road-width dimensions IS that service road — classified and graded as
  service (axial route grading, spine-graph member), never groundside.
  The service-road analogue of the free-road ruling. Note the existing
  law runs the OPPOSITE way (service near terminals = groundside
  evidence, terminals.py GROUNDSIDE_HIGHWAY) and scorer v2 has no
  service-adjacency feature at all; measured class at HECA: 41 shapes
  (29 genuine road bodies), invariant across arms, HECA-specific.

- **Grade-law completeness standard** (2026-08-02, owner verbatim class):
  "our grade law must not allow us to generate an airport patch that
  violates any of the region appropriate regulations." Every regulatory
  requirement needs BOTH an emitter/solver-side binding constraint (the
  patch cannot be generated in violation) AND its validator twin
  (lockstep). A validator-only check is visibility, not law. Gap
  inventory: standards-gap review 2026-08-02 (G-1..G-14) + the
  field-report families (transverse taxiway, drainage spine, coverage).

- **ROFA exemption approved** (2026-08-02): the FAA existing-runway
  exemption is taken — the ≤0% side-slope rule does not bind; the
  back-slope limits (8:1/10:1/16:1 by group, FAA Table 3-7 S-5) do.
- **THE CAMPAIGN GOAL** (2026-08-02, owner verbatim): "iterate until all
  issues found in the KML v3 are resolved, the missing regs are added to
  grade law, all grade law violations are detected and flagged by tests,
  nothing can be quarantined, and SPJC, SPLP, CYXY, HECA, and KCLT all
  build with no known violations." KCLT JOINS THE BATTERY as the
  FAA-ruleset fixture. Acceptance = zero known violations, full census,
  no quarantine machinery, generation-binding law with test twins, all
  five airports.
