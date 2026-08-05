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

- **Lateral-contiguity grade law (service-road absorption, FINAL)**
  (2026-08-02, owner-confirmed): (1) A FREE road — road-width, genuinely
  unpaved ground on both sides (any real gap counts, however thin;
  adjacency = literal shared boundary in the sliced arrangement, never
  proximity) — takes the service-road cap with axial route grading.
  (2) At any station, the laterally-contiguous paved CROSS-SECTION
  (side-sharing closure across any number of touching pavements) takes
  the STRICTEST cap of any class present in it — a road alongside or
  through an apron grades as apron; five ring roads touching one apron
  are one apron-grade surface. The closure NEVER propagates through
  end-connections/mouths — a road resumes its own cap the moment it
  leaves lateral contact (two aprons joined by a road: only the free
  between-segment is road-capped). (3) Segmentation is per-segment via
  the existing mouth-cut machinery. (4) Implementation SHOULD fully
  absorb laterally-contiguous road stretches into the adjacent surface
  (merge, fewer nodes) rather than carry separate shapes with cap
  overrides — owner: "I'm not sure there's a need to keep the road
  separate inside an apron"; the free-road ruling's absorption is the
  model. (5) The runway-strip footprint law supersedes inside strips.
  Classification corollary: road-width pavement sharing an edge with a
  service-road spine is SERVICE ROAD, never groundside (scorer v2 needs
  the service-adjacency feature; the HECA 41-shape class is the fix
  population).
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

- **The goal is LAW COMPLIANCE, not instrument-zero** (2026-08-02, owner
  verbatim: "The goals should always be compliance with grade law, not
  necessarily absolute zero"). The campaign gate is zero VIOLATIONS OF
  GRADE LAW — where the law includes its own exemptions, floors and
  provisional rulings (lawful terraces, the open-boundary floor, the
  ROFA exemption, the materiality floor). A census row that is lawful-
  by-exemption or below materiality is NOT a defect; census instruments
  REPORT, the law ADJUDICATES. "No known violations" on the five-airport
  battery means no adjudicated law violations, never a demand that every
  instrument read zero rows.

- **Lateral-contiguity absorption is class-universal** (2026-08-03, owner
  confirmed): the absorption extends to service roads welded to ANY
  paved class — groundside lots included, not only aprons. "Another
  class" in the law means any; one paved laterally-contiguous surface,
  one (strictest) cap. Consequence: the A2/A3/A4 residual break family
  (259 nodes) is one absorption fix; the service DEM-follow's private
  envelope may not act as a second grading authority.

- **Owner constants: lot 5%, service road 8%** (2026-08-03, approved on
  the primary-source research): `GROUNDSIDE_MAX_GRADE` 0.040 → 0.050
  (citations: ADA §403.3 1:20 walking-surface ceiling, Iowa SUDAS §8B-1,
  Santa Barbara §D.5 — the old 4% was uncited, inherited from the tunnel
  constant) and `SERVICE_ROAD_MAX_GRADE` 0.050 → 0.080 (VDOT GS-9
  service-road standard, level terrain 7-8%; no aviation authority
  regulates either grade — verified FAA/ICAO/EASA/ACRP silent).
  `service_junction` rides the same constant (flag in the round if the
  owner wants junctions split). Consequences: lot+road absorbed surface
  now binds at 5% (the lot); road→apron absorption stays 1%
  (regulation-backed, unchanged); region-invariant (no FAA/ICAO split
  exists landside). Lands as its own identity round AFTER kill-prep
  (new gate-off baselines minted, measured surface effect quoted).
  Standards-gap addition: groundside has no drainage MINIMUM (every
  civil source carries 0.6-2%) — queued as a law item.

- **Single-solve architecture** (2026-08-03, owner): "the most efficient,
  and error free, architecture is ingesting all the data, refining all
  the geometry, and then a single elevation solve with all the grade
  law." END STATE: ingest → geometry (every shape born with role/
  ruleset/caps/law) → ONE solve (all law as directed constraints;
  airside-is-king = constraint direction, groundside receiver-only; the
  one band; loud error on genuine contradiction) → emit verbatim.
  EMITTERS EMIT, NEVER GRADE. Every remaining post-solve value-writer is
  scheduled for ingestion into the solve or retirement: the finalize
  terrain-transition chain (dies when lot law enters the solve —
  receiver-only membership), OLS road regrade, adjacent-ground band
  values, tunnel-ramp lerps, drainage re-clamps, and to_osm consensus
  averaging (single-authority emission replaces it). Four second
  authorities already retired this campaign (pair-graph envelope,
  service private envelope, terrain-pin quarantine, break blend).

