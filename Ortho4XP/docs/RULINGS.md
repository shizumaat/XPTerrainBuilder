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

## 2026-08-05 — Runway flex: the LAW is the only bound (owner)

Owner: follow the law regarding runway flex. The 4.0 m displacement
budget's origin is unclear (it was a prototype-era safety net); we
want to MINIMIZE flex, but anything within the law is legal by
definition — so ELIMINATE the budget.

Binding: RUNWAY_FLEX_MAX_DISPLACEMENT_M is DELETED (and budget_left
leaves the clamp chain — min(pull, slack) remains). The lawful bounds
are what they always were: CIFP pins (absolute, v1), runway grade caps
per segment incl. end zones (the priced slack), and the verify-relax
apply check. Minimization stays the OBJECTIVE via the flex's
minimum-move demand design (÷2 splits, drain-what's-demanded), never
via an arbitrary cap. Expected: closes the +7.011 m 05C/23C↔23R law
shortfall within lawful profile room. Lands in cycle 4 with the flat
oracle as acceptance.

## 2026-08-06 — Instrument truth is law (owner)

Approved after the falsified-premise chain (the law/ride classifier's
false "CIFP cannot reach" sentence, the "NOT budget exhaustion" exit
line falsified by the sweeps ladder, the stale 0.25 m grid-residual
excuse, the flat_ways way-level-tag mislabel, the certificate's 80.6%
catch-all): report-only code was exempt from the twin discipline, and
a lying instrument misroutes more work than a lying emitter — it had
the weaker law and the higher cost.

Binding:
1. KNOWN-ANSWER TWIN, or it is not an instrument. Every instrument
   carries a calibration twin feeding it a case whose answer is known
   and asserting the report (the models: the band-split fix verified
   10/10 hand-checked; surface-inertness proven by byte-identical
   body sha).
2. Instruments report NUMBERS AND FRAMES. A verdict sentence may be
   printed only by the law layer, or when it derives from a
   WORLD-INVARIANT computation (the CIFP-envelope split is the model).
   An interpretation embedded in report code is a defect.
3. FRAME STAMPS: every reported number carries its frame (tree sha,
   node space, world, crown space). Equating two numbers without
   matching stamps is the two-instruments trap by construction.
4. TWO INDEPENDENT INSTRUMENTS per load-bearing quantity, agreement
   asserted within materiality — the emitter/validator lockstep
   pattern extended to instruments.
5. The STANDING-INSTRUMENT SWEEP: every existing instrument is
   audited against 1-4 once, as its own round; an instrument that
   cannot be calibrated is retired, not trusted.

## 2026-08-06 — The low extreme is −500 m (owner)

Owner: to effectively exercise the intention of the extreme low DEM,
the low synthetic world is DEM ≡ −500 m — no particular need for zero,
negative is better. Supersedes the "DEM ≡ 0" letter of the constant-DEM
invariant; the 10,000 m high world stands. Below every CIFP value, so
floor-seating is guaranteed everywhere, and below-sea-level handling is
exercised for free. The DEM≡1 m interim was an unruled loader-guard
dodge and is RETIRED with the synthetic constant-DEM path; the low
frame re-mints at −500 at a cycle boundary.

## 2026-08-06 — Frontage coupling ⇒ band seating (owner)

Owner, on the detached-pad 2-cycle, verbatim intent: "A building close
enough to have frontage and be coupled with the apron has to be seated
based on the route graph that allows the apron to grade smoothly to
its frontage within the apron's grade law."

Binding:
1. A building coupled to airside by frontage — TOUCHING or NEAR-MISS —
   is seated FROM the route-graph band via its frontage chord: the
   seat is an in-band value such that the frontage chord grades within
   the apron's law; DEM chooses WHERE within that lawful range (seed,
   never bound). No DEM-datum value may be a bound on any
   frontage-coupled node.
2. Band-withholding keys on FRONTAGE COUPLING, not touch. Only a
   building with NO frontage coupling is a pure groundside citizen —
   seats at DEM, terraces freely, affects nothing airside.
3. The gap this closes is named for the future: the near-miss frontage
   law minted the constraint EDGE without extending the SEAT
   derivation — a law half-landed. A coupling law and its seating
   authority land TOGETHER henceforth (lockstep extends to seating).
4. The split-level sectioned-seat form remains the relief for large
   intra-footprint relief (unchanged).

## 2026-08-06 — ONE graph: groundside joins the route graph (owner)

Owner, verbatim intent: groundside pavement that is NOT a road grades
exactly like aprons, just with the higher cap; service roads are built
the same as taxiways with a higher cap; roads connect groundside
"aprons" (lots) and buildings at even higher caps than the smallest
taxiway — "it can all just be part of the one system." And: "Anything
truly disconnected, we don't really have to do anything at all — it
just gets left at DEM and doesn't need to be solved."

Binding:
1. ONE ROUTE GRAPH — no second groundside graph. Service roads are
   route edges (their 8% budgets), lots are groundside aprons (5%
   within-shape law), groundside buildings seat by frontage on the
   SAME band mechanism — identical machinery to size-dependent
   taxiway caps on airside. Every connected groundside node's
   feasible band derives from what its service-road routes can reach.
2. Constraint direction unchanged (airside-is-king; single-solve):
   the band flows airside → groundside through the connections;
   groundside is receiver-only, zero pull back.
3. TRULY DISCONNECTED geometry — no route, frontage, or weld coupling
   to the solved network — is NOT SOLVED: it stays at raw DEM by
   construction and mints nothing.
4. Supersedes: the "lot law enters the solve" item's open mechanism
   (this IS the mechanism); the lead's terrace-declaration candidate
   for D′ (REJECTED — one mechanism beats a parallel declaration
   form); and the KCLT canyon service-way spread class dissolves by
   construction (far ends seat in-band from their junction reach, not
   at raw DEM). Ground BETWEEN pavements still terraces freely
   (groundside terrace law unchanged).

## 2026-08-06 — Certificate routes follow the reach law (owner)

Owner, verbatim: "certificate routes follow the same law as reach —
centerlines and lawful surfaces, never through pad interiors, no
zero-budget hops. The route in the KML is invalid."

Context: the HECA specimen KML (anchors 2864↔7478, priced 33.377 m
over 149 edges) showed the conservative certificate's cap-graph
pricing a 586 m hop at budget 0 THROUGH a 40-node pad group, 24/149
edges under 0.9% of their chord, and 29/150 route nodes >100 m from
any taxi centerline. The owner adjudicated the route INVALID.

Binding:
1. ANY instrument or certificate that prices a route budget follows
   the SAME reach law production reach follows (2026-07-30:
   centerlines and lawful surfaces): never through a pad interior,
   never a zero-budget hop. A flat group is a SEATED SURFACE, not a
   free edge — entering and leaving it costs its lawful
   frontage/chord budgets.
2. The seam-pin "depth" class verdict is therefore (d) BROKEN
   INSTRUMENT: the 610-pin population's shortfalls re-adjudicate
   after the certificate reprices. The pins themselves are LAW
   (runway-surface values, CIFP-anchored, flex-moved) — untouched.
3. Riders for the instrument sweep: the class label `seed_rwy_seam`
   is a misnomer for 607/610 of its members (runway pass-2 values,
   not seam pins); and 444 of 1,077 nodes in the class were hardened
   with NO seeder record — an unattributed hardening channel.

## 2026-08-06 — Slab budgets floor at the law (owner; ratifies the fix-4 proposal)

Owner, verbatim: "smoothing beyond law as a constraint makes no
sense, that's the point of the law. Smoothest, minimum grade is the
target, but where needed, the budget is certainly the law."

Binding: interval/slab (rod-channel) budgets FLOOR at their pair's
grade-law budget — a slab may never price tighter than the law.
Smoothness (smoothest, minimum grade) is the OBJECTIVE the solve
optimizes toward, never a hard constraint beyond law. Context: the
rod/slab channel is the seam-continuity constraint plumbing that
SURVIVED the string parking (strings-the-feature remain parked; this
is the relative-displacement machinery that prevents seam tears);
c7cert measured 91.1% of its slabs tighter than law (median 5.26x,
max 2,305x), owning 31.5% of the converged residual. Repricing lands
with the seam-tear families as the counter-read.

## 2026-08-06 — Service-road mouths seat like apron-edge buildings (owner)

Owner, verbatim: "Airside always wins, and the one reachability graph
has to follow service roads to connect to any groundside pavement, so
the mouth of the service road has to function like an apron edge
building, seated where it's feasible for the airside apron to meet
it, then the road and everything else is graded per its law."

Binding (extends the ONE-graph ruling): the service-road MOUTH is the
airside↔groundside interface node — seated exactly like an apron-edge
building frontage: at a value where the airside apron lawfully meets
it within AIRSIDE law (airside wins the seat), after which the road
and everything downstream grades per its OWN law (8% road, 5% lot,
building frontage) from that seat. Reachability into groundside flows
only through mouths; direction stays receiver-only.

## 2026-08-06 — Instrument-truth point 4 SCOPED (owner)

Owner: resolve by scope. "LOAD-BEARING" in binding point 4 means a
quantity that GATES — it feeds adjudication, acceptance, or a verdict.
Those require two independent instruments with agreement asserted.
Pure EVIDENCE readers that share the one law code path stay
single-authority: for them the single-code-path law is the stronger
protection (the census-wrapper precedent). `band_excess` is compliant
as built.

## 2026-08-06 — The projection PARTITIONS (owner-ratified)

Owner: "Ratified, airside first." Promoted from the cycle-8 spec
addendum to owner law: EVERY projection partitions — airside projects
FIRST with groundside pairs excluded from its constraint set;
groundside projects AFTER against the frozen airside values.
Receiver-only holds structurally in every projection; a shared
projection IS a coupling (measured: +6/+5 airside rows from a
groundside seat). The reorder alternative (groundside seats after the
final projection) is FORBIDDEN as a mechanism — measured worse
(434→493). Landed in lane/c8fin; both Q4 debts cured by it.

## 2026-08-06 — No terrace joints across ANY road (owner)

Owner, verbatim: "trucks cannot drive over a vertical step, no
terraces in roads either." The terrace-r2 carried question is CLOSED:
service-road routes STAY in the joint no-cross set, and the principle
is general — a declared step/joint may never cross any ROAD of any
class. Roads are continuous graded surfaces at their own caps, exactly
like every route; terrace relief exists for non-route ground only.

## 2026-08-07 — Test-app release bar: ship now, named remainder (owner)

Owner (morning interview): the 2026-08-06 ~23:00 gate (HECA
adjudicated airside <100) is SUPERSEDED for this build. The Mac TEST
APP builds NOW from the green tip, with RELEASE_NOTES naming the four
remaining defect structures (pad-frontage chords / relief generation /
feature-weld hardening / on-DEM stranding) and the honest adjudicated
numbers (HECA airside 3,734 dem-500 / 4,006 canyon; battery 15,530
adjudicated + 12,320 deferred drainage_minimum). Scope: Mac test app
ONLY — make_engine + make_app + direct-exec smoke; no tag, no CI, no
Windows/Linux artifacts. AMENDED same morning (owner, verbatim: "I'll
build tiles myself, do not build tiles on release"): NO tile builds
are part of a release — the owner builds tiles in-app, which is also
the end-to-end engine test. The five-airport zero-adjudicated
CAMPAIGN GOAL is unchanged; this is a test build, not acceptance.

## 2026-08-07 — Item-4 (on-DEM airside stranding): evidence before ruling (owner)

Owner: no (a)-vs-(d) ruling yet. Deliverable first: a KML of the
on-DEM airside vertices with per-vertex COUPLING CLASSIFICATION
(route edge / frontage / weld / none) plus a written dossier (counts
per class, worst-10 table, per-class (a)-vs-(d) implication). The
ruling follows the evidence review. No fix work on this class until
the sentence lands.

EVIDENCE LANDED same day (Ortho4XP/tmp/item4_evidence/, frame c9air
fix1 e9620ff4, twinned against the lane's recorded census): the
retrospective's "140 vertices / 89 rows" were instrument-frame
artifacts (140 = a way-INCIDENCE count under the geom_guard
partition, labelled hypothesis; 89 irreproducible from any surviving
artifact — 2-attempt cap). True law-partition population: 620 (−500)
/ 88 (10k) airside-role on-DEM vertices; ≥10 m adjudicated airside
rows 48 / 53. Coupling: route-edge 0, frontage 0, WELD carries 100%
of the defect mass (identity welds on adjacent_ground band rings; 29
minting vertices), uncoupled = 512 wall-feet minting ZERO rows. The
ONE-graph point-3 "truly disconnected" class is EMPTY both worlds.
48/48 −500 rows: on-DEM endpoint sits ON a retaining_wall way;
47/48 the law-valued partner does not — the wall-spanned exemption
misses one-sided boundaries. The owner's question is therefore NOT
coupling but: may the adjacent-ground band's outer edge / wall-foot
node take the DEM value ((d): extend the wall exemption one-sided),
or must every welded node of a law-valued ring seat from its ring
((a): missing seat)?

## 2026-08-07 — Service routes are taxiways at a larger cap; EDGES MUST BIND (owner)

Owner, verbatim: "Service routes should function identically to
taxiways, just with a larger grade cap, so I think edges absolutely
matter in relation to their spine. Groundside buildings and parking
areas connected via service roads should be seated based on their
feasible band which follows the service route path back to airside."

Binding: ONE-graph point 1's mechanism is affirmed LITERALLY — the
feasible band propagates ALONG service route edges from the
airside-determined mouth seat, and groundside buildings/lots seat
from that route-following band. K1's measured edges-inert state
(byte-identical patch with every service edge withheld) is therefore
a DEFECT, not a lawful simplification. Recorded suspect (cycle-8's
own measurement, HANDOVER §0): service stringing fires 4/389
segments at SPJC — sliced-road nodes at edges vs the 1.0 m perp
tolerance. Spec: service-band-propagation-spec.md.

PREMISE CORRECTED same day (lane fa31d21, interventional): K1 was a
BROKEN KNIFE — the probe rebound a local name while
`groundside_route_band` rode `G.spine_adj` untouched, so the
"edges-inert" evidence underlying this entry was an instrument
artifact. With the repaired knife the edges BIND today: withholding
them moves +377 groundside rows with airside byte-identical
(receiver-only direction verified; banded nodes 8,283→8,048 by two
independent instruments). The ruling's INTENT is affirmed AND
already implemented; the defect reading is WITHDRAWN. The real gap
is COVERAGE, re-scoped from measurement: at HECA 30.8% of road
metres have NO graph node within ~29 m (road geometry that never
reaches the graph), 21.7% no candidate within tolerance (nearest
eligible node median 17.2 m); 28.1% is the free-road ruling working
(lawful apron remainder); a tolerance bump buys only 10/705 lines.
Whether full-coverage banding (seeding graph nodes along unreached
road geometry) is wanted is an OPEN OWNER SCOPE QUESTION — the
cycle-8 "4/389" figure was a pre-road-feed denominator and is
superseded.

## 2026-08-07 — Mouths are the boundary arbiter; the K2 coupling is lawful (owner)

Owner, verbatim: "Why would we remove mouths? Are they not necessary
to arbitrate the boundary between airside and groundside? Yes, the
airside determines what the mouth seat can be, which then impacts
the feasible band for the route through the service network."

Binding: mouths stay — they arbitrate the airside/groundside
boundary. K2's +134 airside movement when mouths are knifed out is
airside law expressing itself (the mouth seat is an airside act per
the 2026-08-06 mouths ruling), not a forbidden groundside pull. The
K2 gate remains a probe instrument only; no production form ever
ships without mouths.

## 2026-08-07 — Retaining walls emit ONLY at carve structures (owner)

Owner, verbatim: "I can't think of a reason we need to emit
retaining walls except around tunnels." Ruled via interview the same
hour:
1. Walls are lawful ONLY at tunnel/bridge carve structures (portals,
   abutments — the Feature A / below-grade-cutout class). Every
   other emitted retaining wall retires.
2. The replacement form everywhere is FEATHER: graded transitions
   under grade caps, NO explicit relief feature. Where ground must
   change height it grades; tight spots get steep slopes, never
   walls (no tight-spot exception).
3. The adjacent-ground zone's outer boundary FEATHERS INTO RAW DEM —
   the boundary-step class dies BY CONSTRUCTION, and with it most of
   the `wall_foot_ll` population; the item-4 exemption machinery
   stays until that population measures ~zero, then retires.

Execution vehicle (owner choice): the RELIEF-GENERATION ROUND
(retrospective structure #2) — one generator change, one battery
re-read; no separate wall-removal pass. SUPERSEDES/AMENDS: the
groundside terrace law's "(retaining walls)" parenthetical (free
terracing becomes free FEATHERING); the adjacent-ground
"boundary steps are lawful terraces" reading (they feather instead).
Consequences noted same day: the no-joints-across-roads ruling is
mostly mooted outside carves (no joints anywhere); pad-frontage
structure #1's form menu loses its STEP/WALL branch — every frontage
chord grades under the relief form (that round simplifies);
nidrepair's A2 wall-weld identity repair proceeds unchanged (it
repairs what is currently emitted; walls retire via the relief
round, not by leaving them broken meanwhile).

## 2026-08-07 — Airside-surrounded enclaves: G-ENCLAVE extends to ground (owner)

Owner, on the HECA retaining wall at 30.128508, 31.403444 (an area
surrounded by airside apron): "I thought we had standing law that
something completely surrounded by airside pavement could never be
groundside?" CONFIRMED — G-ENCLAVE, owner 2026-07-28
(pavement-scoring-classifier-spec §7): "groundside can never be
surrounded by airside pavement unless it has a tunnel or bridge
service road to get out." CLARIFIED today: the principle covers
EVERYTHING inside an airside-surrounded enclave, paved or bare —
such an area is airside-interior and takes the GAP INTERIOR RING +
SPINE treatment (owner: "should be treated accordingly with a gap
interior ring and spine"); a retaining wall or groundside terrace
there is a defect regardless of which mechanism minted it. The named
specimen is under attribution (did G-ENCLAVE fail to fire, or does
bare ground fall outside its pavement-shape scope — a law gap).
RIDER: a `wall_foot_ll` exemption resting on a wall of this class is
VOID once the wall is reclassified — re-census after the fix.

RULED same day (owner, PROVISIONAL — verbatim "I'm not sure, try
d"): **(d)**. The wall-foot node on the adjacent-ground band's outer
edge may take the raw DEM value; the wall-spanned tear exemption
extends to ONE-SIDED boundaries (the on-DEM endpoint must be
wall-hosted; the law-valued partner need not be). Structural
predicate only — no magnitude cap (step size is a flat-world
artifact by construction). Pure adjudication-side change: patches do
not move. Provisional: revisit at the sim pass. Spec:
adjacent-ground-wall-foot-exemption-spec.md.

## 2026-08-07 — Round order ratified; c9feed probe runs parallel (owner)

Owner ratifies the retrospective's order: (1) pad-frontage round
(~1,870 rows; spec decides per-frontage which ruled form — relief vs
step/wall), (2) relief-generation round scoped WITH the deferred
drainage project (same generator), (3) feature-weld hardening round.
Cycle-10's FIRST measurement — the confounded graph-edge probe,
re-run cleanly on b6936ed — proceeds in parallel (2026-07-31
concurrent-correctness-builds ruling applies).

## 2026-08-07 — Standing approvals granted / withheld (owner)

GRANTED: (a) delete the 529 junk DSF-cache dirs (same class as the
earlier ledgered 535; ledger the deletion; executed by the LEAD, never
delegated — destructive-op rule); (b) retire the default-OFF
O4_SVC_CURVED_JUNCTION experiment outright (the open call from STATUS
20260731d). WITHHELD: timing-baseline re-record — stays deferred to
the final-design profiling round; spurious REGRESSION rows remain
expected until then.

## 2026-08-07 — Tunnel portal fidelity: four rulings (owner, OTHH)

Context: the OTHH six-site tunnel investigation (attribution: memory
`othh-tunnel-emitter-attribution`; every real tunnel is OSM-mapped and
already in the cached corpus; the object classifier cannot fire on the
pack — zero ATTR_hard pack-wide). Owner ruled all four, verbatim
"1. Yes 2. Yes 3. Yes 4. Tunnel ramp should win over pavement":

1. **Mapped ends are preserved unconditionally.** Re-splitting a MAPPED
   `tunnel=yes` bore at pavement crossings must never move a portal
   inside the mapped extent: the 100 m mapped-end preservation
   threshold becomes unconditional for `_had_tunnel` ways. (OTHH: a
   62 m mouth-to-apron stretch fell under the threshold, planting the
   portal 61 m inside the bore and digging a −4 m pit at the mouth.)
2. **Mapped-bore interiors are roofed by definition.** The low-connector
   open-cut test excludes `_had_tunnel` stretches — an interior gap of
   a mapped bore is never dug open, whatever its length. (OTHH C2 and
   the second connector, way -11728.)
3. **Corridor cut clearance joins the 0.6 m standard.** The low-corridor
   airside cutback must clear the SHARED_VERTEX_TOL_M intern bucket
   like every other tunnel emitter (0.5 → 0.6 m; the −5.16/+3.19
   needle).
4. **Tunnel ramp wins over pavement.** At a mapped portal the ramp CUTS
   the pavement it surfaces through (the R13 `cuts_pavement` spirit);
   the fractional ≥50% pavement-overlap drop and graze clip no longer
   remove tunnel ramps, and walls follow their ramp. Spec-level safety
   floor (flagged to owner, not yet separately ratified): a ramp never
   cuts a runway-family shape — such an overlap drops the ramp piece
   loudly instead.

Spec: `docs/specs/tunnel-portal-fidelity-spec.md` (this session).

## 2026-08-07 — Mouth-fed banding is sufficient; road feed merges as-is (owner)

Owner, verbatim: "Mouth-fed banding that reaches should be
sufficient." The full-coverage scope question is CLOSED: no round
seeds graph nodes along road geometry that never reaches the graph;
the free-road apron remainder and the out-of-reach 30.8% of road
metres are lawful non-participants. And: "Merge as-is" — the road
feed (lane/c9feed, receiver-only default, edges verified binding,
mouths arbitrating) merges at its attributed table: HECA 10k airside
4,198 (+192 vs base) / −500 4,027 (−102). The +192 is accepted as
named law expression (mouth seating + threshold effects of the
universal band displacement on four aprons).

## 2026-08-07 — Materiality floor: 0.5 m accumulated, guarded, runways exempt (owner)

Owner: "when I was building osm patch files by hand I never set an
elevation in increments smaller than 1 meter… we don't want any
sharp bumps, but we don't need to be grading to less than 0.5m."
Interview rulings: (1) ADJUDICATION-ONLY first — a defect SITE is
actionable only if its unlawful excess accumulates ≥ 0.5 m; law and
generation unchanged; solver-target relaxation deferred to the
final profiling round; output value-quantization REJECTED (the
dense-node staircase trap — hand files were smooth at 1 m increments
because they were SPARSE). (2) SHARP GUARD: below the floor, any
single step ≥ 0.15 m OR local grade ≥ 2× its cap stays actionable.
(3) RUNWAY-FAMILY surfaces EXEMPT — reg-derived precision governs
there. (4) DECIMATION: measure first (% nodes dropped + mesh/DSF at
0.1/0.25/0.5 m vertical tolerance) before any constant lands.
Spec: materiality-floor-spec.md.

## 2026-08-07 — Role-less feature ways side with their host (lead, nidfix2 escalation (a))

Feature ways carrying no role (shape_interior_ring 92,
gap_interior_ring 88, gap_drainage_spine 49, crown_spine 3) are
ARTICULATION geometry, not surfaces: they take the ROLE AND SIDE of
their HOST shape and are judged at the host's cap; where their
geometry duplicates a host way's, rows belong to the HOST ONLY —
one geometry, one row set; never airside-default at 1.5%, never a
double-count. Instrument-side; folds into the materiality-floor lane.

## 2026-08-07 — Exposing a pre-existing defect never fails the bar (lead, nidfix2 escalation (b))

The zero-new-adjudicated-airside bar targets NEW SURFACE defects. A
repair that makes a pre-existing defect legible — surface proven
inert (0 nodes moved ≥ 0.01 m) — has MET the bar; the newly-legible
rows join the population they always belonged to (here the item-4
on-DEM stranding class). nidfix2's +2/+15 adjudicated MET on
substance.

## 2026-08-07 — Site census is the headline metric; transitive clustering ratified (lead)

census --sites becomes the campaign scoreboard: battery 15,530
adjudicated rows = 778 SITES (20.0 rows/site; top 5 sites carry
50.8%, top 10 65.6%; only 18 adjudicated sites sub-visible at 5 cm).
The transitive weld-join reading (a welded apron complex is ONE
site) is RATIFIED — that is the "one over-cap region" the metric
exists to count; n_ways/extent ride every site for the finer read.

## 2026-08-07 — Ramp-cut boundaries: walls, grades, buildings (owner)

Follow-up rulings on the tunnel-portal-fidelity acceptance findings
(matched-control census: +665 adjudicated at the new ramp/pavement cut
boundaries; 25 tunnel_ramp within-shape rows at 4.9-40.4% vs the 4%
cap; building pad `building1` ring welded to [−3.74, 2.34]):

1. **The tunnel machinery walls its own cut** (owner "Agreed"): where a
   ramp cuts pavement under ruling 4, the cut edge gets retaining-wall
   faces from the TUNNEL emitter (today the adjacent-ground machinery
   improvises retreat walls there, 5 → 63), and wall-hosted ramp-cut
   steps are LAWFUL — the wall-exemption class — subject to the
   attribution pass confirming that is what the +665 rows are.
2. **Over-cap ramp grades: trace and fix** (owner verbatim "Yes, trace
   and fix") — attribution before fix; the 3.5 % plan is lawful, so the
   4.9-40.4 % rows were minted somewhere downstream.
3. **Buildings** (owner verbatim): "A ramp should never cross a
   building pad edge. Either the tunnel is under the building and the
   ramp stops at the building edge, or the building is mis-identified
   and shouldn't be there in the first place." Engine consequence:
   building pads are neither cut nor buried — the emitted open ramp
   CLIPS at the building pad edge; the below-grade continuation under
   the pad is covered bore (not emitted); the portal face stands at the
   building edge. A mis-identified building is a data-quality case,
   never an emitter workaround.

## 2026-08-07 — A-site walk-crossing residual: ACCEPT AND PARK (owner)

The 20 over-cap `tunnel_ramp` rows at OTHH's A-site twin-walk cluster
(+1 actionable site, 83 vs control 82) are ACCEPTED AND PARKED (owner
verbatim "Accept and park"). Two falsified hypotheses are recorded in
`docs/specs/tunnel-fork-sustain-spec.md` (OUTCOME); the located
mechanism — two lawfully-separated portal walks whose paths meet
(93.89 m² overlap, 6 shared nodes) — awaits a reverse-Y-join round
when re-armed. Also parked: the `-11318` `object_bridge_ramp` 4.68 %
pair (different emitter) and the fork-threshold frame-mismatch class
(real, specimen at cluster (295, −2490), not load-bearing at OTHH).

## 2026-08-08 — Enclave −500 +96 accepted per the threshold-class precedent (owner)

Owner, verbatim: "Accept and merge." The enclave round's HECA −500
adjudicated airside +96 — located OUTSIDE keep-out territory,
concentrated on one band site, with the REAL world improving (−5)
and SPJC improving (−2) — is accepted as the flat-world
threshold-crossing class the owner first accepted at the road-feed
merge (lawful value perturbation × oracle-world threshold density).
Rider: site -12976 (30.105897, 31.407168; 3.0-3.6 m steps) gets a
read in the next census pass, not a block. Merged as 0d38040.

## 2026-08-08 — Apron welds to building frontage; the seat IS the weld (owner)

Owner, verbatim: "there can't be a gap between a building pad and an
apron, so the apron pavement should be welded to the building,
buildings fronting apron need to be smooth right up to the building
at apron grade, no steps, no feather into an apron. Two pad feathers
meet in the middle." And: "Building-frontage to me means frontage to
an apron, which means apron cap." And: "If the apron simply welds to
the building frontage, we shouldn't need any other solve
integration."

Binding:
1. A building FRONTING an apron has NO independent seat authority:
   the apron pavement extends/welds to the building face and the
   building seats AT the welded apron value. Apron cap governs the
   whole surface to the face. No steps, no feather, no transition
   zone on the apron side. Any band-derived seat that disagrees with
   the welded frontage value is a DEFECT of the seat mechanism, not
   a pricing gap — for fronting buildings the independent seat
   RETIRES (seat := welded frontage value).
2. DETACHED pads (no apron frontage) keep the service-route band
   seat (ONE-graph law); the ground around them FEATHERS (walls
   ruling); where two pads' feathers approach, they meet in the
   middle.
3. No new solve integration for the fronting case — the apron's own
   law prices everything up to the face (the frontage strip joins
   the apron's within-shape population; movement there is lawful and
   reported). frontage_near_miss self-retires for fronting buildings
   (seat == edge by construction).
This SUPERSEDES the retrospective structure-#1 framing ("price the
chord"): for fronting buildings there is no chord; the detached
remainder folds into the relief/feather round.

## 2026-08-08 — Frontage weld: measured ALREADY-TRUE; retirement parked (lead ruling on the frontweld STOP)

Job-1 measurement on the current tip: the seat-vs-weld disagreement
population is ZERO (79 fronting pads at HECA, |seat − welded face|
max 0.200 m, mean 0.0027 m — pad ring vertices ARE apron ring
vertices at emit). The owner's "we have been welding aprons to pads
smoothly for a long time" is measured true; the 7.42 m retrospective
specimen does not exist on this tree. The 1,373-row fronting class
is the APRON'S OWN RELIEF (apron -10447: 11 m over 600-790 m at
1.4-2.0% vs the 1.0% cap) touching pad vertices — retrospective
structure #2 (relief generation), REASSIGNED to the relief round's
charter. RULED: the code retirement (seed-not-hard + no assert-back)
is PARKED in lane/frontweld 2d2a8e7 (kept, not merged) — it fixes a
zero population at +67 REAL-WORLD airside on the one un-gradeable
apron, and the flat-world threshold precedent does NOT cover real
DEM. It re-lands for re-measurement AFTER the relief round makes
-10447 gradeable (expected cost then ~0). The AUTHORITY LAW STANDS
as the adjudication rule: any future band-vs-weld disagreement is a
band-computation defect (the three emitted law twins document
today's honest exposures as xfail: 0.200 m seat-vs-face, 0.800 m
ring spread, 60 near-miss — all XPASS at CYXY). CYXY hillside group
(owner's named sim case): all fronting, seats == welded values up
the slope (702.80→706.29 m), Δ0 rows — the design already handles
sloped groups on real DEM.

## 2026-08-08 — THE FABRIC MODEL (owner; supersedes "relief generation")

Owner, verbatim: "we have a base 'fabric' we're essentially
deforming, there's no need to 'generate relief'… We simply need to
grade our pavement and building pads, and Ortho4XP will
automatically blend the surrounding terrain. We only add our
adjacent ground and drainage areas to ensure FAA regulations, but
for unregulated areas I believe the answer is to do nothing. I don't
think we even need to grade apron fans." The two thought experiments
(two squares in three worlds; the sparse apron with three welded
buildings and no intermediate back-edge nodes) are recorded in
fabric-model-spec.md as the canonical design articulation.

Interview scope, same exchange:
1. Fan zones RETIRE OUTRIGHT (they compensated for dense emission).
2. Explicit shaping = runway strips + drainage + RESA/OFZ (per the
   standards enumeration; region-keyed per the rulesets ruling).
3. Interior node floor = LAW VERTICES ONLY (seats, welds, mouths,
   boundary direction changes, reg features), owner rider: "as long
   as we keep adequate nodes on spines and at curves."
4. Bands/graded surrounds survive in the REG SET ONLY, owner rider:
   "that should include drainage requirements along all taxiways."
   Unregulated ground: NOTHING — the drape is the feather.

SUPERSEDES the relief-generation framing (retrospective structure
#2). The capacity-deficit argument is falsified by the fp#8 ladder
(pure law satisfiable at HECA: 742 rows @ 0.08 m). Acceptance pair:
apron -10447 (11 m / 790 m / 1% cap) and the CYXY hillside group.

## 2026-08-08 — Reg-set rulings (owner, on the Phase-0 enumeration's questions)

On fabric-model-reg-set.md §6, questions 1-4:
1. **Graded-strip mandatory-DOWN (FAA-only 1.5% min): the ICAO
   ruleset DROPS it, flagged PROVISIONAL** — revisit at the owner's
   sim look at a strip without the band. Strip bands stop being
   emitted at SPJC/SPLP/CYXY/HECA; KCLT keeps the FAA form.
2. **All-taxiway drainage where ICAO gives no number: a named house
   constant, PROVISIONAL** — the FAA 1.0% transverse minimum adopted
   as the ICAO-ruleset default satisfying "sufficient to prevent
   accumulation", labeled PROVISIONAL with the ICAO text quoted in
   the ruleset entry.
3. **RESA: fix both per source.** ICAO: strip-end datum, 90 m shall
   vs 240 m should handled as mandate-vs-recommendation; FAA: the
   Appendix G length-beyond-end column is a BUILD item requiring the
   primary text (fetch currently blocked — the owner can supply the
   AC 150/5300-13B PDF manually for primary verification).
4. **Apron shoulder / beyond-shoulder / apron-edge-wall families:
   RETIRE OUTRIGHT.** Nothing mandates them; the drape takes apron
   surroundings on both rulesets.
Question 5 (105 m precision-approach graded strip, guidance not
specification) remains OPEN with the owner.

## 2026-08-08 — 105 m precision-approach graded strip: ADOPTED (owner; reg-set Q5)

Owner: "Follow the guidance 105m graded strip half width for
precision approach runways." The Annex 14 §3.4.8 Note / EASA GM
figure guidance is adopted as law in BOTH rulesets: precision-
approach runways grade the strip to a 105 m half-width. Recorded as
guidance-adopted-as-law (the one deliberate exceedance of bare
specification in the fabric model's reg set).

## 2026-08-08 — 105 m precision strip DROPPED (owner; supersedes the same-day adoption)

Owner, on learning the 105 m has no FAA anchor: "If there's no FAA
citation for the 105 m precision strip, we can drop it as well." The
guidance adoption is REVERSED on both rulesets: specification values
only. The Annex 14 §3.4.8 Note remains recorded in the reg-set table
as unadopted guidance. Consistent with rulings 1 and 4 of the same
day: shape nothing the specification does not mandate.

## 2026-08-08 — Acceptance fixtures re-scope to the ruled bar (owner)

Owner: "Re-scope group 1." The eight zero-defect acceptance fixtures
(the five per-airport pavement-grade fixtures, the two runway
longitudinal-grade fixtures, and the runway seam DEM-step fixture)
re-scope from raw adjudicated-zero to THE RULED BAR: zero ACTIONABLE
SITES under the 2026-08-07 materiality floor (0.5 m accumulation,
sharp-step and steepness guards, runway-family floor-exempt). A
fixture asserting a superseded bar is the same defect class as an
instrument measuring a superseded frame. Execution: the POST-BATTERY
CLEANUP lane — the owner also folds the CYXY solver-validator
edge-budget lockstep unification there (the "floor > ceiling by
0.0112 m" single-mechanism red).

## 2026-08-08 — Mesh-only entry arms THE shared-repo guard; inset manifests are corpus state, not churn (lead session, applying owner ruling e9daef5)

Measured 2026-08-08 (lane fabricB): two `tools/run_tile_mesh_only.py`
runs (+30+031, -13-078) silently rewrote five files in the shared data
repo — airport-inset `index.json`/`complete.json` manifests and a
bathymetry-band `index.json` — while all 13 guarded `build_airport.py`
runs in the same session reported the repo UNCHANGED.  The silent
side-effect class e9daef5 forbids (the KCLT road-feed precedent).

Ruled: (1) the shared-repo write guard is factored to ONE
implementation, `tools/harness/shared_repo_guard.py`;
`build_airport.py` re-exports it and `run_tile_mesh_only.py` arms it
(census-wrapper precedent: a second copy is a defect).  (2) Inset
manifests get NO churn allowance: unlike the `.lock` and library-index
classes they are fetch-admission state (`is_cached`) whose content
depends on tile config, calendar date and fetch outcomes — a content
change is a corpus mutation and rides `--refresh-data dem`.  (3) The
root cause is fixed engine-side: `_write_index` and
`_write_inset_completion_stamp` skip byte-identical rewrites (the
discipline `O4_Bathymetry_Band` already had), so a warm settled pass
writes NOTHING and needs no allowance.  (4) New
`O4_Bathymetry_Band.join_prefetches()` keeps the band prefetch inside a
steps-1-2 caller's guard window — the measured S13W078 band write
landed after "mesh build complete".

## 2026-08-07 — Shared-repo guard scope: lock files are coordination state; a swallowed DEM prep failure refuses (round delegation; provisional pending owner merge)

From the sliver-attribution round's defect (tmp/sliver_attrib
dossier §5): under the armed shared-repo write guard,
`build_airport.py HECA --patch-only` had its production-parity DEM
prep blocked on the elevation provider's `.lock` file;
`auto_patch.elevation._load_airport_dem`'s single `except
Exception` turned the refusal into a WARN line and the build exited
0 on a silently smaller layout (18.5 k nodes vs production's
34-36 k; retaining_wall / ols_cut / crown_spine / gap_interior_ring
absent; `dem_inset_provenance: null`).

RULED (landed lane/demfix 225fad3, instrument-side only):

1. GUARD SCOPE. A `.lock` sibling inside the shared corpus is
   COORDINATION STATE, never corpus data: the guard allows exactly
   the two calls the engine's lock primitive
   (`O4_File_Lock.hold_file_lock`) makes on one — the exclusive
   `os.open` create and the `os.remove`/`os.unlink` release — and
   nothing else. Any other operation on a `.lock` path and every
   real data write beside it still refuse. Allowed lock operations
   are RECORDED (`write_guard_lock_churn` in `<tag>.result.json` /
   `<tag>.frame.json`); a lock file in the after-snapshot is named
   churn, never contamination.

2. SWALLOWED DEGRADATION. A refusal the build catches is not a
   refusal: a build during which the guard blocked any write, or
   whose layout carries no DEM provenance at all, REFUSES before
   the patch is written (both detectors in `build_patch`, so
   oracle.py and who_wrote.py inherit; `--tile` runs detector 1 in
   main). `--allow-degraded-dem` proceeds knowingly, is recorded in
   frame.json, and authorises NO write. `--refresh-data` remains
   the only act that changes the corpus, and is never required
   merely to run a patch-only build on the shared corpus.

Twins: tests/test_harness.py section 6b (12 new; suite 117).
Provisional until the owner merges lane/demfix (READY-TO-MERGE in
the HANDOVER queue).

## 2026-08-09 — Reseat threshold; terrain-first at flat airports; the basin experiment (owner)

Owner, verbatim (three statements, one session):

1. "When it's less than a meter deviation, adapt the terrain to the
   custom objects, rather than reseating the objects. We prefer not to
   modify an airport if we don't have to. If it has objects that
   deviate more than a meter, then we will need to reseat them."
2. "For the record, KBNA and KCLT are in hilly terrain, not flat,
   while OTHH is very flat. Ideally OTHH would be able to be fully
   terrain adapted with no object reseating, we should be able to
   simply cut out the drainage areas and set the ground level terrain
   at the right elevation so no reseating is required."
3. (on the six drainage facilities whose placement anchor sits inside
   their own open pit, after the lead surfaced that a draped object's
   seat IS the terrain at its anchor) "If the object placement is in
   the middle, maybe it's tied to the bottom of the object, so placing
   it at the bottom of the trench will already seat the top at the
   ground level? Let's try cutting the trench, but don't modify the
   objects so I can see how it looks."

Binding consequences:
1. THE 1 m LAW: a seating unit bakes only at max |delta| ≥
   `DSF_OBJECT_BAKE_MIN_DELTA_M` (1.0); below it the pack is never
   modified and terrain adapts (pad requests → the §5 pad consumer).
   Spec: docs/specs/object-reseat-threshold-spec.md.
2. TERRAIN-CLASS FACTS (correct the flat-KCLT misreading of the
   seating spec's ground-contact numbers): KBNA/KCLT hilly — their
   ≥ 1 m units keep reseating; OTHH very flat — expected to approach
   ZERO pack modification.
3. THE BASIN EXPERIMENT runs before any basin reseating: trench cut
   fully open (no anchor seat), objects untouched, owner views
   in-sim. The measured prediction (placement origin is the RIM;
   draped rims sink ~4.3/13.5 m) is on record; the sim adjudicates.
   Spec: docs/specs/basin-rim-flush-seating-spec.md (v2, §2.2
   deferred).
4. OSM terminal ways are the identity of their buildings (the
   2026-08-09 bug report's third item): docs/specs/
   osm-terminal-way-authority-spec.md (v2: kept ways clip surviving
   clusters).
5. IN-SIM VERDICT (owner, 2026-08-09, build 1.0.226): anchor-outside
   basin facilities seat "just right"; anchor-inside facilities sink
   to their trench floor — the basin experiment's predicted split.
   Consequences: basin spec §2.2 rim-flush reseat ACTIVATED for the
   anchor-inside class only; and object pads must HUG footprints —
   the convex-hull request ring is retired
   (object-reseat-threshold-spec §2.5): a pad spanning water or
   parking lots between objects is a defect, not a request.

## 2026-08-09 — PRE-SHIP DEVELOPMENT MODE (owner)

Owner, verbatim: "we have not released this app yet, it's still in
the initial implementation phase, so I want to streamline the
standard development cycle until we officially ship our first
version. The priority is definitely identifying root cause, good
design and spec, but then implement and build so I can verify in-sim
rather than exhaustive, time consuming and expensive token
consumption on something we're not even sure will deliver the
results we want."

KEPT — non-negotiable even in this mode (each is structural or
near-free, and each earned its keep on 2026-08-09 alone):
1. Root cause before fix; Fable-authored specs; this RULINGS canon.
2. The shared-repo write guard, the harness build entries, and the
   lane ritual — corpus protection is structural, not verification.
3. No test or agent ever writes the real X-Plane install (the
   2026-08-09 sandbox-escape incident class).
4. Unit tests FOR THE CHANGED BEHAVIOR, written with the change and
   run ONCE at land time.
5. Convergence guards (attempt cap 2, materiality floor) — they cap
   spend, they do not add it.

SUSPENDED until the first official release:
1. Per-edit blast-radius suite runs, full-suite passes, and
   matched-control worktree arms. Instead: run only the test files
   directly covering the change, once; consult the recorded
   known-pre-existing-failures list (12 campaign failures as of
   2026-08-09) instead of building control arms.
2. Per-lane acceptance builds, censuses, battery-inertness proofs,
   and lead-side re-verification layers (IoU/row-diff sweeps).
   THE OWNER'S IN-SIM PASS IS ACCEPTANCE. At most ONE patch-level
   build per integration round, only when the lead judges the change
   could reach the sim visibly broken.
3. Long agent final reports — cap: what changed, tests run,
   deviations.
4. Multi-lane parallel decomposition of one coupled change-set —
   default ONE implementer per change-set; parallel lanes only for
   genuinely disjoint files under time pressure.
5. Per-change build-time statements (already suspended for the
   campaign) stay suspended.

THE LEDGER AND THE SHIP GATE: every streamlined land appends one
line to `docs/DEFERRED_VERIFICATION.md` (change, what was skipped).
Before the first official release, ONE hardening round pays the
whole ledger — full suite green, battery A/B + censuses, timing
profile, the absolute-zero acceptance gate. Nothing on the ledger is
ever silently dropped; a direction the sim kills takes its ledger
lines with it, unpaid.

THE STANDARD CYCLE in this mode: owner report → root cause (recon
only as needed) → spec (Fable) → ONE Opus implementer (tight brief:
files, law, its own tests, run-once) → lead merges, freezes engine,
packages app → owner verifies in-sim. Target: a small fix reaches a
testable app well inside an hour.

## 2026-08-09 — Flat-site detector v3 (owner approved the lead's recommendation)

Three parts, all in force (spec v3, flat-site-detector-spec.md):
(a) gate statistics on the PAVEMENT ∪ BOUNDARY extent only — the
margin ring is report-only (surrounding hills have no standing to
veto a flat strip; VMMC is the type case); (b) tail-robust S2 —
DSM building roofs must not testify (defined trim above
median + floor/2, recorded fraction; acceptance = the owner's six
all flat, every S1-failing negative still refused, miss ⇒ STOP with
distributions); (c) per-airport OWNER DECLARATION tile-cfg keys
(`flat_site_declared`, `flat_site_declared_elevation_m`) with
verdict `flat_declared`, the automatic verdict recorded beside it.

## 2026-08-09 — Flat-site S1 spread and the flat test set (owner)

Owner: "CIFP threshold spread < 5m should be a flat candidate" —
`FLAT_SITE_THRESHOLD_SPREAD_M` = 5.0 (the 0.5 was the lead's
provisional value). And the flat-airport test set gains VHHH, VMMC,
YSSY, KSFO, KOAK, KBOS (owner-named; expected flat candidates —
refusals are findings, never silent). Phase-2 corollary: with
nonzero spread the runways keep their CIFP-absolute profiles; the
flat elevation applies off-runway.

## 2026-08-10 — Apron hard gates (owner)

Two classification rulings, owner verbatim, on the OTHH in-sim round
(spec `docs/specs/round4-othh-fixes-spec.md`, R3):

* "Pavement touching a runway cannot be apron"
* "the entire shape narrower than a taxiway cannot be apron"

Both are HARD GATES in scorer v2 (`pavement_scoring.score_shape`):
`G-RUNWAY-CONTACT` removes APRON from a candidate whose own ring
shares ≥ 1 m — or ≥ 10 % of its own perimeter — with the runway ring
within 0.5 m; `G-APRON-WIDTH` removes APRON from a candidate that
vanishes under a 2.0 m erosion. Gates remove candidates, so a gated
shape falls to junction/taxiway under the existing enactment. The
legacy near-runway apron rule said the first of these and is dead
under v2 (`pipeline` gates it behind `_scorer_owns_roles`) — the gate
is its v2 rebirth. Measured specimens, owner build 1.0.229 (OTHH):
sid102 (376 m², 51 % of its perimeter on the runway) for the first;
sid105 (4.1 m OBB width) and sid104 (2.4 m) for the second.

## 2026-08-11 — Harness builds redirect the engine's derived-cache roots lane-local (lead session, applying owner ruling e9daef5)

Measured: the round-9 KCLT acceptance build — guard armed — still wrote
`Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text` into the
shared repo: the DSFTool SUBPROCESS writes its dump directly, which no
Python-level write guard can intercept, and only the post-build snapshot
caught it (run flagged CONTAMINATED, on the deferred-verification
ledger). The pytest suite closed this class on 2026-08-08 with
env-overridden lane-local cache roots; the harness build entry now arms
the SAME mechanism: every `build_patch` and `--tile` run points
`O4_DSF_CACHE_DIR` and `O4_AIRPORT_MOD_CACHE_DIR` at per-run dirs under
`<out>/<tag>.engine_caches/`, the mod-cache root as a symlink-seeded
read-through overlay (warm reads, lane-local writes; the overlay's pure
core, `mirror_tree_as_symlinks`, moved into `shared_repo_guard.py` — one
implementation, conftest delegates). A scope the run is AUTHORISED to
refresh (`--refresh-data airport_mod_cache` / `dsf_cache`) is NOT
redirected — an authorised refresh must land in the shared repo, and a
redirect there would turn it into a silent no-op. Corollary: a cold
derived cache no longer needs `--allow-degraded-dem` to build (the
rewrite lands lane-local instead of being guard-blocked); warming the
SHARED cache remains an explicit `--refresh-data` decision.

## 2026-08-11 — Roads serve tunnels; a cut never crosses a taxiway (owner,
## KCLT round 14)

Owner review of the round-10 KCLT output (`KCLT_20260811T1405`). Three
rulings, spec `docs/specs/round14-tunnel-road-integration-spec.md`.

1. **THE PAVED AREA IS THE CORRIDOR.** Where mapped road pavement covers a
   tunnel system's open cut, that pavement IS the tunnel surface: it is
   re-profiled in place — the whole intersection and both portal areas at
   bore depth as ONE level surface, the approaches grading back to ambient —
   instead of a synthetic corridor rectangle being emitted beside it. A
   synthetic strip next to at-grade road pavement is a CLIFF (measured: an
   8.31 m step across the 0.6 m graze standoff at the service intersection
   between KCLT's two facing portals). Claimed shapes take ref `tunnel_road`
   and keep their own ROLE and authority rank; the ref joins
   `groundside.BELOW_GRADE_REFS` so the unchanged R5 transition law grades
   the surroundings toward them. **AIRSIDE IS KING** — an apron or any
   airside shape inside the extent is never claimed or sunk; it mints a
   counted `tunnel_airside_conflict` finding for the classify instrument.

2. **A CUT NEVER INTERRUPTS AIRCRAFT-TRANSIT PAVEMENT.** Owner: "nothing may
   cut a taxiway." `runway`, `runway_clearance`, `runway_crossing` (already
   never cut) plus `junction`, `cross_connector`, `primary_parallel`,
   `secondary_parallel`, `stub` leave `bridges._tunnel_ramp_cut_roles`; over
   them the stretch is COVERED BORE and the open cut ends at the pavement
   edge. The only exception is a classified hard-deck object bridge.
   **This supersedes ruling 4 (2026-08-07) for the taxiway family ONLY** —
   `apron`, `service_road`, `service_junction` and `groundside_pavement`
   stay cuttable, because ruling 4's beheading precedent was measured
   exactly there (OTHH's mapped portals open within apron and service
   pavement).

3. **THE RAMP RUN IS DEPTH OVER GRADE.** Owner, verbatim: *"Ramps should be
   at up to 5% grade."* `bridges.TUNNEL_APPROACH_GRADE = 0.05` is a CAP, so
   `bore_depth / TUNNEL_APPROACH_GRADE` is the MINIMUM lawful run — a longer
   run at a shallower grade is lawful where geometry demands, a steeper one
   never is. A bore's floor is `deck_reference − BRIDGE_ROAD_CLEARANCE_M`
   (a measured DEM cut keeps R10-3's deeper-of-the-two; the 8 m
   `tunnel_depth_m` survives only with no deck reference at all). The three
   mechanisms that used to outrun grade-reach — the 8 m synthetic floor, the
   3.5 % highway planning grade, and `ramp_min_length_m`'s 200 m MINIMUM —
   are all retired from the portal walk. Measured effect: KCLT's SE chain
   173 m → 90 m, clear of taxiway junction 378.

## 2026-08-11 — Session rulings (rounds 9–15), pointers to the frozen specs

Owner rulings landed this session, canonical text in the named specs
(each FROZEN + amended in place; commit messages carry the measured
evidence):

* **Bridges seat by the DECK TOP, one rigid seat per family, and a
  connected assembly takes ONE seat without splitting** (owner: "if
  it's really several bridges connected as one object, there should be
  a seat level that works for all of them") — the agreeing coalition of
  member deck-face witnesses seats the family; water never authors a
  bridge datum (the MESH's own water bits are the authority).
  `docs/specs/round12-bridge-deck-datum-spec.md` + amendments 1–4.
  In-sim ACCEPTED by the owner 2026-08-11.
* **Roads serve tunnels — "the paved area IS the corridor"** (owner
  verbatim): road-family shapes inside a tunnel's open cut are CLAIMED
  and re-profiled (bore-depth level plate between facing portals, the
  graded approach IS the service road); ramps run at up to **5 % grade**
  (owner cap, `TUNNEL_APPROACH_GRADE`); a cut NEVER interrupts
  runway/taxiway-family pavement (hard-deck object bridge is the only
  exception — supersedes ruling 4 for the taxiway family only).
  `docs/specs/round14-tunnel-road-integration-spec.md` + amendment.
* **Below-grade admission needs physical evidence** — a mapped tunnel
  way emits below grade iff a measured DEM cut, or layer<0 with an
  unusable DEM, or airside-pavement cover (THE COVER IS THE DECK);
  building cover means passthrough-at-grade.
  `docs/specs/round10-tunnel-emission-spec.md` A1/A6.

## 2026-08-11b (session rulings, interview)
* **QB4 RETIRED (owner-ruled):** the "SecretRequest handler / no Win-Linux credential prompt" Q3 drift item is retired on the qtbacklog lane's measurement (in-process engine — no reachable SecretRequest path; parallel-worker secrets serviced parent-side via bundled keyring backends; the Qt sign-in dialog covers all three credential kinds). Do not re-file without new evidence.
* **Swift sign-in parity FILED (owner-ruled):** the macOS app's missing provider sign-in UI is a backlog item; the Qt `_SignInDialog` is the behavioural authority in reverse.
* **+39-095 contamination records ACCEPTED-AS-ANNOTATED; stray clip tmp deleted under explicit owner authorisation; OTBD/OTBH flat declarations DEFERRED pending in-sim look** (ledger line 2026-08-11b).
* **VHHH round QUEUED (owner in-sim on 1.0.239):** runway ends dropping to zero; the island connector grades FLAT like the airport (owner intent ruling); the WHOLE reclaimed perimeter is vertical sea walls.
* **ONE BAND CONSTRUCTION (owner-ruled 2026-08-11b, emphatic):** the reach band is constructed ONCE per solve; every consumer — the writeback clamp, the final band-excess report, seats, endpoints — reads THAT band. A second construction (the vhhh17 finding: clamp on the carried env_band, report on a rebuilt reach_band_unified) is a defect wherever it appears. Extends the standing "ONE band (reach_band_unified)" law from consumers to constructions.
* **KCLT triangle ADJUDICATED (owner 2026-08-11b):** the tunnel-conflict shapes are claimable road pavement (r14 claim law applies); the `tunnel_airside_conflict` finding closes. Artifact: session sq2/KCLT-apron-10602-adjudication.md.
* **KMCI shapeID 995 ADJUDICATED (owner 2026-08-11b):** the parking-lot APRON flip is a real scorer defect; ruled law for the scorer round: `wide_blob` may MAGNIFY but never AUTHOR apron absent at least one airside-contact feature. Companion finding queued with it: KCLT idx 1254 (13k m² apron scoring TAXI 0.58 HIGH). Artifact: session sq2/KMCI-shapeID995-parking-lot-adjudication.md.
  LANDED (lane scorer) as `G-APRON-AIRSIDE` in
  `pavement_scoring.score_shape`: APRON is removed from the candidates
  unless at least one of `name_apron`, `osm_apron`, `osm_stand`,
  `runway_connected`, `airside_contact`, `taxi_contact` is positive —
  the adjudication's own list, spelled with the production feature
  registry's names. The gate is STRUCTURAL (a candidate removal, not a
  weight): `wide_blob` keeps its full weight wherever an airside
  feature is present, so no re-weighting can un-rule it. It survives
  the G-CONFLICT reopen like the two 2026-08-10 apron gates, and each
  build prints one census line counting the shapes it gated. Known
  consequence, flagged for the owner: `alt_name_apron` (the Global
  Airports cross-reference name) is NOT on the ruled list, so a shape
  only the alt pack calls an apron still scores apron but cannot win
  it without other airside evidence.
* **HECA cache refresh AUTHORIZED (owner 2026-08-11b):** one explicit `--refresh-data airport_mod_cache` HECA run regularises the recon build's 5-file footprint-cache contamination; refresh-ledgered.
* **HECA phantom pads: EVIDENCE GATE ruled (owner 2026-08-11b):** building-pad seeds require BUILDING EVIDENCE (OSM footprint or vertical-structure test), not solid-reach alone; the two pending default-OFF defences (connector prefilter, structure-span gate) get ruled by measurement inside the same round.
* **LAWFUL-AIRSIDE VOUCHING (owner 2026-08-12):** airside-contact evidence (taxi_contact etc.) counts ONLY from a shape that is itself lawfully airside — a neighbour that got apron solely via the legacy chain, or that the apron gate would itself refuse, vouches for nothing (evaluate to a fixpoint). Closes the KMCI shapeID-995 emitted-body flip.
* **GROUNDSIDE PAVEMENT GRADES AT THE ROAD LIMIT (owner 2026-08-12):** groundside_pavement's cap moves from GROUNDSIDE_MAX_GRADE 5% to THE ROAD LIMIT (config's ROAD/SERVICE_ROAD cap — currently 8.0%; owner cited "~7%", the ruling's substance is the road limit itself, one constant, no second number). KCLT's hillside-lot +129 rows clear under it.
* **alt_name_apron STAYS OFF the apron evidence list (owner 2026-08-12).**
* **r17b attributions on record (2026-08-12):** the VHHH canyon's binding anchor is SURFACE-LAWFUL (junction/adjacent_ground node 419 at −12.537 INSIDE the Z0 7.315 core), present only in the MID-SOLVE seed pass (pass 2 of 5; passes 0/1/3/4 clean) — the below-grade-body scoping law is measured INERT; next round traces the WRITER of that mid-solve hard value. VMMC is NOT a byte-identical seawall control (itself a flat site at Z0 6.10). The coastline-wall admission is the necessary half only — the constant inset's FEATHER owns the still-ramping face; and the admission currently spans ALL flat-site rectangles incl. mainland coastline (scope: the AIRPORT's island per the owner's ruling, not every flat rectangle).
* **PRE-SHIP MODE AMENDED (owner 2026-08-12): measured arms are lawful.** The suspension of per-lane acceptance builds/censuses is NARROWED: attribution A/Bs (mechanism-before-fix interventions) and ONE measured acceptance arm per lane (single-frame A/B + census + named controls) are LAWFUL and encouraged — they caught three wrong spec premises this session before any sim pass. FULL batteries (multi-airport sweeps beyond the named controls, blast-radius, full suites) remain suspended; unit tests stay once-and-ledgered; every skipped check still gets its DEFERRED line; the owner's in-sim pass remains THE acceptance.
* **CORPUS-WIDE MOD-CACHE RE-WARM AUTHORIZED (owner 2026-08-12):** R18-2's sidecar version bump (4→5) restaled every pack's footprint cache; one owner-authorized `--refresh-data airport_mod_cache` sweep over the active tiles regularises it, refresh-ledgered; version-bump-class flags before the sweep completes are annotated, not re-triaged.
* **THE OWNER'S ARTIFACT IS THE ATTRIBUTION BASELINE (owner 2026-08-12):** a bug report implies the owner already built the tile/airport — root-cause work reads THAT artifact (shipped patch in the data repo, installed tile read-only), never a rebuilt base arm. Rebuilds survive only for FIX VERIFICATION (single-code-version arms, per the standing cross-tree ruling): ONE measured arm at round close, its base served from the artifact ledger when trees repeat. The fix loop itself iterates against an EXTRACTED SYNTHETIC REPRO (the repro-cutter spec) that reproduces the defect's numbers in seconds.
* **CONSOLIDATED ACCEPTANCE, LEAD-OWNED (owner 2026-08-12):** the closing measured arm moves from per-lane to per-merge-set — the LEAD (orchestrator) builds each affected tile/airport ONCE after all lanes merge, testing every fix together against the owner-artifact baseline and each lane's claimed deltas; a regression means attribute → fix → ONE more consolidated arm. Lanes end at implementation + twins + attribution reads (owner artifacts / repro fixtures); an in-lane build is lawful only when an interventional attribution demands an arm no artifact or fixture can answer. Refines the 2026-08-12 measured-arms amendment.
* **CONNECTED-ISLAND WALLS (owner 2026-08-12, in-sim on the rebuilt +22+113):** the island connected to the airport (owner point 22.3123837,113.9521587) gets the straight seawall — wall/feather treatment extends to CLAIMED-CLUSTER inset islands joined to the airport complex; their edges must not slope to water.
* **CANYON ROOT FIELD-CONFIRMED (2026-08-12):** 25C clean in the owner's rebuilt tile; 07L/25R still −8.9 m — phantom-EAT pins author the band at the remaining ends and the seal enforces them. The pending false-EAT ratification gains its third guard candidate: an EAT pin with NO taxi route to any runway anchor is not an end-around taxiway (attribution-first at KCLT before landing).
* **LAND-CONNECTED CONTINUITY, NO DECLARATIONS (owner 2026-08-12):** the corridor override retires — flat-site grading and seawalls must DETECT land connection automatically so it works for all airports and users: on an island land component carrying the airport's graded coverage, the airport core and its cluster insets grade CONTINUOUSLY across the connecting land (the causeway/isthmus), walls on the component's sea edge; never a per-tile bbox. The land-component test IS the connection law (r17d deferred item 4, answered). Mainland components are never flattened (island = sea-bounded component). flat_site_declared_corridors retires.
* **PARALLEL LABELED BUILD TASKS (owner 2026-08-12):** multi-tile test/acceptance builds run IN PARALLEL (as the app does), each launched as its OWN labeled background task per tile — never one opaque serial wrapper script; wall-clock = slowest tile. Timing runs stay exclusive/foreground; a tripped cross-attribution tell re-runs the pair serially before quoting.
* **SERVICE ROADS ENABLED AND BUILT (owner 2026-08-12b, in-sim on 1.0.243):** `ENABLE_SERVICE_ROADS` flips ON and the deferred feature gets BUILT — linear service corridors (apt.dat ground-truck routes + OSM small roads) become real road pavement end-to-end. The R20-2 second clause ("corridor to the taxiway surfaced, plain road pavement otherwise") is due under this ruling; the KCLT SE-tunnel corridor and both HECA spine roads are the named acceptance sites.
* **APT.DAT TRUCK ROUTES ARE A SERVICE-CORRIDOR SOURCE (owner 2026-08-12b):** the apt.dat ground-vehicle network is authoritative for service corridors (owner: both HECA spine roads carry truck routes); OSM small roads complement it. One corridor = ONE continuous law object end-to-end — never fragmented per-junction axes (the HECA four-disjoint-axes state is the named defect).
* **A ROAD'S OWN COURSE IS NEVER TERRACED (owner 2026-08-12b):** the groundside terrace wall across the KCLT lot road at 35.2077303,-80.9290869 is ERRONEOUS. Where a road reaches its free end at ambient terrain it GRADES to DEM under the road cap (8%); walls/terraces may not cut across a road's course. Terrace freedom (RULINGS "groundside terrace law") applies to the ground BETWEEN graded features, never to the feature's own run.
* **BREAK-RESIDUE DISPOSITIONS RE-OPENED FOR SERVICE CORRIDORS (lead 2026-08-12b, per standing law):** the "svc_break quarantine / none actionable" disposition on HECA's spine corridors judged against the retired accepted-residue standard (RULINGS "quarantine UNAUTHORIZED" + vocabulary (a)-(d)); the corridor round re-attributes those residues under the one-law-object-per-corridor frame.
* **LANE MASK WRITES LAND LANE-LOCAL (owner 2026-08-12b):** the engine routes mask reads/writes through an env-overridable masks root (the O4_DSF_CACHE_DIR/O4_AIRPORT_MOD_CACHE_DIR pattern: read at call time, COW-overlay seeded from the shared corpus so warm reads stay warm); harness lane builds arm it, so the legacy-mask cleanup (O4_Mask_Utils.py:427-434, the 16-blocked-removes refusal 2026-08-12) deletes lane-local clones and lane tile builds stop refusing on warm tiles. The shared-repo guard stays as backstop; the bare except:pass swallow site surfaces its refusals.
* **LANE INPUTS ARE PROVISIONED BY THE RITUAL, NEVER HAND-SEEDED (owner 2026-08-12b):** every build INPUT a lane needs (per-tile cfg, request sidecars, config frames) is provisioned automatically from ONE canonical source by the harness (lane_worktree.sh / build_airport), recorded in frame.json — a lane hand-copying an input is the census-wrapper defect re-emerging (two lanes seeded two different tile-cfg sources on 2026-08-12). Products stay lane-local; inputs resolve through the canonical frame. First instances due: per-tile cfg auto-provisioning ('EMPTY default_website' wall); the pad-request sidecar's data-vs-product status remains an open owner question, interim law tile-frame-only for pad acceptance.
* **SHIP RULING 1.0.244 (owner 2026-08-12b):** the service-corridor feature ships ON with the HECA airside regression DISCLOSED (+130 adjudicated rows, apron -11906-class worst 0.86->5.69 m, one new 1.21 m seam tear) — the owner verifies KCLT in-sim now and judges HECA only after the STAGED-SOLVE DESIGN ROUND, which owns: the corridor solve-level residue, HECA's rim-pocket off-face channel (1,238/1,330 rows median 63 m), OTHH absorption (closed interim by post-solve-only), the corridor profile law (hump/pockets/±8%), and the new seam tear. Rim pockets ship DEFAULT-OFF (knoll fix parked with its code on main).
* **DEVELOPMENT MODEL v2 (owner 2026-08-12c; all sessions adopt):** (1) SPEC PREMISES ARE AUTHOR-VERIFIED — the Fable lead verifies every mechanism claim in a spec directly against code/artifacts; evidence agents LOCATE, they never CONCLUDE into law; an unverifiable premise is written as a hypothesis whose test is the lane's step 1. (2) PRE-DELEGATED DECISION TREES — every spec pre-registers the foreseeable branch rulings ("if attribution shows X → do A"); STOPs are for genuinely novel findings only. (3) FABLE SMALL-DIFF CARVE-OUT — the lead MAY implement single-file changes ≤~50 lines that directly encode a ruling (same tests/ledger discipline); bulk, mechanical, migration, and measurement-loop work stays with Opus lanes. (4) REPORT CAPS — lane reports are capped and never restated; durable verdict files replace polling; retired lanes exit silent. (5) BUILD-TIME IS THE STANDING TOP TAX — fixture airports, the solve-stage repro cutter, and census-by-body-hash caching are chartered into the profiling round. Attribution-first + STOP-honesty is KEPT unchanged (it caught 3 wrong premises and 2 wrong fixes on 2026-08-12). Per-round wall/token logging joins the run ledger so the cost question is empirical.
* **PERFORMANCE PHASE OPENED (owner 2026-08-13):** the correctness campaign pauses with the two KCLT integral-constraint spots and HECA's parked items assigned to the STAGED-SOLVE round, which runs AFTER this phase at its faster iteration. THE BASELINE IS FROZEN at the 1.0.245 consolidated-3 state (KCLT 7bf9038e93f7, HECA f562cbfeb8f9, OTHH 75594bc8773a, CYXY 61efa43c3aeb, KSTJ 65844a63b397, with their censuses): every optimization must reproduce these body hashes byte-for-byte OR explain its delta row-by-row against the frozen censuses — known imperfections are held constant, never worsened, never silently "improved". Timing runs stay exclusive/foreground per standing law; the suspended budgets (60 s/airport, 300 s/tile) are adjudicated IN this phase. Chartered instruments: solve-stage repro cutter, fixture airports, census-by-body-hash caching, per-round wall/token ledger logging. The committed build-time baselines are re-recorded WITH owner approval at phase open (the 2026-08-04 machine-drift artifact).
* **AIRPORT DERIVED CACHES KEY ON PRISTINE INPUTS (owner 2026-08-13):** every derived cache over an airport's pack (footprint caches, DSF dump caches, apt parses) is PERSISTENT and fingerprints the PRISTINE input state — the .anchor_bak backup content/shas where the engine's own bake mutated a file, the live file otherwise — never the live stat block of engine-baked files. The engine's own writes (y-bakes) can therefore never invalidate a cache; only an EXTERNAL edit (new pack version, manual change — live sha matching neither written nor backup, exactly object_rebake's existing detection) misses. Builds consume originals per the standing bake law ("always re-read from the backup"); a build must never use airport data a previous build modified.
* **OBJECT PADS: ONE SOLVE, NO CONVERGENCE (owner 2026-08-13):** the pad-request feedback design (post-mesh requests consumed by the NEXT build, `o4_object_foot_pads.json` read-back, per-cluster-object-seating-spec §5.2 "next-build convergence") is RETIRED — the owner wants no convergence and no multi-build anything; the perfbake arm measured its fixed-point promise false (object_pad 689→723→736, sidecar sha still moving after run 3). THE INTENT, restated by the owner: minimize edits to custom objects in airport packs — an object already close to terrain (~1 m class) must not need moving. THE DESIGN: identify every building pad and its deviation from DEM PRE-SOLVE (footprint evidence + pack base elevations, both already available before step 1); where the pad seat can be adjusted to the object base WITHIN THE FEASIBILITY BAND, that adjusted elevation enters THE ONE SOLVE as the seat target and everything grades to it; an object the band cannot reach falls back to the existing rigid reseat (y-bake) path. Builds become deterministic by construction (no cross-build sidecar state; the sidecar's data-vs-product question closes as: PRODUCT of one build, an audit trail nothing consumes). BUILD-TIME GATE, owner-stated: the feature is only useful if it is FASTER than modifying the objects — acceptance must show the in-solve pad path costs no more than the y-bake edits it eliminates, and pack `.obj` files stay UNMODIFIED for every within-band object.
* **TRANSITION MACHINERY RETIRES — WELD OR GAP (owner 2026-08-13):** stacked-conflict walls, groundside terrace walls, feathers and blend shapes RETIRE as a class — they were symptom management for solve conflicts the staged solve is chartered to close, and the patch↔DEM transition is Ortho4XP's own mesh drape (the standing accept-the-drape ruling generalized). The interior adjacency law collapses to WELD OR GAP: two patch surfaces that touch AGREE at shared nodes (the corridor-mouth weld law, generalized); surfaces that must not influence each other are separated by an ambient-DEM gap the mesh drapes; an interior shared-edge disagreement is ALWAYS a defect — never a wall candidate. ONE EXCEPTION, owner-ruled: SEAWALLS survive — the VHHH and connected-island rulings stand (vertical sea edges on reclaimed land are real physical structure and must not slope to water); every other wall/terrace/feather/blend emitter retires in the staged-solve round AS the defect classes that demanded it close (no degradation-shield interims — but retirement follows the closure that makes it safe, measured, with the owner's in-sim pass as acceptance).
* **OBJECT PADS: RELATIVE COUPLING (owner 2026-08-13b, supersedes the seat-target mechanism of the ONE-SOLVE ruling; everything else in it stands):** S5's pre-registered premise test measured the absolute-DEM design infeasible — objects render at MESH-under-anchor + AGL + authored base_y (object_anchor.py:2426-2432), zero absolute-elevation placements exist in either battery pack (HECA 0/3201, OTHH 0/11902), and mesh−DEM at anchors is p50 0.82 m / p90 7.26 m DOMINATED BY OUR OWN SOLVED SURFACE — a pre-solve absolute seat would land pads farther from buildings than today's design. RULED: the pad enters the ONE solve as a RELATIVE coupling — pad_level − ground_level(anchor) = base_y, a rigid constraint between two in-solve nodes — so terrain meets the base exactly wherever the solve lawfully puts the anchor's ground. No cross-build state, no DEM approximation, no new role or constant; determinism, pack-pristine and the faster-than-y-bake gate all stand; grade-law-infeasible couplings fall back to the y-bake path.
* **OTHH −639 ADJUDICATED: CENSUS BLINDNESS (S3 dossier, lane/s3othh a24d748):** the corridor round's role migration (groundside_pavement → service_junction/service_road, ~15.5 km) removed those surfaces from the drainage-minimum walk (`grade_law._DRAINAGE_MIN_GROUNDSIDE_ROLES`); domain-invariant reading is +1,718 rows, plus a PRE-EXISTING 2,997-row blind spot (pre-corridor service_junction never read). The −639 must never be quoted as a delta. Domain restoration is ROUND work (R19 precedent: restore first, judge after); which minimum the road family owes is the owner question asked 2026-08-13b. Absorption gate O4_RIM_PRESOLVE_ABSORB measured INERT in production (rim_ids empty when pockets off) — the 29→9 claim was never shipped; gate retires, ≤9 re-earned as S4 acceptance.
* **DRAINAGE MINIMUM RETIRES — ONLY RUNWAYS CROWN (owner 2026-08-13b):** road-family surfaces (service_road/service_junction) are EXEMPT from the groundside drainage minimum, and the owner's rationale scopes the family itself: "only runways get a crown, the rest can be flat for the sim." The provisional-1.0% groundside drainage-minimum family (version-deferred, never adjudicated) RETIRES for all non-runway surfaces; the runway crown law is the only drainage law. The census DOMAIN restoration from the S3 blindness finding still lands in full (service roles return to every family walk — the blindness was an instrument defect independent of this ruling); the restored rows are judged under the remaining families, and drainage_minimum reports zero by law, not by blindness.
* **OBJECT PADS: EMISSION-TIME RELATIVE (owner 2026-08-14, second mechanism revision; the relative PRINCIPLE and every other clause stand):** the in-solve coupling is unbuildable as ruled — S5v2 measured the packs' SHARED render datums (HECA: one datum carries 1,840 of 1,883 requests; the LSGG shared-datum authoring class) standing on POST-SOLVE emitted terrain (`graded_strip`, a soft receiver with no solve node): 0/1,883 HECA requests couplable, and the datum value is BUILD-STABLE (identical across three builds — the s5pads p90 7.261 m was this one datum, not a distribution). RULED: the relative resolution moves to EMISSION, same build — pad target = the patch's own evaluated ground at the datum + base_y, computed in-run downstream of the one solve; pads remain post-solve ADDITIVE emission (weld-or-gap posture), never solve variables, so no cross-stage pull is possible and the S1b stage-tag interface for pads is DROPPED. Deterministic, single-build, exact for hosted datums; premise test pre-registered: patch-evaluated value at hosted datums must match the perfbake mesh within the existing residual cap. Convergence retirement, determinism, pack-pristine and the faster-than-y-bake gate all stand unchanged.
* **DRAINAGE RULING SCOPE CLARIFIED (owner 2026-08-14, amending "DRAINAGE MINIMUM RETIRES"):** the retirement is NARROW — what retires is ADDING drainage curvature (crown / minimum-slope requirements) to TAXIWAY and ROAD pavement surfaces; those may be flat for the sim. NOT retired: the DRAINAGE SPINE in enclosed areas (enclave/enclosed-region water escape stays law), and the DRAINAGE SLOPE on ADJACENT GROUND beside runways and taxiways (strip/RSA-side slopes stay law). Runways keep their crown. The earlier phrase "the runway crown law is the only drainage law" is superseded by this scope; the drainage_minimum census family retires only where it demanded curvature ON taxiway/road/groundside pavement surfaces.
* **DEM DEVIATION IS NOT AN ERROR AND IS NOT REPORTED (owner 2026-08-14):** deviation of a graded surface from raw DEM is not a defect, not a report line, and not a consideration — extending the standing band-lawful-displacement ruling from "not a defect metric" to "not reported at all." Grade-law violations (slope caps, welds, crowns where owed) remain the only reported surface conditions; residue/worst-deviation magnitude tables (the HECA mega-apron ~11 m class) retire from reports, dossiers and adjudications. The round's instruments stop quoting them; existing adjudications that rested on them (relief-round flags) are void unless re-founded on a grade-law violation.
* **GEOMETRY VISUAL PASS (owner 2026-08-14):** the owner inspected the HECA plan-geometry patch (heca_geom_visual, --geometry-only, 2,797 shapes at 99615ce) and found no obvious issues — the geometry-freeze direction is visually confirmed; the round proceeds as planned.
* **PAD RELIEF CAP MEASURES AGAINST THE PAD'S OWN GROUND, NEVER RAW DEM (Fable 2026-08-14, direct application of the owner's DEM-NOT-REPORTED and band-lawful-displacement rulings):** S5 measured `DSF_OBJECT_PAD_MAX_RELIEF_M` refusing 3,855 of ~3,910 HECA requests against RAW DEM (worst 38.57 m) while the ruled emission-time target lives on the patch's own evaluated ground — two instruments, one assumed population, and a raw-DEM reference is a DEM consideration the owner has retired. The cap's reference frame moves to the pad's own in-run ground authority (patch-evaluated where authored, ambient otherwise — the same two-authority rule the emission path uses), so it keeps its real meaning: a pad may not stand more than the cap above/below the ground it actually adjoins. The cap VALUE is unchanged (no new constant). PRE-REGISTERED STOP: if the re-framed population shows pads standing far above their LOCAL ground at real sites (tower-class artifacts), stop with the sites for the owner's eyes before landing.
* **PAD CAP REFERENCE IS THE PLATE'S LANDING GROUND; FEATURE KEPT AT HONEST SCOPE (owner 2026-08-14):** S5c's tower STOP adjudicated — the cap's reference completes the ruling's own phrase: the ground the pad ACTUALLY ADJOINS is where the PLATE LANDS (the clipped ring's own footprint, two-authority read at that location), never the parts' host surface — refusing the 8 western-apron tower plates (+5.6–8.0 m). The pads feature is KEPT at the scope authoring permits: at shared-datum packs (HECA class) the served population is honestly small (~57) because most objects render tens of metres off local ground BY AUTHORING and stay y-baked — pack-pristine is bounded by the pack, not the engine; the y-bake remains the majority mechanism and that is accepted. Determinism (byte-identical rebuilds) is the feature's non-negotiable, proven property.
* **RIM-POCKET SPINES ARE UNCONDITIONALLY STAGE B (Fable 2026-08-14, resolving S1d's stop):** the "one airside arm on the rim ⇒ the spine is stage A" branch repeats the false-enclosure premise one level up. Airside-is-king means airside is never PULLED — not that everything touching airside becomes an airside VARIABLE. A rim-pocket spine RECEIVES; where a rim arm is airside, the spine reads that value as an IMMUTABLE boundary (the corridor-mouth weld posture — reading airside is the implementation of airside-is-king, not a violation). The twin enforcing the conditional branch updates BY this ruling. Implementation + the S4-acceptance re-flip arm are the pocket re-enable's remaining work; pockets stay default-OFF until it passes.
* **THE SOLVE CAPTURE HAS A BOUNDARY LEAK AT DEM-DERIVED STATE (Fable 2026-08-14, from S1d's differential):** phases 5-6 consume DEM/flat-site products (relief, sea-exclusion, flat-site pack reads) that the capture does not carry — at OTHH the replay's DEM is not the build's (relief 3.71→3.12 m, pads 145→191) and no key-set extension fixes state created outside the captured kwargs. The capture's contract ("the phases 1-4 product at the boundary") RULES the fix: everything phases 5-6 consume is part of that product and must ride the capture (or be reconstructed provably byte-equal); capture_version bumps with it. HECA replays remain trustworthy (byte-for-byte); OTHH replays are NOT quotable until this lands. Chartered as the next instrument fix; consolidated arms use builds and are unaffected.
* **THE DOUBLE PROJECTION RETIRES; THE ROUND DOES NOT CLOSE WITHOUT IT (owner 2026-08-14, superseding the 2026-07-18 keep-both-projections ruling):** eliminating the double projection and never running an expensive task twice is a CORE POINT of the staged-solve architecture, not a follow-up. The round stays open until: (1) post-solve refinement is VALUE-PRESERVING — band/gap emission, tile cuts, conformance welds and densify carry solved values through geometry operations by interpolation, never by re-projection (the geom-guard's 914 post-solve-mutated airside shapes at HECA is the measured size of this work); (2) the pipeline runs ONE grade projection (the mid/late pair collapses — the 2026-07-18 mid-off A/B measured OTHH −64 s under the old law); (3) the remaining stage couplings (9/10/12/21) are wired. The timing block and round report run AFTER this lands, so they measure the finished architecture. The consolidated arms built 2026-08-14 stand as the pre-increment reference bodies.
* **NO DEFERRAL OF AGREED ARCHITECTURE WITHOUT EXPLICIT OWNER APPROVAL (owner 2026-08-14, process law):** the lead's goal is to implement the ENTIRE agreed plan. Docketing an agreed-architecture item without the owner's explicit approval is the premature-wrap defect; "done" means the plan is done. Verification debt (DEFERRED ledger) remains governed by pre-ship law; this ruling governs ARCHITECTURE.
* **A TILE WITHOUT A PER-TILE CFG USES GLOBAL DEFAULTS (owner 2026-08-14):** the harness's missing-canonical-cfg refusal amends — when no per-tile cfg exists at the canonical source, the ritual PROVISIONS one derived from the global Ortho4XP.cfg defaults, recorded in frame.json as derived-from-global-defaults with the source sha, printed loudly. This keeps the provisioning ruling's substance (one canonical source, ritual-provisioned, never hand-seeded, recorded) while matching the engine's own semantics (per-tile cfg is an OVERRIDE of globals, not a requirement). Unblocks OTHH/VHHH tile arms.
* **RATIFICATION TRIAGE IS SEQUENCED POST-ARCHITECTURE (owner 2026-08-14):** the pending 2026-08-12a ratifications (phantom-EAT table, shaping margin, island simplification, light-touch datum, drift instrument, false-EAT guards + HECA −15 m pin) are re-checked AFTER the architecture completes, tested against the final planned design — several may be mooted by it.
* **COMPLETION PLAN APPROVED; DELETION SWEEP AFTER THE OWNER'S IN-SIM TEST (owner 2026-08-14):** the full no-deferral completion plan is approved as sequenced (S1e ∥ cfg-defaults ∥ imagery hardening → S1f empties the architecture docket → consolidated arm → the one timing block → report → app build → owner in-sim → deletion sweep → ratification triage). CONDITION, owner-stated: the gated dead code must be FULLY INERT for testing. Verified state: the retirement gate `_WELD_OR_GAP` (adjacent_ground.py:2720) is a module-level compile-time constant — no env flag, no config key, no runtime path re-enables the retired emitters; S6 proved inertness by census (every retired ref → 0 at six airports) and by byte-identical null controls (SPLP, CYXY); the inverted twins fail if any retired emitter minted a face. The other retired machinery is already DELETED (pads read-back with grep-rails, absorption gate) or reports zero BY LAW with twins (drainage family). What the owner tests IS the post-retirement behavior; deletion changes bytes of source only, never of scenery.
* **FABLE IMPLEMENTATION AUTHORIZED FOR THE COMPLETION PLAN (owner 2026-08-14, amending the 2026-07-30 design-and-review-only ruling for this plan's scope):** where it is more effective or faster, Fable-class agents may IMPLEMENT plan items directly — the natural fit is judgment-heavy solve/law work (STOP resolutions, shield-vs-law adjudications, stage-B law design) where an Opus lane would stop-and-report; mechanical, sweep and measurement work stays with Opus lanes. All other discipline unchanged (specs, twins, ledger-once tests, guards, row attribution, no-merge-by-lanes).
* **THE FROZEN CTX OBJECT IS IDENTITY-BEARING; THE VALUE-KEYED MEMO IS THE COLLAPSE (Fable 2026-08-14, finalarch item 2, under the implementation authorization):** the S1f docket's freeze-graph reuse was implemented and measured in two halves. The `shape_constraints_cached` per-ctx memo is re-keyed from `id(s.polygon)` to CONTENT (`grade_graph._sc_ctx_key` — the perfgraph value-key discipline; twins incl. the recycled-id defect class), closing the mis-keying that served one shape another shape's pairs. Reusing the published frozen ctx OBJECT at the solve was then measured and REJECTED: byte-identical at CYXY/OTHH, but at HECA it moved 72,418 lines and +20 emitted nodes with a node-id renumbering cascade, because `build_context` INTERNS canonical points (`get_or_add`) as it builds — the solve-time call's interning side effect is part of the canonical node space the patch is spelled in (the `law_anchor_key` warning, now measured). RULED: the ctx rebuild at the solve is REQUIRED (identity-bearing, and cheap — dupcensus 0.0 s); the freeze→solve pair-generation duplication is collapsed by the layout-scoped run memo (full value key, spans the gap by construction). The repetition charter's last item closes on this adjudication.
* **THE BAND-SEAL AUTHORSHIP STANDS, ATTRIBUTED — THE FOLLOWING-GRADE ARM IS REFUTED (Fable 2026-08-14, finalarch item 1b):** of the S1f docket's two arms ("a following grade or an attribution for why it stands"), the grade arm was BUILT AND MEASURED: relaxing each band-clamped ring to its clamped vertices under the role cap moved 74 airside survivors at HECA seam 26 (seam-ledger re-projection class 18 → 91) and flipped +24 `within_shape::apron` rows into violation at OTHH — new last-seam airside authorship, the class the ledger exists to refuse, and a smoothing of the step that is the upstream out-of-band author's visible signature (no-degradation-shield law). REVERTED; the refutation is the finding. The seal's authorship STANDS as clamped: the band is the last authority (R17-1b structural), the clamp is confined to the vertices the band actually clamped (twin), every clamp is a counted, sited finding, and the residual step routes to the stage-B/solve docket that owns the out-of-band author.
* **STAGED-SOLVE PERF RESIDUAL APPROVED; PUBLISH/PAIR PERF ROUND CHARTERED POST-IN-SIM (owner 2026-08-14):** the solve-phase cost of the staged architecture (OTHH +46 / HECA +33 / HEAZ +6 vs the P4 baselines; decomposition in the solvereg review) is APPROVED as the architecture's price pending the in-sim validation — ceilings recorded in build_time_approvals.json. Chartered after in-sim: a dedicated perf round on the one-graph+band publish and the pair-law path, INCLUDING the two output-moving candidates as RULED changes with census adjudication (the publish collapse; the GradeShape flag-flavor law gap at solver_primitives._grade_graph_edges — the deliberately-frozen gap gets its owner ruling there). The four improved airports' gains stand.
* **ITERATIVE IS THE PRODUCTION MODEL; CONSTRUCTIVE PARKS; ITS INSTRUMENTS GRAFT (owner 2026-08-15, the constructive-solve round's verdict):** the owner's in-sim A/B (app 1.0.248, full HECA tile: constructive 6m55s vs iterative 8m00s) ruled the quality delta not worth ~1 tile-minute — the solve is no longer the tile's dominant cost. RULED: (1) the constructive core is DISABLED as a user path — `solve_model` default stays `iterative`; the K1b core stays committed and env-reachable for instrumentation only, and carries no acceptance obligations (no per-mode censuses, timing pairs, or mode-isolation gates in future rounds beyond the kill-switch identity below); (2) the LIVING-BAND/A4 INSTRUMENT grafts into the iterative branch REPORT-ONLY, default-on (`O4_BAND_INSTRUMENT=0` kills): the true-anchor band (CIFP+seam, AMENDMENT 1's A1 set) audits every other hard anchor and names each absorbed contradiction with its floor/ceiling-minting anchors (`layout._band_instrument_findings`); (3) the CONSTRUCTIVE WARM START lands default-on (`O4_ITER_WARM_START=0` kills and restores prior bytes exactly, verified CYXY `2c3331baccb1`): soft seeds re-seed on the carrier (Lipschitz-regularized seed field clamped into the true-anchor band) — a seed, never an authority; every solve pass still owns the values. First measurements: CYXY census count unchanged (313 adjudicated), final-projection movement p50 0.080→0.020 m (the smoother direction), cost ~0.2 s. Acceptance for the warm start is the owner's in-sim pass on the fresh app; the three K1b starred deviations are MOOTED for production by this ruling (they live only in the parked core).
* **THE BAND CARRIER IS ROUTE-CONTINUOUS ONLY — THE 47 FINDINGS WERE INSTRUMENT ARTIFACTS (owner audit ruling 2026-08-15, same day as the graft):** the owner audited the band instrument's worst HECA chain by KML and refused it — "the route must follow a taxiway_centerline"; the chain rode apron edges along buildings, cut across non-taxiway area, and followed taxi EDGES.  The refusal is LAW, not taste: a DECLARED TERRACE may lawfully break an apron's within-shape pairs (and terraces may never cross a taxi route or exist inside a runway), so pair-graph composition through aprons is NOT unconditional and the cone it minted was over-tight — the standing reach-follows-centerlines law, re-learned in a new instrument.  The carrier graph is now: airside route-spine edges (taxi centerlines; service excluded) + runway/runway-crossing within-shape pairs.  Under the corrected carrier HECA reports ZERO true-anchor contradictions: all 47 findings (26 seats, 21 rwy_flexed), the seat demotions, their −67 census rows (a degradation-shield-flavored gain, renounced), and the packaged "CIFP+pavement+caps mutually infeasible by ~4 m" claim are WITHDRAWN — feasibility-is-guaranteed held; the instrument was the defect.  The warm start's carrier REGULARIZATION deliberately keeps the full pair graph (it smooths a seed and claims nothing); only the CONE narrowed.  App 1.0.250 (over-tight guard) is not to be evaluated; superseded same day.
* **GAP INTERIOR RINGS NEVER CLIFF AGAINST PAVEMENT (owner 2026-08-15 evening, CYXY 60.709994,-135.0726683):** a `gap_interior_ring` must never create a cliff. Wherever ring geometry is CLOSE TO PAVEMENT it takes the pavement's SOLVED elevation (conformance, not terrain), and the descent to terrain happens through a DRAINAGE SPINE that pulls the gap surface down under the grading requirements (lawful slopes), never through a step at the pavement edge. This is the design law for the stamped-low-flats / gap-ring lane (F3): measured offenders — CYXY ring -10527 at 698.5-698.9 sitting 4-5 m below adjacent road/groundside 702.7 within 11 m, and the flat-695.8 drainage spine 7.7 m below its own terrain.
* **ROADS CARRY SPINES LIKE TAXIWAYS, AND SPINES PASS THROUGH PAVEMENT (owner 2026-08-15 evening, on the CYXY lot-over-road dossier):** every road gets a spine; in most places the OSM road ways are the source (not only apt.dat 1206 truck routes or feed chains — the mapped public road IS the spine where nothing better exists). A road spine does NOT stop at pavement it enters: it CONTINUES THROUGH lots, aprons and junction faces exactly as a taxiway spine continues through an apron, and the crossed pavement consumes the spine's station values in the corridor band. Corollary of the measured defect: one corridor chain through two faces 3.2 m apart with the lot-owned strip between them (CYXY axis 182 / shape 377) is impossible under this law — the continuous spine values the whole crossing. This law shapes the lot-over-road fix (spine-continuity conformance, with the free-road width test gaining its missing landside term for face ownership) and closes the "roads without spines" population (HECA H1 class).
* **ROADS WELD TO APRONS AT MOUTHS ONLY; NEVER TO BUILDINGS; PARALLEL FRONTAGE CUTS BACK TO DEM (owner 2026-08-15 late, the sink ruling):** a service road welds to an apron ONLY at a mouth — a road entering or leaving an apron matches the apron elevation there and grades away from it under its own cap. A road NEVER welds to a building (a building pad datum is legitimate for its own footprint and must not propagate into the road network — the measured CYXY sink: building 25's 697.13 pad datum reached lot 377 through frontage junctions 352/364/365 and carved 40,000 m³ against a 702.2 terrain median). A road running PARALLEL to an apron for more than 1.5× the road's width takes the STANDARD GROUNDSIDE CUTBACK and stays AT DEM — roads commonly run up to and along terminals at DIFFERENT LEVELS (at CYXY the landside frontage road is a second-story level several metres above the airside apron; that separation is real and must be preserved, not welded away).
* **GROUNDSIDE LOTS CUT AND FILL (owner 2026-08-15 late):** a groundside lot maintains grade BOTH ways — the one-sided min(terrain, 8% cone from perimeter welds) law is superseded by the two-sided projection: the lot tracks its terrain clamped into the weld-reachable band [weld − cap·d, weld + cap·d]. Cut-only was the measured mechanism of the CYXY 40,000 m³ lot-377 hollow (attribution dossier 2026-08-15); with the mouths-only weld ruling removing illegitimate low welds, lots under this law sit essentially at terrain except where a true mouth's grade recovery requires cut OR fill.
* **THE WITHIN-SHAPE BUDGET IS ROUTE-METRIC FOR THE APRON FAMILY (owner 2026-08-15 late, resolving C1 SM1/SM2):** the within-shape pair budget for apron/junction/groundside-family surfaces reads the ROUTE metric the band already computes (cap × route-distance between the pair's attachments + legs), not the euclidean chord — one metric for one law, solver bake and census in lockstep. The ICAO surface-slope reading moves from chord to route by this ruling. Basis: the C1 attribution — 1,485/1,502 HECA apron rows sit on pairs the solve itself baked and enforced euclidean while every feasibility instrument is route-metric; the terrace trigger fires zero joints; three clauses could not all stand. Runway/taxiway surface laws are UNCHANGED (chord).
* **STRING-BEND RETIRED (owner 2026-08-15 late):** the K1b string-bend queue item and its end-zone-cap reference-tube design retire with the parked taut-string machinery (it gates no current row — the strip_arc/longitudinal rows have a different author, the adjacent-ground band). If strings are revived the design question revives with them.

## 2026-08-18 — Interview rulings (remote handover session; owner answered via AskUserQuestion; all six 20260815g pending items closed)
* **TRANSVERSE STAYS EUCLIDEAN (owner 2026-08-18, RM question (a)):** the route-metric ruling does NOT extend to the transverse budget — a cross-corridor pair is budgeted over its direct distance, full stop. The flatness debt RM relocates (HECA transverse +963) is paid by MECHANISM — C3's aligned partner feet + junction co-level, reworked airside-frozen — never re-priced. The chord law's cross-corridor-flatness role formally transfers to C3.
* **"AIRSIDE STRICTLY IMPROVES" IS PER-AIRPORT (owner 2026-08-18, RM question (b)):** no airport's airside count may increase in a merge; campaign-net accounting is never an acceptance argument. CYXY's +20 in the RM arm therefore BLOCKS lane/routemetric until attributed and paid (brief: `docs/specs/rm-cyxy-plus20-attribution-brief.md`).
* **KDFW REFUSAL BOUNDS STAY PROVISIONAL PENDING IN-SIM (owner 2026-08-18):** len>1000 m / width>60 m / area>40k m² + the clearance gate remain provisional; ratification is gated on the owner's in-sim look at KDFW and the 10 y-baked KMCI/KDEN cosmetic records. Bridgeguard stays merged and ON in the meantime.
* **CRATER-VS-DAM RESOLVES BY GRADED HANDOFF (owner 2026-08-18, F3's empty-intersection fallback class — 34 of HECA's 70 drainage_spine survivors, way -13464):** where two parents' spine intervals do not intersect, NEITHER clause hard-wins — the spine grades monotonically from the higher authority's crater floor down to the lower parent's dam ceiling across the separation, at lawful slope. Supersedes the 2026-07-09 nearer-parent fallback in `_spine_interval`. Spec: `docs/specs/gap-conformance-spec.md` amendment F3c.
* **join_snap_t GOES ADAPTIVE (owner 2026-08-18):** the 2.0 m constant snap radius (runway_segments.py) is replaced by a radius scaled to local station spacing — no new constant to ratify. Spec'd and implemented in the wave-3 residual sweep together with R8's diagonal-pair blind-spot fix.
* **SM3 RULINGS DEFERRED TO THE RM BASE (owner 2026-08-18):** both pending SM3 items — the 204-node population's disposition and O4_SM3_EMPTY_INTERVAL_PROBE keep/delete — wait for the SM3-on-RM-base re-measure; if the population dissolves under RM the disposition question evaporates. The probe stays a lane flag until then.

## 2026-08-20/21 — Wave-3 lead adjudications (Fable lead; PROVISIONAL until the owner revisits) + owner questions raised

Lead adjudications (live law; each is a mechanism ruling under a standing owner ruling, never a new intent):

* **BAKED PAIRS ARE PRICED BY THE BAKE (lead 2026-08-20, amends RM spec twin (a)).** For a within-shape pair the solver baked, `check_grade` reads the recorded metre budget (floored at the Euclidean `cap × chord` pair-law max) instead of re-deriving a route over a ring it cannot reconstruct (the emitted ring carries post-projection inserts; the geometric widening swallowed the 60 m-chord/440 m-route pair the route-metric ruling exists to price). Lockstep by construction; proven on the RM arm (gate ON == gate OFF, 318/94). CONDITION before RM merges: the sidecar carries a bake hash keyed to the patch body; a mismatch REFUSES the census, never silently prices. `grade_law.ring_adjacent_pair` is the ONE ring-adjacency predicate (lane/routemetric 4ad22a0).
* **AIRSIDE IS DATA TO GROUNDSIDE LIMITERS (lead 2026-08-21, under "airside is king").** A finalize-stage groundside/road writer pins every airside-claimed node (the `layout.GROUNDSIDE_ROLES` partition, the receiver rule's own reading — never a hand list) at its airside-solve value; pinned values still generate the band (airside seats the weld, the road grades from it). Measured: airside values moved vs control CYXY 0 / SPJC 2 @0.01 m / HECA 1 @0.12 m. Freezing airside INSIDE the final projection is NOT the remedy (already built and refused: HECA plateau airside 16.8k→40.9k — that pass is what makes airside lawful today); the `[airside-value-audit]` line reports the pre-existing channel (HECA control 6,085 nodes, worst 16.9 m — docketed). Merged 1590f75.
* **AN UNDECLARED CROWN ENDPOINT IS UNKNOWN, NOT ON THE RIDGE (lead 2026-08-20).** The solver never prices runway ring pairs (`build_unified_graph` scopes to soft roles; `plane_constraints` has no `src/` caller), so a crown offset defaulted to 0 for a node absent from `crown_drops` was a census-minted step. Priced as the compatibility INTERVAL (a skip blinded three real over-cap rows); unpriceable pairs are COUNTED (`CROWN DECLARATION GAP`, HECA 215 / CYXY 29 / SPLP 27), never adjudicated. Merged e55f98d.
* **EAT REFUSAL IS RECT-LEVEL (lead 2026-08-21).** `_build_eat_anchor_rect_pins` stamps a crossing segment flat at ONE value, so a contradiction priced on ANY pin of the rect condemns the value on the whole rect (the r17d unroutable-law reasoning applied to the rect's other property). Before: the contradiction envelope (a spine-graph Dijkstra) reached 3 of 19 KDFW pins at 196.824 and refused all 3; the 16 unjudged kept authority and authored the inverted band. KDFW 284a→150a, 134 gone / 0 new, CYXY byte-identical. Merged 4540c29. Not transferred to the deck-pin guard (per-object; bridgeguard's call).
* **MERGE ORDER chord limiter → C3 → RM** (brief's pre-delegated branch 1): CYXY's +20 under RM is RELOCATED flatness debt (17 transverse on the relaxed apron/junction shapes, 3 RAOA on welded threshold strips), 0 of 20 on a budget RM re-priced; CYXY has ZERO within-shape airside debt for RM to buy.

OWNER QUESTIONS raised this wave (all HELD pending the owner; nothing improvised):

1. **C3 cannot pay RM's relocated AIRSIDE debt.** Airside transverse rows sit on apron|apron / junction|junction pairs priced from AIRCRAFT axes — the TAXI pass — whose aligned-partner completion (`O4_XSECTION_VERTEX_HITS`) was previously REFUSED (doubled apron feet, inverted HECA's reach band). Airside-frozen C3 on the service pass (lane/c3rework ae4a6d5: worst airside pull 58.5 m→1.11 m, HECA groundside −703, 26 twins) leaves CYXY at 93a vs the 75a bar and HECA +13 (all mixed frontage_near_miss). The 2026-08-18 RM (a) premise does not hold as written. Options: (a) extend C3 onto the taxi pass (a refused mechanism — needs a ruling), (b) keep RM parked, (c) something else. RM + SM3-on-RM stay HELD until answered.
2. **RAOA-3 rider:** CYXY `-10406` 1.680 m @3.9 % and 0.450 m @6.5 % survive C3; `-10419` closed. Runway-family law; not assigned by inference.
3. **Adaptive join_snap_t (lane/resid 31909dc):** satisfies the per-airport letter (HECA airside net −62, no airport up, zero new test failures, one join newly snapped at HECA — the bound is not loose) but re-prices HECA's airside population wholesale (415 gone / 353 new) to buy ONE runway row (the 2.24 m sliver) now that the crown fix retired the other two. Merge or drop is the owner's call.
4. **A2 frontage cutback stays default-OFF:** it is a PRE-SOLVE geometry change (SPJC apron -10113 gains a vertex, re-solves 0.03 m lower, +15 airside); no post-solve pin reaches it. The spec's "re-arm when the limiter lands" condition is met and the result still fails per-airport — a spec revision question.
5. **KDFW in-sim list** (bounds ratification): the refused 2,849×821 m inset `220.obj` at 32.88473–32.91032 / −97.04471–−97.03592 (look at the north/south ends; our surface spans 169.85–181.48 m vs its 183.286 datum), 6 KMCI + 4 KDEN flush y-bakes; OTHH viaducts survive; no deck-shaped residue in the census. Plus EAT: KSTJ's rect now refuses whole (5 of 18 pins priced) at an airport not built; ~70 % of KDFW's EAT pins carry no envelope box (a rect with no priceable node is still unjudged).
6. **KAFW new classes** (dossier `Ortho4XP/docs/triage/KAFW-KDFW-20260820.md`): N-1 road transverse at 2–8 % (over the cross-section limit, UNDER the 8 % chord cap — the chord limiter does not book them; is the cross-section limit or the chord cap the law?), N-2 crown-realisation wobble ±0.03–0.05 m (34 rows), N-3 solver exit with 195 both-hard over-cap road edges, N-4 four infeasible tile-seam DEM pin pairs, N-5 (closed by the EAT rect ruling).

## 2026-08-21 — Owner ruling on wave-3 Q1 (interview)

* **RM's RELOCATED AIRSIDE DEBT IS PAID BY THE SOLVER PRICING TRANSVERSE (owner 2026-08-21, supersedes the C3-mechanism clause of the 2026-08-18 RM (a) ruling).** The +20 CYXY / +963 HECA rows are apron|apron and junction|junction pairs — airside's own cross-corridor flatness, not road pairs; a service-pass mechanism cannot reach them. Roads touching airside already conform to it (standing law, unchanged). The remedy is option 2: the airside solve carries the `transverse` family as pair constraints (ONE law function in `grade_law`, both readers), so relaxing within-shape budgets cannot spend headroom unevenly across a corridor. NOT option 1 (planting aligned feet on aircraft axes / un-parking `O4_XSECTION_VERTEX_HITS`), NOT option 3 (parking RM) unless the solve will not converge with the extra family — measured, not assumed. Sequence: a READ first (does the solver price transverse pairs today?), then implementation on the RM lane; acceptance watches solver exit status + `airside_value_delta`, not the census alone.

## 2026-08-21b — Owner ruling: the apron WITHIN-SHAPE population is the MOVEMENT SURFACES, not all vertex pairs

* **AN APRON'S CAP IS OWED ON ITS MOVEMENT SURFACES — corridor profiles, frontage chords (building→spine) and stand entries — NEVER on a generic ring-vertex pair (owner 2026-08-21, answer "ii").** Measured basis: 1,442 of HECA's 1,584 `within_shape apron|apron` airside rows on the transect arm (1,055 of 1,089 on the battery) are generic vertex-pair chords (up to 680 m) that merely CROSS a spine corridor cover; 5 are frontage chords; 87 are back-edge (fan-zone relief would admit 1 row under the zone predicate — fan zones stay RETIRED per 2026-08-08 W2). The corridor surface is priced by its own longitudinal and transverse laws (the transverse family now enforced in the solve, lane/transect 77aeac2 / lane/routemetric fb71455); frontage chords and stand entries are priced building→spine. Consequences: (1) the census's `_check_within_shape` apron population changes to frontage chords + stand entries (corridor pairs are the corridor laws' rows, not within_shape's); (2) the solver's within-shape apron pair bake changes to the same population — ONE predicate, both readers, lockstep artifact in the sidecar; (3) the 2026-08-15 route-metric ruling (RM) applied to the generic population and is to be RE-EVALUATED on the new one before lane/routemetric merges — it may be moot; (4) runway/taxiway/junction within-shape laws are UNCHANGED by this ruling unless the same read shows the same generic-pair class there (report, then ask). Sequence: READ (re-census HECA/SPJC/CYXY under the new population on existing patches — no build) → spec → implement on a lane off main.

## 2026-08-21c — Owner ruling: the apron INTERIOR carries the 5 % ramp cap (amends 2026-08-21b)

* **EVERY APRON PAIR THAT IS NOT A MOVEMENT SURFACE IS PRICED AT THE FAN-RAMP CAP (5 %), NOT REMOVED (owner 2026-08-21, "yes").** Movement surfaces (corridor profiles via the longitudinal + transverse laws, frontage chords building→spine) hold the strict apron cap; every other apron ring-vertex pair — the generic population 2026-08-21b de-listed — is LAW at `fan_ramp_law_cap` (5 %, the 2026-08-05 fan-ramp ruling's own constant; the zone IS "not a movement surface", no zone geometry). Measured basis: under 2026-08-21b alone the apron interior had no law and, composed with transverse-in-the-solve, the transect rows moved SPJC's aprons by up to 9.7 m and the frontage chords absorbed it all (SPJC airside 189→551, 201 of 233 new rows genuine frontage chords). Consequences: the fan-ramp law is reachable again without zones; R19-5's catch stands (a 148 % ring edge fails at 5 %); ONE predicate in `classify_pair` returns the CAP (1 % movement / 5 % interior), both readers; the census's `within_shape apron|apron` rows carry which cap priced them. Fan-ramp ZONES stay retired (W2).

## 2026-08-21d — Owner rulings (JOSM ground-truth session): the apron chord population and the strip exclusion

* **THE STRICT APRON CHORD IS VERTEX → NEAREST SPINE NODE, ONE PAIR PER VERTEX (owner 2026-08-21, on HECA -10612 in JOSM).** From an apron ring vertex the only within-shape chord priced at the strict cap is the chord to its nearest spine (taxi-centerline) node. The building-frontage clamp (`BUILDING_FRONTAGE_MAX_GRADE`, "buildings are the heaviest constraint") applies to THAT chord and to frontage chords — never to arbitrary long pairs touching a pad (measured: 5,050 long HECA pairs at 1 % all entered through the pad clamp; the 53-chord fan from one -10612 pad vertex, 118-847 m, is the refuted class; the owner's expected chord is the 118 m one). Interior pairs stay at 5 % (2026-08-21c); the candidate re-price: HECA within_shape apron airside ~2,038 → ~1,151, max chord 377 m, the -10612 worst-20 class gone by construction.
* **RUNWAY-STRIP AREA IS NEVER APRON-LAW POPULATION (owner 2026-08-21, on node 30.1084958,31.4093845).** A shape or node inside the runway strip keep-out (`grade_law.runway_strip_wall_keepout_rings` — already the law geometry, today consulted only by walls/groundside) is excluded from the apron within-shape population and from the apron seniority partition. HECA way -12251 (10 m × 666 m sliver welded to runway 05C/23C's ring, roled apron, NO OSM source) is the exemplar; its mis-roling routes to the scorer-v2/roles docket separately.

## 2026-08-21e — Owner ruling: CREATION-ORDER SENIORITY

* **GEOMETRY AND WELDS ARE CREATED IN PRIORITY ORDER, AND ANYTHING CREATED LATER DEFERS TO WHAT EXISTS BEFORE IT (owner 2026-08-21).** A pass that mints a vertex, adjacency, or ring after an authority has settled (the solve, the final projection, an earlier emitter) may not conflict with that authority: the minted geometry takes the senior surface's value at its position, and the junior side conforms its own local neighbourhood under its own cap — no pass may create an over-cap step by construction. Measured basis: SPJC's 22-row class is minted by post-projection ring-minting emitters (adjacent-ground band emit, gap-fill spines, crown completion, densify, tile cuts — 114 of 142 residue T-junctions do not exist when the pre-projection weld runs); two weld reorders were law-neutral because ordering alone cannot weld geometry that does not exist yet. This generalises "airside is king" to creation order across every emitter. The two kept reorders (weld-before-projection + its A1) stand as the first instance of the principle.

## 2026-08-21f — Owner clarification: the apron vertex chord is VISIBLE, and a pad intercepts it

* **AN APRON NODE IS PRICED BY THE SHORTEST VISIBLE CHORD TO A TAXI CENTERLINE; IF THAT CHORD INTERSECTS A BUILDING PAD, THE NODE IS PRICED ONLY TO THE BUILDING PAD (owner 2026-08-21).** Clarifies 2026-08-21d's vertex→nearest-spine rule: (1) the candidate chord must be VISIBLE (the engine's existing pavement-visibility notion — never a new predicate); nearest-by-distance through an obstruction is not the chord. (2) A chord that crosses a building pad is replaced by the chord to that pad: a vertex behind a building grades to the building (frontage authority), never through it to the centerline. One selection per vertex, deterministic.

## 2026-08-24 — Owner rulings (HECA in-sim review of the apron-law round)

* **THE 5 % CLASS IS ONLY THE BACK-EDGE ZONES BETWEEN BUILDINGS (owner 2026-08-24, amends 2026-08-21c).** The interior 5 % cap applies ONLY between adjacent buildings at the apron's back edge — the fan-ramp geometry (2026-08-05), computed from pad adjacency (`plan_fan_ramp_zones`' predicate; zones need not be declared/emitted). Everywhere else the apron body holds the STRICT cap: the expectation is that 1 % between pads and centerlines dominates, with 1.5 % along taxiway corridors (the blend/spine credit). Measured basis for the amendment: the broad 5 % interior let whole rings drape onto the DEM (HECA apron median height-above-DEM 2.92 → 1.99 m, ring relief +19 %, the owner's site -10682 down 7.3 m) — the plateau had no authority. Non-back-edge interior pairs return to the strict cap under the existing 60 m body gate; the A4 chord population (visible nearest-spine, frontage, ring edges ≤ 60 m) stands.
* **TINY PADS FOLD INTO THEIR PARENT (owner 2026-08-24).** A building pad below a minimum area is NOT an independent seat authority: exemplar -10144 (216 m², one altitude tag) seated 2.56 m below the terminal it serves, 68 m away. Threshold ≥ ~220 m² to catch the exemplar; 250 m² adopted (sweeps HECA 56 / SPJC 19 / CYXY 3; worst tiny-pad step 12.04 m). A sub-threshold pad folds into its parent: no independent seat, no frontage authority of its own; its ring seats at the parent building's value where welded/within frontage reach, else at the surrounding apron's surface. The existing 100 m² pipeline floor rises to the ruled constant.
* Also this session: RULING 2026-08-21d (strip exclusion) found UNIMPLEMENTED in production (`GradeContext.strip_keepout` never populated; acceptance counts came from re-derivation) — wiring fix ordered, with a twin that fails on the unwired state.

* **NO PLATEAUS — THE APRON IS A CONTINUOUS MEMBRANE ON THE CENTERLINE SCAFFOLD (owner 2026-08-24b, supersedes the lead's plateau framing).** Unless there is a pavement gap there are NO cliffs in aprons. The centerline network traverses the terrain within its own caps (1.5 % taxiway); aprons connect to taxiways and conform continuously. Consequence for the cap chain: an interior apron chord in a corridor-connected region inherits the LOCAL CORRIDOR CAP (1.5 %), because an apron spanning between two lawful 1.5 % taxiways lawfully runs ~1.5 % itself; the 1 % strict cap belongs to the pad↔centerline (stand) chords; 5 % only at the back-edge zones (2026-08-24); a step is lawful only across a pavement gap. The owner's diagnostic question — "how can the taxiways exceed 1.5 %?" — is the acceptance test: centerline longitudinal profiles must NEVER exceed their cap, and any apron row is either a stand chord over 1 %, a corridor-region chord over 1.5 %, a back-edge chord over 5 %, or solver sag to fix — there is no lawful fourth class.

* **APRONS ARE GRADED LIKE TAXIWAYS AND RUNWAYS — THE TAUT MEMBRANE ON THE SCAFFOLD, NEVER A DEM DRAPE (owner 2026-08-24c, confirming and clarifying 24b).** The apron's reference surface is the SCAFFOLD INTERPOLATION — taxi centerline profiles + seated building pads as anchors, taut-string/smooth-plane between them — with NO DEM attraction on the apron interior (licensed by the standing band-lawful-displacement and DEM-not-reported rulings). Ideal: all aprons < 1 % in every direction between anchors; the corridor band through an apron carries the taxiway 1.5 % along itself; locally steeper small ramps (5 %) only at back edges and between adjacent buildings (the fan geometry). STAND SCOPE (owner-approved): the 1 % stand chords are the PAD-ANCHORED vertex→centerline chords; non-pad vertices take the corridor cap. NEW LAW — PAD-SEAT FEASIBILITY GATE: a pad seat that cannot reach its governing centerline anchor within 1 % × chord is a SEAT DEFECT caught at seating time (anchor-placement law analogue), never surface debt. Everything else is mechanism under creation-order seniority.

## 2026-08-25 — Owner rulings (OTHH in-sim review)

* **APRON CHORD TARGETS ARE THE NEAREST VISIBLE ANCHOR — PAD OR CENTERLINE, WHICHEVER IS CLOSER (owner 2026-08-25, amends A4.1(i) and the 2026-08-21d strict-chord clause).** An apron ring vertex's strict chord is measured to the NEAREST VISIBLE anchor across APRON-ONLY pavement, where the anchor set is BOTH the building pads and the taxiway centerline nodes — whichever is closer wins. This supersedes vertex→nearest-spine-node-with-pad-intercept: the pad is a first-class chord target, not merely an interceptor when it happens to lie in the path. Visibility is priced across apron pavement only (a chord may not cross non-apron pavement or gaps). BUILDING FRONTAGE CHORDS ARE UNCHANGED: pad→centerline frontage chords keep their existing rules (2026-08-08 / 2026-08-21d) and caps. Consequence: the chord population near pads becomes LOCAL (vertices price against the pad they stand beside instead of a distant spine node), which is the population the 2026-08-25 pad-seat measurement showed the frontage-subset consistency interval was inconsistent with.
* **DEM IS LAST PRIORITY — PAVEMENT NEVER DRAPES; CUT/RAISE STRAIGHT PLANES BETWEEN ANCHORS (owner 2026-08-25, strengthens 2026-08-24c).** The pavement surface between anchors (centerline profiles, seated pads) is the straight-plane/taut interpolation, cutting into hills and raised over hollows as needed. DEM participates ONLY as the lowest-priority tiebreaker: where the law leaves a choice (a seat interval, an unanchored region), anchor-consistency and plane-flatness are preferred over DEM proximity, and raw DEM authority appears only where no anchor reaches at all. This demotes the standing "DEM chooses WHERE within the lawful range" canon to LAST choice: the range is chosen from anchors first.

## 2026-08-25b — ROAD↔APRON EDGE CONFORMANCE + the band seal's scope (owner)

> **RECONSTRUCTED 2026-09-01 (beta hardening, H2).** This heading was
> MISSING: `2026-08-25b` is cited 28 times across `src/`, `tools/` and
> `tests/` but had no entry here, so every citation dangled. The text
> below is reconstructed from the implementation and its twins — not from
> memory — and the code is authoritative where they disagree. Evidence
> and measured numbers: `docs/specs/road-band-seal-scope-spec.md` (also
> reconstructed in the same commit, from the same sources).

* **A ROAD SHARING AN EDGE WITH AN APRON CONFORMS TO THE STRICTEST GRADE — it becomes part of the apron (owner 2026-08-25).** Contact is CANONICAL IDENTITY, never proximity: two rings share an edge exactly when they share an ordered pair of consecutive node ids (either orientation), which is what `layout.to_osm`'s 11-decimal node dedup makes an identity fact about the emitted graph. Rings that merely come CLOSE are the NEAR-MISS class — reported separately (`tools/band_clamp_attrib.py --contact-rings --near-miss-m`), never folded in; that class is a separate owner call.

* **AMENDMENT 1 — CONFORMANCE IS PRICING, NEVER POPULATION.** Attempt 1 read "becomes part of the apron" as ABSORPTION and it was measured wrong: HECA airside 1,735 → 1,948 and SPJC 175 → 178, adding +53,530 m² of new apron and new 6 m apron|junction steps at ways -12160 / -12167 — the airside-contamination direction "airside is king" forbids. So an edge-sharing ring CONFORMS to the apron's law and does not BECOME the apron: it is stamped `apron_contact`, carries the apron cap end to end, seeds from the apron datum, and keeps its role, its geometry and its groundside-family rows. No absorption, no mouth cut, no reclassification. Gate `O4_ROAD_APRON_EDGE_CONFORM`, default ON. The owner's sentence — "five ring roads touching one apron are one apron-grade surface" — is delivered as GRADE.

* **THE BAND SEAL SEALS ONLY WHAT THE BAND LEGISLATES (owner-approved option (a), same session).** `seal_pavement_to_band` is the pipeline's last elevation author (R17-1(b)), and the band of record is the AIRCRAFT-reachability band: the road family is absent from its propagation domain, its leg-cost grid never paints the road cap, and an off-mask road point is priced at `APRON_MAX_GRADE` × offset with a hard 30 m horizon. Clamping a road to that interval applied a law the road is not under, as the LAST author. MEASURED at HECA: 110 band-clamp records, 92 of them road-family, every floor-side road clamp inside the 30 m off-net radius and none outside it; the owner's site 30.102344, 31.3951157 shipped as a +5.05 m step. The seal's scope is now derived from `raster_reach_band.band_domain_roles()` — ONE source, twinned against a second hand-written copy — and the road family keeps its own authorities (mouth-fed `groundside_reach_band` seating, the road chord limiter at the road cap). Gate `O4_SEAL_AIRSIDE_ONLY`, default ON.

* **Later scoping, recorded here so the chain reads in order:** 2026-08-26b item 2 widened the contact term from the apron to EVERY airside neighbour (spec `road-airside-crossing-conformance-spec.md` §1.1); 2026-08-28e made contact a VALUE law that no longer folds into the cap for a road meeting airside only at a FACE (such a road keeps its free-road class beyond the contact).

> **The rest of the lettered family is reconstructed below** (`c`–`h`,
> 2026-09-01, H2 round 3). The `a` heading is the dated
> `## 2026-08-25` entry above (apron chord anchor targets + DEM-last).

## 2026-08-25c — EAT RECOGNITION SCOPING v2: an end-around taxiway is a ROUTED WRAP, and its pin only CUTS (owner)

> **RECONSTRUCTED 2026-09-01 (H2 round 3), four independent sources:**
> spec `docs/specs/eat-recognition-scoping-spec.md` (present); the twin
> `tests/test_eat_recognition_scoping.py` (its header carries the
> measured basis and enumerates the clauses); `STATUS.md` block
> `20260825b` ("EAT recognition v2 (RULINGS 25c/d: routed wrap +
> vacuous bound + 600 m cap + cut-only pin — LEMD builds, zero pins,
> KCLT byte-identical)"); and the implementation
> (`solver_primitives`, `grade_law`, `route_profile/solve.py`,
> `clearance.py`, `config.py`). Code and spec are authoritative.

* **MEASURED BASIS (LEMD +40-004, 2026-08-25).** 149 EAT pins over 10 crossing segments 1.0–4.6 km beyond the 14R / 36R ends, owning plain apron and junction rings, the 36R pins 59–66 m ABOVE the adjacent DEM-seeded pavement. All 12 contradictory final-band anchor pairs were EAT-pin vs EAT-pin, the phase-A harmonic split an empty polytope at 2,291 nodes, and the build died on the final-band inversion assert. **The owner rules LEMD HAS NO EATs.** Real ones cross at 439–482 m (KCLT).

* **THE RULING, three clauses.** What changes is WHICH pavement is recognised as an end-around taxiway; the anchor-rect MECHANISM of 2026-07-27 (corridor rect, `end_elev + eat_pavement_ceiling(D_mid)`, region table, contradiction guard) is UNTOUCHED. (1) **Routed wrap** — recognition needs a genuine crossing centreline whose route binds on BOTH sides; an apron ring in the corridor with no through-centreline gets no rect, and a crossing binding on one side only (a dead-end spur) gets no rect, priced at the guard site on the law graph. (2) **The vacuous-surface far bound** `D_clear = setback + tail/slope` — not a tunable, but the distance at which the regulation surface stops saying anything. (3) **The pin only CUTS**: a wrap whose regulation sits ABOVE the reference everywhere has its rect refused whole, out loud.

* Gate OFF restores the 2026-07-27 recognition exactly.

## 2026-08-25d — NOTHING IS RECOGNISED AS AN EAT BEYOND 600 m (owner; amends 25c)

> **RECONSTRUCTED 2026-09-01 (H2 round 3), three independent sources:**
> the twin `tests/test_eat_recognition_scoping.py` (which states the
> amendment and its reasoning explicitly, and twins the cap at (d2));
> the constant `EAT_MAX_CROSSING_DIST_M` in `config.py` with
> `solver_primitives`' reading of it; and `STATUS.md` block `20260825b`.

* 25c's three clauses ALL PASSED LEMD's 14R wrap at D = 1066 m — a taxi centreline genuinely crosses the extended centreline there, inside the 1280 m vacuous bound, and the regulation value genuinely cuts — so it was the one rect left standing of the original ten. **The owner rules that is not an end-around taxiway but the airport's own taxi network crossing a projected line.**

* **`EAT_MAX_CROSSING_DIST_M` = 600 m**, set from the measured feature (real EATs cross at 439–482 m at KCLT), and it is a SEPARATE, explicitly named bound: where both apply, the STRICTER of `D_clear` (25c) and the 600 m recognition cap governs.

* Result at the ship: LEMD builds with ZERO EAT pins; KCLT byte-identical.

## 2026-08-25e — THE PORTAL CORRIDOR IS CLAIMED, AND EVERY REMOVER NAMES WHAT IT DELETES (owner, option (a))

> **RECONSTRUCTED 2026-09-01 (H2 round 3), four independent sources:**
> spec `docs/specs/portal-corridor-claim-spec.md` (present, and headed
> "implements RULINGS 2026-08-25e — the mouth-D fix"); `STATUS.md`
> block `20260825b`; the implementation across `bridges.py` and
> `object_terrain_assembly.py`; and the **2026-08-30 canonical-mouth
> entry below, which quotes this ruling verbatim** ("the
> strips-plus-remainder composite that 2026-08-25e declared 'by design
> — explain, don't fix'").

* **THE EVIDENCE (2026-08-25 tunnel attribution, class 2).** OTHH mouth D (25.2789456, 51.5994543; ways `-6785`/`-6786`) is ADMITTED and EMITTED, then every piece is removed by three AGGREGATE-logging passes (covered-stretch drop, graze-clip, R14-1 stand-down). Four of eight OTHH portal clusters lose every ramp this way, and **no remover names what it deletes** — `tunnel_portal_acceptance` fails the mouth at 806.1 m and cannot see more, because absence is all there is to see.

* **§1 THE INSTRUMENT COMES FIRST, MANDATORY AND UNGATED.** Every post-emit tunnel-piece remover logs ONE line PER PIECE removed, carrying the piece's identity (`ref`, way id, lat/lon, coverage, cluster). Aggregate counts may remain as summaries; the per-piece lines are the law, and the summary count must equal the line count.

* **§2 THE CORRIDOR CLAIM — option (a).** Where a mapped mouth's outward approach corridor lands on pavement the walk can neither cut nor claim (the mouth-D class), the ramp **CLAIMS the corridor FOOTPRINT** rather than cutting it: the claim fields RIDE the shape, a drift audit checks them, and the claimed footprint is the only thing taken — never the host's profile. Landed with a bore-depth stand-down guard. Measured: OTHH mouth D emits at −0.90 m, where before there was 727.6 m of nothing.

* **THE ROLE-COMPOSITE DISPOSITION: "by design — explain, don't fix."** A `tunnel_road`-ref strip inside a host `service_road` wrap is a composite the ruling declined to change. **SUPERSEDED for the service-road family by 2026-08-30** (the corridor claim takes such a host WHOLE); `groundside_pavement` hosts keep this behaviour.

## 2026-08-25f — A PAD INSIDE A BASIN SITS AT THE BASIN FLOOR (owner, the building8 disposition)

> **RECONSTRUCTED 2026-09-01 (H2 round 3), five independent sources:**
> `config.py` (`BASIN_PAD_COVERAGE_MIN` and its ruling block, carrying
> the owner's own words); the `BuiltShape` field documentation in
> `layout.py`; `tests/test_object_basin_trench.py::TestBasinPadFloor
> Seating` (which records the amendment chain); `STATUS.md` blocks
> `20260825b` (the docket, owner-pending) and `20260825c` (the
> disposition, "authority clip — no pad severing/seating; building8+18
> unmoved"); and the 2026-08-26 entry below, which extends it.
> **Its spec, `docs/specs/basin-pad-floor-seating-spec.md`, is itself
> MISSING** — see the standing note at the end of this family.

* **THE EVIDENCE (LEMD, the basinpool round's finding 1).** The basin is confined to the owner's bbox (12,251 m², floor 584.5 m, 8.53 m below surrounding grade) but NO terrain cut emitted: the pack's own `building8` pad (way `-10008`, 33,447 m², flat at 600.28 m) covers 100 % of the facility, the floor pan is differenced against every earlier-born shape, and nothing survived. R13's pit cut only ever cut PAVEMENT, never a pad.

* **THE RULING.** Owner, on LEMD's real sunken tower circle: *"building8 should be below apron grade."* A building pad whose footprint lies within a basin facility's footprint (by `BASIN_PAD_COVERAGE_MIN` of the PAD's own area) is BELOW the surrounding grade: its flat level is the facility's DECLARED FLOOR — not the surrounding grade, not a route-reachability envelope — and the basin cut emits THROUGH it (the facility floor is never differenced away against such a pad). A declared pad is left alone by `relevel_pads_to_host_pavement`: a pad in a pit must NOT adopt its host's grade. Default ON.

* **AMENDED THREE TIMES, and amendment 3 is the landed law** (owner 2026-08-25): *"a simple 7 m deep cutout for the whole area should work without having to sever the buildings."* **NO SEVERING, NO SEATING** — the pad keeps its authored grade, geometry, welds and identity everywhere, and only its FLATTENING AUTHORITY yields inside the facility; the floor plates and the R2 wall band are born THROUGH it and own the interior. **Then extended by 2026-08-26** (below): inside a below-grade region the trench is SENIOR to every pad/building authority, and the yield covers the WHOLE derived region.

> **ONE SUB-QUESTION LEFT OPEN BY THE SOURCES.** `config.py` §1 still
> states the rule as the pad *seating* at the facility floor, while the
> twin records amendment 3 as *no seating* — flattening-authority yield
> only. Both are live in the tree (the `BuiltShape` field is written
> pre-solve and read by the seat producers). The reconstruction reports
> the tension rather than resolving it; which of the two the owner
> intends as the standing form needs one line from the owner.

## 2026-08-25g — ROADS ARE LATERALLY FLAT: THE CROSS-SECTION LIMIT IS LAW (owner)

> **RECONSTRUCTED 2026-09-01 (H2 round 3), four independent sources:**
> `config.py`'s ruling block (which quotes the ruling's title and gives
> the measured failure); `groundside.py` + `grade_law.pair_is_transverse`
> + `grade_graph.shape_constraints` (the one implementation, imported
> not copied); `STATUS.md` block `20260825c` ("ROADS — cross-section
> law (25g, transverse road pairs at the cross-section limit; owner
> site worst lateral 7.68 % → 2.11 %)"); and `tools/band_clamp_attrib.py`,
> which quotes the ruling to explain its `--road-profile` mode.
> **Its spec, `docs/specs/road-surface-quality-spec.md`, is MISSING.**

* **THE DEFECT, MEASURED.** This resolves the KAFW N-1 open question of 2026-08-20. The road cap was already generation-binding through the anisotropic bake, and it did NOT hold: the validator's allowance is `max(baked, cap_l · dist)` — "never TIGHTER than the flat cap" — so the 8 % LONGITUDINAL cap always won and **a road pair could tilt 2–8 % across its own width with nothing to price it** (164 rows at KAFW, 254 at KDFW).

* **THE RULING.** A road's CROSS-SECTION carries its own limit, and that limit is law — for the census AND the solve, which are one law and land together. The classifier that says which pairs are the cross-section is the angle between the pair's own axis and the ROAD RING's long axis, with **45° as the partition, not a tuning knob**: it is the angle at which a pair stops being more along the road than across it, so the classification is exhaustive and no pair falls between the two laws. `grade_law.pair_is_transverse` is its ONE implementation; a second 45° test anywhere would be two laws over two populations.

* Gate `O4_ROAD_CROSS_SECTION_LAW`, default ON — ONE kill switch for the whole reading; OFF restores the pre-ruling frame exactly (every pair prices at its longitudinal cap, the `road_cross_section` census family reads zero). Measured at the owner's site: worst lateral 7.68 % → 2.11 %.

## 2026-08-25h — A TRUCK ROUTE ALONG OR THROUGH AN APRON IS A SPINE AT THE APRON'S CAP (owner)

> **RECONSTRUCTED 2026-09-01 (H2 round 3), four independent sources:**
> `config.py`'s ruling block (carrying the owner's sentence);
> `groundside.apron_spine_subsegments` (whose docstring quotes the
> ruling and the spec's own words); `STATUS.md` block `20260825c`
> (with the measured result); and the §3.2 alternation instrument in
> `pipeline.py` + `tools/check_grade.py`.
> **Its spec, `docs/specs/service-road-apron-spine-spec.md`, is MISSING.**

* **THE RULING, in the owner's words:** *"A truck route along/through an apron is a SPINE at the apron's cap — like a taxiway, but 1 %."* A service-road centreline segment running INSIDE an apron or ALONG an apron edge is an apron-spine segment.

* **THE GAP IT CLOSES.** Free-road scoping (2026-07-27 + R7a) cuts a service centreline where it stops being a free road and feeds only the FREE stretches to the slice; the apron-contact stretches were supposed to "grade with the apron" but **were dropped ENTIRELY**, so those roads reached the grade graph with NO CENTRELINE AT ALL. With nothing anchoring them, the apron chain and the road family solved the same welded stations independently — the alternating apron-vs-service sawtooth at the owner's back-edge ripple sites.

* **THE RECOGNITION SET IS THE COMPLEMENT of the free-road predicate** — it takes the free-road walk's own answer and subtracts it, never a third contact test ("reuse their predicates"). Segmentation comes free: the same centreline yields apron-spine pieces inside contact and free-road pieces outside it, because the free-road walk already cut it at those stations. Gate `O4_SERVICE_APRON_SPINE`, default ON.

* **§3.2 THE ALTERNATION INSTRUMENT, report-first.** Adjacent stations along a shared apron/road edge whose AUTHORSHIP alternates by more than `EDGE_ALTERNATION_TOL_M` (0.25 m) are counted on the FINAL surface, after every writer, and published through the sidecar so the census can surface it. It gates nothing. Measured at the ship: HECA airside 2,177 → 918 on the post-lattice frame, alternation class 0.

> **STANDING DOC DEBT FOR THIS FAMILY (flagged 2026-09-01, H2).** Three
> specs these entries cite do not exist and never did:
> `basin-pad-floor-seating-spec.md` (25f), `road-surface-quality-spec.md`
> (25g) and `service-road-apron-spine-spec.md` (25h). The law is live in
> the code and its twins in every case; only the spec is missing, exactly
> as `road-band-seal-scope-spec.md` was for 25b. They are named here so
> the citations resolve to *something*, and left unwritten because
> reconstructing them is its own sourcing pass.

## 2026-08-26 — Owner rulings (LEMD T4S basin, measured against the pack's own shipped mesh patch)

Ground truth for this section: `Aerosoft - LEMD Madrid - 2 - Mesh/Patches/+40-010/+40-004/LEMD.patch.osm` — the pack's own Ortho4XP patch. Its T4S pit: one 87-vertex ring, 27,612 m², rim exactly at the pack's flat 594.625 datum, floor at exactly datum −18.0, vertical walls (paired nodes ~0.5 m apart). The pack's deepest genuine below-grade solid in the family is −7.09 m — the −18 floor is a ~10.9 m overcut to a round number, occluded by the object shell.

* **A PACK'S AUTHORED PIT DEPTH IS NEVER THE FLOOR KEY; THE FLOOR KEYS ON THE FACILITY'S DEEPEST GENUINE SOLID, WITH THE TUNNEL MARGINS RESTORED (owner 2026-08-26, supersedes Amendment 3's open-pit deck-face clause of 2026-08-25).** Floor = R_est + min genuine solid y (thickness-gated per §2.1 `MIN_SOLID_PART_THICKNESS_M`) − (`TUNNEL_FLOOR_BELOW_OBJECT_DECK_M` + `TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M`), for open pits as for bores. Measured basis: LEMD's deck-face-keyed floor 586.01 sat 0.07 m ABOVE the family's deepest solid (−7.087); the reference pack floor is 10.9 m below its own deepest solid. The loss is asymmetric — extra depth is occluded by the modelled shell and free, shallowness is the visible poke-through — so err deep. The §2.2 disagreement gate stays (absurd witnesses that survive the thickness gate), but with §2.1 applied the LEMD witness is −7.087 vs deck −7.016: they agree. Amendment 3's zero-margin deck-face clause is retired-kept-gated (`O4_BASIN_OPEN_PIT_DECK_KEY=1` restores it); the OTHH Drainage floors lawfully deepen by the restored margins.

* **INSIDE A BELOW-GRADE REGION THE TRENCH IS SENIOR TO EVERY PAD/BUILDING AUTHORITY (owner 2026-08-26, resolves the building8-vs-cut docket).** A building whose footprint spans a below-grade region is a shell/bridge over the pit, not a ground claim: its flattening authority yields over the WHOLE region (Amendment 3's authority-yield mechanics, extended to the full derived region), its geometry/welds/identity untouched. Measured basis: LEMD `building8` (the T4S terminal shell, computed footprint 33,471 m²) CONTAINS the entire authored pit; clipping the trench to outside it left 63.5% of the authored pit uncut and was 100% of the footprint shortfall.

* **THE CUT SHAPE IS DERIVED FROM THE OBJECTS THEMSELVES — REGION-LEVEL, NOT STRUCTURE-LEVEL (owner 2026-08-26: "we should be able to determine the exact shape needed from the objects", with or without a pack-shipped mesh patch).** The below-grade footprint is the union of every solid triangle's sub-polygon below −`TRENCH_SPINE_MIN_DEPTH_M` (triangles clipped to their below-threshold portion, decal sheets excluded per §2.1), morphologically closed at `AT_GRADE_FOOTPRINT_CLOSE_M`, taken as connected regions — computed over the placement population, INDEPENDENT of the pool/structure partition. Measured basis: LEMD's 358-object shared-anchor mega-pool classifies FLAT_CONFIRMED, so per-structure footprints saw only the one fully-buried member (12,434 m², 44.9% of authored); the region instrument reproduces the authored ring at 92.7–93.0% IoU across thresholds 1.5–3.0 m. A pack-shipped mesh patch, where present, is ground truth for VALIDATING the derived ring, never a required input.

## 2026-08-26b — Owner sim read of 1.0.260 at HECA (five items; item 4 is a ruling). Attributions measured this session on `/tmp/harness/HECA_20260826T213425.osm` (main cb4749b9-dirty, census ledgered); specs `heca-apron-round3-spec.md` + `road-airside-crossing-conformance-spec.md`.

1. SIM DEFECT — the apron interior lattice OVERLAPS OTHER SHAPES. Measured: 7 of 970 lattice segments leave the apron footprint (89.5 m) — 28.1 m through building shapeID 157 at 30.1111480,31.4041528; 23.5+8.2 m through junctions 2775/2776 at 30.1099666,31.4017001; graded_strips 3260/3422/3247. Mechanism: `_rows_and_columns` joins grid points into straight polylines with only per-POINT containment — segments bridge carved holes and concavities. Fix: round-3 §2 per-segment clip.
2. SIM DEFECT — service roads CROSSING taxiways leave a cliff (owner site 30.104671, 31.3973462; road must grade smoothly to MATCH the airside elevation). Measured: road ring -12847 (102.72–104.76) stands ~1.5 m from junctions -10250/-10257 (106.7–109.52), unwelded, ~2.4–4.1 m step. The 25b conformance term is scoped `{"apron"}` AND keys on literally shared edge vertices — taxiway/junction contact matches neither; the road's crossing axis (709) prices as FREE road (8%) straight across the junction area. Fix: crossing-conformance spec.
3. SIM DEFECT — small dip at 30.1290177, 31.4055841 (owner-named). Measured: lattice membrane 73.12–73.61 (min 70.11, way -14514) beside junction pieces at 73.87–74.34 and a crossing 1.5% axis at ~74 — the membrane is coupled only to its own ring (ring spans 61–74 on apron -10659) and never sees the crossing centerline as an anchor. Same mechanism as item 5. Census: `apron_lattice_membrane` 144 rows, worst 2.750 m.
4. **IF AN APRON LATTICE EXISTS IT JOINS THE TAXIWAY CENTERLINE SPINES SEAMLESSLY (owner 2026-08-26: "it should probably join seamlessly with taxiway centerline spines, since the whole apron must be perfectly smooth for aircraft movement"; necessity of the lattice itself is IN DOUBT — "which I'm not convinced is necessary").** The lattice is not a private membrane: where a taxiway centerline spine crosses or borders the latticed apron, the lattice must tie into those spine nodes (shared anchors / law edges), so apron + taxiway solve as ONE smooth surface. A lattice that merely coexists beside the spines is unlawful. The burden is on the lattice to justify itself: if seamless joining is not achievable cleanly, dropping the lattice is on the table — route that decision back to the owner with measurements (round-3 §3 necessity arm).
5. SIM DEFECT — "disconnected spine segment T with two arcs" between 30.129106,31.4059601 and 30.1293042,31.4068041. Measured: the taxi ROUTE is NOT cut — sidecar axes 656→663→662→212→210/215 chain across the apron, all cap 1.5%. What is cut is the ANCHORED SURFACE: the owner's 84.2 m line carries ZERO interior emitted stations (vertices only at stations 0.00/84.22, alts 74.02/74.55), so the junction pieces anchored by the centerline profile stand 0.7–1.2 m proud of the sagging membrane — the visible "T + arcs". Items 3 and 5 are one defect; fix: round-3 §1 centerline stations through aprons.

## 2026-08-27 — Owner ruling: NO STEPS IN AIRSIDE PAVEMENT

* **NO STEPS IN AIRSIDE PAVEMENT ARE LAWFUL — THE LAW IS GRADE + RATE-OF-CHANGE, NOT MAGNITUDE (owner 2026-08-27: "If our laws allow a step of 1.5m, then the law needs to be updated to prevent that, as it would create an impassable area for aircraft. No steps in airside pavement are lawful." Refined same day: "A 1.5m 'dip' could be ok assuming it was spread across enough area to be smooth, like the runway curvature and rate change rules.").** Context: the round-3 dip-site residual (~1.5 m of local relief between the station-anchored membrane and its low interior, every pointwise NEIGHBOUR pair within budget) was reported as lawful-as-written. The owner rules the LAW defective: a chain of individually-lawful neighbour pairs must never accumulate into relief an aircraft cannot traverse, but relief spread smoothly over enough distance is fine — the operative bounds are the runway-profile pair, applied to all airside pavement: (1) LOCAL DIRECT-DISTANCE GRADE — between two airside points, |Δz| ≤ cap × DIRECT distance (not path distance), within a local window; this holds ACROSS airside shape boundaries as well as within one shape (the round-3 T-pieces vs the membrane beside them, and the apron −10258 vs junction −10250 spread at the item-2 site, are the measured offenders); (2) RATE-OF-CHANGE — grade change per unit length limited, the vertical-curve / K-factor analogue the runway and strip_arc laws already implement for their families. (3) Under DEM-LAST (2026-08-25), an airside membrane interior may not prefer DEM proximity over flatness inside its lawful range — the sag that created the dip was exactly that preference. The pointwise chain caps stay (they govern longitudinal profiles); the new bounds close the accumulation gap. Spec: `docs/specs/airside-no-step-law-spec.md`.

* **THE GAP-SPINE BRIDGE STANDS DOWN WHEN ITS ENDS' SPREAD PRE-EXCEEDS ITS BUDGET (owner 2026-08-27, "2" — resolves the HELD question of the HEAZ build refusal; attribution 4d96a043, lane heazbisect).** A candidate bridge whose two ends' governing anchor values already spread more than cap × bridge-route-length is REFUSED loudly at candidate time (named log line + sidecar evidence), leaving the nodeless region it would have filled — the anchor-placement-law analogue: the bridge itself is the misplaced object. No re-seat of runway profiles (option 1 rejected: cross-runway coupling), no private cap class (option 3 rejected: no-degradation-shield). At HEAZ this restores the pre-c6a85e9c surface exactly; round-3 spine stations, not synthesized routes, are the anchor mechanism for nodeless interiors. Spec: `docs/specs/gap-spine-bridge-stand-down-spec.md`.

* **REFINE THE REACH BAND FIRST — THE BAND IS THE PROJECTION OF THE FULL LAW GRAPH, NARROWED BEFORE ANYTHING IS SEATED AND BEFORE THE SOLVE (owner 2026-08-27 late: "The calculation has to be done at some point, seems as good or better to refine and narrow the reach bands first, then we shouldn't need nearly as much convergence later. Consider how we can build the fully constrained graph as efficiently as possible.").** The band's edge set grows from routes + shortest local leg to the FULL law graph — pad frontage chords, the apron membrane (lattice/stations/ring law edges), and the no-step direct-distance enumeration — so a point's interval is what is TRULY feasible under every law, not merely runway-reachable along routes. Measured basis: building25's route-only band [77.74, 134.38] (56.6 m wide, 1,752 m route at 1.5%) admitted a seat of 82.52 beside an apron surface at 92.00 with a 1% × 72 m = 0.72 m chord budget — both endpoints in-band, the pair 9.77 m over cap; the seat solve and the chord law never met. Consequences: seats consume narrowed ceilings (the pairwise-seat-rule proposal is superseded); an EMPTY interval is a loud pre-solve refusal naming the site (bad data — the building146 class — refuses instead of seating nonsense); the post-solve conform passes become validators expected to approach no-op; budget NON-NEGATIVITY is a pinned invariant (the 2026-08-13 signed-slab Dijkstra blowup class). Spec: `docs/specs/unified-law-band-spec.md`.

* **GRADE LAW OUTRANKS SHARED-DATUM PRESERVATION — PACK GROUPS SPLIT WHEN THEY MUST (owner 2026-08-27 late: "the author just assumes a completely flat plane for the entire airport. If we can accommodate a group of objects with a shared-datum without violating grade, that's fine, but the grade compliance is the higher priority and if necessary we split the objects and seat them individually rather than violate grade law.").** A shared-datum pack group is seated as ONE value only while that value violates no grade law: in band terms, the group's variable lives in the INTERSECTION of its members' narrowed bands (shifted by their authored offsets), and an accommodation that exists is preferred — pack-relationship preservation is the tiebreaker, never the authority. When the intersection is empty, or the group optimum leaves any member's frontage/no-step law over cap, the group SPLITS (into sub-bodies by connected proximity first, individual pads last) and members seat individually. This amends the 2026-08-26/27 basin docket-B rigid facility-group seating: the ONE-datum-plane rule becomes the PREFERRED outcome, conditional on grade compliance, not an invariant. Applies within the pads-as-band-bounded-variables design (spec forthcoming after lane/lawband lands); the split event is LOUD and recorded in the sidecar (which group, why, the violating members and their laws), because a split visibly shears authored pack geometry and the owner will want to see where and why.

## 2026-08-28 — Owner sim read of 1.0.263 at LEMD (eight items; overall "many improvements, less objects floating, aprons look smooth"; HECA read to follow)

1. SIM DEFECT — an `apron_spine_station` at 40.4968469,-3.5645062 sits ON an existing apron edge with UNWELDED nodes (texture tearing). Ground read: 3-node station way -13145 (597.17–597.25) astride the shared boundary of apron rings -10231/-11712 — free station nodes must weld/intern into ring nodes when they land on one (round-3 station machinery gap).
2. SIM DEFECT — building8's pad should NOT exist: it wholly contains the T4S pit and interferes with the rim; the apron dives at 40.4910231,-3.5688464 (inside trench ring -11815, flat 587.75). NOTE the tension: RULINGS 2026-08-26 already ruled building8's flattening authority YIELDS over the whole below-grade region; the padvars round then made building8 a band variable seating 599.393 in a rigid unit with building24 — attribution must decide whether the pad variable un-did the yield.
3. SIM DEFECT — the pit area and main terminal read TOO LOW: ground slopes down from the apron to the pit-wall tops; the rim should be LEVEL with the apron (the basin-rim-flush-seating law's territory).
4. SIM DEFECT — tunnels REVERSED again at several sites: shapes emitted IN the tunnel instead of ramp+mouth. Entrance expected at 40.4980435,-3.5849427 (ground read: bridge_trench corridor -11812 at 606.96 + groundside + two tiny authority_retreat_wall stubs); shapeID 557 roled service_junction sits in grass.
5. SIM DEFECT — mouth at 40.4960151,-3.5849926 is correctly PLACED but has NO tunnel ramp, and its retaining walls are tiny stubs pointing the wrong way.
6. SIM DEFECT — mouth expected at 40.4944689,-3.5546245; no road shapes may extend west of it.
7. SIM DEFECT — mouth expected at 40.4901623,-3.5593036.
8. SIM DEFECT — many road shapes emit as small DISCONNECTED RECTANGLES (e.g. 40.4900517,-3.5604841 and 40.4900901,-3.5604541 — service_road ways -10376/-10377, 5 and 9 nodes, at different levels).

### 2026-08-28b — Owner sim read of 1.0.263 at HECA (five items; sites ground-read on padvars_on)

1. SIM DEFECT — small cliff/step ~30.1284906,31.4120847. Ground read: ZERO emitted ways within 20 m — a nodeless area; the step lives in uncontrolled mesh (the void class, outside the current lattice/station coverage).
2. SIM DEFECT — small rough spot 30.1287581,31.4056763: junction -12810 (the round-3 "T" piece, 73.87–74.32) against apron -13116 (72.83–80.65) — the residual membrane seam at the old dip area.
3. DATA + ROLE — 30.1141206,31.4095574 should be GROUNDSIDE, legitimately 5+ m below the apron; apron shapeID 582 (275 nodes, 86.68–104.44 emitted) must not extend into that ground. CORRECTED 2026-08-28: the owner edited the EMITTED AUTO-PATCH OSM (not the package) — the surgery is REFERENCE GEOMETRY showing the intended airside extent of 582, preserved at Ortho4XP/tmp/owner_surgery/HECA_owner_surgery_20260828.osm (sha dd2bc44dc27d0d47; the live copy in the data repo Patches dir would be overwritten by the owner's next app build). Builds will NOT see it: diff the reference against the built patch to extract the intended extent, then attribute why the BUILDER gives 582 the larger extent (which source/selector) — the fix is in code or source-data handling, never by hand-editing patches; and the 5 m step to groundside is a LAWFUL terrace (groundside terrace law), never to be "fixed".
4. SIM DEFECT — same station-on-edge class as LEMD item 1, at 30.109477,31.4036224 (station way -14575) — covered by lemd-rim-and-stations-spec §A; this site joins that acceptance.
5. SIM DEFECT — disconnected roads with a sharp cliff to the taxiway at 30.104671,31.3973462 (the STANDING apron -10258 attribution docket from the road-crossing round Amendment 2 — now due) and 30.1052938,31.3989669 (service_junction -10774 at 103.9–108.5 vs junction -12708 at 108.1–109.7).

### 2026-08-28c — Owner sim read of 1.0.263 at OTHH (four items, all tunnel-class; sites ground-read on the owner's fresh patch +20+050/+25+051)

1. SIM DEFECT — the tunnel RAMP is welded to the tunnel WALL, breaking the ramp; there must be a small gap. Site 25.2556192,51.6080938: tunnel_ramp -12214 (−1.12..0.06) and tunnel_wall -12220 (−1.12..4.0) coincide at 0.00 m.
2. SIM DEFECT — a shape reads "tunnel_road" where a tunnel RAMP ending in a MOUTH belongs; only ONE side gets a retaining wall, and the end fails to wrap. (No coordinates given — near item 1 / adjudicate via the tunnel_portal_acceptance OTHH profile sites.)
3. SIM DEFECT — same pattern at 25.2790398,51.5994135: ONE way, groundside_pavement ref=tunnel_road (-12168, 71 nodes, −0.9..4.0) — why "tunnel_road", no ramp, no walls, plus two small "road" extensions reaching INTO what should be underground tunnel interior.
4. SIM DEFECT — why is shapeID 1111 emitted at 25.2768917,51.5941058? groundside_pavement plate at 3.96 over BARE DIRT between pavement areas on top of a tunnel (with twin -11110/-11199 pieces beside).

## 2026-08-30 — Owner ruling (OTHH canonical tunnel mouth; supersedes 2026-08-25e for the service-road family)

* **CANONICAL TUNNEL MOUTH — ONE RAMP, ONE WALL PER SIDE, ONE END CAP (owner 2026-08-30, spec `othh-tunnel-mouth-canonical-spec.md`).** At a tunnel mouth the emitted set is exactly: ONE ramp surface descending the corridor centre to the mouth line, ONE retaining wall (wall + foot) per side, ONE straight end cap. The ramp reaches the mouth line. No second road shape may share the corridor: for hosts in the SERVICE-ROAD FAMILY (`service_road`, `service_junction`) the corridor claim takes the host WHOLE — the strips-plus-remainder composite that 2026-08-25e declared "by design — explain, don't fix" is SUPERSEDED for this family by this ruling. `groundside_pavement` hosts keep the 2026-08-25e behavior (the OTHH −12168 class the scoped cut exists for). Nested wall rings and wall fragments are defects. Confirmed by owner sign-off merging `lane/othhmouth` 2026-08-30 with item-3 wall-half residual quoted (7 wall pieces at 25.2715775,51.6023886; next lever: apply "walls follow their ramp" — 2026-08-07 ruling 4 — to the synthetic-corridor stand-down path).

## 2026-08-30b — Owner rulings (HECA round 6 report; four rulings)

* **ITEM-4 UP-BUILD REWORKED AIRSIDE-FROZEN (owner 2026-08-30).** The `_chord_band` pinned-generator up-build (lane/hecar6 `99e47d62`) is HELD from merge: it moved 2,053 solve-owned airside nodes (worst 3.92 m, apron node 30.11058671703,31.39511497552) and +249 census rows. The mechanism (a cut-only final pass dragging a free node down beside a pinned weld) is confirmed; the rework must build groundside UP without propagating into solve-owned airside values (airside-frozen arm, verified by `airside_value_delta.py` — solve-owned moved = 0 within 0.01 m).
* **TAXIWAY ADJACENT-GROUND BAND CUTS GROUNDSIDE (owner 2026-08-30, closes the item-2 exemption).** Zones 1–2 grade FROM THE TAXIWAY regardless of shape ownership: the graded band claims its lawful width and GROUNDSIDE SHAPES ARE CUT BACK by it. A shape boundary is not an exemption; the `s.role != "groundside_pavement"` static-block exclusions and the DEM-only pricing that let groundside carry a 7.51 m cliff at a taxiway edge (HECA junction 586 ↔ groundside 2836) are the defect. Cliffs remain lawful only beyond the graded strip (zone 3), per the standing standards text.
* **ROAD-IN-GROUNDSIDE: NEW SCOPED SEVER, NOT §H3 (owner 2026-08-30).** §H3 `ROAD_EVIDENCE_SEVER` stays refuted (measured +61 HECA/+37 SPJC/+435 LEMD, IoU 0.8221 vs 0.90). The ruled mechanism: sever ONLY where an OSM service road shares vertices with the groundside ring at 11-dp identity (the road is carried by the lot); the severed corridor becomes a road under the free-road ramp law. No global evidence sweep.
* **GROUNDSIDE_PAVEMENT IS A GAP-FILL BLOCKER (owner 2026-08-30, closes the `gap_fill.py:181` open question).** Groundside pavement inside an enclave blocks the gap-fill spine exactly as service roads do; spine graded_strips no longer grade over it (HECA 3225/3227 stacked 100% over 2837/2838 was the evidence).

## 2026-08-30c — Owner rulings (LEMD round: bridge-deck law ratified; rim follow-on accepted; merge sign-off)

* **A MAPPED ROAD BRIDGE OVER A BELOW-GRADE STRUCTURE IS A DECK, NOT CUTTABLE PAVEMENT (owner 2026-08-30, ratified as proposed by lane/lemdbridge).**
  * **§1 — Scope.** A road-feed way carrying `bridge` (any value but `no`) whose span crosses a below-grade structure THIS BUILD EMITTED — a `tunnel_ramp`, `tunnel_trench`, or open cut — is a **ROAD BRIDGE DECK**. `bridge=yes` alone mints nothing: with no emitted below-grade structure beneath it the way drapes exactly as today. The law adds a case; it does not change road drape anywhere else. Where the bridge tag is absent, nothing changes: this law reads the tag, never infers a bridge from geometry.
  * **§2 — What emits.** The deck's carriageway is minted as service-road pavement from the way's own stated width, through the ordinary corridor-course path — the deck is a piece of the road, not a new shape class. Its way is admitted to the corridor course set on the BRIDGE EVIDENCE alone, without the touching-pavement test, so the chain it belongs to is continuous end to end across the span.
  * **§3 — What must not touch it.** The deck is a SECOND exception to R14-2/A-3, beside the classified hard-deck object bridge: it is removed from `_tunnel_ramp_cut_roles`' reach for the span it bridges, and no tunnel-ramp cut, clearance annulus or covered-span mask may remove it. Nor is the deck a corridor terminus: no free-end DEM tie is minted at either abutment, because the road runs THROUGH.
  * **§4 — Where it sits.** The deck stands at least `config.BRIDGE_ROAD_CLEARANCE_M` (5.1 m, the existing constant, already the object-bridge bore-floor driver) above the highest emitted surface beneath the span. **AIRSIDE IS KING is unchanged and is the direction of the constraint:** the structure beneath keeps its authored profile untouched and never yields; the deck conforms upward, never the ramp downward.
  * **§5 — The approaches.** The deck's value is a PIN in the free-road profile solve; the chain reaches it at `SERVICE_ROAD_MAX_GRADE` like any other pinned end, and lands on the far side at the receiving surface's own value.
  * **§6 — Refusal, loudly.** A deck whose two abutment values cannot both be reached at the road cap is REFUSED at candidate time with a named log line and sidecar evidence, leaving the pre-law surface — the gap-spine-bridge stand-down precedent (owner 2026-08-27): the misplaced object is the bridge, and a bridge that cannot be built lawfully is not built.
* **RIM FOLLOW-ON ACCEPTED (owner 2026-08-30).** The LEMD T4S basin rim's 600.48 → 600.25 movement (the rim staying flush with the T4S shell pad after the seven phantom pads stopped biasing the pad solve) is accepted; the flush invariant, not the historical value, is the law. No re-pin.
* **MERGE SIGN-OFF.** lane/lemdbridge merged with the quoted costs: transverse worst 1.430 → 1.641 m at unchanged count (worst pair now apron|apron), rim follow-on above. Item 1 (bridge) implementation dispatched under the ratified law.

## 2026-08-30d — Owner amendment to the ROAD BRIDGE DECK law (terrain-based bridge)

* **NO BRIDGE OBJECT ⇒ TERRAIN-BASED BRIDGE THAT CUTS THROUGH THE RAMP (owner 2026-08-30, amends §3/§4 of 2026-08-30c).** When the scenery pack provides NO airport object for the bridge span — surface cones and edge barriers do not count as bridge objects — the deck is TERRAIN-BASED: the mesh is a heightfield, so the deck's terrain spans the crossing AT ROAD LEVEL and CUTS THROUGH the tunnel ramp's open cut. The ramp CONTINUES ON EITHER SIDE of the deck: its profile resumes at both deck edges (the stretch under the deck is a covered stretch — no open cut, no walls inside it, per the tunneldockets covered-stretch precedent). §4's clearance clause applies to the ramp's CONTINUED profile (the underground continuation passes ≥ `BRIDGE_ROAD_CLEARANCE_M` under the deck by construction of the authored ramp datum, not by moving the deck up); the deck sits at the road solve's own level (§5 approaches unchanged). Where a classified hard-deck OBJECT bridge exists, the object law (R14-2/A-3 first exception) continues to govern and the terrain stays open.

## 2026-08-30e — Owner rulings (HECA round 6b adjudicated)

* **MERGE SIGN-OFF.** lane/hecar6 merged: items 2/4/5 complete, 6 partial, 3 stopped at cap. Item-4 airside gate PASSED (0 solve-owned nodes >0.01 m). Quoted residuals accepted into the merge: low site 104.77 (+0.06), road_cross_section +10 (item-2 re-roling), item-6 two surviving strips, item-3 unverified join.
* **ITEM-4 LEVEL ACCEPTED PENDING SIM READ.** The 104.77 level (capped by the ring's far body ~104.10, mutually-infeasible-welds ceiling case) stands; the owner reads it in sim before any far-body mechanism is specced.
* **BUILDING79 = READER CONVEX HULLS (attribution accepted).** `_close_building_outline` is REFUTED as the minter (+0.3 % only); `dsf_reader.read_dsf_object_buildings` emits each OBJ8's convex hull, so five buildings arrive pre-merged (three hulls of whole complexes, up to 60,390 m²). Ruled fix: footprints from the structure's own wall geometry — dispatched as its own round.
* **CLEANUP LANE DISPATCHED** for item 6's veto-deferral survivors (`_veto_is_only_subdividers` defers when all blockers are subdivider roles) and item 3's join verification + road classification at the site.

## 2026-08-30f — Owner rulings (bridge-deck round 2)

* **§3 THIRD CLAUSE RATIFIED (owner 2026-08-30).** A ROAD BRIDGE DECK is not claimable road pavement either: R14-1's tunnel-road claim ("the paved area IS the corridor") does not reach a confirmed terrain deck. The deck's ground is the road ABOVE the corridor, not the corridor, and re-profiling it toward bore depth is the canyon the deck exists to remove. The claim resumes at both deck edges, exactly as the open cut does.
* **THE DECK REQUIRES STANDARD DEPTH; THE RAMP CLIMBS OUT BEYOND THE BRIDGE (owner 2026-08-30, answers the ramp-datum question).** The bridge deck requires the standard minimum depth beneath it (`BRIDGE_ROAD_CLEARANCE_M`, 5.1 m): the tunnel cut stays AT FULL BORE DATUM from the tunnel mouth all the way to the bridge, passes under the deck at that depth (covered stretch), and the ramp up to DEM begins on the OTHER side of the bridge deck. A ramp that surfaces before the bridge (the measured 600.17–600.95 under the span vs bore 598.45) is the defect this ruling closes.
* Process: the round-1 lane's 4-builds-vs-cap-2 overrun is recorded (one build lost to the sloped-rect defect, one invalidated by the 2026-08-30d amendment mid-flight); round 2 is granted ONE closing build.

* **2026-08-30g addendum:** HECA item-3 road classification DEFERRED TO SIM READ (owner): the identity trigger has no instance (measured, 0 of 2,740 service ways; the 3 mm gap is real geometry), the site sits at lawful height via the band. A containment-trigger widening is NOT ruled; revisit only if the sim read demands a road there.

* **2026-08-30h:** building79 structure-walls lane MERGED (owner sign-off): 8 per-building pads replace the 100,887 m² phantom; census +9 with the attributed airside→groundside shift (−556/+561) and the 7,138-node pad-population re-solve accepted (LEMD-rim-precedent class). Duplicate-ref cosmetic (2 of 175 pads, MultiPolygon groups): owner ruled FIX NOW with its own build.

* **2026-08-30i (bridge round 3):** COVERED-STRETCH CLIP SCOPE EXTENDED (owner): `TUNNEL_ROAD_REF` joins the clip's ref set (bridges.py:6960) — a terrain deck's footprint severs the tunnel corridor's OWN road surface, claimed and synthetic, exactly as it severs the ramp; the corridor resumes at both deck edges. One closing build granted.

* **2026-08-30j:** lane/othhwalls MERGED below bar (owner sign-off, sim read next): item-3 mouth canonical (7→2 wall pieces, wrapped ends = end cap); residuals quoted — census +15 (groundside mid_edge_step density effect at three distant mouths, magnitudes unchanged, not root-caused) and 6 apron-adjacent duplicate walls left standing under airside-is-king (attempt 1 measurably pulled an apron 1.34 m; the guard is law).
* **2026-08-30k:** T4S BASIN FALLOUT CONFIRMED AT LEMD (matched-control read, no bridge code): 141 airside within_shape rows, worst 11.94 m at 16.1 % vs 1.0 % cap at 40.49239,-3.56990 — pure pack-wide structure-walls footprint effect (the hecab79 residual-1 class realized). Attribution lane dispatched.

## 2026-08-30l — Owner law: CONSUMER CENSUS BEFORE CROSS-CUTTING GEOMETRY LAW

* **A cross-cutting geometry-law change starts with a CONSUMER CENSUS, not a first implementation (owner 2026-08-30, from the bridge-deck retrospective).** Any change that introduces a new shape class, a new exemption, or a new region into the layout (a deck, a mask, a claim, a protected union) must, AT SPEC TIME, enumerate EVERY pass that reads the affected geometry — by grep over the region's accessors and the roles/refs involved, plus a seam-probe trace (`O4_COVERAGE_PROBE` class instruments) where static reading is not decisive — and rule the interaction for each consumer in ONE table before any consumer is edited. The bridge-deck precedent is the cost of skipping it: the deck's vertical exemption was discovered against five consumers one build at a time (R14-1 claim → synthetic corridor → covered-stretch clip → ramp cut → groundside demotion), ~8 rounds and ~15 builds for what one consumer table would have made 1–2 rounds. Corollaries: (a) prefer trimming a region at its SINGLE DERIVATION SITE over per-consumer vetoes — round 4's mint-time trim fixed every reader of the published cut at once, while per-shape vetoes failed four times on the lot-contains-strip geometry; (b) a physically impossible model in ratified text (the floated deck in a heightfield mesh) is a spec defect — the spec author checks emitability against the mesh model before ratification is sought.

* **2026-08-30m (bridge round 9):** THE DECK'S GROUND NEVER TAKES AN AIRSIDE ROLE (owner, closes the round-8 question): a confirmed terrain deck's ground is road by §2 from the moment it is minted — whatever upstream pass re-roles it to apron/junction (the neck-split / _R_JCT_NEAR re-role family) is the defect and is fixed THERE. "Airside is king" keeps its full, unnarrowed force: the deck split never carves an airside-roled shape, and no provisional-role exception is created. One closing build granted.

* **2026-08-30n (bridge accepted):** owner accepts the LEMD bridge as built — the 332-node/0.15 m soft-receiver adoption ring (merge sign-off; sim read adjudicates) and the site's 2.62–4.61 m bore cover (structural: deck at §5 road level, cut at 30d bore datum; 5.1 m stays the target where geometry allows). The clearance instrument reads THE STRIP'S OWN VALUES from now on — the area-weighted average that reported "holds" is the defect the instrument fix closes. Branch merges once the instrument fix lands (twins only, no build — report content, not geometry).

## 2026-08-31a — Owner rulings (post-mortem of the 2026-08-30 mega-round; docs/POSTMORTEM-20260831.md is the record)

* **SIM-CHECKPOINT GATE.** At most ONE cross-cutting law (or ~5 scoped fixes) merges between owner sim reads. Instrument-green does not waive the gate; the owner's in-sim pass is the acceptance and it now bounds batch size.
* **APP-LEDGER TRIPWIRE IS ASSIGNED.** After every app build, the lead diffs the owner's recorded per-phase build times (~/.ortho4xp/auto_patch_build_times) against the previous build; >25 % growth on any airport = STOP and attribute before anything else merges. (2026-08-30: +62–75 % was recorded and unread.)
* **TERRAIN-CONFORMANCE INSTRUMENT REQUIRED.** Road-profile-vs-DEM deviation is a first-class measurement (a census cannot see a cutting); lanes gate road-affecting changes on it once it exists.
* **REDESIGN THRESHOLD.** More than 3 rulings needed on one mechanism in a day = STOP; write the replacement design, ratify once. (The 2026-08-30 bridge: 10 rounds, ~7 rulings.)
* **ROAD GRADE LAW (canonical restatement).** Roads follow terrain up to `SERVICE_ROAD_MAX_GRADE` (8 %), pinned ONLY at airside pavement; a road capped below 8 % into a cutting is a defect.
* **TUNNEL MODEL VERDICT.** The `tunnel_road` claim class (R14-1) is judged the defect; the pre-claim model (tunnel mouths, ramps, retaining walls) is the base of the Phase-2 redesign, augmented by the OSM-level crossing classifier (layer/bridge/tunnel tags + shared-node same-level rule). The bridge policy of 30c/30d/30f stands as restated in the post-mortem (object → cut+object bridges; no object → graded deck + 5.1 m clearance cuts both sides).

## 2026-08-31b — Owner rulings (road law refinement + the linear-transport redesign mandate)

* **ROAD PROFILE LAW (refines 31a).** A road may LIFT or CUT terrain as needed to stay within its 8 % cap (`SERVICE_ROAD_MAX_GRADE`); where terrain is cap-lawful it follows terrain. Roads are graded LATERALLY — no side-to-side banking (the cross-slope law the core's `road_banking_limit` machinery already enforces).
* **LEVERAGE THE CORE (owner 2026-08-31).** Ortho4XP's built-in road machinery (`include_roads`: banked-road detection, lateral leveling via shifted-DEM INTERP_ALT, lane-width buffering, airport-area auto mode, apt_area subtraction) does the heavy lifting for general roads. auto_patch's road ownership SHRINKS to: (a) pinned transitions where a road meets airside pavement, (b) bridges (the restated 30c/30d policy, OSM bridge/layer driven, 5.1 m clearance), (c) tunnels (mouths, ramps, retaining walls). The core gains one addition: an 8 % longitudinal clamp pass (bounded lift/cut smoothing over its altitude vector).
* **RETIREMENTS.** `free_road_profile`'s chord/self-pin model (the 7fd69ec1 regression's home) and the `tunnel_road` claim class (R14-1) retire together in the Phase-2 redesign — deleted per 29f once the replacement lands, not gated.

## 2026-08-31c — Owner sim read of the rebuilt HECA (first true read of the round-6 family)

* **HECA mostly good** — the round-6/6b/6c merges are sim-adjudicated as improvements. building79 mostly resolved; residuals: structure-walls footprints still TOO LARGE, and building100 covers TWO buildings (the disjoint-structure split under-splits some clusters) — queued behind the road redesign.
* **ITEM-3 ROAD IS NEEDED (supersedes the 30g deferral):** the road between 30.1123618,31.4059543 and 30.1118258,31.4065064 is MISSING and required for a smooth transition. It becomes a named acceptance site of redesign Batch 2 (the OSM service way exists — the redesign's contact/ownership model must emit it).
* **APRON BACK-EDGE RIPPLES (new):** between 30.1136005,31.4088527 and 30.1142392,31.4096925 the apron back edge ripples and the ripples spread back INTO the apron. Owed; re-read after the road redesign (owner: most issues appear road-related; complete the redesign first).
* Owner directive: COMPLETE THE ROAD REDESIGN, then re-read.

## 2026-08-31d — Owner rulings (Batch 2 adjudication)

* **BATCH 2 MERGED (owner sign-off, below the zero-airside bar):** 3,068 solve-owned nodes moved (worst 5.93 m, 86 % road-uncontacted) accepted as the 29a equilibrium-shift class after 40 km of road shapes left the shared solve's population; the sim read adjudicates. Census −319 HECA / −67 SPJC; cutting class eliminated (>20 m: 846→0); both owner sites closed.
* **PER-TILE CONFIGS ARE OPTIONAL (owner 2026-08-31):** a tile entry finding no per-tile cfg DEFAULTS TO THE USER'S GLOBAL SETTINGS (Ortho4XP.cfg) — it does not refuse. Refusal is reserved for a global config that itself lacks the required key. The harness/tile entries are fixed accordingly (Batch 2b).
* Batch 2b authorized by the spec author within 31b: (a) clip `carve_narrow_service_strips`' feed to the contact scope — the feed-carve minting 1,325 far road rings contradicts 31b's ownership model directly (finding A); (b) the transition profiler becomes the build's true last road-family writer (finding B ordering); (c) the tile-cfg fallback above.

* **2026-08-31e (Batch 2b/2c merged):** the last-writer ordering is REFUTED (+1,093 rows, single-tree; conformance keeps the build's last word — refutation twinned) and the revert verified byte-identical to the signed-off Batch-2 arm (census 6,403, body sha identical). Carve-feed clip stands as law (no-op at HECA, measured). Per-tile-cfg fallback live (31d), demonstrated at -13-078. SPJC DEM refresh owner-authorized and ledger-recorded; way-702 closes at FULL frame (follow 1.000, cut 0.001 m). NAMED for the next batch: the curve-native global slice's `kind=="service"` face classification (pipeline.py:3969) is the true author of the far road-family population (1,603 rings / 511,207 m², stable since Aug 29) — the ownership shrink completes there, not at the minters.

* **2026-08-31f (owner away, gate waived with conditions):** the owner authorizes Batches 3-4 + the buildings round to proceed WITHOUT intervening sim reads (away several days). Conditions: each batch ships its own app build (previous builds preserved for sim A/B on return); instrument acceptance replaces the eye at FULL-inventory strictness (all OTHH mouths, the LEMD bridge site, portal battery, zero-airside gates) with below-bar = STOP-and-wait, never merge; the five-airport sweep + the exclusive perf profile vs committed baselines close the campaign; the owner returns to a written per-site sim guide.

## 2026-08-31g — Batch 3 PARKED (STOP-AND-WAIT per 31f; owner adjudication package)

* STATE on lane/ltbatch3 (13 commits, 728 twins, unmerged): LEMD fully green (decks 5.10/5.39 over bore 598.45 HOLD, basin byte-held, §4 clamp pins live); OTHH 8/10 mouths canonical from 0/7 (surfaces 26→16, unmerged pairs →0, redundant pieces 47→0, census −401); all three 28c/30j owner sites clean; retirement dynamically proven (who_wrote: zero retired passes).
* THE OWNER'S ONE QUESTION: the zero-airside and census-not-worsened bars were premised on tunnels not being a population change; §5-SUPPLEMENT's ordered merge makes them one (153→23 / 95→16 surfaces). MEASURED: 417/435 over-cap within_shape pairs are IDENTICAL points at IDENTICAL heights (≤0.01 m) that the control held in different shapes; shared-vertex |dz| ≤0.05 m. The surface did not move; its boundaries did. Adjudicate: 29a equilibrium-shift class (accept, as Batch 2's shrink was) — or defect.
* RESIDUAL 2 SITES: (a) 25.2761220,51.6134683 — face 97% emitted; the 0.93 m fork crotch cannot hold two 1.6 m bands (geometric impossibility; spec option for ruling: ONE SHARED wall+foot along a crotch narrower than 2× band width); (b) 25.2537652,51.6032373 — 219.5 m² face missing mostly on OUTER stretches, cause not isolated (the lane refused to guess; correct).

* **2026-08-31h (owner): DUAL CARRIAGEWAYS ARE ONE RAMP.** A tunnel approach whose carriageways hold constant separation for the whole approach and to the mouth emits ONE ramp surface spanning both (no fork, no inner faces — outer walls only). A FORK exists only where road/rail ways actually diverge (separation grows). The divergence test is the separation profile along the arms. Expected to dissolve both Batch-3 residual sites (the 0.93 m "impossible" crotch was a mis-modelled dual carriageway).

* **2026-08-31i:** the REPARTITION CLASS IS ACCEPTED (owner): Batch 3's +846 within_shape rows are boundary re-partition of an unmoved surface (417/435 identical vertices ≤0.01 m; motion ≤0.05 m) — the 29a class. Batch 3 merges once the 31h dual-carriageway fix lands green. Census-family note owed: within_shape now prices merged ramp runs.
* **2026-08-31j (spec author):** the FACE-OWNERSHIP REGION is judged POST-SCORER, against the AIRCRAFT-TRANSIT airside union (runway/taxi/apron/junction families after enact_classify) + SERVICE_ROAD_PAVEMENT_NEAR_M — never pav_union (measured vacuous: every slice face is inside it by construction; twinned refutation stands). The release runs after enact_classify, before the solve. Batch 4a round 2 implements it; the 3 new airside strip_seam_tear rows are attributed first.

* **2026-08-31k (Batch 3 FINAL PARK, 18 commits, lane/ltbatch3 @ 7122af78):** OTHH 8/10 canonical (from 0/7; surfaces 26→13, unmerged pairs 0, redundant 47→1, walls/feet 16/16); LEMD green (decks HOLD, basin byte-held); all owner sites clean; retirement dynamically proven. BOTH residuals NAMED: (a) the merged site's foot "gap" is LAWFUL — emit_wall_band opens the band at an arm's far end by law; the inventory instrument mischarges it (bar deliberately NOT adjusted in the parking round — fix the instrument next round, with budget to verify). (b) the fork's inner face is an OWNER LAW COLLISION: the §5-supp-2 shared pinch wall necessarily encroaches on a carriageway, and R10-2 (no cover piece ON tunnel pavement) removes it — which law yields is the owner's call. Also owed: the R10-2 clip path still aggregate-logs (the blindness the named-removal instrument exists to end).

* **2026-08-31l (Batch 4a FINAL PARK, lane/ltbatch4a @ 0cb7b549):** far ref-less road rings 1,325→45 (−98.4% by area, 431,295 m² declared); the ANNULUS CLASS CLOSED GENERALLY (spine-on-building 141,544 control / 229,569 r2 / 0 r4 — the fix also cleaned the control's own pre-existing instance); census 6,403→4,233; sites intact. Residuals for the return package: 2 strip_seam_tear rows from POCKET-MERGE (pre-existing steps, new pairing — owed ruling: merge-and-weld for adjacent spine residuals), +44 airside_no_step in the 29a class, 45 rings/6,802 m². Withdrawn round-3 veto ruling recorded with its refutation.

## 2026-09-01a — Owner rulings (the four decisions + beta mandate)

* **A:** the fork-pinch shared wall STANDS DOWN — R10-2 keeps full force; the fork's inner V goes unwalled at the pinch only (outer faces + feet complete). The 31k collision is resolved.
* **B:** `BUILDING_OUTLINE_FILL_R` 110 → **~15 m**, measured against building79's cluster before landing (the 11.1 m inter-building gap stays open; genuine facade gaps close).
* **C:** adjacent spine/adjacent-ground strips meeting on freed ground WELD at the meeting (merge-and-weld rule) — no step between two graded strips.
* **D + BETA MANDATE:** the three parked batches MERGE TO MAIN as each goes green under the strict gates; the beta ships all-in from main; the owner's Thursday sim read is the final gate before Friday's release. Owner directive: root-cause and fix everything known, regression-test, iterate to confidence — the pre-ship hardening round runs NOW (plan: docs/specs/beta-hardening-plan.md).

* **2026-09-01b (CORRECTION to 31k(a)):** the merged-mouth foot gap is NOT the lawful arm-end opening — retracted by its own author with geometry (the reconstructed opening covers 5 % of the gap; a gap centred 27.3 m inboard cannot be a 4.6 m end opening). The 40.9 m² foot gap at 25.2761183,51.6134359 is UNATTRIBUTED: not a logged removal, not on tunnel pavement, not the opening, and the band emits complete in isolation on that body. A fitted end-zone instrument exclusion was written and REVERTED by its author before landing (the fitting class, refused). Fresh attribution owed via the seam-probe method (present-at-seam-X, gone-after-Y).

## 2026-09-01c — Owner ruling: THE WALL FOOT RETIRES

* The §T5 foot is not useful or necessary and RETIRES (machinery deleted per 29f). THE MODEL: the tunnel ramp is the corridor floor; a 0.5 m gap; then the wall band whose INNER AND OUTER edges both carry the SAME flat corridor-top elevation. Nothing bridges the gap — the mesher's own triangulation between the ramp edge and the wall's inner edge IS the steep face. Consequences by construction: wall_top_flat trivially satisfied (both edges one value); no floor value in any wall band; the unowned-annulus concern is void at 0.5 m (the triangulated gap is the face). `wall_gap_m` = 0.5. Supersedes §T5 (28c item 1's gap intent is kept — the gap remains — the FOOT shape does not). The two unattributed foot-gap residuals (31k/2026-09-01b) are MOOT. Per 30l: consumer census of `tunnel_wall_foot` readers (census roles, mouth inventory, twins, wall machinery) BEFORE the edit.

* **2026-09-01d (owner):** ruling C EXTENDS TO PAD EDGES — the merge-and-weld covers the pad↔apron boundary: ground revealed by the smaller closing radius grades smoothly to the pad seat. Closes both the freed-ground strip class (HECA +4/+4) and the LEMD pad-edge class (+102) in one mechanism.

* **2026-09-01e (owner):** `wall_gap_m` = **0.6 m** — off the weld tolerance (the 0.5 collision with `CONFORMANCE_TOL_M` re-created sim item-9's broken ramp; 2026-09-01c's 0.5 is amended); designed standoffs must never sit ON an interning/welding tolerance. BETA GATE = GREEN-EXCEPT-ACCEPTANCE: every suite green except the declared absolute-zero acceptance module, which stays honestly red as the campaign metric; release notes say so.

* **2026-09-01f:** 01d's pad-edge weld is REFUTED AS SCOPED (three-airport measurement: LEMD's rows are 60+ m direct-distance pairs no boundary weld reaches; HECA's four tears are an authority collision the seam law lawfully declines; SPJC's overlap does not reproduce — ordinal-ref frame). The uncovered-disagreement mechanism is the pad-seat/frontage law's territory (apron reaches the seat at cap over real distance) — a Fable spec + 30l census, not a closing radius. The isthmus split alone is GREEN at three airports.

* **2026-09-01g (owner, supersedes B/01d/01f's frame):** NO FOOTPRINT OUTSIDE THE BUILDING PAD — not even 15 m. The outline close RETIRES entirely (the pad is the structure's own footprint). BUILDING PADS TOUCHING PAVEMENT WELD TO THAT PAVEMENT (contact = value), and everything stays WITHIN THE GRADE CAP FOR ITS CLASS — the revealed ground between pads and distant pavement grades lawfully under its own class caps toward the welds. This IS the frontage mechanism; no closing radius approximates it.
* **2026-09-01h (spec author, batch-3 fork class):** the sibling/R10-2 subtraction CLIPS the wall band to its free-ground remainder (keeping pieces ≥ the emitter floor) — it never removes a piece whose free-ground part is substantial. Same footprint discipline as every batch-3 fix; closes the 51.4 m free-ground wall loss at the 142.8 m fork arm. Plus 01e applied to the two remaining 0.5-defaulting emitters (_emit_taxi_bridges, _emit_through_airport_depressed_roads → 0.6).

* **2026-09-01i (owner — the pad frontage law, completing 01g):** a building may have AIRSIDE on one side and GROUNDSIDE on the other. MIXED case: the pad WELDS TO AIRSIDE; groundside is CUT BACK from the pad (owner said 0.5 m; recorded as 0.6 m per 01e's own standoff-never-on-a-tolerance principle — owner may override with the weld-exemption route) and MAY SIT AT A DIFFERENT ELEVATION (the node-split cliff is lawful there). ALL-AIRSIDE or ALL-GROUNDSIDE case: the pad welds to that pavement and the pavement GRADES AWAY from the weld following its class laws.

* **2026-09-01j (spec author, corrects 01h's scope):** 01h's clip was inert at the ruled site (implemented against a read mechanism — the covered-stretch drop never fired there; the clip stays for where it does). The real seam, measured offline: only divergence ARMS enter the per-arm walling register, so other ramp bodies of a multi-body fork cluster get only the union band (outer hull — no concave inner face possible). RULED: PER-BODY WALLING — every ramp body of a multi-body cluster is walled as its own corridor (the sibling-exclusion + pinch machinery already composes them); the union band applies only to single-body clusters (a 31h-merged dual carriageway is one body). One closing arm.

* **2026-09-01k (owner sign-off):** Batch 4a MERGED for the beta — the two strip_seam_tear pairings (pre-existing steps newly paired by released ground) quoted for the Thursday sim read; census 6,403→4,233, phantom road rings −98.4%, annulus class closed generally.

## 2026-09-01l — Owner ruling: ZERO AIRSIDE FOR THE BETA

* THE BETA BAR IS ZERO AIRSIDE LAW VIOLATIONS. Groundside rows may stand (quoted); airside must be clean.
* HECA RUNWAYS ARE A REGRESSION, NOT AN ACCEPTED RED: they solved within grade previously, and NOTHING is allowed to pull a runway past its caps. The 05C/23C rows (2.40/2.33/2.12 % vs 1.50 %) are root-caused and fixed — the "deliberately red acceptance module" framing must never absorb a runway regression.
* Method: bisect with the runway-profile probe as predicate (the H5 pattern that named the SPLP minter), then fix at the attributed site; the remaining airside population is triaged into named mechanism classes for rapid rounds Wednesday.

## 2026-09-01m — Owner rulings (airside zero, round 1)

* **QUANTIZATION ALLOWANCE RATIFIED.** `check_grade._check_published_law_edges` grants the same sub-quantization envelope its three sibling readers already implement (`_pair_quant_noise_m`: 0.03 m base / 0.1 m junction-family weld hubs). Basis: the patch emits `alt_abs` at 2 dp, so an at-cap pair re-reads up to 1 cm over from the emit lattice alone; measured p50 excess 5 mm, single writer (solve_route_profile writeback) setting pairs exactly to cap×distance, zero patch bytes changed. HECA airside_for_acceptance 1,840 → 1,075 (765 GONE / 0 NEW / 0 MOVED). ACCEPTANCE NUMBERS FROM 2026-09-01 ARE QUOTED AGAINST THE CORRECTED INSTRUMENT — state it wherever the beta claims airside numbers.
* **ALL THREE REMAINING CLASSES ARE ATTEMPTED (owner):** (1) profile-law ingestion — the phase-A profile solve ingests direct-distance and arc-rate law between senior surfaces (211 rate + 26 tier2↔2 rows; supersedes Amendment 1's report-first docket); (2) pass-2 conform extension under its chartered do-no-harm rule (161 imposed-with-free-end); (3) enforcement for structurally-unenforced tiers 1↔2/2↔3 (70 rows) WITHOUT dissolving Amendment 2's senior byte-identity — if a class cannot be closed without breaking a senior invariant, it STOPS and reports rather than trading one law for another. Three parallel lanes; each merges only on its own green.

* **2026-09-01n:** air2 PARKED (lane/air2 @ ad20ca42, unmerged): the profile-law ingestion is CORRECT — identical code closes CYXY (airside 74→63, runway untouched, rate rows 25→17) — but HECA's joint projections EXIT UNCERTIFIED via the stall guard (sweep 1,392/250,000, ~26k active violating edges, **8,416 both-endpoints-hard edges**), so imposed law is stated but never driven to feasibility and partial conformance mints rows (1,075→1,116). ROOT ITEM NAMED: the hard-set contradictions are a defect class under the standing feasibility ruling (a real airport at real thresholds HAS a lawful surface). Lane air6 owns it; air2 re-lands on top once HECA certifies.

* **2026-09-01o (air4 STOP, evidenced):** the 70 no-free-end rows anatomized — 29 partners-contradict (over-cap seniors = air2's class; or a FLAT PAD CANNOT SPAN LAWFUL RELIEF, e.g. b168 4.03 m/397 m = 1.01% — needs the HELD split-level-seat machinery, an OWNER UN-HOLD), 12 outside-pad-band, 9 in-interval (refuted), 20 tier-1↔2 (routed to air2's phase-A ingestion — the runway is a constant, so Amendment 2's objection does not apply). MEASURED REFUTATION: the tier-2 surface has NO CONSTANT VALUE before the final projection, so junior-side conformance at any earlier slot redistributes rather than closes (arms 1,176 and 1,154 vs control 1,073; only 6 of 323 seat↔senior pairs price a constant). Mechanism DELETED per 29f. OWNER QUESTION FOR THURSDAY: un-hold split-level seats for the flat-pad-spans-relief subset?

* **2026-09-01p (air5, COMPLETE — attribution + routing, nothing landed):** the apron second wave re-derived on the corrected instrument (within_shape a|a 266, no_step a|a 142, no_step a|b 96, lattice 108) and ATTRIBUTED INTERVENTIONALLY: **final_grade_projection RE-AUTHORS values the solve left lawful** — 71-94% of every class has an endpoint FGP moved ≥0.1 m off the solve's value (p50 2.0-3.6 m); 827 vertices moved with NO recorded author (max 3.66 m) — the second-author class the single-solve architecture forbids; 21 UNCERTIFIED EXITs in one build, both-hard to 181,456 edges, FGP quitting at sweep 3,416/250,000 with 1,534 violating edges (apron 510 / junction 896). **THE 2026-08-08 APRON-RELIEF PRIOR IS REFUTED BY MEASUREMENT** (emitted dz ≫ DEM dz; these are post-solve re-authoring, not exposed relief) and was already twice superseded (fabric 08-08, taut-membrane 08-24b/c). Routed: three classes to air6's certification round (evidence in /tmp/harness/air5_who*/); no_step apron|building to the split-level un-hold (01o) + the parked pad law (01f).

* **2026-09-01q (air3, PARTIAL — parked for owner sign-off):** the pass-2 do-no-harm extension (lane/air3 @ 63e14774, flag O4_PASS2_CONFORM_EXT default ON, OFF byte-identical): a bounded-slack LP prices the do-no-harm optimum, the SAME feasibility_project builds to those floors, over-cap edges 651→0 (certifies). HECA airside 1,075→1,043 (52 GONE / 21 NEW / net −31), ZERO senior vertices moved, runway untouched, and it structurally eliminates a pre-existing defect (the old conform MINTED 8 violations and GREW 14 past their pass-1 residuals; now 0/0). Of the 161: 34 closable without harm, 127 floored by own-law ceilings against frozen seniors (report-with-reason, 217 pairs published). BELOW BAR on "no NEW rows" ⇒ OWNER SIGN-OFF OWED (Thursday). TWO DEFECTS FOUND: (a) apron_lattice_emit / apron_spine_station_emit are minted at the solve writeback and NEVER refreshed, so pass-2 movement never reaches the emitted carriers; (b) making them truthful explodes airside 1,075→2,120 — THE STALE EMIT MASKS WILD PASS-2 INTERIOR VALUES (lattice 114.6-116.5 over apron 95-104; movers to 15.7 m; own-law residuals to 19.4 m). Republication REVERTED and pinned; the attribution docket precedes any re-attempt. Routed to air6 as its third corroboration.

* **2026-09-01r (air6, STOPPED — the premise REFUTED, the blocker renamed):** the "8,416 hard-set contradictions" is FALSE. Solve exit: 1,194,703 law edges, 245,241 both-hard, **only 759 over-cap** — 99.7% both-pinned-but-LAWFUL (8,416 was one projection's EXCLUDED population; 181,456 a deliberately-frozen stage). **Every material contradiction is a GROUNDSIDE SERVICE PIN** (svc_free_end×svc_free_end 384, svc_profile×svc_profile 266, mixed 106; worst 6.17 m over a 0.32 m budget where a raw-DEM tie sits 6.5 m under its own held profile). **AIRSIDE CARRIES ONE both-hard over-cap pair at 0.003 m** — FEASIBILITY-IS-GUARANTEED HOLDS ON AIRSIDE; CIFP/seam anchors, pad seats, guard-blocked writes and runway flex mint ZERO material contradictions. The zero-airside blocker is therefore (1) FGP's DESIGN (rebuilt graph disagrees with solve law; it re-mints its own weld/couple contradictions — 1,602 at final entry from gs_weld/service_ring sources; its band clamp is a SECOND AUTHOR — air5's +8.05 m mover IS the clamp lifting to a contradicted held profile) and (2) a SHARED-VERTEX/EMIT-CONSENSUS COUPLING CHANNEL: air6's arm measured releasing GROUNDSIDE pins moving EMITTED AIRSIDE values (airside 1,075→1,102, worst 6.72 m apron pair) — an airside-is-king breach, so the fix is gated OFF and NOT merged (byte-inert). Also: an AIRSIDE-SCOPED CERTIFICATE is the decision-grade instrument for the 01l bar. Owner calls owed: the shared-vertex coupling channel (attribute-then-rule), and whether free-end DEM ties may violate the cap among themselves (29c census row) or must be cap-consistent at mint.

* **2026-09-01s (air8, COMPLETE — attribution; EMIT IS INNOCENT):** the "shared-vertex/emit-consensus coupling channel" (01r) is RENAMED by measurement: **the channel is FINAL_GRADE_PROJECTION's rebuilt-graph writeback (solve.py:10199), not emit.** Anatomy: to_osm resolves one canonical node by tier (law > authority > skirt > soft) and emits the winner's value verbatim; AUTHORITY_PRECEDENCE is airside-first, so a groundside authority CANNOT outrank an airside claim — measured ZERO groundside wins at HECA in both arms, 0 unauthored nodes, worst suppressed loser 0.37 m. Solve-exit values are IDENTICAL across air6's arms; FGP writes the difference (ctl 83.03 vs arm 83.49 at the specimen). air6's 6.72 m headline is a THRESHOLD ARTIFACT (pair budget 6.6867 m in both sidecars; endpoint moved 0.01 m); real arm damage p50 0.02 m, max 0.40 m, 25 nodes ≥0.1 m. The 827 author-less moves: only 118 airside movers sit on groundside-shared nodes (27% of material ones); 130 material movers have NO groundside co-claimant — so 01p's FGP-second-author finding owns the bulk and 01r's coupling ranking is refuted for it. LATENT, zero HECA exposure (owner note): `tunnel_ramp` is in layout.GROUNDSIDE_ROLES but ranks in the taxi family (7) in AUTHORITY_PRECEDENCE — a rank-vs-partition disagreement. NO FIX SHIPPED: there is no precedence defect; the breach is inside FGP, which is the cross-cutting docket.

* **2026-09-01t (FGP-elimination experiment, COMPLETE — answers the owner's "can we simply eliminate it?"):** NOT by simple deletion today, but the pass SPLITS by measurement. Whole-pass null arm (O4_FGP_NULL, default OFF, byte-inert proven: OFF body e916085b677a = control): the build RUNS (no structural dependency), all 588 runway-family values byte-identical, basin/tunnel evidence byte-held, and airside goes 1,075 → 1,285 (+210). Row-level join: **FGP CLOSES 641 airside rows nobody else closes** (no_step +323, transverse +60, within_shape junction +43 return without it) **while MINTING 432 of the control's own 1,075 (40%)** and re-authoring 5,328 airside values >1 cm (worst 5.83 m; 4,518 solve-owned). ⇒ **delete the minting, keep the closing = +432 rows; the residual ~209 is real work to move into the solve.** S1 is therefore worth up to 432 rows on its own. CORROBORATIONS: apron_lattice_membrane 107 → 6 without FGP — the stale carriers AGREE with the solve's surface and FGP's movement tears them (01q from the opposite direction); pass-2 conform CANNOT substitute for the projection (NULL→NOPROJ nets −20, its movers reach 35.23 m — the wild-interior class live). RELOCATABLE JOBS named with call sites in scratchpad/fgp_anatomy.md: road-transition profiler (road-family only), lockstep pair-caps freeze, triangle-plane clamp (4 rows), mouth/torn reseats, crown extension (already duplicated at pipeline.py:7819). FGP: solve.py:8348, sole call pipeline.py:7285.

* **2026-09-01u (FGP S1, PARKED cleanly per its own merge rule):** the mechanism WORKS — FGP's self-minted entry contradictions 1,602 → **97** (bar ≤759, passed 8×; solve exit unchanged 759; the FGP-only transverse class 300 → 0; holds stood down: free_end 790, profile 1,114, gs_weld 999), gate-OFF byte-identity PROVEN across three trees (body e916085b677a = control), basin/tunnel PASS, 30l consumer census committed first (docs/specs/fgp-s1-consumer-census.md). It cannot census-clear ALONE: (a) any apron-ring movement FGP makes prices apron_lattice_membrane against the FROZEN carriers (108→245 membrane-lit / 108→169 dark) plus ~200 within_shape apron rows; (b) without carrier seeding the joined no-step pairs price DEM-garbage station interiors (entry worst 29.27 m vs 8.02 m seeded). **⇒ S1+S2+S3 must be measured as ONE configuration** — that is the round, not three. Round ledger: docs/specs/fgp-s1-round-ledger.md.

* **2026-09-01v (FGP combined S1+S2+S3, PARKED but MERGED GATE-OFF):** the first FGP arm ever to IMPROVE airside — HECA 1,075 → **1,063**, total 2,838 → 2,696, entry both-hard over-cap 1,602 → **97**, `apron_lattice_membrane` **108 → 23** (the class whose refresh ALONE caused 01q's 1,075→2,120), no_step 468 → 390 (the DEM-garbage station rows GONE), S2 proven (the FGP-writeback clamp 69 clamps worst +8.05 m → 38 clamps worst +0.80 m, 16 recorded yields), carriers 662 refreshed / 0 unresolved. FAILED bars: certificate count 2,167 → 2,263 (worst 7.002 → 6.398, both-hard 3 → 0, scope +4,096 edges) and the 827-class 896 vs bar 0 (worst 3.66 → 2.97). ZERO movers on runway/tunnel/basin/bridge roles; gate-OFF body BYTE-IDENTICAL to control (e916085b677a). ROOT NAMED FROM INSIDE THE CONFIGURATION: **the solve's exit does not satisfy the law the configuration imposes**, so FGP must still move solve-stated values — 01t's "residual work to move into the solve", which is THE post-beta round. Merged with all four gates DEFAULT OFF (byte-inert, proven) so the post-beta work starts from it rather than a stranded branch. Ledger: docs/specs/fgpall-round-ledger.md.

* **2026-09-01w (self-overlap frame, spawner ruling + its REVEAL):** `check_self_overlap` now resolves rings through `layout.canonical_points` READ-ONLY before intersecting — the instrument measures the EMITTED frame invariant A1 legislates (same class as the ratified quantization allowance 01m; no threshold, no widening; a "never interns" twin pins the read-only contract). It closes the phantom SPJC building17∩building62 (7.5351 m² pre-emit; the pair TILES emitted) — and REVEALS a real defect class the old frame could not see: **weld-minted emitted double-covers**, SPJC 13 pairs / 5.13 m² (worst junction∩junction 1.33 m²), CYXY 2 / 0.59 m², each confirmed against the emitted patch's own rings; KCLT/HECA carry the same class (indicative patch-ring counts 46 / 371, hole-covering rings inflate). test_no_self_overlap[SPJC]/[CYXY] are therefore RED FOR REAL — kept red, not papered over. MERGED: a correct instrument outranks a convenient green. Attribution round dispatched (mechanism before fix).

* **2026-09-02a (weld-minted double-covers, FIXED + merged):** all 15 revealed pairs attributed at vertex level (11-dp identity, instrumented registry): raw overlap 0.000000 m² in every case — the double-cover is minted by `to_osm`'s `get_or_add` interning at 0.5 m, the losing vertex sitting exactly ON its neighbour's boundary in 12/15 while its bucket is claimed by a canonical point OFF the shared edge. MECHANISM RANKING: (1) **zone-node attractors 9/15** — the solve's `_build_node_list` interns adjacent-ground zone-row grid points into the SHARED emit registry; (2) **triangulation lookup interning 3-4/15** — `_vertex_elev_anchored` uses `get_or_add` as a QUERY, registering 2-dp phantom attractors (probe-spec §1x violated by a pipeline pass); (3) **genuine T-vertex donor bow 3/15** (the known wall-weld class). FIX (the recorded remedy): `conformance.reclip_emit_frame_overlaps` at pipeline slot 98b — the ring that GAINED area is re-clipped in the emit frame against its neighbour, shrink-only, interiors kept, pinned with add_exact; never-yield guard on runway + corridor-law roles; every clip logged. RESULTS: SPJC 13 pairs + 1 cascade cleared (census 686→687, 683 EXACT, 1 NEW row |de|=0.000 m — BELOW THE 0.01 m MATERIALITY FLOOR, spawner-accepted as PASS-with-residual), CYXY 2 cleared (160→160 all EXACT, zero movement); test_no_self_overlap SPJC/SPLP/CYXY GREEN. OWED (spec-author docket, NOT a beta item): retire the two registry-pollution channels behind a 30l consumer census of registry writers — their bucket identity is currently load-bearing.

## 2026-09-03b — Owner ruling: TUNNEL WALL CREST = DEM ALL THE WAY ROUND THE RAMP

* **THE WALL STAYS AT DEM (owner sim read of 1.0.275, OTHH).** "The wall should stay at DEM all the way around the tunnel ramp allowing the tunnel to descend to its full depth"; the mouth wall node stands the bore datum (`BRIDGE_ROAD_CLEARANCE_M` 5.1 m) above the ramp's mouth node; "no service road shape running around the outside of the tunnel wall". Spec `docs/specs/tunnel-wall-crest-dem-spec.md`; merged `7c0513cf` (lane/wallcrest). SUPERSEDES for wall crest bands: round-4 spec R5 / lead ruling 2026-08-10 (the transition law graded the crest DOWN to the ramp — the flat 4.00 m crest R5 called the defect IS the ruled surface), R16-2a's crest convergence, and `retaining_wall` in `groundside.TRANSITION_ROLES`. The §F1 station law and 2026-09-01c/e (foot retired, 0.6 m gap, one corridor-top value per station) STAND — the corridor-top value is the DEM.
* **MECHANISM (attributed, not reasoned):** the crest was derived twice — `bridges._CrestProfile` applied `transition_law_altitudes` toward the ramp at emit, and `finalize` → `apply_below_grade_transition` re-graded `retaining_wall` (and every plate outside the wall) toward the ramp again; the approach road's annulus remainder (a 1.8–5.1 m ribbon around the wall) shared the wall's outer-edge nodes and outranked it in `to_osm`. The 2026-08-30 "host WHOLE" clause had retired with the `tunnel_road` claim (08-31) and nothing replaced it.
* **LAW:** L1 crest = DEM by station (transition law DELETED from both emitters, 29f); L2 wall out of `TRANSITION_ROLES` — the wall is the discontinuity; L3 a ramp with a registered wall (`wall_band_owners`) is not a below-grade source for the R5 transition (unwalled shallow ramps and `tunnel_trench` unchanged); L4 service-road-family hosts are taken WHOLE alongside the run — partitioned at the ramp's far-end line, no width/area tolerance; `groundside_pavement` hosts keep 25e. Unmasked by L2: `finalize.deconflict_road_features` clipped wall pieces and kept misaligned altitudes (emit dropped them) — now NN-resamples.
* **MEASURED (OTHH closing build e936a0cb6ab2):** owner wall node −1.10 → 4.00 vs ramp −1.12 (5.12 m); ribbon −10051 gone; census law-true 1,620 → 1,528 (airside 1,202 = 1,202, groundside 282 → 190); acceptance wall_top_flat 5.1 → 3.45 (one 0.47 m² SW-fork crumb), ramp_wall_gap 23 → 23 (pre-existing SW fork-crumb class at 25.2540,51.6034 — owed), mouth_inventory 1 non-canonical → 1 (same SW fork site; wall R cover 0.15 → 0.97), actionable_sites 32 → 17. Twelve L4 host pieces removed (largest service_road #48 1,157 m² at the SW fork — owner eyeball owed).

## 2026-09-03c — +40-004 abort on 1.0.275 attributed: NOT a failure line

* The tile child finished the LEMD patch (13:58:32) and never ran the results loop; the app's Stop (~14:00) labelled it "failed". No failing line exists on disk. Three harness rebuilds of the tile did NOT reproduce (rc=0, ~760 s each). Merged `0fabfce7` (lane/tilewedge): bounded pool/Manager teardown naming stragglers, a cancelling child reports "stopped", step tracebacks reach Ortho4XP.log. Root cause unnamed — the next app run either completes or names the wedged pid. Owed: per-tile Stop never escalates to SIGTERM (only Stop-all does) — chip filed.

## 2026-09-03d — Owner rulings: auto-patch-v2 (ground-up, side by side)

* **V2 IS THE PLAN OF RECORD FOR THE ENGINE'S FUTURE.** Build `auto_patch_v2` from the ground up beside v1 (`docs/specs/auto-patch-v2-plan.md`, appendices A/B): fully LAW-COMPLIANT patches (not byte-identical to v1 — v1's are not lawful), simpler, faster to generate and to apply to the mesh; every source file ≤ 1,000 lines (a larger file needs a written reason); format-agnostic GradedSurface for X-Plane Next-Gen (S2 tiles), the Ortho4XP `.osm` patch being one adapter. Triggered by the week review (`review-20260903-week.md`): auto_patch 225,964 lines vs upstream Ortho4XP 17,979.
* **Solver:** add OSQP to the engine freeze if it measurably beats scipy/HiGHS on the v2 QP (measure, then add).
* **Law tables:** whichever is simpler; no value in retargeting v1's census to a new law source — v1 keeps `check_grade` until retirement; v2's `law/` is v2's own single source, cross-validated against v1's census as the oracle.
* **Loaders and classifiers are REWRITTEN** for v2 with v1 as the reference, cleaner and faster; nothing is carried by inheritance.
* **Mesh-apply bar:** tile mesh wall time and constrained-edge count with the v2 patch vs v1's on the same tile — v2 no slower, fewer edges.
* **Models:** Fable for ALL design, specs and reviews; implementation on whatever is most efficient (Opus by default once `.claude/hooks/agent_guard.py` admits it).
* **2026-09-03e (owner):** the v2 LAW TABLE is a HUMAN-READABLE, EDITABLE DATA FILE — adjusting a cap or adding a family must never require a code change. Implementation: TOML files under `src/auto_patch_v2/law/` (stdlib `tomllib`; comments carry meaning, unit and ruling id per key), a typed schema + loader that validates and fails loudly, and a twin that cross-checks the values against v1's constants. No numeric law value may live in Python.

## 2026-09-03f — R1.4 merged: the phantom plateau is gone; the residual is an intent question

* **MERGED `lane/r1backfill` (902f9c39).** `_seed_elevations` now warm-starts non-ring membrane nodes (apron spine stations, lattice, gap-fill spines) from the writeback's own publications instead of `nearest_hard_backfill` (the nearest CIFP runway corner). HECA: adjudicated airside 1,094 → 1,069, groundside 1,772 → 1,742 (OFF→ON clean read: airside −47 / +12 NEW, groundside +11); runway/tunnel/bridge movers 0; CYXY 74 → 71 with 0 pavement nodes moved; final1 certificates identical (1,985). Pass-2 "infeasible" 1,362 → 1,510 rows but max gap 19.64 → 4.34 m (station-anchored 977 → 72).
* **THE RESIDUAL (owner question, R4 territory):** 1,058 pass-2 rows are apron↔apron between two pad-shared apron ring constants across ~10 m of REAL relief along lattice chains (worst 87.86 vs 77.99 m at 30.1224,31.4080); the two R1.3 sites now show the true step the plateau masked (2.84 m apron|building at −10165/−10749; 3.4 m apron|apron at −10270 with a groundside FGP-hard pin beneath — R6's channel). Which yields — the pad seat or the apron membrane over real relief — is the apron-relief charter the plan's R4 asks for. Still backfilled, out of scope, follow-up: zone rows (95,356) and non-pavement ring vertices (9,125 of 30,496).
* **2026-09-03g (measured, closes decision 1 of 03d):** OSQP is NOT added to the freeze — at 150k vertices it either leaves 112 mm violations (default) or takes 680 s and falsely reports a feasible instance infeasible (1e-6 + polish). scipy/HiGHS LP with the real objective: 5.3 s / 2.0 GB at 150k, 1.1 s at 50k, 0.23 s at 15k; a zero-objective phase-1 is 9× slower (degenerate simplex) — feasibility is answered by the real solve. Infeasibility diagnosis: seeded deletion-filter IIS 0.1–10 s up to 50k, 109 s at 150k (only on infeasible builds). `docs/specs/auto-patch-v2/solver-benchmark-20260903.md`.

## 2026-09-03h — Owner rulings: pads yield; Fable for implementation

* **APRON RELIEF: PADS YIELD.** Over real relief a building pad YIELDS so that it stays connected to its apron and the apron stays within its own grade law. The apron membrane is senior to the pad seat: the pad is a rigid flat group whose level is set by its apron contact (weld = value, 09-01g), never a pin the apron must climb to. Closes the plan's R4 charter question and the R1.4 residual class (1,058 HECA pass-2 apron↔apron rows across ~10 m relief; 2.84 m / 3.4 m steps at the R1.3 sites). v2: encoded in `law/structures.toml [building_pad]` and the pad constraint generator; v1: a pad-seat mechanism round measured on HECA.
* **MODEL: Fable approved for implementation lanes too** (higher success rate); the agent guard stays as it is.
* **2026-09-03i (owner, generalises 03h):** SENIORITY FOLLOWS FROM BEING GOVERNED. Anything NOT covered by a grade law yields to everything that is — pads yield because no grade law governs a pad, not because a pad-specific rule says so. The precedence table therefore has two tiers by construction: governed surfaces (a cap in the law tables) in their stated order, then everything ungoverned (pads, ungraded ground, walls, strips beyond the zones) which takes its level from what it touches. v2: `law/precedence.toml` states the principle and the loader derives the ungoverned tier from "no cap in rulesets"; a new surface class without a cap is junior by omission, no code change. v1: the R4 pad mechanism is one instance.

## 2026-09-03j — v2 M1 merged; three intent questions settled by the spawner (owner may override)

* **M1 bar re-based.** v1's roles are not the truth (they are minted by `junction_repair`'s apron re-role, the road carve and the flat `junction` register — mechanisms v2 lacks by design); M1 reports role agreement (48 % exact / 71 % law-family at CYXY) and the LAW bar is the census on M2's output. Every disagreement stays listed in `m1-report.md`.
* **apt.dat source = the ENABLED pack's** (custom pack when present, Global Airports otherwise) — the scenery-signature ruling (apt.dat + DSF of the active pack).
* **Stand lanes and 1202 edges inside an apron pavement with no pavement of their own are APRON** (the free-road analogue: roads inside an apron ARE the apron); taxi law applies only where a taxiway pavement or an authored taxiway exists.
* **DEM frame = production's**: v2 reads the same smoothed tile DEM + insets the mesh will drape on (read-only through the harness resolution), never raw hgt — a patch solved on a different DEM cannot match the terrain.

## 2026-09-03k — R4 arms 1–2 PARKED; the residual is between two GOVERNED surfaces (owner question)

* Arm 1 (`lane/r4padyield` c0eccc76: pads freed at pass-2/fp#8/FGP) 1,069 → 1,182; arm 2 (`lane/r4padyield2` 33f387a4: attached pads never hard anywhere in the solve, one derivation `apron_attached_pad_groups`) 1,069 → **1,140**, runway/tunnel/bridge/basin movers 0, cert residuals 1,985 → 1,780, groundside 1,742 → 1,671, pass-2 rows 1,510 → 797 (gap 4.34 → 4.01 m) — but the R1.3 steps did not move (2.91 → 2.93 m; 3.75 → 3.64 m). With the pad out of every anchor the pass-2 set is STILL proven infeasible: the contradiction is between tier-1/2 constants — runway values and taxiway-family/junction ring vertices (plus DEM-demoted/backfilled ring vertices, the R1.4 follow-up) — on both sides of an apron across 4–10 m of real relief under the apron's 1 % law. Both sides are GOVERNED, so 03i does not decide it.
* **OWNER QUESTION (arm 3 would be intent, not mechanism):** where an apron cannot span real relief between two taxiway-family constants at 1 %, does the apron (a) DECLARE A TERRACE (a lawful joint — the census already has the terrace families; 08-06 forbids joints across roads, 08-24 forbids plateaus), or (b) release the taxiway-family ring vertices to the apron membrane over relief (taxiways yield locally to the apron's cap), or (c) accept these rows as true geometry and exclude them from the zero bar? v2's apron/pad generators need the same answer before M3 (SPJC's 369 pad↔pavement rows).

## 2026-09-04a — v2 M2 merged (CYXY lawful to within the oracle's own artefacts)

* `lane/v2m2` 8a4d5d56 merged: CYXY end to end in **3.2 s** (v1 41.5 s): 220,371-row LP, 9,329 columns, OPTIMAL, residual ≤ 1e-12. **v1's census on v2's patch: 33 rows** (v1's own patch 160): transverse 72→0, airside_no_step 24→0, road_cross_section 23→0, lattice 12→0, runway_crown 7→0, skirt 3→0; residual raoa 29 (the oracle sorts every strip vertex in the 120 m RAOA rectangle by station and prices cross-width neighbours 4 cm apart as one profile — an instrument reading, not a surface; v2 binds along the approach), within_shape 3 (apron chords 1.02–1.09 %), strip_seam_tear 1. Mesh +60-136 (one run each): input segments 108,708 → 105,420, constrained edges 247,315 → 243,088, step 1 39.4 → 34.8 s, step 2 9.3 → 8.8 s.
* Spawner rulings on M2's deviations: the additive `Linear` row kind and `ring_vertices` are accepted into the frozen API; the law tables' new `[transect]`, `[within_shape]`, `[instrument]` sections are accepted AS DATA (the census's rounding envelopes belong beside the caps they qualify) — the owner may strike them; binding rate/strip rows in the reader's frame is accepted until the tabled laws are reconciled at chord scale (an Appendix-A follow-up).
* OWED: M1's synthetic `.hgt` fixtures were never committed (11 errors + 2 failures under tests/auto_patch_v2 on main) — M3 repairs first; RAOA oracle reading to be adjudicated (v1 instrument or v2 surface); crown declaration on non-runway vertices; `--runs 3` before the mesh bar is called met.

## 2026-09-04b — v2 M3a merged: SPLP zero; two instrument/table corrections

* `lane/v2m3a` cf37ed6a merged. SPLP end to end **6.8 s** (v1 9.5 s); v1 census on v2's SPLP patch **27 airside → 0** (strip_arc 17→0, road_cross_section 8→0, strip_longitudinal 4→0, runway rings 3→0, junction 1→0, no_step 1→0); tile straddle emitted as per-tile pieces with seam DEM values as PREFERENCE rows (tiers seam > end_zone > crown — RATIFIED by the spawner). v2 now solves on production's DEM frame (the core's `compose_tile_dem_from_disk`, read-only, guard armed; CYXY census 33 = 33 on the frame change). M1's uncommitted `.hgt` fixtures restored (78 tests green). Mesh medians of 3, v1 → v2 constrained edges: −13-077 288,810 → 288,047, −13-078 149,413 → 147,269, +60-136 247,315 → 243,088; step 1/2 no slower.
* **INSTRUMENT CORRECTION (91426d6c, taken):** `check_grade`'s RAOA reader sorted every strip vertex in the 120 m rectangle by station and priced cross-width neighbours as one profile — 28/28 CYXY and 6/6 SPLP over-cap triples had a hop more across than along. Fixed with a twin; CYXY v2 census 33 → 2. v1's own RAOA counts drop with it (an instrument correction, like air1: zero patch bytes change).
* **LAW TABLE:** ICAO code-4 runway longitudinal set to **1.5 %** (owner 2026-07-08: 1.5 % is the law; the census prices 1.5 %; Annex 14's 1.25 % is recorded in the key's comment). SPLP's CIFP thresholds imply 1.255 % over the pinned chain, so 1.25 % was a proven IIS. The law twin carries a RULED-DEVIATIONS register so this is the only tolerated drift from v1's ruleset table.
* Remaining at CYXY: strip_seam_tear 2; at SPLP: v2-verify within_shape 1 (oracle 0), −13-078 piece runway_crown 5 (piece-census artefact — open). M3b (SPJC) proceeds on everything except the pad↔pavement class, which waits on 03k.

## 2026-09-04c — v2 M3b merged: SPJC to 1 row; the pad class measured for 03k

* `lane/v2m3b` dd25a4b7 merged. SPJC end to end **13.0 s** (v1 166.2 s): 407 faces, 9,128 vertices, 0 T-vertices; LP 824,216 rows / 20,105 columns / 1.68 M nnz, OPTIMAL in 6.0 s. **v1's census on v2's patch: 1 row** (v1's own: 686 / 596 airside): `plane_gradient` groundside on a 3-vertex sliver whose 0.5 m edge makes the 0.01 m elevation quantum a 2 % grade — an emit-quantisation artefact (open: dissolve identity-spacing slivers at planar build). Mesh −13-078 (3 runs): constrained edges 149,413 → 133,351, triangles 358,546 → 327,898, step 1 16.76 → 16.36 s.
* **DEFECT FOUND (v2 reader, also worth checking in v1's `dsf_reader`):** the DSF facade winding parser read the control point from columns 2–3; with `cpp = 5` the layout is `lon lat wall ctrl_lon ctrl_lat` — one `Cargo_Terminal.fac` winding became a 707,000 km² polygon and swallowed 128 pads. Fixed with a twin.
* Mechanisms landed as law-from-tables: mixed-pad groundside cut-back 0.6 m (09-01g/i), near-miss frontage levelling (08-08; RATIFIED by the spawner as the 03h reading), lateral contiguity per station (08-02/08-28) with `station_caps` published.
* **03k DECISION INPUT (measured, no arm):** with the 5,350 pad↔pavement no-step pairs added, SPJC solves OPTIMAL with NO IIS — the class contradicts no governed surface there: 20/53 pads re-level > 0.5 m (max 8.16 m), apron 358 vertices > 0.5 m (max 2.44), taxi family ≤ 0.88 m at 313 vertices, all within caps, **runways 0 (max 0.17 m)**. So at SPJC option (b) "taxiways yield locally" costs nothing unlawful; option (a) would mint up to 36 joints (7 fronting a service road, forbidden by 08-06); option (c) excludes ~344 rows. HECA's straddled constants remain the case where (b) can be an IIS.
* **Tunnel at SPJC is REAL** (OSM −2525/−641 `highway=trunk tunnel=yes`, 1,260 m under 16R/34L and the parallel; mouths at −12.00874/−77.12730 and −12.01997/−77.12940) — the M4 prototype; v1's "vetoed" tunnels were other ways.

## 2026-09-04d — v2 M4 merged: tunnels and terrain decks at OTHH/LEMD

* `lane/v2m4` 99ffd3e9 merged. OTHH **27.7 s** (v1 434 s; 8 tunnels of 18 mouths; LP 2.48 M rows / 50,307 cols), LEMD **25.4 s** (v1 574 s; 19 tunnels of 58 mouths, 1 terrain deck), SPJC 12.2 s (2 tunnels). Owner's OTHH sites: wall 3.96 / ramp mouth −1.14 (5.1 m by construction, DEM inset 3.96), no road shape outside the wall. Tunnel acceptance v1 → v2: OTHH canonical 9/10 → 8/8, ramp_wall_gap 23 → 0, wall_top_flat 3.45 → 0.00, over_cap_ramp 136 → 0; LEMD ramp_wall_gap 14 → 0, wall_top_flat 3.07 → 1.42. Census: OTHH 2 airside (identical on a no-structure control), SPJC 1 (groundside sliver), LEMD 2,197 of which `runway_crown` 2,185 is a v2 runway-family class present on the control arm (owned by the next lane, not M4). Mesh +25+051 (3 runs): input segments −2.8 %, triangles 753,661 → 727,321, step 2 162 → 147 s, step 1 within noise.
* 30l consumer table for the structure shape class RULED as the lane wrote it (structures cut pavement, never the runway family or pads; zone keep-out at the wall; ramp is its own class; wall vertex shared with governed ground takes that ground's value, bare = DEM — the GROUND RULE, ratified by the spawner; owner may refuse).
* Refusals are loud and listed (OTHH −8342 both mouths against a pad; LEMD 22: 11 against pads, 5 overlapping corridors at the T4 portal complex, 4 self-intersecting bends, 2 no DEM reach) — no tunnel is forced. Seven IIS-named mechanisms fixed on the way (report §7).
* OWED: basins/pits and hard-deck OBJECT decks (v2 lacks an OBJ8 solid-depth / deck-top reader); LEMD `runway_crown` 2,185 (crown declaration on non-runway vertices, M2 open question — its own lane); mouth datum tied to the solved cap vs DEM sample; transitive dual-carriageway merge; CYXY/SPLP re-census.

## 2026-09-04e — LEMD crown class attributed to a planar-map defect; five-airport re-census on main

* `lane/v2crown` 76ddf325 merged. LEMD's 2,185 `runway_crown` rows: the two 142° runways carried NO `runway_profile` breakline — `planar/build.py::_breaklines` snapped lines with `set_precision(grid)` (a 0.5 m precision model stays on the geometry) and the subsequent `buffer(0.3)` snap-rounded any off-axis ribbon to an EMPTY polygon, so the STRtree matched nothing and the source line was dropped (axis-aligned lines survived). Fix: snap, then clear the precision model, query with `dwithin`. General class — every diagonal centreline everywhere (CYXY breaklines 61 → 75, LEMD 531 → 630). LEMD census 2,198 → **14** (plane_gradient 13, seam tear 1).
* Five-airport re-census on main (v2, production DEM, oracle census, single runs): **CYXY 4.5 s 1/1 (seam tear 2.16 m) · SPLP 7.3 s 0/0 PASS · SPJC 12.3 s 1/0 (groundside sliver) · OTHH 27.5 s 2/2 · LEMD 27.0 s 14/13** (v1: 160 / 35 / 686 / 1,620 / —). Remaining v2 residual classes on the five: strip_seam_tear (3 rows across three airports), plane_gradient slivers/junctions (15), v2-only tunnel readers at LEMD (wall_top_flat 63, mouth canonical 8).
* OWED: 740 source edges still unmatched at LEMD (7 single-chord taxi centrelines, 33 zero-length road routes, chords through 122 dropped faces); crown declaration gap on shared taxi vertices (M2 Q3); a `build_airport.py --engine v2` harness entry so v2 builds ledger like v1's.

## 2026-09-04f — v2 M4b merged: basins from OBJ8; object decks twinned only

* `lane/v2basins` fe0272c0 merged. OBJ8 reader resolves every OTHH placement (11,902; 1,366 files, 11.3 s) and all but one at LEMD. OTHH emits Dewatering_02 (floor −10.74) and Dewatering_01 (−9.06) with `retaining_wall` crest 3.96; `basin_floor_declaration` 0; airside rows added 0 at OTHH and LEMD. Hard-deck OBJECT bridges: none found at OTHH or LEMD (OTHH's `Bridge_0x` carry no `ATTR_hard*`) — the object-bridge law is twinned, unexercised (KCLT/EGLL arm at M5).
* Mechanism vs 08-26's letter: depth is judged against the LOCAL terrain under each solid component and a shell must reach grade — the authored-plane reading minted 75 phantom regions on the v1-rebaked LEMD pack on disk. Constants unchanged (8 cross-checked); one NEW table value `max_covered_fraction = 0.5` (ruled deviation in the twin) — owner to ratify.
* Refused, listed: OTHH Drainage_01–06 (54–544 m² below `min_area_m2`); LEMD old-terminal basement (32,542 m², 51 % covered). LEMD invariant: floor 587.76 reproduced from the `.anchor_bak` witness; G 596.682 superseded by the owner's 600.51 seat; the pack on disk is v1-rebaked (1,517 `.anchor_bak` files) and the production DEM already carries the pack's own pit as an inset.
* OWNER QUESTIONS: (1) which pack state v2 reads — on-disk (v1-rebaked) or restore-before-read; (2) a structure-level admission for OTHH's drainage bowls; (3) `max_covered_fraction` 0.5. OWED: OBJ8 parse cache (build +8 s at OTHH/LEMD).

## 2026-09-04g — v2 reaches ZERO on all five first-milestone airports, through the harness

* `lane/v2resid` 80931774 merged. `tools/harness/build_airport.py ICAO --engine v2` runs v2 under v1's refusals, guard, DEM-frame checks, run + artifact ledgers; `frame.json` records `engine` and the law-table digest; v1 ledger keys byte-identical (twinned). Oracle census (adjudicated/airside), ledgered: **CYXY 0/0 (c23880b3e574) · SPLP 0/0 (a4a3758be45b) · SPJC 0/0 (0a79668a0b63) · OTHH 0/0 (42a253005ec9) · LEMD 0/0 (4d96b4d41c41)**. Timing (3 foreground runs, no ledger): CYXY 4.3 s, SPLP 7.3 s; single runs SPJC 12.8, OTHH 28.9, LEMD 30.5 s.
* The last three `strip_seam_tear` rows were generator defects, fixed at their sites: a zone-1 vertex shared with groundside pavement exempt from the band (the 08-30 "a shape boundary is not an exemption" defect); the pocket-rule ceiling switching reference at a corridor's outer edge; an end-lip ring with no along-axis rows (5 % end-skirt as chords). `plane_gradient` (15 rows, zero patch bytes) was the instrument pricing the 0.01 m quantum on ≤ 0.5 m edges; both readers now carry the quantum allowance and judge an undeclared crown vertex over [0, max declared] — v1 controls: CYXY 157 = 157, HECA 2,811 → 2,809 (instrument correction, separate commit 6bf0cc52).
* v2-verify-only residuals: LEMD tunnel readers (wall_top_flat 63, mouth canonical 8 — M4's outward-descending ramps); SPLP within_shape 3 (oracle 0, unattributed). OWED: mesh bar on the final patches (`--runs 3`); OBJ8 parse cache; the app's engine selection (v1 ships until the owner's sim read of v2).
* OPEN (owner): pocket-rule equidistant ridge (blend?); groundside ring vertices now carry the 3–5 % lip with roads exempt (vs 08-30's geometric cut-back).

## 2026-09-04h — v2 selectable in the app and tile builds

* `lane/v2app` 68ddf524 merged. `auto_patch_engine` (`v1` default | `v2`) in the settings registry, per-tile override honoured, picker in the app's Elevation settings; the driver dispatches per task, v2 runs on the worker's own composed tile DEM (never re-composed), writes `Patches/<block>/<tile>/<ICAO>_auto.patch.osm` + sidecar (straddler pieces per tile), provenance `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=optimal dem=production[…]`, verify rows into the tile's debug log; a non-optimal solve is a named `solve` failure with the IIS, a refusal a `build` failure — never a silent skip. Freshness stamp `o4_ap_engine` (schema 2): flipping the key rebuilds. The freeze bundles `auto_patch_v2` + its TOML law files and refuses to freeze without them.
* Closing tile `build_airport.py OTHH --tile 25 51 --engine v2`: OTBD/OTBH/OTHH all optimal, OTHH v2 patch oracle census **0/0**, mesh step 146 s (280,722 constrained edges, 752,691 triangles). rc 1 from the MASKS step's `N25E051_bathymetry_band/index.json.part` write into the shared repo (guard refusal; pre-existing class also seen 2026-08-12 on v1) — chip filed.
* SIM-GUIDE top section "Reading v2 patches from the app": set `auto_patch_engine = v2`, rebuild +25+051 and +60-136, A/B by flipping the key.

## 2026-09-04i — Owner rulings answering 03k / 04f (v2 law)

* **03k → PRIORITY IS THE LAW'S, TERRAIN NEVER BLOCKS.** The DEM is not always reliable. A feasible solution exists for every airport. ALL pavement must comply with the law, and pavement always overrides terrain when needed. When two governed surfaces contradict across relief, the LAW's priority order (`precedence.toml`) decides which yields — the junior governed surface yields to the senior (taxiways yield to runways, aprons to taxiways, …), and the DEM preference yields to every governed surface. No terrace minting, no "accept as geometry". v2: DEM rows are preferences only, never constraints that can make the set infeasible; the solver's tiers follow the precedence order. Unblocks M5 (HECA/KCLT).
* **04f-1 → RESTORE AND RE-BAKE EVERY BUILD.** Every build that generates a new patch restores the scenery pack's objects to their authored state before reading, and re-bakes them against the newly created terrain — otherwise the objects would not comply with the terrain the patch produced. v2 reads the RESTORED pack, never the previously re-baked state on disk; the re-bake is a product of every v2 build (the v1 `.anchor_bak` restore + post-mesh rebake machinery is the reference).
* **04f-2/3 → BELOW-GRADE OBJECTS GET THEIR CUTOUTS.** The terrain cutouts for below-grade objects like OTHH's drainage must be created correctly for every airport; an area floor or covered-fraction constant that refuses a real drainage bowl is a defect, not a law. Admission is by the object's own geometry (a closed below-grade region with a genuine solid floor), and every refusal names its reason.
* **04g-1 / 04g-2 / 04d → SIM CHECK**, with locations supplied by the session (below in STATUS).

## 2026-09-04j — Owner sim read of v2 at CYXY (app 1.0.279): classification law

* Owner: "patch built very fast, a very strong first result." Four items, all CLASSIFICATION: (1) shapeID 69 and (2) 161 each combine service roads AND parking lots into one face graded at 1 % — the law is **roads ≤ 8 %, PARKING LOTS ≤ 5 %** (a class of its own), and faces must be CUT at the road-to-lot mouths; (3) shapeID 127 merges an apron with service roads and lots and applies 1 % to all of it — apron is never merged with groundside; (4) shapeIDs 230/231 are APRON (not groundside), 227/229 are TAXIWAY. v2: `parking_lot` joins the roles and the law tables (5 %); the classifier separates lots from roads at the mouths and never dissolves apron into groundside; the evidence (apt.dat surface/roles, 1206 routes, OSM `amenity=parking` / `highway=service`, pack pavement pages) is recorded per face.

## 2026-09-04k — v2 restore/re-bake merged measured-only; the bridge datum gap

* `lane/v2rebake` 5890bfa0 merged. Premise corrected: v1 never rewrites the DSF — `object_rebake.apply` rewrites OBJ8 vertex `y` in place with `.anchor_bak` backups and a provenance file. v2 now READS every placement from its `.anchor_bak` when present (OTHH: 1,229 of 11,902 restored-for-read, per 04i) and plans/seats a re-bake after the mesh through v1's writer, honouring `modify_custom_airports` and `DSF_OBJECT_REANCHOR` exactly as v1. OTHH closing tile: plan 93 units / 1,083 members; 13 would seat, 79 below the 1.0 m threshold, 1 held, **0 written** — because v2's feet law would seat Bridge_02/03/06 at +5.585 m against the +0.958 m the owner accepted in the sim (R12): OTHH's `Bridge_0x` carry no `ATTR_hard_deck`, so v2's deck law has nothing to govern, and a shared-anchor family (TerminalRoads_03) would be founded by one small below-datum piece. Writing a known regression was refused; the write path is proven by twins (idempotent, backups never overwritten, restore round-trips).
* OWED (spawner-ruled, lane `v2deck`): a DECK SIGNATURE for un-flagged bridge objects — the R12 seats at OTHH are the acceptance (v2 seat = v1 accepted seat within 0.1 m per bridge) — plus a founding-member witness floor for shared-anchor families and basin-family exclusion. The plan stage (16.7 s at OTHH) needs the optimisation review.

## 2026-09-04l — v2 cutouts merged: OTHH's drainage admitted by geometry

* `lane/v2cutouts` 7e732300 merged. Admission = a thickness-gated floor plate ≥ 2.5 m under the LOCAL ground whose shell tops out in the contact band; region = the witnesses' footprint below ground, closed at 2 m; cover reported, a basement (floor wholly under the same object's own above-grade solid) → the building's pad; `min_area_m2` / `max_covered_fraction` are diagnostics only. OTHH (40.8 s): TEN basins — Drainage_06 ×3 (−1.74; 25.252755,51.626279 / 25.253662,51.624418 / 25.253509,51.623991), Drainage_03 (−1.35; 25.291944,51.605865), _01 (25.295672,51.604575), _02 (25.296327,51.606389), _04 (25.253708,51.622961), _05 (25.253917,51.622124), Dewatering_01 (−10.68; 25.295698,51.603557), Dewatering_02 (−10.68; 25.252080,51.624597); rim 3.96 everywhere. Oracle census 0/0 at OTHH and LEMD; acceptance 8/8. LEMD: 0 basins, 67 refusals named (skirts, shells through grade, 3 basements → pads).
* OWNER SIM SITES: the ten OTHH coordinates above (rim level with the ground, walls at 3.96, floors as listed).

## 2026-09-04m — v2 classification round merged; shape 230 ruled apron

* `lane/v2class` 70ea5c2a merged (4e2f1491). Root causes: the pavement union dissolved source boundaries (now `classify/sources.py` reads every apt.dat 110 / DSF page once as road STRIP / parking LOT / open, cut at its own boundary = the mouth); OSM `highway=service` was not evidence (now is; `amenity=parking` / `parking_aisle` readers added, idle on this corpus — feed query widening is a `--refresh-data`); the runway chain ignored the 1202 network (`Chain.runway_network`). New role `parking_lot` (5 % longitudinal / 2 % transverse, groundside, last in order) emitted as `role=groundside_pavement class=parking_lot o4_grade_law_cap=0.05` so the oracle prices exactly 5 %. Airside zone bands cut back 0.6 m from groundside pavement. Owner's shapes: 69 → 13 lots + 2 strips; 161 → service_road; 127 → apron + service_road ×3 + lot; 227 junction, 229 cross_connector, 231 apron. Census 0/0 at CYXY (7.5 s), SPLP, SPJC; v1 role agreement 48.1 → 53.6 % exact. `python -m auto_patch_v2 explain ICAO --shape N | --at LAT,LON` prints role + evidence (INDEX row).
* **SHAPE 230 = APRON (owner).** The 50 m proximity `junction` band does NOT extend onto an apron page a taxiway merely ENDS on; the band stops at the apron page boundary. (Lane's residual, ruled by the owner; the next classification pass applies it as a rule.)
* Open: lot transverse 2 % registered but unpriced (no axis) — record only for now.

## 2026-09-04n — v2 deck signature merged: re-bake seats OTHH's bridges where the owner accepted them

* `lane/v2deck` 6b8a79a5 merged. Deck signature by geometry (`airport/deck_signature.py`, `[bridge]` table): the family's largest-area near-horizontal plane ≥ 2.0 m above its lowest feet and ≥ 200 m², carried by a mapped `bridge≠no` way along ≥ 50 % of a plate or by an emitted below-grade region; `ATTR_hard_deck` stays primary. Seat law: deck top at the abutment grade (R12), water never founds, witness floor 8 / 25 % of the largest member, one delta per family, basin families excluded whole. OTHH seats v2 vs accepted: Bridge_01 +4.186 vs +4.159; 02/03/06 +0.9576 = +0.9576; Bridge_04 +2.994 vs the R12 in-sim pin +2.983 (disk +2.567 is a later v1 re-bake); Bridge_05 +1.731 vs +1.645; BusStation −0.102 unchanged. Lane-local pack write: 502 resources, second run byte-identical, restore round-trips; the real pack untouched. Census 0/0; acceptance 8/8. A candidate mechanism (promoting plates crossing tunnel corridors) lost four OTHH tunnels and was DELETED (29f).
* OWNER (sim): Bridge_04 datum — disk +2.567 or the R12 pin +2.983 (v2 +2.994)? The interchange's accepted +0.9576 buries Bridge_06's ramp feet ~3 m (v2 reproduces v1's coalition; physics says ≈ +3.96). TerminalRoads (367 objects, one anchor) is not one rigid body.

## 2026-09-04o — Owner ruling: feasibility propagates along TAXI ROUTES from the runway thresholds, never along straight chords

* "Feasible elevations propagate out from runway thresholds and have to follow taxi routes … an apron very close laterally to the centre of a runway could have a big elevation difference because aircraft can't travel straight across the grass; they have to follow taxi routes, which is what follows the grade cap." The distance that prices a grade between two airside vertices is the ROUTE distance through pavement along the taxi network (v1's route-metric reach band, `building_feasibility.reach_band_unified`; memory `reach-follows-centerlines`), never the plan chord. This CLARIFIES 2026-08-27 (airside no-step): the no-step law forbids STEPS — pairs adjacent along pavement — and its 150 m / K=16 direct-distance window must not bind pairs whose only connection is across grass. v2: `constraints/no_step.py` pairs are formed along pavement (route distance through the planar map's pavement faces / taxi network, or adjacency only), and the census family reads the same population; v1's constants (window 150 m, K 16) are re-derived as route distances or retired. Measured trigger: CYXY apron shape 156 held 3.4–4.7 m under the lidar terrain by direct chords to runway vertices while its route to the runway is ~250 m at 1.5 %.
* Also ruled: a service road that can lawfully follow the terrain (CYXY shape 153, 2.6 % on 1 m lidar) is a question of intent — the owner will say whether roads seek level; until then roads follow terrain within their cap.

## 2026-09-04p — v2 M5 merged: law-ordered yielding; HECA proves the chord no-step law wrong

* `lane/v2law2` f8dabb8c merged. Tiers derived from `precedence.toml` (runway family never soft → taxi → tunnel_ramp → apron → service_road → service_junction → groundside → ungoverned/rigid); hard solve first; on infeasibility the junior tiers from k_min down become preference rows (`solve/tiers.py`, bisection over k_min, IIS only when even k=1 fails). Pad↔pavement no-step pairs bound (`pad_pavement_no_step_edges`). SPJC 0/0 (19.5 s, hard set feasible); KCLT 58/48 first build (169 s; junction within_shape ≤ 0.64 m, tunnel-site strip tears — not M5's class); **HECA: hard set INFEASIBLE under the 08-27 chord no-step law** (05C/23C thresholds 116.4/114.3 vs 05L/23R 57.9/60.7, parallel runways 2.8 km apart = 2 % real relief; the 150 m chord membrane climbs ≤ 43 m at 1.5 %) → k=1 (runways alone hard) OPTIMAL in 1,242 s, total 1,621 s, oracle 4,364/4,285 airside, runways bent up to 14.1 m to spare junior rows. This is the measured case for 04o: with ROUTE-distance pairs the hard set is predicted feasible and no tier yields. Mesh +30+031 (3 runs): constrained edges 581,124 → 475,273, step 2 63 → 56.4 s.
* Open (owner, after 04o lands): whether a senior surface's DEM fidelity outranks junior law rows (runways bent 14 m at HECA under demotion); how the census counts rows once a tier lawfully yielded; yield spread (L1 concentrates: one 1.7 km stub carried 25.6 m).

## 2026-09-04q — `why` merged; CYXY apron 156 attributed; two consequent rulings (spawner, under 04o)

* `lane/v2why` a91dc91b merged: `python -m auto_patch_v2 why ICAO --shape N | --at LAT,LON` rebuilds the LP and prints per-vertex z/DEM, the ACTIVE rows (family, cap × distance, other endpoint, dual), a chain trace to the nearest hard pin, and relax-one-family re-solves. CYXY 156: chain apron → junction 103 (no_step 1 % × 149.9 m = +1.50) → primary_parallel 6 (+0.51) → runway edge (taxi 1.5 % × 125 m = +1.88) → runway 02 CIFP pin 694.33; the no-step CHORD is the limiter (relax → +2.78 m); the next limiter is junction 103, minted letter-less by the route-proximity cut and priced at 1.5 % over 222 m while taxiway G is 1202 code A (3 %). Shape 153 follows the terrain exactly (2.6 % of a 1 m lidar slope).
* **RULED (04o applied):** (1) a no-step pair is priced at the cap of the TRAVEL PATH between its endpoints over the ROUTE distance — an apron↔taxiway pair carries the taxiway's cap along the taxi route, never the apron's 1 % over a chord; (2) a junction face minted by route proximity inherits the code letter (and cap) of the taxi chain(s) it serves; (3) `solve/` must not import `constraints/` — the tier derivation moves into `law/` (tables) and the vertex-ownership view into `model/`.

## 2026-09-04s — pad pairs through the contact merged; HECA's last infeasibility is a hangar row (owner questions)

* `lane/v2padroute` 778cbe7d merged. Pad↔pavement pairs exist only from a pad's contact vertices along pavement (HECA 117,119 → 108,293 pairs; the 1,181 tier-8 pad rows no longer exist as a population). KCLT: hard set FEASIBLE, no yield, 71.6 s (M5 168.5), census 70/44 (the 8.75 m tunnel-site strip tear gone; 33 airside `junction|junction` rows at the oracle's 1.0 %). HECA: still infeasible → k_min 3 (apron yields 175 rows ≤ 0.443 m), 241 s, census 84/84. **HECA IIS (24 rows, ONE site):** apron face 340 `pav132`, the hangar row 30.1368 → 30.1280 N (DEM 69.3 → 84.7 m over ~1 km): eight FLAT pad groups (building 359/350/339/328/323/311/300/343) whose contacts consume the rim, the apron's 1 % chords between them, and the reach bands at both ends ([62.57, 68.12] north, [73.28, 78.94] south) — the apron can climb Σ(1 % × gaps) ≈ 4.9 m, the routes need ≥ 5.16 m, the terrain climbs 15.4 m. All three populations lawful (03h flat pads, 08-21 apron 1 %, 04o routes).
* SPJC 0/0 → 8/8 and KCLT's 33 airside rows are ONE reader disagreement: v2 solves a junction at its inherited letter (04q-2, 1.5 %) while the oracle prices a junction sharing an apron edge at the APRON cap (owner 2026-07-06, `grade_graph._body_cap_unbounded`). One line on whichever side the owner rules returns SPJC to 0/0.
* **OWNER QUESTIONS:** (1) hangar row over relief — terrace between pads (each pad flat at its own level, the apron stepping at declared joints), or let a pad's contact SLOPE along its frontage, or accept the ≤ 0.44 m apron yield under 04i; (2) a junction sharing an apron edge: the apron's 1 % (07-06) or its taxi chains' letter (04q-2); (3) junction letter when serving chains differ: strictest (ruled) or per-stretch. OWED: `why` in tiered mode for infeasible hard sets; the near-coincident-rim planar class (HECA mid_edge_step 23).

## 2026-09-04t — Owner rulings answering 04s (four)

* **(1) LAST RESORT = LEAST TOTAL VARIANCE FROM LAW.** Where the hard set is infeasible at a site (HECA's hangar row), the solver may relax ALL THREE populations together — a slightly over-cap apron, a slightly sloping pad contact, a slightly over-cap slope between buildings (never a cliff/terrace) — choosing the combination that minimises the TOTAL variance from law (a quadratic spread across the IIS rows, not L1's concentration on one row), and only for the rows an IIS names. No terrace minting.
* **(2) CAP BY EDGE PORTION.** A junction or road MOUTH joining or leaving an apron keeps the junction's / road's own cap; a junction or road sharing a LONG EDGE with an apron takes the stricter (apron) cap only on the portion ALONG the apron; portions that leave the apron return to their normal cap. Refines owner 2026-07-06 (v1 `_body_cap_unbounded` applied the apron cap to the whole junction body) — the oracle reader follows the same portion rule.
* **(3) TAXIWAY CAP CHANGES AT CENTRELINE INTERSECTIONS.** A taxiway's letter (cap) applies from its intersection with another taxiway onward, per stretch — at CYXY, taxiway G's 3 % begins at its intersection with E (60.7079446, −135.0697651): the next G node (60.7078279, −135.0704243) may already differ by 3 %. Junction faces carry the cap of the stretch they belong to; strictest-of-chains (04q-2) is superseded.
* **(4) ROADS: THE CORE SMOOTHS FIRST.** Ortho4XP's own road smoothing (`include_roads` / `clamp_road_network`, RULINGS 2026-08-31 "leverage the core") is applied to road profiles FIRST; v2 adds smoothing only where a road is still over its cap afterwards. A road following a lawful 2.6 % terrain slope (CYXY 153) is therefore the core's smoothed profile, not v2's DEM preference.

## 2026-09-04u — Owner sim read of v2 at CYXY, round 3 (app 1.0.281: "looking really good")

* **Weld gap** at 60.7081013,−135.0771456: cross_connector 101 (pav18) and 208 (pav5) share vertex −2366 at 703.12, but junction 211 (pav5) runs 0.47 m from it with no shared edge — a grass sliver narrower than the identity spacing (0.5 m) survived the planar overlay and the mesh drapes it as a cliff. LAW: two pavement faces whose boundaries lie within the identity spacing of each other WELD (shared edge/vertices) at planar build; no sliver of unowned ground may exist between pavements. Same class as HECA's near-coincident rim (04s).
* **Shape 106** (dsf:pol17 + pol20 + pol123) is NOT apron: groundside parking lots served only by the service road that connects from the apron at 60.7122971,−135.0745001 up to the lot at 60.7125394,−135.0752877 (1206 route 50 / routes 4–6). Classifier defects: an "open" page with no taxi centreline, no startups and no apron evidence defaulted to APRON (the default is groundside: lot if a road/route reaches it, else groundside pavement); a 1206 route reaching a page counted as 0 m of road. RULED: open pavement is never apron by default — apron needs evidence (stands, taxi centreline, apron name/aeroway, or an apron-named page); a route/road reaching a page is road evidence for it.
* **Parking lot 87**, node at 60.714258,−135.0766894 is WELDED to a building pad and pulled down with it. RULED: groundside pavement (lots, roads) never welds to a building pad — it keeps the 0.6 m setback (09-01i cut-back) on every pad it touches, airside-touching or not, so a pad's level cannot pull groundside down; the pad welds to airside pavement only (03h).

## 2026-09-04w — roads: the core smooths first (merged)

* `lane/v2roads` db57c640 merged. Facts: the core's `include_roads` runs AFTER the patch, only on OSM ways, cut back lane_width+2 = 6 m from the patch/apt area, never on 1206 routes, DSF pages or 110 pavements; its algorithm is `refine_way` ≤ 20 m stations + `cap_lipschitz_profile` at `road_grade_limit` (0.08) with both kerbs levelled to the nearest station within 8 m. v2 now computes that same profile for every road-family vertex (`airport/road_profile.py`: OSM way / route breakline / face axis sources, the core's own function on the production DEM) as `PlanarMap.preferred_z`; the cap rows stay; lots beside no road keep the DEM. CYXY 153: kerbs levelled onto the axis profile, z − profile = 0.000 along 130 m; census 0/0 (`1a01cc4112f2`); SPLP 0, SPJC 8 (v2caps' class, unchanged).

## 2026-09-04x — relaxation merged (04t-1); three spawner rulings

* `lane/v2relax` a9226e96 merged. HARD → RELAX → tiers: on infeasibility a dual-ray IIS (Farkas certificate + QuickXplain, 22 s at HECA vs 73–126 s) names the site; junior rows there (apron chords, pad flats → planes, frontage, no-step) get a squared-excess objective (uniform over-cap, integrated along pavement; `highspy` 1.15.1 QP under `[relaxation] qp_time_budget_s`, else a convex 8-piece PWL, reported as approximation); the relief is fixed into the rows and the normal L1 solve runs; a certificate proves plane residual / shared-vertex step ≤ 0.01 m; the sidecar carries `relaxed_rows` and verify tags them `relaxed_by = 04t(1)`. HECA (`726a0e49cdce`): optimal, no tier demoted, 111 s; 117 relaxed rows, max excess 0.318 % (pad building359 slopes 0.32 % over 145 m, rise 0.46 m), Σ relief 2.95 m; census 84 → **52** (2 relaxed; 14 junction rows = v2caps; 26 rim steps = round 3; 7 seam tears; 3 building slivers). SPJC/KCLT byte-identical to main.
* RULED (spawner): (1) size-gate the QP — skip straight to the PWL above a row-count table value (the 20 s budget is pure waste at HECA's scale); (2) a row relaxed under 04t(1) is LAWFUL last resort: the oracle prices its relaxed cap (reads `relaxed_rows`) and reports it under the heading, never as a violation — an airport with only relaxed rows is at zero; (3) the spread statistic is excess GRADE (uniform over-cap), as implemented.

## 2026-09-04x — relaxation merged (04t-1); three spawner rulings

* `lane/v2relax` a9226e96 merged. HARD → RELAX → tiers: on infeasibility a dual-ray IIS (Farkas certificate + QuickXplain, 22 s at HECA vs 73–126 s) names the site; junior rows there (apron chords, pad flats → planes, frontage, no-step) get a squared-excess objective (uniform over-cap, integrated along pavement; `highspy` 1.15.1 QP under `[relaxation] qp_time_budget_s`, else a convex 8-piece PWL, reported as approximation); the relief is fixed into the rows and the normal L1 solve runs; a certificate proves plane residual / shared-vertex step ≤ 0.01 m; the sidecar carries `relaxed_rows` and verify tags them `relaxed_by = 04t(1)`. HECA (`726a0e49cdce`): optimal, no tier demoted, 111 s; 117 relaxed rows, max excess 0.318 % (pad building359 slopes 0.32 % over 145 m, rise 0.46 m), Σ relief 2.95 m; census 84 → **52** (2 relaxed; 14 junction rows = v2caps; 26 rim steps = round 3; 7 seam tears; 3 building slivers). SPJC/KCLT byte-identical to main.
* RULED (spawner): (1) size-gate the QP — skip straight to the PWL above a row-count table value (the 20 s budget is pure waste at HECA's scale); (2) a row relaxed under 04t(1) is LAWFUL last resort: the oracle prices its relaxed cap (reads `relaxed_rows`) and reports it under the heading, never as a violation — an airport with only relaxed rows is at zero; (3) the spread statistic is excess GRADE (uniform over-cap), as implemented. `highspy` (4.5 MB) is now a venv dependency — verify it is in the next freeze.

## 2026-09-04y — caps by portion/stretch merged; runway 1.5 % for every code; junction body chords

* `lane/v2caps` f2d9896a merged. Stretches: a taxi centreline splits at every vertex shared with another centreline, each stretch carrying ITS chain's letter (CYXY G/E: 3.00 % × 38.3 m at the intersection); a pair on one stretch holds that stretch's cap, any other pair the face's strictest crossing letter. Portions: a shared apron run ≥ 1.5 × the face width is a long edge (apron cap on its pairs), shorter is a mouth (`within_shape.apron_edge_portion_min_width_ratio`); the oracle applies the same portion rule (`check_grade.mark_apron_edge_portions`, `APRON_EDGE_PORTION_MIN_WIDTH_RATIO`; zero deltas on the v1 controls). Attribution: the SPJC/KCLT/HECA `junction|junction cap 1.0` rows were the oracle's FRONTAGE rule (a pad endpoint), not 07-06 — v2 now prices taxi pairs with a pad vertex at the pad cap. SPJC **0/0** (`e8992a9dbdd8`), KCLT **27/0** airside (`e5c4db91e012`; groundside lot residual), OTHH/SPLP/LEMD 0/0 re-censused, CYXY 4/4 runway rows = v2 pricing code-1/2 runways at Annex 14's 2 % against the oracle's 1.5 %.
* **RULED (spawner, owner 07-08 applied to every code):** runway longitudinal = 1.5 % for ALL runways in v2's tables (Annex 14's 2 % for code 1/2 recorded in the key's comment); the law twin's ruled-deviation register carries codes 1/2/4. CYXY returns to 0/0 on the next build.
* **RULED (spawner, 04t-3 applied):** a junction body chord whose endpoints lie on stretches of DIFFERENT letters is not a law edge — v2 prices junction bodies as the oracle does (triangle planes at the stretch cap; centreline chords per stretch), never as all-pairs across letters. CYXY apron 156 (−1.87 m, held by exactly such a chord) rises when this lands (round-3 lane or next).

## 2026-09-04z — round 3 merged; three rulings on its questions

* `lane/v2round3` ebda9df1 merged (04u). Weld pass `planar/weld.py` (junior boundaries within `emit.identity.weld_spacing_m` = 1.0 m move onto the senior's; shared vertices frozen; HECA's 0.554 m rim class covered — mid_edge_step 23 → 16); `classify/open_default.py` (open pavement is apron only on evidence; route reach `_road_reach` = road evidence → lot); groundside set-back on every pad with the snap margin. CYXY 0/0 (`46b61609f57a`); SPLP 0/0; SPJC 8 → 4 (v2caps' class, now merged); HECA mid_edge_step 23 → 16.
* RULED (spawner): (1) an apt.dat pavement DESCRIPTION naming a taxiway ("New Taxiway 2/3", "Aeronaval") IS taxi evidence — such a page is taxi family (junction) even without a 1202 centreline, not a lot (next classification pass); (2) the open-pavement default does not override the `requires_terminal` gate (06-11) — kept; (3) the weld is same-side only by law: an airside/groundside pair within the weld spacing keeps the 0.6 m cut-back and may terrace (09-01i) — never welded.

## 2026-09-05a — junction bodies merged (04y); CYXY apron 156 is at the law's ceiling

* `lane/v2junction` 3f83134e merged. `constraints/junction_mesh.py`: junction faces (`emit.within_shape.junction_mesh_roles`) are priced on the oracle's own Delaunay mesh — each mesh edge at the cap of the stretch nearest its midpoint, each triangle plane at the stretch nearest its centroid (strictest-of-three-edges was refuted on the ruling's own G example), pad endpoints at the pad cap; `taxi_within_shape` keeps only common-stretch pairs; an A↔D chord produces no row anywhere; the oracle reads the sidecar `stretches` and applies the same caps (`_junction_stretch_cap`). CYXY 0/0 (`cff35e459d38`), SPJC 0/0 (`f72e721615af`); HECA stored patch re-censused unchanged (52).
* CYXY apron 156: −1.87 → −1.79 m against the lidar; its chain is now pure law — apron 1 % → no-step 1.5 % × 108 m along the route to junction 100 → junction mesh → the parallel taxiway's own 1.5 % over 299 m → the runway-02 CIFP pin. The terrain there climbs faster than a code-D taxiway may; under 04i (pavement complies, terrain yields) the apron's level is lawful. It rises only if that parallel taxiway carries a lower code letter (its width decides — owner's data) or the runway datum differs.
* Open (lane): a ring edge shared by a junction and a rect taxiway is priced by both readers (stricter binds) — accepted; `service_junction` bodies still all-pairs (roads family).

## 2026-09-05b — taxi-name rule merged inert; "ramp" is an apron name

* `lane/v2taxiname` 05ad0280 merged. The 04z(1) premise is REFUTED by the data: "New Taxiway N" is WED's default description on all 31 CYXY 110 polygons (including the owner-ruled lots pav4/pav29/pav30), so a name is no evidence there — the rule ships with `unauthored_names = ["new taxiway"]` and flips nothing; "Aeronaval" (SPJC pav3) is the naval base's ramp beside "Naval Aviation Ramp", not a taxiway; `dsf:pol64`'s description is a library path. CYXY/SPJC 0/0 unchanged.
* RULED (spawner): `apron_name_tokens = ["apron", "ramp"]` — SPJC names its aprons "Ramp". Seven-airport re-census and app 1.0.282 follow.

## 2026-09-05c — seven-airport re-census on main 7ddf3f5b (after six merges); app 1.0.282

* v2 through the harness: **CYXY 0/0 (6 s) · SPLP 0/0 (10 s) · SPJC 0/0 (54 s) · OTHH 0/0 (74 s)** — the four airports the owner sim-reads are clean. **LEMD FAILS** (rc 1, 96 s): `verify/within.py:105 stretch_pair_caps` KeyError 8521 — a merge interaction (stretches vs the weld pass / seam pieces); the driver would report LEMD as a v2 failure in the app, so DO NOT rebuild +40-004 on v2 until lane `v2integ` lands. **KCLT 27/24 airside** (was 27/0 after caps) and **HECA 67/60** (was 52; 244 s) — regressions from the merge interplay, attributed by `v2integ` (bisect over the merges; 04x-2 oracle reading of `relaxed_rows` and 04x-1 QP gate included).
* App **1.0.282 / engine 1.50.1724** built (85 v2 modules; `highspy` NOT frozen — the relaxation takes its PWL path, by design optional). Good for CYXY/SPLP/SPJC/OTHH sim reads; HECA builds (60 rows, relaxed) but LEMD would fail.

## 2026-09-05d — integration merged; a pad-flatness regression blocks the next app build

* `lane/v2integ` c0dafdc8 merged (3e95e73f). LEMD: `verify/within.py` mapped outer rings only while a taxi centreline entered a face's hole (KeyError 8521) — reads `Patch.xy` now; the oracle prices rect shapes at their stretch caps (`_common_stretch_cap`); LEMD 5/3 (two `structures` pins contradict — tunnel crest vs basin rim — tier 8, open). KCLT: 24 rows = one pad (building26) inside taxiway F's zone 2 that lost an accidental weld to a service road in round 3 and settled 2.14 m; zone bands now reach HOLE members and band a detached pad's level; KCLT 3/0. HECA: +8 from the caps merge (05L reach floor vs the 23C pin over 2.5 km of apron-edge pricing); relaxation freed of reach bands (`envelope_free`, `_law_tier`) but the second certificate LP exceeds the 120 s IIS budget → tiers, 61/54 (attempt cap). Seven-airport table on the branch: CYXY/SPLP/SPJC/OTHH 0/0, LEMD 5/3, KCLT 3/0, HECA 61/54.
* **BLOCKER:** the M5 fixture "apron between two taxiways" now solves the building pad 1.18 m across its ring in the HARD mode — a rigid flat group (03h) no longer holds after the merge interplay (zone bands per vertex on pads / relaxation planes / set-back detaching). Lane `v2padflat` fixes it and adds a `pad_flat` verify check; **no app build until it lands** (a tilted pad would ship sloped buildings).
* Open: HECA IIS budget (raise / cache the certificate); LEMD's tunnel-crest-vs-basin-rim pin contradiction (5.99 m yield) — whose class; KCLT's tier-8 yield under the detached-pad band.

## 2026-09-05e — pad-flat blocker refuted and closed; `pad_flat` verify; app 1.0.283

* `lane/v2padflat` 998a8c47 merged. The red M5 twin was the PINNED-runway fixture in relaxed mode: the 04t(1) last resort made one pad a plane (slope 2.27 %, residual 0) by design; the hard fixture is green and pads are one `Flat` each (`constraints/pads.py:40`). Landed: bands on a detached pad act on the group's single level (the per-vertex form was hard-infeasible on a 100 m pad along a 1.5 % lip — KCLT's class); `verify/pads.py` `pad_flat` (unrelaxed pad spread > elevation materiality, relaxed pad plane residual > relaxation materiality) registered as a DEFECT that fails the airport by name in the driver and the harness. CYXY 0/0 pads 10/10 flat (`bd78e2c034b4`), SPJC 0/0 53/53 (`d7ca6dc04663`), KCLT 143/143.
* OWNER (intent): how much may a relaxed pad slope — `[relaxation] pad_slope_max`; spawner default until ruled: 1 % (a 2.27 % floor is a visible tilt).

## 2026-09-05f — Owner: relaxed pad slope ≤ 1 % (`[relaxation] pad_slope_max = 0.01`)

* A pad relaxed under 04t(1) may slope at most 1 % — ratified as the table value (spawner default confirmed). Owner rebuilding LEMD and HECA on app 1.0.283 for the sim read.

## 2026-09-05g — HECA relaxed without demotion; LEMD hard-feasible; oracle reads relaxed rows

* `lane/v2hecalemd` 2a3df1d4 merged. HECA: the certificate LP with the reach bands over used columns costs 3 s (107–207 s without), cached between rounds and seeded into a neighbourhood certificate (4 hops / 20k rows / 0.3 s); QP size-gated (`qp_max_rows = 100000`); **relaxed-optimal, no tier demoted, 125 s (solve 102), census 24/17** (`4856370d74f8`): 14 rim steps at two sites (round-3 class) + 3 building slivers; 150 relaxed rows under `relaxed_by_04t1`, 0 rows at the relaxed site. LEMD: the IIS named tunnel −5938's crest (616.99) vs basin 22's rim (611.00) on one vertex — `_faces_of` joined every `retaining_wall` to the nearest tunnel by ROLE; now by the tunnel's own ref, plus `precedence.toml [structures] datum_order = ["tunnel", "basin"]` and a `reconcile_datums` pass; **hard feasible, 2/0** (`f4f0491023f4`). CYXY 0/0 unchanged. 04x-2: `check_grade` prices `relaxed_rows` at `cap_after × the solve's own (route) distance`, stamps `out_of_scope = relaxed_by_04t1`.
* OWED (next lane): `[relaxation] pad_slope_max = 0.01` as a table value enforced in stage 1 (HECA's relaxed pad slopes 1.28 % > the ruled 1 %); HECA's 14 rim steps (weld class at two sites); stage 1+2 warm start (96 s of HECA's 102).

## 2026-09-05h — Owner CYXY read on 1.0.283: the weld must INSERT the node, not mint a sliver

* At 60.7081013,−135.0771456 the round-3 weld welded node −2353 (702.34) to cross_connector 101/158 but minted a 3-node sliver face 216 (−3229 → −2353 → −2352) between junction 215's straight edge (which still passes 0.47 m off the node) and that vertex — a tiny cliff edge. RULED (owner): the matching node is INSERTED into shape 215's edge so 215 shares it and the taxiway joins the apron smoothly; no sliver face may be minted. This is the edge-insert form of the weld (05g owed; lane `v2hecaclose` item 2, HECA's 14 rim steps are the same class) — the CYXY coordinate is that lane's second acceptance site.

## 2026-09-05i — v2hecaclose MERGED 74c8b85d; tile cfg is a sparse override (ed4a8812); the owner's "v1" builds

* **Tile cfg layering (chip `claude/intelligent-williams-73e05e`, merged ed4a8812).** The owner's 15:44 app run built +60-136 on v2 and +40-004 / +30+031 / +25+051 on v1 with one intended setting. Cause: `auto_patch_engine` is a TILE-scope row, so with CYXY selected the app wrote `auto_patch_engine=v2` into CYXY's cfg only; the global `Ortho4XP.cfg` never carried the key; and `Tile.read_from_config` opened the tile cfg INSTEAD of the global, so a tile cfg written before the key existed resolved it to the registry default. RULED (spawner, the chip's design): a tile cfg is a SPARSE OVERRIDE — `read_from_config` layers the global cfg then the tile cfg, only the keys each carries; one reader for the CLI, the JSONL session and the parallel children. `[provenance] sha=absent` now carries `version=<O4_Version>` in frozen engines. Twins `tests/test_legacy_cfg_values.py` (8 layering cases). The two `test_auto_patch_engine_dispatch.py` reds (stub `_Res` without `rebake_plan`, since 5890bfa0) fixed in the merge. NOTE for the owner: engine-built tiles write COMPLETE cfgs, so −13-077/−13-078 carry an explicit `auto_patch_engine=v1` that outranks a later global v2 until the override is cleared in the app.
* **Lane v2hecaclose MERGED 74c8b85d** (report `docs/specs/auto-patch-v2/m5j-report.md`). (1) `[relaxation] pad_slope_max = 0.01` (05f) is a TABLE VALUE: stage 1 bounds every relaxed pad's plane to the 1 % disc (32 half-planes), `verify/pads.py` reads a steeper plane as a `pad_flat` DEFECT, the certificate carries the bound — HECA pad 1148 1.28 % → 0.998 %. (2) The weld runs to a FIXED POINT (05h: project + insert repeated per segment, never a vertex twice) — HECA's 14 cross_connector|junction rim steps gone, airside 17 → 3 (the building|building slivers), census 24/17 → **10/3**, relaxed-optimal, no tier demoted, 125.9 s. CYXY 0/0, 5.3 s (`649dc3dfb3a9`; re-built on merged main `656f2a6e1d64`, 0/0): at the owner's site node −2354 is now shared by cross_connector −10171/−10107 and junction −10237/−10238 — every vertex of the remaining 5 m² junction triangle is welded to its neighbours (no T-vertex; 702.22–702.45 across 8 m), so the cliff has no mechanism; whether the sim still shows the seam is the owner's read on 1.0.284. (3) Stage-2 warm start REFUTED and deleted (attempt cap): highspy from stage 1's point 364 s vs scipy cold 61.8 s; the plain 1.35 M-row L1 LP costs ~57 s on its own — HECA's cost is the LP size, not the relaxation. (4) The `test_why` "full-suite-only" red was the session detector counting a concurrent guarded build's `.lock` as an unauthorised write — lock churn excluded (`conftest.is_lock_churn`).
* OWED: SPJC/OTHH/LEMD/KCLT re-census after the weld change (the sweep at app-build time); the 3 HECA building|building slivers; HECA 125 s vs the 60 s gate (LP size — a smaller row set, not a warmer start, is the lever); freeze inclusion of highspy unverified.

## 2026-09-05j — OTHH read on 1.0.284: shape 718; the pack's tunnel wall objects; v1 flat-site path (owner questions OPEN)

* **Shape 718 "gap_interior_ring" (owner: should be apron).** Face 718 is junction pav22; its hole is apron 730 EXACTLY (47/47 nodes shared, all 3.96 m). v2 wrote every face hole as a `gap_interior_ring` way carrying the parent's shapeID, so a coincident duplicate ring sat over the apron and read as the shape's label. RULED (spawner): a hole every edge of which is an edge of some face ring is NOT written (the inner faces constrain it); an uncovered hole (raw-terrain pocket) still ships. 6f196e0e; OTHH 0/0, hole ways 297 → 153; twin `test_emit_holes.py`.
* **Tunnel wall objects (pack updated 2026-09-04; 7 OBJ8 under `Objects/tunnels`, 8 placements, in the DSF).** NO v2 build had seen them: `find_text_dump` picked the dump by NAME and the legacy 07-30 `+25+051.dsf.text` out-sorted the fresh `+25+051.dsf.e9df4ffc.text`. RULED (spawner): the dump is keyed on the DSF path exactly as the engine's cache names it, a dump older than the DSF is REFUSED (`--refresh-data airport_mod_cache`), and the app's driver re-dumps a changed pack through the v1 cache before the v2 build (775676eb, twins in `test_airport_load.py`). With the objects read (OTHH_20260904T174430, 0/0): the basin pass refuses them correctly (walls, no floor plate: "genuine solids reach −18 m … a skirt, not a pit"), and the tunnels are still derived from OSM bores at `bore_datum_m` 5.1 (mouth −1.14 under DEM 3.96). Measured object geometry: walls y −15 → +5 m with a crest plate at +5 m (`tunnel1.obj` −10 → +9.5, plate at +9.5), plan extents 39 m (`tunnel west 1`) to 223 × 250 m; OWNER QUESTION 05j-1: read the objects as THE tunnel authority — footprint/length from the object hull under its placement, floor = the placement seat, crest = the top plate (depth 5 m; 9.5 m for tunnel1), OSM bores only where no object stands? Spec to follow the ruling (structures.toml `[tunnel] source_precedence`).
* **v1 flat-site path (owner asked how v1 kept OTHH/VHHH objects unseated).** Scout finding (Fable, read-only): v1 does NOT derive the datum from object seats — Z0 = mean CIFP threshold elevation (`flat_site.py:161-184`), verdict `flat_candidate` on S1 spread < 5 m ∧ S2 DEM relief ≤ 8 m / slope ≤ 0.15 % (S4 pack seats confirm only); the mechanism is a DEM SUBSTITUTION — a synthetic constant inset at Z0 over pavement∪boundary ⊕ 200 m plus claimed-object clusters within 5 km, 60 m feather (`O4_Airport_Elevation_Insets.overlay_flat_site_insets`), runways stay CIFP-absolute; objects stay unseated only because the pack was authored at Z0 (median 4.00 vs 3.96) and the 1 m re-bake law finds nothing. v2 INHERITS the substitution through the production DEM frame (`dem_production.py` composes the tile DEM with the flat-site bake), so at OTHH v2's DEM preference is already the Z0 plateau; nothing of it is in the law tables or v2's provenance. Candidates for the owner: (a) flat verdict ⇒ hard pin family at the seat datum (contradicts CIFP-absolute 08-25 and "grade law outranks shared datum" 08-27); (b) seat/Z0 datum as a strong PREFERENCE in the LP (the `pref` per-vertex hook), runway law hard, re-bake only what still moves; (c) `[flat_site]` law table (ICAO → Z0, source cifp|pack_seats|metres) as the declared override over a ported detector. Spawner recommendation: (b) + (c), detector ported to `airport/` as a measurement, the substitution moved out of DEM prep into the law. OWNER QUESTION 05j-2.

## 2026-09-05k — Owner RULED 05j-1 and 05j-2

* **05k-1 (tunnel wall objects).** The reading is confirmed: the placement seat is the tunnel FLOOR, the object's top plate is the wall CREST; the objects are the tunnel authority for shape, length and depth wherever one stands (OSM bores only where none does). Spec `docs/specs/auto-patch-v2/tunnel-wall-objects-spec.md`; lane `v2tunnelobj`.
* **05k-2 (flat-site datum).** Options (b) + (c): the flat datum (Z0, CIFP by default, pack seats or declared metres by table) is a LAW PREFERENCE the LP prices (`flat_datum`, below law, above seam), runway pins stay CIFP-absolute, and a `[declared]` table in `law/flat_site.toml` is the ONE declared register (the tile-cfg keys retire). Spec `docs/specs/auto-patch-v2/flat-site-datum-spec.md`; lane `v2flatsite`.

## 2026-09-05l — v2flatsite MERGED f0964074; spec amendment: structure faces take no datum row

* Lane `v2flatsite` delivered 05k-2 (b)+(c): `law/flat_site.toml` ([detector] v1 constants by name, [datum] `flat_datum` preference 5e4 between law and seam, [declared] register), `flat_site_schema.py` (model.py at the 1,000-line law), `airport/flat_site.py` detector port (S1–S4 on the production raster, core-vs-v2 verdict logged), `constraints/flat_site.py` soft z = Z0 rows — ONE preference group PER ROW (the assembler's slack is per group: a shared group was freed wholesale by the 5.1 m tunnel-mouth relief, attempt 1's "≈0 delta" was the DEM fit, not the law), provenance `flat=Z0`, v1 `flat_site_declared*` tile-cfg keys RETIRED and v1's declared readers consult the v2 table. CYXY reads `lidar_credible` (1 m inset pixel; v1's class too), zero rows, patch byte-identical to the main control.
* **Amendment (spec author, 30l one-table rule):** correctly priced, the datum lifted OTHH's tunnel ramps and wall rims 3.7 m toward Z0 (the ramp grade is a cap, not a pin; v2-verify minted `tunnel_wall_top_flat` 2 + `tunnel_mouth_canonical` 1). RULED: a STRUCTURE role's values are its generator's datum, never a site-wide preference's — `precedence.toml` `structure = true` on tunnel_ramp / tunnel_trench / retaining_wall / bridge_trench / bridge_causeway (basin floors and walls emit under the first two), `is_structure_role`, and the generator skips every vertex a structure face touches (the same exclusion form as the runway's). OTHH closing build OTHH_20260904T202545: `flat_candidate` Z0 3.96, 15,428/15,437 rows at Z0 (max off 0.157 m), v2-verify 0, census 0/0, 325/23,800 vertices moved vs the main base, max 0.33 m (runway interior), detector 0.13 s.
* OWED: per-flat-site "units would move" count in the re-bake report; a VHHH-class (spread < 5 m, sloped runway) site has no corpus data — the fan-out from pinned thresholds is twin-proven only.

## 2026-09-05m — v2tunnelobj MERGED 0b875c02; object crest = the ground (spawner ruling on the lane's STOP)

* Lane `v2tunnelobj` delivered 05k-1: `[tunnel.object]` law, `airport/tunnel_objects.py` (wall-skirt signature over the ResourceCache geometry; 10 signatures of 1,350 resources in 0.37 s; two spec amendments from OTHH data — no roof/deck face along the hull axis, seat ≥ `basin.admission_depth_m` under the ground — keep the Emiri terminal, duty-free hall, road slabs and fence walls out), corridors replace the OSM bores they cover in the SAME `Tunnel` product (8 corridors, 7 resources; `tunnel1` ×2 are 700 m apart, two corridors), ramp geometry split into `planar/structure_geometry.py`, re-bake `structure_family_excluded`, sidecar `tunnel_objects`. LEMD byte-identical (`8fb43df9ad3a` control = lane). Consumer census in the lane report.
* **The lane's STOP:** every OTHH placement is `OBJECT_AGL −3.0` (`tunnel1` −7.0) with the plate at +5.0 (+9.55): seat 0.96, plate 5.96 = ground + 2.0 m — a PARAPET. Pinned at the plate (spec-literal `crest = "plate"`) the wall band was a 2 m earth berm: 7 `strip_seam_tear` (|de| 2.0 m at 25.2702,51.6026), hard set INFEASIBLE, 1 relaxed row, v2-verify 20. RULED (spawner, correcting the 05k-1 reading the owner confirmed on my description): the TERRAIN crest at a wall object is the GROUND (09-03b, unchanged), the floor is the seat, the object's slab spans floor → plate by itself; `[tunnel.object] crest = "dem"` is the default and `"plate"` stays a lawful value for a pack whose plate IS the ground. Depth below ground at OTHH is therefore 3.0 m (`tunnel1` 7.0 m), the ramp climbs 0.96 → 3.96. OTHH closing build OTHH_20260904T204014: 8 object corridors, hard-feasible, v2-verify 0, census 0/0.
* OWED: the per-corridor log line still prints the object's plate crest / plate height as "crest / depth" — restate as ground crest and depth-below-ground; the owner's sim read of the two open+open corridors (middle-east/-west) and the ramp mouths; five-airport sweep at app-build time.

## 2026-09-05n — Owner OTHH read on 1.0.285: tunnel wall objects round 2 (five laws)

* Owner: (1) the ramp MOUTH is at the full depth of the wall object and the other end reaches GROUND at the end of the wall, or beyond where the ramp law needs the length; (2) the trench never extends beyond the OUTSIDE of the walls and follows their CURVES; (3) OSM tunnel ramps are still built where OSM says there is one, objects or not; (4) the TOP of the wall objects is FLUSH with the surrounding terrain, never below ground. Measured cause of (4): every placement is `OBJECT_AGL` with its anchor INSIDE its own trench, so the round-1 cut under the anchor sank the wall by the cut (plate rendered 2.96 vs ground 3.96; tunnel1 −0.49). RULED (spawner, spec author): the datum is the object's GEOMETRY referenced to the GROUND — plate = ground (the object is RE-SEATED to it, families no longer excluded), floor at the mouth = ground − plate height (5.0 / 9.5 m), the ramp climbs inside the walls to ground at the wall end (beyond only at `ramp_max_grade`), trench = between the walls' inner faces following their curves, precedence per MOUTH. Spec `docs/specs/auto-patch-v2/tunnel-wall-objects-round2-spec.md`; lane `v2tunnelobj2`. Round 1's "crest = plate/dem" pair is superseded by `plate_datum = "ground"`.
* Owner also reports HECA "serious violations, starting with runway 05C/23C" on 1.0.285 — harness build in flight for attribution.

## 2026-09-05o — Owner: HECA "serious violations, starting with runway 05C/23C" (1.0.285) — attributed

* Runway 05C/23C's two crown halves (faces 14/30) share 346 ridge vertices; half 14's OUTER edge (shared with parallel taxiway pav112 and stubs pav91/93/79) falls to 93.4 m under a 111–116 m ridge — 18 m across 31 m — while half 30 tracks the ridge. `why HECA --shape 14`: z−dem min −18.23 (the edge is 18 m BELOW the terrain), chain Σdz taxi_within_shape +25.0, apron_within_shape +12.8, junction_mesh +10.0, no_step_pairs +4.1, runway_crown +0.02: the taxi family's longitudinal law propagates the LOWER runway complex (05L/23R at 55–68 m) up the parallel taxiway into the shared runway edge, and the runway's only cross-slope row is the SOFT crown minimum (weight 1e2, escalated). `rulesets.toml [icao.runway] transverse_max` (§3.1.18, 1.5 % C–F) exists and NO generator prices it; v2 verify checks the crown minimum only; the oracle judges crown pairs under the declared drops — neither instrument saw a 58 % cross-fall. Pre-existing in every HECA v2 build today (not from 05k–05n). RULED (spawner): the runway transverse MAXIMUM is HARD law in the runway tier (both directions: no fall below and no rise above the ridge steeper than the cap); the taxiway conforms and carries the relief into its body at its own cap; verify reads the maximum as a DEFECT. Spec `docs/specs/auto-patch-v2/runway-transverse-max-spec.md`; lane `v2rwytransverse`. The remaining HECA sites are the owner's to name.

## 2026-09-05p — Owner (1.0.285): HECA groundside/buildings above airside; OTHH terminal floating — three mechanisms

* **HECA apron pricing (owner: "priced correctly via the route graph?").** `why HECA --shape 386` (apron pav132, z 74.2–80.3 under a DEM of 87–97): the chain reaches the 23R threshold PIN (60.66 m, CIFP) in 29 hops — apron_within_shape +6.63, junction_mesh +4.36, no_step_pairs +2.42 — i.e. the apron stands exactly as high as the taxi-route law from the LOW runway complex allows (13.6 m above the pin over the route) and 15 m below the terrain. The route graph prices it as ruled (04o); the terrain is the junior party (03k/04i). VERDICT: correct.
* **HECA pads/lots above airside — two mechanisms.** (a) Pads NOT welded: building272/280 (#1089/#1098, pads at 92.7/91.8) stand +15.7/+15.3 m over apron pav132 at 1.24–2.75 m distance, sharing 0 vertices — beyond `[building_pad] frontage_near_miss_m = 1.0`, so no contact row prices them and the pad sits at the DEM. (b) EVERY HECA pack object unseated: the plan skipped 479 buildings as "no genuine solid component" because the Tai Models OBJ8 files INDENT their `TRIS`/`ATTR` lines with a tab (XPlane2Blender under an LOD) and `obj8.parse_obj8` read keywords at column 0 only → no feet → nothing seated → the author's buildings stay at the authored plane while v2 cuts the aprons 15 m down. FIXED 8072bad7 (parser strips each line; twin `test_obj8_indented.py`; 360_room.obj: 0 → 31 genuine components). OWNER QUESTION 05p-1: what gap still counts as "touching" for a pad beside an apron — the near-miss law binds ≤ 1.0 m today; these stand 1.2–2.8 m off. Spawner recommendation: 5.0 m (`frontage_near_miss_m`), a pad within it is served by that apron and levelled by it (03h), the sliver between them graded as frontage.
* **OTHH main terminal floating ≈ 1.9 m.** The pack's whole terminal complex is ONE anchor family (unit:21, 399 members: Terminal_Base/Interior/Orchard/Clutter AND the sunken TerminalRoads/Parking whose feet lie 1.9–2.5 m below grade; their pits were refused — roofed / basement). `emit/rebake._founders` founds a unit on the members reaching ITS LOWEST BAND (v1 I-8), so the sunken roads founded it and the seat lifted all 399 members +1.888 m (provenance: 399 objects at +1.888, written 21:15). RULED (spawner, 04i rule 1 / 04f-2 applied to the seat): a member whose feet stand deeper than `[basin] contact_band_m` BELOW the local mesh is a FACILITY member — it never founds the family (it keeps its authored y; the terrain's cutout is the basin pass's affair); the founding band is the lowest band among the AT-GRADE eligible members; members floating ABOVE the mesh remain eligible (HECA's authored plane over a cut apron is the case the seat exists for). Lane `v2seatfeet`; closing test = the OTHH tile build's seat (terminal delta expected under the 1 m threshold).

## 2026-09-05q — v2seatfeet MERGED 3b8c7a02; the facility test is relative to the family (amendment)

* Lane result at OTHH (tile build, seat post-mesh): unit:21 delta +0.807 → below the 1 m threshold, the terminal stays at its authored y; 19 facility members (the sunken TerminalRoads/Parking, 1.2–2.5 m under) excluded from founding; pack write 57 objects vs 544 on 1.0.285; provenance records `facility member (05p)` per exclusion. The lane flagged the arithmetic of 05p as written: measured against the MESH, no feet seat could ever lift a family by more than `contact_band_m`. AMENDED (spec author): the facility test is relative to the family's AT-GRADE COALITION (the largest agreeing subset of witness-carrying feet deltas within `agreement_window_m`, else the median) — a member whose delta exceeds the coalition's by more than `contact_band_m` is a facility; a family authored uniformly under the DEM lifts as one (the seat's own purpose). Twins repointed (`test_m6a_rebake.py`); 279 tests green on main.
* The lane's OTHH tile build ended rc 1 AFTER the seat and pack write: the masks step's bathymetry-band stamp writes into the shared repo and the guard refused (the known unmerged fix on `claude/laughing-bell-430766`, 0d3da32d — pull it in for the next build). Shared repo unchanged.

## 2026-09-05r — v2tunnelobj2 MERGED e2734c71 (05n delivered); HECA transverse lane at STOP

* OTHH closing build (lane `OTHH_20260904T223147`, main re-build `OTHH_20260904T223612`): 8 object corridors, floor at every mouth = ground − plate = −1.04 (tunnel1 −5.59), wall band = ground 3.96, trench inside the walls' inner faces (0.000 m outside), ramps inside the walls with the beyond-extension only at 4 % (middle-east 45 m, tunnel_sw 65.6 m, tunnel1 16.6 m), the OSM ramp with no object (−9170/−9169 @0) stands; census 0/0, v2-verify 0; LEMD byte-identical. Measured deviations recorded by the lane and ACCEPTED (spec author): every OTHH object is ONE welded U/O component (walls = the crest plate's plan ring; no per-wall bands), every bore ends 3–20 m INSIDE the closed end, "beyond the wall end" decided by the chord as `_ramp_top` prices it, re-seat = plate datum (`structure_seat_threshold_exempt`), corridor merge removed. OWED: the post-mesh plate seat on this round's mesh (tile build), `tunnel_objects` in the census sidecar register.
* Lane `v2rwytransverse` (781d560d, NOT merged): the runway transverse maximum as hard tier-0 law holds every HECA half at ≤ 1.53 % (half 14: 61.9 % → 1.53 %; 05L half 35: 32.9 % → 1.53 %) and CYXY's 14L/32R halves (8.06 / 5.72 % → cap; body changes by ≤ 2.09 m on strips). `runway_crossing` faces exempt (§3.1.19). BUT HECA's hard set is then infeasible in a NEW way: with the runway edges held, the taxi system between the 55–68 m and 93–116 m complexes cannot carry the relief at 1.5 % / the junction stretch caps (IIS: 281 rows between the 05R/23L and 05L/23R threshold pins — 6 runway_transverse, 96 junction_mesh on pav132, 37 taxi longitudinal, 46 no_step, 26 apron frontage chords, 8 pad welds); the pipeline's IIS search hit `iis_time_budget_s` 120 s (needs ≈ 137 s), so 04t(1) never ran and the tier ladder demoted the whole taxi tier (3,037 rows, 5 m): census 1,604/55 vs 40/7. Measurement arm in flight: `iis_time_budget_s` 300 on the lane branch — if 04t(1) over the tier ≥ 3 rows closes it, that is the merge; if the taxi family itself must yield, OWNER QUESTION 05r-1: may taxiways between real runway elevations take the least-total-variance over-cap (04t-1 extended to the taxi family), never the runway edge?
* 05r addendum — the IIS-300 arm (HECA_20260904T222647): still no certificate ("round 3: no budget left for the neighbourhood certificate"), the tier ladder answered, solve 1,273 s, census 1,604/55, v2-verify 2,919. The budget is not the lever. The conflict is physical: the 05L/23R threshold (60.66 m) and the 05R/23L thresholds (129–142 m) are joined by taxi routes too short to climb 70–80 m at 1.5 % once the runway edges no longer absorb it. OWNER QUESTION 05r-1 stands; spawner recommendation: extend 04t(1) to the TAXI family at such sites (least total variance spread over the route, the runway family never, no cliff), and keep `iis_time_budget_s` at 120. The transverse lane (781d560d) waits for that ruling; app 1.0.286 ships without it.

## 2026-09-05s — Owner RULED 05r-1: runways are FLAT LATERALLY; HECA is solvable — v2 is shortcutting the centreline routes

* (1) Runways must be flat laterally: the transverse maximum is hard law and the runway family never yields to the taxi system (the transverse lane 781d560d stands as law). (2) HECA IS solvable — v1's engine produced a surface; v2 is not finding the right centreline routes between the runway complexes. The IIS the lane produced supports it: 96 `junction_mesh` plane-gradient rows on junction pav132 and 37 taxi `within_shape` rows on pav112/pav64/pav131/pav132 price vertex pairs over DIRECT distance inside a shape, while the law (04o: feasibility along taxi ROUTES; 04t-3: caps per STRETCH between centreline intersections) prices the route. Scout dispatched to attribute: v1's HECA surface along the 1202 routes between 05L/23R and 05R/23L (route lengths, climb, max grade per stretch) vs v2's rows on the same pairs. Then a lane removes the shortcut; the transverse lane merges with it.

## 2026-09-05t — Owner RULED 05p-1: the pad-to-apron weld gap stays UNDER 1 m

* `[building_pad] frontage_near_miss_m = 1.0` stands; a pad 1.2–2.8 m off an apron (HECA building272/280 beside pav132) is NOT welded to it — it is groundside ground, terraced under the groundside law, and the pack's building objects seat on it through the re-bake (the OBJ8 indentation fix, 8072bad7). No change to the law tables.

## 2026-09-05u — HECA attributed: the binding chain is the hangar apron + flat pads, not the taxi routes; 04t(1) never ran

* Scout (Fable, read-only, `scratchpad/scout_heca_routes/`): every 1202 taxi route between HECA's runway complexes is feasible at ≤ 1.15 % with the runway edges held (23R ↔ 23C: 53.6 m climb vs 66.7 m at 1.5 %, slack +13.1 m; 23R ↔ 05R +21.1 m); v2's taxi within_shape and junction_mesh rows price chord ≈ station distance (median ratio 1.000) and contribute 0 m to the binding chain — NOT a shortcut. The chain that leaves only 29.5 m where the route grants 43.4 m runs through apron pav132's plan chords at 1 % (one of 700 m) and 597 m of FLAT hangar-pad rims at zero grade (11 pads, 236–370 m off any route). v1's surface (2026-09-02 patch) kept the centreline routes near 1.5 % by breaking the shape laws ~1,000 times (census airside 1,072; certificate 2,167 residuals). The runway must bow below its CIFP line mid-runway (≥ 3.78 m; v1 bowed 9.27 m) — lawful under the 1.5 % longitudinal cap. RULED (spawner): this is the 04t(1) case as written (slight over-cap apron, pads as ≤ 1 % planes, never the taxi family, never a cliff); v2 failed by never reaching it — the certificate search expires (120 / 300 s) and the fallback demotes the TAXI tier. Spec `docs/specs/auto-patch-v2/relaxation-without-certificate-spec.md`: the 04t(1) program runs over the full relaxable scope when no certificate arrives; the tier ladder is last and names its demotion as a FAILURE. Lane `v2relaxfull` carries the transverse law (781d560d) with it.

## 2026-09-05v — HECA: the route graph's apron plan chords are the shortcut (lane v2relaxfull STOP, amended)

* Lane `v2relaxfull` (1b2c3f50, carries the transverse law): with EVERY relaxable row dropped the certificate is 65 rows — 05C/23C transverse 16 + profile 1, no_step 30, taxi 4 (pav112/pav91), reach bands 15; no pin, apron or pad — so 05u's "apron + pads" chain is not the last contradiction. The 15 reach bands and the 30 no_step pairs take their route distance from `constraints/routes.py`, whose graph carries every APRON PLAN CHORD at 1 % (the scout's caveat, wrongly dismissed in the spec's §4): a path cutting across pav132 on a 700 m chord is a 7 m budget where the taxi route grants 43 m, and the bands are hard. RULED (spawner, 04o applied): the reach/no_step route graph is the movement-surface network only (runway + taxi rings, centrelines, stretch chords, the 1202 taxilanes crossing an apron, apron perimeters) — no apron plan chord. Spec §5; lane `v2relaxfull2` on the same branch. Also delivered by the lane and kept: `scope_without_certificate`, `tier_ladder_last` with the demotion a NAMED FAILURE, `apron_edge_portion` rows admitted to the relaxable scope (18,672 were refused by a citation defect), `tools/harness/rwy_xfall.py` promoted; every HECA runway half ≤ 1.53 %.

## 2026-09-05w — HECA: the hangar apron is classified as a 214,000 m² JUNCTION (lane v2relaxfull2 STOP; owner question)

* Lane `v2relaxfull2` (branch `lane/v2relaxfull` @ 856e6c8f): with apron plan chords out of the route graph (05v) and junction chords limited to common stretches, the taxi ROUTE has slack (v6 → v3339: 7,421 m, budget 111.3 m vs 75.9 m of relief) and no reach band binds; the certificate is now 308 SHAPE rows — 163 `junction_mesh` plane-gradient rows (pav132 126, pav131 33, pav39 12), 47 taxi within_shape, 84 no_step. Cause: the hangar apron pav132 (apt.dat 110, 335,171 m², `apron_named`, crossed by 19 taxi chains, only 21 % of it within 25 m of a route) is cut by the ROUTE-PROXIMITY rule (user 2026-07-06, `classify/roles.py` "THE ROUTE-PROXIMITY CUT") into a 214,262 m² cell of role **junction** (three faces 1.2–1.3 km across), whose junction-mesh and taxi rows are tier-0 hard and OUTSIDE the 04t(1) scope — the apron the owner's 04t(1) may relax is not there to relax. OWNER QUESTION 05w-1: on a large apron crossed by taxilanes, is the JUNCTION the bounded route territory (within `[junction] route_territory_half_width_m` = 25 m of the crossing centrelines, and the tight areas at their intersections) with the rest APRON under the apron law — spawner recommendation — or do junction/taxi rows on apron-derived junction cells join the 04t(1) relaxable scope? 
* Also from the lane, ACCEPTED (spawner, 03h contact): pad FRONTAGE hops in the route graph (each pad-hole vertex to the nearest vertex of every other ring of its face within the no-step window, at the pad cap) — without them pad rims inside an apron became route islands (CYXY 2 cross_shape rows 1.95 m at building6/7); with them CYXY 0/0. The two `test_pad_flat` relaxation twins now read a different least-variance answer (133 apron/no_step rows relaxed instead of the pad plane) — to be repointed on the measured meaning with the merge. `flex_audit.py --by-role` promoted.

## 2026-09-05x — Owner RULED 05w-1 (a): the junction is the bounded route territory; the rest of a crossed apron is APRON

* On a large apron crossed by taxilanes the JUNCTION role is the bounded route territory — within `[junction] route_territory_half_width_m` (25 m) of the crossing centrelines and the tight areas at their intersections (`[junction] max_area_m2`) — and everything else stays APRON under the apron law (1 %, relaxable under 04t-1). The 2026-07-06 route-proximity cut is bounded by that territory, never the whole proximity contour. Spec §6; lane `v2relaxfull3` on `lane/v2relaxfull`.

## 2026-09-05y — lane v2relaxfull3: classification delivered; the route graph carries no RUNWAY CROSSING (spawner ruling)

* Delivered (branch `lane/v2relaxfull` @ e68abf8b): the bounded route territory (05x): HECA pav132 junction 418,364 → 273,929 m², apron 141,716 → 286,152 m² (pav39 −109,758, pav47 −68,266, pav131 −39,229 junction); CYXY 0/0 (pav9 junction 60,624 → 41,589), OTHH 0/0 (pav32 −213 k), SPJC 0/0 (degraded frame both arms — its production frame is COLD, owner refresh `osm_layers,dem` owed); 284 twins green; the two `test_pad_flat` twins repointed. Deviation ACCEPTED: the 2026-07-06 runway route-proximity band stays (05x spoke of taxilanes; without it HECA pav81/82, CYXY pav24, OTHH pav32 turn apron).
* HECA STILL infeasible, certificate 9 rows on 05C/23C at xy ≈ (140–200, 130–180): 2 crown, 2 transverse, 1 no_step rate, 4 REACH BANDS — the runway's two edges (v1674/5 at stub pav91: [85.6, 108.8]; v2651/2 at stub pav101 across the runway: [108.8, 143.5]) are 60 m apart and tied within ±0.455 m by the transverse law, yet 3,206 m vs 6,417 m from the low pin in the route graph: the taxi centreline parts inside the runway body are cut away (`region.difference(runway_union)`), so a crossing routes around the runway end. RULED (spawner, 04o): the RUNWAY FAMILY IS PART OF THE ROUTE NETWORK — each runway's ring edges along its length at the runway longitudinal cap (both crown halves), the crossing 1202 centreline parts across it at the runway cap, and the width between the two edges at the transverse cap — so the reach bands are one envelope with the flat-runway law. Spec §7; lane `v2relaxfull4` on the same branch.

## 2026-09-05z — Owner AMENDED 05y: the runway is like an apron in the route graph — crossable, followed along its CENTRELINE; its EDGES are not graph edges

* 05y (i) (runway ring edges at the longitudinal cap) and (iii) (width edges) are WITHDRAWN. The route graph carries the runway's CENTRELINE (the crown spine, at the runway longitudinal cap by code) and the 1202 taxi routes CROSSING the runway (at the runway cap) — a stub at one edge reaches the other edge across the runway through the crossing route and the centreline, exactly as a route crosses an apron on its taxilanes. The runway edge vertices join the graph only where a crossing or the centreline meets them. Spec §7 amended; lane `v2relaxfull4` relaunched.

## 2026-09-05aa — Owner verdict on the HECA limiting-chain KML: the route graph follows EVERY curve of the taxi routes — never a chord across open pavement, never an edge

* Owner read of `HECA_limiting_chain.kml` (v2 route graph at lane/v2relaxfull 11a19b99): the green leg (pav91 → pav101 as the graph saw it) is all RUNWAY EDGE; the yellow taxi-only leg is right until 30°06'59.81"N 31°24'50.24"E and then cuts diagonally away from the centreline, jogs, and crosses open grass straight to the runway (the 2,382 m pav130 chord and the 1,467 m runway chord); the red band leg cuts straight across as well (apron perimeters at 1 %). RULED: the route graph for reach bands and no_step distances is the 1202 CENTRELINE NETWORK ONLY — every taxi centreline stretch at its stretch cap following every curve and turn, the runway centrelines at the runway cap, the crossings — with NO ring edges, NO stretch/apron/junction chords, NO apron perimeters, NO pad frontage hops. A pavement vertex off a centreline attaches to ITS OWN face's centreline at the nearest station by ONE lateral hop over the perpendicular distance at the face's transverse cap (a runway edge vertex to the runway centreline at `transverse_max`; a taxiway edge to its stretch at the taxi transverse cap; an apron vertex to the nearest taxilane crossing or touching it at the apron cap; a pad through its apron frontage). A vertex with no centreline to attach to has no reach band. This is v1's model ("reach follows centerlines"); everything else since 05v was an approximation of it. Spec §8; lane `v2relaxfull5`.

## 2026-09-05ab — lane v2relaxfull5: the graph is centreline-true; the taxi WITHIN-SHAPE chord is the last shortcut (spawner ruling)

* With the 05aa graph (`lane/v2relaxfull` @ 393c98f4: centrelines, crossings, one lateral hop per ring vertex; 10,219 nodes / 11,150 edges) the 05C/23C edge bands OVERLAP — pav91 [87.21, 109.64], pav101 [87.23, 110.58] (23R → pav91 3,265 m along pav81/pav129/pav130/pav132/pav98/pav112; 05R → pav101 3,679 m) — the route law is satisfied. The 9-row certificate is now two taxi `within_shape` CHORD rows: pav101 v2632↔v2831, a 1,462.8 m chord at 1.5 % where the centreline route between them is 3,326 m, and pav91/pav112 v1674↔v2098, 248.6 m vs 368 m — plus the transverse tie and crown. RULED (spawner, 05aa applied to the shape law): a taxi-family within-shape row prices its pair over the CENTRELINE ROUTE distance between the two vertices' attachment stations (hop + centreline path + hop through the route graph), never the chord; a pair with no route between them gets no within-shape row (the transverse law, the junction mesh and no_step govern adjacency). Apron chords at 1 % stay (the apron law is all directions; relaxable). Also: a PAD's attachment to the graph is its CONTACT — the apron vertex it is welded to or its frontage row's apron vertex (0 m) — never a route hop; the lane deleted it with the frontage kind and CYXY minted 2 building rows (0.25 m over 0.5 m at building6/7): restore it. Accepted deviations: the hop prices transverse × perpendicular + centreline cap × the walk to the foot; hops are leaves (never transited); crossing entries are nodes; the planar breakline tolerance fix (`max(0.6·grid, weld spacing)`, HECA taxi136 chain restored). Spec §9; lane `v2relaxfull6`.

## 2026-09-05ac — lane v2relaxfull6: HECA is FEASIBLE under the complete route law (empty certificate); the pairwise formulation is the obstacle (spawner ruling)

* Measured by the lane (branch `lane/v2relaxfull`): with EVERY leaving-chord taxi pair priced over its centreline route (160k rows) the reduced hard set's certificate is EMPTY — HECA is feasible under the flat-runway law, the CIFP pins, the 1.5 % taxi law along every curve and the 04t(1) relaxable scope — but the LP stalls (HiGHS dual simplex > 34 min; the last resort's stage 1 > 240 s). Attempt 1 (`d8aa5a02`, merged to main as a fast-forward: route rows only where "stricter", 38k) SOLVED (scope relaxable, apron pav132 0.63 % over, pads 0.34 %, six runway halves ≤ 1.53 %, no demotion, 248 s) but UNDER-CONSTRAINS: the v2 verify reads 1,018 within_shape rows over the published route pairs, 393 of them > 2 % and 29 > 3 % along their routes (worst 34.8 m over 1,582 m, stub|stub) — pairs that got no row. Attempt 2 (`198d688c`, not merged: hops/crossings/contacts as rows, 7.9k) is infeasible against the IN-FACE chord/plane rows (88 pav91/pav112 chords ≤ 195 m, 58 junction planes). The v1 oracle reads 24,578 (HECA) and 136 (CYXY, 1.51 % on 700 m chords of a slightly bent face): it prices the chord law the owner withdrew (05aa) — for the taxi family the oracle is no longer the law's instrument.
* RULED (spawner, the 05aa/05ab law stated compactly): the taxi-family grade law is EXPRESSED BY THE CHAIN — one hard Diff row per centreline EDGE of every stretch (|Δz| ≤ stretch cap × edge length, every polyline vertex), one hard Diff row per LATERAL HOP (ring vertex ↔ its attachment station at the transverse cap over the perpendicular distance, plus the centreline walk), the crossings and contacts as rows — and NO PAIR ROWS at all for taxi faces (neither leaving chords nor in-face chords: every pair's route budget is implied by the chain, triangle inequality). The junction mesh stays only inside the bounded junction territory (05x). The v2 verify reads pairs over the published routes exactly as today (its 05ab reading), and is the taxi family's instrument; the oracle's taxi chord rows are reported apart as "withdrawn law". Expect the reduced certificate empty (the literal-§9 result) with a ~11k-row formulation. Lane `v2relaxfull7`. Main stays at d8aa5a02 and is NOT built into an app until this lands.

## 2026-09-05ad — v2relaxfull7 MERGED 43d50a53: HECA solves under the complete law; the relaxation's SHAPE is the next owner site

* The chain formulation (05ac): taxi pair rows 237,479 → 7,901 chain rows (5,144 taxi hops, 1,743 apron hops, 968 runway hops, 46 crossings) + 2,299 centreline rows; HECA certificate EMPTY offline in 4.9 s; the build `HECA_20260905T201841` solved OPTIMAL, scope `certificate` (IIS 205 rows in 83 s, stage 1 211 s, stage 2 32 s, total 413 s), no governed demotion; `rwy_xfall` six halves ≤ 1.53 %; v2-verify 41 rows — taxi within_shape 0 over the published routes (offline after the publication fix), lateral_contiguity 26 (pre-existing), transverse 7 and strip_longitudinal 7 NEW (below); oracle adjudicated 33 with the WITHDRAWN chord law (05aa) reported apart: 31,055 rows. CYXY v2-verify 1 = 1 (pre-existing apron chord), oracle 0 = 0; OTHH 0 = 0. 620 tests green on main. Suites, harness census (`withdrawn_law_05aa` heading, `taxi_route_pairs` evidence) and `why` families updated.
* NEXT OWNER SITE — the relaxation's shape: 30,172 relaxed rows, relief Σ 26,540 m, max slack 6.57 m; 21 km of it lawful in spirit (pav132 frontage chords at 1.45–1.50 % vs the 1 % cap) but the PWL program also DUMPED relief on short rows — a 2.55 m ring edge carrying 1.33 m (52 %), transverse rows 0.63–0.78 m, apron/taxilane seam 4–6 % over 14 m (the 7 new transverse rows) — cliffs 04t-1 forbids ("never a cliff"). The 7 strip_longitudinal rows are a strip generator/reader population gap exposed by the pavement edge moving. App 1.0.287 ships this state for the owner's HECA read; the relaxation-shape spec (per-row over-cap bound, the exact QP where the scope fits `qp_max_rows`) follows the read.

## 2026-09-05ae — Owner KML read on the chain law: apron chords cross a road, a building and a non-movement area at 30°07'40.66"N 31°24'45.73"E — RULED; the remaining known issues go to one lane, then app 1.0.288

* The lines are apron pav132's FRONTAGE ("spine") chords (2026-08-21c, `apron_within_shape`, "never dropped"): 585–770 m straight chords at 1 % between apron vertices that leave the pavement through the face's hole where a road and a building stand — 21 km of the relaxation's 26.5 km of relief rode on them. RULED (owner's rule applied to the apron law): an apron within-shape chord — frontage/spine or body — is priced ONLY when the straight chord lies entirely inside the apron face (crossing no hole and no exterior); a chord that leaves the face is not a pair (the ring edges and the inside chords carry the apron law around the obstacle). Same for the junction mesh's triangles: a triangle edge leaving its face is not a row.
* The remaining known issues, all to lane `v2fix288`: (1) the chord rule above; (2) the relaxation's SHAPE (05ad): a relaxed row's slack is bounded by `[relaxation] max_over_cap_factor` × its cap × distance (a "slight" over-cap, 04t-1; never a cliff on a short edge) and the exact QP runs when the certificate scope fits `qp_max_rows` with `qp_time_budget_s` sized for it (measure); (3) the strip generator/reader population gap (7 `strip_longitudinal` rows beside a runway end and taxiway E: the generator states 2 rows for the reader's population); (4) CYXY's pre-existing apron|apron 1.38 % chord (way 88) — expected to be the same chord class. Closing builds HECA (site first), CYXY and OTHH base arms; then app 1.0.288.

## 2026-09-05af — lane v2fix288 delivered; `max_over_cap_factor` = 2.5 (spawner)

* Chords stay inside their face: HECA pav132 dropped 52,962 chords (21,109 km of chord length, 17,330 over 500 m); airport-wide 135,240 of 160,844 apron rows left their face (pav47 39,040, pav131 21,610, pav39 16,171); junction triangles likewise; the oracle reads the face holes (`face_holes` sidecar). Strip gap attributed and closed: the generator counted HOLE rings of taxiways pav93/pav73 as pavement, the reader only outer rings — one population helper (HECA 2 → 133 rows priced; the 7 verify rows → 0). CYXY way 88 was NOT the chord class: a 60.10 m body chord in the TM frame read 59.97 m in the census frame and straddled the 60 m gate — gate inflated by the identity spacing → CYXY v2-verify 0, hard-feasible; OTHH 0 = 0 (apron rows 759k → 69k, solve 7.9 → 2.9 s). 612 twins green.
* The factor: at the ruled 2.0 HECA's relaxation is INFEASIBLE (Farkas core 232 rows — 188 pav132 junction planes, 26 no_step, 8 chain, 7 runway profile, the two pins, and ONE relaxable apron chord of 126 m needing 2.53 m) and the ladder demoted the apron (1,845 rows, 7.82 m — a named failure); feasible at 2.05. RULED (spawner): `[relaxation] max_over_cap_factor = 2.5` — margin over the measured edge; the least-variance objective keeps rows near 1× unless forced (the factor is the anti-cliff ceiling, not a target). The exact QP does not run at HECA's scale (highspy `kSolveError` on the 582k-row model after 8.6 s): the PWL stays, `qp_time_budget_s` unchanged. Closing HECA build at 2.5 in flight; then merge and app 1.0.288.

## 2026-09-05ag — v2fix288 MERGED 4d79dc59; HECA closes at factor 2.5; app 1.0.288

* HECA `HECA_20260905T233648` at `max_over_cap_factor = 2.5`: optimal, scope `relaxable` (the certificate LP still exceeds the 120 s budget; the relaxable scope answered in 230 s solve, 315 s build), 7,631 relaxed rows with MAX SLACK 0.015 m (Σ 17.5 m, mean 2 mm) — no cliff anywhere; v2-verify 27 (lateral_contiguity 26 pre-existing, transverse 1); oracle adjudicated 40 airside / 0 groundside with 31,286 withdrawn-law (05aa) chord rows apart; six runway halves ≤ 1.53 %. CYXY / OTHH v2-verify 0, hard-feasible. 626 tests green. App 1.0.288 built for the owner's HECA read.
* OWED: the 26 `lateral_contiguity` rows at HECA (pre-existing since 05g); the 120 s certificate budget spent on every HECA build (the relaxable scope answers anyway — a lower budget or a scope-first order is a build-time item); the `withdrawn_law_05aa` heading is a transition state until v1's census is retired.

## 2026-09-06a — Owner: the +40-004 tile fails, "why no LEMD patch?" — LEMD's patch is written; LEGT/LERM/LETO refused a cold tile 1,300 km away (two reader defects)

* LEMD's patch was written (147 s, provenance `version=1.50.1730`); the tile failed on LEGT, LERM and LETO: `REFUSING: the production DEM frame for N28W003 is COLD`. Two causes, both in v2's DSF pavement reading: (1) `airport/dsf.py::_flatten` read a UV-MAPPED draped polygon (`BEGIN_POLYGON idx 65535 4`, columns `lon lat u v`) as a bezier with control points at (u, v) — the Global Airports tile's `junctions.pol` markings flattened 23° tall (28.9–52.1° N), so the flat-site detector's sampling grid over the airport region reached tile N28W003; FIXED: `UV_MAPPED_PARAM = 65535` → cpp 4 is `lon lat u v`, cpp 6 is `lon lat ctrl ctrl u v`; twin. (2) `airport/load.py` admitted EVERY pavement page of the tile DSF to every airport (LEGT carried LEMD-tile pages 47–79 km away; LERM 112 → 16 pavements, LETO 121 → 20, LEGT 107 → 9); FIXED: the admission gate `[identity] dsf_pavement_admission_m = 1000.0` — a page is this airport's only within 1 km of its own apt.dat runways / pavements / boundary; refused pages counted in `report.load.dsf_pavements_far`. LEGT/LERM/LETO build (LEGT 0 rows, LETO 1, LERM 0); LEMD's 62 `tunnel_wall_top_flat` + 7 `tunnel_mouth_canonical` verify rows are the known owed item (05i). App 1.0.289.

## 2026-09-06b — Owner reads on 1.0.288: HECA "still very broken" (three unpriced laws, measured); OTHH three adjustments

* HECA tile at 07:27 IS the 1.0.288 patch (engine 1.50.1730; halves ≤ 1.53 %, census 40). What the owner sees, measured (v1 2026-09-02 beside): 05C/23C ridge grade change 2.32 pp per 100 m (v1 0.71; K law 0.33) — `vertical_curve_k_m`/`max_grade_change` are declared and priced by nothing; the graded strip stands up to 5.6 m ABOVE the runway edge within 60 m (v1 follows) — the zone rows are DEM corridors with no tie to the edge; 41 shared-anchor families seated as rigid units with deltas to −35.6 m (133/199 members) — one delta over 85 m of relief buries one end and floats the other (v1 never touched them). RULED (spawner): the vertical-curve law is hard runway-tier rows; the strip is tied to the runway edge at the zone transverse cap both ways; a family seats as one only for the members that AGREE, the rest by their own resource delta. Spec `heca-read-20260906-spec.md`; lane `v2heca3`.
* OTHH (owner: "quite good"): (1) below-grade trench = floor overlapping the object's inner perimeter, a very small gap, the at-grade rim on the outer perimeter — NO wall band emitted, the mesh makes the wall; (2) a pavement tracing the road through a ramp sets the ramp width; (3) basins 879/873 sit below the trench floor (877 right) — handle placement. Spec `othh-read-20260906-spec.md`; lane `v2othh3`.

## 2026-09-06c — Owner LEMD read on 1.0.288: basin at 970, curved edge-wall tunnel at 1088 (RULED; lane sequenced after v2othh3)

* LEMD "looks quite good", seats right (per-object anchors — HECA's shared-anchor pack is the outlier, 06b). (1) shapeID 970 = building16's pad flattened at 597.40 over a 10 m-deep sunken structure: the 04i rule-4 basement test fired at 38 % cover. RULED: basement = wholly covered (`[basin] basement_cover_min = 0.9`); less is a pit and is cut. (2) shapeID 1088: the pack's short edge walls (LEMD85, crest 1.18 m) were refused as kerbs (`plate_min_height_m` 2.0) and the OSM bore ramped straight into a taxiway. RULED: an EDGE-WALL object (skirt, crest < `edge_wall_max_plate_m` 2.0 above the seat, no floor) gives the ramp its plan and curve with the crest flush at grade; the depth is the bore law's. Spec `lemd-read-20260906-spec.md`; lane `v2lemd3` after `v2othh3` (same files).

## 2026-09-06d — lane v2othh3 delivered (a4f58a18, not yet merged); LEMD lane sequenced on it

* Owner's three OTHH laws implemented: `[cutout] floor_overlap_m = 0.3`, `rim_gap_m = 0.3`, `emit_wall_band = false` (measured walls: tunnel sides 1.0 m, ends 2.0–2.5 m, drainage shells 0.75 m; both keys ≤ half the thinnest); the void between floor and rim is emitted as a role-less `o4_feature=structure_rim` ring and the mesh makes the wall; `[tunnel] ramp_width_source = ["pavement","lanes"]` with `ramp_pavement_max_offset_m = 2.0`; `[basin] seat = "floor_plate"`. Basins 873/879: their `OBJECT_AGL` anchors lie INSIDE their own floor, so they rendered at the trench floor (−3.82 m under) while their family was excluded from the seat — now floor = the rendered deepest solid and the basin members are PLATE members seated ON the floor (+4.02 / +4.00 m; 877 +0.001; the two Dewatering pits +13.56 / +8.09). OTHH tile: both tunnel sites floor −1.04 / rim 3.96 / gap 1.1–1.8 m / no band; census 0/0, v2-verify 0 (wall families `tunnel_wall_top_flat`, `tunnel_ramp_wall_gap`, `basin_wall_gap` retired, `structure_rim_gap` added); LEMD verify 72 → 14 (62 wall rows retired; 3 new `strip_seam_tear` ≤ 1.92 m unattributed); CYXY byte-identical. OPEN (to lane v2lemd3): the MESH inside 6 of 12 basin floor faces is not flat (interior points +0.95 m; the Dewatering floors +5.9/+7.1 m) — a plate seated on the floor is poked through.

## 2026-09-06e — v2heca3 MERGED e99653af: vertical curve, strip tie, seat split

* HECA tile (lane, `O4_DSF_OBJECT_REANCHOR=0`): 05C/23C grade change 0.34 pp/100 m (K + the 0.01 m emit quantum; was 2.32, v1 0.71), max grade 1.49 %, bow 11.4 m (was 8.6, v1 9.3 — the smooth profile bows deeper); six halves ≤ 1.52 %; new readers `runway_vertical_curve` / `strip_transverse` 0; v2-verify 27 (unchanged pre-existing), census 42 (bar 40); seat: 3 shared-anchor families SPLIT, 125 members seated by their own delta (unit:42's 133 members: family −14.0, 96 apart at −66…−4), facility 0 (was 76); OTHH unit:21 still seats as one; CYXY/OTHH verify 0. Accepted deviations: one two-sided row per station; strip tie rise-only (zone_bands' floor is the fall side) at `lip_max_down`/`band_max_down` (3 % code 4), not minted where the runway is the vertex's nearest pavement; facility = outside the coalition AND > contact_band_m below the mesh; "witnessed on land" per the lane's definition. OWED: (a) DECK-founded families are not split (HECA unit:43, 199 members, residual −28…+84 m) — the owner will still see that family float/sink; (b) the STUB-MOUTH step class law 1 exposes: stubs pav93/pav101 8 m outside the runway edge do not follow the ridge's bow (pav93's ring vertex +3.47 m above the edge 3.3 m away) — the stub's mouth must reach the runway edge through its crossing; (c) `zone_bands` class-key finding (strip faces carry letter None); (d) HECA solve ~363 s under the relaxable scope.

## 2026-09-06f — LEMD 970 and 1088 attributed at their sites (lane v2lemd3 refuted the 06c mechanisms); v2lemd3 MERGED ab6d3c2a; RULED again

* MERGED ab6d3c2a (v2othh3 + v2lemd3, 683 tests green): the OTHH trench law (floor overlap 0.3 m, rim gap 0.3 m, no wall band, ramp width from pavement, basins seated on their floor), `[basin] basement_cover_min = 0.9`, `[tunnel.object] edge_wall_max_plate_m = 2.0`, and the OTHH floor-flatness residual: Triangle's segment splits on a PATCH ring were free vertices averaged with the void — `O4_Mesh_Utils.patch_segment_split_values` (v1 core) gives them the segment's linear value (12 floors flat, spread 0.00).
* **970 (owner: "objects, including a control tower, sit in the basin and extend well above it").** The lane measured: the blocker is LEMD85 — a 26,905 m² floor plate 4.03 m under the DEM (the T4S sunken structure) refused by the 04i rule-1 RIM test because 21 m² of its faces (15 of 208 triangles) reach +8.44 m. RULED: the rim is the shell's GROUND-CONTACT ring; solids of the same object above grade are cover or protrusions (a tower, a vent), never the rim, unless they cover ≥ `basement_cover_min` of the floor — `[basin] rim_protrusion_max_fraction = 0.05` of the component's solid face area may stand above the contact band without refusing the pit (LEMD85: 21 / ~27,000 m²). Expected: 970 becomes a ≈ 27,000 m² basin at 588.97 with the pad yielding inside it.
* **1088 (owner: "the wall object should be right about here: 40.4862443, −3.5663983").** No OBJECT anchor lies within 120 m; the wall is `Bridge4.obj` — one component of 660 vertices, 76 × 144 m in plan, y −2.88 … −0.86 (ENTIRELY below its seat), anchored 72 m away, 99 of its vertices within 20 m of the owner's point. Refused silently by the signatures (crest below the seat; skirt 2.02 m < `skirt_min_depth_m` 3.0). RULED: an EDGE-WALL object's crest is its top band wherever it lies relative to the seat (the seat is the author's handle, not a datum — 05n-4: the crest is set flush at grade by the re-seat), `[tunnel.object] edge_wall_min_skirt_m = 1.5`; the ramp's plan and curve run between its walls, the depth from the bore law (06c). The ramp crosses under a taxiway there: if a mapped bridge or an apt.dat taxiway spans the corridor it is a DECK over the ramp (the existing deck-interval machinery), never a cut through the taxiway. Lane `v2lemd4` (branch from main ab6d3c2a).

## 2026-09-06g — Owner: "compare how v1 split and seated HECA's objects" — NOT the same; v2 adopts v1's cluster law (spawner ruling)

* Scout (Fable, read-only; `scout_heca_seats/`): v1's unit is a WELDED CONTACT CLUSTER — pools by placed-footprint overlap (0.25 m), structures = connected ε-contact solids (`object_anchor.partition_structures`), clusters cut where two adjacent GROUND parts' seat targets (mesh − base_y) differ by > `DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M` 0.5 m (`object_clusters.form_clusters`), seated on the MEDIAN mesh under the cluster's ground parts (threshold 1.0 m, spans > 3 m bake-and-pad, residuals > 0.75 m to pads), the delta written PER VERTEX (`object_rebake._rewrite_y_tokens` — one file carries several deltas); elevated parts inherit their supporter cluster (I-8), a deck never founds the ground under it; anchor spelling is only the subtrahend (I-3). HECA v1 record (Sep 4): 5,738 clusters, 0 refused, worst residual 2.71 m. v2 (anchor-spelling units, one delta per file): 43 units; 64/400 members within 1 m of their own ground, 182/400 after 06e's seat-apart; unit:43 (199 deck-founded) 9/184. RULED: v2's re-bake adopts v1's law as data-driven code in `auto_patch_v2` — the unit = the contact cluster cut at `[rebake] cluster_seat_tolerance_m = 0.5`, the delta = the median ground under the cluster's ground parts minus the object's anchor ground, applied PER VERTEX through the existing writer, `min_delta_m` 1.0, spans > `cluster_span_pad_m` 3.0 bake-and-pad, residuals > `cluster_residual_pad_m` 0.75 raise pad requests; deck plates seat their own cluster at the abutment grade and never found the ground parts around them. The 05p/05q facility rule and the 05n-4/06d plate seats stay as cluster-level rules. Lane `v2seatclusters`.

## 2026-09-06i — v2seatclusters MERGED c706c64e: v2 seats by v1's contact-cluster law

* HECA tile (lane, no pack write): pools 19 / structures 4,839 / clusters 5,256 (v1 Sep-4 5,738), 5,210 seated, 4 refused (A3), 589 pad requests (worst residual −4.05 m; reported, consumed by no v2 pass yet — owed), members within 1 m of their own ground 253/282 measured (was 182/400), worst 22.9 m, 297 members carrying several per-vertex deltas, 391/415 objects to write; the 199-member deck unit: the deck plate seats alone, the 198 ground members by their own clusters (06e owed (a) CLOSED). OTHH: all 19 structure seats byte-identical; the terminal family stays (below threshold) with 9 lone ground parts seated by their own single-part clusters. 655 tests green. Accepted deviation: `[rebake] facility_requires_at_grade_coalition = true` (05q's words). Build time: the plan stage 24 s offline / 93 s in-build at HECA (was 2 s) — over the 1 % line on an over-budget build; the timing gates are suspended pre-ship (owner 2026-08-04), the Fable optimisation review is OWED at the ship gate; OTHH plan JSON 26 MB.

## 2026-09-06j — v2lemd4 MERGED 5f291558: LEMD 970 basin, 1088 edge-wall corridor

* 970: LEMD85's tower faces above the contact band are 3.4 % of its 29,228 m² solid area → `[basin] rim_protrusion_max_fraction = 0.05` admits the pit: basin LEMD36+37+85, floor 588.95, 27,657 m² floor over a 27,557 m² region (covered pit, own cover 38 %); building16's pad 29,837 → 1,763 m². 1088: the AUTHORED Bridge4.obj stands on its seat (y 0 … 2.016; the −2.88 … −0.86 reading in 06f was v1's bake in the live file) — an edge wall by `edge_wall_min_skirt_m = 1.5`: `tunnel-object:Bridge4.obj@0`, U walls, curved axis 122.3 m (8.6 m off the chord), width 18.7 m, mouth = the bore end (−5970's OSM ramp replaced per 05n-3), floor −5.10 under the mouth ground, no straight chord into pav97; no deck (no cell within 61.6 m) — the pavement-deck machinery (`[bridge] pavement_deck_families = ["taxi"]`) is built and twinned. LEMD census 7 = 7, v2-verify 14 = 14 (the 3 `strip_seam_tear` graded-strip seam rows pre-existing, still owed); OTHH basins identical, tunnel1's ramp beyond the walls 15.7 m shorter (corner-pair fit); CYXY byte-identical; 653 tests green. OWNER READ ITEMS the rim rule now admits: LEMD41 (10,137 m² at 595.5 under the Old Terminal, covered 100 %), Cargo-CNTRL (452 m², 12 m deep), LEMD43 (2 × 40 m²) — pits by the ruled letter. New replay entry `-m auto_patch_v2.planar ICAO --stage structures` (INDEX).

## 2026-09-06k — lane v2bow NOT merged (bar missed); the junction-mesh cone is the withdrawn chord law in disguise (spawner ruling); app 1.0.290 from main

* v2bow (7aeb747e): (a) the in-slab centreline join raises the s≈2218 reach ceiling 110.12 → 114.52 (= the law) but the LP does not move: the stub mouth is a runway ring vertex tied to the ridge by the hard `runway_transverse` row, and the taxi-tier chain holds it — the 4.4 m was the transverse law at the mouth, not the graph; (b) the runway-fit term in the relaxation objective moved the bow 11.04 → 10.12 m and the 05L/23R crest +11.0 → +2.0 at 2.8× the relief (Σ 3,804 → 10,680 m, max 7.16 m), census 42 → 92, and minted a `pad_flat` DEFECT (a pad relaxed exactly to 1 % read over by the emit quantum — the app would fail HECA on it); (c) smoothness λ=5000 straightens the hump, immaterial at HECA once (b) is in. Residual: a hard chain to a hold at s≈2600 (≈105 m, 11.7 m under the route ceiling) through junction_mesh and no_step rows (taxi tier) and apron chords at 2.5×. NOT MERGED. Accepted for the follow-up: (a) with the runway-line reading (only nodes on the runway's own 1202 line join; every interior node gives 110.99), (c) as a table value; (b) OFF by default (`[relaxation] runway_fit_weight = 0`, the owner may turn it on).
* RULED (spawner): the junction mesh's ISOTROPIC plane-gradient cone (16 half-planes at cap·cos π/16) bounds any two points of a junction by 1.5 % × their STRAIGHT distance — the chord law the owner withdrew (05aa), re-entering through the bounded junction cells (pav132's 695 m of planes carry +10.05 m of the chain). Plane rows become ANISOTROPIC: along the junction's serving centreline direction at the stretch longitudinal cap, across it at the taxi transverse cap (the box, 04t-2/3); no_step pairs stay (route-priced). Also: the `pad_flat` reader tolerates the emit quantum (`plane_slope ≤ cap + quantum`). Lane `v2bow2` on `lane/v2bow`. Bars at HECA: bow ≤ 5 m, census ≤ 42, relief Σ ≤ 4,000 m, no DEFECT row, six halves ≤ 1.53 %, K held.
* App 1.0.290 ships from main e42ae584 (seat clusters, OTHH trench/basins, LEMD 970/1088, K law, strip tie) — the HECA bow is still ≈ 11 m there; 1.0.291 after v2bow2.

## 2026-09-06l — v2bow (v2bow2) MERGED ad795571; the bow is the relaxation's ORDER, not a row class (spawner ruling)

* Merged: anisotropic junction planes (HECA plane rows 46,976 → 5,872; a box along the serving stretch at its longitudinal cap, across at the transverse cap), `[relaxation] runway_fit_weight = 0.0` (06h(b) off by default), the in-slab centreline join with the runway-line reading (06k), `runway_profile_smoothness` 5000, the `pad_flat` quantum tolerance. HECA: relief Σ 3,416 m / max 4.62 (06e 3,804 / 4.88), census 33 (was 42), v2-verify 27, solve 232 s (was 363), no DEFECT; CYXY/OTHH 0; 661 tests green. Bow UNCHANGED at −11.04 m.
* The lane's chain read on the identical LP refutes 06k's premise: the boxes bind alone for 2.6 m; the chain from the 23R pin to the s≈2218 hold is apron_edge_portion 1,060 m at 1.18 % (+12.5 m, RELAXED) and apron#364's 754 m frontage chord at 1.45 % (+10.9 m, RELAXED) — pav132's apron rows relaxed to 1.18–1.45 % of an allowed 2.5 % because the pure-variance stage 1 prices apron over-cap and prices sinking the runway at zero. At the full 2.5 × the apron's chain grants ≈ 22 m more and the hold vanishes (the law's 3.3 m bow). RULED (spawner, 04i law order applied to the last resort): the relaxation is LEXICOGRAPHIC — stage 1a minimises the RUNWAY family's departure from its hard-feasible best (its DEM-fit deviation, L1, the runway being senior) subject to every relaxed row within `max_over_cap_factor`; stage 1b minimises the slack variance at that runway; stage 2 as today. The runway sags only as far as the apron's allowance cannot cover. Lane `v2bow3`. Bars at HECA: bow ≤ 5 m, relief Σ quoted (may exceed 3,416 m — that is the trade the owner asked for), no DEFECT, census ≤ 33, six halves ≤ 1.53 %.
* Incidental (lane): HiGHS's 1e-7 tolerance — the relaxed hard set restated with a 1e-6 margin was OPTIMAL in one process and INFEASIBLE in another on the same exact rows (a 289-row Farkas core with presolve off); `highs.RESTATEMENT_MARGIN_M` is a knife edge to watch.

## 2026-09-06m — v2bow3 MERGED (fast-forward 4085694d + order key): the bow's floor is the law's; the order is the owner's trade

* v2bow3 delivered the lexicographic last resort (`solve/stage1.py`: 1a runway L1 departure, 1b variance holding the runway ± `runway_hold_tolerance_m`). HECA under it: bow −9.69 m (variance order −11.04), 05L/23R crest +1.9 (was +11.0), 05R/23L −9.64 unchanged (the DEM itself is −10.2 there — lawful); relief Σ 10,689 m / max 7.39 (variance 3,416 / 4.62); census 83 (variance 33); no DEFECT; six halves ≤ 1.53 %; CYXY/OTHH byte-identical (hard-feasible). THE FLOOR: with every relaxable row dropped and the low station pinned at line − 5 m the set is INFEASIBLE (188-row certificate): pav132's taxi-tier chain to the 23R pin — 21–26 no_step route pairs, 15–22 junction mesh edges at the stretch cap, 116–128 box planes, taxi centreline rows, 2 lateral hops — holds the ridge at ≈ −7.9 m (its DEM is −3.6 there; v1 bowed −9.3). The 5 m bar is not reachable under the tables; the sag is HECA's relief under the 1.5 % taxi law, not a budget error. Stage 2 re-sags 1a's −8.05 to −9.68 (the runway free again against the junior DEM fits); holding the runway in stage 2 gives −8.24 — measured, not landed.
* RULED (spawner): `[relaxation] order = "variance" | "lexicographic" | "weighted"` is a TABLE VALUE, shipped as `"variance"` (bow −11.0, relief 3,416 m, census 33) until the owner rules the trade — 1.4 m less runway sag against 7,000 m more apron relief and census 33 → 83. OWNER QUESTION 06m-1. App 1.0.291 ships the variance order.

## 2026-09-06n — Owner KML verdict on the sag chain: "not a valid route — only taxiway centreline routes count; no apron except a route through it; the red hop crosses two separate aprons with a lawful step" — RULED

* The owner's gold route (their KML over ours): 23R threshold → the parallel taxiway → the 05C/23C hold, **3,231.34 m** — at 1.5 % = 48.47 m, ceiling 109.13 m at the hold, line 115.2 → the route-only law sets a **6.1 m bow** at that station (v2 holds 107.43, −7.8; v1 −9.3). Our binding chain (39 rows) ran 1,937 m of it through apron pav132's edge-portion and frontage-chord rows and crossed from apron cell #364 to #363 where no traffic passes. RULED (owner's law, spawner's mechanism): (1) FEASIBILITY IS THE ROUTE'S — a runway's or taxiway's elevation may be chained only through taxi-centreline rows (the chain law 05ac) and the runway's own rows; apron rows (within-shape chords, edge portions, frontage, pad welds) never carry reach between two taxi routes; (2) two apron cells that no taxi route joins are SEPARATE TERRACES — their shared boundary is a lawful step: a terrace joint (the groundside `terrace_joints` machinery: split vertices at the joint, no row across it, the joint declared in the sidecar so the census reads it as lawful); (3) within one apron cell the apron law (1 % all directions, 05ae chords inside the face) stands; (4) a taxi route THROUGH an apron couples only the apron vertices along that route (the taxilane's own stretch rows and lateral hops), never the whole cell to another route. Consequence: the runway chain can only run along the gold route; pav132's hangar terraces step where no aircraft taxis. Lane `v2terrace`. Bar at HECA: 05C/23C hold ≤ 6.1 m under the line at the owner's station (+ K), the binding chain (why) taxi-centreline rows and runway rows ONLY, census ≤ 33, no DEFECT, six halves ≤ 1.53 %.

## 2026-09-06o — Owner sim read (1.0.291): ridges along both sides of 05C/23C — a law violation the instruments passed; the low point is the 109 m intersection and the runway minimises curvature

* Owner: the lowest point of 05C/23C is the 109 m intersection (the gold route's station; the 06n bar) and the runway otherwise minimises curvature (the 06k `runway_profile_smoothness` preference stays ON; K hard). The adjacent ground stands as RIDGES on both sides of the runway. Measured on the shipped patch (HECA_v2bow2): within 0.5–60 m outside the 05C/23C edge — stub vertices n 217, rise up to +6.02 m at 6.4 m from the edge (122 over 3 %·d), primary_parallel +3.55 at 12 m, graded_strip +3.47 at 5 m (36 over 3 %·d), junction ≤ +0.55. Every one of the worst vertices IS in a published route pair (attached), and the LP is optimal — so no hard row ties them to the runway edge 6 m away: the no_step pair to the adjacent runway-edge vertex was never minted, the strip tie (06e) was minted for 255 vertices and misses these (stub-owned rims are "own-law", strip vertices whose nearest pavement is the stub not the runway), and BOTH instruments (v2 verify `airside_no_step`/`strip_transverse`, the oracle's `airside_no_step_edges`) read only the pairs the generators PUBLISHED — blind by construction to a pair never priced; the oracle's chord law that would have read a 6 m step over 6 m is under the `withdrawn_law_05aa` heading. Instrument ruling (spawner): the adjacent-ground and cross-shape readers must be GEOMETRIC and generator-independent — every vertex within `zone` reach of a runway-family edge (any role) is read against the edge foot at the strip cap, every pair of airside vertices within the proximity window is read over their route distance (or, with no route, the chord — a 6 m neighbour is not the withdrawn 700 m chord: the withdrawn heading applies only above `withdrawn_chord_min_m` = 30 m). Scout dispatched for the row-level attribution of one ridge vertex before the fix lane.

## 2026-09-06p — the 05C/23C ridges attributed (scout `scout_heca_ridges/`); RULED: the runway-edge tie for every vertex, hops at the perpendicular foot, geometric readers

* Worst vertex v2921 (stub pav101 ring + strip hole, 30.117613,31.422610): z 112.12 = its DEM; the runway edge 6.94 m away is cut to 106.12 (DEM 111.91). Its only rows: ONE lateral hop to crossing station v2682 **482.56 m** away (bound 7.24 m — pav101's stretches are stationed hundreds of metres apart and the hop prices d_perp + the along-walk), three no_step rate triples, three strip arc-rate triples, the reach band (floor 100 m). NO no_step §1.1 pair: `route_neighbours` (K 16, window 150 m) finds nothing — the runway edge is 956 route-metres away through the hop. NO strip tie / zone row: `zones.py` `own_law` exempts every ring AND hole vertex of every airside value face. The ridge IS the DEM: the runway is cut 3.4–5.8 m below its DEM to reach the 109 m intersection and nothing joins the stub/strip 7 m away. Readers: v2 `strip_transverse` excludes non-strip vertices and hole rings (`gap_interior_ring` features), `airside_no_step` reads the published list, the oracle's `adjacent_ground_tear` matches `ref == "adjacent_ground"` (v2 refs never match — EMPTY on every v2 patch), `cross_shape` at 0.5 m, and `stamp_withdrawn_taxi_chords` stamps every taxi|taxi within_shape row (stub|stub 13,004, worst 27.8 m) regardless of length — `withdrawn_chord_min_m` exists nowhere yet. Geometric read of the shipped patch (all runways, 0.5–75 m): 1,233 vertices in reach, 207 over the bound (stub 170, primary_parallel 35, junction 2); strip-only 0.
* RULED (spawner): (1) THE RUNWAY-EDGE TIE — every vertex of ANY role (ring or hole, any owner except the runway family and retaining-wall crests) lying abeam a runway-family ring edge within that runway's zone-2 half-width is tied to the edge foot on the RISE side: `z_v − z_foot ≤ strip_transverse_bound(d, code)`; the fall side stays the vertex's own law; `own_law` exempts nothing from this row. (2) A LATERAL HOP attaches at the PERPENDICULAR FOOT on the centreline segment (a virtual station interpolated between the segment ends, as the crown rows do with (a,b,t)), priced at the transverse cap × d_perp only — never nearest-station + along-walk. (3) READERS are geometric: v2 verify and the oracle read the tie over every vertex within the half-width (the oracle's family keyed on v2's `adjacent_ground:*` refs), the oracle's `withdrawn_law_05aa` stamp applies only to chords ≥ `withdrawn_chord_min_m = 30.0` (a 7 m stub|stub step is priced). Accepted consequence: the strip's zone-3 outer ring terraces where the corridor cannot reach the runway cut (lawful, `zones.toml`). Lane `v2ridge`. Bars at HECA: geometric tie rows read 0 (was 207), stubs pav101/pav93 within the bound of the 05C/23C edge, the bow unchanged or better, census ≤ 33 + the newly priced short chords named, CYXY/OTHH 0.

## 2026-09-06q — v2ridge MERGED d002a473 (fast-forward): the runway-edge tie holds; two instrument rulings follow

* HECA: geometric tie read 208 → 0 (922 vertices in reach); v2921 +0.25 m at 6.59 m (bound 0.258; was +6.02); bow −10.71 (was −11.04); six halves ≤ 1.53 %; K held; no DEFECT; relief Σ 4,033 m / max 5.14; solve 250 s. CYXY / OTHH v2-verify 0 (tie rows 75 → 257 / 205 → 1,150; bodies moved ≤ 0.70 / ≤ 0.09 m). Hops now attach at the perpendicular FOOT (5,225 feet at HECA); v2921's route to the edge is still 951 m — pav101's own centrelines are crossings 473 m off — the TIE is what binds it. 671 tests green.
* RULED (spawner): (1) the oracle's SHORT-CHORD reader (taxi|taxi pairs under `withdrawn_chord_min_m`) prices the BOX, not the isotropic chord: |Δz| ≤ longitudinal cap × |Δs| + transverse cap × |Δt| against the nearest stretch axis (the sidecar `axes`/`stretches`) — the 3,722 HECA rows the isotropic reading minted on lawful diagonals are not defects; (2) the runway-edge tie is TWO-WAY against the runway: a vertex within the zone-2 half-width may neither rise above nor fall below the edge foot faster than the strip bound; the pocket rule's nearest-pavement floor applies only where no runway edge is within reach (the 15 strip-hole vertices 0.35–1.25 m below the 05C/23C edge within 3 m are cliffs, not "own law"). Lane `v2ridge2`. Bars: HECA census ≤ 33 + zero isotropic short-chord rows, strip_transverse 15 → 0 both ways, geometric tie 0, six halves ≤ 1.53 %, bow ≤ current, CYXY/OTHH 0.

## 2026-09-06r — v2terrace MERGED 56ba256c: apron terraces stand; the bow now binds INSIDE one apron cell — owner question

* Delivered: `[terrace]` law (`cell_roles`, `neighbour_roles`, `joint_gap_m` 0.6, `max_step_m` 2.0 report-only), "joined by a taxi route" = a 1202 station on the shared boundary (groups = connected components), `planar/terraces.py::split_terraces` (copies 0.6 m inside the junior group's boundary — a true coincident vertex is unemittable, the mesh makes the wall as at the structure rim), joints declared in the sidecar in v1's record shape, both censuses read the step as lawful. HECA: 36 joints / 4,811 m / 212 split vertices (max step 9.87 m; #40|#363 1,193 m at 6.19 m; #363 an island), census adjudicated 21 (was 33), relief Σ 1,448 m / max 3.83 (was 3,416 / 4.62), v2-verify 37 = 26 pre-existing + 11 `strip_seam_tear` fixed post-build (a zone face wedged between two groups: an apron cell also retreats from a zone owned by another group). CYXY 7 joints (970 m, step ≤ 0.21 m — the taxiway-beside-apron class for the owner's read), OTHH 55 joints (11,263 m, all steps 0.00), both verify 0. 679 tests green.
* The bow: −11.05 m, unchanged. The binding chain (`HECA_terrace_binding_chain.kml`, 38 rows) no longer crosses cells: hold → taxi centreline / no_step (route-priced) → INSIDE apron #364: a 723 m frontage chord (relaxed to 1.35 %, +9.78 m) and a 399 m edge portion on junction #393's rim (1.30 %, +5.20 m) → junction #396/#359 mesh + taxi rows → 23R pin. #364 is joined to both routes by taxilanes, so 06n(3) (the apron law within one cell) couples the two routes through it; the apron rows relax only to 1.3 % under the variance order (06m). Lexicographic arm: hold −9.63, relief Σ 8,186 / max 7.39, the same chain. OWNER QUESTION 06r-1: (a) is the taxi part of that chain a valid route (the KML), and (b) may an apron cell touching two routes couple them (its 1 % law) — if not, the apron law within a cell applies only along each route's own corridor and the rest of the cell is a terrace against the other route; if yes, the bow floor under the tables is ≈ −9.6 (lexicographic) / −11.0 (variance), not the gold route's −6.1.

## 2026-09-06s — v2ridge2 MERGED: two-way tie, box reader; the short-pair BOX becomes generator law (spawner ruling)

* HECA: `strip_transverse` 15 → 0 both ways, geometric tie 922/0, v2-verify 26 (the pre-existing lateral_contiguity), no DEFECT, six halves ≤ 1.53 %, bow −10.71, relief unchanged; CYXY/OTHH verify 0. Accepted deviation: 06q's "pocket floor void near a runway" was measured to TEAR the strip 3.1–3.3 m in 3 m at 05L/23R's zone-2 outer ring (the corridor floor 62.0 vs the taxi lip 65.15) — withdrawn; the two-way tie alone closes the 15.
* The box reader (`check_grade` `taxi_box` reading on taxi|taxi pairs under 30 m) prices HECA 23,631 short pairs: 21,554 inside, **2,077 over** (CYXY 32) — REAL steps the generator permits: e.g. stub pav78 two rim neighbours 4.04 m apart with Δz 2.16 m; pav73 27 m across with 6.9 m — the chain law (05ab/ac) prices a rim pair through its feet there-and-back (hop + along + hop: 21.4 m over 1,427 m), so neighbours may carry metres. RULED (spawner): the BOX is generator law for SHORT pairs — every taxi-family pair under `withdrawn_chord_min_m` (30 m) within a face carries a hard row |Δz| ≤ cL·|Δs| + cT·|Δt| against the nearest stretch axis (≈ 24k Diff rows at HECA), and v2 verify reads the same population (lockstep with the oracle's `taxi_box`). Lane `v2ridge3`. Bars: HECA census ≤ 33 (box rows 2,077 → 0), v2-verify ≤ 26, bow ≤ −10.71, halves ≤ 1.53 %, CYXY box 32 → 0, OTHH 0.

## 2026-09-06t — Owner: "the taxi route still gets 1.5 % even when passing through an apron"

* RULED (owner): a taxi centreline route THROUGH an apron carries the taxiway law — the stretch's longitudinal cap (1.5 % by letter) along it and the taxi transverse cap across it — never the apron cap. 05v's "the 1202 taxilanes crossing an apron (at the apron cap)" is WITHDRAWN on the cap: the crossing stretches keep their own letter's cap in the route graph (`constraints/routes.py`), in the chain rows (`taxi.py` centreline + lateral hops, the 05ac chain), in the reach bands and the no_step route distances, and in `stretches.py`'s per-stretch caps; 04t-2 (a junction or road SHARING A LONG EDGE with an apron takes the stricter cap on that portion) is unchanged — it is about alongside, not through. The apron beside the route stays under the apron law (1 % all directions, 05ae chords inside the face, 06n terraces). Consequence at HECA: every route through pav132 (U, G1–G3, J2/J3 and the 19 unnamed chains) gains 50 % of budget; the 06r-1 hold and the box rows are re-measured under it. Lane `v2routecap`, sequenced after `v2ridge3` (same files).

## 2026-09-06u — v2ridge3 MERGED (030695fd): the short-pair box is generator law; grade materiality joins the rate readers' blind spot

* Lane `v2ridge3` (head 1c582d8c) merged. HECA: oracle `taxi_box` rows 2,077 → 3 (an axis tie-break at one pav129 vertex, fixed at head, HECA not rebuilt), census adjudicated 8 (bar ≤ 33), v2-verify 26 lateral_contiguity + 3 box, tie 922/0, six halves ≤ 1.53 %, K held, bow **−10.41** (bar −10.71), solve 198.5 s with 23,600 `taxi_box` Diff rows; CYXY box 32 → 0, OTHH 1 → 0, verify 0.
* The CYXY parity twin went red on the branch: ONE `airside_no_step` §1.2 rate station read **8e-6 over** its allowance plus the rounding blind spot — a knife-edge under the 2026-08-02 grade materiality (0.01 pp). RULED (spawner, precedent `verify/pads.py` and RULINGS 05g): the grade materiality floor is part of every RATE reader's blind spot — the oracle's shared `_rate_reader_blind_spot` (`check_grade.GRADE_MATERIALITY = 0.0001`, so `strip_arc` and `airside_no_step` both) and v2's `rate_breaches(..., floor=emit.materiality.grade)` (no_step and strip_arc). Verify 0 / oracle 0 at CYXY; suite 724 passed.
* NOT a generator margin change: the LP's no_step margin is unchanged; a reading under materiality is PASS-with-residual by the standing guard, never iterated on.

## 2026-09-06v — apron-route-cap round 1 (lane `v2routecap` 35e25cb8, unmerged): the spec's corridor box REFUTED by arithmetic; the apron beside a route is ANISOTROPIC

* Lane report: `edge_cap` no longer tightened by apron faces (chain rows, route edges, reach, no_step distances, transverse at the letter's cap); law key `[*.taxi] width_m` by letter; apron in-corridor short pairs boxed; oracle/verify lockstep; 9 twins. HECA: census 5, `taxi_box` 0, verify 26 (lateral_contiguity only), tie 922/0, halves ≤ 1.53 %, K 0.346 %/100 m, bow **−10.38** (unchanged within 0.03), corridor rows 408; CYXY/OTHH verify 0.
* REFUTED (measured on the fixture): a 1.5 % route through a 1 % apron is INFEASIBLE under any taxiway-width corridor — the apron's chords to the route stations (05ab keeps apron chords; 05aa withdrew long chords on TAXI faces only) re-cap it: any apron vertex with d(P,A)+d(P,B) < 1.5·d(A,B) (a 30 m-abeam vertex against stations 100 m apart: 58+58 < 150) forces Σ ≤ 1.17 m over 1.5 m. At HECA the chain still crosses #364 on 806 m and 311 m apron chords RELAXED to 1.47 % (+11.85 m of the +47.2 m chain).
* RULED (spec author, physics of a continuous surface; owner question 06v-1 below): within an apron face crossed by a stretch, EVERY priced pair (ring edges, spine chords, body chords under their existing gates and the 05ae face-cover gate) is the BOX against the crossing stretch axis NEAREST the pair's midpoint (ties strictest) at ANY length: `|Δz| ≤ cL_stretch·|Δs| + cA·|Δt|`, cL the stretch's longitudinal cap (1.5 % C–F), cA the APRON cap (1 %) across. The corridor and `apron_corridor_pair_max_m` are withdrawn (delete the knob). Faces crossed by no stretch: unchanged isotropic. The oracle and v2 verify read the same population (lockstep). Consequence: a crossed apron cell may tilt 1.5 % along its route's direction everywhere; across it stays 1 %.
* OWNER QUESTION 06v-1: is 1.5 % along the route direction acceptable over the WHOLE crossed apron cell (the surface a 1.5 % route through a 1 % apron physically requires beside the route), or should a crossed cell stay 1 % away from the route (which re-caps the route to ~1 % — the arithmetic above), or terrace at the lane's edge? Implemented as ruled pending the answer.
* Deviations accepted: `role_family == "apron"` names no family — keyed on the emitted role `apron`; `test_pad_route`'s "apron-to-apron path at 1 %" premise withdrawn by 06t.

## 2026-09-06w — OWNER: aprons PREFER 1 %, are ALLOWED 1.5 % wherever needed to minimise runway drag, higher at back edges between buildings (supersedes 06v; answers 06v-1 and 06r-1)

* Owner, on the crossed-cell KML: "Nothing in that KML file should be effecting the route between the runways. All the red marks are where parking lines lead into the apron from the main taxi routes... maybe the simplest solution is to just allow aprons to go to 1.5 % wherever needed to minimize runway 'drag'. Aprons prefer 1 %, but allow 1.5 % (and even higher at back edges between buildings in some cases)."
* RULED (owner; the law as the session states it): the APRON GRADE LAW IS TIERED —
  1. **Hard cap 1.5 % in all directions** (`[*.apron] max = { longitudinal = 0.015, transverse = 0.015 }`, both authorities) on EVERY apron row the law prices today (ring edges, frontage/spine chords, body chords under the 60 m gate and the 05ae face cover, edge portions, stand entries). An apron can never drag a runway harder than a taxiway would (08-24b: "an apron spanning between two lawful 1.5 % taxiways lawfully runs ~1.5 % itself").
  2. **Preference 1 %** (`[*.apron] preferred = 0.010`): the same rows carry the 1 % cap as a PREFERENCE (`Diff.soft` escalation group per apron face, `ceiling` = the hard cap — the existing preference machinery), charged in the objective JUNIOR to the runway family's own objective (profile fit / curvature — 04i law order: the runway first) and SENIOR to the DEM fit. The solver spends apron grade above 1 % only where a senior law (the runway's minimal sag, a taxi route's 1.5 %, a pad seat) needs it, and reports it: per face, the max grade and the number of rows above 1 % (sidecar + `why`).
  3. **Back edges between buildings: the 08-24 class** — chords between ADJACENT pads at the apron's back edge (the `plan_fan_ramp_zones` predicate of 2026-08-05/08-24, never ported to v2) hold `apron_fan_ramp_max` (5 %, the standing table value) hard with the same 1 % preference. Everywhere else 1.5 % hard. Owner: "in some cases" — the value and the predicate are the 08-24 ones until the owner revises them.
* WITHDRAWN: 06v's anisotropic box (any length) and the spec's corridor box; the "crossed cell" concept (a stretch with an edge on the apron ring catches stand lead-ins, not through-routes); 06v-1 is answered. 06r-1 is answered by (1): an apron cell touching two routes couples them at no worse than 1.5 %, the taxiway's own cap. 06t stands (a route through an apron at its letter's cap — with (1) it is consistent without any box; round 1's `edge_cap` change and `[*.taxi] width_m` key stay). 04t(1) last resort: the hard cap is now 1.5 %; relaxation above it stays certificate-scoped as before. Oracle lockstep: `check_grade` reads apron rows against the HARD cap (1.5 %; 5 % on back-edge chords), and reports rows above the preference as a REPORT FIGURE (`apron_over_preference`), never a violation.
* Lane `v2routecap` round 3 (rounds 1–2's box work discarded, branch reset to round 1's 35e25cb8 minus the corridor box and knob). Bars at HECA: bow shrinks toward the owner's 6.1 m floor (quote), census ≤ 5, verify ≤ 26, halves ≤ 1.53 %, K held, CYXY/OTHH verify 0.

## 2026-09-06x — v2routecap MERGED (278be9fc): tiered apron cap live; the bow is held by the OBJECTIVE ORDER (0.72 m) and by apron #364's own 1.5 % surface

* Merged (fast-forward). Law: `[common.roles] apron`/`building` = `{preferred = 1 %, max = 1.5 %}`; every apron pair carries a hard row at max + a preference row at preferred (one escalation group PER ROW — accepted deviation: `assemble` charges a group by Σ chord metres, a per-face group would price a junction's whole population against one escalation); `apron_over_preference` report figure in sidecar/report/why/verify/oracle/census; oracle reads the hard cap through the sidecar's `apron_tier`; round 1's `edge_cap` and `[*.taxi] width_m` kept; the box work deleted. Suite 699 passed.
* HECA: census 6 (5 strip_seam_tear + 1 vertex_to_edge_step, NEW beside pav131 which rose ~1 m — owed), verify 32 (26 lateral_contiguity + those 6), bow **−10.38 unchanged**, ridge min 104.60 @ 2,732 m, halves ≤ 1.535 %, K 0.348, tie 922/0, relaxed rows 4,319 → **184** (the 1.47 % apron chords are lawful now), solve 222.9 s; apron faces over 1 %: #215 1,010 rows, #264 1,007, #389 852, #364 749 (max 1.67 %). CYXY verify 0 (2 rows over preference), OTHH verify 0 (0 of 59,701).
* WHY THE BOW DID NOT MOVE (`why`, chain KML sent to the owner): the chain from the runway vertex v1444 (z 107.89) to the 23R CIFP threshold pin (z 60.66) is 39 hops, Σ +47.24 m: no_step +18.3, **apron preference +16.0 (hops 16–17: an 806 m and a 311 m chord across apron #364/#398 at 1.445 % / 1.41 %)**, junction mesh +5.1, taxi centreline +4.8, transverse +1.7, strip tie +1.2. Two findings: (1) the preference rows bind BELOW the hard cap (dual −18): in the single weighted stage the apron preference (18/m × hundreds of parallel rows) outweighs the runway fit (20/m × a few dozen vertices) — the ruled order (runway ≻ apron preference ≻ DEM) is LEXICOGRAPHIC; fully spent the tier lifts the chain +0.72 m (bow → −9.66). RULED (spawner): implement the lexicographic order — lane `v2lexi`. (2) With the apron at 1.5 % the coupling across #364 is the apron's OWN surface (1,117 m at 1.5 % = 16.8 m), a shorter path than the owner's 3,231 m taxi-only gold route (48.5 m budget → 109.1 m at the hold); the apron chord path gives ≈ 108.6 m. Under 06w that is lawful — the owner reads the KML and rules whether the #364 crossing is the intended coupling (OWNER QUESTION 06x-1).
* Owed: 06w (3) back-edge 5 % class (`plan_fan_ramp_zones` port, ~400–600 lines); the 6 new HECA rows; oracle population divergences (every spine chord vs nearest-spine; any-length apron pairs).

## 2026-09-07a — HECA 05C/23C sag ATTRIBUTED by ablation: the apron cell #364 spans two routes 34 m apart by ceiling; lexicographic order REFUTED (lane v2lexi)

* Lane `v2lexi` replay on the captured HECA set (`scratchpad/lexi_replay.py`, 23,694 vertices, 323k rows): stage A alone (runway objective, hard rows only, no preference charged) gives the SAME runway (v1444 107.89, bow −10.41); stage C fails (HiGHS kUnknown / kSolveError) and the wall is 3.4× (238.6 vs 69.7 s). The apron preference was never the mover; the objective order is REFUTED as a fix — NOT merged (branch parked for its tooling: `tools/rwy_profile.py` promoted a63b44fd; the `[objective] order` mechanism is to be deleted, refuted mechanisms are not kept gated).
* INTERVENTIONAL ablation (spawner, `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` on the same capture, weighted objective; bow = ridge z − threshold line on 05C/23C; v1444 = the hold):

  | rows kept | bow | v1444 |
  |---|---|---|
  | runway family only (pins, K, transverse, crown, DEM fit) | −3.49 | 112.05 |
  | + no_step §1.1 ROUTE pairs | −6.55 | 109.30 |
  | + taxi CHAIN rows (05ac centreline + lateral hops + crossings) | −7.01 | 109.41 |
  | + whole taxi family (chain + 28k short-pair box) | −8.90 | 109.03 |
  | everything (built) | −10.41 | 107.89 |
  | everything minus apron / minus junction / minus taxi / minus roads / minus no_step / minus zones / minus strips / minus transverse / minus pads (one at a time) | −10.20 / −10.20 / −10.30 / −10.37 / −10.41 / −10.41 / −10.41 / −10.41 / −10.41 | ≈ 107.9 |
  | minus apron+junction+taxi+roads together | −7.02 | 109.39 |

  The route graph (05aa: centrelines, hops, crossings — `reach_path_kml.py`) ceilings 05C/23C at −3.14 below the line (station 2,062, via the 23R pin 60.66 over 3,436 m) and the hold v1444 at 114.70; runway + route-priced pairs puts the hold at **109.3 = the owner's 109 m**. The last 2–3 m come from SURFACE families that are each a shorter continuous 1.5 % path than the routes and are REDUNDANT with each other (removing any one reroutes through another): apron chords, junction-body mesh, short-pair box chains along taxiway rings, road profiles.
* THE SITE: apron cell #364 (pav132, 176,501 m²) touches two routes whose contacts v10228 (north, route ceiling 111.35) and v10564 (south, 77.19) are **2,725 m apart by taxi route (40.9 m of budget) and 1,117 m apart across the cell**; its mid vertex v10154 has NO route at all. A continuous 1.5 % surface across the cell holds 16.8 m of the 34.2 m difference, so it pulls the north contact down 19.8 m (built 91.57) and the runway hold with it (114.70 → 107.89). The same span is bridged by junction #397's mesh, the taxi rings' box chains and the service roads — hence the redundancy. KML `HECA_apron364_contacts.kml` sent to the owner. This is 06r-1 measured: an apron cell touching two routes DOES couple them, through its own surface, and 06w's 1.5 % is not enough here (3.1 % would be).
* OWNER QUESTION 07a-1 (the ruling that sets HECA's sag): across the #364 span (and its junction/road neighbours), which is lawful — (a) a TERRACE JOINT inside the cell between its two route contacts (06n extended to within a cell along a line no route crosses; the roads and junction bodies there step with it), (b) steeper surfaces there (the 06w "higher in some cases": the cell holds 3.1 %, roads their own caps), or (c) accept the sag (v1 built 9.3 m; v2 10.4)? Until ruled, the built surface stands.

## 2026-09-07b — lane v2lexi CLOSED (d4d4f7ff, NOT merged): the objective order is refuted at HECA and regresses the census

* Final report: lexicographic A/B/C stages on one HiGHS model (per-column bounds as holds; the dense hold row form ended stage C in kUnknown), HECA solve 222.9 → 156.4 s, CYXY +0.9 s, OTHH −0.5 s, verify 0/0 there. HECA bow −10.38 unchanged; a ceiling probe (max z[v1444] over the HARD rows with every preference free) returns 107.890 — the hard set alone holds it, confirming 07a's ablation. Census 6 → **14**: with the apron preference senior to the apron's DEM fit, pav47 (#95) rises 2.1–2.6 m off its relief and tears the strip 4.15 m (the strip↔apron-ring tie has no row, 06p own-law exemption).
* RULED (spawner): NOT merged; refuted mechanisms are deleted, not kept gated — the branch is parked only until its scratch tooling (capture / replay / probe scripts) is promoted on second use. Harvested onto main: `tools/rwy_profile.py` (cherry-pick of a63b44fd; twin owed). Owed from the report: the strip↔apron-ring tie (one consumer table first, 30l); pav47/pav131 apron-over-relief tears.

## 2026-09-07c — OWNER: an apron point's route is a VISIBLE PATH inside its apron shape to a taxi route, then centrelines only — no shortcuts across aprons (answers 07a-1 and 06r-1; extends 06n INSIDE a cell)

* Owner, on `HECA_apron364_contacts.kml`: "Why would it have any impact on the runway? The lines don't even reach either runway, and the red line is crossing between two separate aprons that are not connected, AND wherever there is a taxi route, we always have to follow that, no shortcuts across aprons. For any given point on an apron, its route to runways must be a visible path (cannot exit the apron shape) to a taxi route, then along taxi centerlines only."
* The impact, stated once: the chain (`HECA_v2routecap3_binding_chain.kml`, 39 hops) runs runway hold → 23C stub → parallel taxiway → cross connector → junctions → #364's NORTH contact (hops 1–15, all taxi/junction rows), then the red chord across the cell (16–17), then junctions → the 23R end (18–39). The taxi route between the two contacts is 2,725 m; the chord 1,117 m; the runway is dragged by the difference (07a ablation: runway + routes alone puts the hold at 109.3 m = the owner's 109 m).
* RULED (owner's law; spawner's mechanism, spec `apron-reach-territory-spec.md`): (1) REACH: every apron vertex's budget from the runways is the least over its CONTACTS (taxi-centreline stations on the cell boundary or on a route through the cell) of [the apron cap × the in-shape VISIBLE path length to the contact] + [the route graph's budget from the contact] — the apron shape is never exited, no chord across the cell, no ring edge, no road, no junction body is a route. (2) TERRITORIES: the cell is partitioned by nearest contact (in-shape path); two adjacent territories whose contacts' route ceilings differ by more than the apron cap can hold along the in-shape path between them are SEPARATE TERRACES — the owner's "two separate aprons that are not connected" — and their boundary is a JOINT (06n machinery: split vertices, no row across, declared in the sidecar, keep-outs unchanged). Territories no route reaches are islands (06n). (3) The joint line CONTINUES through every face that spans the same two territories — junction bodies, roads, pads (a road ramps to the joint at its own cap on each side; a pad belongs to one territory) — so no surface family of any role bridges what the routes do not (07a: apron chords, junction mesh, taxi-ring box chains and road profiles were each a shortcut). (4) 06w's tiers stand INSIDE a territory (prefer 1 %, max 1.5 %); the back-edge class is owed. 07a-1 is answered (a): terrace, never steeper, never accept.
* Bars at HECA (the 06n bar restored): the 05C/23C hold at the 109 m intersection ≤ 6.1 m under the line (+ K), the ridge minimising curvature, the `why` chain taxi-centreline / crossing / runway rows ONLY, joints declared and read lawful (census ≤ 14, no DEFECT), six halves ≤ 1.535 %, CYXY/OTHH/LEMD verify 0 with their joints quoted. Lane `v2terrace2` (Fable).

## 2026-09-07d — OWNER: back edges need no fans or zones — the pair between two pad corners across a gap simply carries 5 %

* Owner: "we are creating a patch file that specifies the elevations we want at specific nodes, then the engine applies that to the mesh, automatically interpolating with the base DEM. If we have a back apron node at one pad corner at one elevation, and then a 10 m gap and another pad that we want to be lower we just set the elevation for that node so it would be a 5 % grade."
* RULED (owner's law; spawner's mechanism): 06w (3)'s `plan_fan_ramp_zones` port is WITHDRAWN. The back-edge class is a PAIR CAP: an apron ring edge (or an apron pair under the identity gate) whose two vertices are frontage/contact vertices of two DIFFERENT pads, on a ring run that no taxi route or stretch touches (the back edge between buildings), carries `apron_fan_ramp_max` (5 %, `rulesets.toml`, the 08-24 value) as its HARD cap in place of `max` (1.5 %); the 1 % preference row stays (06w). Nothing else changes: the mesh interpolates the DEM between the two nodes. Oracle lockstep: the census reads the same pairs at 5 % (the `back_edge` reading beside `apron_over_preference`); v2 verify likewise. Twin: two pads 10 m apart on an apron's back edge with a 0.5 m step between their corners → feasible, read lawful; 0.6 m → a row. Implementer: a short lane after `v2terrace2` (same file `constraints/apron.py`), or folded into that lane's close if it finishes with budget.

## 2026-09-07e — OWNER: the HECA pack "incorrectly connects the two aprons" at 30.127729, 31.412022 — the territory joint is inferred from the routes serving each side

* Owner: the pack's apron polygon joins the two aprons there; "maybe we can tell based on the taxi routes that serve the two aprons from opposite ends but don't connect through here". Measured: the point lies inside #364 (pav132, 176,487 m²); the polygon is 126 m wide at that point (a wide connection, not a sliver weld) — so 06n's weld rule cannot see it and 07c's territory rule is the instrument: the two halves' contacts are reached from opposite ends and no route crosses the connection, so the territory boundary — the joint — falls across it. ACCEPTANCE SITE for lane `v2terrace2`: the minted joint polyline crosses within 60 m of 30.127729, 31.412022 (checked at merge; the owner reads the joint KML).

## 2026-09-07f — lane v2terrace2 CLOSED unmerged (f25ffcf5): the in-cell face cut is refuted on geometry; the spec's reach metric was the shortcut; construction moves to a PRE-ARRANGEMENT POLYGON CUT

* Lane findings (kept): pav132 is ONE apt.dat 110 polygon (509,514 m², 6 holes) that classification cuts into 28 faces — no weld to exploit; §2's literal metric (`cap·d_inshape + budget`) mints NO joint (the south contact "owns" the north contact: 81.67 + 0.015 × 541 = 89.8 < 125.16 — the apron itself became the route); agreement is not transitive (pairwise only); the partition must run over the welded pavement complex, not per face; cutting existing faces along a geodesic seam through ~6 junction faces fails: refused cuts, end copies inside the identity spacing on 0.5 m arcs, and DEAD-END lane stations (taxi202/205/206, no route to a runway) re-join the halves under 06n's "station on the boundary" rule. HECA: bow −10.40, DEMOTED, census 112 FAIL, verify 43, solve 458 s. CYXY minted 5 small joints 06n had not. Not merged; branch is the record. Twins and the census table stand as reference.
* RULED (spawner, spec §2a): (1) TERRITORY = nearest RUNWAY-CONNECTED contact (a station on a route the route graph joins to a runway threshold; a dead-end lane's stations serve no territory and never join cells); the metric decides only the PREDICATE (pairwise, adjacent territories). (2) The joint is a CUT OF THE RAW PAVEMENT POLYGON before the planar arrangement: the shortest chord of the polygon (holes respected) that separates the two territories' contact sets and crosses no runway-connected centreline — the "neck" (owner 07e: the pack's incorrect connection; at HECA the 126 m chord near 30.127729, 31.412022 is the expected answer). The two pieces are then ordinary cells and 06n's between-cell machinery (join only through runway-connected stations; split copies; declaration) does the rest — no in-face seam, no interior joint vertices. (3) Faces of other roles (junction bodies, roads, pads) inside the same pavement polygon are cut by the same chord at classification (they are pieces of the same 110 polygon or overlap it), so the seam is one polyline through the complex; a road crossing it ramps on each side at its own cap. (4) A pavement whose contacts all agree (the predicate false for every adjacent pair) is never cut. Lane `v2terrace3`.

## 2026-09-07g — OWNER reframes the route law: an apron is a route link only when there is no other way between runways; every other node takes the shortest visible in-shape path to a centreline route, then the route (supersedes 07f's polygon cut)

* Owner: "the only time an apron can be counted as part of a centerline route is when there is no other way for the route to connect between runways. Nodes not on the route must take the shortest visible path to a centerline route without leaving the apron, then follow the main route."
* RULED (owner's law; spawner's mechanics — no geometry): (1) THE ROUTE NETWORK is the 1202 centrelines joined to the runways (05aa/06n unchanged); an apron pavement joins the network as a link ONLY when a runway (or a route system) is otherwise unreachable — then the shortest in-shape path across it, at the apron cap, is the link (the feasibility fallback; report every airport where it fires). (2) SERVING CONTACT: every pavement node not on a route is served by the runway-connected route contact it reaches by the shortest visible in-shape path (never leaving its pavement complex); its reach band = the contact's band ± the apron cap × that path (`routes.reach` extended by the in-shape leg). (3) JOINTS WITHOUT CUTS: two adjacent nodes served by contacts whose bands disagree by more than the surface can hold between them (07f's pairwise predicate) form a JOINT EDGE — no row of any family is priced across it (within-shape chords, edge portions, junction mesh, box pairs, hops, road profiles, no_step), it is declared in the sidecar `terrace_joints` so both instruments read the step as lawful, and the mesh builds the step from the two node elevations (owner 07d: "we just set the elevation for that node"). No polygon cut, no split copies, no seam geometry: the joint is the label boundary. (4) A road crossing a joint: its profile rows stop at the joint; report the step the road takes (a ramp needs a ruling). (5) Everything else stands: 06n between cells (a cell no runway-connected station touches is an island), 06t, 06w, 07d.
* At HECA the label boundary of pav132's complex falls where the north and south contact sets meet — the owner's 07e neck (30.127729, 31.412022): the acceptance site. Lane `v2terrace3` is redirected to this construction (its polygon-cut work discarded; its partition/predicate kept).
