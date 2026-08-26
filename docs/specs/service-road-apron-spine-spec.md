# Service-road apron spines (Fable spec, 2026-08-25; implements
# RULINGS 2026-08-25h — the apron-chain fix)

Evidence: both round-2 lanes proved the back-edge ripple sites
(30.1274109,31.3970477; 30.1141206,31.4095574) are 100% welded
pavement stations whose alternating apron-vs-service values neither
the strip machinery (pavement-identity rules) nor the road lateral law
(scoped to ROAD_ROLES) may own. Apron -10582: 0.89 m sawtooth at
10.5%. The owner's model: a truck route along/through an apron is a
SPINE at the apron's cap — like a taxiway, but 1%.

## §1 Recognition

1. A service-road CENTERLINE segment that runs INSIDE an apron or
   ALONG an apron edge (the free-road / 25b contact notions — reuse
   their predicates, never a third contact test) is an APRON-SPINE
   segment. Segmentation is by contact: the same centerline may be
   apron-spine inside contact and a free road outside it.
2. Roles and census populations are UNCHANGED — the road stays a
   road; only its grading authority changes.

## §2 The spine

1. Apron-spine segments receive solved LONGITUDINAL PROFILES exactly
   as taxi centerlines do (phase A / the scaffold's anchor set), at
   the APRON cap (`APRON_MAX_GRADE`, 1%) — never the road cap, never
   DEM-follow. The 24c scaffold interpolation treats them as
   centerline anchors; the §1 chord-anchor law includes them as
   CENTERLINE targets (apron-only visibility, closer-wins, unchanged
   mechanics — the target set grows).
2. `REACH_NO_SERVICE_SPINES` STANDS: these spines join the GRADING
   scaffold, never the reachability band's route graph. A twin pins
   that the band's service exclusion is untouched (the airside-
   contamination regression class).
3. Seeding: the apron-spine segment's nodes seed from the spine
   profile (DEM-last); the mouth-fed DEM-follow applies only to the
   free-road remainder outside contact.

## §3 No alternation

1. Along a shared apron/road edge, the emitted surface carries ONE
   solved value per node — the spine-consistent apron-law solution.
   Both families' rings weld to it; the road-family DEM-hug is
   disabled within contact (25b's seeding clause generalises from
   edge-sharing to the §1 contact scope).
2. The alternation instrument: a named line when adjacent stations
   along an apron edge alternate authorship by >
   `EDGE_ALTERNATION_TOL_M` (0.25) — report-first, census-visible
   via sidecar count.

## Twins

(a) Synthetic apron with a through road: the road centerline gets a
    1% profile, apron vertices chord to it, membrane anchors on it.
(b) The same road outside the apron: 8% / DEM-follow unchanged.
(c) Band twin: reach_band_unified's service exclusion byte-identical.
(d) Edge twin: shared apron/road edge emits one value series — no
    sawtooth beyond materiality.
(e) Flag `O4_SERVICE_APRON_SPINE` default ON; OFF byte-identical.

## Acceptance (ONE HECA build, then SPJC/CYXY)

- Both ripple sites: station amplitude collapses (baseline 0.89-1.08 m
  sawtooth at 7-10.5%; target: monotone within the apron cap along
  the edge); apron -10582's worst edge ≤ apron-law values.
- Airside census: the alternation rows retire; report the class table
  honestly against the current frame (2,115 after the lattice
  un-blinding) — new spine-anchored chords may re-price rows; the
  bar re-founding stays with the owner.
- The owner road site (30.1023) unchanged (free-road remainder).
- SPJC/CYXY non-regression; alternation instrument counts reported
  everywhere.
- Attempt cap 2, materiality 0.01 m, STOP on second miss. No
  shared-repo writes, no timing claims.
