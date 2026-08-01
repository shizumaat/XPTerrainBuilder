# The taut-string model, done once — one reference field, one law, one pass

Review + consolidation spec, 2026-07-30/31.  Written after the
`O4_ENVELOPE_FROM_BAND` round, from disk artifacts only (no new builds:
`/tmp/envband/`, `/tmp/bandq/`, `/tmp/retro/`, `/tmp/pathtrace2/`; three
new measurements below are scripts over those artifacts).  All code-line
citations verified at HEAD+dirty 2026-07-30 (`16d30c9` + the uncommitted
envelope/reference stack) — main tree, not the worktree.

**REVISED 2026-07-30 (owner answers + follow-up chord ruling).**  The
owner answered the §6 rulings and supplied the parallel-taxiway chord
(§0).  This revision: records the answers verbatim (§0); marks ruling 1
ANSWERED and executed (§1.7); adds the owner-chord measurement and the
new W-CHORD acceptance witness (§1.8); adds the anchor priority order
and the string-construction objective as normative text (§2, §4.1,
§4.3.1); sets ε_role (§4.4); resequences §5 with node-space unification
FIRST (owner override) and adds the string-construction step S1; §6 is
rewritten to show answered vs open rulings.  Companion spec:
`node-space-unification-spec.md` (step U1).

The owner's instruction: the taut-string idea has been implemented
piecemeal over two days as at least six overlapping mechanisms, and the
newest measurement shows they interact in ways nobody designed.  Do it
properly, once.  Deletion of legacy paths is preferred over gating them.

---

## §0 Owner rulings 2026-07-30 — recorded verbatim

First batch (answers to §6's numbered rulings; the owner's numbering
2-5 maps to context, ε, sequencing, and execution):

> 2. Answers to open questions:
> 3. The correct elevations at the seam nodes are the ones closest to a
>    chord drawn between 30.124628°N 31.427557°E and 30.101184°N
>    31.396354°E, we care about CIFP runway thresholds, tile boundary
>    seams, runway crossings, then longest possible straight "strings"
>    that only bend where required to allow the route graph to stay
>    within grade between all the anchors.
> 4. Aprons and taxiways tolerance only needs to be within 50cm I
>    think, and roads within 1m.
> 5. If possible I would prefer node-space be unified FIRST, anywhere
>    there's redundancy we're introducing extra work, slow downs, and
>    mistakes.
> 6. Have a Fable agent consider my answers and update the spec if
>    needed, then implement the spec.

Follow-up ruling 1 (after the coordinator relayed the chord geometry;
KML at `/private/tmp/HECA_seam_site.kml`):

> There should be no lateral cap, it should be a straight chord from
> approximately 111m at the North end to about 113m at the south end,
> so nearly flat, meaning the seam elevation would be around 112 if
> matched the string, but will be pulled down to stay within grade to
> serve the 05L/23R runway that's much lower.  I expect closer to the
> 108m.

Follow-up ruling 2 (locating the seam nodes on their own chord):

> They also should be on a taxiway centerline, so should be on a
> string between 30.110767N 31.406856E and 30.114627N 31.403031E and
> graded at 1.5% to the rest of the taxi route centerline graph.  My
> rough guess is between 103m to 106m around that area but not more
> than 1.5% between them of course.

> They're on a taxiway, so thats the standing rule (depending on
> taxiway size) for any taxiway.

Site disambiguation (measured, §1.8): the FIRST chord is the primary
parallel taxiway NW of runway 05C/23C; the seam nodes are NOT on it
(~332 m off-chord).  The SECOND chord is the perpendicular cross
taxiway running NW toward 05L/23R, and the seam nodes ARE on its
centerline.  Three sites are in play — chord 1, the KML dip corridor
ON chord 1, and chord 2 carrying the seam pair — and §1.8 keeps them
distinct.  Follow-up 1's "seam ~112 if matched the string" was said of
chord 1 before follow-up 2 placed the seam on chord 2; the operative
seam expectation is follow-up 2's 103-106 with ≤ 1.5 % pairwise.

---

## §1 Critique of the newest result (`O4_ENVELOPE_FROM_BAND` ON)

What landed: `feasibility_project` reads its break declaration AND its
non-broken clamp from `node_band` (the `reach_band_unified` list sampled
once at `solve.py:682`, carried to the final projections by canonical key
via `layout._env_band_keys`, `solve.py:2393`) instead of the transitive
closure over the pavement pair graph.  Gate-off byte-identity is proven
on disk (`/tmp/envband/HECA_ebPRE2.bodyhash == HECA_ebOFF.bodyhash`,
`d4f52f02…`).

### 1.1 What is genuinely better (verified from the retained patches)

* TOTAL over-cap pairs halved: 18,278 → 9,096 (HECA, within-shape +
  break-bucket).  Cross-matching pair keys between the two arms
  (`xmatch.py` over `/tmp/HECA_eb{OFF,ON}.osm`, law-true sidecar
  context): **10,307 of the OFF arm's 15,067 distinct break-bucket pair
  keys no longer violate at all** under ON.  That is genuine healing,
  not bookkeeping.
* CYXY strip-seam tears 6 → 0; flats keep ZERO step/tear sections;
  corridor sag 0.527 → 0.225 m; mouth step 1.20 → 0.67 m; mid-edge
  steps 204 → 160; spine kinks 185 → 135.
* The two closure Dijkstras are skipped when the band has no inversion —
  a real single-pass dividend.

### 1.2 The within-shape 453 → 2,011 is NOT just re-classification

Measured (same cross-match, HECA, pair identity = both endpoint
coordinates in the shared builder anchor frame, 0.05 m quantised):

| of the ON arm's 2,011 actionable pairs | n |
|---|---|
| same pair was in OFF's break bucket (re-classification) | 906 |
| same pair was already actionable under OFF | 442 |
| **NEW — did not violate at all under OFF** | **663 (33 %)** |

The NEW class is not mild: excess p50 1.76 %, p90 10.7 %, max 67.6 %;
154 of the 663 are > 5 % excess.  The memory's "largely
RE-CLASSIFICATION" is two-thirds right and one-third wrong: freeing
13k nodes minted ~663 genuinely new violating pairs at HECA.  SPJC
(flat) shows the same signature at lower amplitude: 81 → 1,113
actionable against a break bucket that fell 2,819 → 211 — absolute
totals improved (2,900 → 1,324) but a flat fixture now reports > 1k
actionable pairs and the test suite fails on it (STATUS 2026-07-30:
"SPJC 1113 within-shape plane violations, HECA 190 edge steps, CYXY
36" — 10 airport-build tests failing on the current dirty tree).

Also under-reported in the round's headline: **building199's worst
pad-face weld step regressed 0.490 → 1.400 m** (probe.out) — the weld
gate is ≤ 0.2 m — and vertex-to-edge steps rose 26 → 30.

### 1.3 The seam attribution — verified, and sharpened

From `/tmp/bandq/heca_band.*.pkl` (per-node elev, closure, band, broken
sets at fp#8 and both final passes, OFF behaviour):

* The seam node (0.28 m from 30.11211,31.40562) is **broken at every
  pass**, and its elevation is 108.50 / 108.50 / 108.45 across the three
  dumps — i.e. the OFF value IS the §7 broken-branch hold
  (`one_solve.py:1829-1834`: `clamp(z_ref, hard-neighbour interval)`,
  where `z_ref` = the pass-entry snapshot).  "Its 108 came from being
  broken" is **supported**.
* Its pair-closure interval is inverted at every pass ([104.99, 72.09]
  at fp#8), its band is wide and feasible ([98.7, 117.5] at fp#8-time;
  [87.8, 136.0] at final-time).  Free the node and no mechanism holds
  108: the §7 reference term for FREE nodes is a weak proximal pull plus
  an exact-return polish that only returns a node when its neighbours'
  *current* intervals admit it (`one_solve.py:2593-2658`) — a whole
  freed region drifts coherently and the polish follows it down.
* The warm-start alternative is falsified on disk (`HECA_ebDIAG`:
  2,037 vs 2,011, identical 102.75 seam).
* **The sharpening: the drop is enabled by the reference-snapshot
  ratchet.**  `z_ref` is rebuilt at EVERY pass from that pass's entry
  `elev` (`solve.py:1404-1406` at fp#8; `solve.py:3851-3852` at the
  final projection).  Whatever a pass drifts becomes the next pass's
  reference, so a 1-2 m per-pass sag compounds to 5.5 m and the polish
  faithfully "returns" nodes to the drifted values.  Under OFF the
  quarantine hold froze the chain; the band change removed the freeze
  and exposed the ratchet.  So: *proximately* the seam drop is the lost
  §7-on-broken hold (as attributed), but the mechanism that let 5.5 m
  accumulate is that there is no stable reference field — only a chain
  of per-pass snapshots.

### 1.4 A finding nobody had: "THE band" is not one field

Both `/tmp/bandq` dumps rebuilt `reach_band_unified` fresh at their
pass.  Diffing the two rebuilds at 82,093 matched node coordinates
(`band_drift.py`): floor |Δ| p50 2.6 m / p90 35.0 m / max 75.1 m,
ceiling |Δ| p50 3.5 m / p90 16.4 m, and **100 % of matched nodes drift
> 1 m on at least one side** between the fp#8-time and final-time
rebuilds (crown lift accounts for ≤ ~0.35 m of that).  The band is
state-dependent on whatever layout/G state it is built from.  The
shipped implementation samples once at `solve.py:682` and carries by
key — which happens to be the right *shape* of fix — but nothing
defines WHICH build moment is law-true, and every consumer that
resamples (R's honesty ladder via `_BandView`, seats, validators, the
forensic probes) can see a materially different envelope than the one
the solver enforced.  Any "the band says X" claim is currently
ill-posed without a timestamp.

### 1.5 The interaction nobody designed (the honesty ladder goes vacuous)

`apron_reference.py`'s anchor-honesty ladder (rule 2) accepts an anchor
as law-true when the node is *not quarantined* and its value sits inside
its own band.  With the band-sourced envelope, broken ≈ 0 and bands are
tens of metres wide, so **every drifted anchor passes as law-true** and
R — the apron string — is rebuilt each pass on the drifted values,
re-validating the drift instead of resisting it.  Reference honesty
(Track 1) was implemented against the quarantine as its truth signal;
the envelope change deleted that signal.  This is the concrete instance
of "mechanisms interacting in ways nobody designed."

### 1.6 Build time

`check_build_time --runs 3` (cbt.log): CYXY total 44.41 → 42.91
(**improved −1.50 s**) but phase "Solving elevations" 27.65 → 33.12
(**+5.47 s, REGRESSION → hard-law FAIL**), emit phase −5.86 s.
Same-tree alternating arms: 36.4 s (OFF) vs 43.5 s (ON) median,
non-overlapping.  Cause is the enlarged free set (~13k previously
frozen nodes sweeping), not envelope overhead.  Per CLAUDE.md item 6
the accumulated stack owes a Fable-5 whole-pipeline optimisation
review regardless of this change's disposition.

### 1.7 Disposition of `O4_ENVELOPE_FROM_BAND` — ANSWERED, with a nuance

**Status 2026-07-30: R0 (default OFF) STANDS as the interim
disposition, owner-informed — but R0 does NOT close the seam defect.**
The owner gave TWO criteria for the seam pair, and at these nodes they
disagree (measurement §1.8, site iii):

* **VALUE**: the owner's rough guess is 103-106 m there ("pulled down
  to stay within grade to serve the 05L/23R runway that's much lower";
  05L/23R measured z′ 60.76-64.42 vs 05C/23C 111.23-115.75).  envON
  (102.75/103.61) lands essentially inside that band; envOFF
  (108.26/108.59) is 2.3-5.6 m high.
* **LAW**: "not more than 1.5% between them."  The seam pair test
  (~23 m separation): envOFF 1.4% PASSES, envON 3.7% VIOLATES — and
  the raw DEM itself is 3.7% (unlawful; the very reason the site needs
  solving).

So **neither arm is correct**: envOFF is lawful-but-high, envON is
right-height-but-unlawful.  A lawful-but-high surface ships over an
unlawful one — hence OFF — and the seam stays an OPEN defect whose
target is a straight lawful string on the cross-taxiway chord (§1.8
W-CHORD2): inside ~103-106 at the seam station AND ≤ 1.5% pairwise.
The default flip is landed in-tree (`solve.py:686-709`, default "0");
remaining R0 work is verification only (§5 R0-v).  The spec must never
claim R0 closes the seam.

**P0 FALSIFICATION NOTE (2026-07-30, Fable ruling — supersedes every
"green suite" claim in this section and in §1.2's failure
attribution).**  P0 measured the suite TWICE at the OFF default (tree
`50f45b49d849`, independent runs: 25F/3848P and 24F/3849P, diff = one
suite-context flake): **all 10 airport-build failures persist at OFF.**
They are arm-INDEPENDENT, tree-resident defects — the standing
non-convergence classes — and §1.2's attribution of them to the ON
arm was wrong.  Consequences: (i) R0's default-OFF disposition STANDS
on the surviving measured grounds alone — the owner's confirmation,
envON's 1.5%-law violation at the seam pair (3.66-3.75% vs OFF
1.40-1.44%), the building199 weld 0.49 → 1.40 m, the 663
neither-arm pairs minted by ON, and the ON-arm +5.47 s unapproved
phase regression; the suite never discriminated the arms and is
struck from R0's reasoning.  (ii) The 10 failures' fix path is this
line's R1/S1/R2, and their disposition is tracked against the §5.0
suite comparator, not against the envelope gate.  (iii) The
recommendation text below is the historical record; read its "green
suite" clause as falsified.

