# Classification round: lateral-contiguity law, coverage discriminator,
# drainage lockstep

Fable spec, 2026-08-02. Implements the owner-finalized lateral-contiguity
grade law (RULINGS.md `0b4472d`) plus two batch rulings. Lines against
`0b9efaf`. Evidence dirs: `gsclass/` (the 41-shape class + holes),
`fixbatch/` (the H1 probe chain + §B residual), `drainspine/`.

## §1 Scorer service-adjacency feature (gate `O4_SCORER_SERVICE_ADJ`, "0")
Scorer v2 gains a service-adjacency probe beside `apron_edge_bound`
(pavement_scoring.py:1690-1710): substantial shared boundary (≥20 m or
≥20% of perimeter — name constants) with `service_road`/
`service_junction` + road-width dimensions (reuse `free_road_subsegments`'
width semantics) weights toward CLASS_SERVICE. Fix population: the HECA
41-shape class (`gsclass/` shapeIDs; 29 road bodies + 12 slice shavings —
the shavings should merge/absorb, not re-role, note per shape). Report
(do not redesign) the demotion-irreversibility fact (`_ENACT_ROLES`
excludes groundside — a wrong demotion is final within a build).
Pre-reg: the owner's site (30.106209, 31.4002032) classifies service
road; per-airport role-count deltas quoted; no airside role changes.

## §2 Lateral-contiguity cap + absorption (gate `O4_LATERAL_CONTIGUITY_LAW`, "0")
The law verbatim (RULINGS `0b4472d`): free road (genuinely unpaved both
sides, gap = any real gap, adjacency = literal shared boundary in the
sliced arrangement) → service cap, axial grading; at any station the
laterally-contiguous paved cross-section takes the STRICTEST cap present
(closure across side-sharing only, NEVER through end-connections/mouths);
per-segment via the existing mouth-cut machinery — VERIFY what exists
(`free_road_subsegments`' cross-section probe, groundside mouth cuts)
and reuse it; ABSORPTION preferred (merge laterally-contiguous road
stretches into the adjacent surface — fewer nodes; the free-road
ruling's absorption is the model); runway-strip footprint law supersedes
inside strips. If the mouth-cut machinery cannot express the per-segment
closure, STOP and report the gap — do not invent new segmentation.
Pre-reg: the ring-road/apron thought-test encoded as a unit test (all
touching → one strictest-cap surface; two aprons + connector → only the
free between-segment road-capped); the owner's site's corridor grades at
its lawful cap; census deltas quoted both frames.

## §3 The needle-collapse source guard (gate `O4_NEEDLE_SOURCE_GUARD`, "0")
Fable ruling: `_collapse_ring_needles` (pipeline.py, `O4_PRESOLVE_CLEAN`
block) may drop an apex ONLY if the dropped area does NOT cover source
pavement — the discriminator replaces area entirely as the real-vs-
artifact test (`_NEEDLE_MAX_DROP_AREA_M2` stays as a secondary bound).
Source union is available in the pipeline; the probe chain in
`fixbatch/` reproduces H1. Pre-reg: H1's 90.8 m² + the 7-piece/298 m²
population survive to emission (HECA flag-worthy holes 4 → 0 with the
coverage check on — H2 stays, it is a source-data gap, distinguish);
the KBNA apex-artifact class still collapses (the code's recorded
289/290 case as a test); no other geometry changes.

## §4 Drainage second-parent lockstep
The §B residual 4: emitter and validator choose different SECOND
bounding parents. Unify parent selection INTO the law function
(`drainage_spine_envelope`) so both readers get the same parent set by
construction. Pre-reg: HECA at/above-lower 4 → 0; no other spine moves.

## Acceptance
Gate-off byte identity (CYXY `dcebb6ff…`, SPLP `c2316222…`, HECA
repaired `9a49cbce…`); all-gates-on arms HECA+HEAZ+CYXY+SPLP with both
frames quoted; the five owner reference sites re-read; suite green over
the same 23 reds; exclusive build-time per the ledger tool (§2 touches
phase-1 — watch it); per-section pre-registrations written before each
gate-on build. FOREGROUND builds only (memory: background builds land
on efficiency cores).

## Out of scope
Quarantine round 2 (next; includes the §C break-growth attribution);
ruleset phases; the missing-reg law rounds; the transverse solver-side
law.
