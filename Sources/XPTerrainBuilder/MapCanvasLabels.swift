import SwiftUI
import SceneryKit

/// The map's labels (issue #817): tile coordinate top-left and installed
/// imagery bottom-left on every tile big enough to carry them, and airport
/// marks + labels by size, placed without overlap (SceneryKit
/// `MapLabelLayout`, the rule the Qt map shares).
extension MapCanvasView {
    /// The airport layer for one camera: what is marked and what is
    /// labelled where. Built once per camera/viewport change and reused
    /// by every redraw that changes neither (imagery fading in, progress).
    struct AirportPlan {
        var defaultMarks = Path()
        var customMarks = Path()
        var radius: CGFloat = 2.2
        var labels: [(code: String, box: MapLabelLayout.Box, custom: Bool)] = []
    }

    static func makeAirportPlan(overlays: MapOverlays, cam: MapCamera, size: CGSize,
                                bounds: (minLon: Double, maxLon: Double,
                                         minLat: Double, maxLat: Double),
                                textScale: Double = TextScale.defaultValue) -> AirportPlan {
        var plan = AirportPlan()
        plan.radius = CGFloat(MapLabelLayout.markRadius(scale: cam.scale))
        func inView(_ info: AirportInfo) -> Bool {
            // One-degree margin: a mark just off-screen owns a label that
            // reaches into it.
            info.longitude > bounds.minLon - 1 && info.longitude < bounds.maxLon + 1
                && info.latitude > bounds.minLat - 1 && info.latitude < bounds.maxLat + 1
        }
        var candidates: [MapLabelLayout.Candidate] = []
        // `defaultAirports` is sorted largest class first, so the walk
        // stops at the first class this zoom does not mark — a wide view
        // never touches the tens of thousands of small fields.
        for airport in overlays.defaultAirports {
            guard MapLabelLayout.markVisible(sizeClass: airport.sizeClass, custom: false,
                                             scale: cam.scale) else { break }
            guard inView(airport.info) else { continue }
            let p = cam.point(lon: airport.info.longitude, lat: airport.info.latitude, in: size)
            candidates.append(.init(code: airport.icao, x: p.x, y: p.y,
                                    sizeClass: airport.sizeClass,
                                    runwayMeters: airport.runwayMeters, custom: false))
        }
        for airport in overlays.airports where inView(airport.info) {
            let p = cam.point(lon: airport.info.longitude, lat: airport.info.latitude, in: size)
            candidates.append(.init(code: airport.icao, x: p.x, y: p.y,
                                    sizeClass: airport.sizeClass,
                                    runwayMeters: airport.runwayMeters, custom: true))
        }
        let placed = MapLabelLayout.place(candidates, scale: cam.scale,
                                          markRadius: Double(plan.radius),
                                          textScale: textScale)
        let r = plan.radius
        for index in placed.marks {
            let c = candidates[index]
            let rect = CGRect(x: c.x - r, y: c.y - r, width: r * 2, height: r * 2)
            if c.custom { plan.customMarks.addEllipse(in: rect) } else { plan.defaultMarks.addEllipse(in: rect) }
        }
        plan.labels = placed.labels.map { (candidates[$0.index].code, $0.box, candidates[$0.index].custom) }
        return plan
    }

    /// Default marks first (one batched gray path), custom magenta on
    /// top, then the labels on their pills.
    func drawAirports(_ plan: AirportPlan, context: GraphicsContext) {
        let width = max(1.4, plan.radius * 0.4)
        context.stroke(plan.defaultMarks, with: .color(Self.defaultAirport), lineWidth: width)
        context.stroke(plan.customMarks, with: .color(Self.magenta.opacity(0.95)), lineWidth: width)
        for label in plan.labels {
            let box = CGRect(x: label.box.x, y: label.box.y,
                             width: label.box.width, height: label.box.height)
            context.fill(Path(roundedRect: box, cornerRadius: box.height / 2),
                         with: .color(.black.opacity(0.5)))
            context.draw(
                Text(label.code)
                    .font(.system(size: label.box.fontSize, weight: .semibold, design: .monospaced))
                    .foregroundStyle(label.custom ? Self.magentaLabel : Self.defaultAirportLabel),
                at: CGPoint(x: box.midX, y: box.midY))
        }
    }

