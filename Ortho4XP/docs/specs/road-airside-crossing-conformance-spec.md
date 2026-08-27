# Service roads crossing airside pavement conform to it (Fable spec,
# 2026-08-26; owner sim read of 1.0.260, RULINGS 2026-08-26b item 2)

Owner: "Service roads crossing taxiways, like here: 30.104671,
31.3973462, have to grade smoothly to match the apron elevation, not
leave a cliff." Airside is king (standing ruling): the road takes the
airside value; the airside surface feels ZERO pull.

## §0 Measured frame (patch `/tmp/harness/HECA_20260826T213425.osm`,
## tree 97b38bffa614 at cb4749b9-dirty)

- Owner site `30.104671,31.3973462`: service_road ring -12847
  (102.72–104.76, carries `o4_grade_law_cap 0.01`) and service_junction
  -11080 stand ~1.5 m from taxiway junction -10250 (106.7–108.89) and
  -10257 (108.62–109.52), with adjacent_ground graded_strip rings
  between. NO shared nodes: an unwelded ~2.4–4.1 m step across ~1.5 m.
- Sidecar axes at the site: axis 1935 (cap 0.01 — a 25h apron-spine
  piece) ENDS exactly at road-ring node `30.104671,31.397346`; axis 709
  (cap 0.08 — FREE road) runs straight across the taxiway-junction
  area. The road's crossing stretch is priced as free road against
  ambient terrain while the pavement it crosses sits metres higher.
- Why no existing law fires: the 2026-08-25b conformance term is
  scoped `APRON_CONTACT_ROLES = frozenset({"apron"})`
  (`lateral_contiguity.py:83`) AND keys on literally shared edge
  vertices (`EDGE_IDENTITY_TOL_M`); taxiway/junction contact matches
  neither. The 25h apron-spine complement likewise derives from
  apron contact, so the spine stops at the apron edge.

## §1 THE LAW — crossing/contact stretches conform to airside

1. CONTACT POPULATION: a service-road centerline stretch whose
   cross-section stands in AIRSIDE pavement — roles apron, taxiway,
   junction, primary_parallel, stub, runway-adjacent junctions (the
   airside families the census's own role tables name; read them from
   one existing register, never a hand list) — is a CONFORMING
   stretch. Detection extends the existing free-road machinery
   (`free_road_subsegments` / `apron_spine_subsegments` — extend the
   predicates, never a third contact test): the width test already
   reads the full `pav_union`; what changes is that the non-free
   complement now carries conformance against ANY airside neighbour,
   not only aprons.
2. VALUES: the conforming stretch is valued by PINNING to the airside
   solved surface at the contact — at the stretch's entry/exit of the
   airside polygon the road takes the airside boundary value
   (frontage-conformance precedent), and between pins it rides the
   airside surface. Away from the contact the road transitions at its
   own cap (`SERVICE_ROAD_MAX_GRADE`). AIRSIDE IS KING: the pins are
   one-directional — no term of the airside solve may reference the
   road's variables (assert this in the twin).
3. WELDS: where the road ring abuts airside pavement across an
   adjacent_ground strip (the §0 geometry), the strip fairs
   monotonically between its two welded families (the landed
   `O4_TAUT_GRADED_STRIP` mechanism §3.2 — reuse, do not fork) and the
   road-side ring nodes at the contact face take the pinned values, so
   the descent is continuous: junction 107 → strip → road ≤ road cap.
   No new welding machinery unless measurement shows the strip
   mechanism cannot carry it — in that case STOP and report (spec
   deviation needs a Fable ruling).
4. Flag `O4_ROAD_AIRSIDE_CROSSING_CONFORM`, default ON; OFF
   byte-identical.

## §2 Twin

Synthetic taxiway at +3 m over ambient, service road crossing it:
crossing stretch takes the taxiway values (pins at entry/exit), road
descends both sides at ≤ its cap, taxiway vertices BYTE-IDENTICAL to a
road-less control (airside-is-king assertion); flag OFF reproduces the
step.

## §3 Acceptance (ONE HECA build; A/B census vs the round-3 §0 frame)

- Owner site: continuous descent from junction elevation through the
  strip to the road at ≤ the road cap; no step > law across the
  contact (arm_site_read --welds/--line at the site, before/after).
- Census: groundside within_shape service_road/service_junction rows
  at the site explained; the standing "HECA groundside transverse
  +454 residue" re-measured (may shrink; report either way).
- SPJC/CYXY/HEAZ non-regression.
- Convergence guards: materiality 0.01 m, attempt cap 2, STOP on
  second miss, heartbeat. No shared-repo writes, no timing claims;
  build-time impact statement in the report.
