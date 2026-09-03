# Tunnel wall crest = DEM, all the way round the ramp (owner 2026-09-03)

Owner sim read of 1.0.275 (+25+051, OTHH, patch stamped 2026-09-03 13:56):

> "The wall should stay at DEM all the way around the tunnel ramp
> allowing the tunnel to descend to its full depth. 25.2715296,
> 51.6022683 (tunnel wall node, at tunnel mouth) should be 5.1 m (based
> on tunnel/bridge depth constant) above the tunnel node at 25.2715366,
> 51.6022718. Same issue at 25.2556192, 51.6080938, and there should be
> no service road shape running around the outside of the tunnel wall
> at 25.2556004, 51.6080853."

This is an OWNER RULING. It SUPERSEDES, for tunnel wall crest bands:

* round-4 spec R5 (`round4-othh-fixes-spec.md`, lead ruling 2026-08-10)
  as applied to "tunnel walls' crest bands";
* R16-2a's "the crest converges on the ramp at the portal";
* `groundside.TRANSITION_ROLES`' inclusion of `ROLE_RETAINING_WALL`
  ("the band IS the first ring of the transition") — the band is the
  CLIFF TOP;
* the `_band_altitudes` docstring's "sampling the DEM alone gave a flat
  4.00 m crest against a −4.02 m ramp" — that flat crest IS the ruled
  surface.

The §F1 station law (one value per station, LEMD fidelity spec law 1,
`O4_WALL_TOP_STATION`) STANDS. 2026-09-01c/e (foot retired, 0.6 m gap,
both band edges carry one corridor-top value) STAND — this spec fixes
WHAT that corridor-top value is: the DEM.

## 1. Measured (owner's patch, `XPTerrainBuilderData/Patches/+20+050/+25+051/OTHH_auto.patch.osm`)

Site 1 (mouth, ways `-11620` ramp / `-11621` wall, one U-band ring,
both sides + cap across the mouth):

