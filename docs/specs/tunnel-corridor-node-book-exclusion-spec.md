# Tunnel-corridor exclusion from the unified node book (Fable spec,
# 2026-08-25; owner-ordered fix for the OTHH tunnel regression)

Attribution (interventional, single-variable, same-tree — the 2026-08-25
OTHH site investigation): `cce9da6f` added `ROLE_SERVICE_ROAD` +
`ROLE_SERVICE_JUNCTION` to `_CHORD_LIMIT_ROLES`, putting road rings in ONE
node key space with `ROLE_GROUNDSIDE_PAVEMENT` in the finalize-stage
Lipschitz clamp, where the road's value wins at a weld. At OTHH's site-1
bore (25.27158, 51.60244) the descending tunnel floor is a
`groundside_pavement` ring: it gained 17 shared nodes across six road
rings (GOOD: zero), took `tunnel_road` bench values (+2.28/+2.96 against a
−1.1 floor — a 3.3 m mid-ramp step), and 9 of the bore's 10
`authority_retreat_wall` faces stopped being emitted. Reverting the role
set restores everything — but the limiter joined the roles for a reason,
so the fix is scope, not revert.

## The design (fix by AUTHORITY, not by role)

1. The thing the clamp must not capture is defined by authority: a ring
   carrying a tunnel bore's below-grade geometry is owned by the portal
   walk, whatever its role. The role exemption (`tunnel_ramp`) is the
   wrong axis — this bore's floor is `groundside_pavement`.
2. THE EXCLUSION: any ring with nodes inside the TUNNEL OPEN-CUT CLAIM
   SET — the same claim computation R14-1 already performs when it logs
   "claimed N road surface(s) as the tunnel corridor" (one authority,
   never a second geometric notion of "inside the cut") — is excluded
   from the unified node book entirely: it keeps its own solved values
   and contributes no keys to the shared space. Exclusion is per RING
   (membership = any node inside the claim), so a partner way cannot
   import a value across the cut boundary through a shared key.
3. `authority_retreat_wall` emission must be verified downstream of the
   exclusion: the faces are derived from the retreating below-grade
   geometry, and the acceptance requires every GOOD face back.
4. The limiter keeps its full role set everywhere else — its road/lot
   purpose is untouched; its twin's "`tunnel_ramp` untouched" assertion
   is extended to assert the claim-set exclusion (a below-grade
   groundside ring inside a cut keeps its values).
5. Flag `O4_TUNNEL_CORRIDOR_NODE_BOOK_EXCLUSION`, default ON; OFF =
   today's (broken) behaviour, byte-identical, for attribution arms.

## Twins

(a) Synthetic: a groundside ring inside a tunnel claim welded to a road
    ring — with the exclusion ON the ring's below-grade values survive
    the clamp and no shared key is minted; OFF reproduces the capture.
(b) A road ring OUTSIDE any claim still takes the limiter's precedence
    (the cce9da6f purpose, unregressed).
(c) Retreat-wall derivation: given the restored ramp, the retreat faces
    emit (unit-level, synthetic bore).
(d) Flag off → byte-identical to today.

## Acceptance (one OTHH build, from the lane's Ortho4XP/)

- Site-1 ramp profile at the investigation's stations within 0.1 m of
  the GOOD Aug-14 values (−1.10/−1.10/−0.93/−1.09/−1.09/−1.06/−1.10/
  −0.79); the three bench nodes gone; the 21 site movers back to GOOD
  ±0.01 m.
- `authority_retreat_wall`: ALL TEN of GOOD's faces present at the bore
  (ids may differ; match by location/extent). Extra faces beyond the ten
  (the arm-C 13-vs-10 question) are REPORTED with locations, not
  iterated on — the owner ratifies them on the sim pass.
- `tunnel_portal_acceptance.py --control`: subgrade_by_role restored to
  GOOD (service_junction 7→2, service_road 5→3 expected direction).
