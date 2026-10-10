# Beta 2 release notes — DRAFT (bullets)

Draft for the owner's review. At tag time these bullets go into
`docs/RELEASE_NOTES-<version>.md` built from `RELEASE_NOTES-TEMPLATE.md`.
Changes are since 1.0.350-beta.1.

## Improvements

**Airport terrain**

- Building pads are flat right out to the building's outline, and several
  buildings standing on one apron now sit at that apron's level instead of
  each at its own height.
- Roads and parking lots that touch a building in the scenery are joined to
  its pad at the pad's level; ones drawn with a gap are left free and no
  longer drag the pad.
- Paved areas a scenery pack draws only as a ground texture or object —
  parking lots, cargo aprons, paving between buildings — are now recognised
  and graded, including pavement declared by a draped polygon's own surface
  type.
- Pavement composited from more than one scenery pack at the same airport is
  graded as one airport.
- Facades are told apart: a fence or wall line is left alone, while a facade
  that covers a building, garage or fenced lot gets a pad.
- Service roads use gentler ramps (5 % by design, 10 % at most) and ramp only
  where the ground forces it.
- Tunnel ramps, retaining walls, drainage basins and pits that a pack places
  deliberately above or below ground keep the author's placement; the
  terrain is cut to them, and the ground meets basin edges without a slot.
- A wall placed along a road is treated as a terrace: road at the top,
  ground at the bottom.
- Where a runway's published threshold elevations make it steeper than the
  normal limit, its taxiways and the apron beside it follow that grade, so
  connectors no longer dip or climb sharply (Aspen is the test case).
- Taxiway edges follow their centreline's level, and the solver now reaches
  the same surface from build to build: an unrelated change no longer shifts
  ground elsewhere on the airport.

**Elevation data**

- Elevation is now layered around each airport: 1 m at the airport where it
  exists, 10 m out to 10 km, 30 m out to 20 km, base data beyond.
- More US lidar: point-cloud survey data is used where USGS holds it and no
  1 m raster exists (51 airports, including all of Alaska's).

**Speed and feedback**

- Large airports build far faster. Doha (OTHH), about 50 minutes in beta 1,
  now takes about 9 minutes for the airport stage, using all CPU cores.
- The long airport phase reports what it is doing instead of sitting silent.
- Cancelling a tile stops it promptly; the app caches the airport list
  between launches.

## Bug fixes

**Windows**

- The app could fail to start, or silently lose elevation and imagery
  providers, on Windows set to Japanese, Chinese, Korean and some other
  regional languages. Provider and settings files are now read the same way
  on every system.
- Elevation downloads that failed on Windows in beta 1 (reported at LEMD)
  are fixed; downloads now follow redirects, so sources that moved to HTTPS
  work again.
- The packaged app now checks at build time that every bundled provider
  loaded.

**Airport terrain**

- Tunnels built where none exist (Doha, Charlotte) are no longer cut; real
  tunnel mouths that had gone missing (Lima) are back.
- Runways that came out broken or unusable on small or steep fields
  (NLWF, KASE) are fixed.
- Aprons misread as taxiways, taxiways running past an apron mouth, nested
  or jagged apron shapes, and stray spikes, pits and "tiny mountains" on
  aprons and service roads are fixed.
- Terminals and cargo buildings that sat sunken below, or perched above,
  the apron beside them now meet it.
- Groundside areas wrongly flattened to apron level, and cliffs left beside
  roads inside the runway strip, are fixed.
- Runways without published threshold elevations take their level from the
  airport's elevation instead of floating free.

**Scenery objects**

- Multi-part buildings — terminals, elevated roads, covered parking — hold
  together at one level instead of separating into floating pieces; tilted
  objects no longer lean at their own angle.
- Objects are always re-seated from the original scenery pack, so repeated
  builds no longer accumulate errors.
- Object re-seating messages no longer appear when "Modify custom airports"
  is off.

**Elevation and imagery**

- Building footprints removed from lidar no longer drop to the coarse base
  data under terminals.
- Several regional elevation services returned false sea level or no data;
  these read correctly now.
- The colour harmoniser no longer draws straight seam lines between
  textures.

## Known issues

- Building pads may still tilt slightly (up to 1 %); very large buildings
  can show it.
- Parking garages and other landside structures that touch no graded
  pavement can stand on a bank or float (seen at Charlotte's terminal
  garages and toll plaza).
- Some floating roof planes and separated building levels remain at large
  terminals (Cairo).
- A tunnel is still recognised from its map tag alone when nothing else
  confirms it.
