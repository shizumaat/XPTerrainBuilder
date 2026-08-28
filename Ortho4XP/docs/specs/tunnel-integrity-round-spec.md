# Tunnel integrity round (Fable spec, 2026-08-28; RULINGS 2026-08-28
# items 4–8 + 2026-08-28c items 9–12, attribution lane/lemdtun —
# twelve owner items, one subsystem, eight laws)

## §0 Measured frame (lane/lemdtun report; patches pv_on_lemd,
## LEMD_dbg /tmp/harness/LEMD_dbg.osm, owner OTHH patch; all findings
## pre-date padvars — pv_off identical on every tunnel measure)

Key numbers: LEMD portal acceptance 2 PASS / 2 FAIL (site_reach 225.7
and 661.0/542.3 m); 37 LEMD tunnel ways killed by the adjacent-road
system veto; 8/8 LEMD DEM-cut clusters emit no ramp; all 8 tunnel_cap
rings are 0.5–11 m² slivers; OTHH ramp -12214 welded to wall -12220
(4 shared node ids, 0.0000 m); claimed corridors carry 0–48 % wall
coverage vs the synthetic path's 82 %; 22 road-corridor pieces at
grade over roofed bores across the two airports; 48 isolated road
rects (LEMD 32 + OTHH 16) whose 4.4–9.0 m voids are the rect-trim
gaps with the junction fill LOST (40 rects + ~78 fills vanish between
minter and emit, unlogged). Code sites in the lane report.

## §T1 A PACK STRUCTURE OVER A MAPPED BORE IS A TUNNEL, AND THE
## TRENCH UNIONS COMPOSE

1. Object classification: a bridge/tunnel-ambiguous pack structure
   whose corridor lies over a mapped `tunnel=yes` way classifies as
   an object TUNNEL (deck-clearance corridors are for structures over
   OPEN ground). Consequence: R8-3 object-trench yield composes at
   LEMD's -2070 portal.
2. Independent belt: `_object_trench_body_union` widens to include
   `ROLE_BRIDGE_TRENCH` bodies — a bridge trench is still a trench to
   every consumer that asks "is this ground object-owned".
3. The four 0.3–4.3 m² `authority_retreat_wall` stubs at the item-4
   site are the adjacent-ground machinery improvising at an
   object-bridge trench edge — extend the RULINGS 2026-08-07 ramp
   exemption to object trench/bridge-trench edges (no improvised
   retreat walls there).

## §T2 DEM-CUT MODE GATES ON DEM PROVENANCE; THE CAP YIELDS TO THE
## MOUTH AND DIES WHEN IT NO LONGER SPANS

1. "No synthetic ramps (DEM cut present)" requires BOTH measured
   relief (the existing `_cut_measured`) AND a DEM provenance class
   that can actually carry an approach profile (lidar/sub-metre
   inset; the sidecar's `site_class`/`dem_inset_provenance` is the
   register — `sub10m` NEVER qualifies). A coarse-DEM "cut" emits the
   full synthetic ramp+mouth exactly as if no cut existed. The EGGW
   ruling (2026-07-17) is preserved where lidar earned it.
