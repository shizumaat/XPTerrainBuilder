# Taut-string line — session handover, 2026-07-31

Written for a new session to continue and finish implementing the spec.
**Read this, then the specs it points at. Do not re-derive anything in §2 or §6 —
those cost builds and rounds to establish.**

---

## 1. The delegation model (owner standing rules — do not violate)

* **Fable = design and review ONLY.** It writes ALL specs and approves EVERY
  mid-implementation deviation. It never implements.
* **Opus = implementation and investigation.** Every `Agent` launch passes an
  explicit `model`.
* Canonical text: `Ortho4XP/CLAUDE.md` §"Working style" item 1a.
* **When Fable is unavailable** (it ran out of credit twice this session):
  preserve rulings/questions verbatim in a file marked *not a spec*, author no
  spec text, rule no deviations, tell the owner. Register 24.

## 2. The owner's model — all rulings, do not re-litigate

**What a string IS**
* Strings are **idealized elevation targets**. They **do not exist and are never
  emitted**. They give spines a target of the ideal elevation, knowing grading
  will pull nodes off them; the aim is to achieve the straight profile where the
  law permits.
* *"The strings should BE the existing route network just without the curves and
  intermediate nodes."*
* **Straight trunks, cut at turns.** A turning route becomes several strings.
  Straight in **plan**; bending only in **elevation**, where grade forces it.
* **Follow the spine.** Stop when the spine turns, **leave the curve with no
  string**, and for segments **>100 m** emit a new string along the spine.
  A string that crosses open terrain between two spines is the named defect.
* **Anchors**: CIFP runway thresholds > tile boundary seams > runway crossings,
  then the longest possible straight strings bending only where grade forces it.
* **String ends are a new anchor class**, seated by the route feasibility graph
  then anchored — using **the anchor-governed fabric already there**, not a
  fresh band seat (class ii-b).

**Constants ruled by the owner**
* **±8 m** string-to-spine tolerance (supersedes ±5 m, which superseded a
  calibrated 20 m that was derived from a contaminated population).
* **≥100 m** minimum string length; sub-100 m runs stay in the inventory as
  measurement (selection, not construction).
* apron/taxi acceptance **0.50 m**, roads **1.0 m**; spines keep the 2 cm §10 rod
  (tighter is compliant).
* **APT + OSM union approved** as the string substrate.

**THE GOAL, as most recently stated — this reframes acceptance**
> *"majority coverage for long straight sections so we can smooth them to our
> string which is more faithful to a real airport. We don't need 100% coverage."*

Acceptance is **long-straight coverage**, NOT inventory equality. On measured
data that may already be met: union at ±8 m = **32/46 (70%)**, length-weighted
**95.6%**; the apt.dat turn-cut walk reproduces **12/12** of the owner's
≥1000 m strings and chord 1 whole at 3,990 m vs his 3,979 m.

**Owner ground truth on disk**: `/Users/noah/heca_strings.osm` — 46 hand-drawn
ways, 99 nodes, tracing taxiway centerlines. He drew *almost every* straight run,
skipping only a couple under 100 m.

## 3. Where the work stands

**Landed, gate-off byte-identical, nothing wired to production**
* `elevation_per_surface/node_space.py` — U1 canonical store (`view_scalar`),
  66 tests.
* `elevation_per_surface/reference_field.py` — R1 split-source field
  (layer 4 from the assembly moment, layers 2/3/6 from the A-copy), wired at
  fp#8 + both finals behind `O4_REFERENCE_FIELD` (default `"0"`).
* `route_profile/taut_string.py` — S1 constructor: `assemble_runs` (plane) and
  **`walk_spine_runs`** (spine-walk, direction-symmetric consensus), gate
  `O4_TAUT_STRING_CONSTRUCTION` default `"0"`. **33/34 tests.**
* `grade_graph.py` — ungated `centerline_chains` / `centerline_service` export.
* `tests/test_layout.py` — P0c fixed the `to_osm` idempotency flake.

**Identity hashes** (body only, `tail -n +3`): SPLP `d8d0f065…`, CYXY
`dcebb6ff…`, HECA gate-off `d4f52f02…`.

**Blocked** — see `PENDING-unruled-queue.md`; six items awaiting Fable, chiefly
the R3 substrate commit (its pre-registered gate now passes), the dead
`_collapse_straight_edges` primitive, and S1's fixture premise.

## 4. Disposition of the gates

* `O4_ENVELOPE_FROM_BAND` **stays `"0"`** — owner-confirmed: envON breaks the
  1.5% taxiway law at the seam pair (3.66% vs OFF 1.40%).
