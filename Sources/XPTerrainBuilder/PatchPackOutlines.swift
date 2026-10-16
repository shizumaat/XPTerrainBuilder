import Foundation
import Combine
import SwiftUI
import SceneryKit

/// The pack reference outlines under the patch layer (spec §0 A4, §2, §4;
/// mockup "pack apt.dat"): the pack's own apt.dat pavement and boundary
/// (`pack_outlines`) and its building footprints (`PackFootprints`, from
/// the `pack_objects` answer the 3D window shares through
/// `PackBuildingsStore`). Follows the loaded patch; asks only while the
/// "Pack outlines" toggle is on (persisted per user, default on).
@MainActor
final class PatchPackOutlines: ObservableObject {
    static let defaultsKey = "patchEditor.showPackOutlines"

    @Published var enabled: Bool {
        didSet {
            UserDefaults.standard.set(enabled, forKey: Self.defaultsKey)
            if enabled { reloadIfNeeded() }
        }
    }
    /// Projected rings; nil until the first answer lands.
    @Published private(set) var geometry: PackOutlineGeometry?
    /// The engine's sentences about what could not be read.
    @Published private(set) var missing: [String] = []

    private weak var patch: PatchEditModel?
    private var loadedKey: String?
    private var generation = 0
    private var pavement: [[O4LatLon]] = []
    private var footprints: [[O4LatLon]] = []
    private var subscriptions: Set<AnyCancellable> = []

    init(patch: PatchEditModel) {
        self.patch = patch
        enabled = UserDefaults.standard.object(forKey: Self.defaultsKey) as? Bool ?? true
        // Every edit publishes the document; only a new one (another
        // airport or file, or a load / revert: `documentGeneration`) reloads.
        patch.$document.sink { [weak self] _ in
            DispatchQueue.main.async { self?.reloadIfNeeded() }
        }.store(in: &subscriptions)
    }

    private func key(_ doc: PatchDocument) -> String {
        "\(patch?.documentGeneration ?? 0)|\(doc.openKey)"
    }

    private func reloadIfNeeded() {
        guard let doc = patch?.document else { clear(); return }
        if key(doc) != loadedKey { reload() }
    }

    private func clear() {
        generation += 1
        loadedKey = nil
        pavement = []; footprints = []; missing = []
        geometry = nil
    }

    /// A new document (or the same file loaded again after a rebuild).
    private func reload() {
        clear()
        guard enabled, let doc = patch?.document,
              let client = patch?.build?.patchEditorClient() else { return }
        loadedKey = key(doc)
        let gen = generation
        Task { [weak self] in
            do {
                let reply = try await client.packOutlines(tile: doc.tile, icao: doc.icao)
                guard let self, self.generation == gen else { return }
                self.pavement = reply.pavement.flatMap(\.rings)
                self.missing += reply.missing
                self.project()
            } catch {
                guard let self, self.generation == gen else { return }
                self.missing.append("\(error)")
            }
        }
        guard let box = doc.bbox else { return }
        // The 3D window's box (A9), so one request serves both.
        let request = TerrainPreviewModel.terrainRequest(around: box).0
        Task { [weak self] in
            do {
                let objects = try await PackBuildingsStore.shared.objects(
                    client: client, tile: doc.tile, icao: doc.icao, box: request)
                let rings = await Task.detached(priority: .utility) { PackFootprints.outlines(objects) }.value
                guard let self, self.generation == gen else { return }
                self.footprints = rings
                self.project()
            } catch {
                guard let self, self.generation == gen else { return }
                self.missing.append("Pack buildings: \(error)")
            }
        }
    }

    private func project() {
        geometry = PackOutlineGeometry(rings: pavement + footprints)
    }
}

/// Outline rings in the map's world units (longitude, mercator Y), with
/// their extents for culling.
struct PackOutlineGeometry: Sendable {
    struct Ring: Sendable {
        let points: [CGPoint]
        let minX, maxX, minY, maxY: Double
    }

    let rings: [Ring]

    init(rings: [[O4LatLon]]) {
        self.rings = rings.compactMap { ring in
            guard ring.count >= 2 else { return nil }
            let points = ring.map { CGPoint(x: $0.lon, y: MapCamera.mercatorY(lat: $0.lat)) }
            let xs = points.map(\.x), ys = points.map(\.y)
            return Ring(points: points, minX: xs.min()!, maxX: xs.max()!, minY: ys.min()!, maxY: ys.max()!)
        }
    }
}

/// The dashed grey layer, drawn under the patch. It observes only the
/// outlines and the camera — never the patch model or a drag — so editing
/// does not redraw it.
struct PatchPackOutlineLayer: View {
    @ObservedObject var outlines: PatchPackOutlines
    @ObservedObject var camera: ViewState<MapCamera>

    static let stroke = PatchStyle.hex(0x9AA4B5, 0.7)
    static let dash: [CGFloat] = [5, 4]

    var body: some View {
        if outlines.enabled, let geometry = outlines.geometry {
            Canvas(rendersAsynchronously: false) { context, size in
                Self.draw(geometry, camera: camera.value, in: context, size: size)
            }
            .allowsHitTesting(false)
        }
    }

    private static func draw(_ geometry: PackOutlineGeometry, camera: MapCamera,
                             in context: GraphicsContext, size: CGSize) {
        let scale = camera.scale
        let cx = camera.centerLon, cy = MapCamera.mercatorY(lat: camera.centerLat)
        let halfW = Double(size.width) / 2 / scale, halfH = Double(size.height) / 2 / scale
        var path = Path()
        for ring in geometry.rings {
            guard ring.maxX >= cx - halfW, ring.minX <= cx + halfW,
                  ring.maxY >= cy - halfH, ring.minY <= cy + halfH else { continue }
            var outline = Path()
            outline.addLines(ring.points.map {
                CGPoint(x: size.width / 2 + ($0.x - cx) * scale, y: size.height / 2 - ($0.y - cy) * scale)
            })
            outline.closeSubpath()
            path.addPath(outline)
        }
        context.stroke(path, with: .color(stroke), style: StrokeStyle(lineWidth: 1.2, dash: dash))
    }
}
