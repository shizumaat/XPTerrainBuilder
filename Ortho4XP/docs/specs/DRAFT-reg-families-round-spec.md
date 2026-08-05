# DRAFT — Remaining reg families: two law rounds (strip frame / pavement surface)

Fable design DRAFT for lead review, 2026-08-04. BINDING: docs/RULINGS.md
(grade-law completeness: every reg generation-binding + validator twin;
law compliance, not instrument-zero; streamlined lane verification;
timing suspended — ledger tripwire only; region rulesets ruling).

SOURCES. The standards-gap review file (G-1..G-14) is NOT persisted —
only the primary texts survive in scratchpad `standards_gap/` and
siblings. Every regulatory number in this spec is therefore verified
against the PRIMARY text directly: FAA AC 150/5300-13B chg1
(`standards_gap/ac13b.txt`), ICAO Annex 14 Vol I incl. Amdt 18
(`annex14_bazl.txt`, `icao_sl_amd18.txt`), EASA CS-ADR-DSN Issue 7
(`cs_adr_dsn_i7.txt`). Where the review's remembered number (via
RULINGS/HANDOVER echoes) and the primary text agree, no flag; no
conflict was found. One acronym required primary resolution: **RAOA =
Radio Altimeter Operating Area** (Annex 14 §3.8; CS ADR-DSN.B.205).

