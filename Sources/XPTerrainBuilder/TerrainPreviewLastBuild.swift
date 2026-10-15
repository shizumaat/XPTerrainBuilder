import Foundation
import SceneryKit
import simd

/// "Last build" in the 3D preview (patch-editor spec §5, round 6c): the
/// tile mesh X-Plane loads, cropped to the preview extent (`mesh_crop`),
/// drawn instead of the preview surface at the same exaggeration. Fetched
/// when first shown and again only after the tile is rebuilt (its mesh
/// date) — never live. Owned by `TerrainPreviewModel`.
@MainActor
final class TerrainPreviewLastBuild {
    private(set) var state = PatchLastBuildState()
    /// The surface buildings stand on in Last build.
    private(set) var locator: PatchSurfaceLocator?
    private(set) var triangleCount = 0
    var onChange: (() -> Void)?

    private let scene: TerrainPreviewScene
    private var generation = 0

    init(scene: TerrainPreviewScene) { self.scene = scene }

    func clear() {
        generation += 1
        state = PatchLastBuildState()
        locator = nil
        triangleCount = 0
        scene.setLastBuild(nil)
        scene.showLastBuild(false)
        onChange?()
    }

    /// The user picked a mode.
    func select(_ mode: PatchLastBuildState.Mode, request: Request?) {
        let fetch = state.select(mode, build: request?.meshDate)
        scene.showLastBuild(state.mode == .lastBuild && state.mesh == .available)
        onChange?()
        if fetch, let request { load(request) }
    }

    /// The scan reported the tile again: a new mesh date refetches when
    /// Last build is showing, else on its next showing.
    func tileBuilt(_ request: Request?) {
        if state.tileBuilt(request?.meshDate), let request { load(request) }
        onChange?()
    }

    struct Request {
        let client: OrthoEngineClient
        let tile: String
        let box: O4LatLonBox
        let buildDir: String?
        let meshDate: Double?
        let space: PatchPreviewSpace
        let drapeBox: O4LatLonBox
    }

    private func load(_ r: Request) {
        generation += 1
        let gen = generation
        state.fetching(build: r.meshDate)
        onChange?()
        Task { [weak self] in
            do {
                let crop = try await r.client.meshCrop(tile: r.tile, bbox: r.box, buildDir: r.buildDir)
                let built = await Task.detached(priority: .userInitiated) {
                    Self.geometry(crop, space: r.space, drapeBox: r.drapeBox)
                }.value
                guard let self, self.generation == gen else { return }
                self.locator = built.locator
                self.triangleCount = built.indices.count / 3
                self.scene.setLastBuild((built.positions, built.normals, built.texcoords, built.indices))
                self.state.fetched(true)
                self.scene.showLastBuild(self.state.mode == .lastBuild)
            } catch {
                guard let self, self.generation == gen else { return }
                self.state.fetched(false, reason: "\(error)")
                self.scene.showLastBuild(false)
            }
            self?.onChange?()
        }
    }

    private struct Built: Sendable {
        let positions: [SIMD3<Float>]
        let normals: [SIMD3<Float>]
        let texcoords: [SIMD2<Float>]
        let indices: [UInt32]
        let locator: PatchSurfaceLocator
    }

    private nonisolated static func geometry(_ crop: O4MeshCrop, space: PatchPreviewSpace,
                                             drapeBox: O4LatLonBox) -> Built {
        let v = crop.vertices
        var p: [SIMD3<Float>] = [], uv: [SIMD2<Float>] = []
        p.reserveCapacity(v.count / 3); uv.reserveCapacity(v.count / 3)
        for k in stride(from: 0, to: v.count - 2, by: 3) {
            p.append(space.position(lat: v[k + 1], lon: v[k], elevation: v[k + 2]))
            uv.append(PatchDrapePlan.uv(lat: v[k + 1], lon: v[k], box: drapeBox))
        }
        // the mesh's winding is Triangle's; draw both sides, shade up
        let n = PatchPreviewNormals.of(positions: p, indices: crop.triangles).map { $0.y < 0 ? -$0 : $0 }
        return Built(positions: p, normals: n, texcoords: uv, indices: crop.triangles,
                     locator: PatchSurfaceLocator(meshCrop: crop, frame: space.frame))
    }
}
