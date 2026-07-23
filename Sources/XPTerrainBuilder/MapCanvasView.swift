import SwiftUI
import SceneryKit

/// The zoomable world map: night-chart styling (matching the app icon),
/// X-Plane's 1° tile grid, coverage tints for mesh/ortho/landmark packs,
/// sectional-style airport marks, and tile selection.
struct MapCanvasView: View {
    @EnvironmentObject var controller: AnalysisController
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var buildActivity: BuildActivityModel
    /// Live provider imagery — observed so newly fetched tiles redraw the map.
    @EnvironmentObject var imagery: ImageryModel
    @ObservedObject var camera: ViewState<MapCamera>
    @ObservedObject var canvasSize: ViewState<CGSize>

    private var overlays: MapOverlays { controller.mapOverlays }
    @AppStorage("MapSceneryFilter") private var sceneryFilterRaw = MapSceneryFilter.all.rawValue
    private var sceneryFilter: MapSceneryFilter {
        MapSceneryFilter(rawValue: sceneryFilterRaw) ?? .all
    }

    @StateObject private var dragAnchor = ViewState<MapCamera?>(nil)

    // Night-chart palette (the icon's world).
    static let ocean = Color(red: 0.043, green: 0.051, blue: 0.071)
    static let land = Color(red: 0.118, green: 0.133, blue: 0.161)
    static let coast = Color(red: 0.30, green: 0.36, blue: 0.44)
    static let grid = Color(red: 0.55, green: 0.63, blue: 0.75).opacity(0.18)
    static let gridMajor = Color(red: 0.55, green: 0.63, blue: 0.75).opacity(0.34)
    static let magenta = Color(red: 0.78, green: 0.25, blue: 0.47)
    static let tintOrtho = Color(red: 0.85, green: 0.55, blue: 0.20)
    static let regionOutline = Color(white: 0.62).opacity(0.85)
    static let tintMesh = Color(red: 0.30, green: 0.65, blue: 0.45)
    static let tintLandmark = Color(red: 0.30, green: 0.55, blue: 0.90)
    static let selection = Color.white

    // Build mode: the Qt map's vocabulary. Built tiles are colored by their
    // zoom level; selection is yellow; done/error badges green/red.
    static let buildSelection = Color(red: 1.0, green: 0.84, blue: 0.04) // #FFD60A
    static let badgeDone = Color(red: 0.18, green: 0.62, blue: 0.36)     // #2E9E5B
    static let badgeError = Color(red: 0.90, green: 0.22, blue: 0.17)    // #E5372B
    static func zlColor(_ zl: Int?) -> Color {
        switch zl ?? 0 {
        case ..<15 where zl != nil: return Color(red: 0.36, green: 0.55, blue: 0.85) // ≤14 blue
        case 15: return Color(red: 0.40, green: 0.84, blue: 0.89)  // cyan
        case 16: return Color(red: 0.30, green: 0.69, blue: 0.43)  // green
        case 17: return Color(red: 0.91, green: 0.76, blue: 0.24)  // yellow
        case 18: return Color(red: 0.95, green: 0.66, blue: 0.36)  // orange
        case 19: return Color(red: 0.94, green: 0.48, blue: 0.43)  // red
        default: return Color(red: 0.60, green: 0.65, blue: 0.69)  // unknown grey
        }
    }

