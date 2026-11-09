import Foundation

/// One airport of a Gateway offer (engine `GatewayAirports.items`, issue
/// #1989): `flatten` (X-Plane draws its Global Airports entry, which
/// carries `1302 flatten 1`), `update` (the Gateway pack the app installed
/// has a newer Gateway version) or, in an outcome, `installed`.
public struct O4GatewayAirport: Sendable, Equatable, Identifiable {
    public let icao: String
    public let name: String
    public let reason: String
    public let installedId: Int
    public let latestId: Int
    public let pack: String
    public var id: String { icao }

    public init(icao: String, name: String, reason: String,
                installedId: Int, latestId: Int, pack: String) {
        self.icao = icao
        self.name = name
        self.reason = reason
        self.installedId = installedId
        self.latestId = latestId
        self.pack = pack
    }

    /// The row's checkbox title.
    public var title: String { name.isEmpty ? icao : "\(icao) \(name)" }
    /// The row's one-line explanation.
    public var detail: String {
        (O4GatewayAirportsCopy.reasonDetails[reason] ?? "")
            .replacingOccurrences(of: "{installed}", with: "\(installedId)")
            .replacingOccurrences(of: "{latest}", with: "\(latestId)")
    }
}

/// The tile's Gateway airports as ONE question (engine `GatewayAirports`,
/// capability `gateway_airports`, issue #1989). `state` "found" (a build)
/// or "ask" (the report): Install sends `gateway_airports` "install" with
/// the checked ICAOs and every ICAO shown, Never for these airports
/// "never", Not now nothing. The other states are a command's outcome.
public struct O4GatewayAirports: Sendable, Equatable, Identifiable {
    public let lat: Int
    public let lon: Int
    public let items: [O4GatewayAirport]
    public let files: [String]
    public let state: String
    public let error: String

    /// One question per tile and airport set.
    public var id: String {
        "\(lat)|\(lon)|" + items.map { "\($0.icao):\($0.reason)" }.joined(separator: ",")
    }

    public init(lat: Int, lon: Int, items: [O4GatewayAirport],
                files: [String], state: String, error: String) {
        self.lat = lat
        self.lon = lon
        self.items = items
        self.files = files
        self.state = state
        self.error = error
    }

    /// The rows to offer (each checked when the question opens).
    public var offers: [O4GatewayAirport] {
        items.filter { $0.reason == "flatten" || $0.reason == "update" }
    }
    /// A question to ask: a build's or the report's, with a row in it.
    public var asks: Bool { (state == "found" || state == "ask") && !offers.isEmpty }
}

/// The copy, VERBATIM and identical to the Qt question
/// (`Ortho4XP/src/O4_Qt_Gateway_Airports.py`, whose twin
/// `tests/test_qt_gateway_airports.py` reads this file to pin the parity).
public enum O4GatewayAirportsCopy {
    public static let title = "Install airports from the X-Plane Gateway?"

    public static let body = "X-Plane flattens the ground under these "
        + "airports, so it does not draw the graded ground this app builds. "
        + "Choose the airports to install:"

    /// Per reason: its explanation.
    public static let reasonDetails: [String: String] = [
        "flatten": "Install the latest Gateway version without the flatten "
            + "tag.",
        "update": "A newer Gateway version is available ({installed} → "
            + "{latest}); it installs without the flatten tag.",
    ]

    public static let detail = "Each airport is installed as a custom "
        + "airport pack in Custom Scenery and filed with your airports. "
        + "Every build of its tile checks the Gateway for a newer version."

    public static let installButton = "Install"
    public static let notNowButton = "Not now"
    public static let neverButton = "Never for these airports"
}
