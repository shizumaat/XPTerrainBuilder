# Round 17 — VHHH: the reclaimed island (canyons, causeway, sea walls)

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r17vhhh**. Pre-ship mode
(docs/RULINGS.md); deviations STOP-and-report to the Fable lead.
Owner in-sim report on 1.0.239 (+22+113), attribution paid by the
vhhh17 recon (this session; artifacts in the session scratchpad:
`vhhh17.build.log`, `vhhh17.census.*`, `tiles/zOrtho4XP_+22+113/
Data+22+113.mesh`; control = the owner's shipped patch at
`/Users/noah/XPTerrainBuilderData/Patches/+20+110/+22+113/`).

## Carried attribution (measured — do not re-derive)

* Flat mode ACTIVE (Z0 7.315, `+FLAT_SITE` provenance stamped); the
  unsubstituted-DEM suspect is REFUTED. The canyons (−13.1 m worst,
  ~320 m off every runway end; worst census rows 19.57 m steps INSIDE
  junction pavement) exist because the R8-2 writeback clamp is NOT the
  last author: `[final-projection-ingestion]` logs a post-solve
  mutation set of 8,438 moved nodes (p90 19.554 m) AFTER the clamp,
  and the final band report reads the clamp's own worst node
  (x≈2049,y≈712, junction) back out of band — `band_excess` 245 rows,
  worst 17.23 m, all junction. The clamp resolves the CARRIED
  `env_band`; the report REBUILDS `reach_band_unified` — two
  constructions of one band (now an explicit owner ruling, RULINGS
  2026-08-11b: ONE construction per solve).
* Runway-end ground: zero `runway_end_skirt` shapes emitted (the
  [98/100] step runs, emits none) and `adjacent_ground` disclaims
  runway ends — observed, not yet authorized to fix.
