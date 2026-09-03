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

## 2026-08-25b — Owner ruling: an edge-sharing road conforms to the apron's law (strictest grade); enforcement of the free-road ruling ordered

*(Recovery note, 2026-09-03: the seven lettered 2026-08-25 rulings below — b through h — were committed on 2026-08-25 to a stray `docs/RULINGS.md` at the repository root: after the engine tree moved under `Ortho4XP/`, the first append (commit 00383cc) created a NEW file at the old root-relative path instead of extending this one, and the rest of the day's rulings followed it. Merged here verbatim from that file, which is deleted in the same commit; original ruling commits 00383cc, 8bdce6e, 4aeff6c, 788389d, 5163ea7, 9b715a4. The same accident stranded that session's specs in the root `docs/specs/`; `road-band-seal-scope-spec.md` is restored to `Ortho4XP/docs/specs/` in this commit.)*

* **A ROAD SHARING AN EDGE WITH AN APRON CONFORMS TO THE STRICTEST GRADE — IT BECOMES PART OF THE APRON (owner 2026-08-25b, sharpening the standing free-road ruling).** Edge-sharing contact (canonical identity, not proximity) puts the road ring under the apron's law: apron caps price its pairs, apron seeding governs (no DEM-follow inside the contact), and downstream consumers (the graded-strip adoption, the seal) see ONE family at those nodes. The 2026-08-25 HECA measurement (12 road↔airside contact rings, worst 2.22 m over 1.00 m) is the enforcement gap: the free-road scoping already claims such roads at slice time in principle, and the implementation must close whatever path let these rings escape.

## 2026-08-25c — Owner ruling: EAT recognition is a routed wrap + vacuous-surface far bound + cut-only pin (LEMD has no EATs; amends 2026-07-27 clause 2)

* **EAT RECOGNITION IS A ROUTED WRAP, BOUNDED BY THE SURFACE'S OWN GEOMETRY, AND THE PIN ONLY CUTS (owner 2026-08-25c; refines 2026-07-27 after LEMD's 149 false pins — LEMD HAS NO EATs).** Three clauses: (1) RECOGNITION — an EAT crossing is a TAXI ROUTE (centerline) crossing the extended-centerline corridor, connected to the airside network on BOTH sides (a wrap); apron/junction rings with no through-centerline NEVER qualify, whatever the geometry. (2) FAR BOUND — pin nothing beyond D = setback + tail_height/slope (the distance where the regulation surface clears the tallest tail): past it the ceiling binds nothing, so recognition there is vacuous by the regulation's own geometry; no new tuning constant. (3) PIN SEMANTICS — the regulation is a CEILING: pin only where it CUTS (regulation below the pavement's unconstrained level); where the surface is already above, nothing is pinned. Amends 2026-07-27 clause 2 ("even if it has to fill DEM"), which was formed on a cut (KATL Victor) and never intended to lift pavement into the air. Measured basis: every LEMD contradictory anchor pair is EAT-pin vs EAT-pin at 1.0-4.6 km (aprons under the projected centerline, 59-66 m above adjacent pavement); real EATs cross at 439-482 m (KCLT).

## 2026-08-25d — Owner ruling: EAT recognition cap 600 m

* **EAT RECOGNITION CAP AT 600 m (owner 2026-08-25d, closing 25c's survivor).** In addition to the vacuous-surface bound, no EAT rect is recognized beyond 600 m from the DER — real EATs measure 439-482 m (KCLT); LEMD's surviving routed wrap at D=1066 m is not an EAT (owner: LEMD has no EATs). `EAT_MAX_CROSSING_DIST_M = 600`.

## 2026-08-25e — Owner ruling: a portal approach claims and lowers unclaimed pavement (mouth-D option a); per-piece named refusals required; inset deferred

* **A PORTAL APPROACH ON UNCLAIMED PAVEMENT CLAIMS AND LOWERS IT (owner 2026-08-25e, mouth-D disposition).** When a mapped tunnel mouth's outward approach corridor lands on airside or landside pavement, the ramp CLAIMS the corridor's own footprint and lowers it to the bore profile — option (a) of the 2026-08-25 attribution's three. The claim is the CORRIDOR FOOTPRINT only, never the host shape whole; the host pavement grades to the lowered corridor's edges under its own law (steps only at pavement gaps; walls/trench emit through the host as at any bore). PREREQUISITE INSTRUMENT (required regardless): every post-emit tunnel-piece remover names each piece it deletes — ref, way id, centroid lat/lon, predicate, coverage fraction — a silent aggregate line is the defect that made mouth D unattributable for three weeks. The ramp-wall inset question (R16-2b reopen) is DEFERRED to the owner's next in-sim pass.

## 2026-08-25f — Owner ruling: a pad inside a basin sits at the basin floor (building8 disposition)

* **A PAD INSIDE A BASIN SITS AT THE BASIN FLOOR (owner 2026-08-25f, the building8 disposition).** A building pad whose footprint lies within a basin facility's footprint is BELOW the surrounding grade: it seats at the facility floor, and the basin cut emits through it (the R13 pit cut extends to pads inside the facility; the floor is never differenced away against such a pad). LEMD building8 (33,447 m² over the real sunken tower circle) is the exemplar — the owner: "building8 should be below apron grade."

## 2026-08-25g — Owner ruling: roads are laterally flat — the cross-section limit is law (KAFW N-1 resolved)

* **ROADS ARE LATERALLY FLAT — THE CROSS-SECTION LIMIT IS LAW (owner 2026-08-25g, resolving the KAFW N-1 open question from 2026-08-20).** The owner's in-sim read of 1.0.259: roads improved but "still have a lot of bumps and laterally not flat." Within-ring TRANSVERSE road pairs (≥45° to the axis) price at the road CROSS-SECTION limit, not the longitudinal chord cap — the N-1 class (2-8% transverse, under the 8% chord cap, over the cross-section limit) is a defect population, not lawful.

## 2026-08-25h — Owner ruling: service roads in apron contact are spines at the apron 1 % cap; no road/apron alternation along apron edges

* **SERVICE ROADS IN APRON CONTACT ARE SPINES AT THE APRON CAP (owner 2026-08-25h, the apron-chain disposition).** Anywhere a ground truck route runs ALONG or THROUGH an apron, its centerline creates a SPINE through the apron — it functions like a taxiway for grading: a solved longitudinal profile the membrane anchors to, and a first-class centerline target for the nearest-anchor chord law — but unlike a taxiway it ADOPTS THE APRON'S 1 % CAP, never the road cap. THERE IS NO ALTERNATING between road and apron values along an apron edge: the shared edge carries one solved surface. Scope: grading/anchoring only — `REACH_NO_SERVICE_SPINES` stands untouched (aircraft reachability never rides truck routes; the spine is a scaffold anchor, not a band route). Free roads outside apron contact are unchanged. Extends the free-road ruling and 2026-08-25b; the measured basis is the back-edge alternation defect (apron -10582, 0.89 m sawtooth at 10.5 %) both round-2 lanes proved unownable by strip or road machinery.
