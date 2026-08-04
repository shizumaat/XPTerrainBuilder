# Taut-string line — session handover, 2026-08-01

## 0-CAMPAIGN STATE — 2026-08-04, POST KILL-HALF (supersedes everything
## below; RULINGS.md is owner-law canon; memory/campaign-goal.md is the goal)

**THE GOAL** (owner, unchanged): five-airport LAW COMPLIANCE
(SPJC/SPLP/CYXY/HECA/KCLT): zero ADJUDICATED violations (the law includes
its exemptions and floors — instruments report, the law adjudicates),
quarantine machinery GONE, every reg generation-binding with test twins.

**BOARD AS OF 2026-08-04 EVENING (HEAD `9d7eea0`).** Landed today:
seat-gates variant A (`58e2f99` — SEAT_BAND_CONSISTENT ON, coupler HELD,
new HECA anchor `a785f170`, others unchanged); the APRON TERRACE LAW
gated default "0" (`5eaf1e2`, adjudication `768cded` — gate-on at HECA:
apron.slope −52.9%, law-true within −25.5%, joint∩route ≡ 0 structural);
KCLT baseline nesting fix (`6a8f4bf`); licensing docs (`98e7805`); specs
approved: seam-continuity (`6a69d4f`), ref-pull interim (`57f033b`),
seed-fix + coupling reconciliation (`a5e96a9`), rsa amendments
(`9d7eea0`).  SPLIT-LEVEL SEATS: round HELD (verdict in its spec §ROUND
VERDICT, `4c6f449`; worktree seats-lane parked).  SEED ATTRIBUTION
VERDICT: owner's axiom confirmed — HEAZ infeasibility was 100% minted by
the per-edge quant margin compounding per path (raw law 0/2032); HECA
was ONE minted seat (band floor above own hard value + uncapped apron
polytope); every margined-envelope number battery-wide changes meaning
when seed-fix §1 lands.  IN FLIGHT: rsa-law (rebasing + ruling (b)
re-grade), ref-pull interim (worktree refpull-lane), seed-fix (worktree
seedfix-lane).  QUEUE: coupling round (after the oracle), consensus
retirement, adjacent_ground pre-flex band probe, open/closed ring
asymmetry fix, baseline re-record (machine reads 13-32% fast),
one-solve groundside, remaining reg families, SPLP tile-cut class,
test-maintenance (23 reds), scorer re-key, strings verdict LAST.

**THE KILL HALF** (`docs/specs/kill-half-spec.md`, owner-approved in
`b56b37a`).  Three things changed at once, and they are what a user now
gets:

1. **§1 THE DEFAULTS FLIP.** Eleven gates ship ON:
   `ROUTE_METRIC_ENVELOPE` (`019d0bb`), `RETIRE_TERRAIN_PIN_QUARANTINE`
   (`ceef13f`), `LATERAL_CONTIGUITY_LAW` + `NEEDLE_SOURCE_GUARD`
   (`1e5a781`), `SERVICE_LOT_ABSORPTION` + `TRIANGLE_PLANE_REPORTS` +
   `BAND_SEED_EXACT` (`495660a`/`5a94c57`), `SOURCE_COVERAGE_CHECK` +
   `RUNWAY_STRIP_WALL_LAW` + `DRAINAGE_SPINE_LAW` + `ROUTE_LEG_EXACT`
   (`0b9efaf`); `PROJECTION_STALL_REPORT` follows by implication.  Every
   gate keeps its env override, so `O4_<GATE>=0` restores the old path.
   **+1 SINCE THE SEAT-FLIP BATTERY (2026-08-04, lead ruling variant A):
   `SEAT_BAND_CONSISTENT` ships ON** — a full-frontage building seat
   clamps into the intersection of its selection interval and the NODE
   band at its own contact nodes (the band the projection enforces).
   Measured ALONE: HECA −303 law-true within (`building|building` 440→393
   AND the surrounding `apron` 6822→6665 / `junction` 1856→1781 follow it
   down), every other battery airport BYTE-IDENTICAL, no new over-cap
   class, no sweep cost (HECA 31 676, byte-equal to the pre-flip default),
   no build-time cost resolvable above the noise floor.
   EXCLUDED and still "0": `SCORER_SERVICE_ADJ` (re-key queued), the
   string gates (owner pause), `BREAK_BLEND_CONTINUOUS` (died with §2),
   and `SEAT_COUPLE_SHARED_SURFACE` — **HELD, and SEQUENCED not
   rejected**: measured ALONE it is HEAZ −1 / CYXY −4 / SPJC −7 but KCLT
   **+145** law-true within, migrating defects out of buildings
   (`building|building` 46→28) into AIRSIDE pavement (`apron` +75,
   `junction` +49) with a new `adj_edge::graded_strip` over-cap class at
   1.15 m — the airside-is-king failure mode.  Root cause is the
   CHORD-priced metric (at HECA it admits 152 coupled pairs with NO
   jointly-feasible seat set; 130 ship violating their own coupling
   limit), which is what `docs/specs/route-distance-seat-coupling-spec.md`
   (`a5e96a9`) exists to fix.  It re-arms after the seed-fix round lands
   the law-graph budget oracle and the coupling round re-prices
   admission/limits on it.  Separability is MEASURED, not assumed:
   `KCLT_sb1` / `SPJC_sb1` (this gate off, seat-band on) are byte-
   identical to their old defaults.

