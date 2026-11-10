import SwiftUI
import SceneryKit

/// Fly mode's map layers (spec §4.3 (4, 6), §14; #2001; lane U2): the
/// corridor tiles by legend, the route, the aircraft's track and the
/// aircraft. Its own view, so the base map never redraws for it; drawn in
/// Fly mode only. The Qt window's `O4_Qt_Fly_Layer.FlyLayer` is the same.
/// Under them, while "Live flight preview" is on, each visible square's
/// installed imagery (`LivePreviewModel`), asked again when the map moves.
struct FlyMapOverlay: View {
    @ObservedObject var model: FlyModel
    @ObservedObject var modes: AppModeModel
    @ObservedObject var camera: ViewState<MapCamera>
    @ObservedObject private var preview: LivePreviewModel

    init(model: FlyModel, modes: AppModeModel, camera: ViewState<MapCamera>) {
        self.model = model
        self.modes = modes
        self.camera = camera
        self.preview = model.preview
    }

    /// The legend's colors (Qt: `O4_Qt_Fly_Layer.LEGEND_COLORS`).
    static func color(_ key: String) -> Color {
        switch key {
        case "quick": return Color(red: 0.19, green: 0.69, blue: 0.78)   // #30B0C7
        case "built": return MapCanvasView.builtTile
        case "building": return MapCanvasView.customPatchBand
        default: return Color(white: 0.55)                              // #8C8C8C
        }
    }
    static let aircraft = Color(red: 0.04, green: 0.52, blue: 1.0)      // #0A84FF

    var body: some View {
        Group {
            if modes.mode == .fly { canvas }
        }
        // The aircraft is watched while Fly is the mode (Qt: _fly_shown).
        .onAppear { model.setWatching(modes.mode == .fly) }
        .onChange(of: modes.mode) { _, mode in model.setWatching(mode == .fly) }
    }

    private var canvas: some View {
        GeometryReader { proxy in
            Canvas { context, size in
                let cam = camera.value
                drawPreview(cam, size, &context)
                drawLayers(cam, size, &context)
            }
            .onAppear { viewMoved(proxy.size) }
            .onChange(of: camera.value) { _, _ in viewMoved(proxy.size) }
            .onChange(of: proxy.size) { _, size in viewMoved(size) }
            .onChange(of: model.livePreview) { _, _ in viewMoved(proxy.size) }
        }
        .allowsHitTesting(false)
    }

    /// The viewport and its pixels per degree of longitude, for the preview.
    private func viewMoved(_ size: CGSize) {
        let cam = camera.value
        let topLeft = cam.coordinate(of: .zero, in: size)
        let bottomRight = cam.coordinate(of: CGPoint(x: size.width, y: size.height), in: size)
        preview.setView(south: bottomRight.lat, west: topLeft.lon, north: topLeft.lat,
                        east: bottomRight.lon, pxPerDegree: cam.scale)
    }

    /// Each square's installed imagery (#2001), under everything else.
    private func drawPreview(_ cam: MapCamera, _ size: CGSize, _ context: inout GraphicsContext) {
        _ = preview.revision
        for square in preview.squares {
            guard let image = preview.image(square) else { continue }
            let a = cam.point(lon: square.west, lat: square.north, in: size)
            let b = cam.point(lon: square.east, lat: square.south, in: size)
            let rect = CGRect(x: min(a.x, b.x), y: min(a.y, b.y),
                              width: abs(b.x - a.x), height: abs(b.y - a.y))
            context.draw(Image(decorative: image, scale: 1), in: rect)
        }
    }

    private func drawLayers(_ cam: MapCamera, _ size: CGSize, _ context: inout GraphicsContext) {
        for cell in model.cells {
            let a = cam.point(lon: Double(cell.lon), lat: Double(cell.lat + 1), in: size)
            let b = cam.point(lon: Double(cell.lon + 1), lat: Double(cell.lat), in: size)
            let rect = CGRect(x: min(a.x, b.x), y: min(a.y, b.y),
                              width: abs(b.x - a.x), height: abs(b.y - a.y))
            context.stroke(Path(rect.insetBy(dx: 2, dy: 2)),
                           with: .color(Self.color(cell.key)), lineWidth: 2)
        }
        stroke(model.drawing, cam, size, &context, MapCanvasView.magenta, 2.5)
        stroke(model.track.parts, cam, size, &context, Self.aircraft, 2)
        if let last = model.track.last {
            drawAircraft(cam.point(lon: last.lon, lat: last.lat, in: size),
                         track: last.track, &context)
        }
    }

    private func stroke(_ parts: [[GeoPoint]], _ cam: MapCamera, _ size: CGSize,
                        _ context: inout GraphicsContext, _ color: Color, _ width: CGFloat) {
        var path = Path()
        for part in parts {
            guard let first = part.first else { continue }
            path.move(to: cam.point(lon: first.lon, lat: first.lat, in: size))
            for p in part.dropFirst() { path.addLine(to: cam.point(lon: p.lon, lat: p.lat, in: size)) }
        }
        context.stroke(path, with: .color(color), lineWidth: width)
    }

    /// A triangle pointing along the track.
    private func drawAircraft(_ at: CGPoint, track: Double, _ context: inout GraphicsContext) {
        let r = track * .pi / 180
        func corner(_ angle: Double, _ length: Double) -> CGPoint {
            CGPoint(x: at.x + length * sin(r + angle), y: at.y - length * cos(r + angle))
        }
        var path = Path()
        path.move(to: corner(0, 11))
        path.addLine(to: corner(2.5, 8))
        path.addLine(to: corner(-2.5, 8))
        path.closeSubpath()
        context.fill(path, with: .color(Self.aircraft))
        context.stroke(path, with: .color(.white), lineWidth: 1.5)
    }
}
