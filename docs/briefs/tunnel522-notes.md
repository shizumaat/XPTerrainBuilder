# tunnel522 — lane notes (branch `claude/tunnel522`, base main da0b8aac0)

## Part 1 — #522 KCLT false tunnel

Witness confirmed by replay (dry `--from planar` of `valley2/KCLT.pkl`, the witness wrapped
by a scratch driver): bore -11194 (9.9 m, `highway=service tunnel=yes`) is admitted by
§34 (12) (5) (d) "an OSM tunnel inside the airport boundary". Readings: cover 0.0 m, no
crossing, rise +0.00 m, no layer, inside the fence. DEM 224.46 -> 223.95 m along it.

What is really there: the road passes under an elevated terminal link. Four pack parts
(`Terminals/paredes_10/11/12_charlotte.obj`) at base 3.12 .. 3.67 m stand over the 7 m
carriageway, drawn 0.1 .. 0.6 m off the mapped line (two 10 x 15 m roof sheets exactly the
bore's length). Nothing at grade. Its neighbour -11198 is already refused by (a).

FINDING: SPJC -5724 has the SAME four readings (cover 0.0, no crossing, rise +0.00, no
layer, in the fence) and NO pack part within 60 m. The ruling's literal sentence ("no cover
at grade and no rise -> not built") refuses it too; the ruling's acceptance keeps it.
(d) admits exactly these two bores at the seven airports.

Rule built: (d) does not stand when an ELEVATED pack building part (base above
`[rebake] elevated_base_m`) stands over the bore's carriageway and no at-grade part covers
`terrain_cover_min_m` of its line. `planar/structure_service._PackBuildings.passage`.
KCLT -11194 refused, SPJC -5724 built. Needs the master's / owner's ratification as a
reading of 10i (1).

## Part 2 — KASE thresholds (read-only)

Engine pins (sidecar `runway_caps`, kind `threshold`, source CIFP):
RWY 15 2340.864 m (7680 ft), RWY 33 2383.536 m (7820 ft, displaced threshold); span
2130.162 m; dz 42.672 m; 2.00323 %. Source `X-Plane 12/Custom Data/CIFP/KASE.dat` lines
152-153 (Navigraph cycle 2607): `RWY:RW15 ... 07680 ... 0000`, `RWY:RW33 ... 07820 ... 1000`.
apt.dat (Aerosoft pack and Global Airports) carries no threshold elevation: row 1 field
elevation 7835 ft only; row 100 end 33 displaced 314 m.

## Part 3 — DROPPED by the master (RULINGS 2026-10-10j; lane apron523 owns it).
