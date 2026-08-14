# S6 — RETIREMENT RESULTS (weld or gap)

Lane `lane/s6weld`. Control = the same lane worktree at `1faf907`
(pre-edit); the five control patches were built TWICE and reproduced
byte-identical `body_sha` both times, so the control arm is verified by
identity, not by narrative. VHHH's control was built in a separate clean
worktree `lane/s6ctl` at `1faf907`.

## 1. Retirement diff shape

One module constant `_WELD_OR_GAP = True` in `adjacent_ground.py`, three
consumers, +89/-1 lines (all but 4 of them the citation block):

| emitter | change |
|---------|--------|
| `emit_stacked_conflict_walls` | `if _WELD_OR_GAP: return 0` |
| `emit_groundside_terrace_walls` | `if _WELD_OR_GAP: return 0` |
| `emit_authority_retreat_walls` | non-carve vertices dropped from the retreat table (`coincident_top[i] = None`) — no run forms, the loser is not moved, `to_osm` emits the precedence winner at the shared node. The CARVE branch is untouched. |

No geometry is moved by the retirement — only faces stop being minted.

## 2. Emitted rows: the retired refs vanish, the exempt refs survive

| airport | `stacked_conflict_wall` | `authority_retreat_feather` | `groundside_terrace_wall` | `authority_retreat_wall` (CARVE, exempt) | `tunnel_wall` (exempt) |
|---|---|---|---|---|---|
| SPJC | 5 → **0** | 1 → **0** | – | – | 3 → 3 |
| SPLP | – | – | – | – | – |
| CYXY | – | – | – | – | – |
| HECA | 6 → **0** | 34 → **0** | 4 → **0** | – | – |
| KCLT | 8 → **0** | 7 → **0** | – | – | 6 → 6 |
| VHHH | 2 → **0** | 5 → **0** | – | **18 → 18** | 15 → 15 |

SPLP and CYXY are byte-identical across the arms (`body_sha` unchanged) —
a clean null control: the change touches only the retired families.
VHHH's 18 carve-branch walls surviving is the exemption firing for real.

## 3. Five-airport census, row-attributed (adjudicated)

| airport | before | after | Δ |
|---|---|---|---|
| SPJC | 526 | 532 | **+6** |
| SPLP | 60 | 60 | 0 |
| CYXY | 309 | 309 | 0 |
| HECA | 7067 | 7207 | **+140** |
| KCLT | 1292 | 1334 | **+42** |

**NET AIRSIDE −18. NET GROUNDSIDE +223.**

Every moved family:

| airport | family | before → after | side |
|---|---|---|---|
| SPJC | `within_shape` | 158 → 161 (+3) | groundside |
| SPJC | `strip_seam_tear` | 6 → 10 (**+4**) | **airside** |
| SPJC | `mid_edge_step` | 4 → 3 (−1) | groundside |
| HECA | `within_shape` | 3723 → 3974 (+251) | airside −22 / groundside +273 |
| HECA | `plane_gradient` | 11 → 9 (−2) | groundside |
| HECA | `strip_seam_tear` | 1 → 3 (**+2**) | **airside** |
| HECA | `transverse` | 2901 → 2894 (−7) | groundside |
| HECA | `lateral_contiguity` | 4 → 2 (−2) | groundside |
| HECA | `frontage_near_miss` | 86 → 69 (−17) | – |
| HECA | `vertex_to_edge_step` | 42 → 33 (−9) | groundside |
| HECA | `mid_edge_step` | 246 → 170 (−76) | groundside |
| KCLT | `within_shape` | 669 → 725 (+56) | groundside |
| KCLT | `adjacent_ground_tear` | 1 → 0 (−1) | airside |
| KCLT | `strip_seam_tear` | 27 → 26 (−1) | airside |
| KCLT | `transverse` | 504 → 496 (−8) | groundside |
| KCLT | `vertex_to_edge_step` | 2 → 3 (+1) | groundside |
| KCLT | `mid_edge_step` | 28 → 23 (−5) | groundside |

### Attribution

* **The step families FELL, they did not grow** (HECA `mid_edge_step`
  246→170, `vertex_to_edge_step` 42→33). The retired faces were
  themselves minting the steps the census read beside them — the walls
  were not only hiding disagreements, they were creating them.
* **The airside increases are the predicted exposure**, and they are
  narrow: `strip_seam_tear` +4 at SPJC and +2 at HECA. The retired
  `emit_stacked_conflict_walls` operated exactly on `graded_strip`
  vertices, so a strip-vs-strip level change that used to ship as a wall
  is now visible as the seam tear it always was. ROUTED to the
  graded-strip/strip-solve mechanism, not re-walled.
* **Net airside is −18** — an improvement overall, so no STOP.
* **The groundside `within_shape` growth (+273 HECA, +56 KCLT) is the
  weld's real cost** and the round's genuine finding: a losing lot now
  ADOPTS the winner's value at the shared node, and the level change it
  used to shed into a retreat band must instead be absorbed over the
  lot's own run. That is a SOLVE obligation. ROUTED to the groundside /
  stage-B solve (S1/S2 territory), per "a surviving step is a solve
  defect by definition now, never a re-wall candidate".

