# Free-road profile pass (HECA round 5b) — one-way weld + whole-path ramp

Closes what round 5 left open (heca-round5-drainage-and-ramps-spec law 3,
un-implemented; lane/hecar5's interventional evidence, merged 52d54c6e).
The contact-cap scoping (`O4_ROAD_CONTACT_CAP_SCOPE`) shipped DEFAULT OFF
(9ac6ee55) because alone it re-prices but nothing builds the profile:
item-2's site went 0.70 m worse and 9 airside rows moved. This round
builds the profile pass and flips the scoping ON in the same arm.

## Standing evidence (lane/hecar5 — do not re-derive)

- The crossing adoption DOES build the ramp (106.70 → 108.383) and
  `_grade_limit_groundside_chords` (pipeline 6692 + 6957) flattens it
  back: its binding pair is the ring's own RETURN side across the U-loop
  — 5–25 m EUCLIDEAN between points far apart along the PATH. The
  route-metric lesson (rm-route-metric-within-shape-spec, rod-chains-
  split-at-branches) applies verbatim: chords across parallel legs of
  one road must be priced along the path, never across the loop.
- Weld states at the owner sites: item 2 welded (0.000 m); item 4 mouth
  seat (0.02 m); item 3 UNBOUND — nearest end-on approach 1.538 m vs
  the derived 1.5 m (`_PAV_CLEAR_TOL_M + SHARED_VERTEX_TOL_M`) mouth
  tolerance, so nothing binds it.

## Law

1. ONE-WAY WELD: a free road's contact with aircraft pavement pins the
   ROAD to the pavement's SOLVED value — a Dirichlet endpoint. The road
   is solved AFTER airside and never feeds back; airside is king stays
   whole-cloth (zero MOVED airside is again the gate, and now reachable
   by construction).
2. END-ON BINDING TOLERANCE: an end-on approach binds when its gap to
   the pavement is within the road's own half-width (geometric, no new
   constant — item 3's 1.538 m gap binds under a 6 m road; derive, don't
   hardcode; publish refused near-misses like the veto refusals).
3. WHOLE-PATH PROFILE: per free-road chain (path metric, split at
   branches — the rod-chain law), solve the longitudinal profile between
   pinned ends (and DEM-held free ends) at ≤ `SERVICE_ROAD_MAX_GRADE`
   (8 %), monotone where the pins demand it, distributed over the whole
   run including U-turn legs. The profile OWNS the chain's values;
   `_grade_limit_groundside_chords` either prices profile-solved chains
   along the PATH metric or exempts them — it never re-flattens across
   the loop.
4. The contact-cap scoping gate flips DEFAULT ON in this arm (one flag
   day, one measured round).

## Acceptance

- Item 2: monotone ramp start→junction (weld 0.000 kept), cliff at
  30.1052938,31.3989669 gone; the U-turn leg carries the climb to
  30.107403,31.4022258.
- Item 3: end binds (law 2), monotone ramp to 30.1046554,31.3973678.
- Item 4: monotone descent off the apron at 30.114984,31.4107959.
- ZERO MOVED airside rows vs the OFF arm (the round-5 trade eliminated).
- HECA census improves at the four sites; patch-wide not worsened
  beyond attributed un-blinding.
- Controls CYXY/SPJC/OTHH byte-identical OFF; ON deltas attributed.
- Twins: one-way weld direction (airside never moves), binding
  tolerance both sides, path-metric limiter pricing, U-loop
  interventional twin (the flatten reproduced OFF, gone ON).

## AMENDMENT 1 (Fable, 2026-08-28, on lane/hecar5b's fork)

The lane built all four laws; item 4 proves the pass (204.08 % ->
9.35 %). The blocker is METRIC COLLISION: the census prices within-shape
road pairs by euclidean chord, so a path-lawful 8 % ramp across a U-loop
reads 8.33-9.11 % (CYXY +120 rows = 8 % x path/chord, exactly).

