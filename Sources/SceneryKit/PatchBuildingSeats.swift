import Foundation
import simd

// Where the pack's buildings stand in the 3D preview (patch-editor spec
// §5): each placement at `preview_surface(anchor) + agl + y`, turned by its
// heading — X-Plane's own drape at the anchor, so ground lowered under a
// building leaves it floating as it would in the sim (re-seating is off for
// an edited patch). The preview surface is the patch surface where the
// anchor lies on a patch shape, else the terrain grid.

/// The preview surface under a point: which patch shape (if any) and its
/// elevation there.
public struct PatchSurfaceLocator: Sendable {
    private struct Entry: Sendable {
        let way: Int64
        let minX, minY, maxX, maxY: Double
        /// Triangles as metric corners + elevations (nil = from terrain).
        let tris: [(SIMD2<Double>, SIMD2<Double>, SIMD2<Double>, Double?, Double?, Double?)]
    }

    private let entries: [Entry]
    private let frame: PatchLocalFrame

    public init(meshes: [Int64: PatchShapeMesh], document: PatchDocument) {
        frame = document.frame
        var out: [Entry] = []
        for (way, mesh) in meshes.sorted(by: { $0.key < $1.key }) {
            let pts: [(SIMD2<Double>, Double?)] = mesh.vertexIDs.map { id in
                guard let n = document.nodes[id] else { return (.zero, nil) }
                let p = document.frame.metres(lat: n.lat, lon: n.lon)
                return (SIMD2(p.x, p.y), n.alt)
            }
            guard !pts.isEmpty, !mesh.indices.isEmpty else { continue }
            var tris: [(SIMD2<Double>, SIMD2<Double>, SIMD2<Double>, Double?, Double?, Double?)] = []
            for t in stride(from: 0, to: mesh.indices.count - 2, by: 3) {
                let a = pts[Int(mesh.indices[t])], b = pts[Int(mesh.indices[t + 1])],
                    c = pts[Int(mesh.indices[t + 2])]
                tris.append((a.0, b.0, c.0, a.1, b.1, c.1))
            }
            let xs = pts.map(\.0.x), ys = pts.map(\.0.y)
            out.append(Entry(way: way, minX: xs.min()!, minY: ys.min()!, maxX: xs.max()!,
                             maxY: ys.max()!, tris: tris))
        }
        entries = out
    }

    /// The shape under (lat, lon) and the surface elevation there; off the
    /// patch, the terrain's (or `space.base` before the terrain arrives).
    public func surface(lat: Double, lon: Double, space: PatchPreviewSpace) -> (way: Int64?, z: Double) {
        let m = frame.metres(lat: lat, lon: lon)
        let p = SIMD2(m.x, m.y)
        let ground = space.terrain?.elevation(lat: lat, lon: lon) ?? space.base
        for e in entries where p.x >= e.minX && p.x <= e.maxX && p.y >= e.minY && p.y <= e.maxY {
            for (a, b, c, za, zb, zc) in e.tris {
                guard let w = Self.barycentric(p, a, b, c) else { continue }
                let z = w.x * (za ?? ground) + w.y * (zb ?? ground) + w.z * (zc ?? ground)
                return (e.way, z)
            }
        }
        return (nil, ground)
    }

    /// Whether (lat, lon) lies in the bounding box of one of `ways`.
    func nearAny(_ ways: Set<Int64>, lat: Double, lon: Double) -> Bool {
        let m = frame.metres(lat: lat, lon: lon)
        return entries.contains { ways.contains($0.way) && m.x >= $0.minX && m.x <= $0.maxX
            && m.y >= $0.minY && m.y <= $0.maxY }
    }

    static func barycentric(_ p: SIMD2<Double>, _ a: SIMD2<Double>, _ b: SIMD2<Double>,
                            _ c: SIMD2<Double>) -> SIMD3<Double>? {
        let v0 = b - a, v1 = c - a, v2 = p - a
        let d = v0.x * v1.y - v1.x * v0.y
        guard abs(d) > 1e-12 else { return nil }
        let u = (v2.x * v1.y - v1.x * v2.y) / d
        let v = (v0.x * v2.y - v2.x * v0.y) / d
        let eps = -1e-9
        guard u >= eps, v >= eps, u + v <= 1 - eps else { return nil }
        return SIMD3(1 - u - v, u, v)
    }
}

/// One placement's pose in preview space (unexaggerated metres; the
/// window multiplies `y` by the exaggeration): the model's authored frame
/// (x east at heading 0, y up, z south) turned by −heading about y,
/// because X-Plane's heading is clockwise from north seen from above.
public struct PatchBuildingPose: Equatable, Sendable {
    public let position: SIMD3<Float>
    /// Radians about +y (SceneKit `eulerAngles.y`).
    public let yaw: Float

    public init(anchorLat: Double, anchorLon: Double, headingDeg: Double, aglM: Double,
                surfaceZ: Double, space: PatchPreviewSpace) {
        position = space.position(lat: anchorLat, lon: anchorLon, elevation: surfaceZ + aglM)
        yaw = Float(-headingDeg * .pi / 180)
    }

    /// An authored model point in preview space, with vertical
    /// exaggeration `e` applied to the seat only (buildings keep their
    /// true height).
    public func place(_ authored: SIMD3<Float>, exaggeration e: Float = 1) -> SIMD3<Float> {
        let c = cos(yaw), s = sin(yaw)
        let x = c * authored.x + s * authored.z
        let z = -s * authored.x + c * authored.z
        return SIMD3(position.x + x, position.y * e + authored.y, position.z + z)
    }
}

/// The seats of every placement, and the re-seat after an edit: only
/// placements whose anchor lay on a changed shape, or now falls within one.
public struct PatchBuildingSeats: Sendable {
    public private(set) var poses: [PatchBuildingPose]
    public private(set) var shapeOf: [Int64?]
    private let placements: [O4PackObjects.Placement]

    public init(placements: [O4PackObjects.Placement], locator: PatchSurfaceLocator,
                space: PatchPreviewSpace) {
        self.placements = placements
        poses = []
        shapeOf = []
        for p in placements {
            let s = locator.surface(lat: p.lat, lon: p.lon, space: space)
            shapeOf.append(s.way)
            poses.append(PatchBuildingPose(anchorLat: p.lat, anchorLon: p.lon, headingDeg: p.headingDeg,
                                           aglM: p.aglM, surfaceZ: s.z, space: space))
        }
    }

    /// Re-seat after `changedShapes` changed; returns the indices moved.
    public mutating func reseat(changedShapes: Set<Int64>, locator: PatchSurfaceLocator,
                                space: PatchPreviewSpace) -> [Int] {
        guard !changedShapes.isEmpty else { return [] }
        var moved: [Int] = []
        for (i, p) in placements.enumerated() {
            let was = shapeOf[i].map(changedShapes.contains) ?? false
            guard was || locator.nearAny(changedShapes, lat: p.lat, lon: p.lon) else { continue }
            let s = locator.surface(lat: p.lat, lon: p.lon, space: space)
            shapeOf[i] = s.way
            let pose = PatchBuildingPose(anchorLat: p.lat, anchorLon: p.lon, headingDeg: p.headingDeg,
                                         aglM: p.aglM, surfaceZ: s.z, space: space)
            if pose != poses[i] { poses[i] = pose; moved.append(i) }
        }
        return moved
    }
}
