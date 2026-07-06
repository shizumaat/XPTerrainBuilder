import Foundation
import SwiftUI
import SceneryKit

/// Equirectangular camera: world position of the view center plus zoom.
struct MapCamera: Equatable {
    var centerLon: Double = -40
    var centerLat: Double = 30
    /// Pixels per degree.
    var scale: Double = 3.4

    func point(lon: Double, lat: Double, in size: CGSize) -> CGPoint {
        CGPoint(x: size.width / 2 + (lon - centerLon) * scale,
                y: size.height / 2 - (lat - centerLat) * scale)
    }

    func coordinate(of point: CGPoint, in size: CGSize) -> (lon: Double, lat: Double) {
        (centerLon + (Double(point.x) - Double(size.width) / 2) / scale,
         centerLat - (Double(point.y) - Double(size.height) / 2) / scale)
    }

    mutating func clamp() {
        scale = min(max(scale, 1.2), 400)
        centerLat = min(max(centerLat, -85), 85)
        if centerLon < -180 { centerLon += 360 }
        if centerLon > 180 { centerLon -= 360 }
    }
}

/// Offline Natural Earth 110m land polygons, [[ [lon,lat], … ]].
enum LandData {
    static let polygons: [[CGPoint]] = {
        guard let url = Bundle.module.url(forResource: "land", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [[[Double]]]
        else { return [] }
        return raw.map { ring in
            ring.compactMap { pair in
                pair.count >= 2 ? CGPoint(x: pair[0], y: pair[1]) : nil
            }
        }
    }()
}

/// Everything the map needs to draw one pack, precomputed once per scan.
struct MapOverlays {
    struct Airport: Identifiable {
        var id: String { icao + packName }
        let icao: String
        let info: AirportInfo
        let packName: String
        let status: PackStatus
    }

    /// tile key -> kinds of coverage present (drives tile tinting).
    var tileKinds: [String: Set<PackKind>] = [:]
    var airports: [Airport] = []

    init(packs: [SceneryPack]) {
        for pack in packs where !pack.isLaminar {
            if pack.kind == .ortho || pack.kind == .mesh {
                for tile in pack.tiles {
                    tileKinds[tile, default: []].insert(pack.kind)
                }
            } else if pack.kind == .landmark {
                for tile in pack.tiles {
                    tileKinds[tile, default: []].insert(.landmark)
                }
            }
            for (icao, info) in pack.airports where info.latitude != 0 || info.longitude != 0 {
                airports.append(Airport(icao: icao, info: info,
                                        packName: pack.name, status: pack.status))
            }
        }
    }
}
