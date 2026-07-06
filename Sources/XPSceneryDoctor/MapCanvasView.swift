import SwiftUI
import SceneryKit

/// The zoomable world map: night-chart styling (matching the app icon),
/// X-Plane's 1° tile grid, coverage tints for mesh/ortho/landmark packs,
/// sectional-style airport marks, and tile selection.
struct MapCanvasView: View {
    @EnvironmentObject var controller: AnalysisController
    @ObservedObject var camera: ViewState<MapCamera>
    @ObservedObject var canvasSize: ViewState<CGSize>

    private var overlays: MapOverlays { controller.mapOverlays }

    @StateObject private var dragAnchor = ViewState<MapCamera?>(nil)
    @StateObject private var rubberBand = ViewState<CGRect?>(nil)

    // Night-chart palette (the icon's world).
    static let ocean = Color(red: 0.043, green: 0.051, blue: 0.071)
    static let land = Color(red: 0.118, green: 0.133, blue: 0.161)
    static let coast = Color(red: 0.30, green: 0.36, blue: 0.44)
    static let grid = Color(red: 0.55, green: 0.63, blue: 0.75).opacity(0.18)
    static let gridMajor = Color(red: 0.55, green: 0.63, blue: 0.75).opacity(0.34)
    static let magenta = Color(red: 0.78, green: 0.25, blue: 0.47)
    static let tintOrtho = Color(red: 0.85, green: 0.55, blue: 0.20)
    static let tintMesh = Color(red: 0.30, green: 0.65, blue: 0.45)
    static let tintLandmark = Color(red: 0.30, green: 0.55, blue: 0.90)
    static let selection = Color.white

    var body: some View {
        GeometryReader { proxy in
            Canvas(rendersAsynchronously: false) { context, size in
                draw(context: context, size: size)
            }
            .background(Self.ocean)
            .gesture(panOrRubberBand(size: proxy.size))
            .gesture(doubleClickZoom(size: proxy.size))
            .gesture(clickSelect(size: proxy.size))
            .overlay(ScrollZoomCatcher(
                onScroll: { location, delta in
                    zoom(by: pow(1.0035, delta), anchoredAt: location, size: proxy.size)
                },
                onMagnify: { location, magnification in
                    zoom(by: 1 + magnification, anchoredAt: location, size: proxy.size)
                }
            ))
            .overlay(alignment: .bottomLeading) { legend }
            .overlay(alignment: .topTrailing) { zoomControls }
            .onAppear {
                // First layout: fit the world so the map fills the viewport
                // from the very first frame — no small-then-resize flash.
                if canvasSize.value == .zero {
                    camera.value = MapCamera.fitted(to: proxy.size)
                }
                canvasSize.value = proxy.size
            }
            .onChange(of: proxy.size) {
                canvasSize.value = proxy.size
                var cam = camera.value
                cam.clamp(in: proxy.size)
                camera.value = cam
            }
        }
        .clipped()
    }

    /// Zoom keeping the geographic point under `anchor` fixed on screen.
    private func zoom(by factor: Double, anchoredAt anchor: CGPoint, size: CGSize) {
        var cam = camera.value
        let coord = cam.coordinate(of: anchor, in: size)
        cam.scale *= factor
        cam.clamp(in: size)
        cam.centerLon = coord.lon - (Double(anchor.x) - Double(size.width) / 2) / cam.scale
        cam.centerLat = coord.lat + (Double(anchor.y) - Double(size.height) / 2) / cam.scale
        cam.clamp(in: size)
        camera.value = cam
    }

    // MARK: - Drawing

