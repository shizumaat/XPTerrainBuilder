import Foundation

/// A longitude/latitude pair in degrees.
public struct GeoPoint: Sendable, Codable, Hashable {
    public let lon: Double
    public let lat: Double

    public init(lon: Double, lat: Double) {
        self.lon = lon
        self.lat = lat
    }
}
