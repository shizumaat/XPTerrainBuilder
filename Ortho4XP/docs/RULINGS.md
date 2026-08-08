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
