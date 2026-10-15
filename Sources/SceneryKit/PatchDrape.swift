import Foundation
import CoreGraphics
import simd

// The 3D preview's imagery drape (patch-editor spec §5, round 6c): the
// map's live-imagery tiles — the ones the app's ImageryModel already
// caches — composed into ONE texture covering the preview extent, at the
// finest zoom whose texture stays within `maxPixels` on a side.
//
// The texture covers EXACTLY the extent box in web-mercator, so a vertex's
// texture coordinate depends on the box alone (`uv`), never on the zoom:
// switching imagery source or zoom never rebuilds a vertex buffer.

public struct PatchDrapePlan: Equatable, Sendable {
    public static let tileSize = 256
    public static let defaultMaxPixels = 8192

    public let box: O4LatLonBox
    public let zoom: Int
    /// Texture size in pixels (each ≤ maxPixels).
    public let width: Int
    public let height: Int
    /// The slippy-map tiles covering the box at `zoom`.
    public let tiles: [(x: Int, y: Int)]

    public static func == (a: Self, b: Self) -> Bool {
        a.box == b.box && a.zoom == b.zoom && a.width == b.width && a.height == b.height
    }

    /// The finest zoom ≤ `maxZoom` whose texture fits `maxPixels`; nil when
    /// even zoom 0 cannot (never, for a real box).
    public init?(box: O4LatLonBox, maxZoom: Int, maxPixels: Int = defaultMaxPixels) {
        guard maxZoom >= 0 else { return nil }
        var chosen: Int?
        for z in stride(from: min(maxZoom, 22), through: 0, by: -1) {
            let (w, h) = Self.pixels(box, z)
            if w <= Double(maxPixels) && h <= Double(maxPixels) { chosen = z; break }
        }
        guard let z = chosen else { return nil }
        let (w, h) = Self.pixels(box, z)
        self.box = box
        zoom = z
        width = max(1, Int(ceil(w)))
        height = max(1, Int(ceil(h)))
        let x0 = Int(floor(WebMercator.tileX(lon: box.minLon, z: z)))
        let x1 = Int(floor(WebMercator.tileX(lon: box.maxLon, z: z) - 1e-9))
        let y0 = Int(floor(WebMercator.tileY(lat: box.maxLat, z: z)))
        let y1 = Int(floor(WebMercator.tileY(lat: box.minLat, z: z) - 1e-9))
        var t: [(x: Int, y: Int)] = []
        for y in y0...max(y0, y1) { for x in x0...max(x0, x1) { t.append((x, y)) } }
        tiles = t
    }

    private static func pixels(_ b: O4LatLonBox, _ z: Int) -> (Double, Double) {
        let s = Double(tileSize)
        return ((WebMercator.tileX(lon: b.maxLon, z: z) - WebMercator.tileX(lon: b.minLon, z: z)) * s,
                (WebMercator.tileY(lat: b.minLat, z: z) - WebMercator.tileY(lat: b.maxLat, z: z)) * s)
    }

    /// Where tile (x, y) lands in the texture, pixels, origin TOP-LEFT
    /// (north-west); partly outside for the tiles on the box's edges.
    public func rect(x: Int, y: Int) -> CGRect {
        let s = Double(Self.tileSize)
        let ox = WebMercator.tileX(lon: box.minLon, z: zoom) * s
        let oy = WebMercator.tileY(lat: box.maxLat, z: zoom) * s
        return CGRect(x: Double(x) * s - ox, y: Double(y) * s - oy, width: s, height: s)
    }

    /// A point's texture coordinate: u east 0…1, v SOUTH 0…1 (v = 0 is
    /// the box's north edge, the texture's top row).
    public static func uv(lat: Double, lon: Double, box: O4LatLonBox) -> SIMD2<Float> {
        let x0 = WebMercator.tileX(lon: box.minLon, z: 0), x1 = WebMercator.tileX(lon: box.maxLon, z: 0)
        let y0 = WebMercator.tileY(lat: box.maxLat, z: 0), y1 = WebMercator.tileY(lat: box.minLat, z: 0)
        return SIMD2(Float((WebMercator.tileX(lon: lon, z: 0) - x0) / (x1 - x0)),
                     Float((WebMercator.tileY(lat: lat, z: 0) - y0) / (y1 - y0)))
    }
}
