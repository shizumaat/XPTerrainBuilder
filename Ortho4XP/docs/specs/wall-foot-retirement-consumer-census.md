# Wall-foot retirement — consumer census (RULINGS 2026-09-01c, law 2026-08-30l)

THE RULING.  The §T5 wall FOOT retires.  The model is: the tunnel ramp is
the corridor floor; a **0.5 m** gap; then the wall band, whose INNER AND
OUTER edges both carry the SAME flat corridor-top (crest) elevation.
Nothing bridges the gap — the mesher's triangulation between the ramp
edge and the wall's inner edge IS the steep face.  `wall_gap_m` = 0.5.

Per 2026-08-30l this table rules EVERY reader of `tunnel_wall_foot` /
`TUNNEL_WALL_FOOT_REF` / `O4_RAMP_WALL_FOOT` BEFORE any consumer is
edited.  The population is enumerated by grep over the ref literal, the
constant, the env flag, and the role (`ROLE_RETAINING_WALL` — shared with
the face, so role readers are ref-blind and unaffected by construction).

## The region's single derivation site

Two emitters mint the band; both are edited, and nothing else mints a
foot.  Corollary (a) of 30l applies: the retirement lands at the two
derivation sites, not as N per-consumer vetoes.

| # | Consumer | What it reads | Ruling |
|---|----------|---------------|--------|
| 1 | `bridges._emit_facing_corridors` (§ band split) | emits `(foot, face)` band pair; face outer pair took a per-vertex DEM sample, inner pair the floor | **REWIRE** — ONE band from `_half + wall_gap_m` to the crest; both edge pairs carry the crest (one DEM sample per station) |
| 2 | `bridges.emit_wall_band` (`_foot_law`, `_region`, the boolean partition) | partitions the slit band into foot ∩ region / face − region | **REWIRE** — the single-band path only (`_band = _outer − _inner_region`); with no inner boundary the ramp-value overwrite is unreachable, so both edges already carry the §F1 crest |
| 3 | `bridges.TUNNEL_WALL_FOOT_REF` | the ref literal | **RETIRE** (deleted) |
| 4 | `bridges._RAMP_WALL_FOOT_ENV` / `ramp_wall_foot_enabled()` | §T5 gate | **RETIRE** (29f: a retired mechanism is deleted, not kept gated) |
| 5 | `bridges.reclip_wall_feet_against_faces` | foot-only last-word re-clip (face weld-bow yields the shelf) | **RETIRE** — the pass exists only to re-establish the foot/face partition; with no foot there is no partition |
| 6 | `pipeline` seam `11b_wall_foot_reclip` + its call | ledger seam around #5 | **RETIRE** — the seam names a pass that no longer exists (seam list is the passes that exist) |
| 7 | `bridges._WALL_BAND_REFS` (band re-clip, sibling-exclude register, fork bookkeeping) | membership | **REWIRE** — `("tunnel_wall",)` |
| 8 | `bridges._TUNNEL_COVER_REFS` (R10-2 clip, mouth-answer set) | membership | **REWIRE** — drop the member |
| 9 | `bridges` ruling-4 / wall-gate ref tuples (2 sites) | membership | **REWIRE** — drop the member |
| 10 | `adjacent_ground._CarveStructureRefs` + `O4_FOOT_IN_CARVE_REGISTERS` | call-time membership answering an env flag | **RETIRE** — `_CARVE_STRUCTURE_REFS` becomes the plain base frozenset (`tunnel_wall`, `tunnel_portal`, `bridge_abutment`) |
| 11 | `gap_fill._TUNNEL_BLOCKER_REFS` | gap-fill blocker set | **REWIRE** — `frozenset({"tunnel_wall"})` |
| 12 | `verification._MIDEDGE_EXCLUDE_REFS` | designed-vertical-storey exclusion | **REWIRE** — drop the member (the face keeps its exclusion) |
| 13 | `tools/tunnel_portal_acceptance.FACE_REFS` / `_BAND_REFS` | face-coverage + band populations | **REWIRE** — drop the member |
| 14 | `tools/tunnel_portal_acceptance._check_mouth_inventory` | per-side `foot L/R` columns, `feet=` total, canonical law "a wall AND a foot" | **REWIRE** — the per-side bar is the WALL BAND alone; foot columns and the `feet` total leave the inventory |
| 15 | `tools/tunnel_portal_acceptance._check_ramp_wall_gap` | adds foot ways to the "structure" side | **REWIRE** — the structure is the wall band; the gap law now reads ramp vs wall directly (the 0.5 m gap is unowned BY DESIGN) |
| 16 | `tools/tunnel_portal_acceptance._check_wall_top_flat` | excludes the `tunnel_wall_foot` SHELF node set from the crest frame | **REWIRE** — no shelf exists; every band node is a crest node, so the check reads the whole band (2026-09-01c: "wall_top_flat trivially satisfied by construction") |
| 17 | `tools/check_grade.py` / the census | prices by ROLE (`retaining_wall`), never by this ref | **NO CHANGE** — but the foot ROWS leave the census: a declared population change, quoted in the closing arm |
| 18 | `wall_foot_ll` (census law family, `tests/test_harness.py` comment) | the ADJACENT-GROUND wall-foot lateral-level family | **NO CHANGE** — different population; it has no reader of this ref |
| 19 | `Sources/` (Swift) / `o4_engine` wire protocol | — | **NO CHANGE** — grep-verified: the ref never crosses the wire |
| 20 | Twins: `test_round16_geometry_consistency` (§T5 ×6), `test_tunnel_integrity_round` (§T5 ×6), `test_tunnel_mouth_inventory`, `test_tunnel_fork_walls`, `test_tunnel_portal_acceptance` (shelf), `test_tunnel_ramp_keyed_walls`, `test_lemd_ramp_road_fidelity` | assert the foot exists / gate it | **REWIRE** — re-asserted against the new law (both edges one value per station; the gap unowned; no foot ref, flag or call site anywhere) |

## Interaction risks ruled here, before the edit

* **The gap is exactly the vertex-bucket tolerance.**  `SHARED_VERTEX_TOL_M`
  is 0.5 m and `vertex_bucket` is `round(x / 0.5)`, so two points EXACTLY
  0.5 m apart differ by exactly 1 bucket in IEEE-754 — the emit-time
  intern cannot merge the ramp edge with the wall's inner edge.  The
  post-solve T-vertex weld (`CONFORMANCE_TOL_M` 0.5) can still weld
  across it; that population is the `ramp_wall_gap` instrument's, it is
  ALREADY non-zero at 0.6 m (14 shared node ids on the round-3h arm), and
  the closing arm quotes the delta rather than predicting it.
* **`ramp_wall_annulus_owned`** (R16-2b, "no unowned annulus") is
  SUPERSEDED for the tunnel band by this ruling: the annulus is unowned
  BY DESIGN and the triangulated gap is the face.  The instrument keeps
  reporting it; its verdict is no longer a defect bar.
* **Pinch stand-down (ruling A) and per-arm fork walls** operate on the
  band, which survives with a simpler profile — kept unchanged.
