"""KML of the OTHH bridge structures, split by whether they currently get a
terrain cutout — for the owner's ruling.

Each bridge is outlined twice: its WHOLE solid footprint (thin line) and the
BELOW-GRADE portion that a cutout would carve (filled).  Descriptions carry
the classifier's current verdict and the measured numbers behind it.

Run from Ortho4XP/ cwd.
"""
import os
import pickle
import sys
from collections import defaultdict
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from shapely.geometry import Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from auto_patch import dsf_reader, obj8_reader  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _load_object_geometry_by_resource,
)

XP = "/Users/noah/X-Plane 12"
DSF = os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                   "Earth nav data", "+20+050", "+25+051.dsf")
CACHE = ("Airport_mod_cache/OTHH Doha (Aeroscape)/"
         "o4_object_terrain_classification_+25+051.cache")
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/OTHH_bridges.kml"

#: the owner's threshold — below this counts as below grade
BELOW_GRADE_M = 1.0

lines = dsf_reader._load_dsf_text(DSF)
terrain = [p for p in obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"))
    if p.placement_kind != "OBJECT_MSL"]
geometry = _load_object_geometry_by_resource(
    terrain, dsf_reader._pack_root_for_dsf(DSF), XP)
result = pickle.load(open(CACHE, "rb"))["result"]

# ── current verdict per resource ─────────────────────────────────────
carved, verdict = set(), {}
for tunnel in result.tunnels:
    for resource in tunnel.object_resources:
        carved.add(resource)
        verdict[resource] = "TUNNEL — trench cut today"
for bridge in result.bridges:
    for resource in bridge.object_resources:
        carved.add(resource)
        verdict[resource] = "BRIDGE — deck/trench handled today"
for refusal in result.refusals:
    for resource in refusal.object_resources:
        verdict[resource] = "REFUSED — " + refusal.reason
for interface in result.ground_interfaces:
    label = interface.interface_class
    if otf.is_carved_basin_interface(interface):
        carved.update(interface.object_resources)
        label += " — basin trench cut today"
    else:
        label += (
            f" — no cutout (ground contact "
            f"{interface.ground_contact_fraction:.3f}, wall base at grade "
            f"{interface.at_grade_wall_base_share:.3f}, above-grade area "
            f"{interface.above_grade_area_fraction:.3f})")
    for resource in interface.object_resources:
        verdict[resource] = label

# ── group bridge placements by family (OTHH_Bridge_NN) ───────────────
families = defaultdict(list)
for placement in terrain:
    base = os.path.basename(placement.resource_path)
    if "Bridge_" not in base:
        continue
    key = base.split("Bridge_")[1][:2]
    if not key.isdigit():
        continue
    families[f"Bridge_{key}"].append(placement)

print(f"bridge families: {sorted(families)}")


def outline(placements, only_below_grade):
    """Plan outline of the pool's solid geometry as a lon/lat polygon.

    Unions TWO sources, because neither is complete on its own:

    * the frame's TRIANGLES fill horizontal extents (a below-grade slab's
      interior), but a perfectly vertical pier/abutment/shaft face has
      zero horizontal area and is dropped from the triangle list — a
      triangle-only union drew NOTHING for Bridge_04 and Bridge_05;
    * the frame's RAW VERTEX COLUMNS (1 m grid over every solid vertex)
      catch those vertical faces, but are sparse over a large flat slab
      whose interior carries no vertices — a column-only union collapsed
      Bridge_02 from 4 058 m2 to 87 m2.

    Their union is the plan extent a cutout would have to clear."""
    frame = otf._build_structure_frame(placements, geometry)
    grid = otf.WALL_COLUMN_GRID_M
    half = grid / 2.0
    pieces, deepest = [], 0.0
    corner_x = frame.triangle_corner_x_m
    corner_y = frame.triangle_corner_y_m
    corner_z = frame.triangle_corner_z_m
    for index in range(frame.triangle_count):
        low = float(min(corner_y[index]))
        deepest = min(deepest, low)
        if only_below_grade and low >= -BELOW_GRADE_M:
            continue
        polygon = Polygon([
            (float(corner_x[index][k]), float(corner_z[index][k]))
            for k in range(3)])
        if polygon.is_valid and polygon.area > 0.0:
            pieces.append(polygon)
    for (grid_x, grid_z), column in (frame.vertex_columns or {}).items():
        low = float(column[0])
        deepest = min(deepest, low)
        if only_below_grade and low >= -BELOW_GRADE_M:
            continue
        centre_x, centre_z = grid_x * grid, grid_z * grid
        pieces.append(Polygon([
            (centre_x - half, centre_z - half),
            (centre_x + half, centre_z - half),
            (centre_x + half, centre_z + half),
            (centre_x - half, centre_z + half)]))
    if not pieces:
        return None, deepest
    merged = unary_union(pieces)
    if merged.is_empty:
        return None, deepest
    merged = merged.simplify(0.25)
    return otf.frame_polygon_to_longitude_latitude(
        merged, (frame.origin_longitude, frame.origin_latitude)), deepest