    static let magentaLabel = Color(red: 0.95, green: 0.55, blue: 0.72)
    static let defaultAirportLabel = Color(white: 0.88)

    /// Tile coordinate (top-left) on every visible tile, installed imagery
    /// (bottom-left) on built tiles and on tiles another installed ortho
    /// pack covers (read from that pack's file names, #1227; `imagery ?`
    /// when they name no source).
    func drawTileLabels(context: GraphicsContext, size: CGSize, cam: MapCamera,
                        bounds: (minLon: Double, maxLon: Double, minLat: Double, maxLat: Double),
                        built: [BuildModel.TileCoord: O4TileInfo]?, orthoTiles: Set<Int32>?,
                        orthoImagery: [Int32: PackImagery]) {
        guard cam.scale >= MapLabelLayout.tileLabelMinScale else { return }
        let latLo = max(Int(floor(bounds.minLat)), -90), latHi = min(Int(floor(bounds.maxLat)), 89)
        let lonLo = max(Int(floor(bounds.minLon)), -180), lonHi = min(Int(floor(bounds.maxLon)), 179)
        guard latLo <= latHi, lonLo <= lonHi else { return }
        for lat in latLo...latHi {
            for lon in lonLo...lonHi {
                let rect = tileRect(lat: lat, lon: lon, cam: cam, size: size)
                drawPill(TileMath.key(lat: lat, lon: lon), context: context,
                         at: CGPoint(x: rect.minX + 4, y: rect.minY + 4), anchorTop: true)
                let coord = BuildModel.TileCoord(lat: lat, lon: lon)
                let key = Int32((lat + 90) * 360 + lon + 180)
                let imagery: String?
                if let info = built?[coord] {
                    imagery = MapLabelLayout.imageryLabel(provider: info.provider, zl: info.zl,
                                                          hasZones: info.hasZones)
                } else if orthoTiles?.contains(key) == true {
                    let pack = orthoImagery[key]
                    imagery = MapLabelLayout.imageryLabel(provider: pack?.provider, zl: pack?.zl,
                                                          hasZones: false)
                } else {
                    imagery = nil
                }
                if let imagery {
                    drawPill(imagery, context: context,
                             at: CGPoint(x: rect.minX + 4, y: rect.maxY - 4), anchorTop: false)
                }
            }
        }
    }

    /// `text` on a translucent pill whose top-left (or bottom-left) corner
    /// is `point` — readable over any imagery and over the base map.
    private func drawPill(_ text: String, context: GraphicsContext, at point: CGPoint,
                          anchorTop: Bool) {
        let resolved = context.resolve(
            Text(text)
                .font(.system(size: TextScale.scaled(MapLabelLayout.tileLabelFont, textScale),
                              weight: .medium, design: .monospaced))
                .foregroundStyle(.white.opacity(0.92)))
        let textSize = resolved.measure(in: CGSize(width: 400, height: 40))
        let pill = CGRect(x: point.x, y: anchorTop ? point.y : point.y - textSize.height - 4,
                          width: textSize.width + 8, height: textSize.height + 4)
        context.fill(Path(roundedRect: pill, cornerRadius: pill.height / 2),
                     with: .color(.black.opacity(0.55)))
        context.draw(resolved, at: CGPoint(x: pill.minX + 4, y: pill.minY + 2), anchor: .topLeading)
    }
}

/// Holds the last `AirportPlan` and the camera/viewport it was built for.
/// Not published: the canvas reads it while drawing, never observes it.
final class AirportPlanCache: ObservableObject {
    struct Key: Equatable {
        let camera: MapCamera
        let size: CGSize
        let defaults: Int
        let customs: Int
        let textScale: Double
    }

    private var key: Key?
    private var plan = MapCanvasView.AirportPlan()

    func plan(for key: Key, make: () -> MapCanvasView.AirportPlan) -> MapCanvasView.AirportPlan {
        if key != self.key {
            plan = make()
            self.key = key
        }
        return plan
    }
}
