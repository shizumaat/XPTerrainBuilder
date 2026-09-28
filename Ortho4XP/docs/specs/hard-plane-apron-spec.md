# §42 (1b) THE HARD-PLANE APRON (owner RULINGS 2026-09-27a (5); issue #20) — lane `nlwfends`

Short spec, written by the implementing lane on the orchestrator's brief; a Fable
review is OWED before the owner's sim read (CLAUDE.md: Fable writes specs).

**(1) The declaration.** A pack object whose every triangle stands within
`[load] draped_y_tol_m` of Y = 0, with at least one `ATTR_hard` solid triangle and
no draped layer group, is PAVEMENT (`airport/object_pavement.hard_plane_footprint`,
key `[load] object_pavement_hard_planes`, now **true**). Its bodies take the pavement
id prefix `dsf:objpavhp` (a sub-prefix of `dsf:objpav`, so every §42 gate reads it as
any object pavement). NLWF `pavement/vele_apron.obj` (1,499 m²) is the only resource
in the battery that qualifies (lane `nlwf` scan of 11 packs). The ruling's "the
airport's only apron" is NOT coded as a gate: the classify §42 (2) rule already lets a
mapped page's evidence govern where a body meets one.

**(2) The outline.** The object's corner fillets (0.5–0.6 m chords) are not data: the
footprint is simplified at half the identity spacing
(`emit.identity.min_distinct_spacing_m` / 2, topology preserved) before placement.

**(3) The level.** X-Plane draws a hard OBJ LEVEL at its anchor; it cannot tilt.
So the ground under a hard plane is ONE level (`constraints/hard_plane.hard_plane_level`:
one `Flat` over every ring/hole vertex of every `dsf:objpavhp` face, the vertices it
shares with a RUNWAY-family face left out — the runway is fixed first by §20b and is not
level to the millimetre). The §09p (3) body datum does NOT apply: `solve/design` drops
these vertices from every body's DEM plane fit, exactly as it drops a fronting pad's
(10l). The level is set by the frontage through the ordinary airside rows (no-step,
within-shape across the shared runway edge). No DEM datum.

**(4) The pads.** Unchanged law: a pad that fronts pavement takes the frontage's level
(10l / 10k-1 (A)); a pad on the plane therefore takes the plane's level.

**(5) Consumer census (08-30l).**

| # | consumer | reads | RULE |
|---|---|---|---|
| H1 | `airport/object_pavement` | the OBJ | EDITED: marks `hard_plane`, simplifies the outline |
| H2 | `airport/load` | bodies → `Pavement` ids | EDITED: `dsf:objpavhp{k}` for a hard body |
| H3 | `classify/sources` (§42 (2)/(3) gates) | `dsf:objpav` prefix | UNAFFECTED (sub-prefix) |
| H4 | `constraints/hard_plane` (new) | hard faces | NEW: the one `Flat` |
| H5 | `solve/design` 9b body datum | apron bodies | EDITED: hard vertices leave the plane fit |
| H6 | `solve/rows._reduce` | `Flat` groups | UNAFFECTED: one column |
| H7 | pads / 10l pad level rows | frontage | UNAFFECTED |
| H8 | census `hairline_pair`, `pad_airside_renode` | emitted rings | UNAFFECTED CODE (measured below) |

**(6) Measured (NLWF, harness `nlwfends_c0` → `nlwfends_h2`, same tree otherwise).**
Apron (hard plane) faces: control not graded (DEM 5.7–12.8 m) → **5.03 m level**
(junction parts of the plane 4.88–5.03 m where they meet the runway edge); runway
frontage vertices 4.86–4.98 m (plane stands +0.05…+0.17 m over them, residual
reported, see (7)); terminal pad `building1` 15.89 → **5.03–5.10 m**; v2 verify 3 rows
(= control). Census: control 9 / 0 → key ON, datum on (lane `nlwf` r2) 181 / 78 →
this rule before the outline fix 98 / 1 → after it **13 / 1** (4 shore hairlines as
before, 8 hairlines at exactly the 0.5 m spacing where the plane meets the pad, 1
`pad_airside_renode` at -14.311201, -178.068961: the pad corner on the plane's edge).

**(7) Deviations / open.** (a) An explicit hard row "level = mean(frontage)" was tried
and is NOT enforced by the staged solve (0.090 m residual with "0 hard violated"); it
is not minted, the residual is reported. (b) The cliff behind the pad to raw DEM is the
owner's sim read (27a (5)). (c) The one `pad_airside_renode` row is not fixed.
