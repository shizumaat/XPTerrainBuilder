import Foundation

/// X-Plane's 1°×1° tile grid: keys like "+41-073" (south-west corner).
public enum TileMath {
    public static func key(lat: Int, lon: Int) -> String {
        String(format: "%+03d%+04d", lat, lon)
    }

    public static func key(latitude: Double, longitude: Double) -> String {
        key(lat: Int(floor(latitude)), lon: Int(floor(longitude)))
    }

    /// "+41-073" -> (41, -73); nil for malformed names.
    public static func parse(_ key: String) -> (lat: Int, lon: Int)? {
        guard key.count == 7 else { return nil }
        let latPart = String(key.prefix(3))
        let lonPart = String(key.suffix(4))
        guard let lat = Int(latPart), let lon = Int(lonPart),
              abs(lat) <= 90, abs(lon) <= 180 else { return nil }
        return (lat, lon)
    }
}

