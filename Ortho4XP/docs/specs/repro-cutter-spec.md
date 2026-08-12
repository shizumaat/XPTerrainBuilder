# The repro cutter — a defect site becomes a seconds-fast fixture

Spec: 2026-08-12, FROZEN (Fable lead). Lane: **reprocut** (dispatch
after sweeptools merges — shared tools/INDEX churn). Pre-ship mode as
amended; owner directive 2026-08-12 (the fast fix loop). Deviations
STOP-and-report; cap 2.

## The law

`Ortho4XP/tools/repro_cut.py ICAO --coord LAT LON --radius M
[--patch PATH]` extracts, from an EXISTING emitted patch (default:
the shipped artifact in the data repo — the owner's build; never
triggers a build itself) plus the on-disk inputs, a SELF-CONTAINED
fixture directory:
* the shapes whose rings intersect the disc (plus their welded
  neighbours to one ring of adjacency — chains must stay closed),
  re-anchored, with roles/sidecar slice carried;
* the DEM window (from the same source the build frame records),
  saved lane-local, never a corpus write;
* the OSM/apt.dat slices the included shapes reference (runway
  context included when a runway ring intersects — laws need it);
* a `repro.json` manifest: source artifact sha, coordinate, radius,
  the DEFECT PIN — the measured number(s) the fixture must reproduce
  (caller-supplied, e.g. "band_excess worst 17.23 at (2049,712)" or
  "pad -10171 at 86.71 vs DEM 104.7").
And a runner: `repro_cut.py --run FIXTURE_DIR` executes the
auto_patch pipeline on the fixture ONLY (standalone DEM path,
compute_elevations=True) and reports the pinned measurements beside
the fixture's fresh values — REPRODUCED / DIVERGED per pin. Target
wall time: seconds to ~1 min for a 500 m disc (quote it).

Honesty rails: a fixture that cannot carry a law's context (a
tile-boundary effect, a cross-airport claim, mesh-side classes that
need Triangle4XP) REFUSES with the reason — a divergent fixture is
never silently accepted as a repro; the pin table is the contract.
Mesh-side defects (the R18-1b class) are OUT of v1 scope — patch/
solver classes only; say so in the tool's INDEX row.

## Tests
Twins: extraction closure (chains closed, sidecar slice valid,
census runs on the fixture); pin reproduction on a KNOWN case —
build the fixture from a checked-in mini-patch and assert
REPRODUCED; the refusal rail. Directly-covering files once,
ledgered.

## Acceptance
One real demonstration: cut the KSTJ inversion site (or a current
live defect) from the shipped artifact, run the fixture, show the
pin REPRODUCED and the wall time; INDEX row same commit.

## Bookkeeping
Cap 2; heartbeat; DEFERRED lines. Cross-refs: RULINGS 2026-08-12
(owner-artifact baseline), build_target_osm.py (the near-fit —
extend its cutting idioms where they fit rather than duplicating),
[[build-budget-discipline]] (artefacts → replay → unit tests → ONE
airport).
