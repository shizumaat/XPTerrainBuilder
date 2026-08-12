# Round 20 — KCLT: the ramp follows the road, reaches grade, and outranks the lot

Spec: 2026-08-12, FROZEN (Fable lead). Lane: **r20kclt**. Pre-ship as
amended; owner-artifact baseline (the 09:02 rebuild at
XPTerrainBuilderData/Patches/+30-090/+35-081/, READ-ONLY); kcltrecon
attribution paid (scratchpad reb_census/rows + kclt_site.py).
Deviations STOP-and-report; cap 2.

### R20-1 CURVATURE SURVIVES THE WALK (bridges.py:1929-1941)
The 15 m min-spacing merge deletes curve nodes (owner's node -75937:
1.86 m chord error) before _emit_chain's faithful miters; the densify
(:1944-66) interpolates survivors, restoring nothing. Law: plan
geometry keeps every deviation-bearing vertex — replace the spacing
filter with a deviation filter (Douglas-Peucker, tolerance ~0.25 m,
propose from the measured population) OR decouple: the 15 m merge
applies to the ELEVATION profile only, the plan chain stays full.
The altitude-rounding rationale in the comment must stay satisfied —
state how. Claims: max lateral offset emitted-vs-OSM at the owner's
portal < 0.3 m at every OSM node; ramp piece count/geometry quoted.

### R20-2 THE RUN REACHES GRADE (bridges.py:2181-2222, :594, :5932-33)
Round 14's _run_limit uses a PORTAL-LOCAL ambient (deck ref 211.4)
while the walk's DEM climbs to 216.7, and sizes at 5 %
(TUNNEL_APPROACH_GRADE) what it emits at 3.5 % (cap − safety margin):
the ramp tops 4.26 m below DEM in a 4.4 m cliff; ~97 m of corridor to
the taxiway carries no shape (AUG-5 had 9 pieces to 214.76). Law: the
run extends while dem_along_walk(s) − elev_low > emit_grade · s
(the EMITTED grade, one constant path), ending where the ramp
actually meets ground; the walk's surface continues from there to the
taxiway under the road law (the r14 claim machinery where claimed,
plain road pavement otherwise — no 200 m minimum returns, no
synthetic floor returns; the r14 ruling's REMOVALS stand, only the
run-sizing frame is corrected). Claims: ramp meets DEM within
tolerance at its top (no cliff), corridor to the taxiway surfaced,
mouth depth → DEM profile ≤ cap; the round-10/14 tunnel table
elsewhere UNCHANGED (OTHH 8/8, the 35.215/-80.944 tunnel_road claims
byte-stable).

### R20-3 THE ROAD OUTRANKS THE LOT — **HOLD until the lead messages
that adjacent_ground.py is free (r19 owns it)**
The within-tolerance branch of the 37c9771 retreat machinery lets the
road ADOPT the groundside lot's values over shared vertices (the
western dip, −6..−8 % segments); the class is airport-wide (528
groundside|groundside + 285 service_junction rows). Law:
service_junction/service_road OUTRANK groundside_pavement at a shared
vertex — the road's solved value wins, the LOT conforms (retreat/
feather per the r19-4 law on its side); and service roads carry their
o4_grade_law_cap tag (REBUILT has none on -10238; AUG-5 did). Claims:
the owner's corridor 35.206857,-80.9305042 → 35.2077303,-80.9290869
grades within the road cap end-to-end; the 13-of-17 over-cap segments
cleared; lot-side conformance quoted.

## Process
Twins per law, mutation-checked; blast --tests-for selection quoted;
covering files once, ledgered; ONE declared interventional KCLT
--patch-only arm to verify on real geometry (census with the R19-5
instrument if r19 has merged by then — say which). No acceptance
batteries; claims tables; the lead runs the consolidated +35-081 arm.
Files: bridges.py (R20-1/2); R20-3 waits. Never write the shared
repo/X-Plane. DEFERRED lines per skip.

## AMENDMENT 1 (Fable lead, 2026-08-12, on the R20-2 STOP) — one datum on the whole path

Measured: the run is SIZED against the R14-3 clearance floor
(_bore_floor_elevation ≈ 210.5) but _emit_portal_cluster (~:3027)
EMITS from apt_elev − tunnel_depth_m = 206.36 — the ~4.5 m datum
split IS the 4.26 m cliff. R20-2b: the cluster emit adopts the SAME
floor the sizing uses (one datum: gather, size, emit — route
_bore_floor_elevation into _emit_portal_cluster; the legacy
apt_elev−depth datum retires for cut-detected and light-touch alike
only if measurement supports it — scope to the sized path first,
STOP if light-touch needs its own ruling). WITH the safety stop the
lane itself flagged: the run TERMINATES at the first taxiway-family
pavement (extend the drop rule beyond runway-family) so a
never-meeting run cannot lay ramp over taxiways — twin it. REQUIRED
this time: ONE OTHH --patch-only interventional arm (blast radius is
every cluster) — 8/8 systems, ramp/road/wall table vs the shipped
reference, geometry deltas quoted; KCLT arm re-quoted (cliff gone,
corridor surfaced, mouth→DEM ≤ cap). One attempt (cap resets for the
re-ruled target). Fold-in: promote the twice-used kclt_site.py /
osmfeed.py readers into tools/ with INDEX rows + twins (RULINGS
7e90032) in the same lane.