## 4. The three named sites

**(a) HECA seam tear `30.110467,31.409006` (188.5 %) — CLOSED.**
Before: 1 row, `strip_seam_tear graded_strip|graded_strip`, airside,
|de| 8.19 m, 188.52 %, ways −13012/−13014. After: **0 rows.** The
stacked-conflict wall at that site was itself tearing the strip pair (the
lower strip retreated away from its neighbour); with the wall retired the
two strips weld. Resolved BY the retirement.

**(b) HECA pad −10189 + ring −13851 building rows — CLOSED as censused;
the dossier's 2.92 m pair is not reproducible by id.**
`-13851` is a **node** id, not a way, and node ids are per-build — its
coordinates differ between the two arms — so the dossier's pair cannot be
re-joined by id (the canonical-identity-join trap: only the 11-decimal
lat/lon spelling carries). Measured directly instead: pad way `-10189`
(role `building`, 10 nodes) has **zero** shared-coordinate disagreements
with any other way, BEFORE and AFTER — there is no weld for S6 to mint at
that site. What did exist and is now gone: 14 `within_shape
building|building` airside rows on `-10189` at |de| 3.04 m, and 22 rows
in its neighbourhood → **0**. Those were the FEATHER faces, which carry
the loser's own role (`building`) and were judged under building law.
The dossier's 2.92 m figure is a different-frame measurement and ROUTES
back to S2's merge gate.

**(c) KCLT strip↔strip `35.2201431,-80.9635580` (7.18/7.28 m) — SURVIVES,
ROUTED.** 4 rows before, **4 rows after, identical to the milli-metre**
(7.280 / 7.210 / 7.210 / 7.230 m; `strip_seam_tear`,
`graded_strip|graded_strip`, airside; way −12583 against −12584/−12585/
−12586). No wall was ever involved, so the retirement neither helps nor
harms it. This is a pure interior shared-edge disagreement — under
weld-or-gap always a defect — between four graded strips sharing edges.
ROUTED to the graded-strip construction / strip solve. NOT welded here:
one strip disagreeing with three neighbours by 7 m is a solve outcome,
and minting a weld would be exactly the silent fix the charter forbids.

## 5. VHHH — the seawall control

Both arms built from the same shared corpus (`s6ctl` at `1faf907` vs this
lane), then measured with `tools/seawall_admission.py` — production's own
`seawall_breaklines` / `coastline_wall_admission` / `GRADED_COVERAGE_ROLES`,
no re-implementation.

| | before | after |
|---|---|---|
| `wall_lines` | 47 | **47** |
| `wall_m` | 54 734.3 | **54 734.3** |
| `coverage_km2` | 11.3562 | **11.3562** |
| `coverage_perimeter_m` | 124 483.7 | **124 483.7** |
| `longest_walls_m` | [6088.7, 4872.7, 4841.8, 4819.5, …] | **identical** |
| `rings_seen` / `rings_admitted` | 4968 / 4655 | 4961 / 4648 (−7) |

The 7 rings that left the admission set are exactly the 7 retired rows
(5 feather + 2 stacked-conflict). The admitted coastal wall did not move
by one metre. **The `retaining_wall ∈ GRADED_COVERAGE_ROLES` coupling
flagged in the inventory is measured INERT at VHHH**, and the coast still
walls. "Edges must not slope to water" holds.

## 6. Tests

Matched control, identical 30-file `blast --tests-for` selection:

* clean tree (`lane/s6ctl` @ `1faf907`): **1 failed, 792 passed**
* this lane, before twin work: 4 failed, 789 passed
* this lane, after twin inversion: see `tests_final.log`

`test_strip_heal_law_v4::test_the_pass_order_is_unchanged_by_the_law`
fails in BOTH arms — **pre-existing, not S6**. It reads
`inspect.getsource(pipeline.build_airport_pavement)` and finds none of the
three pass names, so `order` comes back `[]`; the passes now live in a
nested `_strip_reconcile_passes` the assertion no longer sees.
→ DEFERRED_VERIFICATION.

Three twins inverted to assert the retirement; the exemption twin
`test_a_carve_structure_keeps_its_wall` was left untouched and still
passes, which is the carve branch's proof.

## 7. Open / routed

| item | owner |
|---|---|
| HECA groundside `within_shape` +273, KCLT +56 — the weld's absorption cost | groundside / stage-B solve (S1/S2) |
| SPJC `strip_seam_tear` +4, HECA +2 (airside) | graded-strip / strip solve |
| KCLT site (c) 7.2–7.3 m strip↔strip shared-edge disagreement | graded-strip construction |
| Apron terrace joints (`emit_terrace_joint_faces`) — already inert at aprons via `O4_FABRIC_W2_RETIRE_APRON_TERRACES`; the residue is the solve-time PLAN, not an emitter | route-profile / apron terrace |
| `test_the_pass_order_is_unchanged_by_the_law` pre-existing failure | DEFERRED |
| Dead code the retirement exposes: `verification.py:3099/3163` pad-blend branch (`REF_PAD_BLEND`), unreachable since S5 | cleanup |
