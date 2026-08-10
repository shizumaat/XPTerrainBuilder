# FLAT-SITE mode (phase 2) — spec (2026-08-09, FROZEN; pre-ship mode)

Author: lead session (Fable). Charter: owner 2026-08-09 — the
simplification itself ("set the whole airport at the same flat
elevation (allowing for off pavement drainage and tunnel entrances)…
so no reseating is required") plus the same-day rulings: S1 spread
< 5 m qualifies a candidate; with nonzero spread the RUNWAYS keep
their CIFP-absolute profiles and the flat elevation applies
off-runway. Phase 1 (the detector) is landed and swept. Rulings:
docs/RULINGS.md ("Instrument truth is law"; "CIFP thresholds absolute
for v1"; "Flat-site S1 spread and the flat test set"; PRE-SHIP MODE).

## 1. The one design idea

FLAT-SITE mode is a **DEM SOURCE SUBSTITUTION, not a new solve
path.** When the detector returns `flat_candidate` **or
`flat_declared`** (the detector spec v3's owner-declaration verdict —
the two are equivalent to this mode; `not_flat`, `lidar_credible`,
`no_data` all take the normal path untouched), DEM prep manufactures
a SYNTHETIC CONSTANT INSET at

    Z0 = the detector's threshold-consensus elevation (CIFP mean)

over the airport extent (the detector's own `(pavement ∪ boundary) ⊕
margin` region) and feeds it through the EXISTING airport-inset
feathering machinery — the same path a Copernicus/LIDAR inset takes
today, feathered into the surrounding base raster by the code that
already does exactly that at every inset airport. Everything
downstream is UNCHANGED and runs against a truthful flat input:

* Runway profiles stay CIFP-absolute (standing ruling) — at zero
  spread they come out flat at Z0 by construction; at spread < 5 m
  they keep their real gradients and the solver's existing junction/
  strip machinery reconciles the (sub-cap, by arithmetic: < 5 m over
  runway-scale runs) transitions to the Z0 field around them.
* Off-pavement drainage down-slopes, adjacent-ground blends, OLS,
  boundary — unchanged laws, now shaping from a flat truth.
* Basins and tunnel entrances cut below Z0 exactly as today; the
  basin `R_est` becomes exactly Z0 (estimate error → 0; the safety
  margin stays and is harmless); the anchor-inside rim-flush bake
  target becomes exactly Z0.
* The reseat-threshold law then finds sub-1 m deltas everywhere a
  pack was authored flat (OTHH pack median 4.00 vs Z0 3.96) —
  expected OTHH outcome: pack modification limited to the six
  anchor-inside drainage facilities' members, nothing else.

## 2. Mechanism

1. **Ordering.** The detector runs INSIDE DEM prep, before the tile
   DEM is finalized: classify on the REAL surface (S2 must read the
   honest DEM), then, iff `flat_candidate` and the gate is on,
   overlay the synthetic inset. Per airport — a multi-airport tile
   applies it only to its flat candidates (the inset machinery is
   already per-airport).
2. **Gate.** `FLAT_SITE_MODE` default **ON** (env `O4_FLAT_SITE_MODE`
   =0 kills). Config beside the detector constants.
3. **Provenance.** The synthetic inset stamps
   `dem_inset_provenance` with a `synthetic_flat_site` entry carrying
   Z0, the detector verdict record, and the extent — a flat-mode
   patch and a real-DEM patch are different frames and every census/
   comparison reader must be able to see which it holds. `site_class`
   in the sidecar (phase 1) already carries the verdict.
4. **Water.** The feather ring must not lift water: the existing
   inset bake's water/bathymetry handling applies verbatim (OTHH's
   real Copernicus inset already feathers against the same lagoon).
   No new machinery; if the existing path proves not to protect the
   shoreline here, STOP and report — do not invent a mask.
5. **No second flatten.** apt_smoothing and any DEM smoothing apply
   to the substituted surface as to any other (they are no-ops on a
   constant); nothing else special-cases flat mode. One substitution
   point, everything else blind to it.

## 3. Constraints (violations are STOP-and-report)

1. `not_flat` / `lidar_credible` / `no_data` airports byte-identical
   to pre-change behavior — the degeneracy gate; `O4_FLAT_SITE_MODE=0`
   restores pre-change behavior everywhere.
2. CIFP-absolute runway thresholds bind exactly as today (the mode
   must not move a runway node off its lawful profile).
3. No writes to the shared corpus: the synthetic inset is derived
   in-run (it is arithmetic, not data) — it must NOT be cached into
   `Elevation_data` (a synthetic raster in the corpus would poison
   the real-DEM path and the refresh ledger's meaning).
4. The pack is never modified by the mode itself; reseat decisions
   remain the threshold/basin laws' (expected to collapse to the
   basin class at OTHH, but that is an OUTCOME, not a wired rule).

## 4. Tests (pre-ship: these files only, run once)

Synthetic fixtures: flat_candidate + gate → DEM samples over the
extent == Z0, feather ring monotone to base, provenance entry
present; not_flat / lidar_credible / gate-off → DEM prep byte-
identical; spread > 0 fixture (thresholds 2 m apart) → runway profile
nodes keep CIFP values while off-runway pavement solves at Z0; water
row in the feather ring unchanged. Sidecar/provenance keys registered
where the harness twins require.

## 5. Acceptance and delivery (pre-ship)

ONE OTHH patch-level harness build (the one build this integration is
allowed — a DEM substitution is exactly the sim-visibly-broken risk
class): confirm off-runway pavement nodes ≈ Z0 (±0.05 m), basin
records show `R_est == Z0`, patch sidecar carries the provenance.
Then the lead merges, freezes the engine, packages the app; the
OWNER'S IN-SIM PASS IS ACCEPTANCE (expected look: the whole field at
one level, drainage pits and tunnel mouths cut into it, objects flush
with zero non-basin pack modification). Ledger line to
docs/DEFERRED_VERIFICATION.md (battery patch-level effects unproven
beyond the degeneracy tests; the feathered shoreline unmeasured
outside the owner's look).

## 6. Budget

One Opus implementer; unit tests once; ONE OTHH patch build; engine
freeze + app package by the lead. Hard cap 2 patch builds.
