# X-Plane Scenery Performance Pitfalls — Research Notes

Compiled July 2026 from developer.x-plane.com (Laminar, authoritative) and
x-plane.org community sources, as groundwork for XPScenery Doctor's check
catalog. Implementation status is tracked inline:
- Implemented: C-09 (animation blocks instancing), C-10 (spill lights),
  C-12 (>1 km object span), system-aware VRAM budgets (PERF-01/02/03),
  PNG→DDS conversion with dead-alpha stripping (C-04 Apply Fix).
- Candidates for next rounds: LOAD_CENTER insertion, degenerate-ANIM baking,
  apt.dat overlap/node lint, facade stretch ratio, missing exclusion zones,
  forest density/LOD (.for).

# X-Plane Scenery Performance Pitfalls — Research Report for XPScenery Doctor

Scope: pitfalls **not** already covered by your existing checks (overdraw, LOD-missing, ATTR/instancing state, PNG-vs-DDS, mipmaps, texture sizing, tiny-object floods, VRAM estimates). Each claim is labeled **[Laminar]** (developer.x-plane.com / Laminar staff, authoritative) or **[Forum/Community]** (indicative). Verbatim quotes are from the cited pages. Where thresholds have no published number, they are marked *(heuristic)*.

---

## 1. Animation / datarefs breaking instancing

**What it is.** Any `ANIM_begin`/`ANIM_trans`/`ANIM_rotate`/`ANIM_hide/show`, dataref-driven attributes (`ATTR_light_level`), smoke puffs, or non-`GLOBAL_` material state in an OBJ forces it off X-Plane's instancing path. You check ATTR state hostility, but animation is the single most common instancing killer and appears to be outside your current checks.

