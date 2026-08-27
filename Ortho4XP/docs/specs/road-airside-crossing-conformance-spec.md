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

## Amendment 1 (Fable, 2026-08-26 late — rulings on the lane's three
## STOP questions; attempt cap RESETS for the amended targets, cap 2)

The lane's report (lane/roadxing c77a8097): owner site unchanged after
two attempts; +78 airside rows in the better arm (an airside-is-king
violation); population 285 stretches / 32.1 km at HECA. Three rulings:

1. **FRAME — contact is asked in the SOURCE pavement frame.** §1.1's
   "cross-section stands in airside pavement" means the pavement union
   the free-road walk itself reads (`pav_union` over source shapes),
   NOT the settled post-slice arrangement. The carve deliberately
   separates the road ring from airside pavement with an
   adjacent_ground strip, so the settled arrangement NEVER contains
   the crossing — reading it there is the mis-frame that made the
   owner site invisible. Detection extends the free-road walk's own
   question (same `pav_union`, same station cast, the ROLE of the
   contiguous run) — still never a third contact test.

2. **SCOPE — CROSSINGS ONLY.** A conforming stretch exists only where
   the road's centerline ENTERS and EXITS airside source pavement (a
   traversal with both mouths on non-airside ground, or terminating
   inside it). A road running ALONGSIDE airside pavement without its
   centerline entering it stays under the existing 25b/25h law
   untouched. This kills the 32.1 km population; expect the honest
   population at HECA to be tens of crossings, not hundreds of
   stretches. Report the population size.

3. **PINS BIND ROAD-FAMILY NODES ONLY — ADOPTION, NEVER CONSTRAINT.**
   The measured apron movement is the predicted failure mode of
   seating pin values at the airside boundary: an entry/exit pin that
   constrains (or is welded into) an airside-ring node is a term in
   the airside solve — the pull the spec forbids. The ruling: the
   conforming stretch's values are ADOPTED from the airside solution
   (read the airside surface where the centerline crosses its
   boundary, after airside has settled — post-solve writeback onto
   road-family nodes, the identity-adoption precedent), never
   expressed as graph terms that couple into apron/taxiway nodes.
   If the one-solve graph cannot express that one-directionality for
   these stretches, impose the values in the writeback stage. BEFORE
   attempt 3 lands: attribute the +78/+124 airside rows on the
   EXISTING arms' artifacts (which term moved the aprons — pins,
   cap re-pricing, or the corridor-complement subtraction) and state
   it in the report; the fix must remove that term's airside coupling,
   and the acceptance gains a hard gate — airside census EXACT vs the
   flag-off arm (zero NEW, zero MOVED airside rows; GONE rows
   allowed only if attributed to the road's own adjacent-ground band).

4. Non-goals reaffirmed: no new welding machinery (§1.3 unchanged);
   HEAZ's BandInversionError and the red near-miss-frontage twin are
   PRE-EXISTING at a111e080 — out of scope, reported separately.
