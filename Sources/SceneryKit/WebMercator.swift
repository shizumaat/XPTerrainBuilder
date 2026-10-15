import Foundation

// Moved from the app's ImageryModel.swift so the 3D preview's imagery
// drape (PatchDrape) and the map share one tile math.

/// Web-mercator (slippy-map) tile math: the map's imagery layer and the
/// 3D preview's drape.
public enum WebMercator {
    public static let maxLat = 85.05112878

    /// Fractional tile y for a latitude at zoom z.
    public static func tileY(lat: Double, z: Int) -> Double {
        let clamped = min(max(lat, -maxLat), maxLat)
        let rad = clamped * .pi / 180
        return (1 - asinh(tan(rad)) / .pi) / 2 * Double(1 << z)
    }

    /// Latitude of a (fractional) tile-row boundary at zoom z.
    public static func lat(tileY y: Double, z: Int) -> Double {
        let n = .pi * (1 - 2 * y / Double(1 << z))
        return atan(sinh(n)) * 180 / .pi
    }

    public static func tileX(lon: Double, z: Int) -> Double {
        (lon + 180) / 360 * Double(1 << z)
    }

    public static func lon(tileX x: Double, z: Int) -> Double {
        x / Double(1 << z) * 360 - 180
    }
}
