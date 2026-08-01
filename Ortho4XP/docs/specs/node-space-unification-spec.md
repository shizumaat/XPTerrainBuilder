# Node-space unification (U1) — one registry, one keyed store, one resolver

Step U1 of the taut-string consolidation (`taut-string-model-spec.md`
§5; run order R0 → **U1** → R1 → S1 → R2 → R3).  2026-07-30.

**STATUS 2026-07-30: U1a IMPLEMENTED AND ACCEPTED.**  `node_space.py`
+ the four simple families migrated; 49 unit tests green; three-way
byte-identity proven (SPLP `d8d0f065…`, CYXY `dcebb6ff…`; pre = post =
pre-again); `check_build_time` PASS (CYXY 35.97 s median).  The final
acceptance item closed 2026-07-30: P0's two independent full-suite
runs (tree `50f45b49d849`) both pass `test_node_space.py` (49) with
zero failures outside the confirmed 24F comparator (taut-string spec
§5.0).  The rod EDGE family is U1b, deferred to ride R1 (§3.1).

**Determinism yellow flag — CLOSED 2026-07-31 (P0b attribution).**
The `test_to_osm_is_idempotent` flake is the `o4_provenance_built`
wall-clock stamp in the OSM ROOT line vs a full-text compare (~5-10 %
per-execution base rate; geometry byte-identical in every captured
failure; clock frozen ⇒ 0/100).  **U1's identity proof stands BY
MECHANISM, not just protocol**: the nondeterminism lives entirely in
the line the body hash (`tail -n +3`) excludes — the very stamp that
is why `patch-ab-integrity` mandates body hashing.  The earlier
"suite-context dependent (3/3 isolated)" reading was an
underpowered-sample error, corrected in the plan.  Residue: plan P0c
(test fix) + the R6-carried question of wall-clock time in emitted
output.  The protocol rule survives: full-file suite-context hashes
are never identity evidence.

## §1 Mandate and provenance

Owner answer 5 (2026-07-30, verbatim):

> If possible I would prefer node-space be unified FIRST, anywhere
> there's redundancy we're introducing extra work, slow downs, and
> mistakes.

This overrides the taut-string spec's original phasing (U was phase 2,
after R1-R5) and the single-space audit's "phase 2 after owner
sign-off" hold — the sign-off is this answer.  Old taut-string step R5
(band timestamp hardening) is ABSORBED here: a single keyed store gives
the band exactly one construction moment structurally.

**Input verdict (audited, phase 1 complete — do NOT re-run the
probe):** 100 % of dropped rod links were strung vertices DELETED by
`emit_decimate` (0 % re-keyed, 0 % service-corridor, canonical registry
stable); the exact fix — composing links across removed runs — is
LANDED (`O4_ROD_COMPOSE`, `O4_ROD_KEEP_CHAIN_ENDS`, both default ON;
rod drops now 0 at HECA and CYXY, ledgers exact).  Consequence for U1:
the canonical-point registry (`layout.canonical_points`) is PROVEN
stable across every post-solve pass — it already IS the single node
identity.  What is not single is the ARTIFACT TRANSPORT layered on top
of it.

## §2 The redundancy, measured (HEAD+dirty 2026-07-30 line cites)

Both the solve and `final_grade_projection` build their node lists from
the SAME registry (`solver_primitives._build_node_list` →
`canonical_points.get_or_add`), yet every cross-pass artifact has its
own bespoke stash-on-layout + resolve-in-pass + crown-lift code:

