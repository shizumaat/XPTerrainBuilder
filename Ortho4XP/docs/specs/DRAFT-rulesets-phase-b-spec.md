# DRAFT — Region rulesets, phase B: the FAA/ICAO split

Fable design DRAFT for lead review, 2026-08-04. BINDING: docs/RULINGS.md
— the region-rulesets ruling (2026-08-02, owner verbatim: "FAA applies
within the USA, and ICAO everywhere else … support region specific
regulations and provide the code structure to allow the possibility to
choose and/or support multiple rulesets in the future"); grade-law
completeness (emitters and validators read the SAME ruleset, lockstep);
jurisdictional fidelity supersedes "take the stricter".

Phase A was the prep, already landed piecewise: per-authority constants
NAMED alongside blended values (the RSA round's
`RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE` +
`…_FAA` pair and grade_law's `ruleset: str = "icao"` parameter are the
extant pattern). Phase B = the structure, the resolution, the split,
the migration. SEQUENCING: phase B lands BEFORE the remaining reg
families (DRAFT-reg-families-round-spec.md) so new families are born
ruleset-keyed — and phase B is an ANCHOR-MINTING EVENT (see §8).

Every regulatory number below is primary-verified against the retained
source texts (`standards_gap/ac13b.txt` = FAA AC 150/5300-13B chg1;
`annex14_bazl.txt` + `icao_sl_amd18.txt` = ICAO Annex 14 Vol I;
`cs_adr_dsn_i7.txt` = EASA CS-ADR-DSN Issue 7). Identity anchors are
cited symbolically as "the tip table" (refpull_interim/RESULTS.md
§CAMPAIGN ANCHORS); RE-PIN AT DISPATCH.

## §1 The ruleset structure (first-class, never branches)

* `config.py` gains a RULESET REGISTRY: `RULESETS = {"faa": …,
  "icao": …}` — a mapping from ruleset key to a constants table
  (dataclass or module-level dict; implementer picks, says why). Keys
  are open-ended: "tp312" (Canada), "casa" (Australia), etc. can be
  added without structural change (the owner's "multiple rulesets in
  the future" clause). NO `if icao.startswith("K")` at any law site —
  a law site reads its constant from the resolved ruleset object only.
* Accessor pattern: the existing
  `runway_strip_max_longitudinal_slope(code_number, ruleset="icao")`
  signature is the template — every split family gets its accessor in
  grade_law/config keyed by the ruleset string; blended call sites
  migrate to pass the layout's resolved key.
* Owner-ruled and engineering constants that are REGION-INVARIANT stay
  plain constants, never enter the registry (§7).

## §2 Region resolution — USA → FAA, else ICAO

* `config.resolve_ruleset(icao: str) -> str`:
  first letter "K" → "faa"; two-letter prefix in {"PA","PH","PG","PJ",
  "PM","PW"} (Alaska, Hawaii, Guam/Marianas, Johnston, Midway, Wake)
  → "faa"; everything else, and empty/unknown → "icao". The owner's
  text is "within the USA": Canada (C…) and Mexico/Central America
  (M…) are ICAO under this ruling.
* EXPLICITLY NOT REUSED: `EAT_FAA_ICAO_PREFIXES` ({K,C,P,M}) — that
  set implements a DIFFERENT, earlier owner ruling scoped to the EAT
  departure surface ("FAA for North America"). The EAT surface
  selection is untouched by phase B (§7); the two resolvers coexist,
  each citing its own ruling. Flagged in the report for optional owner
  harmonization — not assumed.
* Default: ICAO ("everywhere else" is the owner's own default; also
  the fail-safe for unparseable identifiers).
* Override for testing and future UI: `O4_RULESET` env (values
  "faa"/"icao"; empty = resolve) + a per-airport config key later —
  the env knob is required now (the A/B arms in §9 use it).

## §3 Lockstep plumbing (the wire)

* Resolution happens ONCE, at build entry
  (`pipeline.build_airport_pavement`); `layout.ruleset` carries it;
  every law site reads `layout.ruleset` (or receives it — no site
  re-resolves).
* The `.axes.json` sidecar gains a `ruleset` field. `check_grade` and
  `verification` judge in the SIDECAR'S ruleset — never re-resolve
  from the ICAO code (the two-instruments law: production emits what
  it did; the validator judges the same frame). A missing sidecar
  field ⇒ "icao" + a loud stale-sidecar warning (matches the blended
  history: every existing sidecar predates the split).
* Test twins (source-inspection where a build is needed to reach the
  read site, per the ref-pull twin precedent): (1) resolver table —
  KCLT→faa, PANC→faa, PHNL→faa, HECA/SPJC/SPLP/CYXY/HEAZ→icao,
  ""→icao; (2) sidecar round-trip — the emitted sidecar's ruleset
  equals the resolver's answer, and check_grade consumes the sidecar's
  value; (3) lockstep — emitter and validator accessors return
  identical constants for both keys across every split family
  (parameterized over the §4 table).

## §4 The per-authority constants collection (every landed family)

Legend: BLEND = the live blended value and its source authority.
Class: IDENT (FAA == ICAO == blend; split is a no-op), SPLIT (values
differ; honest deltas §5), NA-F/NA-I (family exists in one authority
only), INV (region-invariant, stays out — §7).

| # | family / constant | BLEND (live) | FAA (citation) | ICAO (citation) | class |
|---|---|---|---|---|---|
| 1 | Runway longitudinal max (`RUNWAY_MAX_GRADE`) | 0.015 (FAA C–E) | A/B 0.020, C/D/E 0.015 (§3.16.1) | code 4: 0.0125; code 3: 0.015; code 1–2: 0.020 (§3.1.14) | SPLIT |
| 2 | Runway end-zone grade (`RUNWAY_END_GRADE`) | 0.008, first/last quarter, code 3/4 | >0.8% not acceptable within lesser(quarter, 2,500 ft/762 m), C/D/E (§3.16.1) | code 4: quarter @0.8%; code 3: quarter @0.8% for precision Cat II/III only; code 1–2: none (§3.1.14) | SPLIT |
| 3 | Runway max grade change | (via arc machinery) | A/B ±2.0%, C/D/E ±1.5% (§3.16.1) | code 3–4: 1.5%; 1–2: 2% (§3.1.15) | SPLIT |
| 4 | Runway vertical curve K (`DEFAULT_ARC_K_M`, `RUNWAY_MAX_GRADE_CHANGE_PER_M`) | 305 m/1% (FAA C–E) | C/D/E 1,000 ft (305 m)/1%, A/B 300 ft (91 m)/1%, none <0.4% (§3.16.1) | code 4: 0.1%/30 m (K≈300 m/1%); code 3: 0.2%/30 m; 1–2: 0.4%/30 m (§3.1.16) | SPLIT (4 vs 305/300: sub-2% value drift) |
| 5 | Strip longitudinal (`RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_*`) | ICAO by-code table | = `RUNWAY_MAX_GRADE` (§3.16.5 item 1) — already named `…_FAA` | {4:.015, 3:.0175, 1–2:.020} (§3.4.13) — live | IDENT at code 4; SPLIT at code 3 (FAA .015 vs ICAO .0175) |
| 6 | Strip graded half-width (`RUNWAY_STRIP_HALF_WIDTH_BY_CODE`) | ICAO {30,40,75,75} | RSA half-width by RDC, Appendix G (C/D/E-V verified: 500 ft width → 76.2 m half; pull remaining G-tables at implementation) | {1:30, 2:40, 3:75, 4:75} (§3.4.17 frame) | SPLIT (75 vs 76.2 at KCLT class) |
| 7 | Strip/RSA lateral transverse zone 2 (`RUNWAY_STRIP_BAND_*`) | FAA-mandatory-down min .015, max {3,4:.03; 1,2:.05} | S-3: A/B 1.5–5%, C/D/E 1.5–3% (Table 3-6) | ≤2.5% (code 3–4) / ≤3% (1–2), NO minimum mandate; first 3 m down ≤5% (§3.4.15) | SPLIT + OWNER QUESTION (the 2026-07-08 mandatory-down ruling was premised on the blended ruleset — see §10; until answered, BOTH rulesets keep the blended mandatory-down) |
| 8 | Zone 1 lip (`ADJACENT_GROUND_LIP_*`) | 3 m at 3–5% down | 10 ft at 5±0.5% (§4.14.2 item 4); Fig 3-33 3–5% first 10 ft | first 3 m down ≤5% permitted (§3.4.15) | SPLIT (same shape; ICAO is permissive not mandatory — rides the §10 owner question) |
| 9 | Zone 3 rising ground (`ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE`) | 0.05 | ROFA back-slope by ADG (Table 3-7 S-5/D-1; reg-families §A2) | ±5% beyond graded (§3.4.16 / §3.11.6) | SPLIT once §A2 lands; until then IDENT |
| 10 | RESA / end-skirt longitudinal (`RUNWAY_END_SKIRT_*`) | FAA §3.16.5 items 2–5 (0…−3% first 61 m; −5% beyond; ±2%/30.5 m) | as live (§3.16.5) | down ≤5%, changes "as gradual as practicable" — no 61 m zone, no numeric rate (§3.5.10) | SPLIT (ICAO drops the near-zone + rate; rate PROVISIONALLY retained as the ICAO arc operationalization — reg-families §A3(b) flag) |
| 11 | RESA transverse | (unbound; reg-families §A1) | S-3 first 61 m; ±5% beyond (Fig 3-35) | ±5% (§3.5.11) | SPLIT (born split in §A1) |
| 12 | Skirt lengths (`RUNWAY_END_SKIRT_VISUAL_MAX_LENGTH_M` 90 / `…PRECISION_*` 240/305) | FAA-derived | RSA length beyond end 1,000 ft / prior 600 ft (App G, C/D/E-V verified) | RESA: 90 m min, 240 m recommended beyond strip end (§3.5.2-.3 frame) | IDENT in shape; value audit at implementation (both authorities' lengths verified against the live constants, drift reported not silently fixed) |
| 13 | Taxiway longitudinal (`TAXI_MAX_GRADE`/`…_NARROW`) | C–F .015 / A–B .030 (ICAO by letter) | 1.5% flat; 2% only for exclusively-≤30,000 lb pavement — NOT taken (fleet unknown) → .015 all letters (§4.14.1) | C–F .015 / A–B .030 (§3.9.8) | SPLIT at A/B (FAA .015 vs ICAO .030) |
| 14 | Taxiway transverse (`taxi_transverse_cap_for_letter`) | C–F .015 / A–B .020 (ICAO) | 1.0–1.5% max .015 (§4.14.2 item 1a) | C–F .015 / A–B .020 (§3.9.11) | SPLIT at A/B (max .015 vs .020) |
| 15 | Stand max (`STAND_MAX_GRADE`) | 0.01 | ≤1% parking positions (§5.9.2 rec.) | ≤1% (§3.13.6) | IDENT |
| 16 | Apron gradient family | max 1% (owner-ruled, per-user 2026-05-07) | min 0.5% + max grade change 2% (§5.9.1; reg-families §B3) | qualitative (§3.13.5) | max: INV (owner); min: NA-I (born split in §B3) |
| 17 | Taxiway-strip graded width/slopes (`TAXIWAY_STRIP_*`) | ICAO/EASA by letter (D.325(b) widths; §3.11.5 slopes) | TSA transverse 1.5–5% (§4.14.2 item 5); TSA width table App G | as live | SPLIT (FAA column named at implementation from App G) |
| 18 | Shoulder transverse | (unbound; reg-families §B1) | 1.5–5% + 38±13 mm drop-off (Table 3-6 S-2, §4.14.2) | runway shoulder flush ≤2.5% (§3.2.3) | SPLIT (born split in §B1) |
| 19 | RAOA | (unbound; reg-families §A4) | none (verified silent) | 300 m × ±60 m, ≤2%/30 m (§3.8) | NA-F (born split in §A4) |
| 20 | Wingspan/tail tables (`WINGSPAN_BY_CODE_LETTER`, `TAIL_HEIGHT_…`) | shared | Table 1-1 | Table 1-1-aligned | IDENT |

Families 5, 9, 11, 16(min), 18, 19 are born split by the reg-families
rounds; phase B provides the registry they key into. The remaining
SPLIT rows migrate in phase B itself.

## §5 Migration: byte-identity where blended == resolved, honest deltas elsewhere

Mechanics: gate `O4_RULESET_SPLIT`, default "0". OFF ⇒ every accessor
returns the blended value ⇒ byte-identical to the tip table (2x, all
five + HEAZ). ON ⇒ per-airport resolved values.

Predicted deltas, per airport (pre-registered; each quoted both frames
at the arms; airports change ONLY via the named rows):

* **KCLT (faa)** — row 1: IDENT (AAC D ⇒ .015 = blend). Row 2: IDENT
  for its ≤10,000 ft runways (quarter ≤ 762 m ⇒ lesser() = quarter =
  live behavior). Row 5: IDENT (code 4). Rows 13/14: TIGHTEN at
  A/B-letter taxiways (3.0%→1.5% longitudinal, 2.0%→1.5% transverse)
  — census may RISE where narrow GA pavement was lawful at 3%; honest
  count, quoted. Row 6: strip half-width 75→76.2 m (the strip
  footprint widens ~1.2 m; strip-family populations shift slightly).
  Everything else byte-identity-candidate: the acceptance target is
  "KCLT deltas attributable ONLY to rows 13/14/6", verified by
  interventional single-row arms if the composed delta surprises
  (mechanism-before-fix).
* **HECA, SPJC (icao, code 4)** — row 1: 1.5%→1.25% runway
  longitudinal cap — runway profiles RE-SOLVE. CIFP thresholds are
  immovable (runway-flex law); profiles flex within the tighter cap;
  where terrain forced full-1.5% segments, expect band/earthwork
  growth and census movement (HECA 05R/23L's +9.18 m case reads
  differently at 1.25%). This is the largest predicted surface change
  in phase B — quoted per runway (the flex ledger is the instrument).
  Row 4: K 305→300 m/1% (sub-2% arc tightening, likely sub-materiality
  — reported either way). Row 10: skirt near-zone (0…−3% first 61 m)
  and the ±2%/30.5 m rate relax to ICAO's ≤5%-down + provisional rate
  — skirt profiles may shallow; skirt census quoted.
* **CYXY (icao — Canada is ICAO under the owner's "within the USA")**
  — same rows as HECA/SPJC where its runway is code 4 (length ≥
  1,800 m ⇒ check at dispatch via `runway_code_number`); else code 3:
  row 1 IDENT (.015), row 5 loosens .015→.0175 (strip longitudinal)
  — census may DROP; honest either way.
* **SPLP, HEAZ (icao)** — row-by-row deltas expected sub-materiality
  (short runways, small strips); first measurement quoted, no target.
* Row 7/8 (zone transverse mandate): NO CHANGE in phase B — the
  owner question (§10) gates it; both rulesets keep the blended
  mandatory-down until the owner answers. Stated in the constants
  comment so the deferral is visible law, not drift.

STOP rules: any airport changing through a row NOT named for it is an
identity-mismatch STOP (clean-control first, name the drifted input);
row-1 re-solve failures (infeasible under 1.25%) are LOUD stops
reported with the flex ledger, never quarantined (feasibility is
guaranteed; quarantine is unauthorized).

## §6 KCLT judged under FAA end-to-end — the acceptance fixture

KCLT is the FAA fixture (campaign ruling). Acceptance run: full KCLT
build, gate ON, resolver (not env-forced) selecting "faa"; sidecar
carries "faa"; `O4_TEST_AIRPORTS=KCLT test_pavement_grade` (law-true
frame) judges under the FAA column end-to-end; both census frames
quoted. The pre-registered claim: zero adjudicated violations
introduced by the split at KCLT, with the rows-13/14/6 population
changes adjudicated under the FAA text they now cite (a row lawful at
ICAO 3% and unlawful at FAA 1.5% is a REAL violation to fix or an
honest known-remaining item — never softened; law compliance is the
gate, not instrument-zero).

## §7 What is NOT split (named, so nothing is silently absorbed)

* Owner constants, region-invariant by ruling: apron max 1% (per-user
  2026-05-07), lot 5% + service road 8% (2026-08-03, aviation
  authorities verified silent), tunnel 4%, terminal-pad flatness.
* Engineering-judgment constants with no external citation: daylight
  slope limit 2.0, canonical-registry tolerances, materiality floors.
* EAT departure-surface selection (`EAT_FAA_ICAO_PREFIXES` {K,C,P,M} +
  `eat_surface_slope_and_setback`): a DIFFERENT owner ruling ("FAA for
  North America"); untouched; flagged for optional harmonization only.
* OLS constants (`ols_*`): the OLS family's own authority split is a
  recorded follow-on (its spec predates the rulesets ruling); phase B
  does not rekey it — recorded in the gap tail, not silently blended.
* The wingspan/tail tables (IDENT — one copy, shared).

## §8 The flip/tip interaction — phase B is an anchor-minting event

Gate-ON changes outputs at up to five airports (rows above), so
flipping `O4_RULESET_SPLIT` to default "1" REPLACES the campaign
anchors. Per RULINGS 154ad32: the defaults-changing lane lands LAST in
its batch and its minting IS the tip battery — phase B's flip
therefore sequences WITH THE LEAD as (or inside) the anchor-minting
lane of its train; the split machinery + gate can land earlier in the
train gate-off with byte-identity. Never mint anchors twice; the
reg-families rounds then build on the POST-SPLIT anchors.

## §9 Verification (streamlined protocol)

Offline replay + unit twins first (§3's three twin families + per-row
accessor twins, parameterized over §4). Gate-off byte identity 2x on
all five + HEAZ vs the tip table (re-pinned at dispatch). Gate-on
arms: **KCLT** (the fixture, §6 — the split's whole purpose) and
**HECA** (largest predicted delta: row 1 re-solve + row 10). Env-forced
cross-arms (`O4_RULESET=faa` on an ICAO airport, and vice versa, one
cheap airport each) prove the knob and the resolver are one mechanism
(the flip-equals-knob identity the ref-pull lane established).
Remaining airports' claims are pre-registered here and VERIFIED AT THE
TIP (one battery per batch). Suite: same-selection matched control;
the same 23-red reconciliation discipline. Worktree + symlinks;
foreground; no timing claims (suspended; ledger tripwire). Honest
build budget: 2 gated stress builds + 2 cross-arms + 2x6 identity
builds ≈ 35–45 min build wall; the tip battery is the batch's, not
this lane's.

## §10 Owner questions this spec cannot resolve (formulated precisely)

1. **Zone-2 mandatory-down vs jurisdictional fidelity** (rows 7/8):
   your 2026-07-08 ruling ("enforce fully — where FAA mandates DOWN
   and ICAO merely permits UP, FAA wins") was explicitly premised on
   "one blended global ruleset". Under the 2026-08-02 fidelity ruling,
   should ICAO-ruleset airports revert to ICAO's cap-only strip
   transverse law (flat surrounds lawful again, max 2.5%/3%), or does
   the mandatory-down stand globally as YOUR law independent of
   authority? Phase B keeps the blend until you answer.
2. **ICAO arc rate** (row 10 / reg-families §A3(b)): ICAO gives no
   number for strip/RESA slope-change rate ("as gradual as
   practicable"). Approve the provisional operationalization at the
   FAA rate (±2% per 30.5 m), or set your own value.
3. **Groundside drainage minimum constant** (reg-families §B3):
   approve 1.0% provisional (civil range 0.6–2%) after the primary
   civil-text pull, per the lot/service pattern.
4. **Terrace panels vs the FAA 0.5% apron minimum** (reg-families
   §B3): are your "level panels" (2026-08-04 apron terrace law)
   exempt from the drainage minimum, or should panels carry
   [0.5%, 1%] fall? §B3 exempts them until you answer.
5. **Runway/taxiway crown minimum** (reg-families §B2 recorded item):
   FAA Table 3-6 S-1 and ICAO §3.1.19 both put a ≥1% transverse
   MINIMUM on runways (FAA also 1% on taxiways) — binding it models a
   real crown on every runway (visible cross-section change,
   ~22 cm rise on a 45 m runway at 1%). Bind, or record as
   sim-inapplicable?
