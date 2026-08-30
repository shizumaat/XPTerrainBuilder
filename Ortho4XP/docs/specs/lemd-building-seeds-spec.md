# LEMD round addendum — building-seed defects (items 3 + 4)
# (owner sim read of 1.0.269, 2026-08-30; joins lemd-bridge-pit-spec.md,
# same lane, same ONE closing LEMD build)

Probed on the owner's patch
(`XPTerrainBuilderData/Patches/+40-010/+40-004/LEMD_auto.patch.osm`,
engine 1.50.1713, built 2026-08-29 23:19). SITE-FIRST.

## Item 3 — building1..building7 are not buildings; they cut road + taxiway

Sites: ways -10001..-10007 (shapeIDs 0–6, refs building1..building7),
each a 7-node ring, flat altitudes climbing sequentially 570.78,
570.91, 571.52, 571.64, 572.25, 572.37, 573.08 — a row of small pads
marching west along ~lat 40.4614 from -3.5398 to -3.5416. building1
node -1 (40.461401969,-3.539808940) is COINCIDENT (0.00 m) with
taxiway junction way -10138 (shapeID 137, 398 nodes, 568.99–588.65);
graded_strips 2220/2224/2225/2227/2232 lace between them.

Owner read: these are NOT buildings, and their flat pads cut across a
road and a taxiway. The segmented geometry (seven ~15–20 m rings in a
line, ~0.1–0.7 m altitude steps) reads as one linear elevated feature
— bridge/viaduct segments or similar — extracted from the DSF object
source and misclassified as building footprints.

Attribution first: find the DSF source objects (the building-seed
pipeline's DSF extraction; the dump cache serves reads) — what are
these objects in the Aerosoft package, and what let them pass the
building filter? Then the fix at the correct level: the CLASS of
object must not seed building pads (a filter/classification fix in the
seed pipeline), not a per-ID suppression list. Their pads, and the
grading they imposed on the junction/graded strips, disappear from the
emitted patch.

## Item 4 — visible buildings with no pads (floating) at three sites

Sites: 40.4536785,-3.5672468; 40.4525274,-3.5672629;
40.4524988,-3.5696071 (south field area). Probed: the emitted patch
has ZERO ways within 60 m of all three — no pad, no apron, nothing;
the sim shows buildings there, floating.

Owner asks explicitly: double-check whether these buildings are in the
LEMD package we parse. Attribution: (a) are there DSF objects and/or
apt.dat rows at these sites in `Airport_mod_cache/Aerosoft - LEMD
Madrid - 1 - Airport` (and the mesh package)? (b) if present, why did
the seed pipeline drop them — inclusion boundary, cluster threshold,
absorption ("199 DSF + 27 OSM" style accounting at HECA suggests
cluster logic), or coordinate/tile filtering? (c) if genuinely absent
from the package we parse, report that finding — the answer may be
"they come from another scenery layer", and that is a lawful close
with evidence quoted (name which pack places them).

Fix only what attribution supports: seeds minted for real in-package
buildings at these sites with pads at lawful ground; no speculative
pads for objects we cannot attribute to the parsed package.

## Acceptance

Joins the bridge+pit round: same lane, ONE closing LEMD build + census
covers all four items. building1–7 pads gone and the crossing
road/taxiway rows lawful at their sites; the three south-field sites
either padded (in-package attribution) or closed with the
which-package evidence. LEMD law-true census not worsened beyond
attributed seed changes. Below-bar = STOP with residual quoted.
