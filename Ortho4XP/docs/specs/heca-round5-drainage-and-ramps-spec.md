# HECA round 5 — drainage crossing tear + service-road ramps
# (owner sim read of 1.0.265, 2026-08-28)

Three owner items, probed on the fresh patch (`+30+030/+30+031/
HECA_auto.patch.osm`, built 11:30:13).

## Item 1 — "concrete drainage channel is a spiky mess, tearing the
runway" at 30.1076307,31.4094328

Measured: the point lies on runway 05C/23C (way -12231, alt 105.73–116.2)
AND on `ols_road` service_junction ways -13741/-13744 (alt 108.33–118.85)
plus service_junction -12157 — the ols_road ribbon crosses the runway
carrying elevations up to ~2.9 m ABOVE the runway surface at the
crossing, with adjacent_ground strips (-13539/-13540/-13547) layered at
their own values. The rendered channel spikes and the runway edge tears
along the crossing.

LAW: the runway family is aircraft-transit — NOTHING crosses it carrying
its own elevation authority (R14-2/A-3 class). At a runway crossing the
ols_road/drainage corridor takes the RUNWAY's surface exactly (weld,
canonical identity, zero tear rows), or stands down over the strip. The
spikes' emitter must be attributed interventionally first (which pass
mints the 118.85 values, and why the crossing was not welded — check the
§W1/§W2 wave interactions and the OTHH protected-transit precedent).

## Items 2+3 — service-road ramps refused by the 1 % grade cap

- Item 2: road shapeID 2863 (`o4_grade_law_cap 0.010000`) sits 103.24–
  104.06 at its start (30.1066499,31.4007725); the owner expects it to
  RAMP to taxiway elevation (~108, junction -12711 at 107.93–109.64) by
  30.1058753,31.3996476, then U-turn and keep climbing to
  30.107403,31.4022258. Required: ~4.8 m over ~137 m = **3.5 %**. The
  1 % cap cannot build it; the road is held low and the residual is the
  CLIFF at 30.1052938,31.3989669 (service_junction -10775 spanning
  103.92–108.51).
- Item 3: road shapeID 2854 (cap 0.010) 103.01–105.99 from
  30.1044752,31.3966654 must meet junction -10251 (106.82–108.73) at
  30.1046554,31.3973678. Required: ~4.5 m over ~70 m = **6.4 %**.

LAW (owner intent stated in the read — the ramp IS the expectation):
1. A service road that terminates on (or passes onto) aircraft pavement
   BINDS its end elevation to that pavement (weld at the junction — the
   cliff is never lawful).
2. RULED (owner 2026-08-28e) — AND ALREADY LAW: `SERVICE_ROAD_MAX_GRADE
   = 0.080` (config.py:1331) is the free-road class; free-road scoping
   is supposed to cut each road at the stations where it stops being
   free. THE DEFECT IS SCOPING, NOT A MISSING CONSTANT: all four
   stretches carry `o4_grade_law_cap 0.010000` — classified as APRON
   SPINES (RULINGS 2026-08-25h, 1 %) even where the owner says they have
   left the apron. Attribute WHY each stretch classified as
   apron/spine (edge-sharing test, corridor slice bounds, gap_fill_spine
   adjacency) and fix the scoping so the stretch beyond the apron prices
   and solves at the 8 % free class. No new law constant. Item 3's
   6.4 % is lawful under the existing 8 %.
3. The climb distributes over the road's whole path (item 2's U-turn leg
   included) — segment-local flat solves that dump the whole climb at
   the junction are the defect.

- Item 4 (owner follow-up, same read): service road at
  30.114984,31.4107959 "drops steeply from the apron instead of grading
  smoothly down". Measured: road -12855 (cap 0.010) spans 92.3–98.86,
  junction -10561 spans 94.68–99.15, apron -10557 (98.05–104.47) ~10 m
  away — the 6.6 m fall compresses at the apron edge instead of
  distributing along the run. Same laws apply, descending direction: weld
  at the apron/junction edge, ramp-class grade along the road's whole
  path.

Mechanism-before-fix: verify interventionally which constraint holds the
road low (the cap, a missing junction weld, or a flat segment solve)
before changing law constants; the cap raise applies to this class only
(free service road climbing OR descending to/from a bound end), not to
aprons or covered roads.

## Acceptance

- Item 1 site: zero tear rows at the crossing (seam family), ols_road
  crossing welded to runway values (canonical identity), spikes gone
  (no vertex within the crossing >0.05 m off the runway surface); runway
  05C/23C profile unchanged outside the crossing.
- Item 2: road profile monotone from start to the -12711 junction weld
  (grade ≤5 %), cliff at 30.1052938,31.3989669 gone (adjacent pavements
  meet within the step law); the U-turn leg continues the climb to the
  named end point.
- Item 3: monotone ramp start→junction weld at ≤8 % — fully feasible
  under the ruled class.
- HECA census not worsened outside the three sites; every delta at the
  sites attributed. CYXY/SPJC/LEMD/OTHH controls byte-identical or
  attributed. Twins for the weld law and the ramp-class cap.
