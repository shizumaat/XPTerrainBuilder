import Foundation
import Combine
import SceneryKit
import simd

/// The 3D preview's state (patch-editor spec §5, A8, A9): follows the
/// patch model LIVE and never writes to it. On a new document it asks the
/// engine for the terrain (`terrain_sample`, patch bbox + 500 m at 5 m) and
/// triangulates every surface; on an edit (`PatchEditModel.changes`) it
/// rebuilds the buffers of the shapes that use a changed node, and
/// re-triangulates only the shapes whose rings a topology change altered.
/// The terrain cut-out follows moves after a short pause.
@MainActor
final class TerrainPreviewModel: ObservableObject {
    enum Status: Equatable {
        case noPatch
        case loading(icao: String)
        /// The patch is shown; `terrainError` says why the ground is missing.
        case ready(terrainError: String?)
    }

    @Published private(set) var status: Status = .noPatch
    @Published private(set) var icao: String?
    @Published private(set) var chip = ""
    @Published var exaggeration: Double = 3 {
        didSet { scene.setExaggeration(Float(exaggeration)) }
    }
    @Published var wireframe = false { didSet { scene.setWireframe(wireframe) } }
    /// Bumped by "Reset view"; the scene view frames the extent again.
    @Published private(set) var resetCount = 0

    let scene = TerrainPreviewScene()

    /// A9: the terrain reaches this far past the patch's bbox …
    nonisolated static let marginM = 500.0
    /// … at this spacing.
    nonisolated static let spacingM = 5.0
    /// The engine's cap on one `terrain_sample` (spec §2).
    nonisolated static let maxSamples = 4_000_000.0

    private weak var patch: PatchEditModel?
    private weak var build: BuildModel?
    private var subscriptions: Set<AnyCancellable> = []
    private var documentKey: String?
    private var generation = 0
    private var topologyGeneration = 0
    private var space: PatchPreviewSpace?
    private var meshes: [Int64: PatchShapeMesh] = [:]
    private var index = PatchPreviewIndex(meshes: [:])
    private var surface: PatchTerrainSurface?
    private var cutTask: Task<Void, Never>?

    init(patch: PatchEditModel, build: BuildModel) {
        self.patch = patch
        self.build = build
        patch.changes.sink { [weak self] change in self?.apply(change) }
            .store(in: &subscriptions)
        patch.$selection.sink { [weak self] _ in
            DispatchQueue.main.async { self?.updateMarkers() }
        }.store(in: &subscriptions)
        patch.$document.sink { [weak self] doc in
            DispatchQueue.main.async { self?.documentMayHaveChanged(doc) }
        }.store(in: &subscriptions)
    }

    func resetView() { resetCount += 1 }

    // MARK: - Changes

    private static func key(_ doc: PatchDocument) -> String { "\(doc.tile)|\(doc.icao)|\(doc.path)" }

    /// A window opened on an already-loaded patch (no `.all` will come),
    /// or the layer was hidden.
    private func documentMayHaveChanged(_ doc: PatchDocument?) {
        guard let doc else {
            if documentKey != nil { clear() }
            return
        }
        if Self.key(doc) != documentKey { reload(doc) }
    }

    private func apply(_ change: PatchChange) {
        guard let doc = patch?.document else { clear(); return }
        if change.everything || Self.key(doc) != documentKey {
            reload(doc)
            return
        }
        guard space != nil else { return }      // still loading: the load reads the latest doc
        if change.topology || !change.ways.isEmpty {
            retriangulate(doc, changedNodes: change.nodes)
        } else if !change.nodes.isEmpty {
            rebuildBuffers(index.shapes(using: change.nodes), doc)
            scheduleCut()
        }
        updateMarkers()
    }

    private func clear() {
        generation += 1
        documentKey = nil
        space = nil; surface = nil; meshes = [:]; index = PatchPreviewIndex(meshes: [:])
        cutTask?.cancel()
        scene.removeAll()
        icao = nil; chip = ""
        status = .noPatch
    }

    // MARK: - Full load