2. **§2 THE QUARANTINE MACHINERY IS DELETED** — not gated, deleted: the
   break blend and its continuity gate, the freeze (`broken` → immovable,
   and the `_final_projection_broken_keys` carry), all three
   `_break_node_ll` sinks (solve, projection, weld-relimit), the sidecar's
   `break_nodes` key, `check_grade`'s three splits (pairs, planes, steps)
   and `grade_graph_validate`'s break scoping.  Counts are FULL-CENSUS.
   The A2/A3/A4/B3 minters keep their REPORT halves only.

3. **§3 THE LOUD ERROR** (ungated, it IS the law):
   `building_feasibility.assert_no_final_band_inversion` fails the build
   when the FINAL reach band is inverted by > 0.01 m at any node, naming
   nodes, floor/ceiling and route distances.  MEASURED: fires ZERO times
   across SPLP/CYXY/HEAZ/SPJC/HECA (HEAZ carries 2 sub-materiality
   inversions ≤ 0.01 m, reported PASS-with-residual).

**NEW DEFAULT-ARM PATCH BASELINES** (body sha256, `tail -n +3`, built with
NO `O4_` var set).  The `8eab3acd`/`f460a8f7`/`b7d02779` gate-off anchors
below are RETIRED — gate-off is no longer what ships:

| airport | body sha256 (default arm) | vs the pre-kill CAND arm |
|---|---|---|
| SPLP | `1531e6d0`49bb1c6a7865fb9f6141a4cc565d18a58e942d2e47708b8b750f3853 | BYTE-IDENTICAL |
| CYXY | `5b7a1912`b5c1ce1641e66d4ebaf9d0271a4db24be1c2630ab41a00098fe259dc | BYTE-IDENTICAL |
| HEAZ | `5854d6e7`73126bd1c39954723e4cf305101a3e8d385647b75ecb88759b087859 | differs (see below) |
| SPJC | `b3875f84`b5bfbbefb1b99697703c84ee2e0427238ffd80ef1249180c49a76851 | no CAND dump exists |
| HECA | `2a28d01b`becaad3dc0c1686d1239e425904620b33499bf079ae8b3a9c37a808d | no CAND dump exists |

**SPJC ROW CORRECTED 2026-08-04** (seat-flip battery): the value recorded
here was 63 hex characters — a dropped character in `...84b5fbbefb1b...`.
The true 64-char digest, reproduced 3× that session (a gates-off arm, a
seat-band-only arm, and the dossier-round arm), is `...84b5bfbbefb1b...`
as now shown.  No surface changed; only the transcription was wrong.

**SEAT-FLIP BATTERY BASELINES (2026-08-04, lead ruling variant A —
`SEAT_BAND_CONSISTENT` ON, `SEAT_COUPLE_SHARED_SURFACE` held OFF).**
Default arm, no `O4_` var set, each reproduced 2× on this tree.  ONLY HECA
moves; the other five are byte-identical to the rows above, which is the
whole point of the variant-A ruling:

| airport | body sha256 (default arm) | vs the pre-seat-flip arm |
|---|---|---|
| SPLP | `1531e6d0`49bb1c6a7865fb9f6141a4cc565d18a58e942d2e47708b8b750f3853 | BYTE-IDENTICAL |
| CYXY | `5b7a1912`b5c1ce1641e66d4ebaf9d0271a4db24be1c2630ab41a00098fe259dc | BYTE-IDENTICAL |
| HEAZ | `5854d6e7`73126bd1c39954723e4cf305101a3e8d385647b75ecb88759b087859 | BYTE-IDENTICAL |
| SPJC | `b3875f84`b5bfbbefb1b99697703c84ee2e0427238ffd80ef1249180c49a76851 | BYTE-IDENTICAL (`sb1` arm) |
| KCLT | `74c4731f`2b8954b3d06a18c40c3539b694653e60728feed801b1245ea0d8477f | BYTE-IDENTICAL (`sb1` arm) |
| HECA | `a785f170`3d600fe2cd57da103978f95c96a8dd41da9da01b2f166c6e7578ac9d | **−303 law-true within** (9 952 → 9 649) |

The split-level-seats spec's band 1 needs NO re-base under variant A: the
126/105 frame remains the default frame.  The 152/130 empty-polytope frame
only exists with `SEAT_COUPLE_SHARED_SURFACE` ON, which does not ship.

HEAZ is the only airport whose band is inverted at all, so it is the only
one §2 can move: 796 of 6,204 shared vertices differ (p50 0.01 m, max
0.12 m — one to two emit quanta), 200 of 6,404 geometry vertices are
re-placed in junction and gap-interior rings, and NO runway vertex moves.
Every airport's `.axes.json` sidecar is exactly one key smaller
(`break_nodes` removed, `[]` at SPLP); no other sidecar key changed.

