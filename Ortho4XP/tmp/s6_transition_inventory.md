# S6 — TRANSITION-MACHINERY INVENTORY (weld-or-gap)

Lane `lane/s6weld`, swept at `1faf907`. Authority: RULINGS 2026-08-13
"TRANSITION MACHINERY RETIRES — WELD OR GAP"; staged-solve spec §"S6".
This table is the pre-retirement census of the emitter family. Nothing is
retired in this commit.

## A. Interior wall / terrace / feather / blend emitters

| # | emitter | file:line | gate | role / ref emitted | call site | verdict |
|---|---------|-----------|------|--------------------|-----------|---------|
| W1 | `emit_stacked_conflict_walls` | `adjacent_ground.py:2680` | none (`O4_*` gate deleted); per-face `runway_strip_wall_keepout` + `service_corridor_wall_keepout` drops | `retaining_wall` / `stacked_conflict_wall` | `pipeline.py:7002` | **RETIRE** — interior strip-vs-authority level conflict |
| W2a | `emit_authority_retreat_walls` (carve branch) | `adjacent_ground.py:3240`, `_face_spec` `:3411-3412` | `if any(_carve[i] for i in run)` — `_carve_structure_zone(layout)`, `_CARVE_STRUCTURE_REFS = {"tunnel_wall","tunnel_portal","bridge_abutment"}` | `retaining_wall` / `authority_retreat_wall` | `pipeline.py:7025` | **KEEP** — carve structures, owner ruling 2026-08-07 ("walls exist only at carve structures"), same physical-structure class as seawalls |
| W2b | `emit_authority_retreat_walls` (THE FEATHER) | `_face_spec` `:3416` | else-branch of the same `if` | *loser's own role* / `authority_retreat_feather` | same | **RETIRE** — the named feather path |
| W3 | `emit_groundside_terrace_walls` | `adjacent_ground.py:3585` | `_GROUNDSIDE_TERRACE = True` (`:3524`) | `retaining_wall` / `groundside_terrace_wall` | `pipeline.py:7044` | **RETIRE** — interior lot-vs-ribbon and lot-vs-lot terraces |
| W4 | `emit_terrace_joint_faces` | `apron_terrace.py:3754` | `if plan is None or not plan.joints: return 0`; the PLAN is gated by `fabric_sparse.terraces_declined` → `O4_FABRIC_W2_RETIRE_APRON_TERRACES` (default ON) | `retaining_wall` / `apron_terrace_joint` | `pipeline.py:7064` | **ALREADY RETIRED at aprons** by W2; residue is solve-stage (the plan), not an emitter — routed, not cut here |

## B. Already-dead members of the family (recorded so absence is a decision)

| emitter | ref | why dead |
|---------|-----|----------|
| `_emit_apron_walls` `adjacent_ground.py:8100` | `adjacent_ground_wall` | `O4_FABRIC_W2_RETIRE_APRON_EDGE_WALLS` default ON (`:8184`) |
| `_emit_airport_boundary_shape` `boundary.py:1007` | `airport_boundary` | `ADJACENT_GROUND_LAW_ENABLED = True` → `finalize.py:377` skips |
| `_emit_boundary_dem_bridge` `boundary.py:1692` | `boundary_dem_bridge` | same, `finalize.py:476` |
| pad blend annulus `object_pads.py` | `object_pad_blend` | retired by S5 (`1faf907`) |

## C. NOT transition machinery (kept, with reasons)

* `blend_cross_strip_seam_steps` (`adjacent_ground.py:2221`, `pipeline.py:6976`)
  emits **no shape** — it re-levels vertices at strip↔strip steps. That IS
  the weld half of weld-or-gap; retiring it would remove the mechanism the
  ruling asks for.
* `_heal_emitted_band_tears` — collapses pinch edges; a weld, not a step.
* raster feather `O4_Airport_Elevation_Insets.py:8158` (`feather_m`) — DEM
  inset shaping, Ortho4XP's own drape, explicitly out of the patch frame.
* tunnel/bridge collar lerps (`bridges.py:11174`, `:11765`) — value math,
  no shape.
* carve walls `bridges.py` (`tunnel_wall`, `bridge_wall`) — R19-4 exempt.

## D. SEAWALL EXEMPTION — proven by gate, not by geometry

The seawall family shares **nothing** with the interior family: not a
function, file, role literal, ref literal, gate, or output artifact.

| | interior family | seawall family |
|---|---|---|
| module | `src/auto_patch/` | `src/O4_Vector_Map.py` only |
| output | `BuiltShape` appended to `layout.shapes` → patch OSM | `vector_map.insert_way(coords, SEAWALL_MARKER)` → tile vector-map breaklines |
| identity | `role="retaining_wall"` + `ref` string | attribute bit `SEAWALL_MARKER = dico_attributes["INTERP_ALT"]` (8) |
| gate | `fabric_flags` W2 / unconditional | `constant_inset_area` / `connected_cluster_inset_area` / `airport_island_land` / `curve.intersection(water_area)` |

`grep -ni 'sea\|water\|coast' src/auto_patch/adjacent_ground.py` → **0 hits**.
`grep -rn 'seawall' src/auto_patch/` → **0 hits**.
The interior emitters are structurally incapable of knowing where water is.

**ENTANGLEMENT VERDICT: NONE.** No emitter serves both duties, so no split
is required and no geometry guesswork is involved.

### The one real coupling (consumer, not emitter) — must be measured

`O4_Vector_Map.py:143`

```python
GRADED_COVERAGE_ROLES = frozenset(SEAWALL_PAVEMENT_ROLES | {
    "graded_strip", "tunnel_trench", "tunnel_ramp", "retaining_wall",
})
```

read at `:2457` to build `graded_area`, threaded into
`coastline_wall_admission` (`:1802`) and `airport_island_land` (`:346`).
Retiring interior `retaining_wall` rows therefore **shrinks the seawall's
admission polygon** wherever a wall ring was the only graded coverage at an
island edge. `SEAWALL_PAVEMENT_ROLES` already admits runway/apron/building/
`object_pad`/`groundside_pavement`, so the exposure is narrow — but it is
real and is what the VHHH control arm exists to measure. The frozenset is
**left unchanged** (dropping `retaining_wall` from it would shrink admission
further, and `tests/test_r17_seawall_admission.py` twin-asserts it).

## E. Census row identities for attribution

Refs that must VANISH: `stacked_conflict_wall`, `authority_retreat_feather`,
`groundside_terrace_wall`.
Refs that must SURVIVE: `authority_retreat_wall` (carve only), `tunnel_wall`,
`bridge_wall`, `tunnel_portal`, `bridge_abutment`, and every seawall
breakline (no ref — attribute bit 8).
Law families expected to GROW as walls stop hiding disagreements:
`vertex_to_edge_step`, `mid_edge_step`, `stacked_nodes`,
`adjacent_ground_tear`, `strip_seam_tear`, `cross_shape`.
Law family expected to fall to 0: `wall_in_runway_strip`.
