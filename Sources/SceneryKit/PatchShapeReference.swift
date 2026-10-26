import Foundation

/// What "Copy shape reference" puts on the clipboard (#1281): one plain-text
/// block that locates a shape exactly for an issue report — tile, airport,
/// patch file, engine version, way id, `ref`/`role`/`name` tags, centroid,
/// vertex count, area, elevation range and the first vertices. Twin of
/// `Ortho4XP/src/O4_Qt_Patch_Reference.py`; both produce the same text for
/// `Ortho4XP/tests/fixtures/patch_shape_reference.json`.
public enum PatchShapeReference {
    /// How many vertices the block lists.
    public static let firstVertices = 5
    /// The tags the block names, in this order, when the way has them.
    public static let referenceTags = ["ref", "role", "name"]

    public struct Vertex: Equatable, Sendable {
        public let lat: Double
        public let lon: Double
        public let alt: Double?

        public init(lat: Double, lon: Double, alt: Double?) {
            self.lat = lat; self.lon = lon; self.alt = alt
        }
    }

    /// The block for one shape. `vertices` are in ring order without a
    /// closed way's repeated first node.
    public static func text(tile: String, icao: String, patchFile: String, engineVersion: String,
                            wayId: Int64, tags: [String: String], closed: Bool, area: Double,
                            vertices: [Vertex]) -> String {
        var lines = ["Shape reference (XPTerrainBuilder)",
                     "Tile: \(tile)",
                     "Airport: \(icao)",
                     "Patch file: \(patchFile)",
                     "Engine: \(engineVersion.isEmpty ? "unknown" : engineVersion)",
                     "Way: \(wayId)"]
        for key in referenceTags {
            if let value = tags[key], !value.isEmpty { lines.append("\(key): \(value)") }
        }
        if !vertices.isEmpty {
            var lat = 0.0, lon = 0.0
            for v in vertices { lat += v.lat; lon += v.lon }
            let n = Double(vertices.count)
            lines.append("Centroid: \(latLon(lat / n, lon / n))")
        }
        lines.append("Vertices: \(vertices.count)")
        lines.append(closed ? String(format: "Area: %.1f m²", area) : "Area: open line")
        let alts = vertices.compactMap(\.alt)
        if let lo = alts.min(), let hi = alts.max() {
            var line = String(format: "Elevation: %.2f – %.2f m", lo, hi)
            if alts.count < vertices.count { line += " (\(vertices.count - alts.count) from the mesh)" }
            lines.append(line)
        } else {
            lines.append("Elevation: from the mesh")
        }
        lines.append("First vertices:")
        lines += vertices.prefix(firstVertices).map { latLon($0.lat, $0.lon) }
        return lines.joined(separator: "\n")
    }

    /// The block for one way of an open patch document.
    public static func text(for way: PatchWay, in doc: PatchDocument, engineVersion: String) -> String {
        let refs = way.isClosed ? Array(way.refs.dropLast()) : way.refs
        let vertices = refs.compactMap { doc.nodes[$0] }.map { Vertex(lat: $0.lat, lon: $0.lon, alt: $0.alt) }
        return text(tile: doc.tile, icao: doc.icao, patchFile: (doc.path as NSString).lastPathComponent,
                    engineVersion: engineVersion, wayId: way.id, tags: way.tags, closed: way.isClosed,
                    area: PatchShapeStats.planArea(of: way, in: doc), vertices: vertices)
    }

    private static func latLon(_ lat: Double, _ lon: Double) -> String {
        String(format: "%.9f, %.9f", lat, lon)
    }
}
