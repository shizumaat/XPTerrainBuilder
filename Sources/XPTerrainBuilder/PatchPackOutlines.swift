import Foundation
import Combine
import SwiftUI
import SceneryKit

/// The pack reference outlines under the patch layer (spec §0 A4, §2, §4;
/// mockup "pack apt.dat"): the pack's own apt.dat pavement and boundary
/// (`pack_outlines`) and its building footprints (`PackFootprints`, from
/// the `pack_objects` answer the 3D window shares through
/// `PackBuildingsStore`). Follows the loaded patch; asks only while the
/// "Pack outlines" toggle is on (persisted per user, default on). Each
/// outline carries its label (#1316): the pavement row's description or
/// the object's file name.
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
    private var pavement: [PackOutlineGeometry.Source] = []
    private var footprints: [PackOutlineGeometry.Source] = []
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
                self.pavement = reply.pavement.map { PackOutlineGeometry.Source(label: $0.mapLabel, rings: $0.rings) }
                self.missing += reply.missing
                self.project()
            } catch {
                guard let self, self.generation == gen else { return }
                self.missing.append("\(error)")
            }
        }
        guard let box = doc.bbox else { return }
        // The 3D window's box (A9); plan outlines only (#797)
        let request = TerrainPreviewModel.terrainRequest(around: box).0
        Task { [weak self] in
            do {
                let objects = try await PackBuildingsStore.shared.objects(
                    client: client, tile: doc.tile, icao: doc.icao, box: request,
                    footprintsOnly: true)
                let rings = await Task.detached(priority: .utility) {
                    PackFootprints.labelled(objects).map { PackOutlineGeometry.Source(label: $0.label, rings: [$0.ring]) }
                }.value
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
        geometry = PackOutlineGeometry(pavement + footprints)
    }

    /// The cursor readout's label (#1316): the smallest outline under the
    /// point, while the outlines are on.
    func label(atLat lat: Double, lon: Double) -> String? {
        enabled ? geometry?.label(atLon: lon, mercatorY: MapCamera.mercatorY(lat: lat)) : nil
    }
}

/// The pack outlines' look (#1316: "a bit darker and heavier stroke … a
/// light translucent color"), in one place; the Qt app's
/// `O4_Qt_Pack_Outlines` has the same values (`STROKE_RGB`, …), which
/// `tests/test_qt_pack_outline_style.py` holds equal.
enum PackOutlineStyle {
    static let strokeRGB: UInt32 = 0x3D4757
    static let strokeAlpha = 0.9
    static let lineWidth: CGFloat = 1.8
    /// Long dash, in points: 10 on, 4 off.
    static let dash: [CGFloat] = [10, 4]
    static let fillRGB: UInt32 = 0xC8D0DC
    static let fillAlpha = 0.12
    /// Labels show from this zoom level, at this size, on a dark pill.
    static let labelMinZL = 18.0
    static let labelPointSize: CGFloat = 10
    static let labelBackAlpha = 0.55
    /// Labels closer than this (points) to a drawn one are skipped.
    static let labelGap: CGFloat = 4

    static let stroke = PatchStyle.hex(strokeRGB, strokeAlpha)
    static let fill = PatchStyle.hex(fillRGB, fillAlpha)
    /// The legend swatch's fill: opaque enough to read on its dark panel.
    static let legendFill = PatchStyle.hex(fillRGB, 0.6)

    /// The labels that fit: `candidates` in priority order, each kept
    /// unless it leaves `bounds` or comes nearer than `labelGap` to one
    /// already kept (`O4_Qt_Pack_Outlines.place_labels`).
    static func placeLabels(_ candidates: [(text: String, box: CGRect)],
                            within bounds: CGRect) -> [(text: String, box: CGRect)] {
        var kept: [(text: String, box: CGRect)] = []
        for c in candidates where bounds.contains(c.box) {
            let grown = c.box.insetBy(dx: -labelGap, dy: -labelGap)
            if kept.contains(where: { grown.intersects($0.box) }) { continue }
            kept.append(c)
        }
        return kept
    }
}

/// Outlines in the map's world units (longitude, mercator Y), with their
/// extents for culling, their labels and the labels' anchors.
struct PackOutlineGeometry: Sendable {
    /// One outline as read: its label and `[lat, lon]` rings (exterior
    /// first, then the holes).
    struct Source: Sendable {
        let label: String
        let rings: [[O4LatLon]]
    }

    struct Item: Sendable {
        let label: String
        /// Exterior first, then the holes.
        let rings: [[CGPoint]]
        let minX, maxX, minY, maxY: Double
        /// The exterior's plan area in world units² (to rank, not measure).
        let area: Double
        /// The exterior's vertex mean, where the label sits.
        let anchor: CGPoint
    }

    let items: [Item]