**SUITE**: 23 failed / 4,204 passed / 18 skipped / 13 xfailed — the reds
are EXACTLY the standing 23, name for name.  New xfail(strict) rows: the
2 CYXY drain-ledger tests (the exposed 1.9 % apron pair) and 5
exposed-consumer tests (below).

**BUILD TIME** (2 cold-equivalent runs each, foreground, exclusive,
default arm): SPLP 12.25 / CYXY 35.56 / HEAZ 54.73 / SPJC 174.99 / HECA
351.93 s, written to `tools/build_time_baselines.json`.  The owner's
approved ceilings (SPJC 153.2, HECA 315.4) are in
`tools/build_time_approvals.json`.  TODAY'S NUMBERS ARE ABOVE THOSE
CEILINGS AND THE ROUND IS NOT WHY: a same-session pre-kill control
(worktree at `4d20c7c`, CAND arm, warm caches) measured CYXY 35.8 /
SPJC 177.15 / HECA 336.5 s, i.e. the machine itself is 5-15 % slower than
during the overnight approval battery — visible on phases this round
cannot touch (HECA emit 79.7-80.1 s overnight vs 81.2-90.2 s in every arm
measured today).  Post-kill vs same-session pre-kill: CYXY −0.24 s, SPJC
−2.16 s, HECA +15.4 s, all inside the arms' own spread.

**THE SIM TILE**: `sim_review/zOrtho4XP_+30+031_DEFAULT/` (+
`DEFAULT_NOTE.md`), built with `O4_ vars in this process: []` — this is
what every user build now produces.  Textures symlink to the strings-on
pack as before.

**STOP-AND-REPORT items** (§2's exposed-consumer clause; nothing was
deleted on the implementer's authority, all are xfail(strict) with the
exposure named): `SVC_SPINE_EDGE_COUPLE` / `edge_couple_nodes`,
`O4_CHAIN_RIGID_BLEND` / `O4_BRANCH_RIGID_BLEND`, and fix-arm SITE 2 of
`O4_HARD_NEIGHBOUR_BOUND` — all three had their ONLY effect site inside
the deleted blend.

**QUEUE after review**: rulesets A/B with KCLT (the FAA fixture) →
missing-reg law rounds (strip precedence, abeam-longitudinal, RESA
transverse, ROFA back-slope per the approved exemption, shoulder crown,
runway-profile arc, RAOA, transverse solver-binding, groundside drainage
minimum) → KML-v3 class drain → strings verdict LAST.  Small items still
queued: spine-keyed scorer re-key, late-mint binding point, memo-key bug,
`service_junction` 8 % coupling (owner may split).

---

## 0-CAMPAIGN STATE — 2026-08-03 (SUPERSEDED by the 2026-08-04 block
## above; kept for the attribution chain)

**THE GOAL** (owner): iterate to five-airport LAW COMPLIANCE
(SPJC/SPLP/CYXY/HECA/KCLT — KCLT joins with the ruleset round as the FAA
fixture): zero ADJUDICATED violations (law includes its exemptions/
floors — instruments report, the law adjudicates), quarantine machinery
GONE, every reg generation-binding with test twins. Heartbeat cron
(session-local) re-anchors every 20 min.

**Committed through `495660a` + rulings `47455c1`** (read the commit
messages 0b9efaf..495660a for per-round numbers): the four field-report
fixes (strip walls / drainage law / lateral pricing+transect / coverage
guard + H1 source discriminator); the classification round
(lateral-contiguity law with the owner's ring-road tests, service-
adjacency scorer, drainage lockstep); quarantine rounds 1-2 (terrain-pin
export retired BOTH effects; sole-cause decomposition: ZERO of 287
genuine terrain-vs-law; HEAZ "inversions" = raster seed-cell bug, fixed
in kill-prep §3 to sub-materiality); kill-prep (absorption machinery
portion-only/spine-remains, triangle demotion, band seed fix).

**COMMITTED: the constants+absorption round** — owner
constants GROUNDSIDE 4→5% + SERVICE_ROAD 5→8% (cited in `config.py` and
`docs/STANDARDS.md` rows 25/27, ungated).  **NEW GATE-OFF BASELINES,
each reproduced 2×** — the old CYXY `dcebb6ff` / SPLP `c2316222` / HECA
`9a49cbce` anchors are RETIRED:

| airport | frame | baseline (body sha256, `tail -n +3`) |
|---|---|---|
| CYXY | bare | `8eab3acd`b470b7c285d61c609d9b3d7c4833974d607d71a765523c3008bac3f1 |
| SPLP | bare | `f460a8f7`178d7873c46051170c2488d2d96ae189d608d6e1a39ea3f5eac8955c |
| HECA | repaired | `b7d02779`be109710692558a4bcea0214861f236c1aebe2b9bc8ffd798295396b |

Both constants are GENERATION-binding (the new surface judged by the old
law is 2.2-2.5× worse); every runway vertex is byte-identical across the
change at CYXY/SPLP/HECA.  `service_junction` rides
`SERVICE_ROAD_MAX_GRADE` — flagged for the owner, not split.

