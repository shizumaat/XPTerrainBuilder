import Foundation
import SceneKit
import SceneryKit
import simd

/// The pack's buildings in the 3D preview (patch-editor spec §5, round
/// 6b): asked for once the terrain and patch are shown (`pack_objects`,
/// asynchronous on the engine), drawn as grey massing — one shared
/// geometry per model, one node per placement — each seated at
/// `preview_surface(anchor) + agl + y` with its heading. An edit re-seats
/// only the placements whose anchor lay on (or now falls within) a changed
/// shape. Owned by `TerrainPreviewModel`; never writes to the patch model.
@MainActor
final class TerrainPreviewBuildings {
    enum Status: Equatable {
        case none
        case loading
        case ready(objects: Int, missing: [String])
        case failed(String)
    }

    private(set) var status: Status = .none
    var onStatus: ((Status) -> Void)?

    private let scene: TerrainPreviewScene
    private var generation = 0
    private var seats: PatchBuildingSeats?

    init(scene: TerrainPreviewScene) { self.scene = scene }

    func clear() {
        generation += 1
        seats = nil
        set(.none)
    }

    /// Ask the engine; draw when the event lands (the window shows
    /// "Loading buildings…" until then).
    func load(client: OrthoEngineClient?, document doc: PatchDocument, box: O4LatLonBox,
              space: PatchPreviewSpace, meshes: [Int64: PatchShapeMesh]) {
        generation += 1
        let gen = generation
        guard let client else { set(.none); return }
        set(.loading)
        Task { [weak self] in
            do {
                // Shared with the map's footprints (one request, one answer).
                let objects = try await PackBuildingsStore.shared.objects(
                    client: client, tile: doc.tile, icao: doc.icao, box: box)
                let built = await Task.detached(priority: .userInitiated) {
                    Self.build(objects, document: doc, space: space, meshes: meshes)
                }.value
                guard let self, self.generation == gen else { return }
                self.seats = built.seats
                self.scene.setBuildings(models: built.models, placements: built.keys,
                                        poses: built.seats.poses, facades: built.facades)
                self.set(.ready(objects: built.keys.count + built.facades.count, missing: objects.missing))
            } catch {
                guard let self, self.generation == gen else { return }
                self.set(.failed("\(error)"))
            }
        }
    }

    /// After an edit: re-seat the placements on `changedShapes`.
    func reseat(changedShapes: Set<Int64>, meshes: [Int64: PatchShapeMesh],
                document doc: PatchDocument, space: PatchPreviewSpace) {
        guard var seats, !changedShapes.isEmpty else { return }
        let locator = PatchSurfaceLocator(meshes: meshes, document: doc)
        let moved = seats.reseat(changedShapes: changedShapes, locator: locator, space: space)
        self.seats = seats
        scene.reseatBuildings(moved, poses: seats.poses)
    }

    private func set(_ s: Status) {
        status = s
        onStatus?(s)
    }

    private struct Built: @unchecked Sendable {
        let models: [String: SCNGeometry]
        let keys: [String]
        let seats: PatchBuildingSeats
        let facades: [(SCNGeometry, Float)]
    }

    private nonisolated static func build(_ objects: O4PackObjects, document doc: PatchDocument,
                                          space: PatchPreviewSpace,
                                          meshes: [Int64: PatchShapeMesh]) -> Built {
        var models: [String: SCNGeometry] = [:]
        for m in objects.models {
            models[m.key] = TerrainPreviewScene.modelGeometry(vertices: m.vertices, triangles: m.triangles)
        }
        let drawn = objects.placements.filter { models[$0.model] != nil }
        let locator = PatchSurfaceLocator(meshes: meshes, document: doc)
        let seats = PatchBuildingSeats(placements: drawn, locator: locator, space: space)
        var facades: [(SCNGeometry, Float)] = []
        for f in objects.facades where f.ring.count >= 3 {
            let lat = f.ring.map(\.lat).reduce(0, +) / Double(f.ring.count)
            let lon = f.ring.map(\.lon).reduce(0, +) / Double(f.ring.count)
            let ground = locator.surface(lat: lat, lon: lon, space: space).z
            let ring = f.ring.map { p -> SIMD2<Float> in
                let q = space.position(lat: p.lat, lon: p.lon, elevation: space.base)
                return SIMD2(q.x, q.z)
            }
            facades.append((TerrainPreviewScene.facadeGeometry(ring: ring, height: Float(f.heightM)),
                            Float(ground - space.base)))
        }
        return Built(models: models, keys: drawn.map(\.model), seats: seats, facades: facades)
    }
}