* `O4_REFERENCE_FIELD` **stays `"0"`** — CP2 failed four gates; ARM-5 attributed
  building199 to layer 5's **moment** axis (R drifts 1.397 m at the site, p90
  1.898 m over 812 sites), and CYXY's regression to a **spec-conformance defect**
  in §4.1's layer-4 service sub-domain (now fixed: service takes live `elev`).
* `O4_TAUT_STRING_CONSTRUCTION` **stays `"0"`.**

## 5. Budget

Session totals: **5 HECA, 5 CYXY, ~24 SPLP, 1 full suite, 1 law-true run.**
CP2's 4 HECA are spent; **S1 holds 1 of ≤4.**
Live comparator: **24 stable failures** across 9 files, minus an attributed
removal ledger. Tree hash is provenance, not identity.
`O4_TEST_AIRPORTS` alone does NOT scope a run — keep the `[<ICAO>]` node-id
selector or price it as four airports / ~710 s.

## 6. The transformation chain (measured — do not re-derive)

apt.dat 1201/1202 → `taxi_centerlines` → **151 routes / 196 pieces, −2 vertices,
−0.1 m of 46,142.9 m** (161 of 196 pieces are already 2-point straights) →
**snapshot at `pipeline.py:2253`** → … → **`route_arcs.apply_route_arc_spine`
turns 151 polylines into 653 ways and sets `route_line=None`** → densification →
`_build_global_spine` (admission at `SPINE_PERP_TOL_M = 1.0`).

* **`route_arcs.py:564` `route_line=None` is one line explaining two mysteries**:
  `RouteChain` being 1:1, and "36 authored fragments tile chord 1"
  (`centerline_chains` is keyed by route-arc way, not apt.dat route).
* **89.3% of the 7,126 spine nodes sit within 5 m of the apt.dat source** — the
  chain **preserves position and multiplies count** (366 → 7,126 nodes, 19.5×).
* **A dead branch misleads the logs**: the snapshot precedes discovery at
  `:2540`, so 595 discovered centerlines and five of eight log lines change
  nothing.
* `_build_global_spine:1958` drops `len(on_line) < 2` **silently**.
* **`spine_synthesis._collapse_straight_edges:812`** (2.5 m chord collapse) is
  **exactly the owner's primitive and is dead code**.
* Added geometry violates ±8 m: `_add_junction_arcs` fillets ~15 m,
  `_add_runway_turns` blends 120-550 m radius, in no source line.

## 7. Method lessons that cost real time (the registers)

1. **Mechanism before fix** — nine mechanisms falsified in two days. Interventional
   evidence, or say "the data cannot attribute this."
2. **Intent questions route to the owner** — his sentences twice replaced a build
   plus rounds. Ask for artifacts; he supplies them.
3. **A margin is only as valid as its population** — five instances, one of which
   reached a *shipped constant* (the 20 m margin, calibrated over spine holes).
   Name the population before any distribution becomes a tolerance.
4. **Aggregates cancel** — 32 unmatched-ours vs 16 unmatched-his partially
   cancelled in a bare count. Decompose before diagnosing.
5. **Synthetic fixtures test intent; real-geometry fixtures test mechanism** —
   and a real-geometry fixture must **preserve the competition**, not just the
   geometry. A mechanism fixture carries its own negative control.
6. **Proxy gates fail** — count proxies, heading proxies, phase-1 endpoint
   sharing. Gate on the measured property, not a stand-in.
7. **Warning comments are load-bearing spec** — a lost ★ comment cost the CYXY
   service defect; harvest them during absorption/deletion.
8. **Two-site arms decompose bundles** — a 38 s CYXY arm alongside a 398 s HECA
   arm turned one heal into a three-owner attribution.
9. **Analysis joins key by site, never index** — an index join silently returned
   `n/a` and nearly inverted a decomposition.
10. **Builds are globally exclusive**; arm waiters on the exact PID with a
    `kill -0` re-verify **inside the same command as the build** — a clear is only
    valid at the instant of launch.

## 8. What the next session should do

1. **Get Fable to restate acceptance in the owner's terms** (long-straight
   coverage, not inventory equality) — several open items may close outright.
2. **Clear `PENDING-unruled-queue.md`** — R3 substrate commit first; it unblocks
   the rest.
3. **Unblock S1's fixture premise**, then S1-06.
4. Then: stage-1 re-acceptance against the map, arm 3 (S1's last HECA),
   the §6.4 owner filing (≥159 surfaced contradictions + P3c + class D),
   S1b, R2-CP1, R3-CP1/2/3.

**Live agents at handover** — resumable by name/id if the harness carries them:
Fable design lead; S1 constructor (held on the fixture premise); P7 investigator
(step 0 and code-read complete). A background task
*"Fix dead centerline-discovery branch and silent spine drops"* runs
independently and overlaps §6 — coordinate, do not duplicate.
