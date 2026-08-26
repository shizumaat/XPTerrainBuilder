# Road band-seal scope + road-apron edge conformance (Fable spec,
# 2026-08-25; owner-approved fix (a) for the HECA roads round +
# RULINGS 2026-08-25b enforcement)

Evidence: the 2026-08-25 HECA roads attribution (lane/roads worktree,
patch body 27292e8e62ed): 110 band-clamp records, 92 road-family; every
floor-side road clamp inside the raster band's 30 m off-net radius,
zero outside; owner site 30.102344, 31.3951157 = +5.05 m lift shipped
as a 201 % step because `seal_pavement_to_band` (pipeline.py:7425) runs
AFTER `_grade_limit_groundside_chords` (:6389). The band of record is
the AIRCRAFT-reachability band: road roles are absent from
`raster_reach_band._domain_geom`, the road 8 % cap is painted nowhere
(`_local_cap_grids` skips `is_service`), and off-mask pricing is 1 %
across open ground with a hard 30 m horizon.

## §1 Seal scope (owner-approved option (a))

1. `seal_pavement_to_band` seals ONLY the roles whose law the band
   states — the `_domain_geom` airside set (apron, junction, taxi
   family, runway, runway_crossing, building). `service_road`,
   `service_junction` and `groundside_pavement` LEAVE the seal's role
   set; the road family remains owned by its own authorities (the
   mouth-fed `groundside_reach_band` seating + the road chord limiter
   at the road cap).
2. Define the sealed set FROM `_domain_geom`'s role list (one source;
   a second hand-list is the census-wrapper defect).
3. ORDERING AUDIT (report, do not redesign): with roads out of the
   seal, enumerate every writer that can move a road-family node after
   `_grade_limit_groundside_chords` and name them in the report — a
   post-limiter road author is the same defect shape the seal was.
4. Flag `O4_SEAL_AIRSIDE_ONLY`, default ON; OFF = today, byte-identical.

## §2 Road-apron edge conformance (RULINGS 2026-08-25b)

1. A road ring sharing ≥1 EDGE with an apron ring — canonical identity
   (11-dp spelling), never proximity — takes the APRON'S LAW: its pairs
   price under the apron caps (strictest grade), apron seeding governs
   (no DEM-follow inside the contact ring), and downstream consumers
   (graded-strip adoption, the seal) see ONE family at those nodes.
2. Enforcement point is the EXISTING free-road scoping at slice time
   (`free_road_subsegments` + the absorption path) — find why the 12
   measured contact rings escaped it and close THAT gap; a post-hoc
   relabel pass is a second authority and is refused. If the gap turns
   out to be a definition mismatch (contact ≤1 m but not edge-sharing),
   the ruling's boundary is EDGE-SHARING; report near-miss (<1 m,
   non-sharing) rings separately for the owner, do not absorb them.
3. Census parity: the absorbed rings' rows move to the apron families
   naturally through role/cap assignment — no census-side special case.

## Twins

(a) Synthetic: road ring beyond the 30 m off-net radius with a lawful
    8 % descent — flag ON: unsealed, descent survives; flag OFF: the
    historic clamp reproduces.
(b) Airside sealing byte-identical between flag states.
(c) Edge-sharing road ring absorbs (apron cap prices its pairs, no
    DEM-follow); a free road 2 m away does not.
(d) `test_harness.py` twins pass (families/register parity).

## Acceptance (ONE HECA build on the roads lane, then SPJC/CYXY)

- Road-family band-clamp records 92 → 0 (any residue named row-by-row).
- Owner site 30.102344, 31.3951157: a continuous descent at ≤ the road
  cap — no step; quote the ring profile before/after.
- The 12 contact rings conform (worst 2.22 m over 1.00 m goes to the
  apron-law verdict); near-miss non-sharing rings reported.
- Census: airside stays at the §1 frame (1,731/1,735 — NO new airside
  rows); groundside road rows reported honestly against the 2,965
  baseline with the class table (expect the longitudinal-tear class to
  move; the 2,422 exit_over_budget transects are a SEPARATE docket and
  are only reported).
- Attempt cap 2, materiality 0.01 m; STOP on second miss with the
  table. No shared-repo writes, no timing claims.

## Amendment 1 (Fable, 2026-08-25 — §2 conformance is PRICING + SEEDING,
## never population; resolves attempt 1's measured conflict)

Attempt 1 implemented §2 via absorption (contact rings merged into
airside): HECA airside 1,735 → 1,948 (+53,530 m² apron, new 6 m
apron|junction steps at -12160/-12167), SPJC 175 → 178. That is the
airside-contamination direction airside-is-king forbids; the ruling's
operative words are "conform to the strictest grade".

1. A contact ring (edge-sharing per §2.1's identity test) REMAINS
   groundside population. NO absorption, NO merges, NO role conversion.
2. CONFORMANCE = (a) every pair of the contact ring prices at the
   APRON'S CAP (strictest grade, end-to-end); (b) shared-edge vertices
   carry the apron's values by identity (automatic); (c) the ring's
   seeding inside the contact does not DEM-follow against the shared
   edge — it seeds from the shared-edge apron datum outward under its
   (now-apron) cap. §2.1's "apron seeding governs" means exactly
   (b)+(c), not reclassification; §2.3 is amended to match: rows stay
   in groundside families and the conformance shows as tighter caps.
3. Acceptance amendments: HECA airside returns to the §1 frame
   (1,735/1,736); SPJC to 175; the absorption-minted apron|junction
   steps are gone; everything else (clamp table, owner-site no-step,
   CYXY) stands as attempt 1 measured. Attempt count RESETS under this
   amendment, cap 2.
4. The §1.3 ordering audit's four post-limiter road authors
   (19_final_projection 2084@5.83 m et al.) are RECORDED as the next
   docket — out of scope here.

DISPOSITION (lead, 2026-08-25): PASS with named residue on lane/roadseal
(HECA airside 1,679, SPJC 174, CYXY 32 against its matched control; zero
apron|junction rows; owner site continuous at 7.5%).  The clamp table
reads 92 → 61, not attempt 1's 92 → 14: that fall came from the
reclassification this amendment forbids, and the 61 are WRITEBACK-stage
records, not seal records — the seal's scope carries no road role, it
clamped 3 airside shapes and reported SEAL INTACT.  Residue ACCEPTED and
assigned to the post-limiter road-authors docket at clause 4, not to this
round.
