import Foundation

// The 3D preview's terrain: the `terrain_sample` grid (row 0 = south edge,
// row-major) as two triangles per cell, with the patch cut out
// (Ortho4XP/docs/specs/patch-editor-20261015.md §5, brief pe-3d: "drop
// grid triangles whose centroid lies inside a patch face").

/// The grid's geometry in degrees. Vertex (r, c) is at
/// (south + r·dlat, west + c·dlon) and has index r·cols + c.
public struct PatchTerrainGrid: Equatable, Sendable {
    public let rows: Int
    public let cols: Int
    public let south: Double
    public let west: Double
    public let dlat: Double
    public let dlon: Double

    public init(rows: Int, cols: Int, south: Double, west: Double, dlat: Double, dlon: Double) {
        self.rows = rows; self.cols = cols
        self.south = south; self.west = west
        self.dlat = dlat; self.dlon = dlon
    }

    public init(sample: O4TerrainSample) {
        self.init(rows: sample.rows, cols: sample.cols, south: sample.bbox.minLat,
                  west: sample.bbox.minLon, dlat: sample.dlat, dlon: sample.dlon)
    }

    public var triangleCount: Int { rows > 1 && cols > 1 ? 2 * (rows - 1) * (cols - 1) : 0 }

    /// Triangle `2·(r·(cols−1) + c) + k` of cell (r, c): k = 0 is
    /// (r,c) (r,c+1) (r+1,c+1), k = 1 is (r,c) (r+1,c+1) (r+1,c) — both
    /// counter-clockwise seen from above.
    public func vertices(ofTriangle t: Int) -> (UInt32, UInt32, UInt32) {
        let cell = t / 2, r = cell / (cols - 1), c = cell % (cols - 1)
        let v00 = UInt32(r * cols + c), v01 = v00 + 1
        let v10 = v00 + UInt32(cols), v11 = v10 + 1
        return t % 2 == 0 ? (v00, v01, v11) : (v00, v11, v10)
    }

    /// (lat, lon) of a triangle's centroid.
    public func centroid(ofTriangle t: Int) -> (lat: Double, lon: Double) {
        let cell = t / 2, r = Double(cell / (cols - 1)), c = Double(cell % (cols - 1))
        let (fr, fc) = Self.centroidOffsets[t % 2]
        return (south + (r + fr) * dlat, west + (c + fc) * dlon)
    }

    /// (row, column) offsets of the k = 0 and k = 1 centroids in a cell.
    static let centroidOffsets: [(Double, Double)] = [(1.0 / 3, 2.0 / 3), (2.0 / 3, 1.0 / 3)]
}

public enum PatchTerrainCut {
    /// `covered[t]` is true when triangle t's centroid lies inside a patch
    /// surface (even-odd over its outer ring and holes). A scanline per
    /// centroid row, over the shapes whose latitude span crosses it.
    public static func coveredTriangles(grid: PatchTerrainGrid, shapes: [PatchShape],
                                        document: PatchDocument) -> [Bool] {
        var covered = [Bool](repeating: false, count: grid.triangleCount)
        guard grid.triangleCount > 0 else { return covered }
        for shape in shapes {
            let rings = ([shape.outer] + shape.holes).map { ring in
                ring.compactMap { id in document.nodes[id].map { (lon: $0.lon, lat: $0.lat) } }
            }
            guard rings[0].count >= 3 else { continue }
            let lats = rings[0].map(\.lat)
            let minLat = lats.min()!, maxLat = lats.max()!
            for k in 0..<2 {
                let (fr, fc) = PatchTerrainGrid.centroidOffsets[k]
                let r0 = max(0, Int(ceil((minLat - grid.south) / grid.dlat - fr)))
                let r1 = min(grid.rows - 2, Int(floor((maxLat - grid.south) / grid.dlat - fr)))
                guard r0 <= r1 else { continue }
                for r in r0...r1 {
                    let y = grid.south + (Double(r) + fr) * grid.dlat
                    var xs: [Double] = []
                    for ring in rings {
                        var j = ring.count - 1
                        for i in ring.indices {
                            let a = ring[j], b = ring[i]
                            if (a.lat > y) != (b.lat > y) {
                                xs.append(a.lon + (y - a.lat) * (b.lon - a.lon) / (b.lat - a.lat))
                            }
                            j = i
                        }
                    }
                    xs.sort()
                    var s = 0
                    while s + 1 < xs.count {
                        let c0 = max(0, Int(ceil((xs[s] - grid.west) / grid.dlon - fc)))
                        let c1 = min(grid.cols - 2, Int(ceil((xs[s + 1] - grid.west) / grid.dlon - fc)) - 1)
                        if c0 <= c1 {
                            let base = 2 * (r * (grid.cols - 1))
                            for c in c0...c1 { covered[base + 2 * c + k] = true }
                        }
                        s += 2
                    }
                }
            }
        }
        return covered
    }

    /// The index buffer of the triangles NOT covered.
    public static func keptIndices(grid: PatchTerrainGrid, covered: [Bool]) -> [UInt32] {
        var out: [UInt32] = []
        out.reserveCapacity(3 * (covered.count - covered.lazy.filter { $0 }.count))
        for t in 0..<grid.triangleCount where !covered[t] {
            let (a, b, c) = grid.vertices(ofTriangle: t)
            out.append(a); out.append(b); out.append(c)
        }
        return out
    }
}