SEQUENCING. Per the HANDOVER queue ("rulesets A/B with KCLT →
missing-reg law rounds"), **phase B of the rulesets lands FIRST**
(DRAFT-rulesets-phase-b-spec.md): every constant below is BORN
ruleset-keyed (FAA/ICAO columns named). FALLBACK if the lead flips the
order: land blended values with per-authority constants NAMED (the RSA
round's exact pattern, rsa-law-round-spec.md), and phase B migrates.

RULING: TWO ROUNDS, NOT ONE. Seven families exceed a single lane (the
RSA precedent: TWO families ≈ one full lane, 6 files, 16 tests). The
split is by machinery neighborhood so each round stays in one blast
radius: **Round A** = the strip frame (adjacent_ground march /
grade_law strip family / verification MIRROR family / check_grade strip
readers — all extend the `_strip_law_params` resolver RSA built);
**Round B** = the pavement surface (solver constraint rows, shoulder
emission, transect readers). Each round is single-lane sized; A before
B (B's transect binding reads geometry A does not touch).

Identity anchors: cited SYMBOLICALLY as "the tip table"
(refpull_interim/RESULTS.md §CAMPAIGN ANCHORS, 2x byte-identical,
SPJC 7cc21d87… / SPLP 0d967737… / CYXY d89b73a8… / HECA 122708ac… /
KCLT 4c331a46… / HEAZ 9679dd1e…). RE-PIN AT DISPATCH — lanes are
landing hourly and the anchors will have moved; the dispatch brief
quotes the then-current minted set, never these literals.

Convergence guards (CLAUDE.md §3) apply to every brief cut from this
spec: materiality floor 0.01 m / 0.01 pp, attempt cap 2, progress
heartbeat.

---

## ROUND A — strip-frame families (one lane)

All four families bind through the ONE resolver the RSA round built
(`adjacent_ground._strip_law_params`) and its consumers (the march
split build, the emit value pass, verification MIRROR 7, the
check_grade strip readers). FENCE: every edit stays inside call sites
the RSA round already touched, plus the new law functions in
grade_law.py. `_build_fill_bands`/`_build_cut_bands` internals stay
unchanged (the null-the-reference idiom). The open/closed runway-ring
asymmetry is its OWN queued round (RSA lead amendment 4) — do not fold
it here; strip numbers are re-read there.

### §A1 RESA / end-corridor transverse law — gate `O4_RESA_TRANSVERSE_LAW`, default "0"

The LATERAL strip transverse law already exists (zone 1 lip 3–5% down,
zone 2 band — config.py ADJACENT_GROUND_LIP_* / RUNWAY_STRIP_BAND_*).
The GAP is the END corridor (RESA rectangle): today it carries only the
LONGITUDINAL skirt law (grade_law.RUNWAY_END_SKIRT_*); across-corridor
grades are unbound and unread.

Constants (per-authority, primary-verified):
* ICAO: `RESA_TRANSVERSE_MAX_SLOPE_ICAO = 0.05` up or down — Annex 14
  §3.5.11 ("should not exceed an upward or downward slope of 5 per
  cent; transitions … as gradual as practicable").
* FAA: for the first 200 ft (61 m) beyond the end, Table 3-6 S-3
  applies (§3.16.5 item 6): `RSA_END_TRANSVERSE_RANGE_FAA_BY_AAC` =
  A/B (0.015, 0.05), C/D/E (0.015, 0.03). Beyond 61 m FAA states no
  transverse number (Fig 3-35 shows ±5.0% max transverse across the
  RSA width) — bind ±5% beyond 61 m, cited to Fig 3-35.

Generation binding: `_strip_law_params` gains an end-corridor
transverse envelope; each end-corridor march station's across-corridor
profile is bounded by it (same fill/cut band mechanics as the lateral
zones). Validator twin: extend the strip family's resulting-surface
reader (verification `_strip_longitudinal_scan` pattern) with an
across-corridor scan at the same 30 m grid; check_grade gains
`_check_resa_transverse_grade` rows. New-visible rows: the count RISES
(no reader exists today) — quote honestly per the owner's honest-count
law.

Stress airport: **KCLT** — six precision code-4 ends, the largest
end-corridor population on the battery (RSA spec's own census
justification), and the FAA fixture so both authority columns are
exercised (KCLT FAA, HEAZ/HECA ICAO in the same round's arms).

Pre-registered: KCLT/HEAZ end-corridor transverse rows quoted
before/after (before = first measurement, expect >0); after gate-on,
rows above the per-authority cap → 0 actionable (residue attributed,
class named); lateral-strip numbers unchanged (this is an END-only
family); runway vertices byte-identical.

### §A2 ROFA back-slope law — gate `O4_ROFA_BACKSLOPE_LAW`, default "0"

FAA-ruleset family. RULINGS: the ROFA exemption is APPROVED — Table 3-7
S-4 (side slope ≤0%) does NOT bind; the back-slope limits DO.

Constants (FAA AC 150/5300-13B Table 3-7, primary-verified):
* `ROFA_BACK_SLOPE_RATIO_BY_ADG = {I: 8, II: 8, III: 10, IV: 10,
  V: 16, VI: 16}` (S-5; run:rise — 8:1 = 12.5%, 10:1 = 10%,
  16:1 = 6.25% max rise).
* `ROFA_BACK_SLOPE_RUN_M_BY_ADG = {I: 7.6, II: 12.2, III: 18.0,
  IV: 26.2, V: 32.6, VI: 39.9}` (D-1, ft→m per the table).
* ROFA half-width from AC Appendix G (verified C/D/E-V: 800 ft width
  → 121.9 m half; implementer primary-pulls the remaining G-1..G-12
  widths from `standards_gap/ac13b.txt` — they are all in the retained
  text). ADG keyed via the existing letter proxy
  (`config.runway_code_letter`, A↔I … F↔VI per config's Table 1-1
  note).
* ICAO column: no ROFA exists; the analog (strip beyond-graded ±5%,
  §3.4.16) is ALREADY zone 3 law. ICAO-side constant = None (family
  not applicable — jurisdictional fidelity).

Generation binding: zone 3's rising-ground cap
(`ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE`) becomes, under the FAA
ruleset within the ROFA band, the by-ADG ratio applied over the D-1 run
beyond the ROFA edge; consumed by `grade_law.adjacent_ground_envelope`
(one law, emitter + validator both read it). Validator twin: the
existing adjacent-ground reader gains the by-ADG cap rows in the FAA
frame. Connection recorded: the `skirt.strip.micro` census class
(CYXY 3 / HEAZ 1 rows, 9.2–10.7% measured vs the 5% skirt cap) was
adjudicated "the CAP VALUE needs the ruleset" — those rows are
longitudinal-skirt territory and stay §A1/skirt-owned; this family owns
the RISING side only.

Stress airport: **KCLT** (the only FAA-ruleset battery airport — the
family binds nowhere else; ADG V ⇒ 16:1 over 32.6 m). CYXY as the
cheap gate-off sentinel.

Pre-registered: KCLT rising-terrain-beyond-ROFA rows quoted (first
measurement); gate-on → 0 above 16:1 within the D-1 run; zero effect at
every ICAO airport (byte-identical under gate-on there — the family is
ruleset-scoped); no wall inside any strip (still 0, wall law untouched).

### §A3 Strip profile curvature + longitudinal generation completion — gate `O4_STRIP_PROFILE_ARC`, default "0"

Two halves, one family (the strip's own longitudinal law, axis
completed then smoothed):

(a) THE 146-ROW BINDING (HEAZ population, rsa_law/RESULTS.md §2
COMPLETENESS). The RSA round landed the resulting-surface reader
(`verification.check_strip_longitudinal` + `_strip_longitudinal_scan`):
HEAZ gate-on read **146 rows, worst 7.59% vs the 1.50% cap, 88 rows
raw-DEM at BOTH ends** — ground the breach-trigger corridor
deliberately left un-emitted because it conforms LATERALLY while
breaching LONGITUDINALLY. ATTRIBUTION IS ALREADY MEASURED (this is the
mechanism, not an inference), but it was taken at 5eaf1e2:
ATTRIBUTE-BEFORE-BINDING step = re-run the reader on the tip tree at
dispatch (one HEAZ gated build) and confirm the 88 dem-dem rows stand;
also take the HECA/KCLT first measurements the lane never ran. THE FIX:
the march's band trigger gains the longitudinal axis — a station whose
resulting surface breaches the by-code longitudinal cap
(`RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE`, landed) triggers
emission exactly as a lateral breach does, and the §2 clamp then grades
what it emits. This answers the RSA lane's open question WITHOUT a
fill mandate: the breach-trigger design is kept; the trigger just
stops being blind on one axis. (The full fill-mandate reading — grade
all strip ground regardless of breach — is NOT taken; it remains an
owner question only if the lead wants it, see report.)

(b) THE ARC (the §3.4.14 item RSA recorded-unbound; config.py records
it verbatim at the constant block). Constants:
* FAA between the ends: §3.16.5 item 1 — vertical curves and distance
  between grade changes "same as the comparable standards for the
  runway": reuse the runway VC machinery (K = 1,000 ft (305 m) per 1%
  for C/D/E, §3.16.1; 300 ft (91 m) per 1% for A/B; no curve needed
  below 0.4% change). Beyond the ends: ±2.0% per 100 ft (30.5 m)
  (§3.16.5 item 5) — already `RUNWAY_END_SKIRT_MAX_GRADE_CHANGE_PER_M`;
  the constant is REUSED, not duplicated.
* ICAO: §3.4.14 is QUALITATIVE ("as gradual as practicable and abrupt
  changes or sudden reversals avoided" — no number). Operationalize
  PROVISIONALLY at the FAA beyond-ends rate (0.02/30.5 per m) for the
  ICAO ruleset, constant named `STRIP_ARC_RATE_ICAO_PROVISIONAL`,
  flagged in the constants comment AND the report for owner approval
  (the primary gives no number; the owner may set one).

Generation binding: `grade_law.runway_strip_longitudinal_clamp` gains
the rate-of-change term (the existing runway-profile arc utilities are
the machinery — import, never copy); the march clamp consumes it.
Validator twin: the resulting-surface reader gains a rate-of-change
column at its existing 30 m stations (sensitivity note: at 30 m
stations with 0.1 m emit quantum the rate instrument's blind spot is
~0.33 pp — document it exactly as the RSA lane documented the slope
reader's).

Stress airport: **HEAZ** — the measured 146-row population lives there,
it is the cheapest gated fixture (~40 s class), and it is ICAO-ruleset
(the provisional arc constant gets exercised).

Pre-registered: HEAZ strip-longitudinal rows 146 → 0 actionable above
the instrument blind spot (rows within sensitivity are
PASS-with-residual per the materiality law); worst grade 7.59% → ≤ cap
+ blind spot; strip coverage RISES at HEAZ (58.1% → up; emission grows
where the new trigger fires — quote the honest area delta); HECA/KCLT
first measurements quoted with no pre-registered target (first reads);
runway vertices byte-identical; §A1/§A2 numbers unchanged by (a)/(b)
alone.

### §A4 RAOA — Radio Altimeter Operating Area — gate `O4_RAOA_LAW`, default "0"

ICAO/EASA-ruleset family; FAA has NO equivalent (verified: zero hits
for "radio altimeter" in AC 150/5300-13B) — FAA-side constant None,
KCLT unaffected (jurisdictional fidelity).

Constants (Annex 14 §3.8, primary-verified; CS ADR-DSN.B.205
corroborates verbatim):
* `RAOA_LENGTH_M = 300.0` before the threshold (§3.8.2, "at least").
* `RAOA_HALF_WIDTH_M = 60.0` each side of extended centerline
  (§3.8.3; the 30 m aeronautical-study reduction is NOT taken).
* `RAOA_MAX_GRADE_CHANGE_PER_30M = 0.02` (§3.8.4: slope changes
  avoided/minimized; where unavoidable, rate between consecutive
  slopes ≤ 2% per 30 m).
* Applicability: precision approach runways (§3.8.1; CS B.205 says
  Cat II/III mandatory-ish, Cat I where practicable — bind for ALL
  precision approaches, the stricter contained reading, noted in the
  constant comment). The repo already carries per-end approach class
  for OLS (`_ols_is_instrument` / approach_class) — reuse that
  classification, never a second one.

Generation binding: a pre-threshold rectangle footprint (the end
corridor machinery generalizes: same axis/station frame, length 300 m,
half-width 60 m); within it the RESULTING surface's rate of change is
clamped at the constant — this is exactly the §A3(b) arc machinery
applied on a second footprint, which is why the family is in Round A.
Validator twin: the §A3(b) rate reader run over the RAOA rectangle
(reader reads emitted-or-DEM resulting surface, the RSA lane's
provenance-carrying pattern).

Stress airport: **HECA** — non-USA (family applies), precision
approaches, and the steepest pre-threshold terrain on the battery
(~85 m relief is REAL, per RULINGS; the 05L descent drag class lives
exactly in pre-threshold ground). SPJC pre-registered at the tip, not
built in-lane (streamlined protocol).

Pre-registered: HECA RAOA-rectangle rate rows quoted before (first
measurement, expect >0 on raw-DEM stretches) → 0 actionable after;
KCLT byte-identical with the gate ON (FAA ruleset ⇒ no-op); no strip
or skirt regression (the RAOA clamp composes with, never overrides,
the end-corridor floors — on conflict the STRICTER bound governs and
the composition is a named test twin).

### Round A acceptance

Gate-off byte identity 2x vs the tip table (re-pinned at dispatch) on
all five + HEAZ; gates-on arms per stress airport above (KCLT §A1/§A2,
HEAZ §A3, HECA §A4 — three gated builds + the HEAZ attribution build);
both census frames quoted per arm, never merged; suite = same-selection
matched control (the RSA lane's 11-module pattern) + the new twins
(target: one twin per binding constraint + one per reader, source-
inspection twins for gate defaults per the ref-pull precedent); work in
a WORKTREE with the documented symlink pattern (venv + OSM_data —
auto-patch cwd trap); foreground builds; no timing claims (suspended;
ledger tripwire only). Honest build budget: ~4 gated builds + 2x6
identity builds ≈ 25–35 min build wall total, no exclusive timing runs.

---

## ROUND B — pavement-surface families (one lane, after A)

### §B1 Shoulder transverse (crown) law — gate `O4_SHOULDER_TRANSVERSE_LAW`, default "0"

Shoulders today are absorbed into the pavement outline (the
"shoulder-absorbed union", HANDOVER; SPJC 16R/34L 45 m → 81 m declared
apt.dat shoulders) and carry NO transverse law of their own.

Constants (per-authority, primary-verified):
* FAA paved shoulders: 1.5–5.0% down (Table 3-6 S-2, all AAC; §4.14.2
  item 3 verbatim for taxiway shoulders). Unpaved adjacent surface:
  5 ±0.5% down for the first 10 ft (3 m) (§4.14.2 item 4) — already
  zone-1 lip law, REUSED not duplicated. Edge drop-off between paved
  and unpaved: 1.5 in ±0.5 in (38 ±13 mm) (§4.14.2 item 2; §5.9.1
  repeats it for aprons) — a MANDATED small step.
* ICAO runway shoulders: flush at the runway edge, transverse ≤2.5%
  (§3.2.3). Taxiway shoulders: ICAO gives NO numeric transverse for
  the paved shoulder itself (§3.10 is width/strength only); the ground
  beyond is taxiway-strip law (§3.11.5, already zone 2). ICAO-side
  paved-shoulder constant: max 0.025 (runway), taxiway = flush +
  within the strip band (cite §3.11.5's flush clause).
* Apron shoulders: ALREADY LANDED (APRON_SHOULDER_* 3 m at 1–3%,
  matches FAA §5.9.2) — untouched.

Generation binding: shoulder sub-band transverse envelope in the emit
value pass (the shoulder width is known per runway/taxiway from
apt.dat/geometry; within it the cross-section takes the per-authority
band; beyond it zone law continues). Validator twin: the §B2 transect
reader flags shoulder-band stations against the shoulder band, not the
pavement cap (provenance column says which band judged the station).
The FAA edge drop-off is a LAWFUL step: the step checks
(`_check_vertex_to_edge_step` / `_check_edge_midpoint_step`) and the
seam law gain the exemption UNDER THE FAA RULESET ONLY, width-limited
to 51 mm, at paved/unpaved boundaries only — FENCE: the exemption
predicate lives in the shared strip_seam_law predicate home so seam v4
and the census read ONE text (see fences below).

Stress airport: **SPJC** — the only battery airport with large declared
apt.dat shoulders (45→81 m, the arc-A4 case), ICAO ruleset; KCLT
carries the FAA column at the tip (pre-registered, not built in-lane).

Pre-registered: SPJC shoulder-band stations quoted before (first
measurement) → 0 actionable above 2.5%; the shoulder-absorbed outline
unchanged (geometry untouched — this is a VALUE law); no new steps
minted at ICAO airports (flush law); KCLT tip claim: drop-off
exemption changes 0 rows today (no emitted 38 mm steps exist yet —
the exemption is prospective law, state it).

### §B2 Transverse solver-binding completion — gate `O4_TRANSVERSE_BIND`, default "0"

The caps EXIST and are read by the validator (field-report §C3's
`check_transverse_grade`, always-on, 10 m stations over sidecar axes;
`taxi_transverse_cap_for_letter` C–F 1.5% / A–B 2.0%, Annex 14
§3.9.11; FAA §4.14.2 item 1: 1.0–1.5%). The drain adjudication names
the gap exactly: "transverse cross-slope in the solve (law exists,
generation not bound)". Vertex-pair allowances price the cT term
(`grade_law.Allowance`, `ds_decompose`) but the interpolated SURFACE
between constrained pairs is what the transect reader measures — the
two frames disagree and only the reader sees the surface.

Generation binding: transect-station constraint rows in the solve —
built over the SAME stations, axes, and caps the validator reader
uses (lockstep BY CONSTRUCTION: one station generator, imported by
both; the reader keeps its independent read of the emitted surface).
Sites: the within-shape constraint builder
(`solver_primitives`, the route-profile constraint graph) gains
perpendicular sample rows; implementer picks the composition that
reuses the existing station generator and says why (RSA §B-clause
pattern). Per-authority values: ICAO C–F 0.015 / A–B 0.020 (§3.9.11);
FAA 0.015 max (§4.14.2 item 1a; the ≤30,000 lb 2% relaxation NOT
taken — fleet unknown, stricter contained reading, noted).

RECORDED, NOT BOUND (this round): the MINIMUM transverse mandate —
FAA runway S-1 min 1.0% (Table 3-6) / ICAO §3.1.19 "nor be less than
1 per cent", FAA taxi min 1.0% (§4.14.2 item 1a) — is a CROWN MANDATE:
it forces every runway/taxiway cross-section to carry a real crown,
a visible geometry change to every airport. That is an owner-intent
question (see report), recorded here with citations exactly as the RSA
round recorded §3.4.14.

Stress airport: **HECA** — the transverse census population is
HECA-dominated (drain worklist: 605 of 707 battery transverse rows;
transect census 2,973 ≥1.5% stations at HECA per field-report §C).

Pre-registered: HECA transverse rows (tip frame, law-true) drop to 0
actionable above cap + instrument floor; the transect ≥1.5% station
count collapses to genuinely-transverse-lawful residue (attributed,
p50/p90 quoted); apron/stand within-shape counts move only where
transverse rows overlapped them (no new within-shape class); KCLT/CYXY
tip claims pre-registered (KCLT 327 transverse rows → down;
airport-dependent sign caveat per the RSA lane's measured lesson —
these rows track which corridor lays the shoulder).

### §B3 Drainage minimum — gate `O4_DRAINAGE_MIN_LAW`, default "0"

The queue's "groundside drainage minimum" (RULINGS 2026-08-03: no
groundside minimum exists; every civil source carries 0.6–2%). Scope:
apron + groundside MINIMUM slope only. NOT the drainage-spine law
(landed, field-report §B) and NOT the runway/taxi crown minimum
(recorded in §B2).

Constants:
* FAA aprons: `APRON_MIN_DRAINAGE_GRADE_FAA = 0.005` — §5.9.1
  Standards: "Provide a minimum 0.5 percent apron gradient". Also
  recorded from §5.9.1 (bound as law, cheap): apron max grade change
  2%. NFPA 415 fueling-pavement note: recorded only.
* ICAO aprons: §3.13.5 is qualitative ("sufficient to prevent
  accumulation … as level as drainage requirements permit") — NO
  numeric minimum; ICAO-side constant None (jurisdictional fidelity;
  a numeric ICAO minimum would be minted, not cited).
* Groundside (region-invariant, landside — aviation authorities
  verified silent, the lot/service precedent):
  `GROUNDSIDE_MIN_DRAINAGE_GRADE = 0.010` PROVISIONAL. I could not
  primary-verify the civil texts from the retained corpus (the
  constants-round research trail cites SUDAS §8B-1 et al.; the civil
  range is 0.6–2%). OWNER APPROVES THE CONSTANT before the gate flips
  (the exact pattern of lot 5% / service 8%); the lane lands the
  machinery with the provisional value.

Generation binding: a min-fall constraint per apron/lot surface toward
its drainage edge — the mandatory-DOWN corridor precedent (zone-1 lip)
is the structural model; the drainage-spine machinery (field-report §B)
already names each enclosed interior's low edges, and the apron
back-edge/shoulder constants name the free edges. Validator twin: a
min-gradient reader per surface (flags surfaces flatter than the
minimum over runs > the materiality floor). EXCLUSIONS (named, tested):
building-pad seats stay FLAT (TERMINAL_PADS_SLOPE=False is owner law);
stands keep max 1% — the FAA band on a stand is [0.5%, 1.0%];
apron TERRACE PANELS (owner 2026-08-04: level panels) — see the owner
question in the report: "level panel" vs 0.5% min needs one owner
sentence; until answered the min does NOT bind inside declared terrace
panels (exemption named in the law function, twin-tested).

Stress airport: **KCLT** — the only airport where the FAA apron
minimum binds (ICAO-side is None); groundside minimum exercised
everywhere but KCLT gives both columns in one build.

Pre-registered: KCLT flat-apron area (grade < 0.5% over > materiality
runs) quoted before (first measurement) → 0 actionable outside the
named exemptions; ICAO airports byte-identical under gate-on for the
apron half (None constant ⇒ no-op) and change only via the groundside
half (quoted separately); no stand exceeds 1.0% (the band's upper twin);
no terrace-panel joint crosses a route (existing twin stays green).

### Round B acceptance

Gate-off byte identity 2x vs the then-current tip table on all five +
HEAZ; gates-on arms: SPJC (§B1), HECA (§B2), KCLT (§B3) — three gated
builds; both frames quoted; same-selection suite control; twins per
constraint + reader + exemption; worktree + symlinks; foreground; no
timing claims. Honest build budget: ~3 gated builds + 2x6 identity
builds ≈ 30–40 min build wall total.

---

## Interaction fences (both rounds)

* **seam v4 lane** (O4_STRIP_HEAL_LAW, the adjacent_ground healer,
  strip_seam_law.py): Round A edits the same march/value pass. Rounds
  A/B land AFTER seam v4 merges and rebase onto it (the RSA lane's
  `git apply -3` + re-verify pattern). The healer consumes §A1/§A3
  caps through `_strip_law_params` — ONE resolver, never a second
  copy; §B1's drop-off exemption predicate lives in strip_seam_law's
  shared predicate home so healer and census read one text.
* **consensus lane** (to_osm averaging retirement): no to_osm edits in
  either round; §B2 binds at the SOLVE. The 0.16 m shared-weld class
  stays consensus-lane territory (refpull deviation 2's adjudication).
* **coupling lane** (anchors/seat coupler): §B3 excludes building-pad
  seats; the coupler's polytopes do not consume the min band this
  round; an empty coupling polytope during §B3 arms is a LOUD stop
  (split-level ruling), reported to the coupling lane, never patched
  here.
* **flip lane** (defaults / anchor minting): every gate here lands
  default "0". Default flips belong to the flip lane; the
  anchor-minting lane lands LAST and its minting IS the tip battery
  (RULINGS 154ad32) — no round here mints anchors.

## Recorded, NOT bound (the honest inventory tail)

With citations, so the gap census stays complete: ICAO effective-slope
≤1%/2% (§3.1.13); runway sight distance (§3.1.17) and taxiway sight
distance (§3.9.10); PVI spacing (ICAO §3.1.18 max(K·Σ|Δg|, 45 m),
K = 30 000/15 000/5 000; FAA §3.16.1 250 ft or 1 000 ft × Σ|Δg%|);
taxiway vertical curves (ICAO §3.9.9 1%/30 m C–F, 1%/25 m A–B; FAA
§4.14.1 item 3: change ≤3%, 100 ft (30.5 m) per 1%, none < 0.4%);
stopway arc relaxation (ICAO §3.7.2(b) 0.3%/30 m); runway/runway
intersection transverse machinery (FAA §3.16.4: 3-inch crown-edge
rule, 150 ft (46 m) transitions, 0.5% min for positive drainage);
runway transverse crown minimum (§B2's recorded item). Each is a named
follow-on candidate, none silently dropped.