| node | what | alt | should be |
|---|---|---|---|
| -25229 | ramp mouth vertex (owner's tunnel node) | −1.12 | −1.12 (bore datum: DEM 4.0 − 5.1) |
| -25259 | wall inner vertex 0.85 m off it (owner's wall node) | −1.10 | ≈ 4.0 (DEM) |
| -25258 / -25257 / -25256 | wall inner edge climbing away from the mouth | 0.94 / 3.06 / 4.00 | 4.0 / 4.0 / 4.0 |
| -25260, -25277 | the cap across the mouth | −1.08, −1.10 | 4.0 (the portal headwall) |
| -25276 / -25275 / -25274 | wall OUTER edge | −0.30 / 1.72 / 3.78 | 4.0 |

The crest profile is `ramp + GROUNDSIDE_MAX_GRADE × run`, capped at DEM:
the wall descends WITH the ramp and the cut is a bowl, not a walled
5.1 m trench. `wall_top_flat` reads it as a 5.1 m "pre-existing
residual" (zero-airside plan §DEFERRED) — it is this defect.

Site 2 (mapped tunnel: feed way `-9169` highway=service tunnel=yes
starts at the mouth node; `-8338` highway=service is the approach; the
ramp `-11650` runs along `-8338` down to the mouth; wall `-11651`):

* wall inner/outer edge −1.06 … 4.0, same profile as site 1;
* `service_road` `-10051` (shapeID 51 — the minted approach-road rect
  of `-8338`) survives the ramp cut as a U-shaped RIBBON 1.8–5.1 m wide
  outside the wall band, wrapping the mouth end; it SHARES nodes
  `-1368…-1377` with the wall's outer edge and, `retaining_wall` being
  an unnamed soft receiver in `layout.AUTHORITY_PRECEDENCE`, the road's
  value wins at every shared node (4.0 / 2.5 / 0.78 / −0.99 …);
* the ribbon's own outer nodes carry −0.95 … −0.03 ACROSS the mouth
  (`-1349…-1355`): ground over the bore, dragged to the ramp.

## 2. Mechanism — three sites, one law spelled twice plus a remainder

1. **Emit-time crest (`bridges.py`).** `_CrestProfile.__init__` samples
   the DEM along the walled body's ring and then applies
   `groundside.transition_law_altitudes(ring, dem, _BelowGradeIndex(the
   ramps), GROUNDSIDE_MAX_GRADE)`: one anchor per body pinned at
   `deepest_station + cap × gap`, ring relaxed to the cap. The band's
   vertices read that profile at their station (`emit_wall_band.
   _band_altitudes`); the station-law-OFF fallback in the same function
   runs `transition_law_altitudes` per band ring; the low-corridor
   emitter (`_emit_low_corridor_connectors`, bridges.py ~6432) builds the
   same `_CrestProfile` with a `_BelowGradeIndex` of its own floor.
   `_emit_facing_corridors`' per-body band (bridges.py ~3300) already
   samples raw DEM — that emitter is CORRECT and is the model.
2. **Finalize-time re-profile (`finalize.py:661` →
   `groundside.apply_below_grade_transition`).** Every shape in
   `TRANSITION_ROLES` (groundside_pavement, service_road,
   service_junction, **retaining_wall**) within `transition_reach_m` of a
   `BELOW_GRADE_REFS` body (`tunnel_ramp`, `tunnel_trench`) is re-graded
   toward the body. So even a DEM crest at emit is pulled back down
   here, and the approach-road ribbon and the ground over the bore are
   pulled to the ramp THROUGH the wall.
3. **Host remainder (`bridges._tunnel_ramp_pavement_cut` →
   `cut_pavement_over_footprint`).** The ramp cuts service-road-family
   hosts by the CLEARANCE ANNULUS only (ramp ∪ gap ∪ wall width); every
   remainder part ≥ 5 m² is kept with NN-resampled altitudes. The
   canonical-mouth ruling (RULINGS 2026-08-30: "for hosts in the
   SERVICE-ROAD FAMILY the corridor claim takes the host WHOLE") was
   implemented by the `tunnel_road` claim class, which RETIRED with
   Batch 3 (2026-08-31 tunnel model verdict) — nothing replaced the
   host-whole clause, so the strips-plus-remainder composite is back.

## 3. THE LAW

* **L1 — The crest is the DEM at its station.** `_CrestProfile` samples
  the DEM along the body ring and interpolates by station; NO transition
  law, no below-grade index, in either emitter (`emit_wall_band` both
  paths, `_emit_low_corridor_connectors`). At a mouth the crest stands
  the bore datum (`BRIDGE_ROAD_CLEARANCE_M` = 5.1 m, less DEM
  variation) above the ramp's mouth vertex BY CONSTRUCTION. The cap
  across the mouth is at DEM: it is the portal headwall.
* **L2 — The wall is the discontinuity.** `ROLE_RETAINING_WALL` leaves
  `TRANSITION_ROLES`. No post-emit pass grades a wall crest toward a
  ramp (`apply_below_grade_transition`, and audit the FGP / seam / weld
  passes in the §4 census for any other writer of wall nodes).
* **L3 — Ground outside a walled ramp stands at the crest, not on a
  transition to the ramp.** A ramp body that has a wall band registered
  against it (`bridges.wall_band_owners`) is NOT a below-grade source for
  `apply_below_grade_transition`; its wall carries the drop. Unwalled
  shallow ramps (< `_RAMP_WALL_MIN_DIG_M`, no band) keep R5. Prefer the
  single derivation site: filter inside `below_grade_sources` (or the
  index it builds), never per consumer. `tunnel_trench` (LEMD basins,
  OTHH drainage) is OUT OF SCOPE — unchanged, and the LEMD basin
  evidence must stay byte-held.
* **L4 — Service-road-family hosts: the ramp takes the host WHOLE
  alongside its run.** For `ROLE_SERVICE_ROAD` / `ROLE_SERVICE_JUNCTION`
  hosts the cut is not the annulus but the corridor: every part of the
  host on the tunnel side of the ramp body's FAR (surface) END LINE —
  beside the ramp, beside the wall, across the mouth, over the bore —
  is removed; only host material beyond the far-end line (the road at
  grade the ramp descends from) survives, split at that line. This is a
  geometric partition by the ramp's own end line — NO width, area or
  distance tolerance (RULINGS 2026-09-01e: standoffs never on a
  tolerance; fitted exclusions are refused). Where a host straddles the
  far-end line, `difference` it against the tunnel-side half of the
  corridor and keep the rest. `groundside_pavement` hosts keep
  2026-08-25e (the OTHH −12168 class). Log ONE line per host piece
  taken, with its shapeID and area (the named-removal law, RULINGS
  2026-08-25 §1).

Consequences by construction: `wall_top_flat` still 0.00 (one value per
station); `ramp_wall_gap` still 0 shared ids (the gap is untouched);
the mouth cap becomes the headwall; the two owner wall nodes read
≈ 4.0 against ramp −1.12; way `-10051` no longer exists as a ribbon.
Nothing here touches airside: the bar is AIRSIDE NOT WORSENED
(`census.py`, law-true frame) and the groundside delta REPORTED, not
adjudicated — the owner's sim read adjudicates.

## 4. Consumer census (RULINGS 2026-08-30l) — rule EVERY row before editing

Readers of wall-band values / `retaining_wall` role / `tunnel_wall` ref
(grep counts: bridges 33, adjacent_ground 11, verification 5, layout 4,
groundside 4, tile_cut 2, seam_anchors 2, gap_fill 2, config 2, plus
road_piece_ledger, pipeline, geom_guard, finalize, elevation, boundary 1
each) and of `BELOW_GRADE_REFS` / `below_grade_sources`. For each: does
it READ the crest value (and expected it graded), WRITE wall nodes, or
only test membership? Fill the table in the lane's report; the
expected verdicts: adjacent_ground treats `retaining_wall` as
INADMISSIBLE anchor (2026-08-01) — unchanged; `law_anchor_values` —
wall is a soft receiver, unchanged; FGP — zero movers on tunnel roles
(2026-09-01v), verify still zero; to_osm precedence — with L4 the
wall's outer edge no longer shares nodes with a road host; check what
it DOES share with (groundside_pavement per 25e) and report.

## 5. Method (CLAUDE.md BUILD ECONOMY — synthetic first, ONE airport)

1. Baseline instrument reads on the OWNER'S patch (read-only):
   `tools/tunnel_portal_acceptance.py <patch> --profile OTHH
   --osm-data-dir /Users/noah/XPTerrainBuilderData/OSM_data` and
   `tools/osm_site.py <patch> --at LAT,LON --radius 8` at the four
   coordinates above. Record them as the fixture's pins.
2. Site fixture: `tools/repro_cut.py OTHH --coord 25.2556192 51.6080938
   --radius 160 --patch <owner patch> --pin …` (site 2 exercises L1–L4;
   cut site 1 too, `--coord 25.2715296 51.6022683`). Iterate on the
   fixtures; `solve_cut.py` if a stage replay is cheaper.
3. Twins (rewrite, don't delete the intent):
   `tests/test_round4_pads_claims_transition.py::test_the_wall_crest_stands_at_grade_and_converges_at_the_portal`
   → the crest stands at grade EVERYWHERE, portal included, and
   `apply_below_grade_transition` moves 0 wall shapes;
   `test_the_crest_does_not_hug_the_ramp` stays; the plate tests stay
   for UNWALLED ramps and gain a walled-ramp twin (L3);
   `tests/test_round16_geometry_consistency.py` R16-2a/2b rows that
   assert convergence; `tests/test_lemd_ramp_road_fidelity.py` F1 rows
   stay (station law); `tests/test_tunnel_portal_acceptance.py`; a new
   L4 twin (service host straddling the far-end line: tunnel side gone,
   grade side kept, no width tolerance in the code). Run the blast-listed
   suites (`tools/blast.py` on bridges.py, groundside.py, finalize.py).
4. Closing test: ONE airport, OTHH, through
   `tools/harness/build_airport.py OTHH` in the lane worktree
   `/Users/noah/XPTerrainBuilder/.claude/worktrees/wallcrest/Ortho4XP`;
   then `census.py` (law-true) before/after, `tunnel_portal_acceptance`
   before/after, `osm_site.py` at the four coordinates. NEVER the sweep.
5. Report: mechanism confirmed/refuted per site, the census table (§4),
   the four coordinates' emitted values, airside delta (must be ≤ 0),
   groundside delta, acceptance deltas, and anything L4 removed that
   looks like a real road (list every named removal). The spawner
   merges.

## 6. Delete, don't gate (RULINGS 29f)

The transition-law code in `_CrestProfile` / `_band_altitudes` / the
low-corridor `_BelowGradeIndex` construction is DELETED, with the
`_idx` build in `emit_wall_band` that only served it. No env flag for
the old crest. `O4_WALL_TOP_STATION` (station law) stays as is.