Of the two kill-prep §1 STOP fixes: the merged-surface one-law regrade
LANDED (attempt 2 of 2, gated, big improvement but its pre-registration
missed — see the round report); the 21-runway-vertex airside violation
was **attributed and STOPPED, not fixed** — the suspected emit consensus
is FALSIFIED (staged snapshots: the runway field is identical up to
`AA_pre_solve` and diverges at `AB_post_solve_immediate`), the mover is
the SOLVE, because `service_road`/`service_junction` are
`PAVEMENT_ROLES` and `groundside_pavement` is not, so absorbing a road
into a lot changes solver MEMBERSHIP.

**QUEUE after it:** flip-and-kill (defaults flip + exclusive timing
battery + whole-pipeline review + machinery deletion + the loud
final-field error >0.01 m — measured to fire ZERO times today) →
rulesets A/B with KCLT → missing-reg law rounds (strip precedence,
abeam-longitudinal, RESA transverse, ROFA back-slope per approved
exemption, shoulder crown, runway-profile arc, RAOA, transverse
solver-binding, groundside drainage minimum) → KML-v3 class drain →
strings verdict LAST. Also queued small: spine-keyed scorer re-key,
late-mint binding point, memo-key bug, service_junction 8% coupling
(owner may split).

---

## 0-EVENING PIVOT — 2026-08-01 late (superseded by 0-CAMPAIGN STATE;
## kept for the attribution chain)

The owner flew both arms. VERDICTS: strings-on is "a massive mess"
(cliffs/canyons/tears); strings-off "still has many of the same type,
lower magnitude". STRING WORK IS PAUSED (his purpose statement: strings
are an anti-hills-and-valleys refinement for lawful taxiways, possibly
not aprons — memory `string-purpose-statement`). The QUARANTINE IS
UNAUTHORIZED (zero breaks in paved areas; ALL counts full-census —
memory `feasibility-is-guaranteed`, escalated). ATTRIBUTED CHAIN: the
visible mess = break regions (HECA α full census 19,591 rows/1,023
cliffs, 21.5k quarantined) × a DISCONTINUOUS blend weight
(value-Dijkstra dist by-product as geometric t — one_solve.py:1884; 80%
of ≥2 m close-pair steps carry |Δt|≥0.1) painting pockets manufactured
by FALSE TOPOLOGY: the final projection's envelope walks the pavement
PAIR graph (apron chords, zero-budget pad teleports, 45-hop/4.8 km
chains) instead of taxi routes, letting the two REAL 05L/23R↔05C/23C
tensions ceiling/floor 67%/53% of all break nodes at 3.3 km reach.
Owner directive: FIX THE ROUTE GRAPH ("via actual routes, not cutting
across the edge of aprons"). Counterfactual (megaanchor/): route metric
+ withdrawing non-route-role witnesses (47% of hard anchors —
graded_strip traces etc.) kills every ≥20 m deficit; residue ~17%/p50
5 m incl. the real 282 runway×runway class. IN FLIGHT: break-blend
continuity fix (spec `break-blend-continuity-spec.md`, implementing);
NEXT: `route-metric-envelope-spec.md` (written, implement AFTER blend
fix lands — same files); then residue attribution → quarantine retires
into loud errors → full-census validator → string refit LAST against
the repaired α surface. SPLP baseline is now `c2316222…` (corrected
CIFP; owner fixed a known-bad RW02 253 ft→158 ft). Probe purity fixed
(`b87a1dc`). Sim-review packs + KMLs in `sim_review/` (gitignored).

## 0. CURRENT STATE — 2026-08-01 EOD (this block supersedes §§3-8 below;
## §§1-2 — the delegation model and the owner's model — remain law)

**Branch `taut-string-chord-model`. Commits this session:** `50a12ea`
(probes: mover ledger + hook-time attribution), `b4ff1cd` (fix arm round 1),
`676f8da` (round 2). **Round 4 in flight** (spec
`taut-string-fix-arm-round4-spec.md`); round 3 was measurement-only.
Specs this session: `taut-string-probe-spec.md`,
`taut-string-fix-arm-spec.md`, `-round2-spec.md`, `-round4-spec.md`.

**Owner rulings added today:**
* Band-lawful displacement TRUMPS the DEM — metres moved is not a defect
  metric; conditions: endpoints in band, law-true spines, edge-follow
  (owner wants a simulator look before final say).
* There is ONE band (`reach_band_unified`); seats and string endpoints
  both consume it. Never describe its runway seeding as a second band.

**Old open defects, closed:** #1 G2 pin drag (final passes minted it;
fix-3 hold ⇒ HECA median 0.0020, 100% ≤1 cm; SPJC's residual tail was the
OFF-SPINE class below). #2 conflicts (mover ledger: 94% proj_u.blend,
zero sweeps; Ruling 55 bounding ⇒ 35 undeclared max 0.24 m; the 88
law_anchor class was STATIC — grip pin-vs-hard extension ⇒ 0). #4
hook-time band violations (no hard stamp guilty; plain P0 DEM seeds =
terrain above the runway-anchored ceiling). #5 flip gate READ:
854 → 837 (r1) → 747 (r2), decomposed 362 adjacent_ground-clamp (side
task, running separately) + 244 SPJC apron (⅔ = off-spine pin class,
round-4 fix) + 141 (37 release-induced junctions, 12 CYXY pin-vs-free,
92 post-solve-minted unattributed).