RULED — OPTION 1, as the composition of two standing laws:
1. WITHIN-SHAPE ROAD-FAMILY PAIRS ARE PRICED ALONG THE ROAD'S OWN PATH
   METRIC (the route-metric-within-shape precedent extended to the road
   family), and a chord that LEAVES the shape's own pavement polygon is
   the GAP-CHORD class (RULINGS 2026-08-24b: "a step is lawful only
   across a pavement gap") — never priced as surface grade. ONE
   implementation in the harness law register (check_grade), consumed by
   both readers (emitter limiter + census) — the twins pin the two
   readers to one code path per the census-wrapper law.
2. THE MOVED-AIRSIDE GATE IS ADJUDICATED ON THE SOLVE-OWNED FRAME
   (tools/airside_value_delta.py's second frame, its documented
   distinction): graded_strip and other soft receivers ADOPT from the
   pavement they abut and count as airside only in the row-side split —
   adoption rows are attributed churn, not a breach. Gate: solve-owned
   moved airside = 0.
3. Gates (profile pass + contact-cap scoping) flip DEFAULT ON only in
   the arm where: all four owner sites monotone/lawful, the metric-
   collision rows GONE (CYXY back to control class counts or every
   residual attributed), solve-owned moved airside 0, OTHH/LEMD arms
   built.

## AMENDMENT 2 (Fable, 2026-08-28, on lane/hecar5c's report; 5c merged
9486c765 default-OFF)

5c's path metric is RATIFIED as landed (CYXY collision 71->0, both
scopings — longitudinal-only, census-reader-only — correct and twinned).
Two blockers remain, ruled/chartered:

1. PER-STATION CAP UNIFICATION (the lateral_contiguity self-
   disagreement, ruled): cap authority lives at ONE granularity — the
   STATION. The lateral walk's own adjacency read produces a per-station
   cap vector (1 % where the station is genuinely alongside/inside an
   apron per the free-road ruling; SERVICE_ROAD_MAX_GRADE 8 % free), and
   pricing, the solve graph, and the profile pass's cap-Lipschitz
   envelope ALL consume that one vector — one derivation, three readers.
   The way-level `O4_ROAD_CONTACT_CAP_SCOPE` gate DISSOLVES into this:
   end-on contact binds values and never caps any station; lateral
   contact caps exactly the stations it touches. The CYXY +130
   lateral_contiguity rows and item-4's 1 %-held ramp both fall out.
2. THE DOWNSTREAM AIRSIDE CHANNEL (chartered, mechanism-before-fix):
   1,756 solve-owned airside nodes move at HECA concentrated at item-4's
   apron (worst 2.07 m) via a re-derivation AFTER the profile pass
   (candidates: seat_groundside_on_law, ribbon conformance, final
   projection anchor-reach). FIRST measurement of the round: who_wrote
   at 30.11445,31.40993 in the profile-ON arm. LAW: airside solves first
   and NEVER re-derives from road inputs — whatever pass re-seats an
   apron from a road value is the defect, whatever the fix costs.
   Solve-owned moved airside = 0 stays the gate.
3. Flip-ON conditions restated: all four owner sites monotone/lawful at
   their per-station caps (item 4 back to the 9.35 % class, item 2's
   U-loop lawful under path pricing); CYXY/SPJC/OTHH totals not
   worsened, residuals attributed; solve-owned moved airside 0; all
   four controls + LEMD built.

## AMENDMENT 3 (Fable, 2026-08-28, on lane/hecar5d's report; 5d merges
with 5e)

5d RATIFIED as landed: who_wrote exonerates the profile pass (writers at
the item-4 apron: solve_route_profile, final_grade_projection,
gap_fill._emit_one_gap — never the pass); per-station cap vector +
cap_at accessor + gate dissolution land as built (CYXY −30, airside
untouched, solve-owned 0).

RULINGS:
1. THE ORDERING FORK IS FALSE — both arms are hacks around the actual
   defect the law already names: `final_grade_projection` (and any
   downstream conformance pass) RE-DERIVES airside from the road-
   modified layout. Build toward: profile PRE-SOLVE ON (item 4's ramp
   is real, 9.35 %), and the projection treats every solved AIRSIDE
   value as FROZEN Dirichlet data — it may re-derive road/groundside,
   never airside. The 903 @ 0.25 m residue (post-projection conformance)
   gets its own who_wrote and the same freeze, attributed not assumed.
   Gate stays: solve-owned moved airside = 0 with pre-solve ON.
