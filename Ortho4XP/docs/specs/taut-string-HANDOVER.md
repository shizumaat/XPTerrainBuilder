# Taut-string line — session handover, 2026-08-01

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
`dcebb6ff…` unchanged; **SPLP BASELINE = `c2316222…` (2026-08-01, final).** Full story, all
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
