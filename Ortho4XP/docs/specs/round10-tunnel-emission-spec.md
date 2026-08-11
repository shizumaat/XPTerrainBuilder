# Round 10 — tunnel emission: evidence before depth, walls never cover ramps

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r10tunnel**. Pre-ship mode
(docs/RULINGS.md) — unit tests for changed behaviour once; deviations
STOP-and-report. All code here is `src/auto_patch/bridges.py` unless
named otherwise. Fixture: KCLT (tile +35-081; corpus warm for the road
feed via the owner's app build, else `--allow-degraded-dem`).

## Measured attribution (2026-08-11, KCLT build tree befb3ba,
## O4_TUNNEL_DEBUG log /tmp/harness/kclt_tunnel_debug.log)

AREA 1 (35.2202382, -80.9459021, owner: "no tunnel here, flat ground,
service road passes under the building"):
* The four `tunnel=yes` service ways there run **100 % under mapped
  building footprints** (measured against the tile's airports extract).
* Base DEM dead flat: 218–220 m across ±150 m both axes.
* The engine's own portal probes agree: `median_cross_road_depth`
  0.13–0.22 m, `cut_detected=False` (ways `F|-600, -601, -873, -1119`)
  — and it emitted portal clusters (ramps at synthetic depth, walls)
  anyway: `cut_detected` (line ~1985) only selects DEM-cut vs SYNTHETIC
  ramp construction, never admission. Emitted defects: `tunnel_ramp`
  1729/1730/1731 + `tunnel_wall` 1732/1770 through apron 165 and each
  other (wall 1732 ∩ ramps = 124/254/62 m²).

AREA 2 (the real tunnel, 35.215x, -80.944x..-80.946x): mapped ways
`-9699` (95 m, portals AT the owner's two mouth points ±2.4 m) and
`-9695` (59 m), open gap between them; probes found real cuts
(3.3–4.4 m). Emitted defects:
* mouth 1724 (211.13) + `authority_retreat_wall` 2355-2358 sit ON the
  service_junction shapes 605/606 in the gap — the mouth is stationed at
  the pavement-crossing exit, 48 m from the mapped portal; the mapped
  portal point emits nothing and stays at grade.
* `tunnel_roof` 1723 overlaps taxiway junction 1668 (the covered-stretch
  drop — "dropped 2 tunnel piece(s) under pavement" — did not cover it).
* mouth 1728 (215.83, 3.2 m below its 219.0 deck where the owner states
  ≥5 m) sits on service junctions 627-629 with a `tunnel_cap` but NO
  wall: `[tunnel-walk-dedup] dropped portal of way F|-255 (walk overlaps
  a kept ramp)` — the dedup (line ~2100) discards a whole portal walk
  (ramps AND walls) while the neighbouring cluster's mouth survives
  unwalled.
* The pre-band wall-vs-ramp clip (line ~3341) keeps only the LARGEST
  surviving piece (`parts9[0]`), silently deleting the other wall arcs;
  the continuous perimeter band (~3516) buffers each ramp-union polygon
  separately and never subtracts sibling polygons or later clusters.

## The laws

### R10-1 NO PHYSICAL EVIDENCE, NO DEPTH (kills area 1)

A portal whose DEM probe found no cut (`cut_detected=False`) and whose
way carries no `layer < 0` emits NOTHING below grade at that portal: no
mouth, no synthetic ramps, no portal walls, no cap. The covered stretch
under pavement/buildings is already invisible (the existing drop); a
way with no evidenced portal at EITHER end emits nothing at all.
* `tunnel=building_passage` is a COVERED-AT-GRADE statement by
  definition: it never seeds synthetic depth regardless of the probe
  (it may still satisfy R4 chain-evidence for OTHER laws — do not touch
  `_has_tunnel_tag_evidence`'s role in the implied-bore veto walk).
* Record the verdict per way in the tunnel debug output AND as a counted
  finding on the layout (the `band_clamp_findings` pattern, name it
  `tunnel_passthrough_findings`): way id, portal position, measured
  median depth, building-cover fraction (compute against
  `ROLE_BUILDING` shape footprints — area 1 measures 100 %; the
  fraction is evidence in the record, NOT an admission input).
* The synthetic fallback (`apt_elev − tunnel_depth_m`) survives ONLY for
  portals with `layer < 0` and no usable DEM (an explicit below-grade
  statement the DEM cannot corroborate).

### R10-2 A WALL NEVER COVERS TUNNEL PAVEMENT; DEDUP NEVER UNWALLS A MOUTH

* Every emitted wall/roof/cap polygon (`tunnel_wall`, `tunnel_roof`,
  `tunnel_cap`, the perimeter band) is cut, immediately before its
  shape is appended, against the FULL union of this build's
  `tunnel_ramp`/`tunnel_mouth` polygons emitted so far plus this
  cluster's own — not just its own annulus polygon's inner buffer.
  ALL surviving pieces ≥ 0.5 m² are kept (append extra shapes), fixing
  the largest-piece-only deletion at ~3341 the same way.
* `_dedup` of portal walks (~2100) may drop DUPLICATE RAMP GEOMETRY
  only. When a walk is dropped, the kept cluster it overlapped adopts
  the dropped portal's mouth-edge wall responsibility: after dedup and
  ramp emission, every below-grade mouth's perimeter must be covered by
  wall/cap pieces or abut pavement — assert this as a build-time check
  (report, don't fail: a counted `tunnel_unwalled_mouth` finding names
  the mouth and its uncovered edge length).

### R10-3 MOUTHS AT MAPPED PORTALS, DEPTH FROM CLEARANCE

* A mapped tunnel way's portal stations are its MAPPED END NODES (the
  OSM way's tunnel extent), not the crossing-pavement exit: the portal
  walk starts at the mapped end and runs OUTWARD (the approach) —
  today's walk geometry stays, only its anchor station moves. Where the
  mapped end lies under pavement the existing graze clip applies
  unchanged. (Area-2 acceptance: a mouth within 10 m of each `-9699`
  end; nothing at the junction 48 m away.)
* Mouth depth at a covered crossing: `min(mouth_min_from_DEM,
  deck_reference − TUNNEL_CLEARANCE_M)` — the DEM's smoothed trench
  (1-arcsec under-resolves a narrow cut) can never report a bore
  shallower than the clearance the crossing structurally requires. Use
  the existing clearance constant bridges.py already holds for deck
  clearance; do not mint a new one.
* Roof/cap plates: the covered-stretch drop's cover union must include
  EVERY pavement role (the junction roles are missing today — roof 1723
  over junction 1668); a roof plate never overlaps an emitted pavement
  shape (same cut as R10-2).

## Tests (tests/test_round10_tunnel_emission.py, new; adapt existing
## tunnel tests only where their pinned behaviour is what this spec
## changes — name each adaptation in the commit message)

1. Passthrough twin: flat-DEM probe (depth < TUNNEL_DEM_CUT_MIN_DROP_M),
   `tunnel=yes`, no layer ⇒ zero below-grade shapes, one finding with
   cover fraction; same scene with `layer=-1` ⇒ synthetic emission
   survives; `tunnel=building_passage` + cut ⇒ still nothing synthetic.
2. Wall-cut twin: two disjoint ramp polygons, band around one overlaps
   the other ⇒ emitted wall pieces have zero intersection with the ramp
   union; a wall ring split into 3 arcs keeps all 3 (the largest-only
   regression pin).
3. Dedup twin: two overlapping walks, one dropped ⇒ the surviving
   mouth's perimeter is walled/capped/abutting; the
   `tunnel_unwalled_mouth` finding fires when it is not.
4. Stationing twin: synthetic way with mapped ends inside/outside a
   crossing ⇒ mouth anchors at the mapped end; depth twin: DEM cut
   2.0 m, deck_reference − clearance = 5.0 ⇒ mouth 5.0 below deck.

## Acceptance (ledgered harness builds)

* KCLT rc=0. In the emitted patch: AREA 1 has ZERO shapes with ref in
  {tunnel_ramp, tunnel_mouth, tunnel_wall, tunnel_roof, tunnel_cap}
  within 150 m of 35.2202382,-80.9459021; AREA 2: wall∩ramp overlap
  0 m² patch-wide, every mouth walled (zero unwalled-mouth findings),
  a mouth within 10 m of each mapped `-9699` end, mouth depth ≥
  deck − clearance there, zero roof∩pavement overlap patch-wide.
* OTHH rc=0 (the tunnel-heavy control; its 8 self-evidenced bores must
  still emit — count tunnel clusters before/after and quote both).

## Bookkeeping

One DEFERRED_VERIFICATION.md line (lead writes it at merge): no VHHH
arm, no census, no battery beyond KCLT+OTHH, walk-geometry cost
unmeasured. Version stamps are the lead's at app build.

## AMENDMENT 2026-08-11 (Fable lead ruling on the implementer's three
## STOP items; this section supersedes the conflicting lines above)

**A1 (STOP-1, supersedes R10-1 bullets 1 and 3).** The DEM is the
physical authority; OSM `layer=-1` is a RELATIVE stacking statement
(order against the crossing feature — at a building passthrough, the
building), never absolute depth. The operative predicate, per portal:

    emit below grade  ⇔  cut_detected
                          OR (layer < 0 AND the DEM is unusable)

"Unusable" is exactly the probe's own failure condition:
`_median_depth is None or len(_trench_depths) < 2`. Area 1's ways
(`F|-600/-601/-873/-1119`, all `layer=-1`, all with usable flat probes)
therefore emit nothing — the measured flatness outranks the tag. A
refused portal still mints its `tunnel_passthrough_findings` record
(include the way's layer value in it, so a wrongly-refused real tunnel
is visible evidence, not silence).

**A2 (STOP-2, strikes R10-3 bullet 1).** Mouths already anchor at
mapped end nodes (`_gather_portal_walks` :1763, `walk[0]`) — the
stationing bullet is struck as a no-op; the 48.3 m acceptance miss at
`F|-255` end 1 is owned by the dedup (A3). The 10 m acceptance bullet
stands and is satisfied through A3, not through anchor edits.

**A3 (STOP-3, supersedes R10-2's dedup paragraph; ramp-truncation half
REVISED by owner ruling 2026-08-11 — the open-cut corridor).** Dedup
keys on PORTAL IDENTITY, never on walk overlap: `_dedup_portal_walks`
may drop a portal walk ONLY when its portal station lies within
`portal_cluster_dist_m` of an already-kept portal (the same physical
entrance, e.g. divided carriageways). Facing portals across an open gap
(`F|-255` end 1 vs `F|-251`'s end, 55.5 m apart) are DISTINCT entrances:
BOTH emit mouth + walls.

THE GAP IS AN OPEN CUT, NOT TWO RAMPS (owner, verbatim: "the two close
together tunnel mouths indicate the whole area is lowered … and flat
between the two mouths"). When two portals of the SAME ROAD
(`_way_signature`, the R6-2 same-road law) face each other across a gap
≤ the existing 100 m mapped-end distance:
  * the gap emits ONE depressed CORRIDOR surface at the linear
    interpolation of the two mouth grades (flat when they agree), the
    corridor width the walks' shared carriageway width — NO
    ramp-to-grade geometry anywhere inside the gap;
  * both portal faces (mouth/cap) emit at their mapped stations at
    their bore depth, standing in the corridor;
  * the corridor is walled along BOTH sides (R10-2's cuts apply to it
    exactly as to ramps — add the corridor's role/ref to the cutting
    union alongside tunnel_ramp/tunnel_mouth), and is roofless (it is
    not tagged tunnel);
  * ramp-to-grade geometry emits ONLY at portals NOT facing another
    same-road portal (the outer approaches of the system);
  * depth floor per R10-3: the corridor and mouths take
    max(DEM cut, deck_reference − BRIDGE_ROAD_CLEARANCE_M) below deck —
    the real DEM carries part of this cut (probes measured 3.3–4.4 m)
    and the clearance floor supplies the rest.
The `tunnel_unwalled_mouth` build check stays as the backstop. Add an
acceptance bullet: between the two `F|-255`/`F|-251` facing portals,
the emitted corridor surface is flat within 0.5 m end to end, and no
node inside the gap sits above (corridor grade + 0.5 m).

**A4 (approved extensions the implementer flagged).** The finalize
pass at `_finalize_tunnel_emission` (:4357-4398) receives the same
R10-2 corrections as the per-append cut: include `tunnel_roof` among
the cut shapes, include `tunnel_mouth` in the cutting union, keep ALL
surviving pieces ≥ 0.5 m² (append extra shapes; the `max(geoms)`
largest-piece rule is the same deletion defect as :3341), and drop the
≤0.25 m² overlap-ignore. Both passes stay (per-append for
intra-cluster, finalize for cross-cluster ordering).

**A5 (constants + naming).** The R10-3 clearance constant is
`BRIDGE_ROAD_CLEARANCE_M` (5.1 m, config.py:4467) — NOT the 4.2 m
minimum. Spec/way naming: area-2 ways are `F|-255` (95 m, the owner's
two portals) and `F|-251` (59 m) in the engine's road-feed namespace;
the raw-extract ids `-9699`/`-9695` appear nowhere in the feed cache —
all greps and acceptance checks use the `F|` ids.