The original recommendation follows, kept for the reasoning record:

**Recommendation: default OFF now, re-enable in the same measured
change that lands the reference field (§5 step R1+R2), keep the gate as
the A/B lever.**  Reasoning:

* Ships today with ON: the owner-visible burial recovery fails its gate
  (108.26 → 102.75 vs the required 106-109 class), building199's weld
  triples past its gate, 663 new violating pairs at HECA, a flat
  fixture reporting > 1k actionable pairs, 10 failing tests, and an
  unapproved build-time phase regression.  Ships today with OFF: the
  proven byte-identical shipped baseline.
* The falsified warm-start shows there is no cheap partial fix; the fix
  is the reference field itself (§4), and flipping ON belongs with it.
* What OFF gives up (tears 6→0, sag, halved over-cap) is real but not
  gate-protected; what ON gives up is gate-protected and user-visible.
* This also honours the hard law: the phase regression is not shipped
  unreviewed.

If the owner instead rules the halved over-cap + zero tears worth more
than the seam class in the interim, ON is defensible — but then the
seam gate must be formally re-classed by the owner (ruling required),
and the build-time review is due immediately.  Either way the disposition
is a one-line default flip whose both arms are already hash-proven.

### 1.8 The owner-chord measurements — THREE sites, two named witnesses

All numbers from the retained round patches (`/tmp/HECA_eb{OFF,ON}.osm`
+ `.axes.json` sidecars, law frame z′ = emitted + sidecar crown drop);
**zero builds spent**.  Probe: `owner_chord_probe.py` (§7).  Overcount
caveat binds throughout: raw over-cap counts on an emitted patch
OVERCOUNT — the law-true count is `O4_TEST_AIRPORTS=HECA
test_pavement_grade`, never bare check_grade on a patch
(`check-grade-needs-law-true-frame`).  CAUTION (plan register 14,
measured 2026-07-31): the variable does NOT scope every parametrized
test — a "HECA-only" law-true run builds four airports (~710 s);
budget accordingly.  OFF-vs-ON comparisons here are
informative; absolute counts are not.