* Causeway: the owner's connector point is already flat (claimed-object
  clusters); the break is the open channel; OWNER RULED (2026-08-11,
  interview): the causeway corridor between the airport and the island
  to its EAST — bbox **lat 22.3125624–22.3145276, lon
  113.9426422–113.9469981** — grades flat at Z0 with vertical sea
  walls on both sides; open water OUTSIDE the corridor stays SEA
  (R8-1's channel ruling stands elsewhere). The nearby 8-placement
  cluster refused on `cluster_datum_offset` (−10.82 m median) stays
  refused — the datum check is correct; the declaration is the lawful
  path.
* Sea walls: R7 admits walls only where PAVEMENT touches water — 11
  breaklines / 1,562 m = 7.5 % of the 20,873 m reclaimed shoreline;
  the other edges render ~26 % beach ramps. Owner ruled the WHOLE
  airport edge is vertical sea wall.

## The laws

### R17-1 THE CLAMP IS THE LAST AUTHOR, AND THERE IS ONE BAND

(a) ATTRIBUTE FIRST (one step, bounded): name the post-solve pass
that authored the 8,438-node mutation set (the
`post_solve_mutation_set` partition, `route_profile/solve.py` ~5832,
carries the frame to do it). Quote the pass and its worst moves in
the commit. If that pass is minting the −19 m junction values from
below-grade sources (the KCLT R10 leak family), REPORT the mechanism
— do not fix it beyond what (b) bounds, this round.
(b) The reach-band writeback clamp runs as the LAST elevation author
before emit: re-applied after the final projection AND after every
post-solve mutation pass — nothing writes a pavement altitude after
it. Order enforced structurally (the clamp call sits at the end of
the solve pipeline, not "currently last by luck"); a twin proves a
post-clamp mutation cannot survive to emit.
(c) ONE BAND CONSTRUCTION (owner ruling, RULINGS 2026-08-11b): the
band is built once; the clamp and the final `band_excess` report
consume the SAME object. Whichever construction is production truth
(`reach_band_unified` is the standing consumer law) wins; the other
construction is deleted, not kept as a fallback.
Acceptance: VHHH `band_excess` material floor rows **245 → 0** (the
R8-2 metric, finally paid); mesh transects at all six runway ends
flat within band (no ≤0 m vertex within 500 m of an end on
graded_strip/junction/service_junction/apron roles — the recon's
1,681-vertex population → 0; `tunnel_trench`'s lawful below-grade
population exempt); census worst-ten no longer junction|junction
19.5 m steps. If skirt-emission absence still leaves unowned ground
off any end after (b), REPORT it (count, ends) — a skirt law is a
future round, not this one.

### R17-2 THE CAUSEWAY CORRIDOR (owner-ruled declaration)

A tile-cfg declaration carries the corridor: a new key in the
existing tile-cfg idiom (`O4_Cfg_Vars.py` registry — follow the
`flat_site_declared` naming family), value = one or more lat/lon
bboxes; VHHH's tile cfg gains the owner's bbox above. Effect, all
three authorities, by existing mechanisms only:
* ELEVATION: the corridor joins the flat extent (union), so its
  ground solves/pins at Z0 like the rest of the site;
* LAND: the corridor joins the patch pavement-is-land cutter's
  coverage (closed rings, bits 15 idiom) so the sea flood cannot
  cross it — R4's "CUTTER = pavement union" law gains the DECLARED
  corridor as an explicit, owner-authorized member (record that
  sentence in the commit; it is a ruled exception, not a drift);
* WALLS: the corridor's long edges join R17-3's admission set.
Open water outside the declared bbox is untouched (twin: a point in
the channel north of the corridor stays sea; the R8-1 channel test
stays green).

### R17-3 THE PERIMETER IS THE WALL SET

The seawall admission set becomes: the outer boundary of the EMITTED
GRADED COVERAGE (the union of patch shapes that carry land
altitudes — pavement, aprons, junctions, graded_strip,
adjacent_ground, the declared corridor; NEVER the OSM airport
boundary and NEVER water-spanning ribbon roles) intersected with
water — the existing 0.5 m offset/INTERP_ALT breakline idiom
unchanged, only the admission geometry widens. VMMC IS THE CONTROL:
its boundary spans real sea (standing R4 memory) and its wall count
must stay lawful — quote VMMC's breakline count/length before/after
and show no wall crosses open water away from graded coverage.
Acceptance: VHHH wall coverage of the shoreline where graded
coverage meets water ≥ 90 % of the recon's 20,873 m denominator
(quote the number); the recon's north-shore beach-ramp transect
(lon 113.9200) reads a vertical drop at the wall line; the west
−3.17 m underwater dip likewise walled or graded.

## Tests

Twins per law (post-clamp mutation cannot survive; one-band identity
— the report object IS the clamp object; corridor declaration
parse/union + outside-corridor-stays-sea; admission-set geometry on
a synthetic coverage-vs-water fixture + a VMMC-shaped
boundary-spans-sea fixture). Directly-covering files once, ledgered.
Pre-existing failures matched at base out of scope.

## Acceptance (battery LAST)

VHHH via `build_airport.py VHHH --tile 22 113` with a lane-local
build dir seeded by a COPY of the owner's tile cfg (the recon's
lawful pattern; the X-Plane install is never written). Steps 1–3 +
`mesh_elevation_sampler` transects are sufficient — if step 4 hits
the bathymetry-band index guard refusal, STOP THERE and report (no
shared-repo write is authorized; `--refresh-data` is an owner act).
Census before/after against the recon's before-frame (LAW-TRUE
12,917 / ADJUDICATED 11,995 FAIL): quote the delta; the canyon
families (within_shape junction, vertex/mid-edge steps at the ends)
must collapse; no new family grows beyond the 0.01 m floor. VMMC
control build (--patch-only) for R17-3. KCLT or SPJC as the
non-flat-site control for R17-1 (census Δ0).

## Bookkeeping

Convergence guards: materiality 0.01 m; cap 2, STOP on second miss;
`.progress` heartbeat. DEFERRED candidates per skipped check (lead
writes final). Build-time: R17-1's re-clamp is O(band nodes) — state
the measured phase times (tripwire only); R17-3 widens one union.
Cross-refs: RULINGS 2026-08-11b (one band; causeway ruling), R8-1/
R8-2 (superseded-in-part, cite exactly which bullets), r7seawall
spec, round4 patch-pavement-is-land spec, [[r8-writeback-band-crown-
frame]] (the "fix must cover BOTH halves" memory — (b) is the second
half, finally).
