# LEMD round — bridge-over-tunnel-ramp road level + basin pit apron intrusion
# (owner sim read of 1.0.269, 2026-08-30; screenshot on file for item 2)

Two owner items, probed on the owner's patch
(`XPTerrainBuilderData/Patches/+40-010/+40-004/LEMD_auto.patch.osm`,
engine 1.50.1713, built 2026-08-29 23:19). SITE-FIRST: each item closes
at its coordinate, quoted first, current configuration.

## Item 1 — road carves a canyon where a bridge crosses the tunnel ramp

Site: 40.4836744,-3.5809643. Probed: service_road shapeID 288 (way
-10289, alt 600.93–602.54) with service_junction 514 (way -10515,
600.82–600.93) AT the crossing; tunnel_ramp shapes 1883–1892 directly
beneath at 598.01–600.95 (ramp descending to the 598.45 tunnel datum);
tunnel walls 1911–1918 flanking. East side (owner: "receiving the other
side of the bridge") at 40.4836132,-3.5798814: groundside 557 (way
-10558, 601.79–602.49), service_junctions 184/185 (602.13–603.44),
graded_strips 2379/2381 (~603.0–603.7).

Owner read: the road is WAY too low — it carves a canyon through the
hill. A bridge crosses the tunnel ramp at road level here, from
40.48352,-3.5807455 over to 40.4836132,-3.5798814. The road must reach
the crossing AT LEAST 5 m above the tunnel ramp (ramp ~598.4 ⇒ road
≥ ~603.4) and land smoothly on the east apron area (~602–603.4).
Current configuration instead sags to 600.8 at the crossing — pulled
toward the tunnel-ramp grade.

Attribution first: (a) is there bridge evidence in the road feed /
source (bridge tag, layer) at this span, and did classification drop
it? (b) which mechanism minted 600.8 — road solve welding to
tunnel-adjacent structures, DEM-follow through the tunnel cut, or the
junction seat? (c) does the merged tunnel law family already carry a
bridge-over-ramp case (check the tunnel 8-law spec and the OTHH bridge
deck datum work) — extend within existing law if so; if a NEW law is
required, STOP and report the proposed law text for owner ruling.
Note the HEAZ ruling (bridge stands down, O4_GAP_SPINE_BRIDGE=0)
concerned the GAP-SPINE bridge mechanism, not a road bridge over a
tunnel ramp — do not conflate them.

Target: road span carries ≥ ramp+5 m across the crossing, continuous
climb from the west, smooth landing at the east receive values quoted
above; tunnel ramp beneath keeps its authored profile untouched.

## Item 2 — basin pit cuts into the apron: twin canyons

Site: 40.4924484,-3.5692887. Probed: apron shapeID 226 (way -10227,
286 nodes) spans 596.42–601.19 — its low nodes sit ~4 m below its own
~600.5–601.2 field. The authored object_basin_trench 1760 (way -11759,
floor 587.75 flat) passes 0.74 m from the probe point; basin rim ways
1763/1765 hold rim-top 600.48 flat, while rim ways 1767/1770 span
587.75–600.48 (the descending rim segments). building8 (600.48 flat)
adjoins. Owner screenshot: two V-shaped canyons run OUT of the pit
into the apron, and the apron dips around them.

Law frame (standing, committed basin arc — do NOT regress it): the
trench floor 587.75, trench 99%-of-authored coverage, and the single
G=596.682 relationship invariant (0.000000 m) are adjudicated ground
truth. The defect is the apron: rows belonging to apron 226 are being
pulled below the rim toward the pit.

Attribution first: which channel drags apron nodes to 596.42 — (a)
welded/shared nodes between apron 226 and trench/rim ways (canonical
identity join, never proximity), (b) an adjacent-ground band emitted
FROM the trench claiming apron rows, (c) the descending rim segments
1767/1770 acting as grade sources into the apron, or (d) a
coverage/claim gap letting the trench's zone project past the rim.
Quote the twin-canyon node chains (two lowest apron chains with
positions) in the report.

Target: apron 226 holds its field values (~600.5–601.2) up to the rim
line; the rim (600.48) is the boundary — pit grades stay inside it;
trench floor and G-invariant unchanged to 0.000000 m.

## Acceptance

Each item closes at its coordinate, quoted first. Synthetic-first on
cut fixtures (repro_cut/solve_cut); ONE closing LEMD build via the
harness; controls via the artifact ledger (`--base-arm`, never rebuild
an existing control). LEMD law-true census not worsened; basin-arc
invariants re-quoted in the report. Below-bar = STOP with residual
quoted.