    private func reload(_ doc: PatchDocument) {
        clear()
        generation += 1
        let gen = generation
        documentKey = Self.key(doc)
        icao = doc.icao
        status = .loading(icao: doc.icao)
        let client = build?.patchEditorClient()
        Task { [weak self] in
            let shapes = await Task.detached(priority: .userInitiated) {
                Self.meshes(PatchShapeAssembly.shapes(of: doc), doc)
            }.value
            var sample: O4TerrainSample?
            var terrainError: String?
            if let client, let box = doc.bbox {
                let (request, spacing) = Self.terrainRequest(around: box)
                do {
                    sample = try await client.terrainSample(tile: doc.tile, icao: doc.icao,
                                                            bbox: request, spacingM: spacing)
                } catch {
                    terrainError = "\(error)"
                }
            } else {
                terrainError = "The engine is not running, so the terrain cannot be read."
            }
            guard let self, self.generation == gen else { return }
            // The document as it is NOW (edits may have landed meanwhile).
            let current = self.patch?.document ?? doc
            let built = await Task.detached(priority: .userInitiated) {
                Self.buildTerrain(sample: sample, document: current, shapes: Array(shapes.values))
            }.value
            guard self.generation == gen else { return }
            self.install(built, meshes: shapes, document: current, terrainError: terrainError)
        }
    }

    /// A9's box, and the spacing: 5 m unless that is over the engine's cap,
    /// then the finest spacing under it.
    nonisolated static func terrainRequest(around box: O4LatLonBox) -> (O4LatLonBox, Double) {
        let midLat = (box.minLat + box.maxLat) / 2
        let mLon = PatchLocalFrame.metresPerDegreeLat * max(cos(midLat * .pi / 180), 1e-6)
        let dLat = marginM / PatchLocalFrame.metresPerDegreeLat, dLon = marginM / mLon
        let request = O4LatLonBox(minLat: box.minLat - dLat, minLon: box.minLon - dLon,
                                  maxLat: box.maxLat + dLat, maxLon: box.maxLon + dLon)
        let w = (request.maxLon - request.minLon) * mLon
        let h = (request.maxLat - request.minLat) * PatchLocalFrame.metresPerDegreeLat
        var spacing = spacingM
        while (w / spacing + 2) * (h / spacing + 2) > maxSamples { spacing += 0.5 }
        return (request, spacing)
    }

    private nonisolated static func meshes(_ shapes: [PatchShape], _ doc: PatchDocument) -> [Int64: PatchShapeMesh] {
        var out: [Int64: PatchShapeMesh] = [:]
        for s in shapes { out[s.wayID] = PatchShapeMesh(shape: s, document: doc) }
        return out
    }

    private struct BuiltTerrain: Sendable {
        let space: PatchPreviewSpace
        let mesh: PatchTerrainMesh?
        let indices: [UInt32]
        let extent: (SIMD3<Float>, Float)
        let chip: String
    }

    private nonisolated static func buildTerrain(sample: O4TerrainSample?, document doc: PatchDocument,
                                                 shapes: [PatchShapeMesh]) -> BuiltTerrain {
        let surface = sample.map(PatchTerrainSurface.init)
        let alts = doc.nodes.values.compactMap(\.alt)
        let base = surface?.minElevation ?? alts.min() ?? 0
        let space = PatchPreviewSpace(frame: doc.frame, base: base, terrain: surface)
        let box = doc.bbox ?? O4LatLonBox(minLat: 0, minLon: 0, maxLat: 0, maxLon: 0)
        let lo = space.position(lat: box.minLat, lon: box.minLon, elevation: base)
        let hi = space.position(lat: box.maxLat, lon: box.maxLon, elevation: base)
        let extent = ((lo + hi) / 2, max(abs(hi.x - lo.x), abs(hi.z - lo.z)) / 2 + Float(marginM / 2))
        guard let surface, let sample else {
            return BuiltTerrain(space: space, mesh: nil, indices: [], extent: extent, chip: "Preview · no terrain")
        }
        let mesh = PatchTerrainMesh(surface: surface, space: space)
        let covered = PatchTerrainCut.coveredTriangles(grid: surface.grid, shapes: shapes.map(\.shape),
                                                       document: doc)
        let indices = PatchTerrainCut.keptIndices(grid: surface.grid, covered: covered)
        return BuiltTerrain(space: space, mesh: mesh, indices: indices, extent: extent,
                            chip: chipText(sample))
    }