    var body: some View {
        GeometryReader { proxy in
            Canvas(rendersAsynchronously: false) { context, size in
                draw(context: context, size: size)
            }
            .background(Self.ocean)
            .gesture(pan(size: proxy.size))
            .gesture(doubleClickZoom(size: proxy.size))
            .gesture(tileSelect(size: proxy.size))
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
            .overlay(alignment: .bottomTrailing) {
                VStack(alignment: .trailing, spacing: 6) {
                    ScanProgressChip()
                    zoomChip
                }
            }
            .onAppear {
                // First layout: fit the world so the map fills the viewport
                // from the very first frame — no small-then-resize flash.
                if canvasSize.value == .zero {
                    camera.value = MapCamera.fitted(to: proxy.size)
                }
                canvasSize.value = proxy.size
                controller.scheduleViewportUpdate()
            }
            .onChange(of: proxy.size) {
                canvasSize.value = proxy.size
                var cam = camera.value
                cam.clamp(in: proxy.size)
                camera.value = cam
                controller.scheduleViewportUpdate()
            }
            // The canvas is the ONLY view observing the camera — the
            // debounced viewport recompute fans out to inspector/results
            // from the controller, so a drag frame redraws just the map.
            .onChange(of: camera.value) {
                controller.scheduleViewportUpdate()
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

        // Live imagery from the selected provider, over the vector land
        // (which stays visible while tiles stream in).
        drawImagery(context: context, size: size, cam: cam,
                    minLon: minLon, maxLon: maxLon, minLat: minLat, maxLat: maxLat)

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

        if buildModel.mode == .build, sceneryFilter != .othersOnly {
            drawBuildOverlays(context: context, size: size, cam: cam,
                              minLon: minLon, maxLon: maxLon, minLat: minLat, maxLat: maxLat)
        }

        // Other installed ortho/mesh packages (SpainUHD, meshes, foreign
        // zOrtho tiles): gray boundary outlines showing their coverage and
        // overlap. Our own tiles are skipped — they are already the colored
        // squares: a pack is "ours" when its folder is one of the engine
        // scan's build dirs (covers building straight into Custom Scenery)
        // or a symlink into the working dir.
        if sceneryFilter != .builtOnly {
            let basePath = buildModel.tileBaseFolder?.path
            let builtDirs = Set(buildModel.built.values.map(\.buildDir))
            var regionPath = Path()
            for region in overlays.regions {
                if builtDirs.contains(region.contentRootPath) { continue }
                if let basePath, let resolved = region.resolvedPath,
                   resolved.hasPrefix(basePath) { continue }
                for edge in region.edges {
                    guard max(edge.a.lon, edge.b.lon) > minLon,
                          min(edge.a.lon, edge.b.lon) < maxLon,
                          max(edge.a.lat, edge.b.lat) > minLat,
                          min(edge.a.lat, edge.b.lat) < maxLat else { continue }
                    regionPath.move(to: cam.point(lon: edge.a.lon, lat: edge.a.lat, in: size))
                    regionPath.addLine(to: cam.point(lon: edge.b.lon, lat: edge.b.lat, in: size))
                }
            }
            context.stroke(regionPath, with: .color(Self.regionOutline), lineWidth: 1.5)
        }

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

        // Landmark pack marks: kind-colored diamonds at the pack's tile
        // centroid (tile-resolution until DSF placements are parsed). Only
        // once zoomed past world view — they'd be noise at 1:world.
        if cam.scale > 8 {
            for marker in overlays.markers {
                guard marker.lon > minLon - 1, marker.lon < maxLon + 1,
                      marker.lat > minLat - 1, marker.lat < maxLat + 1 else { continue }
                let p = cam.point(lon: marker.lon, lat: marker.lat, in: size)
                let r: CGFloat = cam.scale > 26 ? 5 : 3.5
                var diamond = Path()
                diamond.move(to: CGPoint(x: p.x, y: p.y - r))
                diamond.addLine(to: CGPoint(x: p.x + r, y: p.y))
                diamond.addLine(to: CGPoint(x: p.x, y: p.y + r))
                diamond.addLine(to: CGPoint(x: p.x - r, y: p.y))
                diamond.closeSubpath()
                let color = Self.tintLandmark.opacity(marker.status == .uninstalled ? 0.35 : 0.95)
                context.stroke(diamond, with: .color(color), lineWidth: max(1.4, r * 0.4))
                if showLabels {
                    context.draw(
                        Text(marker.packName.count > 22
                             ? marker.packName.prefix(21) + "…"
                             : marker.packName)
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundStyle(color),
                        at: CGPoint(x: p.x, y: p.y - r - 8)
                    )
                }
            }
        }

    }

    /// Build mode's tile layers, mirroring the Qt map: built tiles filled
    /// with their ZL color (double inset border when installed in X-Plane,
    /// "PROV ZL*" center label), yellow selection (solid border = active
    /// tile, dashed = other selected), and per-tile progress ring badges.
    /// Web-mercator provider tiles reprojected onto the equirectangular
    /// canvas. Each 256px tile draws in horizontal strips (a piecewise-
    /// linear latitude warp): one strip when the tile spans little
    /// latitude, more near world views where mercator stretch shows.
    private func drawImagery(context: GraphicsContext, size: CGSize, cam: MapCamera,
                             minLon: Double, maxLon: Double,
                             minLat: Double, maxLat: Double) {
        guard imagery.hasActiveSource else { return }

        // Tile zoom so one 256px tile is roughly screen resolution
        // (256·2^z/360 px per degree against the camera's scale).
        let idealZ = Int(ceil(log2(cam.scale * 360 / 256)))
        let z = min(max(idealZ, 2), min(imagery.activeMaxZL, 21))
        let n = 1 << z

        let xMin = Int(floor(WebMercator.tileX(lon: minLon, z: z)))
        let xMax = Int(floor(WebMercator.tileX(lon: maxLon, z: z)))
        let yMin = max(Int(floor(WebMercator.tileY(lat: maxLat, z: z))), 0)
        let yMax = min(Int(floor(WebMercator.tileY(lat: minLat, z: z))), n - 1)
        guard xMax >= xMin, yMax >= yMin,
              (xMax - xMin + 1) * (yMax - yMin + 1) <= 400 else { return }

        /// Screen rect of a mercator tile (single rect, no warp) — used for
        /// low-res stand-ins.
        func tileRect(_ tz: Int, _ tx: Int, _ ty: Int) -> CGRect {
            let left = cam.point(lon: WebMercator.lon(tileX: Double(tx), z: tz),
                                 lat: 0, in: size).x
            let right = cam.point(lon: WebMercator.lon(tileX: Double(tx + 1), z: tz),
                                  lat: 0, in: size).x
            let top = cam.point(lon: 0, lat: WebMercator.lat(tileY: Double(ty), z: tz),
                                in: size).y
            let bottom = cam.point(lon: 0, lat: WebMercator.lat(tileY: Double(ty + 1), z: tz),
                                   in: size).y
            return CGRect(x: left, y: top, width: right - left, height: bottom - top)
        }

        /// One tile, strip-warped from mercator onto the equirect canvas.
        func drawTile(_ cg: CGImage, x: Int, y: Int, alpha: CGFloat) {
            let img = Image(decorative: cg, scale: 1)
            let latTop = WebMercator.lat(tileY: Double(y), z: z)
            let latBottom = WebMercator.lat(tileY: Double(y + 1), z: z)
            let strips = max(1, min(10, Int((latTop - latBottom) / 3)))
            let left = cam.point(lon: WebMercator.lon(tileX: Double(x), z: z),
                                 lat: 0, in: size).x
            let right = cam.point(lon: WebMercator.lon(tileX: Double(x + 1), z: z),
                                  lat: 0, in: size).x
            for strip in 0..<strips {
                let fTop = Double(strip) / Double(strips)
                let fBottom = Double(strip + 1) / Double(strips)
                let top = cam.point(
                    lon: 0, lat: WebMercator.lat(tileY: Double(y) + fTop, z: z),
                    in: size).y
                let bottom = cam.point(
                    lon: 0, lat: WebMercator.lat(tileY: Double(y) + fBottom, z: z),
                    in: size).y
                let dest = CGRect(x: left, y: top,
                                  width: right - left, height: bottom - top)
                guard dest.width > 0.1, dest.height > 0.1 else { continue }
                // Scale the whole tile so its rows [fTop, fBottom] land
                // exactly in the strip's destination rect.
                let fullHeight = dest.height / (fBottom - fTop)
                let fullRect = CGRect(x: dest.minX,
                                      y: dest.minY - fullHeight * fTop,
                                      width: dest.width, height: fullHeight)
                var layer = context
                layer.opacity = alpha
                if strips > 1 {
                    layer.clip(to: Path(dest))
                }
                layer.draw(img, in: fullRect)
            }
        }

        // Outgoing source, drawn from cache beneath the incoming one while
        // a switch cross-fades (no fetches for the old source).
        if imagery.crossfading {
            for y in yMin...yMax {
                for x in xMin...xMax {
                    let wrapped = ((x % n) + n) % n
                    if let cg = imagery.cachedImage(previous: true, z: z, x: wrapped, y: y) {
                        drawTile(cg, x: x, y: y, alpha: 1)
                    }
                }
            }
        }

        for y in yMin...yMax {
            for x in xMin...xMax {
                let wrapped = ((x % n) + n) % n
                if let (cg, alpha) = imagery.image(z: z, x: wrapped, y: y) {
                    // Blur-up stand-in beneath a tile still fading in.
                    if alpha < 1 {
                        drawAncestor(x: x, wrapped: wrapped, y: y, z: z,
                                     n: n, tileRect: tileRect)
                    }
                    drawTile(cg, x: x, y: y, alpha: alpha)
                } else {
                    // Not loaded yet: show the nearest cached lower zoom,
                    // upscaled — soft blur instead of a hard empty square.
                    drawAncestor(x: x, wrapped: wrapped, y: y, z: z,
                                 n: n, tileRect: tileRect)
                }
            }
        }

        func drawAncestor(x: Int, wrapped: Int, y: Int, z: Int, n: Int,
                          tileRect: (Int, Int, Int) -> CGRect) {
            var az = z, ax = wrapped, ay = y
            for _ in 0..<5 {
                guard az > 2 else { return }
                az -= 1; ax /= 2; ay /= 2
                if let cg = imagery.cachedImage(previous: false, z: az, x: ax, y: ay) {
                    let shift = (x - wrapped) / max(1 << (z - az), 1)
                    let parentRect = tileRect(az, ax + shift, ay)
                    let childRect = tileRect(z, x, y)
                    var layer = context
                    layer.clip(to: Path(childRect))
                    layer.draw(Image(decorative: cg, scale: 1), in: parentRect)
                    return
                }
            }
        }
    }

    private func drawBuildOverlays(context: GraphicsContext, size: CGSize, cam: MapCamera,
                                   minLon: Double, maxLon: Double,
                                   minLat: Double, maxLat: Double) {
        func visible(_ coord: BuildModel.TileCoord) -> Bool {
            Double(coord.lon + 1) > minLon && Double(coord.lon) < maxLon
                && Double(coord.lat + 1) > minLat && Double(coord.lat) < maxLat
        }
        func rect(_ coord: BuildModel.TileCoord) -> CGRect {
            tileRect(lat: coord.lat, lon: coord.lon, cam: cam, size: size)
        }

        // Built tiles: ZL color fill + darker border; installed adds the
        // double (inset) border; center label once tiles are big enough.
        let showTileLabels = cam.scale > 44
        for (coord, info) in buildModel.built where visible(coord) {
            let r = rect(coord)
            let color = Self.zlColor(info.zl)
            context.fill(Path(r), with: .color(color.opacity(0.27)))
            context.stroke(Path(r), with: .color(color.opacity(0.85)), lineWidth: 2)
            if buildModel.installed.contains(coord) {
                context.stroke(Path(r.insetBy(dx: r.width * 0.03, dy: r.height * 0.03)),
                               with: .color(color.opacity(0.9)), lineWidth: 1.5)
            }
            if showTileLabels, let zl = info.zl {
                let provider = info.provider.isEmpty ? "?" : String(info.provider.prefix(4))
                context.draw(
                    Text("\(provider) \(zl)\(info.hasZones ? "*" : "")")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(.white.opacity(0.85)),
                    at: CGPoint(x: r.midX, y: r.maxY - 10))
            }
            // Mixed imagery sources: warning triangle in the top-right
            // corner so affected tiles stand out at a glance (details +
            // cleanup in the selection pane's Imagery row).
            if buildModel.conflictTiles.contains(coord), r.width > 14 {
                let s = min(max(r.width * 0.16, 11), 20)
                context.draw(
                    Text(Image(systemName: "exclamationmark.triangle.fill"))
                        .font(.system(size: s))
                        .foregroundStyle(.yellow),
                    at: CGPoint(x: r.maxX - s * 0.7, y: r.minY + s * 0.7))
            }
        }

        // Selection: yellow; active tile solid 3px, others dashed 2px.
        for coord in buildModel.selected where visible(coord) {
            let r = rect(coord)
            context.fill(Path(r), with: .color(Self.buildSelection.opacity(0.14)))
            if coord == buildModel.activeTile {
                context.stroke(Path(r.insetBy(dx: 1.5, dy: 1.5)),
                               with: .color(Self.buildSelection), lineWidth: 3)
            } else {
                context.stroke(Path(r.insetBy(dx: 1, dy: 1)),
                               with: .color(Self.buildSelection),
                               style: StrokeStyle(lineWidth: 2, dash: [5, 4]))
            }
        }

        // Progress badges: rings at tile centers during a run.
        for (coord, progress) in buildActivity.tiles where visible(coord) {
            drawBadge(context: context, rect: rect(coord), progress: progress)
        }
    }

    private func drawBadge(context: GraphicsContext, rect: CGRect, progress: TileProgress) {
        let radius = min(max(min(rect.width, rect.height) * 0.18, 9), 22)
        let center = CGPoint(x: rect.midX, y: rect.midY)
        func circle(_ r: CGFloat) -> Path {
            Path(ellipseIn: CGRect(x: center.x - r, y: center.y - r, width: r * 2, height: r * 2))
        }
        switch progress.state {
        case .queued:
            context.stroke(circle(radius),
                           with: .color(.white.opacity(0.9)),
                           style: StrokeStyle(lineWidth: 2, dash: [3, 3]))
        case .active, .indeterminate:
            context.stroke(circle(radius), with: .color(.white.opacity(0.25)), lineWidth: 3)
            var arc = Path()
            let sweep = progress.state == .indeterminate ? 0.25 : max(progress.percent / 100, 0.02)
            arc.addArc(center: center, radius: radius,
                       startAngle: .degrees(-90), endAngle: .degrees(-90 + 360 * sweep),
                       clockwise: false)
            context.stroke(arc, with: .color(Self.buildSelection), lineWidth: 3)
            if progress.state == .active {
                context.draw(
                    Text("\(Int(progress.percent))")
                        .font(.system(size: 9, weight: .semibold, design: .monospaced))
                        .foregroundStyle(.white),
                    at: center)
            }
        case .done:
            context.fill(circle(radius), with: .color(Self.badgeDone))
            context.draw(Text("✓").font(.system(size: radius, weight: .bold))
                            .foregroundStyle(.white), at: center)
        case .error:
            context.fill(circle(radius), with: .color(Self.badgeError))
            context.draw(Text("!").font(.system(size: radius, weight: .bold))
                            .foregroundStyle(.white), at: center)
        }
        if rect.width > 90, !progress.label.isEmpty, progress.state != .done {
            let label = progress.state == .active
                ? "\(progress.label) · \(Int(progress.percent))%" : progress.label
            context.draw(
                Text(label)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.85)),
                at: CGPoint(x: center.x, y: center.y + radius + 10))
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

    private func pan(size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 3)
            .onChanged { value in
                if dragAnchor.value == nil { dragAnchor.value = camera.value }
                guard let anchor = dragAnchor.value else { return }
                var cam = anchor
                cam.centerLon = anchor.centerLon - Double(value.translation.width) / anchor.scale
                cam.centerLat = anchor.centerLat + Double(value.translation.height) / anchor.scale
                cam.clamp(in: size)
                camera.value = cam
            }
            .onEnded { _ in
                dragAnchor.value = nil
            }
    }

    /// Build mode, Qt semantics: click = select that tile (and make it
    /// active), ⌘-click = toggle in a multi-selection, ⇧-click = contiguous
    /// rectangle from the active tile. Modifiers come from AppKit at event
    /// time — SwiftUI tap gestures don't carry them.
    private func tileSelect(size: CGSize) -> some Gesture {
        SpatialTapGesture(count: 1)
            .onEnded { value in
                guard buildModel.mode == .build else { return }
                let flags = NSEvent.modifierFlags
                let coord = camera.value.coordinate(of: value.location, in: size)
                buildModel.click(lat: Int(floor(coord.lat)), lon: Int(floor(coord.lon)),
                                 command: flags.contains(.command),
                                 shift: flags.contains(.shift))
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

    // MARK: - Chrome

    private var legend: some View {
        HStack(spacing: 10) {
            if buildModel.mode == .build {
                legendSwatch(Self.buildSelection, "Selected")
                Text("built · color = ZL")
                    .foregroundStyle(.white.opacity(0.8))
                legendSwatch(Self.zlColor(15), "15")
                legendSwatch(Self.zlColor(16), "16")
                legendSwatch(Self.zlColor(17), "17")
                legendSwatch(Self.zlColor(18), "18")
                Text("▣ installed · * zones")
                    .foregroundStyle(.white.opacity(0.8))
            } else {
                legendDot(Self.magenta, "Airport")
                legendSwatch(Self.tintOrtho, "Ortho")
                legendSwatch(Self.tintMesh, "Mesh")
                legendSwatch(Self.tintLandmark, "Landmark")
            }
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

    /// Unobtrusive scan progress while the map populates live. Leaf view
    /// observing ProgressModel so its ticks never redraw the canvas.
    struct ScanProgressChip: View {
        @EnvironmentObject var progress: ProgressModel

        var body: some View {
            if let p = progress.scanProgress {
                HStack(spacing: 6) {
                    ProgressView(value: Double(p.done), total: Double(max(p.total, 1)))
                        .frame(width: 90)
                        .controlSize(.mini)
                    Text("\(p.done.formatted())/\(p.total.formatted())")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.white.opacity(0.8))
                }
                .padding(6)
                .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 6))
                .padding(8)
                .help("Scanning Custom Scenery — the map fills in as packages are found")
            }
        }
    }

    /// Bottom-right badge: the tile zoom level the current view equates to,
    /// so what's on screen correlates with the Build ZL setting. Flags when
    /// the view has out-zoomed the imagery source's ceiling (image upscales
    /// and blurs past that point).
    private var zoomChip: some View {
        let viewZL = max(2, Int(ceil(log2(camera.value.scale * 360 / 256))))
        let sourceMax = imagery.hasActiveSource ? imagery.activeMaxZL : nil
        let atLimit = sourceMax.map { viewZL > $0 } ?? false
        return HStack(spacing: 5) {
            Text("ZL \(viewZL)")
                .fontWeight(.semibold)
            if let sourceMax, atLimit {
                Image(systemName: "eye.trianglebadge.exclamationmark")
                Text("\(imagery.activeLabel ?? "source") max ZL \(sourceMax)")
            }
        }
        .font(.caption.monospacedDigit())
        .foregroundStyle(atLimit ? Color.orange : Color.secondary)
        .padding(.horizontal, 9)
        .padding(.vertical, 4)
        .background(.ultraThinMaterial, in: Capsule())
        .padding(8)
        .help(atLimit
              ? "The view is zoomed past the imagery source's finest zoom level — tiles are upscaled and blurry. Builds at higher ZLs would upscale the same data."
              : "The imagery zoom level matching the current view — compare with the Build ZL setting.")
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
        .help("Zoom (double-click the map to zoom in; drag to pan)")
    }

    private func zoom(by factor: Double) {
        var cam = camera.value
        cam.scale *= factor
        cam.clamp(in: canvasSize.value)
        camera.value = cam
    }
}