2. THE FIFTH-SITE BINDING QUESTION DISSOLVES — the chord law pins on
   THE CHAIN'S OWN EMITTED END VALUES (self-pins): a chain's end is
   where it meets the settled world, and its emitted end value is that
   consensus, whatever produced it. No adoption, no authority transfer —
   the 2026-08-15 carrier adjudication stands untouched (the strip's
   value is never read). Raise-only toward the chord between self-pins
   (hills kept, as twinned). This closes the CYXY sag (3.631 m below
   chord at station 59.5/190.3) without naming which pavement binds.
3. Flip-ON conditions: as Amendment 2 §3 plus the fifth site monotone
   between its self-pinned ends; solve-owned moved airside 0 at ALL
   airports with pre-solve ON; the 0.25 m residue class attributed and
   frozen or ruled immaterial (< the 0.01 m floor it is not — attribute
   it).

## AMENDMENT 4 (Fable, 2026-08-28, on lane/hecar5e; 5e merged)

§2 RATIFIED (self-pins; fifth site 3.631 -> 0.270 m; early-return made
conditional). §1's blanket freeze REFINED by the lane's measurement (a
blanket freeze removes the projection's own founding repair — planarize
inserts, T-vertex welds, clip rebuilds: +94/+563/+926 rows profile-OFF):

RULED — THE FREEZE IS SCOPED TO UNMUTATED AIRSIDE RINGS: an airside node
on a ring whose OWN geometry changed after the solve may be re-derived
(the projection's purpose); an airside node on an UNMUTATED ring is
FROZEN — re-deriving it because a road/groundside input changed is
Amendment 3's defect. ONE derivation: the pass's existing
`_scoped_projection_defer_ids` / `post_solve_mutation_set` machinery —
never a second mutation reading. Twin: both halves (mutated ring
re-derives; unmutated ring frozen against a road-input change).

Flip-ON then re-measured whole: item 4 back at its ~9% class; all five
sites; solve-owned moved airside 0 at all airports (road-welded shared
nodes take the AIRSIDE value by the one-way weld — a residual there is
attributed, not accepted); the 0.25 m residue who_wrote; OTHH/LEMD ON
arms built; census totals vs control attributed.

## AMENDMENT 5 (Fable, 2026-08-28, on lane/hecar5f; 5f merged)

Scoped freeze RATIFIED (controls at pre-round values; OTHH −226). The
structural residual is ruled:

1. SNAPSHOT-BLIND RE-DERIVATION: within the projection (and any
   post-solve conformance), an AIRSIDE ring's re-derivation reads every
   NON-AIRSIDE neighbour from the SOLVE-TIME SNAPSHOT — the same
   snapshot the mutation detection already keeps (one snapshot, two
   readers, never a second copy). Airside repair output is thereby
   road-blind by construction: legitimate repair (planarize inserts,
   T-welds, clip rebuilds) reads the world as it stood when airside
   solved; the profile's road movements can never reach an airside
   value through any re-solve. Roads themselves re-derive freely
   (Amendment 3).
2. WELD IDENTITY: the freeze keys join on the canonical 11-dp spelling
   via the chord limiter's existing `_airside_claimed_keys` second
   reading — one edit, never a third key derivation (canonical-identity
   law).
3. Flip-ON: the full Amendment 2 §3 + Amendment 3 §3 bar, now with
   HECA + LEMD ON arms BUILT, the 0.25 m residue who_wrote spent, and
   solve-owned moved airside 0 at all five airports.

## AMENDMENT 6 (Fable, 2026-08-29, on lane/hecar5g's STOP — record
corrected)

Amendments 4/5 rested on a FALSE PREMISE: the mutation-detection
snapshot is `SCOPED_FINAL_PROJECTION`, a PARKED feature (no gate,
retired 2026-08-05 on a build-time measurement) — the 5f scoped freeze
never fired (byte-identical, measured). NEVER un-park it: that retire
was an owner-level measurement decision, and the freeze needs only
VALUES, not the ring/defer machinery.

RULINGS:
1. FREEZE FOUNDATION — a values-only solve-time store: prefer
   `post_solve_mutation_set`'s carried `solved_values` store IF its
   coverage spans the solve-owned airside population (MEASURE the
   coverage first); else capture a values-only snapshot unconditionally
   (an array copy — state its build-time cost per the hard law). One
   store, and both the freeze and its gate instrument read it.
