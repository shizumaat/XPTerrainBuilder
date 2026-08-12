# Round 21 — land-connected continuity (the corridor override retires)

Spec: 2026-08-12, FROZEN (Fable lead). Lane: **r21land**. Owner-ruled
(RULINGS 2026-08-12): automatic, universal; no per-tile declarations.
Pre-ship as amended; owner-artifact baseline; consolidated acceptance
is the lead's. Deviations STOP-and-report; cap 2.

## Attribution FIRST (the honesty gate)
Measure, on the +22+113 inputs (coastline/land data + the mesh's own
land polygons, read-only): is the PHYSICAL causeway between the VHHH
core island and the east island LAND in the data? r17d measured both
on one 21.2 km² land component — name the connecting land geometry
(where the isthmus runs, its width). If the data carries NO land
bridge (the connection is an artifact of an earlier declared-corridor
bake or reading frame), STOP — automatic detection cannot conjure
land the data lacks, and the owner must rule on the data instead.

## The law (after the gate passes)
On an ISLAND land component (sea-bounded within the working frame)
carrying the airport's graded coverage:
1. CONTINUITY: the flat-site family (constant core + admitted cluster
   insets on that component) grades CONTINUOUSLY across the
   CONNECTING LAND between members — the isthmus joins the flat
   extent automatically (bounded: only land on the component between
   member footprints, never the whole component, never mainland —
   the island test is structural, twinned against a mainland fixture
   like HECA where NOTHING may change);
2. WALLS: unchanged from r17d (component's sea edge; the cluster
   admission fixpoint may simplify to the land-component test alone
   per the ruling — measure that the simplification changes nothing
   at VHHH/VMMC/ZGSZ and simplify if so, keep both if they separate);
3. RETIRE `flat_site_declared_corridors`: the O4_Cfg_Vars key, the
   parser, the corridor bake and its twins go; existing cfg lines
   become a loud no-op WARN (never an error — users may carry stale
   cfgs). The r17 corridor twins convert to the automatic law's twins
   (the causeway still grades flat at Z0, sea outside it still sea —
   same acceptance, new mechanism).
Claims: VHHH causeway flat at Z0 with walls, channel outside the
isthmus still sea, east island Z0-to-the-wall; VMMC/ZGSZ unchanged
beyond their own island edges; HECA/mainland byte-identical
(structural twin + one control read); no cfg key consumed anywhere.

## Process
Twins mutation-checked (island vs mainland; isthmus-only bounding;
retired-key WARN); blast --tests-for quoted; covering files once,
ledgered; ONE declared interventional +22+113 steps-1-2 arm for the
mesh claims. Files: flat_site*.py, O4_Vector_Map.py, O4_Cfg_Vars.py
— confirm r17d/r19/r20 lanes are merged/closed for these files
before starting (they are, per the lead). DEFERRED lines per skip.
