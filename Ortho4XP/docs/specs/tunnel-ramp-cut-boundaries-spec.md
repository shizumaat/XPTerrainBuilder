# Tunnel ramp-cut boundaries — spec (2026-08-07, v2 FROZEN)

Author: lead session (Fable). Status: **FROZEN for implementation**
(v1's DRAFT sections resolved by the attribution trace).

Rulings: `docs/RULINGS.md` "2026-08-07 — Ramp-cut boundaries: walls,
grades, buildings". Parent: `tunnel-portal-fidelity-spec.md` (landed,
uncommitted, in the working tree). A/B artifacts:
`/tmp/harness/OTHH_matched_ctl.osm` (control) vs
`/tmp/harness/tunnel-fidelity.osm` (parent fix), sidecars beside both.

## 1. What the trace established (do not re-derive)

* The +665 adjudicated rows: 86-100 % of the step-family rows sit at
  ramp-cut edges; the cut edges ARE walled (`authority_retreat_wall`
  5 → 63, 58/63 within 5 m of a ramp ring) but the step/within
  families consult no third shape, so no wall can bless them
  (`tools/check_grade.py:4253/4359`; wall predicates live only inside
  `_check_strip_seam_tears`).
* The dominant minting mechanism is NOT missing walls but CROSS-
  BOUNDARY VALUE ADOPTION: ruling 4 removed the 0.6 m graze push, so
  new ramp corners land inside solved pavement vertices' 0.5 m intern
  buckets (`SHARED_VERTEX_TOL_M`) and the authority precedence welds
  values across what is physically a wall: building pad `-10001` ring
  dragged to −3.74; 148 ways byte-identical in geometry with drifted
  altitudes (93 apron, 31 junction, 26 building, 16 service_junction);
  the worst grade row (`-11816`, 40.4 %) is a fork-throat corner that
  interned onto junction node `-1498` (3.60 vs the throat's 1.30).
* The 25 over-cap `tunnel_ramp` rows split: 14 shared-corner adoption,
  9 on-edge weld-insert spikes (donor value kept, `layout.py:1982`
  class), 2 genuine pre-existing on `-11325` (`object_bridge_ramp` —
  OUT OF SCOPE, different emitter, note only).
* Two role-less `shape_interior_ring` ways (`-12315`/`-12316` — the
  ramp cut's holes) fall through to airside defaults (1.0 m / 1.5 %)
  and mint 78 step + 9 within rows; `check_grade`'s judged-at-host-cap
  clause is deliberately unimplemented and is now load-bearing.
* `tunnel_wall` 9 → 4 is relabelling (WALL-vs-RAMP clip vs a much
  larger ramp union), not loss.

## 2. W/G-1 — Clearance cut + the tunnel walls its own annulus

The geometric fix that removes the minting vector instead of blessing
its output. In `bridges.py`'s ruling-4 machinery:

* **The pavement cut widens to a clearance annulus.** The ruling-4 cut
  footprint becomes `ramp_union.buffer(wall_gap_m +
  retaining_wall_width_m, join_style=2)` (= the existing 0.6 + 1.0
  perimeter-band geometry) instead of the bare `ramp_union`, so no
  remaining pavement vertex can sit within `SHARED_VERTEX_TOL_M` of a
  ramp ring and cross-boundary interning is geometrically impossible.
* **The tunnel perimeter wall band owns the annulus.** The existing
  continuous-perimeter-wall machinery (the `TUNNEL_FORK_THROAT` band,
  ≈`bridges.py:3117` in the parent tree) emits the 1 m
  `ref='tunnel_wall'` band around the ramp union, DEM/edge-following
  as today; it must not be clipped away against pavement its own cut
  removed (it is judged against the post-cut union already — verify).
  Result: every cut edge reads pavement | wall | ramp, and both
  adjacent pairs carry a `retaining_wall`-family member whose cap is
  `None` — the step rows never mint. The `authority_retreat_wall`
  improvisation at these edges should stop firing on its own (no
  shared canonical points, no authority collision); if retreat walls
  still appear beside ramps at acceptance, report — do not suppress
  them by hand.
* **Ramp-internal corner agreement.** Adjacent ramp pieces of one
  portal walk (chain quads, fork arms, the fork throat) must present
  ONE value at each shared cross-edge node before `to_osm` shape-order
  precedence picks a winner (`-11759`/`-11758` disagreed by 0.96 m;
  the throat's flat landing must join the arm profile at the shared
  edge). Fix at the emitters (`_emit_chain` / `_emit_fork_throat` /
  cluster assembly) — the planned profile is piecewise-linear and the
  correct shared value is well-defined.
* **Weld-splice spikes:** `layout.py`'s valued-node splice is OUT OF
  SCOPE for this round (global machinery, high blast radius). The
  clearance annulus removes the cross-boundary donors observed
  (`-27009` etc. sat on cut-edge geometry). If over-cap rows from
  splices survive at acceptance, STOP and report.
* Buildings participate in the annulus exactly like other pavement is
  cut — EXCEPT they are never cut (§4): where the annulus would enter
  a building pad, the RAMP (and its band) stop at the pad edge per §4
  and the pad ring is left untouched.

## 3. L-1 — Interior rings judged at their host's frame

`tools/check_grade.py` host resolution (`run_checks`, ≈:1068/:1145):
a role-less `shape_interior_ring` way is judged at its HOST shape's
role/cap (the host is the shape whose polygon carries the ring), not
at airside defaults. This is harness-library law: register the change
where the family twins live and extend
`Ortho4XP/tests/test_harness.py` so the CLI, census and pytest paths
stay one code path (a ring-host unit case + the twin assertion).
NO step-family wall exemption is added this round — §2 removes the
need; if acceptance shows a residual wall-hosted class, STOP and
report with the rows.

## 4. B-1 — A ramp never crosses a building pad edge  [unchanged from v1]

Owner (verbatim): "A ramp should never cross a building pad edge.
Either the tunnel is under the building and the ramp stops at the
building edge, or the building is mis-identified and shouldn't be
there in the first place."

* `ROLE_BUILDING` stays OUT of the ramp cut set and OUT of
  `_RAMP_NEVER_CUT_ROLES` (runway floor DROPS; buildings CLIP).
* Every new `tunnel_ramp` piece is clipped against the union of
  `ROLE_BUILDING` pads buffered by `_TUNNEL_GRAZE_CLEARANCE_M`; the
  overlap is covered bore, not emitted; a piece left empty drops with
  a `vprint(1)` naming the way id and pad shapeID. Altitude semantics
  reuse the existing graze-clip conversion — a clipped ramp keeps its
  profile, never stretches it (assert in tests).
* The ramp's end face at a building edge is part of the §2 wall
  perimeter (portal face at the building edge).

## 5. Non-goals

No OSM/data changes; no object-classifier changes; runway safety floor
unchanged; `layout.py` weld machinery untouched; `-11325`
(`object_bridge_ramp`, 4.68 %) untouched — pre-existing, different
emitter, noted for a later round.

## 6. Acceptance — ONE OTHH build + matched census vs `OTHH_matched_ctl.osm`

1. Unit tests (synthetic, `tests/test_tunnel_portal_fidelity.py`
   conventions): annulus clearance (no pavement vertex within 0.5 m of
   a ramp ring), band presence around a cut, ramp-internal shared-edge
   agreement, building clip incl. full-drop log, ring-host law twin.
2. Suite through the ledger (blast.py-named + both tunnel test files).
3. Build `--tag ramp-boundaries`; assert:
   * parent spec §4.3 bullets ALL still pass (mouth at D ≤ 15 m;
     B-site ramps ≤ 60 m at A/B1/B2/B3; zero below-grade in covered
     bore spans; no `tunnel_low_connector`; no needle);
   * `building1` (control way `-10001`) ring flat at 2.34; sub-grade
     nodes by role: building 0, service_junction 0, service_road 0,
     junction 0, apron ≤ control's 9;
   * ways byte-identical in geometry to control with changed
     altitudes: ≤ 10 (was 148), each named in the report;
   * over-cap `within_shape` rows on `tunnel_ramp`: ≤ 2 (the -11325
     pair) — the 23 new-mechanism rows gone;
   * role-less-ring minted rows (`<none>|junction` steps + ring
     within_shape): 0 under L-1;
   * matched ADJUDICATED delta vs control ≤ +50 (was +665); every
     residual NEW row above the materiality floor classified in the
     report (family, roles, wall-hosted or not);
   * `authority_retreat_wall` count within 2 m of a `tunnel_ramp`
     ring: ≤ 5 (was 49) — else report.
4. Census both arms with `tools/harness/census.py` only.
5. Build-time impact statement (tripwire only).

## 7. Convergence guards

Materiality 0.01 m / 0.01 pp (lateral_contiguity's 0.04 m rows are
sub-floor — never iterate on them); attempt cap 2 then
STOP-and-report; `.progress` heartbeat. Honest budget: 1 OTHH build
(~8 min) + census (~2 min) + suite (~8 min).