| # | artifact | mint / stash | resolve sites | bespoke code |
|---|---|---|---|---|
| 1 | bounded-yield seat boxes | `layout._seat_boxes` (anchors) | fp#8 `solve.py:1360-1390`; final `solve.py:3817-3844` | two index-map + crown-lift blocks |
| 2 | reach band, broken-only slice | `layout._apron_band_keys` `solve.py:2381-2390` | honesty ladder `solve.py:3934-3941` | its own key export + crown lift |
| 3 | reach band, full (envelope) | `layout._env_band_keys` `solve.py:2406-2411` | final envelope `solve.py:4083-4084` | second export of the SAME band |
| 4 | pad-face weld shadow | `layout._pad_weld_refs` | fp#8 `solve.py:1456-1486`-area; final `solve.py:3876-3894` | contact→pad resolution twice |
| 5 | §10 rod slabs | rod registration + `_carry_rod…` compose | final `_rod_fp_edges` | edge (two-key) carry + compose across decimated runs |
| 6 | R spine-crossing identity | `layout._apron_spine_keys` | final `solve.py:3906-3908` | key-set export |
| 7 | scoped-projection snapshot | `_capture_projection_snapshot` `solve.py:2370-2373` | `_scoped_projection_defer_ids` | key-set export |

Each carry has its own loss mode (the rod-key lesson cost a full audit
round), its own crown handling, and its own coverage rules.  That is
the "extra work, slow downs, and mistakes" the owner names.  Worse,
two of the mechanisms are not carries at all but REBUILDS —
`z_ref` re-snapshotted per pass (`solve.py:1404-1406`, `:3851-3852`,
`:3864`) and R re-derived per pass — which is the §1.3 ratchet; those
are R1's scope, but they can only be fixed cleanly on top of a single
store (the field must be MINTED ONCE and RESOLVED anywhere).

## §3 Design (normative)

### 3.1 The store

New module `src/auto_patch/elevation_per_surface/node_space.py`:

* **Key = canonical-point ID** from `layout.canonical_points` — the
  audited-stable identity.  Nothing keys by rounded coordinate.
* **`NodeSpaceStore`** attached to the layout (one per build).  Typed
  artifact families, minted ONCE each:
  - `scalar(name)` — per-node values (future: the R1 field);
  - `interval(name)` — per-node `[lo, hi]` (seat boxes, band);
  - `edge(name)` — per-link slabs (rod).  **Deferred to U1b (rides
    R1):** the rod's compose-across-removed-runs implementation is
    landed, audited ledger-exact, and has zero redundancy with the
    other carries — migrating its internals is risk without payoff at
    this step.  U1a ships the four simple families below; the edge
    family adopts the store when R1 rewires the same code region;
  - `keyset(name)` — identity sets (spine crossings, snapshot keys,
    pad-weld contact→pad mapping as a keyed relation).