    private func draw(context: GraphicsContext, size: CGSize) {
        let cam = camera.value
        let (minLon, maxLon, minLat, maxLat) = visibleBounds(cam, size)

        // Land: 110m for world views; 50m rings (bbox-culled to the
        // viewport) once zoomed in enough to see the difference.
        var landPath = Path()
        if cam.scale > 7 && !LandData.detailedRings.isEmpty {
            for ring in LandData.detailedRings {
                guard ring.maxLon > minLon, ring.minLon < maxLon,
                      ring.maxLat > minLat, ring.minLat < maxLat,
                      let first = ring.points.first else { continue }
                landPath.move(to: cam.point(lon: first.x, lat: first.y, in: size))
                for pt in ring.points.dropFirst() {
                    landPath.addLine(to: cam.point(lon: pt.x, lat: pt.y, in: size))
                }
                landPath.closeSubpath()
            }
        } else {
            for ring in LandData.polygons {
                guard let first = ring.first else { continue }
                landPath.move(to: cam.point(lon: first.x, lat: first.y, in: size))
                for pt in ring.dropFirst() {
                    landPath.addLine(to: cam.point(lon: pt.x, lat: pt.y, in: size))
                }
                landPath.closeSubpath()
            }
        }
        context.fill(landPath, with: .color(Self.land))
        context.stroke(landPath, with: .color(Self.coast), lineWidth: 1)

        // Tile tints — numeric compares only; batch by kind into 3 paths so
        // the frame does 3 fills, not one per tile.
        var orthoPath = Path(), meshPath = Path(), landmarkPath = Path()
        for tile in overlays.tintTiles {
            guard Double(tile.lon + 1) > minLon, Double(tile.lon) < maxLon,
                  Double(tile.lat + 1) > minLat, Double(tile.lat) < maxLat else { continue }
            let rect = tileRect(lat: tile.lat, lon: tile.lon, cam: cam, size: size)
            switch tile.kind {
            case .ortho: orthoPath.addRect(rect)
            case .mesh: meshPath.addRect(rect)
            default: landmarkPath.addRect(rect)
            }
        }
        context.fill(orthoPath, with: .color(Self.tintOrtho.opacity(0.22)))
        context.fill(meshPath, with: .color(Self.tintMesh.opacity(0.22)))
        context.fill(landmarkPath, with: .color(Self.tintLandmark.opacity(0.22)))

        // Graticule: 10° always, 1° when zoomed in.
        drawGrid(context: context, size: size, cam: cam, step: 10, color: Self.gridMajor)
        if cam.scale > 14 {
            drawGrid(context: context, size: size, cam: cam, step: 1, color: Self.grid)
        }

        // Tile coordinates in the top-right corner of each tile, once tiles
        // are big enough for the label to fit.
        if cam.scale > 52 {
            for lat in Int(floor(minLat))...Int(ceil(maxLat)) {
                for lon in Int(floor(minLon))...Int(ceil(maxLon)) {
                    guard lat >= -90, lat < 90, lon >= -180, lon < 180 else { continue }
                    let corner = cam.point(lon: Double(lon + 1), lat: Double(lat + 1), in: size)
                    context.draw(
                        Text(TileMath.key(lat: lat, lon: lon))
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundStyle(Self.gridMajor),
                        at: CGPoint(x: corner.x - 4, y: corner.y + 4),
                        anchor: .topTrailing
                    )
                }
            }
        }

        // Selected tiles.
        for key in controller.selectedTiles {
            guard let tile = TileMath.parse(key) else { continue }
            let rect = tileRect(lat: tile.lat, lon: tile.lon, cam: cam, size: size)
            context.fill(Path(rect), with: .color(Self.selection.opacity(0.14)))
            context.stroke(Path(rect), with: .color(Self.selection.opacity(0.85)),
                           lineWidth: 1.5)
        }

        // Airports: sectional dots, ICAO labels when zoomed.
        let showLabels = cam.scale > 26
        let radius: CGFloat = cam.scale > 26 ? 5 : (cam.scale > 8 ? 3.5 : 2.2)
        for airport in overlays.airports {
            let lon = airport.info.longitude, lat = airport.info.latitude
            guard lon > minLon - 1, lon < maxLon + 1, lat > minLat - 1, lat < maxLat + 1 else { continue }
            let p = cam.point(lon: lon, lat: lat, in: size)
            let dim = airport.status == .uninstalled
            let color = Self.magenta.opacity(dim ? 0.35 : 0.95)
            let circle = Path(ellipseIn: CGRect(x: p.x - radius, y: p.y - radius,
                                                width: radius * 2, height: radius * 2))
            context.stroke(circle, with: .color(color), lineWidth: max(1.4, radius * 0.4))
            if showLabels {
                context.draw(
                    Text(airport.icao)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(color),
                    at: CGPoint(x: p.x, y: p.y - radius - 8)
                )
            }
        }

        // Rubber-band rectangle.
        if let band = rubberBand.value {
            context.fill(Path(band), with: .color(Self.selection.opacity(0.08)))
            context.stroke(Path(band), with: .color(Self.selection.opacity(0.6)),
                           style: StrokeStyle(lineWidth: 1, dash: [4, 3]))
        }
    }

    private func visibleBounds(_ cam: MapCamera, _ size: CGSize) -> (Double, Double, Double, Double) {
        let halfW = Double(size.width) / 2 / cam.scale
        let halfH = Double(size.height) / 2 / cam.scale
        return (cam.centerLon - halfW, cam.centerLon + halfW,
                cam.centerLat - halfH, cam.centerLat + halfH)
    }

    private func tileRect(lat: Int, lon: Int, cam: MapCamera, size: CGSize) -> CGRect {
        let topLeft = cam.point(lon: Double(lon), lat: Double(lat + 1), in: size)
        let bottomRight = cam.point(lon: Double(lon + 1), lat: Double(lat), in: size)
        return CGRect(x: topLeft.x, y: topLeft.y,
                      width: bottomRight.x - topLeft.x, height: bottomRight.y - topLeft.y)
    }

    private func drawGrid(context: GraphicsContext, size: CGSize, cam: MapCamera,
                          step: Int, color: Color) {
        let (minLon, maxLon, minLat, maxLat) = visibleBounds(cam, size)
        var path = Path()
        var lon = Int(floor(minLon / Double(step))) * step
        while Double(lon) <= maxLon {
            let x = cam.point(lon: Double(lon), lat: 0, in: size).x
            path.move(to: CGPoint(x: x, y: 0))
            path.addLine(to: CGPoint(x: x, y: size.height))
            lon += step
        }
        var lat = Int(floor(minLat / Double(step))) * step
        while Double(lat) <= maxLat {
            let y = cam.point(lon: 0, lat: Double(lat), in: size).y
            path.move(to: CGPoint(x: 0, y: y))
            path.addLine(to: CGPoint(x: size.width, y: y))
            lat += step
        }
        context.stroke(path, with: .color(color), lineWidth: 0.5)
    }

