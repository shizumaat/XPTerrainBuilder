import Foundation
import Combine
import ImageIO
import SwiftUI
import SceneryKit

/// The terrain view under the patch layer (#1320, owner Q134: hillshade
/// plus contours; the Qt app's `O4_Qt_Terrain_Relief`). While the
/// "Terrain" toggle is on and the patch shows, the map's visible box is
/// asked of `terrain_relief` once the view rests (300 ms), at the view's
/// size with its long side at most `maxSide` px; the engine clips the box
/// to the patch's tile and answers `pending` until it has drawn it. The
/// toggle (off by default: the picture covers the imagery) and the
/// opacity are remembered per user.
@MainActor
final class PatchTerrainRelief: ObservableObject {
    static let defaultsKey = "patchEditor.showTerrain"
    static let opacityKey = "patchEditor.terrainOpacity"
    /// The picture's long side, in pixels (the engine allows 1024).
    static let maxSide: CGFloat = 640
    static let help = "Show the terrain under the patch: hillshade (sun from the north-west) "
        + "with contour lines, from the last build's mesh, else the elevation data."

    @Published var enabled: Bool {
        didSet {
            UserDefaults.standard.set(enabled, forKey: Self.defaultsKey)
            if !enabled { clear() }
        }
    }
    @Published var opacity: Double {
        didSet { UserDefaults.standard.set(opacity, forKey: Self.opacityKey) }
    }
    @Published private(set) var image: CGImage?
    /// The box the picture covers.
    @Published private(set) var box: O4LatLonBox?
    @Published private(set) var legend: O4TerrainRelief.Legend?
    /// The engine's sentence when the picture could not be drawn.
    @Published private(set) var error: String?

    private weak var patch: PatchEditModel?
    private var task: Task<Void, Never>?

    init(patch: PatchEditModel) {
        self.patch = patch
        enabled = UserDefaults.standard.object(forKey: Self.defaultsKey) as? Bool ?? false
        opacity = UserDefaults.standard.object(forKey: Self.opacityKey) as? Double ?? 0.6
    }

    var helpText: String { error.map { Self.help + "\n\n" + $0 } ?? Self.help }

    private func clear() {
        task?.cancel()
        image = nil; box = nil; legend = nil; error = nil
    }

    /// The map moved (or the layer appeared) at `camera` in a view of `size`.
    func viewChanged(_ camera: MapCamera, size: CGSize) {
        task?.cancel()
        guard enabled, let patch, patch.isShowing, let doc = patch.document,
              let client = patch.build?.patchEditorClient(),
              size.width >= 2, size.height >= 2 else { return }
        let nw = camera.coordinate(of: .zero, in: size)
        let se = camera.coordinate(of: CGPoint(x: size.width, y: size.height), in: size)
        let request = O4LatLonBox(minLat: se.lat, minLon: nw.lon, maxLat: nw.lat, maxLon: se.lon)
        let scale = min(1, Self.maxSide / max(size.width, size.height))
        let width = max(1, Int((size.width * scale).rounded()))
        let height = max(1, Int((size.height * scale).rounded()))
        let buildDir = patch.build?.built.first { $0.key.key == doc.tile }?.value.buildDir
        task = Task { [weak self] in
            var delay: UInt64 = 300_000_000            // the view rests
            for _ in 0..<60 {
                try? await Task.sleep(nanoseconds: delay)
                if Task.isCancelled { return }
                do {
                    let reply = try await client.terrainRelief(tile: doc.tile, bbox: request,
                                                               pixelWidth: width, pixelHeight: height,
                                                               buildDir: buildDir)
                    guard let self, !Task.isCancelled else { return }
                    if reply.pending { delay = 400_000_000; continue }
                    self.show(reply)
                    return
                } catch {
                    guard let self, !Task.isCancelled else { return }
                    self.error = "\(error)"
                    return
                }
            }
        }
    }

    private func show(_ reply: O4TerrainRelief) {
        error = nil
        legend = reply.legend
        box = reply.bbox
        image = reply.png.flatMap { data in
            CGImageSourceCreateWithData(data as CFData, nil).flatMap {
                CGImageSourceCreateImageAtIndex($0, 0, nil)
            }
        }
    }
}

/// The picture, drawn under the pack outlines and the patch at the
/// slider's opacity. Asks again whenever the camera moves.
struct PatchTerrainReliefLayer: View {
    @ObservedObject var relief: PatchTerrainRelief
    @ObservedObject var camera: ViewState<MapCamera>

    var body: some View {
        GeometryReader { proxy in
            let image = relief.enabled ? relief.image : nil
            let box = relief.box
            let opacity = relief.opacity
            let map = camera.value
            Canvas(rendersAsynchronously: false) { context, size in
                guard let image, let box else { return }
                let nw = map.point(lon: box.minLon, lat: box.maxLat, in: size)
                let se = map.point(lon: box.maxLon, lat: box.minLat, in: size)
                context.opacity = opacity
                context.draw(Image(decorative: image, scale: 1),
                             in: CGRect(x: nw.x, y: nw.y, width: se.x - nw.x, height: se.y - nw.y))
            }
            .allowsHitTesting(false)
            .onAppear { relief.viewChanged(camera.value, size: proxy.size) }
            .onChange(of: camera.value) { relief.viewChanged(camera.value, size: proxy.size) }
            .onChange(of: relief.enabled) { relief.viewChanged(camera.value, size: proxy.size) }
            .onChange(of: proxy.size) { relief.viewChanged(camera.value, size: proxy.size) }
        }
    }
}

/// The toolbar's "Terrain" check box and, while it is on, its opacity slider.
struct TerrainReliefToggle: View {
    @ObservedObject var relief: PatchTerrainRelief

    var body: some View {
        Toggle("Terrain", isOn: $relief.enabled)
            .toggleStyle(.checkbox)
            .help(relief.helpText)
        if relief.enabled {
            Slider(value: $relief.opacity, in: 0.1...1)
                .frame(width: 80)
                .help("Terrain opacity")
        }
    }
}

/// The legend's row: a contour swatch and `1 m contours · 100–110 m`.
struct TerrainReliefLegendRow: View {
    @ObservedObject var relief: PatchTerrainRelief
    /// The engine's minor contour colour (`o4_engine.relief.CONTOUR_RGB`).
    static let contour = Color(red: 214 / 255, green: 120 / 255, blue: 30 / 255)

    var body: some View {
        if relief.enabled, let legend = relief.legend {
            HStack(spacing: 6) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Self.contour)
                    .frame(width: 14, height: 8)
                Text(legend.text)
            }
        }
    }
}
