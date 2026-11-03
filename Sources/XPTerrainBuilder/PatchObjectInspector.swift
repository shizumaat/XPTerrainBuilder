import Foundation
import Combine
import SwiftUI
import SceneryKit

/// The object inspector (#1702): in Edit mode a click on a pack object's
/// footprint (no node, "+" or line under it) selects the object. It is
/// highlighted like a selected shape and its name box grows to show its
/// height and the elevations of its top and bottom as the last build
/// seated it — the engine's `object_seat` answer, read from the build's
/// placement plan (the text is the engine's, so Qt's
/// `O4_Qt_Object_Inspector` shows the same words). A node or shape
/// selection, Esc, a click on open map or a new document clears it.
/// The selection (`selected.object`, a `PackObjectRef`) is what "Set object
/// elevation…" acts on (#1703, `PatchObjectElevation.swift`).
@MainActor
final class PatchObjectInspector: ObservableObject {
    @Published private(set) var selected: PackOutlineGeometry.Item?
    @Published private(set) var seat: O4ObjectSeat?
    @Published private(set) var failure: String?
    /// "Set object elevation…" is open (#1703, `PatchObjectElevation.swift`).
    @Published var showsSetElevation = false

    private(set) weak var patch: PatchEditModel?
    private let outlines: PatchPackOutlines
    private var query: Task<Void, Never>?
    private var subscriptions: Set<AnyCancellable> = []

    init(patch: PatchEditModel, outlines: PatchPackOutlines) {
        self.patch = patch
        self.outlines = outlines
        outlines.$geometry.sink { [weak self] _ in self?.clear() }.store(in: &subscriptions)
        patch.$selection.sink { [weak self] s in if !s.isEmpty { self?.clear() } }.store(in: &subscriptions)
        patch.$shapeSelection.sink { [weak self] s in if !s.isEmpty { self?.clear() } }
            .store(in: &subscriptions)
    }

    /// Select the object under (lat, lon); false when there is none.
    @discardableResult
    func select(atLat lat: Double, lon: Double) -> Bool {
        guard let item = outlines.object(atLat: lat, lon: lon), let object = item.object else { return false }
        if selected?.object == object { return true }
        clear()
        selected = item
        ask(object)
        return true
    }

    func clear() {
        query?.cancel()
        query = nil
        if selected != nil { selected = nil }
        if seat != nil { seat = nil }
        if failure != nil { failure = nil }
    }

    /// The name box's lines: the name, then the engine's.
    var lines: [String] {
        guard let selected else { return [] }
        if let seat { return [selected.label] + seat.lines }
        return [selected.label, failure ?? "Reading its seat…"]
    }

    /// Asks once, again while the engine reports the ground still loading.
    func ask(_ object: PackObjectRef) {
        guard let doc = patch?.document, let build = patch?.build,
              let client = build.patchEditorClient() else { return }
        let buildDir = Self.buildDir(object, build: build)
        query?.cancel()
        query = Task { @MainActor [weak self] in
            for _ in 0..<20 {
                do {
                    let reply = try await client.objectSeat(tile: doc.tile, icao: doc.icao, object: object,
                                                            buildDir: buildDir)
                    guard let self, !Task.isCancelled else { return }
                    self.seat = reply
                    if !reply.pending { return }
                } catch {
                    guard let self, !Task.isCancelled else { return }
                    self.failure = "Its seat could not be read: \(error)"
                    return
                }
                try? await Task.sleep(nanoseconds: 400_000_000)
                if Task.isCancelled { return }
            }
        }
    }
}

extension PatchObjectInspector {
    /// The built tile folder an object's ground is read from.
    static func buildDir(_ object: PackObjectRef, build: BuildModel) -> String? {
        build.tileFolder(BuildModel.TileCoord(lat: Int(floor(object.lat)), lon: Int(floor(object.lon))))?.path
    }
}

/// The selected object over the patch: its outline in the selection colour
/// over a light tint (as a selected shape), and its grown name box at the
/// outline's label anchor. Draws nothing and takes no clicks otherwise.
struct PatchObjectInspectorLayer: View {
    @ObservedObject var inspector: PatchObjectInspector
    @ObservedObject var camera: ViewState<MapCamera>

    var body: some View {
        if let item = inspector.selected {
            let lines = inspector.lines
            Canvas(rendersAsynchronously: false) { context, size in
                Self.draw(item, lines: lines, camera: camera.value, in: context, size: size)
            }
            .allowsHitTesting(false)
        }
    }

    private static func draw(_ item: PackOutlineGeometry.Item, lines: [String], camera: MapCamera,
                             in context: GraphicsContext, size: CGSize) {
        let scale = camera.scale
        let cx = camera.centerLon, cy = MapCamera.mercatorY(lat: camera.centerLat)
        func screen(_ p: CGPoint) -> CGPoint {
            CGPoint(x: size.width / 2 + (p.x - cx) * scale, y: size.height / 2 - (p.y - cy) * scale)
        }
        var outline = Path()
        for ring in item.rings {
            outline.addLines(ring.map(screen))
            outline.closeSubpath()
        }
        let colour = PatchEditLayer.selectionColor
        context.fill(outline, with: .color(colour.opacity(0.18)), style: FillStyle(eoFill: true))
        context.stroke(outline, with: .color(colour), style: StrokeStyle(lineWidth: 2 * PackOutlineStyle.lineWidth,
                                                                          lineJoin: .round))
        // The grown name box: the name in bold, then the seat's lines.
        let text = lines.enumerated().reduce(Text("")) { acc, line in
            let t = Text((line.offset == 0 ? "" : "\n") + line.element)
            return acc + (line.offset == 0 ? t.bold() : t)
        }
        let resolved = context.resolve(text.font(.system(size: PackOutlineStyle.labelPointSize + 1))
            .foregroundStyle(.white))
        let measured = resolved.measure(in: CGSize(width: 360, height: 400))
        let c = screen(item.anchor)
        let box = CGRect(x: c.x - measured.width / 2 - 8, y: c.y - measured.height / 2 - 5,
                         width: measured.width + 16, height: measured.height + 10)
        context.fill(Path(roundedRect: box, cornerRadius: 7), with: .color(.black.opacity(0.78)))
        context.stroke(Path(roundedRect: box, cornerRadius: 7), with: .color(colour), lineWidth: 1.5)
        context.draw(resolved, in: box.insetBy(dx: 8, dy: 5))
    }
}