    // MARK: - Gestures

    /// Drag pans; shift-drag rubber-band selects tiles.
    private func panOrRubberBand(size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 3)
            .onChanged { value in
                let shift = NSApp.currentEvent?.modifierFlags.contains(.shift) ?? false
                if shift || rubberBand.value != nil {
                    rubberBand.value = CGRect(
                        x: min(value.startLocation.x, value.location.x),
                        y: min(value.startLocation.y, value.location.y),
                        width: abs(value.translation.width),
                        height: abs(value.translation.height))
                } else {
                    if dragAnchor.value == nil { dragAnchor.value = camera.value }
                    guard let anchor = dragAnchor.value else { return }
                    var cam = anchor
                    cam.centerLon = anchor.centerLon - Double(value.translation.width) / anchor.scale
                    cam.centerLat = anchor.centerLat + Double(value.translation.height) / anchor.scale
                    cam.clamp(in: size)
                    camera.value = cam
                }
            }
            .onEnded { value in
                if let band = rubberBand.value {
                    selectTiles(in: band, size: size,
                                additive: NSApp.currentEvent?.modifierFlags.contains(.command) ?? false)
                    rubberBand.value = nil
                }
                dragAnchor.value = nil
            }
    }

    private func clickSelect(size: CGSize) -> some Gesture {
        SpatialTapGesture(count: 1)
            .onEnded { value in
                let additive = NSApp.currentEvent?.modifierFlags.contains(.command) ?? false
                let coord = camera.value.coordinate(of: value.location, in: size)
                let key = TileMath.key(latitude: coord.lat, longitude: coord.lon)
                if additive {
                    if controller.selectedTiles.contains(key) {
                        controller.selectedTiles.remove(key)
                    } else {
                        controller.selectedTiles.insert(key)
                    }
                } else {
                    controller.selectedTiles = controller.selectedTiles == [key] ? [] : [key]
                }
            }
    }

    private func doubleClickZoom(size: CGSize) -> some Gesture {
        SpatialTapGesture(count: 2)
            .onEnded { value in
                var cam = camera.value
                let coord = cam.coordinate(of: value.location, in: size)
                cam.centerLon = coord.lon
                cam.centerLat = coord.lat
                cam.scale *= 2
                cam.clamp(in: size)
                camera.value = cam
            }
    }

    private func selectTiles(in band: CGRect, size: CGSize, additive: Bool) {
        let cam = camera.value
        let a = cam.coordinate(of: CGPoint(x: band.minX, y: band.maxY), in: size)
        let b = cam.coordinate(of: CGPoint(x: band.maxX, y: band.minY), in: size)
        var keys = Set<String>()
        let latRange = Int(floor(a.lat))...Int(floor(b.lat))
        let lonRange = Int(floor(a.lon))...Int(floor(b.lon))
        guard latRange.count * lonRange.count <= 4000 else { return } // sanity
        for lat in latRange {
            for lon in lonRange {
                keys.insert(TileMath.key(lat: lat, lon: lon))
            }
        }
        controller.selectedTiles = additive ? controller.selectedTiles.union(keys) : keys
    }

    // MARK: - Chrome

    private var legend: some View {
        HStack(spacing: 10) {
            legendDot(Self.magenta, "Airport")
            legendSwatch(Self.tintOrtho, "Ortho")
            legendSwatch(Self.tintMesh, "Mesh")
            legendSwatch(Self.tintLandmark, "Landmark")
        }
        .font(.caption2)
        .padding(6)
        .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 6))
        .padding(8)
    }

    private func legendDot(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 3) {
            Circle().stroke(color, lineWidth: 1.5).frame(width: 7, height: 7)
            Text(label).foregroundStyle(.white.opacity(0.8))
        }
    }

    private func legendSwatch(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 3) {
            RoundedRectangle(cornerRadius: 1.5).fill(color.opacity(0.5))
                .frame(width: 9, height: 9)
            Text(label).foregroundStyle(.white.opacity(0.8))
        }
    }

    private var zoomControls: some View {
        VStack(spacing: 0) {
            Button { zoom(by: 1.5) } label: { Image(systemName: "plus") }
            Divider().frame(width: 20)
            Button { zoom(by: 1 / 1.5) } label: { Image(systemName: "minus") }
        }
        .buttonStyle(.borderless)
        .padding(6)
        .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 6))
        .padding(8)
        .help("Zoom (double-click the map to zoom in; drag to pan; shift-drag to select tiles)")
    }

    private func zoom(by factor: Double) {
        var cam = camera.value
        cam.scale *= factor
        cam.clamp(in: canvasSize.value)
        camera.value = cam
    }
}