def rings_of(geom):
    parts = (list(geom.geoms) if geom.geom_type == "MultiPolygon"
             else [geom])
    for part in parts:
        if part.geom_type != "Polygon" or part.is_empty:
            continue
        if part.area * 111132.0 * 100694.0 < 4.0:
            continue
        yield part


def polygon_kml(part):
    def ring(coords):
        return " ".join(f"{lon:.9f},{lat:.9f},0" for lon, lat in coords)
    inner = "".join(
        f"<innerBoundaryIs><LinearRing><coordinates>{ring(h.coords)}"
        "</coordinates></LinearRing></innerBoundaryIs>"
        for h in part.interiors)
    return (
        "<Polygon><altitudeMode>clampToGround</altitudeMode>"
        "<outerBoundaryIs><LinearRing><coordinates>"
        f"{ring(part.exterior.coords)}"
        "</coordinates></LinearRing></outerBoundaryIs>"
        f"{inner}</Polygon>")


STYLES = """
<Style id="nocut"><LineStyle><color>ff2222dd</color><width>3</width>
</LineStyle><PolyStyle><color>7d2222dd</color></PolyStyle></Style>
<Style id="cut"><LineStyle><color>ff22cc44</color><width>3</width>
</LineStyle><PolyStyle><color>5522cc44</color></PolyStyle></Style>
<Style id="whole"><LineStyle><color>ffcccccc</color><width>2</width>
</LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style>
"""

body, summary = [], []
for family in sorted(families):
    placements = families[family]
    resources = sorted({p.resource_path for p in placements})
    is_carved = any(r in carved for r in resources)
    verdicts = sorted({verdict.get(r, "— no classifier record —")
                       for r in resources})
    below, deepest = outline(placements, True)
    whole, _ = outline(placements, False)
    below_area = 0.0
    if below is not None:
        below_area = sum(p.area for p in rings_of(below)) * 111132.0 * 100694.0
    summary.append((family, is_carved, deepest, below_area, len(placements),
                    len(resources)))
    description = (
        f"<![CDATA[<b>{family}</b><br/>"
        f"placements: {len(placements)} &nbsp; resources: {len(resources)}"
        f"<br/>deepest solid: <b>{deepest:.2f} m</b> below grade<br/>"
        f"below-grade footprint: <b>{below_area:,.0f} m2</b><br/>"
        f"cutout today: <b>{'YES' if is_carved else 'NO'}</b><br/><br/>"
        "<u>classifier verdict</u><br/>"
        + "<br/>".join(escape(v) for v in verdicts) + "]]>")
    placemarks = []
    if whole is not None:
        for part in rings_of(whole):
            placemarks.append(
                f"<Placemark><name>{family} — whole footprint</name>"
                f"<styleUrl>#whole</styleUrl>{polygon_kml(part)}</Placemark>")
    if below is not None:
        style = "cut" if is_carved else "nocut"
        for part in rings_of(below):
            placemarks.append(
                f"<Placemark><name>{family} — below grade "
                f"({deepest:.1f} m)</name>"
                f"<description>{description}</description>"
                f"<styleUrl>#{style}</styleUrl>"
                f"{polygon_kml(part)}</Placemark>")
    body.append(
        f"<Folder><name>{family} — "
        f"{'cutout today' if is_carved else 'NO CUTOUT'}</name>"
        f"<description>{description}</description>"
        + "".join(placemarks) + "</Folder>")

kml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
    "<name>OTHH bridges — below-grade geometry and cutout status</name>"
    "<description><![CDATA[Red = no terrain cutout today. "
    "Green = already cut. Grey outline = the whole solid footprint; the "
    "filled shape is only the portion reaching more than 1 m below "
    "grade.]]></description>"
    + STYLES + "".join(body) + "</Document></kml>")

with open(OUT, "w") as handle:
    handle.write(kml)

print(f"\nwrote {OUT}  ({len(kml):,} bytes)")
print(f"\n{'family':12s} {'cutout':7s} {'deepest':>9s} {'below m2':>10s} "
      f"{'places':>7s} {'resources':>10s}")
for family, is_carved, deepest, area, n_place, n_res in summary:
    print(f"{family:12s} {'YES' if is_carved else 'NO':7s} {deepest:9.2f} "
          f"{area:10,.0f} {n_place:7d} {n_res:10d}")
