# XPTerrainBuilder 1.0.573-beta.8

**Beta 8 — a prerelease for outside testers.** Beta 8 brings **dynamic scenery
loading**: the app keeps one World scenery pack, builds tiles with light
placeholder imagery, and fetches full-detail photos around your aircraft as
you fly. What needs testing most is a real flight with it switched on, from
planning to landing. Read *Known issues* first, and the
[testing guide](https://github.com/shizumaat/XPTerrainBuilder/blob/v1.0.573-beta.8/docs/TESTING-GUIDE.md)
for a first build, step by step.

## What this is

XPTerrainBuilder builds X-Plane photoscenery ("ortho" scenery): you pick
1°×1° tiles on a map, choose an imagery provider and build options, and it
produces the mesh, textures and DSF files X-Plane needs. It additionally
regrades paved airport surfaces to FAA/EASA/ICAO geometry instead of draping
them over raw elevation data, and reseats custom airport objects onto the
surface it built.

It is a fork and derivative of
**[Ortho4XP](https://github.com/oscarpilote/Ortho4XP) by Oscar Pilote**.

## What's new in Beta 8

- **Dynamic scenery loading.** Every tile the app builds goes into one Custom
  Scenery pack, `zXPTerrainBuilder World`. New tiles are built with 512 px
  placeholder imagery, and sharp imagery is downloaded ahead of the aircraft,
  like a video stream that buffers ahead. Tiles beyond your plan are laid as
  photo drapes over the default terrain.
- **Fly mode.** The app now has two modes, Build and Fly. Pick a flight plan
  (X-Plane .fms, SimBrief, a quick From/To, or just follow the aircraft) and
  the app prepares the airports and the corridor along the route.
- **One disk budget.** Settings › Storage holds a single budget for everything
  the app stores. It clears the least recently used tiles first and keeps your
  favourites longest. An optional external drive (storage tier) holds sharp
  imagery and rebuild data, and every tile still flies without it.
- **Generated taxiway and road bridges.** Where an airport package has none,
  the app builds bridge decks with Laminar materials, line art and cuts
  underneath (ESSA, KJFK). Generated decks are as wide as the taxiway's FAA
  safety area and carry its centreline. A package object that combines several
  bridges is replaced whole, so the taxiway follows the terrain (KMCO, KRDU,
  KIAH). Airports drawn from X-Plane's Global Airports are offered the Gateway
  version so they can get bridges too.
- **Tile packages (.xptb).** A small shareable rebuild file without imagery.
  Double-click or drag one in to install it.
- **Adjust a modified airport without a rebuild.** Change what is hidden or
  optimised in an airport package from its row under Modified airports.
- **Cliff textures.** Steep cliff faces get X-Plane's own rock instead of a
  stretched photo, by default.

## Quick start: dynamic scenery loading

It is on by default. These steps take a new or existing install to a first
flight.

1. **Quit X-Plane, then open the app.** On first run it creates the
   `zXPTerrainBuilder World` pack and asks "Let XPTerrainBuilder manage your
   ortho tiles?". Choose **Move…** to bring your existing ortho tiles under one
   disk budget (Undo is available), or **Not now** to do it later from
   Settings › Storage › Convert existing tiles. Tiles built by other tools are
   adopted, not rebuilt.
2. **Set your disk budget** in Settings › Storage › Disk budget. The slider
   runs from the minimum (world placeholders plus your airport packages) to as
   much as fits while keeping 50 GB free. Nothing is cleared until you press
   **Confirm**.
3. **Optional: add a storage tier.** Under Storage tiers, add an external
   drive and its size. Sharp imagery and rebuild data move there instead of
   being deleted. When the drive is unplugged, imagery is downloaded again, and
   every tile still flies.
4. **Choose your regions.** In Settings, "On demand in Europe?" (and America,
   Asia, Africa, Australia-Oceania, Antarctica) turns the system on per region.
   Where a region is off, tiles build at full resolution as before.
5. **Plan a flight in Fly mode.** Choose a flight (X-Plane's FMS Plans are read
   automatically), fetch your latest SimBrief plan, type a quick From/To, or
   pick "No plan: follow the aircraft". Press **Prepare flight**; the departure
   and destination airports build first.
6. **Start X-Plane and fly.** The app follows the aircraft through X-Plane's
   Web API and fetches sharp imagery ahead of you. "Photo detail ahead" in the
   Fly pane sets the drape detail (512, 1024 or 4096 px). When sharper imagery
   lands in an area X-Plane already loaded, the app offers **Reload scenery**.

Tip: with on-demand on, the Build box hides "Install in X-Plane automatically"
and "Skip tiles already built". Built tiles always go straight into the World
pack, and the disk budget manages space.

## Other new features

- **Gateway airport offer.** "Install airports from the X-Plane Gateway?"
  appears for airports with a flatten tag, airports that could get bridges,
  and Gateway updates (#1989, #2169).
- **Hide terrain objects included with the package.** Packages that model
  hills as objects can hide them where good elevation data covers the area. On
  by default (#1914, #2036).
- **Overlapping packages.** Where two packages draw the same buildings, the
  app offers to hide the duplicates; the airport package wins by default
  (#2145). Generic ground textures other packages drape over a tile can be
  hidden too (#2085).
- **Sharper approaches.** Airport imagery follows each approach on a 3° glide
  path, set by "How far along the approaches (ft on a 3° glide path)?" (#1990).
- **Custom patches.** An airport covered by your own patch keeps its scenery
  package unmodified, as the patch's author designed it. Turning on "Fit custom
  airport buildings to the new ground" asks you to confirm and names the
  airports it affects (#2171).
- **Patch editor.** Duplicate a shape, and read or edit whole-shape elevations
  and sloping rectangles (#1963, #2137).
- **Map.** One shared key on Build and Fly, a Filter menu for airports and
  ortho tiles, and tiles on an external drive shown as "Requires <volume>"
  (#2031, #2097, #1987). An "Airport patch" item in the Filter menu shows patch
  shapes, and build history has titles and zoom (#2214, #2199).
- **Overlays.** Full tiles get X-Plane roads, forests and buildings in
  `yXPTerrainBuilder Overlays` (#2021).
- **Elevation sources.** FABDEM ranks above Copernicus where no national
  source exists; Svalbard 5 m data is added (#1942, #1926).
- **Engine name.** The build engine's processes now show as
  XPTerrainBuilderEngine in Activity Monitor (#2164).

## Improvements and fixes

Verified in the sim for Beta 8: KEGE, BIKF, KSUN, KBTV, EGNS, LICJ, ENTC,
KDEN, KBNA, OTHH, LOWS, NZWN, OMDB, LGAV, LPPD, KMCO, KRDU and KBUF.

**Airport terrain**

- Gaps inside an airport patch follow the elevation data instead of a flat
  fill, so valleys stay valleys (KDEN) #2155
- Roads leaving taxiways weld and follow the terrain; public roads climb up to
  20 % where the ground demands it (KEGE, LPPD) #1982 #2152
- Builds that used to fail now complete: EFHK, KHOU, KSFO, LSZI, KTUL, KBHM
  #2084 #2051 #2038 #1912 #2170
- Continuous apron between KBNA concourses, graded car parks and service roads
  #2111–#2114
- Paved strips beside taxiways grade as the taxiway's shoulder, with no wall or
  drop at the infield edge (KBIL) #2223

**Bridges and tunnels**

- Every bridge end meets graded ground, and cuts run fully under decks and
  road bridges #2141
- Multi-piece elevated rail and road decks follow the slope instead of
  stair-stepping (KLAX, OMDB, HECA) #2144
- An airport package's own bridge pieces are hidden where the app's bridge
  replaces them (KJFK, OMDB) #2167 #2163
- False pits and tunnels removed at KMCI, OTHH, LFMN, KDEN and KEYW
- Tunnel mouths on long mapped tunnels are cut and seated again (KBUF) #2221

**Buildings and objects**

- Floating and sunken buildings fixed at KEGE, KBZN, EFHK, LOWS, OTHH, ENTC
  and EDDH; stacked car-park decks ride their walls #2129
- XP11 trees upgraded to XP12 species, with no tall trees beside runways
  #1920 #1965
- Draped photo layers in airport packages are detected and hidden on every
  tile they cover (EDDH, LGSR, CYLW) #1943 #1968

**Imagery**

- Inland lakes and rivers get the soft shoreline #1981
- Your departure airport stays sharp, with no colour jump between detail
  levels #2032 #2017

**App**

- Builds share one machine-wide memory budget and no longer run the Mac out of
  memory #2083
- Modified-airport buttons are blocked only while a build is writing that
  package #2168
- A comma list in Build search builds every airport #2043
- The last build stages run once instead of three times, saving about half an
  hour on the largest airports (KATL) #2206
- A rebuilt tile reaches X-Plane even while sharper imagery is loading around
  it #2224
- A failed map-extract download is retried after 6 hours instead of sending
  the region to the slower OSM server for a week #2201
- The storage budget is saved at once and its slider stays live #2162
- The app asks for write access only to a pack folder a build edits #2198

## Known issues (planned for Beta 9)

- Placeholders are still 512 px, so a whole-world install needs more disk than
  planned; 1 px colour placeholders are coming #2147
- The Storage panel can take a while to open #2161
- Big airports are still slow to auto-patch (KATL about an hour, KDFW about
  27 min) #2206 #1706 #1951
- Some bridge and deck cases remain: ESSA embankment smoothing #2165, RJTT
  pier decks #2156, KDEN rail under two road decks #1971, the EDDH terminal
  driveway ends #2129, the LFPG two-level terminal #1717
- More bridge and tunnel cases: KIAH road cuts under road decks, the KRDU road
  hump and overpass, CYYZ tunnels and bridges #2128 #2237–#2241
- LPPD's bluff would benefit from better elevation data #2166
- Sharp imagery can end in a visible line over water #2049
- TFFF builds without its airport patch, and EKVG's runway is graded as a
  taxiway #2219 #2244
- Island tiles whose map extract stops short of open sea use the slower OSM
  server, and the ETA can climb while a large extract downloads #2234 #2218
- With world-wide packs such as AEP or simHeaven, the overlap prompt appears on
  every build; the Favorite star can be slow to change #2227 #2228

## Reporting problems

On a failed tile, **Report this problem** fills most of the report in for you.
Otherwise open an issue at <https://github.com/shizumaat/XPTerrainBuilder/issues>
with the airport, the coordinates and a screenshot.