    /// "Preview · 3.0 km × 2.2 km · DEM base + airport inset · 5 m grid".
    nonisolated static func chipText(_ s: O4TerrainSample) -> String {
        let midLat = (s.bbox.minLat + s.bbox.maxLat) / 2
        let w = (s.bbox.maxLon - s.bbox.minLon) * PatchLocalFrame.metresPerDegreeLat * cos(midLat * .pi / 180)
        let h = (s.bbox.maxLat - s.bbox.minLat) * PatchLocalFrame.metresPerDegreeLat
        let inset = (s.sources["inset"] ?? nil) != nil
        let dem = inset ? "DEM base + airport inset" : "DEM base only"
        let spacing = s.spacingM.truncatingRemainder(dividingBy: 1) == 0
            ? String(Int(s.spacingM)) : String(format: "%.1f", s.spacingM)
        return String(format: "Preview · %.1f km × %.1f km · ", w / 1000, h / 1000) + "\(dem) · \(spacing) m grid"
    }

    private func install(_ built: BuiltTerrain, meshes: [Int64: PatchShapeMesh], document doc: PatchDocument,
                         terrainError: String?) {
        space = built.space
        surface = built.space.terrain
        if let mesh = built.mesh { scene.setTerrain(mesh, indices: built.indices, extent: built.extent) }
        self.meshes = meshes
        index = PatchPreviewIndex(meshes: meshes)
        rebuildBuffers(Set(meshes.keys), doc, retriangulated: true)
        scene.setExaggeration(Float(exaggeration))
        scene.setWireframe(wireframe)
        chip = built.chip
        status = .ready(terrainError: terrainError)
        updateMarkers()
        resetCount += 1
    }

    // MARK: - Incremental

    /// Rebuild these shapes' vertex buffers (and, after a re-triangulation,
    /// their index buffers) from the current document.
    private func rebuildBuffers(_ ways: Set<Int64>, _ doc: PatchDocument, retriangulated: Bool = false) {
        guard let space else { return }
        for way in ways {
            guard let mesh = meshes[way] else { scene.removeShape(way); continue }
            let p = mesh.positions(document: doc, space: space)
            scene.setShape(way, positions: p, normals: PatchPreviewNormals.of(positions: p, indices: mesh.indices),
                           indices: retriangulated ? mesh.indices : nil)
        }
    }

    /// A topology change: re-assemble the surfaces (holes follow nesting),
    /// then re-triangulate only the shapes whose rings differ.
    private func retriangulate(_ doc: PatchDocument, changedNodes: Set<Int64>) {
        topologyGeneration += 1
        let gen = generation, topo = topologyGeneration
        let previous = meshes.mapValues(\.shape)
        Task { [weak self] in
            let changed = await Task.detached(priority: .userInitiated) { () -> [Int64: PatchShapeMesh?] in
                let shapes = PatchShapeAssembly.shapes(of: doc)
                var out: [Int64: PatchShapeMesh?] = [:]
                let present = Set(shapes.map(\.wayID))
                for s in shapes where previous[s.wayID] != s { out[s.wayID] = PatchShapeMesh(shape: s, document: doc) }
                for way in previous.keys where !present.contains(way) { out[way] = .some(nil) }
                return out
            }.value
            guard let self, self.generation == gen, self.topologyGeneration == topo,
                  let current = self.patch?.document else { return }
            for (way, mesh) in changed { self.meshes[way] = mesh }
            self.index = PatchPreviewIndex(meshes: self.meshes)
            self.rebuildBuffers(Set(changed.keys), current, retriangulated: true)
            self.rebuildBuffers(self.index.shapes(using: changedNodes).subtracting(changed.keys), current)
            self.scheduleCut()
            self.updateMarkers()
        }
    }

    /// Recompute the terrain cut-out once edits pause.
    private func scheduleCut() {
        guard let surface else { return }
        cutTask?.cancel()
        let gen = generation
        cutTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 150_000_000)
            guard let self, !Task.isCancelled, self.generation == gen,
                  let doc = self.patch?.document else { return }
            let shapes = self.meshes.values.map(\.shape)
            let indices = await Task.detached(priority: .userInitiated) {
                PatchTerrainCut.keptIndices(grid: surface.grid, covered: PatchTerrainCut.coveredTriangles(
                    grid: surface.grid, shapes: shapes, document: doc))
            }.value
            guard !Task.isCancelled, self.generation == gen else { return }
            self.scene.setTerrainIndices(indices)
        }
    }

    private func updateMarkers() {
        guard let space, let patch, let doc = patch.document else { scene.setMarkers([]); return }
        scene.setMarkers(patch.selection.compactMap { doc.nodes[$0].map(space.position(of:)) })
    }
}
