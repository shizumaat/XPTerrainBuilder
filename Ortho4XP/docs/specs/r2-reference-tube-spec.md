# R2 — the reference tube, off-string flexes enforced (Opus-executable)

Sub-spec of `taut-string-model-spec.md` §4.4 / §5 R2 and
`taut-string-implementation-plan.md` P4.  Fable-authored 2026-07-30.
Deviation rule binds.  ORDER: after R1 (the field exists) AND after
S1 (the field's spine layer is the taut string) — enforcing a tube
around a draped string would lock the §1.8 sag in.

## §1 What R2 adds

§4.4's contract: wherever the field is defined and the node's
hard-neighbour interval admits it, the surface is confined to
**|z − Z_ref| ≤ ε_role**; a node whose tube cannot be reconciled with
its hard neighbours or caps leaves the tube by DECLARED CONFLICT,
never by silent sweep drift.  Cap-lawful sag below the string becomes
unrepresentable.  This is the step that delivers W-CHORD2's owner
band at the seam (the string descends; the fabric may no longer hang
below its reference).

## §2 Mechanism (reuse, not invention)

**The tube is a node-interval constraint, and the solver already has
that channel**: the bounded-yield `node_bounds`/`group_bounds` path
into `feasibility_project`.  R2 composes tube intervals into that
same channel — no new solver machinery:

1. **ε values live in `config.py`** (standards single-source):
   `REF_TUBE_EPSILON_APRON_TAXI_M = 0.50`,
   `REF_TUBE_EPSILON_ROAD_M = 1.0` (owner answer 4; spec §4.4 table).
   Spines are EXEMPT (the §10 rod already binds them tighter);
   groundside is outside the field (clause 7); nodes with no field
   value have no tube.
2. **Derivation at consume time** (single-source; no second artifact):
   at each of the three projection sites, after the field view
   resolves (R1's `view_scalar`), tube(i) = `[ref_i − ε_role(i),
   ref_i + ε_role(i)]` for movable fabric i with a field value,
   where ε_role(i) maps from the node's owning shape-role family
   (apron/taxi fabric vs road) — the role map is a small frozen
   helper in `reference_field.py` beside the field view.
3. **Composition rule (frozen):** tube ∩ existing box, tightest per
   side (`view_interval`-style intersect), EXCEPT where an explicit
   relaxation pass has already WIDENED a side (the mouth-relax
   upper-side relaxation): a relaxed side keeps its relaxed value —
   the relax exists to admit a lawful reconciliation and the tube
   must not un-admit it.  Implementation: compose the tube BEFORE the
   relax pass runs, so the relax's widen lands last.  If the site's
   actual ordering makes that impossible, STOP and report (this is
   the known-fragile point — see §7(ii)).
4. **Declared conflict:** when the projection leaves a pair over-cap
   with an endpoint pinned at a tube face, the existing violated-pair
   export gains a witness class `tube_face` (side + ref value + ε).
   Conflicts are COUNTED and LISTED in the step report — clause 8:
   reports, never tuning.  Broken (band-inverted) nodes hold
   `clamp(Z_ref, hard-neighbour interval)` — under R1 that is already
   the reference hold; R2 does not change broken semantics (that is
   R3's §4.5 consolidation).

## §3 Gate, default

Gate **`O4_REF_TUBE`**, default **"0"** at landing; byte-identity at
"0" by the copied-tree three-way protocol (SPLP + CYXY, sequential —
P0b rule).  Flip to "1" only after checkpoint R2-CP1.

## §4 Acceptance (as tests)

Unit (new `tests/test_ref_tube.py`, synthetic):
1. unconflicted fabric node ends AT its reference (exact-return
   inside the tube);
2. a node dragged by a neighbour beyond ε stops at the tube face and
   the pair exports a `tube_face` witness;
3. mouth-relax interaction: a relax-widened side survives tube
   composition (the §2.3 rule, encoded as a fixture);
4. role mapping: apron/taxi 0.50, road 1.0, spine/groundside/no-field
   exempt;
5. gate OFF ⇒ byte-inert (no tube intervals composed).

HECA (checkpoint R2-CP1, ≤ 4 builds):
* **W-CHORD2 in full**: seam pair ≤ 1.5 % AND both values inside
  103-106 (this step's headline gate — supersedes the retired
  "106-109" class per owner follow-up 2);
* building199 weld ≤ 0.2 m (the tube around the pad-shadow reference
  finally enforces the weld gate);
* within-shape law-true counts not worse than the R0/24F baseline
  values; the §1.2 NEW-pair class must not reappear (`xmatch.py`
  against the R0 baseline patch — patch analysis, not a build);
* W-CHORD1 not worse than S1's result;
* tube-conflict count REPORTED with witnesses (no numeric cap — R4
  attributes them);
* suite comparator: zero failures outside the 24F set.

## §5 Checkpoint

**R2-CP1** — after the first gated HECA arm: the §4 gate table + the
tube-conflict witness list + flats' law-true counts (CYXY/SPJC/SPLP
not worse).  Fable rules on the default flip.

## §6 Build-time statement

One interval per movable fabric node, composed into an existing
channel: O(n) dict work, expected ≪ 0.6 s.  Measure
`check_build_time --run --runs 3 CYXY`; ≥ 0.6 s ⇒ stop, optimization
review.

## §7 EXPECT DIVERGENCE

(i) **Coverage**: today's `node_bounds` channel is populated for
freed seats/pads — R2 widens it to ALL movable fabric with a field
value.  If any site treats `node_bounds` presence as "this node was
seat-freed" (a semantic beyond "clamp me"), report before widening —
that coupling would make the tube change yield behaviour.
(ii) **Mouth-relax ordering** (§2.3): if the relax runs before the
tube composition point at some site, the frozen compose-before-relax
rule cannot hold there — STOP with the site's actual order.
(iii) **Role family mapping**: fabric roles on the global slice may
not partition cleanly into apron/taxi vs road at every shape (mixed
service-adjacent fabric): report unmapped-role counts; unmapped ⇒ no
tube (conservative), never a guessed ε.
(iv) **Group (pad) tubes**: pads are rigid groups with their own
boxes; the pad's reference is its own seat level, so a pad-group tube
is redundant with bounded yield — R2 does NOT add group tubes.  If
measurement shows pads sinking below seat − ε regardless, that is a
report (it would mean the lift-only restore #21 is still load-
bearing), not a group-tube improvisation.
(v) Transient conflict spikes during development are expected where
S1 moved strings far from the old surface; only the §4 gates judge.

## §8 FROZEN / DISCRETION

**FROZEN:** ε names and values in `config.py`; the derive-at-consume
design (no second artifact); the §2.3 composition rule; the
`tube_face` witness class and its fields; gate name/default/flip;
§4 gates and thresholds; the checkpoint; spine/groundside/no-field
exemptions; no group tubes.
**DISCRETION:** the role-map helper's internals; test fixtures;
where in each site's local code the compose lands (subject to §2.3);
report formatting.