- **Apron terrace law** (2026-08-04, owner): long aprons on genuinely
  steep ground MAY terrace into level panels with declared joint steps —
  "but it has to be done in a way that does not interrupt any spine
  where aircraft have to travel." BINDING CONSTRAINT: terrace joints may
  NEVER cross a taxi spine/route; panels are bounded by the taxi
  corridors crossing the apron, joints live only on non-taxiable
  interior edges, and every spine grades continuously at cap through
  the apron regardless of panelization. Evidence: HECA steep-truth runs
  1.47-2.45% over 378-1,469 m vs the 1% cap (carrier_attrib/DOSSIER.md).
- **Split-level building seats** (2026-08-04, owner): a building whose
  footprint relief exceeds a threshold gets SECTIONED seats (each
  section level, steps at section joints); the seat coupler couples
  sections; an empty coupling polytope is LOUD attribution, never a
  silent ship (HECA building197: 13.75 m ring relief, shipped 5.9 m
  step against a touching neighbor). Threshold constant is owner-
  adjustable, provisional default from the coupler's own gap data.

## 2026-08-04 — No degradation-shield interims; retire the string back door (owner)

Owner, verbatim: "There is no need for interim solutions that are
scheduled for deletion to try and keep airports from degrading
temporarily. Retire the string back door and implement the correct
solution."

Binding consequences:
1. GENERAL PRINCIPLE: a mechanism scheduled for deletion must not be
   kept alive to shield surfaces from transitional degradation. The
   lead's interim ruling holding `O4_CORRIDOR_REF_STRING` at "1" (the
   KCLT +95 / HECA −196 trade) is SUPERSEDED.
2. `O4_CORRIDOR_REF_STRING` default → "0" immediately (retired from
   production; the ref-pull lane carries the flip). The code path is
   DELETED in the seam-continuity round's kill along with the pull and
   the refs channel, as specced.
3. The correct solution proceeds: the seam-continuity constraint law
   (docs/specs/seam-continuity-constraint-spec.md) with the
   rod-composition fix as its precondition. The owner's directive
   authorizes the round including its endgame; phase C still honors
   its pre-registered bands and STOP rules — a band miss returns for
   attribution, it does not re-litigate this ruling.

## 2026-08-04 — Per-change timing gates SUSPENDED for the campaign (owner)