**Site (i) — the parallel-taxiway chord (owner's first chord).**
A(30.124628, 31.427557) → B(30.101184, 31.396354), 3,979.8 m, bearing
within 0.01° of runway 05C/23C at a constant ~241 m NW offset: the
primary parallel taxiway drawn as ONE straight string.  Emitted
corridor vertices (|lateral| ≤ 25 m) carry role `junction` in the
global-slice patch (1009/1013) — the witness is role-agnostic airside
pavement, runway and service excluded.

**Site (ii) — the KML dip corridor**, 537 m, lies ON chord 1
(along-from-A 1857-2393).

**Site (iii) — the cross-taxiway chord (owner's second chord) carrying
the seam pair.**  C(30.110767, 31.406856) → D(30.114627, 31.403031),
~565 m, bearing 319.3° — perpendicular to chord 1 (90.2°), running NW
OUTBOUND toward 05L/23R (consistent with the lawful descent story).
The seam nodes sit ON its centerline (lateral ~−7 m; along ~167-191).
The owner's per-size grade rule for it is ALREADY law:
`config.taxi_grade_cap_for_letter` (code A/B < 15 m → 3 %
`TAXI_MAX_GRADE_NARROW`; C-F/unknown → 1.5 % `TAXI_MAX_GRADE`, gate
`O4_TAXI_GRADE_BY_WIDTH` default ON), and `TAXI_GRADE_WIDTH_ROLES`
deliberately EXCLUDES junctions/aprons — the seam pair's emitted roles
(junction/apron) hold the tighter 1.5 %.  Cite this; do not invent a
parallel mechanism.

**Measured (envOFF = shipped baseline):**

| measurement | envOFF | envON | owner ruling |
|---|---|---|---|
| chord 1 worst 200 m-bin departure vs the 111→113 string | **−11.07 m** (along 1800) | −9.96 m (along 1800) | straight string, no lateral cap, sag forbidden |
| chord 1 dip span (1857-2393) | min 100.56, med 103.58 | min 101.92, med 104.41 | — |
| chord 1 end medians (N/S) | 110.54 / 111.92 | 111.60 / 112.74 | "approximately 111" / "about 113" ✓ |
| seam pair values (site iii) | 108.26 → 108.59 | 102.75 → 103.61 | rough guess 103-106 |
| seam pair grade over ~23 m | **1.4 % PASS** | **3.7 % VIOLATE** | "not more than 1.5% between them" |
| raw DEM at the pair | 103.62 → 104.50 = 3.7 % — the DEM itself is unlawful here | | |
| chord 2 edge audit (informative) | 10/104 edges > 1.5 %, all micro-edges at the C end | 24/108, incl. 33.3 % over 3.4 m adjacent to the pair | — |

**Defect A (site i) — chord-1 sag, present in the SHIPPED baseline.**
The chord's ENDS match the owner's string almost exactly, so his
111→113 string is the right reference — and the MIDDLE sags up to
11.07 m below it in envOFF.  R0 does not fix this; §1's headline
metrics never measured it.  The §10 interval rod holds spines to ±2 cm
of the *phase-A faired string* — an 11 m sag under an enforced rod
means **the string itself is constructed sagging**.  The defect is in
string CONSTRUCTION (§4.3.1), not rod enforcement.  Clause 5 in its
purest form: cap-lawful sag below the string is a forbidden answer.

**Defect B (site iii) — the seam, open in BOTH arms** (§1.7): envOFF
lawful-but-high, envON right-height-but-unlawful, DEM unlawful.  The
owner's 103-106 band DOES appear on chord 2 further out (envOFF reads
105.4-106.4 from along ~320 to the D end), so a straight string that
keeps 1.5 % and lands in the owner's range is plausibly constructible.

**W-CHORD1, acceptance witness for site (i)** (patch analysis, no
build): per-200 m-station medians of airside-pavement z′ within 25 m of
chord 1, against the straight line through the measured end-bin medians
(owner nominal 111→113 is the sanity ruler for the ends, ±1 m).  Gates:
* per-step (S1 and after): worst bin departure strictly improves from
  −11.07 m;
* R3 acceptance: every bin within ε_taxi (0.50 m, §4.4) of the string
  EXCEPT at DECLARED bends — a bend carries a named grade-feasibility
  witness (the anchor and route that force it, §4.5 semantics);
* no local V: a departure that recovers within the chord is
  presumptively unlawful sag unless its declared bend witness explains
  BOTH sides.

**W-CHORD2, acceptance witness for site (iii)** (patch analysis, no
build): the seam-pair values and pair grade, plus the chord-2 station
profile.  Gates:
* the seam pair is ≤ 1.5 % (existing law, cited above) — never traded
  away;
* R1/R2 acceptance target: seam-station values inside the owner's
  ~103-106 band while the pair stays lawful — i.e. a straight lawful
  string on chord 2 achieves BOTH criteria that §1.7 shows the two
  arms split between;
* chord-2 fabric adjacent to the pair mints no new > 1.5 % steps
  (OFF-vs-ON comparison basis, law-true count at sign-off).

**Hypothesis to test interventionally — ANSWERED (P3, 2026-07-30,
zero builds; full table in `s1-taut-chord-constructor-spec.md` §1a).**
The 05L-pull explanation for the chord-1 dip is FALSIFIED as a direct
cause (zero hard nodes within 100 m of the chord; swapping the entire
anchor set moves nothing), and so is the correlational band-ceiling
reading (the ceiling sits below the string yet masking it alone moves
0.00 m — latent, not binding; it would have been the TENTH falsified
mechanism).  The attributed class is **corridor decomposition + peg
inheritance**: `_build_spine_corridors` cuts the 3,980 m chord into
62 corridors with zero anchors; 59 endpoint pegs (8 % of nodes) carry
100 % of the movable defect (A8 ≡ A3 bin-for-bin), and with pegs
freed + the then-binding ceiling masked the constructor holds the
owner's line at −0.05 m.  §4.3.1's "longest possible straight chord
between its anchors" was structurally never attempted.  Fix = S1
Stage 0 (maximal-string assembly; pegs dissolve).  Ruling 6 (§6) now
has its concrete object: the band ceiling 0.66-5.94 m below the
owner's string over along 1000-2400 — binding only after Stage 0 —
pending P3c's offline provenance attribution.  Open, owned by P2's
instrumentation: the post-phase-A step that drags the live profile
2.2 m below what the constructor emits (262/721 chord nodes below
their own band floor).

---

## §2 The owner's model (assembled rulings — canonical text in memory)

1. **Anchors immovable, in PRIORITY ORDER** (owner answer 3, §0):
   **CIFP runway thresholds > tile boundary seams > runway crossings**,
   then the strings between them.  Where two anchor classes contradict,
   the higher class holds its value and the contradiction is a declared
   defect charged to the lower class (clause 8) — never a blend.
2. **Reach follows taxi centerlines only.**  Buildings and building-less
   aprons are ENDPOINTS attached by straight chord(s) from their airside
   face to the nearest VISIBLE through-pavement centerline
   (`grade_law.building_requires_full_frontage`: full frontage at/above
   the size threshold; central chord below it — and such a pad is then a
   LOCAL anchor whose surroundings are NOT runway-reach-constrained).
   A building reachable only through groundside is DETACHED → flat pad
   at its own DEM.
3. **The seat IS the pad's rod.**  Fabric between buildings/anchors =
   taut chords.  Pavement CUTS THROUGH or fills, never drapes, unless
   the elevation source is 1 m lidar or better.
4. **Aprons**: visible geodesic, not 1 % all-pair; 1.5 % longitudinal
   along taxi spines, 1 % lateral; an apron wants to be flat and grades
   up to 1 % only where necessary.
5. **Two flexes**: caps bound how the STRING IS CONSTRUCTED; they are
   never licence for the surface to wander off its string.  Cap-lawful
   sag below the string is a forbidden answer.  **Strings are straight
   and maximal** (owner answer 3 + follow-up, §0): a string is the
   longest possible straight chord, it carries NO lateral-departure
   allowance of its own, and it bends ONLY where grade feasibility to
   the anchors (clause 1) forces the bend — each bend is declared and
   witnessed, never emergent from solver drift.
6. **Minimum displacement**: an unconflicted node returns to its
   reference EXACTLY; a conflicted one moves the least the law permits,
   inside its feasibility box.
7. **Airside is king**: groundside is graded and may be pulled BY
   airside, never pulls airside, never carries reach.
8. **Feasibility is guaranteed**: the real airport proves a lawful
   surface exists; "infeasible" is a defect to attribute, never an
   answer.

---

## §3 Mechanism inventory (what exists today, and the verdict)

Line numbers: HEAD+dirty 2026-07-30, main tree.  Verdict key:
**KEEP** (survives as-is), **ABSORB** (its job moves into the field),
**DELETE** (owner's stated preference over gating).

| # | Mechanism | Where | What it does / references | Fires when | Model clause | Verdict |
|---|---|---|---|---|---|---|
| 1 | **§10 interval rod** (string-as-law) | `solve.py:1078-1222` (mint, law clamp), interval edges w/ `envelope_skip` | Hard ±2 cm slab per spine link vs the faired phase-A string; slabs law-clamped into the pair budget | every projection | clause 5 (spine instance) | KEEP — becomes the spine layer of the field tube |
| 2 | **Rod compose across decimation** | `solve.py:2995-3520` (`_carry_rod…`), `emit_decimate.py:585-…` (string-end keep) | Carries slabs into the rebuilt final space by canonical key, composing over removed runs | final projections | clause 5 continuity | KEEP (until the node-space unification of §5-U deletes the need) |
| 3 | **§7 bounded yield boxes** | `solve.py:1331-1381` (fp#8), `:3804-3831` (final); `one_solve` `group_bounds`/`node_bounds` | Freed seats/pads clamp to their seat-time reach-band `[lo,hi]` | fp#8 + finals | clause 6 ("inside its feasibility box") | KEEP |
| 4 | **§7 reference rods — free nodes** | `solve.py:1394-1406`, `:3843-3852`; `one_solve` proximal pull + exact-return polish `:2593-2658` | `z_ref` = **pass-entry `elev` snapshot** for every movable node; weak pull + polish | fp#8 + finals | clause 6, but self-referential | ABSORB → the field (§4); the snapshot builders are DELETED |
| 5 | **§7 reference hold — broken nodes** | `one_solve.py:1829-1834` | Broken node parked at `clamp(z_ref, hard-neighbour interval)`, then quarantined immovable | only when a node is BROKEN | clause 6 — but a *hard* hold gated on a *feasibility* verdict | ABSORB → field hold (§4.5); this asymmetry is the bug of record |
| 6 | **Break blend (t-ramp)** | `one_solve.py:1789-1807` | Distance-weighted blend between the contradicting anchor fields | broken nodes | none (containment device) | ABSORB → field hold; keep only for genuine band inversions |
| 7 | **Chain-rigid blend** | `one_solve.py:1906-2038` | Rigid Δ-shape placement of broken rod chains | broken ∩ strung | clause 5 inside break regions | DELETE — redundant once the field holds the chain shape (already near-inert under band envelope: broken ≈ 0) |
| 8 | **Branch-rigid blend** | `one_solve.py:2039-2100 | Same for rod-degree-≥3 vertices | broken branch vertices | same | DELETE (same reason) |
| 9 | **Corridor-ref-string** | `solve.py:1407-1455` (`O4_CORRIDOR_REF_STRING`), `_rod_string_values` `:2906` | Non-service corridor `z_ref` from the rod-implied string instead of the snapshot | fp#8 | clause 5→6 bridge | ABSORB → the field's spine layer (same function, called once) |
| 10 | **Apron reference surface R** | `apron_reference.py` (whole module), call sites `solve.py:1501-1526`, `:3891-3938` | Dirichlet chords + POCS caps per welded apron component; anchor-honesty ladder; supplies apron `z_ref` | rebuilt at fp#8 AND at the final pass | clauses 3+4 | KEEP construction, ABSORB invocation: built ONCE into the field, carried by key — the per-pass rebuild and the vacuous honesty rule 2 (§1.5) go |
| 11 | **Pad-rod coupling** | `solve.py:946-…`, `:1456-1486`, `:3853-3881` (`O4_PAD_ROD_COUPLING`) | Pad-face welds reference the pad's rod level | fp#8 + finals | clause 3 | ABSORB → field layer (pads before aprons in priority) |
| 12 | **Reach band** (`reach_band_unified`) | `building_feasibility.py:624`, `raster_reach_band.py`; sampled `solve.py:682` | Route-metric, service-excluded floor/ceiling from `G.runway_anchor` over centerlines | built once per build (but rebuildable, §1.4) | clause 2 | KEEP — becomes *the* feasibility source, with a pinned timestamp (§4.2) |
| 13 | **Band-sourced envelope** | `one_solve.py:1714-1886`, carry `solve.py:2380-2404`, `:4058-4084` (`O4_ENVELOPE_FROM_BAND`) | Break declaration + clamp from the band; closure skipped when no inversion | all projections | clauses 2+8 | KEEP (default per §1.7), the model's feasibility layer |
| 14 | **Pair-closure envelope** | `one_solve.py:1738-1788` (`_reach` Dijkstras) | Transitive closure over `edge_lim`, seeded from every hard node | gate off, or any band inversion (for blend t) | none — the rejected composition | DELETE with §5 step R2 (its last job, blend `t`, is replaced by the field hold) |
| 15 | **GS witness clauses** | `one_solve.py:1684-1712`, `solve.py:984-1051`, `:3939-4019` (`O4_GS_NO_AIRSIDE_WITNESS[,_FINAL]`, both default OFF) | Withdraw groundside anchors from the envelope seed set beyond the mouth horizon | gates on (they are not) | clause 7 | DELETE — structural under the band envelope (band seeds runway anchors only; groundside cannot witness by construction) |
| 16 | **GS pin DEM bound** (Part C) | `anchors.py:1364-…` (`O4_GS_PIN_DEM_BOUND`), `MOUTH_ALLOWANCE_M` `anchors.py:31-49` | Groundside pin value ≤ own DEM + cap·15 m | seeding | clause 7 (value side) | KEEP |
| 17 | **Groundside terracing** | `adjacent_ground.emit_groundside_terrace_walls` (`O4_GROUNDSIDE_TERRACE`) | Lot retreats + retaining wall instead of emit averaging | emit | clause 7 + terrace law | KEEP (out of the field entirely) |
| 18 | **Spine-frame pair law + route-leg floor** | `grade_graph.py:113,133` (`O4_SPINE_FRAME_PAIRS`, `O4_ROUTE_METRIC_PAIRS`) | The law web the sweeps enforce (1.5 % along route / 1 % lateral, visible geodesic) | graph build | clause 4 | KEEP — but see the §3.1(e) contradiction |
| 19 | **Seats + frontage law** | `anchors.build_building_seats`, `build_nobuilding_apron_seats`, `grade_law.building_requires_full_frontage` | Band-derived seat + box per building/apron; endpoints-with-chords law | seeding | clauses 2+3 | KEEP |
| 20 | **Yield machinery** | `solve.py:1284-1330` (movable pads, freed seats, seam pins stay), mouth-relax `solve.py:~1443-1505` | Which nodes leave the hard set at fp#8 | fp#8 | enabling machinery | KEEP |
| 21 | **Pad lift-only restore** | `solve.py:4106-4113` | A pad group the final projection SANK > 0.15 m reverts to seed | after final #1 | clause 6 (crude) | ABSORB — with the field tube a pad cannot sink silently; delete after step R2's measurement confirms it never fires |

### 3.1 Named overlaps, gaps and contradictions

(a) **§7 fires-only-when-broken** (the bug of record, verified §1.3):
the model's clause 6 is implemented as a *hard hold* for quarantined
nodes (#5) but only a *weak pull* for free nodes (#4).  Feasibility
verdict and reference strength are entangled; flipping the verdict
silently removed the strongest reference mechanism in the tree.

(b) **The reference-snapshot ratchet**: `z_ref` is rebuilt at every
pass from that pass's entry `elev` (#4), so references are downstream
of the very drift they exist to prevent.  R (#10) is likewise rebuilt
per pass on incoming values.  Violates the single-pass principle and
reference honesty simultaneously; §1.3 measures its 5.5 m consequence.

(c) **The honesty ladder is vacuous under the band envelope** (§1.5):
rule 2 of #10 used "not quarantined" as its truth signal; #13 made
that signal near-universally true.

(d) **Two feasibility answers still exist**: #13 declares on the band;
the sweeps still enforce #18's pair web, whose closure at the seam is
*inverted* ([105.0, 72.1]) while the band is comfortably feasible
([98.7, 117.5]).  The quarantine used to contain that contradiction;
now it plays out as distributed sweep compromise — the 663 new pairs,
the 160 mid-edge steps, and the seam's 102.75 are its residue.  Per
clause 8 this contradiction is a defect with an owner: either chords
exist in the law web that the visible-geodesic law forbids, or a real
corridor is priced 1 % where the ruling says 1.5 %, or the surface
must be allowed to hold its string and *report* the web pairs.  The
model resolves it via the field tube (§4.5) + forensic attribution
(§5 step R4) — never by letting the web drag the surface.

(e) **"THE band" has no timestamp** (§1.4): 100 % of nodes drift > 1 m
between rebuild moments; consumers can consult different envelopes than
the solver enforced.

(f) **Two node spaces** force canonical-key transport of the band,
boxes, refs, rod slabs and R anchors (#2, #3, #10, #13) — five carries,
each with its own loss mode (the rod-key lesson).  Structural
single-pass violation; §5-U.

(g) **The broken-branch family is quadruply redundant**: blend (#6),
§7 hold (#5), chain-rigid (#7), branch-rigid (#8), edge-couple clamp
and bounded-box clamp all write the same nodes in sequence
(`one_solve.py:1789-1870`).  Under the band envelope most are dead
code (broken ≈ 0) yet all remain live paths for gate-off and for flat
fixtures' mouth-relax break exports.

(h) **Dead gates linger**: `O4_GS_NO_AIRSIDE_WITNESS[,_FINAL]` are
default OFF with their machinery (second Dijkstra, weld classification
`solve.py:3976-4019`) still in-tree — the owner's stated preference is
deletion.

(i) **Two flexes unenforced off-spine**: clause 5 is a hard interval
law on spines (#1) but only the weak #4 pull on aprons/fabric —
cap-lawful sag below R is still reachable there (it is exactly what
§1.3 measured).

---

## §4 The correct model (normative)

### 4.1 One reference field, built once

A single module (`reference_field.py`, working name) builds **Z_ref: the
airside reference field**, once per build, in the solve node space,
stored by canonical key.  Layered by priority (higher wins):

1. **Anchors** (clause 1): their values.  Never in the free set.
   Internally ordered per clause 1's priority: 1a CIFP runway
   thresholds, 1b tile boundary seams, 1c runway crossings.  A field
   cell claimed by two anchor classes takes the higher class's value
   and reports the contradiction (clause 8).
2. **Pads**: the seat/rod level (`build_building_seats`; the merged
   flat-group level).  Detached pads: own DEM (existing
   `pad_detached_dem`).
3. **Pad-face weld shadow**: the pad's own level (absorbs #11).
4. **Spine corridors**: the rod-implied string
   (`_rod_string_values` over the §10 slabs — absorbs #9), service
   corridors from `apply_service_road_dem_follow`'s shape.
   **Service sub-domain — CONFORMANCE RULING (2026-07-31, CP2b's
   CYXY half): this sentence's two sub-domains are LOAD-BEARING.**
   The R1 implementation skipped service nodes from layer 4, so they
   fell to layer 6's A-copy — and the A-sourced reference was itself
   unlawful pre-solve (6.03 % prescribed at a 5.0 %-cap service
   pair; the layer-4 pair byte-identical across arms as control).
   Operationally the follow shape IS the live assembly-moment state
   at service nodes (the follow has run by then), so: **service
   nodes take live-`elev` (never `_rod_string_values`, never
   `elev_entry`)** — exactly what the absorbed legacy code's ★
   comment warned ("a rod-derived reference re-imports the
   pre-follow profile that minted the CYXY 8.95 % service pairs").
   An implementation gap against this spec, not a design question;
   ARM-6 retired unspent.
   **VERIFIED 2026-07-31: the fix healed the CYXY spine invariant
   1 → 0 (67 tests, mutation-checked; register 16's ★ obligation
   carried at the code site).  Layer 4's sub-domains are now
   canonical as 4a (taxi: rod-string) and 4b (service: live-elev,
   applying independently of slab existence).  The HECA gates moved
   not at all — the two CP2 defects are measured INDEPENDENT.
   Open at CYXY: +4 non-spine within-shape violations post-fix
   (total 7 → 11) — the CP2 gate reads the TOTAL, so these are
   pending attribution, reported not accepted.**
   **Domain rule (P2-CP1 ruling, 2026-07-30): layer 4's domain is ALL
   strung vertices — a strung vertex NEVER takes layer 6.**  The
   ~108.5 the passes hold at the seam IS the current string value,
   manufactured each pass by the §7 broken hold clamping against the
   hard-neighbour interval; the snapshot layer never governed the
   seam.  The field carries that value in layer 4 by construction,
   and `clamp(field, interval)` replaces the per-pass manufacture.
   **Source-moment rule (P2-CP1 part 2, single-tree instrumented
   build): layer 4 reads the ASSEMBLY-moment (candidate B) strung
   state — the reconciled level the passes demonstrably enforce
   (|field − final#2| spine p50 0.077 from B vs 0.628 from A; the
   pre-registered gate (iv) is the arbiter, since gate (i) cannot
   discriminate: the rod string is a Δ-constraint, moment-robust —
   string(A) 108.458 vs string(B) 108.504 at the seam).  Express
   caveat: pre-S1 this embeds chord-1's attributed sag level, and
   that is CORRECT for R1 — R1 stabilises today's string; S1 replaces
   its construction, after which the same B-read carries the taut
   string's reconciled level.**
5. **Aprons**: R (absorbs #10's construction), built ONCE, anchored on
   layers 1-4 of *this field* — never on live `elev`.  The honesty
   ladder collapses to "anchors come from the field" and rule 2 is
   deleted.
   **"BUILT ONCE" — RETAINED AS A MEASURED CHOICE (CP2b
   decomposition ruling, 2026-07-31).**  R is genuinely
   pass-dependent when rebuilt per pass (site-matched spread p50
   0.299 / p90 1.898 / max 7.589 m over 812 sites), so "once" PICKS
   the assembly-moment R and freezes it — that cost is now measured,
   not assumed.  The premise stands because the moment axis explains
   the ARM DELTA, never the LAWFUL VALUE: at building199 BOTH
   moments miss the pad-adjacent lawful band (pad 89.27, weld target
   ≤ 0.2; frozen R 90.165 is 0.9 high, final-pass R 88.792 is 0.48
   low — legacy's steady state), and per-pass referencing is the
   §1.3 amplifier (heals lawful settling at one site, worsens
   CYXY's cluster 11 → 14 at another — measured).  Neither global
   per-pass nor per-site moment rules are adopted; site-tuned
   moments would be drape-tuning in a moment's clothes.  HYPOTHESIS
   (per the §1a rule, not an attribution): R's assembly-moment
   CONSTRUCTION INPUTS at pad faces — the layer-3 shadow may not
   reach R's Dirichlet anchor set as intended; offline-testable
   riding the next authorized build's layout dump, no new spend.
   The weld's ≤ 0.2 delivery remains R2's (tube + layer-3 shadow),
   under the standing constraints: cross-layer moment-consistency
   at interfaces; no global per-pass R.
6. **Everything else airside**: the phase-A/B solved value at field
   build time (the one legitimate snapshot, taken once).

**OWNER MODEL CONFIRMATION — MASTER STRINGS AND THE DRAW-TOWARD
END-STATE (2026-07-31; ruling on the owner's design question,
verbatim: "If we make only long straight 'strings', shouldn't that
mean we don't need any short strings after densification, everything
still draws toward the master string as much as it can within grade
requirements right?").**  CONFIRMED, with two precisions:
* **Master strings = the AUTHORED taxiway routes, never an extent
  class.**  Chord 2 (~565 m) is owner-ruled to BE a string, so
  "short strings we don't need" means DENSIFICATION FRAGMENTS —
  strings that exist only because dense geometry chopped the
  authored structure.  A master string is a Stage-0-assembled
  maximal string over the SPARSE authored centerline structure
  whose ends carry datums (clause-1 or (ii-b)).  Dense nodes attach
  to their string BY AUTHORSHIP (`on_line` membership), never by
  nearest-neighbour geometry.
  **REFINED BY THE OWNER 2026-07-31 (verbatim: "strings should be
  only straight trunks, changing if there's a turn.  I can count
  how many we should have for HECA, and I could also map them in
  OSM or KML if that's helpful"): AUTHORSHIP IS MEMBERSHIP,
  STRAIGHTNESS IS SEGMENTATION.**  Authorship says WHICH nodes
  belong to a route; the straightness criterion says WHERE the
  route cuts into strings — turns are the cut points, so an
  authored route that turns is SEVERAL strings.  **Axis separation
  (normative): straight in PLAN — a horizontal turn ENDS a string;
  bending only in ELEVATION, and only where grade forces it — a
  vertical bend is a declared event WITHIN a string.**  The turn
  criterion's STRUCTURE is ruled (bearing discontinuity between
  adjacent authored segments at fragment scale — the validated
  window; never dense-node local bearings, which are measured
  fillet noise; a JUNCTION is not a turn — chord 1 runs straight
  through 33; an AUTHORED GEOMETRY BREAK is not a turn — the
  36-fragment tiling is straight); its numeric THRESHOLD is
  calibrated against the owner's ground-truth map, then frozen
  (S1-CP2-reviewed) — never invented.  The map also supplies: the
  expected string COUNT (the number this line has never had),
  per-string wrong-merge vs wrong-split decomposition, and the
  assembly fixture's re-base target.  Negative controls with
  teeth: terminal-segment heading AND dense-node local bearing
  must both FAIL against the map.  Level-2's merge criterion and
  the turn criterion are ONE criterion from two sides: merge
  across a junction iff not a turn.
  **MAP ARRIVED 2026-07-31 (`/Users/noah/heca_strings.osm`, §7):
  40 strings [DENOMINATOR SUPERSEDED same day — the owner extended
  the map to 46 ways / 99 nodes / 41,412.7 m; canonical rule in the
  S1 spec's DENOMINATOR HYGIENE: the file as on disk, measured by
  the acceptance instrument]; chord 1 confirmed ONE string (3,974.8 m, max
  interior bend 0.00° — no turn at 1652; the 58.5 % assembly
  result was a defect, definitively).  Calibration ruled:
  `TAUT_STRING_TURN_DEG = 6.0` on the 36 clean strings, seated in
  the measured empty interval (5.0, 7.54), the 4 outliers referred
  to the owner; membership goes COLLINEARITY-FIRST with a
  value-side RECOGNITION tolerance for source-data near-misses
  (identity ≠ membership ≠ bridging — S1 spec §2).**  Fallback-rate metrics are
  trunk-set-scoped; non-trunk fallback is the design, not a defect
  — with the explicit non-laundering clause that the ≥ 159 surfaced
  contradictions sit on trunk-class corridors and remain §6.4
  defects under any scoping.
* **"Everything draws toward the master string" is the S1b
  end-state, not current behaviour** (measured: fabric references R
  or the snapshot; the 67.1 %-of-motion harmonic has no altitude
  preference).  The confirmed end-state re-founds the reference
  law: fabric reference = the grade-law projection OUT from the
  master-string web (1.5 % along-route / 1 % lateral, §2 clause 4),
  pads keeping layers 2/3 priority; layer 5's R becomes the apron
  INSTANCE of that projection (anchored on string crossings + pad
  shadows — no longer an independent field that can wander); layer
  6 SHRINKS to off-web fallback (the A-copy load-bearing only where
  no string/pad governance exists); the harmonic is re-founded with
  STRING Dirichlet boundaries — S1b's demotion seen from the other
  side, and with string BCs the harmonic finally has an altitude
  preference: the strings'.  Service 4b untouched (outside the web,
  free-road ruling).  One construction moment — strings, then
  relaxation — preserving the moment-consistency constraint.
  Designed at S1b by Fable AFTER S1's measurement, per the standing
  ordination.
   **Moment rule (P2-CP1 ruling; evidence CORRECTED 2026-07-31 to the
   single-tree instrumented build — the first version cited a
   cross-tree artifact, see §5.0's single-tree rule): layer 6's
   source is the PRE-PROJECTION phase-A/B state — "candidate A",
   captured as one list-copy of `elev` before fp#8's feasibility
   projections run.  Single-tree seam values: A = 108.454 (in the
   108.5 class), B = 109.266 (above it), finals 108.500/108.450.
   Candidate B is rejected for layer 6 on measurement + model
   definition: the A→B delta on non-strung movable fabric is p50
   0.000 / p90 0.259 / max 19.199 with 14.78 % of nodes moving —
   the A-copy is LOAD-BEARING, and what B adds is exactly the
   projections' drag, which references must not inherit.  Layers 2
   and 3 also read A (pads sit at their seats there).  Layer 4 reads
   the ASSEMBLY moment instead — see the source-moment rule above.
   The field's ASSEMBLY POINT stays decoupled from the source
   states: assembly happens where all structural inputs are in scope
   (B's code location), consuming the A-copy for layers 2/3/6 and
   the live state for layer 4.**

**Groundside is not in the field** (clause 7): it is graded separately,
terraces between graded ribbons, and connects to airside only through
the mouth allowance (#16), airside → groundside direction only.

The field is immutable after construction.  Every projection pass —
fp#8, final #1, final #2 — consumes the SAME field (by canonical key +
crown lift, like the boxes today).  No pass ever re-snapshots.

### 4.2 One feasibility source, timestamped

`reach_band_unified` is built ONCE, at a **pinned moment: after anchors
and seats settle, before the first yield projection** (today's
`solve.py:682` sampling, moved after seating if measurement shows seat
values feed it), stored by canonical key, and consumed by: the envelope
(#13), the seats' boxes (#3), R/field construction, and the validators.
No consumer may rebuild it (delete `_band_probe_list`-style resampling
from production paths; a unit test asserts the band object is
constructed exactly once per build).  §1.4 is the measured reason.

Off-net ⇒ not broken ⇒ local law governs (the existing documented
contract).  Pad-adjacent fabric: the band remains an OUTER feasibility
box only; its *reference* comes from the pad layer (clause 2's "not
runway-reach-constrained" is satisfied because the reference — what the
node returns to — is pad-derived; the band merely bounds).

### 4.3 Minimum displacement, stated once

The solve is: **minimise displacement from Z_ref, subject to (i) the
law web's pair caps, (ii) the band boxes, (iii) hard anchors.**  An
unconflicted node ends AT Z_ref exactly (the existing exact-return
polish, now against the immutable field).  This subsumes #4/#5/#6 with
one rule and no broken/free asymmetry.

### 4.3.1 How the strings themselves are CONSTRUCTED (owner answer 3)

§4.3 says the surface returns to Z_ref; this clause says how Z_ref's
spine layer is built.  Normative:

* A corridor's string is the **longest possible straight chord**
  between its anchors (§2 clause 1's priority classes), interpolated
  linearly.  Strings carry NO lateral-departure allowance (owner
  follow-up 1, §0).
* The string **bends only where required** for the route graph to stay
  within grade between all the anchors — i.e. a bend is admitted only
  when the straight chord would violate a grade cap or miss an anchor
  value, and each admitted bend carries a DECLARED witness (the anchor
  and cap that force it), in the §4.5 report format.  Bend count is
  minimised: prefer one bend that restores feasibility over many small
  ones; never let bends emerge from solver drift or DEM following.
* This objective SUPERSEDES inheritance of the phase-A faired profile
  as the string source.  §4.1 layer 4's "rod-implied string" is
  therefore a transition state: at step S1 (§5) the spine layer's
  values are re-derived as taut chords per this clause, and the §10
  rod then holds the surface to THAT string.  §1.8's defect A (11 m
  mid-chord sag under a faithfully-enforced rod) is the measured
  reason this clause exists.
* Feasibility interacts as clause 8 demands: a chord that cannot be
  drawn lawfully (anchor values + caps admit no straight string and no
  min-bend string) is a defect to attribute, never a licence to drape.

**STRINGS ARE TARGETS, NOT GEOMETRY (owner clarification 2026-07-31,
verbatim: "The strings are SUPPOSED to be idealized, they don't
actually exist or get emitted, they're creating a taught string
between end points to give the spines a target of the ideal
elevation, knowing that they will be pulled away from it by various
grading requirements, but trying to achieve that straight profile
where possible.")**  This is §4.3's minimum-displacement model and
§2 clause 5 stated operationally by the owner — convergence, not
change.  Normative consequences:
* A string is an idealized ELEVATION TARGET between two endpoint
  elevations; it is never emitted — no weld/decimate/carry class
  exists for string objects (they live as store artifacts and
  construction inputs; the S1 hook's elevation rewrite is how
  targets ENTER the solve, not an emission).
* `TAUT_STRING_RUN_MARGIN_M` is MEMBERSHIP ONLY (which spine nodes
  take this target) — the plan-geometry wander of real pavement
  around an idealized line; NEVER a quality bound or fit tolerance.
* ACCEPTANCE is elevation-approach-to-ideal with every departure
  attributable to a specific grading requirement — W-CHORD1's R3
  form IS this test (worst bin = failure to achieve the ideal;
  departures live only as declared, witnessed bends).  The count
  gate (46 ± pending) survives as the SHAPE of the target field:
  short profiles cannot express one long straight ideal, even
  individually taut.
* **ONE TARGET FIELD, THREE CONSUMERS:** the string web + its
  grade-law projection is the single target source; phase-A
  relaxation (S1b), the reference field (layer 4), and the R2 tube
  consume it at construction, reference, and enforcement — three
  code paths that may NEVER diverge in source.  The owner's
  statement is S1b's design preamble.
* Endpoint elevations are the string's WHOLE input — endpoint
  selection's blast radius is the entire string (why class D's
  45/45 collide with spanned anchors).  Designed, ENABLED ONLY
  after the provenance table: the §2.2b arithmetic runs at ADOPTION
  as an admission test; a materially contradicting adoption is
  REFUSED to free with a declared `datum_refused` record — and the
  refusal default INVERTS if provenance shows the anchors, not the
  datums, are the defect.

**THE SPINE-WALK (owner verdict 2026-07-31 — the third construction
reframe: pairwise → run-based → spine-following; full text and
rulings in the S1 spec §2):** the owner's verdict on the tagged
unmatched runs attributed "pretty much all" of them to ONE defect —
runs cutting across open terrain between different spines — and
supplied the rule as an algorithm: follow the spine, stop when it
turns, leave the curve with no string, emit a string per straight
segment > 100 m.  Ruled: the construction becomes CHORD-GROWING
CONSTRAINED TO THE WALKED SPINE PATH (the run-based core survives;
the domain changes; open-terrain crossing is UNREPRESENTABLE by
construction — verified by test).  **"Sustained departure" and
"straightens" are EMERGENT, not primitives** (corrected 2026-07-31:
the earlier ruling text implied primitives that exist nowhere) —
segments end at bound-departure, curving spine kills successors
short, the ≥ 100 m emission discards them; an emitted string must
be DIRECTION-SYMMETRIC (forward/backward consensus — parameter-free;
forward-only growth was the artifact that let curve tails absorb).
The walk stops at a turn, a spine GAP (P7's holes — a hard
constructor blocker; acceptance stays scoped to the spine-reachable
subset), or route end.  The margin transforms from admission radius
to VALIDATION bound, suspect pending the contamination re-measure
(register 21's fifth strike, pre-registered).

**OWNER RULINGS 2026-07-31 (D1 + the margin + the simplification
framing; verbatim: "We have good spines at HECA, where are they
coming from, and what does the taxi centerline network look like at
it's earliest, simplest stage?  The strings should BE the existing
route network just without the curves and intermediate nodes.  But
for the strings alignment is less critical and could be 5m either
side of the spine and probably be fine, so if OSM has additional
useful data, that would be acceptable for purpose of our simple
string lines."):**
* **D1 RULED — per-consumer source policy, the general principle:**
  the 2026-05-27 apt.dat-only ruling STANDS WHERE IT WAS AIMED
  (centerlines feeding pavement CLIPPING, where misalignment
  mis-clips); strings are clipped against NOTHING, so the ruling's
  failure mode does not apply to them — strings admit OSM linear
  taxiway data where useful.  Never recorded as "the May ruling was
  relaxed": **source admission is per-consumer, keyed to the
  consumer's failure mode.**
* **The margin is OWNER-SUPPLIED at ±5 m** (`TAUT_STRING_SPINE_
  TOLERANCE_M = 5.0`; one constant, two jobs — the simplification
  band and the string-vs-spine validation bound; only he moves it).
  The 20 m constant retires; its epitaph completes when the
  contamination re-measure names the cause (explanatory now, not
  value-setting — the fifth strike keeps its lesson).
* **The construction: the MECHANISM survives, the SUBSTRATE moves —
  CONDITIONALLY.**  "The strings should BE the existing route
  network minus curves and intermediate nodes" is a SIMPLIFICATION
  of the earliest-stage network, and the walk's chord-growing +
  emergent-curve-discard + direction-symmetric consensus IS the
  simplifier (validated); the input tier moves from the processed
  spine to the RAW route network (apt.dat 1201/1202 + OSM linear
  per D1) — which, if committed, dissolves the processed-tier
  artifact classes (interning near-miss inter-chain edges; the
  density/endpoint saga; plausibly bend-split fragmentation).
  COMMIT GATE, pre-registered: P7's raw-network characterization
  must show per-route polylines covering the owner's
  string-inventory class at HECA; an incoherent raw tier returns
  the substrate ruling for redesign.  Surviving regardless: ± 5 m,
  ≥ 100 m, direction symmetry, selection layering, (ii-b) datums,
  identity ≠ membership ≠ bridging.
* **OWNER RULINGS (2026-07-31, verbatim: "+/- 8m is acceptable, and
  the union is fine.  The goal here is majority coverage for long
  straight sections so we can smooth them to our string which is
  more faithful to a real airport.  We don't need 100% coverage."):**
  (1) **±8 m** supersedes ±5 m — `TAUT_STRING_SPINE_TOLERANCE_M =
  8.0`; the constant's chain: 20.0 (retired; epitaph pending the
  explanatory re-measure) → 5.0 (owner) → 8.0 (owner).  (2) **The
  APT+OSM UNION is owner-approved** as the string substrate (his
  confirmation on the ruled composition).  (3) **ACCEPTANCE
  REFRAMED — his terms, not inventory equality:** GATE A (primary)
  = LENGTH-WEIGHTED MAJORITY COVERAGE of the owner's map strings at
  ±8 m, long straights weighted where it matters (measured state:
  union 95.6 % length-weighted, 32/46 by count; the apt.dat
  turn-cut walk covers 12/12 of his ≥ 1000 m strings); GATE B =
  chord 1 end-to-end (measured whole, 3,990 m); GATE C = the
  elevation witnesses W-CHORD1/W-CHORD2 unchanged (his purpose
  clause IS the elevation goal); ≤ 50 stays as an inventory SANITY
  bound.  [Acceptance MEASURED 2026-07-31 and two rulings issued on
  it — dedup granularity SUBSEGMENT; chain domain = maximal
  through-paths (a junction, an authored break, a route id, a dedup
  seam are NOT chain boundaries); GATE B's FAIL attributed to the
  chain boundary, not the walk; the count gate carries a
  pre-registered decision rule.  Canonical text: the S1 spec's
  ACCEPTANCE-MEASUREMENT RULINGS block.]  Exact count-matching, the 69-vs-46 chase, and
  correspondence-table equality DEMOTE to diagnostics (register 23
  applied); the 8-anomaly answer demotes to denominator hygiene.
  Stage-1 is NOT declared passed from the characterization's
  instruments — S1 runs the acceptance measurement itself against
  these gates (zero-build; register 21's population-instrument
  rule).
* **R3 COMMITTED (2026-07-31 — the gate met beyond its terms):**
  the raw tier IS the owner's model as-ingested (HECA: 151 routes /
  46,142.9 m / 438 vertices → 196 pieces / 436 vertices / −0.1 m
  after the bend-split; **161/196 pieces already two-point straight
  lines; 121/151 routes emit as one piece**; no beziers — 1201/1202
  are plain lat/lon).  **The session's chased fragmentation is
  MANUFACTURED at one stage:** `apply_route_arc_spine`
  (151 polylines → 653 ways) with `route_line=None` destroying
  parent identity at `route_arcs.py:556-564` — one line explaining
  BOTH `RouteChain` 1:1 and the 36-fragment tiling of chord 1.
  **Substrate = the S2 snapshot** (`pipeline.py:2253`, 196 pieces),
  composed with OSM linear taxiways per the D1 per-consumer ruling
  (apt.dat-first dedup: an OSM way within the ±5 m corridor of an
  S2 piece yields; OSM stands where apt.dat is absent — the 8 D1
  lines, where ±5 m governs string-vs-its-own-source).  [Two
  same-day updates, canonical in the S1 spec's
  acceptance-measurement rulings: the tolerance is the owner's
  ±8 m (his 2026-07-31 ruling superseding 5.0), and dedup
  granularity is RULED SUBSEGMENT — "where" is locative,
  per-location never per-way; 275/282 standing ways at HECA are
  partial, so the way reading leaves 75 % of emitted metres
  duplicated.]  The added
  junction/runway arcs are NOT a ±5 m conformance defect (wrong
  scope — that ruling governs STRINGS; the arcs are processed-spine
  geometry for other consumers; under S2, strings never see them) —
  recorded as unasserted context for other lines, alongside the
  `[w.size]*nseg` per-segment cap collapse (uniform `seg_caps` —
  noted for the §6.4 band/cap filing's context, unasserted).

### 4.4 Two flexes, enforced everywhere (the tube)

Clause 5 generalised off the spine: wherever the field is defined and
the node's hard-neighbour interval admits it, the surface is confined
to **|z − Z_ref| ≤ ε_role**.  The tube is implemented as the §10 slabs
are: interval constraints, `envelope_skip` semantics, law-clamped so a
tube never contradicts a pair budget it sits inside.  A node whose tube
cannot be reconciled with its hard neighbours or caps leaves the tube
by DECLARED CONFLICT (reported with witness, like break pairs today) —
never by silent sweep drift.  Cap-lawful sag below the string becomes
unrepresentable rather than merely discouraged.

**ε_role — ANSWERED (owner answer 4, §0), with the adopted reading
stated.**  The owner: "Aprons and taxiways tolerance only needs to be
within 50cm I think, and roads within 1m."  Adopted normative reading:
these are **acceptance tolerances** — how far the emitted surface may
sit from its ideal string — not a mandate to loosen construction-time
devices; a tighter construction rod is compliant because tighter always
satisfies looser.  Values:

| where | ε (tube half-width) | note |
|---|---|---|
| spine strings (taxi centerlines) | **construction rod ±2 cm** (unchanged §10 slabs) | the STRING is the law object; the 0.50 m acceptance is met a fortiori |
| apron + taxiway fabric (off-string pavement) | **0.50 m** | replaces the spec's proposed 0.10 m |
| roads (service / groundside graded roads) | **1.0 m** | reference = the service DEM-follow shape (§4.1 layer 4) |
| groundside otherwise | not in the field (clause 7) | terrace law governs |

Reasoning for keeping the 2 cm rod: the rod pins the string's SHAPE
during the sweeps; loosening it to 0.50 m would re-admit exactly the
mid-string sag class §1.8 measures (the surface could drift half a
metre per node while "within tolerance"), un-doing measured wins for
no owner-visible gain.  Flag for owner confirmation: if the intent was
instead "the rod itself may be 0.50 m wide", say so and R2 re-measures
with that width — the tube machinery is identical either way.

**Emit-decimation non-implication (stated position).**  The 0.50 m /
1.0 m tolerances do NOT loosen the two chord decimators
(`emit_decimate`, `to_osm` — both cap chords at 60 m with their own
deviation tolerances; `two-decimators-mask-each-other`).  Those bound
EMITTED MESH GEOMETRY against the solved surface, a different contract
from surface-vs-string acceptance.  Relaxing them for triangle-count
savings is a separately-measured optimisation (R6's whole-pipeline
review may consider it); it does not follow from this ruling and is
not silently widened into.

### 4.5 Feasibility and conflict semantics

* BROKEN = band inversion only (#13, unchanged).
* A broken node holds at `clamp(Z_ref, hard-neighbour interval)` — the
  same hold as today's #5 but sourced from the honest field, applied
  through the same code path as every other node (the tube), so
  breaking/unbreaking a node no longer changes which reference law
  governs it.  This deletes the t-ramp blend (#6) for everything except
  genuine band inversions, and deletes #7/#8 outright (the field
  already carries every chain and branch shape).
* Remaining over-cap pairs between field-held values are REPORTS with
  witness attribution (clause 8): each is a defect in the law web, an
  anchor value, or topology — named by the forensics (#5 step R4),
  never resolved by dragging the surface off its field.

### 4.6 What is deleted (owner preference: delete, don't gate)

* The pair-closure envelope (`_reach`, `ceil/floor` dicts, the
  every-hard-node seeding) — #14.
* Both GS witness gates and their machinery — #15 (structural under
  4.2/4.5; re-run the SPJC 78→121 check once at deletion time to
  confirm no behavior change from removing OFF-gated code).
* Chain-rigid and branch-rigid blends — #7, #8.
* The three per-pass `z_ref` snapshot builders and the per-pass R
  rebuild — #4's and #10's invocation sites.
* The honesty-ladder rule 2 and `_BandView` resampling.
* `O4_YIELD_REFERENCE_RODS`, `O4_CORRIDOR_REF_STRING`,
  `O4_APRON_R_LAW_TRUE`, `O4_PAD_ROD_COUPLING` as separate gates —
  the field has ONE gate (`O4_REFERENCE_FIELD`, default ON once landed;
  off = byte-identical legacy for one release, then the legacy path is
  deleted too).
* The pad lift-only restore (#21) after measurement confirms the tube
  makes it a no-op.

---

## §5 Sequencing (mechanism-before-fix at every step)

### 5.0 The validation ladder (standing practice — owner budget ruling)

Airport builds are the scarce resource (measured on this machine: HECA
305-400 s, SPJC ~105-150 s, CYXY ~35-45 s, SPLP ~10-12 s; the HECA
pytest battery ~10 min per arm; four airports × two arms plus batteries
is 90+ minutes).  Every step below climbs this ladder IN ORDER and
states its build budget as an honest TOTAL — including the builds its
"cheap" rung needs as inputs, since "the replay is 1 s" is misleading
when the replay's dump requires a 6-minute build:

* **(a) existing artefacts** — both arms of most changes in this line
  are already on disk (`/tmp/envband/`, `/tmp/bandq/`, `/tmp/retro/`,
  `/tmp/pathtrace2/`, the probe kit dumps).  Exhaust these first.
* **(b) offline replay** — ~1 s per variant against an
  `O4_DUMP_SOLVE_STATE` / `/tmp/bandq`-style dump; the probe kit reads
  emitted patches directly.  A NEW dump costs a full build — say so.
* **(c) unit / synthetic tests** — mechanism proofs on fixtures.
* **(d) ONE test airport — HECA for this line** — iterated until the
  step FULLY SUCCEEDS there.  A development loop on HECA is ~6-7 min
  per iteration; budget the iteration count, and escalate to the
  coordinator if it is exhausted rather than silently continuing.
* **(e) the full multi-airport battery** — ONLY at final acceptance,
  as a sign-off, never as a development loop.

Every step additionally: its own named gate, default ON only after its
measurement; gate-off byte-identity proven by body hash (`tail -n +3`)
on a copied `src/` tree; build-time statement (`check_build_time --run
--runs 3`, never single runs); `git log`+`git status` before/after;
main tree, `venv/bin/python` from that cwd, one build per process,
outputs to files; no KCLT.  No effect sizes are predicted — expected
*direction* only, with the interventional measurement that must precede
the next step.

**THE SUITE COMPARATOR (normative, Fable ruling 2026-07-30 after P0).**
The suite baseline for this whole line is **P0's confirmed 24-failure
set** (tree `50f45b49d849`, two independent clean runs:
25F/3848P/18S/7xf labelled `taut-P0-baseline` and 24F/3849P harvested;
diff = one flake, `test_layout.py::test_to_osm_is_idempotent` —
CLOSED by P0b 2026-07-31: the `o4_provenance_built` wall-clock stamp
vs a full-text compare, ~5-10 % per-execution base rate in isolation
(the earlier "3/3 isolated ⇒ suite-context" reading was an
underpowered-sample error, see the single-tree rule below); test fix
= plan P0c).  Files: pavement_grade 5, crown_seam_ramp 5,
supporter_fate 3, runway_end_resa_cut 3, compare_target 3,
supporter_smallest 2, tile_cut_parity / object_bake_span_limit /
msfs_xplane_pack 1 each.  Acceptance at EVERY step of this line:
**zero failures outside this set** (the flake excepted, noted when it
fires); failures healed FROM the set are recorded per step and never
regress silently.  "Suite green" is retired as an acceptance phrase —
the 10 airport-build members are this line's target defect classes
(see the §1.7 P0 falsification note): R3 aims to heal them, and any
member still failing at R3 sign-off goes to R4 attribution instead of
blocking on a phrase.  A step report that says "24 failures" is
reporting BASELINE, not regression — that mistake is now structurally
impossible to make honestly.

**REBASE SEMANTICS (Fable ruling 2026-07-31 — the pinned tree hash
`50f45b49d849` no longer exists; hashes go stale, sets with audit
trails do not):** the 24F set above is the HISTORICAL MARKER; the
**live comparator = that set MINUS attributed removals**, where every
removal records (member, attributed cause, evidence, date) at the
same evidence standard as any attribution on this line — never
"probably fixed by X".  ADDITIONS to the baseline are Fable rulings
only, expected never.  Suite runs always label the CURRENT tree hash
as run metadata; the hash is provenance, not comparator identity.
**Ledger discipline (added with the entry-1 correction):** no entry
— removal or seed — is written without RECONCILING the per-file
counts against the membership claim; an unreconciled entry is the
"probably fixed by X" this scheme forbids, wearing a ledger's
clothes.
**Removal ledger:**
1. `test_layout.py::test_to_osm_is_idempotent` — **VOID 2026-07-31
   (same day): the flake was NEVER a 24F member.**  Verified against
   the pinning run's own breakdown: 9 files summing to 24, zero
   `test_layout.py` entries; P0's 25 reconciles as 24F + flake.  The
   entry was written without the reconciliation now required above;
   under the erroneous 23, a correct 24-failure run would have read
   as a phantom +1 regression (P2's clean 24 nearly was).  Kept
   in-place as the audit trail's own worked example.
   **Live comparator today: 24 members (= the historical set;
   no valid removals yet).**

**THE SINGLE-TREE EVIDENCE RULE (normative, Fable ruling 2026-07-31
after P2-CP1's correction).**  Cross-tree elevation comparisons are
NEVER evidence for a moment ruling: two dumps from different trees
differ by tree drift AND by the variable under test, inseparably.
Measured cost of violating it: the §4.1 moment ruling was first
argued from a Jul-29-dump-vs-Jul-30-finals comparison that put
candidate B 1.79 m BELOW the class; the single-tree instrumented
build puts B 0.77 m ABOVE it — a 2.5 m error with the sign flipped.
A moment/attribution ruling requires single-tree, single-code-version
arms from one artifact (what P3 did; what the first comparison was
not).  Companion rule from P0b: an isolation/flake claim requires a
POWERED sample — "3/3 in isolation" concluded suite-context
dependence that a 2/20 base rate fully explains.

**THE ORDER (revised 2026-07-30, owner answer 5 — an override of this
spec's original phasing):**

    R0 (landed) → U1 (node-space unification FIRST) → R1 (field)
    → S1 (string construction) → R2 (tube) → R3 (band ON + deletions
    + battery) → R4 (forensics) → R6 (build-time review)

The owner: "I would prefer node-space be unified FIRST, anywhere
there's redundancy we're introducing extra work, slow downs, and
mistakes."  U is therefore no longer phase 2: it runs before R1 as
step **U1**, scoped and budgeted in its own spec
(`node-space-unification-spec.md`), and old step R5 (band timestamp
hardening) is ABSORBED into it — a single keyed store gives the band
its pinned construction moment structurally.  S1 is NEW (the §4.3.1
string-construction objective, forced by §1.8 defect A); it must
precede R2 because the tube enforces |z − Z_ref| ≤ ε — enforcing a
tube around a DRAPED string would lock the §1.8 sag in.

**R0 — disposition flip.  STATUS: LANDED (in-tree, `solve.py:686-709`
default "0"); verification outstanding.**  Set `O4_ENVELOPE_FROM_BAND`
default "0" per §1.7 (one line, both arms already hash-proven;
restores seam 108.26, building199 0.49).  Owner ruling §0 confirms the
interim disposition (lawful-but-high over unlawful; §1.7 nuance: R0
does NOT close the seam).
Risk: none (proven identity).
Ladder: (a) only — existing hashes.  **Total cost: 0 builds, minutes.**
**R0-v — DONE (P0, 2026-07-30), and it FALSIFIED the inference:** the
10 airport-build tests fail at the OFF default too (measured twice,
tree `50f45b49d849`).  They are arm-independent tree defects; see the
§1.7 P0 falsification note for the ruling and §5.0 for the 24F
comparator they now live in.

**U1 — node-space unification (owner answer 5; FIRST).  STATUS:
U1a IMPLEMENTED 2026-07-30** (in-tree; identity proven SPLP+CYXY
three-way; 49 unit tests; timing PASS — see
`taut-string-implementation-plan.md` P1 for the evidence table and
the one outstanding acceptance item, the P0 suite).  Own spec:
`docs/specs/node-space-unification-spec.md` — the canonical-point
registry becomes THE node space; one keyed artifact store + one
resolver replace the five bespoke cross-space carries (§3.1(f)); the
band gets its single pinned construction moment (absorbing old R5).
Byte-identity refactor by intent, proven tree-vs-tree by body hash.
The audited phase-1 verdict stands as input (100 % of rod-link loss =
`emit_decimate` deletions, 0 % re-keyed, registry stable — do NOT
re-run the probe).
**Total cost: per its own spec — ~2 SPLP/CYXY identity builds +
1 CYXY timing statement (< 10 min); HECA identity rides R1's first
dev build.  Spent: 6 identity builds + 3 timing runs (~6 min).**

**R1 — the reference field module.**  Build Z_ref once (4.1) and feed
the EXISTING `node_refs`/`group_refs` plumbing from it at all three
call sites; delete the per-pass snapshots.  Gate `O4_REFERENCE_FIELD`.
The field is a U1-store artifact (minted once by canonical key,
resolved through the one resolver) — R1 must not re-introduce a
bespoke carry.  R1 uses TODAY'S string values (phase-A faired) for
layer 4: it stabilises references (kills the §1.3 ratchet), it does
NOT re-derive strings — the seam stays in the ~108.5 class at R1, and
that is correct for this step; the descent to the owner's 103-106
lawful string is S1's job.
Mechanism evidence BEFORE any build: offline replay of fp#8 + finals
against the ALREADY-EXISTING dumps (`/tmp/bandq/heca_band.*.pkl`,
`tools/probes_heca_burial_20260729/heca_spineframe_state.pkl`) showing
the seam node's reference stays in the 108.5 class through all passes
with the envelope band-sourced.  Expected direction: the §1.3 ratchet
class closes.  Risk: a field built too early snapshots a worse state
than fp#8 entry — the replay decides the build moment before any build
is spent.
Ladder: (a) dumps on disk → (b) replay → (c) field-construction unit
tests → (d) HECA dev loop.
**Total cost (corrected by the P2-CP1 deviation, 2026-07-30): the
"no new dump needed" claim was falsified — the on-disk dumps are
mid-projection and carry no rod edges, so the governing layer was
unevaluable offline.  1 authorized instrumented dump build + ≤ 4
dev-loop iterations = 5 HECA builds (~35 min); no flats, no battery
here.**

**S1 — string construction: taut chords (NEW, §4.3.1; forced by §1.8
defect A).**  Re-derive the field's spine layer as maximal straight
chords between clause-1 anchors, bends admitted only with a declared
grade-feasibility witness; the §10 rod then holds the surface to the
taut string.  Gate `O4_TAUT_STRING_CONSTRUCTION` (working name).
Mechanism evidence FIRST (the §1.8 hypothesis): interventional offline
replay attributing what pulls the chord-1 dip down (mask the candidate
puller classes one at a time against the existing dumps; if the dumps
cannot answer it, the S1 dev build doubles as the dump build — say so
in the step report).  Acceptance-in-development: **W-CHORD1** worst-bin
departure strictly improves from −11.07 m; **W-CHORD2** seam pair
lawful (≤ 1.5 %) AND moving toward the owner's 103-106 band;
building199 weld ≤ 0.2 m held; no new law-true violations at HECA
(measured per the §1.8 overcount caveat).
Risk: a taut chord that is genuinely infeasible against an anchor set
mints declared bends — they are REPORTS with witnesses; count and
attribute, never tune away (clause 8).
Ladder: (a)+(b) replay on existing dumps → (c) synthetic
chord-construction unit tests (anchor interpolation, forced-bend
admission, bend-witness format) → (d) HECA dev loop.
**Total cost: 0 new-input builds through (c) if the dumps suffice
(else the first dev build mints the dump); (d) budget 4 HECA
iterations (~25-30 min).**

**R2 — the tube (two flexes off-spine).**  4.4, gate `O4_REF_TUBE`.
Runs AFTER S1 so the tube encloses the TAUT string, not the draped one
(§5 order note).  Mechanism evidence: offline replay showing
seam/corridor/hill sites held in-tube (same existing dumps; if R1/S1
landed a new HECA dump, reuse it — do not mint another).
Acceptance-in-development: **W-CHORD2** (seam pair lawful, values in
the 103-106 class — supersedes the old "seam 106-109" gate, per owner
follow-up 2); building199 ≤ 0.2 m weld; within-shape not worse than
the R0 baseline at HECA; the §1.2 NEW-pair class must not reappear
(re-run `xmatch.py` against the R0 baseline patch — patch analysis,
not a build).
Risk: tube-vs-cap conflicts minting declared conflicts in unexpected
places — they are reports; count them, don't tune them away.
Ladder: (a)+(b) replay → (c) synthetic tube unit test (slab vs cap
contradiction fixture) → (d) HECA dev loop.
**Total cost: 0 new-input builds; (d) budget 4 HECA iterations
(~25-30 min).  Flats deferred to R3's sign-off.**

**R3 — re-enable the band envelope + delete the closure + SIGN-OFF
battery.**  Flip `O4_ENVELOPE_FROM_BAND` default ON *with R1+R2 in
place*; delete #14, #7, #8, #15 per 4.6; broken hold per 4.5.
Mechanism evidence: HECA dev loop until the R2 gates hold with ON, with
`O4_BREAK_FORENSICS` enabled on the LAST development build so R4 needs
no build of its own.  The §1.2 cross-match repeated (script exists)
must show the NEW class ≈ 0 while retaining the healed-10,307 class.
Final acceptance = the ONE battery of this whole line: 4 airports × 2
arms (gate-off identity by body hash) + the HECA pytest battery + the
suite.  Acceptance: all R2 gates + **W-CHORD1 in full (every bin
within ε_taxi of the string, bends declared-and-witnessed, no local
V)** + **W-CHORD2 in full (pair lawful AND in the owner band)** +
total over-cap ≤ the 9,096 class + flats ZERO steps/tears + **suite at
the §5.0 comparator: zero failures outside the 24F set, the healed
members listed, any surviving airport-build member handed to R4 with
its witness** + build-time statement.  Precondition SATISFIED
2026-07-31: P0b closed BY ATTRIBUTION — the flake is the
`o4_provenance_built` wall-clock root-line stamp, which the body-hash
identity protocol excludes by mechanism (plan P0b/P0c; P0c's test fix
lands before the battery as hygiene).
Risk: the blend-t replacement changes SPLP/SPJC mouth-relax break
exports — that is what the sign-off battery is for; it is not a dev
loop.
Ladder: (b) replay of the deletion semantics → (d) HECA dev loop
(budget 4 iterations, ~25-30 min) → (e) battery ONCE.
**Total cost: dev ~30 min + sign-off ~90-110 min.  This is the only
step that runs the battery.**

**R4 — forensic attribution of the residual (no code, no build).**
Read the forensics dump R3's last HECA build already wrote: name every
remaining over-cap pair class per clause 8 (law-web chord that the
visible-geodesic law forbids / anchor value / topology / corridor
priced 1 % where the ruling says 1.5 %).  Deliverable: the defect list
for owner ruling — §3.1(d)'s lawful resolution.  No fix is specified
until this list exists.
**Total cost: 0 builds (input folded into R3), analysis only.**

**R5 — band timestamp hardening.  ABSORBED INTO U1** (owner answer 5
resequencing): the keyed store gives the band exactly one construction
moment structurally, the construction-count unit test moves into U1's
test set, and production resampling deletion is U1 scope.  No separate
step remains.

**R6 — build-time review (owed already, independent of R0-R5).**
Fable-5 whole-pipeline optimisation review per CLAUDE.md item 6,
covering the accumulated stack AND the freed-node sweep cost (§1.6:
phase +5.47 s / total −1.50 s at CYXY).  Note for the review: with
R1+R2 the sweeps start at the field (near-solution) — a plausible
convergence win, to be measured, not assumed.
**Total cost: analysis + `check_build_time --run --runs 3 CYXY`
(~3-5 min); anything beyond that is the reviewer's own budgeted ask.**

**U (phase 2) — SUPERSEDED: answered GO and resequenced FIRST as U1**
(owner answer 5, §0; see the order note at the top of §5 and
`docs/specs/node-space-unification-spec.md`).  The original text
proposed U after R1-R5; the owner overrode the ordering.  What ships
as U1 is the key-native store (every artefact minted once, one
resolver, carries #2/#3/#10/#13 dissolve as bespoke code); making
`final_grade_projection` literally consume one mutating node list
end-to-end (pipeline reorder / identity-preservation plumbing) stays
OUT of U1 — it is U2, future, own spec, owner sign-off, and may be
moot once the store removes the mistake class.

---

## §6 Owner rulings — status after the 2026-07-30 answers (§0)

**Answered:**

1. **R0 disposition** (§1.7): ANSWERED with a nuance.  OFF stands as
   the interim (lawful-but-high ships over unlawful), landed in-tree;
   R0 does NOT close the seam — the seam target is W-CHORD2 (§1.8):
   values in the owner's ~103-106 band AND ≤ 1.5 % pairwise, delivered
   by S1/R2.  R0-v verification run still owed.
2. **ε_role for the off-spine tube** (§4.4): ANSWERED — 0.50 m
   aprons/taxiways, 1.0 m roads, spines keep the ±2 cm construction
   rod.  The acceptance-vs-construction reading is stated normatively
   in §4.4; owner may veto the rod reading if the intent was a 0.50 m
   rod.
5. **Node-space unification** (§5-U): ANSWERED — GO, and resequenced
   FIRST (U1, own spec).  "Anywhere there's redundancy we're
   introducing extra work, slow downs, and mistakes."

**Open:**

3. **Terminal rod runs** (#2 residual): chain-end decimation semantics
   still await ratification (`rod-carry-loss-is-emit-decimation`) —
   but the question is DEFANGED: `O4_ROD_KEEP_CHAIN_ENDS` (landed,
   default ON) force-keeps strung chain-terminal vertices and rod
   drops are 0 at HECA and CYXY with exact ledgers; U1's store makes
   the carry itself dissolve.  Recommended ruling: ratify keep-ends as
   the semantics.  Not blocking any step.
4. **R4's outcome** will present law-web defect classes (§3.1(d)) —
   rulings per class, per `feasibility-is-guaranteed`.  Unchanged.
6. **NEW — W-CHORD1 bend admissions** (§1.8): now CONCRETE after P3.
   The dip is attributed (corridor pegs — S1 Stage 0 dissolves them),
   and the remaining candidate bend author is the band CEILING over
   along 1000-2400 (0.66-5.94 m below the owner's string; latent
   today, binding once the pegs are gone; worth ~5.7 m in the
   masked replay).  Sequence: P3c attributes the ceiling's provenance
   offline (seats/gs-pins masked during band recomputation on P2's
   enriched dump); then the owner rules whether S1's declared
   ceiling-bends stand as lawful bends or the ceiling's law inputs
   are the defect (per `feasibility-is-guaranteed` — the real
   taxiway sits at the owner's 111→113 beside its own runway, so a
   ceiling below it is suspect until attributed).

## §7 Verification artifacts (this review + the 2026-07-30 revision)

* `xmatch.py` / `xmatch.out` — OFF↔ON pair cross-match (scratchpad;
  §1.2 table).  Inputs: `/tmp/HECA_eb{OFF,ON}.osm` + sidecars.
* `seam_probe.py` — seam node per-pass elev/closure/band/broken from
  `/tmp/bandq/heca_band.*.pkl` (§1.3).
* `band_drift.py` — fp#8-time vs final-time band rebuild diff (§1.4).
* `owner_chord_probe.py` (scratchpad; to be promoted to
  `tools/probes_heca_burial_20260729/` with W-CHORD1/W-CHORD2 gates) —
  §0/§1.8 chord geometry, chord-1 station profile + worst-bin
  departure, seam-pair law test, runway z′ ranges.  Inputs:
  `/tmp/HECA_eb{OFF,ON}.osm` + `.axes.json`; **zero builds**.
* Owner KML: `/private/tmp/HECA_seam_site.kml` (dip corridor + seam
  site).
* **Owner ground-truth string map: `/Users/noah/heca_strings.osm`**
  (2026-07-31 — 40 strings, 88 nodes, 37,327 m; chord 1 = ONE
  string, 3,974.8 m, max interior bend 0.00°; 36 clean calibration
  strings ≤ 5.0° interior bend; 4 outliers referred back to the
  owner).  THE settling instrument for segmentation: expected-count
  gate, wrong-merge/wrong-split decomposition, turn-threshold +
  recognition-tolerance calibration set, assembly-fixture re-base
  target, and the negative controls' answer key.
* Pre-existing: `/tmp/envband/probe.out` (seam/building199/corridor),
  `cbt.log` (build time), `*.bodyhash` (gate identity),
  `/tmp/bandq/attrib.out`, `replay_fp8.out` (band replay).

No airport was rebuilt for this review or for the 2026-07-30 revision.