- All other tunnel families byte-stable vs the broken arm except the
  restored site (the investigation's family table is the reference).
- The limiter's own existing tests pass unmodified except the extended
  twin (§4). Sites 2 and 3 from the investigation are PRE-EXISTING and
  out of scope — do not touch them.
- Attempt cap 2, materiality 0.01 m, STOP-and-report on a second miss.
  No shared-repo writes, no timing claims.

## Amendment 1 (Fable, 2026-08-25 — after attempt 1's STOP; supersedes §2's
## per-RING clause)

Measured defect of the per-ring rule (attempt 1, OTHH ring `-12221`): a
ring carrying BOTH the bore floor and lot area outside the cut was
excluded whole, stripping lawful chord limiting from its non-bore half
(0.6-1.0 m off GOOD; 4 retreat faces lost; the 21-mover residual).

1. GRANULARITY IS PER NODE, SCOPED TO KEY-MINTING: a node inside the
   open-cut claim set mints NO shared key and accepts NO cross-ring
   import; nodes outside the claim participate exactly as today. Rings
   are NOT removed from the clamp — within-ring limiting continues for
   every ring, in-cut nodes included (GOOD's own regime: the pre-cce9da6f
   pass limited the bore ring as pure groundside with zero cross-ring
   welds, and read correctly). The defect was only ever the cross-role
   SHARED keys.
2. Acceptance amendments: (a) `subgrade_by_role` is judged ARM-RELATIVE
   on this tree — not worse than the role-set revert arm (which reads
   9/6 here); the 2/3 figure was Aug-14-tree provenance and is retired
   as a bar. (b) Retreat-wall target stays ALL TEN of GOOD's faces by
   footprint coverage; extras still reported, not iterated.
3. This amendment is a Fable-adjudicated design change: the attempt
   count RESETS — the implementer runs the amended design as attempt 1
   of 2 under this section.

## Amendment 2 (Fable, 2026-08-25 — after Amendment 1's measured
## refutation; supersedes both prior granularity rules)

The measured mechanism ledger (do not retry): per-RING exclusion gives a
perfect bore floor but strips lawful limiting from a boundary-spanning
ring's lot half (v1: walls 5/10, lot worst 1.03). Per-NODE private keys
close the direct weld channel but leave the TWO-STEP path open — road
value → the same ring's out-of-cut shared welds (road precedence, by
cce9da6f's design) → the ring's own chord law → the bore floor (v2:
bore recaptured, walls 2/10). The role-set revert arm reads near-GOOD at
the site (stations ≤0.13, walls 9/10, adjudicated +17) but surrenders
the limiter's purpose airport-wide.

1. THE RULE: a CLAIM-TOUCHING RING IS ROAD-PRECEDENCE-EXEMPT. A ring
   with any node inside the open-cut claim set participates in the node
   book exactly as pre-cce9da6f groundside: it mints and consumes shared
   keys normally, stays fully in the clamp, but ROAD-ROLE VALUES DO NOT
   WIN at any of its welds (neither on the bore half nor the lot half —
   the lot-half weld is the two-step carrier's entry). Rings not
   touching a claim keep cce9da6f's full precedence — the limiter's
   road/lot purpose is untouched everywhere else.
2. Reuse attempt 1's ring predicate (`_ring_touches_tunnel_claim`,
   4e0a7e3c) verbatim; the change point is the precedence decision at
   the weld, not key-minting and not clamp membership. The v2 private-
   key machinery is retired (keep the twins' census helpers if useful).
3. Expected read = the revert arm AT TUNNEL SITES with the limiter
   intact elsewhere. Acceptance: site-1 stations within 0.15 m of GOOD;
   retreat walls ≥ 9/10 by footprint (a 10th shortfall attributed and
   reported, not iterated); movers reported against the revert arm's
   envelope; subgrade_by_role arm-relative (not worse than revert 9/6);
   adjudicated delta reported vs revert's +17; tunnel families and
   airside byte-stable as before; limiter's own tests pass.
4. Attempt count resets under this section, cap 2. If THIS design
   misses, there is no fourth design from the lane or the lead: the
   options ledger goes to the owner.

## Owner disposition (2026-08-25)

v1 (per-RING exclusion, 4e0a7e3c) ACCEPTED for the sim bundle — ramp
floor exact, walls 7/10, adjudicated +30. Amendments 1 and 2 are
measured-refuted mechanisms (lane/tunnelfix d83379a8, b9ef30c9 — kept
unmerged as the ledger). Option A (claim-scoped ROLE exclusion: road
rings touching a claim leave `_CHORD_LIMIT_ROLES` for the pass) is the
queued next design, owner-gated; finding 2 (a retreat face and a shared
key are mutually exclusive) is the structural constraint any future
design must satisfy.

## Amendment 3 (Fable, 2026-08-25 — OPTION A, owner-ordered: "fix
## tunnels so LEMD and OTHH can build cleanly"; supersedes v1's
## per-ring exclusion)

Finding 2 (structural, measured): a retreat face and a shared key are
mutually exclusive — the faces exist only where claimants disagree, so
the ROAD family must leave the shared key space at tunnel sites, which
is exactly the revert arm's regime (site read: stations ≤0.13, walls
9/10, adjudicated +17) scoped so the limiter keeps every road
elsewhere.

1. THE RULE: a ROAD-ROLE ring (service_road / service_junction) that
   touches the tunnel open-cut claim set leaves `_CHORD_LIMIT_ROLES`
   for the pass — it neither mints nor consumes shared keys and is not
   clamped by the pass; groundside_pavement rings STAY in the pass
   everywhere (their v1 exclusion retires — v1's lot-half defect).
   Non-claim road rings keep cce9da6f's full behaviour.
2. Predicate: attempt 1's `_ring_touches_tunnel_claim` verbatim, over
   the same published claim set. The v1 per-ring exclusion and the v2/
   v3 machinery are all superseded — ONE mechanism after this lands.
3. Flag: reuse `O4_TUNNEL_CORRIDOR_NODE_BOOK_EXCLUSION` (default ON) as
   the gate for THIS rule; OFF = pre-round (cce9da6f full) behaviour.
4. Twins: rework to the role-scoped shape — (a) claim-touching road
   ring unclamped/unkeyed, its groundside partner still clamped by its
   own law; (b) non-claim road ring keeps limiter+precedence; (c)
   retreat faces emit; (d) OFF = pre-round.
5. Acceptance (ONE OTHH build): site-1 stations within 0.15 m of GOOD;
   retreat walls ≥9/10 by footprint (shortfall attributed, reported);
   movers vs the revert envelope; subgrade arm-relative ≤ revert 9/6;
   adjudicated delta vs revert's +17; tunnel families/airside
   byte-stable; limiter's own tests pass. Attempt cap 2; a miss goes
   to the owner with the ledger.