2. MUTATION CRITERION from the live store: a ring is mutated when its
   post-solve node population differs from the store's membership
   (canonical identity, post-solve inserts/welds), never the parked
   ring capture. Snapshot-blind re-derivation (Amendment 5 §1) then
   reads non-airside neighbours from that values store.
3. GATE REFINEMENT — THE WELD SET IS NOT A BREACH: a shared-claim
   variable (one solved node claimed by both an airside role and a
   road-family role) is the WELD — its value is the one solve's
   consensus and legitimately moves when road law changes. The
   zero-moved gate applies to NON-INTERFACE solve-owned airside;
   interface movement is REPORTED separately (count, worst |dz|) and
   the owner's sim read adjudicates it. SPJC's 98 no-road-contact
   movers are NOT interface and must be attributed under the live
   freeze.
4. Then the full five-airport closing arm and flip-ON per the standing
   bar (with §3's refined gate).

## AMENDMENT 7 (Fable, 2026-08-29, on lane/hecar5h — the freeze family
is CLOSED, refuted; the composition that remains is ruled)

5h proved: the live `solved_values` store is a real zero-cost foundation
(99.89/99.95 % coverage), and ANY ring-selection freeze fails
structurally — membership-criterion over-freezes (CYXY repair lost,
+86 airside profile-off) while released rings re-derive against a
frozen neighbourhood and move 1,490 no-road-contact nodes at SPJC (the
FREEZE moves them, not roads). Ring selection cannot reach
airside-blindness: value-mutated rings are exactly the rings roads
touch.

RULED — ROAD-BLIND RE-DERIVATION, NO FREEZE:
1. Every post-solve airside re-derivation (projection + conformance)
   runs EXACTLY as production — same population, same solve, full
   repair — except ROAD-FAMILY neighbour values resolve through the
   live `solved_values` store (solve-time values) instead of the
   current layout. The projection already resolves `_carried_solved`
   through that store; this scopes WHICH source road-family values come
   from inside airside re-derivations. Profile OFF ⇒ store == layout ⇒
   byte-identical by construction. Profile ON ⇒ airside output cannot
   see the profile's road movements. Nothing is frozen; no ring is
   selected; SPJC's released-ring perturbation cannot occur.
2. The weld set stays as Amendment 6 §3 (shared-claim variables
   reported, not gated). True welds take the airside value under the
   one-way weld, so no airside-interior/weld step is minted.
3. All freeze gates from 5e-5h are RETIRED-KEPT-GATED off; their
   ledgers are the refutation record.
4. Closing arm: the five-airport flip-ON per the standing bar with
   Amendment 6's refined gate; 0.25 m residue who_wrote under the
   road-blind arm.

## AMENDMENT 8 (owner 2026-08-29a — FINAL): accept and ship

The solve-equilibrium question is RULED (RULINGS 2026-08-29a): a law
correction's equilibrium shift is not a breach. GATE (final): every
airside move in the ON arm attributed to the law correction, none
exceeding the step law; weld set reported per Amendment 6 §3. The
solve-partition is a chartered docket, not a blocker.

FLIP-ON AUTHORIZED: profile pre-solve + per-station caps + path metric
+ self-pins flip default-ON in one commit after the five-airport arm is
measured under this gate. The 5e-5i freeze/road-blind knobs stay
retired-kept-gated.

## AMENDMENT 9 (Fable, 2026-08-29, on lane/hecar5j's STOP)

The +100s are NOT the accepted equilibrium shift — they are the
census-wrapper failure mode at cap granularity: the per-station cap
vector has three emitter-side readers and the census is not among them
(`_check_lateral_contiguity` prices every station against the way-level
`o4_grade_law_cap`). RULED: the vector TRAVELS IN THE PATCH — a sidecar
key beside the axes exactly as `pair_caps` does — and
`_check_lateral_contiguity` prices each station against ITS cap: the
FOURTH reader of the one derivation. Sidecar-key and law-family
registration go through the harness register so the census twins
(structurally-impossible-omission class) cover it. The CYXY/SPJC +100s
must fall out arithmetically, as the path metric's +120 did in 5c.
Then the five-airport ship arm re-measures and flips per Amendment 8.
