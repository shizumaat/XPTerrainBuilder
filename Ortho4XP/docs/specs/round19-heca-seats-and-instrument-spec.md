# Round 19 — HECA: seats meet their hosts, and the instrument sees every edge

Spec: 2026-08-12, FROZEN (Fable lead). Lane: **r19heca**. Pre-ship
mode as amended; owner-artifact baseline; consolidated acceptance is
the lead's. Deviations STOP-and-report; cap 2 per target. Attribution
paid by the hecarecon2 report (scratchpad heca_rows/sites/patch.pkl +
site_probe.py; baseline = the owner's 09:03 rebuild, patch at
XPTerrainBuilderData/Patches/+30+030/+30+031/).

## The laws (implement R19-5 FIRST — every later measure uses it)

### R19-5 THE CONSTRAINED-PAIR DOMAIN KEEPS EVERY RING EDGE
Measured: check_grade.iter_shape_grade_constraints DROPS 50 of 267
ring edges on apron -10629 — including the owner's three defect edges
(148 % over 8.49 m, 55.6 % over 22.39 m, 36.6 % over 7.84 m), so the
census carries ZERO rows for them. Fix the domain to honour its own
docstring ("ring edges always kept"); name the dropping branch in the
commit. Twin in test_harness idiom: for a synthetic shape, the
census's within_shape row set covers the full ring-edge enumeration.
ALSO: within_shape rows report the PAIR midpoint lat/lon, not the
shape anchor (site_m stays as is). Expect the HECA census to GROW —
quote the before/after totals and note it in the ledger line as the
instrument becoming honest, not a regression.

### R19-1 A PAD FINDS ITS HOST BODY (item 1)
relevel_pads_to_host_pavement (anchors.py:3817) requires a DIFFERING
host vertex within PAD_HOST_LEVEL_CONTACT_M 2.5 m; building114's
nearest is 7.84 m away, so the 88.50 pad never re-levels (53 of 214
HECA pads share the geometry). Law: the host-body probe samples the
HOST'S SOLVED SURFACE at the pad ring (or reaches the host ring's
nearest differing vertex) — a pad welded into a coarse host ring
still finds its body; lips stay lips. building189's borrowed-ring
consensus then evens out by construction. Claims: building114
88.50→85.63; the -774→-767 36.6 % edge gone; the 14 building|building
2.87 m rows on -10189 → 0.

### R19-3 OBJECT PADS RECONCILE WITH THE HOST (item 3)
object_pad targets come from the object's rendered/draped ground
(object_anchor.py:2144) and NOTHING reconciles them with the solved
host (relevel skips role != building). Law: an object pad whose
target exceeds the host pavement's solved level at its ring by more
than the pad's own relief budget ADOPTS the host level (pad + blend;
host body untouched) — extend the R19-1 machinery by role, one
implementation. Claims: object_pad:56 105.51→~93.3; the 55.6 %/148 %
apron -10629 edges gone; the two 13 m ADJACENT-GROUND verify findings
at 30.11355/30.11412 cleared; family 32/650 re-measured.

### R19-2 AN ENCLOSED HOLE GETS FILLED (item 2)
gap_fill refuses the 22,483 m² enclosed airside hole because its
min-rect short side (188.5 m) exceeds GAP_FILL_MAX_WIDTH_M 175 by
8 %. Law: before the width test, an ENCLOSED hole (touching no
coverage-box edge) is SUBDIVIDED by the groundside/service shapes
inside it; each residual face takes the existing width test (here all
≪175 m). Never a blanket cap raise. Claims: the pocket at
30.1165544,31.4112743 gains fill/spine; the +5.2 m single-step hill
gone from the mesh.

### R19-4 EXECUTE THE WALLS RULING (item 4; standing owner law
2026-08-07 "retaining walls emit ONLY at carve structures")
The mid-road wall is emit_authority_retreat_walls resolving a
lot-vs-road authority split (2.3-2.7 m) — no tunnel/bridge within
50 m; 56 of HECA's 58 walls are this class. Law: non-carve
authority_retreat walls RETIRE; the retreat run takes a graded
FEATHER between the two authorities (the ruling's own remedy).
Carve-structure walls (tunnel/bridge portals, abutments, seawalls)
untouched. Claims: zero authority_retreat_wall refs at HECA except
carve sites; the owner's road corridor mesh reads a smooth grade
30.1121634,31.4063032 → 30.1127719,31.4070408 → DEM; census (honest,
post-R19-5) quoted before/after.

## Tests / process
Twins per law, mutation-checked; blast.py --tests-for for selection
(quote it); covering files once, ledgered. NO acceptance builds —
claims tables; the lead runs the consolidated +30+031 arm. In-lane
interventional builds only where a law's mechanism demands one
(declare). Files: check_grade.py+census (R19-5), route_profile/
anchors.py (R19-1/3), gap_fill.py+config (R19-2), adjacent_ground.py
(R19-4). Do NOT touch solve.py/solver_primitives/flat_site/
O4_Vector_Map (r17d owns them). DEFERRED lines per skip.