2. R16-2b vs R10-2: THE MOUTH WINS. The cap face stops at the mouth
   plate's near edge minus the wall gap (never reaches into it), and
   a post-cut cap fragment that no longer SPANS the portal face
   (min-rotated-rect width < the bore's carriageway width) is
   DROPPED with its §1-style named line — never shipped as a
   free-standing sliver. `_TUNNEL_COVER_MIN_PIECE_M2` stops being the
   only survivor gate for caps.
3. Light-touch/DEM-cut mouths lose their exemption from the R10-2
   unwalled-mouth finding — the finding reports them like any mouth.

## §T3 THE ADJACENT-ROAD VETO IS SCOPED — AN AIRPORT'S OWN BORES ARE
## NEVER VETOED BY ITS OWN SERVICE ROADS

1. The veto (SKIP_TUNNEL_RAMPS_NEAR_ROADS) exists for urban
   interchanges (LMML). It no longer applies to a bore whose portal
   (either end) lies inside the airside gate union or whose covered
   span passes under runway/apron/taxiway pavement — those are the
   airport's own tunnels, the very thing the machinery exists to
   model. System propagation drops for NON-crossing neighbours
   (crosses=False, d>0): a road merely near a candidate never vetoes
   the whole system.
2. Every veto that still fires logs at verbosity 0 (one line per
   way, the existing text) and `layout.tunnel_passthrough_findings`
   is published to the sidecar (`tunnel_vetoes`) and printed by the
   census — refusals recorded and thrown away are the class this
   campaign exists to kill.
3. Expected consequence at LEMD: bores -1872/-257, -2085, -2119
   regain their mouths (owner items 6/7); acceptance is the portal
   table flipping those sites to PASS.

## §T4 NO ROAD-CORRIDOR PIECE IS EVER LOST SILENTLY, AND THE FILLS
## COME BACK

1. FIRST (the attribution step the lane chartered): a per-pass shape
   -count checkpoint between `build_service_road_network` and
   `to_osm` (counts by role+ref per pipeline pass, logged once per
   build) — name the pass that drops 40 rects + ~78 junction fills at
   LEMD. Then fix THAT dropper so surviving corridors keep their
   fills; any legitimate removal gains a §1-style per-piece named
   line.
2. Acceptance: the 48 isolated road rects (LEMD 32, OTHH 16) fall to
   0 isolated-with-a-road-neighbour-in-<10 m (a genuinely isolated
   rect far from everything may remain — report it); the owner's
   -10376/-10377 pair is connected through its fill.

## §T5 THE RAMP–WALL GAP RETURNS, AND THE WALL OWNS IT

1. Reconciling the owner's "the ramp must have a small gap from the
   wall" with R16-2b's measured unowned-annulus defect: the wall's
   inner boundary stands off `_g0` (0.6 m) from the ramp again, AND
   the annulus is OWNED BY THE WALL SHAPE as its FOOT — the wall
   polygon extends inward to the ramp edge at ramp-edge elevation
   (flat foot, vertical face rising from the foot's outer edge), so
   no shared node ids between ramp and wall, no unowned mesh, and
   the sim's mesh can articulate the two surfaces. Twin re-measures
   the 17-node OTHH gap class R16-2b fixed: still owned.

## §T6 CLAIMED CORRIDORS ARE FIRST-CLASS BORE GEOMETRY

1. §2.3 of the portal-corridor-claim spec is IMPLEMENTED: a claimed
   corridor walls itself exactly as the synthetic path does (the R2
   node-split wall class through the host), both sides, ends
   wrapped. Acceptance: wall coverage of claimed corridors rises to
   the synthetic path's class (measured 82 %).
2. §2.2 is ENFORCED: the claim rides the corridor FOOTPRINT only —
   never the whole host ring. OTHH -12168 (19,461 m² landside ring
   relabelled whole, tongues at z=1.90 reaching the covered
   interior) is the exemplar: the claim clips to the bore corridor;
   the host keeps its own role/ref outside it; the interior tongues
   fall under §T7's covered-span mask.
3. The acceptance instrument learns both: `site_reach` no longer
   accepts a below-grade `ref=tunnel_road` surface as bore geometry
   without a face; `_record_tunnel_mouth_walling` checks claimed
   corridors too.

## §T7 NO SYNTHESISED ROAD PAVEMENT OVER A COVERED SPAN —
## EMITTER-INDEPENDENT

1. A COVERED-SPAN MASK (union of mapped bores' covered stretches,
   the data the tunnel pass already derives) is published once and
   consumed by `build_service_road_network` (rects and fills never
   minted inside it) and by a post-mint suppression that catches any
   other emitter's synthesised road-corridor pavement there (the 22
   measured pieces: 6.00 m rects, 3.50×6.00 fills, their groundside
   demotions). Mapped REAL pavement polygons (OSM/apt.dat authored)
   are NOT suppressed — the mask kills synthesis, not data.
2. Acceptance: the 22-piece joined population (OTHH 16 + LEMD 6,
   incl. shapeID 1111 and LEMD's shapeID 557) emits nothing; R14-2
   roofing behaviour unchanged.

## §T8 INSTRUMENT REPAIRS (with the round, same commits)

1. `covered_span_clean` gains a local datum (bore deck/grade
   reference, never absolute 0.0) — LEMD's 561–617 m field makes the
   current predicate structurally vacuous.
2. `--site` mode accepts `--bore-osm`/`--bore-ways`/`--covered-span`
   so ad-hoc runs can execute the covered-span and claim checks; a
   LEMD profile ships once the datum bug is fixed (the bores exist in
   the road-feed cache under the named ids).
3. Portal-corridor-claim §1 (one named line per removed piece) is
   enforced at the item-4 removal sites (mouth plate, cap remainder).

## §Twins / flags / acceptance (shared)

- Each §T flag-gated (`O4_OBJ_TUNNEL_COMPOSE`, `O4_DEMCUT_PROVENANCE
  _GATE`, `O4_TUNNEL_VETO_SCOPED`, `O4_ROAD_PIECE_LEDGER`,
  `O4_RAMP_WALL_FOOT`, `O4_CLAIM_WALLS`, `O4_COVERED_SPAN_MASK`),
  default ON, OFF byte-identical each; twins per law including the
  preserved prior rulings (EGGW lidar no-ramp; R16-2b owned annulus;
  LMML veto still fires off-airport).
- Acceptance builds: ONE LEMD + ONE OTHH (+ HECA quick check for
  no-regression); the full portal acceptance tables before/after
  (expect LEMD 4/4 PASS on the owner sites); census honest A/B;
  the owner's twelve items each re-read at its coordinate.
- Convergence guards standard (materiality 0.01 m, cap 2 per §T,
  STOP on second miss, heartbeat); no shared-repo writes; no timing
  claims; build-time statement.
