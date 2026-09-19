# Future features (owner backlog)

Ideas the owner has asked to keep, NOT scheduled and NOT rulings. Each entry
records the owner's words, what is already known, and what a spec would have to
answer. Promote an entry to a spec (Fable) before any lane touches it.

## 1. Adopt a custom airport's own mesh into our patch (owner, 2026-09-18)

Tracked publicly as issue #41; this entry keeps the parts that stay in the repo
(the spec questions).

Owner, verbatim: "When an airport like TFFJ is installed that already has a custom
mesh, ideally XPTerrainBuilder would detect it, disable it in the scenery_packs.ini
if it wasn't already, and incorporate their mesh into our patch so the user can
build new scenery with our tools, but fit seamlessly with their custom objects.
Some meshes are super simple just cut outs for tunnels, and we would want to add
all the other details, others like TFFJ would likely provide the data for the whole
patch."

Known today:
- TFFJ ships exactly this pair on the owner's install: `c_FRA - 100_airport -
  TFFJ_1_Apt` (objects) + `c_FRA - 600_mesh - TFFJ_2_Mesh` (a base-mesh DSF). The
  pack's objects are authored against THAT mesh, not against any DEM.
- Packs also ship terrain as OBJECTS (`Flora/hill.obj`, `TFFG/Ground/
  fixed_platform.obj`, `Ground/Cliff.obj` — pack-read spec §F); RULINGS 2026-09-18t
  (4) already makes scatter standing on them follow them. A mesh pack is the same
  intent expressed as a DSF instead of an OBJ.
- Precedent for a pack as ground truth: the LEMD Aerosoft patch (basin floor
  587.75 m, G = 596.682 invariant) and the shared-datum LSGG class.
- We READ `scenery_packs.ini` today (`O4_Scenery_Packs`) and NEVER write it;
  disabled packs are never rewritten (17b/17c). Writing it is a new class of act on
  the user's install.

A spec would have to answer:
1. DETECTION — what makes a pack "a custom mesh for this airport" (a DSF with
   terrain patches / `sim/overlay 0` covering the airport, in a pack ordered above
   ours; distinguishing it from an ortho tile, from another tool's mesh, and from a
   whole-region mesh such as SpainUHD).
2. WHAT IS ADOPTED — the mesh's elevations as an elevation SOURCE for the patch
   area (a high-trust inset, above lidar?), its cut-outs (tunnels, basins) as
   structure witnesses, or its triangles verbatim; and how the two classes the owner
   names differ: "simple cut-outs" (we add everything else) vs "provides the whole
   patch" (we mostly conform). How it blends into our surrounding terrain (the inset
   feather precedent), and how the laws apply to a surface the author already built
   (airside law vs author's surface — which yields).
3. DISABLING THE PACK'S MESH in `scenery_packs.ini` — consent (a dialog, engine-
   owned like the boundary-airports one), reversibility (restore on uninstall of our
   tile), never touching the OBJECT pack, X-Plane rewriting the ini on launch, and
   the §12a discipline (never destroy what we cannot prove is ours).
4. Interaction with: the apt.dat/pack selector (17a), the pack-set signature that
   stales insets (17c (1)), patch freshness stamps, the object reseat (objects
   authored on the adopted mesh should then need ~zero motion — a strong acceptance
   test), the boundary-airports dialog, and cross-platform byte identity (§46).

First measurement when this is picked up: at TFFJ, the adopted mesh vs our built
surface vs the pack objects' authored feet — if the objects sit on the pack mesh to
centimetres, that is the proof the mesh is the author's intended ground.