**Key mechanisms proven (do not re-derive):**
* Grip completeness: round 1 added pin-vs-hard pairs; round 2 made the
  grip's pair graph the LAW's graph (ring edges from the solve's own
  shape-constraints object streamed once + two-hop through-free family,
  tightest-budget min-merge). Chords never bent; ~29% of pins release.
* OFF-SPINE PINS (round 3, exact): S1b writes every pin but the phase-A
  freeze covers only `u_spine_adj` keys ⇒ off-graph pins get overwritten
  by phase B then held wrong. 32/32 movers off-spine vs 1,620/1,620
  on-spine at 0.000000 m. Fable ruling: a pin the solve cannot hold is
  not a pin (round-4 fix: applied vs `off_graph` ledger + `pin_frozen`).
* DECLARED WEB = LAWFUL BOOKKEEPING (round 3): 0/176 HECA declared
  both-pin nodes at any created defect, 100% law-true; escalation to a
  route-metric grip is RULED DOWN to a monitoring ledger (alarms:
  unquarantined residual >single digits, or defect-coincidence > random
  control). Rod chains are the cheapest subclass, not the priciest.
* Canonical identity join: the .osm 11-decimal spelling IS the canonical
  key (0 collisions); never proximity-join (11.6% wrong-object). ~63% of
  pin vertices are emit-decimated (survivorship bias in any per-pin
  emitted stat).

**Gates:** `O4_TAUT_STRING_CONSTRUCTION` still default "0";
`O4_STRING_MOVER_LEDGER`, `O4_HARD_NEIGHBOUR_BOUND`,
`O4_STRING_PINS_FINAL_HOLD` default "0". Gate-off byte identity: CYXY
`dcebb6ff…` unchanged; **SPLP BASELINE = `c2316222…` (2026-08-01, final).**
*(Both hashes RETIRED 2026-08-03 by the owner-constants round — current
baselines are in §0 above: CYXY `8eab3acd…`, SPLP `f460a8f7…`, HECA
repaired `b7d02779…`.  The story below is still the reason SPLP's
anchor is what it is.)* Full story, all
attributed: SPLP RW02's true elevation is **158 ft** (owner-confirmed;
DEM was right). The owner's mid-day CIFP update had introduced OLD
INCORRECT data (253 ft) — that WAS the "unattributed" hash flip
(`d8d0f065…` → `1d7f6fc7…`; Custom Data dir mtimes moved 12:21-12:22,
file mtimes preserved, which is why the bisect could not see it). Round
7's "old baseline buried the threshold" verdict INVERTS: the keep-CIFP
rule was faithfully applying garbage. Owner fixed the CIFP; the
corrected build hashes `c2316222…` (3× reproduced) with RW02 anchoring
low and only a ~2 m tiered-budget deficit (was 14.6 m under the bad
value). `1d7f6fc7…` is retired. The specced instrument stands and is
now proven necessary: env-gated threshold-reconciliation print +
composed-DEM (and CIFP) fingerprint in patch provenance — a data update
must announce itself, not surface as a hash flip. Probe purity: `O4_STRING_MOVER_LEDGER` proven
byte-inert at SPJC + HECA after round 7's read-only registry query +
published-attribute fence (before that fix, probe-on arms were NOT
production at SPJC). Flip
decisions after round 4; the `O4_HARD_NEIGHBOUR_BOUND` flip changes
α output (75/88 anchor conflicts pre-exist gate-off) and goes to the
owner with battery evidence.

**Next after round 4:** rule on the round-4 reads (off-graph tenure
scope, release-induced junctions, CYXY blind spot, post-solve emitter
probe) → gate flips → suite read → R1 re-read → R1 CP2 → R2 → battery →
owner's simulator look → tile/app. Session scratchpad artifact sets:
`ruling55/ flipgate/ fixarm/ round2/ round3/ round4/` (ephemeral — key
numbers are in the specs and commit messages).

---

(Below: the 2026-08-01 morning handover. §§1-2 remain law; §§3-8 are
superseded by §0.)

Supersedes the 2026-07-31 handover (that one describes the tube-and-funnel
constructor, which is **retired**). Written for a new session to finish the
work. **Do not re-derive §2 or §4** — they cost builds and rounds.

---

## 1. Delegation model (owner standing rules — do not violate)

* **Fable = design and review ONLY.** It writes ALL specs and rules EVERY
  mid-implementation deviation. It never implements.
* **Opus = implementation and investigation.** Every `Agent` launch passes an
  explicit `model`.
