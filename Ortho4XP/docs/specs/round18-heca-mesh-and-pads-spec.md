# Round 18 — HECA: the unflooded mesh cell and the phantom building pads

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r18heca**. Pre-ship
mode (docs/RULINGS.md); deviations STOP-and-report. Owner report +
hecarecon attribution (this session; artifacts `/tmp/harness/
hecarecon.*` + session-scratchpad census/probes). Owner rulings
2026-08-11b: evidence gate ruled; HECA mod-cache refresh authorized
(already run by the lead — the corpus is regularised).

## Carried attribution (measured — do not re-derive)

* **The hill (30.1170578, 31.4098155) is MESH-side; tile NOT stale.**
  Patch smooth (apron −12420, 86–89 m), mesh = patch at every ring
  vertex. `include_patches` seeds INTERP_ALT once per polygonized
  patch face (`O4_Vector_Map.py:1955–1982`), but OSM road ribbons
  carry the same marker (`:1186`) and BLOCK the flood — the 339k m²
  face is cut by 40 road lines into 38 cells; the seed sits in cell
  #9, the owner's point in cell #3 whose single interior vertex
  keeps DEM (99.33 m in an 86 m apron). Class: 89 free interior
  vertices >3 m above their 8 nearest patch nodes tile-wide (next
  worst +10.27 @30.1148799,31.4087224, +8.68 @30.1153363,31.4081113).
* **The groundside cuts are phantom pack pads.** Four flat pads
  11–18 m below their own ground (building172 −10171 14,672 m² @
  86.71 over 104.7 DEM; building176 −10174; building177 −10175;
  building186 −10184) — ZERO OSM buildings under them; footprints
  from the Tai Models pack's object rings (apron slabs, barriers,
  fuel trucks, buses; 45 rings >5,000 m², largest 61,315 m²).
  Admission: `dsf_reader.py:1537+ _compute_dsf_object_buildings`
  (25 m solid reach only; `DSF_OBJECT_CONNECTOR_PREFILTER=0`,
  `DSF_OBJECT_MAX_STRUCTURE_SPAN_M=0`, both default-OFF "pending");
  fusion: `terminals.py:859` (2 m gap bridge) + `:795` (110 m
  outline fill); leveling: `PAD_HOST_PAVEMENT_LEVEL` drops them to
  the host apron median. building190 (142,318 m²) contains the real
  204 m² ATC tower. The census sees NONE of this (0 law rows on the
  18 m cut) — instrument boundary, recorded.

## The laws

### R18-1 EVERY ROAD-CUT SUB-CELL GETS ITS SEED (mesh side)
**BLOCKED until the lead messages that `O4_Vector_Map.py` is free
(a concurrent lane edits it) — implement R18-2 first.**
In `include_patches`' face seeding: the polygonize set that defines
seed cells must include the encoded INTERP_ALT road geometry (or
equivalently: seed every road-cut sub-cell of each patch face) so
no sub-cell of a patch face is left to DEM. Follow the existing
seeding idiom; no new marker semantics. Acceptance (tile mesh
steps 1–2 in a lane-local build dir): mesh at the owner's point
86–89 m; the 89-vertex >3 m class → 0 (quote survivors with
geometry if any are legitimate, e.g. genuinely unpatched holes);
mesh = patch at ring vertices unchanged; one non-HECA control tile
face count unchanged.

### R18-2 A BUILDING PAD NEEDS BUILDING EVIDENCE (owner-ruled)
A DSF-object footprint ring may seed a building pad ONLY with
building evidence: an intersecting OSM building/terminal/hangar
footprint, OR a vertical-structure test on the object's own solid
geometry (a real building is TALL where an apron slab/barrier/
vehicle is not — derive the test from the pack geometry the reader
already parses; propose the threshold from the measured population
and quote it). Rings failing the gate never enter facade
clustering. The two default-OFF defences: MEASURE what each would
have caught on HECA's 817 rings, then arm at the values the
measurement supports (or report why not) — this is the in-round
ruling the owner authorized. PAD_HOST_PAVEMENT_LEVEL itself is
untouched (correct for real pads).
Acceptance: HECA pads 172/176/177/186 GONE (no phantom cuts at the
owner's two coordinates — mesh/patch reads ground-conformant
there); the real ATC tower keeps lawful treatment (building190's
verdict quoted either way); HECA's REAL terminal buildings keep
their pads (count before/after, evidence source per survivor);
OTHH control: object_pad population and 8/8 tunnel systems
unchanged (different machinery — prove it, don't assume it);
census Δ0 beyond the floor on both.

## Tests
Twins, mutation-checked: gate refuses a footprint with no OSM
building and no height; admits with either; span/prefilter twins at
the armed values; R18-1 (when unblocked): a synthetic patch face cut
by a road floods both sub-cells. Directly-covering files once,
ledgered. Pre-existing failures matched at base out of scope.

## Bookkeeping
Cap 2, STOP on second miss; `.progress` heartbeat; DEFERRED lines
per skip; tripwire only. The census's blindness to both classes
(mesh-side defects; pad-vs-own-ground cuts) is RECORDED as an
instrument boundary — a pad-cut instrument is a ship-gate question,
not this round. Cross-refs: RULINGS 2026-08-11b, hecarecon report,
[[shared-datum-pack-authoring]] (every heavy pack is first contact).

## AMENDMENT 1 (Fable lead, 2026-08-12, on the R18-1 refutation) — the interior vertex takes the face's value

Interventionally measured: all 3,204 faces in HECA's coverage are
seeded (the sub-cell pass adds 0), the hill stands at 98.05 m, and
the mechanism is `O4_Mesh_Utils.post_process_altitudes` assigning
each INTERP_ALT vertex ITS OWN carried altitude
(`vertices[6v+2] = vertices[6v+5]`) — for a free interior Steiner
vertex inside a patch face that is the DEM, not the patch.

* **R18-1b:** an INTERP_ALT-treated FREE INTERIOR vertex (not on any
  patch ring / constrained edge carrying a patch value) takes its
  altitude INTERPOLATED FROM THE PATCH-VALUED vertices of its
  constrained face — planar/harmonic across the face interior,
  deterministic, O(vertices), no new marker; ring/constrained
  vertices byte-unchanged. Implementation freedom on the mechanism
  (mesh-side interpolation vs .alt-build authoring) — the LAW is
  that no vertex inside a patch face answers with DEM.
  Acceptance: mesh at 30.1170578, 31.4098155 reads 86–89 m; the
  free-interior class (currently 54 >3 m) → 0 with any legitimate
  survivors named; mesh = patch at ring vertices unchanged; cost
  within the tile-budget tripwire.
* The landed sub-cell seeding stays (harmless, additive, twinned —
  0 seeds on this tree, insurance on others). The two
  `run_tile_mesh_only.py` trap fixes stay (install paths; cache
  redirects) — DEFERRED lines note them.