Owner question ("Why not build everything to plan, then profile on the
final design?") resolved with the lead's recommended option: DEFER +
TRIPWIRE.

1. SUSPENDED for the remainder of the architectural campaign: the
   per-change 1%-budget evaluation, per-round exclusive
   check_build_time runs, and per-change Fable-5 optimization reviews.
   No round's acceptance may require an exclusive timing run.
2. TRIPWIRE (zero-cost): every build already persists per-phase wall
   times to the ledger. A round FLAGS (investigation, not measurement
   builds) only if a comparable airport build goes grossly anomalous —
   ~2x — under comparable load. Quote no ledger number as a timing
   claim.
3. The 60 s / 300 s budgets REMAIN LAW; their adjudication moves to
   ONE final-design profiling round at campaign end: exclusive, fresh
   baselines re-recorded (the owed battery re-record folds in),
   budgets adjudicated, the Fable-5 whole-pipeline optimization review
   run once against the final architecture.
4. Timing-exclusivity discipline (foreground-only, no-nohup,
   quiet-machine) still binds THAT final round.

## 2026-08-04 — Runway flex law clarified (owner)

Owner, on the HECA 6907↔7236 inter-runway tension: "The CIFP numbers
can't be changed but as long as it's within grade rules, the runway can
flex a little."

Binding: CIFP threshold elevations are IMMOVABLE truth; between its
CIFP pins a runway profile MAY flex within runway grade law to drain
inter-runway/taxi-route tension. The 05R/23L case is the type specimen:
its profile rides to +9.18 m above DEM at the 6907 junction while a
0.125% tilt along its length would surrender the full 2.67 m shortfall
— lawful flex, CIFP untouched. Fix direction for seed-fix open item
(b): extend/verify the runway-flex (B2) machinery against this case
BEFORE any band or law change; the flex ledger + CIFP thresholds for
05R/23L are the first read.

## 2026-08-04 — Streamlined lane verification; one battery at the train tip (owner)

Owner: lanes need not each run full batteries — each lane verifies on
the single airport that stresses its specific work; ONE full battery +
suite runs at the merge-train tip before the batch is accepted.

Protocol (extends the build-budget ladder):
1. PER LANE: offline replay + unit twins first; gate-on measurement on
   ONE stress airport (lane-chosen, justified in the pre-reg); gate-off
   byte identity 2x on the stress airport + ONE cheap sentinel (CYXY
   class). Cross-airport claims are PRE-REGISTERED per lane but
   VERIFIED at the tip.
2. TRAIN TIP (once per batch, after the serial lane commits): full
   five-airport battery — identity, census matrices both frames, one
   full suite vs matched control. This gates batch acceptance, merge
   to main, and any sim build (absolute-zero acceptance law
   unchanged). The anchor-minting lane (defaults changer) lands last
   and its minting IS the tip battery — never mint anchors twice.
3. TIP FAILURE: bisect by commit, build only the failing airport;
   identity-mismatch-is-a-stop applies; the offending lane fixes
   forward or reverts.
Known trade accepted: a cross-airport surprise (the KCLT +145 class)
surfaces at the tip instead of in-lane — one bisect step later, many
batteries cheaper.

## 2026-08-04 22:40 PDT — Release-train priority: airside zero first (owner)

Owner: "If necessary, prioritize airside zero defects first, then
groundside if time allows." Binding for the 06:00 train and after:
1. Triage at every cut line: airside classes (runway, strip, taxiway,
   apron, junction, seam-on-airside) outrank groundside (lots,
   service roads, building seats, groundside pavement) whenever a
   choice must be made.
2. Flip verdicts score AIRSIDE-FIRST: a candidate that improves
   airside and costs groundside may still flip; the reverse may not
   (consistent with airside-is-king — groundside must never pull
   airside).
3. The release bar is ZERO ADJUDICATED AIRSIDE DEFECTS on the battery
   airports; groundside residue ships named in the release notes.

## 2026-08-05 ~05:50 — BUILD-COMPLETE-THEN-DEBUG (owner; supersedes the
## gating/train discipline for development)

Owner: the last months were prototyping/experimenting/learning — done.
We have the target architecture. Until the FULL system is implemented
and there ARE NO gates, errors are expected — so no intermediate
testing ceremony. Write ALL the grade laws and the systems to build
and verify, THEN start testing and bug fixing.

Binding consequences:
1. NO GATES. Every believed-in law becomes standing law; O4_ law gates
   and their env overrides are DELETED as their territory is touched.
   Byte-identity proofs, A/B arms, per-change batteries, flip trains,
   anchor-minting ceremony: RETIRED for development. Kept: determinism,
   the unit suite, the lockstep census as the one instrument, and
   certify-or-fail-loud in the solve.
2. Implementers DECIDE-AND-NOTE deviations toward the target
   architecture instead of STOP-and-wait; only a genuine architecture
   ambiguity escalates.
3. The target architecture (owner-ruled, unchanged): ingest all data →
   refine all geometry → ONE elevation solve carrying ALL grade law →
   emitters emit, never grade; single authority everywhere; airside
   solves first, groundside conforms; zero airside errors BY
   CONSTRUCTION — the census's only nonzero content is declared
   structures + terrain-vs-law tensions surfaced as named owner
   rulings.
4. Testing begins when the complete system builds: composed HECA+KCLT
   per debug cycle, airside census strictly decreasing to
   zero-plus-declared.

## 2026-08-05 — There is no lawful-infeasible ground (owner)

Owner, verbatim: "There is no 'lawful-infeasible ground'. DEM is a
seed, nothing more. We are grading pavement to the law. If we ever hit
something that says it's infeasible, it's either an incomplete, or
incorrect law, or a bug in the measurement or test."

Binding consequences:
1. DEM is a SEED — never a constraint, never an authority, never an
   excuse. Pavement (and everything the law governs) grades to the
   LAW.
2. The verdict vocabulary for any infeasibility/violation is CLOSED:
   (a) BUG — fix it; (b) INCOMPLETE LAW — the law lacks the machinery
   the situation needs (terrace, wall, flex freedom, RESA shaping…):
   complete it; (c) INCORRECT LAW — wrong constant/shape: correct it;
   (d) BROKEN INSTRUMENT — the measurement or test is wrong: fix it.
3. "Genuine terrain-vs-law tension", "named tension", "lawful-
   infeasible", "accepted residue" are RETIRED as terminal states.
   Anything previously so labeled (the HECA inter-runway family, the
   break-region "immovable" residue, deep-pocket fractions) is an open
   work item under vocabulary (a)-(d).
4. An "infeasible" report from any solver stage is itself a defect
   report about the law or the instrument — never a property of the
   ground.

## 2026-08-05 — DEM's role, and the constant-DEM invariant (owner)

Owner framing: DEM "provides potential data for where things get
seated within their feasible bands, but we should be able to emit a
perfectly compliant, error free airport where all the pavement is
within the grade laws if the entire DEM was zero, or 10,000m — the
pavement is all about smooth grades between the small number of
anchors."

Binding consequences:
1. DEM chooses WHERE in the lawful band a thing seats. It never
   shapes the band, never constrains, never blocks.
2. THE CONSTANT-DEM INVARIANT (a build oracle): a build with DEM ≡ 0
   or DEM ≡ 10,000 m MUST emit a zero-violation airport. This is the
   cleanest possible law/solver test — no terrain signal at all, so
   every remaining row is a law, solver, or instrument defect with no
   data confound. It joins the verification system as a standing
   synthetic twin (per real airport geometry, constant DEM).
3. The DEM loader's all-zero refusal (the missing-.hgt guard) stays
   for PRODUCTION data but gains an explicit synthetic path for the
   oracle — the guard catches absent data, not constant data.
4. Any violation whose explanation requires terrain roughness is a
   defect: something is reading DEM as a constraint.

ADDENDUM (owner, same conversation): the two synthetic extremes have
PREDICTABLE SEATING, not just compliance — DEM ≡ 10,000 m (airport in
an impossibly deep canyon) seats everything at its CEILING; DEM ≡ 0
(airport on a giant artificial plateau) seats everything at its FLOOR.
The oracle therefore asserts three things: zero violations in both
worlds, extreme-seating saturation (every free value at the band edge
nearest its seed), and — as the bonus diagnostic — the per-node
difference field between the two worlds IS the feasible band width.

## 2026-08-05 — Consult-before-create; promote-on-reuse (owner)

Owner: before creating any tool, script, or skill, an agent MUST first
consult existing resources; if the exact tool is not available, prefer
updating or expanding an existing one; anything used more than once is
encoded as a standard, re-usable tool that enforces consistency across
time, agents, and sessions. Creating something that already exists —
or worse, something slightly different — wastes time and causes
regressions and confusion.

Binding form:
1. CONSULT FIRST: tools/INDEX.md (the tool catalog) + tools/harness/
   are the first stop for any build/measure/setup need. The index is
   the consultation surface; a tool absent from the index is treated
   as absent.
2. EXTEND, DON'T FORK: a near-fit gets a parameter or a subcommand,
   never a copy. A slightly-different duplicate is a DEFECT (the
   census-wrapper frame errors are the precedent).
3. PROMOTE ON REUSE: the second use of any lane-local script is the
   signal to promote it into tools/ with an index entry (and a twin
   where it measures anything). Lane scratchpad scripts are one-off by
   definition and die with the lane — never copied forward.
4. Every new standard tool lands WITH its index entry in the same
   commit.

## 2026-08-05 — One shared data repo across lanes (owner)

Owner: a shared data repo across lanes is MANDATORY — no lane
redownloads or regenerates caches.

Binding form:
1. /Users/noah/XPTerrainBuilderData is THE data repo: DEM + insets,
   OSM extracts + road feeds, airport mod cache, geotiffs, masks, DSF
   cache, orthophotos. Every lane MOUNTS it (symlinks via the harness
   ritual) — never copies, never creates a private cache.
2. Downloads and cache regenerations write into the shared repo,
   EXACTLY ONCE, as EXPLICIT logged events (harness flag), never as a
   build side effect — the KCLT road-feed refresh that silently
   changed campaign hashes mid-night is the precedent this forbids.
3. Concurrent lanes never race a regeneration: the harness guards
   cache writes (lock or refuse-and-report).

## 2026-08-05 — Flat worlds first (owner); the synthetic ladder (lead)

Owner: focus on driving to ZERO on the two synthetic DEMs (all 0 and
all 10,000 m — the extreme low and high seating of the pavement
network) BEFORE reintroducing real DEM.

Working plan (lead, from the owner's question "am I missing
something"): the LADDER — (1) the two flat extremes to zero; (2)
analytic GRADIENT worlds (constant-slope synthetic DEMs at 0.5% /
2% / 10%) to zero — these cover what flat worlds structurally cannot
(terrace/certificate machinery never fires at zero relief; mixed
cut/fill transitions never occur), still with exact analytic ground
truth; (3) real DEM reintroduced — at which point any new failure is
seed-handling by construction, never law. Real-DEM batteries stay
RECORDED as reference frames throughout, not chased.

Named consequence, priced in: flat-zero REQUIRES the drainage-minimum
shaping law (a dead-flat apron violates the FAA 0.5% floor everywhere
— the generator must CREATE minimum drainage slopes regardless of
DEM). This is the largest known remaining generation project.

CORRECTION (owner, same conversation): the flat-DEM worlds are NOT
flat environments — CIFP threshold anchors keep their real spread
(HECA ~85 m), so the route graph connecting them carries the FULL
inter-anchor tension: flex, taxi-cap reconciliation, and
terrace/wall demand all exercise in the flat worlds. The lead's
"terraces never fire at zero relief" was a defect report, not a plan
gap: any trigger keyed on DEM STEEPNESS (the terrace/certificate
steep-truth signature foremost) is keyed on the WRONG QUANTITY —
verdict (c), incorrect law. Triggers derive from ANCHOR-ENVELOPE
INFEASIBILITY (hard values + caps + geometry), identical in flat and
real worlds. Audit every DEM-steepness-keyed trigger. The gradient
rung demotes to optional (covers only mixed cut/fill transitions and
DEM-follow seed-tracking).

## 2026-08-05 — Drainage scope for this version (owner)

Owner: this version implements ONLY (1) runway crowns and (2)
pavement-edge (unpaved areas) drainage. No other pavement drainage
grading.

Binding consequences:
1. RUNWAY CROWNS: generated and bound (this answers open question Q5
   for runways — the crown minimum BINDS on runways; taxiway/apron
   crowns stay recorded-unbound with citations).
2. PAVEMENT-EDGE DRAINAGE: the unpaved-area down-slope shaping at
   pavement edges (the adjacent-ground mandatory-down family) is IN —
   completed and verified.
3. INTERIOR PAVEMENT DRAINAGE GRADING (the FAA apron drainage-minimum
   shaping — KCLT's 1,099-row family and its siblings) is
   VERSION-DEFERRED: the census still REPORTS the family (instruments
   report), but the acceptance gate adjudicates it VERSION-DEFERRED
   with this ruling as the citation — it does not block the
   drive-to-zero and is never silently dropped.
4. Flat-world zero is therefore: zero adjudicated rows EXCLUDING the
   version-deferred classes, which appear in every report under their
   own heading.

## 2026-08-05 — CIFP thresholds absolute for v1 (owner)

Thresholds stay AT CIFP values for the first release of the cleaned-up
model and engine — the DEM-credibility threshold lift
(pavement/runway_segments.py generate_patch_osm, sweep finding #20) is
DELETED. Datum harmonization may be re-introduced later if needed.

## 2026-08-05 — The HECA central-U apron model (owner, ENCODING PENDING
## three clarifications)

Owner: HECA is feasible and gradable along the taxi route spines, for
certain. The large central U apron wrapping the terminals between
05C/23C and 05L/23R follows the building grading rules — straight
chords from building frontage out to the spine — and BETWEEN buildings
along the BACK apron edge, STEEPER RAMPS may support a sort of
terracing, FAN-like, never creating grade violations where aircraft
move.

Already in law: frontage chords building→spine
(building_requires_full_frontage + the frontage band); joints/steps
never crossing spines (terrace law, structural); movement-area cap
protection (corridor cover). NOT yet in law: the steeper-ramp class —
current law offers only LEVEL panels with STEP joints (walls) as
over-cap relief; a continuous fan-shaped ramp zone at the back edge
between buildings has no legal form and would today read as apron-cap
violations or be answered with walls. Encoding awaits the owner's
three answers (asked in-session).

## 2026-08-05 — THE FAN-RAMP LAW (owner, clarifications answered — now
## encodable)

The four answers (owner-confirmed):
1. RAMP CAP: 5% — the groundside-pavement class; no new constant
   family.
2. FORM PRECEDENCE: ramps FIRST; a declared wall/step is the FALLBACK
   only where the 5% cap cannot span the demand within the zone.
3. ZONE: bounded by adjacent buildings' frontage chords, the back
   apron edge, and standard clearance from every spine corridor; the
   fan radiates between adjacent buildings' seat levels along the back
   edge.
4. SCOPE: GENERAL law — every apron with building frontage; the HECA
   central U (between 05C/23C and 05L/23R) is the acceptance exemplar.

The law, composed with what already stands: aircraft-movement surfaces
(spine corridors + frontage chords + stand entries) hold the strict
apron cap, always; frontage chords run straight building→spine;
between frontages at the back edge, the fan-ramp zone carries up to 5%
continuous grade fanning between building seat levels; walls only as
the ruled fallback; no ramp, joint, or wall may touch any movement
surface (structural, via the corridor-cover machinery). The relief
TRIGGER is anchor-envelope infeasibility (4cbed92); the fan ramp is
the first-choice relief ANSWER in frontage-backed apron zones, ahead
of the terrace panel/wall answer which remains the form for
non-frontage aprons.

## 2026-08-05 — Compare-target fixtures PARKED until sim-verified green
## (owner)

Owner: no fixture comparison until builds are fully green AND
sim-verified; the fixtures are then RE-CUT before any new features.
The three standing compare-target reds ((d)-verdicted: vendored
2026-07-20, structurally stale) become explicit skips citing this
ruling — not red noise, not silently deleted. The re-cut is the
FIRST act of the next feature cycle, after the owner's sim pass.

## 2026-08-05 — Real DEM gated on flat-green (owner)

Owner: real-DEM builds happen ONLY when the high and low flat extremes
are FULLY GREEN — zero defects (version-deferred classes excluded per
d48bc0a). Any flat-world issue is addressed first; a real-DEM build
before that has no value. Consequences: no lane runs real-DEM
confirmation/regression builds as acceptance until flat-zero; the
recorded real-DEM reference frame stands as-is, un-refreshed, until
the gate opens; the FIRST real-DEM build after flat-green is the
reintroduction event, run deliberately through the harness.