* Canonical text: `Ortho4XP/CLAUDE.md` §"Working style" item 1a.
* **Report IN-TURN.** Never end a turn holding a completed measurement, and
  never rely on a completion notification to wake the coordinator. That
  pattern cost **eight hours** on 2026-07-31: a finished build sat unread
  from 22:45 to 06:37. Poll builds inside your own turn.

## 2. The owner's model — all rulings, do not re-litigate

**What a string IS (2026-07-31, verbatim):**
> "The string is always a straight chord through space, only the end points
> sit in the middle of the band."

* A string is a **straight chord between two points**. Its two ENDPOINTS take
  **band centre**; between them the chord **may run above or below the band
  freely** — the solver pulls the taxiway to its cap where it does.
* **The string never bends.** It is an idealized elevation target, never
  emitted.
* **Strings are PREFERENCES. Grade law overrules them. A string must NEVER
  CAUSE a grade-law violation.** (Owner, verbatim: *"they should never CAUSE
  a grade law violation… the grade law overrules the string when needed."*)
* Corollary, Fable Ruling 52: **the chord is never bent by law — the GRIP
  is.** Where two pinned ends would force an over-cap pair, the *pin*
  releases; the chord is never modified or clipped.
* A string's whole elevation content is **two numbers**. The hook evaluates
  the chord per vertex by **linear interpolation on the chord station**.

**Owner constants — ONLY HE MOVES THESE:**

| constant | value | job |
|---|---|---|
| `TAUT_STRING_SPINE_TOLERANCE_M` | **8.0** | membership + string-vs-spine validation |
| `TAUT_STRING_MIN_STRING_M` | **100.0** | string duty (sub-100 stays inventory) |
| `TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M` | **50.0** | clip remainder floor |
| string count | **≤ 50** | sanity bound |

Ours, not his: `SUBSTRATE_STATION_M` 5.0, `SUBSTRATE_INTERN_M` 1e-6.

**Other owner rulings:**
* **Runway clip:** clip strings by the **runway outline**, discard anything
  inside, drop remainders < 50 m. Outline = the **shoulder-absorbed union**
  (75.6 m at HECA), not the declared rect — his ruling, because shoulders are
  paved and the runway profile grades them.
* **Substrate** = apt.dat S2 snapshot (`pipeline.py:2253`) ∪ OSM linear
  taxiways, **apt.dat-first, per-LOCATION dedup** (the clause is locative).
* **CIFP is the source of truth for thresholds.** HECA: 05C = 116 m (south
  end), 23C = 114 m (north end). Band centre at chord 1's endpoints matches
  these to +0.07 / +0.61 m — the endpoint law is sound.
* **Chord 1 legitimately descends to 106-107** between along 1462 and 1865
  (his coords 30.116015,31.416090 → 30.113677,31.412894) because of the
  cross-connectors to the much lower 05L/23R, then rises near-straight to
  along 2403 (30.110475,31.408709). **His earlier "111→113" is the IDEAL
  string, not the expected surface.**
* Ground truth: `/Users/noah/heca_strings.osm` — 46 ways, 99 nodes,
  41,412.7 m polyline (the specs' older "40 / 37,327 m" is superseded).

## 3. Where the work stands

**Branch `taut-string-chord-model`, HEAD `d424c9d`, tree clean.**

| commit | content |
|---|---|
| `f1b13c3` | chord model, substrate, clip, tenure, specs |
| `53e1156` | the S1 hook + S1b Dirichlet pins in `solve.py` |
| `d371e68` | working-tree snapshot (other lines' work — recovery point, do not merge wholesale) |
| `b9bd57d` | the pin ledger |
| `d424c9d` | **Ruling 54** + stop-reason and departure ledgers |

**Gate `O4_TAUT_STRING_CONSTRUCTION` default `"0"`. Gate-off byte identity
proven three-way and re-proved after every change: SPLP `d8d0f065…`,
CYXY `dcebb6ff…`** (body hash past the provenance stamp).
*(Historical — both superseded; see §0 for the live baselines.)*

**Landed:** substrate assembly + per-location dedup + seam joints; runway clip
at the owner's outline and floor; through-path composition (authoring
boundaries are NOT chain boundaries); string tenure (an edge is spent only
when an emitted string covers it); the chord model with the three endpoint
read modes; the grip filter; **Ruling 54** (`yield_hard` gains the
law-filtered kept pin set); three ledgers (`pin_ledger`, `walk_boundaries`,
`departures`).

**Retired** (measured, with per-test disposition): the tube, cap propagation,
the funnel, the slope audit, `taut_chain_profile`, `BendWitness`, the
infeasible `StringDefect` classes, the (ii-b) end-datum machinery, §3's value
machinery, the fragment-assembly family.
**KEPT and RESCOPED** (Ruling 53): the phase-A taut pass — provably inert on
strung ground (0 of 3,429 pinned vertices move), retained as the **residual
spine smoother** on unstrung spine. Its footprint (567 vertices moved, max
0.283 m) is the baseline for any future retirement.

### 3a. Implementation map (`route_profile/taut_string.py` unless noted)

| symbol | role |
|---|---|
| `read_endpoint_band_centre` / `EndpointRead` | Ruling 49's read law: `direct` / `interpolated` / `clamped`. HECA 101/0/27 — mode 2 empty **there**, not in general. No snap, no radius constant. |
| `chord_station`, `chord_targets` | z linear in along-station **on the chord** — two numbers give every node a target |
| `compass_ends` | N/S labels from coordinates. **Endpoint order is WALK order and carries no geography** — this caused a transposition that cost a round |
| `filter_pins_by_grade_law` | Ruling 52 grip filter: strict `>` at 1e-9, minimal via a **re-admission pass** (not a greedy stop), endpoint-protective, never releases a law-anchor pair |
| `spine_walk_chains` → `compose_through_paths` → `through_path_chains` | the seam. Global best-collinear pairing, parameter-free; **paths stay LINEAR — that is what keeps open-terrain crossing unrepresentable** |
| `strings_with_tenure` | an edge is spent only by an emitted string; cut/`min_len` edges return; fixpoint, termination arithmetic and asserted |
| `substrate_fingerprint` / `substrate_from_carriage` / `decorate_nodes_onto_strings` | carriage hook side. **Decoration is multi-valued on purpose** (§3 shared-vertex); its index walks segments cell-by-cell — a bbox fill would allocate ~64 M cells for a 4 km diagonal |
| `write_string_sidecar` | idempotent, **called LAST** (see trap 3) |
| `construct_taut_strings` | carriage → service exclusion → chaining → tenure → clip (per-string, so remainders keep the pre-clip chord) → decoration → targets |
| `solve.py` | targets computed at the phase-A call site, grip-filtered, passed as `string_pins=`; merged into the **existing `anchors` set**; post-phase-A overwrite gone; **Ruling 54: `yield_hard |= kept pins`** |

**Ledgers in the `string_domains` sidecar:** `pins`, `walk_boundaries`
(with `is_emitted_end`), `departures`, `pins_in_yield_hard`,
`pin_yield_conflicts`, plus the four counts.

**Retained deliberately:** `taut_string` / `string_with_pegs` are the **§10
rod sweep's**, not string construction's — do not retire them with the
constructor family.

## 4. Measured results — do not re-derive

| | |
|---|---|
| chord 1 delivered at the dip | **106.40 / 106.90** vs the owner's ~106 |
| W-CHORD1 worst bin | −11.07 (baseline) → −10.74 (S1b) → **−5.83**, and it **moved off 1800 to 1600** |
| string-authored defects | **949 → 0** (dissolved by construction) |
| seam pair (W-CHORD2) | 107.83 → 107.83 = **0.00 %** grade, law passes with margin |
| GATE A (length-weighted coverage @ ±8 m) | **86.2 %** |
| GATE B (chord 1 end-to-end) | **FAILS as one string** — corridor fully covered by 3, zero gaps |
| Stage 0 + value path | **73.5 ms**, cheaper than the funnel it replaced |

**The drag mechanism, attributed:** `fp#8` rebuilt `yield_hard` from
`truth_hard` and never inherited the spine freeze, so every vertex phase A
froze went free again and the blend moved it. Ruling 54 fixes it by adding
the kept pins. **Wholesale freeze inheritance was measured to recover the
same ~5.2 m and was rejected** — it over-freezes the unstrung residual that
must yield.

## 5. OPEN DEFECTS — with evidence

1. **G2 FAILS IN PRODUCTION.** `max |emitted − chord|` at kept pins: median
   **0.2342 m**, p90 1.1407, **max 6.9008**; only **28.5 %** within 0.05 m.
   Offline it was 0.000e+00. *Population caveat: 1,580 of 3,790 kept pins
   matched a delivered node within 1 m; the rest are probably spine nodes
   with no nearby emitted vertex — unconfirmed.*
2. **Free-neighbour cap coupling — RULED (Fable Ruling 55), fix not yet
   implemented.** `n_pin_yield_conflicts = 874`: **`free` 786 /
   `law_anchor` 88**, excess median 1.616 m, max 14.682. On chord 1: 36, with
   the **1400-1800 bin holding 7, all `free`, max excess 7.92 m — the same
   station the worst bin moved to.** A pin cannot be moved directly, but its
   un-pinned neighbour can, and cap coupling drags the pin: **the string
   overruled by a blend TRANSITIVELY through the cap.**
   **THE RULING: the neighbour inherits NO freeze and NO new mechanism — it
   already owes the pin exactly one thing under law, the cap.** A yield/blend
   candidate adjacent to a hard node moves within `[hard ± cap·d]`
   intersected with its own law. **BOUNDING, never freezing** — `cap·d` is
   the law's own freedom, so corridors still descend away from pins at cap
   rate. Freezing the neighbours is the wholesale freeze by another name and
   stays rejected. **The law is stated for ALL hard nodes, pins and truth
   anchors alike** — the 88 `law_anchor` conflicts show the same violation
   against anchors, so this was never pin-special; the defect is **any stage
   that MANUFACTURES an over-cap pair against a hard node.**
   **THREE SEPARATIONS BEFORE THE FIX, IN ORDER** (mechanism before fix):
   **(i) THE JOIN FIRST** — 2,210 of 3,790 pins unmatched at a 1 m proximity
   join is the verify-the-reference failure live in our own instrument.
   Re-state the pin→delivered join on **CANONICAL identity** and re-read G2
   on the identity-joined population. **The 0.2342 m median may be partly a
   wrong-object artifact and must NOT be quoted as pin drag until then.**
   **(ii) THE MOVER LEDGER** — per conflict, which stage last moved the free
   member (stamp if cheap, report if not). **(iii)** the 88 `law_anchor`
   conflicts against the α arm: pre-existing or new, one artifact comparison;
   pre-existing routes to its own track.
   **Pre-registered for the fix arm:** identity-joined G2 at pins returns to
   the 0-class where neighbourhoods are lawful; manufactured conflicts
   874 → ~0; the 1600 residual closes toward band/cap-explained;
   hard-adjacent yield infeasibilities surface as **declared** conflicts,
   small and author-carrying — **a large declared population is a finding**
   (the pin web over-constraining the yield network) and returns to Fable.
3. **Chord 1 fragments into 3 strings.** Boundaries at along 398 (turn /
   consensus / route_end, mixed) and 728 (**both ends `consensus`**).
   Corridor census over 239 boundaries: **turn 2**, tenure 113, route_end 63,
   consensus 61. **This is OURS — direction-symmetry and tenure — not the
   owner's tolerance.**
4. **49 hook-time band violations** in the dip window (90 of 966 banded
   corridor nodes above their own ceiling at hook time, worst +2.11 m). The
   corridor arrives at the hook already outside its feasibility band.
   **Upstream of everything else, unattributed.**
5. **The string-attributed law-true slice is UNMEASURED** — that is the flip
   gate (Ruling 19: it must be **zero**). `n_defects = 0` is NOT that gate.
   Needs `O4_TEST_AIRPORTS=HECA test_pavement_grade`, which does **not**
   scope to one airport — price it as four airports / ~710 s.
6. **Offline-vs-production substrate divergence, 3 instances, unattributed**:
   22 apt pieces, 7 OSM ways, 18 strings. **The offline walk is no longer a
   production stand-in.** Make production emit what it did.

## 6. NOT STARTED

* **R1's layer-4 re-read** (offline, on the artifacts) → **R1 CP2** → **R2**.
  R2 is blocked twice over: `O4_REFERENCE_FIELD` is default `"0"` with its CP2
  gates unread, AND S1 changed R1's layer 4 (the spine layer is now the chord).
* **The battery**, then **the tile and the Mac app**. The owner cancelled the
  tile deliberately — he will build his own once the known issues are resolved.
* **A suite read** before anything ships (the live comparator is 24 stable
  failures across 9 files; there were also 5 unrelated `test_crown_seam_ramp`
  reds from a concurrent session).
* **The §6.4 owner filing.**

## 7. Method lessons paid for in this session

**THE DOMINANT FAILURE MODE: two instruments describing different
populations while assumed to describe one.** Seven instances in one night,
**every one caught by an implausible NUMBER, none by code review**:

* distance-to-centerline over a set containing the string's **own source** →
  every apt-tier string read 100 %;
* "corroboration" at 25 m matching the **parallel taxiway 15 m away**;
* a conclusion built on **transposed labels**;
* a pin verdict sampled along the **chord line in the plane** while pins
  follow the walked path — 5 matches against a 311-vertex string;
* a decomposition mixing **two coordinate projections**;
* **the max of a FILTERED set reported as the max** — vertices filtered to
  ≤ 25 m, max quoted as 24.94 m (the filter edge). Real value: **8.64 m**.
  This nearly reached the owner as a structural impossibility that did not
  exist;
* an inventory keyed by `first_vertex`, silently losing **8 of 64 strings**
  while the summary still said 64.

**Defences that work:** predict the magnitude before computing; treat a
too-clean or too-extreme result as a reason to audit the instrument;
exclude the measured object's own source from any reference set; pin ONE
frame/axis/projection and state it beside every number; **make production
emit what it did** rather than reconstructing offline.

**Also standing:** mechanism before fix (interventional evidence, or say
"the data cannot attribute this"); intent questions route to the OWNER, not
to a build — he has ruled correctly from his own data repeatedly, and he
supplies artifacts; a gate-off identity arm is not ceremony (it caught a
shadowed-import `UnboundLocalError` that broke the ungated path for every
airport, which the AST and import probes could not see).

## 8. What the next session should do

1. **Get Fable's ruling on the free-neighbour question** (open defect 2) — it
   is the last named thing between here and closing the residual.
2. **Measure the string-attributed law-true slice** (open defect 5) — it is
   the flip gate and it has never been read.
3. **Attribute the hook-time band violations** (open defect 4) — upstream,
   and it may explain why the clamp bites so hard at that station.
4. Then **R1 re-read → R1 CP2 → R2 → the battery**, per the owner's own
   sequence, and only then a tile and the app.