**Why it costs frames.** [Laminar] "When an object is drawn with instancing, performance is a lot better than without it; the huge numbers of objects you can see in the autogen scenery are due to instancing." There is "a giant pile of things you're not allowed to do in an instanced object – animation, material attributes, smoke puffs, etc., because the object has to be simple so that the GPU can draw a big pile of objects without the CPU intervening." Notably, `ATTR_hard` is explicitly fine: "you can use ATTR_hard in an instanced object, no problem!" ([Making 3-d Modeling Less Weird](https://developer.x-plane.com/2015/12/making-3d-modeling-less-weird/)). Also [Laminar]: "The cost of anim transforms is of course partly in the animation, but part is in the stoppage of drawing" ([Optimizing Object Performance](https://developer.x-plane.com/article/optimizing-object-peformance/)). XPlane2Blender treats animation in an instanced scenery object as an export failure ([XPlane2Blender wiki](https://github.com/X-Plane/XPlane2Blender/wiki/Material-and-Instancing-Model), [issue #368](https://github.com/X-Plane/XPlane2Blender/issues/368)).

**Detection.** Parse each `.obj` for `ANIM_*` commands, `ATTR_light_level`, `smoke_*`, and dataref references. Cross-reference the DSF overlay: count placements per OBJ path. Severity = (instancing-hostile) × (placement count) × (tri count).

**Threshold** *(heuristic)*. Flag any animated OBJ placed ≥ ~20–25 times in one DSF; escalate at ≥100. An animated one-off (windsock, radar) is fine.

**Auto-fix.** Two mechanically safe cases: (a) **degenerate animations** — `ANIM_trans`/`ANIM_rotate` whose keyframes are all identical values (a common exporter artifact): bake the static transform into vertices and strip the ANIM block; (b) animations driven by datarefs that are constants. Anything else: flag-only (removing real animation changes behavior).

---

## 2. ANIM_hide used as an "optimization" / hidden heavy geometry

**What it is.** Authors hide seasonal/optional geometry with `ANIM_hide` believing it saves frames.

**Why it costs frames.** [Laminar] "X-Plane will still run through every command in the object, simply skipping drawing"; texture and geometry prep "are atomic operations (we have to prepare the whole texture and all of the geometry no matter what we will actually use)"; "ANIM_hide is for artistic purposes, but not optimization purposes" ([ANIM_hide is not a framerate optimization](https://developer.x-plane.com/2007/11/anim_hide-is-not-a-framerate-optimization/)).

**Detection.** `ANIM_hide`/`ANIM_show` wrapping large TRIS ranges (e.g., >20% of the object's indices) in scenery OBJs.

**Threshold** *(heuristic)*. Flag when hidden geometry exceeds a few thousand vertices or the object is heavily placed.

**Auto-fix.** None safe. Recommendation text: convert to LOD or split into separate OBJs.

---

## 3. Too many / too-large HDR spill lights

**What it is.** Overuse of spill-emitting lights (`LIGHT_PARAM` full-custom-halo/spill params, `LIGHT_SPILL_CUSTOM`, spill-variant named lights) on aprons, and use of the dataref-driven `LIGHT_SPILL_CUSTOM` form where a parameterized light would do.

**Why it costs frames.** [Laminar] X-Plane uses deferred shading precisely to allow many spill lights, but "global illumination isn't free… the main cost is an increase in VRAM use and fill-rate," and overlapping spill volumes compound fill cost ([X-Plane 10 and Global Illumination](https://developer.x-plane.com/2010/08/x-plane-10-and-global-illumination/), [HDR Isn't Just HDR](https://developer.x-plane.com/2013/12/hdr-isnt-just-hdr-what-does-that-hdr-check-box-do/)). Spill cost scales with **screen area covered**, so a big dim spill is worse than a small bright one (widely circulated Laminar guidance; the primary wiki page hosting the exact wording is gone — treat the area-scaling claim as [Laminar-derived, secondary]). Directly authoritative: "For scenery the param-light version may be notably faster when used many times in an object… if you're building a light used a lot (a streetlight, a taxiway light, an airport lighting fixture) you really want that param version" ([Customizing Spill Lights – Two Ways](https://developer.x-plane.com/2013/04/customizing-spill-lights-two-ways/)). [Forum] Night-FPS collapse at big payware airports is common enough that a mod exists solely to swap apron spill lights for cheaper ones, with multi-FPS gains reported ([XP12: regain FPS at night (simplified apron light)](https://forums.x-plane.org/files/file/84384-xp12-regain-fps-at-night-simplified-apron-light/); [LFPG night FPS reports therein]).

**Detection.** Parse OBJs for `LIGHT_SPILL_CUSTOM`, `LIGHT_PARAM` (with spill-capable light names — carry a table from Laminar's `lights.txt`), and spill-variant `LIGHT_NAMED`. Extract spill **size/radius** parameter where present. Multiply per-OBJ light count by DSF placement count. Additionally, using placement coordinates + spill radii, estimate pairwise spill-volume overlap on aprons.

**Threshold** *(heuristic)*. Flag: (a) total spill lights per airport > ~500–1,000; (b) individual spill radius > ~50–60 m; (c) >2–3 mutually overlapping spills at one location; (d) any `LIGHT_SPILL_CUSTOM` with a dataref in an object placed many times.

**Auto-fix.** Swapping `LIGHT_SPILL_CUSTOM` (constant dataref/no dataref) to an equivalent `LIGHT_PARAM` is mechanical and Laminar-endorsed. Radius reduction or light thinning changes appearance — offer as opt-in fix.

---

## 4. Overlapping apt.dat pavement and excessive taxiway node counts

**What it is.** Layered taxiway polygons (pavement stacked on pavement) and taxiway outlines built from huge numbers of bezier/plain nodes.

**Why it costs frames.** [Laminar] "Overlapping a lot of pavement in an airport can also consume fill rate… Don't overlap pavement in apt.dat files" ([Calculating Rendering Load](https://developer.x-plane.com/article/calculating-rendering-load/)). [Laminar] The apt.dat/WED guidance: describe shapes "with the fewest number of nodes possible" and let X-Plane subdivide beziers at runtime; overlaps are formally illegal ("taxiways may not have overlaps") and can even make pavement disappear at some rendering settings ([Dude, Where's My Taxiway?](https://developer.x-plane.com/2014/10/dude-wheres-my-taxiway/), [apt.dat spec](https://developer.x-plane.com/article/airport-data-apt-dat-12-00-file-format-specification/)).

**Detection.** Parse apt.dat rows 110/111–116 (taxiway polygons + nodes). Compute: (a) total node count per polygon and per airport; (b) polygon–polygon overlap area (tessellate beziers at fixed error, then boolean intersect); (c) self-intersections.

**Threshold** *(heuristic)*. Flag polygons > ~300 nodes; airports > ~10,000 pavement nodes total; any pairwise overlap area beyond a small intersection tolerance (Laminar: "a small overlapping intersection is not so bad" but avoid "layering a huge polygon on top of another huge polygon").

**Auto-fix.** Self-intersection and exact-duplicate-node cleanup is mechanical. Polygon simplification (Douglas-Peucker with bezier preservation) is possible but visually risky — opt-in. De-overlapping is geometry redesign — flag-only.

---

## 5. Over-dense forests (.for)

**What it is.** Forest files with tight `SPACING`, `DENSITY 1.0`, and forest polygons covering large DSF areas.

**Why it costs frames.** [Laminar] Forest spec: "Smaller numbers pack the forest tighter and cause the sim to run slower (since more trees must be used to fill an area)"; the `LOD` command trades draw distance for FPS, and **in X-Plane 12 the LOD command is honored again** ([Forest (.for) spec](https://developer.x-plane.com/article/forest-for-file-format-specification/)). [Laminar] Forests are patch-class geometry and "the biggest consumer of bus bandwidth is patches… forests particularly strain this resource with hundreds of thousands of trees" ([Calculating Rendering Load](https://developer.x-plane.com/article/calculating-rendering-load/)). [Community] alpilotx (author of the HD meshes): higher density directly raises RAM and hurts performance in heavily forested regions ([Old Forest FAQ](https://www.alpilotx.net/faq/old-forest-faq/)).

**Detection.** Parse `.for`: `SPACING`, `RANDOM`, `DENSITY`, `LOD`, and (XP12) `MESH`/`TREE2` `lod_far` and `NO_SHADOW`. From the DSF overlay, sum forest polygon areas × density → estimated tree count per tile.

**Threshold** *(heuristic)*. Flag SPACING < ~15 m applied over > ~1 km² of polygons; estimated >100k trees per tile; missing `LOD` line; XP12 3D-tree meshes lacking `NO_SHADOW` on small clutter ("useful when building small clutter objects… without increasing the computational burden too much" — [Laminar, forest spec]).

**Auto-fix.** Adding/clamping a `LOD` value and adding `NO_SHADOW` to sub-meter clutter meshes are safe mechanical fixes. Raising SPACING changes appearance — opt-in with preview.

---

## 6. Facade over-stretching and per-instance memory

**What it is.** Facade placements stretched far beyond the .fac's designed panel dimensions, and very large/complex facade rings.

**Why it costs frames.** [Laminar] Facades are **non-shared meshes**: "each facade instance consumes additional memory since facades are individually unique"; "at most a facade instantiation should be no larger than twice its ideal size either horizontally or vertically." Their worked example: a facade extended 10×10 produces 40,000 polygons instead of 1,600 ([Performance Tuning and Scenery](https://developer.x-plane.com/article/performance-tuning-and-scenery/), [Facade Tuning and Tips](https://developer.x-plane.com/2010/07/facade-tuning-and-tips/)). Laminar also notes facade cost usually manifests as **memory exhaustion before framerate** — so bill this under your VRAM/RAM estimate, not raw FPS.

**Detection.** Parse `.fac` wall definitions (panel min/max widths, FLOORS/height rules); parse DSF facade placements (ring perimeter, height). Compute stretch ratio = placed panel width / ideal width, and floors implied by height.

**Threshold.** Stretch ratio > 2.0 in either axis (**published Laminar number**). Also *(heuristic)*: single facade rings with > ~100 nodes; thousands of facade instances per tile → fold into RAM estimate.

**Auto-fix.** None safe (requires re-segmenting placements in WED). Flag with the specific offending placements.

---

## 7. Orthophoto mistakes: .pol instead of .ter, missing LOAD_CENTER

**What it is.** Large-area orthos done as draped polygons over the default mesh, and/or ortho textures without `LOAD_CENTER`.

**Why it costs frames.** [Laminar] "Since .pol files cover the base mesh, you pay for your mesh twice – once when X-Plane draws the base mesh and once when it covers over it with polygons. This means twice the VRAM used to draw a frame and twice the fill rate. If you want high performance orthophotos over an area any larger than an airport or down-town, please use .ter files!" And: use "DDS and only DDS" for orthos; `LOAD_CENTER` "saves VRAM, since textures that are far away won't be loaded at full resolution" ([Three Things You Need for Fast Orthophotos](https://developer.x-plane.com/2011/03/three-things-you-need-for-fast-orthophotos/), [DDS Revisited in X-Plane 10](https://developer.x-plane.com/2012/01/dds-revisited-in-x-plane-10/)).

**Detection.** You already catch PNG orthos generically. Add: (a) `.pol` files whose DSF polygon coverage exceeds a threshold area; (b) `.pol`/`.ter` referencing textures ≥2048px with **no `LOAD_CENTER`** directive.

**Threshold** *(heuristic)*. Flag `.pol` ortho coverage > ~4–10 km² ("larger than an airport or down-town" per Laminar); flag any ≥2048px ortho texture missing LOAD_CENTER.

**Auto-fix.** **`LOAD_CENTER` insertion is fully mechanical**: centroid lat/lon from the DSF polygon(s) using the texture, resolution = texture size, size = polygon extent in meters. This is a high-value fix nobody else automates. `.pol`→`.ter` conversion requires mesh rebuilding — flag-only.

---

## 8. Missing exclusion zones (double scenery)

**What it is.** Overlay packs that place objects/facades/forests without DSF exclusion properties, so default autogen/airports render underneath simultaneously.

**Why it costs frames.** [Laminar] "Custom overlay scenery packs should have exclusion zones to mask out the scenery below them, whether it is autogen, airports, or rogue trees" ([WED manual](https://developer.x-plane.com/manuals/wed/), [Prioritizing Scenery and Exclusion Zones](https://developer.x-plane.com/2014/09/prioritizing-scenery-and-exclusion-zones/)). [Forum] Semi-automated packs missing exclusions cause X-Plane "to draw both objects and thus double the load."

**Detection.** Parse the DSF overlay header properties: `sim/exclude_obj`, `sim/exclude_fac`, `sim/exclude_for`, etc. Flag packs with substantial placement counts (say >100 objects or any facades/forests) and zero exclusion properties.

**Threshold.** Presence/absence check; no numeric threshold needed.

**Auto-fix.** Semi-mechanical: propose an exclusion rectangle from the placements' bounding box, but require user confirmation (over-exclusion visibly blanks autogen — a known complaint). Do not apply silently.

---

## 9. Needless alpha channels / blending

**What it is.** Fully opaque textures saved with an alpha channel, or alpha-blended materials with no actually-translucent pixels.

**Why it costs frames.** [Laminar] "If your texture does not have any transparent parts, make sure to save it without an alpha channel"; semi-transparent pixels are slower than fully transparent ones; alpha also doubles/inflates VRAM in some DDS formats (DXT1 vs DXT5) ([Performance Tuning and Scenery](https://developer.x-plane.com/article/performance-tuning-and-scenery/)). This complements your blend ping-pong check: even with clean ATTR state, blending itself costs ROP/fill and defeats early-Z.

**Detection.** Scan texture alpha channels: if min(alpha) ≥ ~250 across all pixels, the alpha is dead weight. Check whether the OBJ/pol uses `GLOBAL_no_blend`/`ATTR_no_blend`.

**Threshold.** All-opaque alpha channel = flag. *(Direct check, no tuning needed.)*

**Auto-fix.** Fully mechanical and safe: re-encode DDS as DXT1/BC1 (no alpha), and/or add `GLOBAL_no_blend` to draped pols whose textures are opaque. Fits your existing DDS pipeline.

---

## 10. Oversized OBJ spatial extent (>1 km objects)

**What it is.** Single OBJs spanning huge areas (whole-airport ground polys or merged mega-objects), which defeat frustum culling and LOD.

**Why it costs frames.** [Laminar] "The ideal object dimensions are no larger than 1000 meters on a side – 500 meters on a side is good"; conversely don't go below ~24 vertices per object ([Performance Tuning and Scenery](https://developer.x-plane.com/article/performance-tuning-and-scenery/)). (Your tiny-object check covers the low end; this is the high end.)

**Detection.** Bounding box from `VT` records.

**Threshold.** > 1,000 m on a side (**published Laminar number**); warn at > 2,000 m.

**Auto-fix.** None safe (splitting changes batching and texture atlases). Flag-only.

---

## 11. Hard surfaces on decorative geometry — include, but low severity

**What it is.** `ATTR_hard`/hard "quads" on high-poly decorative meshes.

**Evidence check.** [Laminar] Explicitly: "The simulator is very good at handling ATTR_hard" and it's listed among the "cheap" attributes — though any attribute can still add a batch: "A single attribute in an OBJ can add one batch and make the OBJ twice as slow on the CPU" ([Optimizing Object Performance](https://developer.x-plane.com/article/optimizing-object-peformance/)); "hard quad" commands are called out as more expensive than regular quads ([Performance Tuning](https://developer.x-plane.com/article/performance-tuning-and-scenery/)). **Verdict:** report as INFO-level only (batch splitting + physics testing), not a headline check. Your suspicion of a big FPS cost is *not* supported by sources.

**Detection/fix.** Count `ATTR_hard`/`ATTR_hard_deck` scopes per OBJ; flag multiple toggles (batch churn) rather than presence. Consolidating consecutive hard/unhard toggles by reordering TRIS is mechanically possible but you likely already do this under ATTR-state lints.

---

## 12. Road networks (.net) — weak/indicative only

[Laminar] Road networks map to patch/vehicle rendering load ([Calculating Rendering Load](https://developer.x-plane.com/article/calculating-rendering-load/)) and the roads + cars rendering settings are called out as CPU-heavy ([Setting the Rendering Options for Best Performance](https://www.x-plane.com/kb/setting-the-rendering-options-for-best-performance/)) — but there is **no authoritative guidance on custom .net authoring costs**, and custom road overlays are rare. Suggest: skip, or INFO-level note when a pack ships a dense custom road DSF.

---

## Non-issues (evidence says don't lint these)

- **Decals**: [Laminar] "Because the decal is part of the shading process… the performance impact is quite low" ([Using Decals to Add Detail to Scenery](https://developer.x-plane.com/article/using-decals-to-add-detail-to-scenery/)). Only nuance: an alpha-only decal saves VRAM vs RGB.
- **ATTR_draped geometry in OBJs**: [Laminar] "A draped-only OBJ should have the same cost as a pol"; draped triangles ignore attribute state and are batched like polygons ([Draped Object Geometry in X-Plane 10](https://developer.x-plane.com/2010/10/draped-object-geometry-in-x-plane-10/), [Draping Part 3](https://developer.x-plane.com/2011/04/draping-part-3-how-do-you-use-draping/)). The cost of draped stuff is **overdraw**, which you already check. Don't add a separate "too much ATTR_draped" lint.
- **Weather/volumetrics interactions**: no author-side evidence found; XP12 weather cost is a sim setting, not a package property. Skip.
- **3D vegetation on orthos**: no authoritative evidence of a distinct pitfall beyond ordinary forest density (Section 5). Skip as its own check.

---

## X-Plane 12-era changes that alter advice

- **Forest LOD is honored again**: "In X-Plane 12, the LOD command is no longer ignored" — a `.for` LOD lint is now meaningful where it was dead weight in XP11 ([forest spec](https://developer.x-plane.com/article/forest-for-file-format-specification/), Laminar).
- **XP12 3D trees**: `MESH`/`TREE2` support up to 4 LOD steps and "a 3-d tree will always have a 2-d billboard tree as its last LOD step"; `NO_SHADOW` exists specifically to cut shadow cost of clutter (Laminar, forest spec).
- **Photometric lighting (12.x)**: light brightness is now in real units (candela); this changes *brightness* authoring, and the deferred-lighting cost model (spill area = cost) still applies ([Crash Fixing, Airports, Photometric Lighting](https://developer.x-plane.com/2021/06/crash-fixing-airports-photometric-lighting/), Laminar). [Forum] Night-FPS complaints persist in XP12, so the spill-light lint remains relevant.
- **12.4 multicore scene traversal**: "Scene graph traversal and rendering… make up the bulk of frame time, sometimes up to 75%. The more demanding your scenery, the more time will be spent on this task" — traversal is now parallelized, but "actual drawing of the scene is still single-threaded," so batch-count and object-count lints remain valid ([The glorious multi core future…](https://developer.x-plane.com/2025/12/the-glorious-multi-core-future-is-now-the-boring-present/), Sidney Just, Laminar).
- **Frame-time framing**: Laminar now explicitly recommends reasoning in ms/frame, not FPS — worth adopting in your report UI ([A very quick performance primer](https://developer.x-plane.com/2025/12/a-very-quick-performance-primer/), Laminar).
- **Object budget context**: "Most users can draw 3,000–8,000 objects per frame," and 10,000+ tiny objects are fine *if* LOD distances are short (KORD taxiway-light example) — useful calibration for your existing draw-call-flood thresholds ([Optimizing Object Performance](https://developer.x-plane.com/article/optimizing-object-peformance/), Laminar).

## Highest-value additions, ranked

1. **LOAD_CENTER auto-insertion for large ortho textures** (mechanical, Laminar-endorsed, unserved niche).
2. **Instancing-killer animation detection + degenerate-ANIM baking** (mechanical fix for the degenerate case).
3. **Spill-light census with radius/overlap scoring** (auto-fix: custom→param conversion).
4. **Dead alpha channel stripping** (fully safe auto-fix, extends your DDS pipeline).
5. **apt.dat overlap/node-count lint** (detection only, but overlaps are formally illegal per Laminar).
6. **Facade stretch-ratio lint** (published 2× threshold).
7. **Missing exclusion zones** (detection + confirmed fix).