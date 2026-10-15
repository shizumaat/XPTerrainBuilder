import Foundation
import simd

// The 3D preview's vertex data, free of SceneKit so it is tested here and
// handed to the window as plain arrays (patch-editor spec §5). Space: the
// document's metric frame (`PatchDocument.frame`) with x = east,
// y = metres above `base`, z = SOUTH (SceneKit is right-handed, y up, so
// north is −z). Vertical exaggeration is the window's node scale, never
// baked in here.

/// The terrain grid with its elevations, NaN filled, for sampling under
/// nodes that carry no elevation (a hand-made patch's nodes take the
/// mesh's elevation, §4 "elevation from the mesh").
public struct PatchTerrainSurface: Sendable {
    public let grid: PatchTerrainGrid
    /// Row-major, row 0 = south; no NaN.
    public let elevations: [Float]
    public let minElevation: Double

    public init(sample: O4TerrainSample) {
        grid = PatchTerrainGrid(sample: sample)
        let finite = sample.elevations.filter(\.isFinite)
        let fill = finite.isEmpty ? 0 : finite.reduce(0, +) / Float(finite.count)
        elevations = sample.elevations.map { $0.isFinite ? $0 : fill }
        minElevation = Double(finite.min() ?? 0)
    }

    /// Bilinear elevation at a point, clamped to the grid.
    public func elevation(lat: Double, lon: Double) -> Double {
        let g = grid
        let fr = min(max((lat - g.south) / g.dlat, 0), Double(g.rows - 1))
        let fc = min(max((lon - g.west) / g.dlon, 0), Double(g.cols - 1))
        let r0 = min(Int(fr), g.rows - 2), c0 = min(Int(fc), g.cols - 2)
        let tr = fr - Double(r0), tc = fc - Double(c0)
        func z(_ r: Int, _ c: Int) -> Double { Double(elevations[r * g.cols + c]) }
        return (1 - tr) * ((1 - tc) * z(r0, c0) + tc * z(r0, c0 + 1))
            + tr * ((1 - tc) * z(r0 + 1, c0) + tc * z(r0 + 1, c0 + 1))
    }
}

/// Where the preview's origin sits: the document frame, and the elevation
/// that maps to y = 0.
public struct PatchPreviewSpace: Sendable {
    public let frame: PatchLocalFrame
    public let base: Double
    public let terrain: PatchTerrainSurface?

    public init(frame: PatchLocalFrame, base: Double, terrain: PatchTerrainSurface?) {
        self.frame = frame; self.base = base; self.terrain = terrain
    }

    /// A node's position; a node without elevation stands on the terrain
    /// (or at `base` before the terrain has arrived).
    public func position(of node: PatchNode) -> SIMD3<Float> {
        let p = frame.metres(lat: node.lat, lon: node.lon)
        let z = node.alt ?? terrain?.elevation(lat: node.lat, lon: node.lon) ?? base
        return SIMD3(Float(p.x), Float(z - base), Float(-p.y))
    }

    public func position(lat: Double, lon: Double, elevation: Double) -> SIMD3<Float> {
        let p = frame.metres(lat: lat, lon: lon)
        return SIMD3(Float(p.x), Float(elevation - base), Float(-p.y))
    }
}

/// One surface's triangles, as indices into its own vertex list. A node
/// move or elevation change rebuilds `positions` only; the triangles stay.
public struct PatchShapeMesh: Sendable {
    public let shape: PatchShape
    /// The shape's nodes, one vertex each.
    public let vertexIDs: [Int64]
    /// Counter-clockwise from above, three per triangle.
    public let indices: [UInt32]

    /// Triangulates `shape` in the document's metric plane.
    public init(shape: PatchShape, document: PatchDocument) {
        self.shape = shape
        let frame = document.frame
        let tris = PatchTriangulator.triangulate(outer: shape.outer, holes: shape.holes) { id in
            document.nodes[id].map { frame.metres(lat: $0.lat, lon: $0.lon) }
        }
        var slot: [Int64: UInt32] = [:]
        var ids: [Int64] = []
        var indices: [UInt32] = []
        indices.reserveCapacity(tris.count * 3)
        for t in tris {
            for id in [t.a, t.b, t.c] {
                if let s = slot[id] { indices.append(s); continue }
                let s = UInt32(ids.count)
                slot[id] = s
                ids.append(id)
                indices.append(s)
            }
        }
        vertexIDs = ids
        self.indices = indices
    }

    public func positions(document: PatchDocument, space: PatchPreviewSpace) -> [SIMD3<Float>] {
        vertexIDs.map { id in document.nodes[id].map(space.position(of:)) ?? .zero }
    }
}

public enum PatchPreviewNormals {
    /// Area-weighted vertex normals of an indexed triangle list (y up).
    public static func of(positions: [SIMD3<Float>], indices: [UInt32]) -> [SIMD3<Float>] {
        var n = [SIMD3<Float>](repeating: .zero, count: positions.count)
        for t in stride(from: 0, to: indices.count - 2, by: 3) {
            let a = Int(indices[t]), b = Int(indices[t + 1]), c = Int(indices[t + 2])
            let f = simd_cross(positions[b] - positions[a], positions[c] - positions[a])
            n[a] += f; n[b] += f; n[c] += f
        }
        return n.map { v in
            let l = simd_length(v)
            return l > 0 ? v / l : SIMD3(0, 1, 0)
        }
    }
}

/// The terrain mesh: one vertex per grid point, the uncovered triangles.
public struct PatchTerrainMesh: Sendable {
    public let positions: [SIMD3<Float>]
    public let normals: [SIMD3<Float>]

    public init(surface: PatchTerrainSurface, space: PatchPreviewSpace) {
        let g = surface.grid
        var p: [SIMD3<Float>] = []
        p.reserveCapacity(g.rows * g.cols)
        for r in 0..<g.rows {
            let lat = g.south + Double(r) * g.dlat
            for c in 0..<g.cols {
                p.append(space.position(lat: lat, lon: g.west + Double(c) * g.dlon,
                                        elevation: Double(surface.elevations[r * g.cols + c])))
            }
        }
        positions = p
        // central differences on the grid (smooth shading; no index walk)
        var n: [SIMD3<Float>] = []
        n.reserveCapacity(p.count)
        for r in 0..<g.rows {
            for c in 0..<g.cols {
                let e = p[r * g.cols + min(c + 1, g.cols - 1)], w = p[r * g.cols + max(c - 1, 0)]
                let nn = p[min(r + 1, g.rows - 1) * g.cols + c], s = p[max(r - 1, 0) * g.cols + c]
                // east × north (−z) points up
                let v = simd_cross(e - w, nn - s)
                let l = simd_length(v)
                n.append(l > 0 ? v / l : SIMD3(0, 1, 0))
            }
        }
        normals = n
    }
}

/// Which shapes draw a node: a node edit rebuilds exactly these.
public struct PatchPreviewIndex: Sendable {
    public private(set) var shapesByNode: [Int64: Set<Int64>] = [:]

    public init(meshes: [Int64: PatchShapeMesh]) {
        for (way, mesh) in meshes {
            for id in mesh.shape.nodeIDs { shapesByNode[id, default: []].insert(way) }
        }
    }

    /// The shapes (way ids) that draw any of `nodes`.
    public func shapes(using nodes: Set<Int64>) -> Set<Int64> {
        nodes.reduce(into: Set<Int64>()) { $0.formUnion(shapesByNode[$1] ?? []) }
    }
}
