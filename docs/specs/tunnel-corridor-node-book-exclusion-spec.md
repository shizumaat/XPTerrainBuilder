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