    init(_ sources: [Source]) {
        items = sources.compactMap { source in
            let rings = source.rings.filter { $0.count >= 3 }
                .map { $0.map { CGPoint(x: $0.lon, y: MapCamera.mercatorY(lat: $0.lat)) } }
            guard let ext = rings.first else { return nil }
            let xs = ext.map(\.x), ys = ext.map(\.y)
            let n = Double(ext.count)
            return Item(label: source.label, rings: rings,
                        minX: xs.min()!, maxX: xs.max()!, minY: ys.min()!, maxY: ys.max()!,
                        area: Self.area(ext),
                        anchor: CGPoint(x: xs.reduce(0, +) / n, y: ys.reduce(0, +) / n))
        }
    }

    /// The label of the smallest outline whose exterior holds the point
    /// and none of whose holes do (`PackOutlines.label_at` in Qt).
    func label(atLon x: Double, mercatorY y: Double) -> String? {
        var best: Item?
        for item in items where x >= item.minX && x <= item.maxX && y >= item.minY && y <= item.maxY {
            if let best, item.area >= best.area { continue }
            let p = CGPoint(x: x, y: y)
            if Self.contains(item.rings[0], p), !item.rings.dropFirst().contains(where: { Self.contains($0, p) }) {
                best = item
            }
        }
        return best?.label
    }

    /// Even-odd ray cast (`O4_Qt_Pack_Outlines.ring_contains`).
    static func contains(_ ring: [CGPoint], _ p: CGPoint) -> Bool {
        var inside = false
        var j = ring.count - 1
        for i in ring.indices {
            let a = ring[i], b = ring[j]
            if (a.y > p.y) != (b.y > p.y), p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x {
                inside.toggle()
            }
            j = i
        }
        return inside
    }

    static func area(_ ring: [CGPoint]) -> Double {
        var a = 0.0
        for i in ring.indices {
            let p = ring[i], q = ring[(i + 1) % ring.count]
            a += p.x * q.y - q.x * p.y
        }
        return abs(a) / 2
    }
}

/// The filled, long-dashed layer under the patch, labelled from ZL 18
/// (#1316). It observes only the outlines and the camera — never the patch
/// model or a drag — so editing does not redraw it.
struct PatchPackOutlineLayer: View {
    @ObservedObject var outlines: PatchPackOutlines
    @ObservedObject var camera: ViewState<MapCamera>

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
        typealias Style = PackOutlineStyle
        let scale = camera.scale
        let cx = camera.centerLon, cy = MapCamera.mercatorY(lat: camera.centerLat)
        let halfW = Double(size.width) / 2 / scale, halfH = Double(size.height) / 2 / scale
        func screen(_ p: CGPoint) -> CGPoint {
            CGPoint(x: size.width / 2 + (p.x - cx) * scale, y: size.height / 2 - (p.y - cy) * scale)
        }
        var stroke = Path()
        var shown: [PackOutlineGeometry.Item] = []
        for item in geometry.items {
            guard item.maxX >= cx - halfW, item.minX <= cx + halfW,
                  item.maxY >= cy - halfH, item.minY <= cy + halfH else { continue }
            var outline = Path()
            for ring in item.rings {
                outline.addLines(ring.map(screen))
                outline.closeSubpath()
            }
            // One fill per outline, even-odd: holes stay open, and a
            // building over an apron does not cut the apron's fill.
            context.fill(outline, with: .color(Style.fill), style: FillStyle(eoFill: true))
            stroke.addPath(outline)
            shown.append(item)
        }
        context.stroke(stroke, with: .color(Style.stroke),
                       style: StrokeStyle(lineWidth: Style.lineWidth, dash: Style.dash))
        guard log2(scale * 360 / 256) >= Style.labelMinZL - 1e-9 else { return }
        drawLabels(shown.sorted { $0.area < $1.area }, screen: screen, in: context, size: size)
    }

    /// Smallest outline first, so a building names itself before the apron
    /// under it; a label that would collide is skipped.
    private static func drawLabels(_ items: [PackOutlineGeometry.Item], screen: (CGPoint) -> CGPoint,
                                   in context: GraphicsContext, size: CGSize) {
        typealias Style = PackOutlineStyle
        var texts: [String: GraphicsContext.ResolvedText] = [:]
        var candidates: [(text: String, box: CGRect)] = []
        for item in items {
            let text = texts[item.label] ?? context.resolve(
                Text(item.label).font(.system(size: Style.labelPointSize)).foregroundStyle(.white.opacity(0.9)))
            texts[item.label] = text
            let measured = text.measure(in: CGSize(width: 1_000, height: 100))
            let w = measured.width + 8, h = measured.height + 2
            let c = screen(item.anchor)
            candidates.append((item.label, CGRect(x: c.x - w / 2, y: c.y - h / 2, width: w, height: h)))
        }
        let bounds = CGRect(origin: .zero, size: size)
        for kept in Style.placeLabels(candidates, within: bounds) {
            let h = kept.box.height
            context.fill(Path(roundedRect: kept.box, cornerRadius: h / 2),
                         with: .color(.black.opacity(Style.labelBackAlpha)))
            if let text = texts[kept.text] {
                context.draw(text, at: CGPoint(x: kept.box.midX, y: kept.box.midY), anchor: .center)
            }
        }
    }
}