* **One resolver**: `store.view(name, b2i, crown_of=None, keys=None)`
  returns the per-space index-keyed dict a pass consumes; crown lift
  happens HERE, once, identically for every artifact (the boxes' and
  band's current per-site lift blocks collapse into it).  `keys=`
  scopes a view to a subset (see coverage, §3.2).
* Minting twice under one name raises; a unit test asserts the band is
  constructed exactly once per build (old R5's test, absorbed).

### 3.2 Byte-identity constraint (the law of this step)

U1 is a **pure transport refactor**: every consumer must read exactly
the values AND the coverage it reads today.

* The band is stored ONCE (full coverage, the `solve.py:682` sample —
  its pinned construction moment).  The honesty ladder's view is
  scoped to the broken-key subset (`keys=` filter reproducing
  `_apron_band_keys`'s coverage exactly); the envelope's view is the
  full set gated by `O4_ENVELOPE_FROM_BAND` exactly as today.  "Build
  once, filter per consumer" — coverage differences are VIEW filters,
  never second builds.
* Gate semantics unchanged: every `O4_*` env read stays where it is.
* The rod edge artifact keeps its compose + keep-chain-ends behavior
  bit-for-bit (ledger-exact today; the ledger check re-run is part of
  acceptance).
* No consumer changes its arithmetic; diffs are mechanical
  (stash/resolve code replaced by store calls).

### 3.3 Explicitly OUT of scope (U2 — future, own spec, owner sign-off)

* Deleting the second `_build_node_list` / making
  `final_grade_projection` consume one mutating node list end-to-end.
* Any pipeline reorder or identity-preservation plumbing in the emit
  passes.
* Any semantic change to references, R, the envelope, or the rod.
  (Those are R1/S1/R2, and they land ON the store.)

With the store in place U2's residual value is performance only (skip
the second context build); it may prove moot — that call is R6's
whole-pipeline review, not U1.

## §4 Gating — a deliberate deviation, stated

U1 ships GATELESS, like old R5 ("byte-identity refactor by intent").
The every-step-a-gate rule exists to make behavior changes reversible;
U1's contract is NO behavior change, proven by body hash tree-vs-tree
— a runtime gate would mean maintaining the five bespoke carries as a
parallel path, exactly the redundancy the owner ordered removed.  If
any consumer migration turns out NON-mechanical during implementation,
that consumer keeps a short-lived `O4_NODE_SPACE_STORE` escape hatch
and the step report says so; the hatch is deleted at R3's battery.

## §5 Ladder and honest budget

Per `taut-string-model-spec.md` §5.0; airport builds are the scarce
resource.

* **(c) unit tests** (new `tests/test_node_space.py`): mint/resolve
  round-trip; double-mint raises; crown-lift equivalence vs a
  hand-lifted dict; coverage filters (broken-only view ≡ today's
  `_apron_band_keys` construction on a synthetic layout); band
  single-construction assert; edge-compose service parity on the
  synthetic rod fixture.  Cost: seconds.
* **(d) byte-identity** on the two CHEAPEST airports: SPLP + CYXY
  body-hash pairs (`tail -n +3 | sha256`), pre-tree vs post-tree,
  copied `src/` trees, never the shared one mutated mid-proof
  (`patch-ab-integrity`; cold-cache first build of a session is not a
  baseline).  Cost: 2×(SPLP ~10-12 s + CYXY ~35-45 s) ≈ **2 min**.
  HECA identity is NOT minted for U1 alone — it rides R1's first dev
  build (compare that build's gate-off hash against the R0 baseline).
* **Build-time statement**: `tools/check_build_time.py --run --runs 3`
  (CYXY) once, after identity passes — expected neutral (store reads
  replace five dict builds); the statement reports the measured delta
  either way.  Cost: ~3×45 s ≈ **2-3 min**.
* **Blast-radius tests**: the `blast.py` sets for `solve.py`,
  `one_solve.py`, `apron_reference.py`, `emit_decimate.py`,
  `raster_reach_band.py` (includes the rod-compose and reach-band
  suites).  Cost: minutes, via the run ledger.

**Honest total: ~4 airport builds' wall (≈ 2 min) + one 3-run timing
(≈ 3 min) + test wall.  No HECA build.  No battery (that is R3's).**

## §6 Acceptance

1. SPLP + CYXY body hashes identical pre/post (and CYXY hash equal
   under `O4_ROD_CARRY_AUDIT=1` off/on spot-check if touched).
2. `test_node_space.py` green; blast-radius suites green at their
   pre-step baseline (pre-existing failures recorded, not absorbed).
3. The seven §2 stash/resolve sites read through the store; grep gate:
   no `layout._env_band_keys` / `_apron_band_keys` / `_seat_boxes` /
   `_pad_weld_refs` / `_apron_spine_keys` ad-hoc stash remains outside
   `node_space.py` (mint sites migrate too).
4. Build-time statement recorded (delta vs same-session baseline runs).
5. Rod ledger re-check: carried/dropped counts unchanged (0 drops at
   CYXY).

## §7 Ruling 3 note (terminal rod runs)

The open "chain-end decimation semantics" ruling is DEFANGED by this
step: with artifacts key-native in one store, there is no transport to
lose links in, and `O4_ROD_KEEP_CHAIN_ENDS` (landed, drops 0, ledgers
exact) already preserves the chain-terminal vertices.  Recommended
ruling for the owner: ratify keep-ends as the permanent semantics; U1
does not block on it.
